
---

# ResearchClaw Docs 内容提取汇总

来源：ResearchClaw 中文文档站点 `/docs/` 页面内容整理版
说明：本文为提取整理稿，保留原有章节结构、命令、代码块与主要表格信息。

## 目录概览

项目介绍
快速开始
控制台
频道
Skills
MCP
Memory 记忆系统
Compact 对话压缩
命令系统
Heartbeat 心跳
配置与工作目录
CLI 命令行
常见问题（FAQ）
社区
贡献指南

---

# ResearchClaw 项目介绍

ResearchClaw 是一款基于 AI 的科研助手工具，帮助研究人员追踪论文、管理文献、记录实验、分析数据。

## 核心特性

论文搜索与追踪：支持 ArXiv、Semantic Scholar 等论文源，自动追踪研究领域最新成果
文献管理：BibTeX 管理、引用格式化、文献库检索
实验与分析：实验记录、数据分析、可视化
多频道支持：钉钉、飞书、QQ、Discord、iMessage 等
Skills 扩展：内置科研技能，支持自定义扩展和定时任务
本地掌控：数据本地存储，支持云端部署

## 架构概览

ResearchClaw 由以下模块组成：

Agent 引擎：基于 ReAct 模式的智能体，负责理解用户意图并调用工具
Skills 系统：可扩展的技能框架，支持自定义科研技能
频道层：统一的消息收发接口，支持多种 IM 平台
控制台：Web 管理界面，用于配置和监控
Memory：对话记忆与上下文管理

## 快速开始

```bash
pip install researchclaw
researchclaw init --defaults
researchclaw app
```

安装完成后，访问 `http://localhost:8088` 即可进入控制台。
详细的安装与配置请参阅“快速开始”文档。

---

# 快速开始

## 环境要求

Python 3.10+
pip 或 uv

## 安装

### 方式一：pip 安装（推荐）

```bash
pip install researchclaw
```

### 方式二：一键安装脚本（macOS / Linux）

```bash
curl -fsSL https://researchclaw.dev/install.sh | bash
```

### 方式三：Docker

```bash
docker pull researchclaw/researchclaw:latest
docker run -p 8088:8088 -v researchclaw-data:/app/working researchclaw/researchclaw:latest
```

## 初始化

首次使用前，需要初始化工作目录：

```bash
researchclaw init --defaults
```

这会创建默认的配置文件和工作目录。

## 启动

```bash
researchclaw app
```

启动后访问 `http://localhost:8088` 进入控制台。

## 配置 LLM

在控制台中配置你的大语言模型提供商和 API Key：

打开控制台 → 设置
选择模型提供商（OpenAI、Claude、通义千问等）
填入 API Key
保存后即可开始使用

## 下一步

频道配置 — 接入钉钉、飞书等 IM 平台
Skills — 了解和扩展科研技能
配置与工作目录 — 详细的配置说明

---

# 控制台

ResearchClaw 内置 Web 控制台，提供可视化的管理界面。

## 访问

启动 ResearchClaw 后，访问 `http://localhost:8088` 即可进入控制台。

## 功能

### 对话

直接与 AI 助手对话
查看对话历史
多会话管理

### 设置

模型提供商配置
API Key 管理
频道开关
Skills 管理

### 环境变量

管理环境变量
配置论文源 API Key（如 Semantic Scholar）

### Skills 管理

查看已安装的 Skills
启用 / 禁用 Skills
配置定时任务

## 技术栈

控制台使用 React + TypeScript 构建，通过 WebSocket 与后端实时通信。

---

# 频道

频道是 ResearchClaw 与外部 IM 平台的连接桥梁。通过配置频道，你可以在常用的即时通讯工具中与 AI 助手交互。

## 支持的频道

| 频道           | 说明                      |
| ------------ | ----------------------- |
| 钉钉           | 企业级 IM，支持群消息和私聊         |
| 飞书           | 字节跳动旗下 IM，支持群组和私聊       |
| QQ           | 基于 QQ 开放平台，支持频道和私聊      |
| Discord      | 海外常用 IM，支持 Bot 方式接入     |
| iMessage     | macOS 原生消息，需本地部署在 Mac 上 |
| WeChat (WIP) | 微信接入（开发中）               |

## 配置方式

### 在控制台中配置

打开控制台 → 设置 → 频道
启用目标频道
填入所需的凭证信息（App Key、Secret 等）
保存并重启

### 在配置文件中配置

编辑 `channels.yaml` 文件：

```yaml
dingtalk:
  enabled: true
  app_key: "your-app-key"
  app_secret: "your-app-secret"
```

## 注意事项

每个频道需要在对应平台创建 Bot 应用并获取凭证
iMessage 频道仅支持 macOS
频道配置变更后需重启服务

---

# Skills

Skills 是 ResearchClaw 的可扩展技能系统，为 AI 助手提供专业的科研能力。

## 内置 Skills

ResearchClaw 内置了多种科研相关技能：

论文搜索：在 ArXiv、Semantic Scholar 等平台搜索论文
论文追踪：定期追踪指定领域或关键词的最新论文
文献管理：管理 BibTeX 文件、生成引用
天气查询：查询天气信息（日常辅助）

## Skill 结构

每个 Skill 是一个独立的 Python 模块，包含：

```text
my_skill/
├── __init__.py
├── skill.json          # 技能元信息
├── handler.py          # 主逻辑
└── requirements.txt    # 依赖（可选）
```

`skill.json`

```json
{
  "name": "my_skill",
  "version": "1.0.0",
  "description": "A custom research skill",
  "author": "Your Name",
  "tags": ["research", "papers"]
}
```

## 安装 Skill

### 从 GitHub 安装

在对话中发送：

```text
安装 skill https://github.com/user/repo
```

### 手动安装

将 Skill 文件夹放入工作目录的 `skills/` 文件夹中。

## 定时任务

Skills 支持 Cron 定时任务：

```json
{
  "cron": "0 9 * * *",
  "cron_prompt": "搜索昨天发布的 LLM Agent 相关论文"
}
```

## 自定义开发

参考 `CONTRIBUTING` 了解如何开发自定义 Skill。

---

# MCP (Model Context Protocol)

ResearchClaw 支持 MCP 协议，允许接入外部工具和服务。

## 什么是 MCP

MCP（Model Context Protocol）是一个标准化协议，允许 AI 助手与外部工具进行交互。通过 MCP，你可以为 ResearchClaw 接入更多工具和数据源。

## 配置 MCP 服务

在 `mcp.yaml` 中配置 MCP 服务器：

```yaml
servers:
  - name: "my-mcp-server"
    url: "http://localhost:3000"
    enabled: true
```

## 使用场景

接入本地知识库
连接数据库进行数据查询
调用自定义 API 服务
扩展文件系统操作能力

## 注意事项

MCP 服务器需要独立部署和运行
确保 MCP 服务器的端口可访问
建议在安全的网络环境中使用

---

# Memory 记忆系统

ResearchClaw 的 Memory 系统管理对话历史和上下文信息，确保 AI 助手能够理解对话的连续性。

## 工作原理

每次对话都会被记录到 Memory 中。当新消息到来时，系统会加载相关的历史消息作为上下文，帮助模型更好地理解和回答。

## 消息存储

对话消息存储在工作目录的 `memory/` 文件夹中，按会话 ID 组织：

```text
working/
└── memory/
    ├── session_001.json
    ├── session_002.json
    └── ...
```

## 上下文窗口

由于 LLM 的上下文窗口有限，Memory 系统会自动管理消息的截取和压缩。

相关功能：
Compact 压缩 — 对话压缩机制
命令系统 — 管理 Memory 的命令

---

# Compact 对话压缩

当对话历史过长时，Compact 机制会自动压缩旧消息，保留关键信息同时节省上下文窗口空间。

## 工作原理

当消息数量或 Token 数超过阈值时，触发 Compact
系统使用 LLM 对旧消息进行摘要
摘要替换原始消息，释放上下文空间
新消息继续在压缩后的上下文中积累

## 配置

在 `config.yaml` 中配置 Compact 参数：

```yaml
memory:
  compact:
    enabled: true
    max_messages: 50
    summary_prompt: "请总结以上对话的关键内容"
```

## 手动触发

你也可以在对话中手动触发压缩：

```text
/compact
```

## 注意事项

Compact 会调用 LLM 生成摘要，产生额外的 API 费用
压缩后的摘要可能丢失部分细节信息
建议根据使用场景调整阈值

---

# 命令系统

ResearchClaw 支持在对话中使用命令来控制系统行为。

## 可用命令

| 命令                  | 说明                |
| ------------------- | ----------------- |
| `/help`             | 显示帮助信息            |
| `/compact`          | 手动触发对话压缩          |
| `/clear`            | 清除当前会话的对话历史       |
| `/reset`            | 重置助手状态            |
| `/skills`           | 列出已安装的 Skills     |
| `/install <url>`    | 从 GitHub 安装 Skill |
| `/uninstall <name>` | 卸载 Skill          |

## 使用方式

在任意频道的对话中，以 `/` 开头输入命令：

```text
/help
/install https://github.com/user/my-skill
```

## 命令与自然语言

除了命令，你也可以用自然语言描述需求，AI 助手会理解并执行对应操作：

```text
帮我安装这个 Skill: https://github.com/user/my-skill
```

效果等同于：

```text
/install https://github.com/user/my-skill
```

---

# Heartbeat 心跳

Heartbeat 是 ResearchClaw 的定时心跳机制，用于执行周期性任务。

## 工作原理

Heartbeat 按照配置的间隔定期运行，检查并执行以下任务：

Skill 定时任务（Cron 触发）
频道连接状态检查
内存清理

## 配置

在 `config.yaml` 中配置心跳参数：

```yaml
heartbeat:
  enabled: true
  interval: 60 # 秒
```

## Cron 任务

Heartbeat 是 Skill Cron 任务的驱动引擎。每次心跳时，系统检查所有 Skill 的 Cron 表达式，执行到期的任务。

示例场景：
每天早上 9 点推送最新论文
每周一生成文献追踪报告
每小时检查 ArXiv 上的新论文

## 注意事项

心跳间隔不宜设置过短，避免不必要的资源消耗
Cron 任务会在心跳触发时执行，实际执行时间可能有少量延迟

---

# 配置与工作目录

## 工作目录

ResearchClaw 的所有数据和配置文件都存储在工作目录中。默认工作目录为 `~/.researchclaw/`。

## 目录结构

```text
~/.researchclaw/
├── config.yaml        # 主配置文件
├── channels.yaml      # 频道配置
├── mcp.yaml           # MCP 配置
├── PROFILE.md         # 助手人设描述
├── skills/            # Skills 文件夹
│   ├── built_in/      # 内置 Skills
│   └── custom/        # 自定义 Skills
├── memory/            # 对话记忆
└── logs/              # 日志文件
```

## 配置文件

### `config.yaml`

主配置文件，包含 LLM、Memory、Heartbeat 等配置：

```yaml
llm:
  provider: openai
  model: gpt-4o
  api_key: "sk-xxx"

memory:
  compact:
    enabled: true
    max_messages: 50

heartbeat:
  enabled: true
  interval: 60

server:
  host: "0.0.0.0"
  port: 8088
```

### `PROFILE.md`

定义 AI 助手的人设和行为风格。你可以自定义助手的性格、专长领域和回答风格。

## 环境变量

部分敏感配置可通过环境变量设置：

| 变量名                        | 说明                |
| -------------------------- | ----------------- |
| `RESEARCHCLAW_WORKING_DIR` | 工作目录路径            |
| `OPENAI_API_KEY`           | OpenAI API Key    |
| `ANTHROPIC_API_KEY`        | Anthropic API Key |

## CLI 配置

使用 CLI 命令管理配置：

```bash
researchclaw config show          # 显示当前配置
researchclaw config set key value # 设置配置项
```

---

# CLI 命令行

ResearchClaw 提供命令行工具用于初始化、启动和管理。

## 安装后可用的命令

```bash
researchclaw <command> [options]
```

## 命令列表

### init

初始化工作目录：

```bash
researchclaw init             # 交互式初始化
researchclaw init --defaults  # 使用默认配置初始化
```

### app

启动 ResearchClaw 应用：

```bash
researchclaw app                # 启动
researchclaw app --port 9090    # 指定端口
researchclaw app --host 0.0.0.0 # 指定主机地址
```

### skills

管理 Skills：

```bash
researchclaw skills list              # 列出已安装的 Skills
researchclaw skills install <url>     # 从 GitHub 安装 Skill
researchclaw skills uninstall <name>  # 卸载 Skill
```

### config

管理配置：

```bash
researchclaw config show              # 显示配置
researchclaw config set <key> <value> # 设置配置项
```

### version

显示版本信息：

```bash
researchclaw version
```

## 全局选项

| 选项              | 说明     |
| --------------- | ------ |
| `--working-dir` | 指定工作目录 |
| `--verbose`     | 显示详细日志 |
| `--help`        | 显示帮助信息 |

---

# 常见问题（FAQ）

## ResearchClaw 支持哪些 LLM 模型？

支持 OpenAI（GPT-4o、GPT-4 等）、Anthropic（Claude 3.5 等）、通义千问、DeepSeek、Ollama（本地模型）等多种模型提供商。

## 数据存储在哪里？安全吗？

所有数据默认存储在本地工作目录（`~/.researchclaw/`）中，不会上传到云端。API Key 等敏感信息加密存储。

## 如何切换语言？

ResearchClaw 支持中英文双语。在控制台界面点击语言切换按钮即可切换。CLI 默认使用系统语言。

## 支持哪些论文数据库？

目前支持 ArXiv、Semantic Scholar。通过 Skills 系统可以扩展支持更多数据库和论文源。

## 如何开发自定义 Skill？

参考 Skills 文档和贡献指南。每个 Skill 是一个独立的 Python 模块，包含 `skill.json` 元信息文件。

## 可以在服务器上部署吗？

可以。推荐使用 Docker 部署：

```bash
docker pull researchclaw/researchclaw:latest
docker run -d -p 8088:8088 -v researchclaw-data:/app/working researchclaw/researchclaw:latest
```

## 频道配置后无法连接怎么办？

检查 API Key / Secret 是否正确
确认网络环境可以访问对应平台
查看日志文件排查错误信息
确保已在对应平台创建 Bot 应用并完成权限配置

## ResearchClaw 和 CoPaw 是什么关系？

ResearchClaw 基于 CoPaw 的架构进行了科研领域的定制和优化，专注于论文搜索、文献管理、实验追踪等科研场景。

---

# 社区

欢迎加入 ResearchClaw 社区！

## 参与方式

### GitHub

项目仓库 — 源码、Issues、Pull Requests
提交 Issue 报告 Bug 或提出功能建议
提交 Pull Request 贡献代码

### 讨论

GitHub Discussions — 提问、分享经验、讨论功能
分享你开发的自定义 Skills

## 行为准则

我们致力于营造友好、包容的社区环境。参与社区时请：

尊重他人
友善沟通
聚焦技术讨论
帮助新成员融入

## 贡献

想要贡献代码？请参阅“贡献指南”。

---

# 贡献指南

感谢你对 ResearchClaw 的贡献兴趣！

## 开发环境

### 后端（Python）

```bash
# 克隆仓库
git clone https://github.com/MingxinYang/ResearchClaw.git
cd ResearchClaw

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装开发依赖
pip install -e ".[dev]"
```

### 控制台（前端）

```bash
cd console
npm install
npm run dev
```

### 官网（前端）

```bash
cd website
npm install
npm run dev
```

## 贡献流程

Fork 仓库
创建特性分支：`git checkout -b feature/my-feature`
提交修改：`git commit -m "feat: add my feature"`
推送分支：`git push origin feature/my-feature`
创建 Pull Request

## 代码规范

Python 代码遵循 PEP 8
TypeScript 代码使用 ESLint + Prettier
Commit 信息遵循 Conventional Commits 规范

## Skill 贡献

开发自定义 Skill：

参考 Skills 文档了解 Skill 结构
在 `skills/` 目录下创建新 Skill
编写 `skill.json` 和处理逻辑
测试确保功能正常
提交 PR 或发布到独立仓库

## 问题反馈

使用 GitHub Issues 报告 Bug
提供复现步骤和环境信息
附上相关的日志输出

---
