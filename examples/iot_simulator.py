"""Simulate a small IoT fleet against the embedded broker.

Run it with::

    python examples/iot_simulator.py

Demonstrates the pattern MQTTForge was built for: spin up a broker in-process,
have several "devices" publish telemetry at different QoS levels, and let one
"collector" aggregate everything with a single wildcard subscription.
"""

from __future__ import print_function

import json
import os
import random
import sys
import time

# Allow running straight from a source checkout.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mqttforge import MQTTClient, MiniBroker
from mqttforge.packets import Will

DEVICES = [
    ("thermostat", "living-room", 1),
    ("thermostat", "bedroom", 1),
    ("meter", "mains", 2),
    ("camera", "front-door", 0),
]


def main():
    broker = MiniBroker(host="127.0.0.1", port=0)
    host, port = broker.start_background()
    print("fleet broker on %s:%d" % (host, port))

    # One collector subscribes to the whole fleet with a single filter.
    collector = MQTTClient(client_id="collector", timeout=5.0)
    collector.connect(host, port, timeout=5.0)
    collector.subscribe([("fleet/#", 2)])

    # Each device announces a will so the collector notices a crash.
    devices = []
    for kind, room, qos in DEVICES:
        client = MQTTClient(
            client_id="dev-%s-%s" % (kind, room),
            will=Will(
                topic="fleet/%s/%s/status" % (kind, room),
                payload=b"offline",
                qos=1,
                retain=True,
            ),
            timeout=5.0,
        )
        client.connect(host, port, timeout=5.0)
        devices.append((kind, room, qos, client))

    for round_index in range(3):
        for kind, room, qos, client in devices:
            payload = json.dumps(
                {
                    "kind": kind,
                    "room": room,
                    "round": round_index,
                    "value": round(random.uniform(18.0, 26.0), 2),
                    "ts": int(time.time()),
                }
            ).encode("utf-8")
            client.publish("fleet/%s/%s/telemetry" % (kind, room), payload, qos=qos)

        # Drain everything the collector received for this round.
        seen = 0
        while seen < len(devices):
            message = collector.wait_for_message(timeout=5.0)
            if message is None:
                break
            seen += 1
            data = json.loads(message.payload.decode("utf-8"))
            print(
                "round %d  %-12s %-12s qos=%d  %5.2f"
                % (round_index, data["kind"], data["room"], message.qos, data["value"])
            )
        time.sleep(0.2)

    print("broker stats: %s" % broker.stats)
    for _, _, _, client in devices:
        client.disconnect()
    collector.disconnect()
    broker.shutdown()


if __name__ == "__main__":
    main()
