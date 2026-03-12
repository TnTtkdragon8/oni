print("BOT FILE STARTED")

import discord
from discord.ext import commands
import logging
import asyncio
import os
import random
import time
import io
import re
import sqlite3
from datetime import datetime, timedelta

import aiohttp
from PIL import Image, ImageDraw, ImageOps

logging.basicConfig(level=logging.WARNING)

# =========================
# Intents
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=".", intents=intents)

# =========================
# إعدادات عامة
# =========================
OWNER_USERNAME = "xjb5"

WELCOME_CHANNEL_NAME = "モ・「👋」الـتـرحـيـب"
WELCOME_BG_URL = "https://i.postimg.cc/xjvBZgKQ/khlfyt.jpg"

LINE_TRIGGER = "خط"
LINE_IMAGE_SOURCE = "https://i.postimg.cc/PrQHV52P/khtt.png"

WELCOME_MEMBER_ROLE = "👥 𝕸𝖇 ❁ عـضـو"
TICKET_STAFF_ROLE = "𝕺ₙ مــســؤول الــتـكــت"

ALLOWED_ADMIN_ROLES = [
    "باشا البلد",
    "𝕺ₙ 𝓣𝓱𝓮 𝓚𝓲𝓷𝓰",
    "𝕺ₙ مسؤول إداره"
]

LEVEL_CHANNEL_ID = 1480725848842834074
TICKET_CATEGORY_NAME = "🎫 Tickets"

LEVEL_ROLES = {
    3: "👥 𝕸𝖇 ❁ 𝓼𝓲𝓵𝓿𝓮𝓻",
    6: "👥 𝕸𝖇 ❁ 𝓰𝓸𝓵𝓭",
    10: "👥 𝕸𝖇 ❁ 𝓭𝓲𝓪𝓶𝓸𝓷𝓭",
    15: "👥 𝕸𝖇 ❁ 𝓻𝓸𝔂𝓪𝓵",
    20: "👥 𝕸𝖇 ❁ 𝓵𝓮𝓰𝓮𝓷𝓭",
}

SPAM_MAX_MESSAGES = 6
SPAM_INTERVAL_SECONDS = 8
SPAM_TIMEOUT_MINUTES = 10

# =========================
# Database
# =========================
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "bot_data.db")

unauthorized_attempts = {}
xp_cooldowns = {}
spam_tracker = {}

# =========================
# Database helpers
# =========================
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs("temp", exist_ok=True)

def get_db():
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            user_id TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            user_id TEXT PRIMARY KEY,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            user_id TEXT PRIMARY KEY,
            channel_id INTEGER NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def get_warning_count(user_id: int) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT count FROM warnings WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()
    return int(row["count"]) if row else 0

def set_warning_count(user_id: int, count: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO warnings (user_id, count)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET count=excluded.count
    """, (str(user_id), int(count)))
    conn.commit()
    conn.close()

def add_warning(user_id: int) -> int:
    current = get_warning_count(user_id) + 1
    set_warning_count(user_id, current)
    return current

def get_user_level_record(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT xp, level FROM levels WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()

    if row:
        record = {"xp": int(row["xp"]), "level": int(row["level"])}
    else:
        cur.execute(
            "INSERT INTO levels (user_id, xp, level) VALUES (?, 0, 0)",
            (str(user_id),)
        )
        conn.commit()
        record = {"xp": 0, "level": 0}

    conn.close()
    return record

def save_user_level_record(user_id: int, xp: int, level: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO levels (user_id, xp, level)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET xp=excluded.xp, level=excluded.level
    """, (str(user_id), int(xp), int(level)))
    conn.commit()
    conn.close()

def get_ticket_channel_id(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT channel_id FROM tickets WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()
    return int(row["channel_id"]) if row else None

def set_ticket_channel_id(user_id: int, channel_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tickets (user_id, channel_id)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET channel_id=excluded.channel_id
    """, (str(user_id), int(channel_id)))
    conn.commit()
    conn.close()

def delete_ticket_record(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM tickets WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()

# =========================
# مساعدات عامة
# =========================
def is_owner_user(member: discord.Member) -> bool:
    return member.name.lower() == OWNER_USERNAME.lower()

def has_any_role(member: discord.Member, role_names) -> bool:
    return any(role.name in role_names for role in member.roles)

def is_admin_member(member: discord.Member) -> bool:
    return has_any_role(member, ALLOWED_ADMIN_ROLES)

def is_ticket_staff(member: discord.Member) -> bool:
    return is_admin_member(member) or any(role.name == TICKET_STAFF_ROLE for role in member.roles)

def has_member_role(member: discord.Member) -> bool:
    return any(role.name == WELCOME_MEMBER_ROLE for role in member.roles)

def can_use_member_features(member: discord.Member) -> bool:
    return has_member_role(member) or is_admin_member(member)

async def count_unauthorized_attempt(ctx):
    uid = str(ctx.author.id)
    unauthorized_attempts[uid] = unauthorized_attempts.get(uid, 0) + 1
    if unauthorized_attempts[uid] >= 5:
        unauthorized_attempts[uid] = 0
        await ctx.send("مش بس يحبيبي صدعتني")

def xp_needed_for_level(level: int) -> int:
    return 120 * (level ** 2) + 80 * level

def level_from_xp(xp: int) -> int:
    level = 0
    while xp >= xp_needed_for_level(level + 1):
        level += 1
    return level

def get_next_level_xp(level: int) -> int:
    return xp_needed_for_level(level + 1)

def sanitize_channel_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF_-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name[:50] if name else "ticket"

def parse_duration(text: str):
    try:
        if text.endswith("د"):
            minutes = int(text[:-1])
            if minutes <= 0:
                return None
            return timedelta(minutes=minutes)
        if text.endswith("س"):
            hours = int(text[:-1])
            if hours <= 0:
                return None
            return timedelta(hours=hours)
    except ValueError:
        return None
    return None

def get_ticket_owner_id_from_topic(topic: str):
    if not topic:
        return None
    match = re.search(r"owner_id:(\d+)", topic)
    if match:
        return int(match.group(1))
    return None

async def can_manage_target(ctx, member: discord.Member):
    if member == bot.user:
        await ctx.send("❌ لا يمكن تنفيذ الأمر على البوت.")
        return False
    if member == ctx.author:
        await ctx.send("❌ لا يمكن تنفيذ الأمر على نفسك.")
        return False
    if member == ctx.guild.owner:
        await ctx.send("❌ لا يمكن تنفيذ الأمر على مالك السيرفر.")
        return False
    if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
        await ctx.send("❌ لا يمكنك تنفيذ الأمر على عضو رتبته أعلى منك أو تساويك.")
        return False
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send("❌ رتبة البوت أقل من رتبة العضو المطلوب.")
        return False
    return True

# =========================
# أدوات صور
# =========================
async def fetch_bytes(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.read()

async def create_welcome_image(member: discord.Member) -> io.BytesIO:
    bg_bytes = await fetch_bytes(WELCOME_BG_URL)
    avatar_bytes = await fetch_bytes(member.display_avatar.replace(size=512).url)

    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

    bg_w, _ = bg.size

    circle_size = 430
    circle_x = (bg_w - circle_size) // 2
    circle_y = 210

    avatar = ImageOps.fit(avatar, (circle_size, circle_size), centering=(0.5, 0.5))

    mask = Image.new("L", (circle_size, circle_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, circle_size, circle_size), fill=255)

    border = Image.new("RGBA", (circle_size + 10, circle_size + 10), (0, 0, 0, 0))
    border_mask = Image.new("L", (circle_size + 10, circle_size + 10), 0)
    border_draw = ImageDraw.Draw(border_mask)
    border_draw.ellipse((0, 0, circle_size + 10, circle_size + 10), fill=180)
    border_draw.ellipse((5, 5, circle_size + 5, circle_size + 5), fill=0)
    border.paste((220, 220, 220, 170), (0, 0), border_mask)

    bg.alpha_composite(border, (circle_x - 5, circle_y - 5))
    bg.paste(avatar, (circle_x, circle_y), mask)

    output = io.BytesIO()
    bg.save(output, format="PNG")
    output.seek(0)
    return output

async def send_line_image(channel: discord.TextChannel):
    try:
        await channel.send(LINE_IMAGE_SOURCE)
    except Exception as e:
        await channel.send(f"❌ حصل خطأ: {e}")

# =========================
# Embeds
# =========================
def make_warn_embed(ctx, member: discord.Member, reason: str, count: int):
    embed = discord.Embed(
        title="⚠️ تم تحذيرك!",
        description=(
            f"**العضو:** {member.mention}\n"
            f"**السبب:** {reason}\n"
            f"**عدد التحذيرات:** {count}"
        ),
        color=discord.Color.dark_red()
    )

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    else:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.set_footer(
        text=f"{ctx.guild.name} • {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"
    )
    return embed

def make_ticket_embed(guild: discord.Guild, opener: discord.Member, ticket_type: str):
    embed = discord.Embed(
        title=f"🎫 تذكرة جديدة - {ticket_type}",
        description=(
            f"مرحبًا {opener.mention}\n"
            f"تم فتح التذكرة بنجاح.\n"
            f"يرجى شرح مشكلتك أو طلبك بوضوح، وسيتم الرد عليك من الإدارة."
        ),
        color=discord.Color.dark_red()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="صاحب التذكرة", value=opener.mention, inline=True)
    embed.add_field(name="النوع", value=ticket_type, inline=True)
    embed.set_footer(text=guild.name)
    return embed

def make_levelup_embed(member: discord.Member, new_level: int):
    embed = discord.Embed(
        description=(
            f"مبروك {member.mention}\n"
            f"تم ترقية مستواك إلى **{new_level}**\n"
            f"شد حيلك عشان توصل للمستوى اللي بعده 🚀"
        ),
        color=discord.Color.dark_red()
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    return embed

# =========================
# Views التكت
# =========================
class TicketManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام التكت", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ غير متاح.", ephemeral=True)
            return

        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message("❌ مش عندك إذن.", ephemeral=True)
            return

        embed = discord.Embed(
            description=(
                f"✅ الإداري {interaction.user.mention} استلم التذكرة.\n"
                f"اتفضل اشرح مشكلتك أو طلبك."
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="قفل التكت", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ غير متاح.", ephemeral=True)
            return

        owner_id = get_ticket_owner_id_from_topic(interaction.channel.topic if isinstance(interaction.channel, discord.TextChannel) else "")
        allowed = is_ticket_staff(interaction.user) or (owner_id == interaction.user.id)

        if not allowed:
            await interaction.response.send_message("❌ مش عندك إذن تقفل التذكرة.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 سيتم إغلاق التذكرة بعد 5 ثوانٍ.")
        await asyncio.sleep(5)

        try:
            channel = interaction.channel
            if isinstance(channel, discord.TextChannel):
                delete_ticket_record(owner_id)
                await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except Exception:
            pass

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ غير متاح.", ephemeral=True)
            return

        member = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ غير متاح هنا.", ephemeral=True)
            return

        if not can_use_member_features(member):
            await interaction.response.send_message("❌ ليس لديك إذن لفتح تكت.", ephemeral=True)
            return

        existing_channel_id = get_ticket_channel_id(member.id)
        if existing_channel_id:
            ch = guild.get_channel(existing_channel_id)
            if ch:
                await interaction.response.send_message(f"❌ لديك تذكرة مفتوحة بالفعل: {ch.mention}", ephemeral=True)
                return

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
        }

        ticket_staff_role = discord.utils.get(guild.roles, name=TICKET_STAFF_ROLE)
        if ticket_staff_role:
            overwrites[ticket_staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        for role_name in ALLOWED_ADMIN_ROLES:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel_name = f"ticket-{sanitize_channel_name(member.name)}"
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"owner_id:{member.id} | type:{ticket_type}"
        )

        set_ticket_channel_id(member.id, channel.id)

        embed = make_ticket_embed(guild, member, ticket_type)
        manage_view = TicketManageView()
        await channel.send(content=f"{member.mention}", embed=embed, view=manage_view)

        await interaction.response.send_message(f"✅ تم فتح التذكرة: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="الدعم الفني", style=discord.ButtonStyle.primary, emoji="🛡️", custom_id="open_support_ticket")
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "الدعم الفني")

    @discord.ui.button(label="البلاغات", style=discord.ButtonStyle.danger, emoji="🔨", custom_id="open_report_ticket")
    async def report_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "البلاغات")

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="refresh_ticket_panel")
    async def refresh_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ تم تحديث الخيارات.", ephemeral=True)

# =========================
# Events
# =========================
@bot.event
async def on_ready():
    init_db()
    bot.add_view(TicketPanelView())
    bot.add_view(TicketManageView())
    print("✅ VERSION SQLITE")
    print(f"البوت شغال كـ {bot.user}")

@bot.event
async def on_member_join(member: discord.Member):
    member_role = discord.utils.get(member.guild.roles, name=WELCOME_MEMBER_ROLE)
    if member_role:
        try:
            await member.add_roles(member_role, reason="Auto member role")
        except Exception:
            pass

    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not channel:
        return

    try:
        image_bytes = await create_welcome_image(member)
        file = discord.File(fp=image_bytes, filename="welcome.png")

        rules_channel = discord.utils.get(member.guild.text_channels, name="القوانين")
        if rules_channel is None:
            rules_channel = discord.utils.get(member.guild.text_channels, name="قوانين")

        embed = discord.Embed(
            title=f"🎉 مرحباً بك في {member.guild.name}",
            description=(
                f"👋 أهلاً بك {member.mention}\n"
                f"🔢 أنت العضو رقم **{member.guild.member_count}**\n"
                f"{f'📜 اقرأ {rules_channel.mention}' if rules_channel else ''}"
            ),
            color=discord.Color.dark_red()
        )
        embed.set_image(url="attachment://welcome.png")
        embed.set_footer(text=f"{member.name} joined the server")
        await channel.send(file=file, embed=embed)
    except Exception as e:
        print(f"خطأ في الترحيب: {e}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    content = message.content.strip()

    if content == "السلام عليكم":
        await message.channel.send("وعليكم السلام ورحمة الله وبركاته")
        return

    if content == ".":
        await message.channel.send("شيلها يا حبيبي")
        return

    if content == LINE_TRIGGER:
        if is_admin_member(message.author):
            try:
                await message.delete()
            except Exception:
                pass
            await send_line_image(message.channel)
        return

    if content == "منشن":
        if is_admin_member(message.author):
            try:
                await message.delete()
            except Exception:
                pass
            await message.channel.send(
                "@everyone @here",
                allowed_mentions=discord.AllowedMentions(everyone=True)
            )
        return

    # مكافحة السبام
    now = time.time()
    uid = str(message.author.id)
    msg_times = spam_tracker.get(uid, [])
    msg_times = [t for t in msg_times if now - t <= SPAM_INTERVAL_SECONDS]
    msg_times.append(now)
    spam_tracker[uid] = msg_times

    if len(msg_times) >= SPAM_MAX_MESSAGES:
        spam_tracker[uid] = []
        if not is_admin_member(message.author):
            try:
                until = discord.utils.utcnow() + timedelta(minutes=SPAM_TIMEOUT_MINUTES)
                await message.author.edit(
                    timed_out_until=until,
                    reason="Auto spam timeout"
                )
                await message.channel.send(
                    f"🚫 {message.author.mention} أخذ تايم {SPAM_TIMEOUT_MINUTES} دقائق بسبب السبام."
                )
            except Exception as e:
                print(f"Spam timeout error: {e}")
        return

    # XP
    if not content.startswith(".") and content:
        last_time = xp_cooldowns.get(uid, 0)

        if now - last_time >= 30:
            xp_cooldowns[uid] = now

            record = get_user_level_record(message.author.id)
            old_level = record["level"]

            gained_xp = random.randint(10, 18)
            new_xp = record["xp"] + gained_xp
            new_level = level_from_xp(new_xp)

            save_user_level_record(message.author.id, new_xp, new_level)

            if new_level > old_level:
                level_channel = message.guild.get_channel(LEVEL_CHANNEL_ID)
                if level_channel:
                    embed = make_levelup_embed(message.author, new_level)
                    await level_channel.send(embed=embed)

                level_role_names = list(LEVEL_ROLES.values())
                roles_to_remove = [discord.utils.get(message.guild.roles, name=r) for r in level_role_names]
                roles_to_remove = [r for r in roles_to_remove if r is not None]

                highest_role_name = None
                for lvl, role_name in sorted(LEVEL_ROLES.items()):
                    if new_level >= lvl:
                        highest_role_name = role_name

                role_to_add = discord.utils.get(message.guild.roles, name=highest_role_name) if highest_role_name else None

                try:
                    if roles_to_remove:
                        await message.author.remove_roles(*roles_to_remove, reason="Level role update")
                    if role_to_add:
                        await message.author.add_roles(role_to_add, reason="Level up reward")
                except Exception:
                    pass

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        if ctx.command and ctx.command.name == "تايم":
            await ctx.send("❌ استخدم: `.تايم @الشخص 10د السبب` أو `.تايم @الشخص 2س السبب`")
            return
        if ctx.command and ctx.command.name == "ت":
            await ctx.send("❌ استخدم: `.ت @الشخص السبب`")
            return
        if ctx.command and ctx.command.name == "حذف":
            await ctx.send("❌ استخدم: `.حذف 10`")
            return
        await ctx.send("❌ ناقص جزء في الأمر.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ فيه خطأ في كتابة الأمر أو المنشن.")
        return

    print(f"Command error: {error}")

# =========================
# أوامر الإدارة
# =========================
@bot.command(name="ت")
async def warn_command(ctx, member: discord.Member, *, reason: str):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    if not await can_manage_target(ctx, member):
        return

    count = add_warning(member.id)
    embed = make_warn_embed(ctx, member, reason, count)

    try:
        await member.send(embed=embed)
    except Exception:
        pass

    await ctx.send(embed=embed)

@bot.command(name="تحذيرات")
async def show_warnings(ctx, member: discord.Member):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    count = get_warning_count(member.id)
    embed = discord.Embed(
        title="⚠️ التحذيرات",
        description=f"{member.mention} لديه **{count}** تحذيرات.",
        color=discord.Color.dark_red()
    )
    await ctx.send(embed=embed)

@bot.command(name="مسح_تحذيرات")
async def reset_warnings(ctx, member: discord.Member):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    set_warning_count(member.id, 0)
    await ctx.send(f"✅ تم تصفير تحذيرات {member.mention}")

@bot.command(name="تايم")
async def timeout_command(ctx, member: discord.Member, duration: str, *, reason: str = "بدون سبب"):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    if not await can_manage_target(ctx, member):
        return

    try:
        delta = parse_duration(duration)
        if delta is None:
            await ctx.send("❌ استخدم الوقت بهذا الشكل: `10د` أو `2س`")
            return

        until = discord.utils.utcnow() + delta
        await member.edit(timed_out_until=until, reason=f"{ctx.author} - {reason}")
        await ctx.send(f"✅ {member.mention} تم تايمه لمدة {duration}")
    except discord.Forbidden:
        await ctx.send("❌ مش عندي صلاحية أعمل تايم.")
    except Exception as e:
        await ctx.send(f"❌ حصل خطأ: {e}")

@bot.command(name="فك")
async def untimeout_command(ctx, member: discord.Member):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    if not await can_manage_target(ctx, member):
        return

    try:
        await member.edit(timed_out_until=None, reason=f"untimeout by {ctx.author}")
        await ctx.send(f"✅ تم فك التايم عن {member.mention}")
    except discord.Forbidden:
        await ctx.send("❌ مش عندي صلاحية أفك التايم.")
    except Exception as e:
        await ctx.send(f"❌ حصل خطأ: {e}")

@bot.command(name="ق")
async def lock_command(ctx):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 تم قفل الشات.", delete_after=3)

@bot.command(name="ف")
async def unlock_command(ctx):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 تم فتح الشات.", delete_after=3)

@bot.command(name="انطر")
async def kick_command(ctx, member: discord.Member, *, reason: str = "بدون سبب"):
    if not any(role.name == "باشا البلد" for role in ctx.author.roles):
        await count_unauthorized_attempt(ctx)
        return

    if not await can_manage_target(ctx, member):
        return

    try:
        await member.kick(reason=f"{ctx.author} - {reason}")
        await ctx.send(f"👢 تم طرد {member.mention}")
    except discord.Forbidden:
        await ctx.send("❌ مش عندي صلاحية أطرد العضو.")
    except Exception as e:
        await ctx.send(f"❌ حصل خطأ: {e}")

@bot.command(name="تفو")
async def ban_command(ctx, member: discord.Member, *, reason: str = "بدون سبب"):
    if not any(role.name == "باشا البلد" for role in ctx.author.roles):
        await count_unauthorized_attempt(ctx)
        return

    if not await can_manage_target(ctx, member):
        return

    try:
        await member.ban(reason=f"{ctx.author} - {reason}")
        await ctx.send(f"🔨 تم حظر {member.mention}")
    except discord.Forbidden:
        await ctx.send("❌ مش عندي صلاحية أحظر العضو.")
    except Exception as e:
        await ctx.send(f"❌ حصل خطأ: {e}")

@bot.command(name="حذف")
async def clear_command(ctx, amount: int):
    if not (is_owner_user(ctx.author) or is_admin_member(ctx.author)):
        await count_unauthorized_attempt(ctx)
        return

    if amount <= 0:
        await ctx.send("❌ اكتب رقم أكبر من 0.")
        return

    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 تم مسح {amount} رسالة", delete_after=3)

# =========================
# أوامر المستوى
# =========================
@bot.command(name="لفل")
async def level_command(ctx, member: discord.Member = None):
    target = member or ctx.author
    record = get_user_level_record(target.id)
    current_level = record["level"]
    current_xp = record["xp"]
    next_xp = get_next_level_xp(current_level)

    embed = discord.Embed(
        title="💫 المستوى",
        description=(
            f"**العضو:** {target.mention}\n"
            f"**اللفل:** {current_level}\n"
            f"**XP:** {current_xp}/{next_xp}"
        ),
        color=discord.Color.dark_red()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

# =========================
# التكت
# =========================
@bot.command(name="تكت")
async def send_ticket_panel_command(ctx):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    embed = discord.Embed(
        title="🎫 نظام التكت",
        description=(
            "**ملاحظات**\n"
            "• عدم فتح التكت لسبب تافه.\n"
            "• عدم الفتح للسؤال عن التقييم.\n"
            "• ممنوع فتح ونسحب.\n"
            "• عقوبة ما سبق: تايم 15 دقيقة.\n\n"
            "**الدعم الفني**\n"
            "• للاستفسار أو طلب مساعدة.\n"
            "• شراء رتب.\n"
            "• أخذ تحذير عن طريق الخطأ.\n\n"
            "**البلاغات**\n"
            "• الإبلاغ عن شخص سبب وفتن.\n"
            "• الإبلاغ عن نصب.\n"
            "• الإبلاغ عن إداري.\n"
            "• الإبلاغ عن مشكلة بالسيرفر.\n\n"
            "اختر الزر المناسب من الأسفل."
        ),
        color=discord.Color.dark_red()
    )

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    view = TicketPanelView()
    await ctx.send(embed=embed, view=view)

@bot.command(name="تيست")
async def test_command(ctx):
    await ctx.send("شغال")

# =========================
# تشغيل
# =========================
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ خطأ: لم يتم تعيين متغير TOKEN")


