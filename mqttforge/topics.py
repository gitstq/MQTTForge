"""MQTT 3.1.1 topic name / topic filter utilities.

Implements the rules of MQTT-3.3 (topic names) and MQTT-4.7 (topic filters):

* A topic name is used when **publishing** and must not contain wildcards.
* A topic filter is used when **subscribing** and may contain the
  single-level (``+``) and multi-level (``#``) wildcards.
* A filter that *starts* with a wildcard never matches topic names that begin
  with ``$`` (MQTT-4.7.2-1), which keeps ``$SYS/...`` telemetry private.
"""

from .errors import TopicError

#: Single level wildcard character.
WILDCARD_SINGLE = "+"
#: Multi level wildcard character.
WILDCARD_MULTI = "#"

#: Maximum length of a UTF-8 encoded topic, dictated by the 2 byte length prefix.
MAX_TOPIC_BYTES = 65535


def topic_levels(topic: str) -> list:
    """Split a topic into its ``/`` separated levels.

    Args:
        topic: Topic name or topic filter.

    Returns:
        List of level strings. ``"a/b"`` becomes ``["a", "b"]`` and a leading
        slash produces an empty first level, e.g. ``"/a"`` -> ``["", "a"]``.
    """
    return topic.split("/")


def _check_common(topic: str, what: str) -> None:
    """Shared validation for topic names and topic filters."""
    if not isinstance(topic, str):
        raise TopicError("%s must be a str, got %s" % (what, type(topic).__name__))
    if topic == "":
        raise TopicError("%s must contain at least one character" % what)
    if "\x00" in topic:
        raise TopicError("%s must not contain the null character (U+0000)" % what)
    if len(topic.encode("utf-8")) > MAX_TOPIC_BYTES:
        raise TopicError(
            "%s exceeds the %d byte protocol limit" % (what, MAX_TOPIC_BYTES)
        )


def validate_topic_name(topic: str) -> str:
    """Validate a topic name used for publishing.

    Args:
        topic: Topic name to validate.

    Returns:
        The validated topic unchanged, so the call can be chained.

    Raises:
        TopicError: If the topic is empty, too long, contains a null byte or
            contains a wildcard character.
    """
    _check_common(topic, "topic name")
    if WILDCARD_SINGLE in topic or WILDCARD_MULTI in topic:
        raise TopicError(
            "topic name must not contain the wildcard characters '+' or '#': %r" % topic
        )
    return topic


def validate_topic_filter(topic_filter: str) -> str:
    """Validate a topic filter used for subscribing.

    Args:
        topic_filter: Filter to validate, may contain ``+`` and ``#``.

    Returns:
        The validated filter unchanged.

    Raises:
        TopicError: If a wildcard does not occupy a whole level, or ``#`` is
            not the final level.
    """
    _check_common(topic_filter, "topic filter")
    levels = topic_levels(topic_filter)
    last = len(levels) - 1
    for index, level in enumerate(levels):
        if WILDCARD_MULTI in level:
            if level != WILDCARD_MULTI:
                raise TopicError(
                    "multi-level wildcard '#' must occupy an entire level: %r"
                    % topic_filter
                )
            if index != last:
                raise TopicError(
                    "multi-level wildcard '#' must be the last level: %r" % topic_filter
                )
        elif WILDCARD_SINGLE in level and level != WILDCARD_SINGLE:
            raise TopicError(
                "single-level wildcard '+' must occupy an entire level: %r"
                % topic_filter
            )
    return topic_filter


def _match(filter_levels: list, name_levels: list) -> bool:
    """Core wildcard matching helper shared by :func:`topic_matches`."""
    for index, flevel in enumerate(filter_levels):
        if flevel == WILDCARD_MULTI:
            # '#' matches every remaining level, including zero levels.
            return True
        if index >= len(name_levels):
            return False
        if flevel == WILDCARD_SINGLE:
            continue
        if flevel != name_levels[index]:
            return False
    return len(filter_levels) == len(name_levels)


def topic_matches(topic_filter: str, topic_name: str) -> bool:
    """Return ``True`` when ``topic_name`` is selected by ``topic_filter``.

    Args:
        topic_filter: Subscription filter, e.g. ``"sport/tennis/#"``.
        topic_name: Concrete topic name, e.g. ``"sport/tennis/player1"``.

    Returns:
        ``True`` when the broker would deliver the message to this filter.

    Notes:
        Per MQTT-4.7.2-1 a filter starting with ``+`` or ``#`` never matches a
        topic name beginning with ``$``.

    Examples:
        >>> topic_matches("sport/#", "sport")
        True
        >>> topic_matches("sport/+/player1", "sport/tennis/player1")
        True
        >>> topic_matches("#", "$SYS/broker/uptime")
        False
    """
    if not isinstance(topic_filter, str) or not isinstance(topic_name, str):
        return False
    if topic_filter == "" or topic_name == "":
        return False
    # MQTT-4.7.2-1: wildcard-leading filters never match '$' topics.
    if topic_name.startswith("$") and topic_filter[:1] in (
        WILDCARD_MULTI,
        WILDCARD_SINGLE,
    ):
        return False
    if topic_filter == topic_name:
        return True
    return _match(topic_levels(topic_filter), topic_levels(topic_name))


def is_valid_topic_name(topic: str) -> bool:
    """Non-raising variant of :func:`validate_topic_name`."""
    try:
        validate_topic_name(topic)
    except TopicError:
        return False
    return True


def is_valid_topic_filter(topic_filter: str) -> bool:
    """Non-raising variant of :func:`validate_topic_filter`."""
    try:
        validate_topic_filter(topic_filter)
    except TopicError:
        return False
    return True


def common_prefix_depth(topic_filter: str) -> int:
    """Return the number of literal (non-wildcard) leading levels of a filter.

    Useful for building subscription trees; also handy in reports.

    Examples:
        >>> common_prefix_depth("sport/tennis/#")
        2
    """
    depth = 0
    for level in topic_levels(topic_filter):
        if level in (WILDCARD_SINGLE, WILDCARD_MULTI):
            break
        depth += 1
    return depth


__all__ = [
    "WILDCARD_SINGLE",
    "WILDCARD_MULTI",
    "MAX_TOPIC_BYTES",
    "topic_levels",
    "validate_topic_name",
    "validate_topic_filter",
    "topic_matches",
    "is_valid_topic_name",
    "is_valid_topic_filter",
    "common_prefix_depth",
]
