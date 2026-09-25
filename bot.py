import discord
from discord.ext import commands
from config import BOT_TOKEN
from tasks import check_reminder_deadlines
from events import setup_events
from reactions import setup_reactions

intents = discord.Intents.default()
intents.reactions = True
intents.members = True
intents.message_content = True

class ReminderBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        check_reminder_deadlines.bot = self

        setup_events(self)
        setup_reactions(self)

        if not check_reminder_deadlines.is_running():
            check_reminder_deadlines.start()


bot = ReminderBot()

@bot.event
async def on_ready():
    if bot.user:
        print(f"Logged in as {bot.user.name}\n------")
    print("[System] Background Engine Active and listening for reaction events...\n------")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
