from __future__ import annotations

import sys

from loguru import logger


def configure_logging() -> None:
    logger.remove()
    logger.configure(extra={"request_id": "-", "path": "-", "method": "-"})
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
            "request_id={extra[request_id]} | {extra[method]} {extra[path]} | "
            "{name}:{function}:{line} - {message}"
        ),
    )
