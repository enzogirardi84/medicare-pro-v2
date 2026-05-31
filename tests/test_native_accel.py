"""Tests para core.native_accel — Native acceleration stubs."""
from __future__ import annotations

import hashlib
import json


class TestChainedHash:
    def test_chained_hash_sha256(self):
        from core.native_accel import chained_hash_sha256
        h = chained_hash_sha256(b"test_data")
        assert len(h) == 64
        assert isinstance(h, str)

    def test_chained_hash_deterministic(self):
        from core.native_accel import chained_hash_sha256
        h1 = chained_hash_sha256(b"data", "prev_hash_abc")
        h2 = chained_hash_sha256(b"data", "prev_hash_abc")
        assert h1 == h2

    def test_chained_hash_changes_with_prev(self):
        from core.native_accel import chained_hash_sha256
        h1 = chained_hash_sha256(b"data", "prev1")
        h2 = chained_hash_sha256(b"data", "prev2")
        assert h1 != h2

    def test_chained_hash_empty_prev(self):
        from core.native_accel import chained_hash_sha256
        h = chained_hash_sha256(b"data")
        expected = hashlib.sha256(b"data").hexdigest()
        assert h == expected


class TestBatchHash:
    def test_batch_hash(self):
        from core.native_accel import batch_hash
        entries = [(b"data1", ""), (b"data2", "prev1")]
        results = batch_hash(entries)
        assert len(results) == 2
        assert all(len(r) == 64 for r in results)

    def test_batch_hash_empty(self):
        from core.native_accel import batch_hash
        assert batch_hash([]) == []


class TestCanonicalJSON:
    def test_canonical_json_deterministic(self):
        from core.native_accel import canonical_json
        a = canonical_json({"b": 2, "a": 1})
        b = canonical_json({"a": 1, "b": 2})
        assert a == b

    def test_canonical_json_compact(self):
        from core.native_accel import canonical_json
        result = canonical_json({"key": "value"})
        assert b" " not in result  # sin espacios


class TestFastMsgPack:
    def test_pack_unpack_roundtrip(self):
        from core.native_accel import fast_msgpack_pack, fast_msgpack_unpack
        original = {"id": "123", "datos": [1, 2, 3]}
        packed = fast_msgpack_pack(original)
        unpacked = fast_msgpack_unpack(packed)
        assert unpacked == original

    def test_pack_bytes(self):
        from core.native_accel import fast_msgpack_pack
        result = fast_msgpack_pack({"msg": "hello"})
        assert isinstance(result, bytes)


class TestBatchVerifyECDSA:
    def test_batch_verify_empty(self):
        from core.native_accel import batch_verify_ecdsa
        assert batch_verify_ecdsa([]) == []

    def test_batch_verify_invalid_key(self):
        from core.native_accel import batch_verify_ecdsa
        entries = [(b"invalid_key", b"payload", "sig")]
        results = batch_verify_ecdsa(entries)
        assert results == [False]


class TestHRTimestamp:
    def test_hrtimestamp_positive(self):
        from core.native_accel import hrtimestamp
        ts = hrtimestamp()
        assert ts > 0


class TestNativeDetection:
    def test_has_native_flag_defined(self):
        from core.native_accel import _HAS_NATIVE
        assert _HAS_NATIVE is not None
