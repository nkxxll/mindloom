import sys
from pathlib import Path

import click

from mindloom_cli.config import get_config, initialize_config
from mindloom_cli.display import render_jobs_table
from mindloom_cli.fileio import read_file, write_file

cfg = get_config()


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


@cli.command()
@click.argument("question")
@click.option(
    "--md",
    "markdown",
    is_flag=True,
    help="Format the answer as a Markdown article for note-taking.",
)
@click.option("--model", default=None, help="Optional model override.")
def ask(question: str, markdown: bool, model: str | None):
    from mindloom_cli.ask import Ask

    a = Ask(cfg)
    result = a.ask(question, markdown=markdown, model=model)
    click.echo(result)


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
def section_improve(file_path: Path, line_range: str | None, model: str | None):
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
def section_extend(file_path: Path, line_range: str | None, model: str | None):
    from mindloom_cli.section import Section, parse_line_range

    s = Section(cfg)
    content = read_file(file_path)
    lines = content.splitlines(keepends=True)
    if not lines:
        raise click.ClickException(f"{file_path} is empty; nothing to extend.")

    if line_range is None:
        start, end = 1, len(lines)
    else:
        try:
            start, end = parse_line_range(line_range, len(lines))
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

    selected_content = "".join(lines[start - 1 : end])
    extended = s.extend_section(selected_content, file_path, start, end, model)
    updated_content = "".join(lines[: start - 1]) + extended + "".join(lines[end:])
    write_file(file_path, updated_content)
    click.secho(f"Extended lines {start}:{end} in {file_path}", fg="green")


@cli.group()
def email():
    pass


@email.command("improve")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
def email_improve(text: str | None, input_file: Path | None, model: str | None):
    from mindloom_cli.email import Email

    e = Email(cfg)
    content = resolve_content_input(text, input_file)
    result = e.improve_email(content, model)
    click.echo(result)


@email.command("write")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
def email_write(text: str | None, input_file: Path | None, model: str | None):
    from mindloom_cli.email import Email

    e = Email(cfg)
    content = resolve_content_input(text, input_file)
    result = e.write_email(content, model)
    click.echo(result)


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
def text_summarize(
    text: str | None,
    input_file: Path | None,
    max_length: int | None,
    model: str | None,
):
    from mindloom_cli.text import Text

    t = Text(cfg)
    content = resolve_content_input(text, input_file)
    result = t.summarize(content, max_length=max_length, model=model)
    click.echo(result)


@text.command("translate")
@with_content_input
@click.option("--target-language", required=True, help="Target language for translation.")
@click.option("--source-language", default=None, help="Optional source language.")
@click.option("--model", default=None, help="Optional model override.")
def text_translate(
    text: str | None,
    input_file: Path | None,
    target_language: str,
    source_language: str | None,
    model: str | None,
):
    from mindloom_cli.text import Text

    t = Text(cfg)
    content = resolve_content_input(text, input_file)
    result = t.translate(
        content,
        target_language=target_language,
        source_language=source_language,
        model=model,
    )
    click.echo(result)


@text.command("proofread")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
def text_proofread(text: str | None, input_file: Path | None, model: str | None):
    from mindloom_cli.text import Text

    t = Text(cfg)
    content = resolve_content_input(text, input_file)
    result = t.proofread(content, model=model)
    click.echo(result)


@cli.group()
def code():
    pass


@code.command("explain")
@with_content_input
@click.option("--language", default=None, help="Optional programming language hint.")
@click.option("--model", default=None, help="Optional model override.")
def code_explain(
    text: str | None,
    input_file: Path | None,
    language: str | None,
    model: str | None,
):
    from mindloom_cli.code import Code

    c = Code(cfg)
    content = resolve_content_input(text, input_file)
    result = c.explain_code(content, language=language, model=model)
    click.echo(result)


@code.command("tests")
@with_content_input
@click.option("--language", default=None, help="Optional programming language hint.")
@click.option("--framework", default=None, help="Optional test framework hint.")
@click.option("--model", default=None, help="Optional model override.")
def code_tests(
    text: str | None,
    input_file: Path | None,
    language: str | None,
    framework: str | None,
    model: str | None,
):
    from mindloom_cli.code import Code

    c = Code(cfg)
    content = resolve_content_input(text, input_file)
    result = c.generate_tests(content, language=language, framework=framework, model=model)
    click.echo(result)


@cli.group()
def git():
    pass


@git.command("commit-message")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
def git_commit_message(text: str | None, input_file: Path | None, model: str | None):
    from mindloom_cli.git import Git

    g = Git(cfg)
    content = resolve_content_input(text, input_file)
    result = g.generate_commit_message(content, model=model)
    click.echo(result)


@cli.group()
def extract():
    pass


@extract.command("actions")
@with_content_input
@click.option("--model", default=None, help="Optional model override.")
def extract_actions(text: str | None, input_file: Path | None, model: str | None):
    from mindloom_cli.extract import Extract

    e = Extract(cfg)
    content = resolve_content_input(text, input_file)
    result = e.extract_actions(content, model=model)
    click.echo(result)


@cli.group()
def rewrite():
    pass


@rewrite.command("tone")
@with_content_input
@click.option("--target-tone", required=True, help="Target tone to rewrite into.")
@click.option("--model", default=None, help="Optional model override.")
def rewrite_tone(
    text: str | None,
    input_file: Path | None,
    target_tone: str,
    model: str | None,
):
    from mindloom_cli.rewrite import Rewrite

    r = Rewrite(cfg)
    content = resolve_content_input(text, input_file)
    result = r.rewrite_tone(content, target_tone=target_tone, model=model)
    click.echo(result)


def main():
    cli()


if __name__ == "__main__":
    main()
