"""Exception hierarchy for MQTTForge.

All exceptions derive from :class:`MQTTError` so callers can catch a single
base class when they only care about "something went wrong".
"""


class MQTTError(Exception):
    """Base class for every error raised by MQTTForge."""


class CodecError(MQTTError):
    """Raised when a byte stream cannot be encoded or decoded.

    Typical causes: truncated packets, an over-long remaining-length field,
    strings longer than the 65535 byte protocol limit, or unknown packet types.
    """


class TopicError(MQTTError):
    """Raised when a topic name or topic filter violates MQTT 3.1.1 rules."""


class ProtocolError(MQTTError):
    """Raised when the peer sends a packet that is illegal in the current state."""


class ConnectionError_(MQTTError):
    """Base class for connection level failures."""


class ConnectRefused(ConnectionError_):
    """Raised when CONNACK carries a non-zero return code.

    Attributes:
        return_code: The raw CONNACK return code (1..5).
    """

    #: Human readable description for every CONNACK return code.
    MESSAGES = {
        1: "Connection refused - unacceptable protocol version",
        2: "Connection refused - identifier rejected",
        3: "Connection refused - server unavailable",
        4: "Connection refused - bad user name or password",
        5: "Connection refused - not authorized",
    }

    def __init__(self, return_code: int):
        self.return_code = return_code
        message = self.MESSAGES.get(
            return_code, "Connection refused - unknown code %d" % return_code
        )
        super().__init__("%s (code=%d)" % (message, return_code))


class TimeoutError_(MQTTError):
    """Raised when an acknowledgement does not arrive within the timeout."""


# The library intentionally shadows two builtin names with an underscore suffix
# so that user code doing `except TimeoutError` still behaves as expected.
Timeout = TimeoutError_
ConnectionError = ConnectionError_

__all__ = [
    "MQTTError",
    "CodecError",
    "TopicError",
    "ProtocolError",
    "ConnectionError_",
    "ConnectRefused",
    "TimeoutError_",
    "Timeout",
    "ConnectionError",
]
