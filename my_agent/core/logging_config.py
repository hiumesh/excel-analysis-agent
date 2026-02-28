import logging
import os

import structlog

LOG_LEVEL = "INFO"


def setup_logging():
    # Standard logging setup
    logging.basicConfig(
        format="%(message)s",
        stream=os.sys.stdout,
        level=LOG_LEVEL,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,  # Add log level
            structlog.processors.TimeStamper(fmt="iso"),  # ISO timestamp
            structlog.processors.JSONRenderer(),  # Render logs as JSON
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()
