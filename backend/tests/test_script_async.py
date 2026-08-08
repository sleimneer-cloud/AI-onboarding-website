import asyncio
import sys

from app.scripts._async import run_async


def test_run_async_uses_a_psycopg_compatible_loop_on_windows() -> None:
    observed_loop: asyncio.AbstractEventLoop | None = None

    async def capture_loop() -> None:
        nonlocal observed_loop
        observed_loop = asyncio.get_running_loop()

    run_async(capture_loop())

    assert observed_loop is not None
    if sys.platform == "win32":
        assert isinstance(observed_loop, asyncio.SelectorEventLoop)
