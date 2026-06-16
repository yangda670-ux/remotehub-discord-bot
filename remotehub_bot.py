import os
import re
import logging
import aiohttp
import discord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GAS_URL = os.environ.get(
    "GAS_URL",
    "https://script.google.com/macros/s/AKfycbxDM-TKpvY8VWG8DGuAdqZVKsogAU56mehr6XBVEMM4EKUj4ksrDyQpjl6E9yMXjWY75A/exec",
)

# チャンネル名 → 単価（円/件）。None は報酬計算対象外（勤怠管理のみ）
CHANNEL_RATES: dict[str, int | None] = {
    "五味八珍-cs": 50,
    "不動産cs": 50,
    "株式会社sou": 80,
    "採用面談-代行": 300,
    "サロン-公式line返信": 10,
    "出勤報告部屋": None,
}

# 上記チャンネル配下で報告を拾う子チャンネル名（スレッド・カテゴリ内チャンネル）
REPORT_CHILD_KEYWORDS = {"報告スペース", "報告", "件数報告"}

REPORT_FIELDS = ["日付", "件数", "伝達事項", "その他"]

# 出勤報告部屋でログイン時刻として認識するキーワード
LOGIN_PATTERNS = [
    re.compile(r"ログイン[：:]\s*(.+)"),
    re.compile(r"出勤[：:]\s*(.+)"),
    re.compile(r"開始[：:]\s*(.+)"),
]


def parse_report(content: str) -> dict:
    result = {}
    current_field = None
    current_lines = []

    for line in content.splitlines():
        matched = False
        for field in REPORT_FIELDS:
            m = re.match(rf"^{field}[：:]\s*(.*)", line.strip())
            if m:
                if current_field:
                    result[current_field] = "\n".join(current_lines).strip()
                current_field = field
                current_lines = [m.group(1).strip()]
                matched = True
                break
        if not matched and current_field:
            current_lines.append(line.strip())

    if current_field:
        result[current_field] = "\n".join(current_lines).strip()

    return result


def is_report_message(content: str) -> bool:
    count = sum(1 for f in REPORT_FIELDS if re.search(rf"{f}[：:]", content))
    return count >= 2


def parse_login_time(content: str) -> str | None:
    for pattern in LOGIN_PATTERNS:
        m = pattern.search(content)
        if m:
            return m.group(1).strip()
    return None


def resolve_channel(channel) -> tuple[str | None, str]:
    """
    対象チャンネルを特定し (親チャンネル名, チャンネル名) を返す。
    対象外の場合は (None, チャンネル名) を返す。
    """
    name = channel.name

    if name in CHANNEL_RATES:
        parent_name = channel.category.name if hasattr(channel, "category") and channel.category else ""
        return name, parent_name

    # スレッドの場合：スレッド名が子チャンネルキーワードで、親が対象チャンネル
    if isinstance(channel, discord.Thread):
        if name in REPORT_CHILD_KEYWORDS and channel.parent and channel.parent.name in CHANNEL_RATES:
            return channel.parent.name, name

    # カテゴリ内チャンネルの場合
    if name in REPORT_CHILD_KEYWORDS:
        category = getattr(channel, "category", None)
        if category and category.name in CHANNEL_RATES:
            return category.name, name

    return None, name


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    logger.info("Bot ready: %s (ID: %s)", client.user, client.user.id)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    parent_channel, sub_channel = resolve_channel(message.channel)
    if parent_channel is None:
        return

    rate = CHANNEL_RATES[parent_channel]
    is_attendance = rate is None  # 出勤報告部屋など報酬計算対象外

    if is_attendance:
        # 勤怠管理：ログイン時刻を記録
        login_time = parse_login_time(message.content)
        if login_time is None:
            return

        payload = {
            "type": "attendance",
            "member": message.author.display_name,
            "channel": parent_channel,
            "sub_channel": sub_channel if sub_channel != parent_channel else "",
            "login_time": login_time,
            "message_url": message.jump_url,
            "timestamp": message.created_at.isoformat(),
        }
        logger.info("Attendance from %s at %s", payload["member"], login_time)

    else:
        # 件数報告：報酬計算
        if not is_report_message(message.content):
            return

        report = parse_report(message.content)
        if not report:
            return

        count_str = report.get("件数", "0")
        try:
            count = int(re.sub(r"[^\d]", "", count_str))
        except ValueError:
            count = 0

        reward = count * rate

        payload = {
            "type": "report",
            "member": message.author.display_name,
            "channel": parent_channel,
            "sub_channel": sub_channel if sub_channel != parent_channel else "",
            "date": report.get("日付", ""),
            "count": count,
            "rate": rate,
            "reward": reward,
            "notes": report.get("伝達事項", ""),
            "other": report.get("その他", ""),
            "message_url": message.jump_url,
            "timestamp": message.created_at.isoformat(),
        }
        logger.info(
            "Report from %s in #%s: %d件 × %d円 = %d円",
            payload["member"], parent_channel, count, rate, reward,
        )

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GAS_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    await message.add_reaction("✅")
                    logger.info("GAS accepted (200)")
                else:
                    body = await resp.text()
                    logger.error("GAS returned %s: %s", resp.status, body)
                    await message.add_reaction("❌")
        except Exception as e:
            logger.exception("Failed to POST to GAS: %s", e)
            await message.add_reaction("❌")


client.run(DISCORD_TOKEN)
