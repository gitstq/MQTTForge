"""MQTT 3.1.1 wire format encoder / decoder.

The module is deliberately dependency free and works purely on ``bytes`` so it
can be reused for unit tests (``BytesIO`` backed), socket reads and offline
packet forensics (``decode_packets``).

Layout of every control packet::

    +------+------------------+---------------------+----------------+
    | byte | bits 7-4         | bits 3-0            | remaining len  |
    |  0   | packet type      | type specific flags | 1..4 bytes     |
    +------+------------------+---------------------+----------------+
    | variable header (per packet type)                              |
    +----------------------------------------------------------------+
    | payload (per packet type)                                      |
    +----------------------------------------------------------------+
"""

import struct
from typing import Callable, List, Tuple

from .errors import CodecError, ProtocolError
from .packets import (
    REQUIRED_FLAGS,
    QOS_2,
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
    Will,
)

#: Maximum value the remaining-length field can encode (4 bytes x 7 bits).
MAX_REMAINING_LENGTH = 268435455
#: Maximum number of bytes in the remaining-length field.
MAX_REMAINING_BYTES = 4
#: Maximum length of a UTF-8 encoded string / binary field (2 byte prefix).
MAX_FIELD_BYTES = 65535


# --------------------------------------------------------------------------
# Primitive helpers
# --------------------------------------------------------------------------
def encode_remaining_length(length: int) -> bytes:
    """Encode a length using the MQTT variable byte integer scheme.

    Args:
        length: Value to encode, ``0 .. 268435455``.

    Returns:
        1 to 4 bytes, little-endian base-128 with a continuation bit.

    Raises:
        CodecError: If the value is out of range.
    """
    if length < 0 or length > MAX_REMAINING_LENGTH:
        raise CodecError(
            "remaining length %d out of range (0..%d)" % (length, MAX_REMAINING_LENGTH)
        )
    out = bytearray()
    value = length
    while True:
        digit = value % 128
        value //= 128
        if value > 0:
            digit |= 0x80
        out.append(digit)
        if value == 0:
            return bytes(out)


def decode_remaining_length(read_exact: Callable[[int], bytes]) -> int:
    """Decode a variable byte integer from a byte source.

    Args:
        read_exact: Callable returning exactly *n* bytes.

    Returns:
        The decoded integer.

    Raises:
        CodecError: If the field is malformed or exceeds 4 bytes.
    """
    multiplier = 1
    value = 0
    for _ in range(MAX_REMAINING_BYTES):
        chunk = read_exact(1)
        if not chunk:
            raise CodecError("unexpected end of stream while reading remaining length")
        byte = chunk[0]
        value += (byte & 0x7F) * multiplier
        if not byte & 0x80:
            return value
        multiplier *= 128
    raise CodecError("malformed remaining length: continuation bit set on 4th byte")


def _encode_string(value: str) -> bytes:
    """Encode a UTF-8 string with the mandatory 2 byte length prefix."""
    raw = value.encode("utf-8")
    if len(raw) > MAX_FIELD_BYTES:
        raise CodecError("string longer than %d bytes" % MAX_FIELD_BYTES)
    return struct.pack("!H", len(raw)) + raw


def _encode_binary(value: bytes) -> bytes:
    """Encode a binary blob with the mandatory 2 byte length prefix."""
    if len(value) > MAX_FIELD_BYTES:
        raise CodecError("binary field longer than %d bytes" % MAX_FIELD_BYTES)
    return struct.pack("!H", len(value)) + value


def _decode_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Decode a length prefixed UTF-8 string. Returns ``(value, new_offset)``."""
    if offset + 2 > len(data):
        raise CodecError("truncated string length prefix")
    (length,) = struct.unpack_from("!H", data, offset)
    offset += 2
    if offset + length > len(data):
        raise CodecError("truncated string body")
    raw = data[offset : offset + length]
    offset += length
    try:
        return raw.decode("utf-8"), offset
    except UnicodeDecodeError as exc:  # MQTT-1.5.4 mandates well formed UTF-8
        raise CodecError("invalid UTF-8 in string field: %s" % exc) from exc


def _decode_binary(data: bytes, offset: int) -> Tuple[bytes, int]:
    """Decode a length prefixed binary blob. Returns ``(value, new_offset)``."""
    if offset + 2 > len(data):
        raise CodecError("truncated binary length prefix")
    (length,) = struct.unpack_from("!H", data, offset)
    offset += 2
    if offset + length > len(data):
        raise CodecError("truncated binary body")
    return data[offset : offset + length], offset + length


def _decode_uint16(data: bytes, offset: int) -> Tuple[int, int]:
    """Decode a big-endian 16 bit unsigned integer."""
    if offset + 2 > len(data):
        raise CodecError("truncated 16 bit field")
    (value,) = struct.unpack_from("!H", data, offset)
    return value, offset + 2


def _read_exact_from_buffer(buffer: bytes):
    """Build a ``read_exact`` callable over an in-memory buffer."""
    state = {"pos": 0}

    def read_exact(count: int) -> bytes:
        start = state["pos"]
        end = start + count
        if end > len(buffer):
            raise CodecError(
                "unexpected end of buffer: need %d bytes, have %d"
                % (end - start, len(buffer) - start)
            )
        state["pos"] = end
        return buffer[start:end]

    return read_exact


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------
def _encode_connect(packet: Connect) -> bytes:
    flags = 0x00
    if packet.username is not None:
        flags |= 0x80
    if packet.password is not None:
        flags |= 0x40
    if packet.will is not None:
        flags |= 0x04
        flags |= (packet.will.qos & 0x03) << 3
        if packet.will.retain:
            flags |= 0x20
    if packet.clean_session:
        flags |= 0x02

    body = _encode_string(packet.protocol_name)
    body += bytes([packet.protocol_level & 0xFF, flags])
    body += struct.pack("!H", max(0, min(65535, int(packet.keepalive))))

    body += _encode_string(packet.client_id)
    if packet.will is not None:
        body += _encode_string(packet.will.topic)
        body += _encode_binary(packet.will.payload)
    if packet.username is not None:
        body += _encode_string(packet.username)
    if packet.password is not None:
        password = packet.password
        if isinstance(password, str):
            password = password.encode("utf-8")
        body += _encode_binary(password)
    return body


def _encode_publish(packet: Publish) -> bytes:
    flags = 0x00
    if packet.dup:
        flags |= 0x08
    flags |= (packet.qos & 0x03) << 1
    if packet.retain:
        flags |= 0x01

    body = _encode_string(packet.topic)
    if packet.qos > 0:
        body += struct.pack("!H", packet.packet_id)
    body += packet.payload
    return flags, body


def encode_packet(packet) -> bytes:
    """Serialise a control packet into a complete MQTT frame.

    Args:
        packet: One of the dataclasses defined in :mod:`mqttforge.packets`.

    Returns:
        The full frame including fixed header, ready to be written to a socket.

    Raises:
        CodecError: If the packet is of an unknown type or a field is invalid.
    """
    if isinstance(packet, Connect):
        return _build(PacketType.CONNECT, 0x00, _encode_connect(packet))
    if isinstance(packet, Connack):
        body = bytes([0x01 if packet.session_present else 0x00, packet.return_code & 0xFF])
        return _build(PacketType.CONNACK, 0x00, body)
    if isinstance(packet, Publish):
        flags, body = _encode_publish(packet)
        return _build(PacketType.PUBLISH, flags, body)
    if isinstance(packet, Puback):
        return _build(PacketType.PUBACK, 0x00, struct.pack("!H", packet.packet_id))
    if isinstance(packet, Pubrec):
        return _build(PacketType.PUBREC, 0x00, struct.pack("!H", packet.packet_id))
    if isinstance(packet, Pubrel):
        return _build(PacketType.PUBREL, 0x02, struct.pack("!H", packet.packet_id))
    if isinstance(packet, Pubcomp):
        return _build(PacketType.PUBCOMP, 0x00, struct.pack("!H", packet.packet_id))
    if isinstance(packet, Subscribe):
        body = struct.pack("!H", packet.packet_id)
        for topic_filter, qos in packet.subscriptions:
            body += _encode_string(topic_filter) + bytes([qos & 0x03])
        return _build(PacketType.SUBSCRIBE, 0x02, body)
    if isinstance(packet, Suback):
        body = struct.pack("!H", packet.packet_id)
        body += bytes(code & 0xFF for code in packet.return_codes)
        return _build(PacketType.SUBACK, 0x00, body)
    if isinstance(packet, Unsubscribe):
        body = struct.pack("!H", packet.packet_id)
        for topic_filter in packet.filters:
            body += _encode_string(topic_filter)
        return _build(PacketType.UNSUBSCRIBE, 0x02, body)
    if isinstance(packet, Unsuback):
        return _build(PacketType.UNSUBACK, 0x00, struct.pack("!H", packet.packet_id))
    if isinstance(packet, Pingreq):
        return _build(PacketType.PINGREQ, 0x00, b"")
    if isinstance(packet, Pingresp):
        return _build(PacketType.PINGRESP, 0x00, b"")
    if isinstance(packet, Disconnect):
        return _build(PacketType.DISCONNECT, 0x00, b"")
    raise CodecError("unsupported packet object: %r" % type(packet).__name__)


def _build(packet_type: PacketType, flags: int, body: bytes) -> bytes:
    """Assemble fixed header + variable header/payload."""
    fixed = bytearray()
    fixed.append(((int(packet_type) & 0x0F) << 4) | (flags & 0x0F))
    fixed += encode_remaining_length(len(body))
    return bytes(fixed) + body


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------
def _check_flags(packet_type: PacketType, flags: int) -> None:
    """Validate the reserved-flag rules of MQTT-2.2.2-1..2."""
    expected = REQUIRED_FLAGS.get(packet_type, 0x00)
    if flags != expected:
        raise ProtocolError(
            "invalid fixed header flags 0x%02X for %s (expected 0x%02X)"
            % (flags, packet_type.name, expected)
        )


def _decode_publish(flags: int, body: bytes) -> Publish:
    dup = bool(flags & 0x08)
    qos = (flags >> 1) & 0x03
    retain = bool(flags & 0x01)
    if qos == 3:
        raise ProtocolError("invalid QoS value 3 in PUBLISH header")
    topic, offset = _decode_string(body, 0)
    packet_id = None
    if qos > 0:
        packet_id, offset = _decode_uint16(body, offset)
    payload = body[offset:]
    return Publish(
        topic=topic,
        payload=payload,
        qos=qos,
        retain=retain,
        dup=dup,
        packet_id=packet_id,
    )


def _decode_connect(body: bytes) -> Connect:
    offset = 0
    protocol_name, offset = _decode_string(body, offset)
    if offset + 3 > len(body):
        raise CodecError("truncated CONNECT variable header")
    protocol_level = body[offset]
    flags = body[offset + 1]
    offset += 2
    keepalive, offset = _decode_uint16(body, offset)

    client_id, offset = _decode_string(body, offset)

    will = None
    if flags & 0x04:
        will_topic, offset = _decode_string(body, offset)
        will_payload, offset = _decode_binary(body, offset)
        will = Will(
            topic=will_topic,
            payload=will_payload,
            qos=(flags >> 3) & 0x03,
            retain=bool(flags & 0x20),
        )

    username = None
    if flags & 0x80:
        username, offset = _decode_string(body, offset)

    password = None
    if flags & 0x40:
        password, offset = _decode_binary(body, offset)

    return Connect(
        client_id=client_id,
        clean_session=bool(flags & 0x02),
        keepalive=keepalive,
        username=username,
        password=password,
        will=will,
        protocol_name=protocol_name,
        protocol_level=protocol_level,
    )


def _decode_body(packet_type: PacketType, flags: int, body: bytes):
    """Decode the variable header and payload of a single packet."""
    # PUBLISH encodes DUP/QoS/RETAIN in the flag nibble; every other packet
    # type has a fixed, reserved flag value (MQTT-2.2.2-1).
    if packet_type is not PacketType.PUBLISH:
        _check_flags(packet_type, flags)
    if packet_type is PacketType.CONNECT:
        return _decode_connect(body)
    if packet_type is PacketType.CONNACK:
        if len(body) < 2:
            raise CodecError("truncated CONNACK body")
        return Connack(session_present=bool(body[0] & 0x01), return_code=body[1])
    if packet_type is PacketType.PUBLISH:
        return _decode_publish(flags, body)
    if packet_type in (
        PacketType.PUBACK,
        PacketType.PUBREC,
        PacketType.PUBREL,
        PacketType.PUBCOMP,
        PacketType.UNSUBACK,
    ):
        if len(body) < 2:
            raise CodecError("truncated %s body" % packet_type.name)
        (packet_id,) = struct.unpack_from("!H", body, 0)
        return {
            PacketType.PUBACK: Puback,
            PacketType.PUBREC: Pubrec,
            PacketType.PUBREL: Pubrel,
            PacketType.PUBCOMP: Pubcomp,
            PacketType.UNSUBACK: Unsuback,
        }[packet_type](packet_id=packet_id)
    if packet_type is PacketType.SUBSCRIBE:
        packet_id, offset = _decode_uint16(body, 0)
        subscriptions = []
        while offset < len(body):
            topic_filter, offset = _decode_string(body, offset)
            if offset >= len(body):
                raise CodecError("SUBSCRIBE missing QoS byte")
            subscriptions.append((topic_filter, body[offset] & 0x03))
            offset += 1
        return Subscribe(packet_id=packet_id, subscriptions=subscriptions)
    if packet_type is PacketType.SUBACK:
        packet_id, offset = _decode_uint16(body, 0)
        return Suback(packet_id=packet_id, return_codes=list(body[offset:]))
    if packet_type is PacketType.UNSUBSCRIBE:
        packet_id, offset = _decode_uint16(body, 0)
        filters = []
        while offset < len(body):
            topic_filter, offset = _decode_string(body, offset)
            filters.append(topic_filter)
        return Unsubscribe(packet_id=packet_id, filters=filters)
    if packet_type is PacketType.PINGREQ:
        return Pingreq()
    if packet_type is PacketType.PINGRESP:
        return Pingresp()
    if packet_type is PacketType.DISCONNECT:
        return Disconnect()
    raise CodecError("unknown packet type %d" % int(packet_type))


def read_packet(read_exact: Callable[[int], bytes]):
    """Read exactly one packet from a byte source.

    Args:
        read_exact: Callable returning exactly *n* bytes, typically backed by a
            socket with a buffered reader.

    Returns:
        The decoded packet object.

    Raises:
        CodecError: If the stream ends unexpectedly or the frame is malformed.
        ProtocolError: If fixed header flags violate the specification.
    """
    first = read_exact(1)
    if not first:
        raise CodecError("connection closed by peer")
    byte0 = first[0]
    raw_type = (byte0 >> 4) & 0x0F
    flags = byte0 & 0x0F
    try:
        packet_type = PacketType(raw_type)
    except ValueError as exc:
        raise CodecError("unknown packet type %d" % raw_type) from exc
    remaining = decode_remaining_length(read_exact)
    body = read_exact(remaining) if remaining else b""
    return _decode_body(packet_type, flags, body)


def _decode_at(data: bytes, offset: int):
    """Decode one frame starting at ``offset``. Returns ``(packet, new_offset)``."""
    if offset >= len(data):
        raise CodecError("no data left to decode")
    byte0 = data[offset]
    offset += 1
    raw_type = (byte0 >> 4) & 0x0F
    flags = byte0 & 0x0F
    try:
        packet_type = PacketType(raw_type)
    except ValueError as exc:
        raise CodecError("unknown packet type %d" % raw_type) from exc

    multiplier = 1
    remaining = 0
    for _ in range(MAX_REMAINING_BYTES):
        if offset >= len(data):
            raise CodecError("truncated remaining length")
        byte = data[offset]
        offset += 1
        remaining += (byte & 0x7F) * multiplier
        if not byte & 0x80:
            break
        multiplier *= 128
    else:
        raise CodecError("malformed remaining length: continuation bit set on 4th byte")

    if offset + remaining > len(data):
        raise CodecError(
            "truncated packet body: need %d bytes, have %d"
            % (remaining, len(data) - offset)
        )
    body = data[offset : offset + remaining]
    return _decode_body(packet_type, flags, body), offset + remaining


def decode_packets(data: bytes, allow_partial: bool = False):
    """Decode a buffer that may contain several concatenated packets.

    Args:
        data: Raw bytes captured from the wire, a pcap payload or a file.
        allow_partial: When ``True`` a trailing incomplete frame is returned as
            the second element instead of raising.

    Returns:
        ``(packets, leftover)`` where *leftover* is ``b""`` unless
        ``allow_partial`` is set and the buffer ends mid-frame.

    Raises:
        CodecError: If a frame is malformed and ``allow_partial`` is ``False``.

    Examples:
        >>> packets, rest = decode_packets(bytes.fromhex("C000"))
        >>> packets[0].__class__.__name__
        'Pingreq'
    """
    packets: List = []
    offset = 0
    while offset < len(data):
        try:
            packet, offset = _decode_at(data, offset)
        except CodecError:
            if allow_partial:
                return packets, data[offset:]
            raise
        packets.append(packet)
    return packets, b""


def decode_one(data: bytes):
    """Decode a single packet from ``data``, ignoring any trailing bytes.

    Args:
        data: Raw frame bytes.

    Returns:
        The decoded packet object.

    Raises:
        CodecError: If the frame is malformed.
    """
    packet, _ = _decode_at(bytes(data), 0)
    return packet


def encode_hex(data: bytes) -> str:
    """Return the uppercase hex representation of ``data``."""
    return data.hex().upper()


def decode_hex(text: str) -> bytes:
    """Parse a hex string (spaces and ``0x`` prefixes allowed) into bytes."""
    cleaned = "".join(text.split()).replace("0x", "").replace("0X", "")
    if len(cleaned) % 2:
        raise CodecError("hex string must contain an even number of digits")
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise CodecError("invalid hex string: %s" % exc) from exc


#: Maximum QoS value accepted by the encoder, re-exported for convenience.
MAX_QOS = QOS_2

__all__ = [
    "MAX_REMAINING_LENGTH",
    "MAX_FIELD_BYTES",
    "encode_remaining_length",
    "decode_remaining_length",
    "encode_packet",
    "read_packet",
    "decode_packets",
    "decode_one",
    "encode_hex",
    "decode_hex",
    "MAX_QOS",
]
