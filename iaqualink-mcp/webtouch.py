"""
WebTouch API client for iAquaLink.

The WebTouch protocol is used by the iAquaLink web interface to send
raw serial commands to the AquaLink RS controller. This gives access
to features not available through the mobile REST API, such as
AquaPure chlorinator control.

Command flow:
  1. GET /v2/webtouch/init?actionID=<id> → returns action IDs
  2. POST /v2/webtouch/command with {"actionID": "<id>", "command": "<num>", "dt": "<ts>"}

Screen navigation (command numbers):
  - Home screen nav bar: Home=1, Menu=2, OneTouch=3, Help=4, Back=5, Status=6
  - Menu items use formula: command = 17 + button_index
  - Set AquaPure = command 25 (Menu button index 8)
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://prm.iaqualink.net/v2/webtouch"

# Navigation commands (bottom nav bar)
CMD_HOME = 1
CMD_MENU = 2
CMD_ONETOUCH = 3
CMD_HELP = 4
CMD_BACK = 5
CMD_STATUS = 6

# Menu screen button commands (17 + button_index)
CMD_MENU_SET_AQUAPURE = 25  # button index 8


class WebTouchClient:
    """Client for the iAquaLink WebTouch API."""

    def __init__(self, action_id: str, id_token: str):
        self.action_id = action_id
        self.id_token = id_token
        self.master_id: str | None = None
        self.master_start: str | None = None
        self.master_stb: str | None = None
        self._http = httpx.AsyncClient(timeout=15)
        self._initialized = False

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": self.id_token,
            "Content-Type": "application/json",
        }

    async def init(self) -> dict:
        """Initialize the WebTouch session and get action IDs."""
        r = await self._http.get(
            f"{API_BASE}/init",
            params={"actionID": self.action_id},
            headers=self._headers,
        )
        r.raise_for_status()
        data = r.json()

        self.master_id = data["actionIdMasterId"]
        self.master_start = data["actionIdMasterStart"]
        self.master_stb = data.get("actionIdMasterSTB")
        self._initialized = True

        logger.info("WebTouch initialized: %s", data.get("label", "unknown"))
        return data

    async def send_command(self, action_id: str, command: int) -> httpx.Response:
        """Send a command to the WebTouch API."""
        body = {
            "actionID": action_id,
            "command": str(command),
            "dt": str(int(time.time() * 1000)),
        }
        r = await self._http.post(
            f"{API_BASE}/command",
            json=body,
            headers=self._headers,
        )
        r.raise_for_status()
        return r

    async def _ensure_init(self):
        if not self._initialized:
            await self.init()

    async def go_home(self):
        """Navigate to the home screen."""
        await self._ensure_init()
        await self.send_command(self.master_start, CMD_HOME)
        await asyncio.sleep(2)

    async def go_menu(self):
        """Navigate to the menu screen."""
        await self._ensure_init()
        await self.send_command(self.master_id, CMD_MENU)
        await asyncio.sleep(1.5)

    async def go_back(self):
        """Press the Back button."""
        await self._ensure_init()
        await self.send_command(self.master_id, CMD_BACK)
        await asyncio.sleep(1)

    async def navigate_to_aquapure(self):
        """Navigate from wherever we are to the Set AquaPure screen.

        Sends: Home → Menu → Set AquaPure
        """
        await self.go_home()
        await self.go_menu()
        await self.send_command(self.master_id, CMD_MENU_SET_AQUAPURE)
        await asyncio.sleep(1.5)

    async def press_button(self, button_index: int):
        """Press a dynamic button on the current screen.

        Button commands use the formula: command = 17 + button_index
        """
        await self._ensure_init()
        command = 17 + button_index
        await self.send_command(self.master_id, command)
        await asyncio.sleep(1)

    async def close(self):
        await self._http.aclose()
