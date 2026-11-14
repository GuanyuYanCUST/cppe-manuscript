"""Typed normative authority objects: CASE / PRECEDENT / PRECEDENT_CAP /
AMEND.

Wire formats follow Blueprint V4 §5.2:

- CASE          = one bounded, non-replayable exception (no rulemaking).
- PRECEDENT_CAP = root-signed delegation authorizing a principal to install
                  reusable rules within a rule class.
- PRECEDENT     = an installed reusable rule certificate (must cite a valid
                  PRECEDENT_CAP and a containment proof hash).
- AMEND         = root-only change of the root envelope (version bump).

A CASE signature is never acceptable where a PRECEDENT_CAP/PRECEDENT is
required: ``kind`` is bound into the signed bytes (crypto domain
separation) and re-checked structurally here.
"""
from __future__ import annotations

from .crypto import canonical

KIND_CASE = "CASE"
KIND_PRECEDENT = "PRECEDENT"
KIND_PRECEDENT_CAP = "PRECEDENT_CAP"
KIND_AMEND = "AMEND"


def _cert(kind: str, **fields) -> dict:
    c = {"kind": kind}
    c.update(fields)
    return c


def make_case(norm: str, case_id: str, subject: str, action: str,
              resource: str, attrs: dict, purpose: str, ttl_min: int,
              version: int, epoch: int, nonce: str, issued_at: float,
              expires_at: float) -> dict:
    return _cert(KIND_CASE, norm=norm, case_id=case_id, subject=subject,
                 action=action, resource=resource, attrs=attrs,
                 purpose=purpose, ttl_min=ttl_min, version=version,
                 epoch=epoch, nonce=nonce, issued_at=issued_at,
                 expires_at=expires_at)


def make_precedent_cap(cap_id: str, issuer: str, rule_class: dict,
                       t_exp: float, version: int, epoch: int) -> dict:
    """Root-signed capability: ``issuer`` may install rules inside
    ``rule_class`` (e.g. {"domain": "cloudops", "actions": [...]})."""
    return _cert(KIND_PRECEDENT_CAP, cap_id=cap_id, issuer=issuer,
                 rule_class=rule_class, t_exp=t_exp, version=version,
                 epoch=epoch)


def make_precedent(norm: str, rule_id: str, rule: dict, rule_hash: str,
                   proof_hash: str, cap_id: str, scope: dict, t_exp: float,
                   version: int, epoch: int) -> dict:
    return _cert(KIND_PRECEDENT, norm=norm, rule_id=rule_id, rule=rule,
                 rule_hash=rule_hash, proof_hash=proof_hash, cap_id=cap_id,
                 scope=scope, t_exp=t_exp, version=version, epoch=epoch)


def make_amend(norm: str, new_d_hash: str, old_v: int, new_v: int,
               new_epoch: int, new_envelope: dict) -> dict:
    return _cert(KIND_AMEND, norm=norm, new_d_hash=new_d_hash, old_v=old_v,
                 new_v=new_v, new_epoch=new_epoch,
                 new_envelope=new_envelope)


def sign_cert(cert: dict, principal) -> dict:
    # signature covers exactly cert_body (everything except issuer/sig),
    # whether or not the caller pre-populated an issuer field
    payload = {k: v for k, v in cert.items() if k not in ("sig", "issuer")}
    out = dict(cert)
    out["issuer"] = principal.name
    out["sig"] = principal.sign(cert["kind"], canonical(payload))
    return out


def cert_body(cert: dict) -> dict:
    """Fields covered by the signature (everything except issuer/sig)."""
    return {k: v for k, v in cert.items() if k not in ("sig", "issuer")}


def verify_signature(cert: dict, keystore) -> tuple[bool, str]:
    """Check structural kind + signature domain separation."""
    kind = cert.get("kind")
    if kind not in (KIND_CASE, KIND_PRECEDENT, KIND_PRECEDENT_CAP, KIND_AMEND):
        return False, "UNKNOWN_KIND"
    issuer = cert.get("issuer")
    if not issuer:
        return False, "NO_ISSUER"
    sig = cert.get("sig")
    if not sig:
        return False, "NO_SIGNATURE"
    ok = keystore.verify(issuer, kind, canonical(cert_body(cert)), sig)
    # Cross-type confusion: a CASE payload re-labelled as PRECEDENT must
    # fail because the signature tag differs (verified by kind check inside
    # keystore.verify against the *declared* kind).
    return (True, "") if ok else (False, "BAD_SIGNATURE")


def is_expired(cert: dict, now: float) -> bool:
    t_exp = cert.get("t_exp", cert.get("expires_at"))
    return t_exp is not None and now > t_exp
