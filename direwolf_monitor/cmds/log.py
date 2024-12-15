import logging
from pathlib import Path
import re
import time
from typing import Iterator, Optional

import aprslib
import click
from haversine import Unit, haversine
from aprsd import conf
from aprsd.packets import core as aprsd_core
from aprsd.packets import log as aprsd_log
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

import direwolf_monitor
from direwolf_monitor.cli import cli
from direwolf_monitor import cli_helper
from direwolf_monitor import utils
from PIL import Image
from term_image.image import AutoImage


LOG = logging.getLogger("dwm")

symbol_chart0 = Image.open("aprs-symbols-128-0.png")
symbol_chart1 = Image.open("aprs-symbols-128-1.png")


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
    print(f"Published {mid}:{userdata}")

def _on_connect(client, userdata, flags, rc):
    print(f"Connected to mqtt://{client}")

def _on_disconnect(client, userdata, rc, flags, ass):
    print("MQTT Client disconnected")
    print(f"_on_disconnect rc:{rc} flags:{flags}")
            
def _create_mqtt_client(ctx, mqtt_host, mqtt_port, mqtt_username, mqtt_password,
                        client_id):
    console = ctx.obj['console']
    
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        # transport='websockets',
        # protocol=mqtt.MQTTv5
        transport='tcp',
        protocol=mqtt.MQTTv311
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
    console.print(f"Connecting to mqtt://{mqtt_host}:{mqtt_port}")
    client.connect(
        mqtt_host,
        port=mqtt_port,
        # clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
        keepalive=60,
        # properties=properties
    )
    return client


def _create_symbol_image(symbol, symbol_table):
    symbol_dimension = 128
    offset = ord(symbol) - 33
    row = offset // 16
    col = offset % 16
    crop_area = (
        col*symbol_dimension,
        row*symbol_dimension,
        col*symbol_dimension+symbol_dimension,
        row*symbol_dimension+symbol_dimension
    )
    if symbol_table == "/":
        test = symbol_chart0.crop(crop_area)
    else:
        test = symbol_chart1.crop(crop_area)
        
    real = AutoImage(test)
    real.height=1
    return real


def packet_print(ctx, packet: aprsd_core.Packet,
                 latitude,
                 longitude,
                 tx: Optional[bool] = False,
                 header: Optional[bool] = True) -> None:
    FROM_COLOR = "#C70039"
    TO_COLOR = "#D033FF"
    TX_COLOR = "red"
    RX_COLOR = "green"
    PACKET_COLOR = "cyan"
    DISTANCE_COLOR = "#FF5733"
    DEGREES_COLOR = "#FFA900"
    
    logit = []
    name = packet.__class__.__name__
    pkt_max_send_count = 3

    if header:
        if tx:
            via_color = "red"
            arrow = f"[{via_color}]\u2192[/]"
            logit.append(
                f"[bold red]TX\u2191[/] "
                f"[cyan]{name}[/]"
                #f":{packet.msgNo}"
                #f" ({packet.send_count + 1} of {pkt_max_send_count})",
            )
        else:
            via_color = "#1AA730"
            arrow = f"[{via_color}]\u2192[/]"
            f"[{via_color}]<-[/]"
            logit.append(
                f"[#1AA730]RX\u2193[/] "
                f"[cyan]{name}[/]"
                #f":{packet.msgNo}",
            )
    else:
        via_color = "green"
        arrow = f"[{via_color}]->[/]"
        logit.append(
            f"[cyan]{name}[/]"
            f":{packet.msgNo}",
        )
        
    if hasattr(packet, "symbol"):
        logit.append(" __XXIMAGEXX__ ")
    else:
        logit.append(" ")

    tmp = None
    if packet.path:
        tmp = f" {arrow} ".join(packet.path) + f" {arrow} "

    logit.append(
        f"[{FROM_COLOR}]{packet.from_call}[/] {arrow}"
        f"{tmp if tmp else ' '}"
        f"[{TO_COLOR}]{packet.to_call}[/]",
    )

    if not isinstance(packet, aprsd_core.AckPacket) and not isinstance(packet, aprsd_core.RejectPacket):
        logit.append(" : ")
        msg = packet.human_info

        if msg:
            msg = msg.replace("<", "\\<")
            logit.append(f"[bright_yellow]{msg}[/]")

    # is there distance information?
    if isinstance(packet, aprsd_core.GPSPacket) and latitude and longitude:
        my_coords = (float(latitude), float(longitude))
        packet_coords = (packet.latitude, packet.longitude)
        try:
            bearing = utils.calculate_initial_compass_bearing(my_coords, packet_coords)
        except Exception as e:
            LOG.error(f"Failed to calculate bearing: {e}")
            bearing = 0
        logit.append(
            f" : [{DEGREES_COLOR}]{utils.degrees_to_cardinal(bearing, full_string=True)}[/]"
            f"[green]@[/][{DISTANCE_COLOR}]{haversine(my_coords, packet_coords, unit=Unit.MILES):.2f}[/] miles",
        )

    console = ctx.obj['console']
    with console.capture() as capture:
        for entry in logit:
            console.print(entry, end="")
    out_str = capture.get()
    if "__XXIMAGEXX__" in out_str:
        symbol_image = _create_symbol_image(packet.symbol, packet.symbol_table)
        final_str = out_str.replace("__XXIMAGEXX__", "{symbol_image:1.1#}")
        vars = {"symbol_image": symbol_image}
        print(final_str.format(**vars))
    else:
        print(out_str)


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
                mqtt_password,
                "direwolf-monitor-log"
            )
            
            line_number = 0
            with open(my_file, 'r') as file:
                # now move the pointer to the end of the file
                file.seek(0, 2)
                for line in follow(file):
                    status.update(f"Reading line {line_number} from {direwolf_log}")
                    line_number += 1
                    print(line, end='')
                    if client.is_connected():
                        print("Publishing line")
                        client.publish(
                            mqtt_topic,
                            payload=line,
                            qos=0
                        )
                    else:
                        print("Client is not Connected.  Reconnect")
                        client.connect(mqtt_host, int(mqtt_port))
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

    def _rx_on_connect(client, userdata, flags, rc, ass):
        console.print(f"Connected with result code {rc}")
        console.print(f"userdata: {userdata}")
        console.print(f"flags: {flags}")
        client.subscribe(mqtt_topic)
        console.print(f"Subscribed to topic {mqtt_topic}")

    def _rx_on_disconnect(client, userdata, flags, rc, ass):
        console.print(f"Disconnected from mqtt server {mqtt_host} result code: {rc}")
        console.print(f"userdata: {userdata}")
        
    def _parse_packet(raw):
        try:
            packet_json = aprslib.parse(raw)
            return aprsd_core.factory(packet_json)
        except aprslib.exceptions.ParseError as e:
            # console.print(f"[bold red]Failed to parse '{raw}' because '{e}'")
            pass
        except aprslib.exceptions.UnknownFormat as e:
            # console.print(f"[bold red]Failed to parse '{raw}' because '{e}'")
            pass

    def _rx_on_message(client, userdata, msg):
        # console.out(f"{msg.topic} msg '{msg.payload}'")
        line = msg.payload.decode('UTF-8').strip()
        #console.out(f"RAW line = '{line}'")
        search = re.search("^\[\d\.*\d*\] (.*)", line)
        if search is not None:
            console.print(search)
            packetstring = search.group(1)
            packetstring = packetstring.replace('<0x0d>','\x0d'). \
                replace('<0x1c>','\x1c').replace('<0x1e>','\x1e'). \
                replace('<0x1f>','\0x1f').replace('<0x0a>','\0x0a')
            packet = _parse_packet(packetstring)
            if packet:
                #aprsd_log.log(packet)
                packet_print(ctx, packet, latitude=latitude,
                             longitude=longitude)
            #console.print(packet)
        elif "[0L]" in line:
            # packet that direwolf Transmitted
            raw = line.replace("[0L]", "").strip()
            #console.print(f"OL {raw}")
            packet = _parse_packet(raw)
            if packet:
                #aprsd_log.log(packet, tx=True)
                packet_print(ctx, packet, latitude=latitude,
                             longitude=longitude,
                             tx=True)
         #elif "[0H]" in line:
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
            #console.print(f"IG {raw}")
            packet = _parse_packet(raw)
            if packet:
                #aprsd_log.log(packet)
                packet_print(ctx, packet, latitude=latitude,
                             longitude=longitude)
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
            #console.print(f"IG>TX {raw}")
            packet = _parse_packet(raw)
            if packet:
                # aprsd_log.log(packet)
                packet_print(ctx, packet, latitude=latitude,
                             longitude=longitude)
            
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
            "direwolf-monitor-terminal"
        )

        client.on_connect = _rx_on_connect
        client.on_disconnect = _rx_on_disconnect
        client.on_message = _rx_on_message
        client.connect(mqtt_host, mqtt_port, 60)

    client.loop_forever(timeout=60)