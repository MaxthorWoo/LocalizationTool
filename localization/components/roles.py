"""列角色下拉组件：工程导入 / 术语导入共用。

- ROLE_OPTIONS：工程导入列角色常量
- column_role_select：工程导入的语义角色下拉
- term_role_select：术语导入的语义角色下拉

依赖：State、column_mapping 常量。
"""
from __future__ import annotations

import reflex as rx

from localization.state import State
from localization.services.column_mapping import ROLE_IGNORE, ROLE_KEY, ROLE_SOURCE

# 工程导入列角色（静态部分；目标语言动态来自 State.lang_role_options）
ROLE_OPTIONS = [
    {"label": "源文案", "value": ROLE_SOURCE},
    {"label": "键", "value": ROLE_KEY},
    {"label": "忽略", "value": ROLE_IGNORE},
]


def column_role_select(col) -> rx.Component:
    """单列的语义角色下拉（目标语言动态来自 State.lang_role_options）。"""
    return rx.select(
        State.column_role_labels,
        on_change=State.set_column_role(col),
        placeholder="选择角色",
        width="100%",
        cursor="pointer",
    )


def term_role_select(col) -> rx.Component:
    """术语导入中单列的语义角色下拉（源术语 / 目标语言 / 备注 / 忽略）。"""
    return rx.select(
        State.term_role_labels,
        on_change=State.set_term_column_role(col),
        placeholder="选择角色",
        width="100%",
        cursor="pointer",
    )
