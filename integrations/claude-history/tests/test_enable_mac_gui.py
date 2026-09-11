"""Tests of the one-time owner launcher; no real OS grants in tests."""
import importlib.util
from pathlib import Path
import plistlib
import pytest
SOURCE=Path(__file__).parents[1]/'enable_mac_gui.py'

def load():
    assert SOURCE.exists(), 'owner-only GUI setup is not implemented'
    spec=importlib.util.spec_from_file_location('enable_gui',SOURCE)
    assert spec is not None and spec.loader is not None
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_launch_contract_is_claude_only_and_requires_exact_review(tmp_path):
    m=load();files=m.plan(tmp_path)
    manifest=files['manifest']
    assert manifest==(SOURCE.parent/'gui-capabilities.yaml').read_text()
    config=plistlib.loads(files['plist'])
    args=config['ProgramArguments']
    assert args[:2]==['/Applications/CuaDriver.app/Contents/MacOS/cua-driver','serve']
    assert '--permission-mode' in args and 'bounded' in args
    assert '--approve-capability-manifest' in args
    assert '--dangerously-bypass-approvals' not in args
    assert config['KeepAlive'] is True
    assert config['EnvironmentVariables']['CUA_TELEMETRY_ENABLED']=='0'
    with pytest.raises(PermissionError):
        m.require_review(manifest,False,'yes')
    with pytest.raises(PermissionError):
        m.require_review(manifest,True,'')
    assert m.require_review(manifest,True,'yes') is None


def test_setup_surfaces_the_command_error(tmp_path):
    import sys
    m=load()
    with pytest.raises(RuntimeError,match='EXPLICIT_TEST_FAILURE'):
        m.run([sys.executable,'-c','import sys; print("EXPLICIT_TEST_FAILURE",file=sys.stderr); sys.exit(23)'])


def test_setup_waits_for_health_and_does_not_start_another_daemon():
    m=load()
    with pytest.raises(RuntimeError,match='起動'):
        m.wait_ready(lambda:False,timeout=0)
    states=iter([False,True])
    assert m.wait_ready(lambda:next(states),timeout=2) is None
