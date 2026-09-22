import copy

import httpx

from pda_mirror.__main__ import Mirror, origins


def workflow():
    dynamic = [{"taskReferenceName": "c1", "name": "implement.fake-a", "type": "SIMPLE"}]
    return {
        "workflowId": "j",
        "status": "RUNNING",
        "tasks": [
            {
                "taskId": "judge",
                "referenceTaskName": "judge__2",
                "taskType": "SIMPLE",
                "seq": 3,
                "status": "COMPLETED",
                "inputData": {"type": "judge"},
                "outputData": {"payload": {"dynamicTasks": dynamic}},
            },
            {
                "taskId": "fork",
                "referenceTaskName": "fork__2",
                "taskType": "FORK_JOIN_DYNAMIC",
                "seq": 4,
                "status": "COMPLETED",
                "inputData": {"dynamicTasks": dynamic},
            },
            {
                "taskId": "cell",
                "referenceTaskName": "c1__2",
                "taskType": "SIMPLE",
                "seq": 5,
                "status": "IN_PROGRESS",
                "retryCount": 0,
                "taskDefName": "implement.fake-a",
                "workerId": "fake-a",
            },
        ],
    }


def test_mirror_origin_and_changes():
    wf = workflow()
    assert origins(wf["tasks"]) == {"cell": "judge__2"}
    mirror = Mirror()
    assert len(mirror.changes(wf)) == 4
    assert mirror.changes(wf) == []
    wf["tasks"][2].update(status="TIMED_OUT", reasonForIncompletion="responseTimeoutSeconds: 30")
    changes = mirror.changes(wf)
    assert len(changes) == 1
    assert changes[0][2]["pda.reason"] == "responseTimeoutSeconds: 30"
    assert changes[0][2]["pda.origin_cell"] == "judge__2"
    retry = copy.deepcopy(wf["tasks"][2])
    retry.update(taskId="retry", retryCount=1, status="SCHEDULED")
    wf["tasks"].append(retry)
    assert mirror.changes(wf)[0][2]["pda.retry_count"] == 1


def test_final_read_once():
    mirror = Mirror()
    mirror.running = {"j"}
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json=[]
            if "/running/" in request.url.path
            else {"workflowId": "j", "status": "COMPLETED", "tasks": []},
        )

    with httpx.Client(base_url="http://engine/api", transport=httpx.MockTransport(handler)) as c:
        mirror.poll(c)
        mirror.poll(c)
    assert calls.count("/api/workflow/j") == 1
