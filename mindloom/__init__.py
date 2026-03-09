from logging import getLogger

from mindloom.logger_config import setup_logging

from .app import app

setup_logging()

logger = getLogger(__name__)


__all__ = ["app"]
