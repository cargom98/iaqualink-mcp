# iAquaLink MCP Server

An [MCP](https://modelcontextprotocol.io/) server that lets AI assistants control your Jandy iAquaLink pool and spa system. Works with [Kiro](https://kiro.dev), Claude Desktop, and any MCP-compatible client.

Built on the [iaqualink](https://github.com/flz/iaqualink-py) Python library for the standard device API, plus a custom WebTouch protocol integration for AquaPure chlorinator control.

## What It Does

- **Monitor** — pool/spa temperatures, equipment status, system health
- **Control** — pumps, heaters, lights, auxiliary switches, thermostats
- **AquaPure** — set chlorine production percentage, activate boost/super chlorinate

## Available Tools

| Tool | Description |
|------|-------------|
| `list_systems` | List all pool/spa systems on your account |
| `get_system_status` | Full dashboard with temps, heaters, pumps, and all devices |
| `list_devices` | List every device with its key, type, and current state |
| `get_device` | Detailed info on a specific device |
| `turn_on_device` | Turn on a pump, heater, switch, or light |
| `turn_off_device` | Turn off a device |
| `toggle_device` | Flip a device's current state |
| `set_temperature` | Set pool or spa thermostat target temperature |
| `set_aquapure` | Set AquaPure chlorine production (0–100%) |
| `boost_aquapure` | Activate AquaPure boost (super chlorinate for 24 hours) |

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** package manager (recommended)
- **iAquaLink account** — the same email and password you use in the iAquaLink mobile app

## Installation

```bash
git clone https://github.com/cargom98/iaqualink-mcp.git
cd iaqualink-mcp/iaqualink-mcp
uv sync --no-install-project
```

## Configuration

### 1. Create a `.env` file

Create a `.env` file in the **repo root** (one level above the `iaqualink-mcp/` folder):

```
IAQUALINK_USERNAME=your-email@example.com
IAQUALINK_PASSWORD=your-password
IAQUALINK_ACTION_ID=your-action-id
```

| Variable | Required | Description |
|----------|----------|-------------|
| `IAQUALINK_USERNAME` | Yes | Your iAquaLink account email |
| `IAQUALINK_PASSWORD` | Yes | Your iAquaLink account password |
| `IAQUALINK_ACTION_ID` | For AquaPure tools only | WebTouch action ID (see below) |

### 2. Find your Action ID (for AquaPure)

The `set_aquapure` and `boost_aquapure` tools use the WebTouch protocol, which requires an action ID specific to your system. To find it:

1. Log in at [iaqualink.zodiacpoolsystems.com](https://iaqualink.zodiacpoolsystems.com/signin)
2. Click on your system name (e.g. "SPOOL")
3. A new tab opens to `webtouch.iaqualink.net`. Look at the URL — the `actionID` parameter is your action ID:
   ```
   https://webtouch.iaqualink.net/?actionID=YOUR_ACTION_ID&idToken=...
   ```
4. Copy the `actionID` value into your `.env` file

If you don't need AquaPure control, you can skip this — all other tools work without it.

## Running the Server

```bash
cd iaqualink-mcp
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
      "cwd": "/absolute/path/to/iaqualink-mcp/iaqualink-mcp",
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

The server reads credentials from the `.env` file automatically — no need to put them in the MCP config.

## Adding to Claude Desktop

Add this to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "iaqualink": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "/absolute/path/to/iaqualink-mcp/iaqualink-mcp"
    }
  }
}
```

## Example Prompts

Once connected, you can ask your AI assistant things like:

- "What's my pool temperature?"
- "Show me the full status of my pool system"
- "Turn on the spa heater and set it to 102"
- "Toggle the pool light"
- "Set the AquaPure to 75%"
- "Activate AquaPure boost"
- "Turn off the pool pump"
- "What devices are on right now?"

## How It Works

The server uses two communication channels with your iAquaLink system:

**Mobile REST API** (`iaqualink` library) — handles system discovery, device status, and standard controls like pumps, heaters, lights, and thermostats. This is the same API the iAquaLink mobile app uses.

**WebTouch Protocol** (custom `webtouch.py` module) — handles AquaPure chlorinator control by sending commands through the same interface as the iAquaLink web portal. This works by navigating the controller's menu system programmatically (Home → Menu → Set AquaPure → enter value).

If you only have one system on your account, you never need to specify a serial number — the server picks it up automatically.

## Supported Systems

This server works with **iAqua** systems (AquaLink RS controllers with iAquaLink 2.0/3.0 Wi-Fi modules). It supports:

- Temperature sensors (pool, spa, air)
- Thermostats with adjustable set points
- Pumps (pool, spa, variable speed)
- Heaters (pool, spa, solar)
- Lights
- Auxiliary switches
- AquaPure salt chlorine generators

## Disclaimer

This is an unofficial project and is not affiliated with or endorsed by Jandy, Zodiac Pool Systems, or Fluidra. Use at your own risk.

## License

MIT
