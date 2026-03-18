import httpx
from mindloom_core.models import SectionResponse, TaskResponse


class RewriteRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class RewriteToneError(RewriteRequestError):
    def __init__(
        self, status_code: int, message: str = "Failed to rewrite tone: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


class Rewrite:
    def __init__(self, config):
        self.config = config

    def rewrite_tone(
        self,
        content: str,
        target_tone: str,
        model: str | None = None,
        async_mode: bool = False,
    ) -> str | int:
        payload: dict[str, object] = {"content": content, "target_tone": target_tone, "async_mode": async_mode}
        if model is not None:
            payload["model"] = model
        response = httpx.post(f"{self.config.host.rstrip('/')}/rewrite/tone", json=payload, timeout=None)
        if response.status_code == 200:
            data = response.json()
            if "job_id" in data:
                result = TaskResponse.model_validate(data)
                return result.job_id
            result = SectionResponse.model_validate(data)
            return result.content
        body = response.text.strip() or "<empty response body>"
        raise RewriteToneError(
            status_code=response.status_code,
            message=f"Request to /rewrite/tone failed ({response.status_code}): {body}",
        )
