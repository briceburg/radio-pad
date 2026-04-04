#!/usr/bin/env python3

import sys

from lib.health import health_path


def main() -> int:
    return 0 if health_path().exists() else 1


if __name__ == "__main__":
    sys.exit(main())
