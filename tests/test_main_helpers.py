from app.main import _parse_bool


def test_parse_bool_accepts_boolean_values():
    assert _parse_bool(True) is True
    assert _parse_bool(False) is False


def test_parse_bool_accepts_common_string_values():
    assert _parse_bool("true") is True
    assert _parse_bool("YES") is True
    assert _parse_bool("0") is False
    assert _parse_bool("off") is False


def test_parse_bool_rejects_invalid_values():
    invalid_values = ["", "2", "truthy", 8, object()]
    for value in invalid_values:
        try:
            _parse_bool(value)
            assert False, f"expected ValueError for {value!r}"
        except ValueError:
            pass
