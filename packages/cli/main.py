from datetime import datetime

import click
from mindloom_core.models import JobResponse
from rich.console import Console
from rich.table import Table

from config import get_config, initialize_config

console = Console()
cfg = get_config()


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat(sep=" ", timespec="seconds")


def _truncate_text(value: str | None, max_length: int = 60) -> str:
    if not value:
        return "-"
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _style_status(status: str) -> str:
    status_styles = {
        "pending": "yellow",
        "running": "cyan",
        "completed": "green",
        "failed": "red",
    }
    style = status_styles.get(status.lower(), "white")
    return f"[{style}]{status}[/{style}]"


def _render_jobs_table(jobs: list[JobResponse], title: str = "Jobs") -> None:
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
            _style_status(job.status),
            _format_datetime(job.created_at),
            _format_datetime(job.updated_at),
            _truncate_text(job.result),
        )

    console.print(table)


@click.group()
def cli():
    pass


@cli.command()
def health():
    from health import Health

    h = Health(cfg)
    try:
        res = h.get_health()
        if res:
            click.secho("OK", fg="green")
        else:
            click.secho("ERROR", fg="red", err=True)
    except Exception as e:
        click.secho(f"ERROR: {e}", fg="red", err=True)


@cli.group(invoke_without_command=True)
@click.argument("id", required=False, type=click.INT)
@click.pass_context
def jobs(ctx: click.Context, id: int | None):
    if ctx.invoked_subcommand is not None:
        return

    from jobs import Jobs

    j = Jobs(cfg)
    if id is not None:
        job = j.get_job_by_id(id)
        _render_jobs_table([job], title=f"Job {id}")
    else:
        jobs = j.get_jobs()
        _render_jobs_table(jobs)


@cli.command()
@click.argument("id", type=click.INT)
def restart(id: int):
    from jobs import Jobs

    j = Jobs(cfg)
    job = j.restart_by_id(id)
    _render_jobs_table([job], title=f"Restarted Job {id}")


@cli.group()
def config():
    pass


@config.command()
def init():
    initialize_config()
