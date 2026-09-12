"""Opt-in report editing plugin. No registration-time external calls."""
import json


def register(ctx):
    from .report_editor.contracts import SCHEMA, parse_request
    from .report_editor.pipeline import edit, record_metrics
    try:
        from agent.output_delivery import current_output_delivery
    except ImportError:
        # Older Hermes cannot withhold drafts: remain completely inactive.
        return

    def settings():
        return {k:ctx.get_config(k,default) for k,default in [('enabled',False),('adapter',None),('timeout_seconds',15.0),('metrics_path',None)]}

    def prepare(output_context):
        from agent.delegation_context import is_delegated_child_process_context
        config=settings()
        if (config['enabled'] is True and isinstance(config['adapter'],dict)
                and config['adapter'].get('factory') and output_context.surface=='api_server.runs'
                and output_context.purpose=='interactive' and not output_context.is_cancelled()
                and not is_delegated_child_process_context()):
            output_context.state['pda-report-editor']={'config':config}
            output_context.restore_replay=True
            return None  # Eligibility alone must not suppress ordinary streaming.
        return None

    def stage(args,**kwargs):
        from agent.delegation_context import is_delegated_child_process_context
        delivery=current_output_delivery()
        state=delivery.state.get('pda-report-editor') if delivery else None
        if (not state or delivery.finalized or delivery.is_cancelled()
                or kwargs.get('session_id')!=delivery.session_id
                or is_delegated_child_process_context()):
            return json.dumps({'staged':False,'reason':'not_eligible'})
        if delivery.output_started:
            return json.dumps({'staged':False,'reason':'output_already_started'})
        try:request=parse_request(args)
        except (ValueError,TypeError):
            return json.dumps({'staged':False,'reason':'invalid_or_sensitive_input'})
        if delivery.draft_was_visible(request['draft']):
            return json.dumps({'staged':False,'reason':'draft_already_visible'})
        # One prepared request per host invocation, not a global session map.
        if 'request' in state:return json.dumps({'staged':False,'reason':'already_prepared'})
        state['request']=request
        delivery.buffered=True  # Only a valid, explicitly staged report is held.
        return json.dumps({'staged':True,'next':'Return the exact draft as the final answer. Do not call any editor or tool again.'})

    def transform(response_text,output_context=None,**kwargs):
        if output_context is None:return None
        state=output_context.state.get('pda-report-editor')
        if not state or 'request' not in state:return None
        if state.get('attempted'):return None
        state['attempted']=True
        request=state['request']
        if response_text!=request['draft']:return None
        result=edit(request,state['config'],output_context.is_cancelled)
        record_metrics(state['config'],output_context,result)
        return result['text'] or None

    ctx.register_hook('prepare_output_delivery',prepare)
    ctx.register_hook('transform_llm_output',transform)
    ctx.register_tool(name='report_editor_prepare',toolset='report_editor',schema={
        'name':'report_editor_prepare',
        'description':('After technical work and any legitimate interim progress, but before emitting the FINAL technical completion/incompletion/incident report or decision/approval request, prepare its non-secret content once with this tool. '
                       'Copy every relevant objective/outcome, verified fact, failure/unmet/unknown, option and rationale, recommendation, required reader decision and protected value into the structured fields AND draft. '
                       'Do not send conversation history, reasoning, secrets or logs. Only public material is eligible. Never use for ordinary short chat, JSON/code/raw artifacts, title/tags/helpers, internal/subagent/editor outputs or urgent stop/status replies. '
                       'This does no technical work and cannot certify success. If staged, immediately output draft verbatim; the host handles editing without showing a draft first. If denied, use the original answer.'),
        'parameters':SCHEMA},handler=stage,
        check_fn=lambda: settings()['enabled'] is True and bool(settings()['adapter']),
        description='Prepare a non-secret final technical report for editing')
