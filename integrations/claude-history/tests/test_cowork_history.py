"""Synthetic Cowork originals; integration is verified separately on Mac."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_history import load_reader, transcript, SOURCE

ACCOUNT='11111111-1111-4111-8111-111111111111'
ORG='22222222-2222-4222-8222-222222222222'
DESKTOP='local_33333333-3333-4333-8333-333333333333'
SID='44444444-4444-4444-8444-444444444444'

def cowork(root):
    folder=root/ACCOUNT/ORG
    folder.mkdir(parents=True)
    (folder/(DESKTOP+'.json')).write_text(json.dumps({'sessionId':DESKTOP,'cliSessionId':SID,'title':'Cowork原文','isArchived':False,'createdAt':1,'lastActivityAt':2}))
    path=transcript(folder/DESKTOP/'.claude/projects',project='-sessions-task',session=SID)
    return path

def test_cowork_cli_lists_originals_and_preserves_desktop_identity(tmp_path):
    path=cowork(tmp_path)
    before=(path.read_bytes(),path.stat().st_mtime_ns)
    p=subprocess.run([sys.executable,'-B',str(SOURCE),'list','--source=desktop-cowork','--root',str(tmp_path)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    r=json.loads(p.stdout)
    assert r['source_kind']=='claude-desktop-cowork'
    assert r['scan_complete'] is True
    assert r['coverage_complete'] is False
    assert r['total']==1
    row=r['items'][0]
    assert row['session_id']==SID
    assert row['desktop_session_id']==DESKTOP
    assert row['organization_id']==ORG
    assert row['project']==str(Path(ACCOUNT)/ORG/DESKTOP/'.claude/projects/-sessions-task')
    assert row['messages']==2
    assert row['source_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert before==(path.read_bytes(),path.stat().st_mtime_ns)


def test_cowork_search_to_read_roundtrip_and_pagination(tmp_path):
    path=cowork(tmp_path)
    reader=load_reader()
    r=reader.query(tmp_path,source='desktop-cowork',action='search',search='日本語')
    assert r['total']==1
    hit=r['items'][0]
    assert hit['line']==1
    assert hit['message_index']==0
    r=reader.query(tmp_path,source='desktop-cowork',action='read',session_id=SID,
                   project=hit['project'],limit=1,text_limit=3)
    assert r['items'][0]['text']=='日本語'
    assert r['items'][0]['text_next_offset']==3
    assert r['items'][0]['source_sha256']==hit['source_sha256']
    assert r['next_offset']==1
    r=reader.query(tmp_path,source='desktop-cowork',action='read',session_id=SID,
                   offset=1,limit=1)
    assert r['items'][0]['role']=='assistant'
    assert r['items'][0]['line']==2
    assert r['next_offset'] is None
    with pytest.raises(ValueError,match='not found'):
        reader.query(tmp_path,source='desktop-cowork',action='read',session_id='missing')


@pytest.mark.parametrize('args',[{'limit':0},{'offset':-1},{'text_offset':-1},
                                  {'text_limit':0},{'action':'search','search':' '}])
def test_cowork_rejects_invalid_queries(tmp_path,args):
    cowork(tmp_path)
    with pytest.raises(ValueError):
        load_reader().query(tmp_path,source='desktop-cowork',**args)


def test_cowork_bounded_scan(tmp_path,monkeypatch):
    cowork(tmp_path)
    reader=load_reader()
    monkeypatch.setattr(reader,'COWORK_AGGREGATE_LIMIT',8,raising=False)
    with pytest.raises(ValueError,match='size limit'):
        reader.query(tmp_path,source='desktop-cowork')


def test_cowork_includes_prior_runs_but_not_nested_subagents(tmp_path):
    path=cowork(tmp_path)
    old=transcript(path.parent.parent,project=path.parent.name,session='55555555-5555-4555-8555-555555555555')
    transcript(path.parent/SID/'subagents',project='nested')
    rows=load_reader().query(tmp_path,source='desktop-cowork')['items']
    assert {r['session_id'] for r in rows}=={SID,old.stem}
    assert {r['desktop_session_id'] for r in rows}=={DESKTOP}


def test_cowork_refuses_symlink_roots_and_omits_aliases(tmp_path):
    root=tmp_path/'original';path=cowork(root)
    alias=tmp_path/'alias';alias.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):
        load_reader().query(alias,source='desktop-cowork')
    (root/'alias-account').symlink_to(root/ACCOUNT,target_is_directory=True)
    (path.parent/'alias.jsonl').symlink_to(path)
    r=load_reader().query(root,source='desktop-cowork')
    assert r['total']==1


def test_cowork_reports_in_progress_tail(tmp_path):
    path=cowork(tmp_path)
    with path.open('a') as f:f.write('{')
    r=load_reader().query(tmp_path,source='desktop-cowork')
    assert r['total']==1 and not r['scan_complete'] and not r['coverage_complete']
    assert r['warnings'][0]['line']==3
