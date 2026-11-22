"""Playwright-driven assistant bot that joins a meeting as a participant.

The bot opens the meeting link in a real (visible) Chrome window that this
process launches itself, using a **persistent profile** so a one-time Google
sign-in is remembered. It then walks the normal Google Meet guest/join flow —
"Continue as guest" → fill the name → **click "Ask to join"** — and reports its
progress so the UI can show the real state instead of a fake "joined" message.

The bot never bypasses waiting rooms, domain restrictions or host approval: it
requests admission and waits for the host to let it in, exactly like a person.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

logger = logging.getLogger(__name__)

# --- Configuration (env-overridable) --------------------------------------- #
BOT_NAME_DEFAULT = os.getenv("BOT_NAME", "AI Class Assistant")

# Google Meet blocks headless browsers, so the window must be visible.
BOT_HEADLESS = os.getenv("BOT_HEADLESS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Persistent Chrome profile: sign in to Google once and it is remembered.
# The path is always resolved to an absolute one: a relative `--user-data-dir`
# makes Chrome's crash handler fail on Windows with
# "SetEndOfFile: Access is denied", which aborts the whole launch.
_DEFAULT_PROFILE_DIR = Path(__file__).resolve().parents[2] / "data" / "bot_profile"
BOT_USER_DATA_DIR = str(
    Path(os.getenv("BOT_GOOGLE_PROFILE_DIR", str(_DEFAULT_PROFILE_DIR))).resolve()
)

# "chrome" drives the installed Google Chrome (best for Meet, native user agent).
# Set BOT_CHANNEL=msedge to use Edge, or empty to use Playwright's Chromium.
BOT_CHANNEL = os.getenv("BOT_CHANNEL", "chrome").strip()

# How long the bot waits for the host to admit it before giving up (seconds).
BOT_JOIN_TIMEOUT_SECONDS = int(os.getenv("BOT_JOIN_TIMEOUT_SECONDS", "240"))

# After admission the bot stays in the meeting until the caller stops it.
BOT_IDLE_POLL_SECONDS = 3

# Terminal / informational statuses surfaced to the UI.
STATUS_STARTING = "starting"
STATUS_OPENING = "opening"
STATUS_ACTION_REQUIRED = "action_required"
STATUS_REQUESTING = "requesting_admission"
STATUS_WAITING = "waiting_for_host"
STATUS_ADMITTED = "admitted"
STATUS_FAILED = "failed"
STATUS_STOPPED = "stopped"

# Statuses that mean the bot is still doing something (not re-startable).
_LIVE_STATUSES = {
    STATUS_STARTING,
    STATUS_OPENING,
    STATUS_ACTION_REQUIRED,
    STATUS_REQUESTING,
    STATUS_WAITING,
    STATUS_ADMITTED,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MeetingBotService:
    """Tracks one background assistant bot per meeting link."""

    def __init__(self) -> None:
        # bot_id -> status dict (also holds the asyncio.Task under "_task")
        self.active_bots: dict[str, dict] = {}

    # ------------------------------------------------------------------ #
    # Identity / status
    # ------------------------------------------------------------------ #
    @staticmethod
    def bot_id_for_link(link: str) -> str:
        digest = hashlib.sha1(link.strip().encode("utf-8")).hexdigest()[:12]
        return f"bot_{digest}"

    @staticmethod
    def _public(bot: dict) -> dict:
        return {k: v for k, v in bot.items() if not k.startswith("_")}

    def get_status(self, bot_id: str) -> dict | None:
        bot = self.active_bots.get(bot_id)
        return self._public(bot) if bot else None

    def status_for_link(self, link: str) -> dict | None:
        return self.get_status(self.bot_id_for_link(link))

    def _set(self, bot_id: str, status: str, detail: str) -> None:
        bot = self.active_bots.get(bot_id)
        if bot is not None:
            bot["status"] = status
            bot["detail"] = detail
            bot["updatedAt"] = _now_iso()
        logger.info("[%s] %s - %s", bot_id, status, detail)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def join_meeting(
        self,
        meeting_link: str,
        bot_name: str = BOT_NAME_DEFAULT,
    ) -> str:
        """Start (or reuse) a bot for the link. Returns the bot id."""
        bot_id = self.bot_id_for_link(meeting_link)

        existing = self.active_bots.get(bot_id)
        if existing and existing.get("status") in _LIVE_STATUSES:
            logger.info("Bot already active for this meeting: %s", bot_id)
            return bot_id

        self.active_bots[bot_id] = {
            "botId": bot_id,
            "link": meeting_link,
            "status": STATUS_STARTING,
            "detail": "Preparing the assistant browser…",
            "startedAt": _now_iso(),
            "updatedAt": _now_iso(),
        }

        self.active_bots[bot_id]["_task"] = asyncio.create_task(
            self._run_bot(bot_id, meeting_link, bot_name)
        )
        return bot_id

    async def stop_bot(self, bot_id: str) -> bool:
        """Signal the bot to leave and release its browser context."""
        bot = self.active_bots.get(bot_id)
        if bot is None:
            return False

        # Mark stopped first so the polling loop exits, then cancel the task.
        bot["_stopping"] = True
        self._set(bot_id, STATUS_STOPPED, "Assistant left the meeting.")

        task: asyncio.Task | None = bot.get("_task")
        if task and not task.done():
            task.cancel()

        self.active_bots.pop(bot_id, None)
        return True

    # ------------------------------------------------------------------ #
    # The actual browser automation
    # ------------------------------------------------------------------ #
    async def _run_bot(self, bot_id: str, meeting_link: str, bot_name: str) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            self._set(bot_id, STATUS_FAILED, "Playwright is not installed on the server.")
            return

        context = None
        try:
            Path(BOT_USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

            async with async_playwright() as p:
                self._set(bot_id, STATUS_STARTING, "Launching the assistant browser…")

                launch_kwargs: dict = {
                    "user_data_dir": BOT_USER_DATA_DIR,
                    "headless": BOT_HEADLESS,
                    "permissions": ["microphone", "camera"],
                    "args": [
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-blink-features=AutomationControlled",
                        # Chrome's crash handler cannot write in some locked-down
                        # Windows setups and aborts launch; turn it off.
                        "--disable-crash-reporter",
                        "--disable-breakpad",
                        "--use-fake-ui-for-media-stream",
                    ],
                }

                # Try the configured browser first, then Edge, then Playwright's
                # own Chromium — the first installed one wins.
                candidates = [BOT_CHANNEL, "msedge", None]
                context = None
                last_error: Exception | None = None
                for channel in candidates:
                    if context is not None:
                        break
                    if channel:
                        launch_kwargs["channel"] = channel
                    else:
                        launch_kwargs.pop("channel", None)
                    try:
                        context = await p.chromium.launch_persistent_context(**launch_kwargs)
                    except Exception as exc:  # noqa: BLE001 - try the next browser
                        last_error = exc
                        logger.warning("Could not launch browser channel=%r: %s", channel, exc)

                if context is None:
                    raise last_error or RuntimeError("No usable browser could be launched.")

                page = context.pages[0] if context.pages else await context.new_page()

                self._set(bot_id, STATUS_OPENING, f"Opening {meeting_link} …")
                await page.goto(meeting_link, wait_until="domcontentloaded", timeout=60_000)
                await asyncio.sleep(3)

                # --- Sign-in gate (persistent profile not signed in yet) ---
                if "accounts.google.com" in page.url:
                    self._set(
                        bot_id,
                        STATUS_ACTION_REQUIRED,
                        "The assistant browser needs you to sign in to Google. "
                        "Complete the sign-in in the Chrome window that just opened.",
                    )
                    for _ in range(150):  # up to ~5 minutes
                        if self._stop_requested(bot_id) or page.is_closed():
                            return
                        if "meet.google.com" in page.url:
                            break
                        await asyncio.sleep(2)
                    else:
                        self._set(bot_id, STATUS_FAILED, "Sign-in was not completed in time.")
                        return

                await self._enter_meeting(bot_id, page, bot_name)

                # --- Stay in the meeting until stopped or the tab closes ---
                while not self._stop_requested(bot_id):
                    if page.is_closed():
                        break
                    await asyncio.sleep(BOT_IDLE_POLL_SECONDS)

        except asyncio.CancelledError:
            logger.info("[%s] bot task cancelled.", bot_id)
            raise
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            logger.exception("Meeting bot failed.")
            self._set(bot_id, STATUS_FAILED, f"Assistant browser error: {exc}")
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    logger.debug("Could not close bot context cleanly.", exc_info=True)

            bot = self.active_bots.get(bot_id)
            if bot is not None and bot.get("status") in _LIVE_STATUSES:
                self._set(bot_id, STATUS_STOPPED, "Assistant browser closed.")
            logger.info("Meeting bot stopped: %s", bot_id)

    async def _enter_meeting(self, bot_id: str, page, bot_name: str) -> None:
        """Walk the Google Meet join flow and request admission."""
        # 1) "Continue as guest" (shown only when not signed in).
        guest = page.get_by_role("button", name=re.compile(r"continue as guest", re.I))
        try:
            if await guest.count():
                await guest.first.click(timeout=8_000)
                logger.info("[%s] Clicked 'Continue as guest'.", bot_id)
                await asyncio.sleep(1.5)
        except Exception:
            logger.debug("[%s] No guest button (already signed in?).", bot_id)

        # 2) Fill the display name.
        name_field = page.get_by_placeholder(re.compile(r"name", re.I))
        try:
            await name_field.first.wait_for(state="visible", timeout=20_000)
            await name_field.first.fill(bot_name)
            logger.info("[%s] Filled guest name: %s", bot_id, bot_name)
        except Exception:
            logger.debug("[%s] Name field not found (signed-in account).", bot_id)

        # 3) Ask to join / Join now — this is the step the old code never did.
        self._set(bot_id, STATUS_REQUESTING, "Requesting permission to enter the meeting…")
        join_button = page.get_by_role(
            "button", name=re.compile(r"ask to join|join now|request to join", re.I)
        )
        await join_button.first.wait_for(state="visible", timeout=30_000)
        await join_button.first.click(timeout=10_000)
        logger.info("[%s] Clicked the join button.", bot_id)

        self._set(
            bot_id,
            STATUS_WAITING,
            "Waiting for the host to admit the assistant from the waiting room…",
        )

        # 4) Wait for admission (or rejection) and report the true outcome.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + BOT_JOIN_TIMEOUT_SECONDS
        leave_button = page.get_by_role("button", name=re.compile(r"leave call|leave meeting", re.I))

        while loop.time() < deadline:
            if self._stop_requested(bot_id) or page.is_closed():
                return

            try:
                body = (await page.locator("body").inner_text()).lower()
            except Exception:
                body = ""

            if "you have joined the call" in body or await leave_button.count() > 0:
                self._set(
                    bot_id,
                    STATUS_ADMITTED,
                    "Assistant admitted to the meeting. You can start recording now.",
                )
                return

            if (
                "you can't join this video call" in body
                or "return to home screen" in body
                or "no one can join this call" in body
            ):
                self._set(
                    bot_id,
                    STATUS_FAILED,
                    "The meeting refused entry (host, domain or sign-in restriction).",
                )
                return

            await asyncio.sleep(3)

        self._set(
            bot_id,
            STATUS_FAILED,
            "The host did not admit the assistant in time. You can try again.",
        )

    def _stop_requested(self, bot_id: str) -> bool:
        bot = self.active_bots.get(bot_id)
        return bot is None or bool(bot.get("_stopping"))


meeting_bot = MeetingBotService()
