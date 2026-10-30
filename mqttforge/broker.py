"""A miniature, dependency free MQTT 3.1.1 broker.

The broker exists for two reasons:

1. **Fast local testing.** Spinning up an embedded broker turns integration
   tests into pure in-process, offline tests - no Mosquitto, no Docker, no
   network access required.
2. **Protocol reference.** Because it shares the codec with the client, any
   handshake bug shows up immediately on both sides of the wire.

Supported features: QoS 0/1/2 delivery (including the full QoS 2 handshake),
topic wildcards, retained messages, will messages, keep-alive pings and
multi-client fan-out. It is intended for development and CI, not as a
production MQTT server.
"""

import socket
import threading
import time
import uuid
from typing import Dict, List, Optional, Union

from .codec import encode_packet, read_packet
from .errors import CodecError, MQTTError, ProtocolError
from .packets import (
    PACKET_ID_MAX,
    PACKET_ID_MIN,
    QOS_FAILURE,
    Connack,
    Connect,
    Pingresp,
    Publish,
    Puback,
    Pubcomp,
    Pubrec,
    Pubrel,
    Suback,
    Subscribe,
    Unsuback,
    Unsubscribe,
    validate_qos,
)
from .topics import is_valid_topic_filter, topic_matches, validate_topic_name

#: Maximum QoS the broker is willing to grant (2 = exactly once).
DEFAULT_MAX_QOS = 2


def _carrier_publish(topic: str, payload, qos: int, retain: bool) -> Publish:
    """Build a PUBLISH used purely for internal routing.

    The wire codec requires a packet identifier whenever QoS > 0, but a message
    injected by the broker (or replayed from a will) is never serialised
    directly: :meth:`MiniBroker._deliver` allocates a fresh identifier per
    subscriber. A placeholder is therefore safe here and keeps the model
    consistent with real wire packets.
    """
    return Publish(
        topic=topic,
        payload=payload,
        qos=validate_qos(qos),
        retain=retain,
        packet_id=(PACKET_ID_MIN if qos else None),
    )


class _Session:
    """Per-connection broker state."""

    def __init__(self, broker: "MiniBroker", sock: socket.socket, addr, connect: Connect):
        self.broker = broker
        self.sock = sock
        self.addr = addr
        self.connect = connect
        self.client_id = connect.client_id or ("broker-" + uuid.uuid4().hex[:8])
        #: ``topic filter -> granted qos``
        self.subscriptions: Dict[str, int] = {}
        #: outbound QoS 1/2 publishes awaiting PUBACK / PUBCOMP
        self.outbound: Dict[int, Publish] = {}
        #: inbound QoS 2 publishes awaiting PUBREL
        self.inbound: Dict[int, Publish] = {}
        self.send_lock = threading.RLock()
        self.lock = threading.RLock()
        self._pid_counter = PACKET_ID_MIN
        self.graceful_close = False
        self.created_at = time.time()

    # -- helpers ---------------------------------------------------------
    def next_packet_id(self) -> int:
        with self.lock:
            for _ in range(PACKET_ID_MAX):
                pid = self._pid_counter
                self._pid_counter += 1
                if self._pid_counter > PACKET_ID_MAX:
                    self._pid_counter = PACKET_ID_MIN
                if pid not in self.outbound:
                    return pid
            raise ProtocolError("no free packet identifier for session")

    def read_exact(self, count: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < count:
            chunk = self.sock.recv(count - len(chunks))
            if not chunk:
                raise CodecError("connection closed by peer")
            chunks += chunk
        return bytes(chunks)

    def send(self, packet) -> bool:
        """Write a packet, returning ``False`` if the peer is gone."""
        try:
            with self.send_lock:
                self.sock.sendall(encode_packet(packet))
            return True
        except OSError:
            return False


class MiniBroker:
    """An embedded MQTT 3.1.1 broker for development, testing and demos.

    Args:
        host: Interface to bind, defaults to ``127.0.0.1``.
        port: TCP port to bind; ``0`` picks a free ephemeral port, which is the
            recommended setting for tests.
        max_qos: Highest QoS the broker grants to subscribers (0, 1 or 2).

    Attributes:
        port: The effective port after :meth:`start`.
        stats: Counters for connections, publishes and deliveries.

    Example:
        >>> broker = MiniBroker()
        >>> host, port = broker.start_background()
        >>> broker.shutdown()                      # doctest: +SKIP
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0, max_qos: int = DEFAULT_MAX_QOS):
        self.host = host
        self.port = int(port)
        self.max_qos = validate_qos(max_qos)
        self.sessions: Dict[str, _Session] = {}
        self.retained: Dict[str, Publish] = {}
        self.stats = {"connections": 0, "published": 0, "delivered": 0, "retained": 0}

        self._lock = threading.RLock()
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._session_threads: List[threading.Thread] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> "MiniBroker":
        """Bind the listening socket and start the accept loop."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(128)
        sock.settimeout(0.5)
        self._sock = sock
        self.port = sock.getsockname()[1]
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._accept_loop, name="mqttforge-broker", daemon=True
        )
        self._thread.start()
        return self

    def start_background(self):
        """Start the broker and return its ``(host, port)`` tuple."""
        self.start()
        return self.host, self.port

    def serve_forever(self):
        """Block until :meth:`shutdown` is called."""
        if self._thread is None:
            self.start()
        try:
            while not self._stop.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:  # pragma: no cover - interactive use
            self.shutdown()

    def shutdown(self):
        """Close the listening socket and every active client session."""
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        with self._lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            try:
                session.sock.close()
            except OSError:
                pass
        self.retained.clear()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.shutdown()
        return False

    # ------------------------------------------------------------------
    # Accept loop
    # ------------------------------------------------------------------
    def _accept_loop(self):
        while not self._stop.is_set() and self._sock is not None:
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            thread = threading.Thread(
                target=self._serve, args=(conn, addr), name="mqttforge-conn", daemon=True
            )
            thread.start()
            with self._lock:
                self._session_threads.append(thread)

    # ------------------------------------------------------------------
    # Per connection handling
    # ------------------------------------------------------------------
    def _serve(self, conn: socket.socket, addr):
        session = None
        try:
            conn.settimeout(15.0)
            first = read_packet(conn_read_exact(conn))
            if not isinstance(first, Connect):
                conn.close()
                return
            session = _Session(self, conn, addr, first)
            conn.settimeout(None)
            with self._lock:
                self.sessions[session.client_id] = session
                self.stats["connections"] += 1
            if not session.send(Connack(session_present=False, return_code=0)):
                return
            self._pump(session)
        except (CodecError, ProtocolError, OSError, ValueError):
            pass
        finally:
            if session is not None:
                self._drop(session)
            else:
                try:
                    conn.close()
                except OSError:
                    pass

    def _drop(self, session: _Session):
        """Remove a session, publishing its will message if it died abruptly."""
        with self._lock:
            self.sessions.pop(session.client_id, None)
        will = session.connect.will
        if will is not None and not session.graceful_close:
            try:
                validate_topic_name(will.topic)
                self.publish(will.topic, will.payload, qos=will.qos, retain=will.retain)
            except (ValueError, OSError, MQTTError):
                # A malformed will topic must never take the broker down.
                pass
        try:
            session.sock.close()
        except OSError:
            pass

    def _pump(self, session: _Session):
        while not self._stop.is_set():
            packet = read_packet(session.read_exact)
            name = type(packet).__name__
            if isinstance(packet, Publish):
                self._on_publish(session, packet)
            elif isinstance(packet, Pubrel):
                stored = session.inbound.pop(packet.packet_id, None)
                if stored is not None:
                    self._dispatch(stored)
                if not session.send(Pubcomp(packet_id=packet.packet_id)):
                    break
            elif isinstance(packet, Puback):
                session.outbound.pop(packet.packet_id, None)
            elif isinstance(packet, Pubrec):
                if not session.send(Pubrel(packet_id=packet.packet_id)):
                    break
            elif isinstance(packet, Pubcomp):
                session.outbound.pop(packet.packet_id, None)
            elif isinstance(packet, Subscribe):
                self._on_subscribe(session, packet)
            elif isinstance(packet, Unsubscribe):
                for topic_filter in packet.filters:
                    session.subscriptions.pop(topic_filter, None)
                if not session.send(Unsuback(packet_id=packet.packet_id)):
                    break
            elif name == "Pingreq":
                if not session.send(Pingresp()):
                    break
            elif name == "Disconnect":
                session.graceful_close = True
                break
            else:
                # Unknown or unexpected packet: close the connection.
                break

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _on_publish(self, session: _Session, packet: Publish):
        try:
            validate_topic_name(packet.topic)
        except Exception:
            return
        with self._lock:
            self.stats["published"] += 1
        # Retained messages: an empty payload clears the stored value.
        if packet.retain:
            with self._lock:
                if packet.payload:
                    self.retained[packet.topic] = packet
                    self.stats["retained"] = len(self.retained)
                else:
                    self.retained.pop(packet.topic, None)
                    self.stats["retained"] = len(self.retained)

        if packet.qos == 1:
            if not session.send(Puback(packet_id=packet.packet_id)):
                return
        elif packet.qos == 2:
            # QoS 2 is forwarded only after PUBREL arrives. Forwarding on
            # PUBLISH would duplicate the message whenever the publisher
            # retransmits, because the handshake can be replayed.
            session.inbound[packet.packet_id] = packet
            if not session.send(Pubrec(packet_id=packet.packet_id)):
                return
            return
        self._dispatch(packet)

    def _on_subscribe(self, session: _Session, packet: Subscribe):
        granted: List[int] = []
        for topic_filter, qos in packet.subscriptions:
            if is_valid_topic_filter(topic_filter):
                effective = min(int(qos), self.max_qos)
                session.subscriptions[topic_filter] = effective
                granted.append(effective)
            else:
                granted.append(QOS_FAILURE)
        if not session.send(Suback(packet_id=packet.packet_id, return_codes=granted)):
            return
        # Replay retained messages that match the new subscriptions.
        with self._lock:
            retained = list(self.retained.items())
        for topic, stored in retained:
            for topic_filter, sub_qos in list(session.subscriptions.items()):
                if topic_matches(topic_filter, topic):
                    self._deliver(session, stored, min(sub_qos, stored.qos))
                    break

    def _dispatch(self, packet: Publish):
        """Fan a publish out to every matching subscriber."""
        with self._lock:
            sessions = list(self.sessions.values())
        for session in sessions:
            for topic_filter, sub_qos in list(session.subscriptions.items()):
                if topic_matches(topic_filter, packet.topic):
                    self._deliver(session, packet, min(sub_qos, packet.qos))
                    break

    def _deliver(self, session: _Session, packet: Publish, qos: int):
        """Send one copy of ``packet`` to ``session`` at the effective QoS."""
        packet_id = None
        if qos > 0:
            packet_id = session.next_packet_id()
            session.outbound[packet_id] = packet
        # Count before the write so that "the client already has it" always
        # implies "delivered >= 1"; a failed send rolls the counter back.
        with self._lock:
            self.stats["delivered"] += 1
        ok = session.send(
            Publish(
                topic=packet.topic,
                payload=packet.payload,
                qos=qos,
                retain=False,
                packet_id=packet_id,
            )
        )
        if not ok:
            with self._lock:
                self.stats["delivered"] -= 1
            if packet_id is not None:
                session.outbound.pop(packet_id, None)

    # ------------------------------------------------------------------
    # Local injection API
    # ------------------------------------------------------------------
    def publish(
        self,
        topic: str,
        payload: Union[bytes, str] = b"",
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """Inject a message from the broker side (server-side publish).

        Handy for tests and for simulating devices without a real client.
        """
        validate_topic_name(topic)
        packet = _carrier_publish(topic, payload, qos, retain)
        if packet.retain:
            with self._lock:
                if packet.payload:
                    self.retained[packet.topic] = packet
                    self.stats["retained"] = len(self.retained)
                else:
                    self.retained.pop(packet.topic, None)
                    self.stats["retained"] = len(self.retained)
        with self._lock:
            self.stats["published"] += 1
        self._dispatch(packet)

    def subscriber_count(self) -> int:
        """Number of currently connected sessions."""
        with self._lock:
            return len(self.sessions)


def conn_read_exact(sock: socket.socket):
    """Build a ``read_exact`` callable bound to a raw socket."""

    def read_exact(count: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < count:
            chunk = sock.recv(count - len(chunks))
            if not chunk:
                raise CodecError("connection closed by peer")
            chunks += chunk
        return bytes(chunks)

    return read_exact


__all__ = ["MiniBroker", "DEFAULT_MAX_QOS"]
