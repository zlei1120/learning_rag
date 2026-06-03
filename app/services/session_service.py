from __future__ import annotations

import re
from uuid import uuid4


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")


def generate_session_id() -> str:
    """生成前端可直接复用的会话标识。"""
    return f"sess_{uuid4().hex}"


def is_valid_session_id(session_id: str) -> bool:
    """判断会话标识是否符合公开接口约定。"""
    return bool(SESSION_ID_PATTERN.fullmatch(session_id))


def validate_session_id(session_id: str) -> str:
    """校验会话标识格式，不合法时抛出值错误供上层转换。"""
    if not is_valid_session_id(session_id):
        raise ValueError("session_id 格式非法，必须是 8 到 64 位字母、数字、下划线或中划线组合。")
    return session_id
