import logging
from logging import NullHandler
from logging.handlers import RotatingFileHandler
import queue
import sys

from oslo_config import cfg

from direwolf_monitor.logging import rich as my_logging


CONF = cfg.CONF
LOG = logging.getLogger("dwm")
logging_queue = queue.Queue()


LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

DEFAULT_DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"
DEFAULT_LOG_FORMAT = (
    "[%(asctime)s] [%(threadName)-20.20s] [%(levelname)-5.5s]"
    " %(message)s - [%(pathname)s:%(lineno)d]"
)

QUEUE_DATE_FORMAT = "[%m/%d/%Y] [%I:%M:%S %p]"
QUEUE_LOG_FORMAT = (
    "%(asctime)s [%(threadName)-20.20s] [%(levelname)-5.5s]"
    " %(message)s - [%(pathname)s:%(lineno)d]"
)

logging_group = cfg.OptGroup(name='logging',
                             title='Logging options')
logging_opts = [
    cfg.StrOpt('date_format',
               default=DEFAULT_DATE_FORMAT,
               help="Date format for log entries"),
    cfg.BoolOpt("rich_logging",
                default=True,
                help="Enable Rich logging"),
    cfg.StrOpt('logfile',
               default=None,
               help="File to log to"),
    cfg.StrOpt('logformat',
               default=DEFAULT_LOG_FORMAT,
               help="Log file format, unless rich_logging enabled.")
]

CONF.register_group(logging_group)
CONF.register_opts(logging_opts, group=logging_group)



# Setup the logging faciility
# to disable logging to stdout, but still log to file
# use the --quiet option on the cmdline
def setup_logging(loglevel, quiet):
    log_level = LOG_LEVELS[loglevel]
    LOG.setLevel(log_level)
    date_format = CONF["logging"].get("date_format")

    rich_logging = False
    if CONF["logging"].get("rich_logging") and not quiet:
        log_format = "%(message)s"
        log_formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
        rh = my_logging.RichHandler(
            show_thread=True, thread_width=20,
            rich_tracebacks=True, omit_repeated_times=False,
        )
        rh.setFormatter(log_formatter)
        LOG.addHandler(rh)
        rich_logging = True

    log_file = CONF["logging"].get("logfile")
    log_format = CONF["logging"].get("logformat")
    log_formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    if log_file:
        fh = RotatingFileHandler(log_file, maxBytes=(10248576 * 5), backupCount=4)
        fh.setFormatter(log_formatter)
        LOG.addHandler(fh)


def setup_logging_no_config(loglevel, quiet):
    log_level = LOG_LEVELS[loglevel]
    LOG.setLevel(log_level)
    log_format = DEFAULT_LOG_FORMAT
    date_format = DEFAULT_DATE_FORMAT
    log_formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    fh = NullHandler()

    fh.setFormatter(log_formatter)
    LOG.addHandler(fh)

    if not quiet:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(log_formatter)
        LOG.addHandler(sh)
