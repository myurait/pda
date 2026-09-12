"""Adapter worker protocol. stdin/stdout only; no transcripts or runtime hooks."""
import importlib
import json
import sys
from pathlib import Path

# This script also runs from installed plugin directories, without installation.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    try:
        # Schema-valid UTF-8 reports can exceed 128KB when fields repeat
        # draft fragments; cap the complete envelope without truncating them.
        payload=sys.stdin.buffer.read(4 * 1024 * 1024 + 1)
        if len(payload)>4 * 1024 * 1024:
            raise ValueError('input_limit')
        envelope=json.loads(payload)
        config=envelope['adapter']
        module,cls=config['factory'].split(':',1)
        adapter=getattr(importlib.import_module(module),cls)(config)
        result=adapter.edit(envelope['request'],envelope['deadline'])
        print(json.dumps({'result':result},ensure_ascii=False),flush=True)
    except Exception:
        # Never print exception text: SDK errors may contain prompt/credentials.
        print(json.dumps({'error':'adapter_failure'}),flush=True)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
