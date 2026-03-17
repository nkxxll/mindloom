import httpx
from mindloom_core.models import SectionResponse


class AskRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class AskError(AskRequestError):
    def __init__(self, status_code: int, message: str = "Failed to answer question: non 200 status code."):
        super().__init__(status_code=status_code, message=message)


class Ask:
    def __init__(self, config):
        self.config = config

    def _request_text_response(
        self,
        endpoint: str,
        payload: dict[str, object],
        *,
        error_type: type[AskRequestError],
    ) -> SectionResponse:
        response = httpx.post(f"{self.config.host.rstrip('/')}{endpoint}", json=payload, timeout=None)
        if response.status_code == 200:
            return SectionResponse.model_validate(response.json())
        body = response.text.strip() or "<empty response body>"
        raise error_type(
            status_code=response.status_code,
            message=f"Request to {endpoint} failed ({response.status_code}): {body}",
        )

    def ask(self, question: str, markdown: bool = False, model: str | None = None) -> str:
        payload: dict[str, object] = {"question": question}
        if markdown:
            payload["markdown"] = True
        if model is not None:
            payload["model"] = model
        result = self._request_text_response("/ask", payload, error_type=AskError)
        return result.content
