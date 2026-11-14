"""Domain-separated signing primitives.

Ed25519 via PyNaCl when available; HMAC-SHA256 fallback so the offline
pipeline also runs with zero third-party dependencies.  The backend in use
is recorded in every run manifest (``crypto_backend``) so results are never
misattributed.  Domain separation: every signature covers ``b"<KIND>|" +
canonical(payload)`` where KIND is the certificate type, so a CASE
signature can never verify as a PRECEDENT signature even under identical
keys (unit-tested in tests/test_crypto.py).
"""
from __future__ import annotations

import hashlib
import hmac
import json

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError

    BACKEND = "ed25519-pynacl"
except ImportError:  # pragma: no cover - fallback path
    SigningKey = VerifyKey = None
    BadSignatureError = Exception
    BACKEND = "hmac-sha256"


def canonical(obj) -> bytes:
    """Canonical JSON bytes for signing (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _msg(tag: str, payload: bytes) -> bytes:
    return tag.encode("utf-8") + b"|" + payload


class Principal:
    """A key holder with an authority role.

    Roles: ``root`` (AMEND + capability delegation), ``case_issuer``
    (bounded case adjudication), ``precedent_issuer`` (rulemaking delegate
    for a class), ``agent`` (no signing power at all).
    """

    def __init__(self, name: str, role: str, seed: int | None = None):
        self.name = name
        self.role = role
        seed = 0 if seed is None else seed
        if BACKEND == "ed25519-pynacl":
            # Deterministic per (name, role, seed) so runs are reproducible.
            sk = hashlib.sha256(f"{name}|{role}|{seed}".encode()).digest()
            self._sk = SigningKey(sk)
            self.public = bytes(self._sk.verify_key).hex()
        else:
            self._key = hashlib.sha256(f"{name}|{role}|{seed}".encode()).digest()
            self.public = hashlib.sha256(b"pub:" + self._key).hexdigest()

    def sign(self, tag: str, payload: bytes) -> str:
        if BACKEND == "ed25519-pynacl":
            return self._sk.sign(_msg(tag, payload)).signature.hex()
        return hmac.new(self._key, _msg(tag, payload),
                        hashlib.sha256).hexdigest()


class KeyStore:
    """Registry of principals; verifies signatures by issuer name.

    In HMAC fallback mode verification necessarily looks up the named
    principal's key (a MAC, not a public-key signature); this is acceptable
    only for the offline phase and is why ``crypto_backend`` is logged.
    """

    def __init__(self):
        self.principals: dict[str, Principal] = {}

    def add(self, p: Principal) -> Principal:
        self.principals[p.name] = p
        return p

    def get(self, name: str) -> Principal | None:
        return self.principals.get(name)

    def verify(self, issuer: str, tag: str, payload: bytes, sig: str) -> bool:
        p = self.principals.get(issuer)
        if p is None or not isinstance(sig, str):
            return False
        if BACKEND == "ed25519-pynacl":
            try:
                VerifyKey(bytes.fromhex(p.public)).verify(
                    _msg(tag, payload), bytes.fromhex(sig))
                return True
            except (BadSignatureError, ValueError, TypeError):
                return False
        return hmac.compare_digest(
            hmac.new(p._key, _msg(tag, payload), hashlib.sha256).hexdigest(),
            sig)
