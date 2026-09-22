import re

CELL = re.compile(r"^c(\d+)__(\d+)$")


def previous_outputs(workflow: dict) -> tuple[int, list[dict]]:
    rounds: dict[int, dict[str, dict]] = {}
    for task in workflow.get("tasks", []):
        reference = task.get("referenceTaskName", "")
        match = CELL.fullmatch(reference)
        if not match:
            continue
        tasks = rounds.setdefault(int(match[2]), {})
        old = tasks.get(reference)
        if old is None or task.get("retryCount", 0) > old.get("retryCount", 0):
            tasks[reference] = task
    if not rounds:
        return 0, []
    outputs = []
    latest = rounds[max(rounds)]
    for reference in sorted(latest, key=lambda ref: int(CELL.fullmatch(ref)[1])):
        task = latest[reference]
        if task.get("status") != "COMPLETED":
            continue
        output = task.get("outputData", {})
        name = task.get("taskDefName", "")
        type_name, _, executor = name.rpartition(".")
        outputs.append(
            {
                "cell_id": reference,
                "type": type_name,
                "executor": executor,
                "kind": output.get("kind"),
                "payload": output.get("payload"),
            }
        )
    return len(rounds), outputs


def origin_cell(task: dict, workflow: dict) -> str | None:
    match = CELL.fullmatch(task.get("referenceTaskName", ""))
    if not match:
        return None
    cell, iteration = f"c{match[1]}", match[2]
    tasks = workflow.get("tasks", [])
    forks = [
        t
        for t in tasks
        if t.get("referenceTaskName") == f"fork__{iteration}"
        and t.get("workflowTask", {}).get("type") == "FORK_JOIN_DYNAMIC"
    ]
    judges = sorted(
        [
            t
            for t in tasks
            if t.get("referenceTaskName") == f"judge__{iteration}"
            and t.get("status") == "COMPLETED"
        ],
        key=lambda t: t.get("retryCount", 0),
        reverse=True,
    )
    for fork in forks:
        definitions = fork.get("inputData", {}).get("dynamicTasks")
        if not definitions or not any(
            item.get("taskReferenceName") == cell and item.get("name") == task.get("taskDefName")
            for item in definitions
        ):
            continue
        for judge in judges:
            if definitions == judge.get("outputData", {}).get("payload", {}).get("dynamicTasks"):
                return judge["referenceTaskName"]
    return None
