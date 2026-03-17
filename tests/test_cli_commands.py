from pathlib import Path

from click.testing import CliRunner

from mindloom_cli.__main__ import cli


def test_cli_help_lists_new_groups():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    for command_name in ["email", "text", "code", "git", "extract", "rewrite", "section"]:
        assert command_name in result.output


def test_section_legacy_command_still_improves_file(monkeypatch):
    import mindloom_cli.section as section_module

    calls: dict[str, object] = {}

    class FakeSection:
        def __init__(self, _config):
            pass

        def improve_file(self, content: str, file_path: Path, model: str | None = None) -> str:
            calls["content"] = content
            calls["file_path"] = file_path
            calls["model"] = model
            return "updated file\n"

    monkeypatch.setattr(section_module, "Section", FakeSection)

    runner = CliRunner()
    with runner.isolated_filesystem():
        file_path = Path("legacy.txt")
        file_path.write_text("original\n", encoding="utf-8")

        result = runner.invoke(cli, ["section", "legacy.txt", "--model", "qwen3:latest"])

        assert result.exit_code == 0
        assert file_path.read_text(encoding="utf-8") == "updated file\n"
        assert calls == {
            "content": "original\n",
            "file_path": file_path,
            "model": "qwen3:latest",
        }


def test_section_extend_updates_only_selected_range(monkeypatch):
    import mindloom_cli.section as section_module

    calls: dict[str, object] = {}

    class FakeSection:
        def __init__(self, _config):
            pass

        def extend_section(
            self,
            content: str,
            file_path: Path,
            start: int,
            end: int,
            model: str | None = None,
        ) -> str:
            calls["content"] = content
            calls["file_path"] = file_path
            calls["start"] = start
            calls["end"] = end
            calls["model"] = model
            return "expanded\n"

    monkeypatch.setattr(section_module, "Section", FakeSection)

    runner = CliRunner()
    with runner.isolated_filesystem():
        file_path = Path("section.txt")
        file_path.write_text("line1\nline2\nline3\n", encoding="utf-8")

        result = runner.invoke(
            cli,
            ["section", "extend", "section.txt", "--range", "2:2", "--model", "ministral-3:latest"],
        )

        assert result.exit_code == 0
        assert file_path.read_text(encoding="utf-8") == "line1\nexpanded\nline3\n"
        assert calls == {
            "content": "line2\n",
            "file_path": file_path,
            "start": 2,
            "end": 2,
            "model": "ministral-3:latest",
        }


def test_email_improve_uses_inline_text(monkeypatch):
    import mindloom_cli.email as email_module

    calls: dict[str, object] = {}

    class FakeEmail:
        def __init__(self, _config):
            pass

        def improve_email(self, content: str, model: str | None = None) -> str:
            calls["content"] = content
            calls["model"] = model
            return "improved email"

    monkeypatch.setattr(email_module, "Email", FakeEmail)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["email", "improve", "--text", "hello team", "--model", "qwen3:14b"],
    )

    assert result.exit_code == 0
    assert result.output.strip() == "improved email"
    assert calls == {"content": "hello team", "model": "qwen3:14b"}


def test_text_translate_reads_from_file(monkeypatch):
    import mindloom_cli.text as text_module

    calls: dict[str, object] = {}

    class FakeText:
        def __init__(self, _config):
            pass

        def translate(
            self,
            content: str,
            target_language: str,
            source_language: str | None = None,
            model: str | None = None,
        ) -> str:
            calls["content"] = content
            calls["target_language"] = target_language
            calls["source_language"] = source_language
            calls["model"] = model
            return "translated text"

    monkeypatch.setattr(text_module, "Text", FakeText)

    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("translate.txt")
        input_path.write_text("Bitte senden", encoding="utf-8")

        result = runner.invoke(
            cli,
            [
                "text",
                "translate",
                "--file",
                "translate.txt",
                "--target-language",
                "English",
                "--source-language",
                "German",
                "--model",
                "gemma3:latest",
            ],
        )

        assert result.exit_code == 0
        assert result.output.strip() == "translated text"
        assert calls == {
            "content": "Bitte senden",
            "target_language": "English",
            "source_language": "German",
            "model": "gemma3:latest",
        }


def test_git_commit_message_reads_stdin(monkeypatch):
    import mindloom_cli.git as git_module

    calls: dict[str, object] = {}

    class FakeGit:
        def __init__(self, _config):
            pass

        def generate_commit_message(self, content: str, model: str | None = None) -> str:
            calls["content"] = content
            calls["model"] = model
            return "feat: add new cli commands"

    monkeypatch.setattr(git_module, "Git", FakeGit)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["git", "commit-message", "--model", "llama3.2:latest"],
        input="diff --git a/file.py b/file.py\n+print('hi')\n",
    )

    assert result.exit_code == 0
    assert result.output.strip() == "feat: add new cli commands"
    assert calls == {
        "content": "diff --git a/file.py b/file.py\n+print('hi')\n",
        "model": "llama3.2:latest",
    }


def test_code_tests_forwards_language_and_framework(monkeypatch):
    import mindloom_cli.code as code_module

    calls: dict[str, object] = {}

    class FakeCode:
        def __init__(self, _config):
            pass

        def generate_tests(
            self,
            content: str,
            language: str | None = None,
            framework: str | None = None,
            model: str | None = None,
        ) -> str:
            calls["content"] = content
            calls["language"] = language
            calls["framework"] = framework
            calls["model"] = model
            return "generated tests"

    monkeypatch.setattr(code_module, "Code", FakeCode)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "code",
            "tests",
            "--text",
            "def divide(a, b): return a / b",
            "--language",
            "Python",
            "--framework",
            "pytest",
            "--model",
            "ministral-3:latest",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == "generated tests"
    assert calls == {
        "content": "def divide(a, b): return a / b",
        "language": "Python",
        "framework": "pytest",
        "model": "ministral-3:latest",
    }


def test_extract_actions_and_rewrite_tone(monkeypatch):
    import mindloom_cli.extract as extract_module
    import mindloom_cli.rewrite as rewrite_module

    extract_calls: dict[str, object] = {}
    rewrite_calls: dict[str, object] = {}

    class FakeExtract:
        def __init__(self, _config):
            pass

        def extract_actions(self, content: str, model: str | None = None) -> str:
            extract_calls["content"] = content
            extract_calls["model"] = model
            return "1. Do thing"

    class FakeRewrite:
        def __init__(self, _config):
            pass

        def rewrite_tone(
            self, content: str, target_tone: str, model: str | None = None
        ) -> str:
            rewrite_calls["content"] = content
            rewrite_calls["target_tone"] = target_tone
            rewrite_calls["model"] = model
            return "Could you please share the update?"

    monkeypatch.setattr(extract_module, "Extract", FakeExtract)
    monkeypatch.setattr(rewrite_module, "Rewrite", FakeRewrite)

    runner = CliRunner()

    extract_result = runner.invoke(
        cli,
        ["extract", "actions", "--text", "Finalize roadmap and send notes", "--model", "qwen3:latest"],
    )
    assert extract_result.exit_code == 0
    assert extract_result.output.strip() == "1. Do thing"
    assert extract_calls == {
        "content": "Finalize roadmap and send notes",
        "model": "qwen3:latest",
    }

    rewrite_result = runner.invoke(
        cli,
        [
            "rewrite",
            "tone",
            "--text",
            "send update asap",
            "--target-tone",
            "formal",
            "--model",
            "gemma3:latest",
        ],
    )
    assert rewrite_result.exit_code == 0
    assert rewrite_result.output.strip() == "Could you please share the update?"
    assert rewrite_calls == {
        "content": "send update asap",
        "target_tone": "formal",
        "model": "gemma3:latest",
    }
