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
from urllib.parse import parse_qs, parse_qsl, quote, urlencode, unquote, urljoin, urlparse, urlsplit, urlunsplit

import imaplib
import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from curl_cffi.requests import Session as CurlCffiSession  # type: ignore
except ImportError:
    CurlCffiSession = None  # type: ignore


APP_TITLE = "OpenAI 注册 + Session 获取"
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
AUTH_PHONE_OTP_SEND_URL = f"{AUTH_BASE_URL}/api/accounts/phone-otp/send"
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
DEFAULT_STRIPE_PK = "pk_live_51HOrSwC6h1nxGoI3lTAgRjYVrz4dU3fVOabyCcKR3pbEJguCVAlqCxdxCUvoRh1XWwRacViovU3kLKvpkjh7IqkW00iXQsjo3n"
STRIPE_VERSION_FULL = "2025-03-31.basil; checkout_server_update_beta=v1; checkout_manual_approval_preview=v1"
DEFAULT_STRIPE_RUNTIME_VERSION = "6f8494a281"
PAY_LONG_LINK_TIMEOUT = 30


class BRProxiesExhausted(Exception):
    pass


class TurnstileRequired(Exception):
    pass


IMAP_SCOPE = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
TOKEN_ENDPOINTS = [
    {"name": "LIVE", "url": "https://login.live.com/oauth20_token.srf", "scope": ""},
    {"name": "LIVE+scope", "url": "https://login.live.com/oauth20_token.srf", "scope": IMAP_SCOPE},
    {"name": "V1-COMMON", "url": "https://login.microsoftonline.com/common/oauth2/token", "scope": "", "resource": "https://outlook.office.com/"},
    {"name": "V1-CONSUMERS", "url": "https://login.microsoftonline.com/consumers/oauth2/token", "scope": "", "resource": "https://outlook.office.com/"},
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
    "GoPay 长链接 ID/IDR": {"country": "ID", "currency": "IDR"},
    "PayPal 长链接 US/USD": {"country": "US", "currency": "USD"},
    "PayPal 长链接 US/USD (BR双代理)": {"country": "US", "currency": "USD", "br_stripe_proxy_split": True},
    "试用短链 PayPal US/USD": {"country": "US", "currency": "USD", "trial_short_link": True},
    "PayPal 长链接 FR/EUR": {"country": "FR", "currency": "EUR"},
    "Apple Pay 支付页 US/USD": {"country": "US", "currency": "USD", "apple_pay_hosted": True},
    "Apple Pay 支付页 JP/JPY": {"country": "JP", "currency": "JPY", "apple_pay_hosted": True},
}
PAYMENT_MODE_ALIASES = {name.replace("长链接", "短链"): name for name in PAYMENT_MODES}
KEPT_REGISTER_BROWSER_SESSIONS = {}
TEAM_EMAIL_DOMAIN = "wishtoapp.edu.kg"
COUNTRY_CURRENCY = {
    "AT": "EUR", "AU": "AUD", "BE": "EUR", "BR": "BRL", "CA": "CAD", "CH": "CHF", "CZ": "CZK",
    "DE": "EUR", "DK": "DKK", "ES": "EUR", "FI": "EUR", "FR": "EUR", "GB": "GBP", "HK": "HKD",
    "ID": "IDR", "IE": "EUR", "IN": "INR", "IT": "EUR", "JP": "JPY", "KR": "KRW", "MX": "MXN",
    "MY": "MYR", "NL": "EUR", "NO": "NOK", "NZ": "NZD", "PH": "PHP", "PL": "PLN", "PT": "EUR",
    "SE": "SEK", "SG": "SGD", "TH": "THB", "TW": "TWD", "US": "USD", "VN": "VND",
}
OPENAI_SUPPORTED_COUNTRY_CODES = {
    "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR",
    "AM", "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BE",
    "BZ", "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR",
    "IO", "BN", "BG", "BF", "BI", "CV", "KH", "CM", "CA", "KY",
    "CF", "TD", "CL", "CX", "CC", "CO", "KM", "CG", "CK", "CR",
    "CI", "HR", "CW", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC",
    "SV", "GQ", "ER", "EE", "SZ", "FK", "FO", "FJ", "FI", "FR",
    "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR",
    "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT",
    "HM", "VA", "HN", "HU", "IS", "IN", "ID", "IQ", "IE", "IM",
    "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KW",
    "KG", "LA", "LV", "LB", "LS", "LR", "LI", "LT", "LU", "MG",
    "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT",
    "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM",
    "NA", "NR", "NP", "NL", "NC", "NZ", "NI", "NE", "NG", "NU",
    "NF", "MK", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG",
    "PE", "PH", "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RW",
    "BL", "SH", "KN", "LC", "MF", "PM", "VC", "WS", "SM", "ST",
    "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO",
    "ZA", "GS", "KR", "SS", "ES", "LK", "SR", "SJ", "SE", "CH",
    "TW", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR",
    "TM", "TC", "TV", "UG", "UA", "AE", "GB", "UM", "US", "UY",
    "UZ", "VU", "WF", "EH", "ZM",
}
EUR_COUNTRIES = {
    "AD", "AT", "BE", "CY", "EE", "FI", "FR", "DE", "GR", "HR",
    "IE", "IT", "LV", "LT", "LU", "MT", "MC", "ME", "NL", "PT",
    "SM", "SK", "SI", "ES",
}
COUNTRY_CURRENCY.update({country: "EUR" for country in EUR_COUNTRIES if country not in COUNTRY_CURRENCY})
COUNTRY_CURRENCY.update({
    "AE": "AED", "AR": "ARS", "BH": "BHD", "BM": "BMD", "BO": "BOB", "BQ": "USD",
    "CL": "CLP", "CO": "COP", "GU": "USD", "IL": "ILS", "PR": "USD", "TR": "TRY",
    "UA": "UAH", "UM": "USD", "ZA": "ZAR",
})
COUNTRY_PHONE_PREFIX = {
    "AU": "+61", "CA": "+1", "DE": "+49", "GB": "+44", "IE": "+353", "JP": "+81",
    "NZ": "+64", "SG": "+65", "TH": "+66", "US": "+1",
    "AD": "+376", "AE": "+971", "AL": "+355", "AR": "+54", "AT": "+43", "BE": "+32",
    "BG": "+359", "BH": "+973", "BM": "+1", "BO": "+591", "BR": "+55", "CH": "+41",
    "CL": "+56", "CO": "+57", "CR": "+506", "CY": "+357", "CZ": "+420", "DK": "+45",
    "EE": "+372", "ES": "+34", "FI": "+358", "FR": "+33", "GI": "+350", "GR": "+30",
    "HK": "+852", "HU": "+36", "ID": "+62", "IL": "+972", "IN": "+91", "IS": "+354",
    "IT": "+39", "KR": "+82", "KZ": "+7", "LI": "+423", "LT": "+370", "LU": "+352",
    "LV": "+371", "MC": "+377", "MD": "+373", "ME": "+382", "MK": "+389", "MT": "+356",
    "MX": "+52", "MY": "+60", "NL": "+31", "NO": "+47", "PH": "+63", "PL": "+48",
    "PT": "+351", "QA": "+974", "RO": "+40", "RS": "+381", "SA": "+966", "SE": "+46",
    "SI": "+386", "SK": "+421", "SM": "+378", "TR": "+90", "TW": "+886", "UA": "+380",
    "UY": "+598", "ZA": "+27",
}
US_BILLING_NAMES = [("James", "Smith"), ("John", "Brown"), ("Michael", "Johnson"), ("Robert", "Miller"), ("David", "Davis"), ("William", "Wilson")]
US_BILLING_STREETS = [
    ("3110 Sunset Boulevard", "Los Angeles", "CA", "90026"),
    ("1200 Market Street", "San Francisco", "CA", "94102"),
    ("500 Main Street", "Austin", "TX", "78701"),
    ("88 Broadway", "New York", "NY", "10007"),
    ("1200 Peachtree St", "Atlanta", "GA", "30309"),
]
DE_BILLING_NAMES = [("Lukas", "Schneider"), ("Felix", "Muller"), ("Jonas", "Weber"), ("Leon", "Fischer"), ("Marie", "Wagner"), ("Laura", "Becker"), ("Maximilian", "Hoffmann"), ("Paul", "Schulz"), ("Emma", "Koch"), ("Hannah", "Bauer"), ("Sophie", "Richter"), ("Noah", "Klein")]
DE_BILLING_STREETS = [
    ("Friedrichstrasse 123", "Berlin", "BE", "10117"),
    ("Leopoldstrasse 50", "Munich", "BY", "80802"),
    ("Zeil 85", "Frankfurt am Main", "HE", "60313"),
    ("Konigsallee 60", "Dusseldorf", "NW", "40212"),
    ("Moenckebergstrasse 7", "Hamburg", "HH", "20095"),
    ("Hohenzollernring 72", "Cologne", "NW", "50672"),
    ("Kaiserstrasse 44", "Stuttgart", "BW", "70173"),
    ("Kaufingerstrasse 15", "Munich", "BY", "80331"),
    ("Georgstrasse 24", "Hanover", "NI", "30159"),
    ("Prager Strasse 9", "Dresden", "SN", "01069"),
    ("Schadowstrasse 36", "Dusseldorf", "NW", "40212"),
    ("Breite Strasse 18", "Bonn", "NW", "53111"),
]
GB_BILLING_NAMES = [("Oliver", "Smith"), ("George", "Taylor"), ("Harry", "Brown"), ("Noah", "Wilson"), ("Jack", "Davies"), ("Arthur", "Evans"), ("Olivia", "Johnson"), ("Amelia", "Roberts"), ("Isla", "Walker"), ("Ava", "Thompson"), ("Mia", "White"), ("Grace", "Hughes")]
GB_BILLING_STREETS = [
    ("221B Baker Street", "London", "England", "NW1 6XE"),
    ("10 Downing Street", "London", "England", "SW1A 2AA"),
    ("45 Deansgate", "Manchester", "England", "M3 2AY"),
    ("18 Park Row", "Leeds", "England", "LS1 5JA"),
    ("77 Queen Street", "Cardiff", "Wales", "CF10 2GR"),
    ("9 Princes Street", "Edinburgh", "Scotland", "EH2 2ER"),
    ("33 Broad Street", "Birmingham", "England", "B1 2HF"),
    ("14 Castle Street", "Liverpool", "England", "L2 0NE"),
    ("52 College Green", "Bristol", "England", "BS1 5SH"),
    ("6 Royal Avenue", "Belfast", "Northern Ireland", "BT1 1DA"),
]
AU_BILLING_NAMES = [("Jack", "Wilson"), ("Oliver", "Taylor"), ("Noah", "Brown"), ("Charlotte", "Smith"), ("Amelia", "Jones"), ("Isla", "Williams")]
AU_BILLING_STREETS = [
    ("120 Collins Street", "Melbourne", "Victoria", "3000"),
    ("88 George Street", "Sydney", "New South Wales", "2000"),
    ("45 Queen Street", "Brisbane", "Queensland", "4000"),
    ("22 King William Street", "Adelaide", "South Australia", "5000"),
    ("60 St Georges Terrace", "Perth", "Western Australia", "6000"),
    ("18 Elizabeth Street", "Hobart", "Tasmania", "7000"),
]
EXTRA_BILLING_NAMES = [("Alex", "Tan"), ("Daniel", "Lee"), ("Emma", "Wong"), ("Mia", "Chen"), ("Noah", "Martin"), ("Olivia", "Nguyen")]
EXTRA_BILLING_STREETS = {
    "TH": [("999 Rama I Road", "Bangkok", "Bangkok", "10330"), ("88 Sukhumvit Road", "Bangkok", "Bangkok", "10110"), ("45 Nimman Road", "Chiang Mai", "Chiang Mai", "50200")],
    "JP": [("1-1 Marunouchi", "Chiyoda-ku", "Tokyo", "100-0005"), ("2-2-1 Yaesu", "Chuo-ku", "Tokyo", "104-0028"), ("3-1 Umeda", "Osaka", "Osaka", "530-0001")],
    "SG": [("10 Anson Road", "Singapore", "Singapore", "079903"), ("1 Raffles Place", "Singapore", "Singapore", "048616"), ("80 Robinson Road", "Singapore", "Singapore", "068898")],
    "NZ": [("22 Queen Street", "Auckland", "Auckland", "1010"), ("50 Lambton Quay", "Wellington", "Wellington", "6011"), ("120 Hereford Street", "Christchurch", "Canterbury", "8011")],
    "CA": [("100 King Street West", "Toronto", "ON", "M5X 1A9"), ("555 West Hastings Street", "Vancouver", "BC", "V6B 4N6"), ("1250 Rene-Levesque Blvd", "Montreal", "QC", "H3B 4W8")],
    "IE": [("1 Grand Canal Square", "Dublin", "Dublin", "D02 P820"), ("10 South Mall", "Cork", "Cork", "T12 RD43"), ("5 Eyre Square", "Galway", "Galway", "H91 FPK2")],
}
BILLING_PROFILE_CITY_BY_COUNTRY = {
    "AT": ["Vienna", "Graz", "Linz"], "BE": ["Brussels", "Antwerp", "Ghent"], "BR": ["Sao Paulo", "Rio de Janeiro", "Brasilia"],
    "CH": ["Zurich", "Geneva", "Basel"], "DK": ["Copenhagen", "Aarhus", "Odense"], "ES": ["Madrid", "Barcelona", "Valencia"],
    "FI": ["Helsinki", "Espoo", "Tampere"], "FR": ["Paris", "Lyon", "Marseille"], "ID": ["Jakarta", "Surabaya", "Bandung"],
    "IT": ["Rome", "Milan", "Turin"], "KR": ["Seoul", "Busan", "Incheon"], "MX": ["Mexico City", "Guadalajara", "Monterrey"],
    "NL": ["Amsterdam", "Rotterdam", "Utrecht"], "NO": ["Oslo", "Bergen", "Trondheim"], "PL": ["Warsaw", "Krakow", "Gdansk"],
    "PT": ["Lisbon", "Porto", "Coimbra"], "SE": ["Stockholm", "Gothenburg", "Malmo"], "TW": ["Taipei", "Taichung", "Kaohsiung"],
}
POSTAL_PATTERN_BY_COUNTRY = {
    "AD": "AD###", "AR": "C####", "AU": "####", "AT": "####", "BE": "####", "BR": "#####-###",
    "CA": "A#A #A#", "CH": "####", "CL": "#######", "CZ": "### ##", "DE": "#####", "DK": "####",
    "ES": "#####", "FI": "#####", "FR": "#####", "GB": "AA# #AA", "IE": "A## A###", "ID": "#####",
    "IN": "######", "IT": "#####", "JP": "###-####", "KR": "#####", "MX": "#####", "NL": "#### AA",
    "NO": "####", "NZ": "####", "PL": "##-###", "PT": "####-###", "SE": "### ##", "SG": "######",
    "TH": "#####", "US": "#####",
}
BILLING_STREET_POOL = ["Market Street", "Central Avenue", "Station Road", "Main Street", "High Street", "King Street"]
BILLING_PROFILE_BY_COUNTRY = {
    country: {
        "currency": COUNTRY_CURRENCY.get(country, "USD"),
        "phone_prefix": COUNTRY_PHONE_PREFIX.get(country, "+1"),
        "city_pool": BILLING_PROFILE_CITY_BY_COUNTRY.get(country, ["Capital City", "Central District", "Market Town"]),
        "postal_pattern": POSTAL_PATTERN_BY_COUNTRY.get(country, "#####"),
        "street_pool": BILLING_STREET_POOL,
    }
    for country in OPENAI_SUPPORTED_COUNTRY_CODES
}
LOCALE_MAP = {
    "de": ("de-DE", "de"), "en": ("en-US", "en"), "en-US": ("en-US", "en"), "es": ("es-ES", "es"),
    "fr": ("fr-FR", "fr"), "id": ("id-ID", "id"), "it": ("it-IT", "it"), "ja": ("ja-JP", "ja"),
    "ko": ("ko-KR", "ko"), "pt-BR": ("pt-BR", "pt-BR"), "zh-CN": ("zh-CN", "zh-CN"), "zh-TW": ("zh-TW", "zh-TW"),
}

DEVICE_PROFILES = [
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/New_York"},
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Chicago"},
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Los_Angeles"},
    {"locale": "en-GB", "languages": ["en-GB", "en"], "timezone": "Europe/London"},
]
REGISTER_DEVICE_PROFILES = [
    {"locale": "ja-JP", "languages": ["ja-JP", "ja"], "timezone": "Asia/Tokyo"},
]
TEAM_DEVICE_PROFILES = [
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/New_York"},
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Chicago"},
    {"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Los_Angeles"},
]
PAYMENT_DEVICE_PROFILES = [
    {"locale": "ja-JP", "languages": ["ja-JP", "ja"], "timezone": "Asia/Tokyo"},
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
    mail_provider: str = "hotmail"
    api_key: str = ""


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

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d.pop("accept_language", None)
        d.pop("chrome_major", None)
        d.pop("chrome_full", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DeviceFingerprint":
        return cls(
            user_agent=d.get("user_agent", ""),
            locale=d.get("locale", "en-US"),
            languages=list(d.get("languages", ["en-US", "en"])),
            timezone=d.get("timezone", "America/New_York"),
            viewport_width=d.get("viewport_width", 1365),
            viewport_height=d.get("viewport_height", 768),
            screen_width=d.get("screen_width", 1366),
            screen_height=d.get("screen_height", 768),
            outer_width=d.get("outer_width", 1365),
            outer_height=d.get("outer_height", 768),
            device_scale_factor=d.get("device_scale_factor", 1.0),
            hardware_concurrency=d.get("hardware_concurrency", 8),
            device_memory=d.get("device_memory", 8),
            platform=d.get("platform", "Win32"),
            vendor=d.get("vendor", "Google Inc."),
            max_touch_points=d.get("max_touch_points", 0),
        )


FINGERPRINT_STORE_FILE = APP_DIR / "fingerprint_store.json"


def _load_fingerprint_store() -> dict:
    try:
        if FINGERPRINT_STORE_FILE.exists():
            return json.loads(FINGERPRINT_STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_fingerprint_store(store: dict) -> None:
    tmp = FINGERPRINT_STORE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(FINGERPRINT_STORE_FILE)


def get_fingerprint_for_email(email: str) -> DeviceFingerprint | None:
    store = _load_fingerprint_store()
    data = store.get(email.lower())
    if isinstance(data, dict):
        return DeviceFingerprint.from_dict(data)
    return None


def get_or_create_fingerprint_for_email(email: str, generator: callable) -> DeviceFingerprint:
    cached = get_fingerprint_for_email(email)
    if cached:
        return cached
    fp = generator()
    save_fingerprint_for_email(email, fp)
    return fp


def save_fingerprint_for_email(email: str, fp: DeviceFingerprint) -> None:
    store = _load_fingerprint_store()
    store[email.lower()] = fp.to_dict()
    _save_fingerprint_store(store)


def generate_fingerprint(profiles: list[dict] | None = None) -> DeviceFingerprint:
    profile = random.choice(profiles or DEVICE_PROFILES)
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


def generate_register_fingerprint() -> DeviceFingerprint:
    return generate_fingerprint(REGISTER_DEVICE_PROFILES)


def generate_team_fingerprint() -> DeviceFingerprint:
    return generate_fingerprint(TEAM_DEVICE_PROFILES)


def generate_payment_fingerprint() -> DeviceFingerprint:
    return generate_fingerprint(PAYMENT_DEVICE_PROFILES)


_COUNTRY_LOCALE_TZ = {
    "JP": ("ja-JP", "Asia/Tokyo"),
    "US": ("en-US", "America/Los_Angeles"),
    "BR": ("pt-BR", "America/Sao_Paulo"),
    "CN": ("zh-CN", "Asia/Shanghai"),
    "HK": ("zh-HK", "Asia/Hong_Kong"),
    "TW": ("zh-TW", "Asia/Taipei"),
    "KR": ("ko-KR", "Asia/Seoul"),
    "SG": ("en-SG", "Asia/Singapore"),
    "IN": ("en-IN", "Asia/Kolkata"),
    "ID": ("id-ID", "Asia/Jakarta"),
    "TH": ("th-TH", "Asia/Bangkok"),
    "VN": ("vi-VN", "Asia/Ho_Chi_Minh"),
    "GB": ("en-GB", "Europe/London"),
    "DE": ("de-DE", "Europe/Berlin"),
    "FR": ("fr-FR", "Europe/Paris"),
    "IT": ("it-IT", "Europe/Rome"),
    "ES": ("es-ES", "Europe/Madrid"),
    "NL": ("nl-NL", "Europe/Amsterdam"),
    "SE": ("sv-SE", "Europe/Stockholm"),
    "AU": ("en-AU", "Australia/Sydney"),
    "CA": ("en-CA", "America/Toronto"),
    "MX": ("es-MX", "America/Mexico_City"),
    "AR": ("es-AR", "America/Argentina/Buenos_Aires"),
    "CO": ("es-CO", "America/Bogota"),
    "CL": ("es-CL", "America/Santiago"),
    "TR": ("tr-TR", "Europe/Istanbul"),
    "RU": ("ru-RU", "Europe/Moscow"),
    "UA": ("uk-UA", "Europe/Kiev"),
    "PL": ("pl-PL", "Europe/Warsaw"),
    "PH": ("en-PH", "Asia/Manila"),
    "MY": ("en-MY", "Asia/Kuala_Lumpur"),
    "NG": ("en-NG", "Africa/Lagos"),
    "ZA": ("en-ZA", "Africa/Johannesburg"),
    "KE": ("en-KE", "Africa/Nairobi"),
    "EG": ("ar-EG", "Africa/Cairo"),
    "AE": ("ar-AE", "Asia/Dubai"),
    "SA": ("ar-SA", "Asia/Riyadh"),
    "IL": ("he-IL", "Asia/Jerusalem"),
}


def _proxy_country_to_locale_tz(country_code: str) -> tuple | None:
    cc = str(country_code or "").upper().strip()
    return _COUNTRY_LOCALE_TZ.get(cc)


def generate_team_email() -> str:
    return f"{secrets.token_hex(6)}@{TEAM_EMAIL_DOMAIN}"


def parse_account_line(line: str) -> MailAccount:
    parts = [part.strip() for part in str(line or "").strip().split("----")]
    if len(parts) == 1:
        email_addr = parts[0]
        if not email_addr or "@" not in email_addr:
            raise ValueError("格式错误, 单段格式需为有效邮箱地址")
        return MailAccount(
            email=email_addr,
            password="",
            client_id="",
            refresh_token="",
            raw=email_addr,
            mail_provider="custom_api",
            api_key="",
        )
    if len(parts) == 2:
        email_addr, api_key = parts
        if not email_addr or not api_key:
            raise ValueError("格式错误, email / key 不能为空")
        return MailAccount(
            email=email_addr,
            password="",
            client_id="",
            refresh_token="",
            raw="----".join([email_addr, api_key]),
            mail_provider="custom_api",
            api_key=api_key,
        )
    is_custom_api = False
    if len(parts) >= 3 and "=" in parts[2]:
        is_custom_api = True
    if is_custom_api:
        email_addr, api_key = parts[:2]
        if not email_addr or not api_key:
            raise ValueError("格式错误, email / key 不能为空")
        extras = extract_account_extras(parts[2:])
        openai_rt = extras["openai_rt"]
        base_raw = "----".join([email_addr, api_key])
        return MailAccount(
            email=email_addr,
            password="",
            client_id="",
            refresh_token="",
            raw=base_raw,
            mail_provider="custom_api",
            api_key=api_key,
            account_type=str(extras.get("account_type") or ("plus" if openai_rt else "free")),
            status="已绑定手机号" if openai_rt else "待获取RT" if extras["auth_phone_number"] and extras["auth_phone_sms_url"] else "",
            openai_rt=openai_rt,
            auth_phone_number=extras["auth_phone_number"],
            auth_phone_sms_url=extras["auth_phone_sms_url"],
        )
    if len(parts) < 4:
        raise ValueError("格式错误, 应为 email 或 email----password----client_id----refresh_token")
    email_addr, password, client_id, refresh_token = parts[0], parts[1], parts[2], parts[3]
    if not email_addr or not password or not refresh_token:
        raise ValueError("格式错误, email / password / refresh_token 不能为空")
    extras = extract_account_extras(parts[4:])
    openai_rt = extras["openai_rt"]
    return MailAccount(
        email=email_addr,
        password=password,
        client_id=client_id,
        refresh_token=refresh_token,
        raw="----".join([email_addr, password, client_id, refresh_token]),
        account_type=str(extras.get("account_type") or ("plus" if openai_rt else "free")),
        status="已绑定手机号" if openai_rt else "待获取RT" if extras["auth_phone_number"] and extras["auth_phone_sms_url"] else "",
        openai_rt=openai_rt,
        auth_phone_number=extras["auth_phone_number"],
        auth_phone_sms_url=extras["auth_phone_sms_url"],
    )


def extract_account_extras(extra_parts: list[str]) -> dict:
    result = {"openai_rt": "", "auth_phone_number": "", "auth_phone_sms_url": "", "account_type": ""}
    for raw_part in extra_parts:
        part = str(raw_part or "").strip()
        if not part:
            continue
        lower = part.lower()
        if lower.startswith(("rt_token=", "openai_rt=")):
            result["openai_rt"] = part.split("=", 1)[1].strip()
            continue
        if lower.startswith(("auth_phone=", "auth_phone_number=", "phone=")):
            result["auth_phone_number"] = part.split("=", 1)[1].strip()
            continue
        if lower.startswith(("auth_phone_sms_url=", "auth_sms_url=", "phone_sms_url=", "sms_url=")):
            result["auth_phone_sms_url"] = part.split("=", 1)[1].strip()
            continue
        if lower.startswith(("account_type=", "type=")):
            account_type = part.split("=", 1)[1].strip().lower()
            if account_type in {"free", "plus", "team"}:
                result["account_type"] = account_type
            continue
        inline_phone = re.match(r"^([+\d][\d\s().-]*)(https?://\S+)$", part)
        if inline_phone:
            result["auth_phone_number"] = result["auth_phone_number"] or inline_phone.group(1).strip()
            result["auth_phone_sms_url"] = result["auth_phone_sms_url"] or inline_phone.group(2).strip()
            continue
        if not result["auth_phone_number"] and re.fullmatch(r"[+\d][\d\s().-]{5,}", part):
            result["auth_phone_number"] = part
            continue
        if not result["auth_phone_sms_url"] and re.match(r"https?://\S+$", part):
            result["auth_phone_sms_url"] = part
            continue
    return result


def extract_rt_token(extra_parts: list[str]) -> str:
    return str(extract_account_extras(extra_parts).get("openai_rt") or "")


def account_to_dict(account: MailAccount) -> dict:
    raw = account.raw
    if not raw:
        if account.client_id and account.refresh_token:
            raw = "----".join([account.email, account.password, account.client_id, account.refresh_token])
        elif account.api_key:
            raw = "----".join([account.email, account.api_key])
    return {
        "email": account.email,
        "password": account.password,
        "client_id": account.client_id,
        "refresh_token": account.refresh_token,
        "raw": raw,
        "account_type": account.account_type,
        "status": account.status,
        "openai_rt": account.openai_rt,
        "auth_phone_number": account.auth_phone_number,
        "auth_phone_sms_url": account.auth_phone_sms_url,
        "mail_provider": account.mail_provider,
        "api_key": account.api_key,
    }


def account_from_dict(value: dict) -> MailAccount:
    raw_value = str(value.get("raw") or "")
    if raw_value:
        try:
            account = parse_account_line(raw_value)
            account.account_type = str(value.get("account_type", account.account_type) or "free")
            account.status = str(value.get("status", account.status) or "")
            account.openai_rt = str(value.get("openai_rt", account.openai_rt) or account.openai_rt)
            account.auth_phone_number = str(value.get("auth_phone_number", account.auth_phone_number) or account.auth_phone_number)
            account.auth_phone_sms_url = str(value.get("auth_phone_sms_url", account.auth_phone_sms_url) or account.auth_phone_sms_url)
            return account
        except Exception:
            pass
    email_addr = str(value.get("email", "")).strip()
    password = str(value.get("password", ""))
    client_id = str(value.get("client_id", "")).strip()
    refresh_token = str(value.get("refresh_token", "")).strip()
    mail_provider = str(value.get("mail_provider", "hotmail") or "hotmail")
    api_key = str(value.get("api_key", "") or "")
    raw = raw_value
    if not raw:
        if client_id and refresh_token:
            raw = "----".join([email_addr, password, client_id, refresh_token])
        elif api_key:
            raw = "----".join([email_addr, api_key])
    account = MailAccount(
        email=email_addr,
        password=password,
        client_id=client_id,
        refresh_token=refresh_token,
        raw=raw,
        account_type=str(value.get("account_type", "free") or "free"),
        status=str(value.get("status", "") or ""),
        openai_rt=str(value.get("openai_rt", "") or ""),
        auth_phone_number=str(value.get("auth_phone_number", "") or ""),
        auth_phone_sms_url=str(value.get("auth_phone_sms_url", "") or ""),
        mail_provider=str(value.get("mail_provider", "hotmail") or "hotmail"),
        api_key=str(value.get("api_key", "") or ""),
    )
    return account


def account_export_line(account: MailAccount, name_prefix: str = "") -> str:
    if account.raw:
        line = account.raw
    elif account.mail_provider == "custom_api":
        line = "----".join([account.email, account.api_key])
    else:
        line = "----".join([account.email, account.password, account.client_id, account.refresh_token]).rstrip("-")
    if not line:
        line = account.email
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
        receive_count=max(0, int(value.get("receive_count", 0) or 0)),
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


def normalize_us_phone_for_form(phone_number: str) -> str:
    digits = re.sub(r"\D+", "", str(phone_number or ""))
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


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


def random_proxy_sid(length: int = 10) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(alphabet) for _ in range(length))


def randomize_proxy_sid(proxy_url: str) -> str:
    text = str(proxy_url or "").strip()
    if not text:
        return ""
    sid = random_proxy_sid()
    parsed = urlsplit(text)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key.lower() == "sid" for key, _value in query_pairs):
        query = urlencode([(key, sid if key.lower() == "sid" else value) for key, value in query_pairs])
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))

    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, host = netloc.rsplit("@", 1)
        new_userinfo = re.sub(r"(?i)(sid[-_=])([^-:@;&/?]+)", lambda m: f"{m.group(1)}{sid}", userinfo, count=1)
        if new_userinfo != userinfo:
            return urlunsplit((parsed.scheme, f"{new_userinfo}@{host}", parsed.path, parsed.query, parsed.fragment))

    new_text = re.sub(r"(?i)(sid[-_=])([^-:@;&/?]+)", lambda m: f"{m.group(1)}{sid}", text, count=1)
    return new_text


def mask_proxy_url(proxy_url: str) -> str:
    text = str(proxy_url or "").strip()
    if not text:
        return "直连"
    try:
        parsed = urlsplit(text)
        if "@" not in parsed.netloc:
            return text
        userinfo, host = parsed.netloc.rsplit("@", 1)
        if ":" in userinfo:
            username, _password = userinfo.split(":", 1)
            userinfo = f"{username}:***"
        else:
            userinfo = "***"
        return urlunsplit((parsed.scheme, f"{userinfo}@{host}", parsed.path, parsed.query, parsed.fragment))
    except Exception:
        return re.sub(r":([^:@/]+)@", ":***@", text)


def find_access_token(value) -> str:
    if isinstance(value, dict):
        for key in ("accessToken", "access_token", "token"):
            token = str(value.get(key) or "").strip()
            if token:
                return token
        for item in value.values():
            token = find_access_token(item)
            if token:
                return token
    if isinstance(value, list):
        for item in value:
            token = find_access_token(item)
            if token:
                return token
    return ""


def extract_access_token_from_session_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if raw.startswith("Bearer "):
        return raw.split(None, 1)[1].strip()
    try:
        return find_access_token(json.loads(raw))
    except Exception:
        pass
    match = re.search(r'"(?:accessToken|access_token|token)"\s*:\s*"([^"]+)"', raw)
    if match:
        return match.group(1).strip()
    return raw if raw.count(".") >= 2 and len(raw) > 80 else ""


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


def currency_for_country(country: str) -> str:
    return COUNTRY_CURRENCY.get(str(country or "").upper(), "USD")


def normalize_opll_country(country: str) -> str:
    country = str(country or "").strip().upper()
    return country if country in OPENAI_SUPPORTED_COUNTRY_CODES else "US"


def locale_parts(locale: str = "en") -> tuple[str, str]:
    return LOCALE_MAP.get(str(locale or "").strip(), LOCALE_MAP["en"])


def opll_extract_processor_entity(data) -> str:
    if not isinstance(data, dict):
        return ""
    direct = data.get("processor_entity") or data.get("processorEntity")
    if direct:
        return str(direct).strip()
    for key in ("checkout_session", "session", "checkout", "data"):
        nested = data.get(key)
        if isinstance(nested, dict):
            found = opll_extract_processor_entity(nested)
            if found:
                return found
    return ""


def opll_extract_stripe_publishable_key(data) -> str:
    if isinstance(data, str):
        match = re.search(r"pk_live_[A-Za-z0-9]+", data)
        return match.group(0) if match else ""
    if isinstance(data, dict):
        for key in ("stripe_publishable_key", "publishable_key", "publishableKey", "stripePublishableKey", "key"):
            found = opll_extract_stripe_publishable_key(data.get(key))
            if found:
                return found
        for item in data.values():
            found = opll_extract_stripe_publishable_key(item)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            found = opll_extract_stripe_publishable_key(item)
            if found:
                return found
    return ""


def opll_processor_entity_for_country(country: str, processor_entity: str = "") -> str:
    entity = str(processor_entity or "").strip()
    if entity:
        return entity
    return "openai_llc" if str(country or "").upper() == "US" else "openai_ie"


def opll_chatgpt_success_return_url(cs_id: str, country: str, processor_entity: str = "") -> str:
    entity = opll_processor_entity_for_country(country, processor_entity)
    return f"https://chatgpt.com/checkout/verify?stripe_session_id={cs_id}&processor_entity={entity}&plan_type=plus"


def opll_to_openai_pay_url(stripe_hosted_url: str) -> str:
    url = str(stripe_hosted_url or "").strip()
    if not url:
        return ""
    if url.startswith("https://checkout.stripe.com"):
        return "https://pay.openai.com" + url[len("https://checkout.stripe.com"):]
    parsed = urlsplit(url)
    if parsed.netloc.lower() == "checkout.stripe.com":
        return urlunsplit((parsed.scheme or "https", "pay.openai.com", parsed.path, parsed.query, parsed.fragment))
    return url


def opll_stripe_checkout_long_url(cs_id: str, country: str, processor_entity: str = "") -> str:
    return (
        f"https://checkout.stripe.com/c/pay/{cs_id}"
        f"?returned_from_redirect=true&ui_mode=custom&return_url="
        f"{quote(opll_chatgpt_success_return_url(cs_id, country, processor_entity), safe='')}"
    )


def opll_stripe_confirm_return_url(cs_id: str, checkout: dict, stripe_hosted_url: str) -> str:
    hosted_url = opll_to_openai_pay_url(stripe_hosted_url) or opll_stripe_checkout_long_url(
        cs_id,
        checkout["billing_country"],
        checkout.get("processor_entity", ""),
    )
    if "pay.openai.com/" in hosted_url or "checkout.stripe.com/" in hosted_url:
        parsed = urlsplit(hosted_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.setdefault(
            "success_return_url",
            opll_chatgpt_success_return_url(
                cs_id,
                checkout["billing_country"],
                checkout.get("processor_entity", ""),
            ),
        )
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    return hosted_url


def opll_new_http_session() -> requests.Session:
    if CurlCffiSession is not None:
        session = CurlCffiSession(impersonate="chrome136")  # type: ignore[assignment]
    else:
        session = requests.Session()
    if hasattr(session, "trust_env"):
        session.trust_env = False
    return session


def opll_build_chatgpt_session(access_token: str, proxy_url: str = "") -> requests.Session:
    token = extract_access_token_from_session_text(access_token) or str(access_token or "").strip()
    if not token:
        raise RuntimeError("当前账号没有 Access Token，请先注册并获取 Session 信息")
    device_id = str(uuid.uuid4())
    session = opll_new_http_session()
    session.headers.update({
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": f"Bearer {token}",
        "Origin": "https://chatgpt.com",
        "Referer": "https://chatgpt.com/",
        "Content-Type": "application/json",
        "oai-device-id": device_id,
        "oai-language": "en-US",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "Cookie": f"oai-did={device_id}",
    })
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    return session


def opll_create_checkout(access_token: str, country: str, currency: str, proxy_url: str = "") -> dict:
    country = normalize_opll_country(country)
    currency = currency_for_country(country)
    session = opll_build_chatgpt_session(access_token, proxy_url)
    response = session.post(
        "https://chatgpt.com/backend-api/payments/checkout",
        json={
            "entry_point": "all_plans_pricing_modal",
            "plan_name": "chatgptplusplan",
            "billing_details": {"country": country, "currency": currency},
            "promo_campaign": {"promo_campaign_id": "plus-1-month-free", "is_coupon_from_query_param": False},
            "checkout_ui_mode": "custom",
        },
        headers={
            "Referer": "https://chatgpt.com/",
            "x-openai-target-path": "/backend-api/payments/checkout",
            "x-openai-target-route": "/backend-api/payments/checkout",
        },
        timeout=PAY_LONG_LINK_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"checkout create failed: HTTP {response.status_code} {response.text[:500]}")
    data = response.json() or {}
    cs_id = data.get("checkout_session_id") or data.get("session_id") or data.get("id")
    if not cs_id or not str(cs_id).startswith("cs_"):
        raise RuntimeError(f"checkout response missing cs_id: {str(data)[:500]}")
    return {
        "cs_id": str(cs_id),
        "processor_entity": opll_extract_processor_entity(data),
        "stripe_publishable_key": opll_extract_stripe_publishable_key(data),
        "billing_country": country,
        "currency": currency,
    }


def opll_stripe_key_for_checkout(checkout: dict | None = None) -> str:
    return str((checkout or {}).get("stripe_publishable_key") or "").strip() or DEFAULT_STRIPE_PK


def opll_stripe_init(cs_id: str, country: str, currency: str, proxy_url: str = "", payment_locale: str = "en", stripe: requests.Session | None = None, ctx: dict | None = None, checkout: dict | None = None) -> dict:
    browser_locale, elements_locale = locale_parts(payment_locale)
    stripe_pk = opll_stripe_key_for_checkout(checkout)
    stripe_session = stripe or requests.Session()
    if stripe is None:
        stripe_session.headers.update({"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        if hasattr(stripe_session, "trust_env"):
            stripe_session.trust_env = False
        if proxy_url:
            stripe_session.proxies.update({"http": proxy_url, "https": proxy_url})
    response = stripe_session.post(
        f"https://api.stripe.com/v1/payment_pages/{cs_id}/init",
        data={
            "browser_locale": browser_locale,
            "browser_timezone": "Asia/Shanghai",
            "elements_session_client[client_betas][0]": "custom_checkout_server_updates_1",
            "elements_session_client[client_betas][1]": "custom_checkout_manual_approval_1",
            "elements_session_client[elements_init_source]": "custom_checkout",
            "elements_session_client[referrer_host]": "chatgpt.com",
            "elements_session_client[stripe_js_id]": str((ctx or {}).get("stripe_js_id") or uuid.uuid4()),
            "elements_session_client[locale]": elements_locale,
            "elements_session_client[is_aggregation_expected]": "false",
            "elements_options_client[saved_payment_method][enable_save]": "never",
            "elements_options_client[saved_payment_method][enable_redisplay]": "never",
            "key": stripe_pk,
            "_stripe_version": STRIPE_VERSION_FULL,
        },
        timeout=PAY_LONG_LINK_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"stripe init failed: HTTP {response.status_code} {response.text[:500]}")
    return response.json() or {}


def opll_build_stripe_session(proxy_url: str = "") -> requests.Session:
    session = opll_new_http_session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    return session


def opll_stripe_context(init_payload: dict, payment_locale: str = "en", ctx: dict | None = None) -> dict:
    _browser_locale, elements_locale = locale_parts(payment_locale)
    base = ctx or {}
    return {
        "stripe_js_id": str(base.get("stripe_js_id") or uuid.uuid4()),
        "elements_session_id": str(base.get("elements_session_id") or f"elements_session_{uuid.uuid4().hex[:11]}"),
        "elements_session_config_id": str(init_payload.get("config_id") or base.get("elements_session_config_id") or uuid.uuid4()),
        "config_id": str(init_payload.get("config_id") or ""),
        "init_checksum": str(init_payload.get("init_checksum") or ""),
        "checkout_amount": str(opll_expected_amount(init_payload)),
        "currency": str(init_payload.get("currency") or "").lower(),
        "locale": elements_locale,
        "runtime_version": str(base.get("runtime_version") or DEFAULT_STRIPE_RUNTIME_VERSION),
    }


def opll_expected_amount(init_payload: dict) -> str:
    return opll_stripe_amount_info(init_payload)[0]


def opll_stripe_amount_info(init_payload) -> tuple[str, str]:
    if not isinstance(init_payload, dict):
        return "0", "missing_payload"
    total_summary = init_payload.get("total_summary") if isinstance(init_payload, dict) else None
    if isinstance(total_summary, dict) and total_summary.get("due") is not None:
        return str(total_summary.get("due")), "total_summary.due"
    invoice = init_payload.get("invoice") if isinstance(init_payload, dict) else None
    if isinstance(invoice, dict) and invoice.get("amount_due") is not None:
        return str(invoice.get("amount_due")), "invoice.amount_due"
    line_items = init_payload.get("line_items") if isinstance(init_payload, dict) else None
    if isinstance(line_items, list):
        total = 0
        found = False
        for item in line_items:
            if isinstance(item, dict) and item.get("amount") is not None:
                try:
                    total += int(item.get("amount") or 0)
                    found = True
                except Exception:
                    pass
        if found:
            return str(total), "line_items.amount"
    return "0", "fallback_zero"


def opll_random_postal_code(pattern: str) -> str:
    result = []
    for char in str(pattern or "#####"):
        if char == "#":
            result.append(str(random.randint(0, 9)))
        elif char == "A":
            result.append(chr(random.randint(ord("A"), ord("Z"))))
        else:
            result.append(char)
    return "".join(result)


def opll_billing_for_country(country: str) -> dict:
    country = normalize_opll_country(country)
    if country == "DE":
        first, last = random.choice(DE_BILLING_NAMES)
        line1, city, state, postal = random.choice(DE_BILLING_STREETS)
    elif country == "GB":
        first, last = random.choice(GB_BILLING_NAMES)
        line1, city, state, postal = random.choice(GB_BILLING_STREETS)
    elif country == "AU":
        first, last = random.choice(AU_BILLING_NAMES)
        line1, city, state, postal = random.choice(AU_BILLING_STREETS)
    elif country == "US":
        first, last = random.choice(US_BILLING_NAMES)
        line1, city, state, postal = random.choice(US_BILLING_STREETS)
    elif country in EXTRA_BILLING_STREETS:
        first, last = random.choice(EXTRA_BILLING_NAMES)
        line1, city, state, postal = random.choice(EXTRA_BILLING_STREETS[country])
    elif country in OPENAI_SUPPORTED_COUNTRY_CODES:
        profile = BILLING_PROFILE_BY_COUNTRY[country]
        first, last = random.choice(EXTRA_BILLING_NAMES)
        line1 = f"{random.randint(10, 999)} {random.choice(profile['street_pool'])}"
        city = random.choice(profile["city_pool"])
        state = country
        postal = opll_random_postal_code(str(profile.get("postal_pattern") or "#####"))
    else:
        raise RuntimeError(f"不支持的账单资料地区: {country}")
    suffix = random.randint(1000, 9999)
    phone_prefix = str(BILLING_PROFILE_BY_COUNTRY.get(country, {}).get("phone_prefix") or COUNTRY_PHONE_PREFIX.get(country, "+1"))
    return {
        "name": f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}{suffix}@example.com",
        "phone": f"{phone_prefix}{random.randint(100000000, 999999999)}",
        "country": country,
        "line1": line1,
        "city": city,
        "state": state,
        "postal_code": postal,
    }


def opll_random_jp_billing() -> dict:
    suffix = random.randint(1000, 9999)
    first = random.choice(["Haruto", "Yuto", "Sota", "Ren", "Yui", "Hina", "Aoi", "Sakura"])
    last = random.choice(["Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Ito", "Yamamoto"])
    street, city, state, postal = random.choice([
        ("1-1 Marunouchi", "Chiyoda-ku", "Tokyo", "100-0005"),
        ("2-8-1 Nishi-Shinjuku", "Shinjuku-ku", "Tokyo", "160-0023"),
        ("1-1 Umeda", "Kita-ku Osaka", "Osaka", "530-0001"),
        ("3-1 Minatomirai", "Nishi-ku Yokohama", "Kanagawa", "220-0012"),
    ])
    return {"name": f"{first} {last}", "email": f"{first.lower()}.{last.lower()}{suffix}@example.com", "country": "JP", "line1": street, "city": city, "state": state, "postal_code": postal}


def opll_stripe_create_paypal_method(stripe: requests.Session, cs_id: str, ctx: dict, billing: dict, stripe_pk: str = "") -> str:
    runtime_version = str(ctx.get("runtime_version") or DEFAULT_STRIPE_RUNTIME_VERSION)
    body = {
        "billing_details[name]": billing.get("name") or "John Doe",
        "billing_details[email]": billing.get("email") or "buyer@example.com",
        "billing_details[phone]": billing.get("phone") or "",
        "billing_details[address][country]": billing.get("country") or "US",
        "billing_details[address][line1]": billing.get("line1") or "3110 Sunset Boulevard",
        "billing_details[address][city]": billing.get("city") or "Los Angeles",
        "billing_details[address][postal_code]": billing.get("postal_code") or "90026",
        "billing_details[address][state]": billing.get("state") or "CA",
        "type": "paypal",
        "payment_user_agent": f"stripe.js/{runtime_version}; stripe-js-v3/{runtime_version}; payment-element; deferred-intent",
        "referrer": "https://chatgpt.com",
        "time_on_page": str(random.randint(25000, 55000)),
        "client_attribution_metadata[checkout_session_id]": cs_id,
        "client_attribution_metadata[client_session_id]": ctx["stripe_js_id"],
        "client_attribution_metadata[checkout_config_id]": ctx.get("config_id") or "",
        "client_attribution_metadata[elements_session_id]": ctx["elements_session_id"],
        "client_attribution_metadata[elements_session_config_id]": ctx["elements_session_config_id"],
        "client_attribution_metadata[merchant_integration_source]": "elements",
        "client_attribution_metadata[merchant_integration_subtype]": "payment-element",
        "client_attribution_metadata[merchant_integration_version]": "2021",
        "client_attribution_metadata[payment_intent_creation_flow]": "deferred",
        "client_attribution_metadata[payment_method_selection_flow]": "automatic",
        "client_attribution_metadata[merchant_integration_additional_elements][0]": "payment",
        "client_attribution_metadata[merchant_integration_additional_elements][1]": "address",
        "key": stripe_pk or DEFAULT_STRIPE_PK,
        "_stripe_version": STRIPE_VERSION_FULL,
    }
    response = stripe.post("https://api.stripe.com/v1/payment_methods", data=body, timeout=PAY_LONG_LINK_TIMEOUT)
    if response.status_code >= 400:
        raise RuntimeError(f"stripe payment_methods failed: HTTP {response.status_code} {response.text[:500]}")
    pm_id = str((response.json() or {}).get("id") or "")
    if not pm_id.startswith("pm_"):
        raise RuntimeError(f"stripe payment_methods bad response: {response.text[:300]}")
    return pm_id


def opll_short_error(detail: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(detail or "")).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def opll_stripe_error_summary(prefix: str, response) -> str:
    try:
        payload = response.json() or {}
    except Exception:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        error = {}
    extra_fields = error.get("extra_fields") if isinstance(error.get("extra_fields"), dict) else {}
    parts = []
    for label, value in (
        ("code", error.get("code")),
        ("decline_code", error.get("decline_code")),
        ("type", error.get("type")),
        ("message", error.get("message")),
        ("payment_method_type", extra_fields.get("payment_method_type")),
        ("confirm_error_reason", extra_fields.get("confirm_error_reason")),
        ("confirm_error_code", extra_fields.get("confirm_error_code")),
        ("confirm_error_message", extra_fields.get("confirm_error_message")),
    ):
        if value is not None and value != "":
            parts.append(f"{label}={opll_short_error(str(value), 180)}")
    if parts:
        return f"{prefix}: " + ", ".join(parts)
    return f"{prefix}: {opll_short_error(response.text, 500)}"


def opll_is_external_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def opll_is_paypal_url(value: str) -> bool:
    host = (urlsplit(value).netloc or "").lower()
    return host == "paypal.com" or host.endswith(".paypal.com") or host == "paypalobjects.com" or host.endswith(".paypalobjects.com")


def opll_is_paypal_ba_approve_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    if not (host == "paypal.com" or host.endswith(".paypal.com")):
        return False
    path = parsed.path.rstrip("/").lower()
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return path == "/agreements/approve" and bool(str(query.get("ba_token") or "").strip())


def opll_is_ignored_resource_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    ignored_hosts = {"stripe-camo.global.ssl.fastly.net", "files.stripe.com", "q.stripe.com", "js.stripe.com", "m.stripe.network"}
    ignored_suffixes = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".ico", ".css", ".js", ".woff", ".woff2")
    if host in ignored_hosts or any(host.endswith(f".{item}") for item in ignored_hosts):
        return True
    return path.endswith(ignored_suffixes)


def opll_collect_urls(payload, urls: list[str] | None = None) -> list[str]:
    found = urls if urls is not None else []
    if isinstance(payload, str):
        for match in re.findall(r"https?://[^\s\"'<>]+", payload):
            found.append(match.rstrip("),.;]"))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if key in ("url", "return_url", "redirect_url", "redirect_to_url") and isinstance(value, str) and opll_is_external_url(value):
                found.append(value)
            else:
                opll_collect_urls(value, found)
    elif isinstance(payload, list):
        for item in payload:
            opll_collect_urls(item, found)
    return found


def opll_extract_redirect_to_url(payload) -> str:
    if not isinstance(payload, dict):
        urls = opll_collect_urls(payload)
        return next(
            (item for item in urls if opll_is_paypal_ba_approve_url(item)),
            next((item for item in urls if opll_is_paypal_url(item) and not opll_is_ignored_resource_url(item)), ""),
        )
    next_action = payload.get("next_action")
    if isinstance(next_action, dict) and next_action.get("type") == "redirect_to_url":
        redirect_to_url = next_action.get("redirect_to_url") or {}
        if isinstance(redirect_to_url, dict):
            url = str(redirect_to_url.get("url") or "").strip()
            if url:
                return url
    for key in ("setup_intent", "payment_intent"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            found = opll_extract_redirect_to_url(nested)
            if found:
                return found
    urls = opll_collect_urls(payload)
    return next(
        (item for item in urls if opll_is_paypal_ba_approve_url(item)),
        next((item for item in urls if opll_is_paypal_url(item) and not opll_is_ignored_resource_url(item)), ""),
    )


def opll_first_non_empty(values: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = str(values.get(key) or "").strip()
        if value:
            return value
    return ""


def opll_submission_attempt_failure_fields(submission) -> dict[str, str]:
    wanted = {"error", "code", "message", "reason", "failure_reason", "decline_code", "failure_code", "failure_message"}
    found: dict[str, str] = {}

    def walk(value) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key or "").strip()
                if normalized in wanted and normalized not in found:
                    if isinstance(item, (str, int, float, bool)):
                        text = str(item).strip()
                    elif isinstance(item, dict):
                        text = str(item.get("message") or item.get("code") or item.get("reason") or item.get("type") or "").strip()
                    else:
                        text = ""
                    if text:
                        found[normalized] = text[:240]
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    if isinstance(submission, dict):
        walk(submission)
    return found


def opll_find_submission_attempt(payload) -> dict:
    if isinstance(payload, dict):
        item = payload.get("submission_attempt")
        if isinstance(item, dict):
            return item
        for value in payload.values():
            found = opll_find_submission_attempt(value)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = opll_find_submission_attempt(value)
            if found:
                return found
    return {}


def opll_submission_attempt_summary(submission: dict) -> str:
    if not submission:
        return "未找到 submission_attempt"
    fields = opll_submission_attempt_failure_fields(submission)
    state = str(submission.get("state") or "未知").strip()
    reason = opll_first_non_empty(fields, "reason", "failure_reason", "decline_code", "failure_code", "code")
    code = opll_first_non_empty(fields, "code", "decline_code", "failure_code")
    message = opll_first_non_empty(fields, "message", "failure_message", "error")
    parts = [f"state={state}"]
    if reason:
        parts.append(f"reason={reason}")
    if code:
        parts.append(f"code={code}")
    if message:
        parts.append(f"message={message}")
    return "，".join(parts)


def opll_stripe_payload_diagnostics(payload, ctx: dict) -> str:
    if not isinstance(payload, dict):
        return f"payload_type={type(payload).__name__}"
    keys = ",".join(sorted(payload.keys())[:12])
    urls = opll_collect_urls(payload)
    paypal_count = sum(1 for item in urls if opll_is_paypal_url(item))
    ba_count = sum(1 for item in urls if opll_is_paypal_ba_approve_url(item))
    ignored_count = sum(1 for item in urls if opll_is_ignored_resource_url(item))
    submission = opll_find_submission_attempt(payload)
    submission_state = str(submission.get("state") or "") if isinstance(submission, dict) else ""
    submission_fields = opll_submission_attempt_failure_fields(submission)
    submission_reason = opll_first_non_empty(submission_fields, "reason", "failure_reason", "decline_code", "failure_code", "code")
    submission_code = opll_first_non_empty(submission_fields, "code", "decline_code", "failure_code")
    submission_message = opll_first_non_empty(submission_fields, "message", "failure_message", "error")
    return (
        f"keys=[{keys}], urls={len(urls)}, paypal_urls={paypal_count}, ba_approve_urls={ba_count}, "
        f"ignored_resource_urls={ignored_count}, submission_attempt={bool(submission)}, submission_state={submission_state or '未知'}, "
        f"submission_reason={submission_reason or '无'}, submission_code={submission_code or '无'}, "
        f"submission_message={submission_message or '无'}, ctx_session={ctx.get('elements_session_id') or ''}"
    )


class OpllStripeRequiresApproval(Exception):
    pass


class OpllChatgptApproveBlocked(Exception):
    pass


OPLL_APPROVE_BURST_RESULTS = {"blocked", "exception"}


def opll_chatgpt_approve(chatgpt: requests.Session, cs_id: str, checkout: dict) -> None:
    entity = opll_processor_entity_for_country(checkout["billing_country"], checkout.get("processor_entity", ""))
    try:
        chatgpt.post(
            "https://chatgpt.com/backend-api/sentinel/ping",
            json={},
            headers={
                "Referer": "https://chatgpt.com/",
                "x-openai-target-path": "/backend-api/sentinel/ping",
                "x-openai-target-route": "/backend-api/sentinel/ping",
            },
            timeout=PAY_LONG_LINK_TIMEOUT,
        )
    except Exception:
        pass
    response = chatgpt.post(
        "https://chatgpt.com/backend-api/payments/checkout/approve",
        json={"checkout_session_id": cs_id, "processor_entity": entity},
        headers={"Referer": f"https://chatgpt.com/checkout/{entity}/{cs_id}", "x-openai-target-path": "/backend-api/payments/checkout/approve", "x-openai-target-route": "/backend-api/payments/checkout/approve"},
        timeout=PAY_LONG_LINK_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"chatgpt approve failed: HTTP {response.status_code} {response.text[:500]}")
    try:
        result = (response.json() or {}).get("result")
    except Exception:
        result = ""
    normalized_result = str(result or "").strip().lower()
    if normalized_result in OPLL_APPROVE_BURST_RESULTS:
        raise OpllChatgptApproveBlocked(f"chatgpt approve retryable result: {normalized_result!r}")
    if result != "approved":
        raise RuntimeError(f"chatgpt approve unexpected result: {result!r}")


def opll_chatgpt_approve_with_retry(access_token: str, cs_id: str, checkout: dict, proxy_url: str = "") -> requests.Session:
    last_error = ""
    for _ in range(3):
        try:
            chatgpt = opll_build_chatgpt_session(access_token, proxy_url)
            opll_chatgpt_approve(chatgpt, cs_id, checkout)
            return chatgpt
        except OpllChatgptApproveBlocked as exc:
            last_error = str(exc)
            break
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1)
    raise RuntimeError(f"ChatGPT approve 连续失败: {last_error}")


def opll_stripe_payment_page_redirect_url(stripe: requests.Session, cs_id: str, stripe_pk: str, payment_locale: str = "en", timeout_seconds: int = 45, ctx: dict | None = None) -> str:
    deadline = time.time() + max(1, timeout_seconds)
    _browser_locale, elements_locale = locale_parts(payment_locale)
    ctx = ctx or {}
    params = {
        "elements_session_client[client_betas][0]": "custom_checkout_server_updates_1",
        "elements_session_client[client_betas][1]": "custom_checkout_manual_approval_1",
        "elements_session_client[elements_init_source]": "custom_checkout",
        "elements_session_client[referrer_host]": "chatgpt.com",
        "elements_session_client[session_id]": str(ctx.get("elements_session_id") or f"elements_session_{uuid.uuid4().hex[:11]}"),
        "elements_session_client[stripe_js_id]": str(ctx.get("stripe_js_id") or uuid.uuid4()),
        "elements_session_client[locale]": elements_locale,
        "elements_session_client[is_aggregation_expected]": "false",
        "elements_options_client[saved_payment_method][enable_save]": "never",
        "elements_options_client[saved_payment_method][enable_redisplay]": "never",
        "key": stripe_pk,
        "_stripe_version": STRIPE_VERSION_FULL,
    }
    last_err = ""
    while time.time() < deadline:
        response = stripe.get(
            f"https://api.stripe.com/v1/payment_pages/{cs_id}",
            params=params,
            timeout=PAY_LONG_LINK_TIMEOUT,
        )
        if response.status_code == 200:
            payload = response.json() or {}
            redirect_url = opll_extract_redirect_to_url(payload)
            if redirect_url:
                return redirect_url
            submission = opll_find_submission_attempt(payload)
            if submission.get("state") == "requires_approval":
                raise OpllStripeRequiresApproval("payment page requires ChatGPT approval")
            if submission.get("state") == "failed":
                raise RuntimeError(f"stripe submission failed: {opll_stripe_payload_diagnostics(payload, ctx)}")
            last_err = opll_stripe_payload_diagnostics(payload, ctx)
        else:
            last_err = f"HTTP {response.status_code} {response.text[:120]}"
        time.sleep(1)
    raise RuntimeError(f"redirect url resolution timeout: {last_err}")


def opll_resolve_external_redirect(stripe: requests.Session, redirect_url: str, preferred_hosts: tuple[str, ...] = ("paypal.com",)) -> str:
    current = str(redirect_url or "").strip()
    for _ in range(5):
        if not current:
            return ""
        if opll_is_paypal_ba_approve_url(current):
            return current
        host = (urlsplit(current).netloc or "").lower()
        if preferred_hosts and any(host == item or host.endswith(f".{item}") for item in preferred_hosts):
            return current
        try:
            response = stripe.get(current, allow_redirects=False, timeout=PAY_LONG_LINK_TIMEOUT)
        except Exception:
            return current
        if response.status_code not in (301, 302, 303, 307, 308):
            return current
        location = str(response.headers.get("Location") or "").strip()
        if not location:
            return current
        current = urljoin(current, location)
    return current


def opll_stripe_confirm(stripe: requests.Session, cs_id: str, pm_id: str, stripe_pk: str, init_payload: dict, ctx: dict, checkout: dict, stripe_hosted_url: str) -> dict:
    return_url = opll_stripe_confirm_return_url(cs_id, checkout, stripe_hosted_url)
    runtime_version = str(ctx.get("runtime_version") or DEFAULT_STRIPE_RUNTIME_VERSION)
    response = stripe.post(
        f"https://api.stripe.com/v1/payment_pages/{cs_id}/confirm",
        data={
            "guid": uuid.uuid4().hex,
            "muid": uuid.uuid4().hex,
            "sid": uuid.uuid4().hex,
            "payment_method": pm_id,
            "init_checksum": str(init_payload.get("init_checksum") or ctx.get("init_checksum") or ""),
            "version": runtime_version,
            "expected_amount": str(ctx.get("checkout_amount") or opll_expected_amount(init_payload)),
            "expected_payment_method_type": "paypal",
            "return_url": return_url,
            "elements_session_client[session_id]": ctx["elements_session_id"],
            "elements_session_client[locale]": str(ctx.get("locale") or "en"),
            "elements_session_client[referrer_host]": "chatgpt.com",
            "elements_session_client[is_aggregation_expected]": "false",
            "elements_session_client[elements_init_source]": "custom_checkout",
            "elements_session_client[stripe_js_id]": ctx["stripe_js_id"],
            "elements_session_client[client_betas][0]": "custom_checkout_server_updates_1",
            "elements_session_client[client_betas][1]": "custom_checkout_manual_approval_1",
            "elements_options_client[saved_payment_method][enable_save]": "never",
            "elements_options_client[saved_payment_method][enable_redisplay]": "never",
            "client_attribution_metadata[client_session_id]": ctx["stripe_js_id"],
            "client_attribution_metadata[checkout_session_id]": cs_id,
            "client_attribution_metadata[checkout_config_id]": ctx.get("config_id") or "",
            "client_attribution_metadata[elements_session_id]": ctx["elements_session_id"],
            "client_attribution_metadata[elements_session_config_id]": ctx["elements_session_config_id"],
            "client_attribution_metadata[merchant_integration_source]": "checkout",
            "client_attribution_metadata[merchant_integration_subtype]": "payment-element",
            "client_attribution_metadata[merchant_integration_version]": "custom",
            "client_attribution_metadata[payment_intent_creation_flow]": "deferred",
            "client_attribution_metadata[payment_method_selection_flow]": "automatic",
            "client_attribution_metadata[merchant_integration_additional_elements][0]": "payment",
            "client_attribution_metadata[merchant_integration_additional_elements][1]": "address",
            "consent[terms_of_service]": "accepted",
            "key": stripe_pk,
            "_stripe_version": STRIPE_VERSION_FULL,
        },
        timeout=PAY_LONG_LINK_TIMEOUT,
    )
    if response.status_code >= 400:
        try:
            error_body = response.text[:2000]
        except Exception:
            error_body = "(unable to read response body)"
        raise RuntimeError(f"{opll_stripe_error_summary('stripe confirm failed', response)} | body={error_body}")
    return response.json() or {}


def opll_redirect_url_after_confirm(access_token: str, stripe: requests.Session, confirm_payload: dict, cs_id: str, stripe_pk: str, ctx: dict, checkout: dict, proxy_url: str = "") -> str:
    redirect_url = opll_extract_redirect_to_url(confirm_payload)
    if redirect_url:
        return redirect_url
    submission = opll_find_submission_attempt(confirm_payload)
    if submission.get("state") == "requires_approval":
        opll_chatgpt_approve_with_retry(access_token, cs_id, checkout, proxy_url)
        return opll_stripe_payment_page_redirect_url(stripe, cs_id, stripe_pk, ctx=ctx, timeout_seconds=45)
    if submission.get("state") == "failed":
        raise RuntimeError(f"stripe submission failed: {opll_stripe_payload_diagnostics(confirm_payload, ctx)}")
    try:
        return opll_stripe_payment_page_redirect_url(stripe, cs_id, stripe_pk, ctx=ctx, timeout_seconds=30)
    except OpllStripeRequiresApproval:
        opll_chatgpt_approve_with_retry(access_token, cs_id, checkout, proxy_url)
        return opll_stripe_payment_page_redirect_url(stripe, cs_id, stripe_pk, ctx=ctx, timeout_seconds=45)


def opll_combo_attempt_order(country: str) -> list[tuple[str, str]]:
    requested = normalize_opll_country(country)
    ordered = [(requested, requested)]
    if requested == "DE":
        ordered.extend([("US", "US"), ("DE", "US"), ("US", "DE")])
    result = []
    seen = set()
    for item in ordered:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _opll_detect_proxy_exit(proxy_url: str) -> str:
    if not proxy_url:
        return ""
    try:
        response = requests.get(
            "https://ipinfo.io/json",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=10,
        )
        if response.status_code >= 400:
            return ""
        payload = response.json() or {}
        ip = str(payload.get("ip") or "").strip()
        country = str(payload.get("country") or "").strip()
        if ip and country:
            return f"{ip} ({country})"
        return ip or country
    except Exception:
        return ""


def generate_opll_paypal_long_link(access_token: str, country: str, currency: str, proxy_url: str = "", checkout_proxy_url: str = "", log=None) -> dict:
    failures: list[str] = []
    requested_country = normalize_opll_country(country)
    checkout_proxy = checkout_proxy_url or proxy_url
    if log:
        _detect = _opll_detect_proxy_exit
        def _log(step, proxy, msg):
            c = _detect(proxy)
            prefix = f"[{step}]" + (f" {c}" if c else "")
            log(f"{prefix}: {msg}")
    else:
        _log = lambda *_: None
    for checkout_country, pm_country in opll_combo_attempt_order(requested_country):
        try:
            checkout = opll_create_checkout(access_token, checkout_country, currency_for_country(checkout_country), checkout_proxy)
            _log("checkout", checkout_proxy, f"ok: cs_id={checkout.get('cs_id')} proc={checkout.get('processor_entity')} country={checkout.get('billing_country')} currency={checkout.get('currency')} combo={checkout_country}:{pm_country}")
            stripe = opll_build_stripe_session(proxy_url)
            init_payload = opll_stripe_init(checkout["cs_id"], checkout["billing_country"], checkout["currency"], proxy_url, stripe=stripe, checkout=checkout)
            stripe_hosted_url = str(init_payload.get("stripe_hosted_url") or "").strip()
            if not stripe_hosted_url:
                raise RuntimeError(f"stripe init response missing stripe_hosted_url, keys={sorted(init_payload.keys())}")
            if log:
                stripe_amount, _sa_src = opll_stripe_amount_info(init_payload)
                _log("stripe", proxy_url, f"init ok: amount={stripe_amount} hosted_url={stripe_hosted_url[:80]}")
            hosted_long_url = opll_to_openai_pay_url(stripe_hosted_url)
            stripe_pk = opll_stripe_key_for_checkout(checkout)
            ctx = opll_stripe_context(init_payload)
            if not ctx.get("currency"):
                ctx["currency"] = str(checkout.get("currency") or "").lower()
            stripe_amount, stripe_amount_source = opll_stripe_amount_info(init_payload)
            pm_id = opll_stripe_create_paypal_method(stripe, checkout["cs_id"], ctx, opll_billing_for_country(pm_country), stripe_pk)
            _log("stripe", proxy_url, f"payment_method ok: pm_id={pm_id}")
            _log("confirm", proxy_url, "trying")
            confirm_payload = opll_stripe_confirm(stripe, checkout["cs_id"], pm_id, stripe_pk, init_payload, ctx, checkout, stripe_hosted_url)
            _log("confirm", proxy_url, "ok")
            stripe_redirect_url = opll_redirect_url_after_confirm(access_token, stripe, confirm_payload, checkout["cs_id"], stripe_pk, ctx, checkout, proxy_url)
            is_already_approve = opll_is_paypal_ba_approve_url(stripe_redirect_url)
            _log("redirect", proxy_url, f"url={'approve' if is_already_approve else 'external'} url={stripe_redirect_url[:120]}")
            if is_already_approve:
                provider_url = stripe_redirect_url
            else:
                provider_url = opll_resolve_external_redirect(stripe, stripe_redirect_url)
                _log("approve", proxy_url, f"resolved: url={provider_url[:120]}")
            if not opll_is_paypal_ba_approve_url(provider_url):
                resource_hint = "仅发现 Stripe 资源 URL，未发现 PayPal BA approve 链；" if opll_is_ignored_resource_url(provider_url) else ""
                raise RuntimeError(
                    f"{resource_hint}未提取到最终 PayPal BA approve 链；成功标准必须为 "
                    f"https://www.paypal.com/agreements/approve?ba_token=...；当前结果: {provider_url or stripe_redirect_url}"
                )
            return {
                **checkout,
                "payment_method_country": pm_country,
                "payment_method_id": pm_id,
                "stripe_hosted_url": stripe_hosted_url,
                "stripe_redirect_url": stripe_redirect_url,
                "provider_redirect_url": provider_url,
                "fallback": (checkout_country, pm_country) != (requested_country, requested_country),
                "provider_error": "; ".join(failures),
                "long_url": provider_url or hosted_long_url,
                "stripe_amount": stripe_amount,
                "stripe_amount_source": stripe_amount_source,
            }
        except Exception as exc:
            failures.append(f"{checkout_country}+{pm_country}: {opll_short_error(str(exc))}")
    raise RuntimeError(f"所有组合均未提取到 PayPal BA approve 链；{'; '.join(failures)}")


def generate_opll_hosted_long_link(access_token: str, country: str, currency: str, proxy_url: str = "") -> dict:
    checkout = opll_create_checkout(access_token, country, currency, proxy_url)
    init_payload = opll_stripe_init(checkout["cs_id"], checkout["billing_country"], checkout["currency"], proxy_url, checkout=checkout)
    stripe_hosted_url = str(init_payload.get("stripe_hosted_url") or "").strip()
    if not stripe_hosted_url:
        raise RuntimeError(f"stripe init response missing stripe_hosted_url, keys={sorted(init_payload.keys())}")
    long_url = opll_to_openai_pay_url(stripe_hosted_url) or opll_stripe_checkout_long_url(
        checkout["cs_id"], checkout["billing_country"], checkout.get("processor_entity", "")
    )
    return {**checkout, "stripe_hosted_url": stripe_hosted_url, "long_url": long_url}


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
    found_paid = ""
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            lower_keys = {str(key).lower(): value for key, value in item.items()}
            for key in ["is_paid_subscription_active", "has_active_subscription", "is_plus_user", "is_subscribed"]:
                if key in lower_keys:
                    value = lower_keys[key]
                    if value is True:
                        found_paid = found_paid or f"{key}=true"
                    if value is False:
                        found_free = found_free or f"{key}=false"
            for key in ["subscription_plan", "plan_type", "plan", "account_plan", "product_name", "sku", "name"]:
                value = lower_keys.get(key)
                if isinstance(value, str):
                    text = value.lower()
                    if any(word in text for word in ["team", "enterprise"]):
                        return "team", f"{key}={value}"
                    if any(word in text for word in ["plus", "pro", "chatgptplusplan"]):
                        return "plus", f"{key}={value}"
                    if any(word in text for word in ["free", "none", "no_plan"]):
                        found_free = found_free or f"{key}={value}"
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    if found_paid:
        return "plus", found_paid
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
        self.lock = threading.Lock()
        self.active_sockets: set[socket.socket] = set()
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

    def set_dynamic_proxy(self, dynamic_proxy: str) -> None:
        sockets: list[socket.socket]
        with self.lock:
            self.dynamic_proxy = normalize_proxy_url(dynamic_proxy)
            sockets = list(self.active_sockets)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

    def _track_socket(self, sock: socket.socket) -> None:
        with self.lock:
            self.active_sockets.add(sock)

    def _untrack_socket(self, sock: socket.socket) -> None:
        with self.lock:
            self.active_sockets.discard(sock)

    def _serve(self) -> None:
        assert self.server is not None
        while not self.stop_event.is_set():
            try:
                client, _addr = self.server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _handle_client(self, client: socket.socket) -> None:
        upstream = None
        self._track_socket(client)
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
                self._track_socket(upstream)
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self._relay(client, upstream)
                return
            rewritten = self._rewrite_plain_request(head, method, target, version)
            upstream = self._open_chain_to_target(self._target_from_plain_request(method, target, head))
            self._track_socket(upstream)
            upstream.sendall(rewritten)
            self._relay(client, upstream)
        except Exception:
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except Exception:
                pass
        finally:
            self._untrack_socket(client)
            if upstream:
                self._untrack_socket(upstream)
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
        with self.lock:
            local_proxy = self.local_proxy
            dynamic_proxy = self.dynamic_proxy
        if local_proxy:
            sock = self._connect_proxy(local_proxy)
            self._send_connect(sock, self._proxy_connect_target(dynamic_proxy) if dynamic_proxy else target)
            if dynamic_proxy:
                self._send_connect(sock, target, proxy_url=dynamic_proxy)
            return sock
        if dynamic_proxy:
            sock = self._connect_proxy(dynamic_proxy)
            self._send_connect(sock, target, proxy_url=dynamic_proxy)
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
        r"(?:OpenAI|ChatGPT|verification|verify|code|验证码|登录码|認証コード|検証コード|コード)[^\d]{0,100}(\d{6})",
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
            log(f"尝试邮箱 Token 端点 {endpoint['name']}")
            resp = requests.post(
                endpoint["url"],
                data=data,
                headers={"Accept": "application/json"},
                timeout=10,
                proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            )
            payload = resp.json() if resp.text else {}
            if resp.ok and payload.get("access_token"):
                log(f"邮箱 Token 端点 {endpoint['name']} 成功")
                return str(payload["access_token"])
            msg = payload.get("error_description") or payload.get("error") or f"HTTP {resp.status_code}"
            errors.append(f"{endpoint['name']}: {msg}")
            log(f"邮箱 Token 端点 {endpoint['name']} 失败: {msg}")
        except Exception as exc:
            errors.append(f"{endpoint['name']}: {exc}")
            log(f"邮箱 Token 端点 {endpoint['name']} 异常: {exc}")
    raise RuntimeError("所有邮箱 Token 端点均失败 -> " + " | ".join(errors))


class ProxiedIMAP4SSL(imaplib.IMAP4_SSL):
    def __init__(self, host: str, port: int, proxied_socket: socket.socket, timeout: float | None = None):
        self._proxied_socket = proxied_socket
        super().__init__(host=host, port=port, timeout=timeout)

    def open(self, host: str = "", port: int = 0, timeout: float | None = None):
        self.host = host
        self.port = port
        self.sock = self._proxied_socket
        try:
            self.file = self.sock.makefile("rb")
        except AttributeError:
            pass


class CustomApiOtpReader:
    def __init__(self, account: MailAccount, api_url: str, admin_key: str, log, proxy_url: str = "", poll_interval: int = 5, first_delay: int = 5):
        self.account = account
        self.api_url = api_url
        self.admin_key = admin_key
        self.log = log
        self.proxy_url = proxy_url
        self.poll_interval = max(1, poll_interval)
        self.first_delay = max(0, first_delay)
        self._session = requests.Session()
        if proxy_url:
            self._session.proxies.update({"http": proxy_url, "https": proxy_url})

    def connect(self) -> None:
        self.log(f"自定义邮箱 API 模式就绪: {self.account.email}")

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    def wait_for_code(self, min_timestamp: float, timeout: int = 180) -> str:
        started = time.time()
        last_notice = 0.0
        body = {"adminKey": self.admin_key, "email": self.account.email}
        if self.first_delay > 0:
            self.log(f"等待 {self.first_delay}s 后开始获取验证码...")
            time.sleep(self.first_delay)
        while time.time() - started < timeout:
            try:
                resp = self._session.post(self.api_url, json=body, timeout=15)
                if not resp.ok:
                    self.log(f"自定义邮箱 API 返回 {resp.status_code}: {resp.text[:200]}")
                else:
                    raw_text = resp.text or ""
                    self.log(f"[DEBUG] API={self.api_url} body={body} resp={raw_text[:500]}")
                    payload = resp.json() if raw_text else {}
                    if isinstance(payload, dict):
                        code = self._extract_code_from_payload(payload)
                        if code:
                            self.log(f"收到 OpenAI 验证码: {code}")
                            return code
                        text = str(payload.get("code") or payload.get("verificationCode") or "")
                        if text:
                            code = extract_openai_code(text)
                            if code:
                                self.log(f"收到 OpenAI 验证码(顶层字段): {code}")
                                return code
                        for key in ("body", "text", "content", "message"):
                            val = payload.get(key)
                            if val:
                                code = extract_openai_code(str(val))
                                if code:
                                    self.log(f"收到 OpenAI 验证码({key}): {code}")
                                    return code
                        self.log(f"[DEBUG] API 返回 keys={sorted(payload.keys())} 但未提取到验证码, mail.from={str(payload.get('mail', {}).get('from', ''))[:80]}")
                    elif isinstance(payload, str):
                        code = extract_openai_code(payload)
                        if code:
                            self.log(f"收到 OpenAI 验证码: {code}")
                            return code
            except Exception as exc:
                self.log(f"自定义邮箱 API 请求异常: {exc}")
            if time.time() - last_notice >= 20:
                remain = max(0, int(timeout - (time.time() - started)))
                self.log(f"仍在轮询自定义邮箱 API，剩余约 {remain}s")
                last_notice = time.time()
            time.sleep(self.poll_interval)
        self.log("主轮询超时，尝试备用验证码 API...")
        code = self._try_verification_code_api(timeout=30)
        if code:
            return code
        raise TimeoutError("等待自定义邮箱验证码超时")

    def _extract_code_from_payload(self, payload: dict) -> str:
        code = str(payload.get("code") or payload.get("verificationCode") or "").strip()
        if code and len(code) >= 4:
            return extract_openai_code(code) or code
        mail = payload.get("mail") or {}
        if isinstance(mail, dict):
            for field in ("body", "preview", "text", "html"):
                val = mail.get(field)
                if val:
                    code = extract_openai_code(str(val))
                    if code:
                        return code
        for key in ("body", "text", "content"):
            val = payload.get(key)
            if val:
                code = extract_openai_code(str(val))
                if code:
                    return code
        return ""

    def _build_verification_code_url(self) -> str:
        import urllib.parse
        parsed = urllib.parse.urlparse(self.api_url)
        path = parsed.path.rsplit("/", 1)[0] + "/verification-code"
        return urllib.parse.urlunparse(parsed._replace(path=path))

    def _try_verification_code_api(self, timeout: int = 30) -> str:
        url = self._build_verification_code_url()
        body = {"adminKey": self.admin_key, "email": self.account.email}
        self.log(f"[DEBUG] 尝试备用验证码 API: {url} body={body}")
        started = time.time()
        while time.time() - started < timeout:
            try:
                resp = self._session.post(url, json=body, timeout=10)
                if resp.ok:
                    payload = resp.json() if resp.text else {}
                    code = str(payload.get("code") or payload.get("verificationCode") or "").strip()
                    if code:
                        self.log(f"备用 API 获取到验证码: {code}")
                        return code
                    self.log(f"[DEBUG] 备用API resp={resp.text[:300]}")
            except Exception as exc:
                self.log(f"备用验证码 API 请求异常: {exc}")
            time.sleep(3)
        return ""


class HotmailOtpReader:
    def __init__(self, account: MailAccount, log, proxy_url: str = ""):
        self.account = account
        self.log = log
        self.proxy_url = proxy_url
        self.seen: set[str] = set()
        self.imap: imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        self.log(f"正在连接邮箱取码: {self.account.email}")
        access_token = refresh_hotmail_access_token(self.account, self.log, self.proxy_url)
        auth_string = f"user={self.account.email}\x01auth=Bearer {access_token}\x01\x01"
        if self.proxy_url:
            self.imap = self._connect_imap_via_proxy(self.proxy_url)
        else:
            self.log("正在连接 Outlook IMAP: outlook.office365.com:993")
            self.imap = imaplib.IMAP4_SSL("outlook.office365.com", 993, timeout=20)
            try:
                self.imap.sock.settimeout(20)
            except Exception:
                pass
        self.log("正在进行邮箱 XOAUTH2 认证")
        self.imap.authenticate("XOAUTH2", lambda _: auth_string.encode("utf-8"))
        try:
            self.imap.sock.settimeout(30)
        except Exception:
            pass
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
        try:
            tls_sock.settimeout(20)
        except Exception:
            pass
        return ProxiedIMAP4SSL("outlook.office365.com", 993, tls_sock, timeout=20)

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
            try:
                self.connect()
            except Exception as exc:
                self.log(f"邮箱取码连接失败: {exc}")
                raise
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

    def _select_folder_count(self, folder: str) -> int:
        assert self.imap is not None
        for name in (folder, f'"{folder}"'):
            try:
                status, data = self.imap.select(name, readonly=True)
                if status != "OK":
                    continue
                if data and data[0]:
                    return int(data[0])
                return 0
            except Exception:
                continue
        return -1

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
            msg = email_pkg.message_from_bytes(raw)
            date_header = msg.get("Date")
            try:
                mail_time = parsedate_to_datetime(date_header).timestamp() if date_header else time.time()
            except Exception:
                mail_time = time.time()
            if mail_time + 30 < min_timestamp:
                continue
            subject = decode_header_text(msg.get("Subject"))
            from_addr = decode_header_text(msg.get("From"))
            body = extract_message_text(msg)
            haystack = f"{subject}\n{from_addr}\n{body}"
            if not re.search(r"openai|chatgpt", haystack, flags=re.I):
                continue
            self.seen.add(key)
            code = extract_openai_code(haystack)
            if code:
                self.log(f"收到 OpenAI 验证码: {code}")
                return code
        return ""


class OpenAIJsonAuthFlow:
    def __init__(self, account: MailAccount, log, phone_provider=None, input_callback=None, proxy_url: str = "", custom_api_url: str = "", custom_api_admin_key: str = "", custom_api_poll_interval: int = 5, custom_first_delay: int = 5, custom_password: str = ""):
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
        self.custom_api_url = custom_api_url
        self.custom_api_admin_key = custom_api_admin_key
        self.custom_api_poll_interval = custom_api_poll_interval
        self.custom_first_delay = custom_first_delay
        self.custom_password = custom_password
        self.otp_reader = None

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

    @staticmethod
    def _extract_error_code(response: requests.Response) -> str:
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                return str(error.get("code") or "")
            if isinstance(error, str):
                return error
        except Exception:
            pass
        return ""

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
            raise TurnstileRequired("当前 OpenAI 登录触发 Turnstile，将回退到浏览器模式")
        pow_data = requirements.get("proofofwork") or {}
        proof = None
        if pow_data.get("required") and pow_data.get("seed") and pow_data.get("difficulty"):
            proof = f"gAAAAAB{generate_sentinel_answer(str(pow_data['seed']), str(pow_data['difficulty']))}"
        return json.dumps({"p": proof, "t": None, "c": requirements.get("token"), "id": self.device_id, "flow": flow}, separators=(",", ":"))

    def _authorize_continue(self) -> str:
        try:
            sentinel_token = self._fetch_sentinel_token("authorize_continue")
        except TurnstileRequired:
            self.log("邮箱提交触发 Turnstile，切换到浏览器模式")
            return self._authorize_continue_browser()
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

    @staticmethod
    def _init_fingerprint_context(context, fp):
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
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"15.0.0"',
        })
        context.add_init_script("""
            (() => {
                const fp = __FP__;
                const d = (o, p, v) => { try { Object.defineProperty(o, p, { get: () => v, configurable: true }); } catch (_) {} };
                d(Navigator.prototype, 'webdriver', undefined);
                d(Navigator.prototype, 'platform', fp.platform);
                d(Navigator.prototype, 'vendor', fp.vendor);
                d(Navigator.prototype, 'language', fp.languages[0]);
                d(Navigator.prototype, 'languages', fp.languages);
                d(Navigator.prototype, 'hardwareConcurrency', fp.hardwareConcurrency);
                d(Navigator.prototype, 'deviceMemory', fp.deviceMemory);
                d(Navigator.prototype, 'maxTouchPoints', fp.maxTouchPoints);
                d(Screen.prototype, 'width', fp.screenWidth);
                d(Screen.prototype, 'height', fp.screenHeight);
                d(Screen.prototype, 'availWidth', fp.screenWidth);
                d(Screen.prototype, 'availHeight', fp.screenHeight - 40);
                d(window, 'outerWidth', fp.outerWidth);
                d(window, 'outerHeight', fp.outerHeight);
                d(window, 'devicePixelRatio', fp.deviceScaleFactor);
            })();
        """.replace("__FP__", fp_payload))

    def _authorize_continue_browser(self) -> str:
        cached = get_fingerprint_for_email(self.account.email.lower())
        if cached:
            fp = cached
            self.log(f"使用已保存的浏览器指纹: Chrome/{fp.chrome_major} {fp.locale} {fp.timezone}")
        else:
            fp = generate_register_fingerprint()
            exit_info = _opll_detect_proxy_exit(self.proxy_url)
            if exit_info:
                country = exit_info.split("(")[-1].rstrip(")")
                locale_tz = _proxy_country_to_locale_tz(country)
                if locale_tz:
                    fp.locale = locale_tz[0]
                    fp.languages = [locale_tz[0]]
                    fp.timezone = locale_tz[1]
            save_fingerprint_for_email(self.account.email.lower(), fp)
            self.log(f"浏览器指纹: Chrome/{fp.chrome_major} {fp.viewport_width}x{fp.viewport_height} {fp.locale} {fp.timezone}")
        with sync_playwright() as p:
            proxy_config = {"server": self.proxy_url} if self.proxy_url else None
            browser = p.chromium.launch(
                headless=False,
                proxy=proxy_config,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    f"--lang={fp.locale}",
                    f"--window-size={fp.outer_width},{fp.outer_height}",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=fp.user_agent,
                locale=fp.locale,
                timezone_id=fp.timezone,
                viewport={"width": fp.viewport_width, "height": fp.viewport_height},
                screen={"width": fp.screen_width, "height": fp.screen_height},
                device_scale_factor=fp.device_scale_factor,
            )
            self._init_fingerprint_context(context, fp)
            cookies_for_browser = []
            for cookie in self.session.cookies:
                cookies_for_browser.append({
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                    "httpOnly": False,
                })
            context.add_cookies(cookies_for_browser)
            page = context.new_page()
            try:
                page.goto(f"{AUTH_BASE_URL}/log-in", wait_until="domcontentloaded", timeout=30000)
                if page.url != f"{AUTH_BASE_URL}/log-in" and not page.url.startswith(f"{AUTH_BASE_URL}/log-in"):
                    page.goto(f"{AUTH_BASE_URL}/log-in", wait_until="domcontentloaded", timeout=15000)
                page.wait_for_selector('input[name="email"], input[name="username"], input[type="email"]', timeout=90000)
                page.fill('input[name="email"], input[name="username"], input[type="email"]', self.account.email, timeout=5000)
                page.wait_for_selector('button[type="submit"]', timeout=5000)
                page.click('button[type="submit"]', timeout=5000)
                page.wait_for_load_state("load", timeout=30000)
                page.wait_for_timeout(3000)
                browser_cookies = context.cookies()
                for bc in browser_cookies:
                    self.session.cookies.set(bc["name"], bc["value"], domain=bc["domain"], path=bc.get("path") or "/")
                continue_url = page.url
                self.log(f"浏览器提交邮箱完成，跳转到: {continue_url[:120]}")
                return normalize_auth_continue_url(continue_url)
            except Exception:
                page.screenshot(path="/tmp/turnstile_email_fail.png", full_page=True)
                raise
            finally:
                browser.close()

    def _submit_password(self) -> str:
        try:
            sentinel_token = self._fetch_sentinel_token("authorize_continue")
        except TurnstileRequired:
            self.log("密码提交触发 Turnstile，切换到浏览器模式")
            return self._submit_password_browser()
        response = self.session.post(
            AUTH_AUTHORIZE_CONTINUE_URL,
            headers=self._headers({
                "content-type": "application/json",
                "openai-sentinel-token": sentinel_token,
            }),
            json={"username": {"kind": "email", "value": self.account.email}, "password": self.custom_password},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"Password登录请求失败: {self._format_error_response(response)}")
        return normalize_auth_continue_url(str(response.json().get("continue_url") or ""))

    def _submit_password_browser(self) -> str:
        cached = get_fingerprint_for_email(self.account.email.lower())
        if cached:
            fp = cached
            self.log(f"使用已保存的浏览器指纹: Chrome/{fp.chrome_major} {fp.locale} {fp.timezone}")
        else:
            fp = generate_register_fingerprint()
            exit_info = _opll_detect_proxy_exit(self.proxy_url)
            if exit_info:
                country = exit_info.split("(")[-1].rstrip(")")
                locale_tz = _proxy_country_to_locale_tz(country)
                if locale_tz:
                    fp.locale = locale_tz[0]
                    fp.languages = [locale_tz[0]]
                    fp.timezone = locale_tz[1]
            save_fingerprint_for_email(self.account.email.lower(), fp)
            self.log(f"浏览器指纹: Chrome/{fp.chrome_major} {fp.viewport_width}x{fp.viewport_height} {fp.locale} {fp.timezone}")
        with sync_playwright() as p:
            proxy_config = {"server": self.proxy_url} if self.proxy_url else None
            browser = p.chromium.launch(
                headless=False,
                proxy=proxy_config,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    f"--lang={fp.locale}",
                    f"--window-size={fp.outer_width},{fp.outer_height}",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=fp.user_agent,
                locale=fp.locale,
                timezone_id=fp.timezone,
                viewport={"width": fp.viewport_width, "height": fp.viewport_height},
                screen={"width": fp.screen_width, "height": fp.screen_height},
                device_scale_factor=fp.device_scale_factor,
            )
            self._init_fingerprint_context(context, fp)
            cookies_for_browser = []
            for cookie in self.session.cookies:
                cookies_for_browser.append({
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                    "httpOnly": False,
                })
            context.add_cookies(cookies_for_browser)
            page = context.new_page()
            try:
                page.goto(f"{AUTH_BASE_URL}/log-in/password", wait_until="domcontentloaded", timeout=30000)
                if page.url != f"{AUTH_BASE_URL}/log-in/password" and not page.url.startswith(f"{AUTH_BASE_URL}/log-in/password"):
                    page.goto(f"{AUTH_BASE_URL}/log-in/password", wait_until="domcontentloaded", timeout=15000)
                page.wait_for_function("""() => {
                    const buttons = Array.from(document.querySelectorAll('button, a'));
                    return buttons.some(el => /one.time|code|ワンタイム|コード/i.test(el.textContent || ''));
                }""", timeout=90000)
                page.evaluate("""() => {
                    const buttons = Array.from(document.querySelectorAll('button, a'));
                    const matches = buttons.filter(el => /one.time|code|ワンタイム|コード/i.test(el.textContent || ''));
                    if (matches.length > 0) matches[matches.length - 1].click();
                }""")
                self.email_otp_requested_at = time.time()
                nav_started = time.time()
                while time.time() - nav_started < 90:
                    try:
                        page.wait_for_url(re.compile(r"(email-verification|add-phone|oauth)"), timeout=5000)
                        break
                    except Exception:
                        page_text = ""
                        try:
                            page_text = page.locator("body").inner_text(timeout=2000)
                        except Exception:
                            pass
                        if "turnstile" in (page_text or "").lower() or "cloudflare" in (page_text or "").lower():
                            self.log("点击后触发 Cloudflare Turnstile 验证，等待放行...")
                            page.wait_for_function(
                                "() => !/turnstile|cloudflare/i.test(document.body.innerText || '')",
                                timeout=60000,
                            )
                            page.wait_for_timeout(3000)
                        if not page.url.startswith(f"{AUTH_BASE_URL}/log-in/password"):
                            break
                        page.wait_for_timeout(3000)
                else:
                    page.screenshot(path="/tmp/turnstile_no_navigation.png", full_page=True)
                    raise RuntimeError("点击一次性验证码后页面90s未跳转，可能被 Cloudflare 拦截")
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                browser_cookies = context.cookies()
                for bc in browser_cookies:
                    self.session.cookies.set(bc["name"], bc["value"], domain=bc["domain"], path=bc.get("path") or "/")
                continue_url = page.url
                self.log(f"浏览器点击一次性验证码登录，跳转到: {continue_url[:120]}")
                return normalize_auth_continue_url(continue_url)
            except Exception:
                page.screenshot(path="/tmp/turnstile_password_fail.png", full_page=True)
                raise
            finally:
                browser.close()

    def _handle_phone_otp_channel(self) -> str:
        self.log("处理手机验证码")

        headers = self._headers({"content-type": "application/json", "accept": "application/json"})
        phone_number = ""
        phone_entry = None

        send_resp = self.session.post(AUTH_PHONE_OTP_SEND_URL, json={"channel": "sms"}, headers=headers, timeout=30)
        if send_resp.ok:
            try:
                send_data = send_resp.json()
            except Exception as exc:
                self.log(f"phone-otp/send JSON解析失败: {exc} raw={send_resp.text[:200]}")
                send_data = {}
            phone_number = self._extract_phone_from_send_response(send_data)
            if not phone_number:
                self.log(f"phone-otp/send 响应未含手机号 keys={list(send_data.keys())} text={send_resp.text[:300]}")
                phone_number = self._read_bound_phone_from_page()
            self.log(f"已绑定手机号{' ' + phone_number if phone_number else '(未知)'}，短信验证码已发送")
        else:
            self.log(f"phone-otp/send 失败: {send_resp.status_code} {send_resp.text[:300]}")
            error_code = self._extract_error_code(send_resp)
            if error_code == "fraud_guard":
                bound_phone = self._read_bound_phone_from_page()
                if bound_phone:
                    raise RuntimeError(f"已绑定手机号 {bound_phone} 被OpenAI风控标记，无法发送验证码。请等待一段时间后重试，或联系OpenAI客服。")
                raise RuntimeError("该账号已绑定的手机号被OpenAI风控标记，无法发送验证码。请等待一段时间后重试，或联系OpenAI客服。")
            if self.phone_provider:
                phone_entry = self.phone_provider("next", self.account.email, {"country": "US"})
            if phone_entry:
                phone_number = str(phone_entry.get("number") or "").strip()
                self.log(f"使用手机号: {phone_number}")

            if not phone_number and self.input_callback:
                phone_number = self.input_callback("phone_number", self.account.email,
                    "该账号需要绑定手机号\n请输入手机号（含国家代码）")
                if phone_number:
                    phone_number = phone_number.strip()

            if not phone_number:
                raise RuntimeError(
                    "该账号需要绑定手机号才能完成授权。"
                    "请在邮箱列表填写 auth_phone_number，或导入手机号池，或手动输入。"
                )

            send_resp = self.session.post(
                AUTH_PHONE_OTP_SEND_URL,
                json={"phone": phone_number, "channel": "sms"},
                headers=headers,
                timeout=30,
            )
            if not send_resp.ok:
                if phone_entry:
                    self.phone_provider("bad", self.account.email, {**phone_entry, "error": self._format_error_response(send_resp)})
                raise RuntimeError(f"发送手机验证码失败: {send_resp.status_code} {self._format_error_response(send_resp)}")
            self.log(f"短信验证码已发送至 {phone_number}")

        code = None
        if phone_entry:
            code = self.phone_provider("code", self.account.email, phone_entry)
        if not code and self.input_callback:
            if phone_number:
                prompt = f"验证码已发送至 {phone_number}\n请输入收到的短信验证码"
            else:
                prompt = "验证码已发送至您绑定的手机号\n请输入收到的短信验证码"
            code = self.input_callback("sms_code", self.account.email, prompt)
        if not code:
            raise RuntimeError("未收到手机验证码")
        self.log(f"获取到手机验证码: {code}")

        validate_resp = self.session.post(
            AUTH_PHONE_OTP_VALIDATE_URL,
            json={"code": str(code).strip()},
            headers=headers,
            timeout=30,
        )
        if not validate_resp.ok:
            if phone_entry:
                self.phone_provider("bad", self.account.email, {**phone_entry, "error": self._format_error_response(validate_resp)})
            raise RuntimeError(f"手机验证码验证失败: {validate_resp.status_code} {self._format_error_response(validate_resp)}")

        try:
            data = validate_resp.json()
        except Exception:
            data = {}
        continue_url = data.get("continue_url") or ""
        if not continue_url:
            result = data.get("result", {})
            if isinstance(result, dict):
                continue_url = result.get("url") or ""
            elif isinstance(result, str):
                continue_url = result
        if not continue_url:
            page_info = data.get("page", {})
            if isinstance(page_info, dict):
                payload = page_info.get("payload", {})
                if isinstance(payload, dict):
                    continue_url = payload.get("url") or ""

        self.log(f"手机验证码验证成功，跳转到: {continue_url[:120]}")
        return normalize_auth_continue_url(continue_url)

    def _read_bound_phone_from_page(self) -> str:
        for page_path in ["/phone-otp/select-channel", "/phone-otp/channel"]:
            try:
                resp = self.session.get(
                    f"{AUTH_BASE_URL}{page_path}",
                    headers=self._headers({"accept": "text/html"}),
                    timeout=15,
                )
                html = resp.text or ""
                self.log(f"手机号页面 {page_path} status={resp.status_code} len={len(html)}")

                for pattern in [
                    r'"phone"\s*:\s*"(\+[\d\-]+)"',
                    r'"maskedPhone"\s*:\s*"([^"]*)"',
                    r'"number"\s*:\s*"(\+[\d\-]+)"',
                    r'phoneNumber["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'data-phone-number\s*=\s*["\']([^"\']+)["\']',
                    r'phone["\']?\s*[:=]\s*["\']?(\+[\d\-\s]+)["\']?',
                    r'(\+[\d\s\-\*\(\)]+\d{2,6})\*?',
                ]:
                    match = re.search(pattern, html, flags=re.I)
                    if match:
                        result = match.group(1) if len(match.groups()) >= 1 else match.group(0).strip()
                        self.log(f"从页面 {page_path} 正则匹配到手机号: {result} (pattern: {pattern[:40]})")
                        return result
                for script_m in re.finditer(r'<script[^>]*>(.*?)</script>', html, flags=re.I | re.S):
                    try:
                        data = json.loads(script_m.group(1).strip())
                    except Exception:
                        continue
                    phone = self._find_phone_in_json(data)
                    if phone:
                        self.log(f"从页面 {page_path} script JSON 提取到手机号: {phone}")
                        return phone
                self.log(f"页面 {page_path} 未匹配到手机号 text={html[:500]}")
            except Exception as exc:
                self.log(f"手机号页面 {page_path} 请求失败: {exc}")
                continue
        self.log("所有手机号页面均未能提取到号码")
        return ""

    @staticmethod
    def _find_phone_in_json(data, depth: int = 0) -> str:
        if depth > 5:
            return ""
        if isinstance(data, dict):
            for key in ("phone", "phone_number", "maskedPhone", "masked_phone", "number"):
                val = data.get(key)
                if isinstance(val, str) and re.search(r"\d", val):
                    return val.strip()
            for val in data.values():
                result = OpenAIJsonAuthFlow._find_phone_in_json(val, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = OpenAIJsonAuthFlow._find_phone_in_json(item, depth + 1)
                if result:
                    return result
        return ""

    @staticmethod
    def _extract_phone_from_send_response(data: dict) -> str:
        for key in ("phone", "phone_number", "masked_phone", "maskedPhone"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for container_key in ("result", "page", "payload"):
            container = data.get(container_key)
            if isinstance(container, dict):
                for key in ("phone", "phone_number", "masked_phone", "maskedPhone"):
                    val = container.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        return ""

    def _handle_add_phone(self) -> str:
        self.log("处理添加手机号，先检测是否已绑定")

        headers = self._headers({"content-type": "application/json", "accept": "application/json"})

        probe_resp = self.session.post(AUTH_PHONE_OTP_SEND_URL, json={"channel": "sms"}, headers=headers, timeout=30)
        if probe_resp.ok:
            self.log("add-phone页面检测到已绑定手机号，切换到phone-otp流程")
            try:
                send_data = probe_resp.json()
            except Exception:
                send_data = {}
            phone_number = self._extract_phone_from_send_response(send_data)
            if not phone_number:
                self.log(f"phone-otp/send 响应未含手机号 keys={list(send_data.keys())} text={probe_resp.text[:300]}")
                phone_number = self._read_bound_phone_from_page()
            self.log(f"已绑定手机号{' ' + phone_number if phone_number else '(未知)'}，短信验证码已发送")

            code = None
            if self.input_callback:
                if phone_number:
                    prompt = f"验证码已发送至 {phone_number}\n请输入收到的短信验证码"
                else:
                    prompt = "验证码已发送至您绑定的手机号\n请输入收到的短信验证码"
                code = self.input_callback("sms_code", self.account.email, prompt)

            if not code:
                raise RuntimeError("未收到手机验证码")
            self.log(f"获取到手机验证码: {code}")

            validate_resp = self.session.post(
                AUTH_PHONE_OTP_VALIDATE_URL,
                json={"code": str(code).strip()},
                headers=headers,
                timeout=30,
            )
            if not validate_resp.ok:
                raise RuntimeError(f"手机验证码验证失败: {validate_resp.status_code} {self._format_error_response(validate_resp)}")
            try:
                data = validate_resp.json()
            except Exception:
                data = {}
            continue_url = data.get("continue_url") or data.get("redirect_url") or ""
            if not continue_url:
                result = data.get("result", {})
                if isinstance(result, dict):
                    continue_url = result.get("url") or ""
                elif isinstance(result, str):
                    continue_url = result
            self.log(f"手机验证码验证成功，跳转到: {continue_url[:120]}")
            return normalize_auth_continue_url(continue_url) or AUTH_WORKSPACE_SELECT_URL

        error_code = self._extract_error_code(probe_resp)
        if error_code == "fraud_guard":
            bound_phone = self._read_bound_phone_from_page()
            if bound_phone:
                raise RuntimeError(f"已绑定手机号 {bound_phone} 被OpenAI风控标记，无法发送验证码。请等待一段时间后重试，或联系OpenAI客服。")
            raise RuntimeError("该账号已绑定的手机号被OpenAI风控标记，无法发送验证码。请等待一段时间后重试，或联系OpenAI客服。")

        self.log(f"phone-otp/send 探测失败: {probe_resp.status_code} {probe_resp.text[:200]}，需要用户提供手机号")

        phone_number = ""
        phone_entry = None

        if self.phone_provider:
            while not phone_number:
                phone_entry = self.phone_provider("next", self.account.email, {"country": ""})
                if not phone_entry:
                    break
                candidate = str(phone_entry.get("number") or "").strip()
                if not candidate:
                    break
                self.log(f"add-phone 尝试手机号: {candidate}")
                send_resp = self.session.post(
                    AUTH_PHONE_SEND_URL,
                    json={"phone": candidate},
                    headers=headers,
                    timeout=30,
                )
                if send_resp.ok:
                    phone_number = candidate
                    self.log(f"add-phone 验证码已发送至 {phone_number}")
                    break
                err = self._extract_error_code(send_resp)
                err_msg = self._format_error_response(send_resp)
                if err == "fraud_guard":
                    self.log(f"手机号 {candidate} 被风控，换号重试")
                    self.phone_provider("bad", self.account.email, {**phone_entry, "error": "fraud_guard"})
                    continue
                self.phone_provider("bad", self.account.email, {**phone_entry, "error": err_msg})
                raise RuntimeError(f"发送 add-phone 验证码失败: {err_msg}")
            if phone_number:
                pass
            else:
                self.log("手机号池已用完或无可用号码")

        if not phone_number and self.input_callback:
            phone_number = self.input_callback("phone_number", self.account.email,
                "该账号需要添加手机号\n请输入手机号（含国家代码）")
            if phone_number:
                phone_number = phone_number.strip()

        if not phone_number:
            raise RuntimeError("该账号需要添加手机号。请在邮箱列表填写 auth_phone_number，或导入手机号池，或手动输入。")

        if not phone_entry:
            self.log(f"add-phone 发送验证码至: {phone_number}")
            send_resp = self.session.post(AUTH_PHONE_SEND_URL, json={"phone": phone_number}, headers=headers, timeout=30)
            if not send_resp.ok:
                raise RuntimeError(f"发送 add-phone 验证码失败: {send_resp.status_code} {self._format_error_response(send_resp)}")

        code = None
        if phone_entry:
            code = self.phone_provider("code", self.account.email, phone_entry)
        if not code and self.input_callback:
            code = self.input_callback("sms_code", self.account.email,
                f"请输入 {phone_number} 收到的短信验证码")
        if not code:
            raise RuntimeError("未提供短信验证码")
        self.log(f"用户输入短信验证码: {code}")

        validate_resp = self.session.post(
            AUTH_PHONE_OTP_VALIDATE_URL,
            json={"code": str(code).strip()},
            headers=headers,
            timeout=30,
        )
        if not validate_resp.ok:
            raise RuntimeError(f"add-phone 验证码验证失败: {validate_resp.status_code} {self._format_error_response(validate_resp)}")

        try:
            data = validate_resp.json()
        except Exception:
            data = {}
        continue_url = data.get("continue_url") or data.get("redirect_url") or ""
        if not continue_url:
            result = data.get("result", {})
            if isinstance(result, dict):
                continue_url = result.get("url") or ""
            elif isinstance(result, str):
                continue_url = result
        return normalize_auth_continue_url(continue_url) or AUTH_WORKSPACE_SELECT_URL

    def _select_workspace(self, consent_url: str) -> str:
        self.log("选择非个人工作空间")
        resp = self.session.get(consent_url, headers=self._headers({"accept": "text/html"}), timeout=30)
        html = resp.text or ""

        ws_id = ""
        ws_name = ""

        for script_m in re.finditer(r'<script[^>]*>(.*?)</script>', html, flags=re.I | re.S):
            content = script_m.group(1).strip()
            if not content:
                continue
            try:
                data = json.loads(content)
            except Exception:
                continue
            raw = self._find_workspace_list_in_json(data)
            if not raw:
                continue
            ws_id, ws_name = self._pick_non_personal_workspace(raw)
            if ws_id:
                break

        if not ws_id:
            for m in re.finditer(
                r'(?:data-workspace-id|data-id|data-type|value)\s*=\s*"([^"]*org-[^"]+|[^"]{20,})"',
                html, flags=re.I,
            ):
                ws_id = m.group(1)
                break

        if not ws_id:
            for name_m in re.finditer(r'(?i)(?:workspace|account|org)\w*\s*[:=]\s*"([\w-]{20,})"', html):
                ws_id = name_m.group(1)
                break

        if not ws_id:
            self.log("HTML未解析到工作空间，尝试API获取工作空间列表")
            raw = self._fetch_workspace_list_api()
            if raw:
                ws_id, ws_name = self._pick_non_personal_workspace(raw)

        if not ws_id:
            self.log("未找到工作空间ID，使用页面默认选中项直接提交")
            headers = self._headers({"content-type": "application/json", "accept": "application/json"})
            resp = self.session.post(AUTH_WORKSPACE_SELECT_URL, json={}, headers=headers, timeout=30)
            if not resp.ok:
                raise RuntimeError(f"工作空间选择失败: {resp.status_code} {self._format_error_response(resp)}")
            try:
                data = resp.json()
            except Exception:
                data = {}
            return normalize_auth_continue_url(data.get("continue_url") or data.get("redirect_url") or "")

        self.log(f"选择工作空间: {ws_name or ws_id} ({ws_id})")
        headers = self._headers({"content-type": "application/json", "accept": "application/json"})
        resp = self.session.post(AUTH_WORKSPACE_SELECT_URL, json={"workspace_id": ws_id}, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"工作空间选择失败: {resp.status_code} {self._format_error_response(resp)}")
        try:
            data = resp.json()
        except Exception:
            data = {}
        continue_url = data.get("continue_url") or data.get("redirect_url") or ""
        if not continue_url:
            result = data.get("result", {})
            if isinstance(result, dict):
                continue_url = result.get("url") or ""
            elif isinstance(result, str):
                continue_url = result
        self.log(f"已选择工作空间，跳转到: {continue_url[:120]}")
        return normalize_auth_continue_url(continue_url)

    @staticmethod
    def _find_workspace_list_in_json(data, depth: int = 0) -> list | None:
        if depth > 6:
            return None
        if isinstance(data, dict):
            for key in ("workspaces", "accounts", "workspaceList", "orgs", "organizations"):
                val = data.get(key)
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return val
            for val in data.values():
                result = OpenAIJsonAuthFlow._find_workspace_list_in_json(val, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = OpenAIJsonAuthFlow._find_workspace_list_in_json(item, depth + 1)
                if result:
                    return result
        return None

    @staticmethod
    def _pick_non_personal_workspace(workspaces: list) -> tuple[str, str]:
        for ws in workspaces:
            if not isinstance(ws, dict):
                continue
            name = str(ws.get("name") or ws.get("display_name") or "").lower()
            if any(kw in name for kw in ("personal", "person", "个人", "私人", "individual")):
                continue
            ws_id = str(ws.get("id") or ws.get("workspace_id") or "")
            ws_name = str(ws.get("name") or "")
            if ws_id:
                return ws_id, ws_name
        if workspaces and isinstance(workspaces[0], dict):
            ws = workspaces[0]
            return str(ws.get("id") or ws.get("workspace_id") or ""), str(ws.get("name") or "")
        return "", ""

    def _fetch_workspace_list_api(self) -> list | None:
        for api_url in [
            f"{AUTH_BASE_URL}/api/accounts",
            f"{AUTH_BASE_URL}/api/accounts/workspaces",
        ]:
            try:
                resp = self.session.get(api_url, headers=self._headers({"accept": "application/json"}), timeout=15)
                if not resp.ok:
                    continue
                data = resp.json()
            except Exception:
                continue
            if isinstance(data, dict):
                ws = data.get("workspaces") or data.get("accounts") or data.get("data") or data.get("results")
                if isinstance(ws, list):
                    self.log(f"通过 {api_url} 获取到 {len(ws)} 个工作空间")
                    return ws
            if isinstance(data, list):
                self.log(f"通过 {api_url} 获取到 {len(data)} 个工作空间")
                return data
        return None

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

    @staticmethod
    def _is_phone_otp_url(url: str) -> bool:
        return url.startswith(f"{AUTH_BASE_URL}/phone-otp") or url.startswith(f"{AUTH_BASE_URL}/api/accounts/phone-otp") or "/phone-verification" in url

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
                if self._is_phone_otp_url(next_url):
                    current_url = next_url
                    continue
                if next_url.startswith(f"{AUTH_BASE_URL}/add-phone"):
                    current_url = self._handle_add_phone()
                    continue
                if next_url.startswith(f"{AUTH_BASE_URL}/sign-in-with-chatgpt"):
                    current_url = self._select_workspace(next_url)
                    continue
                if next_url.startswith(DEFAULT_REDIRECT_URI):
                    return self._extract_auth_result(next_url)
                current_url = next_url
                continue
            if self._is_phone_otp_url(response.url):
                current_url = self._handle_phone_otp_channel()
                continue
            if response.url.startswith(f"{AUTH_BASE_URL}/add-phone"):
                current_url = self._handle_add_phone()
                continue
            if response.url.startswith(f"{AUTH_BASE_URL}/sign-in-with-chatgpt"):
                current_url = self._select_workspace(response.url)
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

    def _send_email_otp(self):
        self.email_otp_requested_at = time.time()
        headers = self._headers({
            "content-type": "application/json",
            "accept": "application/json",
        })
        resp = self.session.post(AUTH_EMAIL_OTP_SEND_URL, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"发送邮箱验证码失败: {resp.status_code} {self._format_error_response(resp)}")
        try:
            data = resp.json()
        except Exception:
            data = {}
        continue_url = data.get("continue_url") or ""
        if not continue_url:
            page_info = data.get("page", {})
            if isinstance(page_info, dict):
                payload = page_info.get("payload", {})
                if isinstance(payload, dict):
                    continue_url = payload.get("url") or ""
        if not continue_url:
            result = data.get("result", {})
            if isinstance(result, dict):
                continue_url = result.get("url") or ""
            elif isinstance(result, str):
                continue_url = result
        self.log(f"发送邮箱验证码成功，跳转到: {continue_url[:120]}")
        return normalize_auth_continue_url(continue_url)

    def _email_otp_validate(self):
        self.log("等待邮箱验证码")
        if not self.otp_reader:
            if self.account.mail_provider == "custom_api":
                self.otp_reader = CustomApiOtpReader(
                    self.account, self.custom_api_url, self.custom_api_admin_key,
                    self.log, self.proxy_url, self.custom_api_poll_interval, self.custom_first_delay)
            else:
                self.otp_reader = HotmailOtpReader(self.account, self.log, self.proxy_url)

        code = self.otp_reader.wait_for_code(self.email_otp_requested_at)
        self.log(f"获取到邮箱验证码: {code}")

        headers = self._headers({
            "content-type": "application/json",
            "accept": "application/json",
        })
        resp = self.session.post(AUTH_EMAIL_OTP_VALIDATE_URL, json={"code": code}, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"邮箱验证码验证失败: {resp.status_code} {self._format_error_response(resp)}")

        try:
            data = resp.json()
        except Exception:
            data = {}
        continue_url = data.get("continue_url") or ""
        if not continue_url:
            result = data.get("result", {})
            if isinstance(result, dict):
                continue_url = result.get("url") or ""
            elif isinstance(result, str):
                continue_url = result
        if not continue_url:
            page_info = data.get("page", {})
            if isinstance(page_info, dict):
                payload = page_info.get("payload", {})
                if isinstance(payload, dict):
                    continue_url = payload.get("url") or ""

        self.log(f"邮箱验证码验证成功，跳转到: {continue_url[:120]}")
        try:
            self.otp_reader.close()
        except Exception:
            pass
        return normalize_auth_continue_url(continue_url)

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
            f"{AUTH_BASE_URL}/log-in/password",
            f"{AUTH_BASE_URL}/email-verification",
            f"{AUTH_BASE_URL}/sign-in-with-chatgpt/codex/consent",
            f"{AUTH_BASE_URL}/add-phone",
        }
        if response.url not in allowed_start_urls and not response.url.startswith(f"{AUTH_BASE_URL}/add-phone") and not self._is_phone_otp_url(response.url):
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
            if self.custom_password:
                self.log("提交密码")
                continue_url = self._submit_password()
            else:
                self.log("密码页, 改用一次性验证码登录")
                continue_url = self._send_email_otp()
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
    def __init__(self, account: MailAccount, payment_mode: str, headless: bool, register_proxy: ProxyConfig, extract_proxy: ProxyConfig, log, phone_provider=None, custom_api_url: str = "", custom_api_admin_key: str = "", custom_api_poll_interval: int = 5, custom_password: str = "", custom_first_delay: int = 5):
        self.account = account
        self.payment_mode = payment_mode
        self.headless = headless
        self.register_proxy = register_proxy
        self.extract_proxy = extract_proxy
        self.log = log
        self.phone_provider = phone_provider
        self.custom_api_url = custom_api_url
        self.custom_api_admin_key = custom_api_admin_key
        self.custom_api_poll_interval = custom_api_poll_interval
        self.custom_password = custom_password
        self.custom_first_delay = custom_first_delay
        self.active_register_phone: dict | None = None
        self.otp_reader: HotmailOtpReader | CustomApiOtpReader | None = None
        cached = get_fingerprint_for_email(self.account.email.lower())
        if cached:
            self.fingerprint = cached
            self.log(f"使用已保存的浏览器指纹: {cached.chrome_major} {cached.locale} {cached.timezone}")
        else:
            self.fingerprint = generate_register_fingerprint()
            save_fingerprint_for_email(self.account.email.lower(), self.fingerprint)

    def _mark_email_used(self) -> None:
        if self.account.mail_provider != "custom_api" or not self.custom_api_url:
            return
        try:
            base = self.custom_api_url.rstrip("/")
            idx = base.rfind("/api/")
            if idx < 0:
                self.log(f"自定义邮箱 API URL 格式异常，跳过标记已使用: {self.custom_api_url}")
                return
            mark_url = base[:idx] + "/api/admin/credential/state"
            body = {"adminKey": self.custom_api_admin_key, "email": self.account.email, "used": True}
            resp = requests.post(mark_url, json=body, timeout=15)
            self.log(f"标记邮箱已使用 {'OK' if resp.ok else f'HTTP {resp.status_code}'}: {self.account.email}")
        except Exception as exc:
            self.log(f"标记邮箱已使用失败: {exc}")

    def run(self) -> dict:
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
                self.log("注册完成，当前窗口保持打开，新开标签页获取 session 信息")
                result = self._extract_session_info(register_context)
                self._mark_email_used()
                old_session = KEPT_REGISTER_BROWSER_SESSIONS.pop(self.account.email.lower(), None)
                if old_session:
                    try:
                        old_session[0].close()
                        old_session[1].close()
                    except Exception:
                        pass
                KEPT_REGISTER_BROWSER_SESSIONS[self.account.email.lower()] = (register_context, register_browser, self.register_proxy.dynamic_proxy)
                register_context = None
                register_browser = None
                return result
            finally:
                if self.otp_reader:
                    self.otp_reader.close()
                self._close_browser(register_context, register_browser)
                self._close_browser(extract_context, extract_browser)

    def run_team(self) -> dict:
        cached = get_fingerprint_for_email(self.account.email.lower())
        if cached:
            self.fingerprint = cached
        else:
            self.fingerprint = generate_team_fingerprint()
            save_fingerprint_for_email(self.account.email.lower(), self.fingerprint)
        with sync_playwright() as p:
            browser = None
            context = None
            try:
                browser, context = self._new_browser_context(p, self.register_proxy)
                context.clear_cookies()
                self.log(
                    f"Team 浏览器指纹: Chrome/{self.fingerprint.chrome_major} "
                    f"{self.fingerprint.viewport_width}x{self.fingerprint.viewport_height} "
                    f"{self.fingerprint.locale} {self.fingerprint.timezone} "
                    f"cpu={self.fingerprint.hardware_concurrency} mem={self.fingerprint.device_memory}"
                )
                page = context.new_page()
                self._log_browser_proxy_status(page, self.register_proxy, "Team注册浏览器代理")
                self._register_team_sso(page, context)
                record = self._authorize_rt_from_browser(context, page)
                self.log("Team RT 获取成功")
                self._mark_email_used()
                old_session = KEPT_REGISTER_BROWSER_SESSIONS.pop(self.account.email.lower(), None)
                if old_session:
                    try:
                        old_session[0].close()
                        old_session[1].close()
                    except Exception:
                        pass
                KEPT_REGISTER_BROWSER_SESSIONS[self.account.email.lower()] = (context, browser, self.register_proxy.dynamic_proxy)
                context = None
                browser = None
                session_payload = self._session_payload_from_record(record)
                return {
                    "url": "",
                    "access_token": str(record.get("access_token") or ""),
                    "session_json": json.dumps(session_payload, ensure_ascii=False, indent=2),
                    "storage_state_json": "",
                    "openai_rt": str(record.get("refresh_token") or ""),
                }
            finally:
                self._close_browser(context, browser)

    def relink(self) -> dict:
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
                if self.otp_reader:
                    self.otp_reader.close()
                self._close_browser(login_context, login_browser)
                self._close_browser(extract_context, extract_browser)

    def _new_browser_context(self, p, proxy: ProxyConfig, storage_state: dict | None = None):
        browser = p.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--lang={self.fingerprint.locale}",
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

    def _register_team_sso(self, page, context) -> None:
        self.log(f"开始 Team SSO 注册: {self.account.email}")
        page.goto(CHATGPT_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        signin_url = self._create_openai_signin_url(context)
        page.goto(signin_url, wait_until="domcontentloaded", timeout=90000)
        self.log("已打开 Team SSO 注册页，准备填写随机邮箱")
        deadline = time.time() + 600
        route_error_retries = 0
        workspace_clicked = False
        approve_clicked = False
        last_wait_notice = 0.0
        bad_gateway_refreshes = 0
        while time.time() < deadline:
            refreshed, bad_gateway_refreshes = self._refresh_bad_gateway_if_visible(page, bad_gateway_refreshes, "Team SSO")
            if refreshed:
                time.sleep(3)
                continue
            error_text = self._detect_route_error(page)
            if error_text:
                if route_error_retries < 3 and self._retry_route_error(page):
                    route_error_retries += 1
                    self.log(f"Team SSO 页面超时，已点击重试 ({route_error_retries}/3)")
                    time.sleep(5)
                    continue
                raise RuntimeError(f"Team SSO 页面错误，通常是代理/风控导致接口超时: {error_text}")
            if self._complete_team_onboarding_if_visible(page):
                time.sleep(2)
                continue
            if self._has_chatgpt_session(page):
                if self._team_onboarding_pending(page):
                    if time.time() - last_wait_notice >= 15:
                        self.log("Team SSO 已登录，继续等待 onboarding 完成")
                        last_wait_notice = time.time()
                    time.sleep(2)
                    continue
                self.log("Team SSO 注册完成，已获得 ChatGPT 会话")
                return
            if not approve_clicked and self._approve_sso_login_if_visible(page):
                approve_clicked = True
                self._wait_team_sso_progress(page, "批准登录后跳转", 90)
                continue
            if not workspace_clicked and self._select_team_workspace_if_visible(page):
                workspace_clicked = True
                self._wait_team_sso_progress(page, "工作空间选择后跳转", 90)
                continue
            if self._fill_email_if_visible(page):
                self._wait_team_sso_progress(page, "提交 Team 邮箱后跳转", 60)
                continue
            if time.time() - last_wait_notice >= 15:
                self.log(f"Team SSO 等待页面推进中: {page.url[:100]}")
                last_wait_notice = time.time()
            time.sleep(2)
        raise TimeoutError("Team SSO 注册流程超时；如果浏览器停在人机验证或异常页面，请手动处理后重试")

    def _wait_team_sso_progress(self, page, label: str, timeout: int) -> None:
        started = time.time()
        start_url = page.url
        last_notice = 0.0
        bad_gateway_refreshes = 0
        while time.time() - started < timeout:
            refreshed, bad_gateway_refreshes = self._refresh_bad_gateway_if_visible(page, bad_gateway_refreshes, label)
            if refreshed:
                start_url = page.url
                time.sleep(3)
                continue
            if self._has_chatgpt_session(page):
                return
            current_url = page.url
            if current_url != start_url:
                self.log(f"{label}: 已跳转到 {current_url[:100]}")
                return
            if self._page_has_text(page, ["批准登录", "Approve login", "Approve sign-in", "Verify it's you", "验证是您本人", "sign-in-consent", "callback"]):
                return
            if time.time() - last_notice >= 15:
                remain = max(0, int(timeout - (time.time() - started)))
                self.log(f"{label}: 仍在等待页面响应，剩余约 {remain}s")
                last_notice = time.time()
            time.sleep(1)
        self.log(f"{label}: 等待 {timeout}s 未检测到跳转，继续轮询当前页面")

    def _refresh_bad_gateway_if_visible(self, page, refresh_count: int, label: str) -> tuple[bool, int]:
        try:
            title = page.title(timeout=1000)
        except Exception:
            title = ""
        try:
            body = page.locator("body").inner_text(timeout=1000)
        except Exception:
            body = ""
        text = f"{title}\n{body}"
        if not re.search(r"Bad gateway|Error code 502|Host\s+Error|HTTP\s*502", text, flags=re.I):
            return False, refresh_count
        if refresh_count >= 8:
            raise RuntimeError(f"{label}: 连续检测到 Bad gateway/502，已刷新 {refresh_count} 次仍未恢复")
        refresh_count += 1
        self.log(f"{label}: 检测到 Bad gateway/502，刷新页面重试 ({refresh_count}/8)")
        try:
            page.reload(wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            self.log(f"{label}: 502 页面刷新失败，继续等待: {str(exc)[:120]}")
        return True, refresh_count

    def _page_has_text(self, page, texts: list[str]) -> bool:
        try:
            body = page.locator("body").inner_text(timeout=1000)
        except Exception:
            return False
        return any(text in body for text in texts)

    def _select_team_workspace_if_visible(self, page) -> bool:
        try:
            page_text = page.locator("body").inner_text(timeout=1000)
        except Exception:
            page_text = ""
        if not re.search(r"采用何种方式|何种方式.*登录|工作空间|workspace|sign in", page_text, flags=re.I):
            return False
        try:
            clicked = page.evaluate(
                r"""() => {
                    const visible = el => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                    };
                    const enabled = el => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                    const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter(el => visible(el) && enabled(el));
                    const workspace = candidates.find(el => {
                        const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.replace(/\s+/g, ' ').trim();
                        return /工作空间|workspace|Trantow|Team/i.test(text)
                            && !/Google|Microsoft|Apple|密码|password|电话|phone/i.test(text);
                    });
                    if (!workspace) return false;
                    workspace.scrollIntoView({ block: 'center', inline: 'center' });
                    workspace.click();
                    return true;
                }"""
            )
        except Exception:
            clicked = False
        if clicked:
            self.log("已选择 Team 工作空间登录选项")
            return True
        return False

    def _team_onboarding_pending(self, page) -> bool:
        try:
            body = page.locator("body").inner_text(timeout=1000)
        except Exception:
            return False
        return bool(re.search(
            r"What kind of work do you do|Select the option that best applies|你从事哪种工作|你从事什么工作|借助\s*Codex|更快完成工作|选择你的工作应用|启用这些应用|work apps|Maybe later|Skip|稍后再说|跳过",
            body,
            flags=re.I,
        ))

    def _complete_team_onboarding_if_visible(self, page) -> bool:
        try:
            result = page.evaluate(
                r"""() => {
                    const visible = el => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                    };
                    const enabled = el => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                    const body = document.body?.textContent || '';
                    const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter(el => visible(el) && enabled(el));

                    if (/What kind of work do you do|Select the option that best applies|你从事哪种工作|你从事什么工作/i.test(body)) {
                        const target = candidates.find(el => /Engineering|工程/i.test((el.textContent || '').trim())) || candidates[0];
                        if (!target) return '';
                        target.scrollIntoView({ block: 'center', inline: 'center' });
                        target.click();
                        return 'work';
                    }

                    const later = candidates.find(el => /Maybe later|Not now|稍后再说|稍後再說|以后再说|暫時不要/i.test((el.textContent || '').trim()));
                    if (later) {
                        later.scrollIntoView({ block: 'center', inline: 'center' });
                        later.click();
                        return 'later';
                    }

                    const skip = candidates.find(el => /Skip|跳过|跳過/i.test((el.textContent || '').trim()));
                    if (skip) {
                        skip.scrollIntoView({ block: 'center', inline: 'center' });
                        skip.click();
                        return 'skip';
                    }

                    return '';
                }"""
            )
        except Exception:
            result = ""
        if result:
            labels = {"work": "已选择 Team onboarding 工作类型: Engineering", "later": "已点击 Team onboarding 稍后再说", "skip": "已点击 Team onboarding 跳过"}
            self.log(labels.get(str(result), "已处理 Team onboarding"))
            return True
        return False

    def _approve_sso_login_if_visible(self, page) -> bool:
        try:
            clicked = page.evaluate(
                r"""() => {
                    const visible = el => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                    };
                    const enabled = el => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                    const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], input[type="submit"]')).filter(el => visible(el) && enabled(el));
                    const approve = candidates.find(el => {
                        const text = `${el.value || ''} ${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.replace(/\s+/g, ' ').trim();
                        return /批准登录|批准登入|Approve\s+(login|sign[- ]?in)|Approve\s+sign[- ]?in/i.test(text)
                            && !/不认识|不認識|Not.*account|deny|cancel/i.test(text);
                    });
                    if (!approve) return false;
                    approve.scrollIntoView({ block: 'center', inline: 'center' });
                    approve.click();
                    return true;
                }"""
            )
        except Exception:
            clicked = False
        if clicked:
            self.log("已点击批准登录")
            return True
        return False

    def _prepare_browser_oauth_url(self) -> tuple[str, str]:
        state = random_urlsafe_string(24)
        code_verifier = random_urlsafe_string(64)
        query = urlencode({
            "client_id": DEFAULT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": DEFAULT_REDIRECT_URI,
            "scope": "openid email profile offline_access",
            "state": state,
            "code_challenge": pkce_code_challenge(code_verifier),
            "code_challenge_method": "S256",
            "prompt": "login",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "login_hint": self.account.email,
        })
        return f"{AUTH_BASE_URL}/oauth/authorize?{query}", code_verifier

    def _authorize_rt_from_browser(self, context, page) -> dict:
        oauth_url, code_verifier = self._prepare_browser_oauth_url()
        self.log("在当前 Team 标签页发起 OAuth 授权获取 RT")
        page.goto(oauth_url, wait_until="domcontentloaded", timeout=90000)
        started = time.time()
        approve_clicked = False
        last_notice = 0.0
        bad_gateway_refreshes = 0
        while time.time() - started < 180:
            refreshed, bad_gateway_refreshes = self._refresh_bad_gateway_if_visible(page, bad_gateway_refreshes, "Team OAuth")
            if refreshed:
                time.sleep(3)
                continue
            current_url = page.url
            if current_url.startswith(DEFAULT_REDIRECT_URI):
                result = self._extract_oauth_callback_from_url(current_url)
                self.log("已获取 OAuth 授权 code，交换 refresh_token")
                return self._exchange_browser_code_for_token(context, result["code"], code_verifier)
            if self._complete_team_onboarding_if_visible(page):
                time.sleep(2)
                continue
            if not approve_clicked and self._approve_sso_login_if_visible(page):
                approve_clicked = True
                self._wait_team_sso_progress(page, "OAuth 批准登录后跳转", 60)
                continue
            if self._click_codex_consent_if_visible(page):
                self._wait_team_sso_progress(page, "OAuth 授权确认后跳转", 60)
                continue
            if time.time() - last_notice >= 15:
                remain = max(0, int(180 - (time.time() - started)))
                self.log(f"Team OAuth 等待 callback 中，剩余约 {remain}s，当前 URL: {current_url[:100]}")
                last_notice = time.time()
            time.sleep(1)
        raise TimeoutError(f"Team OAuth 授权 180 秒内未到 callback，当前 URL: {page.url}")

    def _click_codex_consent_if_visible(self, page) -> bool:
        try:
            clicked = page.evaluate(
                r"""() => {
                    const visible = el => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                    };
                    const enabled = el => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                    const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], input[type="submit"]')).filter(el => visible(el) && enabled(el));
                    const target = candidates.find(el => {
                        const text = `${el.value || ''} ${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.replace(/\s+/g, ' ').trim();
                        return /Authorize|授权|允許|允许|Continue|继续|続行|Approve/i.test(text);
                    });
                    if (!target) return false;
                    target.scrollIntoView({ block: 'center', inline: 'center' });
                    target.click();
                    return true;
                }"""
            )
        except Exception:
            clicked = False
        if clicked:
            self.log("已点击授权/继续按钮")
            return True
        return False

    def _extract_oauth_callback_from_url(self, callback_url: str) -> dict:
        parsed = urlparse(callback_url)
        query = parse_qs(parsed.query)
        code = (query.get("code") or [""])[0]
        if not code:
            raise RuntimeError(f"callback 中缺少 code: {callback_url}")
        return {"callback_url": callback_url, "code": code}

    def _exchange_browser_code_for_token(self, context, code: str, code_verifier: str) -> dict:
        last_error = ""
        for token_url in AUTH_OAUTH_TOKEN_URLS:
            response = context.request.post(
                token_url,
                headers=openai_browser_headers({
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
                    "code_verifier": code_verifier,
                },
                timeout=30000,
            )
            if response.ok:
                return normalize_openai_auth_record(self.account.email, response.json())
            last_error = f"endpoint={token_url} HTTP {response.status} {response.text()[:300]}"
        raise RuntimeError(f"Team Code换Token失败: {last_error}")

    def _session_payload_from_record(self, record: dict) -> dict:
        return {
            "user": {"email": self.account.email},
            "accessToken": str(record.get("access_token") or ""),
            "expires": str(record.get("expired") or ""),
        }

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
                if self._handle_phone_continue_if_visible(page):
                    email_code_submitted = False
                    about_you_submitted = False
                    continue
                raise RuntimeError("当前账号触发手机验证，但未找到可自动处理的手机号注册页面")
            if self._handle_phone_continue_if_visible(page):
                email_code_submitted = False
                about_you_submitted = False
                continue
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
                self._fill_password_step(page)
                self._wait_and_reload(page, "密码已填写，等待跳转")
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
        csrf_value, device_id = self._get_chatgpt_csrf_and_device(context)
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
            "locale": self.fingerprint.locale,
        })
        response = context.request.post(
            f"{CHATGPT_BASE_URL}/api/auth/signin/openai?{query}",
            form={"callbackUrl": f"{CHATGPT_BASE_URL}/", "csrfToken": csrf_value, "json": "true"},
            headers={"Accept": "application/json", "Accept-Language": self.fingerprint.accept_language},
        )
        if not response.ok:
            raise RuntimeError(f"打开注册页失败: HTTP {response.status} {response.text()[:300]}")
        payload = response.json()
        signin_url = payload.get("url")
        if not signin_url:
            raise RuntimeError(f"打开注册页缺少跳转 URL: {payload}")
        return signin_url

    def _create_login_url(self, context) -> str:
        csrf_value, device_id = self._get_chatgpt_csrf_and_device(context)
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
            "locale": self.fingerprint.locale,
        })
        response = context.request.post(
            f"{CHATGPT_BASE_URL}/api/auth/signin/openai?{query}",
            form={"callbackUrl": f"{CHATGPT_BASE_URL}/", "csrfToken": csrf_value, "json": "true"},
            headers={"Accept": "application/json", "Accept-Language": self.fingerprint.accept_language},
        )
        if not response.ok:
            raise RuntimeError(f"打开登录页失败: HTTP {response.status} {response.text()[:300]}")
        payload = response.json()
        signin_url = payload.get("url")
        if not signin_url:
            raise RuntimeError(f"打开登录页缺少跳转 URL: {payload}")
        return signin_url

    def _get_chatgpt_csrf_and_device(self, context) -> tuple[str, str]:
        cookies = context.cookies([CHATGPT_BASE_URL, "https://openai.com"])
        csrf_value = ""
        device_id = ""
        for cookie in cookies:
            if cookie.get("name") == "__Host-next-auth.csrf-token":
                csrf_value = unquote(cookie.get("value", "")).split("|")[0]
            if cookie.get("name") == "oai-did":
                device_id = cookie.get("value", "")
        if not csrf_value:
            last_exc = ""
            for attempt in range(3):
                try:
                    response = context.request.get(
                        f"{CHATGPT_BASE_URL}/api/auth/csrf",
                        headers={"Accept": "application/json", "Accept-Language": self.fingerprint.accept_language, "Referer": f"{CHATGPT_BASE_URL}/"},
                        timeout=30000,
                    )
                    if response.ok:
                        payload = response.json()
                        csrf_value = str(payload.get("csrfToken") or "").strip()
                        if csrf_value:
                            break
                    last_exc = f"HTTP {response.status}: {str(response.text())[:120]}"
                except Exception as exc:
                    last_exc = str(exc)[:160]
                if attempt < 2:
                    delay = (attempt + 1) * 3
                    self.log(f"获取 ChatGPT CSRF 失败，{delay}s 后重试 ({attempt+1}/2): {last_exc}")
                    time.sleep(delay)
            if not csrf_value:
                self.log(f"获取 ChatGPT CSRF 接口失败(已重试2次): {last_exc}")
                cookies = context.cookies([CHATGPT_BASE_URL, "https://openai.com"])
                for cookie in cookies:
                    if cookie.get("name") == "__Host-next-auth.csrf-token":
                        csrf_value = unquote(cookie.get("value", "")).split("|")[0]
                        break
        if not device_id:
            cookies = context.cookies([CHATGPT_BASE_URL, "https://openai.com"])
            for cookie in cookies:
                if cookie.get("name") == "oai-did":
                    device_id = cookie.get("value", "")
                    break
        return csrf_value, device_id

    def _has_chatgpt_session(self, page) -> bool:
        if not page.url.startswith(CHATGPT_BASE_URL):
            return False
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
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
                const candidates = buttons.filter(el =>
                    (el.textContent || '').includes('Finish creating account')
                    || (el.textContent || '').includes('Continue')
                    || (el.textContent || '').includes('继续')
                    || (el.textContent || '').includes('続行')
                    || (el.textContent || '').includes('アカウントの作成を完了する')
                    || (el.textContent || '').includes('作成')
                    || (el.getAttribute('data-dd-action-name') || '') === 'Continue'
                    || (el.type || '').toLowerCase() === 'submit'
                );
                if (!candidates.length) return false;
                let button = candidates[0];
                let maxY = 0;
                for (const c of candidates) {
                    const y = c.getBoundingClientRect().bottom;
                    if (y > maxY) { maxY = y; button = c; }
                }
                if (button.getAttribute('aria-disabled') === 'true' || button.disabled) return false;
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

    def _handle_phone_continue_if_visible(self, page) -> bool:
        if not self.phone_provider:
            return False
        clicked_phone_continue = self._click_use_phone_number_continue(page)
        if not clicked_phone_continue and not self._has_register_phone_number_form(page):
            return False

        self.log("检测到“使用电话号码继续”，改用手机号池注册")
        if clicked_phone_continue:
            time.sleep(1)
        last_error = ""
        for _ in range(30):
            phone = self.phone_provider("next", self.account.email, {"country": "US"})
            if not phone:
                detail = f"，最后错误: {last_error}" if last_error else ""
                raise RuntimeError(f"手机号池没有可用的美国 +1 手机号，无法继续电话注册{detail}")
            phone_number = str(phone.get("number") or "").strip()
            local_number = normalize_us_phone_for_form(phone_number)
            number_submitted = False
            try:
                if not phone_number.startswith("+1") or len(local_number) < 10:
                    raise RuntimeError("当前电话注册流程要求美国 +1 手机号")
                if not self._select_us_phone_country(page):
                    raise RuntimeError("未能将手机号国家切换为美国 +1")
                self.log(f"填写美国注册手机号: {phone_number}")
                self._fill_register_phone_number(page, local_number[-10:])
                if not self._click_continue(page):
                    raise RuntimeError("手机号已填写，但未找到继续按钮")
                number_submitted = True
                self._wait_for_register_phone_code_form(page)
                code = self.phone_provider("code", self.account.email, phone)
                if not code:
                    raise RuntimeError("短信链接未读取到验证码")
                self.log(f"读取到手机注册验证码: {code}")
                self._submit_register_phone_code(page, str(code))
                self.active_register_phone = dict(phone)
                self.log("已提交手机注册验证码，继续后续注册流程")
                time.sleep(3)
                return True
            except Exception as exc:
                last_error = str(exc)
                if not number_submitted:
                    raise RuntimeError(last_error)
                self.phone_provider("bad", self.account.email, {**phone, "error": last_error})
                self.log(f"手机号 {phone_number} 注册不可用，切换下一个: {last_error}")
                if not self._reset_phone_registration_for_next_number(page):
                    raise RuntimeError(f"手机号注册失败且无法回到号码输入页: {last_error}")
                time.sleep(1)
        raise RuntimeError(f"手机号注册失败次数过多: {last_error or 'unknown'}")

    def _has_register_phone_number_form(self, page) -> bool:
        inputs = self._visible_inputs(page, [
            'input[type="tel"]',
            'input[inputmode="tel"]',
            'input[name*="phone" i]',
            'input[autocomplete*="tel" i]',
            'input[aria-label*="phone" i]',
            'input[aria-label*="手机" i]',
            'input[placeholder*="phone" i]',
            'input[placeholder*="手机" i]',
        ])
        if not inputs:
            return False
        for input_box in inputs:
            try:
                if input_box.evaluate(
                    r"""el => {
                        const meta = [el.type, el.inputMode, el.name, el.id, el.placeholder, el.autocomplete, el.getAttribute('aria-label')]
                            .join(' ')
                            .toLowerCase();
                        return /phone|tel|手机|手機|電話|\+1|\+81/.test(meta);
                    }"""
                ):
                    return True
            except Exception:
                pass
        try:
            text = page.locator("body").inner_text(timeout=1000)
        except Exception:
            text = ""
        return bool(re.search(r"country|国家|國家|日本|美国|美國|United States", text, flags=re.I))

    def _click_use_phone_number_continue(self, page) -> bool:
        try:
            return bool(page.evaluate(
                r"""() => {
                    const visible = el => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                    };
                    const enabled = el => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                    const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter(el => visible(el) && enabled(el));
                    const target = candidates.find(el => {
                        const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.replace(/\s+/g, ' ').trim();
                        const hasPhone = /使用电话号码|使用電話號碼|電話番号|phone number/i.test(text);
                        const hasContinue = /继续|繼續|続行|continue/i.test(text);
                        return hasPhone && hasContinue;
                    });
                    if (!target) return false;
                    target.scrollIntoView({ block: 'center', inline: 'center' });
                    target.click();
                    return true;
                }"""
            ))
        except Exception:
            return False

    def _select_us_phone_country(self, page) -> bool:
        result = page.evaluate(
            r"""() => {
                const visible = el => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                };
                const setNativeValue = (el, value) => {
                    const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
                    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (desc && desc.set) desc.set.call(el, value); else el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                };
                const isUnitedStates = text => {
                    const value = String(text || '').replace(/\s+/g, ' ').trim();
                    if (/美属|美屬|萨摩亚|薩摩亞|维尔京|維爾京|关岛|關島|波多黎各/.test(value)) return false;
                    if (/Samoa|Virgin|Guam|Mariana|Puerto Rico/i.test(value)) return false;
                    return /(^|\s)美国\s*(\(\+?1\)|\+?1)?$/i.test(value)
                        || /(^|\s)美國\s*(\(\+?1\)|\+?1)?$/i.test(value)
                        || /United States\s*(\(\+?1\)|\+?1)?/i.test(value);
                };

                for (const select of Array.from(document.querySelectorAll('select')).filter(visible)) {
                    const matched = Array.from(select.options || []).find(opt => {
                        const value = String(opt.value || '').trim().toUpperCase();
                        return value === 'US' || isUnitedStates(opt.textContent || '');
                    });
                    if (matched) {
                        setNativeValue(select, matched.value);
                        return 'select';
                    }
                }

                const buttons = Array.from(document.querySelectorAll('button, [role="button"], [role="combobox"], [aria-haspopup]')).filter(visible);
                const current = buttons.find(el => {
                    const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.replace(/\s+/g, ' ');
                    return /\+81|日本|Japan|country|region|国家|國家/i.test(text);
                });
                if (current) {
                    current.scrollIntoView({ block: 'center', inline: 'center' });
                    current.click();
                    return 'opened';
                }
                return '';
            }"""
        )
        if result == "select":
            return True
        if result == "opened":
            time.sleep(0.8)
            selected = page.evaluate(
                r"""() => {
                    const visible = el => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                    };
                    const isUnitedStates = text => {
                        const value = String(text || '').replace(/\s+/g, ' ').trim();
                        if (/美属|美屬|萨摩亚|薩摩亞|维尔京|維爾京|关岛|關島|波多黎各/.test(value)) return false;
                        if (/Samoa|Virgin|Guam|Mariana|Puerto Rico/i.test(value)) return false;
                        return /^(?:🇺🇸\s*)?美国\s*(\(\+?1\)|\+?1)?$/i.test(value)
                            || /^(?:🇺🇸\s*)?美國\s*(\(\+?1\)|\+?1)?$/i.test(value)
                            || /United States\s*(\(\+?1\)|\+?1)?/i.test(value);
                    };
                    const options = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], li, button, div'))
                        .filter(visible)
                        .filter(el => isUnitedStates(el.textContent || el.getAttribute('aria-label') || ''));
                    const target = options[0];
                    if (!target) return false;
                    target.scrollIntoView({ block: 'center', inline: 'center' });
                    target.click();
                    return true;
                }"""
            )
            if selected:
                time.sleep(0.5)
                return True
        self.log("未能确认手机号国家已切换为美国")
        return False

    def _fill_register_phone_number(self, page, local_number: str) -> None:
        selectors = [
            'input[type="tel"]',
            'input[inputmode="tel"]',
            'input[inputmode="numeric"]',
            'input[name*="phone" i]',
            'input[autocomplete*="tel" i]',
            'input[aria-label*="phone" i]',
            'input[aria-label*="手机" i]',
            'input[placeholder*="phone" i]',
            'input[placeholder*="手机" i]',
        ]
        inputs = self._visible_inputs(page, selectors)
        if not inputs:
            raise RuntimeError("未找到手机号输入框")
        if not self._force_fill_locator(inputs[0], local_number):
            raise RuntimeError("手机号输入框填写失败")

    def _looks_like_register_phone_code_page(self, page) -> bool:
        try:
            text = page.locator("body").inner_text(timeout=1000)
        except Exception:
            text = ""
        normalized = re.sub(r"\s+", " ", str(text or ""))
        has_phone = re.search(r"短信|SMS|text message|手机号|手機|電話|phone number|\+\d", normalized, flags=re.I)
        has_code = re.search(r"验证码|驗證碼|コード|code|6[- ]?digit|verification", normalized, flags=re.I)
        has_email_only = re.search(r"email|邮件|郵件|邮箱|電子メール", normalized, flags=re.I)
        return bool(has_phone and has_code and not (has_email_only and not re.search(r"短信|SMS|text message|phone", normalized, flags=re.I)))

    def _register_phone_code_inputs(self, page):
        strict_inputs = self._visible_inputs(page, [
            'input[autocomplete="one-time-code"]',
            'input[name="code"]',
            'input[aria-label*="code" i]',
            'input[placeholder*="code" i]',
            'input[aria-label*="验证码" i]',
            'input[placeholder*="验证码" i]',
        ])
        if strict_inputs:
            return strict_inputs
        if self._looks_like_register_phone_code_page(page):
            numeric_inputs = self._visible_inputs(page, ['input[inputmode="numeric"]'])
            if len(numeric_inputs) >= 6:
                return numeric_inputs
            code_inputs = []
            for input_box in numeric_inputs:
                try:
                    if input_box.evaluate(
                        r"""el => {
                            const meta = [el.type, el.inputMode, el.name, el.id, el.placeholder, el.autocomplete, el.getAttribute('aria-label')]
                                .join(' ')
                                .toLowerCase();
                            const maxLength = Number(el.maxLength || 0);
                            if (/phone|tel|手机|手機|電話|\+1|\+81/.test(meta)) return false;
                            return maxLength > 0 && maxLength <= 8;
                        }"""
                    ):
                        code_inputs.append(input_box)
                except Exception:
                    pass
            return code_inputs
        return []

    def _wait_after_register_phone_code_submit(self, page, timeout: int = 30) -> None:
        started = time.time()
        while time.time() - started < timeout:
            if self._has_chatgpt_session(page):
                return
            if "about-you" in page.url or self._has_about_you_form(page):
                return
            if "password" in page.url and self._has_visible_password(page):
                return
            if not self._register_phone_code_inputs(page):
                return
            time.sleep(1)
        raise RuntimeError(f"手机验证码提交后仍停留在短信验证页: {self._page_text_summary(page)}")

    def _wait_for_register_phone_code_form(self, page, timeout: int = 45) -> None:
        started = time.time()
        while time.time() - started < timeout:
            if self._has_chatgpt_session(page):
                return
            if self._register_phone_code_inputs(page):
                return
            time.sleep(1)
        raise RuntimeError(f"提交手机号后未进入短信验证码页: {self._page_text_summary(page)}")

    def _submit_register_phone_code(self, page, code: str) -> None:
        inputs = self._register_phone_code_inputs(page)
        if not inputs:
            if self._has_chatgpt_session(page):
                return
            raise RuntimeError("页面未找到手机验证码输入框")
        if len(inputs) >= 6:
            for index, char in enumerate(code[:6]):
                inputs[index].fill(char)
        else:
            inputs[0].fill(code)
        self._click_continue(page)
        self._wait_after_register_phone_code_submit(page)

    def _reset_phone_registration_for_next_number(self, page) -> bool:
        if self._has_register_phone_number_form(page):
            return True
        if self._click_button_by_text(page, ["Change phone", "Edit", "Back", "更改", "编辑", "返回", "戻る"]):
            time.sleep(1)
            return self._has_register_phone_number_form(page)
        try:
            page.go_back(wait_until="domcontentloaded", timeout=15000)
            time.sleep(1)
            return self._has_register_phone_number_form(page)
        except Exception:
            return False

    def _has_visible_password(self, page) -> bool:
        return bool(self._visible_inputs(page, ['input[type="password"]', 'input[name="password"]']))

    def _fill_password_step(self, page) -> None:
        if not self.account.password:
            if self.custom_password:
                self.account.password = self.custom_password
                self.log(f"账号需要密码步骤，使用自定义密码继续")
            else:
                self.account.password = self._generate_password()
                self.log(f"账号需要密码步骤，已生成密码: {self.account.password}")
            if self.account.mail_provider == "custom_api":
                self.account.raw = "----".join([self.account.email, self.account.api_key])
            else:
                self.account.raw = "----".join([
                    self.account.email,
                    self.account.password,
                    self.account.client_id,
                    self.account.refresh_token,
                ])
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
        if self._looks_like_register_phone_code_page(page):
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
        if not self.otp_reader:
            if self.account.mail_provider == "custom_api":
                proxy_url = self.register_proxy.chain_url if self.register_proxy else ""
                self.otp_reader = CustomApiOtpReader(self.account, self.custom_api_url, self.custom_api_admin_key, self.log, proxy_url, self.custom_api_poll_interval, self.custom_first_delay)
            else:
                self.otp_reader = HotmailOtpReader(self.account, self.log, "")

        for retry in range(2):
            code = self.otp_reader.wait_for_code(min_timestamp)
            self.log(f"获取到验证码: {code}")
            inputs = self._visible_inputs(page, [
                'input[autocomplete="one-time-code"]',
                'input[inputmode="numeric"]',
                'input[type="tel"]',
                'input[name="code"]',
            ])
            if not inputs:
                raise RuntimeError("页面未找到验证码输入框")
            for inp in inputs:
                try:
                    inp.fill("")
                except Exception:
                    pass
            if len(inputs) >= 6:
                for index, char in enumerate(code[:6]):
                    inputs[index].fill(char)
            else:
                inputs[0].fill(code)
            continue_url, is_wrong = self._validate_email_code_api(page, code)
            if continue_url:
                self.log("已通过接口提交邮箱验证码")
                page.goto(continue_url, wait_until="domcontentloaded", timeout=90000)
                self._wait_after_otp_submit(page)
                return
            if not is_wrong or retry >= 1:
                raise RuntimeError(f"邮箱验证码提交失败")
            self.log(f"验证码 {code} 被拒绝，点击重发按钮获取新码")
            if not self._click_resend_email_otp(page):
                raise RuntimeError("无法点击重发验证码按钮，且页面刷新也失败")
            min_timestamp = time.time()
            time.sleep(2)

    def _validate_email_code_api(self, page, code: str) -> tuple[str, bool]:
        """Returns (continue_url, is_wrong_code). is_wrong_code=True means the code was rejected and we should resend."""
        last_detail = ""
        last_body = ""
        for attempt in range(3):
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
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
                return (str(payload.get("continue_url") or payload.get("page", {}).get("payload", {}).get("url") or ""), False)

            last_detail = str(result.get("text") or result.get("status") or "")
            last_body = str(result.get("text") or "")
            if self._is_cloudflare_challenge(last_detail) and attempt < 2:
                self.log("EmailOtpValidate 触发 Cloudflare challenge，正在浏览器中打开挑战页并等待放行")
                self._handle_cloudflare_challenge(page, last_detail)
                continue
            break

        if self._is_cloudflare_challenge(last_detail):
            raise RuntimeError("EmailOtpValidate 被 Cloudflare 持续拦截。请换更干净的动态代理，或在浏览器里的 Cloudflare 页面手动等待通过后重试。")

        is_wrong = bool(
            re.search(r'wrong_email_otp|invalid.*code|incorrect.*code|code.*invalid|code.*expired|code.*wrong|otp.*invalid', last_body, re.IGNORECASE)
            or re.search(r'验证码.*错误|验证码.*过期|コード.*違|コード.*誤|コード.*期限', last_body)
        )
        if is_wrong:
            self.log(f"邮箱验证码被拒绝: {last_detail[:200]}")
            return ("", True)
        raise RuntimeError(f"EmailOtpValidate 接口失败: {last_detail[:800]}")

    def _click_resend_email_otp(self, page) -> bool:
        selectors = [
            "button:has-text('Send again')",
            "button:has-text('Resend')",
            "button:has-text('再送信')",
            "button:has-text('重新发送')",
            "button:has-text('再发送')",
            "button:has-text('Renvoyer')",
            "[role='button']:has-text('Send again')",
            "[role='button']:has-text('再送信')",
            "a:has-text('Send again')",
            "a:has-text('Resend code')",
            "a:has-text('再送信')",
        ]
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=500):
                    btn.click(timeout=5000)
                    self.log(f"已点击重发验证码按钮: {selector}")
                    return True
            except Exception:
                continue
        self.log("未找到重发验证码按钮，尝试页面刷新代替重发")
        try:
            page.reload(wait_until="domcontentloaded", timeout=15000)
            return True
        except Exception:
            return False

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
            if not self._click_button_by_text(page, ["Finish creating account", "完成帐户创建", "完成账户创建", "Create account", "Continue", "完成", "続行", "次へ", "完了", "作成", "アカウントを作成", "アカウントの作成を完了する"]):
                return False

        started = time.time()
        retried = False
        while time.time() - started < 30:
            if page.is_closed():
                raise RuntimeError("浏览器页面已关闭，无法等待基础资料提交结果")
            if self._has_chatgpt_session(page):
                return True
            if page.url != before_url and "about-you" not in page.url:
                return True
            if "add-phone" in page.url or "phone-verification" in page.url:
                return True
            if not retried and time.time() - started > 3:
                self.log("about-you 首次提交 3 秒未跳转，重试点击按钮")
                self._click_finish_creating_account(page)
                retried = True
            time.sleep(1)
        self.log("基础资料提交后页面未跳转，继续检测当前页面状态")
        return True

    def _click_finish_creating_account(self, page) -> bool:
        texts = ["Finish creating account", "Continue", "继续", "完成", "Finish", "Create account", "Next", "下一步", "Submit", "続行", "次へ", "完了", "作成", "アカウントを作成", "アカウントの作成を完了する", "登録"]
        for text in texts:
            try:
                btn = page.locator(f"button:has-text('{text}')").last
                if btn.is_visible(timeout=700):
                    btn.scroll_into_view_if_needed(timeout=3000)
                    btn.click(timeout=5000)
                    self.log(f"已点击 about-you 按钮: '{text}'")
                    return True
            except Exception:
                continue
            try:
                btn = page.locator(f"[role='button']:has-text('{text}')").last
                if btn.is_visible(timeout=700):
                    btn.click(timeout=5000)
                    self.log(f"已点击 about-you [role=button]: '{text}'")
                    return True
            except Exception:
                continue
        return False

    def _click_button_by_text(self, page, texts: list[str]) -> bool:
        box = page.evaluate(
            """({texts}) => {
                const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                };
                const safe = el => el.tagName !== 'A' || el.classList.contains('btn') || el.classList.contains('button');
                const candidates = Array.from(document.querySelectorAll('button, [role="button"], a'))
                    .filter(visible)
                    .filter(safe)
                    .filter(el => texts.some(text => (el.textContent || '').includes(text)));
                if (!candidates.length) return null;
                let el = candidates[0];
                let maxY = 0;
                for (const c of candidates) {
                    const y = c.getBoundingClientRect().bottom;
                    if (y > maxY) { maxY = y; el = c; }
                }
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
            values = self._fill_about_you_inputs_by_dom(page, name, age)
            if self._about_you_values_ok(values):
                self.log("基础资料已通过 DOM 填写")
                return
        except Exception as exc:
            self.log(f"基础资料 DOM 填写失败，改用键盘输入: {str(exc)[:120]}")

        try:
            self._fill_visible_input_by_keyboard(page, 0, name)
            self._fill_visible_input_by_keyboard(page, 1, age, press_tab=False)
            values = self._visible_input_values(page)
            if self._about_you_values_ok(values):
                self.log("基础资料已通过键盘输入")
                return
        except Exception as exc:
            self.log(f"基础资料键盘输入失败: {str(exc)[:120]}")

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
            if (el.type === 'file' || el.type === 'checkbox' || el.type === 'radio' || el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return false;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
        }).map(el => el.value || '')""")
        if self._about_you_values_ok(values):
            return

        self.log("基础资料 DOM 填写未生效，改用鼠标点击 + 键盘输入")
        self._fill_visible_input_by_keyboard(page, 0, name)
        self._fill_visible_input_by_keyboard(page, 1, age, press_tab=False)
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
                const controls = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]')).filter(el => {
                    if (el.type === 'file' || el.type === 'checkbox' || el.type === 'radio' || el.type === 'hidden') return false;
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                });
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
            if (el.type === 'file' || el.type === 'checkbox' || el.type === 'radio' || el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return false;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
        }).map(el => el.isContentEditable ? (el.textContent || '') : (el.value || ''))""")

    def _about_you_values_ok(self, values: list[str]) -> bool:
        normalized = [str(value).strip() for value in values]
        return len(normalized) >= 2 and bool(normalized[0]) and bool(normalized[1])

    def _fill_visible_input_by_keyboard(self, page, index: int, value: str, press_tab: bool = True) -> None:
        box = page.evaluate(
            """({index}) => {
                const controls = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]')).filter(el => {
                    if (el.type === 'file' || el.type === 'checkbox' || el.type === 'radio' || el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return false;
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
        if press_tab:
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

    def _extract_pay_link(self, page) -> dict:
        mode = PAYMENT_MODES.get(self.payment_mode) or PAYMENT_MODES["无卡长链接 US/USD"]
        trial_short_link = bool(mode.get("trial_short_link"))
        apple_pay_hosted = bool(mode.get("apple_pay_hosted"))
        link_label = "试用短链" if trial_short_link else ("Apple Pay 支付页" if apple_pay_hosted else "支付长链接")
        self.log(f"提取{link_label}: {self.payment_mode}")
        if page.is_closed():
            raise RuntimeError(f"浏览器页面已关闭，无法提取{link_label}")
        page.goto(CHATGPT_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        last_error = "未知错误"
        started = time.time()
        for attempt in range(1, 16):
            if page.is_closed():
                raise RuntimeError(f"浏览器页面已关闭，无法提取{link_label}")
            if time.time() - started > 120:
                break
            self.log(f"正在提取{link_label} ({attempt}/15)")
            try:
                if trial_short_link:
                    return self._extract_trial_short_link_by_click(page)
                result = page.evaluate(
                    """async () => {
                        const sessionResp = await fetch('/api/auth/session', { credentials: 'include' });
                        if (!sessionResp.ok) throw new Error(`Session 请求失败: HTTP ${sessionResp.status}`);
                        const session = await sessionResp.json();
                        if (!session.accessToken) throw new Error('无法获取 accessToken，请确认已登录');
                        return { accessToken: session.accessToken, session };
                    }"""
                )
                access_token = str((result or {}).get("accessToken") or "")
                if not access_token:
                    raise RuntimeError("无法获取 accessToken，请确认已登录")
                self.log("已提取 ChatGPT session/accessToken")
                country = str(mode.get("country") or "US")
                currency = str(mode.get("currency") or currency_for_country(country))
                proxy_url = self.extract_proxy.chain_url or self.extract_proxy.local_proxy or self.extract_proxy.dynamic_proxy
                if apple_pay_hosted:
                    link_result = generate_opll_hosted_long_link(access_token, country, currency, proxy_url)
                    long_url = str(link_result.get("long_url") or link_result.get("stripe_hosted_url") or "").strip()
                    if not long_url:
                        raise RuntimeError(f"接口生成成功但没有返回 Apple Pay 支付页链接: {link_result}")
                    self.log("Apple Pay hosted 支付页已生成；请用 Safari/iPhone/Mac 打开并手动付款")
                    return {
                        "url": long_url,
                        "checkout_url": long_url,
                        "access_token": access_token,
                        "session_json": json.dumps((result or {}).get("session") or {}, ensure_ascii=False, indent=2),
                        "payment_link_type": "apple_pay_hosted",
                    }
                link_result = generate_opll_paypal_long_link(access_token, country, currency, proxy_url)
                long_url = str(link_result.get("provider_redirect_url") or link_result.get("long_url") or "").strip()
                if not opll_is_paypal_ba_approve_url(long_url):
                    raise RuntimeError(f"返回的不是 PayPal BA approve 长链，拒绝保存: {long_url[:160]}")
                self.log("PayPal BA approve 长链已生成，注册浏览器窗口保持打开")
                return {
                    "url": long_url,
                    "checkout_url": long_url,
                    "access_token": access_token,
                    "session_json": json.dumps((result or {}).get("session") or {}, ensure_ascii=False, indent=2),
                    "payment_link_type": "paypal_approve",
                }
            except Exception as exc:
                last_error = exc
                if "Target page" in str(exc) or "closed" in str(exc).lower():
                    raise RuntimeError(f"浏览器被关闭，{link_label}提取已停止")
                self.log(f"{link_label}提取失败，准备重试: {str(exc)[:180]}")
                time.sleep(4)
        raise RuntimeError(f"提取{link_label}失败: {last_error}")

    def _extract_session_info(self, context) -> dict:
        page = context.new_page()
        try:
            page.goto("https://chatgpt.com/api/auth/session", wait_until="domcontentloaded", timeout=60000)
            body = page.locator("body").inner_text(timeout=15000).strip()
            try:
                session = json.loads(body)
            except Exception as exc:
                raise RuntimeError(f"Session 接口返回不是有效 JSON: {body[:300]}") from exc
            access_token = str(session.get("accessToken") or "")
            if not access_token:
                self.log("Session JSON 已获取，但未发现 accessToken")
            else:
                self.log("Session JSON 和 Access Token 已获取")
            storage_state = context.storage_state()
            return {
                "url": "",
                "access_token": access_token,
                "session_json": json.dumps(session, ensure_ascii=False, indent=2),
                "storage_state_json": json.dumps(storage_state, ensure_ascii=False),
            }
        finally:
            try:
                page.bring_to_front()
            except Exception:
                pass

    def _extract_trial_short_link_by_click(self, page) -> dict:
        session_info = page.evaluate(
            """async () => {
                const sessionResp = await fetch('/api/auth/session', { credentials: 'include' });
                if (!sessionResp.ok) throw new Error(`Session 请求失败: HTTP ${sessionResp.status}`);
                const session = await sessionResp.json();
                if (!session.accessToken) throw new Error('无法获取 accessToken，请确认已登录');
                return { accessToken: session.accessToken, session };
            }"""
        )
        self.log("已提取 ChatGPT session/accessToken")
        page.goto("https://chatgpt.com/?promo_campaign=plus-1-month-free#pricing", wait_until="domcontentloaded", timeout=60000)
        self.log("已打开试用页面，准备点击领取按钮")
        clicked = page.evaluate(
            """() => {
                const visible = el => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                };
                const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'))
                    .filter(el => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true');
                const target = candidates.find(el => {
                    const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.trim();
                    return /领取\\s*Plus|免费优惠|Plus\\s*免费|Claim\\s*Plus|free\\s*trial|Get\\s*Plus|Start/i.test(text);
                });
                if (!target) return false;
                target.scrollIntoView({ block: 'center' });
                target.click();
                return true;
            }"""
        )
        if not clicked:
            raise RuntimeError("试用页面未找到领取 Plus 免费优惠按钮")
        started = time.time()
        while time.time() - started < 60:
            if page.is_closed():
                raise RuntimeError("浏览器页面已关闭，无法等待试用短链跳转")
            current_url = page.url
            if "pay.openai.com" in current_url or "checkout.stripe.com" in current_url or "paypal.com" in current_url:
                self.log("试用短链已通过页面点击跳转生成")
                return {
                    "url": current_url,
                    "checkout_url": current_url,
                    "access_token": str(session_info.get("accessToken") or ""),
                    "session_json": json.dumps(session_info.get("session") or {}, ensure_ascii=False, indent=2),
                }
            time.sleep(1)
        raise RuntimeError(f"点击试用按钮后 60 秒内未跳转到支付页，当前 URL: {page.url}")


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x760")
        self.accounts: list[MailAccount] = []
        self.phones: list[PhoneEntry] = []
        self.payment_cards: list[PaymentCard] = []
        self.results: dict[str, str] = {}
        self.session_results: dict[str, dict] = {}
        self.events: queue.Queue = queue.Queue()
        self.pending_prompts: dict[str, queue.Queue] = {}
        self.running = False
        self.opening_payment_link = False
        self.stop_event = threading.Event()
        self.payment_context = None
        self.payment_contexts: set = set()
        self.trial_proxy_chain: ProxyChainServer | None = None
        self.trial_payment_dynamic_proxy = ""
        self.trial_account_email = ""
        self.open_payment_window_count = 0
        self.phone_lock = threading.Lock()
        self.payment_mode = StringVar(value="无卡长链接 US/USD")
        self.headless = BooleanVar(value=False)
        self.local_proxy = StringVar(value="http://127.0.0.1:7890")
        self.payment_dynamic_proxy = StringVar(value="")
        self.reuse_payment_proxy = StringVar(value="")
        self.require_japan_extract_proxy = BooleanVar(value=False)
        self.register_with_payment_proxy = BooleanVar(value=False)
        self.payment_extension_dir = StringVar(value=DEFAULT_PAYPAL_EXTENSION_DIR)
        self.br_stripe_proxy = StringVar(value="")
        self.paypal_phone = StringVar(value="")
        self.paypal_card = StringVar(value="")
        self.paypal_sms_url = StringVar(value="")
        self.paypal_phone_pool = StringVar(value="")
        self.export_name_prefix = StringVar(value="")
        self.custom_api_url = StringVar(value="")
        self.custom_api_admin_key = StringVar(value="")
        self.custom_api_poll_interval = IntVar(value=5)
        self.custom_api_first_delay = IntVar(value=5)
        self.custom_api_password = StringVar(value="")
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
        ttk.Label(top, text="每行：email (管理员模式) 或 email----password----client_id----refresh_token (Hotmail)[----auth_phone=手机号----auth_phone_sms_url=接码链接]").pack(side=LEFT)
        ttk.Button(top, text="从文件导入", command=self.load_file).pack(side=RIGHT)
        self.import_text = ScrolledText(import_tab, height=4)
        self.import_text.pack(fill=X, pady=(6, 0))
        ttk.Label(import_tab, text="日志").pack(anchor="w", pady=(8, 4))
        self.log_text = ScrolledText(import_tab, height=13)
        self.log_text.pack(fill=BOTH, expand=True)

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
        ttk.Label(proxy_frame, text="动态代理池（每行一个：username:password@hostname:port；注册/获取 Session 取第一行，用后移除）").pack(anchor="w", pady=(8, 4))
        self.proxy_text = ScrolledText(proxy_frame, height=4)
        self.proxy_text.pack(fill=X)
        payment_proxy_row = ttk.Frame(proxy_frame)
        payment_proxy_row.pack(fill=X, pady=(8, 0))
        ttk.Label(payment_proxy_row, text="支付链接动态代理（每行一个；打开链接时取第一行，用后移除）").pack(anchor="w")
        self.payment_dynamic_proxy_text = ScrolledText(payment_proxy_row, height=3)
        self.payment_dynamic_proxy_text.pack(fill=X, pady=(6, 0))
        reuse_proxy_row = ttk.Frame(proxy_frame)
        reuse_proxy_row.pack(fill=X, pady=(8, 0))
        ttk.Label(reuse_proxy_row, text="长链复用代理").pack(side=LEFT)
        ttk.Entry(reuse_proxy_row, textvariable=self.reuse_payment_proxy, width=72).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        ttk.Label(reuse_proxy_row, text="配置后 Session 提长链优先使用，不取用/移除支付代理池").pack(side=LEFT)
        br_stripe_row = ttk.Frame(proxy_frame)
        br_stripe_row.pack(fill=X, pady=(8, 0))
        ttk.Label(br_stripe_row, text="BR Stripe代理（每行一个；失败自动切下一条）").pack(anchor="w")
        self.br_stripe_proxy_text = ScrolledText(br_stripe_row, height=3)
        self.br_stripe_proxy_text.pack(fill=X, pady=(6, 0))
        ttk.Checkbutton(proxy_frame, text="提取长链强制日本出口（不勾选=只记录出口，不限制）", variable=self.require_japan_extract_proxy).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(proxy_frame, text="注册时使用支付链接动态代理（特殊情况勾选；不勾选则用上方动态代理池）", variable=self.register_with_payment_proxy).pack(anchor="w", pady=(6, 0))
        extension_row = ttk.Frame(proxy_frame)
        extension_row.pack(fill=X, pady=(8, 0))
        ttk.Label(extension_row, text="支付链接扩展目录").pack(side=LEFT)
        ttk.Entry(extension_row, textvariable=self.payment_extension_dir, width=72).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        ttk.Button(extension_row, text="选择目录", command=self.select_payment_extension_dir).pack(side=LEFT, padx=(0, 8))
        ttk.Label(extension_row, text="需选择解压后的 Chrome 扩展目录").pack(side=LEFT)

        custom_mail_frame = ttk.Frame(tabs, padding=8)
        tabs.add(custom_mail_frame, text="自定义邮箱API")
        ttk.Label(custom_mail_frame, text="使用 email----key 格式导入邮箱后，通过 API 获取验证码。").pack(anchor="w")
        custom_url_row = ttk.Frame(custom_mail_frame)
        custom_url_row.pack(fill=X, pady=(8, 0))
        ttk.Label(custom_url_row, text="API 地址").pack(side=LEFT)
        ttk.Entry(custom_url_row, textvariable=self.custom_api_url, width=72).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        custom_admin_row = ttk.Frame(custom_mail_frame)
        custom_admin_row.pack(fill=X, pady=(8, 0))
        ttk.Label(custom_admin_row, text="Admin Key").pack(side=LEFT)
        ttk.Entry(custom_admin_row, textvariable=self.custom_api_admin_key, width=36, show="*").pack(side=LEFT, padx=(8, 8))
        ttk.Label(custom_admin_row, text="管理员登录密码").pack(side=LEFT)
        custom_poll_row = ttk.Frame(custom_mail_frame)
        custom_poll_row.pack(fill=X, pady=(8, 0))
        ttk.Label(custom_poll_row, text="轮询间隔(秒)").pack(side=LEFT)
        ttk.Entry(custom_poll_row, textvariable=self.custom_api_poll_interval, width=8).pack(side=LEFT, padx=(8, 8))
        custom_first_delay_row = ttk.Frame(custom_mail_frame)
        custom_first_delay_row.pack(fill=X, pady=(8, 0))
        ttk.Label(custom_first_delay_row, text="首次延迟(秒)").pack(side=LEFT)
        ttk.Entry(custom_first_delay_row, textvariable=self.custom_api_first_delay, width=8).pack(side=LEFT, padx=(8, 8))
        ttk.Label(custom_first_delay_row, text="首次获取验证码前等待的时间").pack(side=LEFT)
        custom_pass_row = ttk.Frame(custom_mail_frame)
        custom_pass_row.pack(fill=X, pady=(8, 0))
        ttk.Label(custom_pass_row, text="自定义密码").pack(side=LEFT)
        ttk.Entry(custom_pass_row, textvariable=self.custom_api_password, width=24).pack(side=LEFT, padx=(8, 8))
        ttk.Label(custom_pass_row, text="留空=自动生成；填入则在密码步骤直接使用").pack(side=LEFT)
        ttk.Label(custom_mail_frame, text="请求格式: POST JSON {adminKey, credential: email----key}，响应中包含验证码。").pack(anchor="w", pady=(12, 4))
        ttk.Label(custom_mail_frame, text="邮箱格式: email (管理员模式无需key)；Hotmail: email----password----client_id----refresh_token (4段)").pack(anchor="w")

        controls = ttk.Frame(main)
        controls.pack(fill=X, pady=(0, 4))
        row1 = ttk.Frame(controls)
        row1.pack(fill=X)
        ttk.Button(row1, text="导入到列表", command=self.import_accounts).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="清空列表", command=self.clear_accounts).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="删除选中邮箱", command=self.delete_selected_account).pack(side=LEFT, padx=(0, 16))
        ttk.Button(row1, text="设为 Plus", command=lambda: self.set_selected_account_type("plus")).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="设为 Team", command=lambda: self.set_selected_account_type("team")).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="设为 Free", command=lambda: self.set_selected_account_type("free")).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="刷新类型", command=self.refresh_selected_account_type).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="授权获取RT", command=self.start_authorize_selected).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="Team随机注册获取RT", command=self.start_team_random_register).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="导出已授权", command=self.export_authorized).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="导出邮箱RT", command=self.export_authorized_email_rt).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="导出sub2api", command=self.export_sub2api).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row1, text="停止当前任务", command=self.stop_current_task).pack(side=LEFT)

        row2 = ttk.Frame(controls)
        row2.pack(fill=X, pady=(6, 0))
        ttk.Label(row2, text="支付模式").pack(side=LEFT)
        ttk.Combobox(row2, textvariable=self.payment_mode, values=list(PAYMENT_MODES.keys()), state="readonly", width=22).pack(side=LEFT, padx=8)
        ttk.Checkbutton(row2, text="无头浏览器", variable=self.headless).pack(side=LEFT, padx=8)
        ttk.Button(row2, text="注册并获取Session信息", command=self.start_selected).pack(side=LEFT, padx=(16, 8))
        ttk.Button(row2, text="用Session生成长链接", command=self.generate_link_from_selected_session).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row2, text="粘贴Session生成", command=self.generate_link_from_pasted_session).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row2, text="批量提取选中长链", command=self.generate_links_from_selected_sessions).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row2, text="切换支付代理", command=self.switch_current_trial_to_payment_proxy).pack(side=LEFT, padx=(0, 8))
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
        ttk.Label(result_header, text="当前选中邮箱链接（旧功能）").pack(side=LEFT)
        ttk.Button(result_header, text="批量打开选中", command=self.open_selected_links).pack(side=RIGHT, padx=(0, 8))
        ttk.Button(result_header, text="浏览器打开", command=self.open_link).pack(side=RIGHT)
        ttk.Button(result_header, text="用提链代理打开", command=self.open_link_with_extraction_proxy).pack(side=RIGHT, padx=(0, 8))
        ttk.Button(result_header, text="复制长链接", command=self.copy_link).pack(side=RIGHT, padx=(0, 8))

        link_bar = ttk.Frame(right)
        link_bar.pack(fill=X, pady=(6, 8))
        self.link_var = StringVar(value="")
        ttk.Entry(link_bar, textvariable=self.link_var).pack(side=LEFT, fill=X, expand=True)

        proxy_bar = ttk.Frame(right)
        proxy_bar.pack(fill=X, pady=(0, 8))
        ttk.Label(proxy_bar, text="长链使用代理").pack(side=LEFT)
        self.link_proxy_var = StringVar(value="")
        ttk.Entry(proxy_bar, textvariable=self.link_proxy_var).pack(side=LEFT, fill=X, expand=True, padx=(8, 8))
        ttk.Button(proxy_bar, text="复制代理", command=self.copy_link_proxy).pack(side=LEFT)

        session_header = ttk.Frame(right)
        session_header.pack(fill=X, pady=(4, 0))
        ttk.Label(session_header, text="当前选中邮箱 Session 信息").pack(side=LEFT)
        ttk.Button(session_header, text="复制 Access Token", command=self.copy_access_token).pack(side=RIGHT, padx=(0, 8))
        ttk.Button(session_header, text="复制 Session JSON", command=self.copy_session_json).pack(side=RIGHT, padx=(0, 8))
        self.session_text = ScrolledText(right, height=5)
        self.session_text.pack(fill=X, pady=(6, 8))

    def load_state(self) -> None:
        if not STATE_FILE.exists():
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.accounts = [account_from_dict(item) for item in data.get("accounts", [])]
            self.phones = [phone_from_dict(item) for item in data.get("phones", []) if item]
            self.payment_cards = [payment_card_from_dict(item) for item in data.get("payment_cards", []) if item]
            self.results = {str(k): str(v) for k, v in data.get("results", {}).items() if v}
            raw_sessions = data.get("session_results", {})
            self.session_results = {str(k): v for k, v in raw_sessions.items() if isinstance(v, dict)} if isinstance(raw_sessions, dict) else {}
            settings = data.get("settings", {})
            saved_payment_mode = str(settings.get("payment_mode") or "")
            if saved_payment_mode in PAYMENT_MODES:
                self.payment_mode.set(saved_payment_mode)
            elif saved_payment_mode in PAYMENT_MODE_ALIASES:
                self.payment_mode.set(PAYMENT_MODE_ALIASES[saved_payment_mode])
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
            if "reuse_payment_proxy" in settings:
                self.reuse_payment_proxy.set(str(settings["reuse_payment_proxy"]))
            if "require_japan_extract_proxy" in settings:
                self.require_japan_extract_proxy.set(bool(settings["require_japan_extract_proxy"]))
            if "register_with_payment_proxy" in settings:
                self.register_with_payment_proxy.set(bool(settings["register_with_payment_proxy"]))
            if "payment_extension_dir" in settings:
                self.payment_extension_dir.set(str(settings["payment_extension_dir"]).strip() or DEFAULT_PAYPAL_EXTENSION_DIR)
            if "br_stripe_proxy" in settings:
                self.br_stripe_proxy_text.delete("1.0", END)
                self.br_stripe_proxy_text.insert(END, str(settings["br_stripe_proxy"]))
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
            if "custom_api_url" in settings:
                self.custom_api_url.set(str(settings["custom_api_url"]))
            if "custom_api_admin_key" in settings:
                self.custom_api_admin_key.set(str(settings["custom_api_admin_key"]))
            if "custom_api_poll_interval" in settings:
                self.custom_api_poll_interval.set(max(1, int(settings["custom_api_poll_interval"] or 5)))
            if "custom_api_password" in settings:
                self.custom_api_password.set(str(settings["custom_api_password"]))
            if "custom_api_first_delay" in settings:
                self.custom_api_first_delay.set(max(0, int(settings["custom_api_first_delay"] or 5)))
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
            "session_results": self.session_results,
            "settings": {
                "payment_mode": self.payment_mode.get(),
                "headless": bool(self.headless.get()),
                "local_proxy": self.local_proxy.get(),
                "dynamic_proxies": self.proxy_text.get("1.0", END).strip(),
                "payment_dynamic_proxy": self.payment_dynamic_proxy_text.get("1.0", END).strip(),
                "reuse_payment_proxy": self.reuse_payment_proxy.get().strip(),
                "require_japan_extract_proxy": bool(self.require_japan_extract_proxy.get()),
                "register_with_payment_proxy": bool(self.register_with_payment_proxy.get()),
                "payment_extension_dir": self.payment_extension_dir.get().strip(),
                "br_stripe_proxy": self.br_stripe_proxy_text.get("1.0", END).strip(),
                "paypal_phone": self.paypal_phone.get().strip(),
                "paypal_card": self.paypal_card.get().strip(),
                "paypal_sms_url": self.paypal_sms_url.get().strip(),
                "paypal_phone_pool": self.paypal_phone_pool_text.get("1.0", END).strip(),
                "export_name_prefix": self.export_name_prefix.get().strip(),
                "phone_max_receive_count": max(0, int(self.phone_max_receive_count.get() or 0)),
                "paypal_phone_pool_index": self.paypal_phone_pool_index,
                "custom_api_url": self.custom_api_url.get().strip(),
                "custom_api_admin_key": self.custom_api_admin_key.get().strip(),
                "custom_api_poll_interval": max(1, int(self.custom_api_poll_interval.get() or 5)),
                "custom_api_password": self.custom_api_password.get().strip(),
                "custom_api_first_delay": max(0, int(self.custom_api_first_delay.get() or 5)),
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
                account.auth_phone_number = account.auth_phone_number or self.accounts[old_index].auth_phone_number
                account.auth_phone_sms_url = account.auth_phone_sms_url or self.accounts[old_index].auth_phone_sms_url
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
            if account_type == "team":
                account.status = account.status or "Team待注册"
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
            account.status = "Team" if account_type == "team" else "已绑定手机号" if account_type == "plus" else "Free"
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

    def start_team_random_register(self) -> None:
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        email_addr = generate_team_email()
        account = MailAccount(
            email=email_addr,
            password="",
            client_id="",
            refresh_token="",
            raw=email_addr,
            account_type="team",
            status="Team待注册",
        )
        self.accounts.append(account)
        self._render_accounts()
        self._select_account_by_email(email_addr)
        self.running = True
        self.stop_event.clear()
        self.save_state()
        mode = self.payment_mode.get()
        headless = bool(self.headless.get())
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        use_payment_proxy_for_register = bool(self.register_with_payment_proxy.get())
        dynamic_proxy = self._peek_payment_dynamic_proxy() if use_payment_proxy_for_register else (self._take_dynamic_proxies(1)[0] if self._read_dynamic_proxies() else "")
        threading.Thread(target=self._run_team_account_worker, args=(account, mode, headless, local_proxy, dynamic_proxy, use_payment_proxy_for_register), daemon=True).start()

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
                flow = OpenAIJsonAuthFlow(account, lambda msg: self.events.put(("log", msg)), self._phone_provider, self._request_user_input, chain.url, self.custom_api_url.get().strip(), self.custom_api_admin_key.get().strip(), self.custom_api_poll_interval.get(), self.custom_api_first_delay.get(), self.custom_api_password.get().strip())
                record = flow.run()
            account.openai_rt = str(record.get("refresh_token") or "")
            if not account.openai_rt:
                raise RuntimeError("授权成功但未获取到 refresh_token")
            if account.account_type != "team":
                account.account_type = "plus"
            account.status = "RT已获取"
            self.events.put(("account-updated", account.email))
            self.events.put(("status", account.email, account.status))
            self.events.put(("log", f"[{account.email}] RT 获取成功，已标记为{account.status}"))
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
            requested_country = str((payload or {}).get("country") or "").upper() if isinstance(payload, dict) else ""
            with self.phone_lock:
                for account in self.accounts:
                    if account.email.lower() != email_addr.lower():
                        continue
                    if account.auth_phone_number and account.auth_phone_sms_url:
                        if requested_country == "US" and not account.auth_phone_number.startswith("+1"):
                            break
                        self.events.put(("log", f"[{email_addr}] 使用导入授权手机号: {account.auth_phone_number}"))
                        return {"number": account.auth_phone_number, "sms_url": account.auth_phone_sms_url, "account_bound": True}
                    break
                for phone in self.phones:
                    if requested_country == "US" and not phone.number.startswith("+1"):
                        continue
                    if self._phone_is_frozen(phone):
                        if phone.status != "冻结":
                            phone.status = "冻结"
                            self.events.put(("phones-updated",))
                        continue
                    if phone.status not in {"不可用", "冻结", "使用中"}:
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
            return self._wait_for_phone_code(str(payload.get("number") or ""), str(payload.get("sms_url") or ""), timeout=120)
        if action == "bad":
            number = str(payload.get("number") or "")
            error = str(payload.get("error") or "")
            if bool(payload.get("account_bound")):
                self.events.put(("log", f"[{email_addr}] 导入授权手机号不可用: {number} {error}"))
                return {}
            with self.phone_lock:
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
        deadline = started + timeout
        last_text = ""
        while time.time() < deadline:
            try:
                request_timeout = max(1, min(20, int(deadline - time.time())))
                response = requests.get(sms_url, timeout=request_timeout)
                text = response.text.strip()
                last_text = text[:300]
                code = self._extract_phone_code(text)
                if code:
                    with self.phone_lock:
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
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            time.sleep(min(5, remaining))
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

    def _read_br_stripe_proxies(self) -> list[str]:
        lines = [line.strip() for line in self.br_stripe_proxy_text.get("1.0", END).splitlines() if line.strip()]
        return [normalize_proxy_url(line) for line in lines]

    def _remove_br_stripe_proxy(self, proxy_url: str) -> bool:
        target = normalize_proxy_url(proxy_url)
        if not target:
            return False
        lines = [line.strip() for line in self.br_stripe_proxy_text.get("1.0", END).splitlines() if line.strip()]
        kept = []
        removed = False
        for line in lines:
            if not removed and normalize_proxy_url(line) == target:
                removed = True
                continue
            kept.append(line)
        if not removed:
            return False
        rest = "\n".join(kept)
        self.br_stripe_proxy_text.delete("1.0", END)
        if rest:
            self.br_stripe_proxy_text.insert(END, rest)
        self.save_state()
        self.log(f"BR Stripe代理不可用已移除: {mask_proxy_url(target)}")
        return True

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
        self.log(f"注册/获取 Session 动态代理已取用并移除 {len(proxies)} 个")
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

    def _remove_payment_dynamic_proxy_value(self, proxy_url: str) -> bool:
        target = normalize_proxy_url(proxy_url)
        if not target:
            return False
        lines = [line.strip() for line in self.payment_dynamic_proxy_text.get("1.0", END).splitlines() if line.strip()]
        kept = []
        removed = False
        for line in lines:
            if not removed and normalize_proxy_url(line) == target:
                removed = True
                continue
            kept.append(line)
        if not removed:
            return False
        rest = "\n".join(kept)
        self.payment_dynamic_proxy_text.delete("1.0", END)
        if rest:
            self.payment_dynamic_proxy_text.insert(END, rest)
        self.payment_dynamic_proxy.set(rest)
        self.save_state()
        self.log(f"失败支付代理已移除: {mask_proxy_url(target)}")
        return True

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
        if account.account_type == "team":
            self._run_team_account_once(account, mode, headless, local_proxy, register_dynamic_proxy, use_payment_proxy_for_register)
            return
        self.events.put(("status", account.email, "处理中"))
        try:
            with ProxyChainServer(local_proxy, register_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as register_chain:
                register_proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=register_dynamic_proxy, chain_url=register_chain.url)
                extract_proxy = register_proxy
                register_source = "支付链接动态代理" if use_payment_proxy_for_register else "注册动态代理池"
                self.events.put(("log", f"[{account.email}] 注册使用代理({register_source}): {register_proxy.label}"))
                self.events.put(("log", f"[{account.email}] 获取 Session 复用注册代理: {extract_proxy.label}"))
                worker = OpenAIRegisterPayLinkWorker(account, mode, headless, register_proxy, extract_proxy, lambda msg: self.events.put(("log", msg)), self._phone_provider, self.custom_api_url.get().strip(), self.custom_api_admin_key.get().strip(), self.custom_api_poll_interval.get(), self.custom_api_password.get().strip(), self.custom_api_first_delay.get())
                result = worker.run()
            self.events.put(("account-updated", account.email))
            self.events.put(("result", account.email, result))
            self.events.put(("status", account.email, "Session已获取"))
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 失败: {exc}"))
            self.events.put(("status", account.email, "失败"))

    def _run_team_account_worker(self, account: MailAccount, mode: str, headless: bool, local_proxy: str, dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        try:
            self._run_team_account_once(account, mode, headless, local_proxy, dynamic_proxy, use_payment_proxy_for_register)
        finally:
            self.events.put(("done",))

    def _run_team_account_once(self, account: MailAccount, mode: str, headless: bool, local_proxy: str, register_dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        self.events.put(("status", account.email, "Team注册中"))
        try:
            with ProxyChainServer(local_proxy, register_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as register_chain:
                register_proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=register_dynamic_proxy, chain_url=register_chain.url)
                source = "支付链接动态代理" if use_payment_proxy_for_register else "注册动态代理池"
                self.events.put(("log", f"[{account.email}] Team 注册使用代理({source}): {register_proxy.label}"))
                worker = OpenAIRegisterPayLinkWorker(account, mode, headless, register_proxy, register_proxy, lambda msg: self.events.put(("log", msg)), None, self.custom_api_url.get().strip(), self.custom_api_admin_key.get().strip(), self.custom_api_poll_interval.get(), self.custom_api_password.get().strip(), self.custom_api_first_delay.get())
                result = worker.run_team()
            account.openai_rt = str(result.get("openai_rt") or "")
            if not account.openai_rt:
                raise RuntimeError("Team 注册成功但未获取到 refresh_token")
            account.account_type = "team"
            account.status = "Team RT已获取"
            self.events.put(("account-updated", account.email))
            self.events.put(("result", account.email, result))
            self.events.put(("status", account.email, account.status))
            self.events.put(("log", f"[{account.email}] Team RT 获取成功"))
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] Team 注册失败: {exc}"))
            self.events.put(("status", account.email, "Team失败"))

    def _refetch_account_once(self, account: MailAccount, mode: str, headless: bool, local_proxy: str, register_dynamic_proxy: str, extract_dynamic_proxy: str, use_payment_proxy_for_register: bool) -> None:
        self.events.put(("status", account.email, "重新获取中"))
        with ProxyChainServer(local_proxy, register_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as register_chain, \
             ProxyChainServer(local_proxy, extract_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as extract_chain:
            register_proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=register_dynamic_proxy, chain_url=register_chain.url)
            extract_proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=extract_dynamic_proxy, chain_url=extract_chain.url)
            register_source = "支付链接动态代理" if use_payment_proxy_for_register else "注册动态代理池"
            self.events.put(("log", f"[{account.email}] 重新获取长链接登录使用代理({register_source}): {register_proxy.label}"))
            self.events.put(("log", f"[{account.email}] 重新获取长链接提取使用代理: {extract_proxy.label}"))
            worker = OpenAIRegisterPayLinkWorker(account, mode, headless, register_proxy, extract_proxy, lambda msg: self.events.put(("log", msg)), None, self.custom_api_url.get().strip(), self.custom_api_admin_key.get().strip(), self.custom_api_poll_interval.get(), self.custom_api_password.get().strip(), self.custom_api_first_delay.get())
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
                fingerprint = generate_payment_fingerprint()
                profile_dir = tempfile.mkdtemp(prefix="paylink-profile-")
                self._seed_payment_browser_preferences(profile_dir)
                self.events.put(("log", f"支付窗口全新隔离浏览器环境: {profile_dir}"))
                args = [
                    "--disable-blink-features=AutomationControlled",
                    f"--lang={fingerprint.locale}",
                    f"--window-size={fingerprint.outer_width},{fingerprint.outer_height}",
                    "--disable-features=IsolateOrigins,site-per-process,AutofillServerCommunication,AutofillEnableAccountWalletStorage,AutofillCreditCardUpload,AutofillEnablePaymentsMandatoryReauth",
                    "--disable-save-password-bubble",
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
                    self._install_payment_fingerprint(context, fingerprint)
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
                    paypal_signup_logged: set[str] = set()
                    success_ready_at: dict[int, float] = {}
                    cpay_click_ready_at: dict[int, float] = {}
                    cpay_clicked: set[str] = set()
                    cpay_clicked_url: dict[int, str] = {}
                    self.events.put(("log", "支付链接已在支持扩展的全新 Chromium 窗口打开；关闭窗口后任务结束"))
                    while not self.stop_event.is_set() and context.pages:
                        for current_page in list(context.pages):
                            if current_page.is_closed():
                                continue
                            if "pay.openai.com/c/pay/" in current_page.url:
                                page_id = id(current_page)
                                url_key = f"{page_id}:{current_page.url}"
                                if url_key not in cpay_clicked:
                                    if page_id not in cpay_click_ready_at or cpay_clicked_url.get(page_id, "") != current_page.url:
                                        cpay_click_ready_at[page_id] = time.time() + 5
                                        cpay_clicked_url[page_id] = current_page.url
                                        self.events.put(("log", f"检测到 OpenAI 支付确认页，等待 5 秒后点击确认按钮: {current_page.url[:80]}"))
                                    if time.time() >= cpay_click_ready_at[page_id]:
                                        if self._click_openai_pay_confirm(current_page):
                                            cpay_clicked.add(url_key)
                                            success_ready_at.pop(page_id, None)
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
                                    if self._click_openai_pay_confirm(current_page):
                                        cpay_clicked.add(url_key)
                                        cpay_clicked_url[page_id] = current_page.url
                                        success_ready_at.pop(page_id, None)
                                        self.events.put(("log", f"已点击返回后的 OpenAI 支付确认按钮: {current_page.url[:80]}"))
                                        continue
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
                            current_url = current_page.url
                            current_parts = urlsplit(current_url)
                            is_paypal_agreements_page = current_parts.netloc.lower().endswith("paypal.com") and current_parts.path.startswith("/agreements/approve")
                            if is_paypal_agreements_page:
                                paypal_action = self._handle_paypal_agreements_page(current_page)
                                if paypal_action == "clicked_create_account":
                                    self.events.put(("log", f"已点击 PayPal 创建账户按钮: {current_page.url[:80]}"))
                                    continue
                                if paypal_action == "submitted_signup_email":
                                    self.events.put(("log", f"已填写 PayPal 随机邮箱并点击继续支付: {current_page.url[:80]}"))
                                    continue
                            is_paypal_signup_page = current_parts.netloc.lower() == "www.paypal.com" and current_parts.path.startswith("/checkoutweb/signup")
                            if is_paypal_signup_page:
                                key = f"{id(current_page)}:{current_page.url.split('?')[0]}"
                                if key not in paypal_signup_logged:
                                    paypal_signup_logged.add(key)
                                    self.events.put(("log", f"检测到 PayPal 创建账户页，扩展将自动填写一次: {current_page.url[:80]}"))
                        time.sleep(1)
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as exc:
            err = str(exc)
            if "Target page" in err and "closed" in err.lower():
                self.events.put(("log", "支付窗口已关闭或任务已停止，已取消当前打开流程"))
            else:
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

    def _seed_payment_browser_preferences(self, profile_dir: str) -> None:
        default_dir = Path(profile_dir) / "Default"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
            preferences_path = default_dir / "Preferences"
            if preferences_path.exists():
                return
            preferences = {
                "autofill": {
                    "credit_card_enabled": False,
                    "profile_enabled": False,
                },
                "credentials_enable_service": False,
                "profile": {
                    "password_manager_enabled": False,
                },
                "payments": {
                    "can_make_payment_enabled": False,
                },
            }
            preferences_path.write_text(json.dumps(preferences), encoding="utf-8")
        except Exception as exc:
            self.events.put(("log", f"支付浏览器偏好写入失败，已忽略: {exc}"))

    def _install_payment_fingerprint(self, context, fp: DeviceFingerprint) -> None:
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
            }})();""".replace("__FP_PAYLOAD__", fp_payload)
        )

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

    def _handle_paypal_agreements_page(self, page) -> str:
        try:
            return str(page.evaluate(
                """() => {
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
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    };
                    const randomEmail = () => `pp${Date.now()}${Math.floor(Math.random() * 10000)}@gmail.com`;
                    const candidates = Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"]'));
                    const createBtn = candidates.find(el => {
                        if (!visible(el) || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
                        const text = `${el.textContent || ''} ${el.getAttribute('value') || ''} ${el.getAttribute('aria-label') || ''}`.trim().toLowerCase();
                        return text.includes('アカウントを開設') || text.includes('アカウントを作成') || text.includes('create account') || text.includes('sign up');
                    });
                    if (createBtn) {
                        createBtn.scrollIntoView({ block: 'center' });
                        createBtn.click();
                        return 'clicked_create_account';
                    }
                    const emailInput = Array.from(document.querySelectorAll('input')).find(input => {
                        if (!visible(input) || input.disabled) return false;
                        const meta = `${input.type || ''} ${input.name || ''} ${input.id || ''} ${input.placeholder || ''} ${input.getAttribute('aria-label') || ''}`.toLowerCase();
                        return meta.includes('email') || meta.includes('login_email') || meta.includes('メール');
                    });
                    if (!emailInput || String(emailInput.value || '').trim()) return '';
                    setValue(emailInput, randomEmail());
                    const continueBtn = candidates.find(el => {
                        if (!visible(el) || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
                        const text = `${el.textContent || ''} ${el.getAttribute('value') || ''} ${el.getAttribute('aria-label') || ''}`.trim().toLowerCase();
                        if (/cancel|back|return|キャンセル|戻る/.test(text)) return false;
                        return text.includes('支払いを続ける') || text.includes('continue to payment') || text.includes('continue') || text.includes('次へ');
                    });
                    if (!continueBtn) return '';
                    continueBtn.scrollIntoView({ block: 'center' });
                    continueBtn.click();
                    return 'submitted_signup_email';
                }"""
            ) or "")
        except Exception:
            return ""

    def _autofill_payment_extension(self, page, paypal_phone: str, paypal_card: str, paypal_sms_url: str) -> bool:
        if not paypal_card:
            return False
        try:
            parts = urlsplit(page.url)
            if parts.netloc.lower() != "www.paypal.com" or not parts.path.startswith("/checkoutweb/signup"):
                return False
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
                    email_addr = event[1]
                    payload = event[2]
                    if isinstance(payload, dict):
                        if payload.get("url"):
                            self.results[email_addr] = str(payload.get("url") or "")
                        old_session = self.session_results.get(email_addr, {})
                        self.session_results[email_addr] = {
                            "access_token": str(payload.get("access_token") or old_session.get("access_token") or ""),
                            "session_json": str(payload.get("session_json") or old_session.get("session_json") or ""),
                            "checkout_url": str(payload.get("checkout_url") or old_session.get("checkout_url") or ""),
                            "storage_state_json": str(payload.get("storage_state_json") or old_session.get("storage_state_json") or ""),
                            "openai_rt": str(payload.get("openai_rt") or old_session.get("openai_rt") or ""),
                            "link_proxy": str(payload.get("link_proxy") or old_session.get("link_proxy") or ""),
                            "link_proxy_label": str(payload.get("link_proxy_label") or old_session.get("link_proxy_label") or ""),
                            "link_proxy_exit": str(payload.get("link_proxy_exit") or old_session.get("link_proxy_exit") or ""),
                            "payment_link_type": str(payload.get("payment_link_type") or old_session.get("payment_link_type") or ""),
                        }
                    else:
                        self.results[email_addr] = str(payload)
                    self.link_var.set(self.results.get(email_addr, ""))
                    self._render_results()
                    self._select_account_by_email(email_addr)
                    self.save_state()
                elif kind == "account-updated":
                    self._render_accounts()
                    self.save_state()
                elif kind == "phones-updated":
                    self._render_phones()
                    self.save_state()
                elif kind == "remove-payment-proxy":
                    self._remove_payment_dynamic_proxy_value(event[1])
                elif kind == "export-authorized-ready":
                    self._finish_export_authorized(event[1], event[2])
                elif kind == "export-email-rt-ready":
                    self._finish_export_authorized_email_rt(event[1])
                elif kind == "export-sub2api-ready":
                    self._start_sub2api_export_with_accounts(event[1])
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
            status = account.status or ("Session已获取" if account.email in self.session_results else "成功" if account.email in self.results else "待处理")
            if not account.openai_rt and account.auth_phone_number and account.auth_phone_sms_url and status == "待处理":
                status = "待获取RT(带授权手机号)"
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
            self.link_var.set("")
            self.link_proxy_var.set("")
            return
        index = int(selected[0])
        if index < 0 or index >= len(self.accounts):
            self.link_var.set("")
            self.link_proxy_var.set("")
            return
        email_addr = self.accounts[index].email
        self.link_var.set(self.results.get(email_addr, ""))
        payload = self.session_results.get(email_addr, {})
        self.link_proxy_var.set(str(payload.get("link_proxy") or payload.get("link_proxy_label") or ""))
        self._show_session_result(email_addr)

    def _show_session_result(self, email_addr: str) -> None:
        if not hasattr(self, "session_text"):
            return
        payload = self.session_results.get(email_addr, {})
        access_token = str(payload.get("access_token") or "")
        session_json = str(payload.get("session_json") or "")
        checkout_url = str(payload.get("checkout_url") or "")
        link_proxy = str(payload.get("link_proxy") or "")
        link_proxy_label = str(payload.get("link_proxy_label") or "")
        link_proxy_exit = str(payload.get("link_proxy_exit") or "")
        payment_link_type = str(payload.get("payment_link_type") or "")
        text = ""
        if access_token:
            text += f"Access Token:\n{access_token}\n"
        if checkout_url:
            text += ("\n" if text else "") + f"Checkout URL:\n{checkout_url}\n"
        if payment_link_type:
            text += ("\n" if text else "") + f"Payment Link Type:\n{payment_link_type}\n"
        if link_proxy or link_proxy_label:
            text += ("\n" if text else "") + f"Long Link Proxy:\n{link_proxy or link_proxy_label}\n"
        if link_proxy_exit:
            text += ("\n" if text else "") + f"Long Link Proxy Exit:\n{link_proxy_exit}\n"
        if session_json:
            text += ("\n" if text else "") + f"Session JSON:\n{session_json}"
        self.session_text.delete("1.0", END)
        if text:
            self.session_text.insert(END, text)

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

    def copy_link_proxy(self) -> None:
        proxy_url = self.link_proxy_var.get().strip()
        if not proxy_url:
            messagebox.showwarning(APP_TITLE, "当前选中邮箱暂无长链使用代理")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(proxy_url)
        self.log("长链使用代理已复制到剪贴板")

    def _selected_session_payload(self) -> dict:
        selected = self.account_list.selection()
        if not selected:
            return {}
        try:
            index = int(selected[0])
        except ValueError:
            return {}
        if index < 0 or index >= len(self.accounts):
            return {}
        return self.session_results.get(self.accounts[index].email, {})

    def _selected_account(self) -> MailAccount | None:
        selected = self.account_list.selection()
        if not selected:
            return None
        try:
            index = int(selected[0])
        except ValueError:
            return None
        if index < 0 or index >= len(self.accounts):
            return None
        return self.accounts[index]

    def _create_pasted_session_account(self) -> MailAccount:
        base = datetime.now().strftime("pasted-session-%Y%m%d-%H%M%S")
        existing = {account.email.lower() for account in self.accounts}
        email_addr = base
        counter = 1
        while email_addr.lower() in existing:
            counter += 1
            email_addr = f"{base}-{counter}"
        account = MailAccount(
            email=email_addr,
            password="",
            client_id="",
            refresh_token="",
            raw="",
            account_type="free",
            status="Session已获取",
        )
        self.accounts.append(account)
        self._render_accounts()
        self._select_account_by_email(account.email)
        self.save_state()
        self.log(f"已创建临时 Session 记录: {account.email}")
        return account

    def _start_session_long_link_generation(self, account: MailAccount, access_token: str) -> None:
        self.running = True
        self.stop_event.clear()
        self.save_state()
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        reuse_proxy = normalize_proxy_url(self.reuse_payment_proxy.get())
        payment_dynamic_proxy = reuse_proxy or self._peek_payment_dynamic_proxy()
        if reuse_proxy:
            self.log(f"Session 生成长链接优先使用复用代理: {mask_proxy_url(reuse_proxy)}")
        elif payment_dynamic_proxy:
            self.log(f"Session 生成长链接使用支付代理: {mask_proxy_url(payment_dynamic_proxy)}")
        threading.Thread(target=self._generate_opll_link_from_session_worker, args=(account, access_token, local_proxy, payment_dynamic_proxy), daemon=True).start()

    def generate_link_from_selected_session(self) -> None:
        account = self._selected_account()
        if not account:
            messagebox.showwarning(APP_TITLE, "请先选中一个已获取 Session 的邮箱")
            return
        payload = self.session_results.get(account.email, {})
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            messagebox.showwarning(APP_TITLE, "当前邮箱暂无 Access Token，请先重新执行“注册并获取Session信息”")
            return
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        self._start_session_long_link_generation(account, access_token)

    def generate_link_from_pasted_session(self) -> None:
        account = self._selected_account()
        if not account:
            account = self._create_pasted_session_account()
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        dialog = Toplevel(self.root)
        dialog.title("粘贴 Session JSON")
        dialog.geometry("720x420")
        ttk.Label(dialog, text="粘贴 ChatGPT Session JSON / Access Token").pack(anchor="w", padx=10, pady=(10, 4))
        text_box = ScrolledText(dialog, height=16)
        text_box.pack(fill=BOTH, expand=True, padx=10, pady=(0, 8))

        buttons = ttk.Frame(dialog)
        buttons.pack(fill=X, padx=10, pady=(0, 10))

        def submit() -> None:
            session_text = text_box.get("1.0", END).strip()
            access_token = extract_access_token_from_session_text(session_text)
            if not access_token:
                messagebox.showwarning(APP_TITLE, "未从粘贴内容中解析到 accessToken")
                return
            old_session = self.session_results.get(account.email, {})
            self.session_results[account.email] = {
                **old_session,
                "access_token": access_token,
                "session_json": session_text,
            }
            account.status = "Session已获取"
            self._render_accounts()
            self._select_account_by_email(account.email)
            self._show_selected_account_link()
            self.save_state()
            dialog.destroy()
            self.log(f"[{account.email}] 已从粘贴 Session JSON 解析 Access Token，开始生成长链")
            self._start_session_long_link_generation(account, access_token)

        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side=RIGHT)
        ttk.Button(buttons, text="生成长链", command=submit).pack(side=RIGHT, padx=(0, 8))
        text_box.focus_set()

    def generate_links_from_selected_sessions(self) -> None:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中已获取 Session 的邮箱")
            return
        accounts = []
        missing = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if index < 0 or index >= len(self.accounts):
                continue
            account = self.accounts[index]
            payload = self.session_results.get(account.email, {})
            access_token = str(payload.get("access_token") or "").strip()
            if access_token:
                accounts.append((account, access_token))
            else:
                missing.append(account.email)
        if not accounts:
            messagebox.showwarning(APP_TITLE, "选中的邮箱暂无 Access Token，请先执行“注册并获取Session信息”")
            return
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return
        if missing:
            self.log(f"批量提取跳过无 Access Token 邮箱: {', '.join(missing[:5])}" + (f" 等 {len(missing)} 个" if len(missing) > 5 else ""))
        self.running = True
        self.stop_event.clear()
        self.save_state()
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        reuse_proxy = normalize_proxy_url(self.reuse_payment_proxy.get())
        payment_dynamic_proxies = [reuse_proxy] if reuse_proxy else self._read_payment_dynamic_proxies()
        if reuse_proxy:
            self.log(f"批量提取长链优先使用复用代理: {mask_proxy_url(reuse_proxy)}")
        elif not payment_dynamic_proxies:
            self.log("支付代理池为空，批量提取长链改用当前本地代理")
        threading.Thread(target=self._generate_opll_links_from_sessions_worker, args=(accounts, local_proxy, payment_dynamic_proxies, bool(reuse_proxy)), daemon=True).start()

    def _generate_opll_links_from_sessions_worker(self, accounts: list[tuple[MailAccount, str]], local_proxy: str, payment_dynamic_proxies: list[str], reuse_proxy_enabled: bool = False) -> None:
        try:
            total = len(accounts)
            self.events.put(("log", f"批量并发提取选中长链启动: {total} 个账号"))
            proxy_queue: queue.Queue = queue.Queue()
            if payment_dynamic_proxies:
                for proxy in payment_dynamic_proxies:
                    proxy_queue.put(proxy)
            threads = []
            for index, (account, access_token) in enumerate(accounts, start=1):
                thread = threading.Thread(
                    target=self._generate_opll_link_retry_worker,
                    args=(account, access_token, local_proxy, proxy_queue, index, total, reuse_proxy_enabled),
                    daemon=True,
                )
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
        finally:
            self.events.put(("done",))

    def _generate_opll_link_retry_worker(self, account: MailAccount, access_token: str, local_proxy: str, proxy_queue: queue.Queue, index: int, total: int, reuse_proxy_enabled: bool = False) -> None:
        attempt = 0
        if reuse_proxy_enabled:
            payment_dynamic_proxy = str(proxy_queue.queue[0] if proxy_queue.qsize() else "")
            self.events.put(("log", f"[{account.email}] 批量提取长链使用复用代理({index}/{total}): {mask_proxy_url(payment_dynamic_proxy)}"))
            self._generate_opll_link_for_account(account, access_token, local_proxy, payment_dynamic_proxy)
            return
        if proxy_queue.empty():
            self.events.put(("log", f"[{account.email}] 批量提取长链使用本地代理({index}/{total})"))
            self._generate_opll_link_for_account(account, access_token, local_proxy, "")
            return
        while not self.stop_event.is_set():
            try:
                base_payment_proxy = str(proxy_queue.get_nowait())
            except queue.Empty:
                self.events.put(("log", f"[{account.email}] 支付代理池已耗尽，停止重试"))
                self.events.put(("status", account.email, "代理耗尽"))
                return
            attempt += 1
            payment_dynamic_proxy = base_payment_proxy
            if payment_dynamic_proxy:
                self.events.put(("log", f"[{account.email}] 批量提取长链使用支付代理({index}/{total}) 第 {attempt} 次: {mask_proxy_url(payment_dynamic_proxy)}"))
            try:
                ok = self._generate_opll_link_for_account(account, access_token, local_proxy, payment_dynamic_proxy)
            except BRProxiesExhausted:
                self.events.put(("log", f"[{account.email}] BR代理全部失败，停止该账号提取"))
                self.events.put(("status", account.email, "BR代理耗尽"))
                return
            if ok:
                return
            self.events.put(("remove-payment-proxy", base_payment_proxy))
            if self.stop_event.is_set():
                break
            self.events.put(("log", f"[{account.email}] 支付链接生成失败，已移除当前支付代理，换下一个代理继续重试"))
            time.sleep(1)
        self.events.put(("log", f"[{account.email}] 批量生成支付链接已停止"))

    def _generate_opll_link_from_session_worker(self, account: MailAccount, access_token: str, local_proxy: str, payment_dynamic_proxy: str) -> None:
        try:
            self._generate_opll_link_for_account(account, access_token, local_proxy, payment_dynamic_proxy)
        finally:
            self.events.put(("done",))

    def _detect_proxy_exit(self, proxy_url: str) -> str:
        if not proxy_url:
            return "直连"
        try:
            response = requests.get(
                "https://ipinfo.io/json",
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=15,
            )
            if response.status_code >= 400:
                return f"检测失败 HTTP {response.status_code}: {response.text[:120]}"
            payload = response.json() or {}
            ip = str(payload.get("ip") or "").strip()
            country = str(payload.get("country") or "").strip()
            region = str(payload.get("region") or "").strip()
            city = str(payload.get("city") or "").strip()
            org = str(payload.get("org") or "").strip()
            location = "/".join(part for part in (country, region, city) if part)
            return " ".join(part for part in (ip, location, org) if part)
        except Exception as exc:
            return f"检测失败: {exc}"

    def _proxy_exit_is_japan(self, proxy_exit: str) -> bool:
        return bool(re.search(r"(?:^|\s)JP(?:/|\s|$)", str(proxy_exit or "")))

    def _proxy_exit_is_br(self, proxy_exit: str) -> bool:
        return bool(re.search(r"(?:^|\s)BR(?:/|\s|$)", str(proxy_exit or "")))

    def _generate_opll_link_for_account(self, account: MailAccount, access_token: str, local_proxy: str, payment_dynamic_proxy: str) -> bool:
        try:
            if self.stop_event.is_set():
                return False
            mode = PAYMENT_MODES.get(self.payment_mode.get(), PAYMENT_MODES["无卡长链接 US/USD"])
            country = str(mode.get("country") or "US")
            currency = str(mode.get("currency") or currency_for_country(country))
            apple_pay_hosted = bool(mode.get("apple_pay_hosted"))
            is_paypal_br = bool(mode.get("br_stripe_proxy_split"))
            br_stripe_proxies = self._read_br_stripe_proxies() if is_paypal_br else []

            if is_paypal_br and br_stripe_proxies:
                jp_proxy_label = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=payment_dynamic_proxy, chain_url="").label
                self.events.put(("status", account.email, "提取PP链中(BR双代理)"))
                self.events.put(("log", f"[{account.email}] PayPal BR 双代理模式: checkout={jp_proxy_label}, BR代理池共 {len(br_stripe_proxies)} 个"))
                with ProxyChainServer(local_proxy, payment_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as jp_chain:
                    jp_proxy_url = jp_chain.url or local_proxy or payment_dynamic_proxy
                    jp_exit = self._detect_proxy_exit(jp_proxy_url)
                    self.events.put(("log", f"[{account.email}] Checkout代理(JP)出口: {jp_exit}"))
                    if not self._proxy_exit_is_japan(jp_exit):
                        raise RuntimeError(f"Checkout代理出口不是日本: {jp_exit}")
                    last_error = ""
                    for idx, br_proxy in enumerate(br_stripe_proxies, start=1):
                        if self.stop_event.is_set():
                            return False
                        br_proxy_label = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=br_proxy, chain_url="").label
                        self.events.put(("log", f"[{account.email}] 尝试 BR代理 {idx}/{len(br_stripe_proxies)}: {br_proxy_label}"))
                        try:
                            with ProxyChainServer(local_proxy, br_proxy, lambda msg: self.events.put(("log", msg))) as br_chain:
                                stripe_proxy_url = br_chain.url or local_proxy or br_proxy
                                stripe_exit = self._detect_proxy_exit(stripe_proxy_url)
                                self.events.put(("log", f"[{account.email}] Stripe代理出口: {stripe_exit}"))
                                if not self._proxy_exit_is_br(stripe_exit):
                                    raise RuntimeError(f"BR代理出口不是巴西: {stripe_exit}")
                                self.events.put(("log", f"[{account.email}] 生成支付链接: checkout -> {jp_proxy_label} , Stripe -> {br_proxy_label}"))
                                br_log = lambda msg: self.events.put(("log", f"[{account.email}] {msg}"))
                                result = generate_opll_paypal_long_link(access_token, country, currency, stripe_proxy_url, jp_proxy_url, log=br_log)
                                long_url = str(result.get("provider_redirect_url") or result.get("long_url") or "").strip()
                                if not long_url:
                                    raise RuntimeError(f"接口提取成功但没有返回 PayPal approve 长链: {result}")
                                if not opll_is_paypal_ba_approve_url(long_url):
                                    raise RuntimeError(f"返回的不是 PayPal BA approve 长链，拒绝保存: {long_url[:160]}")
                                self.events.put(("result", account.email, {"url": long_url, "checkout_url": long_url, "access_token": access_token, "link_proxy": stripe_proxy_url, "link_proxy_label": f"checkout={jp_proxy_label} stripe={br_proxy_label}", "link_proxy_exit": stripe_exit, "payment_link_type": "paypal_approve"}))
                                self.events.put(("status", account.email, "长链已提取"))
                                self.events.put(("log", f"[{account.email}] PayPal BA approve 长链提取完成(BR双代理 {idx}/{len(br_stripe_proxies)}): {long_url}"))
                        except Exception as exc:
                            last_error = str(exc)
                            self.events.put(("log", f"[{account.email}] BR代理 {idx}/{len(br_stripe_proxies)} 不可用: {last_error[:200]}"))
                            self._remove_br_stripe_proxy(br_proxy)
                            continue
                        return True
                    raise BRProxiesExhausted(f"所有 {len(br_stripe_proxies)} 个 BR代理均失败: {last_error[:200]}")
                return True

            proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=payment_dynamic_proxy, chain_url="")
            used_proxy = payment_dynamic_proxy or local_proxy
            self.events.put(("status", account.email, "生成ApplePay页中" if apple_pay_hosted else "提取PP链中"))
            self.events.put(("log", f"[{account.email}] {'生成 Apple Pay hosted 支付页' if apple_pay_hosted else '按截图逻辑提取 PayPal approve 长链'}，代理: {proxy.label}"))
            with ProxyChainServer(local_proxy, payment_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as chain:
                proxy_url = chain.url or local_proxy or payment_dynamic_proxy
                proxy_exit = self._detect_proxy_exit(proxy_url)
                self.events.put(("log", f"[{account.email}] 提链代理出口: {proxy_exit}"))
                if bool(self.require_japan_extract_proxy.get()) and not self._proxy_exit_is_japan(proxy_exit):
                    self.events.put(("status", account.email, "代理非日本"))
                    raise RuntimeError(f"提链代理出口不是日本，已停止本次提取: {proxy_exit}")
                if apple_pay_hosted:
                    result = generate_opll_hosted_long_link(access_token, country, currency, proxy_url)
                    long_url = str(result.get("long_url") or result.get("stripe_hosted_url") or "").strip()
                    if not long_url:
                        raise RuntimeError(f"接口生成成功但没有返回 Apple Pay 支付页链接: {result}")
                    self.events.put(("result", account.email, {"url": long_url, "checkout_url": long_url, "access_token": access_token, "link_proxy": used_proxy, "link_proxy_label": proxy.label, "link_proxy_exit": proxy_exit, "payment_link_type": "apple_pay_hosted"}))
                    self.events.put(("status", account.email, "ApplePay页已生成"))
                    self.events.put(("log", f"[{account.email}] Apple Pay hosted 支付页已生成，请用 Safari/iPhone/Mac 打开并手动付款: {long_url}"))
                else:
                    log_cb = lambda msg: self.events.put(("log", f"[{account.email}] {msg}"))
                    result = generate_opll_paypal_long_link(access_token, country, currency, proxy_url, log=log_cb)
                    long_url = str(result.get("provider_redirect_url") or result.get("long_url") or "").strip()
                    if not long_url:
                        raise RuntimeError(f"接口提取成功但没有返回 PayPal approve 长链: {result}")
                    if not opll_is_paypal_ba_approve_url(long_url):
                        raise RuntimeError(f"返回的不是 PayPal BA approve 长链，拒绝保存: {long_url[:160]}")
                    self.events.put(("result", account.email, {"url": long_url, "checkout_url": long_url, "access_token": access_token, "link_proxy": used_proxy, "link_proxy_label": proxy.label, "link_proxy_exit": proxy_exit, "payment_link_type": "paypal_approve"}))
                    self.events.put(("status", account.email, "长链已提取"))
                    self.events.put(("log", f"[{account.email}] PayPal BA approve 长链提取完成: {long_url}"))
                return True
        except BRProxiesExhausted:
            self.events.put(("log", f"[{account.email}] BR代理全部失败，停止提取"))
            self.events.put(("status", account.email, "BR代理耗尽"))
            raise
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 接口提取长链失败: {exc}"))
            self.events.put(("status", account.email, "提取长链失败"))
        return False

    def _open_trial_payment_from_session_worker(self, account: MailAccount, storage_state_text: str, local_proxy: str, payment_dynamic_proxy: str) -> None:
        context = None
        try:
            self.events.put(("status", account.email, "打开试用页中"))
            storage_state = json.loads(storage_state_text)
            register_dynamic_proxy = ""
            kept = KEPT_REGISTER_BROWSER_SESSIONS.get(account.email.lower())
            if kept:
                try:
                    register_context, _register_browser = kept[0], kept[1]
                    storage_state = register_context.storage_state()
                    if len(kept) >= 3:
                        register_dynamic_proxy = str(kept[2] or "")
                except Exception:
                    pass
            with ProxyChainServer(local_proxy, register_dynamic_proxy, lambda msg: self.events.put(("log", msg))) as chain:
                proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=register_dynamic_proxy, chain_url=chain.url)
                self.events.put(("log", f"[{account.email}] 打开试用页阶段使用注册代理: {proxy.label}"))
                self.trial_proxy_chain = chain
                self.trial_payment_dynamic_proxy = payment_dynamic_proxy
                self.trial_account_email = account.email
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=False,
                        args=["--disable-blink-features=AutomationControlled", "--disable-features=IsolateOrigins,site-per-process"],
                        proxy={"server": chain.url} if chain.url else None,
                    )
                    context = browser.new_context(storage_state=storage_state, user_agent=DEFAULT_USER_AGENT, locale="en-US", timezone_id="America/New_York")
                    self.payment_context = context
                    self.payment_contexts.add(context)
                    page = context.new_page()
                    page.goto("https://chatgpt.com/?promo_campaign=plus-1-month-free#pricing", wait_until="domcontentloaded", timeout=300000)
                    self.events.put(("status", account.email, "试用页已打开"))
                    self.events.put(("log", f"[{account.email}] 已用注册代理打开试用页面。看到领取按钮后，请先点软件里的“切换支付代理”，再手动点击网页按钮"))
                    while not self.stop_event.is_set() and context.pages:
                        time.sleep(1)
        except Exception as exc:
            self.events.put(("log", f"[{account.email}] 打开试用支付页失败: {exc}"))
            self.events.put(("status", account.email, "打开支付页失败"))
        finally:
            if context in self.payment_contexts:
                self.payment_contexts.discard(context)
            self.payment_context = None
            if self.trial_account_email == account.email:
                self.trial_proxy_chain = None
                self.trial_payment_dynamic_proxy = ""
                self.trial_account_email = ""
            self.events.put(("done",))

    def _switch_trial_click_proxy(self, account: MailAccount, chain: ProxyChainServer, local_proxy: str, payment_dynamic_proxy: str) -> None:
        chain.set_dynamic_proxy(payment_dynamic_proxy)
        proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=payment_dynamic_proxy, chain_url=chain.url)
        self.events.put(("log", f"[{account.email}] 已找到试用按钮，点击前切换到支付代理: {proxy.label}"))
        time.sleep(1)

    def switch_current_trial_to_payment_proxy(self) -> None:
        if not self.trial_proxy_chain or not self.trial_account_email:
            messagebox.showwarning(APP_TITLE, "当前没有打开中的试用页窗口")
            return
        payment_dynamic_proxy = str(self.trial_payment_dynamic_proxy or "").strip()
        if not payment_dynamic_proxy:
            messagebox.showwarning(APP_TITLE, "当前没有已取用的支付链接动态代理，请重新打开试用页")
            return
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        self.trial_proxy_chain.set_dynamic_proxy(payment_dynamic_proxy)
        proxy = ProxyConfig(local_proxy=local_proxy, dynamic_proxy=payment_dynamic_proxy, chain_url=self.trial_proxy_chain.url)
        self.log(f"[{self.trial_account_email}] 已手动切换到支付代理: {proxy.label}，现在可以手动点击网页里的领取按钮")

    def _click_trial_claim_button(self, page, before_click=None) -> bool:
        deadline = time.time() + 300
        while time.time() < deadline:
            try:
                found = page.evaluate(
                    """() => {
                        const visible = el => {
                            if (!el) return false;
                            const r = el.getBoundingClientRect();
                            const s = getComputedStyle(el);
                            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                        };
                        const enabled = el => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                        const clickableFor = el => el?.closest?.('button, a, [role="button"], [onclick], [tabindex]') || el;
                        const candidates = Array.from(new Set([
                            ...Array.from(document.querySelectorAll('button, a, [role="button"], [onclick], [tabindex]')),
                            ...Array.from(document.querySelectorAll('body *')).map(clickableFor),
                        ])).filter(el => visible(el) && enabled(el));
                        const score = el => {
                            const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''} ${el.getAttribute('data-testid') || ''}`.trim();
                            if (/Claim[\t\n\r ]*free[\t\n\r ]*offer|领取[\t\n\r ]*Plus|Plus[\t\n\r ]*免费|免费优惠|無料.*Plus|Plus.*無料|Claim[\t\n\r ]*Plus|Get[\t\n\r ]*Plus|Start.*trial|free.*trial|Try[\t\n\r ]*Plus/i.test(text)) return 10;
                            if (/Plus/i.test(text) && /free|trial|claim|get|start|upgrade|subscribe|continue|领取|免费|無料|続行|開始|アップグレード/i.test(text)) return 8;
                            if (/claim|get|start|upgrade|subscribe|continue|领取|免费|無料|続行|開始|購入|登録/i.test(text)) return 3;
                            return 0;
                        };
                        const target = candidates
                            .map(el => ({ el, score: score(el) }))
                            .filter(item => item.score > 0)
                            .sort((a, b) => b.score - a.score)[0]?.el;
                        if (!target) return false;
                        target.scrollIntoView({ block: 'center' });
                        return true;
                    }"""
                )
                if found:
                    if before_click:
                        before_click()
                    clicked = False
                    try:
                        button = page.get_by_text("Claim free offer", exact=True).first
                        button.click(timeout=5000)
                        clicked = True
                    except Exception:
                        clicked = page.evaluate(
                        """() => {
                            const visible = el => {
                                if (!el) return false;
                                const r = el.getBoundingClientRect();
                                const s = getComputedStyle(el);
                                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                            };
                            const enabled = el => el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                            const clickableFor = el => el?.closest?.('button, a, [role="button"], [onclick], [tabindex]') || el;
                            const candidates = Array.from(new Set([
                                ...Array.from(document.querySelectorAll('button, a, [role="button"], [onclick], [tabindex]')),
                                ...Array.from(document.querySelectorAll('body *')).map(clickableFor),
                            ])).filter(el => visible(el) && enabled(el));
                            const score = el => {
                                const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''} ${el.getAttribute('data-testid') || ''}`.trim();
                                if (/Claim[\t\n\r ]*free[\t\n\r ]*offer|领取[\t\n\r ]*Plus|Plus[\t\n\r ]*免费|免费优惠|無料.*Plus|Plus.*無料|Claim[\t\n\r ]*Plus|Get[\t\n\r ]*Plus|Start.*trial|free.*trial|Try[\t\n\r ]*Plus/i.test(text)) return 10;
                                if (/Plus/i.test(text) && /free|trial|claim|get|start|upgrade|subscribe|continue|领取|免费|無料|続行|開始|アップグレード/i.test(text)) return 8;
                                if (/claim|get|start|upgrade|subscribe|continue|领取|免费|無料|続行|開始|購入|登録/i.test(text)) return 3;
                                return 0;
                            };
                            const target = candidates
                                .map(el => ({ el, score: score(el) }))
                                .filter(item => item.score > 0)
                                .sort((a, b) => b.score - a.score)[0]?.el;
                            if (!target) return false;
                            target.scrollIntoView({ block: 'center' });
                            target.click();
                            return true;
                        }"""
                        )
                    if not clicked:
                        return False
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def copy_access_token(self) -> None:
        token = str(self._selected_session_payload().get("access_token") or "").strip()
        if not token:
            messagebox.showwarning(APP_TITLE, "当前邮箱暂无 Access Token")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(token)
        self.log("Access Token 已复制到剪贴板")

    def copy_session_json(self) -> None:
        session_json = str(self._selected_session_payload().get("session_json") or "").strip()
        if not session_json:
            messagebox.showwarning(APP_TITLE, "当前邮箱暂无 Session JSON")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(session_json)
        self.log("Session JSON 已复制到剪贴板")

    def _preview_and_save_text(self, title: str, text: str, default_extension: str = ".txt", filetypes=None, extra_buttons: list | None = None) -> str:
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
        if extra_buttons:
            for label, cmd in extra_buttons:
                ttk.Button(buttons, text=label, command=cmd).pack(side=LEFT, padx=(8, 0))
        ttk.Button(buttons, text="取消", command=cancel).pack(side=RIGHT)
        ttk.Button(buttons, text="确定导出", command=confirm_export).pack(side=RIGHT, padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(dialog)
        return result["path"]

    def export_authorized(self) -> None:
        accounts = self._selected_accounts_for_export()
        if not accounts:
            return
        if self._ensure_export_accounts_have_rt(accounts, "authorized"):
            return
        self._finish_export_authorized(accounts, self.export_name_prefix.get().strip())

    def _finish_export_authorized(self, accounts: list[MailAccount], prefix: str) -> None:
        accounts = [account for account in accounts if account.openai_rt]
        if not accounts:
            messagebox.showwarning(APP_TITLE, "没有可导出的已授权 RT")
            return
        text = "\n".join(account_export_line(account, prefix) for account in accounts) + "\n"
        path = self._preview_and_save_text("导出已授权邮箱", text)
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self.log(f"已导出 {len(accounts)} 个已授权邮箱 TXT: {path}")

    def export_authorized_email_rt(self) -> None:
        accounts = self._selected_accounts_for_export()
        if not accounts:
            return
        if self._ensure_export_accounts_have_rt(accounts, "email_rt"):
            return
        self._finish_export_authorized_email_rt(accounts)

    def _finish_export_authorized_email_rt(self, accounts: list[MailAccount]) -> None:
        accounts = [account for account in accounts if account.openai_rt]
        if not accounts:
            messagebox.showwarning(APP_TITLE, "没有可导出的已授权 RT")
            return
        text = "\n".join(f"{account.email}----{account.openai_rt}" for account in accounts) + "\n"

        def copy_rt_only() -> None:
            rt_only = "\n".join(account.openai_rt for account in accounts)
            self.root.clipboard_clear()
            self.root.clipboard_append(rt_only)
            self.log(f"已复制 {len(accounts)} 个 RT 到剪贴板")

        path = self._preview_and_save_text("导出邮箱----RT", text, extra_buttons=[("复制RT", copy_rt_only)])
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self.log(f"已导出 {len(accounts)} 个邮箱----RT TXT: {path}")

    def _selected_accounts_for_export(self) -> list[MailAccount]:
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先在左侧选择要导出的邮箱，可多选")
            return []
        selected_accounts = []
        for item in selected:
            try:
                index = int(item)
            except ValueError:
                continue
            if 0 <= index < len(self.accounts):
                selected_accounts.append(self.accounts[index])
        return selected_accounts

    def _selected_authorized_accounts(self) -> list[MailAccount]:
        accounts = [account for account in self._selected_accounts_for_export() if account.openai_rt]
        if not accounts:
            messagebox.showwarning(APP_TITLE, "选中的邮箱里没有已授权 RT")
        return accounts

    def _ensure_export_accounts_have_rt(self, accounts: list[MailAccount], export_kind: str) -> bool:
        missing = [account for account in accounts if not account.openai_rt]
        if not missing:
            return False
        if self.running:
            messagebox.showinfo(APP_TITLE, "任务正在运行")
            return True
        preview = "\n".join(account.email for account in missing[:12])
        if len(missing) > 12:
            preview += f"\n... 另有 {len(missing) - 12} 个"
        if not messagebox.askyesno(APP_TITLE, f"选中邮箱中有 {len(missing)} 个没有 RT，将先自动授权获取 RT 后再导出。\n{preview}\n\n是否继续？"):
            return True
        self.running = True
        self.stop_event.clear()
        self.save_state()
        local_proxy = normalize_proxy_url(self.local_proxy.get())
        dynamic_proxies = self._read_dynamic_proxies()
        threading.Thread(target=self._authorize_missing_rt_then_export_worker, args=(accounts, missing, local_proxy, dynamic_proxies, export_kind, self.export_name_prefix.get().strip()), daemon=True).start()
        return True

    def _authorize_missing_rt_then_export_worker(self, accounts: list[MailAccount], missing: list[MailAccount], local_proxy: str, dynamic_proxies: list[str], export_kind: str, prefix: str) -> None:
        done_sent = False
        try:
            self.events.put(("log", f"导出前自动获取 RT: {len(missing)} 个账号"))
            for account in missing:
                if self.stop_event.is_set():
                    self.events.put(("log", "导出前授权任务已手动停止"))
                    break
                dynamic_proxy = self._next_dynamic_proxy(dynamic_proxies)
                self._authorize_account_once(account, local_proxy, dynamic_proxy)
            ready = [account for account in accounts if account.openai_rt]
            failed = [account.email for account in accounts if not account.openai_rt]
            if failed:
                self.events.put(("log", f"以下账号仍无 RT，导出时跳过: {', '.join(failed[:8])}" + (f" 等 {len(failed)} 个" if len(failed) > 8 else "")))
            self.events.put(("done",))
            done_sent = True
            if export_kind == "authorized":
                self.events.put(("export-authorized-ready", ready, prefix))
            elif export_kind == "email_rt":
                self.events.put(("export-email-rt-ready", ready))
            elif export_kind == "sub2api":
                self.events.put(("export-sub2api-ready", ready))
        finally:
            if not done_sent:
                self.events.put(("done",))

    def export_sub2api(self) -> None:
        accounts = self._selected_accounts_for_export()
        if not accounts:
            return
        if self._ensure_export_accounts_have_rt(accounts, "sub2api"):
            return
        self._start_sub2api_export_with_accounts(accounts)

    def _start_sub2api_export_with_accounts(self, accounts: list[MailAccount]) -> None:
        accounts = [account for account in accounts if account.openai_rt]
        if not accounts:
            messagebox.showwarning(APP_TITLE, "没有可导出的已授权 RT")
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

    def open_link_with_extraction_proxy(self) -> None:
        link = self.link_var.get().strip()
        if not link:
            messagebox.showwarning(APP_TITLE, "暂无长链接")
            return
        selected = self.account_list.selection()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请先选中邮箱")
            return
        email_addr = ""
        link_proxy = ""
        try:
            index = int(selected[0])
            if 0 <= index < len(self.accounts):
                email_addr = self.accounts[index].email
                payload = self.session_results.get(email_addr, {})
                link_proxy = str(payload.get("link_proxy") or "").strip()
        except Exception:
            email_addr = ""
            link_proxy = ""
        if not link_proxy:
            messagebox.showwarning(APP_TITLE, "当前选中邮箱暂无长链提取代理")
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
        self.log(f"[{email_addr}] 使用长链提取代理打开支付窗口: {link_proxy}")
        self.open_payment_window_count += 1
        self.opening_payment_link = True
        threading.Thread(target=self._open_payment_link_worker, args=(link, local_proxy, link_proxy, extension_dir, paypal_phone, paypal_card, paypal_sms_url, email_addr), daemon=True).start()

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
        self.stop_event.clear()
        for email_addr, link in links:
            paypal_config = self._take_paypal_phone_config()
            if paypal_config is None:
                break
            paypal_phone, paypal_sms_url = paypal_config
            paypal_card = self._next_paypal_card_text()
            if paypal_card is None:
                break
            dynamic_proxy = self._take_payment_dynamic_proxy()
            self.open_payment_window_count += 1
            self.opening_payment_link = True
            threading.Thread(target=self._open_payment_link_worker, args=(link, local_proxy, dynamic_proxy, extension_dir, paypal_phone, paypal_card, paypal_sms_url, email_addr), daemon=True).start()
            self.log(f"[{email_addr}] 已启动独立支付窗口")
            started += 1
        if started:
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
