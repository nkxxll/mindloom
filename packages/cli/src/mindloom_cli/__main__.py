import sys
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar

import click
import httpx
from rich.console import Console

from mindloom_cli.config import get_config, initialize_config
from mindloom_cli.display import render_jobs_table, render_single_job
from mindloom_cli.fileio import read_file, write_file

cfg = get_config()
_REQUEST_WAIT_MESSAGE = "Waiting for response..."
_BRAILLE_SPINNER = "dots"
_SPINNER_CONSOLE = Console(stderr=True)

P = ParamSpec("P")
T = TypeVar("T")


class StyledError(click.ClickException):
    def show(self, file=None):
        if file is None:
            file = sys.stderr
        click.secho(f"💥 Error: {self.format_message()}", fg="red", bold=True, err=True)


def with_response_spinner(
    operation: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    try:
        if not sys.stderr.isatty():
            return operation(*args, **kwargs)

        with _SPINNER_CONSOLE.status(_REQUEST_WAIT_MESSAGE, spinner=_BRAILLE_SPINNER):
            return operation(*args, **kwargs)
    except httpx.ConnectError:
        raise StyledError(
            f"Could not connect to the server at {cfg.host}. Is it running?"
        )


class DefaultCommandGroup(click.Group):
    def __init__(self, *args, default_command: str, **kwargs):
        self.default_command = default_command
        super().__init__(*args, **kwargs)

    def resolve_command(self, ctx: click.Context, args: list[str]):
        if args:
            non_option_tokens = [arg for arg in args if not arg.startswith("-")]
            if non_option_tokens and non_option_tokens[0] not in self.commands:
                args = [self.default_command, *args]
        return super().resolve_command(ctx, args)


def with_content_input(command):
    command = click.option(
        "--text",
        default=None,
        help="Inline input content.",
    )(command)
    command = click.option(
        "--file",
        "input_file",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        default=None,
        help="Read input content from a file.",
    )(command)
    return command


def resolve_content_input(text: str | None, input_file: Path | None) -> str:
    if text is not None and input_file is not None:
        raise click.UsageError("Use either --text or --file, not both.")

    if input_file is not None:
        return read_file(input_file)

    if text is not None:
        return text

    if not sys.stdin.isatty():
        stdin_content = sys.stdin.read()
        if stdin_content:
            return stdin_content

    if sys.stdin.isatty():
        return click.prompt("Enter content")

    raise click.UsageError("No input provided. Use --text, --file, or stdin.")


def handle_async_result(result: str | int) -> None:
    """Handle result that could be content (sync) or job_id (async)."""
    if isinstance(result, int):
        click.secho(f"Job started with ID: {result}", fg="green")
        click.secho(f"Check status with: mindloom jobs {result}", fg="cyan")
    else:
        click.echo(result)


@click.group()
def cli():
    pass


@cli.command()
def health():
    from mindloom_cli.health import Health

    h = Health(cfg)
    try:
        res = with_response_spinner(h.get_health)
        if res:
            click.secho("OK", fg="green")
        else:
            click.secho("ERROR", fg="red", err=True)
    except Exception as e:
        click.secho(f"ERROR: {e}", fg="red", err=True)


@cli.command()
@click.argument("question")
@click.option(
    "--md",
    "markdown",
    is_flag=True,
    help="Format the answer as a Markdown article for note-taking.",
)
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def ask(question: str, markdown: bool, model: str | None, async_mode: bool):
    from mindloom_cli.ask import Ask

    a = Ask(cfg)
    result = with_response_spinner(a.ask, question, markdown=markdown, model=model, async_mode=async_mode)
    if isinstance(result, int):
        click.secho(f"Job started with ID: {result}", fg="green")
        click.secho(f"Check status with: mindloom jobs {result}", fg="cyan")
    else:
        click.echo(result)


@cli.group(invoke_without_command=True)
@click.argument("id", required=False, type=click.INT)
@click.option(
    "-r",
    "--raw",
    is_flag=True,
    help="Output only the result field as plain text (no formatting).",
)
@click.pass_context
def jobs(ctx: click.Context, id: int | None, raw: bool):
    if ctx.invoked_subcommand is not None:
        return

    from mindloom_cli.jobs import GetJobByIdError, Jobs

    j = Jobs(cfg)
    if id is not None:
        try:
            job = with_response_spinner(j.get_job_by_id, id)
            is_piped = not sys.stdout.isatty()
            render_single_job(job, raw=raw, is_piped=is_piped)
        except GetJobByIdError as e:
            raise StyledError(f"Job {id} not found (status code: {e.status_code})")
    else:
        jobs = with_response_spinner(j.get_jobs)
        render_jobs_table(jobs)


@cli.command()
@click.argument("id", type=click.INT)
def restart(id: int):
    from mindloom_cli.jobs import Jobs, RestartJobError

    j = Jobs(cfg)
    try:
        job = with_response_spinner(j.restart_by_id, id)
        render_jobs_table([job], title=f"Restarted Job {id}")
    except RestartJobError as e:
        raise StyledError(f"Failed to restart job {id}: {e.message}")


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
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def file(file_path: Path, model: str | None, async_mode: bool):
    from mindloom_cli.section import Section

    s = Section(cfg)
    content = read_file(file_path)
    result = with_response_spinner(s.improve_file, content, file_path, model, async_mode)
    if isinstance(result, int):
        click.secho(f"Job started with ID: {result}", fg="green")
        click.secho(f"Check status with: mindloom jobs {result}", fg="cyan")
    else:
        write_file(file_path, result)
        click.secho(f"Updated {file_path}", fg="green")


@cli.group(cls=DefaultCommandGroup, default_command="improve")
def section():
    pass


@section.command("improve")
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
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def section_improve(file_path: Path, line_range: str | None, model: str | None, async_mode: bool):
    from mindloom_cli.section import Section, parse_line_range

    s = Section(cfg)
    content = read_file(file_path)

    if line_range is None:
        result = with_response_spinner(s.improve_file, content, file_path, model, async_mode)
        if isinstance(result, int):
            click.secho(f"Job started with ID: {result}", fg="green")
            click.secho(f"Check status with: mindloom jobs {result}", fg="cyan")
        else:
            write_file(file_path, result)
            click.secho(f"Updated {file_path}", fg="green")
        return

    lines = content.splitlines(keepends=True)
    if not lines:
        raise StyledError(
            f"{file_path} is empty; nothing to improve in a range."
        )

    try:
        start, end = parse_line_range(line_range, len(lines))
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    selected_content = "".join(lines[start - 1 : end])
    improved = with_response_spinner(
        s.improve_section, selected_content, file_path, start, end, model, async_mode
    )
    if isinstance(improved, int):
        click.secho(f"Job started with ID: {improved}", fg="green")
        click.secho(f"Check status with: mindloom jobs {improved}", fg="cyan")
    else:
        updated_content = "".join(lines[: start - 1]) + improved + "".join(lines[end:])
        write_file(file_path, updated_content)
        click.secho(f"Updated lines {start}:{end} in {file_path}", fg="green")


@section.command("extend")
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
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def section_extend(file_path: Path, line_range: str | None, model: str | None, async_mode: bool):
    from mindloom_cli.section import Section, parse_line_range

    s = Section(cfg)
    content = read_file(file_path)
    lines = content.splitlines(keepends=True)
    if not lines:
        raise StyledError(f"{file_path} is empty; nothing to extend.")

    if line_range is None:
        start, end = 1, len(lines)
    else:
        try:
            start, end = parse_line_range(line_range, len(lines))
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

    selected_content = "".join(lines[start - 1 : end])
    extended = with_response_spinner(
        s.extend_section, selected_content, file_path, start, end, model, async_mode
    )
    if isinstance(extended, int):
        click.secho(f"Job started with ID: {extended}", fg="green")
        click.secho(f"Check status with: mindloom jobs {extended}", fg="cyan")
    else:
        updated_content = "".join(lines[: start - 1]) + extended + "".join(lines[end:])
        write_file(file_path, updated_content)
        click.secho(f"Extended lines {start}:{end} in {file_path}", fg="green")


@cli.group()
def email():
    pass


@email.command("improve")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def email_improve(text: str | None, input_file: Path | None, model: str | None, async_mode: bool):
    from mindloom_cli.email import Email

    e = Email(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(e.improve_email, content, model, async_mode)
    handle_async_result(result)


@email.command("write")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def email_write(text: str | None, input_file: Path | None, model: str | None, async_mode: bool):
    from mindloom_cli.email import Email

    e = Email(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(e.write_email, content, model, async_mode)
    handle_async_result(result)


@cli.group()
def text():
    pass


@text.command("summarize")
@with_content_input
@click.option(
    "--max-length",
    type=click.INT,
    default=None,
    help="Optional maximum length hint for summarization.",
)
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def text_summarize(
    text: str | None,
    input_file: Path | None,
    max_length: int | None,
    model: str | None,
    async_mode: bool,
):
    from mindloom_cli.text import Text

    t = Text(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(
        t.summarize, content, max_length=max_length, model=model, async_mode=async_mode
    )
    handle_async_result(result)


@text.command("translate")
@with_content_input
@click.option("--target-language", required=True, help="Target language for translation.")
@click.option("--source-language", default=None, help="Optional source language.")
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def text_translate(
    text: str | None,
    input_file: Path | None,
    target_language: str,
    source_language: str | None,
    model: str | None,
    async_mode: bool,
):
    from mindloom_cli.text import Text

    t = Text(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(
        t.translate,
        content,
        target_language=target_language,
        source_language=source_language,
        model=model,
        async_mode=async_mode,
    )
    handle_async_result(result)


@text.command("proofread")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def text_proofread(text: str | None, input_file: Path | None, model: str | None, async_mode: bool):
    from mindloom_cli.text import Text

    t = Text(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(t.proofread, content, model=model, async_mode=async_mode)
    handle_async_result(result)


@cli.group()
def code():
    pass


@code.command("explain")
@with_content_input
@click.option("--language", default=None, help="Optional programming language hint.")
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def code_explain(
    text: str | None,
    input_file: Path | None,
    language: str | None,
    model: str | None,
    async_mode: bool,
):
    from mindloom_cli.code import Code

    c = Code(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(
        c.explain_code, content, language=language, model=model, async_mode=async_mode
    )
    handle_async_result(result)


@code.command("tests")
@with_content_input
@click.option("--language", default=None, help="Optional programming language hint.")
@click.option("--framework", default=None, help="Optional test framework hint.")
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def code_tests(
    text: str | None,
    input_file: Path | None,
    language: str | None,
    framework: str | None,
    model: str | None,
    async_mode: bool,
):
    from mindloom_cli.code import Code

    c = Code(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(
        c.generate_tests, content, language=language, framework=framework, model=model, async_mode=async_mode
    )
    handle_async_result(result)


@cli.group()
def git():
    pass


@git.command("commit-message")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def git_commit_message(text: str | None, input_file: Path | None, model: str | None, async_mode: bool):
    from mindloom_cli.git import Git

    g = Git(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(g.generate_commit_message, content, model=model, async_mode=async_mode)
    handle_async_result(result)


@cli.group()
def extract():
    pass


@extract.command("actions")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def extract_actions(text: str | None, input_file: Path | None, model: str | None, async_mode: bool):
    from mindloom_cli.extract import Extract

    e = Extract(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(e.extract_actions, content, model=model, async_mode=async_mode)
    handle_async_result(result)


@cli.group()
def rewrite():
    pass


@rewrite.command("tone")
@with_content_input
@click.option("--target-tone", required=True, help="Target tone to rewrite into.")
@click.option("--model", default=None, help="Optional model override.")
@click.option("--async", "async_mode", is_flag=True, help="Run task asynchronously and return job ID.")
def rewrite_tone(
    text: str | None,
    input_file: Path | None,
    target_tone: str,
    model: str | None,
    async_mode: bool,
):
    from mindloom_cli.rewrite import Rewrite

    r = Rewrite(cfg)
    content = resolve_content_input(text, input_file)
    result = with_response_spinner(
        r.rewrite_tone, content, target_tone=target_tone, model=model, async_mode=async_mode
    )
    handle_async_result(result)


def main():
    cli()


if __name__ == "__main__":
    main()
