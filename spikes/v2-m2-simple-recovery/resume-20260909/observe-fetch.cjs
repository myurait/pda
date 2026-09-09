// Diagnostic-only: observe synthetic local-provider requests, no rewrites.
const fs = require('node:fs');
const original = globalThis.fetch;
globalThis.fetch = async function(input, init) {
  const url = typeof input === 'string' ? input : (input instanceof URL ? input.href : input.url);
  if (url.startsWith('http://model:11434/') && init && typeof init.body === 'string') {
    fs.appendFileSync('/home/node/.letta/m2-wire.jsonl', JSON.stringify({url, at: new Date().toISOString(), body: JSON.parse(init.body)})+'\n', {mode:0o600});
  }
  return original.apply(this, arguments);
};
