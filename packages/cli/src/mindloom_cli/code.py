import httpx
from mindloom_core.models import SectionResponse, TaskResponse


class CodeRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class ExplainCodeError(CodeRequestError):
    def __init__(
        self, status_code: int, message: str = "Failed to explain code: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


class GenerateTestsError(CodeRequestError):
    def __init__(
        self,
        status_code: int,
        message: str = "Failed to generate tests: non 200 status code.",
    ):
        super().__init__(status_code=status_code, message=message)


class Code:
    def __init__(self, config):
        self.config = config

    def _request_text_response(
        self,
        endpoint: str,
        payload: dict[str, object],
        *,
        error_type: type[CodeRequestError],
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

    def explain_code(
        self,
        content: str,
        language: str | None = None,
        model: str | None = None,
        async_mode: bool = False,
    ) -> str | int:
        payload: dict[str, object] = {"content": content, "async_mode": async_mode}
        if language is not None:
            payload["language"] = language
        if model is not None:
            payload["model"] = model
        result = self._request_text_response("/code/explain", payload, error_type=ExplainCodeError)
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content

    def generate_tests(
        self,
        content: str,
        language: str | None = None,
        framework: str | None = None,
        model: str | None = None,
        async_mode: bool = False,
    ) -> str | int:
        payload: dict[str, object] = {"content": content, "async_mode": async_mode}
        if language is not None:
            payload["language"] = language
        if framework is not None:
            payload["framework"] = framework
        if model is not None:
            payload["model"] = model
        result = self._request_text_response(
            "/code/generate-tests", payload, error_type=GenerateTestsError
        )
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content
