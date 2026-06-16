import os
import re
import logging
import aiohttp
import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GAS_URL = os.environ.get(
    "GAS_URL",
    "https://script.google.com/macros/s/AKfycbxDM-TKpvY8VWG8DGuAdqZVKsogAU56mehr6XBVEMM4EKUj4ksrDyQpjl6E9yMXjWY75A/exec",
)

REPORT_FIELDS = ["日付", "件数", "伝達事項", "その他"]


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
    if not is_report_message(message.content):
        return

    report = parse_report(message.content)
    if not report:
        return

    payload = {
        "member": message.author.display_name,
        "channel": message.channel.name,
        "date": report.get("日付", ""),
        "count": report.get("件数", ""),
        "notes": report.get("伝達事項", ""),
        "other": report.get("その他", ""),
        "message_url": message.jump_url,
        "timestamp": message.created_at.isoformat(),
    }

    logger.info("Sending report from %s in #%s", payload["member"], payload["channel"])

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GAS_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    await message.add_reaction("✅")
                    logger.info("GAS accepted report (200)")
                else:
                    body = await resp.text()
                    logger.error("GAS returned %s: %s", resp.status, body)
                    await message.add_reaction("❌")
        except Exception as e:
            logger.exception("Failed to POST to GAS: %s", e)
            await message.add_reaction("❌")


client.run(DISCORD_TOKEN)
