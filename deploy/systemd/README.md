# Running the Axocare agent with systemd

Axocare has two related processes with different lifecycles:

- The FastAPI application is a long-running service. Its `/api/agent/chat` and
  `/api/agent/chat/stream` routes are the network-facing agent endpoints.
- The MCP server uses standard input/output. The agent starts a private MCP
  subprocess for each request and closes it afterward. It is not a standalone
  network daemon and normally should not be enabled as a systemd service.

This is the recommended arrangement because it keeps the SQLite database and
MCP protocol off the network. Only the API (or an NGINX proxy in front of it)
is reachable by dashboard clients.

## Prerequisites

The examples assume the repository is `/home/pi/axocare`, its virtual
environment is `/home/pi/axocare/.venv`, and the service account is `pi`.
Change all three consistently if your installation differs.

Install the application first:

```bash
cd /home/pi/axocare
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
test -r /home/pi/axocare/axocare.db
```

The configured model must support OpenAI-style tool calls. If the provider is
local (for example, listening on `127.0.0.1:11434`), make sure its service is
running before testing Axocare.

## Install the agent/API service

Copy the samples and protect the environment file, which may contain an API
key:

```bash
sudo install -d -m 0750 -o root -g pi /etc/axocare
sudo install -m 0644 deploy/systemd/axocare-agent.service.example \
  /etc/systemd/system/axocare-agent.service
sudo install -m 0640 -o root -g pi deploy/systemd/axocare-agent.env.example \
  /etc/axocare/agent.env
sudoedit /etc/axocare/agent.env
```

Validate and start it:

```bash
sudo systemd-analyze verify /etc/systemd/system/axocare-agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now axocare-agent.service
sudo systemctl status axocare-agent.service
journalctl -u axocare-agent.service -f
```

The sample binds to `127.0.0.1:8000`, which is appropriate when NGINX runs on
the same host. Change it to `0.0.0.0` only when the API must be reached directly
and the host firewall and network are trusted.

Test the agent through the API:

```bash
curl --fail-with-body \
  -H 'Content-Type: application/json' \
  -d '{"question":"How is the aquarium right now?","history":[]}' \
  http://127.0.0.1:8000/api/agent/chat
```

## MCP server lifecycle

No separate MCP unit is required by `axocare-agent.service`. The agent uses the
Python interpreter from its virtual environment to run:

```bash
/home/pi/axocare/.venv/bin/python -m mcp_server.server \
  --db /home/pi/axocare/axocare.db
```

For another local MCP client, configure that command directly. The client must
own stdin and stdout, and stdout must remain reserved for MCP messages.

`axocare-mcp@.service.example` is included only as a starting point for a local
systemd socket or protocol bridge that explicitly owns the service's stdin and
stdout. It has no install target and must not be enabled at boot. Starting it
with ordinary `systemctl start` does not create a usable MCP connection.

If a persistent, independently addressable MCP service is needed, add an MCP
HTTP transport and authentication first; do not expose the raw stdio process
with a generic TCP relay.

## Updates and troubleshooting

After updating Python dependencies or application code:

```bash
cd /home/pi/axocare
.venv/bin/pip install -r requirements.txt
sudo systemctl restart axocare-agent.service
```

Common failures are visible in the journal. In particular, verify that the
database is readable by `pi`, the provider URL is reachable from the host, and
the selected model supports tool calling. To test the two layers separately:

```bash
sudo -u pi /home/pi/axocare/.venv/bin/python -m mcp_server.server \
  --db /home/pi/axocare/axocare.db

sudo -u pi --preserve-env=AXOCARE_AGENT_BASE_URL,AXOCARE_AGENT_MODEL \
  /home/pi/axocare/.venv/bin/python -m axocare_agent.cli \
  --db /home/pi/axocare/axocare.db \
  --question 'How is the aquarium right now?'
```

The MCP command waits for protocol input, so `Ctrl-C` after confirming it
starts without an import or database error.
