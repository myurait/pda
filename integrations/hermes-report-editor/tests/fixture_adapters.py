"""Interchangeable process adapters used only by deterministic regressions."""
import time
from pathlib import Path

class Paragraphs:
    def __init__(self,config):self.config=config
    def edit(self,request,deadline):
        return {'text':'\n'.join([request['purpose']]+request['verified_facts']+request['failures_unmet_unknown']), 'finish_reason':'stop','calls':1,'usage':None}

class Slow:
    def __init__(self,config):
        self.config=config
        self.marker=Path(config['marker'])
        self.marker.write_text('started')
        if config['mode']=='queue':time.sleep(30)
    def edit(self,request,deadline):
        # Simulate SDK retries or cleanup before the external call returns.
        time.sleep(30)
        self.marker.with_suffix('.late').write_text('late')
        return Compact({}).edit(request,deadline)

class Failure:
    def __init__(self,config):self.config=config
    def edit(self,request,deadline):
        mode=self.config['mode']
        if mode in {'raise','auth'}:raise RuntimeError('synthetic failure')
        r=Compact({}).edit(request,deadline)
        if mode=='empty':r['text']=''
        if mode=='cut':r['finish_reason']='length'
        if mode=='format':r['text']='```'+r['text']+'```'
        if mode=='missing':r['text']=request['purpose']
        if mode=='numbers':r['text']+='さらに9件です。'
        if mode=='extra_claim':r['text']+='本番も完全に成功しました。'
        return r

class Compact:
    def __init__(self, config):self.config=config
    def edit(self, request, deadline):
        return {'text':''.join([request['purpose']]+request['verified_facts']+request['failures_unmet_unknown']+request['candidates_reasons']+request['recommendations']+request['decisions_required']), 'finish_reason':'stop','calls':1,'usage':None}
