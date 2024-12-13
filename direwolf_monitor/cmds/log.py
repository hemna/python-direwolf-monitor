import logging
from pathlib import Path
import sys
import uuid

import click
from oslo_config import cfg
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties


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
            
def _on_publish(client, userdata, mid):
    LOG.info(f"Published {mid}:{userdata}")

def _on_connect(client, userdata, flags, rc):
    LOG.info(
        f"Connected to mqtt://{client}"
    )

def _on_disconnect(client, userdata, rc):
    LOG.warning(
        "MQTT Client disconnected"
    )
            
def _create_mqtt_client(ctx, mqtt_host, mqtt_port, mqtt_username, mqtt_password):
    console = ctx.obj['console']
    
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="aprsd_mqtt_plugin",
        # transport='websockets',
        # protocol=mqtt.MQTTv5
    )
    # self.client.on_publish = self.on_publish
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    
    client.username_pw_set(
       mqtt_username,
       mqtt_password 
    )

    mqtt_properties = Properties(PacketTypes.PUBLISH)
    mqtt_properties.MessageExpiryInterval = 30  # in seconds
    properties = Properties(PacketTypes.CONNECT)
    properties.SessionExpiryInterval = 30 * 60  # in seconds
    LOG.info(f"Connecting to mqtt://{mqtt_host}:{mqtt_port}")
    client.connect(
        mqtt_host,
        port=mqtt_port,
        # clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
        keepalive=60,
        # properties=properties
    )
    return client


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
    "--mqtt-username",
    envvar="DWM_MQTT_USERNAME",
    show_envvar=True,
    help="The mqtt username for login",
)
@click.option(
    "--mqtt-password",
    envvar="DWM_MQTT_PASSWORD",
    show_envvar=True,
    help="The mqtt password for login",
)
@click.option(
    "--direwolf-log",
    default="./direwolf.log",
    show_default=True,
    help="The direwolf log path and filename"
)
@click.pass_context
@cli_helper.process_standard_options
def log_to_mqtt(ctx, mqtt_host, mqtt_port, mqtt_topic, mqtt_username, mqtt_password, direwolf_log):
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
            
            # Create mqtt client connection
            status.update("Creating MQTT connection")
            client = _create_mqtt_client(
                ctx,
                mqtt_host,
                int(mqtt_port),
                mqtt_username,
                mqtt_password
            )
            
            line_number = 0
            with open(FILE, 'r') as file:
                # now move the pointer to the end of the file
                file.seek(0, 2)
                for line in follow(file):
                    status.update(f"Reading line {line_number} from {direwolf_log}")
                    line_number += 1
                    print(line, end='')
                    client.publish(
                        mqtt_topic,
                        payload=line,
                        qos=0
                    )
        else:
            console.print(f"[bold red]{direwolf_log} doesn't exist.[/]")