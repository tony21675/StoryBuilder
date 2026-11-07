#!/usr/bin/env python3
from __future__ import annotations

import sys

from builder.handoff_backup import HandoffBackupError, refresh_handoff_backups


def main() -> int:
    try:
        for message in refresh_handoff_backups():
            print(message)
    except HandoffBackupError as exc:
        print(f"WARNING: local handoff backup was not fully refreshed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
