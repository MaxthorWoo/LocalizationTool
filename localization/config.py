"""本地化可视化翻译平台配置模块。

集中管理全局配置项：数据库路径、上传/导出目录、默认语言等。
"""
from pathlib import Path

# 项目根目录（localization 包所在目录）
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库文件路径
DB_PATH = BASE_DIR / "localization.db"

# 上传文件与导出文件存储目录
UPLOAD_DIR = BASE_DIR / "uploads"
EXPORT_DIR = BASE_DIR / "exports"

# 默认源语言（用于纯文本直粘、翻译时的源语言提示）
DEFAULT_SOURCE_LANG = "zh-CN"

# 默认目标语言（导入时语言猜测失败时的兜底）
DEFAULT_TARGET_LANG = "en"

# 平台支持的语言代码列表（供 UI 下拉与语言猜测）
AVAILABLE_LANG_CODES = [
    "zh-CN", "zh-TW", "en", "ja", "ko", "th", "id",
    "vi", "fr", "de", "es", "pt", "ru", "ar",
]

# 默认单用户 ID（首期单用户，所有数据归属该 ID）
DEFAULT_USER_ID = 0

# 默认组织 ID（未加入任何组织时使用，代表"个人/本地"）
DEFAULT_ORG_ID = 0

# 翻译分批大小（避免单次请求过大导致超时）
TRANSLATION_BATCH_SIZE = 20

# ---- 并发调度相关 ----
# 并发探测的绝对硬上限（即使引擎声明更高也不超过该值，保护账号安全）
CONCURRENCY_HARD_MAX = 16
# 并发探测的最小起点
CONCURRENCY_PROBE_MIN = 1
# 并发探测每档用于验证的最小请求数（并发 N 时发 N 个请求验证是否全成功）
CONCURRENCY_PROBE_PER_LEVEL = 3
# 默认探测用并发起点（无缓存时的初始档）
CONCURRENCY_DEFAULT_START = 2
# 全局并发调度线程池与信号量的上限（防止极端配置下资源失控）
CONCURRENCY_ABS_CAP = 32

# 表格预览行数（导入向导中预览前几行）
PREVIEW_ROWS = 5


def ensure_dirs() -> None:
    """确保必要的存储目录存在（运行时调用）。"""
    for d in (UPLOAD_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
