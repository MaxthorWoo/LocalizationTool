"""提示词模板服务：模板 CRUD、组织过滤、内置变量渲染。

提示词模板以"多角色消息序列"存储（PromptTemplate.messages = JSON）：
    [{"role": "system", "content": "你是翻译助手...{target_lang}..."},
     {"role": "user", "content": "翻译以下内容：{source_text}"}]

翻译时通过 render_messages 将内置变量占位符替换为实际值，得到可提交给
/chat/completions 的 messages 数组。模板独立于引擎，任意模板×任意引擎组合。
"""
from __future__ import annotations

import re
from typing import Any

from sqlmodel import select

from .. import config
from ..db import session_scope
from ..models import PromptTemplate, json_dumps, json_loads

# 内置变量定义：(变量名, 说明)
# 变量名需与 render_messages 调用方（translation_service）传入的关键字一致，
# 未传值的变量在渲染时保留原占位符，避免误替换。
PROMPT_VARS: tuple[tuple[str, str], ...] = (
    ("source_text", "待翻译的源文案内容"),
    ("source_lang", "源语言代码（如 zh-CN）"),
    ("source_lang_name", "源语言名称（如 简体中文）"),
    ("target_lang", "目标语言代码（如 en）"),
    ("target_lang_name", "目标语言名称（如 英语）"),
    ("term_context", "命中的术语约束（若出现请优先采用指定译法）"),
    ("user_instruction", "用户自定义的翻译指令"),
    ("entry_key", "当前条目的键名（如 SK1，无则留空）"),
)

_VAR_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def prompt_var_docs() -> list[dict[str, str]]:
    """返回内置变量说明，供 UI 展示。"""
    return [{"name": name, "desc": desc} for name, desc in PROMPT_VARS]


def render_messages(messages: list[dict[str, str]], **vars: str) -> list[dict[str, str]]:
    """将 messages 中的 {变量} 占位符替换为实际值。

    仅替换 PROMPT_VARS 中声明的变量；未声明的占位符原样保留。
    """
    rendered: list[dict[str, str]] = []
    for m in messages:
        content = m.get("content", "")

        def _replace(match: re.Match) -> str:
            name = match.group(1)
            return vars.get(name, match.group(0))

        content = _VAR_PATTERN.sub(_replace, content)
        rendered.append({"role": m.get("role", "user"), "content": content})
    return rendered


def build_default_translation_template() -> list[dict[str, str]]:
    """构造一个内置的默认翻译提示词模板（多角色消息）。"""
    return [
        {
            "role": "system",
            "content": (
                "你是一位专业的本地化翻译专家，请将源语言({source_lang})内容准确、"
                "自然地翻译为{target_lang}。请遵循以下规则：\n"
                "1. 保持原文的语气、格式与专业术语的准确传达；\n"
                "2. {term_context}；\n"
                "3. 只输出翻译结果，不要添加任何解释或额外文字；\n"
                "4. 不要使用任何 Markdown 标记（如 **加粗**、*斜体*、`代码`、# 标题），"
                "纯文本输出；\n"
                "5. 保留原文的换行与段落结构，不要合并行。"
            ),
        },
        {
            "role": "user",
            "content": "请翻译：{source_text}",
        },
    ]


# ---- 模板 CRUD ----

def create_template(
    name: str,
    messages: list[dict[str, str]],
    description: str = "",
    is_default: bool = False,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> PromptTemplate:
    tpl = PromptTemplate(
        user_id=user_id,
        org_id=org_id,
        name=name,
        description=description,
        messages=json_dumps(messages),
        is_default=is_default,
    )
    with session_scope() as s:
        s.add(tpl)
        s.flush()
        s.refresh(tpl)
        return tpl


def list_templates(user_id: int = config.DEFAULT_USER_ID, org_id: int = config.DEFAULT_ORG_ID) -> list[PromptTemplate]:
    """列出个人 + 所在组织共享的模板。"""
    with session_scope() as s:
        stmt = select(PromptTemplate).where(
            (PromptTemplate.user_id == user_id) | (PromptTemplate.org_id == org_id)
        )
        return list(s.exec(stmt).all())


def get_template(tpl_id: int) -> PromptTemplate | None:
    with session_scope() as s:
        return s.get(PromptTemplate, tpl_id)


def update_template(
    tpl_id: int,
    name: str | None = None,
    messages: list[dict[str, str]] | None = None,
    description: str | None = None,
    is_default: bool | None = None,
) -> PromptTemplate | None:
    with session_scope() as s:
        tpl = s.get(PromptTemplate, tpl_id)
        if tpl is None:
            return None
        if name is not None:
            tpl.name = name
        if description is not None:
            tpl.description = description
        if messages is not None:
            tpl.messages = json_dumps(messages)
        if is_default is not None:
            tpl.is_default = is_default
        s.add(tpl)
        s.flush()
        s.refresh(tpl)
        return tpl


def delete_template(tpl_id: int) -> None:
    with session_scope() as s:
        tpl = s.get(PromptTemplate, tpl_id)
        if tpl:
            s.delete(tpl)


def get_default_template(user_id: int = config.DEFAULT_USER_ID) -> PromptTemplate | None:
    """返回默认模板；无默认则返回第一个；都没有则构造内置默认（不落库）。"""
    with session_scope() as s:
        stmt = (
            select(PromptTemplate)
            .where(
                (PromptTemplate.user_id == user_id) | (PromptTemplate.org_id == config.DEFAULT_ORG_ID)
            )
            .where(PromptTemplate.is_default == True)  # noqa: E712
        )
        tpl = s.exec(stmt).first()
        if tpl is not None:
            return tpl
        first = s.exec(
            select(PromptTemplate).where(
                (PromptTemplate.user_id == user_id)
                | (PromptTemplate.org_id == config.DEFAULT_ORG_ID)
            )
        ).first()
        return first


def serialize_template(tpl: PromptTemplate) -> dict[str, Any]:
    """转为便于 UI 使用的字典。"""
    return {
        "id": tpl.id,
        "name": tpl.name,
        "description": tpl.description,
        "messages": tpl.get_messages(),
        "is_default": tpl.is_default,
        "org_id": tpl.org_id,
    }
