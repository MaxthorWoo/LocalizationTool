"""翻译调度服务：分批翻译、术语约束注入、提示词渲染、跳过/覆盖策略。

翻译流程（针对某个目标语言）：
1. 遍历工程条目；
2. 依据"跳过已有/覆盖重译"策略决定是否翻译当前条目；
3. 用提示词模板渲染出多角色 messages（注入源文本、目标语言、术语约束、用户指令）；
4. 调用翻译引擎翻译；
5. 写回译文并更新条目状态；
6. 通过进度回调向 UI 反馈进度。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .. import config
from ..models import STATUS_TRANSLATED, STRATEGY_OVERWRITE, STRATEGY_SKIP, Entry
from . import language_service, prompt_service, term_service
from . import file_service


def _lang_name(code: str) -> str:
    """根据语言代码返回语言名称（如 zh-CN -> 简体中文）。"""
    if not code:
        return ""
    for l in language_service.list_languages():
        if l["code"] == code:
            return l["name"]
    return code


@dataclass
class TranslationResult:
    """一次翻译会话的结果统计。"""

    total: int = 0
    translated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "translated": self.translated,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


ProgressCb = Callable[[int, int, str], None]


def _filter_longest_hits(hits: list[str]) -> list[str]:
    """最长匹配优先：若一个命中词是另一个更长命中词的子串，丢弃短的。

    例如文本含「神器传说」时命中 ['传说', '神器传说']，只保留「神器传说」，
    避免短的通用词稀释长术语的约束。
    """
    ordered = sorted(set(hits), key=len, reverse=True)
    kept: list[str] = []
    for h in ordered:
        if not any(h in k for k in kept):
            kept.append(h)
    return kept


def build_messages(
    prompt_msgs: list[dict[str, str]],
    *,
    source_text: str,
    source_lang: str,
    target_lang: str,
    term_context: str,
    user_instruction: str = "",
    entry_key: str = "",
) -> list[dict[str, str]]:
    """用提示词模板渲染出可提交给 API 的 messages。

    注意：渲染后若最后一条消息是 assistant（模板里以示例结尾），会把它剥离。
    否则 OpenAI 兼容接口会把末位 assistant 视为"模型已回复的内容"，
    导致模型顺着示例继续续写（如编造"示例2/示例3…"），而不是翻译原文。
    """
    rendered = prompt_service.render_messages(
        prompt_msgs,
        source_text=source_text,
        source_lang=source_lang,
        source_lang_name=_lang_name(source_lang),
        target_lang=target_lang,
        target_lang_name=_lang_name(target_lang),
        term_context=term_context,
        user_instruction=user_instruction,
        entry_key=entry_key,
    )
    while rendered and rendered[-1].get("role") == "assistant":
        rendered = rendered[:-1]
    return rendered


def translate_one(
    translator,
    prompt_msgs: list[dict[str, str]],
    entry: Entry,
    source_lang: str,
    target_lang: str,
    term_context: str,
    user_instruction: str = "",
) -> str:
    """翻译单条：渲染 messages 并调用引擎。"""
    messages = build_messages(
        prompt_msgs,
        source_text=entry.source_text,
        source_lang=source_lang,
        target_lang=target_lang,
        term_context=term_context,
        user_instruction=user_instruction,
        entry_key=entry.key_text,
    )
    return translator.translate(messages, target_lang)


def _should_translate(entry: Entry, target_lang: str, strategy: str) -> bool:
    """根据策略判断某条目某语言是否需要翻译。"""
    if strategy == STRATEGY_OVERWRITE:
        return True
    # 默认跳过已有
    return not entry.get_translation(target_lang)


def translate_entries(
    entries: list[Entry],
    translator,
    prompt_msgs: list[dict[str, str]],
    *,
    source_lang: str,
    target_lang: str,
    terms: list,
    strategy: str = STRATEGY_SKIP,
    user_instruction: str = "",
    progress_cb: ProgressCb | None = None,
    batch_size: int = config.TRANSLATION_BATCH_SIZE,
) -> TranslationResult:
    """批量翻译条目（自动分批处理，内部逐条调用 translate_single，串行）。

    供非并发场景（如单语言、兼容旧调用方）使用；并发调度请直接调用
    translate_single。
    """
    result = TranslationResult(total=len(entries))
    term_by_source = {t.source_term: t for t in terms if t.source_term}
    done = 0
    for entry in entries:
        status = translate_single(
            entry,
            translator,
            prompt_msgs,
            source_lang=source_lang,
            target_lang=target_lang,
            terms=terms,
            term_by_source=term_by_source,
            strategy=strategy,
            user_instruction=user_instruction,
        )
        if status == "translated":
            result.translated += 1
        elif status == "failed":
            result.failed += 1
        else:
            result.skipped += 1
        done += 1
        if progress_cb:
            progress_cb(done, len(entries), entry.source_text)
    return result


def translate_single(
    entry: Entry,
    translator,
    prompt_msgs: list[dict[str, str]],
    *,
    source_lang: str,
    target_lang: str,
    terms: list,
    term_by_source: dict | None = None,
    strategy: str = STRATEGY_SKIP,
    user_instruction: str = "",
    entry_lock=None,
    capacity_error_raise: bool = False,
) -> str:
    """翻译单条条目，返回状态字符串。

    Returns:
        "translated"  翻译成功并写库
        "skipped"     命中跳过策略（已有译文）或返回空译文
        "failed"      发生非容量类错误（已记录到 DB？不，仅上层统计）

    Note:
        - 容量类错误（429/5xx/连接类）时：若 capacity_error_raise=True 则向上抛出
          异常以便调度层降级并发重试；否则按 failed 处理。
        - entry_lock 用于并发下保护 entry.set_translation 的内存读-改-写。
    """
    if not _should_translate(entry, target_lang, strategy):
        return "skipped"
    # 命中术语 → 只注入命中条目的紧凑上下文（最长匹配优先）
    hit_words = _filter_longest_hits(term_service.match_terms(entry.source_text, terms))
    if term_by_source is None:
        term_by_source = {t.source_term: t for t in terms if t.source_term}
    hit_terms = [term_by_source[w] for w in hit_words if w in term_by_source]
    term_context = term_service.build_term_context(hit_terms, target_lang)
    try:
        translated = translate_one(
            translator,
            prompt_msgs,
            entry,
            source_lang,
            target_lang,
            term_context,
            user_instruction,
        )
        if translated:
            file_service.update_entry_text(entry.id, target_lang, translated)
            file_service.update_entry_term_hits(entry.id, hit_words)
            lock = entry_lock or _DEFAULT_ENTRY_LOCK
            with lock:
                # 内存状态更新（并发下多个语言同时写同一 entry，需加锁）
                entry.set_translation(target_lang, translated)
                if entry.status == "pending":
                    entry.status = STATUS_TRANSLATED
                    file_service.update_entry_status(entry.id, STATUS_TRANSLATED)
            return "translated"
        return "skipped"
    except Exception as exc:  # noqa: BLE001
        if capacity_error_raise:
            # 交由调度层判断是否容量错误并降级
            raise
        return "failed"


# 全局默认锁，保护并发下 Entry.set_translation 的内存写（读-改-写）。
import threading as _threading

_DEFAULT_ENTRY_LOCK = _threading.Lock()
