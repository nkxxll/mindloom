from pathlib import Path

import click


def read_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise click.ClickException(
            f"Failed to decode {file_path} as UTF-8: {exc}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"Failed to read {file_path}: {exc}") from exc


def write_file(file_path: Path, content: str) -> None:
    try:
        file_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Failed to write {file_path}: {exc}") from exc
