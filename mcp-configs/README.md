# MCP Configuration Examples

## Claude Desktop

Copy `claude-desktop.json` content into your Claude Desktop config at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Cursor

Copy `cursor.json` content into `.cursor/mcp.json` in your project root.

## Claude Code

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "webcontrol": {
      "command": "webcontrol",
      "args": ["mcp-stdio"]
    }
  }
}
```

## HTTP Transport (for custom agents)

If running as an HTTP server (`webcontrol serve`), connect your MCP client to:

```
http://localhost:8080/mcp
```

If API key auth is enabled, pass it via the `x-api-key` header.
