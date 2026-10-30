"""MQTTForge quick start - everything in one file, no external broker needed.

Run it with::

    python examples/quickstart.py

The script starts the embedded broker, connects a client, exercises QoS 0/1/2,
a wildcard subscription and a retained message, then shuts everything down.
"""

from __future__ import print_function

import os
import sys

# Allow running straight from a source checkout: `python examples/quickstart.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mqttforge import MQTTClient, MiniBroker
from mqttforge.packets import Will


def main():
    # 1. Start a throwaway broker on a free ephemeral port.
    broker = MiniBroker(host="127.0.0.1", port=0)
    host, port = broker.start_background()
    print("broker listening on %s:%d" % (host, port))

    # 2. Connect a subscriber with a last-will message.
    subscriber = MQTTClient(
        client_id="quickstart-sub",
        will=Will(topic="quickstart/status", payload=b"sub-gone", qos=1),
        timeout=5.0,
    )
    subscriber.connect(host, port, timeout=5.0)

    # One subscription covers every topic below "quickstart/".
    granted = subscriber.subscribe([("quickstart/#", 2)])
    print("subscribed to 'quickstart/#' -> granted QoS %s" % granted)

    # 3. Publish at each QoS level from a second client.
    publisher = MQTTClient(client_id="quickstart-pub", timeout=5.0)
    publisher.connect(host, port, timeout=5.0)

    for qos in (0, 1, 2):
        topic = "quickstart/qos%d" % qos
        payload = ("message at QoS %d" % qos).encode("utf-8")
        publisher.publish(topic, payload, qos=qos)
        message = subscriber.wait_for_message(timeout=5.0)
        print("received %-18s qos=%d payload=%r" % (message.topic, message.qos, message.payload))

    # 4. Retained messages are replayed to subscribers that arrive later.
    publisher.publish("quickstart/config", b'{"interval": 30}', qos=1, retain=True)
    late = MQTTClient(client_id="quickstart-late", timeout=5.0)
    late.connect(host, port, timeout=5.0)
    late.subscribe([("quickstart/config", 1)])
    replayed = late.wait_for_message(timeout=5.0)
    print("late subscriber instantly received retained value: %r" % replayed.payload)

    # 5. Measure the round trip time.
    print("ping rtt: %.2f ms" % publisher.ping(timeout=5.0))

    # 6. Clean up.
    late.disconnect()
    publisher.disconnect()
    subscriber.disconnect()
    print("broker stats: %s" % broker.stats)
    broker.shutdown()


if __name__ == "__main__":
    main()
