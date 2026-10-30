"""MQTT 3.1.1 control packet data model.

Every control packet is modelled as a frozen-ish :mod:`dataclasses` dataclass.
The wire representation lives in :mod:`mqttforge.codec`; this module is purely
a declarative description of the protocol so that user code, the client, the
broker and the CLI can all share one vocabulary.

Reference: OASIS MQTT Version 3.1.1 specification, section 2 (control packet
format) and section 3 (packet payloads).
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Tuple, Union

from .version import PROTOCOL_LEVEL, PROTOCOL_NAME


class PacketType(IntEnum):
    """MQTT 3.1.1 control packet types (upper nibble of the first byte)."""

    CONNECT = 1
    CONNACK = 2
    PUBLISH = 3
    PUBACK = 4
    PUBREC = 5
    PUBREL = 6
    PUBCOMP = 7
    SUBSCRIBE = 8
    SUBACK = 9
    UNSUBSCRIBE = 10
    UNSUBACK = 11
    PINGREQ = 12
    PINGRESP = 13
    DISCONNECT = 14


#: Human readable packet names, indexed by :class:`PacketType`.
PACKET_NAMES = {
    PacketType.CONNECT: "CONNECT",
    PacketType.CONNACK: "CONNACK",
    PacketType.PUBLISH: "PUBLISH",
    PacketType.PUBACK: "PUBACK",
    PacketType.PUBREC: "PUBREC",
    PacketType.PUBREL: "PUBREL",
    PacketType.PUBCOMP: "PUBCOMP",
    PacketType.SUBSCRIBE: "SUBSCRIBE",
    PacketType.SUBACK: "SUBACK",
    PacketType.UNSUBSCRIBE: "UNSUBSCRIBE",
    PacketType.UNSUBACK: "UNSUBACK",
    PacketType.PINGREQ: "PINGREQ",
    PacketType.PINGRESP: "PINGRESP",
    PacketType.DISCONNECT: "DISCONNECT",
}

#: Flags that MUST be present in the fixed header of the given packet type.
REQUIRED_FLAGS = {
    PacketType.PUBREL: 0x02,
    PacketType.SUBSCRIBE: 0x02,
    PacketType.UNSUBSCRIBE: 0x02,
}

#: QoS levels understood by MQTT 3.1.1.
QOS_0 = 0
QOS_1 = 1
QOS_2 = 2
#: QoS value used by SUBACK to signal a failed subscription.
QOS_FAILURE = 0x80

#: Human readable QoS labels used by reports and the CLI.
QOS_NAMES = {
    0: "0 (at most once)",
    1: "1 (at least once)",
    2: "2 (exactly once)",
}

#: CONNACK return codes.
CONNACK_ACCEPTED = 0

CONNACK_MESSAGES = {
    0: "Connection accepted",
    1: "Connection refused - unacceptable protocol version",
    2: "Connection refused - identifier rejected",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad user name or password",
    5: "Connection refused - not authorized",
}

#: Lowest and highest legal packet identifier values.
PACKET_ID_MIN = 1
PACKET_ID_MAX = 0xFFFF


def validate_packet_id(packet_id: Optional[int]) -> int:
    """Validate and normalise a packet identifier.

    Args:
        packet_id: Identifier to validate.

    Returns:
        The identifier unchanged.

    Raises:
        ValueError: If the identifier is outside ``1..65535``.
    """
    if packet_id is None:
        raise ValueError("packet identifier is required for this packet")
    packet_id = int(packet_id)
    if not (PACKET_ID_MIN <= packet_id <= PACKET_ID_MAX):
        raise ValueError(
            "packet identifier must be in range %d..%d, got %d"
            % (PACKET_ID_MIN, PACKET_ID_MAX, packet_id)
        )
    return packet_id


def validate_qos(qos: int) -> int:
    """Validate a QoS level.

    Args:
        qos: Quality of service level to validate.

    Returns:
        The QoS unchanged.

    Raises:
        ValueError: If the QoS is not 0, 1 or 2.
    """
    qos = int(qos)
    if qos not in (QOS_0, QOS_1, QOS_2):
        raise ValueError("qos must be 0, 1 or 2, got %r" % (qos,))
    return qos


@dataclass
class Will:
    """Last Will and Testament message published by the broker on an
    ungraceful client disconnect.

    Attributes:
        topic: Topic the will message is published to.
        payload: Raw message body. ``str`` values are UTF-8 encoded.
        qos: QoS level used to deliver the will (0, 1 or 2).
        retain: Whether the broker should retain the will message.
    """

    topic: str
    payload: Union[bytes, bytearray, str] = b""
    qos: int = QOS_0
    retain: bool = False

    def __post_init__(self):
        validate_qos(self.qos)
        if isinstance(self.payload, str):
            self.payload = self.payload.encode("utf-8")
        elif isinstance(self.payload, bytearray):
            self.payload = bytes(self.payload)
        elif not isinstance(self.payload, bytes):
            raise TypeError("will payload must be bytes or str")


@dataclass
class Connect:
    """CONNECT - client request to establish a network connection."""

    client_id: str = ""
    clean_session: bool = True
    keepalive: int = 60
    username: Optional[str] = None
    password: Optional[Union[str, bytes]] = None
    will: Optional[Will] = None
    protocol_name: str = PROTOCOL_NAME
    protocol_level: int = PROTOCOL_LEVEL


@dataclass
class Connack:
    """CONNACK - broker acknowledgement of a CONNECT request."""

    session_present: bool = False
    return_code: int = CONNACK_ACCEPTED

    @property
    def message(self) -> str:
        """Human readable description of the return code."""
        return CONNACK_MESSAGES.get(self.return_code, "Unknown return code")

    @property
    def accepted(self) -> bool:
        """``True`` when the connection was accepted."""
        return self.return_code == CONNACK_ACCEPTED


@dataclass
class Publish:
    """PUBLISH - application message, the heart of MQTT.

    Attributes:
        topic: Destination topic name (no wildcards allowed).
        payload: Raw application payload.
        qos: Delivery guarantee: 0 (at most once), 1 (at least once),
            2 (exactly once).
        retain: Ask the broker to keep this message for future subscribers.
        dup: Retransmission flag, set by the sender when re-delivering.
        packet_id: Required for QoS 1 and QoS 2, absent for QoS 0.
    """

    topic: str
    payload: Union[bytes, bytearray, str] = b""
    qos: int = QOS_0
    retain: bool = False
    dup: bool = False
    packet_id: Optional[int] = None

    def __post_init__(self):
        validate_qos(self.qos)
        if isinstance(self.payload, str):
            self.payload = self.payload.encode("utf-8")
        elif isinstance(self.payload, bytearray):
            self.payload = bytes(self.payload)
        elif not isinstance(self.payload, bytes):
            raise TypeError("publish payload must be bytes or str")
        if self.qos > QOS_0:
            validate_packet_id(self.packet_id)
        else:
            self.packet_id = None


@dataclass
class Puback:
    """PUBACK - QoS 1 publish acknowledgement."""

    packet_id: int = 0

    def __post_init__(self):
        validate_packet_id(self.packet_id)


@dataclass
class Pubrec:
    """PUBREC - QoS 2 publish received, first leg of the handshake."""

    packet_id: int = 0

    def __post_init__(self):
        validate_packet_id(self.packet_id)


@dataclass
class Pubrel:
    """PUBREL - QoS 2 publish release, second leg of the handshake."""

    packet_id: int = 0

    def __post_init__(self):
        validate_packet_id(self.packet_id)


@dataclass
class Pubcomp:
    """PUBCOMP - QoS 2 publish complete, final leg of the handshake."""

    packet_id: int = 0

    def __post_init__(self):
        validate_packet_id(self.packet_id)


@dataclass
class Subscribe:
    """SUBSCRIBE - subscribe to one or more topic filters.

    Attributes:
        packet_id: Identifier echoed back in the SUBACK.
        subscriptions: Sequence of ``(topic_filter, qos)`` pairs.
    """

    packet_id: int = 0
    subscriptions: List[Tuple[str, int]] = field(default_factory=list)

    def __post_init__(self):
        validate_packet_id(self.packet_id)
        normalised = []
        for topic_filter, qos in self.subscriptions:
            normalised.append((topic_filter, validate_qos(qos)))
        self.subscriptions = normalised


@dataclass
class Suback:
    """SUBACK - broker acknowledgement of a SUBSCRIBE request."""

    packet_id: int = 0
    return_codes: List[int] = field(default_factory=list)

    def __post_init__(self):
        validate_packet_id(self.packet_id)

    @property
    def granted_qos(self) -> List[int]:
        """Granted QoS for each requested subscription, ``-1`` on failure."""
        return [-1 if code == QOS_FAILURE else code for code in self.return_codes]


@dataclass
class Unsubscribe:
    """UNSUBSCRIBE - unsubscribe from one or more topic filters."""

    packet_id: int = 0
    filters: List[str] = field(default_factory=list)

    def __post_init__(self):
        validate_packet_id(self.packet_id)


@dataclass
class Unsuback:
    """UNSUBACK - broker acknowledgement of an UNSUBSCRIBE request."""

    packet_id: int = 0

    def __post_init__(self):
        validate_packet_id(self.packet_id)


@dataclass
class Pingreq:
    """PINGREQ - keep alive ping request."""


@dataclass
class Pingresp:
    """PINGRESP - keep alive ping response."""


@dataclass
class Disconnect:
    """DISCONNECT - graceful disconnection notification."""


__all__ = [
    "PacketType",
    "PACKET_NAMES",
    "REQUIRED_FLAGS",
    "QOS_0",
    "QOS_1",
    "QOS_2",
    "QOS_FAILURE",
    "QOS_NAMES",
    "CONNACK_ACCEPTED",
    "CONNACK_MESSAGES",
    "PACKET_ID_MIN",
    "PACKET_ID_MAX",
    "validate_packet_id",
    "validate_qos",
    "Will",
    "Connect",
    "Connack",
    "Publish",
    "Puback",
    "Pubrec",
    "Pubrel",
    "Pubcomp",
    "Subscribe",
    "Suback",
    "Unsubscribe",
    "Unsuback",
    "Pingreq",
    "Pingresp",
    "Disconnect",
]
