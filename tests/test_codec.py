"""Unit tests for the MQTT 3.1.1 wire codec."""

import struct
import unittest

from mqttforge.codec import (
    decode_hex,
    decode_packets,
    decode_one,
    encode_hex,
    encode_packet,
    encode_remaining_length,
    read_packet,
)
from mqttforge.errors import CodecError, ProtocolError
from mqttforge.packets import (
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


def reader_for(data: bytes):
    """Build a ``read_exact`` callable backed by an in-memory buffer."""
    state = {"pos": 0}

    def read_exact(count: int) -> bytes:
        start = state["pos"]
        end = start + count
        if end > len(data):
            raise CodecError("unexpected end of buffer")
        state["pos"] = end
        return data[start:end]

    return read_exact


class TestRemainingLength(unittest.TestCase):
    """Variable byte integer encoding (MQTT-2.2.3)."""

    BOUNDARIES = [0, 1, 127, 128, 16383, 16384, 2097151, 2097152, 268435455]

    def test_round_trip_boundaries(self):
        for value in self.BOUNDARIES:
            encoded = encode_remaining_length(value)
            self.assertLessEqual(len(encoded), 4)
            decoded = self._decode(encoded)
            self.assertEqual(decoded, value, "round trip failed for %d" % value)

    def test_known_encodings(self):
        self.assertEqual(encode_remaining_length(0), b"\x00")
        self.assertEqual(encode_remaining_length(127), b"\x7f")
        self.assertEqual(encode_remaining_length(128), b"\x80\x01")
        self.assertEqual(encode_remaining_length(16383), b"\xff\x7f")
        self.assertEqual(encode_remaining_length(16384), b"\x80\x80\x01")
        self.assertEqual(encode_remaining_length(268435455), b"\xff\xff\xff\x7f")

    def test_out_of_range(self):
        with self.assertRaises(CodecError):
            encode_remaining_length(268435456)
        with self.assertRaises(CodecError):
            encode_remaining_length(-1)

    def test_malformed_continuation(self):
        with self.assertRaises(CodecError):
            self._decode(b"\xff\xff\xff\xff")

    def _decode(self, raw: bytes) -> int:
        from mqttforge.codec import decode_remaining_length

        return decode_remaining_length(reader_for(raw))


class TestConnect(unittest.TestCase):
    """CONNECT / CONNACK encoding and decoding."""

    def test_minimal_round_trip(self):
        packet = Connect(client_id="abc", clean_session=True, keepalive=60)
        decoded = decode_one(encode_packet(packet))
        self.assertIsInstance(decoded, Connect)
        self.assertEqual(decoded.client_id, "abc")
        self.assertEqual(decoded.protocol_name, "MQTT")
        self.assertEqual(decoded.protocol_level, 4)
        self.assertTrue(decoded.clean_session)
        self.assertEqual(decoded.keepalive, 60)
        self.assertIsNone(decoded.username)
        self.assertIsNone(decoded.password)
        self.assertIsNone(decoded.will)

    def test_full_round_trip(self):
        packet = Connect(
            client_id="device-42",
            clean_session=False,
            keepalive=120,
            username="alice",
            password="s3cret",
            will=Will(topic="device/42/status", payload=b"offline", qos=2, retain=True),
        )
        decoded = decode_one(encode_packet(packet))
        self.assertEqual(decoded.client_id, "device-42")
        self.assertFalse(decoded.clean_session)
        self.assertEqual(decoded.keepalive, 120)
        self.assertEqual(decoded.username, "alice")
        self.assertEqual(decoded.password, b"s3cret")
        self.assertIsNotNone(decoded.will)
        self.assertEqual(decoded.will.topic, "device/42/status")
        self.assertEqual(decoded.will.payload, b"offline")
        self.assertEqual(decoded.will.qos, 2)
        self.assertTrue(decoded.will.retain)

    def test_wire_layout(self):
        """The first bytes must spell out 'MQTT' + level 4 + flags + keepalive."""
        raw = encode_packet(
            Connect(client_id="x", clean_session=True, keepalive=30)
        )
        # [0] fixed header, [1] remaining length, [2:4] length prefix of the
        # protocol name, [4:8] b"MQTT", [8] level, [9] flags, [10:12] keepalive
        self.assertEqual(raw[0], 0x10)
        self.assertEqual(raw[2:4], b"\x00\x04")
        self.assertEqual(raw[4:8], b"MQTT")
        self.assertEqual(raw[8], 4)
        self.assertEqual(raw[9], 0x02)  # clean session flag only
        self.assertEqual(struct.unpack("!H", raw[10:12])[0], 30)

    def test_connack(self):
        raw = encode_packet(Connack(session_present=True, return_code=0))
        self.assertEqual(raw, b"\x20\x02\x01\x00")
        decoded = decode_one(raw)
        self.assertTrue(decoded.session_present)
        self.assertTrue(decoded.accepted)


class TestPublish(unittest.TestCase):
    """PUBLISH and its acknowledgement packets."""

    def test_qos0(self):
        raw = encode_packet(Publish(topic="a/b", payload=b"hi"))
        self.assertEqual(raw[0], 0x30)  # PUBLISH, no flags
        decoded = decode_one(raw)
        self.assertEqual(decoded.topic, "a/b")
        self.assertEqual(decoded.payload, b"hi")
        self.assertEqual(decoded.qos, 0)
        self.assertIsNone(decoded.packet_id)

    def test_qos1_with_packet_id(self):
        decoded = decode_one(
            encode_packet(Publish(topic="a/b", payload=b"x", qos=1, packet_id=4242))
        )
        self.assertEqual(decoded.qos, 1)
        self.assertEqual(decoded.packet_id, 4242)

    def test_qos2_flags(self):
        raw = encode_packet(
            Publish(topic="t", payload=b"p", qos=2, retain=True, dup=True, packet_id=9)
        )
        # DUP(0x08) | QoS2(0x04) | RETAIN(0x01) == 0x0D
        self.assertEqual(raw[0] & 0x0F, 0x0D)
        decoded = decode_one(raw)
        self.assertTrue(decoded.dup)
        self.assertTrue(decoded.retain)
        self.assertEqual(decoded.qos, 2)

    def test_empty_and_binary_payload(self):
        for payload in (b"", b"\x00\x01\xff\xfe", bytes(range(256))):
            decoded = decode_one(encode_packet(Publish(topic="bin", payload=payload)))
            self.assertEqual(decoded.payload, payload)

    def test_string_payload_is_utf8_encoded(self):
        decoded = decode_one(encode_packet(Publish(topic="u", payload="温度 25℃")))
        self.assertEqual(decoded.payload, "温度 25℃".encode("utf-8"))

    def test_large_payload_uses_multibyte_length(self):
        payload = b"x" * 200000
        raw = encode_packet(Publish(topic="big", payload=payload))
        packets, leftover = decode_packets(raw)
        self.assertEqual(len(packets), 1)
        self.assertEqual(leftover, b"")
        self.assertEqual(len(packets[0].payload), 200000)

    def test_qos1_requires_packet_id(self):
        with self.assertRaises(ValueError):
            Publish(topic="t", payload=b"p", qos=1)

    def test_invalid_qos(self):
        with self.assertRaises(ValueError):
            Publish(topic="t", payload=b"p", qos=3)

    def test_acks(self):
        for packet in (Puback(packet_id=1), Pubrec(packet_id=2),
                       Pubrel(packet_id=3), Pubcomp(packet_id=4)):
            decoded = decode_one(encode_packet(packet))
            self.assertEqual(decoded.packet_id, packet.packet_id)
        # PUBREL must carry the reserved flag 0x02
        self.assertEqual(encode_packet(Pubrel(packet_id=3))[0], 0x62)


class TestSubscribe(unittest.TestCase):
    """SUBSCRIBE / SUBACK / UNSUBSCRIBE / UNSUBACK."""

    def test_subscribe_round_trip(self):
        packet = Subscribe(
            packet_id=77, subscriptions=[("sensors/#", 1), ("devices/+/temp", 2)]
        )
        decoded = decode_one(encode_packet(packet))
        self.assertEqual(decoded.packet_id, 77)
        self.assertEqual(
            decoded.subscriptions, [("sensors/#", 1), ("devices/+/temp", 2)]
        )
        self.assertEqual(encode_packet(packet)[0], 0x82)

    def test_suback_granted_qos(self):
        packet = Suback(packet_id=77, return_codes=[0, 1, 2, 0x80])
        decoded = decode_one(encode_packet(packet))
        self.assertEqual(decoded.granted_qos, [0, 1, 2, -1])

    def test_unsubscribe_round_trip(self):
        packet = Unsubscribe(packet_id=5, filters=["a/b", "c/#"])
        decoded = decode_one(encode_packet(packet))
        self.assertEqual(decoded.filters, ["a/b", "c/#"])
        self.assertEqual(encode_packet(packet)[0], 0xA2)

    def test_unsuback(self):
        decoded = decode_one(encode_packet(Unsuback(packet_id=5)))
        self.assertEqual(decoded.packet_id, 5)


class TestSimplePackets(unittest.TestCase):
    """Zero-payload control packets."""

    def test_ping_and_disconnect(self):
        self.assertEqual(encode_packet(Pingreq()), b"\xc0\x00")
        self.assertEqual(encode_packet(Pingresp()), b"\xd0\x00")
        self.assertEqual(encode_packet(Disconnect()), b"\xe0\x00")
        self.assertIsInstance(decode_one(b"\xc0\x00"), Pingreq)
        self.assertIsInstance(decode_one(b"\xd0\x00"), Pingresp)
        self.assertIsInstance(decode_one(b"\xe0\x00"), Disconnect)


class TestStreamDecoding(unittest.TestCase):
    """Decoding concatenated frames and malformed input."""

    def test_multiple_frames(self):
        stream = (
            encode_packet(Pingreq())
            + encode_packet(Publish(topic="a", payload=b"1"))
            + encode_packet(Puback(packet_id=1))
            + encode_packet(Disconnect())
        )
        packets, leftover = decode_packets(stream)
        self.assertEqual(len(packets), 4)
        self.assertEqual(leftover, b"")
        self.assertEqual(
            [type(p).__name__ for p in packets],
            ["Pingreq", "Publish", "Puback", "Disconnect"],
        )

    def test_partial_trailing_frame(self):
        stream = encode_packet(Pingreq()) + b"\x30\x05"
        with self.assertRaises(CodecError):
            decode_packets(stream)
        packets, leftover = decode_packets(stream, allow_partial=True)
        self.assertEqual(len(packets), 1)
        self.assertEqual(leftover, b"\x30\x05")

    def test_unknown_packet_type(self):
        with self.assertRaises(CodecError):
            decode_one(b"\x00\x00")  # type 0 is reserved

    def test_truncated_body(self):
        with self.assertRaises(CodecError):
            decode_one(b"\x30\x0a\x00\x02hi")  # claims 10 bytes, supplies 4

    def test_invalid_pubrel_flags(self):
        with self.assertRaises(ProtocolError):
            decode_one(b"\x60\x02\x00\x01")  # PUBREL without the reserved flag

    def test_invalid_qos_value_three(self):
        with self.assertRaises(ProtocolError):
            decode_one(b"\x36\x06\x00\x02hi\x00\x01")  # QoS bits == 3

    def test_invalid_utf8(self):
        with self.assertRaises(CodecError):
            decode_one(b"\x30\x04\x00\x02\xff\xfe")

    def test_read_packet_from_reader(self):
        raw = encode_packet(Publish(topic="r", payload=b"reader"))
        self.assertIsInstance(read_packet(reader_for(raw)), Publish)

    def test_empty_stream(self):
        packets, leftover = decode_packets(b"")
        self.assertEqual(packets, [])
        self.assertEqual(leftover, b"")

    def test_hex_helpers(self):
        self.assertEqual(encode_hex(b"\x10\x2a"), "102A")
        self.assertEqual(decode_hex("10 2A"), b"\x10\x2a")
        self.assertEqual(decode_hex("0x100x2A"), b"\x10\x2a")
        with self.assertRaises(CodecError):
            decode_hex("102")


if __name__ == "__main__":
    unittest.main()
