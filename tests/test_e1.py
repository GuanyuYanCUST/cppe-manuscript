"""E1 end-to-end mechanism validation (small seed count)."""
from experiments.e1_endtoend import main as e1_main


def test_e1_all_arms(tmp_path):
    summary = e1_main(n_seeds=3, outdir=str(tmp_path / "E1"))
    arms = summary["arms"]
    # headline statistical unit = seed (clustered)
    assert arms["A"]["UIR_seed"]["k"] == arms["A"]["UIR_seed"]["n"] == 3
    assert arms["A"]["UER_seed"]["k"] == arms["A"]["UER_seed"]["n"] == 3
    # arm B: no install opportunity -> N/A, never 0%
    assert arms["B"]["UIR"]["n"] == 0 and arms["B"]["UIR"]["na"] is True
    assert arms["B"]["UER"]["k"] == 0
    assert arms["C"]["UIR_seed"]["k"] == 0
    assert arms["C"]["UIR_seed"]["n"] == 3      # 1 seed = 1 sample
    assert arms["C"]["UIR"]["n"] == 6           # 2 attempts/seed descriptive
    assert arms["D"]["UIR_seed"]["k"] == 0
    assert arms["D"]["VPA"]["k"] == arms["D"]["VPA"]["n"] == 3
    assert summary["all_checks_passed"] is True
    # traces exist and every line parses; ttl varies across seeds
    import json
    lines = (tmp_path / "E1" / "traces.jsonl").read_text().splitlines()
    assert len(lines) >= 3 * 15
    ttls = set()
    for ln in lines:
        rec = json.loads(ln)
        assert rec["model_name"] == "mock-deterministic-v1"
        assert rec["is_llm"] is False
        if rec["event"] == "HISTORY_CASE_EXEC":
            ttls.add(json.dumps(rec["case_scope"]))
    assert len(ttls) >= 1

