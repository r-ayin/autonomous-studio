---
name: port-mapping
description: Get the public URL for a local container port. Use when the user wants to access a service running on a specific port from outside the container, or needs to share a public URL for a local port.
allowed-tools: Bash
repository: https://code.alibaba-inc.com/qunbu/port-mapping
version: 1.0.0
---

# Port Mapping - Get Public URL for Container Port

This skill retrieves the public-facing URL mapped to a given port inside the current Cloud CLI container.

## How It Works

The Cloud CLI server exposes a localhost-only API at `GET /api/port-mapping?port=<port>`.

## Usage

To get the public URL for a port, run:

```bash
curl -s "http://localhost:58596/api/port-mapping?port=<PORT>" | jq .
```

Replace `<PORT>` with the actual port number (e.g., 8080, 3000, 5173).

## Response Format

Success:
```json
{
  "success": true,
  "port": 8080,
  "host": "xxxxxx-sandbox-sessionxxxxx-8080.agent.alibaba-inc.com",
  "url": "https://xxxxxx-sandbox-sessionxxxxx-8080.agent.alibaba-inc.com"
}
```

The `url` field is the public HTTPS URL that maps to the container's local port.

## Error Cases

- Missing port parameter: 400
- Server token not configured: 500
- No active session found: 404
- Session not running: 409

## Example

User asks: "How do I access my dev server on port 3000 from outside?"

```bash
curl -s "http://localhost:58596/api/port-mapping?port=3000" | jq -r .url
```

This returns a URL like `https://abc123-sandbox-session456-3000.agent.alibaba-inc.com` that can be opened in a browser.
