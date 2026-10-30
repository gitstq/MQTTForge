"""Human readable rendering of MQTT packets and raw bytes.

Used by the ``decode`` command, by ``--verbose`` modes and by anyone who wants
to pretty-print a captured frame without pulling in a hex editor.
"""

from typing import List

from .packets import (
    PACKET_NAMES,
    QOS_NAMES,
    Connack,
    Connect,
    Disconnect,
    PacketType,
    Pingreq,
    Pingresp,
    Puback,
    Pubcomp,
    Publish,
    Pubrec,
    Pubrel,
    Suback,
    Subscribe,
    Unsuback,
    Unsubscribe,
)

#: Rendering width used by :func:`hexdump`.
DEFAULT_WIDTH = 16


def _qos_label(qos: int) -> str:
    return QOS_NAMES.get(qos, "QoS %s" % qos)


def _preview(payload: bytes, limit: int = 48) -> str:
    """Render a payload preview, escaping anything non printable."""
    if payload is None:
        return ""
    chunk = bytes(payload[:limit])
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    suffix = " ..." if len(payload) > limit else ""
    return "%s%s" % (text, suffix)


def describe(packet) -> str:
    """Render a single packet as an indented, multi-line report."""
    lines: List[str] = []
    packet_type = _type_of(packet)
    name = PACKET_NAMES.get(packet_type, type(packet).__name__)
    lines.append("%s" % name)

    if isinstance(packet, Connect):
        lines.append("  protocol      : %s v%d" % (packet.protocol_name, packet.protocol_level))
        lines.append("  client id     : %s" % (packet.client_id or "<empty>"))
        lines.append("  clean session : %s" % packet.clean_session)
        lines.append("  keep alive    : %ds" % packet.keepalive)
        lines.append("  username      : %s" % (packet.username or "-"))
        lines.append("  password      : %s" % ("<set>" if packet.password is not None else "-"))
        if packet.will is not None:
            lines.append(
                "  will          : %s (qos=%d, retain=%s, %d bytes)"
                % (packet.will.topic, packet.will.qos, packet.will.retain,
                   len(packet.will.payload))
            )
        return "\n".join(lines)

    if isinstance(packet, Connack):
        lines.append("  session present: %s" % packet.session_present)
        lines.append("  return code    : %d (%s)" % (packet.return_code, packet.message))
        return "\n".join(lines)

    if isinstance(packet, Publish):
        lines.append("  topic         : %s" % packet.topic)
        lines.append("  qos           : %s" % _qos_label(packet.qos))
        lines.append("  retain        : %s" % packet.retain)
        lines.append("  dup           : %s" % packet.dup)
        lines.append("  packet id     : %s" % (packet.packet_id or "-"))
        lines.append("  payload       : %d bytes" % len(packet.payload))
        lines.append("  preview       : %r" % _preview(packet.payload))
        return "\n".join(lines)

    if isinstance(packet, (Puback, Pubrec, Pubrel, Pubcomp, Suback, Unsuback)):
        lines.append("  packet id     : %d" % packet.packet_id)
        if isinstance(packet, Suback):
            lines.append("  granted qos   : %s" % packet.granted_qos)
        return "\n".join(lines)

    if isinstance(packet, Subscribe):
        lines.append("  packet id     : %d" % packet.packet_id)
        for topic_filter, qos in packet.subscriptions:
            lines.append("  subscribe     : %s -> %s" % (topic_filter, _qos_label(qos)))
        return "\n".join(lines)

    if isinstance(packet, Unsubscribe):
        lines.append("  packet id     : %d" % packet.packet_id)
        for topic_filter in packet.filters:
            lines.append("  unsubscribe   : %s" % topic_filter)
        return "\n".join(lines)

    if isinstance(packet, (Pingreq, Pingresp, Disconnect)):
        lines.append("  (no payload)")
        return "\n".join(lines)

    lines.append("  raw           : %r" % (packet,))
    return "\n".join(lines)


def _type_of(packet) -> PacketType:
    """Map a packet object back to its :class:`PacketType`."""
    mapping = {
        Connect: PacketType.CONNECT,
        Connack: PacketType.CONNACK,
        Publish: PacketType.PUBLISH,
        Puback: PacketType.PUBACK,
        Pubrec: PacketType.PUBREC,
        Pubrel: PacketType.PUBREL,
        Pubcomp: PacketType.PUBCOMP,
        Subscribe: PacketType.SUBSCRIBE,
        Suback: PacketType.SUBACK,
        Unsubscribe: PacketType.UNSUBSCRIBE,
        Unsuback: PacketType.UNSUBACK,
        Pingreq: PacketType.PINGREQ,
        Pingresp: PacketType.PINGRESP,
        Disconnect: PacketType.DISCONNECT,
    }
    for klass, packet_type in mapping.items():
        if isinstance(packet, klass):
            return packet_type
    return PacketType.CONNECT


def hexdump(data: bytes, width: int = DEFAULT_WIDTH) -> str:
    """Render ``data`` in the classic offset / hex / ASCII layout."""
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join("%02X" % byte for byte in chunk)
        ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append("%08X  %-*s  |%s|" % (offset, width * 3 - 1, hex_part, ascii_part))
    if not lines:
        lines.append("%08X  (empty)" % 0)
    return "\n".join(lines)


def format_packets(packets) -> str:
    """Render a sequence of packets into a single printable report."""
    blocks = []
    for index, packet in enumerate(packets, start=1):
        blocks.append("---- frame #%d ----" % index)
        blocks.append(describe(packet))
    return "\n".join(blocks)


__all__ = ["describe", "hexdump", "format_packets", "DEFAULT_WIDTH"]
