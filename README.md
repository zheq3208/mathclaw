# MathClaw

MathClaw 是一个面向初高中数学学习场景的多模态学习助手。它支持图片、截图、PDF 和文本输入，围绕一道题或一张试卷完成这条主链路：

`OCR -> 求解与验证 -> 薄弱点诊断 -> 引导式讲解 -> 变式题生成 -> 学习记忆更新`

这份 README 的目标不是解释所有内部细节，而是让第一次使用这个仓库的人能尽快跑起来。

## 1. 一句话说明

当前仓库已经内置了一套适合首跑的默认值：

- 默认模型提供商：`dashscope`
- 默认基座地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 默认模型：`qwen3-vl-plus`
- 默认视觉能力：开启
- 默认 QQ / 企业微信通道：关闭
- 默认 Tavily / Playwright / Filesystem MCP：关闭

也就是说，第一次运行时你至少只需要准备一个百炼 Qwen API Key；QQ、企业微信、Tavily 都是可选增强项。

## 2. 运行要求

建议环境：

- Python `3.10` - `3.13`
- Node.js `18+`
- npm `9+`
- Linux 服务器或 Linux 容器
- 能访问你配置的模型 API

如果你要启用可选 MCP：

- Playwright MCP 需要 `npx`
- Filesystem MCP 需要 `npx`
- Tavily MCP 需要 `Tavily API Key`

## 3. 安装依赖

```bash
cd /path/to/mathclaw
python -m pip install -U pip
python -m pip install -e .

cd console
npm install
```

如果机器上默认 `python` 不可用，可以换成你自己的 Conda/Miniconda Python，例如：

```bash
/root/miniconda3/bin/python -m pip install -U pip
/root/miniconda3/bin/python -m pip install -e .
```

## 4. 最简单的启动方式

一条命令同时启动后端和前端：

```bash
cd /path/to/mathclaw
bash start.sh
```

启动后默认地址：

- 后端：`http://127.0.0.1:6006`
- 前端：`http://127.0.0.1:6008`

`start.sh` 现在会自动把运行目录固定到仓库内部：

- 工作目录：`$REPO/.mathclaw`
- 密钥目录：`$REPO/.mathclaw.secret`
- 运行日志目录：`$REPO/.runtime`

如果你只想启动后端：

```bash
cd /path/to/mathclaw
python scripts/start_mathclaw6006.py
```

## 5. 启动后先验证

```bash
curl http://127.0.0.1:6006/api/health
curl http://127.0.0.1:6006/api/config/template
```

- `/api/health` 用于确认后端已启动
- `/api/config/template` 会返回默认配置模板和 quickstart 接口字段

## 6. 现在需要填哪些参数

你通常只需要关注以下几类参数。

### 6.1 模型参数

最少需要：

- `api_key`

常用可调：

- `provider`
- `base_url`
- `model_name`
- `supports_vision`

默认已经设成适合数学图片题的 DashScope/Qwen 组合，所以大多数情况下你只补 `api_key` 即可。

### 6.2 企业微信参数

如果你要接企业微信机器人，当前代码读取的是：

- `wecom_bot_id`
- `wecom_secret`
- `wecom_bot_prefix`，可选
- `wecom_welcome_message`，可选

这一部分的接入方式可以参考 [NanoBot](https://github.com/HKUDS/nanobot)，但字段名和最终配置结构以 MathClaw 当前代码为准。

### 6.3 QQ 参数

如果你要接 QQ 机器人，当前代码读取的是：

- `qq_app_id`
- `qq_client_secret`
- `qq_bot_prefix`，可选

这部分同样可以参考 [NanoBot](https://github.com/HKUDS/nanobot) 的注册流程，但参数名以本仓库为准。

### 6.4 Tavily 参数

如果你要启用搜索增强：

- `enable_tavily`
- `tavily_api_key`

## 7. 推荐配置接口

现在后端新增了两个直接给使用者用的接口：

- `GET /api/config/template`
- `POST /api/config/quickstart`

设计意图：

- `template` 负责告诉你默认值和字段列表
- `quickstart` 负责把你输入的参数写入配置，并尽量直接让模型热加载

### 7.1 看默认模板

```bash
curl http://127.0.0.1:6006/api/config/template
```

你会看到：

- 默认配置文件路径
- 默认 `DashScope + qwen3-vl-plus` 配置
- `quickstart` 支持的字段
- 各可选模块在启用时需要补哪些参数

### 7.2 最小可运行示例：只填百炼 Qwen API

```bash
curl -X POST http://127.0.0.1:6006/api/config/quickstart \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "<YOUR_DASHSCOPE_API_KEY>"
  }'
```

这条请求会：

- 把默认提供商设为 `dashscope`
- 把默认模型设为 `qwen3-vl-plus`
- 把 `supports_vision` 设为 `true`
- 把配置写到 `.mathclaw/config.json`
- 把提供商写到 `.mathclaw.secret/providers.json`
- 如果 API Key 有效，后端会尝试热加载这个模型

### 7.3 百炼 Qwen + 企业微信

```bash
curl -X POST http://127.0.0.1:6006/api/config/quickstart \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "<YOUR_DASHSCOPE_API_KEY>",
    "wecom_enabled": true,
    "wecom_bot_id": "<YOUR_WECOM_BOT_ID>",
    "wecom_secret": "<YOUR_WECOM_SECRET>",
    "wecom_bot_prefix": "",
    "wecom_welcome_message": "你好，我是 MathClaw。"
  }'
```

### 7.4 百炼 Qwen + QQ

```bash
curl -X POST http://127.0.0.1:6006/api/config/quickstart \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "<YOUR_DASHSCOPE_API_KEY>",
    "qq_enabled": true,
    "qq_app_id": "<YOUR_QQ_APP_ID>",
    "qq_client_secret": "<YOUR_QQ_CLIENT_SECRET>",
    "qq_bot_prefix": ""
  }'
```

### 7.5 启用 Tavily 搜索

```bash
curl -X POST http://127.0.0.1:6006/api/config/quickstart \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "<YOUR_DASHSCOPE_API_KEY>",
    "enable_tavily": true,
    "tavily_api_key": "<YOUR_TAVILY_API_KEY>"
  }'
```

### 7.6 百炼 Qwen + 企业微信 + 网络搜索

如果你要一次性启用百炼模型、企业微信和 Tavily 网络搜索，可以直接使用下面这条：

```bash
curl -X POST http://127.0.0.1:6006/api/config/quickstart \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "dashscope",
    "api_key": "<YOUR_DASHSCOPE_API_KEY>",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model_name": "qwen3-vl-plus",
    "supports_vision": true,
    "wecom_enabled": true,
    "wecom_bot_id": "<YOUR_WECOM_BOT_ID>",
    "wecom_secret": "<YOUR_WECOM_SECRET>",
    "wecom_bot_prefix": "",
    "wecom_welcome_message": "你好，我是 MathClaw。",
    "enable_tavily": true,
    "tavily_api_key": "<YOUR_TAVILY_API_KEY>"
  }'
```

说明：

- `QQ`、`企业微信`、`Tavily`、`Playwright MCP`、`Filesystem MCP` 这些开关可以同时启用
- 建议尽量一次性提交完整配置，而不是把不同示例分多次调用，否则后一次调用可能会覆盖前一次开关

## 8. 接口返回值怎么看

`POST /api/config/quickstart` 会返回这些关键信息：

- `runner_started`：模型是否已经被热加载
- `restart_required`：是否建议你重启后端以让通道或 MCP 生效
- `missing_required`：还缺哪些关键参数
- `summary`：当前配置摘要，不会直接回显密钥

一般可以按这个规则判断：

- `runner_started=true`：模型已可用，文本或图片问答可以直接试
- `restart_required=true`：你刚改了 QQ、企业微信或 MCP，建议重启一次后端
- `missing_required` 非空：说明当前配置还缺关键项

## 9. 前端和接口怎么验证

后端启动且模型配置好之后，可以这样检查：

```bash
curl http://127.0.0.1:6006/api/config/model
curl http://127.0.0.1:6006/api/providers
```

浏览器可直接打开：

- `http://127.0.0.1:6008`

如果你在云主机上运行，再由平台把 `6006/6008` 端口映射出去即可。

## 10. 重要文件位置

默认运行后，你会主要看到这些文件：

- `./.mathclaw/config.json`：主配置文件
- `./.mathclaw.secret/providers.json`：模型提供商配置
- `./.runtime/mathclaw6006-live.log`：后端日志
- `./.runtime/console6008-live.log`：前端日志

## 11. 当前推荐实践

如果你是第一次部署，建议按下面顺序做：

1. 安装 Python 和 Node 依赖。
2. 运行 `bash start.sh`。
3. 先调用 `GET /api/config/template` 看默认字段。
4. 再调用 `POST /api/config/quickstart`，至少填入 `api_key`。
5. 如果要接企业微信或 QQ，再补通道参数并重启一次后端。

## 12. 补充说明

- 当前代码虽然已经转向数学学习场景，但仓库里仍然保留了一些历史 `research` 命名和论文相关模块。
- 这不影响数学主链路运行。
- 文档里如果提到 `NanoBot`，仅用于说明 QQ 和企业微信注册思路；具体字段仍然以 MathClaw 当前代码为准。
