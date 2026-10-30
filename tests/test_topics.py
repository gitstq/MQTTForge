"""Unit tests for topic name / topic filter handling (MQTT-4.7)."""

import unittest

from mqttforge.errors import TopicError
from mqttforge.topics import (
    common_prefix_depth,
    is_valid_topic_filter,
    is_valid_topic_name,
    topic_levels,
    topic_matches,
    validate_topic_filter,
    validate_topic_name,
)


class TestValidateTopicName(unittest.TestCase):
    """Topic names are used when publishing and must not contain wildcards."""

    def test_valid(self):
        for topic in ("a", "a/b", "/a", "a/", "sensors/42/temp", "$SYS/broker/uptime",
                      "温度/传感器"):
            self.assertTrue(is_valid_topic_name(topic), topic)

    def test_empty(self):
        with self.assertRaises(TopicError):
            validate_topic_name("")

    def test_wildcards_rejected(self):
        for topic in ("sensors/+", "sensors/#", "#", "+"):
            with self.assertRaises(TopicError):
                validate_topic_name(topic)

    def test_null_character_rejected(self):
        with self.assertRaises(TopicError):
            validate_topic_name("a\x00b")

    def test_too_long(self):
        with self.assertRaises(TopicError):
            validate_topic_name("x" * 65536)

    def test_non_string(self):
        with self.assertRaises(TopicError):
            validate_topic_name(42)

    def test_returns_input(self):
        self.assertEqual(validate_topic_name("a/b"), "a/b")


class TestValidateTopicFilter(unittest.TestCase):
    """Topic filters are used when subscribing and may contain wildcards."""

    def test_valid(self):
        for value in ("#", "sensors/#", "sensors/+/temp", "+", "+/+", "sensors/+"):
            self.assertTrue(is_valid_topic_filter(value), value)

    def test_empty(self):
        with self.assertRaises(TopicError):
            validate_topic_filter("")

    def test_hash_must_be_last(self):
        with self.assertRaises(TopicError):
            validate_topic_filter("sensors/#/temp")

    def test_hash_must_own_level(self):
        with self.assertRaises(TopicError):
            validate_topic_filter("sensors/#x")

    def test_plus_must_own_level(self):
        with self.assertRaises(TopicError):
            validate_topic_filter("sensors/+x")

    def test_returns_input(self):
        self.assertEqual(validate_topic_filter("a/#"), "a/#")


class TestTopicMatches(unittest.TestCase):
    """Wildcard matching semantics from the specification."""

    CASES = [
        # (filter, topic, expected)
        ("sport/#", "sport", True),
        ("sport/#", "sport/tennis", True),
        ("sport/#", "sport/tennis/player1", True),
        ("sport/#", "sport/tennis/player1/ranking", True),
        ("sport/tennis/#", "sport/tennis", True),
        ("#", "anything/at/all", True),
        ("sport/tennis/+", "sport/tennis/player1", True),
        ("sport/tennis/+", "sport/tennis/player1/ranking", False),
        ("sport/+", "sport", False),
        ("sport/+", "sport/", True),
        ("+/+", "/finance", True),
        ("/+", "/finance", True),
        ("+", "/finance", False),
        ("sport/tennis", "sport/tennis", True),
        ("sport/tennis", "sport/tennis/1", False),
        ("sport/tennis", "sport", False),
        ("sport/tennis/#", "sport/rugby", False),
    ]

    def test_specification_cases(self):
        for topic_filter, topic, expected in self.CASES:
            self.assertEqual(
                topic_matches(topic_filter, topic),
                expected,
                "filter=%r topic=%r expected=%r" % (topic_filter, topic, expected),
            )

    def test_dollar_topics_are_protected(self):
        """MQTT-4.7.2-1: wildcard-leading filters never match '$' topics."""
        self.assertFalse(topic_matches("#", "$SYS/broker/uptime"))
        self.assertFalse(topic_matches("+/monitor/Clients", "$SYS/monitor/Clients"))
        self.assertTrue(topic_matches("$SYS/#", "$SYS/broker/uptime"))
        self.assertTrue(topic_matches("$SYS/broker/+", "$SYS/broker/uptime"))

    def test_degenerate_inputs(self):
        self.assertFalse(topic_matches("", "a"))
        self.assertFalse(topic_matches("a", ""))
        self.assertFalse(topic_matches(None, "a"))
        self.assertFalse(topic_matches("a", None))


class TestHelpers(unittest.TestCase):
    """Small utilities built on top of the matching engine."""

    def test_topic_levels(self):
        self.assertEqual(topic_levels("a/b/c"), ["a", "b", "c"])
        self.assertEqual(topic_levels("/a"), ["", "a"])
        self.assertEqual(topic_levels("a/"), ["a", ""])

    def test_common_prefix_depth(self):
        self.assertEqual(common_prefix_depth("sport/tennis/#"), 2)
        self.assertEqual(common_prefix_depth("sport/+"), 1)
        self.assertEqual(common_prefix_depth("#"), 0)


if __name__ == "__main__":
    unittest.main()
