# CLI (Command Line Interface)

MathClaw provides CLI tools for initialization, startup, and management.

## Commands

```bash
mathclaw <command> [options]
```

## Command Reference

### `init`

Initialize the working directory:

```bash
mathclaw init             # Interactive init
mathclaw init --defaults  # Init with defaults
```

### `app`

Start the MathClaw application:

```bash
mathclaw app                    # Start
mathclaw app --port 9090        # Specify port
mathclaw app --host 0.0.0.0     # Specify host
```

### `skills`

Manage Skills:

```bash
mathclaw skills list              # List installed skills
mathclaw skills install <url>     # Install skill from GitHub
mathclaw skills uninstall <name>  # Uninstall skill
```

### `config`

Manage configuration:

```bash
mathclaw config show              # Show config
mathclaw config set <key> <value> # Set a config value
```

### `version`

Show version info:

```bash
mathclaw version
```

## Global Options

| Option          | Description               |
| --------------- | ------------------------- |
| `--working-dir` | Specify working directory |
| `--verbose`     | Show verbose logging      |
| `--help`        | Show help                 |
