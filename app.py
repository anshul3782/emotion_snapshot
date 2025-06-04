import pymysql
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# ✅ DB Config
DB_CONFIG = {
    'host': 'db-mysql-nyc3-54076-do-user-19716193-0.k.db.ondigitalocean.com',
    'user': 'doadmin',
    'password': 'AVNS_oAN9S2VKGNizJx9BtBA',
    'database': 'overall',
    'port': 25060,
    'ssl': {'ssl': {}},
    'cursorclass': pymysql.cursors.DictCursor
}

# ✅ Groq API Config
GROQ_API_KEY = "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"
GROQ_MODEL = "llama-3.1-8b-instant"

# ✅ Emoji Map
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

# ✅ Flask App Setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ✅ Fetch and format Apple Health data
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

# ✅ Fetch and format app usage data
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

# ✅ Prompt Builders
def build_health_prompt(log):
    return f"""
You're a health signal extractor. Do NOT analyze or predict emotions.
Extract data relevant to emotional states like stress, fatigue, or anxiety — WITHOUT inferring emotions.

Health Log:
{log}

- Emotion-Relevant Data Points:
  • <key>: <value>
"""

def build_behavior_prompt(log):
    return f"""
You're an expert in behavioral analysis.
Summarize behavioral patterns, flags, and habits — DO NOT infer mood/emotion.

Behavior Log:
{log}

- 🔄 Habits:
- ⚠️ Flags:
- 🧠 Traits:
"""

def build_classification_prompt(health_log, behavior_log):
    emoji_reference = "\n".join([f"{k}: {v}" for k, v in EMOJI_MAP.items()])
    return f"""
Choose the user's emotional state from the following list (ID: emoji):
{emoji_reference}

Avoid using generic or low-engagement emojis like 'neutral-face'. Choose expressive and emotionally meaningful states.

Respond with the ID and emoji name only on the first line, like:
ID: 33 (joy)

Then add:
- 4–5 bullet points supporting the classification.
- 2–3 reasons why it may not fully fit.

Health Log:
{health_log}

Behavior Log:
{behavior_log}
"""

# ✅ Groq call
def analyze_prompt(prompt):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
    )
    try:
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error: {e}\n{response.text}"

# ✅ Flask API Endpoint
@app.route('/analyze_user', methods=['POST'])
def analyze_user():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Username is required"}), 400

    health_log = fetch_concatenated_health_data(username)
    behavior_log = get_user_behavior(username)

    health_result = analyze_prompt(build_health_prompt(health_log))
    behavior_result = analyze_prompt(build_behavior_prompt(behavior_log))
    classification_result = analyze_prompt(build_classification_prompt(health_log, behavior_log))

    lines = classification_result.strip().splitlines()
    first_line = lines[0]
    emoji_id = None
    if "ID:" in first_line:
        try:
            emoji_id = int(first_line.split("ID:")[1].split()[0])
        except:
            emoji_id = None

    user_emotion_profile = "\n".join(lines[1:]).strip()

    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_emotions (username, emotion)
                VALUES (%s, %s)
                """,
                (username, json.dumps({
                    "predicted_emoji_id": emoji_id,
                    "health_factors": health_result,
                    "behavior_factors": behavior_result,
                    "user_emotion_profile": user_emotion_profile
                }))
            )
            connection.commit()
    except Exception as e:
        return jsonify({"error": f"DB insert failed: {e}"}), 500
    finally:
        connection.close()

    return jsonify({
        "predicted_emoji_id": emoji_id,
        "health_factors": health_result,
        "behavior_factors": behavior_result,
        "user_emotion_profile": user_emotion_profile
    })

# ✅ Run App
if __name__ == '__main__':
    app.run(debug=True, port=5000)
