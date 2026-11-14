"""Fig.6 bar v4 — scientific-integrity guards (unit + integration).

Run: .venv/bin/python -m pytest tests/test_fig6_bar_v4.py -q
Any failure must block the figure from being marked as the official
version.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import fig6_bar_data_v4 as fd  # noqa: E402

DATA_PRESENT = all(
    (ROOT / "results" / d / "replay_v2" / "main.jsonl").exists()
    for d, _ in fd.ARMS)


def row(model="GPT", domain="cloudops", channel="episodic", seed=0,
        method="B1", proposed=True, installed=True, reason=None,
        issuer=True, scope=False, unauth=False, vpa=False):
    return {"domain": domain, "channel": channel, "seed": seed,
            "method": method, "k_req": 10, "attacker": False,
            "proposed": proposed, "installed": installed,
            "reject_reason": reason, "cppe_issuer": issuer,
            "cppe_scope": scope, "unauth_effect": unauth,
            "valid_accepted": vpa,
            "_model": model, "_key": (model, domain, channel, seed, method)}


# ---------------- statistics ----------------
def test_wilson_zero_and_full():
    lo, hi = fd.wilson(0, 200)
    assert lo < 1e-12 and 0 < hi < 5
    lo, hi = fd.wilson(200, 200)
    assert hi == 1.0 and 0 < lo < 1
    from pguard.stats import wilson
    assert wilson(0, 0) == (0.0, 1.0)   # degenerate input; fd.pct blocks n=0


def test_pct_zero_denominator_raises():
    with pytest.raises(fd.Fig6DataError):
        fd.pct(0, 0)


# ---------------- row validation ----------------
@pytest.mark.parametrize("bad", [
    dict(proposed=False, installed=True),                 # outcome w/o proposal
    dict(proposed=False, reason="OUT_OF_ROOT"),
    dict(installed=True, reason="CAP_SCOPE"),             # installed + reason
    dict(installed=False, reason=None),                   # rejected w/o reason
    dict(installed=False, reason="SOMETHING_ELSE"),       # unknown reason
    dict(proposed=None, installed=False),                 # missing boolean
])
def test_check_reason_rejects(bad):
    with pytest.raises(fd.Fig6DataError):
        fd.check_reason(row(**bad))


def test_check_reason_accepts_valid():
    assert fd.check_reason(row()) is None
    assert fd.check_reason(row(installed=False,
                               reason="MALFORMED_RULE:cond:ttl_min")) \
        == "MALFORMED_RULE:cond:ttl_min"
    assert fd.check_reason(row(proposed=False, installed=False)) is None


# ---------------- identity guards ----------------
def test_identity_duplicate_key():
    rows = [row(), row(seed=0)]
    with pytest.raises(fd.Fig6DataError, match="duplicate"):
        fd.check_identity(rows)


def test_identity_missing_method():
    chs = ["c0", "c1", "c2", "c3"]
    rows = [row(seed=s, channel=c, domain=d)
            for s in range(50) for c in chs for d in fd.DOMAIN_KEYS]
    with pytest.raises(fd.Fig6DataError, match="missing"):
        fd.check_identity(rows)          # complete B1 arm, no B2/B3/B4/B6/PG


def test_identity_wrong_cell_count():
    rows = []
    for s in range(3):                                     # 3 < 800
        for meth in fd.LOAD_METHODS:
            rows.append(row(seed=s, method=meth))
    with pytest.raises(fd.Fig6DataError, match="want 800"):
        fd.check_identity(rows)


def test_family_identity_divergence():
    rows = [row(seed=s, method=m,
                unauth=(m == "B1"))          # B1 diverges from B2/B4/B6
            for s in range(2) for m in ("B1", "B2", "B4", "B6")]
    with pytest.raises(fd.Fig6DataError, match="divergence"):
        fd.check_family_identity(rows)


# ---------------- aggregation on synthetic data ----------------
def _mini_rows():
    rows = []
    for s in range(3):
        for meth in ("B1", "B3", "PG"):
            unauth_b1 = s == 0
            rows.append(row(seed=s, method=meth,
                            proposed=s < 2,
                            installed=s < 2,
                            reason=None if s < 2 else None,
                            issuer=(meth != "PG") and s < 2,
                            scope=(meth == "B1" and s == 1),
                            unauth=(meth == "B1" and unauth_b1),
                            vpa=(meth == "PG" and s == 1)))
    return rows


def test_aggregate_counts():
    A, B, C, D = fd.aggregate(_mini_rows())
    assert A["GPT"]["cloudops"]["b1_unauth"] == 1
    assert A["GPT"]["cloudops"]["pg_unauth"] == 0
    assert B["GPT"] == {"proposed": 2, "installed": 2, "oor": 0,
                        "cap_scope": 0, "malformed": 0}
    assert D["B1"]["issuer"] == 2 and D["B1"]["scope"] == 1 \
        and D["B1"]["effect"] == 1
    assert D["PG"]["issuer"] == 0 and D["PG"]["effect"] == 0


def test_aggregate_pg_unauth_nonzero_is_counted_not_hidden():
    rows = [row(seed=0, method="PG", installed=True, unauth=True),
            row(seed=1, method="PG", installed=True, unauth=False)]
    A, *_ = fd.aggregate(rows)
    assert A["GPT"]["cloudops"]["pg_unauth"] == 1


# ---------------- integration on frozen data ----------------
@pytest.mark.skipif(not DATA_PRESENT, reason="frozen replay_v2 not present")
def test_full_payload_guards():
    P = fd.build_payload()
    h = P["headlines"]
    assert h["legit_traj"] == 4000 and h["proposed"] == 3168
    assert h["well_formed"] == 2960 and h["b1_issuer"] == 2960
    assert h["b3_issuer"] == 2362
    assert abs(fd.pct(2362, 4000) - 59.05) < 0.005    # NOT 58.05
    assert h["b1_scope"] == 598 and h["b1_unauth"] == 584
    assert h["pg_installed"] == 2275 and h["pg_vpa"] == 720
    assert h["pg_unauth"] == 0
    for m, want in fd.EXPECT["pg_proposed_per_model"].items():
        assert P["B"][m]["proposed"] == want
    for m in fd.MODELS:                              # PG zero, 20 cells
        for d in fd.DOMAIN_KEYS:
            assert P["A"][m][d]["pg_unauth"] == 0
        assert P["C"][m]["vpa"] <= P["C"][m]["installed"] \
            <= P["C"][m]["proposed"]


@pytest.mark.skipif(not DATA_PRESENT, reason="frozen replay_v2 not present")
def test_csv_roundtrip(tmp_path):
    P = fd.build_payload()
    f = tmp_path / "fig6_bar_data_v4.csv"
    fd.write_csv(f, P)
    lines = f.read_text(encoding="utf-8-sig").strip().splitlines()
    assert len(lines) == 91          # header + 40a + 20b + 10c + 9d + 11 hd
    import csv
    rows = list(csv.DictReader(lines))
    d_rows = [r for r in rows if r["panel"] == "d"]
    by = {(r["method"], r["series"]): r for r in d_rows}
    assert by[("B1", "Issuer-unsafe installation")]["numerator"] == "2960"
    assert by[("B3", "Issuer-unsafe installation")]["pct"].startswith("59.05")
    assert by[("PG", "Unauthorized sandbox effect")]["numerator"] == "0"
    b_rows = [r for r in rows if r["panel"] == "b" and r["model"] == "GLM"]
    assert sum(int(r["numerator"]) for r in b_rows) == 729
