"""MQTTForge - a zero-dependency MQTT 3.1.1 toolkit for Python.

The package ships four building blocks that can be used independently:

* :mod:`mqttforge.codec`   - pure byte level encode/decode of every control packet
* :mod:`mqttforge.client`  - blocking MQTT 3.1.1 client with QoS 0/1/2 support
* :mod:`mqttforge.broker`  - embedded broker for offline testing and local dev
* :mod:`mqttforge.topics`  - topic name validation and wildcard matching

Quick start::

    from mqttforge import MQTTClient, MiniBroker

    broker = MiniBroker()
    host, port = broker.start_background()

    with MQTTClient(client_id="demo") as client:
        client.connect(host, port)
        client.subscribe([("sensors/#", 1)])
        client.publish("sensors/temp", b"21.5", qos=1)
        print(client.wait_for_message(timeout=2).payload)

    broker.shutdown()

CLI equivalent::

    $ mqttforge selftest
    $ mqttforge broker --port 1883
    $ mqttforge subscribe --host 127.0.0.1 -t "sensors/#"
    $ mqttforge publish --host 127.0.0.1 -t sensors/temp -m 21.5 -q 1
"""

from . import codec, inspect, packets, topics
from .broker import MiniBroker
from .client import MQTTClient
from .codec import decode_one, decode_packets, encode_packet
from .errors import (
    CodecError,
    ConnectRefused,
    MQTTError,
    ProtocolError,
    TopicError,
)
from .packets import (
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
from .topics import (
    is_valid_topic_filter,
    is_valid_topic_name,
    topic_matches,
    validate_topic_filter,
    validate_topic_name,
)
from .version import PROTOCOL_LEVEL, PROTOCOL_NAME, __version__

__all__ = [
    # high level building blocks
    "MQTTClient",
    "MiniBroker",
    # sub modules
    "codec",
    "inspect",
    "packets",
    "topics",
    # codec helpers
    "encode_packet",
    "decode_packets",
    "decode_one",
    # packet model
    "PacketType",
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
    "Will",
    # topic helpers
    "topic_matches",
    "validate_topic_name",
    "validate_topic_filter",
    "is_valid_topic_name",
    "is_valid_topic_filter",
    # errors
    "MQTTError",
    "CodecError",
    "TopicError",
    "ProtocolError",
    "ConnectRefused",
    # metadata
    "__version__",
    "PROTOCOL_NAME",
    "PROTOCOL_LEVEL",
]
