"""Context-boundary regressions; never spawn or delegate another agent."""
from types import SimpleNamespace
import json
import pytest
from harness import runtime,REPORT

@pytest.mark.asyncio
async def test_child_identity_cannot_prepare_parent_report(tmp_path,monkeypatch):
    async with runtime(tmp_path,monkeypatch):
        from agent.output_delivery import OutputDelivery,output_delivery_scope
        from tools.registry import registry
        delivery=OutputDelivery('probe','parent','api_server.runs','interactive',lambda:False)
        with output_delivery_scope(delivery):
            result=json.loads(registry.dispatch('report_editor_prepare',REPORT,session_id='child'))
            assert result['staged'] is False
            assert not delivery.state['pda-report-editor'].get('request')

@pytest.mark.asyncio
@pytest.mark.parametrize('child_session',['child','parent'])
async def test_child_output_does_not_finalize_parent(tmp_path,monkeypatch,child_session):
    async with runtime(tmp_path,monkeypatch):
        from agent.output_delivery import OutputDelivery,output_delivery_scope,transform_buffered_response
        from agent.delegation_context import delegated_child_context
        delivery=OutputDelivery('probe','parent','api_server.runs','interactive',lambda:False)
        child=SimpleNamespace(session_id=child_session,model='fixture',platform='internal',_delegate_depth=1)
        with output_delivery_scope(delivery):
            with delegated_child_context(child_session):
                assert transform_buffered_response(child,'内部子出力です。')=='内部子出力です。'
            assert delivery.finalized is False
