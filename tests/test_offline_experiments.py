"""Mechanism tests for E5 / E7 / E9 / ER (offline, mock)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "src"))


def test_e5_factorial(tmp_path):
    from e5_factorial import run_factorial
    _, summ = run_factorial(seeds=[0, 1], domains=["cloudops", "finance"],
                            outdir=str(tmp_path / "e5"))
    assert all(summ["checks"].values())
    head = summ["table"]["exact|grant=0"]
    assert head["PG"]["install_rate"]["rate"] == 0.0
    assert head["B2"]["UIR"]["rate"] == 1.0
    assert head["B6"]["UIR"]["rate"] == 1.0
    lossy_grant = summ["table"]["lossy|grant=1"]
    assert lossy_grant["PG"]["install_rate"]["rate"] == 1.0
    assert lossy_grant["PG"]["UIR"]["rate"] == 0.0
    assert lossy_grant["B2"]["install_rate"]["rate"] == 0.0


def test_e7_ablations(tmp_path):
    from e7_ablation import run_ablations
    summ = run_ablations(domain_names=["cloudops", "dataaccess"],
                         outdir=str(tmp_path / "e7"))
    assert summ["all_attacks_penetrate_only_under_ablation"]
    r = summ["results"]["cloudops"]
    assert r["A1_issuer_typing"]["outcomes"]["full"]["reason"] \
        .startswith("TYPE_CONFUSION")
    assert r["A4_epoch_cas"]["outcomes"]["stale_epoch"]["full"]["reason"] \
        == "STALE_EPOCH"
    # post-AMEND install on the full store is stopped by at-commit
    # containment revalidation (OUT_OF_ROOT) or the version fence
    # (CAS_RACE) — layered defenses, either is a correct rejection
    assert r["A4_epoch_cas"]["outcomes"]["post_amend_cas"]["full"][
        "reason"] in ("OUT_OF_ROOT", "CAS_RACE")
    assert not r["A4_epoch_cas"]["outcomes"]["post_amend_cas"]["full"][
        "install"]


def test_er_revocation(tmp_path):
    from er_revocation import run
    summ = run(outdir=str(tmp_path / "er"))
    assert all(v["passed"] for v in summ["results"].values())


def test_e9_robustness(tmp_path):
    from e9_robustness import run
    summ = run(outdir=str(tmp_path / "e9"))
    assert all(summ["checks"].values())
    assert summ["corruption"]["p=0.00"]["FRR"]["rate"] == 0.0
    assert summ["overload"]["20x"]["denial_rate"]["rate"] > 0.9
    for v in summ["corruption"].values():
        assert v["unsafe_admissions"]["rate"] == 0.0
    for v in summ["overload"].values():
        assert v["unsafe_admissions"]["rate"] == 0.0


def test_e6_smoke(tmp_path):
    from e6_adaptive import run
    _, summ = run(outdir=str(tmp_path / "e6"), budgets=(1, 5),
                  seeds=(0,), domains=("cloudops",))
    assert summ["pg_never_unsafe_admits"]
    t2 = summ["raw"]["T2_similarity_nudging"]["5"][0]["out"]
    # the evidence-consistency judge admits unsafe rules; PG does not
    assert t2["JUDGE_EVID"]["unsafe_installs"] > 0
    assert t2["PG"]["unsafe_installs"] == 0
    t4 = summ["raw"]["T4_exact_log_laundering"]["5"][0]["out"]
    assert t4["B2"]["unsafe_installs"] == 5
    assert t4["PG"]["unsafe_installs"] == 0
