"""Fixture input is real, deterministic and distinct from results."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "experiments/v2/generate_memory_fixture.py"


def test_fixture_cli_builds_resolvable_corpus_and_separate_gold(tmp_path):
    assert GENERATOR.exists(), "concrete memory fixture generator is not implemented"
    result = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--out", str(tmp_path), "--seed", "101", "--scale", "small"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    read = lambda name: [json.loads(line) for line in (tmp_path / name).read_text().splitlines()]
    corpus, skills, inputs, gold, scenarios = map(read, [
        "corpus.jsonl", "skills.jsonl", "input.jsonl", "gold.jsonl", "scenarios.jsonl"
    ])
    assert len(corpus) == 120 and len(skills) == 12
    assert len(inputs) == len(gold) == len(scenarios) == 160
    assert manifest["kind"] == "synthetic-input-not-candidate-results"
    assert manifest["model_calls"] == 0
    available = {row["id"] for row in corpus + skills}
    for row in gold:
        assert set(row["expected_source_ids"]) <= available
        assert set(row["forbidden_source_ids"]) <= available
    assert all("gold" not in row and "label" not in row and "split" not in row for row in inputs)
    assert not any(row["query"].startswith("これは検索不要") for row in inputs)
    assert sum(row["split"] == "holdout" for row in gold) == 32
    assert {row["feature"] for row in gold} == {f"F{i}" for i in range(13, 21)}
    pairs = {}
    groups = {}
    for row in gold:
        pairs.setdefault(row["pair_id"], []).append(row)
        groups.setdefault(row["group_id"], set()).add(row["split"])
    assert all(len(values) == 1 for values in groups.values())
    assert all({row["polarity"] for row in pair} == {"positive", "negative"} for pair in pairs.values())
    assert all(len({row["domain"] for row in pair}) == 1 for pair in pairs.values())
    assert all(row["events"] for row in scenarios if row["feature"] in {"F13", "F17", "F19", "F20"})


def test_cross_topic_gold_has_a_visible_applicability_link(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--out", str(tmp_path), "--seed", "101", "--scale", "small"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    read = lambda name: [json.loads(line) for line in (tmp_path / name).read_text().splitlines()]
    sources = {row["id"]: row for row in read("corpus.jsonl")}
    queries = {row["case_id"]: row["query"] for row in read("input.jsonl")}
    for gold in read("gold.jsonl"):
        if gold["feature"] == "F18" and gold["polarity"] == "positive":
            for source_id in gold["expected_source_ids"]:
                applies_to = sources[source_id].get("applies_to")
                assert isinstance(applies_to, str) and applies_to, "cross-topic source has no visible entity association"
                assert applies_to in queries[gold["case_id"]]


def test_critical_constraint_fixture_starts_dormant(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--out", str(tmp_path), "--seed", "101", "--scale", "small"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    read = lambda name: [json.loads(line) for line in (tmp_path / name).read_text().splitlines()]
    sources = {row["id"]: row for row in read("corpus.jsonl")}
    cases = [row for row in read("gold.jsonl") if row["feature"] == "F19" and row["polarity"] == "positive"]
    assert cases
    for gold in cases:
        source = sources[gold["expected_source_ids"][0]]
        assert source["lifecycle"] == "dormant", "critical constraint must start dormant"
        assert source["authority_locator"]


def test_revoked_fixture_cannot_disappear_from_any_restore_phase(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--out", str(tmp_path), "--seed", "101", "--scale", "small"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    read = lambda name: [json.loads(line) for line in (tmp_path / name).read_text().splitlines()]
    sources = {row["id"]: row for row in read("corpus.jsonl")}
    scenarios = {row["case_id"]: row for row in read("scenarios.jsonl")}
    cases = [row for row in read("gold.jsonl") if row["feature"] == "F20" and row["polarity"] == "positive"]
    assert cases
    for gold in cases:
        events = scenarios[gold["case_id"]]["events"]
        invalidations = [ev for ev in events if ev["op"] == "record_invalidation"]
        assert invalidations, "restore fixture must have authoritative revocation evidence"
        revoked = invalidations[0]["id"]
        assert sources[revoked]["lifecycle"] == "revoked"
        assert sources[revoked]["validity"] == "revoked"
        assert revoked in gold["forbidden_source_ids"]
        phases = [ev for ev in events if ev["op"] in {"index_rebuild", "restore_fixture_snapshot", "migrate_fixture_export"}]
        assert len(phases) == 3
        for phase in phases:
            assert revoked in phase["assert_after"]["revoked_ids"]
