"""Serialización JSON unificada (orjson si existe, si no stdlib)."""

import json

import pytest

from core.db_serialize import dumps_db_sorted, loads_db_payload, loads_json_any


def test_loads_json_any_dict_roundtrip():
    raw = '{"a":1,"b":"x"}'.encode("utf-8")
    assert loads_json_any(raw) == {"a": 1, "b": "x"}


def test_loads_json_any_list():
    assert loads_json_any("[1,2,3]") == [1, 2, 3]


def test_loads_db_payload_rejects_list_root():
    assert loads_db_payload("[1,2]") == {}


def test_dumps_db_sorted_stable_keys():
    a, _ = dumps_db_sorted({"z": 1, "a": 2})
    b, _ = dumps_db_sorted({"a": 2, "z": 1})
    assert a == b


def test_loads_json_any_invalid_raises():
    # orjson suele lanzar JSONDecodeError propio; stdlib json.JSONDecodeError.
    with pytest.raises((json.JSONDecodeError, ValueError)):
        loads_json_any(b"not json {{{")
