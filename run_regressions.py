"""Run every baseline regression offline with the REAL installed MCP SDK."""
from __future__ import annotations

import os
from pathlib import Path
import unittest


def main() -> int:
    os.environ['TRIPSHOT_DISABLE_SCHEDULE_REFRESH'] = '1'
    os.environ['TRIPSHOT_DISABLE_SERVICE_REFRESH'] = '1'
    # Fail early instead of allowing legacy test modules to install an SDK stub.
    from mcp.server import MCPServer  # noqa: F401

    root = Path(__file__).resolve().parent
    loader = unittest.TestLoader()
    suite = loader.discover(str(root / 'tests'))
    suite.addTests(loader.loadTestsFromNames([
        'test_limit_guardrails', 'test_tripshot_v8',
        'test_tripshot_v9', 'test_tripshot_v10',
    ]))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
