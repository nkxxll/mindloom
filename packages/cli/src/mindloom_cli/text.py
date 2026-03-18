import httpx
from mindloom_core.models import SectionResponse, TaskResponse


class TextRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class SummarizeError(TextRequestError):
    def __init__(self, status_code: int, message: str = "Failed to summarize: non 200 status code."):
        super().__init__(status_code=status_code, message=message)


class TranslateError(TextRequestError):
    def __init__(self, status_code: int, message: str = "Failed to translate: non 200 status code."):
        super().__init__(status_code=status_code, message=message)


class ProofreadError(TextRequestError):
    def __init__(self, status_code: int, message: str = "Failed to proofread: non 200 status code."):
        super().__init__(status_code=status_code, message=message)


class Text:
    def __init__(self, config):
        self.config = config

    def _request_text_response(
        self,
        endpoint: str,
        payload: dict[str, object],
        *,
        error_type: type[TextRequestError],
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

    def summarize(
        self,
        content: str,
        max_length: int | None = None,
        model: str | None = None,
        async_mode: bool = False,
    ) -> str | int:
        payload: dict[str, object] = {"content": content, "async_mode": async_mode}
        if max_length is not None:
            payload["max_length"] = max_length
        if model is not None:
            payload["model"] = model
        result = self._request_text_response("/summarize", payload, error_type=SummarizeError)
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content

    def translate(
        self,
        content: str,
        target_language: str,
        source_language: str | None = None,
        model: str | None = None,
        async_mode: bool = False,
    ) -> str | int:
        payload: dict[str, object] = {
            "content": content,
            "target_language": target_language,
            "async_mode": async_mode,
        }
        if source_language is not None:
            payload["source_language"] = source_language
        if model is not None:
            payload["model"] = model
        result = self._request_text_response("/translate", payload, error_type=TranslateError)
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content

    def proofread(self, content: str, model: str | None = None, async_mode: bool = False) -> str | int:
        payload: dict[str, object] = {"content": content, "async_mode": async_mode}
        if model is not None:
            payload["model"] = model
        result = self._request_text_response("/proofread", payload, error_type=ProofreadError)
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content
