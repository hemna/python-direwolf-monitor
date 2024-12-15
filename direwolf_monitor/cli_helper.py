from functools import update_wrapper
import typing as t
import os

import click
from oslo_config import cfg
from rich.console import Console

import direwolf_monitor
from direwolf_monitor.logging import log
from direwolf_monitor.utils import trace


CONF = cfg.CONF

F = t.TypeVar("F", bound=t.Callable[..., t.Any])

common_options = [
    click.option(
        "--loglevel",
        default="DEBUG",
        show_default=True,
        type=click.Choice(
            ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
            case_sensitive=False,
        ),
        show_choices=True,
        help="The log level to use for logging",
    ),
    click.option(
        "--quiet",
        is_flag=True,
        default=False,
        help="Don't log to stdout",
    ),
    click.option(
        "--config-file",
        default=None,
        help="Config file for direwolf_monitor"
    )
]


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


def process_standard_options(f: F) -> F:
    def new_func(*args, **kwargs):
        ctx = args[0]
        ctx.ensure_object(dict)
        if kwargs['config_file']:
            default_config_files = [kwargs['config_file']]
        else:
            default_config_files = None
            
        # To prevent an error with aprsd's conf
        os.environ["OS_DEFAULT__CALLSIGN"] = "NOCALL"
        CONF([], project='direwolf_monitor', version=direwolf_monitor.__version__,
             default_config_files=default_config_files)

        ctx.obj["loglevel"] = kwargs["loglevel"]
        ctx.obj["quiet"] = kwargs["quiet"]
        log.setup_logging(
            ctx.obj["loglevel"],
            ctx.obj["quiet"],
        )
        if CONF.get("trace_enable"):
            trace.setup_tracing(["method", "api"])

        ctx.obj['console'] = Console()

        del kwargs["loglevel"]
        del kwargs["config_file"]
        del kwargs["quiet"]
        return f(*args, **kwargs)

    return update_wrapper(t.cast(F, new_func), f)


def process_standard_options_no_config(f: F) -> F:
    """Use this as a decorator when config isn't needed."""
    def new_func(*args, **kwargs):
        ctx = args[0]
        ctx.ensure_object(dict)
        ctx.obj["loglevel"] = kwargs["loglevel"]
        ctx.obj["config_file"] = kwargs["config_file"]
        ctx.obj["quiet"] = kwargs["quiet"]
        log.setup_logging_no_config(
            ctx.obj["loglevel"],
            ctx.obj["quiet"],
        )

        del kwargs["loglevel"]
        del kwargs["config_file"]
        del kwargs["quiet"]
        return f(*args, **kwargs)

    return update_wrapper(t.cast(F, new_func), f)
