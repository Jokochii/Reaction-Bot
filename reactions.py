import discord
import asyncio
import time
from datetime import datetime
from config import WATCHED_CHANNELS, TARGET_EMOJI, COOLDOWNS, PROCESSING_REACTIONS
from parsers import parse_date_from_text, extract_readybot_data, fetch_store_metadata
from tasks import load_database, save_database

def setup_reactions(bot):
    @bot.event
    async def on_raw_reaction_add(payload):
        if payload.channel_id not in WATCHED_CHANNELS or payload.emoji.name != TARGET_EMOJI or payload.user_id == bot.user.id: 
            return
            
        uid_str, mid_str = str(payload.user_id), str(payload.message_id)
        up_key = f"{mid_str}-{uid_str}"
        now_ts = datetime.now().timestamp()
        
        # 1. Global Lockout Verification State
        if f"lockout-{uid_str}" in COOLDOWNS:
            if now_ts - COOLDOWNS[f"lockout-{uid_str}"] < 3600:
                print(f" Request Denied: User ID {uid_str} is banned server-wide.")
                return 
            else:
                del COOLDOWNS[f"lockout-{uid_str}"]
                if up_key in COOLDOWNS: COOLDOWNS[up_key] = []

        if up_key not in COOLDOWNS: COOLDOWNS[up_key] = []
        COOLDOWNS[up_key] = [t for t in COOLDOWNS[up_key] if now_ts - t < 3600]
        COOLDOWNS[up_key].append(now_ts)

        # 2. Check Spam Velocity Limits
        if len(COOLDOWNS[up_key]) >= 5:
            COOLDOWNS[f"lockout-{uid_str}"] = now_ts
            print(f"Ban Enforced: User ID {uid_str} spammed Post ID {mid_str}.")
            try:
                ch = bot.get_channel(payload.channel_id) or await bot.fetch_channel(payload.channel_id)
                msg = await ch.fetch_message(payload.message_id)

                title, _, _, _ = await extract_readybot_data(msg)
                
                m = payload.member or ch.guild.get_member(payload.user_id)
                w_emb = discord.Embed(title="⛔ Anti-Spam Interaction Lockout", description=f"Hello {m.display_name}.\n\nYou spammed the reaction button for **{title}**.\n\nYour account is **locked out** from tracking **ALL posts** for the next **1 hour**.", color=0xe74c3c, timestamp=datetime.now())
                asyncio.create_task(m.send(embed=w_emb))
            except Exception: pass
            return

        if len(COOLDOWNS[up_key]) > 1 and now_ts - COOLDOWNS[up_key][-2] < 2: 
            return 

        guild = bot.get_guild(payload.guild_id)
        if not guild: return
        member = payload.member or guild.get_member(payload.user_id)
        if not member or member.bot: return

        try:
            channel = bot.get_channel(payload.channel_id) or await bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
        except Exception: return

        rx_key = f"{message.id}-{member.id}"
        if rx_key in PROCESSING_REACTIONS: return 
        
        try:
            PROCESSING_REACTIONS.add(rx_key)
            try: await message.remove_reaction(payload.emoji, member)
            except Exception: pass

            raw_text = message.content or ""
            if message.embeds:
                for embed in message.embeds: 
                    raw_text += f"\n{embed.title or ''}\n{embed.description or ''}"
                    for f in embed.fields: raw_text += f"\n{f.name}\n{f.value}"

            end_date_str = parse_date_from_text(raw_text) or "none"

            item_title, product_url, _, image_list = await extract_readybot_data(message)

            db = load_database()
            msg_key = str(message.id)
            if msg_key not in db: 
                db[msg_key] = {"end_date": end_date_str, "channel_id": channel.id, "alerts_sent": False, "users": [], "raw_images": image_list}
                
            if uid_str in db[msg_key]["users"]:
                db[msg_key]["users"].remove(uid_str)
                if not db[msg_key]["users"] and db[msg_key]["end_date"] == "none": 
                    del db[msg_key]
                await save_database(db)
                
                opt_out = discord.Embed(title="❌ Reminder Cancelled", description=f"You have **opted out** of alerts for **{item_title}**.", color=0xe74c3c, timestamp=datetime.now())
                try: await member.send(embed=opt_out)
                except Exception: pass
                print(f"➖ Opt-Out: {member.name} stopped tracking '{item_title}'")
            else:
                if uid_str not in db[msg_key]["users"]:
                    db[msg_key]["users"].append(uid_str)
                await save_database(db)
                is_urgent, display_deadline = False, "Ongoing / No Deadline"
                
                if end_date_str != "none":
                    try:
                        date_obj = datetime.strptime(end_date_str, '%Y-%m-%d')
                        unix_timestamp = int(date_obj.timestamp())
                        display_deadline = f"<t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)"
                        if (date_obj - datetime.now()).total_seconds() <= 86400: is_urgent = True
                    except Exception: pass

                embed = discord.Embed(color=0x2ecc71, timestamp=datetime.now(), url=message.jump_url)
                if is_urgent:
                    embed.title, embed.color, embed.description = "⏰ Event Reminder Warning!", 0x3498db, f"Hello {member.display_name}! You just opted in, but this item is concluding within 24 hours!"
                    embed.add_field(name="📦 Item Name", value=f"**{item_title}**", inline=False)
                    embed.add_field(name="📅 Closing Date", value=display_deadline, inline=True)
                    embed.add_field(name="🌐 Server", value=guild.name, inline=True)
                    embed.add_field(name="⏳ Status", value="🚨 Concluding in less than 24 hours!", inline=False)
                else:
                    if end_date_str != "none":
                        embed.title, embed.description = "✅ Reminder Confirmed", f"You are now **tracking** alerts for **{item_title}**!"
                        embed.add_field(name="📦 Item Name", value=f"**{item_title}**", inline=False)
                        embed.add_field(name="📅 Closing Date", value=display_deadline, inline=True)
                        embed.add_field(name="🌐 Server", value=guild.name, inline=True)
                        embed.add_field(name="⏳ Status", value="📌 Reminder Active (24h Warning Enqueued)", inline=False)
                    else:
                        embed.title, embed.color, embed.description = "📌 Ongoing / No Deadline", 0x7f8c8d, f"Hello {member.display_name}! You requested a tracking marker for an item that does not have a closing deadline yet."
                        embed.add_field(name="📦 Item Name", value=f"**{item_title}**", inline=False)
                        embed.add_field(name="🌐 Server", value=guild.name, inline=True)
                        embed.add_field(name="⏳ Status", value="Ongoing / Pre-Registered", inline=False)

                embed.set_footer(text="Automated Reminder Service", icon_url=str(bot.user.avatar.url) if bot.user.avatar else None)

                all_embeds = [embed]
                discord_files = []

                if image_list:
                    for idx, img_path in enumerate(image_list[:4]):
                        if img_path.startswith("local_"):

                            import os
                            image_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stored_images")
                            true_path = os.path.join(image_folder, img_path.replace("local_", ""))
                            if os.path.exists(true_path):
                                filename = os.path.basename(true_path)

                                discord_files.append(discord.File(true_path, filename=filename))
                                
                                if idx == 0:
                                    embed.set_image(url=f"attachment://{filename}")
                                else:
                                    extra_embed = discord.Embed(url=message.jump_url)
                                    extra_embed.set_image(url=f"attachment://{filename}")
                                    all_embeds.append(extra_embed)
                        else:

                            if idx == 0:
                                embed.set_image(url=img_path)
                            else:
                                extra_embed = discord.Embed(url=message.jump_url)
                                extra_embed.set_image(url=img_path)
                                all_embeds.append(extra_embed)

                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="💬 Jump to Post", url=message.jump_url, style=discord.ButtonStyle.link))
                if product_url: view.add_item(discord.ui.Button(label="🛒 Open Webpage", url=product_url, style=discord.ButtonStyle.link))
                
                try: 

                    await member.send(embeds=all_embeds, files=discord_files if discord_files else None, view=view)
                except Exception as e:
                    print(f"⚠️ DM transmission failed: {e}")
                    
                print(f"➕ Opt-In: {member.name} started tracking '{item_title}' (Deadline: {display_deadline})")


        finally:

            await asyncio.sleep(0.4)
            PROCESSING_REACTIONS.discard(rx_key)
