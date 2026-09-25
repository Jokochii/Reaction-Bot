from config import WATCHED_CHANNELS, TARGET_EMOJI, COOLDOWNS
from parsers import parse_date_from_text
from tasks import load_database, save_database, check_reminder_deadlines


def setup_events(bot):
    check_reminder_deadlines.bot = bot

    @bot.event
    async def on_message(message):
        if message.author.id == bot.user.id: return
        if message.channel.id in WATCHED_CHANNELS:
            try:
                await message.add_reaction(TARGET_EMOJI)
            except Exception:
                pass
        await bot.process_commands(message)

    @bot.event
    async def on_raw_message_edit(payload):
        if payload.channel_id not in WATCHED_CHANNELS: return
        data = payload.data or {}
        text = data.get("content", "")
        for emb_data in data.get("embeds", []):
            text += f"\n{emb_data.get('title', '')}\n{emb_data.get('description', '')}"

        new_date = parse_date_from_text(text)
        if new_date:
            db = load_database()
            mk = str(payload.message_id)

            if mk in db and new_date != db[mk].get("end_date", "none"):
                db[mk]["end_date"], db[mk]["alerts_sent"] = new_date, False
                await save_database(db)

                if check_reminder_deadlines.is_running():
                    check_reminder_deadlines.restart()

    @bot.event
    async def on_raw_message_delete(payload):
        if payload.channel_id not in WATCHED_CHANNELS: return
        msg_key = str(payload.message_id)
        db = load_database()
        if msg_key in db:
            del db[msg_key]
            await save_database(db)
            print(f"Database Purged: Erased historical record for deleted post ID {msg_key}")
        for cache_key in list(COOLDOWNS.keys()):
            if cache_key.startswith(msg_key): del COOLDOWNS[cache_key]
