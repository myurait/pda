"""Generate and idempotently register Conductor metadata from registry/."""
import argparse
import json
from pathlib import Path

import httpx

from pda_wrapper.registry import Registry


def schema_def(name: str, data: dict) -> dict:
    return {'name': name, 'version': 1, 'type': 'JSON', 'data': data}


def generate(root: str | Path) -> tuple[list[dict], dict]:
    registry = Registry(root)
    tasks = []
    for eid, executor in registry.executors.items():
        for type_name in executor['types']:
            decl = registry.types[type_name]
            tasks.append({'name': f'{type_name}.{eid}', **decl['task_def'],
                          'inputSchema': schema_def(type_name + '.input', decl['input_schema']),
                          'outputSchema': schema_def(type_name + '.output', decl['output_schema']),
                          'enforceSchema': True})
    workflow = json.loads((registry.root / 'workflows/pda_job.json').read_text())
    workflow['inputSchema'] = schema_def('pda_job.input', {
        'type': 'object', 'required': ['initial_input'],
        'properties': {'initial_input': {'type': 'string'}, 'context': {'type': 'object'}},
        'additionalProperties': False})
    return tasks, workflow


def register(client: httpx.Client, tasks: list[dict], workflow: dict) -> list[dict]:
    results = []
    for task in tasks:
        existing = client.get('/metadata/taskdefs/' + task['name'])
        if existing.status_code == 404:
            response = client.post('/metadata/taskdefs', json=[task])
        else:
            existing.raise_for_status()
            response = client.put('/metadata/taskdefs', json=task)
        response.raise_for_status()
        results.append({'name': task['name'], 'status': response.status_code})
    existing = client.get('/metadata/workflow/' + workflow['name'],
                          params={'version': workflow['version']})
    if existing.status_code == 404:
        response = client.post('/metadata/workflow', json=workflow)
    else:
        existing.raise_for_status()
        response = client.put('/metadata/workflow', json=[workflow])
    response.raise_for_status()
    results.append({'name': workflow['name'], 'status': response.status_code})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', default='registry')
    parser.add_argument('--conductor', default='http://localhost:8080')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    tasks, workflow = generate(args.registry)
    if args.dry_run:
        print(json.dumps({'taskDefs': tasks, 'workflowDef': workflow}, ensure_ascii=False, indent=2))
    else:
        with httpx.Client(base_url=args.conductor.rstrip('/') + '/api', timeout=30) as client:
            print(json.dumps(register(client, tasks, workflow)))


if __name__ == '__main__':
    main()
