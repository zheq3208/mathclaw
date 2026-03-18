# CLI 命令行

MathClaw 提供命令行工具用于初始化、启动和管理。

## 安装后可用的命令

```bash
mathclaw <command> [options]
```

## 命令列表

### `init`

初始化工作目录：

```bash
mathclaw init             # 交互式初始化
mathclaw init --defaults  # 使用默认配置初始化
```

### `app`

启动 MathClaw 应用：

```bash
mathclaw app                    # 启动
mathclaw app --port 9090        # 指定端口
mathclaw app --host 0.0.0.0     # 指定主机地址
```

### `skills`

管理 Skills：

```bash
mathclaw skills list              # 列出已安装的 Skills
mathclaw skills install <url>     # 从 GitHub 安装 Skill
mathclaw skills uninstall <name>  # 卸载 Skill
```

### `config`

管理配置：

```bash
mathclaw config show              # 显示配置
mathclaw config set <key> <value> # 设置配置项
```

### `version`

显示版本信息：

```bash
mathclaw version
```

## 全局选项

| 选项            | 说明         |
| --------------- | ------------ |
| `--working-dir` | 指定工作目录 |
| `--verbose`     | 显示详细日志 |
| `--help`        | 显示帮助信息 |
