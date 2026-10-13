"""loguru 日志配置，并接管标准 logging。"""

from __future__ import annotations

import logging
import sys

from loguru import logger


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(debug: bool = False) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if debug else "INFO",
        backtrace=debug,
        diagnose=False,
    )
    # 文件日志：data/logs/app.log，50MB 轮转，保留 5 份
    from liberastra.core.config import get_settings

    log_dir = get_settings().data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app.log",
        level="DEBUG" if debug else "INFO",
        rotation="50 MB",
        retention=5,
        encoding="utf-8",
        enqueue=True,
    )
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
