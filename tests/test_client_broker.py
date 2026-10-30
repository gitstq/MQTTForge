"""End-to-end tests: client + embedded broker over a real loopback socket.

These tests are fully offline - the embedded broker removes any dependency on
an external MQTT server such as Mosquitto.
"""

import socket
import threading
import unittest

from mqttforge.broker import MiniBroker
from mqttforge.client import MQTTClient
from mqttforge.errors import ConnectRefused
from mqttforge.packets import Will


class BrokerTestCase(unittest.TestCase):
    """Shared fixture: a fresh embedded broker per test."""

    def setUp(self):
        self.broker = MiniBroker(host="127.0.0.1", port=0)
        self.broker.start()
        self.host, self.port = self.broker.host, self.broker.port

    def tearDown(self):
        self.broker.shutdown()

    def client(self, **kwargs) -> MQTTClient:
        """Create and connect a client bound to the embedded broker."""
        kwargs.setdefault("timeout", 5.0)
        client = MQTTClient(**kwargs)
        client.connect(self.host, self.port, timeout=5.0)
        self.addCleanup(client.disconnect)
        return client


class TestConnection(BrokerTestCase):
    """CONNECT / CONNACK / DISCONNECT behaviour."""

    def test_connect_and_disconnect(self):
        client = self.client(client_id="c1")
        self.assertTrue(client.connected)
        self.assertEqual(client.client_id, "c1")
        self.assertEqual(self.broker.subscriber_count(), 1)
        client.disconnect()
        self.assertFalse(client.connected)

    def test_random_client_id(self):
        client = self.client()
        self.assertTrue(client.client_id.startswith("mqttforge-"))

    def test_context_manager(self):
        with MQTTClient(client_id="ctx", timeout=5.0) as client:
            client.connect(self.host, self.port, timeout=5.0)
            self.assertTrue(client.connected)

    def test_broker_stop_alias_and_context_manager(self):
        """``start()``/``stop()`` and the ``with`` form must both work."""
        broker = MiniBroker(host="127.0.0.1", port=0)
        broker.start_background()
        broker.stop()                      # alias of shutdown()
        self.assertEqual(broker.sessions, {})

        with MiniBroker(host="127.0.0.1", port=0) as second:
            client = MQTTClient(client_id="cm", timeout=5.0)
            client.connect(second.host, second.port, timeout=5.0)
            self.assertTrue(client.connected)
            client.disconnect()
        self.assertIsNone(second._sock)

    def test_ping(self):
        client = self.client(client_id="ping")
        rtt = client.ping(timeout=5.0)
        self.assertGreaterEqual(rtt, 0.0)

    def test_connection_refused(self):
        """A broker that answers with return code 5 must raise ConnectRefused."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def serve():
            conn, _ = server.accept()
            try:
                conn.recv(4096)  # swallow the CONNECT frame
                conn.sendall(b"\x20\x02\x00\x05")  # CONNACK, not authorized
            finally:
                conn.close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            client = MQTTClient(client_id="rejected", timeout=5.0)
            with self.assertRaises(ConnectRefused) as ctx:
                client.connect("127.0.0.1", port, timeout=5.0)
            self.assertEqual(ctx.exception.return_code, 5)
        finally:
            server.close()


class TestSubscribePublish(BrokerTestCase):
    """QoS 0/1/2 delivery and subscription handling."""

    def test_qos0(self):
        client = self.client(client_id="q0")
        self.assertEqual(client.subscribe([("t/q0", 0)]), [0])
        client.publish("t/q0", b"payload-0", qos=0)
        message = client.wait_for_message(timeout=5.0)
        self.assertIsNotNone(message)
        self.assertEqual(message.topic, "t/q0")
        self.assertEqual(message.payload, b"payload-0")
        self.assertEqual(message.qos, 0)

    def test_qos1(self):
        client = self.client(client_id="q1")
        self.assertEqual(client.subscribe([("t/q1", 1)]), [1])
        client.publish("t/q1", b"payload-1", qos=1)
        message = client.wait_for_message(timeout=5.0)
        self.assertIsNotNone(message)
        self.assertEqual(message.payload, b"payload-1")
        self.assertEqual(message.qos, 1)

    def test_qos2_delivered_exactly_once(self):
        client = self.client(client_id="q2")
        self.assertEqual(client.subscribe([("t/q2", 2)]), [2])
        client.publish("t/q2", b"payload-2", qos=2)
        message = client.wait_for_message(timeout=5.0)
        self.assertIsNotNone(message)
        self.assertEqual(message.payload, b"payload-2")
        # Exactly once: nothing else must arrive.
        self.assertIsNone(client.wait_for_message(timeout=0.6))

    def test_string_payload(self):
        client = self.client(client_id="str")
        client.subscribe([("t/str", 0)])
        client.publish("t/str", "hello world", qos=0)
        message = client.wait_for_message(timeout=5.0)
        self.assertEqual(message.payload, b"hello world")

    def test_subscribe_with_string(self):
        client = self.client(client_id="single")
        self.assertEqual(client.subscribe("t/single", qos=1), [1])

    def test_subscribe_with_dict(self):
        client = self.client(client_id="dict")
        self.assertEqual(client.subscribe({"a/#": 0, "b/#": 1}), [0, 1])

    def test_invalid_topic_on_publish(self):
        from mqttforge.errors import TopicError

        client = self.client(client_id="bad")
        with self.assertRaises(TopicError):
            client.publish("invalid/#", b"nope")

    def test_granted_qos_capped_by_broker(self):
        broker = MiniBroker(host="127.0.0.1", port=0, max_qos=1)
        broker.start()
        self.addCleanup(broker.shutdown)
        client = MQTTClient(client_id="cap", timeout=5.0)
        client.connect(broker.host, broker.port, timeout=5.0)
        self.addCleanup(client.disconnect)
        self.assertEqual(client.subscribe([("t/cap", 2)]), [1])


class TestFanOut(BrokerTestCase):
    """Wildcard routing between multiple clients."""

    def test_two_subscribers(self):
        wide = self.client(client_id="wide")
        narrow = self.client(client_id="narrow")
        wide.subscribe([("sensors/#", 0)])
        narrow.subscribe([("sensors/temp", 0)])

        publisher = self.client(client_id="pub")
        publisher.publish("sensors/temp", b"21.5", qos=0)

        self.assertEqual(wide.wait_for_message(timeout=5.0).payload, b"21.5")
        self.assertEqual(narrow.wait_for_message(timeout=5.0).payload, b"21.5")

    def test_non_matching_filter_is_not_delivered(self):
        client = self.client(client_id="filtered")
        client.subscribe([("sensors/humidity", 0)])
        publisher = self.client(client_id="pub2")
        publisher.publish("sensors/temp", b"nope", qos=0)
        self.assertIsNone(client.wait_for_message(timeout=0.6))

    def test_single_level_wildcard(self):
        client = self.client(client_id="plus")
        client.subscribe([("room/+/temp", 0)])
        publisher = self.client(client_id="pub3")
        publisher.publish("room/kitchen/temp", b"ok", qos=0)
        publisher.publish("room/kitchen/humidity", b"ignored", qos=0)
        message = client.wait_for_message(timeout=5.0)
        self.assertEqual(message.topic, "room/kitchen/temp")

    def test_broker_side_publish(self):
        client = self.client(client_id="injected")
        client.subscribe([("server/announce", 0)])
        self.broker.publish("server/announce", b"from-broker", qos=0)
        self.assertEqual(client.wait_for_message(timeout=5.0).payload, b"from-broker")

    def test_broker_stats(self):
        client = self.client(client_id="stats")
        client.subscribe([("stats/#", 0)])
        client.publish("stats/x", b"1", qos=0)
        client.wait_for_message(timeout=5.0)
        self.assertGreaterEqual(self.broker.stats["published"], 1)
        self.assertGreaterEqual(self.broker.stats["delivered"], 1)


class TestRetained(BrokerTestCase):
    """Retained message semantics."""

    def test_retained_is_replayed_to_new_subscriber(self):
        # QoS 1 so the broker has stored the value before publish() returns.
        publisher = self.client(client_id="retain-pub")
        publisher.publish("cfg/interval", b"30", qos=1, retain=True)
        self.assertEqual(self.broker.stats["retained"], 1)

        reader = self.client(client_id="retain-sub")
        reader.subscribe([("cfg/#", 1)])
        message = reader.wait_for_message(timeout=5.0)
        self.assertIsNotNone(message)
        self.assertEqual(message.payload, b"30")

    def test_empty_payload_clears_retained(self):
        # QoS 1 is used so the broker has certainly processed each publish
        # (it stores the retained value before sending PUBACK).
        publisher = self.client(client_id="clear-pub")
        publisher.publish("cfg/interval", b"30", qos=1, retain=True)
        self.assertEqual(self.broker.stats["retained"], 1)
        publisher.publish("cfg/interval", b"", qos=1, retain=True)
        self.assertEqual(self.broker.stats["retained"], 0)

        reader = self.client(client_id="clear-sub")
        reader.subscribe([("cfg/#", 0)])
        self.assertIsNone(reader.wait_for_message(timeout=0.6))

    def test_retained_survives_new_connection(self):
        first = self.client(client_id="first-gen")
        first.publish("device/version", b"1.0.0", qos=1, retain=True)
        first.disconnect()

        second = self.client(client_id="second-gen")
        second.subscribe([("device/version", 0)])
        self.assertEqual(second.wait_for_message(timeout=5.0).payload, b"1.0.0")


class TestUnsubscribe(BrokerTestCase):
    """UNSUBSCRIBE stops further delivery."""

    def test_unsubscribe(self):
        client = self.client(client_id="unsub")
        client.subscribe([("stop/#", 0)])
        client.unsubscribe(["stop/#"])
        publisher = self.client(client_id="pub4")
        publisher.publish("stop/me", b"too late", qos=0)
        self.assertIsNone(client.wait_for_message(timeout=0.6))

    def test_partial_unsubscribe(self):
        client = self.client(client_id="partial")
        client.subscribe([("keep/#", 0), ("drop/#", 0)])
        client.unsubscribe(["drop/#"])
        publisher = self.client(client_id="pub5")
        publisher.publish("drop/x", b"ignored", qos=0)
        publisher.publish("keep/x", b"delivered", qos=0)
        self.assertEqual(client.wait_for_message(timeout=5.0).payload, b"delivered")


class TestWill(BrokerTestCase):
    """Last Will and Testament handling."""

    def test_will_published_on_abrupt_disconnect(self):
        watcher = self.client(client_id="watcher")
        watcher.subscribe([("devices/#", 1)])

        dying = MQTTClient(
            client_id="dying",
            will=Will(topic="devices/dying/status", payload=b"offline", qos=1),
            timeout=5.0,
        )
        dying.connect(self.host, self.port, timeout=5.0)
        # Simulate a crash: drop the TCP connection without sending DISCONNECT.
        # shutdown() is required because a bare close() does not emit FIN while
        # the client's receiver thread is still blocked in recv() on Linux.
        dying._sock.shutdown(socket.SHUT_RDWR)
        dying._sock.close()

        message = watcher.wait_for_message(timeout=5.0)
        self.assertIsNotNone(message)
        self.assertEqual(message.topic, "devices/dying/status")
        self.assertEqual(message.payload, b"offline")

    def test_will_not_published_on_graceful_disconnect(self):
        watcher = self.client(client_id="watcher2")
        watcher.subscribe([("polite/#", 1)])

        polite = MQTTClient(
            client_id="polite",
            will=Will(topic="polite/status", payload=b"offline", qos=1),
            timeout=5.0,
        )
        polite.connect(self.host, self.port, timeout=5.0)
        polite.disconnect()

        self.assertIsNone(watcher.wait_for_message(timeout=0.8))


if __name__ == "__main__":
    unittest.main()
