"""A Codex statusline provider using newline-delimited MCP over stdio."""

import json
import re
import sys
from pathlib import Path

from core import Limit, Snapshot
from layout import render


URI = "ui://claude-footer/footer"
TOOL = {
    "name": "statusline",
    "title": "Claude Code style",
    "description": "Show the project, model, usage and local progress in the Codex footer.",
    "inputSchema": {"type": "object", "properties": {}},
    "_meta": {
        "openai/ui": {"entrypoints": [{"type": "statusline", "resourceUri": URI}]}
    },
}


MODEL_FAMILIES = {"astra": "AST", "sol": "SOL", "terra": "TER", "luna": "LUN"}
EFFORT = {"low": "L", "medium": "M", "high": "H", "xhigh": "XH", "max": "MAX", "ultra": "U"}


def model_name(model):
    name = model.get("display_name") or model.get("id") or "Codex"
    slug = (model.get("id") or name).lower().replace(" ", "-")
    match = re.fullmatch(r"gpt-(\d+(?:\.\d+)*)-([a-z]+)", slug)
    if match and match[2] in MODEL_FAMILIES:
        return MODEL_FAMILIES[match[2]] + match[1]
    return {"gpt-reserve": "RSV", "codex-auto-review": "REV"}.get(slug, name)


def rate_limits(account):
    buckets = account.get("rate_limits") or []
    fallback = buckets[0] if len(buckets) == 1 else {}
    bucket = next((b for b in buckets if b.get("limit_id") == "codex"), fallback)
    windows = {}
    for key in ("primary_limit", "secondary_limit"):
        window = bucket.get(key) or {}
        if window.get("used_percent") is not None:
            windows[window.get("window_minutes")] = window
    for minutes, label in ((300, "5h"), (10080, "7d")):
        if minutes in windows:
            window = windows[minutes]
            yield Limit(label, window["used_percent"], window.get("resets_at"))


def snapshot(state):
    thread = state.get("thread") or {}
    cwd = (thread.get("workspace") or {}).get("cwd")
    model = thread.get("model") or {}
    if not cwd or not model:
        return None
    effort = model.get("reasoning_level")
    usage = thread.get("usage") or {}
    return Snapshot(
        client="codex", cwd=Path(cwd), project_dir=Path(cwd),
        model=model_name(model), effort=EFFORT.get(effort, effort),
        context_used=(usage.get("context") or {}).get("used_percentage"),
        limits=tuple(rate_limits(state.get("account") or {})),
    )


def respond(method, params):
    if method == "initialize":
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "claude-footer", "version": "1.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [TOOL]}
    if method == "tools/call":
        if params.get("name") != TOOL["name"]:
            raise ValueError("Unknown tool name")
        return {
            "content": [{"type": "text", "text": f"The statusline resource is {URI}."}]
        }
    if method == "resources/list":
        return {
            "resources": [
                {"name": "footer", "uri": URI, "mimeType": "application/json"}
            ]
        }
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    if method == "resources/read":
        if params.get("uri") != URI:
            raise ValueError("Unknown resource URI")
        state = snapshot(params.get("_meta", {}).get("com.openai/codex-statusline-state", {}))
        return {
            "contents": [
                {
                    "uri": URI,
                    "mimeType": "application/json",
                    "text": json.dumps(render(state) if state else None, ensure_ascii=False),
                }
            ]
        }
    raise KeyError(method)


def main():
    for line in sys.stdin.buffer:
        reply = {"jsonrpc": "2.0", "id": None}
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or not isinstance(
                request.get("method"), str
            ):
                reply["error"] = {"code": -32600, "message": "Invalid request"}
            elif "id" not in request:
                continue
            else:
                reply["id"] = request["id"]
                reply["result"] = respond(request["method"], request.get("params", {}))
        except json.JSONDecodeError:
            reply["error"] = {"code": -32700, "message": "Parse error"}
        except KeyError:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        except (TypeError, ValueError, AttributeError):
            reply["error"] = {"code": -32602, "message": "Invalid parameters"}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
