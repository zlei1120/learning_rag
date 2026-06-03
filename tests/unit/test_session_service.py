from __future__ import annotations

import re

import pytest

from app.services.session_service import generate_session_id, is_valid_session_id, validate_session_id


def test_generate_session_id_matches_public_contract():
    """自动生成的会话标识应符合对外公开格式。"""
    session_id = generate_session_id()

    assert re.fullmatch(r"sess_[0-9a-f]{32}", session_id)
    assert is_valid_session_id(session_id) is True


@pytest.mark.parametrize(
    ("session_id", "expected"),
    [
        ("sess_12345678", True),
        ("A2345678", True),
        ("bad id", False),
        ("short", False),
        ("sess_中文内容", False),
    ],
)
def test_is_valid_session_id(session_id: str, expected: bool):
    """会话标识校验应正确区分合法与非法格式。"""
    assert is_valid_session_id(session_id) is expected


def test_validate_session_id_raises_on_invalid_value():
    """非法会话标识应抛出明确错误信息。"""
    with pytest.raises(ValueError, match="session_id 格式非法"):
        validate_session_id("bad id")
