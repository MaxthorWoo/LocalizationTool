"""翻译引擎适配器包。

通过 ENGINE_REGISTRY 注册可用引擎，UI 据此生成引擎下拉选项。
新增引擎时：新建适配器类继承 BaseTranslator，并在底部调用 register_engine。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

# 引擎注册表：engine_name -> translator 类
ENGINE_REGISTRY: dict[str, type] = {}


def register_engine(name: str, translator_cls: type) -> None:
    """注册翻译引擎到全局注册表。"""
    ENGINE_REGISTRY[name] = translator_cls


def get_registered_engines() -> list[str]:
    """返回当前已注册的引擎名称列表。"""
    return list(ENGINE_REGISTRY.keys())


def create_translator(engine_name: str, config) -> "BaseTranslator":
    """根据引擎名与 ApiConfig 创建翻译引擎实例。"""
    cls = ENGINE_REGISTRY.get(engine_name)
    if cls is None:
        raise ValueError(f"未注册的翻译引擎: {engine_name}")
    return cls(config)


# 注册内置引擎（在此导入并注册，避免循环依赖）
from .openai_compat import OpenAICompatTranslator  # noqa: E402

register_engine("GLM", OpenAICompatTranslator)
register_engine("OpenAI 兼容", OpenAICompatTranslator)


if TYPE_CHECKING:  # pragma: no cover
    from .base import BaseTranslator
