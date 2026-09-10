#!/bin/bash
set -euo pipefail

AGENT_HOST="${PDA_AGENT_HOST:-192.168.0.59}"
AGENT_USER="${PDA_AGENT_USER:-user}"
AGENT_SSH_PORT="${PDA_AGENT_SSH_PORT:-22}"
REVERSE_PORT="${PDA_REVERSE_PORT:-22037}"
AGENT_HOSTKEY_SHA256="SHA256:UtsFq2x11m/66njM8DRN9jO27CTa/2pnDUZtYV5jqMA"
AGENT_CONTROL_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJUeP7vJxCBLE+OKQf46ow8EeubU0sgg9tSgzO4HXD8Q agent-node-to-main"
LABEL="com.pda.agent-node-reverse-ssh"
TUNNEL_KEY="$HOME/.ssh/pda_reverse_tunnel_ed25519"
AGENT_KNOWN_HOSTS="$HOME/.ssh/pda_agent_node_known_hosts"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
STDOUT_LOG="$HOME/Library/Logs/$LABEL.out.log"
STDERR_LOG="$HOME/Library/Logs/$LABEL.err.log"

say() { printf '\n[%s] %s\n' "$1" "$2"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || fail "This bootstrap must run on the macOS development PC."
for cmd in /usr/bin/ssh /usr/bin/ssh-keygen /usr/bin/ssh-keyscan /usr/bin/nc /bin/launchctl /usr/sbin/systemsetup; do
  [ -x "$cmd" ] || fail "Required command is missing: $cmd"
done

mkdir -p "$HOME/.ssh" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
chmod 700 "$HOME/.ssh"

say 1 "Pinning agent-node's ED25519 host key."
tmp_scan="$(mktemp)"
trap 'rm -f "$tmp_scan"' EXIT
/usr/bin/ssh-keyscan -T 5 -p "$AGENT_SSH_PORT" -t ed25519 "$AGENT_HOST" >"$tmp_scan" 2>/dev/null || fail "Could not fetch agent-node's SSH host key."
actual_fp="$(/usr/bin/ssh-keygen -lf "$tmp_scan" | /usr/bin/awk '{print $2; exit}')"
[ "$actual_fp" = "$AGENT_HOSTKEY_SHA256" ] || fail "agent-node host-key mismatch: expected $AGENT_HOSTKEY_SHA256, got $actual_fp"
cp "$tmp_scan" "$AGENT_KNOWN_HOSTS"
chmod 600 "$AGENT_KNOWN_HOSTS"

SSH_BASE=(/usr/bin/ssh -p "$AGENT_SSH_PORT" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$AGENT_KNOWN_HOSTS")
"${SSH_BASE[@]}" "$AGENT_USER@$AGENT_HOST" true || fail "Existing non-interactive SSH authentication to agent-node did not work."

say 2 "Enabling macOS Remote Login if localhost:22 is not listening."
if ! /usr/bin/nc -z 127.0.0.1 22 >/dev/null 2>&1; then
  printf '%s\n' "macOS will ask for your local administrator password once. Hermes never receives it."
  # systemsetup can report a permission refusal on stdout, not stderr.
  # Keep both streams visible and handle failure before errexit hides the fix.
  if sudo /usr/sbin/systemsetup -setremotelogin on; then
    :
  else
    remote_login_status=$?
    fail "Could not enable Remote Login (exit $remote_login_status). Open System Settings > General > Sharing > Remote Login on this Mac, turn it on, allow only your login user, then rerun this script. You do not need to grant Terminal Full Disk Access just to finish this setup."
  fi
fi
/usr/bin/nc -z 127.0.0.1 22 >/dev/null 2>&1 || fail "Remote Login is still unavailable on localhost:22. Enable System Settings > General > Sharing > Remote Login, then rerun this script."

say 3 "Authorizing agent-node's dedicated login key on this Mac."
auth_file="$HOME/.ssh/authorized_keys"
touch "$auth_file"
chmod 600 "$auth_file"
control_blob="$(printf '%s\n' "$AGENT_CONTROL_PUBKEY" | /usr/bin/awk '{print $2}')"
if ! /usr/bin/grep -Fq "$control_blob" "$auth_file"; then
  printf 'from="127.0.0.1",restrict %s\n' "$AGENT_CONTROL_PUBKEY" >>"$auth_file"
fi

say 4 "Creating a dedicated key for the Mac-to-agent-node tunnel."
if [ ! -f "$TUNNEL_KEY" ]; then
  /usr/bin/ssh-keygen -q -t ed25519 -N '' -C 'main-to-agent-node-reverse-tunnel' -f "$TUNNEL_KEY"
fi
chmod 600 "$TUNNEL_KEY"
chmod 644 "$TUNNEL_KEY.pub"
TUNNEL_PUB="$(<"$TUNNEL_KEY.pub")"
case "$TUNNEL_PUB" in
  ssh-ed25519\ *) ;;
  *) fail "Unexpected tunnel public-key format." ;;
esac
# authorized_keys requires host:port; bare "none" is sshd_config-only.
# Reserve an absolute .invalid name so real direct destinations stay denied.
TUNNEL_AUTH_LINE="restrict,port-forwarding,permitopen=\"pda-no-direct.invalid.:1\",permitlisten=\"127.0.0.1:${REVERSE_PORT}\",command=\"/bin/false\" $TUNNEL_PUB"
TUNNEL_AUTH_B64="$(printf '%s' "$TUNNEL_AUTH_LINE" | /usr/bin/base64 | /usr/bin/tr -d '\n')"
"${SSH_BASE[@]}" "$AGENT_USER@$AGENT_HOST" "PDA_KEY_LINE_B64='$TUNNEL_AUTH_B64' /usr/bin/python3 -c 'import base64, os; from pathlib import Path; line=base64.b64decode(os.environ[\"PDA_KEY_LINE_B64\"]).decode(); parts=line.split(); i=parts.index(\"ssh-ed25519\"); blob=parts[i+1]; d=Path.home()/\".ssh\"; d.mkdir(mode=0o700, exist_ok=True); p=d/\"authorized_keys\"; old=p.read_text().splitlines() if p.exists() else []; old=[x for x in old if not (blob in x and \"main-to-agent-node-reverse-tunnel\" in x)]; p.write_text(\"\\n\".join(old+[line])+\"\\n\"); p.chmod(0o600)'" || fail "Could not register the tunnel key on agent-node."

say 5 "Installing a persistent per-user LaunchAgent."
cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/ssh</string>
    <string>-n</string>
    <string>-NT</string>
    <string>-p</string>
    <string>$AGENT_SSH_PORT</string>
    <string>-i</string>
    <string>$TUNNEL_KEY</string>
    <string>-o</string>
    <string>BatchMode=yes</string>
    <string>-o</string>
    <string>IdentitiesOnly=yes</string>
    <string>-o</string>
    <string>ExitOnForwardFailure=yes</string>
    <string>-o</string>
    <string>ServerAliveInterval=30</string>
    <string>-o</string>
    <string>ServerAliveCountMax=3</string>
    <string>-o</string>
    <string>StrictHostKeyChecking=yes</string>
    <string>-o</string>
    <string>UserKnownHostsFile=$AGENT_KNOWN_HOSTS</string>
    <string>-R</string>
    <string>127.0.0.1:$REVERSE_PORT:127.0.0.1:22</string>
    <string>$AGENT_USER@$AGENT_HOST</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>$STDOUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$STDERR_LOG</string>
</dict>
</plist>
PLIST
chmod 600 "$PLIST"
/usr/bin/plutil -lint "$PLIST" >/dev/null
/bin/launchctl bootout "gui/$UID/$LABEL" >/dev/null 2>&1 || true
/bin/launchctl bootstrap "gui/$UID" "$PLIST"
/bin/launchctl enable "gui/$UID/$LABEL"
/bin/launchctl kickstart -k "gui/$UID/$LABEL"

say 6 "Waiting for the reverse listener and testing an SSH command back to this Mac."
listener_ok=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if "${SSH_BASE[@]}" "$AGENT_USER@$AGENT_HOST" "/usr/bin/python3 -c 'import socket; s=socket.create_connection((\"127.0.0.1\", $REVERSE_PORT), 2); s.close()'" >/dev/null 2>&1; then
    listener_ok=1
    break
  fi
  sleep 1
done
if [ "$listener_ok" -ne 1 ]; then
  printf '%s\n' "LaunchAgent stderr follows:" >&2
  [ -f "$STDERR_LOG" ] && /usr/bin/tail -n 30 "$STDERR_LOG" >&2 || true
  fail "Reverse listener did not appear on agent-node:127.0.0.1:$REVERSE_PORT."
fi

DEV_USER="$(id -un)"
REMOTE_RESULT="$("${SSH_BASE[@]}" "$AGENT_USER@$AGENT_HOST" "/usr/bin/ssh -i /home/user/.ssh/id_ed25519_devpc -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new -p $REVERSE_PORT '$DEV_USER@127.0.0.1' 'printf \"user=\"; id -un; printf \" host=\"; hostname; printf \" os=\"; uname -s'" 2>&1)" || {
  printf '%s\n' "$REMOTE_RESULT" >&2
  fail "The reverse TCP tunnel exists, but SSH authentication back into the Mac failed."
}

say OK "End-to-end reverse SSH is working."
printf '%s\n' "$REMOTE_RESULT"
printf 'agent endpoint: 127.0.0.1:%s\n' "$REVERSE_PORT"
printf 'macOS user: %s\n' "$DEV_USER"
printf 'LaunchAgent: %s\n' "$PLIST"
printf 'stderr log: %s\n' "$STDERR_LOG"
