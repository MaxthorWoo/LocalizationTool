# -*- coding: utf-8 -*-
"""临时脚本：测试 GLM-4V-Flash 的并发能力。

参考智谱官方：GLM-4V-Flash 免费版并发限制为 10（RPM），
本脚本用现有 API Key 发起多轮并发请求，统计成功/失败与限流情况。
"""
import io
import sys
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from openai import OpenAI
from localization.models import ApiConfig
from localization.services import file_service


def build_client(cfg: ApiConfig):
    kwargs = {"api_key": cfg.api_key}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    return OpenAI(**kwargs)


def one_request(client, model: str, idx: int, results: list, lock) -> None:
    """发一次请求，记录结果。"""
    start = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是翻译助手，只回复OK。"},
                {"role": "user", "content": "hello"},
            ],
            temperature=0.3,
        )
        content = resp.choices[0].message.content or ""
        elapsed = time.time() - start
        with lock:
            results.append(("OK", idx, round(elapsed, 2), content[:20]))
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - start
        msg = str(exc)[:120]
        with lock:
            results.append(("FAIL", idx, round(elapsed, 2), msg))


def main() -> None:
    # 取默认配置作为测试凭证
    cfg = file_service.list_api_configs()[0]
    model = "glm-4v-flash"
    print(f"使用配置: {cfg.engine_name} / {cfg.model} / {cfg.base_url}")
    print(f"测试模型: {model}")
    print(f"测试目标: 10 并发（官方标注并发上限）")
    print("=" * 60)

    client = build_client(cfg)

    # 场景1：先发 1 个请求验证模型可用性
    results = []
    lock = threading.Lock()
    one_request(client, model, 0, results, lock)
    print("单请求预检:", results[0])
    if results[0][0] != "OK":
        print("模型不可用，终止测试")
        return

    # 场景2：10 并发同时发
    print("\n--- 场景：10 个并发请求 ---")
    results = []
    threads = []
    start = time.time()
    for i in range(10):
        t = threading.Thread(target=one_request, args=(client, model, i, results, lock))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    total = time.time() - start

    ok = [r for r in results if r[0] == "OK"]
    fail = [r for r in results if r[0] == "FAIL"]
    print(f"总耗时: {total:.2f}s")
    print(f"成功: {len(ok)}/10, 失败: {len(fail)}/10")
    for r in sorted(results, key=lambda x: x[1]):
        print("  ", r)

    # 场景3：连续发 20 个（测 RPM 限流）
    print("\n--- 场景：连续 20 个请求（测每分钟限流）---")
    results = []
    threads = []
    start = time.time()
    for i in range(20):
        t = threading.Thread(target=one_request, args=(client, model, i, results, lock))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    total = time.time() - start

    ok = [r for r in results if r[0] == "OK"]
    fail = [r for r in results if r[0] == "FAIL"]
    print(f"总耗时: {total:.2f}s")
    print(f"成功: {len(ok)}/20, 失败: {len(fail)}/20")
    for r in sorted(results, key=lambda x: x[1]):
        print("  ", r)


if __name__ == "__main__":
    main()
