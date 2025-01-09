import logging
from typing import Optional

import aprslib
from aprsd.packets import core as aprsd_core
from PIL import Image
from term_image.image import AutoImage
from haversine import Unit, haversine

from direwolf_monitor import utils

symbol_chart0 = Image.open("aprs-symbols-128-0.png")
symbol_chart1 = Image.open("aprs-symbols-128-1.png")

LOG = logging.getLogger("dwm")

def parse_packet(raw):
    try:
        packet_json = aprslib.parse(raw)
        return aprsd_core.factory(packet_json)
    except aprslib.exceptions.ParseError:
        # console.print(f"[bold red]Failed to parse '{raw}' because '{e}'")
        pass
    except aprslib.exceptions.UnknownFormat:
        # console.print(f"[bold red]Failed to parse '{raw}' because '{e}'")
        pass
    
    
    
def create_symbol_image(symbol, symbol_table):
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


def add_gps(logit, packet, my_latitude=0, my_longitude=0):
    DISTANCE_COLOR = "#FF5733"
    DEGREES_COLOR = "#FFA900"
    if hasattr(packet, "latitude") and hasattr(packet, "longitude"):
        my_coords = (float(my_latitude), float(my_longitude))
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
    
    
def packet_print(ctx, packet: aprsd_core.Packet,
                 latitude: float, longitude: float,
                 tx: Optional[bool] = False,
                 header: Optional[str] = None) -> None:
    FROM_COLOR = "#C70039"
    TO_COLOR = "#D033FF"

    logit = []
    name = packet.__class__.__name__

    if header:
        if tx:
            via_color = "red"
            logit.append(
                f"[bold red]{header}\u2191[/] "
                f"[cyan]{name}[/]"
            )
        else:
            via_color = "#1AA730"
            f"[{via_color}]<-[/]"
            logit.append(
                f"[#1AA730]{header}\u2193[/] "
                f"[cyan]{name}[/]"
            )
        arrow = f"[{via_color}]\u2192[/]"
    else:
        if tx:
            via_color = "red"
            logit.append(
                f"[bold red]TX\u2191[/] "
                f"[cyan]{name}[/]"
            )
        else:
            via_color = "#1AA730"
            f"[{via_color}]<-[/]"
            logit.append(
                f"[#1AA730]PISS\u2193[/] "
                f"[cyan]{name}[/]"
            )
        arrow = f"[{via_color}]\u2192[/]"

    if hasattr(packet, "symbol"):
        logit.append(" __XXIMAGEXX__ ")
    else:
        logit.append(" ")

    tmp = f'{f"{arrow}".join(packet.path)}{arrow}' if packet.path else None
    logit.append(
        f"[{FROM_COLOR}]{packet.from_call}[/]{arrow}"
        f"{tmp if tmp else ' '}"
        f"[{TO_COLOR}]{packet.to_call}[/]",
    )

    if isinstance(packet, aprsd_core.ThirdPartyPacket):
        # show the original tx -> rx callsigns
        sub_pkt = packet.subpacket
        if sub_pkt.path:
            tmp = f'{f"{arrow}".join(sub_pkt.path)}{arrow}'

        sub_head = f" ([{FROM_COLOR}]{sub_pkt.from_call}[/]{arrow}" \
            f"{tmp if tmp else ' '}" \
            f"[{TO_COLOR}]{sub_pkt.to_call}[/]) :"

        logit.extend((sub_head, sub_pkt.human_info))
        if latitude:
            add_gps(logit, sub_pkt, latitude, longitude)

    elif not isinstance(packet, aprsd_core.AckPacket) and not isinstance(packet, aprsd_core.RejectPacket):
        logit.append(" : ")
        if msg := packet.human_info:
            msg = msg.replace("<", "\\<")
            logit.append(f"[bright_yellow]{msg}[/]")

    if latitude:
        add_gps(logit, packet, latitude, longitude)

    console = ctx.obj['console']
    with console.capture() as capture:
        for entry in logit:
            console.print(entry, end="")
    out_str = capture.get()
    if "__XXIMAGEXX__" in out_str:
        symbol_image = create_symbol_image(packet.symbol, packet.symbol_table)
        final_str = out_str.replace("__XXIMAGEXX__", "{symbol_image:1.1#}")
        vars = {"symbol_image": symbol_image}
        print(final_str.format(**vars))
    else:
        print(out_str)