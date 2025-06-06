import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timezone

import os

# Load .env token

TOKEN = os.getenv("DISCORD_TOKEN")

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="dx.", intents=intents)

# --- Database Setup ---
conn = sqlite3.connect('voice_stats.db')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS voice_activity (
    user_id INTEGER,
    guild_id INTEGER,
    total_seconds INTEGER DEFAULT 0,
    last_join_time TEXT,
    PRIMARY KEY (user_id, guild_id)
)
''')
conn.commit()

def now():
    return datetime.now(timezone.utc).isoformat()

# --- Voice Channel Tracking ---

@bot.event
async def on_voice_state_update(member, before, after):
    user_id = member.id
    guild_id = member.guild.id

    if before.channel is None and after.channel is not None:
        # User joined voice
        c.execute('''
            INSERT INTO voice_activity (user_id, guild_id, total_seconds, last_join_time)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET last_join_time=excluded.last_join_time
        ''', (user_id, guild_id, now()))
        conn.commit()

    elif before.channel is not None and after.channel is None:
        # User left voice
        c.execute('SELECT last_join_time, total_seconds FROM voice_activity WHERE user_id=? AND guild_id=?', (user_id, guild_id))
        row = c.fetchone()
        if row and row[0]:
            join_time = datetime.fromisoformat(row[0])
            duration = (datetime.now(timezone.utc) - join_time).total_seconds()
            total = row[1] + int(duration)
            c.execute('UPDATE voice_activity SET total_seconds=?, last_join_time=NULL WHERE user_id=? AND guild_id=?',
                      (total, user_id, guild_id))
            conn.commit()

# --- Commands ---

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong! 🏓")

@bot.command(name="h")
async def help_command(ctx):
    help_text = (
        "**📘 Dex Bot Help:**\n"
        "`dx.ping` - Check if the bot is online\n"
        "`dx.h` - Show this help message\n"
        "`dx.s` - Show your voice time in this server"
    )
    await ctx.send(help_text)

@bot.command(name="s")
async def stats(ctx):
    user_id = ctx.author.id
    guild_id = ctx.guild.id

    c.execute('SELECT total_seconds, last_join_time FROM voice_activity WHERE user_id=? AND guild_id=?', (user_id, guild_id))
    row = c.fetchone()

    total_seconds = 0
    if row:
        total_seconds = row[0]
        if row[1]:  # still in VC
            join_time = datetime.fromisoformat(row[1])
            total_seconds += int((datetime.now(timezone.utc) - join_time).total_seconds())

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    await ctx.send(f"⏱️ {ctx.author.mention}, you've spent **{hours}h {minutes}m {seconds}s** in voice channels on this server.")

# --- Error Handling ---

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Unknown command: `{ctx.message.content}`. Use `dx.h` for help.")
    else:
        await ctx.send("⚠️ An error occurred. Please try again later.")
        raise error

# --- Run the bot ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not found in .env")
    else:
        print("✅ Starting bot...")
        bot.run(TOKEN)
