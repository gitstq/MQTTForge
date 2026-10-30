"""Allow ``python -m mqttforge`` to behave exactly like the ``mqttforge`` script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
