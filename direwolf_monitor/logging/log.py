import logging
import sys

from loguru import logger
from oslo_config import cfg

from aprsd.conf import log as conf_log


CONF = cfg.CONF
LOG = logger


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Setup the log faciility
# to disable log to stdout, but still log to file
# use the --quiet option on the cmdln
def setup_logging(loglevel=None, quiet=False):
    if not loglevel:
        log_level = CONF.logging.log_level
    else:
        log_level = conf_log.LOG_LEVELS[loglevel]

    # intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(log_level)

    disable_list = [
        "aprslib",
        "aprslib.parsing",
        "aprslib.exceptions",
    ]

    # remove every other logger's handlers
    # and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        if name in disable_list:
            logging.getLogger(name).propagate = False
        else:
            logging.getLogger(name).propagate = True

    handlers = [
        {
            "sink": sys.stdout,
            "serialize": False,
            "format": CONF.logging.logformat,
            "colorize": True,
            "level": log_level,
        },
    ]
    if CONF.logging.logfile:
        handlers.append(
            {
                "sink": CONF.logging.logfile,
                "serialize": False,
                "format": CONF.logging.logformat,
                "colorize": False,
                "level": log_level,
            },
        )

    # configure loguru
    logger.configure(handlers=handlers)
    logger.level("DEBUG", color="<fg #BABABA>")
