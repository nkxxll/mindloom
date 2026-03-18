from datetime import datetime

import click
from mindloom_core.models import JobResponse
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

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


def render_single_job(job: JobResponse, raw: bool = False, is_piped: bool = False) -> None:
    """Render a single job with all details in a copy-friendly format.
    
    Args:
        job: The job to render
        raw: If True, only output the result field as plain text
        is_piped: If True, output as plain ASCII without styling
    """
    
    # Raw mode: only output the result
    if raw:
        if job.result:
            click.echo(job.result)
        return
    
    # Piped mode: plain ASCII output
    if is_piped:
        click.echo("=" * 80)
        click.echo(f"Job ID: {job.id}")
        click.echo(f"Task Type: {job.task_type}")
        click.echo(f"Status: {job.status}")
        click.echo(f"Created: {format_datetime(job.created_at)}")
        click.echo(f"Updated: {format_datetime(job.updated_at)}")
        click.echo("=" * 80)
        
        if job.content:
            click.echo()
            click.echo("--- CONTENT " + "-" * 68)
            click.echo(job.content)
            click.echo("-" * 80)
        
        if job.result:
            click.echo()
            click.echo("--- RESULT " + "-" * 69)
            click.echo(job.result)
            click.echo("-" * 80)
        elif job.status == "pending":
            click.echo()
            click.echo("Job is pending - no result yet")
        elif job.status == "running":
            click.echo()
            click.echo("Job is running - no result yet")
        elif job.status == "failed":
            click.echo()
            click.echo("Job failed - no result available")
        return
    
    # Rich styled output for TTY
    # Job header with metadata
    metadata = Text()
    metadata.append("Job ID: ", style="bold cyan")
    metadata.append(f"{job.id}\n")
    
    metadata.append("Task Type: ", style="bold cyan")
    metadata.append(f"{job.task_type}\n")
    
    metadata.append("Status: ", style="bold cyan")
    metadata.append(style_status(job.status))
    metadata.append("\n")
    
    metadata.append("Created: ", style="bold cyan")
    metadata.append(f"{format_datetime(job.created_at)}\n")
    
    metadata.append("Updated: ", style="bold cyan")
    metadata.append(f"{format_datetime(job.updated_at)}")
    
    console.print(Panel(metadata, title="[bold]Job Information[/bold]", border_style="cyan"))
    
    # Content section (if available)
    if job.content:
        console.print()
        console.rule("[bold cyan]Content[/bold cyan]", style="cyan")
        console.print(job.content)
        console.rule(style="cyan")
    
    # Result section (if available)
    if job.result:
        console.print()
        console.rule("[bold green]Result[/bold green]", style="green")
        console.print(job.result)
        console.rule(style="green")
    elif job.status == "pending":
        console.print()
        console.print("[yellow]Job is pending - no result yet[/yellow]")
    elif job.status == "running":
        console.print()
        console.print("[cyan]Job is running - no result yet[/cyan]")
    elif job.status == "failed":
        console.print()
        console.print("[red]Job failed - no result available[/red]")
