# Connecting an AI pilot (Claude, ChatGPT/Codex, Gemini, others)

The simulator server owns the MuJoCo engine and the flight. An AI pilot is any assistant that can read
`GET /api/observe` and send `POST /api/action` to that server. This is how Colin's sessions flew the R6 and the
Phantom: the assistant's own app handles speech; the assistant observes, decides, commands and reads telemetry back.

`tools/vtx_pilot_mcp.py` exposes that same interface as Model Context Protocol tools, so an assistant can fly in
conversation without writing scripts. It holds no aircraft state and starts no simulator.

| Tool | Simulator endpoint |
|---|---|
| `vtx_status` | `/api/view`, `/api/identity` |
| `vtx_observe` | `/api/observe` |
| `vtx_take_seat` | `/api/pilot/handover` (run-scoped; the previous pilot is fenced off) |
| `vtx_command` | `/api/action` (phantom-fbw-1), then `/api/observe` |
| `vtx_instruct` | `/api/pilot/command` |
| `vtx_set_objective` | `/api/objective` |

## Set-up on the PC

Start the simulator, then register the connector with the assistant. The command is the same for each client:

```text
command: C:\Users\steve\Documents\Github\-vtx-flight-sim\.venv\Scripts\python.exe
args:    C:\Users\steve\Documents\Github\vtx-three-panel-20261110\tools\vtx_pilot_mcp.py
env:     VTX_LAB_URL=http://127.0.0.1:18911      (the port the simulator is running on)
```

* Claude Code: `claude mcp add vtx-pilot --env VTX_LAB_URL=http://127.0.0.1:18911 -- <python> <path>\tools\vtx_pilot_mcp.py`
* Claude Desktop, Codex CLI and Gemini CLI: add the same command, args and env to their MCP server settings.

An assistant running on the PC reaches `127.0.0.1` directly. An assistant running in the cloud or on a phone needs
the simulator reachable over HTTPS with `VTX_CLOUD_ACCESS_TOKEN` set on both sides (see `R6_MOBILE_RUNTIME.md`).

## Rules the connector keeps

* Authority, run ID, pilot ownership and schema checks are the server's own; a refused command returns the server's reason.
* The simulator holds the last accepted command, so the aircraft keeps flying while the conversation continues or reconnects.
* Every decision is recorded in the flight's `events.jsonl` with its reason and the observation it used.
