import os
from pathlib import Path
import tomllib

from pydantic import BaseModel


class Config(BaseModel):
    host: str = "http://127.0.0.1"


def _serialize_toml_value(value) -> str:
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    raise TypeError(f"Unsupported config value type: {type(value)!r}")


def generate_default_config() -> str:
    config_items = DEFAULT_CONFIG.model_dump()
    lines = [f"{key} = {_serialize_toml_value(value)}" for key, value in config_items.items()]
    return "\n".join(lines) + "\n"


def get_config_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / "mindloom" / "config.toml"
    return Path.home() / ".config" / "mindloom" / "config.toml"


def is_config_initialized() -> bool:
    return CONFIG_PATH.is_file()


def load_config() -> Config:
    with CONFIG_PATH.open("rb") as config_file:
        data = tomllib.load(config_file)
    return Config(**data)


def get_default_config() -> Config:
    return DEFAULT_CONFIG.model_copy(deep=True)


def get_config() -> Config:
    if is_config_initialized():
        return load_config()
    return get_default_config()


def initialize_config() -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return CONFIG_PATH


DEFAULT_CONFIG = Config(host="http://127.0.0.1")
CONFIG_PATH = get_config_path()
DEFAULT_CONFIG_TEXT = generate_default_config()
