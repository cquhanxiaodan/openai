from __future__ import annotations

import dataclasses
import email as email_pkg
import base64
import hashlib
import json
import queue
import random
import re
import secrets
import shutil
import select
import socket
import ssl
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, BooleanVar, IntVar, StringVar, Tk, Toplevel, filedialog, messagebox, simpledialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from urllib.parse import parse_qs, urlencode, unquote, urljoin, urlparse

import imaplib
import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


APP_TITLE = "OpenAI 注册 + 支付长链接"
APP_DIR = Path(__file__).resolve().parent
STATE_FILE = APP_DIR / "state.json"
CHATGPT_BASE_URL = "https://chatgpt.com"
AUTH_BASE_URL = "https://auth.openai.com"
DEFAULT_PAYPAL_EXTENSION_DIR = r"D:\downloads\googledownloads\palpay扩展\palpay"
AUTH_AUTHORIZE_CONTINUE_URL = f"{AUTH_BASE_URL}/api/accounts/authorize/continue"
AUTH_EMAIL_OTP_SEND_URL = f"{AUTH_BASE_URL}/api/accounts/email-otp/send"
AUTH_EMAIL_OTP_VALIDATE_URL = f"{AUTH_BASE_URL}/api/accounts/email-otp/validate"
AUTH_WORKSPACE_SELECT_URL = f"{AUTH_BASE_URL}/api/accounts/workspace/select"
AUTH_PHONE_SEND_URL = f"{AUTH_BASE_URL}/api/accounts/add-phone/send"
AUTH_PHONE_OTP_VALIDATE_URL = f"{AUTH_BASE_URL}/api/accounts/phone-otp/validate"
AUTH_OAUTH_TOKEN_URLS = [
    f"{AUTH_BASE_URL}/api/oauth/oauth2/token",
    f"{AUTH_BASE_URL}/oauth/token",
]
DEFAULT_REDIRECT_URI = "http://localhost:1455/auth/callback"
DEFAULT_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)

IMAP_SCOPE = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
TOKEN_ENDPOINTS = [
    {"name": "V1-COMMON", "url": "https://login.microsoftonline.com/common/oauth2/token", "scope": "", "resource": "https://outlook.office.com/"},
    {"name": "V1-CONSUMERS", "url": "https://login.microsoftonline.com/consumers/oauth2/token", "scope": "", "resource": "https://outlook.office.com/"},
    {"name": "LIVE", "url": "https://login.live.com/oauth20_token.srf", "scope": ""},
    {"name": "LIVE+scope", "url": "https://login.live.com/oauth20_token.srf", "scope": IMAP_SCOPE},
    {"name": "CONSUMERS", "url": "https://login.microsoftonline.com/consumers/oauth2/v2.0/token", "scope": IMAP_SCOPE},
    {"name": "CONSUMERS-noscope", "url": "https://login.microsoftonline.com/consumers/oauth2/v2.0/token", "scope": ""},
    {"name": "COMMON", "url": "https://login.microsoftonline.com/common/oauth2/v2.0/token", "scope": IMAP_SCOPE},
    {"name": "COMMON-noscope", "url": "https://login.microsoftonline.com/common/oauth2/v2.0/token", "scope": ""},
]

FIRST_NAMES = [
    "Ethan", "Noah", "Liam", "Mason", "Lucas", "Logan", "Owen", "Ryan", "Leo", "Adam",
    "Ella", "Ava", "Mia", "Luna", "Chloe", "Grace", "Ruby", "Nora", "Ivy", "Sofia",
]
LAST_NAMES = [
    "Smith", "Brown", "Taylor", "Walker", "Wilson", "Clark", "Hall", "Young", "Allen", "King",
    "Scott", "Green", "Baker", "Adams", "Turner",
]

PAYMENT_MODES = {
    "无卡长链接 US/USD": {"country": "US", "currency": "USD"},
    "无卡长链接 BR/BRL": {"country": "BR", "currency": "BRL"},
    "无卡长链接 DE/EUR": {"country": "DE", "currency": "EUR"},
    "无卡长链接 FR/EUR": {"country": "FR", "currency": "EUR"},
    "无卡长链接 GB/GBP": {"country": "GB", "currency": "GBP"},
    "无卡长链接 CA/CAD": {"country": "CA", "currency": "CAD"},
    "无卡长链接 AU/AUD": {"country": "AU", "currency": "AUD"},
    "无卡长链接 JP/JPY": {"country": "JP", "currency": "JPY"},
    "PayPal 长链接 FR/EUR": {"country": "FR", "currency": "EUR"},
}

DEVICE_PROFILES = [
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/New_York"},
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Chicago"},
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Los_Angeles"},
    {"locale": "en-GB", "languages": ["en-GB", "en"], "timezone": "Europe/London"},
]


@dataclasses.dataclass
class MailAccount:
    email: str
    password: str
    client_id: str
    refresh_token: str
    raw: str
    account_type: str = "free"
    status: str = ""
    openai_rt: str = ""
    auth_phone_number: str = ""
    auth_phone_sms_url: str = ""


@dataclasses.dataclass
class PhoneEntry:
    number: str
    sms_url: str
    status: str = "可用"
    last_code: str = ""
    last_error: str = ""
    receive_count: int = 0


@dataclasses.dataclass
class PaymentCard:
    card: str
    month: str
    year: str
    cvv: str
    status: str = "未用"


@dataclasses.dataclass
class ProxyConfig:
    local_proxy: str = ""
    dynamic_proxy: str = ""
    chain_url: str = ""

    @property
    def label(self) -> str:
        parts = []
        if self.local_proxy:
            parts.append(f"本地={self.local_proxy}")
        if self.dynamic_proxy:
            parts.append(f"动态={self.dynamic_proxy}")
        return " -> ".join(parts) if parts else "直连"


@dataclasses.dataclass
class DeviceFingerprint:
    user_agent: str
    locale: str
    languages: list[str]
    timezone: str
    viewport_width: int
    viewport_height: int
    screen_width: int
    screen_height: int
    outer_width: int
    outer_height: int
    device_scale_factor: float
    hardware_concurrency: int
    device_memory: int
    platform: str
    vendor: str = "Google Inc."
    max_touch_points: int = 0

    @property
    def accept_language(self) -> str:
        if not self.languages:
            return self.locale
        return ",".join([self.languages[0], *[f"{lang};q={max(0.5, 0.9 - i * 0.1):.1f}" for i, lang in enumerate(self.languages[1:], start=0)]])

    @property
    def chrome_major(self) -> str:
        match = re.search(r"Chrome/(\d+)", self.user_agent)
        return match.group(1) if match else "146"

    @property
    def chrome_full(self) -> str:
        match = re.search(r"Chrome/([\d.]+)", self.user_agent)
        return match.group(1) if match else "146.0.0.0"


def generate_fingerprint() -> DeviceFingerprint:
    profile = random.choice(DEVICE_PROFILES)
    viewport = random.choice([
        (1280, 720, 1280, 720, 1),
        (1365, 768, 1366, 768, 1),
        (1440, 900, 1440, 900, 1),
        (1536, 864, 1536, 864, 1.25),
        (1600, 900, 1600, 900, 1),
        (1920, 1080, 1920, 1080, 1),
    ])
    major = random.randint(134, 146)
    build = random.randint(6000, 9999)
    patch = random.randint(50, 220)
    user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.{build}.{patch} Safari/537.36"
    return DeviceFingerprint(
        user_agent=user_agent,
        locale=profile["locale"],
        languages=list(profile["languages"]),
        timezone=profile["timezone"],
        viewport_width=viewport[0],
        viewport_height=viewport[1],
        screen_width=viewport[2],
        screen_height=viewport[3],
        outer_width=viewport[0] + random.randint(8, 16),
        outer_height=viewport[1] + random.randint(72, 96),
        device_scale_factor=viewport[4],
        hardware_concurrency=random.choice([4, 6, 8, 8, 12, 16]),
        device_memory=random.choice([4, 8, 8, 16]),
        platform="Win32",
    )


def parse_account_line(line: str) -> MailAccount:
    parts = [part.strip() for part in str(line or "").strip().split("----")]
    if len(parts) < 4:
        raise ValueError("格式错误，应为 email----password----client_id----refresh_token")
    email_addr, password, client_id, refresh_token = parts[:4]
    if not email_addr or not client_id or not refresh_token:
        raise ValueError("email / client_id / refresh_token 不能为空")
    openai_rt = extract_rt_token(parts[4:])
    return MailAccount(
        email=email_addr,
        password=password,
        client_id=client_id,
        refresh_token=refresh_token,
        raw="----".join([email_addr, password, client_id, refresh_token]),
        account_type="plus" if openai_rt else "free",
        status="已绑定手机号" if openai_rt else "",
        openai_rt=openai_rt,
    )


def extract_rt_token(extra_parts: list[str]) -> str:
    for part in extra_parts:
        if part.startswith("rt_token="):
            return part.split("=", 1)[1].strip()
    return ""


def account_to_dict(account: MailAccount) -> dict:
    return {
        "email": account.email,
        "password": account.password,
        "client_id": account.client_id,
        "refresh_token": account.refresh_token,
        "raw": account.raw,
        "account_type": account.account_type,
        "status": account.status,
        "openai_rt": account.openai_rt,
        "auth_phone_number": account.auth_phone_number,
        "auth_phone_sms_url": account.auth_phone_sms_url,
    }


def account_from_dict(value: dict) -> MailAccount:
    if value.get("raw"):
        account = parse_account_line(str(value["raw"]))
        account.account_type = str(value.get("account_type", account.account_type) or "free")
        account.status = str(value.get("status", account.status) or "")
        account.openai_rt = str(value.get("openai_rt", account.openai_rt) or account.openai_rt)
        account.auth_phone_number = str(value.get("auth_phone_number", account.auth_phone_number) or account.auth_phone_number)
        account.auth_phone_sms_url = str(value.get("auth_phone_sms_url", account.auth_phone_sms_url) or account.auth_phone_sms_url)
        return account
    account = MailAccount(
        email=str(value.get("email", "")).strip(),
        password=str(value.get("password", "")),
        client_id=str(value.get("client_id", "")).strip(),
        refresh_token=str(value.get("refresh_token", "")).strip(),
        raw="----".join([
            str(value.get("email", "")).strip(),
            str(value.get("password", "")),
            str(value.get("client_id", "")).strip(),
            str(value.get("refresh_token", "")).strip(),
        ]),
        account_type=str(value.get("account_type", "free") or "free"),
        status=str(value.get("status", "") or ""),
        openai_rt=str(value.get("openai_rt", "") or ""),
        auth_phone_number=str(value.get("auth_phone_number", "") or ""),
        auth_phone_sms_url=str(value.get("auth_phone_sms_url", "") or ""),
    )
    return account


def account_export_line(account: MailAccount, name_prefix: str = "") -> str:
    line = account.raw or "----".join([account.email, account.password, account.client_id, account.refresh_token])
    prefix = str(name_prefix or "").strip()
    if prefix:
        parts = line.split("----", 1)
        if parts:
            parts[0] = f"({prefix}){parts[0]}"
            line = "----".join(parts)
    if account.openai_rt and "----rt_token=" not in line:
        line = f"{line}----rt_token={account.openai_rt}"
    if account.auth_phone_number and "----auth_phone=" not in line:
        line = f"{line}----auth_phone={account.auth_phone_number}"
    if account.auth_phone_sms_url and "----auth_phone_sms_url=" not in line:
        line = f"{line}----auth_phone_sms_url={account.auth_phone_sms_url}"
    return line


def phone_to_dict(phone: PhoneEntry) -> dict:
    return dataclasses.asdict(phone)


def phone_from_dict(value: dict) -> PhoneEntry:
    return PhoneEntry(
        number=str(value.get("number", "")).strip(),
        sms_url=str(value.get("sms_url", "")).strip(),
        status=str(value.get("status", "可用") or "可用"),
        last_code=str(value.get("last_code", "") or ""),
        last_error=str(value.get("last_error", "") or ""),
    )


def parse_phone_line(line: str) -> PhoneEntry:
    text = str(line or "").strip()
    if "----" in text:
        parts = [part.strip() for part in text.split("----")]
        if len(parts) >= 2 and re.fullmatch(r"\+\d+", parts[0]) and re.match(r"https?://\S+$", parts[1]):
            return PhoneEntry(number=parts[0], sms_url=parts[1])
    match = re.match(r"^(\+\d+)\s*(https?://\S+)\s*$", text)
    if not match:
        raise ValueError("格式错误，应为 +手机号https://短信链接 或 +手机号----https://短信链接")
    return PhoneEntry(number=match.group(1), sms_url=match.group(2))


def parse_paypal_phone_line(line: str) -> PhoneEntry:
    text = str(line or "").strip()
    if "----" in text:
        number, sms_url = [part.strip() for part in text.split("----", 1)]
        if number and re.match(r"https?://\S+$", sms_url):
            return PhoneEntry(number=number, sms_url=sms_url)
    match = re.match(r"^([+\d][\d\s().-]*)\s*(https?://\S+)\s*$", text)
    if not match:
        raise ValueError("格式错误，应为 手机号----https://接码链接")
    return PhoneEntry(number=match.group(1).strip(), sms_url=match.group(2).strip())


def payment_card_to_dict(card: PaymentCard) -> dict:
    return dataclasses.asdict(card)


def payment_card_from_dict(value: dict) -> PaymentCard:
    return PaymentCard(
        card=str(value.get("card", "")).strip(),
        month=str(value.get("month", "")).strip(),
        year=str(value.get("year", "")).strip(),
        cvv=str(value.get("cvv", "")).strip(),
        status=str(value.get("status", "未用") or "未用"),
    )


def parse_payment_card_line(line: str) -> PaymentCard:
    parts = [part.strip() for part in str(line or "").strip().split("|")]
    if len(parts) != 4:
        raise ValueError("格式错误，应为 卡号|月|年|CVV")
    card, month, year, cvv = parts
    if not re.fullmatch(r"\d{12,19}", card) or not re.fullmatch(r"\d{1,2}", month) or not re.fullmatch(r"\d{4}", year) or not re.fullmatch(r"\d{3,4}", cvv):
        raise ValueError("卡号/月/年/CVV 格式不正确")
    return PaymentCard(card=card, month=str(int(month)), year=year, cvv=cvv)


def replace_paypal_card_head(paypal_card: str, payment_card: PaymentCard) -> str:
    parts = str(paypal_card or "").split("----")
    if len(parts) < 7:
        raise ValueError("PayPal 卡信息格式错误，需要至少 7 段 ---- 分隔")
    parts[0] = payment_card.card
    parts[1] = f"{payment_card.year}/{payment_card.month}"
    parts[2] = payment_card.cvv
    return "----".join(parts)


def normalize_proxy_url(value: str, default_scheme: str = "http") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"{default_scheme}://{text}"
    return text


def random_urlsafe_string(length: int) -> str:
    token = secrets.token_urlsafe(max(1, length))
    return token[:length]


def pkce_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def decode_jwt_payload(token: str) -> dict:
    parts = str(token or "").split(".")
    if len(parts) < 2:
        return {}
    try:
        payload = parts[1].replace("-", "+").replace("_", "/")
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.b64decode(payload).decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_nested_record(payload: dict, key: str) -> dict:
    value = payload.get(key) if isinstance(payload, dict) else None
    return value if isinstance(value, dict) else {}


def first_non_empty(*values) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def parse_expired_time(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return int(datetime.fromisoformat(text).timestamp())
    except Exception:
        return 0


def resolve_organization_id(id_claims: dict, access_claims: dict) -> str:
    id_auth = get_nested_record(id_claims, "https://api.openai.com/auth")
    access_auth = get_nested_record(access_claims, "https://api.openai.com/auth")
    organizations = id_auth.get("organizations") if isinstance(id_auth.get("organizations"), list) else access_auth.get("organizations")
    if not isinstance(organizations, list) or not organizations:
        return ""
    first = organizations[0]
    return first_non_empty(first.get("id") if isinstance(first, dict) else "")


def normalize_openai_auth_record(email_addr: str, payload: dict) -> dict:
    access_token = str(payload.get("access_token") or "")
    refresh_token = str(payload.get("refresh_token") or "")
    id_token = str(payload.get("id_token") or "")
    if not access_token:
        raise RuntimeError(f"token响应缺少 access_token: {payload}")
    if not refresh_token:
        raise RuntimeError(f"token响应缺少 refresh_token: {payload}")
    if not id_token:
        raise RuntimeError(f"token响应缺少 id_token: {payload}")
    access_claims = decode_jwt_payload(access_token)
    id_claims = decode_jwt_payload(id_token)
    auth_claim = get_nested_record(access_claims, "https://api.openai.com/auth")
    id_auth_claim = get_nested_record(id_claims, "https://api.openai.com/auth")
    account_id = first_non_empty(auth_claim.get("chatgpt_account_id"), id_auth_claim.get("chatgpt_account_id"))
    exp = int(access_claims.get("exp") or 0)
    if not account_id:
        raise RuntimeError(f"token中缺少 account_id: {access_claims}")
    if not exp:
        raise RuntimeError(f"access_token中缺少 exp: {access_claims}")
    return {
        "access_token": access_token,
        "account_id": account_id,
        "disabled": False,
        "email": first_non_empty(id_claims.get("email"), access_claims.get("email"), email_addr),
        "expired": datetime.fromtimestamp(exp, timezone.utc).isoformat().replace("+00:00", "Z"),
        "id_token": id_token,
        "last_refresh": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "refresh_token": refresh_token,
        "type": "codex",
        "websockets": False,
    }


def build_sub2api_json(record: dict) -> dict:
    access_claims = decode_jwt_payload(str(record.get("access_token") or ""))
    id_claims = decode_jwt_payload(str(record.get("id_token") or ""))
    access_auth = get_nested_record(access_claims, "https://api.openai.com/auth")
    access_profile = get_nested_record(access_claims, "https://api.openai.com/profile")
    expires_at = parse_expired_time(str(record.get("expired") or "")) or int(access_claims.get("exp") or 0)
    issued_at = int(access_claims.get("iat") or 0)
    expires_in = max(expires_at - issued_at, 0) if expires_at and issued_at else 864000
    email_addr = first_non_empty(record.get("email"), access_profile.get("email"), id_claims.get("email"), access_claims.get("email"))
    sub = first_non_empty(access_claims.get("sub"), id_claims.get("sub"))
    return {
        "data": {
            "type": "sub2api-data",
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "proxies": [],
            "accounts": [{
                "name": email_addr or f"openai-{int(time.time())}",
                "platform": "openai",
                "type": "oauth",
                "credentials": {
                    "access_token": str(record.get("access_token") or ""),
                    "chatgpt_account_id": first_non_empty(record.get("account_id"), access_auth.get("chatgpt_account_id")),
                    "chatgpt_user_id": first_non_empty(access_auth.get("chatgpt_user_id"), access_auth.get("user_id"), access_claims.get("sub")),
                    "expires_at": expires_at,
                    "expires_in": expires_in,
                    "organization_id": resolve_organization_id(id_claims, access_claims),
                    "refresh_token": str(record.get("refresh_token") or ""),
                },
                "extra": {"email": email_addr, "sub": sub},
                "concurrency": 10,
                "priority": 1,
                "rate_multiplier": 1,
                "auto_pause_on_expired": True,
            }],
        },
        "skip_default_group_bind": True,
    }


def build_sub2api_account(record: dict) -> dict:
    access_claims = decode_jwt_payload(str(record.get("access_token") or ""))
    id_claims = decode_jwt_payload(str(record.get("id_token") or ""))
    access_auth = get_nested_record(access_claims, "https://api.openai.com/auth")
    id_auth = get_nested_record(id_claims, "https://api.openai.com/auth")
    access_profile = get_nested_record(access_claims, "https://api.openai.com/profile")
    expires_at = parse_expired_time(str(record.get("expired") or "")) or int(access_claims.get("exp") or 0)
    issued_at = int(access_claims.get("iat") or 0)
    expires_in = max(expires_at - issued_at, 0) if expires_at and issued_at else 864000
    email_addr = first_non_empty(record.get("email"), access_profile.get("email"), id_claims.get("email"), access_claims.get("email"))
    plan_type = first_non_empty(record.get("plan_type"), access_auth.get("chatgpt_plan_type"), id_auth.get("chatgpt_plan_type"))
    return {
        "name": email_addr or f"openai-{int(time.time())}",
        "platform": "openai",
        "type": "oauth",
        "credentials": {
            "access_token": str(record.get("access_token") or ""),
            "chatgpt_account_id": first_non_empty(record.get("account_id"), access_auth.get("chatgpt_account_id"), id_auth.get("chatgpt_account_id")),
            "chatgpt_user_id": first_non_empty(access_auth.get("chatgpt_user_id"), access_auth.get("chatgpt_user_id"), access_auth.get("user_id"), access_claims.get("sub")),
            "client_id": DEFAULT_CLIENT_ID,
            "email": email_addr,
            "expires_at": expires_at,
            "expires_in": expires_in,
            "id_token": str(record.get("id_token") or ""),
            "organization_id": resolve_organization_id(id_claims, access_claims),
            "plan_type": plan_type,
            "refresh_token": str(record.get("refresh_token") or ""),
        },
        "extra": {"email": email_addr},
        "concurrency": 10,
        "priority": 1,
        "rate_multiplier": 1,
        "auto_pause_on_expired": True,
    }


def build_sub2api_export(records: list[dict]) -> dict:
    accounts = [build_sub2api_account(record) for record in records]
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "proxies": [],
        "accounts": accounts,
    }


def openai_record_from_refresh_payload(email_addr: str, payload: dict) -> dict:
    access_token = str(payload.get("access_token") or "")
    if not access_token:
        raise RuntimeError("刷新 RT 后缺少 access_token")
    access_claims = decode_jwt_payload(access_token)
    access_auth = get_nested_record(access_claims, "https://api.openai.com/auth")
    account_id = first_non_empty(access_auth.get("chatgpt_account_id"), access_auth.get("account_id"))
    exp = int(access_claims.get("exp") or 0)
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token.startswith("rt_"):
        raise RuntimeError("刷新 RT 后缺少有效 refresh_token")
    if not account_id:
        raise RuntimeError(f"access_token 中缺少 account_id: {access_claims}")
    return {
        "access_token": access_token,
        "account_id": account_id,
        "email": email_addr,
        "expired": datetime.fromtimestamp(exp, timezone.utc).isoformat().replace("+00:00", "Z") if exp else "",
        "id_token": str(payload.get("id_token") or ""),
        "last_refresh": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "plan_type": first_non_empty(access_auth.get("chatgpt_plan_type")),
        "refresh_token": refresh_token,
        "type": "codex",
    }


def normalize_auth_continue_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("http") else urljoin(AUTH_BASE_URL, text)


def performance_now_ms() -> int:
    return time.perf_counter_ns() // 1_000_000


def base64_json(value) -> str:
    return base64.b64encode(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii")


def sentinel_hash_hex(value: str) -> str:
    hash_value = 2166136261
    for char in value:
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    hash_value ^= hash_value >> 16
    hash_value = (hash_value * 2246822507) & 0xFFFFFFFF
    hash_value ^= hash_value >> 13
    hash_value = (hash_value * 3266489909) & 0xFFFFFFFF
    hash_value ^= hash_value >> 16
    return f"{hash_value & 0xFFFFFFFF:08x}"


def collect_sentinel_fingerprint_data(sid: str) -> list:
    return [
        1366 + 768,
        datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S GMT%z (%Z)"),
        4294967296,
        random.random(),
        DEFAULT_USER_AGENT,
        "https://sentinel.openai.com/sentinel/20260219f9f6/sdk.js",
        "20260219f9f6",
        "zh-CN",
        "zh-CN,zh",
        random.random(),
        random.choice([
            f"userAgent−{DEFAULT_USER_AGENT}",
            "language−zh-CN",
            "hardwareConcurrency−8",
        ]),
        "location",
        random.choice(["window", "self", "document", "navigator", "location", "screen", "history"]),
        performance_now_ms(),
        sid,
        "sv",
        8,
        int(time.time() * 1000),
        0,
        1,
        1,
        0,
        0,
        0,
        1,
    ]


def generate_sentinel_answer(seed: str, difficulty: str) -> str:
    started = performance_now_ms()
    sid = str(uuid.uuid4())
    data = collect_sentinel_fingerprint_data(sid)
    for attempt in range(500000):
        data[3] = attempt
        data[9] = round(performance_now_ms() - started)
        encoded = base64_json(data)
        digest = sentinel_hash_hex(seed + encoded)
        if digest[:len(difficulty)] <= difficulty:
            return f"{encoded}~S"
    return "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + base64_json("max attempts exceeded")


def openai_browser_headers(extra: dict | None = None) -> dict:
    headers = {
        "user-agent": DEFAULT_USER_AGENT,
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "sec-ch-ua": '"Google Chrome";v="146", "Chromium";v="146", "Not.A/Brand";v="24"',
        "sec-ch-ua-full-version-list": '"Google Chrome";v="146.0.0.0", "Chromium";v="146.0.0.0", "Not.A/Brand";v="24.0.0.0"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-platform-version": '"15.0.0"',
        "sec-ch-viewport-width": '"1365"',
    }
    if extra:
        headers.update(extra)
    return headers


def refresh_openai_access_token(openai_rt: str, proxy_url: str = "") -> dict:
    if not str(openai_rt or "").startswith("rt_"):
        raise RuntimeError("当前保存的 rt_token 不是有效 OpenAI refresh_token，请重新授权获取 RT")
    session = requests.Session()
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    last_error = ""
    for token_url in AUTH_OAUTH_TOKEN_URLS:
        response = session.post(
            token_url,
            headers=openai_browser_headers({"accept": "application/json", "content-type": "application/x-www-form-urlencoded"}),
            data={"grant_type": "refresh_token", "client_id": DEFAULT_CLIENT_ID, "refresh_token": openai_rt},
            timeout=30,
        )
        if response.ok:
            payload = response.json()
            if payload.get("access_token"):
                return payload
        last_error = f"endpoint={token_url} HTTP {response.status_code} {response.text[:300]}"
    raise RuntimeError(f"OpenAI RT 刷新 access_token 失败: {last_error}")


def infer_account_type_from_payload(payload) -> tuple[str, str]:
    found_free = ""
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            lower_keys = {str(key).lower(): value for key, value in item.items()}
            for key in ["is_paid_subscription_active", "has_active_subscription", "is_plus_user", "is_subscribed"]:
                if key in lower_keys:
                    value = lower_keys[key]
                    if value is True:
                        return "plus", f"{key}=true"
                    if value is False:
                        found_free = found_free or f"{key}=false"
            for key in ["subscription_plan", "plan_type", "plan", "account_plan", "product_name", "sku", "name"]:
                value = lower_keys.get(key)
                if isinstance(value, str):
                    text = value.lower()
                    if any(word in text for word in ["plus", "pro", "team", "enterprise", "chatgptplusplan"]):
                        return "plus", f"{key}={value}"
                    if any(word in text for word in ["free", "none", "no_plan"]):
                        found_free = found_free or f"{key}={value}"
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return ("free", found_free) if found_free else ("", "未发现明确套餐字段")


def detect_openai_account_type(openai_rt: str, proxy_url: str = "") -> tuple[str, str, str]:
    token_payload = refresh_openai_access_token(openai_rt, proxy_url)
    access_token = str(token_payload.get("access_token") or "")
    new_rt = str(token_payload.get("refresh_token") or openai_rt)
    access_claims = decode_jwt_payload(access_token)
    auth_claim = get_nested_record(access_claims, "https://api.openai.com/auth")
    account_id = first_non_empty(auth_claim.get("chatgpt_account_id"), auth_claim.get("account_id"))
    session = requests.Session()
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    headers = openai_browser_headers({
        "accept": "application/json",
        "authorization": f"Bearer {access_token}",
        "origin": CHATGPT_BASE_URL,
        "referer": f"{CHATGPT_BASE_URL}/",
    })
    endpoints = [f"{CHATGPT_BASE_URL}/backend-api/accounts/check/v4-2023-04-27"]
    if account_id:
        endpoints.append(f"{CHATGPT_BASE_URL}/backend-api/accounts/{account_id}/subscription")
    endpoints.extend([
        f"{CHATGPT_BASE_URL}/backend-api/me",
        f"{CHATGPT_BASE_URL}/backend-api/models",
    ])
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            response = session.get(endpoint, headers=headers, timeout=30)
            if not response.ok:
                errors.append(f"{endpoint}: HTTP {response.status_code}")
                continue
            payload = response.json()
            account_type, detail = infer_account_type_from_payload(payload)
            if account_type:
                return account_type, f"{endpoint} -> {detail}", new_rt
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("无法判断 Free/Plus: " + " | ".join(errors[-3:]))


class ProxyChainServer:
    def __init__(self, local_proxy: str, dynamic_proxy: str, log):
        self.local_proxy = normalize_proxy_url(local_proxy)
        self.dynamic_proxy = normalize_proxy_url(dynamic_proxy)
        self.log = log
        self.server: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.url = ""

    def __enter__(self):
        if not self.local_proxy and not self.dynamic_proxy:
            return self
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(64)
        port = self.server.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        self.close()

    def close(self) -> None:
        self.stop_event.set()
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
        self.server = None

    def _serve(self) -> None:
        assert self.server is not None
        while not self.stop_event.is_set():
            try:
                client, _addr = self.server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _handle_client(self, client: socket.socket) -> None:
        try:
            client.settimeout(30)
            head = self._read_http_head(client)
            if not head:
                return
            first_line = head.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
            parts = first_line.split()
            if len(parts) < 3:
                return
            method, target, version = parts[0].upper(), parts[1], parts[2]
            if method == "CONNECT":
                upstream = self._open_chain_to_target(target)
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self._relay(client, upstream)
                return
            rewritten = self._rewrite_plain_request(head, method, target, version)
            upstream = self._open_chain_to_target(self._target_from_plain_request(method, target, head))
            upstream.sendall(rewritten)
            self._relay(client, upstream)
        except Exception:
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except Exception:
                pass
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _read_http_head(self, client: socket.socket) -> bytes:
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                break
            data += chunk
        return data

    def _target_from_plain_request(self, method: str, target: str, head: bytes) -> str:
        if target.startswith("http://") or target.startswith("https://"):
            parsed = urlparse(target)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            return f"{parsed.hostname}:{port}"
        host = ""
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"host:"):
                host = line.split(b":", 1)[1].strip().decode("latin1")
                break
        return host

    def _rewrite_plain_request(self, head: bytes, method: str, target: str, version: str) -> bytes:
        if not (target.startswith("http://") or target.startswith("https://")):
            return head
        parsed = urlparse(target)
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        lines = head.split(b"\r\n")
        lines[0] = f"{method} {path} {version}".encode("latin1")
        return b"\r\n".join(lines)

    def _open_chain_to_target(self, target: str) -> socket.socket:
        if self.local_proxy:
            sock = self._connect_proxy(self.local_proxy)
            self._send_connect(sock, self._proxy_connect_target(self.dynamic_proxy) if self.dynamic_proxy else target)
            if self.dynamic_proxy:
                self._send_connect(sock, target, proxy_url=self.dynamic_proxy)
            return sock
        if self.dynamic_proxy:
            sock = self._connect_proxy(self.dynamic_proxy)
            self._send_connect(sock, target, proxy_url=self.dynamic_proxy)
            return sock
        host, port = self._split_host_port(target, 80)
        return socket.create_connection((host, port), timeout=30)

    def _connect_proxy(self, proxy_url: str) -> socket.socket:
        parsed = urlparse(proxy_url)
        if parsed.scheme not in ("http", "https"):
            raise RuntimeError(f"链式代理当前只支持 http/https 代理: {proxy_url}")
        host = parsed.hostname
        if not host:
            raise RuntimeError(f"代理地址缺少 host: {proxy_url}")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        raw = socket.create_connection((host, port), timeout=30)
        if parsed.scheme == "https":
            return ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        return raw

    def _proxy_connect_target(self, proxy_url: str) -> str:
        parsed = urlparse(proxy_url)
        if not parsed.hostname:
            raise RuntimeError(f"动态代理地址缺少 host: {proxy_url}")
        return f"{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}"

    def _send_connect(self, sock: socket.socket, target: str, proxy_url: str = "") -> None:
        headers = [f"CONNECT {target} HTTP/1.1", f"Host: {target}", "Proxy-Connection: keep-alive"]
        auth = self._proxy_auth(proxy_url)
        if auth:
            headers.append(f"Proxy-Authorization: Basic {auth}")
        request = ("\r\n".join(headers) + "\r\n\r\n").encode("latin1")
        sock.sendall(request)
        response = self._read_http_head(sock)
        status = response.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
        if " 200 " not in f" {status} ":
            raise RuntimeError(f"代理 CONNECT 失败: {status}")

    def _proxy_auth(self, proxy_url: str) -> str:
        parsed = urlparse(proxy_url)
        if not parsed.username:
            return ""
        username = unquote(parsed.username)
        password = unquote(parsed.password or "")
        return base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")

    def _split_host_port(self, target: str, default_port: int) -> tuple[str, int]:
        if target.startswith("["):
            host, rest = target[1:].split("]", 1)
            port = int(rest[1:]) if rest.startswith(":") else default_port
            return host, port
        if ":" in target:
            host, port = target.rsplit(":", 1)
            return host, int(port)
        return target, default_port

    def _relay(self, left: socket.socket, right: socket.socket) -> None:
        sockets = [left, right]
        for sock in sockets:
            sock.settimeout(None)
        try:
            while True:
                readable, _, _ = select.select(sockets, [], [], 60)
                if not readable:
                    return
                for src in readable:
                    dst = right if src is left else left
                    data = src.recv(65536)
                    if not data:
                        return
                    dst.sendall(data)
        finally:
            try:
                right.close()
            except Exception:
                pass


def decode_header_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def html_to_text(value: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text))


def extract_message_text(msg) -> str:
    parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type not in ("text/plain", "text/html"):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
            parts.append(html_to_text(text) if content_type == "text/html" else text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
            parts.append(html_to_text(text) if msg.get_content_type() == "text/html" else text)
    return "\n".join(parts)


def extract_openai_code(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text or " ")
    patterns = [
        r"(?:OpenAI|ChatGPT|verification|verify|code|验证码|登录码)[^\d]{0,100}(\d{6})",
        r"\b(\d{6})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.I)
        if match:
            return match.group(1)
    return ""


def refresh_hotmail_access_token(account: MailAccount, log, proxy_url: str = "") -> str:
    errors: list[str] = []
    for endpoint in TOKEN_ENDPOINTS:
        data = {
            "client_id": account.client_id,
            "grant_type": "refresh_token",
            "refresh_token": account.refresh_token,
        }
        if endpoint.get("scope"):
            data["scope"] = endpoint["scope"]
        if endpoint.get("resource"):
            data["resource"] = endpoint["resource"]
        try:
            resp = requests.post(
                endpoint["url"],
                data=data,
                headers={"Accept": "application/json"},
                timeout=25,
                proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            )
            payload = resp.json() if resp.text else {}
            if resp.ok and payload.get("access_token"):
                log(f"邮箱 Token 端点 {endpoint['name']} 成功")
                return str(payload["access_token"])
            msg = payload.get("error_description") or payload.get("error") or f"HTTP {resp.status_code}"
            errors.append(f"{endpoint['name']}: {msg}")
        except Exception as exc:
            errors.append(f"{endpoint['name']}: {exc}")
    raise RuntimeError("所有邮箱 Token 端点均失败 -> " + " | ".join(errors))


class ProxiedIMAP4SSL(imaplib.IMAP4_SSL):
    def __init__(self, host: str, port: int, proxied_socket: socket.socket, timeout: float | None = None):
        self._proxied_socket = proxied_socket
        super().__init__(host=host, port=port, timeout=timeout)

    def open(self, host: str = "", port: int = 0, timeout: float | None = None):
        self.host = host
        self.port = port
        self.sock = self._proxied_socket
        self.file = self.sock.makefile("rb")


class HotmailOtpReader:
    def __init__(self, account: MailAccount, log, proxy_url: str = ""):
        self.account = account
        self.log = log
        self.proxy_url = proxy_url
        self.seen: set[str] = set()
        self.imap: imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        access_token = refresh_hotmail_access_token(self.account, self.log, self.proxy_url)
        auth_string = f"user={self.account.email}\x01auth=Bearer {access_token}\x01\x01"
        if self.proxy_url:
            self.imap = self._connect_imap_via_proxy(self.proxy_url)
        else:
            self.imap = imaplib.IMAP4_SSL("outlook.office365.com", 993)
        self.imap.authenticate("XOAUTH2", lambda _: auth_string.encode("utf-8"))
        self.log("邮箱 IMAP 已连接，准备自动收 OpenAI 验证码")

    def _connect_imap_via_proxy(self, proxy_url: str) -> imaplib.IMAP4_SSL:
        parsed = urlparse(proxy_url)
        if parsed.scheme != "http" or not parsed.hostname:
            raise RuntimeError(f"IMAP 代理只支持 HTTP CONNECT: {proxy_url}")
        proxy_port = parsed.port or 80
        raw = socket.create_connection((parsed.hostname, proxy_port), timeout=30)
        target = "outlook.office365.com:993"
        request = [f"CONNECT {target} HTTP/1.1", f"Host: {target}", "Proxy-Connection: keep-alive"]
        if parsed.username:
            token = base64.b64encode(f"{unquote(parsed.username)}:{unquote(parsed.password or '')}".encode("utf-8")).decode("ascii")
            request.append(f"Proxy-Authorization: Basic {token}")
        raw.sendall(("\r\n".join(request) + "\r\n\r\n").encode("latin1"))
        response = b""
        while b"\r\n\r\n" not in response and len(response) < 65536:
            chunk = raw.recv(4096)
            if not chunk:
                break
            response += chunk
        status = response.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
        if " 200 " not in f" {status} ":
            raw.close()
            raise RuntimeError(f"IMAP 代理 CONNECT 失败: {status}")
        tls_sock = ssl.create_default_context().wrap_socket(raw, server_hostname="outlook.office365.com")
        return ProxiedIMAP4SSL("outlook.office365.com", 993, tls_sock)

    def close(self) -> None:
        if not self.imap:
            return
        try:
            self.imap.logout()
        except Exception:
            pass
        self.imap = None

    def wait_for_code(self, min_timestamp: float, timeout: int = 180) -> str:
        if not self.imap:
            self.connect()
        assert self.imap is not None
        started = time.time()
        last_notice = 0.0
        folders = ["INBOX", "Junk", "Junk Email"]
        while time.time() - started < timeout:
            for folder in folders:
                code = self._scan_folder(folder, min_timestamp)
                if code:
                    return code
            if time.time() - last_notice >= 20:
                remain = max(0, int(timeout - (time.time() - started)))
                self.log(f"仍在等待 OpenAI 新验证码邮件，剩余约 {remain}s")
                last_notice = time.time()
            time.sleep(5)
        raise TimeoutError("等待 OpenAI 邮箱验证码超时")

    def _select_folder(self, folder: str) -> bool:
        assert self.imap is not None
        for name in (folder, f'"{folder}"'):
            try:
                status, _ = self.imap.select(name, readonly=True)
                if status == "OK":
                    return True
            except Exception:
                continue
        return False

    def _scan_folder(self, folder: str, min_timestamp: float) -> str:
        assert self.imap is not None
        if not self._select_folder(folder):
            return ""
        status, data = self.imap.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            return ""
        ids = data[0].split()[-30:]
        for msg_id in reversed(ids):
            key = f"{folder}:{msg_id.decode(errors='ignore')}"
            if key in self.seen:
                continue
            status, msg_data = self.imap.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data:
                continue
            raw = next((item[1] for item in msg_data if isinstance(item, tuple)), None)
            if not raw:
                continue
            self.seen.add(key)
            msg = email_pkg.message_from_bytes(raw)
            date_header = msg.get("Date")
            try:
                mail_time = parsedate_to_datetime(date_header).timestamp() if date_header else time.time()
            except Exception:
                mail_time = time.time()
            if mail_time < min_timestamp:
                continue
            subject = decode_header_text(msg.get("Subject"))
            from_addr = decode_header_text(msg.get("From"))
            body = extract_message_text(msg)
            haystack = f"{subject}\n{from_addr}\n{body}"
            if not re.search(r"openai|chatgpt", haystack, flags=re.I):
                continue
            code = extract_openai_code(haystack)
            if code:
                self.log(f"收到 OpenAI 验证码: {code}")
                return code
        return ""


class OpenAIJsonAuthFlow:
    def __init__(self, account: MailAccount, log, phone_provider=None, input_callback=None, proxy_url: str = ""):
        self.account = account
        self.log = log
        self.phone_provider = phone_provider
        self.input_callback = input_callback
        self.session = requests.Session()
        self.proxy_url = proxy_url
        if proxy_url:
            self.session.proxies.update({"http": proxy_url, "https": proxy_url})
        self.state = ""
        self.code_verifier = ""
        self.device_id = ""
        self.email_otp_requested_at = 0.0

    def _headers(self, extra: dict | None = None) -> dict:
        return openai_browser_headers(extra)

    def _format_error_response(self, response: requests.Response) -> str:
        body = response.text
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            code = error.get("code") if isinstance(error, dict) else error
            if code:
                return f"{response.status_code} code={code}"
        except Exception:
            pass
        return f"{response.status_code} body={body[:500]}"

    def _read_cookie(self, url: str, key: str) -> str:
        for cookie in self.session.cookies:
            if cookie.name == key and (not cookie.domain or urlparse(url).hostname.endswith(cookie.domain.lstrip("."))):
                return cookie.value
        return ""

    def _prepare_login_url(self) -> str:
        self.state = random_urlsafe_string(24)
        self.code_verifier = random_urlsafe_string(64)
        query = urlencode({
            "client_id": DEFAULT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": DEFAULT_REDIRECT_URI,
            "scope": "openid email profile offline_access",
            "state": self.state,
            "code_challenge": pkce_code_challenge(self.code_verifier),
            "code_challenge_method": "S256",
            "prompt": "login",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "login_hint": self.account.email,
        })
        return f"{AUTH_BASE_URL}/oauth/authorize?{query}"

    def _fetch_sentinel_token(self, flow: str) -> str:
        requirement_seed = str(random.random())
        req_token = f"gAAAAAC{generate_sentinel_answer(requirement_seed, '0')}"
        response = self.session.post(
            "https://sentinel.openai.com/backend-api/sentinel/req",
            headers={"content-type": "application/json", "user-agent": DEFAULT_USER_AGENT},
            json={"p": req_token, "id": self.device_id, "flow": flow},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"请求 sentinel requirements 失败: {response.status_code} body={response.text[:300]}")
        requirements = response.json()
        if (requirements.get("turnstile") or {}).get("dx"):
            raise RuntimeError("当前 OpenAI 登录触发 Turnstile，服务器无浏览器模式暂不能自动通过")
        pow_data = requirements.get("proofofwork") or {}
        proof = None
        if pow_data.get("required") and pow_data.get("seed") and pow_data.get("difficulty"):
            proof = f"gAAAAAB{generate_sentinel_answer(str(pow_data['seed']), str(pow_data['difficulty']))}"
        return json.dumps({"p": proof, "t": None, "c": requirements.get("token"), "id": self.device_id, "flow": flow}, separators=(",", ":"))

    def _authorize_continue(self) -> str:
        sentinel_token = self._fetch_sentinel_token("authorize_continue")
        response = self.session.post(
            AUTH_AUTHORIZE_CONTINUE_URL,
            headers=self._headers({
                "content-type": "application/json",
                "openai-sentinel-token": sentinel_token,
            }),
            json={"username": {"kind": "email", "value": self.account.email}},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"AuthorizeContinue请求失败: {self._format_error_response(response)}")
        return normalize_auth_continue_url(str(response.json().get("continue_url") or ""))

    def _send_email_otp(self) -> str:
        response = self.session.get(
            AUTH_EMAIL_OTP_SEND_URL,
            headers=self._headers({"accept": "application/json", "referer": f"{AUTH_BASE_URL}/log-in"}),
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"EmailOtpSend请求失败: {self._format_error_response(response)}")
        self.email_otp_requested_at = time.time()
        return normalize_auth_continue_url(str(response.json().get("continue_url") or ""))

    def _email_otp_validate(self) -> str:
        last_error = ""
        for attempt in range(1, 3):
            otp_reader = HotmailOtpReader(self.account, self.log, "")
            try:
                code = otp_reader.wait_for_code(self.email_otp_requested_at or time.time() - 10)
            finally:
                otp_reader.close()
            response = self.session.post(
                AUTH_EMAIL_OTP_VALIDATE_URL,
                headers=self._headers({
                    "accept": "application/json",
                    "content-type": "application/json",
                    "origin": AUTH_BASE_URL,
                    "referer": f"{AUTH_BASE_URL}/email-verification",
                }),
                json={"code": code},
                timeout=30,
            )
            if response.ok:
                return normalize_auth_continue_url(str(response.json().get("continue_url") or ""))
            last_error = self._format_error_response(response)
            if "wrong_email_otp_code" not in last_error or attempt >= 2:
                raise RuntimeError(f"EmailOtpValidate请求失败: {last_error}")
            self.log("验证码疑似过期或取错，重新发码后重试")
            self._send_email_otp()
            time.sleep(2)
        raise RuntimeError(f"EmailOtpValidate请求失败: {last_error or 'unknown'}")

    def _resolve_workspace_id(self) -> str:
        cookie = self._read_cookie(AUTH_BASE_URL, "oai-client-auth-session")
        if not cookie:
            raise RuntimeError("未找到 oai-client-auth-session cookie，无法提取 workspace")
        encoded = cookie.split(".")[0]
        encoded += "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
        workspaces = payload.get("workspaces") or []
        workspace = next((item for item in workspaces if isinstance(item, dict) and item.get("kind") == "personal"), None)
        if not workspace and workspaces:
            workspace = workspaces[0]
        workspace_id = workspace.get("id") if isinstance(workspace, dict) else ""
        if not workspace_id:
            raise RuntimeError(f"当前会话未发现 workspace: {payload}")
        return str(workspace_id)

    def _select_workspace(self, consent_url: str) -> str:
        self.session.get(
            consent_url,
            headers=self._headers({
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "referer": f"{AUTH_BASE_URL}/email-verification",
            }),
            timeout=30,
        )
        workspace_id = self._resolve_workspace_id()
        response = self.session.post(
            AUTH_WORKSPACE_SELECT_URL,
            headers=self._headers({
                "accept": "application/json",
                "content-type": "application/json",
                "origin": AUTH_BASE_URL,
                "referer": consent_url,
            }),
            json={"workspace_id": workspace_id},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"WorkspaceSelect请求失败: {self._format_error_response(response)}")
        return normalize_auth_continue_url(str(response.json().get("continue_url") or ""))

    def _send_phone_otp(self, phone_number: str) -> str:
        response = self.session.post(
            AUTH_PHONE_SEND_URL,
            headers=self._headers({
                "accept": "application/json",
                "content-type": "application/json",
                "origin": AUTH_BASE_URL,
                "referer": f"{AUTH_BASE_URL}/add-phone",
            }),
            json={"phone_number": phone_number},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"SendPhoneOtp请求失败: {self._format_error_response(response)}")
        return normalize_auth_continue_url(str(response.json().get("continue_url") or ""))

    def _validate_phone_otp(self, code: str) -> str:
        response = self.session.post(
            AUTH_PHONE_OTP_VALIDATE_URL,
            headers=self._headers({
                "accept": "application/json",
                "content-type": "application/json",
                "origin": AUTH_BASE_URL,
                "referer": f"{AUTH_BASE_URL}/phone-verification",
            }),
            json={"code": code},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"PhoneOtpValidate请求失败: {self._format_error_response(response)}")
        return normalize_auth_continue_url(str(response.json().get("continue_url") or ""))

    def _handle_add_phone(self) -> str:
        if self.phone_provider:
            last_error = ""
            while True:
                phone = self.phone_provider("next", self.account.email, "")
                if not phone:
                    if last_error:
                        self.log(f"手机号池没有可用手机号，改为手动输入: {last_error}")
                    else:
                        self.log("手机号池为空或没有可用手机号，改为手动输入")
                    break
                phone_number = str(phone.get("number") or "").strip()
                self.log(f"提交手机号: {phone_number}")
                try:
                    self._send_phone_otp(phone_number)
                    code = self.phone_provider("code", self.account.email, phone)
                    if not code:
                        raise RuntimeError("短信链接未读取到验证码")
                    self.log(f"读取到短信验证码: {code}")
                    return self._validate_phone_otp(str(code))
                except Exception as exc:
                    last_error = str(exc)
                    self.phone_provider("bad", self.account.email, {**phone, "error": last_error})
                    self.log(f"手机号 {phone_number} 不可用，切换下一个: {last_error}")
                    continue

        if not self.input_callback:
            raise RuntimeError("未配置手机号池，也未配置手动输入回调")
        phone_number = self.input_callback("phone", self.account.email, "请输入手机号（包含国家码，例如 +1xxxxxxxxxx）")
        if not phone_number:
            raise RuntimeError("已取消手机号输入")
        self.log(f"提交手机号: {phone_number}")
        self._send_phone_otp(phone_number)
        code = self.input_callback("phone-code", self.account.email, f"请输入 {phone_number} 收到的短信验证码")
        if not code:
            raise RuntimeError("已取消短信验证码输入")
        self.log("提交短信验证码")
        return self._validate_phone_otp(code)

    def _extract_auth_result(self, callback_url: str) -> dict:
        parsed = urlparse(callback_url)
        query = parse_qs(parsed.query)
        code = (query.get("code") or [""])[0]
        state = (query.get("state") or [""])[0]
        if not code:
            raise RuntimeError(f"callback 中缺少 code: {callback_url}")
        if not state:
            raise RuntimeError(f"callback 中缺少 state: {callback_url}")
        if self.state and state != self.state:
            raise RuntimeError(f"callback state 不匹配: expected={self.state} actual={state}")
        return {"callback_url": callback_url, "code": code, "state": state}

    def _follow_oauth_redirects(self, start_url: str) -> dict:
        current_url = start_url
        for _ in range(10):
            response = self.session.get(
                current_url,
                allow_redirects=False,
                headers=self._headers({"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}),
                timeout=30,
            )
            location = response.headers.get("location")
            if location:
                next_url = urljoin(current_url, location)
                if next_url.startswith(f"{AUTH_BASE_URL}/add-phone"):
                    current_url = self._handle_add_phone()
                    continue
                if next_url.startswith(DEFAULT_REDIRECT_URI):
                    return self._extract_auth_result(next_url)
                current_url = next_url
                continue
            if response.url.startswith(f"{AUTH_BASE_URL}/add-phone"):
                current_url = self._handle_add_phone()
                continue
            if response.url.startswith(DEFAULT_REDIRECT_URI):
                return self._extract_auth_result(response.url)
            raise RuntimeError(f"OAuth跳转未到达callback: status={response.status_code} url={response.url}")
        raise RuntimeError(f"OAuth跳转次数过多，最后停在: {current_url}")

    def _exchange_code_for_token(self, code: str) -> dict:
        last_error = ""
        for token_url in AUTH_OAUTH_TOKEN_URLS:
            response = self.session.post(
                token_url,
                headers=self._headers({
                    "accept": "application/json",
                    "content-type": "application/x-www-form-urlencoded",
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-site",
                }),
                data={
                    "grant_type": "authorization_code",
                    "client_id": DEFAULT_CLIENT_ID,
                    "code": code,
                    "redirect_uri": DEFAULT_REDIRECT_URI,
                    "code_verifier": self.code_verifier,
                },
                timeout=30,
            )
            if not response.ok:
                last_error = f"endpoint={token_url} {self._format_error_response(response)}"
                continue
            return normalize_openai_auth_record(self.account.email, response.json())
        raise RuntimeError(f"Code换Token失败: {last_error}")

    def run(self) -> dict:
        self.log(f"开始 OpenAI 邮箱验证码授权: {self.account.email}")
        oauth_url = self._prepare_login_url()
        response = self.session.get(
            oauth_url,
            allow_redirects=True,
            headers=self._headers({
                "accept-encoding": "gzip, deflate",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
            }),
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(f"OauthUrl请求失败: {response.status_code}")
        if response.url.startswith(DEFAULT_REDIRECT_URI):
            result = self._extract_auth_result(response.url)
            return self._exchange_code_for_token(result["code"])

        allowed_start_urls = {
            f"{AUTH_BASE_URL}/log-in",
            f"{AUTH_BASE_URL}/email-verification",
            f"{AUTH_BASE_URL}/sign-in-with-chatgpt/codex/consent",
            f"{AUTH_BASE_URL}/add-phone",
        }
        if response.url not in allowed_start_urls and not response.url.startswith(f"{AUTH_BASE_URL}/add-phone"):
            raise RuntimeError(f"OauthUrl重定向到错误的URL: {response.url}")

        self.device_id = self._read_cookie("https://openai.com", "oai-did")
        if not self.device_id:
            self.device_id = str(uuid.uuid4())

        continue_url = response.url
        if continue_url == f"{AUTH_BASE_URL}/email-verification":
            self.email_otp_requested_at = time.time() - 10
        if continue_url == f"{AUTH_BASE_URL}/log-in":
            self.log("提交登录邮箱")
            continue_url = self._authorize_continue()
        if continue_url == f"{AUTH_BASE_URL}/log-in/password":
            raise RuntimeError("该账号进入密码登录页，无法无密码获取 RT")
        if continue_url == AUTH_EMAIL_OTP_SEND_URL:
            self.log("发送邮箱验证码")
            continue_url = self._send_email_otp()
        if continue_url == f"{AUTH_BASE_URL}/email-verification":
            self.log("等待并提交邮箱验证码")
            continue_url = self._email_otp_validate()
        if continue_url.startswith(f"{AUTH_BASE_URL}/add-phone"):
            self.log("遇到 add-phone，等待手动输入手机号和短信验证码")
            continue_url = self._handle_add_phone()
        if continue_url == f"{AUTH_BASE_URL}/sign-in-with-chatgpt/codex/consent":
            self.log("选择默认工作区")
            continue_url = self._select_workspace(continue_url)

        if continue_url.startswith(f"{AUTH_BASE_URL}/add-phone"):
            self.log("遇到 add-phone，等待手动输入手机号和短信验证码")
            continue_url = self._handle_add_phone()
        if continue_url == f"{AUTH_BASE_URL}/sign-in-with-chatgpt/codex/consent":
            self.log("选择默认工作区")
            continue_url = self._select_workspace(continue_url)

        self.log("交换授权 code 获取 refresh_token")
        result = self._follow_oauth_redirects(continue_url)
        return self._exchange_code_for_token(result["code"])


def random_profile() -> tuple[str, str]:
    age = random.randint(25, 34)
    today = datetime.now(timezone.utc)
    year = today.year - age
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}", f"{year:04d}-{month:02d}-{day:02d}"


class OpenAIRegisterPayLinkWorker:
    def __init__(self, account: MailAccount, payment_mode: str, headless: bool, register_proxy: ProxyConfig, extract_proxy: ProxyConfig, log):
        self.account = account
        self.payment_mode = payment_mode
        self.headless = headless
        self.register_proxy = register_proxy
        self.extract_proxy = extract_proxy
        self.log = log
        self.otp_reader = HotmailOtpReader(account, log, "")
        self.fingerprint = generate_fingerprint()

    def run(self) -> str:
        with sync_playwright() as p:
            register_browser = None
            register_context = None
            extract_browser = None
            extract_context = None
            try:
                register_browser, register_context = self._new_browser_context(p, self.register_proxy)
                register_context.clear_cookies()
                self.log(
                    f"浏览器指纹: Chrome/{self.fingerprint.chrome_major} "
                    f"{self.fingerprint.viewport_width}x{self.fingerprint.viewport_height} "
                    f"{self.fingerprint.locale} {self.fingerprint.timezone} "
                    f"cpu={self.fingerprint.hardware_concurrency} mem={self.fingerprint.device_memory}"
                )
                register_page = register_context.new_page()
                self._log_browser_proxy_status(register_page, self.register_proxy, "注册浏览器代理")
                self._register(register_page, register_context)
                storage_state = register_context.storage_state()
                reuse_same_context = self.register_proxy.chain_url == self.extract_proxy.chain_url
                self.log("注册完成，已保存登录态" + ("，复用当前窗口提取长链接" if reuse_same_context else "，切换到长链接提取代理"))

                if reuse_same_context:
                    self._log_browser_proxy_status(register_page, self.extract_proxy, "长链接浏览器代理")
                    return self._extract_pay_link(register_page)

                self._close_browser(register_context, register_browser)
                register_context = None
                register_browser = None

                extract_browser, extract_context = self._new_browser_context(p, self.extract_proxy, storage_state)
                extract_page = extract_context.new_page()
                self._log_browser_proxy_status(extract_page, self.extract_proxy, "长链接浏览器代理")
                return self._extract_pay_link(extract_page)
            finally:
                self.otp_reader.close()
                self._close_browser(register_context, register_browser)
                self._close_browser(extract_context, extract_browser)

    def relink(self) -> str:
        with sync_playwright() as p:
            login_browser = None
            login_context = None
            extract_browser = None
            extract_context = None
            try:
                login_browser, login_context = self._new_browser_context(p, self.register_proxy)
                login_context.clear_cookies()
                self.log(
                    f"浏览器指纹: Chrome/{self.fingerprint.chrome_major} "
                    f"{self.fingerprint.viewport_width}x{self.fingerprint.viewport_height} "
                    f"{self.fingerprint.locale} {self.fingerprint.timezone} "
                    f"cpu={self.fingerprint.hardware_concurrency} mem={self.fingerprint.device_memory}"
                )
                login_page = login_context.new_page()
                self._log_browser_proxy_status(login_page, self.register_proxy, "登录浏览器代理")
                self._login_existing_account(login_page, login_context)
                storage_state = login_context.storage_state()
                self.log("登录完成，已保存登录态，切换到长链接提取代理")

                self._close_browser(login_context, login_browser)
                login_context = None
                login_browser = None

                extract_browser, extract_context = self._new_browser_context(p, self.extract_proxy, storage_state)
                extract_page = extract_context.new_page()
                self._log_browser_proxy_status(extract_page, self.extract_proxy, "长链接浏览器代理")
                return self._extract_pay_link(extract_page)
            finally:
                self.otp_reader.close()
                self._close_browser(login_context, login_browser)
                self._close_browser(extract_context, extract_browser)

    def _new_browser_context(self, p, proxy: ProxyConfig, storage_state: dict | None = None):
        browser = p.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--window-size={self.fingerprint.outer_width},{self.fingerprint.outer_height}",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            proxy={"server": proxy.chain_url} if proxy.chain_url else None,
        )
        context_options = {
            "user_agent": self.fingerprint.user_agent,
            "locale": self.fingerprint.locale,
            "timezone_id": self.fingerprint.timezone,
            "viewport": {"width": self.fingerprint.viewport_width, "height": self.fingerprint.viewport_height},
            "screen": {"width": self.fingerprint.screen_width, "height": self.fingerprint.screen_height},
            "device_scale_factor": self.fingerprint.device_scale_factor,
            "is_mobile": False,
            "has_touch": False,
        }
        if storage_state:
            context_options["storage_state"] = storage_state
        context = browser.new_context(**context_options)
        self._install_fingerprint(context)
        return browser, context

    def _close_browser(self, context, browser) -> None:
        try:
            if context:
                context.close()
        except Exception:
            pass
        try:
            if browser:
                browser.close()
        except Exception:
            pass

    def _cleanup_profile_dir(self, profile_dir: str) -> None:
        for attempt in range(8):
            try:
                shutil.rmtree(profile_dir, ignore_errors=False)
                return
            except FileNotFoundError:
                return
            except PermissionError:
                time.sleep(0.5 + attempt * 0.25)
            except OSError:
                time.sleep(0.5 + attempt * 0.25)
        self.log(f"临时浏览器目录清理失败，已忽略: {profile_dir}")

    def _install_fingerprint(self, context) -> None:
        fp = self.fingerprint
        fp_payload = json.dumps({
            "platform": fp.platform,
            "vendor": fp.vendor,
            "languages": fp.languages,
            "hardwareConcurrency": fp.hardware_concurrency,
            "deviceMemory": fp.device_memory,
            "maxTouchPoints": fp.max_touch_points,
            "screenWidth": fp.screen_width,
            "screenHeight": fp.screen_height,
            "outerWidth": fp.outer_width,
            "outerHeight": fp.outer_height,
            "deviceScaleFactor": fp.device_scale_factor,
            "chromeMajor": fp.chrome_major,
            "chromeFull": fp.chrome_full,
        }, ensure_ascii=False)
        context.set_extra_http_headers({
            "Accept-Language": fp.accept_language,
            "sec-ch-ua": f'"Google Chrome";v="{fp.chrome_major}", "Chromium";v="{fp.chrome_major}", "Not.A/Brand";v="24"',
            "sec-ch-ua-full-version-list": f'"Google Chrome";v="{fp.chrome_full}", "Chromium";v="{fp.chrome_full}", "Not.A/Brand";v="24.0.0.0"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"15.0.0"',
        })
        context.add_init_script(
            """(() => {
                const fp = __FP_PAYLOAD__;
                const defineGetter = (obj, prop, value) => {
                    try { Object.defineProperty(obj, prop, { get: () => value, configurable: true }); } catch (_) {}
                };
                defineGetter(Navigator.prototype, 'webdriver', undefined);
                defineGetter(Navigator.prototype, 'platform', fp.platform);
                defineGetter(Navigator.prototype, 'vendor', fp.vendor);
                defineGetter(Navigator.prototype, 'language', fp.languages[0]);
                defineGetter(Navigator.prototype, 'languages', fp.languages);
                defineGetter(Navigator.prototype, 'hardwareConcurrency', fp.hardwareConcurrency);
                defineGetter(Navigator.prototype, 'deviceMemory', fp.deviceMemory);
                defineGetter(Navigator.prototype, 'maxTouchPoints', fp.maxTouchPoints);
                defineGetter(Screen.prototype, 'width', fp.screenWidth);
                defineGetter(Screen.prototype, 'height', fp.screenHeight);
                defineGetter(Screen.prototype, 'availWidth', fp.screenWidth);
                defineGetter(Screen.prototype, 'availHeight', fp.screenHeight - 40);
                defineGetter(window, 'outerWidth', fp.outerWidth);
                defineGetter(window, 'outerHeight', fp.outerHeight);
                defineGetter(window, 'devicePixelRatio', fp.deviceScaleFactor);
                if (!navigator.userAgentData) {
                    defineGetter(Navigator.prototype, 'userAgentData', {
                        mobile: false,
                        platform: 'Windows',
                        brands: [
                            { brand: 'Google Chrome', version: fp.chromeMajor },
                            { brand: 'Chromium', version: fp.chromeMajor },
                            { brand: 'Not.A/Brand', version: '24' },
                        ],
                        getHighEntropyValues: async hints => {
                            const values = {
                                architecture: 'x86', bitness: '64', mobile: false, model: '',
                                platform: 'Windows', platformVersion: '15.0.0', uaFullVersion: fp.chromeFull,
                                fullVersionList: [
                                    { brand: 'Google Chrome', version: fp.chromeFull },
                                    { brand: 'Chromium', version: fp.chromeFull },
                                    { brand: 'Not.A/Brand', version: '24.0.0.0' },
                                ],
                                wow64: false,
                            };
                            return Object.fromEntries(hints.filter(h => h in values).map(h => [h, values[h]]));
                        },
                    });
                }
                try {
                    const originalQuery = navigator.permissions && navigator.permissions.query;
                    if (originalQuery) {
                        navigator.permissions.query = params => params && params.name === 'notifications'
                            ? Promise.resolve({ state: Notification.permission })
                            : originalQuery.call(navigator.permissions, params);
                    }
                } catch (_) {}
                try {
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Inc.';
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                        return getParameter.call(this, parameter);
                    };
                } catch (_) {}
            }})();"""
            .replace("__FP_PAYLOAD__", fp_payload)
        )

    def _log_browser_proxy_status(self, page, proxy: ProxyConfig, label: str) -> None:
        if not proxy.chain_url:
            self.log(f"{label}: 直连")
            return
        try:
            page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded", timeout=30000)
            text = page.locator("body").inner_text(timeout=5000)
            self.log(f"{label}检测成功，出口信息: {text.strip()[:120]}")
        except Exception as exc:
            self.log(f"{label}检测失败: {exc}")

    def _register(self, page, context) -> None:
        self.log(f"开始注册: {self.account.email}")
        page.goto(CHATGPT_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        signin_url = self._create_openai_signin_url(context)
        otp_min_timestamp = time.time() - 10
        page.goto(signin_url, wait_until="domcontentloaded", timeout=90000)
        self.log("已打开 OpenAI 注册页；如出现人机验证，请在浏览器中手动完成")

        deadline = time.time() + 600
        email_code_submitted = False
        about_you_submitted = False
        route_error_retries = 0
        while time.time() < deadline:
            url = page.url
            error_text = self._detect_route_error(page)
            if error_text:
                if route_error_retries < 3 and self._retry_route_error(page):
                    route_error_retries += 1
                    self.log(f"OpenAI 页面超时，已点击重试 ({route_error_retries}/3)")
                    time.sleep(5)
                    continue
                raise RuntimeError(f"OpenAI 页面错误，通常是代理/风控导致接口超时: {error_text}")
            if self._has_chatgpt_session(page):
                self.log("注册完成，已获得 ChatGPT 会话")
                return
            if "add-phone" in url or "phone-verification" in url:
                raise RuntimeError("当前账号触发手机验证，脚本只做邮箱注册，已停止")
            if "password" in url and self._has_visible_password(page):
                self._fill_password_step(page)
                email_code_submitted = False
                about_you_submitted = False
                continue
            if "about-you" in url or self._has_about_you_form(page):
                email_code_submitted = False
                self._fill_about_you(page)
                about_you_submitted = True
                continue
            if "email-verification" in url or self._has_otp_input(page):
                if email_code_submitted:
                    time.sleep(2)
                    continue
                self._submit_email_code(page, otp_min_timestamp)
                email_code_submitted = True
                continue
            if self._fill_email_if_visible(page):
                otp_min_timestamp = time.time()
                email_code_submitted = False
                about_you_submitted = False
                continue
            time.sleep(2)

        raise TimeoutError("注册流程超时；如果浏览器停在人机验证或异常页面，请手动处理后重试")

    def _login_existing_account(self, page, context) -> None:
        self.log(f"开始登录已有账号: {self.account.email}")
        page.goto(CHATGPT_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        signin_url = self._create_login_url(context)
        otp_min_timestamp = time.time() - 10
        page.goto(signin_url, wait_until="domcontentloaded", timeout=90000)
        self.log("已打开 OpenAI 登录页；如出现人机验证，请在浏览器中手动完成")

        deadline = time.time() + 600
        email_code_submitted = False
        route_error_retries = 0
        while time.time() < deadline:
            url = page.url
            error_text = self._detect_route_error(page)
            if error_text:
                if route_error_retries < 3 and self._retry_route_error(page):
                    route_error_retries += 1
                    self.log(f"OpenAI 登录页超时，已点击重试 ({route_error_retries}/3)")
                    time.sleep(5)
                    continue
                raise RuntimeError(f"OpenAI 登录页错误，通常是代理/风控导致接口超时: {error_text}")
            if self._has_chatgpt_session(page):
                self.log("登录完成，已获得 ChatGPT 会话")
                return
            if "add-phone" in url or "phone-verification" in url:
                raise RuntimeError("当前账号触发手机验证，重新获取长链接已停止")
            if "password" in url and self._has_visible_password(page):
                raise RuntimeError("该账号进入密码登录页，当前只支持邮箱验证码重新获取长链接")
            if "email-verification" in url or self._has_otp_input(page):
                if email_code_submitted:
                    time.sleep(2)
                    continue
                self._submit_email_code(page, otp_min_timestamp)
                email_code_submitted = True
                continue
            if self._fill_email_if_visible(page):
                otp_min_timestamp = time.time()
                email_code_submitted = False
                continue
            time.sleep(2)

        raise TimeoutError("重新获取长链接登录流程超时；如果浏览器停在人机验证或异常页面，请手动处理后重试")

    def _detect_route_error(self, page) -> str:
        try:
            text = page.locator("body").inner_text(timeout=700)
        except Exception:
            return ""
        normalized = re.sub(r"\s+", " ", text).strip()
        if "糟糕，出错了" in normalized or "Operation timed out" in normalized or "Route Error" in normalized:
            return normalized[:400]
        return ""

    def _retry_route_error(self, page) -> bool:
        selectors = [
            'button:has-text("Try again")',
            'button:has-text("重试")',
            'a:has-text("Try again")',
            'a:has-text("重试")',
            '[role="button"]:has-text("Try again")',
            '[role="button"]:has-text("重试")',
        ]
        for selector in selectors:
            target = page.locator(selector).first
            try:
                if target.is_visible(timeout=800):
                    target.click(timeout=5000)
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    return True
            except Exception:
                continue
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception:
            return False

    def _create_openai_signin_url(self, context) -> str:
        cookies = context.cookies([CHATGPT_BASE_URL, "https://openai.com"])
        csrf_value = ""
        device_id = ""
        for cookie in cookies:
            if cookie.get("name") == "__Host-next-auth.csrf-token":
                csrf_value = unquote(cookie.get("value", "")).split("|")[0]
            if cookie.get("name") == "oai-did":
                device_id = cookie.get("value", "")
        if not csrf_value:
            raise RuntimeError("未找到 ChatGPT CSRF cookie，无法打开注册页")
        if not device_id:
            device_id = str(uuid.uuid4())

        query = urlencode({
            "prompt": "login",
            "ext-oai-did": device_id,
            "auth_session_logging_id": str(uuid.uuid4()),
            "ext-passkey-client-capabilities": "0111",
            "screen_hint": "signup",
            "login_hint": self.account.email,
        })
        response = context.request.post(
            f"{CHATGPT_BASE_URL}/api/auth/signin/openai?{query}",
            form={"callbackUrl": f"{CHATGPT_BASE_URL}/", "csrfToken": csrf_value, "json": "true"},
            headers={"Accept": "application/json"},
        )
        if not response.ok:
            raise RuntimeError(f"打开注册页失败: HTTP {response.status} {response.text()[:300]}")
        payload = response.json()
        signin_url = payload.get("url")
        if not signin_url:
            raise RuntimeError(f"打开注册页缺少跳转 URL: {payload}")
        return signin_url

    def _create_login_url(self, context) -> str:
        cookies = context.cookies([CHATGPT_BASE_URL, "https://openai.com"])
        csrf_value = ""
        device_id = ""
        for cookie in cookies:
            if cookie.get("name") == "__Host-next-auth.csrf-token":
                csrf_value = unquote(cookie.get("value", "")).split("|")[0]
            if cookie.get("name") == "oai-did":
                device_id = cookie.get("value", "")
        if not csrf_value:
            raise RuntimeError("未找到 ChatGPT CSRF cookie，无法打开登录页")
        if not device_id:
            device_id = str(uuid.uuid4())

        query = urlencode({
            "prompt": "login",
            "ext-oai-did": device_id,
            "auth_session_logging_id": str(uuid.uuid4()),
            "ext-passkey-client-capabilities": "0111",
            "screen_hint": "login",
            "login_hint": self.account.email,
        })
        response = context.request.post(
            f"{CHATGPT_BASE_URL}/api/auth/signin/openai?{query}",
            form={"callbackUrl": f"{CHATGPT_BASE_URL}/", "csrfToken": csrf_value, "json": "true"},
            headers={"Accept": "application/json"},
        )
        if not response.ok:
            raise RuntimeError(f"打开登录页失败: HTTP {response.status} {response.text()[:300]}")
        payload = response.json()
        signin_url = payload.get("url")
        if not signin_url:
            raise RuntimeError(f"打开登录页缺少跳转 URL: {payload}")
        return signin_url

    def _has_chatgpt_session(self, page) -> bool:
        if not page.url.startswith(CHATGPT_BASE_URL):
            return False
        try:
            payload = page.evaluate(
                """async () => {
                    const resp = await fetch('/api/auth/session', { credentials: 'include' });
                    if (!resp.ok) return null;
                    return await resp.json();
                }"""
            )
            return bool(payload and payload.get("accessToken"))
        except Exception:
            return False

    def _visible_inputs(self, page, selectors: list[str]):
        visible = []
        for selector in selectors:
            locator = page.locator(selector)
            try:
                count = min(locator.count(), 12)
            except Exception:
                continue
            for index in range(count):
                item = locator.nth(index)
                try:
                    if item.is_visible():
                        visible.append(item)
                except Exception:
                    pass
        return visible

    def _click_continue(self, page) -> bool:
        selectors = [
            'button:has-text("Finish creating account")',
            'button[data-dd-action-name="Continue"][type="submit"]',
            'button:has-text("Continue")',
            'button:has-text("继续")',
            'button:has-text("完成帐户创建")',
            'button:has-text("完成账户创建")',
            'button:has-text("Next")',
            'button:has-text("下一步")',
            'button:has-text("Create")',
            'button:has-text("完成")',
            'button[type="submit"]',
            '[role="button"]:has-text("Finish creating account")',
            '[role="button"]:has-text("Continue")',
        ]
        for selector in selectors:
            button = page.locator(selector).first
            try:
                if button.is_visible(timeout=700):
                    button.click(timeout=5000)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return True
            except Exception:
                continue
        if self._click_submit_button_by_dom(page):
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            return True
        return False

    def _click_submit_button_by_dom(self, page) -> bool:
        return bool(page.evaluate(
            """() => {
                const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                };
                const buttons = Array.from(document.querySelectorAll('button, [role="button"]')).filter(visible);
                const button = buttons.find(el =>
                    (el.textContent || '').includes('Finish creating account')
                    || (el.getAttribute('data-dd-action-name') || '') === 'Continue'
                    || (el.type || '').toLowerCase() === 'submit'
                );
                if (!button || button.getAttribute('aria-disabled') === 'true' || button.disabled) return false;
                button.scrollIntoView({ block: 'center', inline: 'center' });
                button.focus();
                button.click();
                return true;
            }"""
        ))

    def _fill_email_if_visible(self, page) -> bool:
        inputs = self._visible_inputs(page, [
            'input[type="email"]',
            'input[name="email"]',
            'input[name="username"]',
            'input[autocomplete="email"]',
        ])
        if not inputs:
            return False
        self.log("填写注册邮箱")
        inputs[0].fill(self.account.email)
        self._click_continue(page)
        return True

    def _has_visible_password(self, page) -> bool:
        return bool(self._visible_inputs(page, ['input[type="password"]', 'input[name="password"]']))

    def _fill_password_step(self, page) -> None:
        if not self.account.password:
            self.account.password = self._generate_password()
            self.account.raw = "----".join([
                self.account.email,
                self.account.password,
                self.account.client_id,
                self.account.refresh_token,
            ])
            self.log(f"账号需要密码步骤，已生成密码: {self.account.password}")
        else:
            self.log("账号需要密码步骤，使用导入行已有密码继续")

        inputs = self._visible_inputs(page, ['input[type="password"]', 'input[name="password"]'])
        if not inputs:
            raise RuntimeError("进入密码步骤但未找到密码输入框")
        for input_box in inputs:
            self._force_fill_locator(input_box, self.account.password)
        if not self._click_continue(page):
            raise RuntimeError("密码已填写，但未找到继续按钮")

    def _generate_password(self) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
        suffix = "!A7"
        return "".join(random.choice(alphabet) for _ in range(13)) + suffix

    def _has_otp_input(self, page) -> bool:
        if "about-you" in page.url or self._has_about_you_form(page):
            return False
        return bool(self._visible_inputs(page, [
            'input[autocomplete="one-time-code"]',
            'input[name="code"]',
            'input[aria-label*="code" i]',
            'input[placeholder*="code" i]',
            'input[aria-label*="验证码" i]',
            'input[placeholder*="验证码" i]',
        ]))

    def _submit_email_code(self, page, min_timestamp: float) -> None:
        self.log("等待 OpenAI 邮箱验证码")
        code = self.otp_reader.wait_for_code(min_timestamp)
        inputs = self._visible_inputs(page, [
            'input[autocomplete="one-time-code"]',
            'input[inputmode="numeric"]',
            'input[type="tel"]',
            'input[name="code"]',
        ])
        if not inputs:
            raise RuntimeError("页面未找到验证码输入框")
        if len(inputs) >= 6:
            for index, char in enumerate(code[:6]):
                inputs[index].fill(char)
        else:
            inputs[0].fill(code)
        continue_url = self._validate_email_code_api(page, code)
        self.log("已通过接口提交邮箱验证码")
        if continue_url:
            page.goto(continue_url, wait_until="domcontentloaded", timeout=90000)
        self._wait_after_otp_submit(page)

    def _validate_email_code_api(self, page, code: str) -> str:
        last_detail = ""
        for attempt in range(3):
            result = page.evaluate(
                """async ({code}) => {
                    const resp = await fetch('/api/accounts/email-otp/validate', {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                            accept: 'application/json',
                            'content-type': 'application/json',
                            origin: 'https://auth.openai.com',
                            referer: 'https://auth.openai.com/email-verification',
                        },
                        body: JSON.stringify({ code }),
                    });
                    const text = await resp.text();
                    let data = null;
                    try { data = JSON.parse(text); } catch (_) {}
                    return { ok: resp.ok, status: resp.status, text, data };
                }""",
                {"code": code},
            )
            if result.get("ok"):
                payload = result.get("data") or {}
                return str(payload.get("continue_url") or payload.get("page", {}).get("payload", {}).get("url") or "")

            last_detail = str(result.get("text") or result.get("status") or "")
            if self._is_cloudflare_challenge(last_detail) and attempt < 2:
                self.log("EmailOtpValidate 触发 Cloudflare challenge，正在浏览器中打开挑战页并等待放行")
                self._handle_cloudflare_challenge(page, last_detail)
                continue
            break

        if self._is_cloudflare_challenge(last_detail):
            raise RuntimeError("EmailOtpValidate 被 Cloudflare 持续拦截。请换更干净的动态代理，或在浏览器里的 Cloudflare 页面手动等待通过后重试。")
        raise RuntimeError(f"EmailOtpValidate 接口失败: {last_detail[:800]}")

    def _is_cloudflare_challenge(self, text: str) -> bool:
        value = str(text or "")
        return "challenges.cloudflare.com" in value or "__cf_chl" in value or "Just a moment" in value

    def _extract_cloudflare_challenge_url(self, text: str) -> str:
        value = unescape(str(text or ""))
        for pattern in [r'cUPMDTk:\s*"([^"]+)"', r'history\.replaceState\([^,]+,[^,]+,"([^"]+)"']:
            match = re.search(pattern, value)
            if match:
                raw = match.group(1).replace("\\/", "/")
                return raw if raw.startswith("http") else f"{AUTH_BASE_URL}{raw}"
        return ""

    def _handle_cloudflare_challenge(self, page, challenge_html: str) -> None:
        if self.headless:
            raise RuntimeError("触发 Cloudflare challenge，但当前开启了无头模式，无法手动验证；请取消 UI 中的“无头浏览器”后重试")
        challenge_url = self._extract_cloudflare_challenge_url(challenge_html)
        if not challenge_url:
            raise RuntimeError("触发 Cloudflare challenge，但未能解析挑战 URL；请换代理或手动刷新页面后重试")

        challenge_page = page.context.new_page()
        challenge_page.bring_to_front()
        challenge_page.goto(challenge_url, wait_until="domcontentloaded", timeout=90000)
        self.log("Cloudflare 页面已在新标签页打开，请在弹出的 Chromium 窗口中手动完成验证")
        started = time.time()
        last_notice = 0.0
        while time.time() - started < 120:
            try:
                challenge_page.bring_to_front()
            except Exception:
                pass
            if self._has_cloudflare_clearance(page):
                self.log("Cloudflare 已放行，重试提交邮箱验证码")
                break
            if time.time() - last_notice >= 10:
                remain = max(0, int(120 - (time.time() - started)))
                self.log(f"仍在等待 Cloudflare 放行，剩余约 {remain}s")
                last_notice = time.time()
            time.sleep(2)
        if not self._has_cloudflare_clearance(page):
            raise RuntimeError("Cloudflare 120 秒内未放行；当前代理/IP 风控过高，请更换动态代理后重试")
        try:
            challenge_page.close()
        except Exception:
            pass
        page.bring_to_front()
        page.goto(f"{AUTH_BASE_URL}/email-verification", wait_until="domcontentloaded", timeout=90000)

    def _has_cloudflare_clearance(self, page) -> bool:
        try:
            cookies = page.context.cookies([AUTH_BASE_URL])
            return any(cookie.get("name") == "cf_clearance" for cookie in cookies)
        except Exception:
            return False

    def _wait_after_otp_submit(self, page, timeout: int = 20) -> None:
        started = time.time()
        while time.time() - started < timeout:
            if self._has_chatgpt_session(page):
                return
            if "about-you" in page.url or self._has_about_you_form(page):
                return
            if not ("email-verification" in page.url or self._has_otp_input(page)):
                return
            time.sleep(1)
        page_text = self._page_text_summary(page)
        raise RuntimeError(f"验证码提交后页面仍停留在邮箱验证页，可能验证码已过期/已使用或页面校验失败。页面内容: {page_text}")

    def _page_text_summary(self, page, max_length: int = 300) -> str:
        try:
            text = page.locator("body").inner_text(timeout=1500)
        except Exception:
            return page.url
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_length] or page.url

    def _has_about_you_form(self, page) -> bool:
        try:
            text = page.locator("body").inner_text(timeout=1000).lower()
            return (
                "tell us about you" in text
                or "about you" in text
                or "birth" in text
                or "how old are you" in text
                or "full name" in text
                or "finish creating account" in text
            )
        except Exception:
            return False

    def _fill_about_you(self, page) -> None:
        name, birthdate = random_profile()
        age = str(max(18, datetime.now(timezone.utc).year - int(birthdate.split("-")[0])))
        self.log(f"填写基础资料: {name} / age={age}")
        self._wait_for_about_you_inputs(page)
        self._fill_about_you_inputs(page, name, age)
        self.log("基础资料已填写，等待 5 秒后提交")
        time.sleep(5)
        if not self._submit_about_you(page):
            raise RuntimeError("基础资料已填写，但未找到“完成帐户创建”按钮")

    def _submit_about_you(self, page) -> bool:
        before_url = page.url
        if not self._click_finish_creating_account(page) and not self._click_continue(page):
            if not self._click_button_by_text(page, ["Finish creating account", "完成帐户创建", "完成账户创建", "Create account", "Continue", "完成"]):
                return False

        started = time.time()
        while time.time() - started < 30:
            if page.is_closed():
                raise RuntimeError("浏览器页面已关闭，无法等待基础资料提交结果")
            if self._has_chatgpt_session(page):
                return True
            if page.url != before_url and "about-you" not in page.url:
                return True
            if "add-phone" in page.url or "phone-verification" in page.url:
                return True
            time.sleep(1)
        self.log("基础资料提交后页面未跳转，继续检测当前页面状态")
        return True

    def _click_finish_creating_account(self, page) -> bool:
        selectors = [
            'button:has-text("Finish creating account")',
            'button[type="submit"]:has-text("Finish")',
            'button[data-dd-action-name="Continue"][type="submit"]:has-text("Finish")',
        ]
        for selector in selectors:
            button = page.locator(selector).first
            try:
                if not button.is_visible(timeout=700):
                    continue
                button.scroll_into_view_if_needed(timeout=3000)
                button.click(timeout=5000, force=True)
                self.log(f"已 force click: {selector}")
                return True
            except Exception as exc:
                self.log(f"force click 失败 {selector}: {str(exc)[:120]}")
            try:
                box = button.bounding_box(timeout=3000)
                if box:
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    time.sleep(0.1)
                    page.mouse.up()
                    self.log(f"已坐标点击: {selector}")
                    return True
            except Exception as exc:
                self.log(f"坐标点击失败 {selector}: {str(exc)[:120]}")
            try:
                button.focus(timeout=3000)
                page.keyboard.press("Enter")
                self.log(f"已聚焦按钮并回车: {selector}")
                return True
            except Exception as exc:
                self.log(f"按钮回车失败 {selector}: {str(exc)[:120]}")

        try:
            inputs = self._visible_inputs(page, ['input'])
            if len(inputs) >= 2:
                inputs[1].focus(timeout=3000)
                page.keyboard.press("Enter")
                self.log("已在年龄输入框按 Enter 提交")
                return True
        except Exception as exc:
            self.log(f"年龄输入框 Enter 提交失败: {str(exc)[:120]}")

        clicked = page.evaluate(
            """() => {
                const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                };
                const enabled = (el) => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                const buttons = Array.from(document.querySelectorAll('button')).filter(el => visible(el) && enabled(el));
                const finish = buttons.find(el => (el.textContent || '').trim().includes('Finish creating account'));
                const submit = finish || buttons.find(el =>
                    (el.type || '').toLowerCase() === 'submit'
                    && (el.getAttribute('data-dd-action-name') || '') === 'Continue'
                    && (el.textContent || '').trim().includes('Finish')
                );
                if (!submit) return false;
                submit.scrollIntoView({ block: 'center', inline: 'center' });
                submit.focus();
                const form = submit.closest('form');
                if (form && typeof form.requestSubmit === 'function') {
                    form.requestSubmit(submit);
                    return true;
                }
                submit.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'mouse', isPrimary: true }));
                submit.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
                submit.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerType: 'mouse', isPrimary: true }));
                submit.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, button: 0 }));
                submit.click();
                return true;
            }"""
        )
        if clicked:
            self.log("已提交 Finish creating account 表单")
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            return True
        return False

    def _click_button_by_text(self, page, texts: list[str]) -> bool:
        box = page.evaluate(
            """({texts}) => {
                const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                };
                const candidates = Array.from(document.querySelectorAll('button, [role="button"], a'))
                    .filter(visible)
                    .filter(el => texts.some(text => (el.textContent || '').includes(text)));
                const el = candidates[0];
                if (!el) return null;
                el.scrollIntoView({ block: 'center', inline: 'center' });
                const r = el.getBoundingClientRect();
                return { x: r.left + r.width / 2, y: r.top + r.height / 2, text: el.textContent || '' };
            }""",
            {"texts": texts},
        )
        if not box:
            return False
        page.mouse.click(float(box["x"]), float(box["y"]))
        self.log(f"已点击按钮: {str(box.get('text', '')).strip()[:40]}")
        return True

    def _wait_for_about_you_inputs(self, page, timeout: int = 30) -> None:
        started = time.time()
        while time.time() - started < timeout:
            count = page.evaluate("""() => Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]')).filter(el => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
            }).length""")
            if int(count or 0) >= 2:
                return
            time.sleep(0.5)
        raise RuntimeError("about-you 页面 30 秒内未出现姓名/年龄输入框")

    def _fill_about_you_inputs(self, page, name: str, age: str) -> None:
        try:
            self._fill_visible_input_by_keyboard(page, 0, name)
            self._fill_visible_input_by_keyboard(page, 1, age)
            values = self._visible_input_values(page)
            if self._about_you_values_ok(values):
                self.log("基础资料已通过键盘输入")
                return
        except Exception as exc:
            self.log(f"基础资料键盘输入失败，改用 DOM 填写: {str(exc)[:120]}")

        values = self._fill_about_you_inputs_by_dom(page, name, age)
        if self._about_you_values_ok(values):
            return

        filled_name = self._fill_first_visible(page, [
            'input[name="name"]',
            'input[autocomplete="name"]',
            'input[placeholder*="name" i]',
            'input[placeholder*="全名" i]',
            'input[aria-label*="name" i]',
            'input[aria-label*="全名" i]',
        ], name)
        filled_age = self._fill_first_visible(page, [
            'input[name="age"]',
            'input[placeholder*="age" i]',
            'input[aria-label*="age" i]',
            'input[placeholder*="年龄" i]',
            'input[aria-label*="年龄" i]',
        ], age)

        if not filled_name or not filled_age:
            visible_inputs = self._visible_inputs(page, ['input'])
            if not filled_name and len(visible_inputs) >= 1:
                self._force_fill_locator(visible_inputs[0], name)
                filled_name = True
            if not filled_age and len(visible_inputs) >= 2:
                self._force_fill_locator(visible_inputs[1], age)
                filled_age = True

        values = page.evaluate("""() => Array.from(document.querySelectorAll('input')).filter(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
        }).map(el => el.value || '')""")
        if self._about_you_values_ok(values):
            return

        self.log("基础资料 DOM 填写未生效，改用鼠标点击 + 键盘输入")
        self._fill_visible_input_by_keyboard(page, 0, name)
        self._fill_visible_input_by_keyboard(page, 1, age)
        values = self._visible_input_values(page)
        if not self._about_you_values_ok(values):
            raise RuntimeError(f"基础资料输入框未写入成功，当前可见输入值={values}。请手动填写姓名和年龄后继续")

    def _fill_about_you_inputs_by_dom(self, page, name: str, age: str) -> list[str]:
        return page.evaluate(
            """({name, age}) => {
                const visible = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                };
                const controls = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]')).filter(visible);
                const setValue = (el, value) => {
                    if (!el) return false;
                    el.scrollIntoView({ block: 'center', inline: 'center' });
                    el.focus();
                    if (el.isContentEditable) {
                        el.textContent = value;
                    } else {
                        const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                        const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                        if (desc && desc.set) desc.set.call(el, value); else el.value = value;
                    }
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                    return true;
                };
                const attrMatch = (el, words) => words.some(word => [
                    el.getAttribute('name'), el.getAttribute('autocomplete'), el.getAttribute('placeholder'),
                    el.getAttribute('aria-label'), el.id, el.getAttribute('data-testid')
                ].some(value => String(value || '').toLowerCase().includes(word.toLowerCase())));
                const byLabel = (words) => {
                    for (const label of Array.from(document.querySelectorAll('label'))) {
                        const text = (label.textContent || '').trim().toLowerCase();
                        if (!words.some(word => text.includes(word.toLowerCase()))) continue;
                        if (label.htmlFor) {
                            const linked = document.getElementById(label.htmlFor);
                            if (visible(linked)) return linked;
                        }
                        const nested = label.querySelector('input, textarea, [contenteditable="true"]');
                        if (visible(nested)) return nested;
                        const sibling = label.parentElement?.querySelector('input, textarea, [contenteditable="true"]');
                        if (visible(sibling)) return sibling;
                    }
                    return null;
                };
                const nameEl = controls.find(el => attrMatch(el, ['name', 'full', 'fullname', '全名'])) || byLabel(['全名', 'name']) || controls[0];
                const ageEl = controls.find(el => el !== nameEl && attrMatch(el, ['age', '年龄']))
                    || byLabel(['年龄', 'age'])
                    || controls.find(el => el !== nameEl && (el.type === 'number' || el.inputMode === 'numeric'))
                    || controls.find(el => el !== nameEl)
                    || controls[1];
                setValue(nameEl, name);
                setValue(ageEl, age);
                return controls.map(el => el.isContentEditable ? (el.textContent || '') : (el.value || ''));
            }""",
            {"name": name, "age": age},
        )

    def _visible_input_values(self, page) -> list[str]:
        return page.evaluate("""() => Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]')).filter(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
        }).map(el => el.isContentEditable ? (el.textContent || '') : (el.value || ''))""")

    def _about_you_values_ok(self, values: list[str]) -> bool:
        normalized = [str(value).strip() for value in values]
        return len(normalized) >= 2 and bool(normalized[0]) and bool(normalized[1])

    def _fill_visible_input_by_keyboard(self, page, index: int, value: str) -> None:
        box = page.evaluate(
            """({index}) => {
                const controls = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]')).filter(el => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                });
                const el = controls[index];
                if (!el) return null;
                el.scrollIntoView({ block: 'center', inline: 'center' });
                const r = el.getBoundingClientRect();
                return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            }""",
            {"index": index},
        )
        if not box:
            raise RuntimeError(f"未找到第 {index + 1} 个可见输入框")
        page.mouse.click(float(box["x"]), float(box["y"]))
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(str(value), delay=30)
        page.keyboard.press("Tab")
        time.sleep(0.5)

    def _fill_first_visible(self, page, selectors: list[str], value: str) -> bool:
        for locator in self._visible_inputs(page, selectors):
            if self._force_fill_locator(locator, value):
                return True
        return False

    def _force_fill_locator(self, locator, value: str) -> bool:
        try:
            locator.click(timeout=3000)
            locator.fill(str(value), timeout=5000)
            locator.evaluate("""(el, value) => {
                const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                if (desc && desc.set) desc.set.call(el, value); else el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", str(value))
            return True
        except Exception:
            return False

    def _extract_pay_link(self, page) -> str:
        mode = PAYMENT_MODES.get(self.payment_mode) or PAYMENT_MODES["无卡长链接 US/USD"]
        self.log(f"提取支付长链接: {self.payment_mode}")
        if page.is_closed():
            raise RuntimeError("浏览器页面已关闭，无法提取支付长链接")
        page.goto(CHATGPT_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        last_error = "未知错误"
        started = time.time()
        for attempt in range(1, 16):
            if page.is_closed():
                raise RuntimeError("浏览器页面已关闭，无法提取支付长链接")
            if time.time() - started > 120:
                break
            self.log(f"正在提取支付长链接 ({attempt}/15)")
            try:
                link = page.evaluate(
                    """async ({country, currency}) => {
                        const sessionResp = await fetch('/api/auth/session', { credentials: 'include' });
                        if (!sessionResp.ok) throw new Error(`Session 请求失败: HTTP ${sessionResp.status}`);
                        const session = await sessionResp.json();
                        if (!session.accessToken) throw new Error('无法获取 accessToken，请确认已登录');
                        const payload = {
                            entry_point: 'ALL_PLANS_PRICING_MODAL',
                            plan_name: 'chatgptplusplan',
                            billing_details: { country, currency },
                            cancel_url: 'https://chatgpt.com/#pricing',
                            promo_campaign: { promo_campaign_id: 'plus-1-month-free', is_coupon_from_query_param: false },
                            checkout_ui_mode: 'hosted',
                        };
                        const resp = await fetch('/backend-api/payments/checkout', {
                            method: 'POST',
                            credentials: 'include',
                            headers: { Authorization: `Bearer ${session.accessToken}`, 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload),
                        });
                        const data = await resp.json().catch(() => ({}));
                        const url = data.url || data.checkout_url || data.redirect_url;
                        if (!resp.ok || !url) throw new Error(`生成支付链接失败: HTTP ${resp.status} ${JSON.stringify(data).slice(0, 300)}`);
                        return url;
                    }""",
                    mode,
                )
                if link:
                    self.log("支付长链接已生成")
                    return str(link)
            except Exception as exc:
                last_error = exc
                if "Target page" in str(exc) or "closed" in str(exc).lower():
                    raise RuntimeError("浏览器被关闭，支付长链接提取已停止")
                self.log(f"支付长链接提取失败，准备重试: {str(exc)[:180]}")
                time.sleep(4)
        raise RuntimeError(f"提取支付长链接失败: {last_error}")


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x760")
        self.accounts: list[MailAccount] = []
        self.phones: list[PhoneEntry] = []
        self.payment_cards: list[PaymentCard] = []
        self.results: dict[str, str] = {}
        self.events: queue.Queue = queue.Queue()
        self.pending_prompts: dict[str, queue.Queue] = {}
        self.running = False
        self.opening_payment_link = False
        self.stop_event = threading.Event()
        self.payment_context = None
        self.payment_contexts: set = set()
        self.open_payment_window_count = 0
        self.payment_mode = StringVar(value="无卡长链接 US/USD")
        self.headless = BooleanVar(value=False)
        self.local_proxy = StringVar(value="http://127.0.0.1:7890")
        self.payment_dynamic_proxy = StringVar(value="")
        self.register_with_payment_proxy = BooleanVar(value=False)
        self.payment_extension_dir = StringVar(value=DEFAULT_PAYPAL_EXTENSION_DIR)
        self.paypal_phone = StringVar(value="")
        self.paypal_card = StringVar(value="")
        self.paypal_sms_url = StringVar(value="")
        self.paypal_phone_pool = StringVar(value="")
        self.export_name_prefix = StringVar(value="")
        self.phone_max_receive_count = IntVar(value=0)
        self.dynamic_proxy_index = 0
        self.paypal_phone_pool_index = 0
        self._build_ui()
        self.load_state()
        self.root.after(100, self._drain_events)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=BOTH, expand=True)

        tabs = ttk.Notebook(main)
        tabs.pack(fill=X, pady=(0, 8))

        import_tab = ttk.Frame(tabs, padding=8)
        tabs.add(import_tab, text="导入邮箱")
        top = ttk.Frame(import_tab)
        top.pack(fill=X)
        ttk.Label(top, text="每行：email----password----client_id----refresh_token").pack(side=LEFT)
        ttk.Button(top, text="从文件导入", command=self.load_file).pack(side=RIGHT)
        self.import_text = ScrolledText(import_tab, height=4)
        self.import_text.pack(fill=X, pady=(6, 0))

        phone_frame = ttk.Frame(tabs, padding=8)
        tabs.add(phone_frame, text="手机号池")
        ttk.Label(phone_frame, text="每行：+手机号https://短信链接 或 +手机号----https://短信链接；同一手机号可连续授权，失败后自动标记不可用").pack(anchor="w")
        phone_limit_row = ttk.Frame(phone_frame)
        phone_limit_row.pack(fill=X, pady=(6, 0))
        ttk.Label(phone_limit_row, text="每个手机号最多接码次数（0=不限制）").pack(side=LEFT)
        ttk.Entry(phone_limit_row, textvariable=self.phone_max_receive_count, width=8).pack(side=LEFT, padx=(8, 0))
        phone_top = ttk.Frame(phone_frame)
        phone_top.pack(fill=X, pady=(6, 0))
        self.phone_text = ScrolledText(phone_top, height=3)
        self.phone_text.pack(side=LEFT, fill=X, expand=True)
        phone_buttons = ttk.Frame(phone_top)
        phone_buttons.pack(side=LEFT, padx=(8, 0), fill="y")
        ttk.Button(phone_buttons, text="导入手机号", command=self.import_phones).pack(fill=X)
        ttk.Button(phone_buttons, text="重置手机号", command=self.reset_phones).pack(fill=X, pady=(8, 0))
        ttk.Button(phone_buttons, text="清空手机号", command=self.clear_phones).pack(fill=X, pady=(8, 0))
        ttk.Button(phone_buttons, text="手动取码", command=self.fetch_selected_phone_code).pack(fill=X, pady=(8, 0))
        ttk.Label(phone_frame, text="手机号状态").pack(anchor="w", pady=(8, 4))
        self.phone_list = ttk.Treeview(phone_frame, columns=("number", "count", "status", "code"), show="headings", height=3)
        self.phone_list.heading("number", text="手机号")
        self.phone_list.heading("count", text="接码次数")
        self.phone_list.heading("status", text="状态")
        self.phone_list.heading("code", text="最近验证码")
        self.phone_list.column("number", width=180)
        self.phone_list.column("count", width=80)
        self.phone_list.column("status", width=120)
        self.phone_list.column("code", width=120)
        self.phone_list.pack(fill=X)

        paypal_frame = ttk.Frame(tabs, padding=8)
        tabs.add(paypal_frame, text="PayPal扩展")
        ttk.Label(paypal_frame, text="支付 PP 用；这里的手机号不是授权接码手机号").pack(anchor="w")
        paypal_top = ttk.Frame(paypal_frame)
        paypal_top.pack(fill=X, pady=(6, 0))
        ttk.Label(paypal_top, text="PP手机号").pack(side=LEFT)
        ttk.Entry(paypal_top, textvariable=self.paypal_phone, width=24).pack(side=LEFT, padx=(8, 16))
        ttk.Label(paypal_top, text="卡信息").pack(side=LEFT)
        ttk.Entry(paypal_top, textvariable=self.paypal_card).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        ttk.Button(paypal_top, text="保存", command=self.save_paypal_settings).pack(side=LEFT)
        paypal_ext_row = ttk.Frame(paypal_frame)
        paypal_ext_row.pack(fill=X, pady=(8, 0))
        ttk.Label(paypal_ext_row, text="支付链接扩展目录").pack(side=LEFT)
        ttk.Entry(paypal_ext_row, textvariable=self.payment_extension_dir, width=72).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        ttk.Button(paypal_ext_row, text="选择目录", command=self.select_payment_extension_dir).pack(side=LEFT, padx=(0, 8))
        ttk.Label(paypal_frame, text="卡信息格式：卡号----有效期----CVV----电话----sms-token----姓名----街道,城市 邮编,国家").pack(anchor="w", pady=(6, 0))
        paypal_sms_row = ttk.Frame(paypal_frame)
        paypal_sms_row.pack(fill=X, pady=(8, 0))
        ttk.Label(paypal_sms_row, text="PP取码链接").pack(side=LEFT)
        ttk.Entry(paypal_sms_row, textvariable=self.paypal_sms_url).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        ttk.Label(paypal_frame, text="PP手机号+接码池（每行一个：+手机号----https://接码链接；打开支付链接优先取第一行，用后移除）").pack(anchor="w", pady=(8, 4))
        self.paypal_phone_pool_text = ScrolledText(paypal_frame, height=3)
        self.paypal_phone_pool_text.pack(fill=X)
        ttk.Label(paypal_frame, text="支付卡池（每行：卡号|月|年|CVV；每次打开支付链接自动取一张未用卡替换卡信息前三段）").pack(anchor="w", pady=(8, 4))
        card_top = ttk.Frame(paypal_frame)
        card_top.pack(fill=X)
        self.payment_card_text = ScrolledText(card_top, height=3)
        self.payment_card_text.pack(side=LEFT, fill=X, expand=True)
        card_buttons = ttk.Frame(card_top)
        card_buttons.pack(side=LEFT, padx=(8, 0), fill="y")
        ttk.Button(card_buttons, text="导入卡", command=self.import_payment_cards).pack(fill=X)
        ttk.Button(card_buttons, text="重置卡", command=self.reset_payment_cards).pack(fill=X, pady=(8, 0))
        self.payment_card_list = ttk.Treeview(paypal_frame, columns=("card", "expiry", "cvv", "status"), show="headings", height=3)
        self.payment_card_list.heading("card", text="卡号")
        self.payment_card_list.heading("expiry", text="有效期")
        self.payment_card_list.heading("cvv", text="CVV")
        self.payment_card_list.heading("status", text="状态")
        self.payment_card_list.column("card", width=220)
        self.payment_card_list.column("expiry", width=100)
        self.payment_card_list.column("cvv", width=80)
        self.payment_card_list.column("status", width=80)
        self.payment_card_list.pack(fill=X, pady=(6, 0))

        proxy_frame = ttk.Frame(tabs, padding=8)
        tabs.add(proxy_frame, text="代理设置")
        ttk.Label(proxy_frame, text="链式：本地代理 -> 动态代理 -> 目标站点").pack(anchor="w")
        proxy_top = ttk.Frame(proxy_frame)
        proxy_top.pack(fill=X, pady=(6, 0))
        ttk.Label(proxy_top, text="本地代理").pack(side=LEFT)
        ttk.Entry(proxy_top, textvariable=self.local_proxy, width=36).pack(side=LEFT, padx=(8, 16))
        ttk.Label(proxy_top, text="留空=不走本地代理；例如 http://127.0.0.1:7890 / socks 请先转 HTTP").pack(side=LEFT)
        ttk.Label(proxy_frame, text="动态代理池（每行一个：username:password@hostname:port；注册/提取长链取第一行，用后移除）").pack(anchor="w", pady=(8, 4))
        self.proxy_text = ScrolledText(proxy_frame, height=4)
        self.proxy_text.pack(fill=X)
        payment_proxy_row = ttk.Frame(proxy_frame)
        payment_proxy_row.pack(fill=X, pady=(8, 0))
        ttk.Label(payment_proxy_row, text="支付链接动态代理（每行一个；打开链接时取第一行，用后移除）").pack(anchor="w")
        self.payment_dynamic_proxy_text = ScrolledText(payment_proxy_row, height=3)
        self.payment_dynamic_proxy_text.pack(fill=X, pady=(6, 0))
        ttk.Checkbutton(proxy_frame, text="注册时使用支付链接动态代理（特殊情况勾选；不勾选则用上方动态代理池）", variable=self.register_with_payment_proxy).pack(anchor="w", pady=(6, 0))
        extension_row = ttk.Frame(proxy_frame)
        extension_row.pack(fill=X, pady=(8, 0))
        ttk.Label(extension_row, text="支付链接扩展目录").pack(side=LEFT)
        ttk.Entry(extension_row, textvariable=self.payment_extension_dir, width=72).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        ttk.Button(extension_row, text="选择目录", command=self.select_payment_extension_dir).pack(side=LEFT, padx=(0, 8))
        ttk.Label(extension_row, text="需选择解压后的 Chrome 扩展目录").pack(side=LEFT)

        controls = ttk.Frame(main)
        controls.pack(fill=X, pady=(0, 4))
        row1 = ttk.Frame(controls)
        row1.pack(fill=X)
        ttk.Button(row1, text="导入到列表", command=self.import_accounts).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="清空列表", command=self.clear_accounts).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="删除选中邮箱", command=self.delete_selected_account).pack(side=LEFT, padx=(0, 16))
        ttk.Button(row1, text="设为 Plus", command=lambda: self.set_selected_account_type("plus")).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="设为 Free", command=lambda: self.set_selected_account_type("free")).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="刷新类型", command=self.refresh_selected_account_type).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="Plus授权获取RT", command=self.start_authorize_selected).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="导出已授权", command=self.export_authorized).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="导出邮箱RT", command=self.export_authorized_email_rt).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="导出sub2api", command=self.export_sub2api).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="停止当前任务", command=self.stop_current_task).pack(side=LEFT)

        row2 = ttk.Frame(controls)
        row2.pack(fill=X, pady=(6, 0))
        ttk.Label(row2, text="支付模式").pack(side=LEFT)
        ttk.Combobox(row2, textvariable=self.payment_mode, values=list(PAYMENT_MODES.keys()), state="readonly", width=22).pack(side=LEFT, padx=8)
        ttk.Checkbutton(row2, text="无头浏览器", variable=self.headless).pack(side=LEFT, padx=8)
        ttk.Button(row2, text="注册选中邮箱并提取长链接", command=self.start_selected).pack(side=LEFT, padx=(16, 8))
        ttk.Button(row2, text="重新获取长链接", command=self.refetch_selected_link).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row2, text="批量并发重新获取", command=self.refetch_selected_links_batch).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row2, text="批量处理全部", command=self.start_all).pack(side=LEFT)
        ttk.Label(row2, text="导出名前缀").pack(side=LEFT, padx=(16, 0))
        ttk.Entry(row2, textvariable=self.export_name_prefix, width=18).pack(side=LEFT, padx=(8, 0))

        body = ttk.PanedWindow(main, orient="horizontal")
        body.pack(fill=BOTH, expand=True)

        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text="邮箱列表").pack(anchor="w")
        self.account_list = ttk.Treeview(left, columns=("email", "type", "status"), show="headings", height=14, selectmode="extended")
        self.account_list.heading("email", text="邮箱")
        self.account_list.heading("type", text="类型")
        self.account_list.heading("status", text="状态")
        self.account_list.column("email", width=270)
        self.account_list.column("type", width=70)
        self.account_list.column("status", width=140)
        self.account_list.pack(fill=BOTH, expand=True, pady=(6, 0))
        self.account_list.bind("<<TreeviewSelect>>", lambda _e: self._show_selected_account_link())

        right = ttk.Frame(body)
        body.add(right, weight=2)
        result_header = ttk.Frame(right)
        result_header.pack(fill=X)
        ttk.Label(result_header, text="当前选中邮箱长链接").pack(side=LEFT)
        ttk.Button(result_header, text="批量打开选中", command=self.open_selected_links).pack(side=RIGHT, padx=(0, 8))
        ttk.Button(result_header, text="浏览器打开", command=self.open_link).pack(side=RIGHT)
        ttk.Button(result_header, text="复制长链接", command=self.copy_link).pack(side=RIGHT, padx=(0, 8))

        link_bar = ttk.Frame(right)
        link_bar.pack(fill=X, pady=(6, 8))
        self.link_var = StringVar(value="")
        ttk.Entry(link_bar, textvariable=self.link_var).pack(side=LEFT, fill=X, expand=True)

        ttk.Label(right, text="日志").pack(anchor="w", pady=(12, 0))
        self.log_text = ScrolledText(right, height=14)
        self.log_text.pack(fill=BOTH, expand=True, pady=(6, 0))

    def load_state(self) -> None:
        if not STATE_FILE.exists():
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.accounts = [account_from_dict(item) for item in data.get("accounts", [])]
            self.phones = [phone_from_dict(item) for item in data.get("phones", []) if item]
            self.payment_cards = [payment_card_from_dict(item) for item in data.get("payment_cards", []) if item]
            self.results = {str(k): str(v) for k, v in data.get("results", {}).items() if v}
            settings = data.get("settings", {})
            if settings.get("payment_mode") in PAYMENT_MODES:
                self.payment_mode.set(settings["payment_mode"])
            if "headless" in settings:
                self.headless.set(bool(settings["headless"]))
            if "local_proxy" in settings:
                self.local_proxy.set(str(settings["local_proxy"]))
            if "dynamic_proxies" in settings:
                self.proxy_text.delete("1.0", END)
                self.proxy_text.insert(END, str(settings["dynamic_proxies"]))
            if "payment_dynamic_proxy" in settings:
                self.payment_dynamic_proxy.set(str(settings["payment_dynamic_proxy"]))
                self.payment_dynamic_proxy_text.delete("1.0", END)
                self.payment_dynamic_proxy_text.insert(END, str(settings["payment_dynamic_proxy"]))
            if "register_with_payment_proxy" in settings:
                self.register_with_payment_proxy.set(bool(settings["register_with_payment_proxy"]))
            if "payment_extension_dir" in settings:
                self.payment_extension_dir.set(str(settings["payment_extension_dir"]).strip() or DEFAULT_PAYPAL_EXTENSION_DIR)
            if "paypal_phone" in settings:
                self.paypal_phone.set(str(settings["paypal_phone"]))
            if "paypal_card" in settings:
                self.paypal_card.set(str(settings["paypal_card"]))
            if "paypal_sms_url" in settings:
                self.paypal_sms_url.set(str(settings["paypal_sms_url"]))
            if "paypal_phone_pool" in settings:
                self.paypal_phone_pool.set(str(settings["paypal_phone_pool"]))
                self.paypal_phone_pool_text.delete("1.0", END)
                self.paypal_phone_pool_text.insert(END, str(settings["paypal_phone_pool"]))
            if "export_name_prefix" in settings:
                self.export_name_prefix.set(str(settings["export_name_prefix"]))
            if "phone_max_receive_count" in settings:
                self.phone_max_receive_count.set(max(0, int(settings["phone_max_receive_count"] or 0)))
            if "paypal_phone_pool_index" in settings:
                self.paypal_phone_pool_index = max(0, int(settings["paypal_phone_pool_index"] or 0))
            self._render_accounts()
            self._render_phones()
            self._render_payment_cards()
            self._render_results()
            self.log(f"已加载本地记录: {STATE_FILE}")
        except Exception as exc:
            self.log(f"加载本地记录失败: {exc}")

    def save_state(self) -> None:
        data = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "accounts": [account_to_dict(account) for account in self.accounts],
            "phones": [phone_to_dict(phone) for phone in self.phones],
            "payment_cards": [payment_card_to_dict(card) for card in self.payment_cards],
            "results": self.results,
            "settings": {
                "payment_mode": self.payment_mode.get(),
                "headless": bool(self.headless.get()),
                "local_proxy": self.local_proxy.get(),
                "dynamic_proxies": self.proxy_text.get("1.0", END).strip(),
                "payment_dynamic_proxy": self.payment_dynamic_proxy_text.get("1.0", END).strip(),
                "register_with_payment_proxy": bool(self.register_with_payment_proxy.get()),
                "payment_extension_dir": self.payment_extension_dir.get().strip(),
                "paypal_phone": self.paypal_phone.get().strip(),
                "paypal_card": self.paypal_card.get().strip(),
                "paypal_sms_url": self.paypal_sms_url.get().strip(),
                "paypal_phone_pool": self.paypal_phone_pool_text.get("1.0", END).strip(),
                "export_name_prefix": self.export_name_prefix.get().strip(),
                "phone_max_receive_count": max(0, int(self.phone_max_receive_count.get() or 0)),
                "paypal_phone_pool_index": self.paypal_phone_pool_index,
            },
        }
        tmp = STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(STATE_FILE)

    def load_file(self) -> None:
        path = filedialog.askopenfilename(title="选择邮箱文件", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        self.import_text.delete("1.0", END)
        self.import_text.insert(END, Path(path).read_text(encoding="utf-8"))

    def select_payment_extension_dir(self) -> None:
        path = filedialog.askdirectory(title="选择解压后的 Chrome 扩展目录")
        if not path:
            return
        self.payment_extension_dir.set(path)
        self.save_state()

    def save_paypal_settings(self) -> None:
        self.save_state()
        self.log("PayPal 扩展资料已保存")

    def import_phones(self) -> None:
        lines = [line.strip() for line in self.phone_text.get("1.0", END).splitlines() if line.strip()]
        if not lines:
            messagebox.showwarning(APP_TITLE, "请先粘贴手机号")
            return
        imported = 0
        errors = []
        for index, line in enumerate(lines, start=1):
            try:
                phone = parse_phone_line(line)
            except Exception as exc:
                errors.append(f"第 {index} 行: {exc}")
                continue
            old_index = next((i for i, item in enumerate(self.phones) if item.number == phone.number), -1)
            if old_index >= 0:
                self.phones[old_index].sms_url = phone.sms_url
                if self.phones[old_index].status == "不可用":
                    self.phones[old_index].status = "可用"
                    self.phones[old_index].last_error = ""
            else:
                self.phones.append(phone)
            imported += 1
        self._render_phones()
        self.save_state()
        self.log(f"已导入 {imported} 个手机号" + (f"；失败: {'; '.join(errors)}" if errors else ""))

    def reset_phones(self) -> None:
        for phone in self.phones:
            phone.status = "可用"
            phone.last_error = ""
            phone.receive_count = 0
        self._render_phones()
        self.save_state()
        self.log("手机号池已重置为可用")

    def clear_phones(self) -> None:
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行，不能清空手机号池")
            return
        if not self.phones:
            return
        if not messagebox.askyesno(APP_TITLE, f"确认清空手机号池？\n当前共 {len(self.phones)} 个手机号"):
            return
        self.phones.clear()
        self._render_phones()
        self.save_state()
        self.log("手机号池已清空")

    def _phone_receive_limit(self) -> int:
        try:
            return max(0, int(self.phone_max_receive_count.get() or 0))
        except Exception:
            return 0

    def _phone_is_frozen(self, phone: PhoneEntry) -> bool:
        limit = self._phone_receive_limit()
        return limit > 0 and phone.receive_count >= limit

    def fetch_selected_phone_code(self) -> None:
        selected = self.phone_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中手机号")
            return
        try:
            index = int(selected[0])
        except ValueError:
            return
        if index < 0 or index >= len(self.phones):
            return
        phone = self.phones[index]
        threading.Thread(target=self._manual_fetch_phone_code_worker, args=(phone,), daemon=True).start()

    def _manual_fetch_phone_code_worker(self, phone: PhoneEntry) -> None:
        try:
            self.events.put(("log", f"[手动取码] 开始读取 {phone.number}"))
            code = self._wait_for_phone_code(phone.number, phone.sms_url, timeout=30)
            self.events.put(("log", f"[手动取码] {phone.number} 读取到验证码: {code}"))
            self.events.put(("phone-code-popup", phone.number, code))
        except Exception as exc:
            self.events.put(("log", f"[手动取码] {phone.number} 读取失败: {exc}"))
            self.events.put(("phone-code-popup", phone.number, ""))

    def import_payment_cards(self) -> None:
        lines = [line.strip() for line in self.payment_card_text.get("1.0", END).splitlines() if line.strip()]
        if not lines:
            messagebox.showwarning(APP_TITLE, "请先粘贴支付卡")
            return
        imported = 0
        errors = []
        for index, line in enumerate(lines, start=1):
            try:
                card = parse_payment_card_line(line)
            except Exception as exc:
                errors.append(f"第 {index} 行: {exc}")
                continue
            old_index = next((i for i, item in enumerate(self.payment_cards) if item.card == card.card), -1)
            if old_index >= 0:
                old_status = self.payment_cards[old_index].status
                self.payment_cards[old_index] = card
                self.payment_cards[old_index].status = old_status
            else:
                self.payment_cards.append(card)
            imported += 1
        self._render_payment_cards()
        self.save_state()
        self.log(f"已导入 {imported} 张支付卡" + (f"；失败: {'; '.join(errors)}" if errors else ""))

    def reset_payment_cards(self) -> None:
        for card in self.payment_cards:
            card.status = "未用"
        self._render_payment_cards()
        self.save_state()
        self.log("支付卡池已重置为未用")

    def import_accounts(self) -> None:
        lines = [line.strip() for line in self.import_text.get("1.0", END).splitlines() if line.strip()]
        if not lines:
            messagebox.showwarning(APP_TITLE, "请先粘贴邮箱账户")
            return
        imported = 0
        errors = []
        for index, line in enumerate(lines, start=1):
            try:
                account = parse_account_line(line)
            except Exception as exc:
                errors.append(f"第 {index} 行: {exc}")
                continue
            old_index = next((i for i, item in enumerate(self.accounts) if item.email.lower() == account.email.lower()), -1)
            if old_index >= 0:
                account.account_type = self.accounts[old_index].account_type
                account.status = self.accounts[old_index].status
                account.openai_rt = self.accounts[old_index].openai_rt or account.openai_rt
                self.accounts[old_index] = account
            else:
                self.accounts.append(account)
            imported += 1
        self._render_accounts()
        self.save_state()
        self.log(f"已导入 {imported} 个邮箱" + (f"；失败: {'; '.join(errors)}" if errors else ""))

    def clear_accounts(self) -> None:
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行，不能清空列表")
            return
        self.accounts.clear()
        self.results.clear()
        self._render_accounts()
        self._render_results()
        self.link_var.set("")
        self.save_state()

    def delete_selected_account(self) -> None:
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行，不能删除邮箱")
            return
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中要删除的邮箱")
            return
        indices = sorted({int(item) for item in selected if str(item).isdigit()}, reverse=True)
        accounts = [self.accounts[index] for index in indices if 0 <= index < len(self.accounts)]
        if not accounts:
            return
        if len(accounts) == 1:
            confirm_text = f"确认删除邮箱？\n{accounts[0].email}"
        else:
            preview = "\n".join(account.email for account in accounts[:20])
            if len(accounts) > 20:
                preview += f"\n... 另有 {len(accounts) - 20} 个"
            confirm_text = f"确认删除 {len(accounts)} 个邮箱？\n{preview}"
        if not messagebox.askyesno(APP_TITLE, confirm_text):
            return
        current_link = self.link_var.get().strip()
        deleted_emails = []
        clear_link = False
        for index in indices:
            if index < 0 or index >= len(self.accounts):
                continue
            account = self.accounts[index]
            old_link = self.results.pop(account.email, "")
            if old_link and current_link == old_link:
                clear_link = True
            deleted_emails.append(account.email)
            del self.accounts[index]
        if clear_link:
            self.link_var.set("")
        self._render_accounts()
        self._render_results()
        self.save_state()
        self.log(f"已删除邮箱 {len(deleted_emails)} 个: {', '.join(deleted_emails[:10])}" + (f" 等" if len(deleted_emails) > 10 else ""))

    def set_selected_account_type(self, account_type: str) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中邮箱，可多选")
            return
        updated = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if index < 0 or index >= len(self.accounts):
                continue
            account = self.accounts[index]
            account.account_type = account_type
            if account_type == "plus":
                account.status = account.status or "Plus"
            if account_type == "free":
                account.status = ""
                account.openai_rt = ""
            updated.append(account.email)
        if not updated:
            return
        self._render_accounts()
        self.save_state()
        self.log(f"已将 {len(updated)} 个邮箱类型改为 {account_type}: {', '.join(updated[:10])}" + (" 等" if len(updated) > 10 else ""))

    def refresh_selected_account_type(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中一个邮箱")
            return
        index = int(selected[0])
        if index < 0 or index >= len(self.accounts):
            return
        account = self.accounts[index]
        if not account.openai_rt:
            messagebox.showwarning(APP_TITLE, "这个邮箱还没有 rt_token，请先 Plus授权获取RT")
            return
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        self.running = True
        self.save_state()
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        dynamic_proxy = self._next_dynamic_proxy(self._read_dynamic_proxies())
        threading.Thread(target=self._refresh_account_type_worker, args=(account, local_proxy, dynamic_proxy), daemon=True).start()

    def _refresh_account_type_worker(self, account: MailAccount, local_proxy: str, dynamic_proxy: str) -> None:
        try:
            self.events.put(("status", account.email, "刷新类型中"))
            with ProxyChainServer(local_proxy, dynamic_proxy, lambda msg: self.events.put(("log", msg))) as chain:
                proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=dynamic_proxy, chain_url=chain.url)
                self.events.put(("log", f"[{account.email}] 刷新类型使用代理: {proxy.label}"))
                account_type, detail, new_rt = detect_openai_account_type(account.openai_rt, chain.url)
            account.account_type = account_type
            if new_rt:
                account.openai_rt = new_rt
            account.status = "已绑定手机号" if account_type == "plus" else "Free"
            self.events.put(("account-updated", account.email))
            self.events.put(("status", account.email, account.status))
            self.events.put(("log", f"[{account.email}] 当前类型: {account_type} ({detail})"))
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 刷新类型失败: {exc}"))
            self.events.put(("status", account.email, "刷新失败"))
        finally:
            self.events.put(("done",))

    def stop_current_task(self) -> None:
        self.stop_event.set()
        if self.payment_context:
            try:
                self.payment_context.close()
            except Exception:
                pass
        for context in list(self.payment_contexts):
            try:
                context.close()
            except Exception:
                pass
        for prompt_id, result_queue in list(self.pending_prompts.items()):
            try:
                result_queue.put("")
            except Exception:
                pass
            self.pending_prompts.pop(prompt_id, None)
        if self.running or self.opening_payment_link:
            self.log("已请求停止当前任务")
        self.running = False
        self.opening_payment_link = False
        self.save_state()

    def start_selected(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中邮箱")
            return
        accounts = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if 0 <= index < len(self.accounts):
                accounts.append(self.accounts[index])
        if accounts:
            self._start_worker(accounts)

    def start_all(self) -> None:
        if not self.accounts:
            messagebox.showwarning(APP_TITLE, "请先导入邮箱")
            return
        self._start_worker(list(self.accounts))

    def refetch_selected_link(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中邮箱")
            return
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        index = int(selected[0])
        account = self.accounts[index]
        self.running = True
        self.stop_event.clear()
        self.save_state()
        mode = self.payment_mode.get()
        headless = bool(self.headless.get())
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        dynamic_proxies = self._take_dynamic_proxies(1)
        payment_dynamic_proxy = self._peek_payment_dynamic_proxy()
        use_payment_proxy_for_register = bool(self.register_with_payment_proxy.get())
        threading.Thread(target=self._refetch_link_worker, args=(account, mode, headless, local_proxy, dynamic_proxies, payment_dynamic_proxy, use_payment_proxy_for_register), daemon=True).start()

    def refetch_selected_links_batch(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中邮箱，可多选")
            return
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        accounts = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if 0 <= index < len(self.accounts):
                accounts.append(self.accounts[index])
        if not accounts:
            messagebox.showwarning(APP_TITLE, "未找到有效选中邮箱")
            return
        self.running = True
        self.stop_event.clear()
        self.save_state()
        mode = self.payment_mode.get()
        headless = bool(self.headless.get())
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        dynamic_proxies = self._take_dynamic_proxies(len(accounts))
        payment_dynamic_proxy = self._peek_payment_dynamic_proxy()
        use_payment_proxy_for_register = bool(self.register_with_payment_proxy.get())
        proxy_assignments = []
        proxy_index = 0
        for account in accounts:
            extract_dynamic_proxy = dynamic_proxies[proxy_index] if proxy_index < len(dynamic_proxies) else ""
            if proxy_index < len(dynamic_proxies):
                proxy_index += 1
            register_dynamic_proxy = payment_dynamic_proxy if use_payment_proxy_for_register else extract_dynamic_proxy
            proxy_assignments.append((account, register_dynamic_proxy, extract_dynamic_proxy))
        threading.Thread(target=self._refetch_links_batch_worker, args=(proxy_assignments, mode, headless, local_proxy, use_payment_proxy_for_register), daemon=True).start()

    def start_authorize_selected(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中邮箱，可多选")
            return
        accounts = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if 0 <= index < len(self.accounts):
                accounts.append(self.accounts[index])
        if not accounts:
            return
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        self.running = True
        self.stop_event.clear()
        self.save_state()
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        dynamic_proxies = self._read_dynamic_proxies()
        threading.Thread(target=self._authorize_accounts_worker, args=(accounts, local_proxy, dynamic_proxies), daemon=True).start()

    def _authorize_accounts_worker(self, accounts: list[MailAccount], local_proxy: str, dynamic_proxies: list[str]) -> None:
        try:
            for account in accounts:
                if self.stop_event.is_set():
                    self.events.put(("log", "授权任务已手动停止"))
                    break
                dynamic_proxy = self._next_dynamic_proxy(dynamic_proxies)
                self._authorize_account_once(account, local_proxy, dynamic_proxy)
        finally:
            self.events.put(("done",))

    def _authorize_account_worker(self, account: MailAccount, local_proxy: str, dynamic_proxy: str) -> None:
        try:
            self._authorize_account_once(account, local_proxy, dynamic_proxy)
        finally:
            self.events.put(("done",))

    def _authorize_account_once(self, account: MailAccount, local_proxy: str, dynamic_proxy: str) -> None:
        try:
            self.events.put(("status", account.email, "授权中"))
            with ProxyChainServer(local_proxy, dynamic_proxy, lambda msg: self.events.put(("log", msg))) as chain:
                proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=dynamic_proxy, chain_url=chain.url)
                self.events.put(("log", f"[{account.email}] 授权使用代理: {proxy.label}"))
                flow = OpenAIJsonAuthFlow(account, lambda msg: self.events.put(("log", msg)), self._phone_provider, self._request_user_input, chain.url)
                record = flow.run()
            account.openai_rt = str(record.get("refresh_token") or "")
            if not account.openai_rt:
                raise RuntimeError("授权成功但未获取到 refresh_token")
            account.account_type = "plus"
            account.status = "已绑定手机号"
            self.events.put(("account-updated", account.email))
            self.events.put(("status", account.email, account.status))
            self.events.put(("log", f"[{account.email}] RT 获取成功，已标记为已绑定手机号"))
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 授权失败: {exc}"))
            self.events.put(("status", account.email, "授权失败"))

    def _request_user_input(self, prompt_type: str, email_addr: str, prompt: str) -> str:
        prompt_id = str(uuid.uuid4())
        result_queue: queue.Queue = queue.Queue(maxsize=1)
        self.pending_prompts[prompt_id] = result_queue
        self.events.put(("prompt", prompt_id, prompt_type, email_addr, prompt))
        return str(result_queue.get())

    def _phone_provider(self, action: str, email_addr: str, payload) -> dict | str:
        if action == "next":
            for phone in self.phones:
                if self._phone_is_frozen(phone):
                    if phone.status != "冻结":
                        phone.status = "冻结"
                        self.events.put(("phones-updated",))
                    continue
                if phone.status not in {"不可用", "冻结"}:
                    phone.status = "使用中"
                    self.events.put(("phones-updated",))
                    self.events.put(("log", f"[{email_addr}] 使用手机号: {phone.number}"))
                    for account in self.accounts:
                        if account.email.lower() == email_addr.lower():
                            account.auth_phone_number = phone.number
                            account.auth_phone_sms_url = phone.sms_url
                            self.events.put(("account-updated", email_addr))
                            break
                    return {"number": phone.number, "sms_url": phone.sms_url}
            return {}
        if action == "code":
            return self._wait_for_phone_code(str(payload.get("number") or ""), str(payload.get("sms_url") or ""))
        if action == "bad":
            number = str(payload.get("number") or "")
            error = str(payload.get("error") or "")
            for phone in self.phones:
                if phone.number == number:
                    phone.status = "不可用"
                    phone.last_error = error
                    self.events.put(("phones-updated",))
                    break
            return {}
        return {}

    def _wait_for_phone_code(self, number: str, sms_url: str, timeout: int = 180) -> str:
        started = time.time()
        last_text = ""
        while time.time() - started < timeout:
            try:
                response = requests.get(sms_url, timeout=20)
                text = response.text.strip()
                last_text = text[:300]
                code = self._extract_phone_code(text)
                if code:
                    for phone in self.phones:
                        if phone.number == number:
                            phone.receive_count += 1
                            phone.status = "冻结" if self._phone_is_frozen(phone) else "可用"
                            phone.last_code = code
                            phone.last_error = ""
                            self.events.put(("phones-updated",))
                            break
                    return code
            except Exception as exc:
                last_text = str(exc)
            time.sleep(5)
        raise RuntimeError(f"等待手机号 {number} 短信验证码超时，最后返回: {last_text}")

    def _extract_phone_code(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", str(text or ""))
        patterns = [
            r"OpenAI[^\d]{0,80}(\d{6})",
            r"验证代码[^\d]{0,20}(\d{6})",
            r"验证码[^\d]{0,20}(\d{6})",
            r"\b(\d{6})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.I)
            if match:
                return match.group(1)
        return ""

    def _start_worker(self, accounts: list[MailAccount]) -> None:
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        self.running = True
        self.stop_event.clear()
        self.save_state()
        mode = self.payment_mode.get()
        headless = bool(self.headless.get())
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        use_payment_proxy_for_register = bool(self.register_with_payment_proxy.get())
        dynamic_proxies = [] if use_payment_proxy_for_register else self._take_dynamic_proxies(len(accounts))
        payment_dynamic_proxy = self._peek_payment_dynamic_proxy()
        threading.Thread(target=self._run_accounts, args=(accounts, mode, headless, local_proxy, dynamic_proxies, payment_dynamic_proxy, use_payment_proxy_for_register), daemon=True).start()

    def _read_dynamic_proxies(self) -> list[str]:
        lines = [line.strip() for line in self.proxy_text.get("1.0", END).splitlines() if line.strip()]
        return [normalize_proxy_url(line) for line in lines]

    def _read_payment_dynamic_proxies(self) -> list[str]:
        lines = [line.strip() for line in self.payment_dynamic_proxy_text.get("1.0", END).splitlines() if line.strip()]
        return [normalize_proxy_url(line) for line in lines]

    def _take_dynamic_proxies(self, count: int) -> list[str]:
        lines = [line.strip() for line in self.proxy_text.get("1.0", END).splitlines() if line.strip()]
        if count <= 0 or not lines:
            return []
        taken = lines[:count]
        rest = "\n".join(lines[count:])
        self.proxy_text.delete("1.0", END)
        if rest:
            self.proxy_text.insert(END, rest)
        self.save_state()
        proxies = [normalize_proxy_url(line) for line in taken]
        self.log(f"注册/提取长链动态代理已取用并移除 {len(proxies)} 个")
        return proxies

    def _peek_payment_dynamic_proxy(self) -> str:
        proxies = self._read_payment_dynamic_proxies()
        return proxies[0] if proxies else ""

    def _take_payment_dynamic_proxy(self) -> str:
        lines = [line.strip() for line in self.payment_dynamic_proxy_text.get("1.0", END).splitlines() if line.strip()]
        if not lines:
            return ""
        value = normalize_proxy_url(lines[0])
        rest = "\n".join(lines[1:])
        self.payment_dynamic_proxy_text.delete("1.0", END)
        if rest:
            self.payment_dynamic_proxy_text.insert(END, rest)
        self.payment_dynamic_proxy.set(rest)
        self.save_state()
        self.log(f"支付链接动态代理已取用并移除: {value}")
        return value

    def _take_paypal_phone_config(self) -> tuple[str, str] | None:
        lines = [line.strip() for line in self.paypal_phone_pool_text.get("1.0", END).splitlines() if line.strip()]
        if lines:
            line = lines[self.paypal_phone_pool_index % len(lines)]
            try:
                phone = parse_paypal_phone_line(line)
            except Exception as exc:
                messagebox.showwarning(APP_TITLE, f"PP手机号+接码池第 {self.paypal_phone_pool_index % len(lines) + 1} 行格式错误: {exc}")
                return None
            self.paypal_phone_pool_index += 1
            self.paypal_phone_pool.set("\n".join(lines))
            self.save_state()
            self.log(f"PP手机号+接码已轮询取用: {phone.number}")
            return phone.number, phone.sms_url
        return self.paypal_phone.get().strip(), self.paypal_sms_url.get().strip()

    def _next_dynamic_proxy(self, dynamic_proxies: list[str]) -> str:
        if not dynamic_proxies:
            return ""
        value = dynamic_proxies[self.dynamic_proxy_index % len(dynamic_proxies)]
        self.dynamic_proxy_index += 1
        return value

    def _run_accounts(self, accounts: list[MailAccount], mode: str, headless: bool, local_proxy: str, dynamic_proxies: list[str], payment_dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        try:
            concurrency = len(dynamic_proxies) if dynamic_proxies and not use_payment_proxy_for_register else 1
            concurrency = max(1, concurrency)
            if concurrency > 1:
                self.events.put(("log", f"注册批量并发窗口数: {concurrency}（按动态代理池每个窗口一个代理）"))
            proxy_index = 0
            for start in range(0, len(accounts), concurrency):
                if self.stop_event.is_set():
                    self.events.put(("log", "任务已手动停止"))
                    break
                threads = []
                for account in accounts[start:start + concurrency]:
                    extract_dynamic_proxy = dynamic_proxies[proxy_index] if proxy_index < len(dynamic_proxies) else ""
                    if proxy_index < len(dynamic_proxies):
                        proxy_index += 1
                    register_dynamic_proxy = payment_dynamic_proxy if use_payment_proxy_for_register else extract_dynamic_proxy
                    thread = threading.Thread(
                        target=self._run_account_thread,
                        args=(account, mode, headless, local_proxy, register_dynamic_proxy, extract_dynamic_proxy, use_payment_proxy_for_register),
                        daemon=True,
                    )
                    thread.start()
                    threads.append(thread)
                for thread in threads:
                    thread.join()
        finally:
            self.events.put(("done",))

    def _run_account_thread(self, account: MailAccount, mode: str, headless: bool, local_proxy: str, register_dynamic_proxy: str, extract_dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        if self.stop_event.is_set():
            return
        self.events.put(("status", account.email, "处理中"))
        try:
            with ProxyChainServer(local_proxy, register_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as register_chain:
                register_proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=register_dynamic_proxy, chain_url=register_chain.url)
                extract_proxy = register_proxy
                register_source = "支付链接动态代理" if use_payment_proxy_for_register else "注册动态代理池"
                self.events.put(("log", f"[{account.email}] 注册使用代理({register_source}): {register_proxy.label}"))
                self.events.put(("log", f"[{account.email}] 提取长链接复用注册代理: {extract_proxy.label}"))
                worker = OpenAIRegisterPayLinkWorker(account, mode, headless, register_proxy, extract_proxy, lambda msg: self.events.put(("log", msg)))
                link = worker.run()
            self.events.put(("account-updated", account.email))
            self.events.put(("result", account.email, link))
            self.events.put(("status", account.email, "成功"))
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 失败: {exc}"))
            self.events.put(("status", account.email, "失败"))

    def _refetch_account_once(self, account: MailAccount, mode: str, headless: bool, local_proxy: str, register_dynamic_proxy: str, extract_dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        self.events.put(("status", account.email, "重新获取中"))
        with ProxyChainServer(local_proxy, register_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as register_chain, \
             ProxyChainServer(local_proxy, extract_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as extract_chain:
            register_proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=register_dynamic_proxy, chain_url=register_chain.url)
            extract_proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=extract_dynamic_proxy, chain_url=extract_chain.url)
            register_source = "支付链接动态代理" if use_payment_proxy_for_register else "注册动态代理池"
            self.events.put(("log", f"[{account.email}] 重新获取长链接登录使用代理({register_source}): {register_proxy.label}"))
            self.events.put(("log", f"[{account.email}] 重新获取长链接提取使用代理: {extract_proxy.label}"))
            worker = OpenAIRegisterPayLinkWorker(account, mode, headless, register_proxy, extract_proxy, lambda msg: self.events.put(("log", msg)))
            link = worker.relink()
        self.events.put(("result", account.email, link))
        self.events.put(("status", account.email, "成功"))

    def _refetch_link_worker(self, account: MailAccount, mode: str, headless: bool, local_proxy: str, dynamic_proxies: list[str], payment_dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        try:
            extract_dynamic_proxy = self._next_dynamic_proxy(dynamic_proxies)
            register_dynamic_proxy = payment_dynamic_proxy if use_payment_proxy_for_register else extract_dynamic_proxy
            self._refetch_account_once(account, mode, headless, local_proxy, register_dynamic_proxy, extract_dynamic_proxy, use_payment_proxy_for_register)
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 重新获取长链接失败: {exc}"))
            self.events.put(("status", account.email, "失败"))
        finally:
            self.events.put(("done",))

    def _refetch_links_batch_worker(self, proxy_assignments: list[tuple[MailAccount, str, str]], mode: str, headless: bool, local_proxy: str, use_payment_proxy_for_register: bool) -> None:
        threads = []
        try:
            for account, register_dynamic_proxy, extract_dynamic_proxy in proxy_assignments:
                if self.stop_event.is_set():
                    self.events.put(("log", "任务已手动停止"))
                    break
                thread = threading.Thread(
                    target=self._refetch_account_thread,
                    args=(account, mode, headless, local_proxy, register_dynamic_proxy, extract_dynamic_proxy, use_payment_proxy_for_register),
                    daemon=True,
                )
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
        finally:
            self.events.put(("done",))

    def _refetch_account_thread(self, account: MailAccount, mode: str, headless: bool, local_proxy: str, register_dynamic_proxy: str, extract_dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        try:
            self._refetch_account_once(account, mode, headless, local_proxy, register_dynamic_proxy, extract_dynamic_proxy, use_payment_proxy_for_register)
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 重新获取长链接失败: {exc}"))
            self.events.put(("status", account.email, "失败"))

    def _open_payment_link_worker(self, link: str, local_proxy: str, dynamic_proxy: str, extension_dir: str, paypal_phone: str, paypal_card: str, paypal_sms_url: str, email_addr: str = "") -> None:
        profile_dir = ""
        context = None
        try:
            extension_path = Path(extension_dir).resolve() if extension_dir else None
            if extension_path and not extension_path.is_dir():
                raise RuntimeError(f"扩展目录不存在: {extension_path}")
            if extension_path and not (extension_path / "manifest.json").exists():
                raise RuntimeError(f"扩展目录缺少 manifest.json: {extension_path}")

            with ProxyChainServer(local_proxy, dynamic_proxy, lambda msg: self.events.put(("log", msg))) as chain:
                proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=dynamic_proxy, chain_url=chain.url)
                self.events.put(("log", f"打开支付链接使用代理: {proxy.label}"))
                fingerprint = generate_fingerprint()
                profile_dir = tempfile.mkdtemp(prefix="paylink-profile-")
                args = [
                    "--disable-blink-features=AutomationControlled",
                    f"--window-size={fingerprint.outer_width},{fingerprint.outer_height}",
                    "--disable-features=IsolateOrigins,site-per-process",
                ]
                if extension_path:
                    ext = str(extension_path)
                    args.extend([
                        f"--disable-extensions-except={ext}",
                        f"--load-extension={ext}",
                    ])
                    self.events.put(("log", f"已加载支付链接扩展目录: {ext}"))
                with sync_playwright() as p:
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=profile_dir,
                        headless=False,
                        args=args,
                        proxy={"server": chain.url} if chain.url else None,
                        user_agent=fingerprint.user_agent,
                        locale=fingerprint.locale,
                        timezone_id=fingerprint.timezone,
                        viewport={"width": fingerprint.viewport_width, "height": fingerprint.viewport_height},
                        screen={"width": fingerprint.screen_width, "height": fingerprint.screen_height},
                        device_scale_factor=fingerprint.device_scale_factor,
                        is_mobile=False,
                        has_touch=False,
                    )
                    self.payment_context = context
                    self.payment_contexts.add(context)
                    context.clear_cookies()
                    if paypal_card or paypal_sms_url:
                        paypal_payload = json.dumps({"phone": paypal_phone, "card": paypal_card, "smsUrl": paypal_sms_url}, ensure_ascii=False)
                        context.add_init_script(
                            """(() => {
                                const data = __PAYPAL_PAYLOAD__;
                                const phone = data.phone || '';
                                const card = data.card || '';
                                const smsUrl = data.smsUrl || '';
                                try {
                                    localStorage.setItem('opencode_paypal_phone', phone);
                                    localStorage.setItem('opencode_paypal_card', card);
                                    localStorage.setItem('ppaf_phone', phone);
                                    localStorage.setItem('ppaf_card', card);
                                    localStorage.setItem('opencode_paypal_sms_url', smsUrl);
                                    localStorage.setItem('ppaf_sms_url', smsUrl);
                                } catch (_) {}
                            })();""".replace("__PAYPAL_PAYLOAD__", paypal_payload)
                        )
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(link, wait_until="domcontentloaded", timeout=90000)
                    fill_attempts: set[str] = set()
                    fill_ready_at: dict[str, float] = {}
                    success_ready_at: dict[int, float] = {}
                    cpay_click_ready_at: dict[int, float] = {}
                    cpay_clicked: set[int] = set()
                    cpay_clicked_url: dict[int, str] = {}
                    self.events.put(("log", "支付链接已在支持扩展的临时 Chromium 窗口打开；关闭窗口后任务结束"))
                    while not self.stop_event.is_set() and context.pages:
                        for current_page in list(context.pages):
                            if current_page.is_closed():
                                continue
                            if "pay.openai.com/c/pay/" in current_page.url:
                                page_id = id(current_page)
                                if page_id not in cpay_clicked:
                                    if page_id not in cpay_click_ready_at:
                                        cpay_click_ready_at[page_id] = time.time() + 5
                                        self.events.put(("log", f"检测到 OpenAI 支付确认页，等待 5 秒后点击确认按钮: {current_page.url[:80]}"))
                                    if time.time() >= cpay_click_ready_at[page_id]:
                                        if self._click_openai_pay_confirm(current_page):
                                            cpay_clicked.add(page_id)
                                            cpay_clicked_url[page_id] = current_page.url
                                            self.events.put(("log", f"已点击 OpenAI 支付确认按钮，等待后续跳转: {current_page.url[:80]}"))
                                        else:
                                            cpay_click_ready_at[page_id] = time.time() + 1
                                    continue
                                if current_page.url == cpay_clicked_url.get(page_id, ""):
                                    continue
                                if page_id not in success_ready_at:
                                    success_ready_at[page_id] = time.time() + 5
                                    self.events.put(("log", f"检测到支付确认后跳转页，等待 5 秒后关闭并标记 Plus: {current_page.url[:80]}"))
                                if time.time() >= success_ready_at[page_id]:
                                    if email_addr:
                                        self.events.put(("mark-plus", email_addr))
                                    try:
                                        current_page.close()
                                    except Exception:
                                        pass
                                    try:
                                        context.close()
                                    except Exception:
                                        pass
                                    return
                            if "pay.openai.com" in current_page.url or "paypal.com" in current_page.url:
                                key = f"{id(current_page)}:{current_page.url.split('?')[0]}"
                                if key not in fill_ready_at:
                                    fill_ready_at[key] = time.time() + 10
                                    self.events.put(("log", f"检测到支付页，等待 10 秒后自动填写: {current_page.url[:80]}"))
                                if time.time() < fill_ready_at[key]:
                                    continue
                                if key not in fill_attempts:
                                    if self._autofill_payment_extension(current_page, paypal_phone, paypal_card, paypal_sms_url):
                                        fill_attempts.add(key)
                        time.sleep(1)
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as exc:
            self.events.put(("log", f"打开支付链接失败: {exc}"))
        finally:
            if profile_dir:
                self._cleanup_profile_dir(profile_dir)
            if context in self.payment_contexts:
                self.payment_contexts.discard(context)
            self.payment_context = None
            self.events.put(("open-link-done",))

    def _cleanup_profile_dir(self, profile_dir: str) -> None:
        for attempt in range(8):
            try:
                shutil.rmtree(profile_dir, ignore_errors=False)
                return
            except FileNotFoundError:
                return
            except PermissionError:
                time.sleep(0.5 + attempt * 0.25)
            except OSError:
                time.sleep(0.5 + attempt * 0.25)
        self.events.put(("log", f"临时支付浏览器目录清理失败，已忽略: {profile_dir}"))

    def _click_openai_pay_confirm(self, page) -> bool:
        try:
            return bool(page.evaluate(
                """() => {
                    const visible = el => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                    };
                    const buttons = Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"]'));
                    const target = buttons.find(el => {
                        if (!visible(el) || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
                        const text = `${el.textContent || ''} ${el.getAttribute('value') || ''} ${el.getAttribute('aria-label') || ''}`.trim().toLowerCase();
                        if (/cancel|back|return|キャンセル|戻る/.test(text)) return false;
                        return /subscribe|confirm|continue|pay|complete|同意|続行|確認|支払|購入|登録/.test(text);
                    });
                    if (!target) return false;
                    target.scrollIntoView({ block: 'center' });
                    target.click();
                    return true;
                }"""
            ))
        except Exception:
            return False

    def _autofill_payment_extension(self, page, paypal_phone: str, paypal_card: str, paypal_sms_url: str) -> bool:
        if not paypal_card:
            return False
        try:
            if "pay.openai.com" in page.url:
                parsed = parse_paypal_address_payload(paypal_card)
                if parsed.get("country") == "JP":
                    parsed["state_en"] = normalize_jp_prefecture_name(parsed.get("state", ""))
                    direct_result = page.evaluate(
                        """async (payload) => {
                            const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
                            const visible = el => {
                                if (!el) return false;
                                const r = el.getBoundingClientRect();
                                const s = getComputedStyle(el);
                                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                            };
                            const setValue = (el, value) => {
                                if (!el) return false;
                                const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                                const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                                if (desc && desc.set) desc.set.call(el, value); else el.value = value;
                                try { el.setAttribute('value', value); } catch (_) {}
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                el.dispatchEvent(new Event('blur', { bubbles: true }));
                                return true;
                            };
                            const waitFor = async (fn, timeout = 12000) => {
                                const start = Date.now();
                                while (Date.now() - start < timeout) {
                                    const value = fn();
                                    if (value) return value;
                                    await sleep(300);
                                }
                                return null;
                            };
                            const paypalBtn = Array.from(document.querySelectorAll('button, [role="button"], label')).find(el => visible(el) && /paypal/i.test((el.textContent || '').trim()));
                            if (paypalBtn) {
                                paypalBtn.click();
                                await sleep(1200);
                            }
                            const selectCountry = async () => {
                                const select = await waitFor(() => document.querySelector('select[name="billingCountry"]'));
                                if (!select) return false;
                                if ((select.value || '').toUpperCase() !== 'JP') {
                                    setValue(select, 'JP');
                                    await sleep(1200);
                                }
                                return true;
                            };
                            const manualBtn = Array.from(document.querySelectorAll('button')).find(el => visible(el) && /enter address manually|手动输入地址/i.test((el.textContent || '').trim()));
                            if (manualBtn) {
                                manualBtn.click();
                                await sleep(1000);
                            }
                            const selectPrefecture = async () => {
                                const select = await waitFor(() => document.querySelector('select[name="billingAdministrativeArea"]'));
                                if (!select) return false;
                                for (const opt of Array.from(select.options)) {
                                    const text = (opt.textContent || '').trim();
                                    if (text.includes(payload.state) || (payload.state_en && text.includes(payload.state_en))) {
                                        select.value = opt.value;
                                        select.dispatchEvent(new Event('change', { bubbles: true }));
                                        await sleep(1000);
                                        return true;
                                    }
                                }
                                return false;
                            };
                            if (!(await selectCountry())) return { ok: false, stage: 'country' };
                            const city = await waitFor(() => document.querySelector('input[name="billingLocality"]') || document.querySelector('input[placeholder="City"]'));
                            const line1 = await waitFor(() => document.querySelector('input[name="billingAddressLine1"]') || document.querySelector('input[placeholder="Address"]'));
                            if (city) setValue(city, payload.city || '');
                            if (line1) setValue(line1, payload.line1 || '');
                            if (!(await selectPrefecture())) return { ok: false, stage: 'prefecture' };
                            const postal = await waitFor(() => document.getElementById('billingPostalCode') || document.querySelector('input[name="billingPostalCode"]'));
                            if (postal) {
                                setValue(postal, payload.postal || '');
                                await sleep(500);
                                if ((postal.value || '').replace(/\D/g, '') !== String(payload.postal || '').replace(/\D/g, '')) {
                                    setValue(postal, `${String(payload.postal || '').slice(0, 3)}-${String(payload.postal || '').slice(3)}`);
                                    await sleep(500);
                                }
                                if ((postal.value || '').replace(/\D/g, '') !== String(payload.postal || '').replace(/\D/g, '')) {
                                    setValue(postal, payload.postal || '');
                                    await sleep(500);
                                }
                                if ((postal.value || '').replace(/\D/g, '') !== String(payload.postal || '').replace(/\D/g, '')) {
                                    return { ok: false, stage: 'postal' };
                                }
                            }
                            return { ok: true, stage: 'ready' };
                        }""",
                        parsed,
                    )
                    if isinstance(direct_result, dict) and direct_result.get("ok"):
                        self.events.put(("log", f"已直接填充日本支付表单: {page.url[:80]}"))
                        return True
                    self.events.put(("log", f"日本支付表单直接填充未完成，阶段={direct_result.get('stage') if isinstance(direct_result, dict) else 'unknown'}"))
            result = page.evaluate(
                """async ({phone, card, smsUrl}) => {
                    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
                    const setValue = (el, value) => {
                        if (!el) return false;
                        const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                        const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                        if (desc && desc.set) desc.set.call(el, value); else el.value = value;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    };
                    const waitFor = async selector => {
                        for (let i = 0; i < 12; i++) {
                            const el = document.querySelector(selector);
                            if (el) return el;
                            await sleep(500);
                        }
                        return null;
                    };
                    let filled = false;
                    try { localStorage.setItem('ppaf_phone', phone); localStorage.setItem('ppaf_card', card); localStorage.setItem('ppaf_sms_url', smsUrl || ''); } catch (_) {}
                    try { chrome.storage.local.set({ lastCardInput: card, lastPhone: phone, paypalSmsUrl: smsUrl || '', lastCardSavedAt: Date.now() }); } catch (_) {}
                    const stripeBtn = document.querySelector('#stripe-autofill-btn');
                    if (stripeBtn) {
                        stripeBtn.click();
                        const input = await waitFor('#saf-input');
                        const ok = await waitFor('#saf-ok');
                        if (input && ok) {
                            setValue(input, card);
                            ok.click();
                            filled = true;
                        }
                    }
                    const paypalBtn = document.querySelector('#ppaf-btn');
                    if (paypalBtn) {
                        paypalBtn.click();
                        const phoneInput = await waitFor('#ppaf-phone');
                        const cardInput = await waitFor('#ppaf-card');
                        const fillBtn = await waitFor('#ppaf-fill');
                        if (phoneInput && cardInput && fillBtn) {
                            setValue(phoneInput, phone);
                            setValue(cardInput, card);
                            fillBtn.click();
                            filled = true;
                        }
                    }
                    return filled;
                }""",
                {"phone": paypal_phone, "card": paypal_card, "smsUrl": paypal_sms_url},
            )
            if result:
                self.events.put(("log", f"已自动填入支付扩展资料: {page.url[:80]}"))
                return True
            self.events.put(("log", f"未找到支付扩展面板按钮，稍后重试: {page.url[:80]}"))
        except Exception:
            pass
        return False

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    self.log(event[1])
                elif kind == "status":
                    self._set_account_status(event[1], event[2])
                elif kind == "result":
                    self.results[event[1]] = event[2]
                    self.link_var.set(event[2])
                    self._render_results()
                    self._select_account_by_email(event[1])
                    self.save_state()
                elif kind == "account-updated":
                    self._render_accounts()
                    self.save_state()
                elif kind == "phones-updated":
                    self._render_phones()
                    self.save_state()
                elif kind == "phone-code-popup":
                    number = event[1]
                    code = event[2]
                    if code:
                        messagebox.showinfo(APP_TITLE, f"{number}\n验证码: {code}")
                    else:
                        messagebox.showwarning(APP_TITLE, f"{number}\n未读取到验证码")
                elif kind == "done":
                    self.running = False
                    self.stop_event.clear()
                    self.save_state()
                    self.log("任务结束")
                elif kind == "open-link-done":
                    self.open_payment_window_count = max(0, self.open_payment_window_count - 1)
                    self.opening_payment_link = self.open_payment_window_count > 0
                    self.stop_event.clear()
                    self.log("支付链接窗口任务结束")
                elif kind == "mark-plus":
                    self._mark_account_plus(event[1])
                    self.save_state()
                    self.log(f"[{event[1]}] 已标记为 Plus")
                elif kind == "prompt":
                    self._handle_prompt_event(event[1], event[2], event[3], event[4])
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _handle_prompt_event(self, prompt_id: str, prompt_type: str, email_addr: str, prompt: str) -> None:
        title = "输入手机号" if prompt_type == "phone" else "输入短信验证码"
        value = simpledialog.askstring(title, f"{email_addr}\n{prompt}", parent=self.root)
        result_queue = self.pending_prompts.pop(prompt_id, None)
        if result_queue:
            result_queue.put(value or "")

    def _render_accounts(self) -> None:
        for item in self.account_list.get_children():
            self.account_list.delete(item)
        for index, account in enumerate(self.accounts):
            status = account.status or ("成功" if account.email in self.results else "待处理")
            self.account_list.insert("", END, iid=str(index), values=(account.email, account.account_type, status))

    def _render_phones(self) -> None:
        for item in self.phone_list.get_children():
            self.phone_list.delete(item)
        for index, phone in enumerate(self.phones):
            if self._phone_is_frozen(phone) and phone.status not in {"不可用", "冻结"}:
                phone.status = "冻结"
            self.phone_list.insert("", END, iid=str(index), values=(phone.number, phone.receive_count, phone.status, phone.last_code))

    def _render_payment_cards(self) -> None:
        for item in self.payment_card_list.get_children():
            self.payment_card_list.delete(item)
        for index, card in enumerate(self.payment_cards):
            self.payment_card_list.insert("", END, iid=str(index), values=(card.card, f"{card.year}/{card.month}", card.cvv, card.status))

    def _set_account_status(self, email_addr: str, status: str) -> None:
        for index, account in enumerate(self.accounts):
            if account.email.lower() == email_addr.lower():
                account.status = status
                self.account_list.set(str(index), "status", status)
                return

    def _mark_account_plus(self, email_addr: str) -> None:
        for index, account in enumerate(self.accounts):
            if account.email.lower() == email_addr.lower():
                account.account_type = "plus"
                account.status = "Plus"
                self.account_list.set(str(index), "type", "plus")
                self.account_list.set(str(index), "status", "Plus")
                return

    def _render_results(self) -> None:
        self._show_selected_account_link()

    def _show_selected_result(self) -> None:
        self._show_selected_account_link()

    def _show_selected_account_link(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            return
        index = int(selected[0])
        if index < 0 or index >= len(self.accounts):
            return
        self.link_var.set(self.results.get(self.accounts[index].email, ""))

    def _select_account_by_email(self, email_addr: str) -> None:
        for index, account in enumerate(self.accounts):
            if account.email.lower() == email_addr.lower():
                iid = str(index)
                try:
                    self.account_list.selection_set(iid)
                    self.account_list.see(iid)
                except Exception:
                    pass
                return

    def copy_link(self) -> None:
        link = self.link_var.get().strip()
        if not link:
            messagebox.showwarning(APP_TITLE, "暂无长链接")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(link)
        self.log("长链接已复制到剪贴板")

    def _preview_and_save_text(self, title: str, text: str, default_extension: str = ".txt", filetypes=None) -> str:
        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("760x520")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="请先核对导出内容，可复制；点击“确定导出”后选择保存文件。").pack(anchor="w", padx=10, pady=(10, 6))
        preview = ScrolledText(dialog, height=24)
        preview.pack(fill=BOTH, expand=True, padx=10, pady=(0, 8))
        preview.insert(END, text)

        result = {"path": ""}

        def copy_preview() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(preview.get("1.0", END).rstrip("\n"))
            self.log("导出预览内容已复制到剪贴板")

        def confirm_export() -> None:
            path = filedialog.asksaveasfilename(
                parent=dialog,
                title=title,
                defaultextension=default_extension,
                filetypes=filetypes or [("Text", "*.txt"), ("All", "*.*")],
            )
            if not path:
                return
            result["path"] = path
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill=X, padx=10, pady=(0, 10))
        ttk.Button(buttons, text="复制内容", command=copy_preview).pack(side=LEFT)
        ttk.Button(buttons, text="取消", command=cancel).pack(side=RIGHT)
        ttk.Button(buttons, text="确定导出", command=confirm_export).pack(side=RIGHT, padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(dialog)
        return result["path"]

    def export_authorized(self) -> None:
        accounts = self._selected_authorized_accounts()
        if not accounts:
            return
        prefix = self.export_name_prefix.get().strip()
        text = "\n".join(account_export_line(account, prefix) for account in accounts) + "\n"
        path = self._preview_and_save_text("导出已授权邮箱", text)
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self.log(f"已导出 {len(accounts)} 个已授权邮箱 TXT: {path}")

    def export_authorized_email_rt(self) -> None:
        accounts = self._selected_authorized_accounts()
        if not accounts:
            return
        text = "\n".join(f"{account.email}----{account.openai_rt}" for account in accounts) + "\n"
        path = self._preview_and_save_text("导出邮箱----RT", text)
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self.log(f"已导出 {len(accounts)} 个邮箱----RT TXT: {path}")

    def _selected_authorized_accounts(self) -> list[MailAccount]:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先在左侧选择要导出的已授权邮箱，可多选")
            return []
        selected_accounts = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if 0 <= index < len(self.accounts):
                selected_accounts.append(self.accounts[index])
        accounts = [account for account in selected_accounts if account.openai_rt]
        if not accounts:
            messagebox.showwarning(APP_TITLE, "选中的邮箱里没有已授权 RT")
        return accounts

    def export_sub2api(self) -> None:
        accounts = self._selected_authorized_accounts()
        if not accounts:
            return
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        path = filedialog.asksaveasfilename(
            title="导出 sub2api JSON",
            defaultextension=".sub2api.json",
            filetypes=[("sub2api JSON", "*.sub2api.json"), ("JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            return
        self.running = True
        self.stop_event.clear()
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        dynamic_proxy = self._next_dynamic_proxy(self._read_dynamic_proxies())
        threading.Thread(target=self._export_sub2api_worker, args=(accounts, path, local_proxy, dynamic_proxy, self.export_name_prefix.get().strip()), daemon=True).start()

    def _export_sub2api_worker(self, accounts: list[MailAccount], path: str, local_proxy: str, dynamic_proxy: str, prefix: str) -> None:
        try:
            records = []
            with ProxyChainServer(local_proxy, dynamic_proxy, lambda msg: self.events.put(("log", msg))) as chain:
                proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=dynamic_proxy, chain_url=chain.url)
                self.events.put(("log", f"导出 sub2api 使用代理: {proxy.label}"))
                for account in accounts:
                    if self.stop_event.is_set():
                        break
                    token_payload = refresh_openai_access_token(account.openai_rt, chain.url)
                    refreshed_rt = str(token_payload.get("refresh_token") or "")
                    if refreshed_rt.startswith("rt_"):
                        account.openai_rt = refreshed_rt
                    token_payload["refresh_token"] = account.openai_rt
                    export_email = f"({prefix}){account.email}" if prefix else account.email
                    record = openai_record_from_refresh_payload(export_email, token_payload)
                    records.append(record)
                    self.events.put(("log", f"已刷新 sub2api token: {account.email}"))
            if not records:
                raise RuntimeError("没有可导出的 sub2api 记录")
            Path(path).write_text(json.dumps(build_sub2api_export(records), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.events.put(("log", f"已导出 {len(records)} 个账号 sub2api JSON: {path}"))
            self.events.put(("account-updated", ""))
        except Exception as exc:
            self.events.put(("log", f"导出 sub2api 失败: {exc}"))
        finally:
            self.events.put(("done",))

    def open_link(self) -> None:
        link = self.link_var.get().strip()
        if not link:
            messagebox.showwarning(APP_TITLE, "暂无长链接")
            return
        self.stop_event.clear()
        self.save_state()
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        extension_dir = self.payment_extension_dir.get().strip()
        paypal_config = self._take_paypal_phone_config()
        if paypal_config is None:
            self.opening_payment_link = self.open_payment_window_count > 0
            return
        paypal_phone, paypal_sms_url = paypal_config
        paypal_card = self._next_paypal_card_text()
        if paypal_card is None:
            self.opening_payment_link = self.open_payment_window_count > 0
            return
        dynamic_proxy = self._take_payment_dynamic_proxy()
        email_addr = ""
        selected = self.account_list.selection()
        if selected:
            try:
                index = int(selected[0])
                if 0 <= index < len(self.accounts) and self.results.get(self.accounts[index].email, "").strip() == link:
                    email_addr = self.accounts[index].email
            except Exception:
                email_addr = ""
        self.open_payment_window_count += 1
        self.opening_payment_link = True
        threading.Thread(target=self._open_payment_link_worker, args=(link, local_proxy, dynamic_proxy, extension_dir, paypal_phone, paypal_card, paypal_sms_url, email_addr), daemon=True).start()

    def open_selected_links(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中邮箱")
            return
        links = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if 0 <= index < len(self.accounts):
                account = self.accounts[index]
                link = self.results.get(account.email, "").strip()
                if link:
                    links.append((account.email, link))
        if not links:
            messagebox.showwarning(APP_TITLE, "选中的邮箱里没有可打开的长链接")
            return
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        extension_dir = self.payment_extension_dir.get().strip()
        started = 0
        for email_addr, link in links:
            paypal_config = self._take_paypal_phone_config()
            if paypal_config is None:
                break
            paypal_phone, paypal_sms_url = paypal_config
            paypal_card = self._next_paypal_card_text()
            if paypal_card is None:
                break
            dynamic_proxy = self._take_payment_dynamic_proxy()
            threading.Thread(target=self._open_payment_link_worker, args=(link, local_proxy, dynamic_proxy, extension_dir, paypal_phone, paypal_card, paypal_sms_url, email_addr), daemon=True).start()
            self.log(f"[{email_addr}] 已启动独立支付窗口")
            started += 1
        if started:
            self.open_payment_window_count += started
            self.opening_payment_link = True
            self.stop_event.clear()
            self.save_state()

    def _next_paypal_card_text(self) -> str | None:
        base_card = self.paypal_card.get().strip()
        if not base_card:
            return ""
        for card in self.payment_cards:
            if card.status == "未用":
                try:
                    value = replace_paypal_card_head(base_card, card)
                except Exception as exc:
                    messagebox.showwarning(APP_TITLE, str(exc))
                    return None
                card.status = "已用"
                self._render_payment_cards()
                self.save_state()
                self.log(f"本次支付使用卡: {card.card}")
                return value
        if self.payment_cards:
            messagebox.showwarning(APP_TITLE, "支付卡池没有未用卡，请导入新卡或重置卡池")
            return None
        return base_card

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)


def main() -> None:
    root = Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
