"""Blocking MQTT 3.1.1 client built on the standard library only.

The client is intentionally small but protocol complete:

* QoS 0 (at most once), QoS 1 (at least once) and QoS 2 (exactly once)
  publish flows with the full PUBREC/PUBREL/PUBCOMP handshake.
* SUBSCRIBE / UNSUBSCRIBE / PINGREQ / DISCONNECT.
* A background receiver thread that dispatches inbound PUBLISH messages to a
  callback and/or an internal queue, and answers the broker's handshakes.
* Optional automatic keep-alive pings.

Example:
    >>> from mqttforge import MQTTClient
    >>> client = MQTTClient(client_id="demo")
    >>> client.connect("127.0.0.1", 1883)          # doctest: +SKIP
    >>> client.subscribe([("sensors/#", 1)])       # doctest: +SKIP
    [1]
    >>> client.publish("sensors/temp", b"21.5", qos=1)  # doctest: +SKIP
    >>> client.disconnect()                        # doctest: +SKIP
"""

import queue
import socket
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from .codec import encode_packet, read_packet
from .errors import (
    CodecError,
    ConnectRefused,
    MQTTError,
    ProtocolError,
    TimeoutError_,
)
from .packets import (
    PACKET_ID_MAX,
    PACKET_ID_MIN,
    Connack,
    Connect,
    Disconnect,
    Pingreq,
    Publish,
    Puback,
    Pubcomp,
    Pubrec,
    Pubrel,
    Subscribe,
    Unsubscribe,
    Will,
    validate_qos,
)
from .topics import validate_topic_filter, validate_topic_name

#: Default socket timeout in seconds.
DEFAULT_TIMEOUT = 10.0


class MQTTClient:
    """A compact, thread-safe MQTT 3.1.1 client.

    Args:
        client_id: Identifier sent to the broker. When empty a random
            ``mqttforge-<hex>`` identifier is generated.
        clean_session: Ask the broker to discard any previous session state.
        keepalive: Keep-alive period in seconds; a PINGREQ is sent whenever the
            link has been idle for this long. ``0`` disables keep-alive.
        username: Optional user name for broker authentication.
        password: Optional password, ``str`` or ``bytes``.
        will: Optional :class:`~mqttforge.packets.Will` message.
        timeout: Default acknowledgement timeout in seconds.
        on_message: Optional callable invoked as ``on_message(client, publish)``
            for every inbound application message.

    Attributes:
        messages: :class:`queue.Queue` holding inbound
            :class:`~mqttforge.packets.Publish` objects.
        connected: ``True`` while the transport is up.
    """

    def __init__(
        self,
        client_id: str = "",
        clean_session: bool = True,
        keepalive: int = 60,
        username: Optional[str] = None,
        password: Optional[Union[str, bytes]] = None,
        will: Optional[Will] = None,
        timeout: float = DEFAULT_TIMEOUT,
        on_message: Optional[Callable[["MQTTClient", Publish], None]] = None,
    ):
        self.client_id = client_id or ("mqttforge-" + uuid.uuid4().hex[:12])
        self.clean_session = clean_session
        self.keepalive = int(keepalive)
        self.username = username
        self.password = password
        self.will = will
        self.timeout = float(timeout)
        self.on_message = on_message
        self.messages: "queue.Queue[Publish]" = queue.Queue()

        self._sock: Optional[socket.socket] = None
        self._send_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._cond = threading.Condition(self._state_lock)
        self._acks: Dict[Tuple[int, str], object] = {}
        self._inbound_qos2: Dict[int, Publish] = {}
        self._used_pids = set()
        self._pid_counter = PACKET_ID_MIN
        self._ping_done = False
        self._connected = False
        self._stop = threading.Event()
        self._error: Optional[BaseException] = None
        self._receiver: Optional[threading.Thread] = None
        self._keepalive_thread: Optional[threading.Thread] = None
        self._last_io = 0.0

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        """``True`` while the client holds an open, usable connection."""
        with self._state_lock:
            return self._connected and self._sock is not None

    def connect(self, host: str, port: int = 1883, timeout: Optional[float] = None):
        """Open a TCP connection and complete the CONNECT/CONNACK exchange.

        Args:
            host: Broker host name or IP address.
            port: Broker TCP port, defaults to ``1883``.
            timeout: Socket timeout for the handshake; overrides the default.

        Returns:
            ``self`` so the call can be chained.

        Raises:
            ConnectRefused: If the broker replies with a non-zero return code.
            TimeoutError_: If CONNACK does not arrive in time.
            OSError: If the TCP connection cannot be established.
        """
        if self.connected:
            raise ProtocolError("client is already connected")
        timeout = self.timeout if timeout is None else timeout

        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.settimeout(timeout)
        self._sock = sock
        self._stop.clear()
        self._error = None
        self._last_io = time.monotonic()

        connect = Connect(
            client_id=self.client_id,
            clean_session=self.clean_session,
            keepalive=self.keepalive,
            username=self.username,
            password=self.password,
            will=self.will,
        )
        self._send(connect)

        connack = read_packet(self._read_exact)
        if not isinstance(connack, Connack):
            raise ProtocolError("expected CONNACK, got %s" % type(connack).__name__)
        if not connack.accepted:
            self._close_socket()
            raise ConnectRefused(connack.return_code)

        # The handshake is done: hand the socket over to the receiver thread.
        sock.settimeout(None)
        with self._state_lock:
            self._connected = True
        self._receiver = threading.Thread(
            target=self._receive_loop, name="mqttforge-rx", daemon=True
        )
        self._receiver.start()

        if self.keepalive > 0:
            self._keepalive_thread = threading.Thread(
                target=self._keepalive_loop, name="mqttforge-ka", daemon=True
            )
            self._keepalive_thread.start()
        return self

    def disconnect(self):
        """Send DISCONNECT and tear down the transport gracefully."""
        if self._sock is not None:
            try:
                self._send(Disconnect())
            except (OSError, MQTTError):
                pass
        with self._state_lock:
            self._connected = False
        self._stop.set()
        self._close_socket()
        with self._cond:
            self._cond.notify_all()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()
        return False

    def _close_socket(self):
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Socket primitives
    # ------------------------------------------------------------------
    def _read_exact(self, count: int) -> bytes:
        """Read exactly ``count`` bytes, raising on premature EOF."""
        if self._sock is None:
            raise CodecError("socket is closed")
        chunks = bytearray()
        while len(chunks) < count:
            chunk = self._sock.recv(count - len(chunks))
            if not chunk:
                raise CodecError("connection closed by peer")
            chunks += chunk
        return bytes(chunks)

    def _send(self, packet) -> None:
        """Serialise and write one packet, guarded by the send lock."""
        with self._send_lock:
            if self._sock is None:
                raise ProtocolError("not connected")
            self._sock.sendall(encode_packet(packet))
            self._last_io = time.monotonic()

    # ------------------------------------------------------------------
    # Packet identifier management
    # ------------------------------------------------------------------
    def _acquire_packet_id(self) -> int:
        with self._state_lock:
            for _ in range(PACKET_ID_MAX):
                pid = self._pid_counter
                self._pid_counter += 1
                if self._pid_counter > PACKET_ID_MAX:
                    self._pid_counter = PACKET_ID_MIN
                if pid not in self._used_pids:
                    self._used_pids.add(pid)
                    return pid
            raise ProtocolError("no free packet identifier available")

    def _release_packet_id(self, packet_id: int) -> None:
        with self._state_lock:
            self._used_pids.discard(packet_id)

    def _wait_ack(self, packet_id: int, kinds: Sequence[str], timeout: float):
        """Block until one of ``kinds`` arrives for ``packet_id``."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                if self._error is not None:
                    raise self._error
                for kind in kinds:
                    key = (packet_id, kind)
                    if key in self._acks:
                        return self._acks.pop(key)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError_(
                        "timed out after %.2fs waiting for %s (packet id %d)"
                        % (timeout, "/".join(kinds), packet_id)
                    )
                self._cond.wait(min(remaining, 0.25))

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------
    def publish(
        self,
        topic: str,
        payload: Union[bytes, str] = b"",
        qos: int = 0,
        retain: bool = False,
        timeout: Optional[float] = None,
    ) -> None:
        """Publish an application message.

        Args:
            topic: Destination topic name; must not contain wildcards.
            payload: Message body, ``bytes`` or ``str``.
            qos: ``0``, ``1`` or ``2``.
            retain: Ask the broker to retain the message.
            timeout: Override the default acknowledgement timeout.

        Raises:
            TopicError: If the topic name is invalid.
            TimeoutError_: If the broker does not complete the QoS handshake.
        """
        validate_topic_name(topic)
        qos = validate_qos(qos)
        timeout = self.timeout if timeout is None else timeout

        packet_id = self._acquire_packet_id() if qos > 0 else None
        try:
            self._send(
                Publish(
                    topic=topic, payload=payload, qos=qos, retain=retain,
                    packet_id=packet_id,
                )
            )
            if qos == 1:
                self._wait_ack(packet_id, ("PUBACK",), timeout)
            elif qos == 2:
                self._wait_ack(packet_id, ("PUBREC",), timeout)
                self._send(Pubrel(packet_id=packet_id))
                self._wait_ack(packet_id, ("PUBCOMP",), timeout)
        finally:
            if packet_id is not None:
                self._release_packet_id(packet_id)

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe
    # ------------------------------------------------------------------
    def subscribe(
        self,
        subscriptions: Union[Sequence[Tuple[str, int]], Dict[str, int], str],
        qos: int = 0,
        timeout: Optional[float] = None,
    ) -> List[int]:
        """Subscribe to one or more topic filters.

        Args:
            subscriptions: A single filter (``str``), a ``{filter: qos}`` dict,
                or a sequence of ``(filter, qos)`` pairs.
            qos: QoS applied when ``subscriptions`` is a plain string.
            timeout: Override the default acknowledgement timeout.

        Returns:
            Granted QoS level for each requested filter, in order. ``-1`` marks
            a rejected subscription.

        Raises:
            TopicError: If a topic filter is invalid.
            TimeoutError_: If SUBACK does not arrive in time.
        """
        pairs = self._normalise_subscriptions(subscriptions, qos)
        for topic_filter, _ in pairs:
            validate_topic_filter(topic_filter)
        timeout = self.timeout if timeout is None else timeout

        packet_id = self._acquire_packet_id()
        try:
            self._send(Subscribe(packet_id=packet_id, subscriptions=pairs))
            suback = self._wait_ack(packet_id, ("SUBACK",), timeout)
        finally:
            self._release_packet_id(packet_id)
        return list(suback.granted_qos)

    def unsubscribe(
        self, filters: Union[str, Sequence[str]], timeout: Optional[float] = None
    ) -> None:
        """Unsubscribe from one or more topic filters.

        Args:
            filters: A single filter or a sequence of filters.
            timeout: Override the default acknowledgement timeout.
        """
        if isinstance(filters, str):
            filters = [filters]
        for topic_filter in filters:
            validate_topic_filter(topic_filter)
        timeout = self.timeout if timeout is None else timeout

        packet_id = self._acquire_packet_id()
        try:
            self._send(Unsubscribe(packet_id=packet_id, filters=list(filters)))
            self._wait_ack(packet_id, ("UNSUBACK",), timeout)
        finally:
            self._release_packet_id(packet_id)

    @staticmethod
    def _normalise_subscriptions(subscriptions, default_qos: int = 0):
        """Coerce the accepted subscription shapes into ``(filter, qos)`` pairs."""
        if isinstance(subscriptions, str):
            return [(subscriptions, validate_qos(default_qos))]
        if isinstance(subscriptions, dict):
            return [(key, validate_qos(value)) for key, value in subscriptions.items()]
        pairs = []
        for item in subscriptions:
            if isinstance(item, str):
                pairs.append((item, validate_qos(default_qos)))
            else:
                topic_filter, qos = item
                pairs.append((topic_filter, validate_qos(qos)))
        return pairs

    # ------------------------------------------------------------------
    # Keep alive
    # ------------------------------------------------------------------
    def ping(self, timeout: Optional[float] = None) -> float:
        """Send PINGREQ and wait for PINGRESP.

        Returns:
            Measured round trip time in milliseconds.

        Raises:
            TimeoutError_: If PINGRESP does not arrive in time.
        """
        timeout = self.timeout if timeout is None else timeout
        with self._cond:
            self._ping_done = False
        started = time.monotonic()
        self._send(Pingreq())
        deadline = started + timeout
        with self._cond:
            while not self._ping_done:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError_("timed out waiting for PINGRESP")
                self._cond.wait(min(remaining, 0.25))
        return (time.monotonic() - started) * 1000.0

    def _keepalive_loop(self):
        while not self._stop.is_set() and self.connected:
            self._stop.wait(max(1.0, self.keepalive / 2.0))
            if self._stop.is_set() or not self.connected:
                break
            try:
                with self._state_lock:
                    idle = time.monotonic() - self._last_io
                if idle >= self.keepalive:
                    self._send(Pingreq())
            except (OSError, MQTTError):
                break

    # ------------------------------------------------------------------
    # Message plumbing
    # ------------------------------------------------------------------
    def wait_for_message(self, timeout: Optional[float] = None) -> Optional[Publish]:
        """Block until an inbound PUBLISH arrives.

        Args:
            timeout: Optional timeout in seconds; ``None`` waits forever.

        Returns:
            The received :class:`~mqttforge.packets.Publish`, or ``None`` on
            timeout.
        """
        try:
            return self.messages.get(timeout=timeout)
        except queue.Empty:
            return None

    def _deliver(self, packet: Publish) -> None:
        self.messages.put(packet)
        if self.on_message is not None:
            try:
                self.on_message(self, packet)
            except Exception:  # pragma: no cover - user callback safety net
                pass

    def _receive_loop(self):
        try:
            while not self._stop.is_set():
                packet = read_packet(self._read_exact)
                self._last_io = time.monotonic()
                self._handle_packet(packet)
        except (CodecError, ProtocolError, OSError, ValueError) as exc:
            self._error = exc
        finally:
            with self._state_lock:
                self._connected = False
            with self._cond:
                self._cond.notify_all()

    def _handle_packet(self, packet) -> None:
        # Packet names are normalised to upper case so they match the keys used
        # by :meth:`_wait_ack` (e.g. "SUBACK", "PUBACK").
        name = type(packet).__name__.upper()
        if isinstance(packet, Publish):
            if packet.qos == 1:
                self._send(Puback(packet_id=packet.packet_id))
            elif packet.qos == 2:
                with self._state_lock:
                    self._inbound_qos2[packet.packet_id] = packet
                self._send(Pubrec(packet_id=packet.packet_id))
            self._deliver(packet)
            return
        if isinstance(packet, Pubrel):
            with self._state_lock:
                self._inbound_qos2.pop(packet.packet_id, None)
            self._send(Pubcomp(packet_id=packet.packet_id))
            return
        if name in ("PUBACK", "PUBREC", "PUBCOMP", "SUBACK", "UNSUBACK"):
            key = (packet.packet_id, name)
            with self._cond:
                self._acks[key] = packet
                self._cond.notify_all()
            return
        if name == "PINGRESP":
            with self._cond:
                self._ping_done = True
                self._cond.notify_all()
            return
        if name == "DISCONNECT":
            with self._state_lock:
                self._connected = False
            return
        # CONNACK arriving here is unexpected but harmless.
        return


__all__ = ["MQTTClient", "DEFAULT_TIMEOUT"]
