"""
iAquaLink MCP Server

Connects your Jandy iAquaLink pool/spa system to AI assistants
via the Model Context Protocol.
"""

import asyncio
import os
import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the workspace root (one level up from this server file)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

from mcp.server.fastmcp import FastMCP, Context

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem
from iaqualink.device import (
    AqualinkDevice,
    AqualinkThermostat,
    AqualinkSwitch,
    AqualinkLight,
    AqualinkSensor,
)

from webtouch import WebTouchClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan: manage the AqualinkClient session
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Create and manage the iAquaLink client session."""
    username = os.environ.get("IAQUALINK_USERNAME", "")
    password = os.environ.get("IAQUALINK_PASSWORD", "")

    if not username or not password:
        logger.error(
            "IAQUALINK_USERNAME and IAQUALINK_PASSWORD environment variables are required"
        )
        yield {"client": None}
        return

    client = AqualinkClient(username, password)
    try:
        await client.login()
        logger.info("Connected to iAquaLink as %s", username)

        # WebTouch action ID for AquaPure and other advanced controls
        action_id = os.environ.get("IAQUALINK_ACTION_ID", "")

        yield {
            "client": client,
            "id_token": client.id_token,
            "action_id": action_id,
        }
    finally:
        await client.close()
        logger.info("Disconnected from iAquaLink")


# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "iAquaLink",
    instructions="Control your Jandy iAquaLink pool and spa system",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_client(ctx: Context) -> AqualinkClient:
    """Extract the AqualinkClient from the lifespan context."""
    client = ctx.request_context.lifespan_context.get("client")
    if client is None:
        raise RuntimeError(
            "iAquaLink client is not connected. "
            "Make sure IAQUALINK_USERNAME and IAQUALINK_PASSWORD are set."
        )
    return client


async def _resolve_system(
    ctx: Context, system_serial: str | None = None
) -> AqualinkSystem:
    """Resolve a system by serial, or return the first one if only one exists."""
    client = await _get_client(ctx)
    systems = await client.get_systems()

    if not systems:
        raise ValueError("No iAquaLink systems found on this account.")

    if system_serial:
        if system_serial not in systems:
            available = ", ".join(systems.keys())
            raise ValueError(
                f"System '{system_serial}' not found. Available: {available}"
            )
        return systems[system_serial]

    # If there's only one system, use it automatically
    if len(systems) == 1:
        return list(systems.values())[0]

    available = ", ".join(
        f"{s.name} ({serial})" for serial, s in systems.items()
    )
    raise ValueError(
        f"Multiple systems found. Please specify system_serial. "
        f"Available: {available}"
    )


def _device_info(device: AqualinkDevice) -> dict:
    """Build a summary dict for a device."""
    info = {
        "name": device.label,
        "key": device.name,
        "state": device.state,
    }

    if isinstance(device, AqualinkThermostat):
        info["type"] = "thermostat"
        info["is_on"] = device.is_on
        info["target_temperature"] = device.target_temperature
    elif isinstance(device, AqualinkLight):
        info["type"] = "light"
        info["is_on"] = device.is_on
    elif isinstance(device, AqualinkSwitch):
        info["type"] = "switch"
        info["is_on"] = device.is_on
    elif isinstance(device, AqualinkSensor):
        info["type"] = "sensor"
    else:
        info["type"] = "device"

    return info


async def _get_webtouch(ctx: Context) -> WebTouchClient:
    """Create a WebTouch client from the lifespan context."""
    lc = ctx.request_context.lifespan_context
    action_id = lc.get("action_id")
    id_token = lc.get("id_token")

    if not action_id:
        raise RuntimeError(
            "IAQUALINK_ACTION_ID is not set. "
            "You can find it in the URL when you open your system "
            "from the iAquaLink Owner's Center web interface."
        )
    if not id_token:
        raise RuntimeError("iAquaLink client is not connected.")

    wt = WebTouchClient(action_id, id_token)
    await wt.init()
    return wt


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_systems(ctx: Context) -> str:
    """List all iAquaLink pool/spa systems on your account.

    Returns the name, serial number, and online status of each system.
    """
    client = await _get_client(ctx)
    systems = await client.get_systems()

    if not systems:
        return "No iAquaLink systems found on this account."

    lines = []
    for serial, system in systems.items():
        if system.online is None:
            status = "unknown"
        elif system.online:
            status = "online"
        else:
            status = "offline"
        lines.append(f"• {system.name} (serial: {serial}) — {status}")

    return "Systems found:\n" + "\n".join(lines)


@mcp.tool()
async def get_system_status(ctx: Context, system_serial: str | None = None) -> str:
    """Get a full status overview of a pool/spa system.

    Shows temperatures, heater states, pump status, and all device states.
    If you only have one system, system_serial is optional.

    Args:
        system_serial: Serial number of the system (optional if only one system).
    """
    system = await _resolve_system(ctx, system_serial)
    await system.update()
    devices = await system.get_devices()

    online_str = "online" if system.online else ("offline" if system.online is False else "unknown")
    lines = [f"System: {system.name}"]
    lines.append(f"Status: {online_str}")
    lines.append("")

    # Group devices by type
    temps = []
    thermostats = []
    switches = []
    lights = []
    others = []

    for device in devices.values():
        info = _device_info(device)
        if isinstance(device, AqualinkSensor) and "temp" in device.name:
            temps.append(info)
        elif isinstance(device, AqualinkThermostat):
            thermostats.append(info)
        elif isinstance(device, AqualinkLight):
            lights.append(info)
        elif isinstance(device, AqualinkSwitch):
            switches.append(info)
        else:
            others.append(info)

    if temps:
        lines.append("🌡️  Temperatures:")
        for t in temps:
            lines.append(f"   {t['name']}: {t['state']}°")

    if thermostats:
        lines.append("\n🎯 Thermostats:")
        for t in thermostats:
            on_str = "ON" if t.get("is_on") else "OFF"
            lines.append(
                f"   {t['name']} ({t['key']}): {on_str}, target {t.get('target_temperature', '?')}°"
            )

    if switches:
        lines.append("\n⚙️  Switches:")
        for s in switches:
            on_str = "ON" if s.get("is_on") else "OFF"
            lines.append(f"   {s['name']} ({s['key']}): {on_str}")

    if lights:
        lines.append("\n💡 Lights:")
        for l in lights:
            on_str = "ON" if l.get("is_on") else "OFF"
            lines.append(f"   {l['name']} ({l['key']}): {on_str}")

    if others:
        lines.append("\n📋 Other Devices:")
        for o in others:
            lines.append(f"   {o['name']} ({o['key']}): {o['state']}")

    return "\n".join(lines)


@mcp.tool()
async def list_devices(ctx: Context, system_serial: str | None = None) -> str:
    """List all devices for a pool/spa system.

    Args:
        system_serial: Serial number of the system (optional if only one system).
    """
    system = await _resolve_system(ctx, system_serial)
    devices = await system.get_devices()

    if not devices:
        return "No devices found."

    lines = []
    for device in devices.values():
        info = _device_info(device)
        lines.append(
            f"• {info['name']} (key: {info['key']}, type: {info['type']}, state: {info['state']})"
        )

    return f"Devices for {system.name}:\n" + "\n".join(lines)


@mcp.tool()
async def get_device(
    ctx: Context, device_key: str, system_serial: str | None = None
) -> str:
    """Get detailed information about a specific device.

    Args:
        device_key: The device key (e.g. 'pool_temp', 'spa_heater', 'aux_1').
        system_serial: Serial number of the system (optional if only one system).
    """
    system = await _resolve_system(ctx, system_serial)
    devices = await system.get_devices()

    device = devices.get(device_key)
    if not device:
        available = ", ".join(devices.keys())
        return f"Device '{device_key}' not found. Available devices: {available}"

    info = _device_info(device)
    lines = [f"Device: {info['name']}"]
    lines.append(f"Key: {info['key']}")
    lines.append(f"Type: {info['type']}")
    lines.append(f"State: {info['state']}")

    if "is_on" in info:
        lines.append(f"Is On: {info['is_on']}")
    if "target_temperature" in info:
        lines.append(f"Target Temperature: {info['target_temperature']}°")

    return "\n".join(lines)


@mcp.tool()
async def turn_on_device(
    ctx: Context, device_key: str, system_serial: str | None = None
) -> str:
    """Turn on a pool/spa device.

    Works with pumps, heaters, auxiliary switches, lights, and other controllable devices.

    Args:
        device_key: The device key (e.g. 'pool_pump', 'spa_heater', 'aux_1').
        system_serial: Serial number of the system (optional if only one system).
    """
    system = await _resolve_system(ctx, system_serial)
    devices = await system.get_devices()

    device = devices.get(device_key)
    if not device:
        available = ", ".join(devices.keys())
        return f"Device '{device_key}' not found. Available devices: {available}"

    if not isinstance(device, (AqualinkSwitch, AqualinkLight, AqualinkThermostat)):
        return f"Device '{device_key}' ({device.label}) is not a controllable device."

    await device.turn_on()
    return f"✅ Turned ON: {device.label} ({device_key})"


@mcp.tool()
async def turn_off_device(
    ctx: Context, device_key: str, system_serial: str | None = None
) -> str:
    """Turn off a pool/spa device.

    Works with pumps, heaters, auxiliary switches, lights, and other controllable devices.

    Args:
        device_key: The device key (e.g. 'pool_pump', 'spa_heater', 'aux_1').
        system_serial: Serial number of the system (optional if only one system).
    """
    system = await _resolve_system(ctx, system_serial)
    devices = await system.get_devices()

    device = devices.get(device_key)
    if not device:
        available = ", ".join(devices.keys())
        return f"Device '{device_key}' not found. Available devices: {available}"

    if not isinstance(device, (AqualinkSwitch, AqualinkLight, AqualinkThermostat)):
        return f"Device '{device_key}' ({device.label}) is not a controllable device."

    await device.turn_off()
    return f"✅ Turned OFF: {device.label} ({device_key})"


@mcp.tool()
async def toggle_device(
    ctx: Context, device_key: str, system_serial: str | None = None
) -> str:
    """Toggle a pool/spa device on or off.

    Useful for lights and other devices where you want to flip the current state.

    Args:
        device_key: The device key (e.g. 'aux_3' for a light).
        system_serial: Serial number of the system (optional if only one system).
    """
    system = await _resolve_system(ctx, system_serial)
    devices = await system.get_devices()

    device = devices.get(device_key)
    if not device:
        available = ", ".join(devices.keys())
        return f"Device '{device_key}' not found. Available devices: {available}"

    if not isinstance(device, (AqualinkSwitch, AqualinkLight, AqualinkThermostat)):
        return f"Device '{device_key}' ({device.label}) is not a toggleable device."

    if device.is_on:
        await device.turn_off()
        new_state = "OFF"
    else:
        await device.turn_on()
        new_state = "ON"

    return f"✅ Toggled {device.label} ({device_key}) → now {new_state}"


@mcp.tool()
async def set_temperature(
    ctx: Context,
    device_key: str,
    temperature: int,
    system_serial: str | None = None,
) -> str:
    """Set the target temperature for a thermostat.

    Common thermostat keys are 'pool_set_point' and 'spa_set_point'.

    Args:
        device_key: The thermostat device key (e.g. 'spa_set_point', 'pool_set_point').
        temperature: Target temperature in degrees (typically Fahrenheit).
        system_serial: Serial number of the system (optional if only one system).
    """
    system = await _resolve_system(ctx, system_serial)
    devices = await system.get_devices()

    device = devices.get(device_key)
    if not device:
        available = ", ".join(devices.keys())
        return f"Device '{device_key}' not found. Available devices: {available}"

    if not isinstance(device, AqualinkThermostat):
        return f"Device '{device_key}' ({device.label}) is not a thermostat."

    await device.set_temperature(temperature)
    return f"✅ Set {device.label} ({device_key}) to {temperature}°"


# ---------------------------------------------------------------------------
# AquaPure tools (via WebTouch protocol)
# ---------------------------------------------------------------------------


@mcp.tool()
async def set_aquapure(ctx: Context, percentage: int) -> str:
    """Set the AquaPure chlorine production percentage.

    Navigates through the WebTouch interface to the Set AquaPure screen
    and enters the desired production percentage.

    Args:
        percentage: Chlorine production level (0-100).
    """
    if not 0 <= percentage <= 100:
        return f"Invalid percentage: {percentage}. Must be between 0 and 100."

    wt = await _get_webtouch(ctx)
    try:
        # Navigate: Home → Menu → Set AquaPure
        await wt.navigate_to_aquapure()

        # On the Set Chlorine Production screen (screen 48):
        # Button 0 = current pool %, Button 1 = current spa %
        # Button 2 = "Set Pool %" (clickable), Button 3 = "Set Spa %"
        # The keypad is on the right side for entering values.
        # Press button 2 to select "Set Pool %" then enter the number

        # Press "Set Pool %" button (index 2)
        await wt.press_button(2)

        # Enter the percentage digits via keypad
        for digit in str(percentage):
            body = {
                "actionID": wt.master_stb,
                "command": "128",
                "text": digit,
                "dt": str(int(time.time() * 1000)),
            }
            await wt._http.post(
                "https://prm.iaqualink.net/v2/webtouch/command",
                json=body,
                headers=wt._headers,
            )
            await asyncio.sleep(0.5)

        # Press Enter to confirm
        body = {
            "actionID": wt.master_stb,
            "command": "128",
            "text": "enter",
            "dt": str(int(time.time() * 1000)),
        }
        await wt._http.post(
            "https://prm.iaqualink.net/v2/webtouch/command",
            json=body,
            headers=wt._headers,
        )
        await asyncio.sleep(1)

        # Go back to home
        await wt.go_home()

        return f"✅ Set AquaPure chlorine production to {percentage}%"
    finally:
        await wt.close()


@mcp.tool()
async def boost_aquapure(ctx: Context) -> str:
    """Activate the AquaPure boost (super chlorinate) mode.

    This navigates through the WebTouch interface to trigger
    the AquaPure boost function, which runs the chlorinator
    at maximum output for 24 hours.
    """
    wt = await _get_webtouch(ctx)
    try:
        # Navigate: Home → Menu → Set AquaPure
        await wt.navigate_to_aquapure()

        # On the Set Chlorine Production screen (screen 48):
        # Button 3 = "Boost" option (dynamic-ot-med at index 3)
        await wt.press_button(3)

        # On the AquaPure Boost screen (screen 63):
        # Button 0 = first option (e.g. "Start Boost" or hours display)
        # Button 1 = second option
        # Button 2 = third option
        # Typically button 0 is "Start Boost" or "Enable"
        await wt.press_button(0)

        await asyncio.sleep(1)

        # Go back to home
        await wt.go_home()

        return "✅ AquaPure boost mode activated (super chlorinate for 24 hours)"
    finally:
        await wt.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
