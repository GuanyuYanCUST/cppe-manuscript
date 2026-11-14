"""Boundary conditions required by the E1 independent audit:
wrong issuer, cross-domain delegation, cross-domain CASE, expiry at the
PEP, replay, revocation of caps and cases, and necessity-denied retry.
"""
import time

from pguard import certs as C
from pguard.crypto import KeyStore, Principal
from pguard.domains import get_domain

from test_store import make_cap, make_case, world


def test_case_from_non_issuer_principal_rejected():
    """A keystore-valid signature is NOT case authority: an agent- or
    root-signed CASE must be refused (fail-closed issuer check)."""
    d, st, root, iss = world()
    agent = st.keystore.add(Principal("agent", "agent", 1))
    forged = make_case(agent, d, tag="forged")
    assert st.issue_case(forged) == (False, "BAD_ISSUER")
    # even root itself is not a case issuer here
    root_signed = make_case(root, d, tag="rootcase")
    assert st.issue_case(root_signed) == (False, "BAD_ISSUER")
    # and at the PEP directly
    dec = st.pep_decide(d.case_request, root_signed)
    assert dec[:2] == ("DENY", "BAD_ISSUER")


def test_cross_domain_cap_is_void():
    """A cloudops PRECEDENT_CAP cannot install rules in the finance store."""
    d_f, st_f, root_f, iss_f = world(domain="finance")
    d_c = get_domain("cloudops")
    cap_cloud = make_cap(root_f, d_c)          # root-signed but cloudops-scoped
    ok, why, _ = st_f.guarded_install(d_f.positive_rule, cap_cloud)
    assert not ok and why == "CAP_SCOPE"


def test_cross_domain_case_denied():
    """A cloudops CASE cert cannot authorize a finance request."""
    d_f, st_f, root_f, iss_f = world(domain="finance")
    d_c = get_domain("cloudops")
    case_c = make_case(iss_f, d_c, tag="xdom")
    st_f.issue_case(case_c)
    dec = st_f.pep_decide(d_f.case_request, case_c)
    assert dec[0] == "DENY"
    assert dec[1] in ("BAD_ISSUER", "CASE_SCOPE_MISMATCH", "OUT_OF_ROOT")


def test_expired_case_denied_at_pep():
    d, st, root, iss = world()
    past = time.time() - 5
    cert = C.sign_cert(C.make_case(
        norm=d.name, case_id="C-exp", subject="agent",
        action=d.case_request["action"], resource=d.case_request["resource"],
        attrs=d.case_request["attrs"], purpose="availability", ttl_min=30,
        version=1, epoch=1, nonce="n-exp", issued_at=past - 60,
        expires_at=past), iss)
    st.issue_case(cert)
    assert st.pep_decide(d.case_request, cert)[1] == "EXPIRED"


def test_nonce_replay_denied_once_consumed():
    d, st, root, iss = world()
    case = make_case(iss, d, nonce="n-rep")
    st.issue_case(case)
    assert st.pep_decide(d.case_request, case)[0] == "ADMIT_CASE"
    assert st.pep_decide(d.case_request, case)[1] == "REPLAY"


def test_revoked_cap_cannot_install():
    d, st, root, iss = world()
    cap = make_cap(root, d)
    st.revoke(cap["cap_id"])
    ok, why, _ = st.guarded_install(d.positive_rule, cap)
    assert not ok and why == "REVOKED"


def test_legitimate_revocation_kills_serving_immediately():
    d, st, root, iss = world()
    ok, _, prec = st.guarded_install(d.positive_rule, make_cap(root, d))
    assert st.pep_decide(d.case_request)[0] == "ADMIT_PRECEDENT"
    st.revoke(prec["rule_id"])
    assert st.pep_decide(d.case_request)[0] == "DENY"
    assert st.pep_decide(d.case_request)[1] == "NO_AUTHORIZATION"


def test_tampered_case_body_invalidates_signature():
    d, st, root, iss = world()
    case = make_case(iss, d)
    case["attrs"] = dict(case["attrs"], role_tier=2)   # escalate after signing
    assert st.issue_case(case)[0] is False
    assert st.pep_decide(d.case_request, case)[1].startswith("BAD_CASE_SIG")


def test_epoch_rotation_invalidates_stale_precedent_serving():
    d, st, root, iss = world()
    ok, _, prec = st.guarded_install(d.positive_rule, make_cap(root, d))
    st.rotate_epoch()
    # precedent minted under old epoch no longer serves
    assert st.pep_decide(d.case_request)[0] == "DENY"
