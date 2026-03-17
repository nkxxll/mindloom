from pathlib import Path

import click

from mindloom_cli.config import get_config, initialize_config
from mindloom_cli.display import render_jobs_table
from mindloom_cli.fileio import read_file, write_file

cfg = get_config()


@click.group()
def cli():
    pass


@cli.command()
def health():
    from mindloom_cli.health import Health

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

    from mindloom_cli.jobs import Jobs

    j = Jobs(cfg)
    if id is not None:
        job = j.get_job_by_id(id)
        render_jobs_table([job], title=f"Job {id}")
    else:
        jobs = j.get_jobs()
        render_jobs_table(jobs)


@cli.command()
@click.argument("id", type=click.INT)
def restart(id: int):
    from mindloom_cli.jobs import Jobs

    j = Jobs(cfg)
    job = j.restart_by_id(id)
    render_jobs_table([job], title=f"Restarted Job {id}")


@cli.group()
def config():
    pass


@config.command()
def init():
    initialize_config()


@cli.command()
@click.argument(
    "file_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option("--model", default=None, help="Optional model override.")
def file(file_path: Path, model: str | None):
    from mindloom_cli.section import Section

    s = Section(cfg)
    content = read_file(file_path)
    result = s.improve_file(content, file_path, model)
    write_file(file_path, result)
    click.secho(f"Updated {file_path}", fg="green")


@cli.command()
@click.argument(
    "file_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--range",
    "line_range",
    default=None,
    help="Optional line range in START:END format (1-based, inclusive).",
)
@click.option("--model", default=None, help="Optional model override.")
def section(file_path: Path, line_range: str | None, model: str | None):
    from mindloom_cli.section import Section, parse_line_range

    s = Section(cfg)
    content = read_file(file_path)

    if line_range is None:
        result = s.improve_file(content, file_path, model)
        write_file(file_path, result)
        click.secho(f"Updated {file_path}", fg="green")
        return

    lines = content.splitlines(keepends=True)
    if not lines:
        raise click.ClickException(
            f"{file_path} is empty; nothing to improve in a range."
        )

    try:
        start, end = parse_line_range(line_range, len(lines))
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    selected_content = "".join(lines[start - 1 : end])
    improved = s.improve_section(selected_content, file_path, start, end, model)
    updated_content = "".join(lines[: start - 1]) + improved + "".join(lines[end:])
    write_file(file_path, updated_content)
    click.secho(f"Updated lines {start}:{end} in {file_path}", fg="green")


def main():
    cli()


if __name__ == "__main__":
    main()
