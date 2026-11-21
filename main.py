
import os
import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl

import asyncpg
from flask import Flask, request, render_template

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YAR CHAT</title>
</head>
<body>
<h2>YAR CHAT</h2>
<p id="status">در حال بررسی حساب شما...</p>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

fetch("/api/check", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({initData: tg.initData})
})
.then(r => r.json())
.then(data => {
  document.getElementById("status").innerText =
    data.message;
});
</script>
</body>
</html>
"""

def verify_telegram(init_data):
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash")

        auth_date = int(pairs["auth_date"])
        if abs(time.time() - auth_date) > 300:
            return None

        data_check = "\n".join(
            f"{k}={v}" for k, v in sorted(pairs.items())
        )

        secret = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated = hmac.new(
            secret,
            data_check.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated, received_hash):
            return None

        return json.loads(pairs["user"])

    except (ValueError, KeyError, TypeError):
        return None

@@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/check")
def check_user():
    data = request.get_json(silent=True) or {}

    print("INIT_DATA_LENGTH:", len(data.get("initData", "")))

    telegram_user = verify_telegram(data.get("initData", ""))

    if not telegram_user:
        return {"ok": False, "message": "ورود معتبر نیست."}, 401

    user_id = telegram_user.get("id")
    async def find_user():
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            return await conn.fetchrow("""
                SELECT gender, voice_status,
                       registration_completed, is_blocked
                FROM users
                WHERE user_id = $1
            """, user_id)
        finally:
            await conn.close()

    import asyncio
    user = asyncio.run(find_user())

    if not user:
        return {"ok": False, "message": "حساب شما پیدا نشد."}, 403

    if user["is_blocked"]:
        return {"ok": False, "message": "حساب شما مسدود است."}, 403

    if not user["registration_completed"]:
        return {"ok": False, "message": "ثبت‌نام شما کامل نیست."}, 403

    if user["gender"] != "female":
        return {"ok": False, "message": "ورود فقط برای کاربران خانم مجاز است."}, 403

    if user["voice_status"] != "approved":
        return {"ok": False, "message": "تأیید صدای شما کامل نیست."}, 403

    return {
        "ok": True,
        "message": "ورود موفق بود. خوش آمدید به YAR CHAT."
    }

if __name__ == "__main__":
    app.run()
    
