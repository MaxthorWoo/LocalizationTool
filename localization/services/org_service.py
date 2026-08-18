"""组织服务：组织管理、join_code 邀请码生成/校验、加入组织。

首期数据预留：模板/术语库按 org_id 归属，加入组织即可获得该组织的共享资源。
"""
from __future__ import annotations

import random
import string

from sqlmodel import select

from .. import config
from ..db import session_scope
from ..models import Org


def _gen_code(length: int = 6) -> str:
    """生成不含易混淆字符的随机邀请码。"""
    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("L", "")
    return "".join(random.choices(alphabet, k=length))


def create_org(
    name: str,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> tuple[Org | None, str]:
    """创建组织并生成唯一邀请码。

    返回 (组织对象或 None, 提示信息)。
    同名组织已存在时不重复创建，返回已存在的组织。
    """
    name = (name or "").strip()
    if not name:
        return None, "组织名称不能为空"
    with session_scope() as s:
        existing = s.exec(select(Org).where(Org.name == name)).first()
        if existing is not None:
            return existing, "该名称的组织已存在，直接复用（邀请码见下方列表）"
        code = _gen_code()
        while s.exec(select(Org).where(Org.join_code == code)).first():
            code = _gen_code()
        org = Org(name=name, join_code=code, created_by=user_id, user_id=user_id, org_id=org_id)
        s.add(org)
        s.flush()
        s.refresh(org)
        return org, ""


def delete_org(
    org_id: int,
    user_id: int = config.DEFAULT_USER_ID,
) -> tuple[bool, str]:
    """删除组织。仅创建者（created_by 匹配）可删除。"""
    with session_scope() as s:
        org = s.get(Org, org_id)
        if org is None:
            return False, "组织不存在"
        if org.created_by != user_id:
            return False, "只能删除自己创建的组织"
        s.delete(org)
        return True, ""


def list_orgs() -> list[Org]:
    with session_scope() as s:
        return list(
            s.exec(select(Org).order_by(Org.created_time.desc())).all()
        )


def get_org(org_id: int) -> Org | None:
    with session_scope() as s:
        return s.get(Org, org_id)


def join_by_code(join_code: str) -> Org | None:
    """通过邀请码查找组织（加入组织 = 校验邀请码有效）。"""
    with session_scope() as s:
        return s.exec(select(Org).where(Org.join_code == join_code.strip().upper())).first()


def regenerate_code(org_id: int) -> Org | None:
    """为组织重新生成邀请码。"""
    with session_scope() as s:
        org = s.get(Org, org_id)
        if org is None:
            return None
        code = _gen_code()
        while s.exec(select(Org).where(Org.join_code == code)).first():
            code = _gen_code()
        org.join_code = code
        s.add(org)
        s.flush()
        s.refresh(org)
        return org
