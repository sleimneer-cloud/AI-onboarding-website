from __future__ import annotations

import asyncio
import sys
from collections.abc import Coroutine
from typing import Any


def run_async(coroutine: Coroutine[Any, Any, None]) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(coroutine)
