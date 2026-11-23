"""Read available Codex usage resets without delaying footer rendering."""

import asyncio
import json
import threading
import time


async def _read_count():
    process = await asyncio.create_subprocess_exec(
        "codex", "app-server", "--stdio", stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )

    async def request(request_id, method, params):
        message = {"id": request_id, "method": method, "params": params}
        process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()
        while line := await process.stdout.readline():
            reply = json.loads(line)
            if reply.get("id") == request_id:
                return reply.get("result") or {}
        return {}

    try:
        await request(1, "initialize", {
            "clientInfo": {"name": "agent_statusline", "version": "1"},
            "capabilities": {"experimentalApi": True},
        })
        process.stdin.write(b'{"method":"initialized"}\n')
        result = await request(2, "account/rateLimits/read", {})
        count = (result.get("rateLimitResetCredits") or {}).get("availableCount")
        return count if type(count) is int and count >= 0 else None
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.wait()


_count = None
_refresh_at = 0.0


def _refresh():
    global _count
    try:
        _count = asyncio.run(asyncio.wait_for(_read_count(), timeout=8))
    except (OSError, ValueError, asyncio.TimeoutError):
        _count = None


def available_resets():
    global _refresh_at
    now = time.monotonic()
    if now >= _refresh_at:
        _refresh_at = now + 300
        threading.Thread(target=_refresh, daemon=True).start()
    return _count
