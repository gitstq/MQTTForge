"""Command line interface for MQTTForge.

Commands::

    mqttforge selftest      Run the full offline self-test suite
    mqttforge broker        Start the embedded broker
    mqttforge publish       Publish one message
    mqttforge subscribe     Subscribe and print inbound messages
    mqttforge probe         Probe broker capabilities / reachability
    mqttforge decode        Decode raw MQTT bytes (hex / base64 / file)
    mqttforge topics        Topic name & filter utilities
    mqttforge bench         Throughput benchmark against a broker

Every command works with zero external services: ``selftest`` and ``bench``
start the embedded broker when no host is supplied.
"""

import argparse
import base64
import sys
import time
from typing import List, Optional

from .broker import MiniBroker
from .client import MQTTClient
from .codec import decode_hex, decode_packets, encode_packet, encode_hex
from .errors import MQTTError
from .inspect import describe, format_packets, hexdump
from .packets import Will
from .topics import is_valid_topic_filter, topic_matches, validate_topic_filter, validate_topic_name
from .version import PROTOCOL_LEVELS, __version__

#: Symbol used for a passing self-test step.
OK = "  [PASS]"
#: Symbol used for a failing self-test step.
FAIL = "  [FAIL]"


# ----------------------------------------------------------------------
# Parser construction
# ----------------------------------------------------------------------
def _add_connection_args(parser: argparse.ArgumentParser, default_host: str = "127.0.0.1"):
    """Attach the shared connection options to a sub-command."""
    parser.add_argument("--host", default=default_host, help="broker host (default: %(default)s)")
    parser.add_argument("--port", type=int, default=1883, help="broker port (default: %(default)s)")
    parser.add_argument("--client-id", default="", help="client identifier (random when empty)")
    parser.add_argument("--username", default=None, help="user name for authentication")
    parser.add_argument("--password", default=None, help="password for authentication")
    parser.add_argument("--timeout", type=float, default=10.0, help="ack timeout in seconds")


def build_parser() -> argparse.ArgumentParser:
    """Build the fully populated argument parser."""
    parser = argparse.ArgumentParser(
        prog="mqttforge",
        description="MQTTForge - zero-dependency MQTT 3.1.1 toolkit (client, broker, codec, CLI)",
    )
    parser.add_argument("--version", action="version", version="mqttforge %s" % __version__)
    sub = parser.add_subparsers(dest="command")

    # selftest
    p_selftest = sub.add_parser("selftest", help="run the offline end-to-end self-test")
    p_selftest.add_argument("--qos", type=int, default=2, choices=[0, 1, 2],
                            help="highest QoS level to exercise (default: %(default)s)")

    # broker
    p_broker = sub.add_parser("broker", help="start the embedded MQTT broker")
    p_broker.add_argument("--host", default="127.0.0.1", help="bind address")
    p_broker.add_argument("--port", type=int, default=1883, help="bind port")

    # publish
    p_pub = sub.add_parser("publish", help="publish a single message")
    _add_connection_args(p_pub)
    p_pub.add_argument("-t", "--topic", required=True, help="topic name (no wildcards)")
    p_pub.add_argument("-m", "--message", default="", help="message payload")
    p_pub.add_argument("-q", "--qos", type=int, default=0, choices=[0, 1, 2], help="QoS level")
    p_pub.add_argument("-r", "--retain", action="store_true", help="retain the message")
    p_pub.add_argument("--will-topic", default=None, help="register a will topic")
    p_pub.add_argument("--will-message", default="", help="will message payload")
    p_pub.add_argument("--will-qos", type=int, default=0, choices=[0, 1, 2], help="will QoS")

    # subscribe
    p_sub = sub.add_parser("subscribe", help="subscribe and print inbound messages")
    _add_connection_args(p_sub)
    p_sub.add_argument("-t", "--topic", action="append", default=[],
                       help="topic filter, repeatable")
    p_sub.add_argument("-q", "--qos", type=int, default=0, choices=[0, 1, 2], help="QoS level")
    p_sub.add_argument("-n", "--count", type=int, default=0,
                       help="stop after N messages (0 = unlimited)")
    p_sub.add_argument("--duration", type=float, default=0.0,
                       help="stop after N seconds (0 = run until interrupted)")

    # probe
    p_probe = sub.add_parser("probe", help="probe broker reachability and capabilities")
    _add_connection_args(p_probe)

    # decode
    p_decode = sub.add_parser("decode", help="decode raw MQTT bytes")
    group = p_decode.add_mutually_exclusive_group(required=True)
    group.add_argument("--hex", dest="hex", default=None, help="hex string, e.g. 10 0C 00 04 ...")
    group.add_argument("--base64", dest="b64", default=None, help="base64 encoded frame")
    group.add_argument("--file", dest="file", default=None, help="file containing raw bytes")
    p_decode.add_argument("--dump", action="store_true", help="also print a hex dump")
    p_decode.add_argument("--allow-partial", action="store_true",
                          help="tolerated a truncated trailing frame")

    # topics
    p_topics = sub.add_parser("topics", help="topic name / filter utilities")
    tsub = p_topics.add_subparsers(dest="topics_command")
    p_match = tsub.add_parser("match", help="test whether a filter selects a topic name")
    p_match.add_argument("filter", help="topic filter, e.g. 'sensors/#'")
    p_match.add_argument("name", help="topic name, e.g. 'sensors/temp'")
    p_validate = tsub.add_parser("validate", help="validate a topic name or filter")
    p_validate.add_argument("topic", help="topic name or filter")
    p_validate.add_argument("--filter", action="store_true",
                            help="validate as a topic filter instead of a topic name")

    # bench
    p_bench = sub.add_parser("bench", help="throughput benchmark")
    _add_connection_args(p_bench, default_host="")
    p_bench.add_argument("-t", "--topic", default="bench/mqttforge", help="benchmark topic")
    p_bench.add_argument("-n", "--messages", type=int, default=500, help="messages to publish")
    p_bench.add_argument("-q", "--qos", type=int, default=0, choices=[0, 1, 2], help="QoS level")
    p_bench.add_argument("-s", "--size", type=int, default=128, help="payload size in bytes")

    return parser


# ----------------------------------------------------------------------
# Command implementations
# ----------------------------------------------------------------------
def _make_client(args, **extra) -> MQTTClient:
    """Build an :class:`MQTTClient` from parsed arguments."""
    will = None
    if getattr(args, "will_topic", None):
        will = Will(
            topic=args.will_topic,
            payload=args.will_message,
            qos=args.will_qos,
        )
    return MQTTClient(
        client_id=getattr(args, "client_id", "") or "",
        username=getattr(args, "username", None),
        password=getattr(args, "password", None),
        will=will,
        timeout=getattr(args, "timeout", 10.0),
        **extra
    )


def cmd_selftest(args) -> int:
    """Run the offline end-to-end self-test suite."""
    results: List[tuple] = []
    broker = MiniBroker(host="127.0.0.1", port=0)
    broker.start()
    host, port = broker.host, broker.port
    print("MQTTForge self-test (embedded broker on %s:%d)" % (host, port))
    print("Python %s" % sys.version.split()[0])

    def check(label: str, fn):
        try:
            detail = fn()
            results.append((True, label, detail))
            print("%s %s%s" % (OK, label, " - %s" % detail if detail else ""))
        except Exception as exc:  # noqa: BLE001 - self-test reports everything
            results.append((False, label, "%s: %s" % (type(exc).__name__, exc)))
            print("%s %s - %s: %s" % (FAIL, label, type(exc).__name__, exc))

    max_qos = args.qos

    def _connect():
        client = MQTTClient(client_id="selftest", timeout=5.0)
        client.connect(host, port, timeout=5.0)
        return client

    client = None
    try:
        def t_connect():
            nonlocal client
            client = _connect()
            return "client id=%s" % client.client_id

        check("CONNECT / CONNACK handshake", t_connect)

        def t_subscribe():
            granted = client.subscribe([("selftest/#", max_qos)])
            assert granted == [max_qos], "granted %r" % (granted,)
            return "granted qos=%d" % granted[0]

        check("SUBSCRIBE / SUBACK", t_subscribe)

        def t_qos0():
            client.publish("selftest/qos0", b"hello-qos0", qos=0)
            msg = client.wait_for_message(timeout=3.0)
            assert msg is not None, "no message received"
            assert msg.payload == b"hello-qos0", msg.payload
            return "%d bytes" % len(msg.payload)

        check("PUBLISH qos0 (at most once)", t_qos0)

        if max_qos >= 1:
            def t_qos1():
                client.publish("selftest/qos1", b"hello-qos1", qos=1)
                msg = client.wait_for_message(timeout=3.0)
                assert msg is not None and msg.payload == b"hello-qos1", msg
                return "%d bytes" % len(msg.payload)

            check("PUBLISH qos1 (PUBACK handshake)", t_qos1)

        if max_qos >= 2:
            def t_qos2():
                client.publish("selftest/qos2", b"hello-qos2", qos=2)
                msg = client.wait_for_message(timeout=3.0)
                assert msg is not None and msg.payload == b"hello-qos2", msg
                return "%d bytes" % len(msg.payload)

            check("PUBLISH qos2 (PUBREC/PUBREL/PUBCOMP)", t_qos2)

        def t_wildcard():
            client.publish("selftest/deep/nested/topic", b"wild", qos=0)
            msg = client.wait_for_message(timeout=3.0)
            assert msg is not None and msg.topic == "selftest/deep/nested/topic", msg
            return msg.topic

        check("topic wildcard '#' fan-out", t_wildcard)

        def t_ping():
            rtt = client.ping(timeout=3.0)
            return "rtt=%.2f ms" % rtt

        check("PINGREQ / PINGRESP", t_ping)

        def t_retain():
            client.publish("selftest/retained", b"kept", qos=0, retain=True)
            time.sleep(0.15)
            reader = MQTTClient(client_id="selftest-retain", timeout=5.0)
            reader.connect(host, port, timeout=5.0)
            reader.subscribe([("selftest/retained", 1)])
            msg = reader.wait_for_message(timeout=3.0)
            assert msg is not None and msg.payload == b"kept", msg
            reader.disconnect()
            return "replayed %r" % msg.payload

        check("retained message replay", t_retain)

        def t_unsubscribe():
            client.unsubscribe(["selftest/#"])
            return "filter removed"

        check("UNSUBSCRIBE / UNSUBACK", t_unsubscribe)

        def t_codec():
            from .packets import Connect, Publish, Subscribe

            frame = encode_packet(
                Publish(topic="codec/round/trip", payload=b"x" * 300, qos=1, packet_id=7)
            )
            packets, leftover = decode_packets(frame)
            assert len(packets) == 1, packets
            assert leftover == b"", leftover
            restored = packets[0]
            assert restored.topic == "codec/round/trip", restored.topic
            assert len(restored.payload) == 300
            assert restored.packet_id == 7
            return "300-byte payload, 4-byte length prefix verified"

        check("codec round-trip (multi-byte length)", t_codec)

        def t_disconnect():
            client.disconnect()
            return "graceful"

        check("DISCONNECT", t_disconnect)
    finally:
        broker.shutdown()

    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    print("\n%d/%d checks passed" % (passed, total))
    return 0 if passed == total else 1


def cmd_broker(args) -> int:
    """Start the embedded broker and serve until interrupted."""
    broker = MiniBroker(host=args.host, port=args.port)
    broker.start()
    print("MQTTForge broker listening on %s:%d" % (broker.host, broker.port))
    print("Press Ctrl+C to stop.")
    try:
        broker.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down ...")
    finally:
        broker.shutdown()
    return 0


def cmd_publish(args) -> int:
    """Publish a single message."""
    validate_topic_name(args.topic)
    client = _make_client(args)
    try:
        client.connect(args.host, args.port, timeout=args.timeout)
        client.publish(args.topic, args.message.encode("utf-8"), qos=args.qos, retain=args.retain)
    finally:
        client.disconnect()
    print("published %d bytes to '%s' (qos=%d, retain=%s)"
          % (len(args.message.encode("utf-8")), args.topic, args.qos, args.retain))
    return 0


def cmd_subscribe(args) -> int:
    """Subscribe to one or more filters and print inbound messages."""
    filters = args.topic or ["#"]
    for topic_filter in filters:
        validate_topic_filter(topic_filter)
    client = _make_client(args)
    received = 0
    try:
        client.connect(args.host, args.port, timeout=args.timeout)
        granted = client.subscribe([(f, args.qos) for f in filters])
        for topic_filter, qos in zip(filters, granted):
            print("subscribed to '%s' (granted qos=%d)" % (topic_filter, qos))
        deadline = time.monotonic() + args.duration if args.duration > 0 else None
        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                message = client.wait_for_message(timeout=remaining)
            else:
                message = client.wait_for_message(timeout=1.0)
            if message is None:
                if deadline is not None:
                    break
                continue
            received += 1
            payload = message.payload.decode("utf-8", "replace")
            print("[%s] qos=%d retain=%s %s" % (message.topic, message.qos,
                                                message.retain, payload))
            if args.count and received >= args.count:
                break
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        client.disconnect()
    print("received %d message(s)" % received)
    return 0


def cmd_probe(args) -> int:
    """Probe broker reachability and report the connection result."""
    client = _make_client(args)
    started = time.monotonic()
    try:
        client.connect(args.host, args.port, timeout=args.timeout)
        elapsed = (time.monotonic() - started) * 1000.0
        rtt = client.ping(timeout=args.timeout)
        print("host            : %s:%d" % (args.host, args.port))
        print("status          : ONLINE")
        print("connect time    : %.2f ms" % elapsed)
        print("ping round trip : %.2f ms" % rtt)
        print("protocol        : MQTT %s" % PROTOCOL_LEVELS.get(4, "3.1.1"))
        print("client id       : %s" % client.client_id)
    except (MQTTError, OSError) as exc:
        print("host   : %s:%d" % (args.host, args.port))
        print("status : OFFLINE - %s: %s" % (type(exc).__name__, exc))
        return 1
    finally:
        client.disconnect()
    return 0


def cmd_decode(args) -> int:
    """Decode a raw MQTT frame supplied as hex, base64 or a file."""
    try:
        if args.hex is not None:
            raw = decode_hex(args.hex)
        elif args.b64 is not None:
            try:
                raw = base64.b64decode(args.b64, validate=False)
            except Exception as exc:  # noqa: BLE001
                raise MQTTError("invalid base64 input: %s" % exc) from exc
        else:
            try:
                with open(args.file, "rb") as handle:
                    raw = handle.read()
            except OSError as exc:
                raise MQTTError("cannot read file: %s" % exc) from exc
        packets, leftover = decode_packets(raw, allow_partial=args.allow_partial)
    except MQTTError as exc:
        print("decode error: %s" % exc)
        return 1

    if not packets:
        print("no complete MQTT frame found in %d byte(s)" % len(raw))
        return 1
    print("input: %d byte(s), %d frame(s)" % (len(raw), len(packets)))
    print(format_packets(packets))
    if args.dump:
        print("\nhex dump:")
        print(hexdump(raw))
    if leftover:
        print("\ntruncated trailing bytes (%d): %s" % (len(leftover), encode_hex(leftover)))
    return 0


def cmd_topics(args) -> int:
    """Topic name and topic filter utilities."""
    if args.topics_command == "match":
        matched = topic_matches(args.filter, args.name)
        print("filter : %s" % args.filter)
        print("topic  : %s" % args.name)
        print("match  : %s" % matched)
        return 0 if matched else 1
    if args.topics_command == "validate":
        try:
            if args.filter:
                validate_topic_filter(args.topic)
                kind = "topic filter"
            else:
                validate_topic_name(args.topic)
                kind = "topic name"
        except MQTTError as exc:
            print("topic  : %s" % args.topic)
            print("valid  : False")
            print("reason : %s" % exc)
            return 1
        print("topic  : %s" % args.topic)
        print("kind   : %s" % kind)
        print("valid  : True")
        return 0
    print("usage: mqttforge topics {match,validate}")
    return 1


def cmd_bench(args) -> int:
    """Measure publish throughput against an embedded or remote broker."""
    broker = None
    host, port = args.host, args.port
    if not host:
        broker = MiniBroker(host="127.0.0.1", port=0)
        broker.start()
        host, port = broker.host, broker.port
        print("using embedded broker on %s:%d" % (host, port))

    payload = b"x" * max(0, args.size)
    received = {"count": 0}
    try:
        subscriber = MQTTClient(client_id="bench-sub", timeout=args.timeout)
        subscriber.connect(host, port, timeout=args.timeout)
        subscriber.subscribe([("#", min(args.qos, 2))])

        publisher = MQTTClient(client_id="bench-pub", timeout=args.timeout)
        publisher.connect(host, port, timeout=args.timeout)

        started = time.monotonic()
        for index in range(args.messages):
            publisher.publish(args.topic, payload, qos=args.qos)
        elapsed = time.monotonic() - started

        # Drain whatever the broker has already queued for the subscriber.
        stop_at = time.monotonic() + 2.0
        while received["count"] < args.messages and time.monotonic() < stop_at:
            if subscriber.wait_for_message(timeout=0.2) is not None:
                received["count"] += 1

        rate = args.messages / elapsed if elapsed > 0 else float("inf")
        print("messages     : %d" % args.messages)
        print("qos          : %d" % args.qos)
        print("payload size : %d bytes" % len(payload))
        print("elapsed      : %.3f s" % elapsed)
        print("throughput   : %.1f msg/s" % rate)
        print("received     : %d" % received["count"])
        subscriber.disconnect()
        publisher.disconnect()
    finally:
        if broker is not None:
            broker.shutdown()
    return 0


#: Mapping of sub-command name to handler function.
COMMANDS = {
    "selftest": cmd_selftest,
    "broker": cmd_broker,
    "publish": cmd_publish,
    "subscribe": cmd_subscribe,
    "probe": cmd_probe,
    "decode": cmd_decode,
    "topics": cmd_topics,
    "bench": cmd_bench,
}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector; ``None`` reads ``sys.argv[1:]``.

    Returns:
        Process exit code: ``0`` on success, non-zero on failure.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    handler = COMMANDS[args.command]
    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130
    except MQTTError as exc:
        print("error: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


__all__ = ["main", "build_parser"]
