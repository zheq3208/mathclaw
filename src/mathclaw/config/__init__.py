"""Configuration package."""

from mathclaw.config.config import (
    build_default_config,
    config_path,
    get_heartbeat_config,
    get_heartbeat_query_path,
    load_config,
    merge_config,
    save_config,
    update_last_dispatch,
)

__all__ = [
    "build_default_config",
    "config_path",
    "load_config",
    "merge_config",
    "save_config",
    "get_heartbeat_config",
    "get_heartbeat_query_path",
    "update_last_dispatch",
    "ConfigWatcher",
]


def __getattr__(name: str):
    if name == "ConfigWatcher":
        from mathclaw.config.watcher import ConfigWatcher

        return ConfigWatcher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
