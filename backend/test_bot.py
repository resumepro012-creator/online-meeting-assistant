import asyncio
import logging
import sys
import os

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.meeting_bot_service import meeting_bot

logging.basicConfig(level=logging.INFO)

async def test_bot():
    # Use a dummy Google Meet link or a real one if you have it
    # Since I don't have a real one, I'll use the one from the user's screenshot
    link = "https://meet.google.com/adp-etat-bop"
    print(f"Testing bot join for: {link}")
    
    bot_id = await meeting_bot.join_meeting(link, "AI Assistant Debug")
    print(f"Bot task created: {bot_id}")
    
    # Wait for the bot to do its thing
    await asyncio.sleep(40)
    
    await meeting_bot.stop_bot(bot_id)
    print("Test finished.")

if __name__ == "__main__":
    asyncio.run(test_bot())
