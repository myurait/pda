"""Offline assertion/aggregation of observed M2 evidence, never synthetic run output."""
from pathlib import Path
import ast, json, py_compile
ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/'evidence'/f'{name}.json').read_text())

cases=[]
for i in range(1,5):
    name=f'hermes-final-crash-{i}'; d=load(name)
    assert d['injection_rc']==0 and d['recovered'] and d['preserved'] and d['semantic']['passed']
    assert d['before']['pid'] != d['after']['pid']
    cases.append({'id':name,'control_s':d['recovery_s'],'readback_s':d['semantic']['elapsed_s'],'pass':True})
for kind in ('bytes','inodes','memory'):
    name='hermes-final-resource-'+kind;d=load(name)
    assert d['health_while_limited'] and d['preserved'] and d['semantic']['passed'] and d['cleanup_rc']==0
    assert d['injection_rc']==(137 if kind=='memory' else 0)
    if kind=='memory': assert 'oom_kill 1' in d['cgroup_memory_events']
    else: assert ast.literal_eval(d['stdout'].strip())['errno']==28
    cases.append({'id':name,'control_s':0,'injection_s':d['injection_s'],'readback_s':d['semantic']['elapsed_s'],'pass':True,'scope':'work tmpfs or container memory only; persistent home is not hard-quota bounded'})
for mode in ('stop','orphan'):
    name='hermes-final-inflight-'+mode;d=load(name);s=load(name+'-semantic');a=load(name+'-assessment')
    assert d['injection_rc']==0 and d['single_effect'] and not d['delayed_tool_remaining'] and d['native_terminal_preserved'] and d['same_run_replayed'] and s['passed']
    assert d['receipt_before']==d['receipt_after']=='accepted-1\n'
    b=a['last']['state']['body'];assert b['status']=='completed' and 'accepted-1' in b['output']
    cases.append({'id':name,'control_s':d['recovery_s'],'readback_s':s['elapsed_s'],'native_effect_assessment_s':a['elapsed_s'],'pass':True})
for name in ('hermes-bad-update','hermes-compatible-restore','hermes-final-memory-outage','hermes-model-outage'):
    d=load(name);assert d['preserved'] and d['semantic']['passed']
    recovery=d.get('standard_restore_s',d.get('dependency_restore_s'))
    assert recovery is not None
    cases.append({'id':name,'control_s':d.get('control_s',recovery),'standard_restore_s':recovery,'readback_s':d['semantic']['elapsed_s'],'pass':True})
r=load('hermes-repair-capability-verification');assert r['preserved'] and ast.literal_eval(r['actual_readback'].strip())=='repaired-violet-739\n' and r['reply']['last']['state']['body']['status']=='completed'
cases.append({'id':'hermes-repair-capability-verification','model_s':r['reply']['elapsed_s'],'pass':True,'scope':'bounded file repair, not body/host update authority'})
assert len(cases)==14 and len({c['id'] for c in cases})==14
for c in cases:
    if 'control_s' in c: assert c['control_s']<120
    c['sum_of_recorded_components_s']=round(sum(c.get(k,0) for k in ('control_s','readback_s','native_effect_assessment_s')),3)
    assert c['sum_of_recorded_components_s']<300
custody=load('hermes-message-custody-self-check');assert custody['old_message_count']>0 and not custody['missing_ids'] and not custody['changed_committed_message_ids']
for name in ('hermes-cleanup','letta-cleanup'):
    d=load(name)
    assert not d.get('remaining_containers',d.get('remaining',''))
for p in ROOT.glob('*.py'): py_compile.compile(str(p),doraise=True)
for p in (ROOT/'evidence').glob('*.json'): json.loads(p.read_text())
result={'task_id':'t_ec4c52b9','technical_verdict':'LIMITED_M3_CANDIDATE_SELECTED','independent_review':False,'production_adoption':False,'production_change':False,'selected':'Hermes 0.21.1 clean source, minimal standard Docker deployment','cases':cases,'selected_case_count':len(cases),'max_control_or_standard_restore_s':max(c.get('control_s',0) for c in cases),'max_sum_of_recorded_components_s':max(c['sum_of_recorded_components_s'] for c in cases),'timing_caveat':'Sums combine separate recorded intervals and exclude observer bookkeeping; they are not a separately sampled whole-drill wall clock. State/model-available recovery thresholds remain 120/300 seconds. Model-provider outage itself is not healed by restarting the body.','custody':custody,'tested_violation_counts':{'owner_rescue':0,'committed_message_loss_at_restore':len(custody['missing_ids']),'stopped_job_auto_restart':0,'blind_replay_effects':0},'letta':{'decision':'NOT_SELECTED_THIS_CONFIGURATION','baseline':'INCONCLUSIVE; no successful Letta-mediated model readback','source':'official npm 0.31.13; gitHead a501f8c4557e49812d66c7b801eff0ade5516343','plain_restart':load('letta-plain-restart'),'not_run':'Full fault matrix: baseline precondition unmet'},'managed_hybrid':{'decision':'UNVERIFIED_NOT_REJECTED_ON_PERFORMANCE','representatives':['Letta Cloud managed sandbox','Letta Cloud with BYOM','Cloudflare Agents / Durable Objects','OpenAI Responses / Conversations with local execution']},'limits':['Stopped/quiesced pre-change full-state restore; not arbitrary rollback zero RPO','Persistent state mount lacks hard aggregate byte/inode quota','Synthetic file effect, not real business sink or universal stop/send fence','Native API idempotency retention is finite; long-window reconciliation remains M3','No whole-host/disk loss, external-provider continuity, actual production ingress preservation during network reconfiguration','No proof of candidate self-update authority or independent recovery of current production PDA','Attention, forgetting, dormant skills, activity UI, real work handoff, migration and exit remain M3']}
(ROOT/'VERDICT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'verified_selected_cases':len(cases),'max_control_or_restore_s':result['max_control_or_standard_restore_s'],'max_recorded_component_sum_s':result['max_sum_of_recorded_components_s'],'preserved_committed_messages':custody['old_message_count'],'independent_review':False},ensure_ascii=False))
