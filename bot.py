from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"


@dataclass
class Draw:
    market: str
    date: str
    first: str = ""
    four: str = ""
    three_top: list[str] = field(default_factory=list)
    three_bottom: list[str] = field(default_factory=list)
    two_top: str = ""
    two_bottom: str = ""
    source: str = ""

    @property
    def key(self) -> str:
        return f"{self.market}:{self.date}:{self.first or self.four}:{self.two_bottom or self.two_top}"


class Config:
    def __init__(self) -> None:
        load_dotenv(BASE_DIR / ".env")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.default_chat_ids = parse_chat_ids(os.getenv("TELEGRAM_DEFAULT_CHAT_IDS", ""))
        self.lao_api_key = os.getenv("LAO_API_KEY", "").strip()
        self.lao_history_url = os.getenv(
            "LAO_HISTORY_URL", "https://api.apilotto.com/api/v1/laolottohistory"
        ).strip()
        self.lao_fallback_url = os.getenv(
            "LAO_FALLBACK_URL",
            "https://www.raakaadee.com/ตรวจหวย-หุ้น/หวยลาวพัฒนา/",
        ).strip()
        self.thai_api_base = os.getenv("THAI_API_BASE", "https://lotto.api.rayriffy.com").strip().rstrip("/")
        self.thai_history_pages = int(os.getenv("THAI_HISTORY_PAGES", "3") or "3")
        self.thai_archive_raw_base = os.getenv(
            "THAI_ARCHIVE_RAW_BASE",
            "https://raw.githubusercontent.com/vicha-w/thai-lotto-archive/master/lottonumbers",
        ).strip().rstrip("/")
        self.manual_results_file = Path(os.getenv("MANUAL_RESULTS_FILE", DATA_DIR / "manual_results.json"))
        if not self.manual_results_file.is_absolute():
            self.manual_results_file = BASE_DIR / self.manual_results_file
        self.check_interval_minutes = int(os.getenv("CHECK_INTERVAL_MINUTES", "15") or "15")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_chat_ids(raw: str) -> set[int]:
    chat_ids: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            chat_ids.add(int(item))
        except ValueError:
            pass
    return chat_ids


def http_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    url = iri_to_uri(url)
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
            return json.loads(text)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} จาก {url}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"เชื่อมต่อ {url} ไม่สำเร็จ: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ข้อมูลจาก {url} ไม่ใช่ JSON ที่อ่านได้") from exc


def http_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    url = iri_to_uri(url)
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if headers:
        default_headers.update(headers)
    request = urllib.request.Request(url, headers=default_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} จาก {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"เชื่อมต่อ {url} ไม่สำเร็จ: {exc.reason}") from exc


def iri_to_uri(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%")
    query = urllib.parse.quote(parts.query, safe="=&?/%:+,")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def only_digits(value: Any, size: int | None = None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if size is not None and digits:
        return digits[-size:].zfill(size)
    return digits


def numbers_from_prize(items: list[dict[str, Any]], prize_id: str) -> list[str]:
    for item in items:
        if item.get("id") == prize_id:
            return [only_digits(number) for number in item.get("number", []) if only_digits(number)]
    return []


def normalize_thai(payload: dict[str, Any]) -> Draw:
    response = payload.get("response", payload)
    prizes = response.get("prizes", []) or []
    running = response.get("runningNumbers", []) or []
    first = (numbers_from_prize(prizes, "prizeFirst") or [""])[0]
    front_three = numbers_from_prize(running, "runningNumberFrontThree")
    back_three = numbers_from_prize(running, "runningNumberBackThree")
    back_two = (numbers_from_prize(running, "runningNumberBackTwo") or [""])[0]
    return Draw(
        market="หวยไทย",
        date=str(response.get("date", "-")),
        first=first,
        three_top=[n[-3:].zfill(3) for n in front_three],
        three_bottom=[n[-3:].zfill(3) for n in back_three],
        two_bottom=back_two[-2:].zfill(2) if back_two else "",
        source=str(response.get("endpoint", "")),
    )


def normalize_lao(item: dict[str, Any]) -> Draw:
    two = item.get("laohistory2") or {}
    four = only_digits(item.get("laohistory4"), 4)
    three = only_digits(item.get("laohistory3"), 3)
    return Draw(
        market="หวยลาวพัฒนา",
        date=str(item.get("date", "-")),
        four=four,
        three_top=[three] if three else [],
        two_top=only_digits(two.get("top"), 2),
        two_bottom=only_digits(two.get("bottom"), 2),
    )


def fetch_lao_draws(config: Config, limit: int = 30) -> list[Draw]:
    manual = fetch_manual_draws(config, "lao", limit)
    if manual:
        return manual

    api_error: Exception | None = None
    if config.lao_api_key:
        try:
            payload = http_json(
                config.lao_history_url,
                headers={"x-api-key": config.lao_api_key, "Content-Type": "application/json"},
            )
            if payload.get("status") != 1:
                raise RuntimeError(payload.get("message", "Lao API ตอบกลับไม่สำเร็จ"))
            return [normalize_lao(item) for item in payload.get("data", [])[:limit]]
        except Exception as exc:
            api_error = exc

    fallback_draws = fetch_lao_fallback_draws(config, limit)
    if fallback_draws:
        return fallback_draws

    detail = f" API error: {api_error}" if api_error else ""
    raise RuntimeError(f"ดึงหวยลาวไม่สำเร็จ ทั้ง API และเว็บสำรองใช้ไม่ได้{detail}")


def fetch_lao_fallback_draws(config: Config, limit: int = 30) -> list[Draw]:
    html = http_text(config.lao_fallback_url, timeout=20)
    text = strip_html(html)
    blocks = re.split(r"ตรวจผล\s+หวยลาวพัฒนา\s+ออก\s+", text)
    draws: list[Draw] = []
    for block in blocks[1:]:
        clean_block = re.sub(r"\s+", " ", block).strip()
        date_match = re.search(r"(.{1,60}?เวลา\s*20:30\s*น\.)", clean_block)
        number_match = re.search(r"หวยออก\s+([0-9]+)", clean_block)
        three_match = re.search(r"3\s*ตัวบน\s+([0-9]{3})", clean_block)
        two_top_match = re.search(r"2\s*ตัวบน\s+([0-9]{2})", clean_block)
        two_bottom_match = re.search(r"2\s*ตัวล่าง\s+([0-9]{2})", clean_block)
        if not (number_match and three_match and two_top_match and two_bottom_match):
            continue
        full_number = only_digits(number_match.group(1))
        date_text = (date_match.group(1) if date_match else "").replace("\n", " ").strip()
        draws.append(
            Draw(
                market="หวยลาวพัฒนา",
                date=date_text or "-",
                four=full_number[-4:].zfill(4) if full_number else "",
                three_top=[only_digits(three_match.group(1), 3)],
                two_top=only_digits(two_top_match.group(1), 2),
                two_bottom=only_digits(two_bottom_match.group(1), 2),
                source=config.lao_fallback_url,
            )
        )
        if len(draws) >= limit:
            break
    return draws


def strip_html(html: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<[^>]+>", "\n", html)
    return re.sub(r"[ \t\r\f\v]+", " ", html)


def fetch_thai_draws(config: Config, limit: int = 30) -> list[Draw]:
    manual = fetch_manual_draws(config, "thai", limit)
    if manual:
        return manual

    api_error: Exception | None = None
    list_items: list[dict[str, Any]] = []
    try:
        list_urls = [f"{config.thai_api_base}/list"]
        list_urls.extend(f"{config.thai_api_base}/list/{page}" for page in range(2, max(config.thai_history_pages, 1) + 1))
        for url in list_urls:
            payload = http_json(url)
            if payload.get("status") != "success":
                continue
            list_items.extend(payload.get("response", []))
            if len(list_items) >= limit:
                break

        if not list_items:
            latest = http_json(f"{config.thai_api_base}/latest")
            return [normalize_thai(latest)]

        draws: list[Draw] = []
        for item in list_items[:limit]:
            url = item.get("url") or f"/lotto/{item.get('id')}"
            if not str(url).startswith("/"):
                url = f"/{url}"
            payload = http_json(f"{config.thai_api_base}{url}")
            draws.append(normalize_thai(payload))
        return draws
    except Exception as exc:
        api_error = exc

    archive_draws = fetch_thai_archive_draws(config, limit)
    if archive_draws:
        return archive_draws
    raise RuntimeError(f"Thai API ใช้งานไม่ได้ และดึงข้อมูลสำรองจาก GitHub ไม่สำเร็จ: {api_error}")


def fetch_thai_archive_draws(config: Config, limit: int = 30) -> list[Draw]:
    draws: list[Draw] = []
    for date_id in thai_archive_candidate_dates():
        url = f"{config.thai_archive_raw_base}/{date_id}.txt"
        try:
            text = http_text(url, timeout=15).strip()
        except RuntimeError:
            continue
        if not text:
            continue
        draws.append(parse_thai_archive_line(date_id, text, url))
        if len(draws) >= limit:
            break
    return draws


def thai_archive_candidate_dates(days_back: int = 900) -> list[str]:
    import datetime as _dt

    today = _dt.date.today()
    candidates: set[_dt.date] = set()
    for offset in range(days_back + 1):
        day = today - _dt.timedelta(days=offset)
        if day.day in {1, 16}:
            candidates.add(day)
        if day.month == 5 and day.day == 2:
            candidates.add(day)
        if day.month == 1 and day.day == 17:
            candidates.add(day)
        if day.month == 12 and day.day == 30:
            candidates.add(day)
    return [day.isoformat() for day in sorted(candidates, reverse=True)]


def parse_thai_archive_line(date_id: str, text: str, source: str) -> Draw:
    tokens = text.split()
    labels = {
        "FIRST",
        "THREE",
        "THREE_FIRST",
        "THREE_LAST",
        "TWO",
        "NEAR_FIRST",
        "SECOND",
        "THIRD",
        "FOURTH",
        "FIFTH",
    }
    values: dict[str, list[str]] = {}
    current_label = ""
    for token in tokens[1:]:
        if token in labels:
            current_label = token
            values.setdefault(current_label, [])
            continue
        if current_label:
            values[current_label].append(only_digits(token))

    first = (values.get("FIRST") or [""])[0]
    three_top = values.get("THREE_FIRST") or []
    three_bottom = values.get("THREE_LAST") or values.get("THREE") or []
    two_bottom = (values.get("TWO") or [""])[0]
    return Draw(
        market="หวยไทย",
        date=date_id,
        first=only_digits(first, 6),
        three_top=[only_digits(number, 3) for number in three_top],
        three_bottom=[only_digits(number, 3) for number in three_bottom],
        two_bottom=only_digits(two_bottom, 2),
        source=source,
    )


def fetch_manual_draws(config: Config, market_key: str, limit: int) -> list[Draw]:
    path = config.manual_results_file
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get(market_key, [])[:limit]
    draws: list[Draw] = []
    for item in items:
        if market_key == "thai":
            draws.append(
                Draw(
                    market="หวยไทย",
                    date=str(item.get("date", "-")),
                    first=only_digits(item.get("first"), 6),
                    three_top=[only_digits(n, 3) for n in item.get("three_top", [])],
                    three_bottom=[only_digits(n, 3) for n in item.get("three_bottom", [])],
                    two_bottom=only_digits(item.get("two_bottom"), 2),
                    source="manual",
                )
            )
        else:
            draws.append(
                Draw(
                    market="หวยลาวพัฒนา",
                    date=str(item.get("date", "-")),
                    four=only_digits(item.get("four"), 4),
                    three_top=[only_digits(item.get("three_top"), 3)] if item.get("three_top") else [],
                    two_top=only_digits(item.get("two_top"), 2),
                    two_bottom=only_digits(item.get("two_bottom"), 2),
                    source="manual",
                )
            )
    return draws


def format_draw(draw: Draw) -> str:
    lines = [f"{draw.market} - งวด {draw.date}"]
    if draw.first:
        lines.append(f"รางวัลที่ 1: {draw.first}")
    if draw.four:
        lines.append(f"เลข 4 ตัว: {draw.four}")
    if draw.three_top:
        lines.append(f"เลขหน้า/บน 3 ตัว: {', '.join(draw.three_top)}")
    if draw.three_bottom:
        lines.append(f"เลขท้าย 3 ตัว: {', '.join(draw.three_bottom)}")
    if draw.two_top:
        lines.append(f"เลข 2 ตัวบน: {draw.two_top}")
    if draw.two_bottom:
        lines.append(f"เลข 2 ตัวล่าง: {draw.two_bottom}")
    return "\n".join(lines)


def format_draws(title: str, draws: list[Draw], limit: int = 2) -> str:
    if not draws:
        return f"{title}\nยังไม่มีข้อมูล"
    body = "\n\n".join(format_draw(draw) for draw in draws[:limit])
    return f"{title}\n{body}"


def collect_digit_samples(draws: list[Draw]) -> dict[str, list[str]]:
    two_numbers: list[str] = []
    three_numbers: list[str] = []
    main_numbers: list[str] = []
    for draw in draws:
        two_numbers.extend([number for number in [draw.two_top, draw.two_bottom] if number])
        three_numbers.extend(draw.three_top + draw.three_bottom)
        main_numbers.extend([number for number in [draw.first, draw.four] if number])
    return {"two": two_numbers, "three": three_numbers, "main": main_numbers}


def top_pairs_from_digits(numbers: list[str], count: int = 6) -> list[str]:
    digits = Counter("".join(numbers))
    if not digits:
        return []
    ranked_digits = [digit for digit, _ in digits.most_common(6)]
    scored_pairs: list[tuple[int, str]] = []
    for first in ranked_digits:
        for second in ranked_digits:
            pair = f"{first}{second}"
            score = digits[first] + digits[second]
            if pair in numbers:
                score += 2
            scored_pairs.append((score, pair))
    return [pair for _, pair in sorted(scored_pairs, reverse=True)[:count]]


def format_counter(counter: Counter[str], limit: int = 5) -> str:
    if not counter:
        return "-"
    return ", ".join(f"{number}({freq})" for number, freq in counter.most_common(limit))


def analyze_draws(title: str, draws: list[Draw]) -> str:
    if not draws:
        return f"{title}\nยังไม่มีข้อมูลสำหรับวิเคราะห์"

    samples = collect_digit_samples(draws)
    two_counter = Counter(samples["two"])
    three_counter = Counter(samples["three"])
    digit_counter = Counter("".join(samples["two"] + samples["three"] + samples["main"]))
    pair_suggestions = top_pairs_from_digits(samples["two"] + samples["three"] + samples["main"])

    cold_digits = [str(digit) for digit in range(10) if str(digit) not in digit_counter]
    if not cold_digits:
        cold_digits = [digit for digit, _ in digit_counter.most_common()[:-6:-1]]

    lines = [
        title,
        f"ใช้ข้อมูลย้อนหลัง {len(draws)} งวดล่าสุดที่ดึงได้",
        f"เลข 2 ตัวที่ซ้ำ/เด่น: {format_counter(two_counter)}",
        f"เลข 3 ตัวที่ซ้ำ/เด่น: {format_counter(three_counter)}",
        f"ตัวเลขเดี่ยวที่พบบ่อย: {format_counter(digit_counter, 10)}",
        f"ตัวเลขที่ออกน้อยในชุดข้อมูลนี้: {', '.join(cold_digits[:6])}",
    ]
    if pair_suggestions:
        lines.append(f"ชุดเลข 2 ตัวเชิงสถิติ: {', '.join(pair_suggestions)}")
    lines.append("หมายเหตุ: เป็นการสรุปความถี่ ไม่ใช่การการันตีผลหรือเพิ่มโอกาสจริงของการสุ่ม")
    return "\n".join(lines)


def load_state(config: Config) -> dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    else:
        state = {}
    state.setdefault("subscribers", [])
    state.setdefault("last_seen", {})
    for chat_id in config.default_chat_ids:
        if chat_id not in state["subscribers"]:
            state["subscribers"].append(chat_id)
    return state


def save_state(state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class TelegramBot:
    def __init__(self, config: Config) -> None:
        if not config.telegram_token:
            raise RuntimeError("ยังไม่ได้ตั้งค่า TELEGRAM_BOT_TOKEN ใน .env")
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.telegram_token}"
        self.state = load_state(config)
        self.offset = 0
        self.next_check = 0.0

    def api(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        data = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return http_json(f"{self.base_url}/{method}", headers=headers, timeout=60) if data is None else self.post_json(method, data)

    def post_json(self, method: str, data: bytes) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def send(self, chat_id: int, text: str) -> None:
        chunks = split_message(text)
        for chunk in chunks:
            self.api("sendMessage", {"chat_id": chat_id, "text": chunk})

    def get_updates(self) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"timeout": 30, "offset": self.offset})
        payload = http_json(f"{self.base_url}/getUpdates?{query}", timeout=40)
        if not payload.get("ok"):
            return []
        return payload.get("result", [])

    def run(self) -> None:
        print("Telegram Lotto Bot started. Press Ctrl+C to stop.")
        while True:
            try:
                self.check_notifications()
                for update in self.get_updates():
                    self.offset = max(self.offset, update["update_id"] + 1)
                    self.handle_update(update)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                time.sleep(5)

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        if not chat_id or not text:
            return
        command = text.split()[0].split("@")[0].lower()
        try:
            reply = self.dispatch(command, int(chat_id))
        except Exception as exc:
            reply = f"ทำรายการไม่สำเร็จ: {exc}"
        self.send(int(chat_id), reply)

    def dispatch(self, command: str, chat_id: int) -> str:
        if command in {"/start", "/help"}:
            return HELP_TEXT
        if command == "/chatid":
            return f"chat id นี้คือ {chat_id}"
        if command == "/notify_on":
            subscribers = set(map(int, self.state.get("subscribers", [])))
            subscribers.add(chat_id)
            self.state["subscribers"] = sorted(subscribers)
            save_state(self.state)
            return "เปิดแจ้งเตือนผลหวยใหม่ให้แชทนี้แล้ว"
        if command == "/notify_off":
            subscribers = set(map(int, self.state.get("subscribers", [])))
            subscribers.discard(chat_id)
            self.state["subscribers"] = sorted(subscribers)
            save_state(self.state)
            return "ปิดแจ้งเตือนให้แชทนี้แล้ว"
        if command == "/thai":
            return format_draws("ผลหวยไทยย้อนหลัง 2 งวดล่าสุด", fetch_thai_draws(self.config, limit=2))
        if command == "/lao":
            return format_draws("ผลหวยลาวพัฒนาย้อนหลัง 2 งวดล่าสุด", fetch_lao_draws(self.config, limit=2))
        if command == "/latest":
            return "\n\n".join(
                [
                    format_draws("ผลหวยไทยย้อนหลัง 2 งวดล่าสุด", fetch_thai_draws(self.config, limit=2)),
                    format_draws("ผลหวยลาวพัฒนาย้อนหลัง 2 งวดล่าสุด", fetch_lao_draws(self.config, limit=2)),
                ]
            )
        if command == "/analyze_thai":
            return analyze_draws("วิเคราะห์หวยไทย", fetch_thai_draws(self.config, limit=30))
        if command == "/analyze_lao":
            return analyze_draws("วิเคราะห์หวยลาวพัฒนา", fetch_lao_draws(self.config, limit=30))
        if command == "/analyze":
            return "\n\n".join(
                [
                    analyze_draws("วิเคราะห์หวยไทย", fetch_thai_draws(self.config, limit=30)),
                    analyze_draws("วิเคราะห์หวยลาวพัฒนา", fetch_lao_draws(self.config, limit=30)),
                ]
            )
        return "ไม่รู้จักคำสั่งนี้ พิมพ์ /help เพื่อดูคำสั่งทั้งหมด"

    def check_notifications(self) -> None:
        now = time.time()
        if now < self.next_check:
            return
        self.next_check = now + self.config.check_interval_minutes * 60
        subscribers = [int(chat_id) for chat_id in self.state.get("subscribers", [])]
        if not subscribers:
            return

        messages: list[str] = []
        for market_key, fetcher in [("thai", fetch_thai_draws), ("lao", fetch_lao_draws)]:
            try:
                latest = fetcher(self.config, limit=1)[0]
            except Exception as exc:
                print(f"Skip {market_key}: {exc}", file=sys.stderr)
                continue
            previous_key = self.state.setdefault("last_seen", {}).get(market_key)
            if previous_key and previous_key != latest.key:
                messages.append("พบผลหวยงวดใหม่\n" + format_draw(latest))
            self.state["last_seen"][market_key] = latest.key

        save_state(self.state)
        for message in messages:
            for chat_id in subscribers:
                self.send(chat_id, message)


def split_message(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in text.split("\n\n"):
        part_len = len(paragraph) + 2
        if current and current_len + part_len > limit:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += part_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


HELP_TEXT = """ระบบผลหวยลาวพัฒนาและหวยไทย

/thai - ดูผลหวยไทย 2 งวดล่าสุด
/lao - ดูผลหวยลาวพัฒนา 2 งวดล่าสุด
/latest - ดูทั้งสองตลาด
/analyze_thai - วิเคราะห์หวยไทย
/analyze_lao - วิเคราะห์หวยลาวพัฒนา
/analyze - วิเคราะห์ทั้งสองตลาด
/notify_on - เปิดแจ้งเตือนในแชทนี้
/notify_off - ปิดแจ้งเตือนในแชทนี้
/chatid - ดู chat id"""


def run_once(config: Config) -> None:
    sections: list[str] = []
    for title, fetcher in [
        ("ผลหวยไทยย้อนหลัง 2 งวดล่าสุด", fetch_thai_draws),
        ("ผลหวยลาวพัฒนาย้อนหลัง 2 งวดล่าสุด", fetch_lao_draws),
    ]:
        try:
            draws = fetcher(config, limit=30)
            sections.append(format_draws(title, draws, limit=2))
            sections.append(analyze_draws(title.replace("ผล", "วิเคราะห์"), draws))
        except Exception as exc:
            sections.append(f"{title}\nทำรายการไม่สำเร็จ: {exc}")
    print("\n\n".join(sections))


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram bot for Thai and Lao lottery results.")
    parser.add_argument("--once", action="store_true", help="fetch and print results once, then exit")
    args = parser.parse_args()

    config = Config()
    if args.once:
        run_once(config)
        return

    TelegramBot(config).run()


if __name__ == "__main__":
    main()
