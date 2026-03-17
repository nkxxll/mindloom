import httpx
from mindloom_core.models import SectionResponse


class ExtractRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class ExtractActionsError(ExtractRequestError):
    def __init__(
        self,
        status_code: int,
        message: str = "Failed to extract actions: non 200 status code.",
    ):
        super().__init__(status_code=status_code, message=message)


class Extract:
    def __init__(self, config):
        self.config = config

    def extract_actions(self, content: str, model: str | None = None) -> str:
        payload: dict[str, object] = {"content": content}
        if model is not None:
            payload["model"] = model
        response = httpx.post(f"{self.config.host.rstrip('/')}/extract/actions", json=payload, timeout=None)
        if response.status_code == 200:
            result = SectionResponse.model_validate(response.json())
            return result.content
        body = response.text.strip() or "<empty response body>"
        raise ExtractActionsError(
            status_code=response.status_code,
            message=f"Request to /extract/actions failed ({response.status_code}): {body}",
        )
