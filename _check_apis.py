# -*- coding: utf-8 -*-
"""临时检查：现有 API 配置。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from localization.services import file_service

for a in file_service.list_api_configs():
    print(
        {
            "id": a.id,
            "engine_name": a.engine_name,
            "display_name": a.display_name,
            "model": a.model,
            "base_url": a.base_url,
            "is_default": a.is_default,
            "api_key_hidden": (a.api_key[:4] + "..." + a.api_key[-4:]) if a.api_key else "",
        }
    )
