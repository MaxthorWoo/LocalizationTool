# 本地化可视化翻译平台

基于 **Python + Reflex** 的通用本地化可视化翻译平台。实现「多态输入 → 通用列映射解析 → AI 翻译 → 人工校对 → 列表展示 → 导出交付」的完整闭环。

定位为**通用工具**而非写死的个人工具：用户可自行配置翻译 API、术语库、提示词模板，并支持组织内共享。

## 核心能力

| 能力 | 说明 |
|------|------|
| **多态输入** | 上传文件（xlsx/csv/txt）或直接粘贴纯文本，均围绕「工程」展开 |
| **通用列映射解析** | 不写死列名。导入时预览表格、自动猜测列语义角色，用户可手动指认，并可将常用结构保存为模板复用，适配任意结构的表格文件 |
| **多引擎翻译适配** | 翻译引擎抽象为适配器架构，首期实现 GLM（走 OpenAI 兼容接口），用户可配置 `base_url/api_key/model` |
| **提示词模板管理** | 大模型指令不写死，作为独立实体存储；支持 System/User/Assistant 多角色消息序列；内置变量占位（`{source_text}` 等）；按组织共享 |
| **术语库双源导入** | 本地文件（xlsx/csv/txt）+ 在线表格直链（Google Sheets，`gdown` 下载）；术语约束模式：翻译时优先采用指定译法，校对时高亮提醒 |
| **可视化校对编辑** | 源文案与各目标语言译文的对照表格，行内直接编辑，状态徽标（待译/已译/已校对/需复核），术语命中高亮 |
| **已有译文策略** | 每个目标语言列可选「跳过已有 / 覆盖重译」 |
| **产出** | 后台列表展示、进度统计，导出 xlsx（含源文案、各语言译文、状态、命中术语） |
| **组织共享** | 创建/加入组织，共享组织的提示词模板与术语库（数据层预留 `org_id`） |

## 技术栈

- **前后端一体化**：Reflex 0.9.8（纯 Python，自带响应式 Web UI 与状态管理）
- **翻译引擎客户端**：openai 库（GLM 等大模型均提供 OpenAI 兼容接口，统一走 `/chat/completions`）
- **文件解析**：pandas + openpyxl（xlsx/csv）、内置文本处理（txt）
- **在线表格源**：gdown（解析 Google Sheets/Drive 分享直链）
- **数据持久化**：SQLite + SQLModel
- **运行环境**：Python 3.10+（已在 Python 3.14 验证通过）

## 快速开始

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. 启动应用
reflex run
```

启动后浏览器访问：
- 前端：<http://localhost:3000>
- 后端 API：<http://localhost:8000>

首次使用时，请在「引擎配置」页添加你的翻译 API（如 GLM），并设为默认引擎。

## 使用流程

1. **我的工程**：上传文件进入「列映射向导」，或粘贴纯文本直接创建工程
2. **翻译校对**：选择目标语言 → 点击「开始翻译」→ 在对照表格中人工编辑、标记状态
3. **提示词模板**：维护翻译用的多角色指令模板，内置变量自动填充
4. **术语库**：导入术语，翻译时自动约束译法
5. **组织**：创建组织获得邀请码，他人凭邀请码加入并共享模板

## 目录结构

```
LocalizationTool/
├── app.py                        # Reflex 应用入口，页面路由与组件
├── rxconfig.py                   # Reflex 项目配置
├── requirements.txt              # 依赖清单
├── localization/
│   ├── state.py                  # Reflex 核心状态类（全部业务事件）
│   ├── config.py                 # 全局配置
│   ├── models.py                 # SQLModel 数据模型
│   ├── db.py                     # SQLite 初始化与会话管理
│   ├── services/
│   │   ├── column_mapping.py     # 列语义角色、语言猜测、列模板 CRUD
│   │   ├── parser.py             # 文件解析（表格/纯文本）
│   │   ├── exporter.py           # xlsx 导出
│   │   ├── file_service.py       # 上传、建工程、条目、API 配置
│   │   ├── translation_service.py# 翻译调度、术语约束、跳过/覆盖策略
│   │   ├── term_service.py       # 术语导入/查询/匹配
│   │   ├── term_sources.py       # 术语数据源（本地/在线直链）
│   │   ├── prompt_service.py     # 提示词模板 CRUD + 内置变量渲染
│   │   └── org_service.py        # 组织管理、邀请码
│   └── translators/
│       ├── base.py               # BaseTranslator 抽象
│       ├── openai_compat.py      # OpenAI 兼容接口（GLM）
│       └── __init__.py           # 引擎注册表
├── uploads/                      # 上传文件存储（运行时生成）
├── exports/                      # 导出文件存储（运行时生成）
└── README.md
```

## 架构说明

```
Reflex 应用层 ──► 服务层 ──► 引擎/数据源 ──► 数据层
  State/UI        FileService     Parser/Exporter
                  TranslationService  BaseTranslator → OpenAICompat(GL)
                  TermService        LocalFileSource / OnlineSheetSource(gdown)
                  PromptService      PromptTemplate（多角色消息+内置变量）
                  OrgService         SQLite (projects/entries/terms/
                                          api_configs/column_templates/orgs/prompts)
```

关键设计：
- **翻译引擎适配器**：`BaseTranslator` 接收「已渲染的多角色 messages」，而非单文本，从而支持可配置提示词模板
- **提示词模板**：`PromptTemplate.messages` 存 JSON 多角色消息序列，翻译时用内置变量渲染为 `/chat/completions` 的 `messages`
- **通用列映射**：表格读为 DataFrame 后按「列 → 语义角色」映射提取，语言代码用词典/正则自动猜测，可保存为模板
- **数据模型预留扩展**：所有模型含 `user_id`/`org_id`（默认 0），后期多用户/组织仅需加登录与过滤

## 扩展指引

### 新增翻译引擎

1. 在 `localization/translators/` 新建适配器类，继承 `BaseTranslator`
2. 实现 `translate(self, messages, target_lang) -> str`
3. 在 `localization/translators/__init__.py` 中调用 `register_engine("引擎名", 类名)`
4. 重新启动，UI「引擎配置」下拉即出现新引擎

### 新增术语数据源

在 `localization/services/term_sources.py` 新增 `BaseTermSource` 子类，实现 `fetch_rows()`，并在 `fetch_terms` 中接入调度。

### 扩展提示词模板变量

在 `localization/services/prompt_service.py` 的 `PROMPT_VARS` 中新增 `(变量名, 说明)`，翻译调度时会自动注入。

## 数据模型

| 模型 | 说明 |
|------|------|
| `Project` | 一个上传文件 / 一段文本 = 一个工程 |
| `Entry` | 条目：一行一源多语言，`translations` 存 `{lang: text}` |
| `TermEntry` | 术语：`source_term → target_term` |
| `ApiConfig` | 翻译引擎配置（多引擎可配） |
| `ColumnTemplate` | 列映射模板（复用列结构） |
| `Org` | 组织（含邀请码 `join_code`） |
| `PromptTemplate` | 提示词模板（多角色消息序列） |

## 说明与限制（首期）

- 首期单用户使用，不做登录鉴权；数据模型已预留 `user_id`/`org_id`
- API 密钥存储于本地 SQLite，仅适合本地单机场景
- 翻译为同步调度，大批量数据翻译时页面会有等待（进度以最终结果反馈），后续可优化为后台任务
- 术语匹配采用子串检测，满足多数场景
