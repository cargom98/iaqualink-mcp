# iAquaLink MCP Server

An MCP (Model Context Protocol) server that connects your Jandy iAquaLink pool/spa system to AI assistants like Kiro, Claude, and others.

## Features

- **System Discovery** — List all pool/spa systems on your account
- **Device Status** — View temperatures, heater states, pump status, and more
- **Device Control** — Turn devices on/off, set temperatures, toggle lights
- **System Overview** — Get a full status dashboard in one call

## Prerequisites

- Python 3.12+
- An iAquaLink account (the same credentials you use in the iAquaLink app)
- `uv` package manager (recommended) or `pip`

## Installation

```bash
cd iaqualink-mcp
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

## Configuration

Set your iAquaLink credentials as environment variables:

```bash
export IAQUALINK_USERNAME="your-email@example.com"
export IAQUALINK_PASSWORD="your-password"
```

## Running the Server

```bash
uv run python server.py
```

## Adding to Kiro

Add this to your `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "iaqualink": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "/absolute/path/to/iaqualink-mcp",
      "env": {
        "IAQUALINK_USERNAME": "your-email@example.com",
        "IAQUALINK_PASSWORD": "your-password"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_systems` | List all pool/spa systems on your account |
| `get_system_status` | Get full status overview for a system |
| `list_devices` | List all devices for a system |
| `get_device` | Get details for a specific device |
| `turn_on_device` | Turn on a device (pump, heater, aux, etc.) |
| `turn_off_device` | Turn off a device |
| `toggle_device` | Toggle a device on/off |
| `set_temperature` | Set a thermostat target temperature |

## Example Prompts

Once connected, you can ask your AI assistant things like:

- "What's my pool temperature?"
- "Turn on the spa heater"
- "Set the spa temperature to 102"
- "Show me the full status of my pool system"
- "Turn off the pool pump"
- "Toggle the pool light"
