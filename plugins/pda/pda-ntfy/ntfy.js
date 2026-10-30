import { readFile } from "node:fs/promises";

// ntfy.env は NTFY_TOPIC=... と NTFY_SERVER=... の行を持つ。トピックはパスワードとして働くので、
// 値は送信にだけ使い、ログやエラーには出さない。
export async function loadNtfyConfig(file) {
  const text = await readFile(file, "utf8");
  const values = {};
  for (const line of text.split("\n")) {
    const match = line.match(/^\s*(?:export\s+)?(NTFY_TOPIC|NTFY_SERVER)\s*=\s*(.*?)\s*$/);
    if (match) values[match[1]] = match[2].replace(/^(["'])(.*)\1$/, "$2");
  }
  if (!values.NTFY_TOPIC) throw Object.assign(new Error("NTFY_TOPIC is missing"), { code: "NO_TOPIC" });
  return { topic: values.NTFY_TOPIC, server: (values.NTFY_SERVER || "https://ntfy.sh").replace(/\/+$/, "") };
}

// トピックは URL ではなく JSON の本文に入れる (URL は各所に残りやすい)。
export async function sendNtfy({ envFile, timeoutMs, title, message, click, priority, tags, fetchImpl = fetch }) {
  const { topic, server } = await loadNtfyConfig(envFile);
  const payload = { topic, title, message };
  if (click) payload.click = click;
  if (priority) payload.priority = priority;
  if (tags?.length) payload.tags = tags;
  const response = await fetchImpl(server, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw Object.assign(new Error(`ntfy responded ${response.status}`), { code: `HTTP_${response.status}` });
}
