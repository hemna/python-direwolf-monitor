import logging
from pathlib import Path
import sys
import uuid

import click
from oslo_config import cfg

import direwolf_monitor
from direwolf_monitor.cli import cli
from direwolf_monitor import cli_helper


LOG = logging.getLogger("dwm")
CONF = cfg.CONF


import time
from typing import Iterator

FILE = "/home/pi/direwolf.log"


def follow(file, sleep_sec=0.1) -> Iterator[str]:
    """ Yield each line from a file as they are written.
    `sleep_sec` is the time to sleep after empty reads. """
    line = ''
    while True:
        tmp = file.readline()
        if tmp is not None and tmp != "":
            line += tmp
            if line.endswith("\n"):
                yield line
                line = ''
        elif sleep_sec:
            time.sleep(sleep_sec)


@cli.command()
@cli_helper.add_options(cli_helper.common_options)
@click.option(
    "--mqtt-host",
    envvar="DWM_MQTT_HOST",
    show_envvar=True,
    help="MQTT Hostname to send entries"
)
@click.option(
    "--mqtt-port",
    envvar="DWM_MQTT_PORT",
    show_envvar=True,
    help="MQTT Port"
)
@click.option(
    "--mqtt-topic",
    envvar="DWM_MQTT_TOPIC",
    default="direwolf",
    show_envvar=True,
    help="The MQTT Topic to send entries to" ,
)
@click.option(
    "--direwolf-log",
    default="./direwolf.log",
    show_default=True,
    help="The direwolf log path and filename"
)
@click.pass_context
@cli_helper.process_standard_options
def mqtt(ctx, mqtt_host, mqtt_port, mqtt_topic, direwolf_log):
    """Tail direwolf.log and put entries in MQTT

    Args:
        ctx (_type_): _description_
    """
    console = ctx.obj['console']
    count = 1
    import time
    msg = f"Checking for direwolf log {direwolf_log}"
    with console.status(msg) as status:
        my_file = Path(direwolf_log)
        if my_file.is_file():
            line_number = 0
            with open(FILE, 'r') as file:
                for line in follow(file):
                    status.update("Reading line {line_number} from {direwolf_log}")
                    line_number += 1
                    console.print(line, end='')
        else:
            console.print(f"[bold red]{direwolf_log} doesn't exist.[/]")