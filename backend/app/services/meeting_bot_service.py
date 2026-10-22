import asyncio
import logging
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

from app.core.config import settings

logger = logging.getLogger(__name__)

class MeetingBotService:
    def __init__(self):
        self.active_bots = {}

    async def join_meeting(self, meeting_link: str, bot_name: str = "AI Class Assistant"):
        """
        Launches a headless browser to join the meeting as a guest bot.
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not installed. Bot cannot join.")
            return None

        bot_id = f"bot_{hash(meeting_link)}"
        
        async def run_bot():
            async with async_playwright() as p:
                # Launch browser with mic/camera permissions granted
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    permissions=["microphone", "camera"],
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                page = await context.new_page()
                
                try:
                    logger.info(f"Bot joining meeting: {meeting_link}")
                    await page.goto(meeting_link)
                    
                    # Debug: Take screenshot of the initial page
                    await page.screenshot(path="bot_initial.png")
                    
                    # Google Meet Logic
                    if "meet.google.com" in meeting_link:
                        # Sometimes there are "Dismiss" buttons for mic/camera block notices
                        try:
                            # Wait a bit for popups
                            await asyncio.sleep(2)
                            dismiss_button = page.locator('button:has-text("Dismiss"), button:has-text("Got it"), button:has-text("Allow")')
                            if await dismiss_button.count() > 0:
                                await dismiss_button.first.click()
                                logger.info("Dismissed a popup")
                        except:
                            pass

                        # Google Meet often has a "Ready to join?" screen.
                        try:
                            # 1. Dismiss initial popups (mic/camera block notices)
                            for _ in range(3):
                                dismiss_button = page.locator('button:has-text("Dismiss"), button:has-text("Got it"), button:has-text("Allow"), [aria-label="Close"]')
                                if await dismiss_button.count() > 0:
                                    await dismiss_button.first.click()
                                    logger.info("Dismissed a popup")
                                    await asyncio.sleep(1)
                                else:
                                    break
                            
                            # 2. Look for name input
                            # Sometimes it's a field, sometimes a button first.
                            name_input = page.locator('input[aria-label="Your name"], input[placeholder="Your name"], input[type="text"]')
                            await name_input.first.wait_for(state="visible", timeout=15000)
                            await name_input.first.fill(bot_name)
                            logger.info(f"Filled bot name: {bot_name}")
                            
                            # 3. Click "Ask to join" or "Join now"
                            # We use a broad locator and try multiple times
                            join_selectors = [
                                'button:has-text("Ask to join")', 
                                'button:has-text("Join now")',
                                '[aria-label="Ask to join"]',
                                '[aria-label="Join now"]'
                            ]
                            
                            joined = False
                            for selector in join_selectors:
                                btn = page.locator(selector)
                                if await btn.count() > 0:
                                    await btn.first.click()
                                    logger.info(f"Clicked join button with selector: {selector}")
                                    joined = True
                                    break
                            
                            if not joined:
                                logger.warning("Could not find join button with primary selectors, trying generic button")
                                await page.click('button:visible') # Last resort: click the first visible button
                                
                        except Exception as e:
                            logger.error(f"Google Meet join flow failed: {e}")
                            await page.screenshot(path="bot_error_flow.png")
                            raise
                        
                        # Wait to see if we get in
                        await asyncio.sleep(5)
                        await page.screenshot(path="bot_after_knock.png")
                        
                        # Once admitted, start recording inside the browser
                        # We use a small script to record audio from the page
                        await page.evaluate("""
                            window.recorder = null;
                            window.chunks = [];
                            async function startRecording() {
                                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                                window.recorder = new MediaRecorder(stream);
                                window.recorder.ondataavailable = (e) => window.chunks.push(e.data);
                                window.recorder.start();
                            }
                            startRecording();
                        """)

                        # Keep the page open to stay in the meeting
                        while bot_id in self.active_bots:
                            await asyncio.sleep(5)
                        
                        # Stop recording and get the data
                        # Note: In a real app, we'd stream this or save it to a file
                        logger.info("Bot leaving meeting and saving recording...")
                    
                except Exception as e:
                    logger.error(f"Bot failed to join: {e}")
                finally:
                    await browser.close()
                    if bot_id in self.active_bots:
                        del self.active_bots[bot_id]

        # Run in background
        task = asyncio.create_task(run_bot())
        self.active_bots[bot_id] = task
        return bot_id

    async def stop_bot(self, bot_id: str):
        if bot_id in self.active_bots:
            # The loop in run_bot will exit when bot_id is removed
            del self.active_bots[bot_id]
            return True
        return False

# Global instance
meeting_bot = MeetingBotService()
