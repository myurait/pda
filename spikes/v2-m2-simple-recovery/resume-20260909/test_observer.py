import json,unittest
from unittest.mock import patch
import letta_readback as probe
class ObserverContract(unittest.TestCase):
    def test_requires_approval_is_not_client_turn_completion(self):
        # Recorded native provider frames; this is ONLY an observer unit test.
        src=json.loads((probe.E/'letta-4b-native-baseline.json').read_text())['events']
        frames=[x for x in src if x.get('delta',{}).get('message_type') in ('approval_request_message','stop_reason')]
        final=json.loads((probe.E/'letta-schema-baseline.json').read_text())['events']
        frames += [x for x in final if x.get('delta',{}).get('message_type') in ('assistant_message','stop_reason')]
        class Replay:
            def __init__(self):self.messages=iter(frames)
            def send(self,v):pass
            def recv(self,timeout):return json.dumps(next(self.messages))
        with patch.object(probe,'record',lambda *args:None):
            r=probe.turn(Replay(),{},'unit-only','unit-only',seconds=5)
        self.assertEqual(r['stops'][-1],'end_turn')
        self.assertTrue(r['text'])
        self.assertTrue(r['tools'])
    def test_noop_fault_is_not_a_recovery_pass(self):
        import letta_drill as d
        state={'response':{'success':True,'content':'synthetic-unit-memory'}}
        with patch.object(d,'record',lambda *args:None), patch.object(d,'native_status',lambda *args:state), patch.object(d,'docker',lambda *a,**k:{'code':0,'stdout':'123 0\n','stderr':''}), patch.object(d,'wait_ready',lambda **k:{}), patch.object(d,'readback',lambda *a,**k:{'matches':True,'terminal':['end_turn']}):
            result=d.drill('process-death')
        self.assertFalse(result['passed'],'unchanged container generation is NOT an injected process death')

    def test_state_json_inside_native_reply_wrapper(self):
        from unittest.mock import MagicMock
        saved=json.loads((probe.E/'letta-fault-process-death@verified-model.json').read_text())
        with patch.object(probe,'ws',MagicMock()), patch.object(probe,'connect_runtime',lambda *a:{}), patch.object(probe,'turn',lambda *a,**k:saved), patch.object(probe,'record',lambda *a:None):
            result=probe.readback('unit-only')
        self.assertEqual(result['data'],probe.EXPECTED)

    def test_connection_reset_is_recorded_as_transport_failure(self):
        import observe
        with patch.object(observe.urllib.request,'urlopen',side_effect=ConnectionResetError(104,'Connection reset by peer')):
            result=observe.http('/health',base='http://127.0.0.1:19450',auth=False)
        self.assertEqual(result['code'],0)
        self.assertIn('ConnectionResetError',result['error'])

if __name__=='__main__':unittest.main()
