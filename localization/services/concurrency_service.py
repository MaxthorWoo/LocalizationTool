"""并发调度与自适应并发数探测服务。

职责：
- 容量类错误分类（429 / 5xx / 连接类 / 限流）
- 有效并发解析（手动上限 > 已探测缓存 > 触发探测）
- 并发探测：指数增长试探，某档全部成功即视为有效，失败回退上一档
- 降级重测并持久化 tested_concurrency 到 DB（跨重启保留）
"""
from __future__ import annotations

import threading
import time

from .. import config
from . import file_service

# 探测请求的最小消息，避免浪费 token
_PROBE_MESSAGES = [
    {"role": "system", "content": "你是一个翻译助手。只回复两个字：连接成功。不要多说。"},
    {"role": "user", "content": "请回复：连接成功"},
]

# 进程内缓存：api.id -> 本次运行已解析的有效并发（避免同次多次探测）
_probe_cache: dict[int, int] = {}
_cache_lock = threading.Lock()


def is_capacity_error(exc: BaseException) -> bool:
    """判断是否为容量类错误（并发过高触发，需降级重试）。

    覆盖：openai.RateLimitError / APIConnectionError / APITimeoutError /
    InternalServerError（APIStatusError），HTTP 429/5xx，以及 requests 连接类异常。
    """
    if exc is None:
        return False
    # openai 库异常
    try:
        import openai
    except Exception:  # noqa: BLE001
        openai = None
    if openai is not None:
        for name in (
            "RateLimitError",
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "APIConnectionPoolTimeoutError",
        ):
            cls = getattr(openai, name, None)
            if cls and isinstance(exc, cls):
                return True
        # 通用 APIStatusError 按状态码判断
        if isinstance(exc, getattr(openai, "APIStatusError", ())):
            sc = getattr(exc, "status_code", 0) or 0
            if sc == 429 or 500 <= sc < 600:
                return True
    # 带 status_code 属性的通用错误（如 httpx 包装）
    sc = getattr(exc, "status_code", 0) or 0
    if sc == 429 or 500 <= sc < 600:
        return True
    # requests 连接类
    try:
        import requests
    except Exception:  # noqa: BLE001
        requests = None
    if requests is not None and isinstance(
        exc, (requests.ConnectionError, requests.Timeout)
    ):
        return True
    # 消息关键词兜底
    msg = str(exc).lower()
    for kw in (
        "rate limit",
        "rate_limit",
        "too many requests",
        "quota exceeded",
        "connection",
        "timeout",
        "timed out",
        "server error",
        "overloaded",
        "429",
        "capacity",
    ):
        if kw in msg:
            return True
    return False


def _max_allowed(cfg) -> int:
    """解析该配置允许的并发硬上限（手动上限或绝对上限）。"""
    manual = getattr(cfg, "max_concurrency", 0) or 0
    if manual > 0:
        return min(manual, config.CONCURRENCY_HARD_MAX)
    return config.CONCURRENCY_HARD_MAX


def resolve_effective_concurrency(cfg) -> int | None:
    """返回应使用的有效并发；None 表示需要触发探测。

    优先级：手动上限 > 已探测缓存 > 触发探测。
    """
    manual = getattr(cfg, "max_concurrency", 0) or 0
    if manual > 0:
        return min(manual, config.CONCURRENCY_HARD_MAX)
    tested = getattr(cfg, "tested_concurrency", 0) or 0
    if tested > 0:
        return min(tested, config.CONCURRENCY_HARD_MAX)
    return None


def _send_probe(cfg) -> bool:
    """发送一条最小探测请求，成功返回 True。"""
    from ..translators import create_translator

    try:
        translator = create_translator(cfg.engine_name, cfg)
        reply = translator.translate(list(_PROBE_MESSAGES), "en")
        return bool(reply and reply.strip())
    except Exception:  # noqa: BLE001
        return False


def _probe_level(cfg, level: int) -> bool:
    """并发发送 level 个最小探测请求，全部成功返回 True。

    真正同时发 level 个请求，模拟并发 N 的实际压力；只要有一条失败
    即视为该档并发不可用（返回 False，调度层会回退上一档）。
    """
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=level) as ex:
        results = list(ex.map(lambda _i: _send_probe(cfg), range(level)))
    return all(results)


def _persist_tested(cfg, concurrency: int) -> None:
    """持久化已探测并发到 DB；cfg 无 id（临时对象）时跳过。"""
    cid = getattr(cfg, "id", 0) or 0
    if cid <= 0:
        return
    try:
        file_service.update_tested_concurrency(cid, concurrency)
    except Exception:  # noqa: BLE001
        pass


def probe_max_concurrency(cfg) -> int:
    """指数增长探测最高并发并持久化；返回有效并发。

    并发档位 2→4→8→…（受 _max_allowed 约束）。每档真正并发发
    level 个最小请求，全部成功即有效；某档有失败则回退到上一档并停止。
    结果写回 DB 的 tested_concurrency。
    若连第 2 档都失败，回退 CONCURRENCY_PROBE_MIN。
    """
    cap = _max_allowed(cfg)
    best = config.CONCURRENCY_PROBE_MIN
    level = config.CONCURRENCY_DEFAULT_START
    while level <= cap:
        if not _probe_level(cfg, level):
            break
        best = level
        # 下一档（防止溢出）
        if level >= cap:
            break
        level = min(level * 2, cap)
    _persist_tested(cfg, best)
    return best


def downgrade_concurrency(cfg, current: int) -> int:
    """容量错误触发的降级：重测并覆盖持久化缓存，返回新的有效并发。

    以当前并发的一半（向下取整，最小为 1）为起点重新探测，
    将结果覆盖写回 DB 的 tested_concurrency。
    """
    start = max(config.CONCURRENCY_PROBE_MIN, current // 2)
    # 用更低起点重测（不能超过当前值，确保比 current 小）
    new_val = _probe_below(cfg, start, current)
    _persist_tested(cfg, new_val)
    return new_val


def _probe_below(cfg, start: int, hard_ceiling: int) -> int:
    """在 [PROBE_MIN, hard_ceiling) 区间内探测，返回低于硬上限的最大有效并发。

    从 start 逐级下调试探；若某并发全部成功则尝试更高一档（仍低于 ceiling）。
    """
    cap = min(_max_allowed(cfg), hard_ceiling - 1)
    if cap < config.CONCURRENCY_PROBE_MIN:
        return config.CONCURRENCY_PROBE_MIN
    best = config.CONCURRENCY_PROBE_MIN
    level = max(config.CONCURRENCY_PROBE_MIN, start)
    while level <= cap:
        if not _probe_level(cfg, level):
            break
        best = level
        level += 1
    return best


class DynamicSemaphore:
    """可动态调整上限的信号量。

    BoundedSemaphore 无法扩容/缩容，而并发降级需要运行时调整上限，
    故用 Condition + 计数实现。set_count 可在任意线程调用。
    """

    def __init__(self, count: int) -> None:
        self._cond = threading.Condition()
        self._count = max(0, int(count))

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        with self._cond:
            if not blocking:
                if self._count > 0:
                    self._count -= 1
                    return True
                return False
            if timeout is None:
                while self._count <= 0:
                    self._cond.wait()
            else:
                deadline = time.monotonic() + timeout
                while self._count <= 0:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
            self._count -= 1
            return True

    def release(self) -> None:
        with self._cond:
            self._count += 1
            self._cond.notify(1)

    def set_count(self, n: int) -> None:
        """重置并发上限（可升可降）。降低会拒绝新 acquire 直至 count 回正。"""
        with self._cond:
            self._count = max(0, int(n))
            if self._count > 0:
                self._cond.notify_all()

    @property
    def count(self) -> int:
        with self._cond:
            return self._count


def get_or_probe_effective(cfg) -> int:
    """运行时获取应使用的有效并发；无缓存/无手动上限则先探测并持久化。

    带进程内缓存，同一 ApiConfig 在同次运行内只探测一次。
    """
    cached = get_cached_effective(cfg)
    if cached:
        return min(cached, _max_allowed(cfg))
    resolved = resolve_effective_concurrency(cfg)
    if resolved:
        cache_effective(cfg, resolved)
        return resolved
    # 触发探测
    probed = probe_max_concurrency(cfg)
    cache_effective(cfg, probed)
    return probed


def cache_effective(cfg, concurrency: int) -> None:
    """记录本次运行已解析的有效并发到进程内缓存（同次运行复用）。"""
    cid = getattr(cfg, "id", 0) or 0
    if cid <= 0:
        return
    with _cache_lock:
        _probe_cache[cid] = int(concurrency)


def get_cached_effective(cfg) -> int | None:
    """读取本次运行进程内缓存的并发。"""
    cid = getattr(cfg, "id", 0) or 0
    if cid <= 0:
        return None
    with _cache_lock:
        return _probe_cache.get(cid)


def clear_cache() -> None:
    """清空进程内并发缓存（通常在启动/配置变更时调用）。"""
    with _cache_lock:
        _probe_cache.clear()
