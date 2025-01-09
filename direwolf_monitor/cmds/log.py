import logging
from pathlib import Path
import re
import time
from typing import Iterator

import click
import paho
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from direwolf_monitor.cli import cli
from direwolf_monitor import cli_helper
from direwolf_monitor.utils import packet as packet_utils


LOG = logging.getLogger("dwm")


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
            
def _on_connect(client, userdata, flags, rc, properties):
    print(f"Connected to mqtt://{client}")
    
def _on_connect_fail(client, userdata):
    print("MQTT Client failed to connect.")

def _on_disconnect(client, userdata, flags, rc, properties):
    print("MQTT Client disconnected")
    print(f"_on_disconnect rc:{rc} flags:{flags}")
    
def _on_message(client, userdata, flags, rc, properties):
    print("on_message")
            
def _create_mqtt_client(ctx, mqtt_host, mqtt_port, mqtt_username, mqtt_password,
                        client_id, on_connect=None, on_connect_fail=None,
                        on_disconnect=None, on_message=None):
    console = ctx.obj['console']
    
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        # transport='websockets',
        protocol=paho.mqtt.client.MQTTv5,
        #transport='tcp',
        #protocol=mqtt.MQTTv311
    )
    client.on_connect = on_connect or _on_connect
    client.on_connect_fail = on_connect_fail or _on_connect_fail
    client.on_disconnect = on_disconnect or _on_disconnect
    client.on_message = on_message or _on_message
    
    client.username_pw_set(
        mqtt_username,
        mqtt_password 
    )

    mqtt_properties = Properties(PacketTypes.PUBLISH)
    mqtt_properties.MessageExpiryInterval = 30  # in seconds
    
    properties = Properties(PacketTypes.CONNECT)
    properties.SessionExpiryInterval = 30 * 60  # in seconds
    console.print(f"Connecting to mqtt://{mqtt_host}:{mqtt_port}")
    client.connect(
        mqtt_host,
        port=mqtt_port,
        # clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
        keepalive=60,
        properties=properties
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
                mqtt_password,
                "direwolf-monitor-log"
            )

            status.update(f"Opening file {my_file} for reading") 
            line_number = 0
            with open(my_file, 'r') as file:
                # now move the pointer to the end of the file
                status.update(f"Reading line {line_number} from {my_file}")
                file.seek(0, 2)
                for line in follow(file):
                    status.update(f"Reading line {line_number} from {my_file}")
                    line_number += 1
                    #print(line, end='')
                    print(f"Published {line}", end='')
                    client.publish(
                        mqtt_topic,
                        payload=line,
                        qos=0
                    )
        else:
            console.print(f"[bold red]{direwolf_log} doesn't exist.[/]")
            
            
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
    default=1883,
    show_default=True,
    help="MQTT Port"
)
@click.option(
    "--mqtt-topic",
    envvar="DWM_MQTT_TOPIC",
    default="direwolf",
    show_envvar=True,
    show_default=True,
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
    "--latitude",
    envvar="DWM_LATITUDE",
    show_envvar=True,
    help="GPS Latitude of the direwolf instance"
)
@click.option(
    "--longitude",
    envvar="DWM_LONGITUDE",
    show_envvar=True,
    help="GPS Longitude of the direwolf instance"
)
@click.pass_context
@cli_helper.process_standard_options
def mqtt_to_terminal(ctx, mqtt_host, mqtt_port, mqtt_topic, mqtt_username, mqtt_password,
                    latitude, longitude):
    """Pull direwolf log lines from mqtt and display them in the terminal!

    Args:
        ctx (_type_): _description_
        mqtt_host (_type_): _description_
        mqtt_port (_type_): _description_
        mqtt_topic (_type_): _description_
        mqtt_username (_type_): _description_
        mqtt_password (_type_): _description_
    """
    console = ctx.obj['console']

    def _rx_on_connect(client, userdata, flags, rc, properties):
        console.print(f"Connected with result code {rc}")
        console.print(f"userdata: {userdata}")
        console.print(f"flags: {flags}")
        client.subscribe(mqtt_topic)
        console.print(f"Subscribed to topic {mqtt_topic}")
        
    def _rx_on_connect_fail(client, userdata):
        console.print("Failed to connect to MQTT host")

    def _rx_on_disconnect(client, userdata, flags, rc, properties):
        console.print(f"Disconnected from mqtt server {mqtt_host} result code: {rc}")
        console.print(f"userdata: {userdata}")
        
    def _rx_on_message(client, userdata, msg):
        # console.out(f"{msg.topic} msg '{msg.payload}'")
        line = msg.payload.decode('UTF-8').strip()
        #console.out(f"RAW line = '{line}'")
        search = re.search("^\[\d\.*\d*\] (.*)", line)
        if search is not None:
            packetstring = search.group(1)
            packetstring = packetstring.replace('<0x0d>','\x0d'). \
                replace('<0x1c>','\x1c').replace('<0x1e>','\x1e'). \
                replace('<0x1f>','\0x1f').replace('<0x0a>','\0x0a')
            packet = packet_utils.parse_packet(packetstring)
            if packet:
                #aprsd_log.log(packet)
                packet_utils.packet_print(ctx, packet, latitude=latitude, longitude=longitude)
            #console.print(packet)
        elif "[0L]" in line:
            # packet that direwolf Transmitted
            raw = line.replace("[0L]", "").strip()
            #console.print(f"OL {raw}")
            packet = packet_utils.parse_packet(raw)
            if packet:
                #aprsd_log.log(packet, tx=True)
                packet_utils.packet_print(ctx, packet, latitude=latitude, longitude=longitude, tx=True)
        # elif "[0H]" in line:
            # packet RX'd already covered?
            # raw = line.replace("[0H]", "").strip()
            # console.print(f"IG {raw}")
            # packet = _parse_packet(raw)
            # if packet:
            #     aprsd_log.log(packet)
            return
        elif "[ig]" in line:
            # Packet sent to direwolf from APRSIS
            # strip out the [ig]
            raw = line.replace("[ig]", "").strip()
            console.print(f"IG {raw}")
            packet = packet_utils.parse_packet(raw)
            if packet:
                #aprsd_log.log(packet)
                packet_utils.packet_print(ctx, packet, latitude=latitude, longitude=longitude)
            #console.print(packet)
        elif "[rx>ig]" in line:
            # Got a line from RF and sent to APRSIS 
            if line != "[rx>ig] #":
                #console.print(f"RX->IG '{line}'")
                pass
            else:
                pass
                #console.out(f"Ignoring '{line}'")
        elif "[ig>tx]" in line:
            raw = line.replace("[ig>tx]", "").strip()
            # console.print(f"IG>TX {raw}")
            packet = packet_utils.parse_packet(raw)
            if packet:
                # aprsd_log.log(packet)
                packet_utils.packet_print(
                    ctx, packet, latitude=latitude, longitude=longitude,
                    header="\[ig>tx]"
                )
            
        elif 'ig_to_tx' in line:
            # ignoring
            # console.out(f"Ignoring '{line}'")
            return
        else:
            # ignore
            #console.print(f"Ignoring '{line}'")
            return

    msg = f"Connecting to MQTT server {mqtt_host}"
    with console.status(msg) as status:
        # Create mqtt client connection
        status.update("Creating MQTT connection")
        client = _create_mqtt_client(
            ctx,
            mqtt_host,
            int(mqtt_port),
            mqtt_username,
            mqtt_password,
            "direwolf-monitor-terminal",
            on_connect = _rx_on_connect,
            on_connect_fail = _rx_on_connect_fail,
            on_message = _rx_on_message,
        )

        client.on_connect = _rx_on_connect
        client.on_disconnect = _rx_on_disconnect
        client.on_message = _rx_on_message
        client.connect(mqtt_host, mqtt_port, 60)

    client.loop_forever(timeout=60)