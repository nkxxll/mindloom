import httpx
from mindloom_core.models import SectionResponse, TaskResponse


class EmailRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class ImproveEmailError(EmailRequestError):
    def __init__(
        self, status_code: int, message: str = "Failed to improve email: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


class WriteEmailError(EmailRequestError):
    def __init__(
        self, status_code: int, message: str = "Failed to write email: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


class Email:
    def __init__(self, config):
        self.config = config

    def _request_text_response(
        self,
        endpoint: str,
        payload: dict[str, object],
        *,
        error_type: type[EmailRequestError],
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

    def improve_email(self, content: str, model: str | None = None, async_mode: bool = False) -> str | int:
        payload: dict[str, object] = {"content": content, "async_mode": async_mode}
        if model is not None:
            payload["model"] = model
        result = self._request_text_response(
            "/email/improve", payload, error_type=ImproveEmailError
        )
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content

    def write_email(self, content: str, model: str | None = None, async_mode: bool = False) -> str | int:
        payload: dict[str, object] = {"content": content, "async_mode": async_mode}
        if model is not None:
            payload["model"] = model
        result = self._request_text_response("/email/write", payload, error_type=WriteEmailError)
        if isinstance(result, TaskResponse):
            return result.job_id
        return result.content
