"""Opt-in diagnostic fixture. Captures ONLY exact public_examples.json inputs.
Never configured in production; the real adapter result is returned unchanged.
"""
import json
from pathlib import Path
from report_editor.adapters.claude_cli import ClaudeCliAdapter

class PublicCandidate(ClaudeCliAdapter):
    def edit(self,request,deadline):
        approved=json.loads(Path(__file__).with_name('public_examples.json').read_text())
        if request not in approved.values():
            raise ValueError('not_an_approved_public_fixture')
        result=super().edit(request,deadline)
        Path(self.config['public_capture_path']).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return result
