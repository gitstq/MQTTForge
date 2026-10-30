"""Offline MQTT packet forensics - decode frames without touching a network.

Run it with::

    python examples/packet_forensics.py

Useful when you have captured bytes from ``tcpdump -X``, a Wireshark export or
an IoT device log and want a readable breakdown.
"""

from __future__ import print_function

import os
import sys

# Allow running straight from a source checkout.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mqttforge.codec import decode_hex, decode_packets, encode_hex, encode_packet
from mqttforge.inspect import format_packets, hexdump
from mqttforge.packets import Connect, Publish, Subscribe, Will


def main():
    # Build a few representative frames, then decode them back.
    frames = [
        Connect(
            client_id="device-007",
            keepalive=60,
            username="fleet",
            password="hunter2",
            will=Will(topic="device/007/status", payload=b"offline", qos=1, retain=True),
        ),
        Subscribe(packet_id=11, subscriptions=[("device/+/telemetry", 1)]),
        Publish(topic="device/007/telemetry", payload=b'{"temp": 24.5}', qos=1, packet_id=12),
    ]

    stream = b"".join(encode_packet(frame) for frame in frames)
    print("== captured stream (%d bytes) ==" % len(stream))
    print(hexdump(stream))
    print()

    packets, leftover = decode_packets(stream)
    print("== decoded %d frame(s), %d leftover byte(s) ==" % (len(packets), len(leftover)))
    print(format_packets(packets))
    print()

    # The same works on hex pasted straight from a terminal.
    hex_text = encode_hex(encode_packet(Publish(topic="t", payload=b"hi", qos=0)))
    print("== decoding hex: %s ==" % hex_text)
    decoded, _ = decode_packets(decode_hex(hex_text))
    print(format_packets(decoded))


if __name__ == "__main__":
    main()
