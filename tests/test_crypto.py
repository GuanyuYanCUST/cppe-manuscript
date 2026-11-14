"""Domain separation, tamper detection, determinism."""
from pguard.crypto import BACKEND, KeyStore, Principal, canonical


def _ks_root():
    ks = KeyStore()
    ks.add(Principal("root", "root", 1))
    return ks


def test_domain_separation_kind_tag():
    ks = _ks_root()
    payload = canonical({"a": 1})
    sig = ks.get("root").sign("CASE", payload)
    assert ks.verify("root", "CASE", payload, sig)
    # same bytes, different cert kind -> must NOT verify
    assert not ks.verify("root", "PRECEDENT_CAP", payload, sig)
    assert not ks.verify("root", "PRECEDENT", payload, sig)
    assert not ks.verify("root", "AMEND", payload, sig)


def test_tamper_detection():
    ks = _ks_root()
    sig = ks.get("root").sign("CASE", canonical({"x": 1}))
    assert not ks.verify("root", "CASE", canonical({"x": 2}), sig)


def test_unknown_issuer_and_garbage_sig():
    ks = _ks_root()
    assert not ks.verify("mallory", "CASE", b"{}", "deadbeef")
    assert not ks.verify("root", "CASE", b"{}", "not-hex!!")


def test_deterministic_keys():
    a = Principal("root", "root", 42)
    b = Principal("root", "root", 42)
    c = Principal("root", "root", 43)
    assert a.public == b.public != c.public


def test_backend_recorded():
    assert BACKEND in ("ed25519-pynacl", "hmac-sha256")
