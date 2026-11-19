import asyncio
import logging
import os

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

logger = logging.getLogger(__name__)

CDP_ENDPOINT = os.getenv(
    "MEET_CDP_ENDPOINT",
    "http://127.0.0.1:9223"
)


class MeetingBotService:
    def __init__(self):
        self.active_bots = {}

    async def join_meeting(
        self,
        meeting_link: str,
        bot_name: str = "AI Class Assistant"
    ):
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright is not installed.")
            return None

        bot_id = f"bot_{hash(meeting_link)}"

        if bot_id in self.active_bots:
            logger.warning("Bot already active for this meeting.")
            return bot_id

        async def run_bot():
            page = None

            try:
                async with async_playwright() as p:
                    logger.info("Connecting to guest Chrome: %s", CDP_ENDPOINT)

                    browser = await p.chromium.connect_over_cdp(
                        CDP_ENDPOINT
                    )

                    if not browser.contexts:
                        raise RuntimeError(
                            "No Chrome browser context available."
                        )

                    context = browser.contexts[0]
                    page = await context.new_page()

                    logger.info("Opening meeting: %s", meeting_link)
                    await page.goto(
                        meeting_link,
                        wait_until="domcontentloaded"
                    )

                    guest_button = page.get_by_role(
                        "button",
                        name="Continue as guest"
                    )

                    await guest_button.wait_for(
                        state="visible",
                        timeout=30000
                    )

                    await guest_button.click()
                    logger.info("Continue as guest clicked.")

                    name_field = page.get_by_placeholder(
                        "Enter your name"
                    )

                    await name_field.wait_for(
                        state="visible",
                        timeout=30000
                    )

                    await name_field.fill(bot_name)
                    logger.info("Guest name filled: %s", bot_name)

                    ask_button = page.get_by_role(
                        "button",
                        name="Ask to join"
                    )

                    await ask_button.wait_for(
                        state="visible",
                        timeout=15000
                    )

                    if not await ask_button.is_enabled():
                        raise RuntimeError(
                            "Ask to join button is disabled."
                        )

                    logger.info(
                        "READY: Click Ask to join manually in guest Chrome."
                    )

                    joined_logged = False

                    while bot_id in self.active_bots:
                        if page.is_closed():
                            logger.warning("Guest Chrome tab was closed.")
                            break

                        body_text = await page.locator("body").inner_text()

                        if (
                            "You have joined the call" in body_text
                            or await page.get_by_role(
                                "button",
                                name="Leave call"
                            ).count() > 0
                        ):
                            if not joined_logged:
                                logger.info(
                                    "Guest successfully joined the meeting."
                                )
                                joined_logged = True

                        await asyncio.sleep(2)

            except Exception:
                logger.exception("Meeting bot failed.")

            finally:
                # Close only the bot's own tab.
                # Never close the externally managed Chrome browser.
                if page is not None:
                    try:
                        if not page.is_closed():
                            await page.close()
                    except Exception:
                        logger.exception("Could not close bot tab.")

                self.active_bots.pop(bot_id, None)
                logger.info("Meeting bot stopped: %s", bot_id)

        task = asyncio.create_task(run_bot())
        self.active_bots[bot_id] = task

        return bot_id

    async def stop_bot(self, bot_id: str):
        if bot_id in self.active_bots:
            del self.active_bots[bot_id]
            return True

        return False


meeting_bot = MeetingBotService()
