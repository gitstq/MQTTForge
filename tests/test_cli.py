"""Tests for the command line interface (subprocess driven)."""

import os
import subprocess
import sys
import unittest

from mqttforge.broker import MiniBroker
from mqttforge.codec import encode_hex, encode_packet
from mqttforge.packets import Connect, Publish

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(args, timeout: int = 90):
    """Run ``python -m mqttforge <args>`` and return the completed process."""
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "mqttforge"] + args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestBasicCommands(unittest.TestCase):
    """Commands that need no broker."""

    def test_version(self):
        result = run_cli(["--version"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("mqttforge", result.stdout)

    def test_no_command_prints_help(self):
        result = run_cli([])
        self.assertEqual(result.returncode, 1)
        self.assertIn("usage", result.stdout.lower())

    def test_topics_match_true(self):
        result = run_cli(["topics", "match", "sensors/#", "sensors/temp"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("True", result.stdout)

    def test_topics_match_false(self):
        result = run_cli(["topics", "match", "sensors/+", "sensors/temp/deep"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("False", result.stdout)

    def test_topics_validate_name(self):
        result = run_cli(["topics", "validate", "sensors/temp"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("topic name", result.stdout)

    def test_topics_validate_rejects_wildcard_in_name(self):
        result = run_cli(["topics", "validate", "sensors/+"])
        self.assertEqual(result.returncode, 1)

    def test_topics_validate_filter_accepts_wildcard(self):
        result = run_cli(["topics", "validate", "sensors/+", "--filter"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("topic filter", result.stdout)


class TestDecodeCommand(unittest.TestCase):
    """Offline packet forensics."""

    def test_decode_hex(self):
        raw = encode_packet(
            Publish(topic="cli/test", payload=b"hello", qos=1, packet_id=12)
        )
        result = run_cli(["decode", "--hex", encode_hex(raw)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("PUBLISH", result.stdout)
        self.assertIn("cli/test", result.stdout)
        self.assertIn("12", result.stdout)

    def test_decode_with_dump(self):
        raw = encode_packet(Connect(client_id="abc", keepalive=60))
        result = run_cli(["decode", "--hex", raw.hex(), "--dump"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("CONNECT", result.stdout)
        self.assertIn("hex dump", result.stdout)

    def test_decode_multiple_frames(self):
        raw = encode_packet(Connect(client_id="abc")) + encode_packet(
            Publish(topic="a", payload=b"b")
        )
        result = run_cli(["decode", "--hex", raw.hex()])
        self.assertIn("2 frame(s)", result.stdout)

    def test_decode_invalid_hex(self):
        result = run_cli(["decode", "--hex", "zzzz"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("decode error", result.stdout)


class TestSelftest(unittest.TestCase):
    """The built-in self-test must pass end to end."""

    def test_selftest_passes(self):
        result = run_cli(["selftest"], timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("11/11", result.stdout)

    def test_selftest_qos0_only(self):
        result = run_cli(["selftest", "--qos", "0"], timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("checks passed", result.stdout)


class TestBench(unittest.TestCase):
    """Throughput benchmark against the embedded broker."""

    def test_bench_embedded(self):
        result = run_cli(
            ["bench", "-n", "20", "-q", "1", "-s", "32"], timeout=120
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("throughput", result.stdout)
        self.assertIn("messages     : 20", result.stdout)


class TestNetworkCommands(unittest.TestCase):
    """publish / subscribe / probe against a live embedded broker."""

    def setUp(self):
        self.broker = MiniBroker(host="127.0.0.1", port=0)
        self.broker.start()
        self.addCleanup(self.broker.shutdown)

    def test_probe(self):
        result = run_cli(
            ["probe", "--host", self.broker.host, "--port", str(self.broker.port)]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ONLINE", result.stdout)

    def test_probe_offline(self):
        # Port 1 is reserved and nothing listens there.
        result = run_cli(["probe", "--host", "127.0.0.1", "--port", "1", "--timeout", "3"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("OFFLINE", result.stdout)

    def test_publish_then_subscribe(self):
        host, port = self.broker.host, str(self.broker.port)
        published = run_cli(
            ["publish", "--host", host, "--port", port, "-t", "cli/demo",
             "-m", "hello-cli", "-q", "1"]
        )
        self.assertEqual(published.returncode, 0, published.stdout + published.stderr)
        self.assertIn("published", published.stdout)

        # The message above is gone, so subscribe and publish concurrently.
        import threading
        import time

        def delayed_publish():
            time.sleep(1.5)
            run_cli(
                ["publish", "--host", host, "--port", port, "-t", "cli/demo",
                 "-m", "delayed", "-q", "0"]
            )

        thread = threading.Thread(target=delayed_publish, daemon=True)
        thread.start()
        result = run_cli(
            ["subscribe", "--host", host, "--port", port, "-t", "cli/#",
             "-n", "1", "--duration", "15"],
            timeout=60,
        )
        thread.join(timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("delayed", result.stdout)
        self.assertIn("received 1 message(s)", result.stdout)


if __name__ == "__main__":
    unittest.main()
