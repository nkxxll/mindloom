from logging import getLogger

import ollama

from .defaults import DEFAULT_MODEL
from .models import Model

logger = getLogger(__name__)


def chat_ollama(
    user_input: str,
    system_message: str,
    model: Model = DEFAULT_MODEL,
) -> ollama.Message:
    logger.info(
        f"Calling ollama with model: {model} and input: {user_input} and system_message: {system_message}"
    )
    response = ollama.chat(
        model=str(model),
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input},
        ],
        think="medium",
    )
    return response.message
