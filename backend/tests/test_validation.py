import re

import pytest
from pydantic import ValidationError

from backend.app.sessions.schemas import PlayerInput
from backend.app.sessions.service import (
    SessionError,
    bearer_hash,
    new_room_code,
    token_hash,
    validate_code,
)


@pytest.mark.parametrize(
    "name",
    ["", " ", "\t\n", "x" * 41, "a\nb", "a\x00b", "a\u200bb", None, 4, True, [], {}],
)
def test_invalid_names(name):
    with pytest.raises(ValidationError):
        PlayerInput(display_name=name)


@pytest.mark.parametrize(
    "name,expected", [(" Jiya ", "Jiya"), ("李", "李"), ("x" * 40, "x" * 40)]
)
def test_valid_names(name, expected):
    assert PlayerInput(display_name=name).display_name == expected


@pytest.mark.parametrize(
    "code", ["abc123", "ABCD", "ABC1234", "AB-12Q", " A1234", "💻12345"]
)
def test_invalid_code_format(code):
    with pytest.raises(SessionError) as error:
        validate_code(code)
    assert error.value.status == 422


def test_code_generation_matches_contract():
    for _ in range(30):
        code = new_room_code()
        assert re.fullmatch(r"[A-HJ-NP-Z2-9]{6}", code)
        validate_code(code)


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Bearer",
        "Basic abc",
        "Bearer bad",
        "Bearer " + "a" * 44,
        "Bearer " + "!" * 43,
        "Bearer " + "a" * 43 + " extra",
    ],
)
def test_malformed_authorization(header):
    with pytest.raises(SessionError) as error:
        bearer_hash(header)
    assert error.value.status == 401


def test_bearer_scheme_is_case_insensitive():
    assert bearer_hash("bEaReR " + "a" * 43) == token_hash("a" * 43)
