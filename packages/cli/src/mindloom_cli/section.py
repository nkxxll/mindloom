from pathlib import Path

import httpx
from mindloom_core.models import SectionResponse, TaskResponse


class SectionRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class ImproveFileError(SectionRequestError):
    def __init__(
        self, status_code: int, message: str = "Failed to improve file: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


class ImproveSectionError(SectionRequestError):
    def __init__(
        self, status_code: int, message: str = "Failed to improve section: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


class ExtendSectionError(SectionRequestError):
    def __init__(
        self, status_code: int, message: str = "Failed to extend section: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


def parse_line_range(line_range: str, total_lines: int) -> tuple[int, int]:
    parts = line_range.split(":", maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Range must be in START:END format.")
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError("Range values must be integers.") from exc

    if start < 1 or end < 1:
        raise ValueError("Range values must be >= 1.")
    if start > end:
        raise ValueError("Range start must be <= end.")
    if end > total_lines:
        raise ValueError(
            f"Range end ({end}) is out of bounds for file with {total_lines} lines."
        )
    return start, end


class Section:
    def __init__(self, config):
        self.config = config

    def _request_section_response(
        self,
        endpoint: str,
        payload: dict[str, object],
        *,
        error_type: type[SectionRequestError],
    ) -> SectionResponse | TaskResponse:
        response = httpx.post(f"{self.config.host.rstrip('/')}{endpoint}", json=payload, timeout=None)
        if response.status_code == 200:
            data = response.json()
            if "job_id" in data:
                return TaskResponse.model_validate(data)
            return SectionResponse.model_validate(data)
        body = response.text.strip() or "<empty response body>"
        raise error_type(
            status_code=response.status_code,
            message=f"Request to {endpoint} failed ({response.status_code}): {body}",
        )

    def improve_file(self, content: str, file_path: Path, model: str | None = None, async_mode: bool = False) -> str | int:
        payload: dict[str, object] = {"content": content, "file_path": str(file_path), "async_mode": async_mode}
        if model is not None:
            payload["model"] = model
        result = self._request_section_response(
            "/file/improve", payload, error_type=ImproveFileError
        )
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content

    def improve_section(
        self,
        content: str,
        file_path: Path,
        start: int,
        end: int,
        model: str | None = None,
        async_mode: bool = False,
    ) -> str | int:
        payload: dict[str, object] = {
            "start": start,
            "end": end,
            "content": content,
            "file_path": str(file_path),
            "async_mode": async_mode,
        }
        if model is not None:
            payload["model"] = model
        result = self._request_section_response(
            "/section/improve", payload, error_type=ImproveSectionError
        )
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content

    def extend_section(
        self,
        content: str,
        file_path: Path,
        start: int,
        end: int,
        model: str | None = None,
        async_mode: bool = False,
    ) -> str | int:
        payload: dict[str, object] = {
            "start": start,
            "end": end,
            "content": content,
            "file_path": str(file_path),
            "async_mode": async_mode,
        }
        if model is not None:
            payload["model"] = model
        result = self._request_section_response(
            "/section/extend", payload, error_type=ExtendSectionError
        )
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content
