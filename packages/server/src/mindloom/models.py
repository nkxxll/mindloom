from __future__ import annotations

from pydantic import BaseModel

from mindloom_core.models import (  # noqa: F401 — re-exported for backwards compat
    CommitMessageRequest,
    ConversationTaskType,
    EmailRequest,
    EthemeralTaskType,
    ExplainCodeRequest,
    ExtractActionsRequest,
    FileRequest,
    GenerateTestsRequest,
    Job,
    JobCreate,
    JobResponse,
    Model,
    ProofreadRequest,
    RewriteToneRequest,
    SectionRequest,
    SectionResponse,
    Status,
    SummarizeRequest,
    TranslateRequest,
)


class Prompts(BaseModel):
    # For TaskType.FILE: Fixing an entire code or text file
    fix_file: str = (
        "Review the following file for syntax errors, logical inconsistencies, "
        "and PEP8 compliance. Return the corrected file in full."
    )

    # For TaskType.SECTION: Fixing a specific snippet or paragraph
    fix_section: str = (
        "Analyze the provided text section. Correct any grammatical errors "
        "or clarity issues while maintaining the original tone."
    )

    # For TaskType.SECTION_EXTEND: Adding depth/length to a section
    extend_section: str = (
        "Elaborate on the following section by adding relevant details and "
        "examples. Ensure the flow remains natural and matches the existing style."
    )

    # For TaskType.IMPROVE_EMAIL: Refining an existing draft
    fix_email: str = (
        "Refine this email draft to be more professional and concise. "
        "Ensure the call to action is clear and the tone is polite."
    )

    # For TaskType.WRITE_EMAIL: Generating from scratch (New field)
    write_email: str = (
        "Draft a new email based on the following key points. "
        "Use a professional subject line and a structured body."
    )

    summarize: str = "Summarize the following text concisely, preserving all key points."
    translate: str = "Translate the following text accurately, preserving tone and meaning."
    explain_code: str = (
        "Explain the following code in plain English. Describe what it does, "
        "why, and any notable patterns or pitfalls."
    )
    commit_message: str = (
        "Generate a concise conventional-commit message for the following diff. "
        "Use the format: type(scope): description."
    )
    extract_actions: str = (
        "Extract all action items and key points from the following text "
        "as a structured bullet-point list."
    )
    rewrite_tone: str = (
        "Rewrite the following text in the requested tone while preserving "
        "all original meaning and information."
    )
    proofread: str = (
        "Proofread the following text. For each issue found, quote the original "
        "phrase, suggest the correction, and briefly explain why."
    )
    generate_tests: str = (
        "Generate unit test stubs for the following code. Cover happy paths, "
        "edge cases, and error conditions."
    )


def get_user_message(task_type: EthemeralTaskType, content: str) -> str:
    p = Prompts()
    prefixes = {
        EthemeralTaskType.FILE: p.fix_file,
        EthemeralTaskType.SECTION: p.fix_section,
        EthemeralTaskType.SECTION_EXTEND: p.extend_section,
        EthemeralTaskType.IMPROVE_EMAIL: p.fix_email,
        EthemeralTaskType.WRITE_EMAIL: p.write_email,
        EthemeralTaskType.SUMMARIZE: p.summarize,
        EthemeralTaskType.TRANSLATE: p.translate,
        EthemeralTaskType.EXPLAIN_CODE: p.explain_code,
        EthemeralTaskType.COMMIT_MESSAGE: p.commit_message,
        EthemeralTaskType.EXTRACT_ACTIONS: p.extract_actions,
        EthemeralTaskType.REWRITE_TONE: p.rewrite_tone,
        EthemeralTaskType.PROOFREAD: p.proofread,
        EthemeralTaskType.GENERATE_TESTS: p.generate_tests,
    }
    prefix = prefixes.get(task_type, "")
    return f"{prefix}\n\n{content}" if prefix else content


def get_system_message(task_type: EthemeralTaskType | ConversationTaskType) -> str:
    base = "You are a highly efficient AI assistant. "

    directives = {
        EthemeralTaskType.FILE: (
            "Act as a Senior Developer. Your goal is technical perfection. "
            "Correct syntax, improve logic, and return only the code/content "
            "without conversational filler."
        ),
        EthemeralTaskType.SECTION: (
            "Act as a meticulous Copy Editor. Change only what is necessary "
            "to fix errors or improve clarity. Do not rewrite the entire context."
        ),
        EthemeralTaskType.SECTION_EXTEND: (
            "Act as a Creative Partner. Expand the provided text while "
            "strictly mimicking the user's existing tone, vocabulary, and rhythm."
        ),
        EthemeralTaskType.IMPROVE_EMAIL: (
            "Act as a Corporate Communications Expert. Focus on making the "
            "email more professional, persuasive, and concise."
        ),
        EthemeralTaskType.WRITE_EMAIL: (
            "Act as a Ghostwriter. Draft a clear, polite, and effective email "
            "based on the provided points. Ensure a strong subject line."
        ),
        EthemeralTaskType.SUMMARIZE: (
            "Act as a Research Assistant. Produce clear, faithful summaries. "
            "Never invent information not present in the source."
        ),
        EthemeralTaskType.TRANSLATE: (
            "Act as a Professional Translator. Preserve meaning, tone, and "
            "formatting. Flag any ambiguous phrases."
        ),
        EthemeralTaskType.EXPLAIN_CODE: (
            "Act as a Patient Senior Developer. Explain code clearly for "
            "someone unfamiliar with the codebase."
        ),
        EthemeralTaskType.COMMIT_MESSAGE: (
            "Act as a meticulous open-source maintainer. Write commit messages "
            "that are concise, descriptive, and follow conventional-commits."
        ),
        EthemeralTaskType.EXTRACT_ACTIONS: (
            "Act as a Project Manager. Identify every actionable item and "
            "decision. Use clear, imperative bullet points."
        ),
        EthemeralTaskType.REWRITE_TONE: (
            "Act as a Versatile Copywriter. Match the requested tone exactly "
            "while keeping all facts intact."
        ),
        EthemeralTaskType.PROOFREAD: (
            "Act as a Strict Proofreader. List issues with quoted originals "
            "and corrections. Do NOT rewrite the whole text."
        ),
        EthemeralTaskType.GENERATE_TESTS: (
            "Act as a QA Engineer. Write idiomatic test code using the "
            "specified framework. Include descriptive test names."
        ),
    }

    return base + directives.get(task_type, "Provide accurate and helpful assistance.")
