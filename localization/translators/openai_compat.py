"""OpenAI 兼容接口翻译引擎适配器。

GLM（智谱）等众多大模型均提供 OpenAI 兼容的 /chat/completions 接口，
本适配器通过配置 base_url/api_key/model 复用 openai 客户端实现翻译。
"""
from __future__ import annotations

from typing import Any

from ..models import ApiConfig
from .base import BaseTranslator


class OpenAICompatTranslator(BaseTranslator):
    """面向 OpenAI 兼容接口的通用翻译适配器（GLM 走此实现）。"""

    name = "OpenAI 兼容"

    def __init__(self, config: ApiConfig) -> None:
        super().__init__(config)
        self._client = None
        self._client_kwargs: dict[str, Any] = {}

    def _get_client(self):
        """懒加载 openai 客户端，避免在无密钥时导入失败。"""
        if self._client is None:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self.config.api_key}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def translate(self, messages: list[dict[str, str]], target_lang: str) -> str:
        """调用 OpenAI 兼容接口完成翻译。

        GLM 兼容参数：model 使用 ApiConfig.model；消息直接透传已渲染的 messages。
        """
        client = self._get_client()
        model = self.config.model or "glm-4-flash"
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        content = resp.choices[0].message.content
        return self._clean_output(content or "")
