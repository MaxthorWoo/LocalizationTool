"""翻译引擎抽象基类。

所有翻译引擎实现该接口。BaseTranslator 接收"已渲染的多角色 messages"
（由提示词模板渲染而来），而不是单一文本，从而支持可配置的提示词模板。
"""
from __future__ import annotations

import abc
import re
from typing import Any

from ..models import ApiConfig


def _strip_fences(code: str) -> str:
    """去掉 ``` 或 ~~~ 代码块围栏，仅保留内部内容。"""
    lines = code.splitlines()
    lines = [l for l in lines if not l.strip().startswith("```") and not l.strip().startswith("~~~")]
    return "\n".join(lines).strip()


class BaseTranslator(abc.ABC):
    """翻译引擎适配器抽象基类。"""

    #: 引擎显示名（如 "GLM"），用于 UI 下拉展示
    name: str = "Base"

    def __init__(self, config: ApiConfig) -> None:
        """用一条 ApiConfig 记录初始化引擎。"""
        self.config = config

    @abc.abstractmethod
    def translate(self, messages: list[dict[str, str]], target_lang: str) -> str:
        """执行翻译。

        Args:
            messages: 已渲染的多角色消息序列，如
                [{"role": "system", "content": "..."},
                 {"role": "user", "content": "...{source_text}..."}]
            target_lang: 目标语言代码（如 "en"）。

        Returns:
            译文文本（去掉多余换行/空白后）。
        """
        raise NotImplementedError

    def _clean_output(self, text: str) -> str:
        """清洗模型输出：去掉首尾空白，并剥离模型自行添加的 Markdown 格式标记。

        常见模型会在译文中夹带 **加粗**、__加粗__、*斜体*、`代码` 等标记，
        这里统一剥离，保证展示与导出为纯文本。
        """
        t = text or ""
        # 1. 去掉代码块围栏（保留内部内容）：``` 或 ~~~ 包裹
        t = re.sub(r"```[\s\S]*?```", lambda m: _strip_fences(m.group(0)), t)
        # 2. 去掉行内代码 `...`，保留内容
        t = re.sub(r"`([^`]*)`", r"\1", t)
        # 3. 去掉 **加粗** / __加粗__
        t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
        t = re.sub(r"__([^_]+)__", r"\1", t)
        # 4. 去掉 *斜体*（成对且非 `**` 残留）
        t = re.sub(r"(?<!\*)\*([^*\s][^*]*?)\*(?!\*)", r"\1", t)
        # 5. 去掉行首的 # 标题标记（# 、## 等）
        t = re.sub(r"(?m)^\s*#{1,6}\s+", "", t)
        return t.strip()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} name={self.name}>"
