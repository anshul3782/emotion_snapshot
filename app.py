import requests
import openai
import base64
from PIL import Image
from io import BytesIO
import pymysql
import json
from datetime import datetime
from flask_cors import CORS
from flask import Flask, request, jsonify
import os
# Initialize Flask App
app = Flask(__name__)

# ✅ Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Set up OpenAI client
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
GROQ_API_KEY = "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"
GROQ_MODEL = "llama3-70b-8192"
DB_CONFIG = {
    'host': 'db-mysql-nyc3-54076-do-user-19716193-0.k.db.ondigitalocean.com',
    'user': 'doadmin',
    'password': 'AVNS_oAN9S2VKGNizJx9BtBA',
    'database': 'overall',
    'port': 25060,
    'ssl': {'ssl': {}},
    'cursorclass': pymysql.cursors.DictCursor
}
EMOJI_MAP = {
    1: "angry", 2: "anguished", 3: "anxios-with-sweat", 4: "astonished", 5: "bandage-face",
    6: "big-frown", 7: "blush", 8: "cold-face", 9: "concerned", 10: "cry",
    11: "cursing", 12: "Diagonal-mouth", 13: "distraught", 14: "dizzy-face", 15: "drool",
    16: "exhale", 17: "expressionless", 18: "flushed", 19: "frown", 20: "gasp",
    21: "grimacing", 22: "grin-sweat", 23: "grin", 24: "grinning", 25: "hand-over-mouth",
    26: "happy-cry", 27: "head-nod", 28: "head-shake", 29: "heart-eyes", 30: "heart-face",
    31: "holding-back-tears", 32: "hot-face", 33: "hug-face", 34: "joy", 35: "kissing-closed-eyes",
    36: "kissing-heart", 37: "kissing-smile", 38: "kissing", 39: "laughing", 40: "loudly-crying",
    41: "melting", 42: "mind-blown", 43: "monocle", 44: "mouth-none", 45: "mouth-open",
    46: "neutral-face", 47: "partying-face", 48: "peeking", 49: "pensive", 50: "pleading",
    51: "rage", 52: "raised-eyebrow", 53: "relieved", 54: "rofl", 55: "rolling-eyes",
    56: "sad", 57: "scared", 58: "screaming", 59: "scrunched-eyes", 60: "scrunched-mouth",
    61: "shaking-face", 62: "shushing-face", 63: "sick", 64: "similing-eyes-with-hand-over-mouth", 65: "sleep",
    66: "sleepy", 67: "slightly-frowning", 68: "slightly-happy", 69: "smile-with-big-eyes", 70: "smile",
    71: "smirk", 72: "sneeze", 73: "squinting-tongue", 74: "star-struck", 75: "stick-out-tounge",
    76: "surprised", 77: "sweat", 78: "thermometer-face", 79: "thinking-face", 80: "tired",
    81: "triumph", 82: "unamused", 83: "upside-down-face", 84: "vomit", 85: "warm-smile",
    86: "weary", 87: "wink", 88: "winky-tongue", 89: "woozy", 90: "worried",
    91: "x-eyes", 92: "yawn", 93: "yum", 94: "zany-face", 95: "zipper-face"
}


def fetch_concatenated_health_data(username):
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT health_data, created_at FROM apple_health WHERE username = %s ORDER BY created_at DESC LIMIT 2",
                (username,)
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                created = row.get("created_at", "")
                try:
                    health_data = json.loads(row["health_data"])
                    flattened = " | ".join(f"{k}: {v}" for k, v in health_data.items())
                    result.append(f"{created} → {flattened}")
                except json.JSONDecodeError:
                    result.append(f"{created} → ❌ Invalid JSON")
            return "\n".join(result)
    finally:
        connection.close()

def build_health_prompt(log):
    return f"""
You are a health data extractor. 
ONLY extract factual, measurable data related to stress, fatigue, or anxiety. 
DO NOT infer, explain, or mention emotions.

Format the output as a clean, indented list:
  key: value

Health Log:
{log}

Extracted Data:
"""


def get_user_behavior(email):
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT activity FROM email_activity
                WHERE email = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (email,))
            row = cursor.fetchone()
            if not row:
                return f"No activity found for '{email}'."

            activity_json = json.loads(row['activity'])
            actions = activity_json.get("details", {}).get("activities", [])
            actions.sort(key=lambda x: x["timestamp"])

            timeline = []
            tab_times = {}
            button_clicks = []
            current_tab = None
            current_tab_start = None

            for act in actions:
                action = act["action"]
                ts = datetime.fromisoformat(act["timestamp"].replace("Z", "+00:00"))
                details = act.get("details", {})

                if action == "session_start":
                    device = details.get("device_info", {}).get("device_name", "unknown")
                    os = details.get("device_info", {}).get("system_version", "")
                    timeline.append(f"SESSION START — {ts} — Device: {device} (iOS {os})")
                elif action == "tab_enter":
                    tab = details.get("tab_name", "Unknown")
                    timeline.append(f"TAB_ENTER — {ts} — {tab}")
                    if current_tab and current_tab_start:
                        duration = (ts - current_tab_start).total_seconds()
                        tab_times[current_tab] = tab_times.get(current_tab, 0) + duration
                    current_tab = tab
                    current_tab_start = ts
                elif action == "button_click":
                    button_clicks.append(f"{ts} — {details.get('button_name', '')}")
                elif action.startswith("app_") or action.startswith("notification") or action.startswith("user_"):
                    timeline.append(f"{action.upper()} — {ts}")

            if current_tab and current_tab_start:
                last_time = datetime.fromisoformat(actions[-1]["timestamp"].replace("Z", "+00:00"))
                duration = (last_time - current_tab_start).total_seconds()
                tab_times[current_tab] = tab_times.get(current_tab, 0) + duration

            summary = "\n".join(timeline)
            summary += "\n\n" + "\n".join(f"- {tab}: {sec:.1f}s" for tab, sec in tab_times.items())
            summary += "\n\n" + "\n".join(button_clicks)
            return summary
    finally:
        connection.close()

def build_behavior_prompt(log):
    return f"""
You are a behavioral data extractor.
ONLY extract observable patterns, habits, and flags. Do NOT infer or mention emotions or mood.
Output as a short, indented list under each category, with no extra text.

Behavior Log:
{log}

Habits:
  - 
Flags:
  - 
Traits:
  - 
"""

# Groq API credentials
GROQ_API_KEY = "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"
GROQ_MODEL = "llama3-70b-8192"


def get_weather_emotion_report(lat, lon):
    API_KEY = "011501207ff84544b5b141025251206"
    url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={lat},{lon}"
    response = requests.get(url)
    data = response.json()

    localtime = data['location']['localtime']
    current = data['current']

    weather = {
        "temp_c": current["temp_c"],
        "feelslike_c": current["feelslike_c"],
        "heatindex_c": current.get("heatindex_c", current["feelslike_c"]),
        "windchill_c": current.get("windchill_c", current["feelslike_c"]),
        "condition": current["condition"]["text"],
        "cloud": current["cloud"],
        "vis_km": current["vis_km"],
        "humidity": current["humidity"],
        "dewpoint_c": current["dewpoint_c"],
        "precip_mm": current["precip_mm"],
        "wind_kph": current["wind_kph"],
        "gust_kph": current["gust_kph"],
        "wind_dir": current["wind_dir"],
        "uv": current["uv"],
        "pressure_mb": current["pressure_mb"]
    }

    result = f"🕒 Local Time: {localtime}\n"

    result += "\n🌡️ Temperature-Related\n"
    result += f"  - temp_c / feelslike_c: {weather['temp_c']}°C / {weather['feelslike_c']}°C → {'Irritability' if weather['temp_c'] > 30 else 'Comfort'}\n"
    result += f"  - heatindex_c: {weather['heatindex_c']}°C → {'Stressful' if weather['heatindex_c'] - weather['temp_c'] > 3 else 'Normal'}\n"
    result += f"  - windchill_c: {weather['windchill_c']}°C → {'Discomfort' if weather['windchill_c'] < 10 else 'No effect'}\n"

    result += "\n🌤️ Sky & Visibility\n"
    result += f"  - condition: {weather['condition']} → {'Neutral' if 'cloud' in weather['condition'].lower() else 'Energizing' if 'sun' in weather['condition'].lower() else 'Gloomy'}\n"
    result += f"  - cloud: {weather['cloud']}% → {'Dullness' if weather['cloud'] > 70 else 'Clear'}\n"
    result += f"  - vis_km: {weather['vis_km']} km → {'Clarity' if weather['vis_km'] > 10 else 'Anxiety'}\n"

    result += "\n💧 Moisture & Air\n"
    result += f"  - humidity: {weather['humidity']}% → {'Irritability' if weather['humidity'] > 70 else 'Dry discomfort' if weather['humidity'] < 30 else 'Neutral'}\n"
    result += f"  - dewpoint_c: {weather['dewpoint_c']}°C → {'Muggy' if weather['dewpoint_c'] > 20 else 'Comfortable'}\n"
    result += f"  - precip_mm: {weather['precip_mm']} mm → {'Gloomy' if weather['precip_mm'] > 0 else 'Uplifting'}\n"

    result += "\n💨 Wind & Gusts\n"
    result += f"  - wind_kph: {weather['wind_kph']} kph → {'Refreshing' if weather['wind_kph'] < 15 else 'Agitating'}\n"
    result += f"  - gust_kph: {weather['gust_kph']} kph → {'Unease' if weather['gust_kph'] > 20 else 'Stable'}\n"
    result += f"  - wind_dir: {weather['wind_dir']} → Minimal effect\n"

    result += "\n🌞 UV & Pressure\n"
    result += f"  - uv: {weather['uv']} → {'Overexposure' if weather['uv'] > 6 else 'Mild stimulation'}\n"
    result += f"  - pressure_mb: {weather['pressure_mb']} mb → {'Alert and stable' if weather['pressure_mb'] > 1010 else 'Sleepy'}\n"

    return result


def analyze_satellite_image(lat, lon):
    try:
        map_url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom=17&size=800x800&maptype=satellite&key=AIzaSyCI0GwnC4CerLGK0c7ZestrOO4MyAdQ8oE"
        response = requests.get(map_url)
        image = Image.open(BytesIO(response.content)).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        image_bytes = buffer.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        ai_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Describe this satellite image for the location {lat}, {lon}. Include terrain, man-made structures, vegetation, and visible patterns."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                    ]
                }
            ],
            max_tokens=500
        )

        return ai_response.choices[0].message.content

    except Exception as e:
        return f"❌ Error analyzing satellite image: {e}"


def call_groq_chat(api_key, model, prompt):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
    )
    try:
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error: {e}\n{response.text}"



def summarize_health_by_username(username):
    raw_log = fetch_concatenated_health_data(username)
    if not raw_log:
        return "❌ No health data found for user."
    prompt = build_health_prompt(raw_log)
    return call_groq_chat(GROQ_API_KEY, GROQ_MODEL, prompt)


def summarize_behavior_data(email):
    behavior_log = get_user_behavior(email)


    prompt = build_behavior_prompt(behavior_log)


    summary = call_groq_chat(GROQ_API_KEY, GROQ_MODEL, prompt)

    return summary

# ✅ High-level function that runs everything
from flask import Flask, request, jsonify
import pymysql

app = Flask(__name__)

import re

@app.route('/analyze_user', methods=['POST'])
def analyze_user():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Missing 'username' in request body"}), 400

    # Step 1: Fetch latest location
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT latitude, longitude
                FROM user_location
                WHERE username = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (username,))
            location = cursor.fetchone()
            if not location:
                return jsonify({"error": f"No location found for user '{username}'"}), 404
            lat = location['latitude']
            lon = location['longitude']
    finally:
        connection.close()

    # Step 2: Try getting all 4 components
    weather = get_weather_emotion_report(lat, lon)
    satellite = analyze_satellite_image(lat, lon)
    behavioral_analysis = summarize_behavior_data(username)
    health_summary = summarize_health_by_username(username)

    # Step 3: Check if all are missing
    if not any([weather, satellite, behavioral_analysis, health_summary]):
        return jsonify({"error": "No usable data found to analyze emotion."}), 400

    # Step 4: Build dynamic prompt
    final_prompt = f"""You are analyzing the likely emotion of user '{username}' using structured signals.\n"""

    if behavioral_analysis:
        final_prompt += f"\n## 🧠 PRIORITY 1: Behavioral Patterns (most weight)\n{behavioral_analysis}"
    if health_summary:
        final_prompt += f"\n\n## 💓 PRIORITY 2: Apple Health Signals (moderate weight)\n{health_summary}"
    if satellite:
        final_prompt += f"\n\n## 🛰️ PRIORITY 3: Satellite Terrain (low weight)\n{satellite}"
    if weather:
        final_prompt += f"\n\n## 🌦️ PRIORITY 4: Weather Conditions (lowest weight)\n{weather}"

    final_prompt += f"""

---

Your task:
Choose one emotion from this dictionary:
{EMOJI_MAP}

Instructions:
- Prioritize top sections more heavily.
- Do NOT invent or assume anything.
- Avoid 'neutral-face'.
- Keep reasons short (max 6–7 words).

Output format:
Emotion ID: <integer>
Label: <label from dictionary>
Reasons:
- <reason 1>
- <reason 2>
- <reason 3>
- <reason 4>
- <reason 5>
- <reason 6>
- <reason 7>
- <reason 8>
- <optional reason 9>
"""

    # Step 5: Parse LLM output
    result = call_groq_chat(GROQ_API_KEY, GROQ_MODEL, final_prompt)
    emotion_id = re.search(r'Emotion ID: (\d+)', result)
    label = re.search(r'Label: ([^\n]+)', result)
    reasons = re.findall(r'- (.+)', result)

    return jsonify({
        "username": username,
        "emotion_id": int(emotion_id.group(1)) if emotion_id else None,
        "label": label.group(1) if label else None,
        "reasons": reasons
    })






if __name__ == '__main__':
    app.run(debug=True, port=5000)
