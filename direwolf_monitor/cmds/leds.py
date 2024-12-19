import logging
import time

import click
from oslo_config import cfg
try:
    import RPi.GPIO as GPIO
except Exception:
    print("fuct")
    pass

from direwolf_monitor.cli import cli
from direwolf_monitor import cli_helper


LOG = logging.getLogger("dwm")
CONF = cfg.CONF

@cli.command()
@cli_helper.add_options(cli_helper.common_options)
@click.pass_context
@cli_helper.process_standard_options
def monitor_leds(ctx):
    console = ctx.obj['console']
    CONF.log_opt_values(LOG, logging.DEBUG)

    GPIO.setmode(GPIO.BCM)  # logical pin numbers, not BOARD
    GPIO.setwarnings(False)
    # RED_LED = GPIO.setup(26, GPIO.IN)

    console.print("monitor LEDS Exit.")
    count = 1
    msg = "Checking status of TX LED "
    with console.status(msg) as status:
        while count < 1000:
            led_state = GPIO.input(26)
            status.update(f"{msg} : State {led_state} count {count}")
            count += 1
            time.sleep(.1)


@cli.command()
@cli_helper.add_options(cli_helper.common_options)
@click.pass_context
@cli_helper.process_standard_options
def piss(ctx):
    console = ctx.obj['console']
    console.print("PISS")
    count = 1
    import time
    msg = "Checking status of TX LED "
    with console.status(msg) as status:
        while count <= 10:
            status.update(f"{msg} :  PISS {count}")
            time.sleep(1)
            count += 1


