# Deployment Guide

## Local Process

### Install

```bash
cd /path/to/WebControl
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

### Run

```bash
# Default (port 8080, headless)
webcontrol serve

# Custom port
webcontrol serve --port 9000

# With auth and proxy
WC_API_KEY="my-secret" WC_PROXY_SERVER="http://proxy:8080" webcontrol serve

# JSON logs for production
WC_LOG_JSON=true WC_LOG_LEVEL=INFO webcontrol serve
```

### Run as Background Service (macOS launchd)

Create `~/Library/LaunchAgents/com.webcontrol.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.webcontrol</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/WebControl/.venv/bin/webcontrol</string>
        <string>serve</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>WC_LOG_JSON</key>
        <string>true</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/webcontrol.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/webcontrol.err</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.webcontrol.plist
```

---

## Docker

### Build and Run

```bash
# Using docker compose
docker compose up --build

# Or manually
docker build -t webcontrol .
docker run -p 8080:8080 -e WC_LOG_JSON=true webcontrol
```

### Docker Compose Configuration

```yaml
services:
  webcontrol:
    build: .
    ports:
      - "8080:8080"
    environment:
      - WC_HEADLESS=true
      - WC_MAX_SESSIONS=10
      - WC_LOG_JSON=true
      - WC_API_KEY=your-secret-key
    restart: unless-stopped
    # Resource limits (recommended for production)
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"
```

### Health Checks

The container includes a built-in healthcheck hitting `/health`. Docker will report the container as healthy/unhealthy automatically.

External monitoring:

```bash
curl -f http://localhost:8080/health || echo "DOWN"
```

---

## Environment Variables Quick Reference

| Variable | Production Recommendation |
|----------|--------------------------|
| `WC_HEADLESS` | `true` (always in containers) |
| `WC_API_KEY` | Set a strong random key |
| `WC_MAX_SESSIONS` | Size based on available RAM (~200MB per session) |
| `WC_DEFAULT_SESSION_TTL_SECONDS` | Lower for shared environments (300-600) |
| `WC_LOG_JSON` | `true` for structured log aggregation |
| `WC_LOG_LEVEL` | `INFO` for production, `DEBUG` for troubleshooting |
| `WC_NAVIGATION_RETRIES` | `2-3` for unreliable networks |
| `WC_NAVIGATION_TIMEOUT_MS` | Increase for slow sites (45000-60000) |

---

## Resource Planning

Each browser session consumes approximately:
- **Memory:** 100-300 MB (depends on page complexity)
- **CPU:** Minimal when idle; spikes during navigation and rendering

**Guidelines:**
- 2 GB RAM → ~10 concurrent sessions comfortably
- 4 GB RAM → ~20 concurrent sessions
- Set `WC_MAX_SESSIONS` to match your available memory

---

## Security Considerations

### Network

- Run behind a reverse proxy (nginx, Caddy) if exposed to the internet
- Use HTTPS termination at the proxy level
- Restrict access by IP or VPN when possible

### Authentication

- Always set `WC_API_KEY` in shared or production environments
- Rotate keys periodically
- The MCP stdio transport bypasses HTTP auth (it runs locally as a subprocess)

### Browser Sandbox

Playwright's Chromium runs with sandboxing enabled by default. In Docker, the container already provides process isolation.

### Session Cleanup

- Sessions auto-expire after `WC_DEFAULT_SESSION_TTL_SECONDS` of inactivity
- The cleanup loop runs every 60 seconds
- On shutdown, all sessions are closed gracefully
