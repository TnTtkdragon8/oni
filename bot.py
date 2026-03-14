print("BOT FILE STARTED")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import asyncio
import os
import random
import time
import io
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

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
intents.presences = True
intents.invites = True

bot = commands.Bot(command_prefix=[".", "-", "!"], intents=intents)

# =========================
# إعدادات عامة
# =========================
OWNER_USERNAME = "xjb5"

WELCOME_CHANNEL_NAME = "モ・「👋」الـتـرحـيـب"
RULES_CHANNEL_NAME = "モ・「⚖️」الـقـوانـيـن"
WELCOME_BG_URL = "https://i.postimg.cc/xjvBZgKQ/khlfyt.jpg"

LINE_TRIGGER = "خط"
LINE_IMAGE_SOURCE = "https://i.postimg.cc/PrQHV52P/khtt.png"

WELCOME_MEMBER_ROLE = "👥 𝕸𝖇 ❁ عـضـو"
TICKET_STAFF_ROLE = "𝕺ₙ مــســؤول الــتـكــت"
MEDIATOR_MONITOR_ROLE = "مــراقــب وسـطـاء 𝕺ₙ"

ALLOWED_ADMIN_ROLES = [
    "باشا البلد",
    "𝕺ₙ 𝓣𝓱𝓮 𝓚𝓲𝓷𝓰",
    "𝕺ₙ مسؤول إداره",
    "مــبــرمــج 𝕺ₙ"
]

# =========================
# إعدادات الجيف أواي
# =========================
GIVEAWAY_CHANNEL_ID = 1482218416613097603  # قناة الهدايا
GIVEAWAY_ALLOWED_ROLES = ALLOWED_ADMIN_ROLES  # رتب الإداريين المسموح لهم في أي مكان
GIVEAWAY_EMOJI = "🎉"
GIVEAWAY_FORCE_WINNER_NAME = ""  # ضع اسم المستخدم هنا لتزوير الفوز (مثل "cns2")، واتركه فارغاً للعشوائية

NORMAL_TICKET_EXTRA_MENTION_ROLES = [
    # "رتبة إضافية 1",
    # "رتبة إضافية 2",
]

MEDIATOR_EXTRA_WATCH_ROLES = [
    # "رتبة إضافية 1",
]

LEVEL_CHANNEL_ID = 1481211010160398386
COMMANDS_CHANNEL_NAME = "ア・「🤖」أوامــر"
TICKET_CATEGORY_NAME = "🎫 Tickets"
MEDIATOR_TICKET_CATEGORY_NAME = "🎫 Mediator Tickets"

LEVEL_ROLES = {
    3: "👥 𝕸𝖇 ❁ 𝓼𝓲𝓵𝓿𝓮𝓻",
    6: "👥 𝕸𝖇 ❁ 𝓰𝓸𝓵𝓭",
    10: "👥 𝕸𝖇 ❁ 𝓭𝓲𝓪𝓶𝓸𝓷𝓭",
    15: "👥 𝕸𝖇 ❁ 𝓻𝓸𝔂𝓪𝓵",
    20: "👥 𝕸𝖇 ❁ 𝓵𝓮𝓰𝓮𝓷𝓭",
}

XP_COOLDOWN_SECONDS = 20
XP_MIN_GAIN = 8
XP_MAX_GAIN = 12

MEDIATOR_ROLE_OPTIONS = [
    ("🥉", "وسيط مبتدئ 𝕺ₙ"),
    ("🟢", "وسيط جيد 𝕺ₙ"),
    ("💎", "وسيط ممتاز 𝕺ₙ"),
    ("👑", "وسيط اسطوري 𝕺ₙ"),
    ("🔥", "وسيط مخضرم 𝕺ₙ"),
]

SPAM_MAX_MESSAGES = 6
SPAM_INTERVAL_SECONDS = 8
SPAM_TIMEOUT_MINUTES = 10

TICKET_AUTO_DELETE_SECONDS = 15 * 60
TICKET_EXTEND_SECONDS = 15 * 60
TICKET_REMINDER_SECONDS = 2 * 60

FAKE_ACCOUNT_DAYS = 7  # للحساب الوهمي في الدعوات

# =========================
# Database
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = "/data" if os.path.exists("/data") else os.path.join(BASE_DIR, "data")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
DB_PATH = os.path.join(DATA_DIR, "bot_data.db")

unauthorized_attempts = {}
xp_cooldowns = {}
spam_tracker = {}
ticket_delete_tasks = {}
ticket_reminder_tasks = {}
invite_cache = {}  # guild_id -> {code: uses}

# متغير عام لتخزين الجيفات النشطة (message_id -> Giveaway object)
active_giveaways = {}

# =========================
# Database helpers
# =========================
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


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
            channel_id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'normal',
            ticket_type TEXT,
            target_role TEXT,
            claimed_by TEXT,
            claimed_role TEXT,
            delete_at REAL,
            monitor_claimed_by TEXT,
            extra_member_id TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invite_joins (
            joined_user_id TEXT PRIMARY KEY,
            inviter_id TEXT,
            invite_code TEXT,
            joined_at TEXT,
            account_created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invite_codes (
            guild_id TEXT NOT NULL,
            code TEXT NOT NULL,
            inviter_id TEXT,
            uses INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, code)
        )
    """)

    # جدول الجيفات النشطة
    cur.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            message_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            host_id INTEGER NOT NULL,
            prize TEXT NOT NULL,
            end_time REAL NOT NULL,
            winners_count INTEGER NOT NULL,
            rigged_user_id INTEGER
        )
    """)

    # جدول المشاركين في كل جيف
    cur.execute("""
        CREATE TABLE IF NOT EXISTS giveaway_entries (
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (message_id, user_id)
        )
    """)

    conn.commit()

    # تحديث الأعمدة المفقودة في جدول tickets (إذا كانت موجودة مسبقاً)
    cur.execute("PRAGMA table_info(tickets)")
    cols = [row["name"] for row in cur.fetchall()]
    needed = {
        "kind": "ALTER TABLE tickets ADD COLUMN kind TEXT NOT NULL DEFAULT 'normal'",
        "ticket_type": "ALTER TABLE tickets ADD COLUMN ticket_type TEXT",
        "target_role": "ALTER TABLE tickets ADD COLUMN target_role TEXT",
        "claimed_by": "ALTER TABLE tickets ADD COLUMN claimed_by TEXT",
        "claimed_role": "ALTER TABLE tickets ADD COLUMN claimed_role TEXT",
        "delete_at": "ALTER TABLE tickets ADD COLUMN delete_at REAL",
        "monitor_claimed_by": "ALTER TABLE tickets ADD COLUMN monitor_claimed_by TEXT",
        "extra_member_id": "ALTER TABLE tickets ADD COLUMN extra_member_id TEXT",
    }
    for col, sql in needed.items():
        if col not in cols:
            cur.execute(sql)

    conn.commit()
    conn.close()


# =========================
# Warning helpers
# =========================
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


# =========================
# Level helpers
# =========================
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


# =========================
# Ticket helpers
# =========================
def get_open_ticket_channel_id(user_id: int, kind: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    if kind:
        cur.execute(
            "SELECT channel_id FROM tickets WHERE user_id = ? AND kind = ?",
            (str(user_id), kind)
        )
    else:
        cur.execute(
            "SELECT channel_id FROM tickets WHERE user_id = ?",
            (str(user_id),)
        )
    row = cur.fetchone()
    conn.close()
    return int(row["channel_id"]) if row else None


def set_ticket_record(
    channel_id: int,
    user_id: int,
    kind: str,
    ticket_type: str,
    target_role: Optional[str] = None,
    claimed_by: Optional[int] = None,
    claimed_role: Optional[str] = None,
    delete_at: Optional[float] = None,
    monitor_claimed_by: Optional[int] = None,
    extra_member_id: Optional[int] = None,
):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tickets (
            channel_id, user_id, kind, ticket_type, target_role,
            claimed_by, claimed_role, delete_at, monitor_claimed_by, extra_member_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            user_id=excluded.user_id,
            kind=excluded.kind,
            ticket_type=excluded.ticket_type,
            target_role=excluded.target_role,
            claimed_by=excluded.claimed_by,
            claimed_role=excluded.claimed_role,
            delete_at=excluded.delete_at,
            monitor_claimed_by=excluded.monitor_claimed_by,
            extra_member_id=excluded.extra_member_id
    """, (
        int(channel_id),
        str(user_id),
        kind,
        ticket_type,
        target_role,
        str(claimed_by) if claimed_by else None,
        claimed_role,
        float(delete_at) if delete_at else None,
        str(monitor_claimed_by) if monitor_claimed_by else None,
        str(extra_member_id) if extra_member_id else None,
    ))
    conn.commit()
    conn.close()


def get_ticket_by_channel(channel_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE channel_id = ?", (int(channel_id),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_ticket_claim(channel_id: int, claimed_by: Optional[int], claimed_role: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tickets SET claimed_by = ?, claimed_role = ? WHERE channel_id = ?",
        (str(claimed_by) if claimed_by else None, claimed_role, int(channel_id))
    )
    conn.commit()
    conn.close()


def update_ticket_monitor_claim(channel_id: int, monitor_claimed_by: Optional[int]):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tickets SET monitor_claimed_by = ? WHERE channel_id = ?",
        (str(monitor_claimed_by) if monitor_claimed_by else None, int(channel_id))
    )
    conn.commit()
    conn.close()


def update_ticket_extra_member(channel_id: int, extra_member_id: Optional[int]):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tickets SET extra_member_id = ? WHERE channel_id = ?",
        (str(extra_member_id) if extra_member_id else None, int(channel_id))
    )
    conn.commit()
    conn.close()


def update_ticket_delete_at(channel_id: int, delete_at: Optional[float]):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tickets SET delete_at = ? WHERE channel_id = ?",
        (float(delete_at) if delete_at else None, int(channel_id))
    )
    conn.commit()
    conn.close()


def update_ticket_target_role(channel_id: int, target_role: Optional[str]):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tickets SET target_role = ? WHERE channel_id = ?",
        (target_role, int(channel_id))
    )
    conn.commit()
    conn.close()


def delete_ticket_record_by_channel(channel_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM tickets WHERE channel_id = ?", (int(channel_id),))
    conn.commit()
    conn.close()


def get_all_tickets():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =========================
# Invite helpers
# =========================
def save_invite_snapshot(guild_id: int, invites: list[discord.Invite]):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM invite_codes WHERE guild_id = ?", (str(guild_id),))
    for inv in invites:
        inviter_id = str(inv.inviter.id) if inv.inviter else None
        cur.execute("""
            INSERT OR REPLACE INTO invite_codes (guild_id, code, inviter_id, uses)
            VALUES (?, ?, ?, ?)
        """, (str(guild_id), inv.code, inviter_id, int(inv.uses or 0)))
    conn.commit()
    conn.close()


def record_member_join_invite(joined_user_id: int, inviter_id: Optional[int], invite_code: Optional[str], joined_at: datetime, account_created_at: datetime):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO invite_joins (
            joined_user_id, inviter_id, invite_code, joined_at, account_created_at
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        str(joined_user_id),
        str(inviter_id) if inviter_id else None,
        invite_code,
        joined_at.isoformat(),
        account_created_at.isoformat()
    ))
    conn.commit()
    conn.close()


def get_invite_stats_for_user(guild: discord.Guild, inviter_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT joined_user_id, account_created_at
        FROM invite_joins
        WHERE inviter_id = ?
    """, (str(inviter_id),))
    rows = cur.fetchall()
    conn.close()

    total = len(rows)
    left = 0
    fake = 0

    for row in rows:
        joined_member = guild.get_member(int(row["joined_user_id"]))
        if joined_member is None:
            left += 1

        try:
            created_at = datetime.fromisoformat(row["account_created_at"])
            joined_age = datetime.now(timezone.utc) - created_at
            if joined_age.days < FAKE_ACCOUNT_DAYS:
                fake += 1
        except Exception:
            pass

    real = total - fake - left
    if real < 0:
        real = 0

    return {
        "total": total,
        "fake": fake,
        "left": left,
        "real": real,
    }


async def refresh_guild_invite_cache(guild: discord.Guild):
    try:
        invites = await guild.invites()
    except Exception:
        return

    invite_cache[guild.id] = {inv.code: int(inv.uses or 0) for inv in invites}
    save_invite_snapshot(guild.id, invites)


# =========================
# دوال الجيف أواي
# =========================
def save_giveaway_to_db(giveaway_data: dict):
    """حفظ أو تحديث جيف في قاعدة البيانات"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO giveaways
        (message_id, channel_id, host_id, prize, end_time, winners_count, rigged_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        giveaway_data["message_id"],
        giveaway_data["channel_id"],
        giveaway_data["host_id"],
        giveaway_data["prize"],
        giveaway_data["end_time"],
        giveaway_data["winners_count"],
        giveaway_data.get("rigged_user_id")
    ))
    conn.commit()
    conn.close()

def delete_giveaway_from_db(message_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM giveaways WHERE message_id = ?", (message_id,))
    cur.execute("DELETE FROM giveaway_entries WHERE message_id = ?", (message_id,))
    conn.commit()
    conn.close()

def load_all_giveaways_from_db():
    """تحميل جميع الجيفات النشطة من قاعدة البيانات وإرجاع قاموس (message_id -> Giveaway)"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM giveaways")
    rows = cur.fetchall()
    giveaways = {}
    for row in rows:
        gw = dict(row)
        # تحميل المشاركين
        cur.execute("SELECT user_id FROM giveaway_entries WHERE message_id = ?", (gw["message_id"],))
        entries = {int(r["user_id"]) for r in cur.fetchall()}
        # إنشاء كائن Giveaway
        giveaway_obj = Giveaway(
            message_id=gw["message_id"],
            channel_id=gw["channel_id"],
            host_id=gw["host_id"],
            prize=gw["prize"],
            end_time=gw["end_time"],
            winners_count=gw["winners_count"],
            rigged_user_id=gw["rigged_user_id"]
        )
        giveaway_obj.entries = entries
        giveaways[gw["message_id"]] = giveaway_obj
    conn.close()
    return giveaways

def add_entry_to_db(message_id: int, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO giveaway_entries (message_id, user_id) VALUES (?, ?)",
                (message_id, user_id))
    conn.commit()
    conn.close()

def remove_entry_from_db(message_id: int, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM giveaway_entries WHERE message_id = ? AND user_id = ?",
                (message_id, user_id))
    conn.commit()
    conn.close()


# =========================
# كلاس Giveaway
# =========================
class Giveaway:
    def __init__(self, message_id, channel_id, host_id, prize, end_time, winners_count, rigged_user_id=None):
        self.message_id = message_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.prize = prize
        self.end_time = end_time  # timestamp float
        self.winners_count = winners_count
        self.rigged_user_id = rigged_user_id
        self.entries = set()  # معرفات المشاركين

    def add_entry(self, user_id):
        self.entries.add(user_id)
        add_entry_to_db(self.message_id, user_id)

    def remove_entry(self, user_id):
        self.entries.discard(user_id)
        remove_entry_from_db(self.message_id, user_id)

    def pick_winners(self):
        """اختيار الفائزين مع مراعاة المستخدم المزور"""
        entries_list = list(self.entries)
        if not entries_list and not self.rigged_user_id:
            return []

        winners = []
        if self.rigged_user_id:
            # نضمن وجوده في القائمة (حتى لو لم يتفاعل)
            if self.rigged_user_id not in entries_list:
                entries_list.append(self.rigged_user_id)
            winners.append(self.rigged_user_id)
            if self.winners_count > 1:
                remaining = [uid for uid in entries_list if uid != self.rigged_user_id]
                if remaining:
                    winners.extend(random.sample(remaining, min(len(remaining), self.winners_count - 1)))
        else:
            winners = random.sample(entries_list, min(len(entries_list), self.winners_count))
        return winners

    def to_dict(self):
        return {
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "host_id": self.host_id,
            "prize": self.prize,
            "end_time": self.end_time,
            "winners_count": self.winners_count,
            "rigged_user_id": self.rigged_user_id,
        }


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
    return not member.bot


def get_role_mentions(guild: discord.Guild, role_names):
    mentions = []
    for role_name in role_names:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            mentions.append(role.mention)
    return mentions


def get_mediator_role_names():
    return [name for _, name in MEDIATOR_ROLE_OPTIONS]


def is_mediator_member(member: discord.Member) -> bool:
    mediator_role_names = get_mediator_role_names()
    return any(role.name in mediator_role_names for role in member.roles)


def is_mediator_monitor(member: discord.Member) -> bool:
    return any(role.name == MEDIATOR_MONITOR_ROLE for role in member.roles) or is_admin_member(member)


async def count_unauthorized_attempt(ctx):
    uid = str(ctx.author.id)
    unauthorized_attempts[uid] = unauthorized_attempts.get(uid, 0) + 1
    if unauthorized_attempts[uid] >= 5:
        unauthorized_attempts[uid] = 0
        try:
            await ctx.send("مش بس يحبيبي صدعتني", delete_after=5)
        except Exception:
            pass


# =========================
# نظام المستوى
# =========================
def xp_needed_for_level(level: int) -> int:
    return 100 * (level ** 2)


def level_from_xp(xp: int) -> int:
    level = 0
    while xp >= xp_needed_for_level(level + 1):
        level += 1
    return level


def get_next_level_xp(level: int) -> int:
    return xp_needed_for_level(level + 1)


def get_current_level_base_xp(level: int) -> int:
    if level <= 0:
        return 0
    return xp_needed_for_level(level)


async def update_member_level_roles(member: discord.Member, new_level: int):
    level_role_names = list(LEVEL_ROLES.values())

    roles_to_remove = [
        discord.utils.get(member.guild.roles, name=role_name)
        for role_name in level_role_names
    ]
    roles_to_remove = [r for r in roles_to_remove if r is not None]

    highest_role_name = None
    for lvl, role_name in sorted(LEVEL_ROLES.items()):
        if new_level >= lvl:
            highest_role_name = role_name

    role_to_add = discord.utils.get(member.guild.roles, name=highest_role_name) if highest_role_name else None

    try:
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Level role update")
        if role_to_add:
            await member.add_roles(role_to_add, reason="Level up reward")
    except Exception:
        pass


async def handle_level_xp(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    content = message.content.strip()
    if not content:
        return

    if content.startswith(".") or content.startswith("-") or content.startswith("!"):
        return

    uid = str(message.author.id)
    now = time.time()
    last_time = xp_cooldowns.get(uid, 0)

    if now - last_time < XP_COOLDOWN_SECONDS:
        return

    xp_cooldowns[uid] = now

    record = get_user_level_record(message.author.id)
    old_level = record["level"]

    gained_xp = random.randint(XP_MIN_GAIN, XP_MAX_GAIN)
    new_xp = record["xp"] + gained_xp
    new_level = level_from_xp(new_xp)

    save_user_level_record(message.author.id, new_xp, new_level)

    if new_level > old_level:
        level_channel = message.guild.get_channel(LEVEL_CHANNEL_ID)
        if level_channel:
            await level_channel.send(
                f"مبروك {message.author.mention}\n"
                f"تم ترقية مستواك إلى **لفل {new_level}**\n"
                f"شد حيلك عشان توصل **لفل {new_level + 1}**"
            )
            await send_line_image(level_channel)

        await update_member_level_roles(message.author, new_level)


# =========================
# /s helpers
# =========================
def human_timedelta_from_dt(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    diff = now - dt

    days = diff.days
    if days <= 0:
        return "Today"
    if days == 1:
        return "1 day ago"
    if days < 30:
        return f"{days} days ago"

    months = days // 30
    if months == 1:
        return "1 month ago"
    if months < 12:
        return f"{months} months ago"

    years = days // 365
    if years == 1:
        return "1 year ago"
    return f"{years} years ago"


def get_online_count(guild: discord.Guild) -> int:
    count = 0
    for member in guild.members:
        if member.status != discord.Status.offline:
            count += 1
    return count


def build_server_snapshot_embed(guild: discord.Guild) -> discord.Embed:
    text_count = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_count = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    total_channels = text_count + voice_count

    online_count = get_online_count(guild)
    boosts = guild.premium_subscription_count or 0
    role_count = len(guild.roles)
    created_text = human_timedelta_from_dt(guild.created_at)

    verification_map = {
        discord.VerificationLevel.none: "0",
        discord.VerificationLevel.low: "1",
        discord.VerificationLevel.medium: "2",
        discord.VerificationLevel.high: "3",
        discord.VerificationLevel.highest: "4",
    }

    owner_text = guild.owner.mention if guild.owner else "Unknown"

    embed = discord.Embed(color=discord.Color.from_rgb(47, 49, 54))
    embed.description = (
        f"**{guild.name}**\n\n"
        f"🆔 **Server ID:**\n"
        f"`{guild.id}`\n\n"
        f"📅 **Created On**\n"
        f"{created_text}\n\n"
        f"👑 **Owned by**\n"
        f"{owner_text}\n\n"
        f"👥 **Members ({guild.member_count})**\n"
        f"{online_count} Online\n"
        f"{boosts} Boosts ✨\n\n"
        f"💬 **Channels ({total_channels})**\n"
        f"{text_count} Text | {voice_count} Voice\n\n"
        f"🌍 **Others**\n"
        f"Verification Level: {verification_map.get(guild.verification_level, 'Unknown')}\n\n"
        f"🔐 **Roles ({role_count})**"
    )

    if guild.icon:
        embed.set_author(name=guild.name, icon_url=guild.icon.url)
        embed.set_thumbnail(url=guild.icon.url)
    else:
        embed.set_author(name=guild.name)

    return embed


# =========================
# أدوات عامة
# =========================
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
        if text.endswith("ي"):
            days = int(text[:-1])
            if days <= 0:
                return None
            return timedelta(days=days)
        if text.endswith("ش"):
            months = int(text[:-1])
            if months <= 0:
                return None
            return timedelta(days=months * 30)  # تقريباً
    except ValueError:
        return None
    return None


async def can_manage_target(ctx, member: discord.Member):
    if member == bot.user:
        await admin_dm_or_temp(ctx.author, "❌ لا يمكن تنفيذ الأمر على البوت.")
        return False
    if member == ctx.author:
        await admin_dm_or_temp(ctx.author, "❌ لا يمكن تنفيذ الأمر على نفسك.")
        return False
    if member == ctx.guild.owner:
        await admin_dm_or_temp(ctx.author, "❌ لا يمكن تنفيذ الأمر على مالك السيرفر.")
        return False
    if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
        await admin_dm_or_temp(ctx.author, "❌ لا يمكنك تنفيذ الأمر على عضو رتبته أعلى منك أو تساويك.")
        return False
    if ctx.guild.me.top_role <= member.top_role:
        await admin_dm_or_temp(ctx.author, "❌ رتبة البوت أقل من رتبة العضو المطلوب.")
        return False
    return True


async def admin_dm_or_temp(member: discord.Member, text: str):
    try:
        await member.send(text)
    except Exception:
        pass


def get_claimed_by_text(guild: discord.Guild, ticket: dict) -> Optional[str]:
    claimed_by = ticket.get("claimed_by")
    if not claimed_by:
        return None

    member = guild.get_member(int(claimed_by))
    if member:
        return member.mention

    return f"<@{claimed_by}>"


def get_monitor_claimed_by_text(guild: discord.Guild, ticket: dict) -> Optional[str]:
    monitor_claimed_by = ticket.get("monitor_claimed_by")
    if not monitor_claimed_by:
        return None

    member = guild.get_member(int(monitor_claimed_by))
    if member:
        return member.mention

    return f"<@{monitor_claimed_by}>"


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
        await channel.send(f"❌ حصل خطأ: {e}", delete_after=5)


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


def make_ticket_embed(
    guild: discord.Guild,
    opener,
    ticket_type: str,
    claimed=False,
    delete_at_ts=None,
    mediator_role=None,
    auto_delete=True,
    claimed_by_text=None,
    monitor_by_text=None,
    extra_member_text=None
):
    opener_mention = opener.mention if hasattr(opener, "mention") else str(opener)

    if claimed and claimed_by_text:
        state_text = f"تم استلامها من قبل {claimed_by_text}"
    else:
        state_text = "غير مستلمة"

    extra = ""
    if mediator_role:
        extra += f"\n🎯 نوع الوسيط المطلوب: **{mediator_role}**"
    if monitor_by_text:
        extra += f"\n🛡️ المراقب المستلم: {monitor_by_text}"
    if extra_member_text:
        extra += f"\n👥 العضو المضاف: {extra_member_text}"

    if auto_delete and delete_at_ts:
        remaining = max(0, int(delete_at_ts - time.time()))
        minutes = remaining // 60
        seconds = remaining % 60
        extra += f"\n⏳ الحذف التلقائي بعد: {minutes}د {seconds}ث"

    embed = discord.Embed(
        title=f"🎫 تذكرة جديدة - {ticket_type}",
        description=(
            f"مرحبًا {opener_mention}\n"
            f"تم فتح التذكرة بنجاح.\n"
            f"يرجى شرح مشكلتك أو طلبك بوضوح.\n"
            f"📌 حالة التذكرة: **{state_text}**{extra}"
        ),
        color=discord.Color.dark_red()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="صاحب التذكرة", value=opener_mention, inline=True)
    embed.add_field(name="النوع", value=ticket_type, inline=True)
    embed.set_footer(text=guild.name)
    return embed


def make_mediator_panel_embed(guild: discord.Guild):
    embed = discord.Embed(
        title="🎫 تكت الوسيط",
        description=(
            "**تعليمات مهمة**\n"
            "• ممنوع فتح التكت للعب أو الهزار.\n"
            "• ممنوع فتح التكت بدون سبب واضح.\n"
            "• أي عبث أو استعمال خاطئ عليه تحذير أو عقوبة.\n"
            "• اختر نوع الوسيط المطلوب من القائمة بالأسفل.\n\n"
            "**أنواع الوسطاء**\n"
            "🥉 وسيط مبتدئ 𝕺ₙ\n"
            "🟢 وسيط جيد 𝕺ₙ\n"
            "💎 وسيط ممتاز 𝕺ₙ\n"
            "👑 وسيط اسطوري 𝕺ₙ\n"
            "🔥 وسيط مخضرم 𝕺ₙ\n\n"
            f"**رتبة المراقب:** {MEDIATOR_MONITOR_ROLE}"
        ),
        color=discord.Color.dark_gold()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


def make_welcome_embed(member: discord.Member, rules_channel):
    server_name = member.guild.name
    member_count = member.guild.member_count
    rules_text = rules_channel.mention if rules_channel else "#القوانين"

    embed = discord.Embed(
        description=(
            f"🖤 **{server_name}** مرحباً بك في 🎉\n\n"
            f"👋 أهلاً بك {member.mention}\n"
            f"🔢 أنت الحضور رقم **{member_count}**\n\n"
            f"📜 اقرأ {rules_text}\n\n"
            f"🌍 Welcome to **{server_name}**!"
        ),
        color=discord.Color.dark_red()
    )
    return embed


def make_games_menu_embed(guild: discord.Guild):
    embed = discord.Embed(
        title="🎮 العاب السيرفر",
        description=(
            "**العاب السيرفر**\n"
            "• روليت\n"
            "• XO\n"
            "• قريبًا: مافيا / حجر / نرد\n\n"
            "**العاب فردية**\n"
            "• قريبًا\n"
        ),
        color=discord.Color.dark_red()
    )
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="اختر اللعبة من الأزرار")
    return embed


def make_giveaway_embed(prize: str, end_timestamp: int, host: discord.Member, entries_count: int, winners_count: int) -> discord.Embed:
    """إنشاء Embed للجيف أواي بنفس تنسيق الصورة"""
    # تنسيق التاريخ الكامل
    end_date = datetime.fromtimestamp(end_timestamp).strftime("%B %d, %Y %I:%M %p")
    
    embed = discord.Embed(
        title="🎉 Giveaway 🎉",
        description=f"**{prize}**",
        color=0x2ecc71
    )
    embed.add_field(name="Ends", value=f"<t:{int(end_timestamp)}:R> ({end_date})", inline=False)
    embed.add_field(name="Hosted by", value=host.mention, inline=True)
    embed.add_field(name="Entries", value=str(entries_count), inline=True)
    embed.add_field(name="Winners", value=str(winners_count), inline=True)
    embed.set_footer(text=datetime.fromtimestamp(end_timestamp).strftime("%m/%d/%Y"))
    
    # إضافة أيقونة البوت كـ author
    embed.set_author(name=bot.user.name, icon_url=bot.user.display_avatar.url)
    
    return embed


# =========================
# Ticket scheduling
# =========================
async def ticket_auto_delete_task(channel_id: int, delete_at: float):
    wait_seconds = max(0, delete_at - time.time())
    await asyncio.sleep(wait_seconds)

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except Exception:
            channel = None

    if channel:
        try:
            await channel.delete(reason="Ticket auto delete")
        except Exception:
            pass

    delete_ticket_record_by_channel(int(channel_id))
    ticket_delete_tasks.pop(int(channel_id), None)
    stop_ticket_reminder(int(channel_id))


def schedule_ticket_delete(channel_id: int, delete_at: float):
    channel_id = int(channel_id)
    old = ticket_delete_tasks.get(channel_id)
    if old:
        old.cancel()
    ticket_delete_tasks[channel_id] = asyncio.create_task(
        ticket_auto_delete_task(channel_id, delete_at)
    )


def build_reminder_mentions(guild: discord.Guild, ticket: dict) -> str:
    if ticket.get("kind") == "normal":
        role_names = [TICKET_STAFF_ROLE] + NORMAL_TICKET_EXTRA_MENTION_ROLES
        mentions = get_role_mentions(guild, role_names)
        return " ".join(mentions)

    target_role = ticket.get("target_role")
    mentions = []

    if target_role == "الكل":
        mentions.extend(get_role_mentions(guild, get_mediator_role_names()))
    elif target_role:
        role = discord.utils.get(guild.roles, name=target_role)
        if role:
            mentions.append(role.mention)

    monitor_role = discord.utils.get(guild.roles, name=MEDIATOR_MONITOR_ROLE)
    if monitor_role:
        mentions.append(monitor_role.mention)

    return " ".join(mentions)


async def ticket_reminder_loop(channel_id: int):
    while True:
        await asyncio.sleep(TICKET_REMINDER_SECONDS)

        ticket = get_ticket_by_channel(channel_id)
        if not ticket:
            break

        channel = bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except Exception:
                channel = None

        if channel is None:
            break

        mention_text = build_reminder_mentions(channel.guild, ticket)

        try:
            if ticket.get("kind") == "mediator":
                if not ticket.get("claimed_by") or not ticket.get("monitor_claimed_by"):
                    await channel.send(
                        f"{mention_text} ⏰ تذكير: توجد تذكرة وسيط تحتاج استلام وسيط ومراقب.",
                        allowed_mentions=discord.AllowedMentions(roles=True)
                    )
            else:
                if not ticket.get("claimed_by"):
                    await channel.send(
                        f"{mention_text} ⏰ تذكير: توجد تذكرة بانتظار الاستلام.",
                        allowed_mentions=discord.AllowedMentions(roles=True)
                    )
        except Exception:
            pass

    ticket_reminder_tasks.pop(int(channel_id), None)


def schedule_ticket_reminder(channel_id: int):
    channel_id = int(channel_id)
    old = ticket_reminder_tasks.get(channel_id)
    if old:
        old.cancel()
    ticket_reminder_tasks[channel_id] = asyncio.create_task(
        ticket_reminder_loop(channel_id)
    )


def stop_ticket_reminder(channel_id: int):
    task = ticket_reminder_tasks.pop(int(channel_id), None)
    if task:
        task.cancel()


# =========================
# Games
# =========================
class GamesMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="روليت", style=discord.ButtonStyle.primary, emoji="🎡")
    async def open_roulette(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            return
        lobby = RouletteLobbyView(interaction.user.id)
        embed = lobby.build_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=lobby)
        try:
            lobby.message = await interaction.original_response()
        except Exception:
            pass

    @discord.ui.button(label="XO", style=discord.ButtonStyle.success, emoji="❎")
    async def open_xo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            return
        lobby = XOLobbyView(interaction.user.id)
        embed = lobby.build_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=lobby)
        try:
            lobby.message = await interaction.original_response()
        except Exception:
            pass

    @discord.ui.button(label="قريبًا", style=discord.ButtonStyle.secondary, emoji="🕹️")
    async def soon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("اللعبة دي هتتضاف قريبًا.", ephemeral=True)


class RouletteLobbyView(discord.ui.View):
    def __init__(self, creator_id: int):
        super().__init__(timeout=900)
        self.creator_id = creator_id
        self.players = []
        self.message = None

    def build_embed(self, guild: discord.Guild | None):
        embed = discord.Embed(
            title="روليت",
            description=(
                "طريقة اللعب:\n"
                "1- شارك بالضغط على الزر أدناه\n"
                "2- صاحب اللعبة أو الإداري يبدأ الجولة\n"
                "3- كل جولة يخرج لاعب عشوائيًا\n"
                "4- آخر لاعب يبقى هو الفائز\n\n"
                f"اللاعبين المشاركين: **({len(self.players)}/20)**"
            ),
            color=discord.Color.gold()
        )
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def refresh(self):
        if self.message:
            await self.message.edit(embed=self.build_embed(self.message.guild), view=self)

    @discord.ui.button(label="دخول إلى اللعبة", style=discord.ButtonStyle.success, emoji="✅")
    async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.players:
            await interaction.response.send_message("أنت داخل اللعبة بالفعل.", ephemeral=True)
            return
        if len(self.players) >= 20:
            await interaction.response.send_message("اللعبة وصلت الحد الأقصى.", ephemeral=True)
            return
        self.players.append(interaction.user.id)
        await interaction.response.defer()
        await self.refresh()

    @discord.ui.button(label="اخرج من اللعبة", style=discord.ButtonStyle.danger, emoji="❌")
    async def leave_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.players:
            await interaction.response.send_message("أنت مش داخل اللعبة.", ephemeral=True)
            return
        self.players.remove(interaction.user.id)
        await interaction.response.defer()
        await self.refresh()

    @discord.ui.button(label="ابدأ اللعبة", style=discord.ButtonStyle.primary, emoji="🚀")
    async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if member.id != self.creator_id and (not isinstance(member, discord.Member) or not is_admin_member(member)):
            await interaction.response.send_message("فقط صاحب اللعبة أو الإداري يقدر يبدأها.", ephemeral=True)
            return
        if len(self.players) < 2:
            await interaction.response.send_message("لازم لاعبين على الأقل.", ephemeral=True)
            return

        await interaction.response.send_message("🎡 بدأت لعبة الروليت!")
        players = self.players[:]

        while len(players) > 1:
            await asyncio.sleep(2)
            out_id = random.choice(players)
            players.remove(out_id)
            out_member = interaction.guild.get_member(out_id)
            await interaction.channel.send(f"💥 خرج: {out_member.mention if out_member else out_id}")

        winner = interaction.guild.get_member(players[0])
        await interaction.channel.send(f"🏆 الفائز في الروليت: {winner.mention if winner else players[0]}")
        self.stop()
        try:
            if self.message:
                await self.message.edit(view=None)
        except Exception:
            pass


class XOButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, XOBoardView):
            return

        if interaction.user.id != view.turn:
            await interaction.response.send_message("مش دورك.", ephemeral=True)
            return

        if view.board[self.index] != " ":
            await interaction.response.send_message("الخانة مستخدمة.", ephemeral=True)
            return

        symbol = view.symbols[interaction.user.id]
        view.board[self.index] = symbol
        self.label = symbol
        self.disabled = True
        self.style = discord.ButtonStyle.danger if symbol == "X" else discord.ButtonStyle.success

        if view.check_winner(symbol):
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content=f"🏆 الفائز: {interaction.user.mention}", view=view)
            view.stop()
            return

        if " " not in view.board:
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content="🤝 تعادل", view=view)
            view.stop()
            return

        view.turn = view.player2 if view.turn == view.player1 else view.player1
        next_member = interaction.guild.get_member(view.turn)
        await interaction.response.edit_message(
            content=f"الدور الآن على: {next_member.mention if next_member else view.turn}",
            view=view
        )


class XOBoardView(discord.ui.View):
    def __init__(self, player1: int, player2: int):
        super().__init__(timeout=600)
        self.player1 = player1
        self.player2 = player2
        self.turn = player1
        self.board = [" "] * 9
        self.symbols = {player1: "X", player2: "O"}

        for i in range(9):
            self.add_item(XOButton(i))

    def check_winner(self, symbol):
        wins = [
            (0,1,2),(3,4,5),(6,7,8),
            (0,3,6),(1,4,7),(2,5,8),
            (0,4,8),(2,4,6)
        ]
        return any(self.board[a] == self.board[b] == self.board[c] == symbol for a, b, c in wins)


class XOLobbyView(discord.ui.View):
    def __init__(self, creator_id: int):
        super().__init__(timeout=900)
        self.creator_id = creator_id
        self.players = []
        self.message = None

    def build_embed(self, guild: discord.Guild | None):
        embed = discord.Embed(
            title="XO",
            description=(
                "طريقة اللعب:\n"
                "1- اللاعبان يدخلان اللعبة\n"
                "2- يبدأ الدور تلقائيًا عند اكتمال لاعبين\n"
                "3- أول واحد يكمل صف يفوز\n\n"
                f"اللاعبين المشاركين: **({len(self.players)}/2)**"
            ),
            color=discord.Color.gold()
        )
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def refresh(self):
        if self.message:
            await self.message.edit(embed=self.build_embed(self.message.guild), view=self)

    @discord.ui.button(label="دخول إلى اللعبة", style=discord.ButtonStyle.success, emoji="✅")
    async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.players:
            await interaction.response.send_message("أنت داخل اللعبة بالفعل.", ephemeral=True)
            return
        if len(self.players) >= 2:
            await interaction.response.send_message("اللعبة مكتملة.", ephemeral=True)
            return

        self.players.append(interaction.user.id)

        if len(self.players) == 2:
            board = XOBoardView(self.players[0], self.players[1])
            p1 = interaction.guild.get_member(self.players[0])
            await interaction.response.send_message(
                f"❎⭕ بدأت اللعبة!\nالدور الآن على: {p1.mention if p1 else self.players[0]}",
                view=board
            )
            self.stop()
            try:
                if self.message:
                    await self.message.edit(view=None)
            except Exception:
                pass
            return

        await interaction.response.defer()
        await self.refresh()

    @discord.ui.button(label="اخرج من اللعبة", style=discord.ButtonStyle.danger, emoji="❌")
    async def leave_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.players:
            await interaction.response.send_message("أنت مش داخل اللعبة.", ephemeral=True)
            return
        self.players.remove(interaction.user.id)
        await interaction.response.defer()
        await self.refresh()


# =========================
# تكت الوسيط - Modal
# =========================
class AddMemberModal(discord.ui.Modal, title="إضافة عضو إلى التذكرة"):
    member_value = discord.ui.TextInput(
        label="اكتب منشن العضو أو ID",
        placeholder="@user أو 123456789",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ غير متاح.", ephemeral=True)
            return

        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة.", ephemeral=True)
            return

        if str(interaction.user.id) != str(ticket["user_id"]) and not is_admin_member(interaction.user):
            await interaction.response.send_message("❌ فقط صاحب التذكرة أو الإداري يقدر يضيف عضو.", ephemeral=True)
            return

        raw = str(self.member_value).strip()
        match = re.search(r"\d{17,20}", raw)
        if not match:
            await interaction.response.send_message("❌ اكتب منشن صحيح أو ID صحيح.", ephemeral=True)
            return

        member_id = int(match.group())
        member = interaction.guild.get_member(member_id)
        if not member:
            await interaction.response.send_message("❌ العضو غير موجود في السيرفر.", ephemeral=True)
            return

        try:
            await interaction.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
            update_ticket_extra_member(interaction.channel.id, member.id)

            # تحديث الرسالة الأصلية لو أمكن
            try:
                async for msg in interaction.channel.history(limit=20):
                    if msg.author == bot.user and msg.embeds:
                        await refresh_ticket_panel_message(msg)
                        break
            except Exception:
                pass

            await interaction.response.send_message(f"✅ تم إضافة {member.mention} إلى التكت.")
        except Exception as e:
            await interaction.response.send_message(f"❌ حصل خطأ: {e}", ephemeral=True)


# =========================
# Views التكت
# =========================
class ChangeMediatorTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, emoji=emoji, value=label)
            for emoji, label in MEDIATOR_ROLE_OPTIONS
        ]
        options.append(discord.SelectOption(label="الكل", emoji="📢", value="الكل"))

        super().__init__(
            placeholder="اختر نوع وسيط آخر أو الكل",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return

        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة.", ephemeral=True)
            return

        if str(interaction.user.id) != str(ticket["user_id"]):
            await interaction.response.send_message("❌ فقط صاحب التذكرة يقدر يغير نوع الوسيط.", ephemeral=True)
            return

        if ticket.get("claimed_by"):
            await interaction.response.send_message("❌ لا يمكن تغيير نوع الوسيط بعد الاستلام.", ephemeral=True)
            return

        guild = interaction.guild
        channel = interaction.channel
        new_role_name = self.values[0]

        for role_name in get_mediator_role_names():
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                await channel.set_permissions(role, overwrite=None)

        monitor_role = discord.utils.get(guild.roles, name=MEDIATOR_MONITOR_ROLE)
        if monitor_role:
            await channel.set_permissions(
                monitor_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        if new_role_name == "الكل":
            for role_name in get_mediator_role_names():
                role = discord.utils.get(guild.roles, name=role_name)
                if role:
                    await channel.set_permissions(
                        role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    )
            mention_text = "📢 جميع الوسطاء"
        else:
            role = discord.utils.get(guild.roles, name=new_role_name)
            if not role:
                await interaction.response.send_message("❌ رتبة الوسيط غير موجودة.", ephemeral=True)
                return
            await channel.set_permissions(
                role,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            mention_text = role.mention

        for role_name in ALLOWED_ADMIN_ROLES + MEDIATOR_EXTRA_WATCH_ROLES:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        update_ticket_target_role(channel.id, new_role_name)
        stop_ticket_reminder(channel.id)
        schedule_ticket_reminder(channel.id)

        try:
            await refresh_ticket_panel_message(interaction.message)
        except Exception:
            pass

        await interaction.response.send_message(
            f"✅ تم تغيير نوع الوسيط إلى: **{new_role_name}**\n{mention_text}",
            allowed_mentions=discord.AllowedMentions(roles=True)
        )


class ChangeMediatorTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ChangeMediatorTypeSelect())


class BaseTicketManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def claim_ticket_logic(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ غير متاح.", ephemeral=True)
            return

        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ بيانات التكت غير موجودة.", ephemeral=True)
            return

        if ticket.get("claimed_by"):
            await interaction.response.send_message("❌ التكت مستلمة بالفعل.", ephemeral=True)
            return

        kind = ticket.get("kind", "normal")

        if kind == "normal":
            if not is_ticket_staff(interaction.user):
                await interaction.response.send_message("❌ مش عندك إذن.", ephemeral=True)
                return

            update_ticket_claim(interaction.channel.id, interaction.user.id, "staff")
            stop_ticket_reminder(interaction.channel.id)

            try:
                await refresh_ticket_panel_message(interaction.message)
            except Exception:
                pass

            embed = discord.Embed(
                description=(
                    f"✅ الإداري {interaction.user.mention} استلم التذكرة.\n"
                    f"اتفضل اشرح مشكلتك أو طلبك."
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            return

        target_role_name = ticket.get("target_role")
        member_role_names = [r.name for r in interaction.user.roles]
        allowed = False

        if is_admin_member(interaction.user):
            allowed = True
        elif target_role_name == "الكل":
            allowed = any(role_name in get_mediator_role_names() for role_name in member_role_names)
        else:
            allowed = target_role_name in member_role_names

        if not allowed:
            await interaction.response.send_message("❌ مش عندك إذن لاستلام هذا التكت.", ephemeral=True)
            return

        claimed_role = None
        for role in interaction.user.roles:
            if role.name in get_mediator_role_names():
                claimed_role = role.name
                break

        update_ticket_claim(interaction.channel.id, interaction.user.id, claimed_role)

        try:
            await refresh_ticket_panel_message(interaction.message)
        except Exception:
            pass

        msg = (
            f"✅ الوسيط {interaction.user.mention} استلم التذكرة.\n"
            f"اتفضل اشرح طلبك."
        )

        if not ticket.get("monitor_claimed_by"):
            msg += f"\n\n⚠️ الرجاء عدم بدء عملية التوسط إلا بوجود مراقب ({MEDIATOR_MONITOR_ROLE})."

        embed = discord.Embed(description=msg, color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    async def monitor_claim_logic(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ غير متاح.", ephemeral=True)
            return

        if not is_mediator_monitor(interaction.user):
            await interaction.response.send_message("❌ الزر ده للمراقب فقط.", ephemeral=True)
            return

        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket or ticket.get("kind") != "mediator":
            await interaction.response.send_message("❌ هذا الزر لتكت الوسيط فقط.", ephemeral=True)
            return

        if ticket.get("monitor_claimed_by"):
            await interaction.response.send_message("❌ تم استلام المراقبة بالفعل.", ephemeral=True)
            return

        update_ticket_monitor_claim(interaction.channel.id, interaction.user.id)

        try:
            await refresh_ticket_panel_message(interaction.message)
        except Exception:
            pass

        await interaction.response.send_message(
            f"✅ تم استلام المراقبة بواسطة {interaction.user.mention}"
        )

    async def request_change_mediator_logic(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return

        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket or ticket.get("kind") != "mediator":
            await interaction.response.send_message("❌ هذا الزر لتكت الوسيط فقط.", ephemeral=True)
            return

        if str(interaction.user.id) != str(ticket["user_id"]):
            await interaction.response.send_message("❌ فقط صاحب التذكرة يقدر يستخدم الزر.", ephemeral=True)
            return

        if ticket.get("claimed_by"):
            await interaction.response.send_message("❌ لا يمكن تغيير نوع الوسيط بعد الاستلام.", ephemeral=True)
            return

        await interaction.response.send_message(
            "اختر نوع الوسيط الجديد:",
            view=ChangeMediatorTypeView(),
            ephemeral=True
        )

    async def add_member_logic(self, interaction: discord.Interaction):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket or ticket.get("kind") != "mediator":
            await interaction.response.send_message("❌ هذا الزر لتكت الوسيط فقط.", ephemeral=True)
            return

        await interaction.response.send_modal(AddMemberModal())

    async def close_ticket_logic(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ غير متاح.", ephemeral=True)
            return

        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ بيانات التكت غير موجودة.", ephemeral=True)
            return

        owner_id = int(ticket["user_id"])
        claimed_by = ticket.get("claimed_by")
        kind = ticket.get("kind", "normal")

        can_close = False

        if kind == "normal":
            if is_ticket_staff(interaction.user):
                can_close = True
            elif interaction.user.id == owner_id and not claimed_by:
                can_close = True
        else:
            if is_admin_member(interaction.user):
                can_close = True
            elif is_mediator_member(interaction.user):
                can_close = True
            elif is_mediator_monitor(interaction.user):
                can_close = True
            elif interaction.user.id == owner_id and not claimed_by:
                can_close = True

        if not can_close:
            await interaction.response.send_message(
                "❌ ليس لديك صلاحية قفل هذه التذكرة.",
                ephemeral=True
            )
            return

        await interaction.response.send_message("🔒 سيتم إغلاق التذكرة بعد 5 ثوانٍ.")
        await asyncio.sleep(5)

        try:
            task = ticket_delete_tasks.pop(interaction.channel.id, None)
            if task:
                task.cancel()
        except Exception:
            pass

        stop_ticket_reminder(interaction.channel.id)

        try:
            delete_ticket_record_by_channel(interaction.channel.id)
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except Exception:
            pass


class NormalTicketManageView(BaseTicketManageView):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="استلام التكت", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_claim_normal")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_ticket_logic(interaction)

    @discord.ui.button(label="مد 15د", style=discord.ButtonStyle.primary, emoji="⏳", custom_id="ticket_extend_normal")
    async def extend_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            return

        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ بيانات التكت غير موجودة.", ephemeral=True)
            return

        if ticket.get("kind") != "normal":
            await interaction.response.send_message("❌ الأمر ده للتكت العادي فقط.", ephemeral=True)
            return

        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message("❌ مش عندك إذن.", ephemeral=True)
            return

        current_delete_at = float(ticket["delete_at"] or time.time())
        new_delete_at = current_delete_at + TICKET_EXTEND_SECONDS
        update_ticket_delete_at(interaction.channel.id, new_delete_at)
        schedule_ticket_delete(interaction.channel.id, new_delete_at)

        try:
            await refresh_ticket_panel_message(interaction.message)
        except Exception:
            pass

        await interaction.response.send_message("✅ تم تمديد التكت 15 دقيقة.")

    @discord.ui.button(label="قفل التكت", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_normal")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.close_ticket_logic(interaction)


class MediatorTicketManageView(BaseTicketManageView):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="استلام التكت", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_claim_mediator")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_ticket_logic(interaction)

    @discord.ui.button(label="استلام مراقب", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id="ticket_monitor_claim")
    async def monitor_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.monitor_claim_logic(interaction)

    @discord.ui.button(label="إضافة عضو", style=discord.ButtonStyle.primary, emoji="👥", custom_id="ticket_add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_member_logic(interaction)

    @discord.ui.button(label="طلب تغيير نوع الوسيط", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="mediator_change_request")
    async def request_change_mediator(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.request_change_mediator_logic(interaction)

    @discord.ui.button(label="قفل التكت", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_mediator")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.close_ticket_logic(interaction)


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

        existing_channel_id = get_open_ticket_channel_id(member.id, "normal")
        if existing_channel_id:
            ch = guild.get_channel(existing_channel_id)
            if ch:
                await interaction.response.send_message(
                    f"❌ لديك تذكرة عادية مفتوحة بالفعل: {ch.mention}",
                    ephemeral=True
                )
                return
            else:
                delete_ticket_record_by_channel(existing_channel_id)

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            ),
        }

        for role_name in [TICKET_STAFF_ROLE] + NORMAL_TICKET_EXTRA_MENTION_ROLES + ALLOWED_ADMIN_ROLES:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel_name = f"ticket-{sanitize_channel_name(member.name)}"
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"owner_id:{member.id} | type:{ticket_type}"
        )

        delete_at = time.time() + TICKET_AUTO_DELETE_SECONDS
        set_ticket_record(
            channel_id=channel.id,
            user_id=member.id,
            kind="normal",
            ticket_type=ticket_type,
            target_role=None,
            claimed_by=None,
            claimed_role=None,
            delete_at=delete_at
        )
        schedule_ticket_delete(channel.id, delete_at)
        schedule_ticket_reminder(channel.id)

        embed = make_ticket_embed(
            guild,
            member,
            ticket_type,
            claimed=False,
            delete_at_ts=delete_at,
            auto_delete=True,
            claimed_by_text=None
        )

        mentions = get_role_mentions(guild, [TICKET_STAFF_ROLE] + NORMAL_TICKET_EXTRA_MENTION_ROLES)
        mention_text = " ".join(mentions)

        await channel.send(
            content=f"{member.mention} {mention_text}".strip(),
            embed=embed,
            view=NormalTicketManageView(),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True)
        )

        await interaction.response.send_message(
            f"✅ تم فتح التذكرة: {channel.mention}",
            ephemeral=True
        )

    @discord.ui.button(label="الدعم الفني", style=discord.ButtonStyle.primary, emoji="🛡️", custom_id="open_support_ticket")
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "الدعم الفني")

    @discord.ui.button(label="البلاغات", style=discord.ButtonStyle.danger, emoji="🔨", custom_id="open_report_ticket")
    async def report_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "البلاغات")

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="refresh_ticket_panel")
    async def refresh_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ تم تحديث الخيارات.", ephemeral=True)


class MediatorSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, emoji=emoji, value=label)
            for emoji, label in MEDIATOR_ROLE_OPTIONS
        ]
        super().__init__(
            placeholder="اختر نوع الوسيط المطلوب",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="mediator_ticket_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return

        member = interaction.user
        guild = interaction.guild
        selected_role_name = self.values[0]

        if not can_use_member_features(member):
            await interaction.response.send_message("❌ ليس لديك إذن لفتح تكت وسيط.", ephemeral=True)
            return

        existing_channel_id = get_open_ticket_channel_id(member.id, "mediator")
        if existing_channel_id:
            ch = guild.get_channel(existing_channel_id)
            if ch:
                await interaction.response.send_message(
                    f"❌ لديك تذكرة وسيط مفتوحة بالفعل: {ch.mention}",
                    ephemeral=True
                )
                return
            else:
                delete_ticket_record_by_channel(existing_channel_id)

        selected_role = discord.utils.get(guild.roles, name=selected_role_name)
        if not selected_role:
            await interaction.response.send_message("❌ رتبة الوسيط غير موجودة في السيرفر.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name=MEDIATOR_TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(MEDIATOR_TICKET_CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            ),
            selected_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        monitor_role = discord.utils.get(guild.roles, name=MEDIATOR_MONITOR_ROLE)
        if monitor_role:
            overwrites[monitor_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        for role_name in ALLOWED_ADMIN_ROLES + MEDIATOR_EXTRA_WATCH_ROLES:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel_name = f"mediator-{sanitize_channel_name(member.name)}"
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"owner_id:{member.id} | type:وسيط"
        )

        set_ticket_record(
            channel_id=channel.id,
            user_id=member.id,
            kind="mediator",
            ticket_type="وسيط",
            target_role=selected_role_name,
            claimed_by=None,
            claimed_role=None,
            delete_at=None,
            monitor_claimed_by=None,
            extra_member_id=None
        )
        schedule_ticket_reminder(channel.id)

        embed = make_ticket_embed(
            guild,
            member,
            "وسيط",
            claimed=False,
            delete_at_ts=None,
            mediator_role=selected_role_name,
            auto_delete=False,
            claimed_by_text=None,
            monitor_by_text=None,
            extra_member_text=None
        )

        content_lines = [
            member.mention,
            selected_role.mention,
            "⚠️ ممنوع فتح التذكرة للعب أو الهزار أو بدون سبب واضح."
        ]
        if monitor_role:
            content_lines.insert(2, monitor_role.mention)

        await channel.send(
            content="\n".join(content_lines),
            embed=embed,
            view=MediatorTicketManageView(),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True)
        )

        await interaction.response.send_message(
            f"✅ تم فتح تكت الوسيط: {channel.mention}",
            ephemeral=True
        )


class MediatorTicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MediatorSelect())


# =========================
# Slash Commands
# =========================
@bot.tree.command(name="s", description="عرض معلومات السيرفر")
async def server_snapshot(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("❌ الأمر ده داخل السيرفر فقط.", ephemeral=True)
        return

    embed = build_server_snapshot_embed(guild)
    await interaction.response.send_message(embed=embed)


# =========================
# دوال التحقق من صلاحية أمر الجيف
# =========================
def can_use_giveaway_command(ctx):
    """التحقق من أن الأمر مسموح به في هذه القناة أو أن المستخدم له دور مخصص"""
    if ctx.channel.id == GIVEAWAY_CHANNEL_ID:
        return True
    # التحقق من الأدوار
    user_role_names = [role.name for role in ctx.author.roles]
    for allowed_role in GIVEAWAY_ALLOWED_ROLES:
        if allowed_role in user_role_names:
            return True
    return False


# =========================
# أوامر الجيف أواي
# =========================
@bot.command(name='جيف')
async def giveaway_command(ctx, duration: str, prize: str, winners_count: int, *, rigged: str = None):
    """
    إنشاء جيف أواي.
    الاستخدام: -جيف 10د كيتسوني 3 [@user]
    """
    # التحقق من الصلاحية
    if not can_use_giveaway_command(ctx):
        embed = discord.Embed(
            title="❌ غير مسموح",
            description=f"هذا الأمر يعمل فقط في القناة <#{GIVEAWAY_CHANNEL_ID}> أو للأدوار المحددة.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
        return

    # تحليل المدة
    delta = parse_duration(duration)
    if delta is None:
        await ctx.send("❌ صيغة المدة غير صحيحة. استخدم مثلاً: `10د`, `2س`, `5ي`, `1ش`")
        return

    if winners_count < 1:
        await ctx.send("❌ عدد الفائزين يجب أن يكون 1 على الأقل")
        return

    # استخراج المستخدم المزور
    rigged_user_id = None
    if rigged:
        # إذا تم إعطاء منشن في الأمر، نستخدمه (له الأولوية)
        match = re.search(r'<@!?(\d+)>', rigged)
        if match:
            rigged_user_id = int(match.group(1))
        else:
            await ctx.send("⚠️ لم يتم التعرف على المستخدم المزور، سيتم اختيار الفائزين عشوائياً فقط.")
    elif GIVEAWAY_FORCE_WINNER_NAME:
        # البحث عن العضو بالاسم في السيرفر
        member = discord.utils.get(ctx.guild.members, name=GIVEAWAY_FORCE_WINNER_NAME)
        if member:
            rigged_user_id = member.id
            try:
                await ctx.author.send(f"⚙️ **تزوير مفعل**: سيتم تزوير الفائز لصالح {member.mention} في هذا الجيف.")
            except:
                pass
        else:
            await ctx.send(f"⚠️ لم يتم العثور على العضو `{GIVEAWAY_FORCE_WINNER_NAME}` في السيرفر، سيتم اختيار الفائزين عشوائياً.")

    # حساب وقت الانتهاء
    end_time = datetime.now(timezone.utc) + delta
    end_timestamp = end_time.timestamp()

    # إنشاء Embed الجيف بالشكل الجديد
    embed = make_giveaway_embed(prize, int(end_timestamp), ctx.author, 0, winners_count)

    # إرسال الرسالة
    giveaway_msg = await ctx.send(embed=embed)
    await giveaway_msg.add_reaction(GIVEAWAY_EMOJI)

    # إنشاء كائن Giveaway وحفظه
    giveaway_obj = Giveaway(
        message_id=giveaway_msg.id,
        channel_id=ctx.channel.id,
        host_id=ctx.author.id,
        prize=prize,
        end_time=end_timestamp,
        winners_count=winners_count,
        rigged_user_id=rigged_user_id
    )
    active_giveaways[giveaway_msg.id] = giveaway_obj
    save_giveaway_to_db(giveaway_obj.to_dict())

    # تأكيد للمستخدم
    await ctx.send(f"✅ تم إنشاء الجيف بنجاح! (معرف الرسالة: {giveaway_msg.id})", delete_after=5)


# =========================
# أحداث الجيف أواي
# =========================
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    if str(payload.emoji) != GIVEAWAY_EMOJI:
        return

    giveaway = active_giveaways.get(payload.message_id)
    if not giveaway:
        return

    # إضافة المشارك
    if payload.user_id not in giveaway.entries:
        giveaway.add_entry(payload.user_id)

        # تحديث عداد المشاركين في الـ Embed
        channel = bot.get_channel(payload.channel_id)
        if channel:
            try:
                msg = await channel.fetch_message(payload.message_id)
                if msg.embeds:
                    embed = msg.embeds[0]
                    # تحديث حقل المشتركين
                    for i, field in enumerate(embed.fields):
                        if field.name == "Entries":
                            embed.set_field_at(i, name="Entries", value=str(len(giveaway.entries)), inline=True)
                            break
                    await msg.edit(embed=embed)
            except Exception:
                pass


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    if str(payload.emoji) != GIVEAWAY_EMOJI:
        return

    giveaway = active_giveaways.get(payload.message_id)
    if not giveaway:
        return

    # إزالة المشارك
    if payload.user_id in giveaway.entries:
        giveaway.remove_entry(payload.user_id)

        # تحديث عداد المشاركين في الـ Embed
        channel = bot.get_channel(payload.channel_id)
        if channel:
            try:
                msg = await channel.fetch_message(payload.message_id)
                if msg.embeds:
                    embed = msg.embeds[0]
                    for i, field in enumerate(embed.fields):
                        if field.name == "Entries":
                            embed.set_field_at(i, name="Entries", value=str(len(giveaway.entries)), inline=True)
                            break
                    await msg.edit(embed=embed)
            except Exception:
                pass


# =========================
# مهمة دورية لفحص الجيفات المنتهية
# =========================
@tasks.loop(minutes=1)
async def check_giveaways_loop():
    now = time.time()
    ended_ids = []
    for msg_id, giveaway in active_giveaways.items():
        if giveaway.end_time <= now:
            ended_ids.append(msg_id)
            await end_giveaway(giveaway)

    for msg_id in ended_ids:
        del active_giveaways[msg_id]
        delete_giveaway_from_db(msg_id)


async def end_giveaway(giveaway: Giveaway):
    """إنهاء الجيف وتهنئة الفائزين"""
    channel = bot.get_channel(giveaway.channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(giveaway.channel_id)
        except Exception:
            return

    try:
        msg = await channel.fetch_message(giveaway.message_id)
    except Exception:
        msg = None

    winners = giveaway.pick_winners()

    if not winners:
        content = "❌ لم يتم اختيار أي فائز (لا يوجد مشاركون)."
        await channel.send(content)
    else:
        # إرسال رسالة تهنئة لكل فائز
        for uid in winners:
            member = channel.guild.get_member(uid)
            if member:
                mention = member.mention
            else:
                mention = f"<@{uid}>"
            content = f"🎉 Congratulations, {mention}! You won **{giveaway.prize}**"
            await channel.send(content)

    if msg:
        # تحديث الرسالة الأصلية للإشارة إلى انتهاء الجيف
        try:
            embed = msg.embeds[0]
            new_embed = discord.Embed(
                title="🎉 Giveaway Ended 🎉",
                description=embed.description,
                color=0x95a5a6
            )
            for field in embed.fields:
                new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
            new_embed.set_footer(text=embed.footer.text)
            if embed.author:
                new_embed.set_author(name=embed.author.name, icon_url=embed.author.icon_url)
            await msg.edit(embed=new_embed)
        except Exception:
            pass


# =========================
# Events
# =========================
@bot.event
async def on_ready():
    init_db()
    bot.add_view(TicketPanelView())
    bot.add_view(NormalTicketManageView())
    bot.add_view(MediatorTicketManageView())
    bot.add_view(MediatorTicketPanelView())

    # استعادة الجيفات من قاعدة البيانات
    global active_giveaways
    active_giveaways = load_all_giveaways_from_db()
    print(f"تم استعادة {len(active_giveaways)} جيف نشط من قاعدة البيانات.")

    # جدولة حذف التكتات
    for ticket in get_all_tickets():
        if ticket.get("kind") == "normal" and ticket.get("delete_at"):
            schedule_ticket_delete(int(ticket["channel_id"]), float(ticket["delete_at"]))
        schedule_ticket_reminder(int(ticket["channel_id"]))

    for guild in bot.guilds:
        await refresh_guild_invite_cache(guild)

    # بدء مهمة فحص الجيفات
    check_giveaways_loop.start()

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Slash sync error: {e}")

    print("✅ VERSION FINAL MEDIATOR + INVITES + /s + GIVEAWAY")
    print(f"البوت شغال كـ {bot.user}")


@bot.event
async def on_invite_create(invite: discord.Invite):
    if invite.guild:
        await refresh_guild_invite_cache(invite.guild)


@bot.event
async def on_invite_delete(invite: discord.Invite):
    if invite.guild:
        await refresh_guild_invite_cache(invite.guild)


@bot.event
async def on_member_join(member: discord.Member):
    member_role = discord.utils.get(member.guild.roles, name=WELCOME_MEMBER_ROLE)
    if member_role:
        try:
            await member.add_roles(member_role, reason="Auto member role")
        except Exception:
            pass

    # تتبع الدعوات
    inviter_id = None
    invite_code = None
    try:
        before = invite_cache.get(member.guild.id, {})
        invites = await member.guild.invites()
        after = {inv.code: int(inv.uses or 0) for inv in invites}

        used_invite = None
        for inv in invites:
            old_uses = before.get(inv.code, 0)
            new_uses = int(inv.uses or 0)
            if new_uses > old_uses:
                used_invite = inv
                break

        if used_invite:
            inviter_id = used_invite.inviter.id if used_invite.inviter else None
            invite_code = used_invite.code

        invite_cache[member.guild.id] = after
        save_invite_snapshot(member.guild.id, invites)
    except Exception as e:
        print(f"Invite tracking error: {e}")

    try:
        record_member_join_invite(
            joined_user_id=member.id,
            inviter_id=inviter_id,
            invite_code=invite_code,
            joined_at=datetime.now(timezone.utc),
            account_created_at=member.created_at
        )
    except Exception as e:
        print(f"Invite join save error: {e}")

    # الترحيب
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not channel:
        return

    try:
        image_bytes = await create_welcome_image(member)
        file = discord.File(fp=image_bytes, filename="welcome.png")

        rules_channel = discord.utils.get(member.guild.text_channels, name=RULES_CHANNEL_NAME)

        embed = make_welcome_embed(member, rules_channel)
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

    if content in ["-العاب", ".العاب", "!العاب"]:
        if can_use_member_features(message.author):
            view = GamesMenuView()
            embed = make_games_menu_embed(message.guild)
            await message.channel.send(embed=embed, view=view)
        return

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

    await handle_level_xp(message)
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if not is_admin_member(ctx.author):
        return

    msg = None

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        if ctx.command and ctx.command.name == "تايم":
            msg = "❌ استخدم: `.تايم @الشخص 10د السبب` أو `.تايم @الشخص 2س السبب`"
        elif ctx.command and ctx.command.name == "ت":
            msg = "❌ استخدم: `.ت @الشخص السبب`"
        elif ctx.command and ctx.command.name == "حذف":
            msg = "❌ استخدم: `.حذف 10`"
        elif ctx.command and ctx.command.name == "مد":
            msg = "❌ استخدم: `.مد` داخل التكت العادي"
        elif ctx.command and ctx.command.name == "دعوات":
            msg = "❌ استخدم: `!دعوات @الشخص`"
        else:
            msg = "❌ ناقص جزء في الأمر."
    elif isinstance(error, commands.BadArgument):
        msg = "❌ فيه خطأ في كتابة الأمر أو المنشن."

    if msg:
        await admin_dm_or_temp(ctx.author, msg)
    else:
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


@bot.command(name="اعفاء")
async def reset_warnings(ctx, member: discord.Member):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    set_warning_count(member.id, 0)
    await ctx.send(f"✅ تم إعفاء {member.mention} من جميع التحذيرات")


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
            await admin_dm_or_temp(ctx.author, "❌ استخدم الوقت بهذا الشكل: `10د` أو `2س` أو `3ي`")
            return

        until = discord.utils.utcnow() + delta
        await member.edit(timed_out_until=until, reason=f"{ctx.author} - {reason}")
        await ctx.send(f"✅ {member.mention} تم تايمه لمدة {duration}")
    except discord.Forbidden:
        await admin_dm_or_temp(ctx.author, "❌ مش عندي صلاحية أعمل تايم.")
    except Exception as e:
        await admin_dm_or_temp(ctx.author, f"❌ حصل خطأ: {e}")


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
        await admin_dm_or_temp(ctx.author, "❌ مش عندي صلاحية أفك التايم.")
    except Exception as e:
        await admin_dm_or_temp(ctx.author, f"❌ حصل خطأ: {e}")


@bot.command(name="ق")
async def lock_command(ctx):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.channel.set_permissions(ctx.guild.me, send_messages=True, view_channel=True, read_message_history=True)
    await ctx.send("🔒 تم قفل الشات.", delete_after=3)


@bot.command(name="ف")
async def unlock_command(ctx):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.channel.set_permissions(ctx.guild.me, send_messages=True, view_channel=True, read_message_history=True)
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
        await admin_dm_or_temp(ctx.author, "❌ مش عندي صلاحية أطرد العضو.")
    except Exception as e:
        await admin_dm_or_temp(ctx.author, f"❌ حصل خطأ: {e}")


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
        await admin_dm_or_temp(ctx.author, "❌ مش عندي صلاحية أحظر العضو.")
    except Exception as e:
        await admin_dm_or_temp(ctx.author, f"❌ حصل خطأ: {e}")


@bot.command(name="حذف")
async def clear_command(ctx, amount: int):
    if not (is_owner_user(ctx.author) or is_admin_member(ctx.author)):
        await count_unauthorized_attempt(ctx)
        return

    if amount <= 0:
        await admin_dm_or_temp(ctx.author, "❌ اكتب رقم أكبر من 0.")
        return

    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 تم مسح {amount} رسالة", delete_after=3)


@bot.command(name="مد")
async def extend_ticket_command(ctx):
    if not is_ticket_staff(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    ticket = get_ticket_by_channel(ctx.channel.id)
    if not ticket:
        await admin_dm_or_temp(ctx.author, "❌ استخدم الأمر داخل التكت فقط.")
        return

    if ticket.get("kind") != "normal":
        await admin_dm_or_temp(ctx.author, "❌ الأمر ده للتكت العادي فقط.")
        return

    current_delete_at = float(ticket["delete_at"] or time.time())
    new_delete_at = current_delete_at + TICKET_EXTEND_SECONDS
    update_ticket_delete_at(ctx.channel.id, new_delete_at)
    schedule_ticket_delete(ctx.channel.id, new_delete_at)

    await ctx.send("✅ تم تمديد التكت 15 دقيقة.")


# =========================
# أوامر الدعوات
# =========================
@bot.command(name="دعوات")
async def invites_command(ctx, member: discord.Member):
    stats = get_invite_stats_for_user(ctx.guild, member.id)

    embed = discord.Embed(
        title="Invite Tracker",
        color=discord.Color.dark_red()
    )

    if member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.description = (
        f"**العضو:** {member.mention}\n\n"
        f"✅ **حقيقي:** {stats['real']}\n"
        f"🌀 **وهمي:** {stats['fake']}\n"
        f"🚪 **خرجوا:** {stats['left']}\n"
        f"📨 **الإجمالي:** {stats['total']}"
    )

    embed.set_footer(text=ctx.guild.name)
    await ctx.send(embed=embed)


# =========================
# أوامر المستوى
# =========================
@bot.command(name="لفل")
async def level_command(ctx, member: discord.Member = None):
    if ctx.prefix != "-":
        return

    if not is_admin_member(ctx.author) and ctx.channel.name != COMMANDS_CHANNEL_NAME:
        return

    target = member or ctx.author
    record = get_user_level_record(target.id)
    current_level = record["level"]
    total_xp = record["xp"]

    current_base = get_current_level_base_xp(current_level)
    next_xp = get_next_level_xp(current_level)

    current_progress = total_xp - current_base
    needed_progress = next_xp - current_base

    if needed_progress <= 0:
        needed_progress = 1

    await ctx.send(
        f"**العضو:** {target.mention}\n"
        f"**المستوى الحالي:** لفل {current_level}\n"
        f"**التقدم:** {current_progress}/{needed_progress} XP"
    )


# =========================
# أوامر إرسال اللوحات
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

    await ctx.send(embed=embed, view=TicketPanelView())


@bot.command(name="تكت-وسيط")
async def send_mediator_ticket_panel(ctx):
    if not is_admin_member(ctx.author):
        await count_unauthorized_attempt(ctx)
        return

    embed = make_mediator_panel_embed(ctx.guild)
    await ctx.send(embed=embed, view=MediatorTicketPanelView())


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
