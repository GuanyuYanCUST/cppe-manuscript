"""E2/E3 baselines comparison — mechanism tests on a tiny matrix.

Locks the matched-fork contract: every cell runs all 8 methods; PG never
commits an unauthorized install/effect; each baseline's one defining
condition produces its expected offline signature; no baseline's CASE path
is broken (ATC=1 everywhere).
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "src"))

from e2_baselines import METHODS, run_matrix  # noqa: E402


def _tiny(tmp_path):
    rows, summ = run_matrix(seeds=[0, 1], domains=["cloudops"],
                            channels=["episodic", "skill_consolidation"],
                            k_values=[0, 1, 2],
                            outdir=str(tmp_path / "e2"))
    return rows, summ


def test_matched_forks_every_cell(tmp_path):
    rows, _ = _tiny(tmp_path)
    cells = {}
    for r in rows:
        cells.setdefault(r["cell"], set()).add((r["method"], r["fork"]))
    assert cells
    full = {(m, f) for m in METHODS for f in ("ratchet", "positive")}
    for cell, got in cells.items():
        assert got == full, (cell, full - got)


def test_pg_never_unauthorized(tmp_path):
    rows, _ = _tiny(tmp_path)
    for r in rows:
        if r["method"] == "PG":
            assert not r["cppe_issuer"] and not r["cppe_scope"]
            assert not r["unauth_effect"]


def test_method_signatures(tmp_path):
    _, summ = _tiny(tmp_path)
    bm = summ["by_method"]
    assert bm["PG"]["UIR"]["rate"] == 0.0
    assert bm["PG"]["UER"]["rate"] == 0.0
    assert bm["PG"]["VPA"]["rate"] == 1.0
    assert bm["PG"]["FRR"]["rate"] == 0.0
    # strict store: nothing installs, nothing serves, contained proposal
    # rejected (utility cost), but the CASE path is intact
    assert bm["B0"]["FRR"]["rate"] == 1.0
    assert bm["B0"]["VPA"]["rate"] == 0.0
    assert bm["B0"]["UIR"]["na"]                # never attempts
    # learner-write family: every commit unauthorized (issuer; scope on
    # ratchet), effects only where rules serve
    for m in ("B1", "B2", "B4", "B6"):
        assert bm[m]["UIR"]["rate"] == 1.0
        assert bm[m]["UER"]["rate"] > 0          # k=0 cells dilute below 1
        assert bm[m]["VPA"]["rate"] == 1.0
    # judge-only: contained commits still lack rulemaking authority (UIR>0)
    # but no unauthorized EFFECT offline; scope failures are E6/LLM phase
    assert bm["B3"]["UER"]["rate"] == 0.0
    assert bm["B3"]["UIR"]["rate"] > 0
    # action-level authorizer: installs but never serves -> no effect, no VPA
    assert bm["B5"]["UER"]["rate"] == 0.0
    assert bm["B5"]["VPA"]["rate"] == 0.0
    # no baseline was artificially weakened: CASE path healthy everywhere
    for m in METHODS:
        assert bm[m]["ATC"]["rate"] == 1.0, m


def test_k0_is_na_not_zero(tmp_path):
    _, summ = _tiny(tmp_path)
    k0 = summ["by_method_k"]["k0"]
    for m in METHODS:
        assert k0[m]["UIR"]["na"], (m, k0[m]["UIR"])
        assert k0[m]["VPA"]["na"], (m, k0[m]["VPA"])
        assert k0[m]["UER"]["rate"] == 0.0       # probed, denied — real 0


def test_skill_consolidation_needs_two_successes(tmp_path):
    rows, _ = _tiny(tmp_path)
    for r in rows:
        if r["channel"] == "skill_consolidation" and r["k"] == 1:
            assert not r["proposed"], r


def test_expected_pattern_all_match(tmp_path):
    _, summ = _tiny(tmp_path)
    for m, v in summ["expected_pattern"].items():
        assert v["match"], (m, v["diffs"])
