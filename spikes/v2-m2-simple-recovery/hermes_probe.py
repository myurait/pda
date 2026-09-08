"""One-shot setup/inspection for the Hermes trial; not a recovery service."""
from pathlib import Path
import json, os, secrets, shlex, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'
SOURCE = RUNTIME / 'hermes'
HOME = RUNTIME / 'hermes-home'
NAME = 'm2proof-hermes'

def docker(*args, timeout=60):
    return subprocess.run(['sg', 'docker', '-c', shlex.join(['docker', *map(str, args)])], capture_output=True, text=True, timeout=timeout)

def record(name, obj):
    path = ROOT / 'evidence' / (name + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

if __name__ == '__main__':
    assert not HOME.exists(), 'Refuse to overwrite trial state'
    assert docker('inspect', NAME).returncode != 0, 'Trial container already exists'
    HOME.mkdir(mode=0o700)
    (HOME / 'memories').mkdir()
    (HOME / 'memories' / 'MEMORY.md').write_text('Synthetic continuity memory: project ORCHID uses marker violet-739. Preserve stopped and uncertain activities; do not execute them.\n')
    shutil.copyfile(ROOT / 'hermes-config.yaml', HOME / 'config.yaml')
    # Existing, authorized PDA-local provider. No other account, login or provider.
    shutil.copyfile('/home/user/.hermes/auth.json', HOME / 'auth.json')
    os.chmod(HOME / 'auth.json', 0o600)
    envpath = RUNTIME / 'hermes-env'
    envpath.write_text('API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\nAPI_SERVER_PORT=19450\nAPI_SERVER_KEY=' + secrets.token_hex(24) + '\nHERMES_HOME=/home/proof/.hermes\nHOME=/home/proof\nPYTHONDONTWRITEBYTECODE=1\nPYTHONUNBUFFERED=1\n')
    envpath.chmod(0o600)
    python = SOURCE / '.venv/bin/python'
    python_root = python.resolve().parent.parent
    result = docker('run', '-d', '--name', NAME, '--init', '--restart', 'unless-stopped',
        '--user', '1000:1000', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--memory', '2g', '--memory-swap', '2g', '--cpus', '2', '--pids-limit', '96',
        '--log-opt', 'max-size=4m', '--log-opt', 'max-file=2',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m,nr_inodes=4096,uid=1000,gid=1000',
        '--tmpfs', '/work:rw,nosuid,nodev,size=64m,nr_inodes=2048,uid=1000,gid=1000',
        '--tmpfs', '/home/proof:rw,nosuid,nodev,size=16m,uid=1000,gid=1000',
        '--mount', f'type=bind,src={SOURCE},dst={SOURCE},readonly',
        '--mount', f'type=bind,src={python_root},dst={Path(os.readlink(python)).parent.parent},readonly',
        '--mount', f'type=bind,src={HOME},dst=/home/proof/.hermes',
        '--workdir', str(SOURCE), '--env-file', str(envpath),
        '-p', '127.0.0.1:19450:19450', 'python:3.11-bookworm',
        str(python), '-m', 'hermes_cli.main', 'gateway', 'run')
    record('hermes-start', {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
                            'upstream_patch': False, 'supervisor': 'Docker on-failure:3',
                            'trial_only': True, 'model_auth': 'existing PDA-local openai-codex; private copy, not committed'})
    print(result.stdout, result.stderr)
    sys.exit(result.returncode)
