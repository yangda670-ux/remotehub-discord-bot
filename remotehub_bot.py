import os
import re
import math
import logging
from datetime import date, datetime, time, timedelta, timezone
import aiohttp
import discord
from discord.ext import tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GAS_URL = os.environ.get(
    "GAS_URL",
    "https://script.google.com/macros/s/AKfycbxDM-TKpvY8VWG8DGuAdqZVKsogAU56mehr6XBVEMM4EKUj4ksrDyQpjl6E9yMXjWY75A/exec",
)

# 営業進捗報告テンプレートの投稿先チャンネル。
# SALES_REPORT_CHANNEL_ID（チャンネルID）を優先し、未設定なら SALES_REPORT_CHANNEL_NAME の名前で検索する。
SALES_REPORT_CHANNEL_ID = os.environ.get("SALES_REPORT_CHANNEL_ID")
SALES_REPORT_CHANNEL_NAME = os.environ.get("SALES_REPORT_CHANNEL_NAME", "改テック")

JST = timezone(timedelta(hours=9))

# 投稿曜日：火曜(1)・木曜(3)。Python の weekday() は月曜=0始まり。
SALES_REPORT_WEEKDAYS = {1, 3}

# 毎日 UTC 00:00 = JST 09:00 にタスクを起動し、曜日判定は post_sales_report_template 内で行う。
SALES_REPORT_POST_TIME_UTC = time(hour=0, minute=0, tzinfo=timezone.utc)

SALES_REPORT_TEMPLATE = """【営業進捗報告】

■ 営業活動数
・DM送付：
・フォーム送信：{form_line}
・メール送信：
・その他：

■ 反応状況
・返信件数：
・商談化件数：
・紹介見込み：
・成約見込み：

■ 主な反応内容
・
・
・

■ 課題・気づき
・
・

■ 次回までの予定
・
・

■ その他共有事項
・"""

# チャンネル名 → 単価（円/件）。None は報酬計算対象外（勤怠管理のみ）
CHANNEL_RATES: dict[str, int | None] = {
    "五味八珍-cs-🍚": 50,
    "不動産cs-🏠": 50,
    "株式会社sou": 100,
    "採用面談-代行🏃‍♀️‍➡️": 300,
    "サロン-公式line返信": 10,
    "営業テレアポチーム": 1100,
    "フェイシャルサロンline": 10,
    "ウェブアプリcs": 50,
    "タクシー案件": 120,
    "経理": 1000,  # 時給制。件数欄に稼働時間を入力する運用
    "出勤報告部屋": None,
}

# チャンネル名 → {メンバー名: 単価}。CHANNEL_RATES より優先される例外単価
MEMBER_RATE_OVERRIDES: dict[str, dict[str, int]] = {
    "五味八珍-cs-🍚": {"こやま": 60},
    "採用面談-代行🏃‍♀️‍➡️": {"ほの": 500},
}

# 日額固定＋時間割のハイブリッド単価チャンネル（開始・終了時刻から実働時間を計算）
# regular_hours: 規定時間 / day_rate: 規定時間ちょうどの日額 / overtime_rate: 規定時間超過分の円/時
# revenue_rate: 案件側の売上計算用の円/時（外注費とは別に売上をBotから送信する）
HYBRID_RATE_CHANNELS: dict[str, dict[str, float]] = {
    "corder架電": {
        "regular_hours": 6,
        "day_rate": 5000,
        "overtime_rate": 1000,
        "revenue_rate": 1500,
    },
    "株式会社composure架電": {
        "regular_hours": 9,
        "day_rate": 6500,
        "overtime_rate": 1000,
        "revenue_rate": 1300,
    },
}

# ハイブリッド単価チャンネルの実際のDiscordチャンネル/スレッド名と一致しない場合に備え、
# メッセージ先頭行の案件ラベル（例:「Composure」「CORDER」）からも判定できるようにする
PROJECT_LABEL_ALIASES: dict[str, str] = {
    "composure": "株式会社composure架電",
    "corder": "corder架電",
}


def detect_project_from_content(content: str) -> str | None:
    for line in content.splitlines():
        label = line.strip().lower()
        if not label:
            continue
        for alias, channel_name in PROJECT_LABEL_ALIASES.items():
            if label.startswith(alias):
                return channel_name
        break  # 先頭の非空行のみ見る
    return None

# 固定月額報酬のため単価計算をしないチャンネル（報告は記録するのみ）
FIXED_FEE_CHANNELS: dict[str, int] = {
    "エアコン案件": 30000,
}

# 上記チャンネル配下で報告を拾う子チャンネル（スレッド・カテゴリ内チャンネル）の判定キーワード。
# 運用側で「報告スレッド」→「報告チャンネル」のように名称変更されても追従できるよう、
# 完全一致ではなく「報告」を含むかどうかで判定する。
REPORT_CHILD_NAME_HINT = "報告"

REPORT_FIELDS = ["日付", "件数", "伝達事項", "その他", "案件", "対応者", "開始時刻", "終了時刻"]

# 出勤報告部屋でログイン時刻として認識するキーワード
LOGIN_PATTERNS = [
    re.compile(r"ログイン[：:]\s*(.+)"),
    re.compile(r"出勤[：:]\s*(.+)"),
    re.compile(r"開始[：:]\s*(.+)"),
]

# 「9:00」「09時00分」などの時刻表記から分数（0時からの経過分）を読み取る
TIME_PATTERN = re.compile(r"(\d{1,2})\s*[:：時]\s*(\d{1,2})?\s*分?")

# 「7/30」「2026/7/30」のような年省略可のスラッシュ区切り日付
DATE_PATTERN = re.compile(r"(?:(\d{4})[/／])?(\d{1,2})[/／](\d{1,2})")


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


def parse_time_to_minutes(text: str) -> int | None:
    """「9:00」「09時00分」等の時刻表記を0時からの経過分に変換する（全角コロン「：」も対応）。"""
    m = TIME_PATTERN.search(text.strip())
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    return hour * 60 + minute


def normalize_date(text: str) -> str:
    """「7/30」のような年省略形式を当年のISO日付に正規化する。パースできなければ元の文字列を返す。"""
    m = DATE_PATTERN.search(text.strip())
    if not m:
        return text.strip()
    year = int(m.group(1)) if m.group(1) else datetime.now().year
    month, day = int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return text.strip()


# 対象チャンネル名の集合（CHANNEL_RATES / HYBRID_RATE_CHANNELS / FIXED_FEE_CHANNELS のいずれか）
ALL_TRACKED_CHANNELS = set(CHANNEL_RATES) | set(HYBRID_RATE_CHANNELS) | set(FIXED_FEE_CHANNELS)


def resolve_channel(channel) -> tuple[str | None, str]:
    """
    対象チャンネルを特定し (親チャンネル名, チャンネル名) を返す。
    対象外の場合は (None, チャンネル名) を返す。
    """
    name = channel.name

    if name in ALL_TRACKED_CHANNELS:
        parent_name = channel.category.name if hasattr(channel, "category") and channel.category else ""
        return name, parent_name

    # スレッドの場合：スレッド名に「報告」を含み、親が対象チャンネル
    if isinstance(channel, discord.Thread):
        if REPORT_CHILD_NAME_HINT in name and channel.parent and channel.parent.name in ALL_TRACKED_CHANNELS:
            return channel.parent.name, name

    # カテゴリ内チャンネルの場合：チャンネル名に「報告」を含み、カテゴリが対象チャンネル
    if REPORT_CHILD_NAME_HINT in name:
        category = getattr(channel, "category", None)
        if category and category.name in ALL_TRACKED_CHANNELS:
            return category.name, name

    return None, name


def resolve_rate(channel_name: str, member_name: str) -> int | None:
    """チャンネルとメンバーから適用単価を決定する。MEMBER_RATE_OVERRIDES を優先し、
    該当がなければ CHANNEL_RATES の値を使う。"""
    overrides = MEMBER_RATE_OVERRIDES.get(channel_name, {})
    if member_name in overrides:
        return overrides[member_name]
    return CHANNEL_RATES[channel_name]


OVERTIME_GRACE_MINUTES = 5  # 規定時間超過がこの分数未満なら誤差として切り捨て、残業扱いにしない


def calc_hybrid_cost(worked_hours: float, cfg: dict) -> tuple[int, int]:
    """(通常分の外注費, 残業分の外注費) を返す。円未満は切り捨て。
    実働時間が規定時間以上 → 日額固定＋超過分×残業単価
    （超過が OVERTIME_GRACE_MINUTES 分未満の場合は誤差として切り捨て、規定時間ちょうど扱い）
    実働時間が規定時間未満 → 実働時間×時間割単価（日額÷規定時間、円未満切り捨て）"""
    regular_hours = cfg["regular_hours"]
    day_rate = int(cfg["day_rate"])
    if worked_hours >= regular_hours:
        excess_hours = worked_hours - regular_hours
        if excess_hours * 60 < OVERTIME_GRACE_MINUTES:
            return day_rate, 0
        overtime_cost = math.floor(excess_hours * cfg["overtime_rate"])
        return day_rate, overtime_cost
    hourly_rate = math.floor(day_rate / regular_hours)
    normal_cost = math.floor(worked_hours * hourly_rate)
    return normal_cost, 0


async def post_to_gas(session: aiohttp.ClientSession, payload: dict) -> int:
    """GAS WebApp にクエリパラメータ付きGETで送信する（doGet で受け取る）。"""
    timeout = aiohttp.ClientTimeout(total=15)
    # 日本語を含む値は urllib が自動でパーセントエンコードする
    params = {k: str(v) for k, v in payload.items()}
    async with session.get(GAS_URL, params=params, timeout=timeout) as resp:
        return resp.status


async def fetch_sales_form_summary() -> tuple[int, int] | None:
    """「完了件数集計」シートの合計リスト作成件数・フォーム送信件数を GAS 経由で取得する。
    取得できない場合は None を返す（呼び出し側は空欄のまま投稿する）。"""
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GAS_URL, params={"type": "sales_summary"}, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.error("sales_summary GAS returned %s", resp.status)
                    return None
                data = await resp.json(content_type=None)
    except Exception:
        logger.exception("Failed to fetch sales summary from GAS")
        return None

    if "error" in data:
        logger.error("sales_summary error: %s", data["error"])
        return None

    return int(data.get("list_count", 0)), int(data.get("form_count", 0))


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)


async def resolve_sales_report_channel() -> discord.abc.Messageable | None:
    """SALES_REPORT_CHANNEL_ID（優先）または SALES_REPORT_CHANNEL_NAME に一致するテキストチャンネルを返す。"""
    if SALES_REPORT_CHANNEL_ID:
        channel = client.get_channel(int(SALES_REPORT_CHANNEL_ID))
        if channel is not None:
            return channel
        logger.error("SALES_REPORT_CHANNEL_ID=%s のチャンネルが見つかりません", SALES_REPORT_CHANNEL_ID)

    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.name == SALES_REPORT_CHANNEL_NAME:
                return channel
    return None


@tasks.loop(time=SALES_REPORT_POST_TIME_UTC)
async def post_sales_report_template():
    """毎週火曜・木曜の朝9:00頃（JST）に営業進捗報告テンプレートを自動投稿する。"""
    now_jst = datetime.now(JST)
    if now_jst.weekday() not in SALES_REPORT_WEEKDAYS:
        return

    channel = await resolve_sales_report_channel()
    if channel is None:
        logger.error(
            "営業進捗報告の投稿先チャンネルが見つかりません（SALES_REPORT_CHANNEL_ID または name=%s）",
            SALES_REPORT_CHANNEL_NAME,
        )
        return

    summary = await fetch_sales_form_summary()
    if summary is not None:
        list_count, form_count = summary
        form_line = f"フォーム送信{form_count}件／リスト作成{list_count}件"
    else:
        form_line = ""

    await channel.send(SALES_REPORT_TEMPLATE.format(form_line=form_line))
    logger.info("Posted sales report template to #%s", channel.name)


@post_sales_report_template.before_loop
async def before_post_sales_report_template():
    await client.wait_until_ready()


@client.event
async def on_ready():
    logger.info("Bot ready: %s (ID: %s)", client.user, client.user.id)
    if not post_sales_report_template.is_running():
        post_sales_report_template.start()


def build_attendance_payload(parent_channel: str, sub_channel: str, message: discord.Message) -> dict | None:
    """出勤報告部屋など：ログイン時刻を記録するのみで報酬計算はしない。"""
    login_time = parse_login_time(message.content)
    if login_time is None:
        return None

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
    return payload


def build_report_payload(parent_channel: str, sub_channel: str, message: discord.Message, rate: int) -> dict | None:
    """件数×単価で報酬を計算する通常チャンネル向け。"""
    if not is_report_message(message.content):
        return None

    report = parse_report(message.content)
    if not report:
        return None

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
    return payload


def build_fixed_fee_payload(parent_channel: str, sub_channel: str, message: discord.Message) -> dict | None:
    """エアコン案件など：固定月額のため単価計算はせず、報告のみ記録する。
    monthly_fee はメッセージ件数に関わらず常に同じ固定値（月次集計はスプレッドシート側で行う）。"""
    if not is_report_message(message.content):
        return None

    report = parse_report(message.content)
    if not report:
        return None

    member = report.get("対応者") or message.author.display_name

    payload = {
        "type": "fixed_fee",
        "member": member,
        "channel": parent_channel,
        "sub_channel": sub_channel if sub_channel != parent_channel else "",
        "date": report.get("日付", ""),
        "monthly_fee": FIXED_FEE_CHANNELS[parent_channel],
        "notes": report.get("伝達事項", ""),
        "message_url": message.jump_url,
        "timestamp": message.created_at.isoformat(),
    }
    logger.info(
        "Fixed-fee report from %s in #%s (月額%d円は固定計上)",
        member, parent_channel, FIXED_FEE_CHANNELS[parent_channel],
    )
    return payload


def build_hybrid_payload(parent_channel: str, sub_channel: str, message: discord.Message) -> tuple[dict | None, str | None]:
    """corder架電・株式会社Composure架電など：開始/終了時刻から実働時間を算出し、
    日額固定＋残業時間割のハイブリッド単価で外注費と売上を計算する。
    戻り値は (payload, warning)。報告として認識できなければ (None, None)、
    報告らしいが時刻が読み取れない場合は (None, 警告文) を返す。"""
    if not is_report_message(message.content):
        return None, None

    report = parse_report(message.content)
    if not report:
        return None, None

    start_min = parse_time_to_minutes(report.get("開始時刻", ""))
    end_min = parse_time_to_minutes(report.get("終了時刻", ""))
    if start_min is None or end_min is None or end_min <= start_min:
        logger.warning("Invalid start/end time in #%s: %r", parent_channel, message.content)
        return None, "⚠開始時刻・終了時刻の形式をご確認ください（例：9:00〜18:00）"

    worked_hours = (end_min - start_min) / 60
    cfg = HYBRID_RATE_CHANNELS[parent_channel]
    normal_cost, overtime_cost = calc_hybrid_cost(worked_hours, cfg)
    reward = normal_cost + overtime_cost
    revenue = math.floor(worked_hours * cfg["revenue_rate"])

    member = report.get("対応者") or message.author.display_name

    payload = {
        "type": "hybrid_report",
        "member": member,
        "channel": parent_channel,
        "sub_channel": sub_channel if sub_channel != parent_channel else "",
        "project": report.get("案件", parent_channel),
        "date": normalize_date(report.get("日付", "")),
        "start_time": report.get("開始時刻", ""),
        "end_time": report.get("終了時刻", ""),
        "worked_hours": round(worked_hours, 2),
        "normal_cost": normal_cost,
        "overtime_cost": overtime_cost,
        "reward": reward,
        "revenue": revenue,
        "notes": report.get("伝達事項", ""),
        "message_url": message.jump_url,
        "timestamp": message.created_at.isoformat(),
    }
    logger.info(
        "Hybrid report from %s in #%s: %.2fh (通常=%d円, 残業=%d円, 合計=%d円, 売上=%d円)",
        member, parent_channel, worked_hours, normal_cost, overtime_cost, reward, revenue,
    )
    return payload, None


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    parent_channel, sub_channel = resolve_channel(message.channel)

    # チャンネル/スレッド名で判定できない場合、メッセージ先頭行の案件ラベル
    # （「Composure」「CORDER」等）からハイブリッド単価チャンネルへのフォールバック判定を試みる
    if parent_channel is None:
        fallback_channel = detect_project_from_content(message.content)
        if fallback_channel is not None:
            parent_channel, sub_channel = fallback_channel, message.channel.name

    if parent_channel is None:
        return

    warning = None
    if parent_channel in HYBRID_RATE_CHANNELS:
        payload, warning = build_hybrid_payload(parent_channel, sub_channel, message)
    elif parent_channel in FIXED_FEE_CHANNELS:
        payload = build_fixed_fee_payload(parent_channel, sub_channel, message)
    elif CHANNEL_RATES[parent_channel] is None:
        payload = build_attendance_payload(parent_channel, sub_channel, message)
    else:
        rate = resolve_rate(parent_channel, message.author.display_name)
        payload = build_report_payload(parent_channel, sub_channel, message, rate)

    if payload is None:
        if warning:
            await message.reply(warning)
        return

    async with aiohttp.ClientSession() as session:
        try:
            status = await post_to_gas(session, payload)
            if status == 200:
                await message.add_reaction("✅")
                logger.info("GAS accepted (200)")
            else:
                logger.error("GAS returned %s", status)
                await message.add_reaction("❌")
        except Exception as e:
            logger.exception("Failed to GET from GAS: %s", e)
            await message.add_reaction("❌")


client.run(DISCORD_TOKEN)
