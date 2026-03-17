from datetime import datetime

import click
from mindloom_core.models import JobResponse
from rich.console import Console
from rich.table import Table

console = Console()


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat(sep=" ", timespec="seconds")


def truncate_text(value: str | None, max_length: int = 60) -> str:
    if not value:
        return "-"
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def style_status(status: str) -> str:
    status_styles = {
        "pending": "yellow",
        "running": "cyan",
        "completed": "green",
        "failed": "red",
    }
    style = status_styles.get(status.lower(), "white")
    return f"[{style}]{status}[/{style}]"


def render_jobs_table(jobs: list[JobResponse], title: str = "Jobs") -> None:
    if not jobs:
        click.echo("No jobs found.")
        return

    table = Table(title=title)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Task Type", style="magenta")
    table.add_column("Status")
    table.add_column("Created", no_wrap=True)
    table.add_column("Updated", no_wrap=True)
    table.add_column("Result")

    for job in jobs:
        table.add_row(
            str(job.id),
            job.task_type,
            style_status(job.status),
            format_datetime(job.created_at),
            format_datetime(job.updated_at),
            truncate_text(job.result),
        )

    console.print(table)
