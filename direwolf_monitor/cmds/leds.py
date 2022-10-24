import logging
import sys
import uuid

import click
from oslo_config import cfg
from oslo_context import context
from oslo_log import log

import direwolf_monitor
from direwolf_monitor.cli import cli
from direwolf_monitor import cli_helper


LOG = log.getLogger("dwm")
CONF = cfg.CONF

@cli.command()
@cli_helper.add_options(cli_helper.common_options)
@click.pass_context
@cli_helper.process_standard_options
def monitor_leds(ctx):
    console = ctx.obj['console']
    CONF.log_opt_values(LOG, logging.DEBUG)

    console.print("monitor LEDS Exit.")
