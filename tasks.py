import os
import json
import discord
import asyncio
import aiofiles
import urllib.request
from datetime import datetime
from discord.ext import tasks
from config import DB_FILE
from parsers import extract_readybot_data

db_lock = asyncio.Lock()

def load_database():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except Exception: return {}

async def save_database(data):
    async with db_lock:
        try:
            image_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stored_images")
            if not os.path.exists(image_folder): os.makedirs(image_folder)

            for msg_id, payload in data.items():
                if "users" in payload and payload["users"]:
                    if "raw_images" not in payload: payload["raw_images"] = []
                    for idx, img_url in enumerate(payload["raw_images"]):
                        if img_url and ("://discordapp.com" in img_url or "media.discordapp.net" in img_url) and not img_url.startswith("local_"):
                            try:
                                file_ext = img_url.split('?')[0].split('.')[-1].lower()
                                if file_ext not in ['png', 'jpg', 'jpeg', 'gif', 'webp']: file_ext = 'png'
                                
                                local_filename = f"msg_{msg_id}_img_{idx}.{file_ext}"
                                full_save_path = os.path.join(image_folder, local_filename)

                                req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                                with urllib.request.urlopen(req, timeout=5) as response:
                                    with open(full_save_path, 'wb') as out_file: out_file.write(response.read())

                                payload["raw_images"][idx] = f"local_{local_filename}"
                                print(f"Permanently Mirrored Asset: {local_filename}")
                            except Exception: pass

            async with aiofiles.open(DB_FILE, 'w') as f:
                await f.write(json.dumps(data, indent=4))
        except Exception: pass

@tasks.loop(minutes=30)
async def check_reminder_deadlines():
    bot = getattr(check_reminder_deadlines, "bot", None)
    if not bot: return
    db = load_database()
    if not db: return
    now, db_changed = datetime.now(), False
    
    for msg_id in list(db.keys()):
        item_data = db[msg_id]
        date_str = item_data.get("end_date")
        if not date_str or date_str == "none": continue
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            if (target_date - now).total_seconds() <= 86400 and not item_data.get("alerts_sent", False):
                chan = bot.get_channel(item_data["channel_id"]) or await bot.fetch_channel(item_data["channel_id"])
                msg = await chan.fetch_message(int(msg_id))
                title, prod_url, _, img_list = await extract_readybot_data(msg)
                
                loop_unix = int(target_date.timestamp())
                display_loop_deadline = f"<t:{loop_unix}:F> (<t:{loop_unix}:R>)"
                base_url = prod_url or msg.jump_url

                embed = discord.Embed(title="⏰ Event Reminder Warning!", description="An event you track concludes within 24 hours.", color=0x3498db, timestamp=now, url=base_url)
                embed.add_field(name="📦 Item Name", value=f"**{title}**", inline=False)
                embed.add_field(name="📅 Closing Date", value=display_loop_deadline, inline=True)
                embed.add_field(name="🌐 Server", value=chan.guild.name, inline=True)
                embed.add_field(name="⏳ Status", value="🚨 Concluding in less than 24 hours!", inline=False)
                embed.set_footer(text="Automated Reminder Service", icon_url=str(bot.user.avatar.url) if bot.user.avatar else None)
                
                all_embeds = [embed]
                discord_files = []
                image_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stored_images")

                if img_list:
                    for idx, img_path in enumerate(img_list):
                        if img_path.startswith("local_"):
                            filename_raw = img_path.replace("local_", "")
                            true_path = os.path.join(image_folder, filename_raw)
                            if os.path.exists(true_path):
                                discord_files.append(discord.File(true_path, filename=filename_raw))
                                if idx == 0: embed.set_image(url=f"attachment://{filename_raw}")
                                else:
                                    extra_embed = discord.Embed(url=base_url)
                                    extra_embed.set_image(url=f"attachment://{filename_raw}")
                                    all_embeds.append(extra_embed)
                        else:
                            if idx == 0: embed.set_image(url=img_path)
                            else:
                                extra_embed = discord.Embed(url=base_url)
                                extra_embed.set_image(url=img_path)
                                all_embeds.append(extra_embed)

                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="💬 Jump to Post", url=msg.jump_url, style=discord.ButtonStyle.link))
                if prod_url: view.add_item(discord.ui.Button(label="🛒 Open Webpage", url=prod_url, style=discord.ButtonStyle.link))
                
                for uid in item_data.get("users", []):
                    try:
                        m = chan.guild.get_member(int(uid)) or await chan.guild.fetch_member(int(uid))
                        if m and not m.bot: 
                            for f in discord_files: f.reset()
                            await m.send(embeds=all_embeds, files=discord_files if discord_files else None, view=view)
                    except Exception: pass 
                item_data["alerts_sent"] = True
                db_changed = True

            if (target_date - now).total_seconds() < -7776000:
                if "raw_images" in db[msg_id]:
                    image_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stored_images")
                    for img_path in db[msg_id]["raw_images"]:
                        if img_path.startswith("local_"):
                            clean_target = os.path.join(image_folder, img_path.replace("local_", ""))
                            if os.path.exists(clean_target):
                                try: os.remove(clean_target)
                                except Exception: pass
                del db[msg_id]
                db_changed = True
        except Exception: pass
    if db_changed: await save_database(db)

@check_reminder_deadlines.before_loop
async def before_clock_loop():
    bot = getattr(check_reminder_deadlines, "bot", None)
    if bot: await bot.wait_until_ready()
