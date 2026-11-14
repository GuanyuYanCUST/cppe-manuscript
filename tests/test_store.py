"""PolicyStore acceptance list: expiry, replay, type confusion, missing/
wrong authority, scope rejection WITH valid authority, CAS, positive path,
hard invariant, standing, amend revalidation, revoke, epoch staleness."""
import time

from pguard import certs as C
from pguard.crypto import KeyStore, Principal
from pguard.domains import get_domain
from pguard.policy_store import PolicyStore


def world(domain="cloudops", guarded=True, seed=0):
    d = get_domain(domain)
    ks = KeyStore()
    root = ks.add(Principal("root", "root", seed))
    issuer = ks.add(Principal("casesvc", "case_issuer", seed))
    ks.add(Principal("agent", "agent", seed))
    return d, PolicyStore(d, ks, root, guarded=guarded,
                          case_issuers={"casesvc"}), root, issuer


def make_case(issuer, d, tag="c1", req=None, ttl=30.0, nonce="n1"):
    req = req or d.case_request
    now = time.time()
    return C.sign_cert(C.make_case(
        norm=d.name, case_id=f"C-{tag}", subject="agent",
        action=req["action"], resource=req["resource"], attrs=req["attrs"],
        purpose="availability", ttl_min=30, version=1, epoch=1, nonce=nonce,
        issued_at=now, expires_at=now + ttl), issuer)


def make_cap(root, d, epoch=1, t_exp=None):
    return C.sign_cert(C.make_precedent_cap(
        cap_id="CAP1", issuer="root", rule_class=d.rule_class,
        t_exp=t_exp if t_exp is not None else time.time() + 3600,
        version=1, epoch=epoch), root)


def test_valid_case_admits_and_replays_are_denied():
    d, st, root, iss = world()
    case = make_case(iss, d)
    assert st.issue_case(case)[0]
    assert st.pep_decide(d.case_request, case)[0] == "ADMIT_CASE"
    dec = st.pep_decide(d.case_request, case)
    assert dec[:2] == ("DENY", "REPLAY")


def test_expired_case_denied():
    d, st, root, iss = world()
    old = make_case(iss, d, ttl=-10.0)
    assert st.issue_case(old) == (False, "EXPIRED")


def test_case_scope_mismatch_denied():
    d, st, root, iss = world()
    case = make_case(iss, d)
    st.issue_case(case)
    dec = st.pep_decide(d.probe_request, case)
    assert dec[:2] == ("DENY", "CASE_SCOPE_MISMATCH") or \
        dec[:2] == ("DENY", "OUT_OF_ROOT")


def test_hard_invariant_beats_everything():
    d, st, root, iss = world()
    req = {"action": "attach_role", "resource": "prod-db",
           "attrs": {"incident_active": 1, "scope_match": 1, "role_tier": 2,
                     "ttl_min": 1440, "purpose": "availability"}}
    case = make_case(iss, d, req=req)
    st.issue_case(case)
    assert st.pep_decide(req, case)[1] == "HARD_INVARIANT"


def test_standing_admits_without_any_credential():
    d, st, root, iss = world()
    req = {"action": "read_logs", "resource": "prod-api",
           "attrs": {"incident_active": 0, "scope_match": 0, "role_tier": 0,
                     "ttl_min": 15, "purpose": "routine"}}
    assert st.pep_decide(req)[0] == "ADMIT_CASE"


def test_guarded_install_rejects_no_authority():
    d, st, root, iss = world()
    ok, why, _ = st.guarded_install(d.ratchet_rule, None)
    assert not ok and why == "NO_AUTHORITY"


def test_case_cert_is_not_precedent_authority():
    d, st, root, iss = world()
    case = make_case(iss, d)
    ok, why, _ = st.guarded_install(d.ratchet_rule, case)
    assert not ok and why == "TYPE_CONFUSION_CASE_AS_PRECEDENT"


def test_valid_cap_still_rejects_out_of_root_rule():
    d, st, root, iss = world()
    ok, why, _ = st.guarded_install(d.ratchet_rule, make_cap(root, d))
    assert not ok and why == "OUT_OF_ROOT"


def test_tampered_cap_rejected():
    d, st, root, iss = world()
    cap = make_cap(root, d)
    cap["rule_class"] = {"domain": "cloudops", "actions": ["*"]}
    ok, why, _ = st.guarded_install(d.positive_rule, cap)
    assert not ok and why.startswith("BAD_CAP_SIG")


def test_cap_scope_action_mismatch_rejected():
    d, st, root, iss = world()
    cap = make_cap(root, d)
    cap["rule_class"] = {"domain": "cloudops", "actions": ["restart_service"]}
    cap = C.sign_cert({k: v for k, v in cap.items() if k not in ("sig",)},
                      root)
    rule = dict(d.positive_rule, action="modify_iam_binding") \
        if d.positive_rule["action"] == "attach_role" else d.positive_rule
    ok, why, _ = st.guarded_install(rule, cap)
    assert not ok and why == "CAP_SCOPE"


def test_stale_epoch_cap_rejected():
    d, st, root, iss = world()
    st.rotate_epoch()
    ok, why, _ = st.guarded_install(d.positive_rule, make_cap(root, d))
    assert not ok and why == "STALE_EPOCH"


def test_expired_cap_rejected():
    d, st, root, iss = world()
    ok, why, _ = st.guarded_install(
        d.positive_rule, make_cap(root, d, t_exp=time.time() - 1))
    assert not ok and why == "CAP_EXPIRED"


def test_cas_race_rejected():
    d, st, root, iss = world()
    ok, why, _ = st.guarded_install(d.positive_rule, make_cap(root, d),
                                    expected_version=99)
    assert not ok and why == "CAS_RACE"


def test_positive_path_installs_and_serves():
    d, st, root, iss = world()
    ok, why, prec = st.guarded_install(d.positive_rule, make_cap(root, d))
    assert ok, why
    dec = st.pep_decide(d.case_request)          # no case presented
    assert dec[0] == "ADMIT_PRECEDENT" and dec[2] == prec["rule_id"]


def test_unguarded_store_commits_learner_writes():
    d, st, root, iss = world(guarded=False)
    ok, why, prec = st.unguarded_install(d.ratchet_rule)
    assert ok and prec["install_path"] == "learner_write"
    assert st.pep_decide(d.probe_request)[0] == "ADMIT_PRECEDENT"
    # and the guarded API is unavailable on an unguarded store
    d2, st2, r2, i2 = world(guarded=False)
    assert st2.guarded_install(d2.positive_rule, make_cap(r2, d2))[1] == \
        "STORE_NOT_GUARDED"


def test_amend_revalidation_drops_incompatible_precedents():
    d, st, root, iss = world()
    st.guarded_install(d.positive_rule, make_cap(root, d))
    amend = C.sign_cert(C.make_amend(
        norm=d.name, new_d_hash="h", old_v=1, new_v=2, new_epoch=0,
        new_envelope={}), root)
    ok, why = st.amend(amend, lambda x: False)   # empty new envelope
    assert ok, why
    assert st.version == 2 and not st.active_precedents
    assert st.pep_decide(d.case_request)[0] == "DENY"


def test_amend_requires_root_signature():
    d, st, root, iss = world()
    mallory = st.keystore.add(Principal("mallory", "agent", 7))
    amend = C.sign_cert(C.make_amend(
        norm=d.name, new_d_hash="h", old_v=1, new_v=2, new_epoch=0,
        new_envelope={}), mallory)
    assert not st.amend(amend, lambda x: False)[0]


def test_revoke_kills_precedent_and_case():
    d, st, root, iss = world()
    ok, _, prec = st.guarded_install(d.positive_rule, make_cap(root, d))
    st.revoke(prec["rule_id"])
    assert st.pep_decide(d.case_request)[0] == "DENY"
    case = make_case(iss, d, nonce="n9")
    st.issue_case(case)
    st.revoke(case["case_id"])
    assert st.pep_decide(d.case_request, case)[1] == "REVOKED"


def test_audit_log_hash_chained_and_policy_hash_stable_under_learning():
    d, st, root, iss = world()
    h0 = st.policy_hash()
    case = make_case(iss, d, nonce="n2")
    st.issue_case(case)
    st.pep_decide(d.case_request, case)
    assert st.policy_hash() == h0        # CASE exec never changes policy
    st.guarded_install(d.positive_rule, make_cap(root, d))
    assert st.policy_hash() != h0
    assert all("chain_hash" in e for e in st.audit)


# --- F-C2 fix: out_of_root stamped at the commit funnel -------------------

def test_out_of_root_stamped_on_unguarded_commit():
    """Learner-write install of an escaping rule stamps out_of_root=True;
    classify_install (oracle) now sees real scope ground truth."""
    from pguard.oracle import AuthorizationOracle
    d, st, root, iss = world(guarded=False)
    ok, why, prec_bad = st.unguarded_install(d.ratchet_rule)
    assert ok, why
    assert prec_bad["out_of_root"] is True
    ok2, why2, prec_good = st.unguarded_install(d.positive_rule)
    assert ok2, why2
    assert prec_good["out_of_root"] is False
    ev_bad = next(e for e in st.audit if e["label"] == "INSTALL_PREC"
                 and e["rule_id"] == prec_bad["rule_id"])
    ev_good = next(e for e in st.audit if e["label"] == "INSTALL_PREC"
                   and e["rule_id"] == prec_good["rule_id"])
    assert ev_bad["out_of_root"] is True and ev_good["out_of_root"] is False
    orc = AuthorizationOracle(d, st.keystore, "root")
    cls_bad = orc.classify_install(ev_bad)
    cls_good = orc.classify_install(ev_good)
    assert cls_bad["cppe_scope"] is True and cls_bad["cppe_issuer"] is True
    assert cls_good["cppe_scope"] is False and cls_good["cppe_issuer"] is True


def test_out_of_root_boundary_envelope_edge_rule():
    """Boundary: a rule covering ONLY in-envelope requests stamps False
    (positive_rule is the canonical contained control; a rule whose
    coverage touches the envelope edge from inside must not trip)."""
    d, st, root, iss = world()
    ok, why, prec = st.guarded_install(d.positive_rule, make_cap(root, d))
    assert ok, why and prec["out_of_root"] is False


def test_guarded_reject_emits_no_install_event():
    """Negative control: OUT_OF_ROOT reject must NOT stamp any commit —
    only INSTALL_REJECTED is emitted, with no rule_id commit row."""
    d, st, root, iss = world()
    ok, why, prec = st.guarded_install(d.ratchet_rule, make_cap(root, d))
    assert not ok and why == "OUT_OF_ROOT" and prec is None
    assert [e["label"] for e in st.audit] == ["INSTALL_REJECTED"]
    assert not st.active_precedents
