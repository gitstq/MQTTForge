"""Version metadata for MQTTForge."""

__version__ = "1.0.0"

# Protocol level advertised in CONNECT: 4 == MQTT 3.1.1 (OASIS standard).
PROTOCOL_NAME = "MQTT"
PROTOCOL_LEVEL = 4

# Human readable protocol level table, used by the `probe` command.
PROTOCOL_LEVELS = {
    3: "MQTT 3.1",
    4: "MQTT 3.1.1",
    5: "MQTT 5.0",
}

__all__ = [
    "__version__",
    "PROTOCOL_NAME",
    "PROTOCOL_LEVEL",
    "PROTOCOL_LEVELS",
]
