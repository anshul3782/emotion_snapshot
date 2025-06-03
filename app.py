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
GROQ_MODEL = "llama-3.1-8b-instant"  # Reasoning-capable and cost-efficient model

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
            if not rows:
                return f"No health data found for user '{username}'."

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
    return f"""
Given the following health and behavior logs, classify the user's most likely emotional state as one of the following emojis:
1–95, mapped by emojiMap index. Respond with the emoji name and ID only in the first line, like:
ID: 33 (joy)

⚠️ Important: Avoid choosing generic or low-engagement emojis like 'neutral-face'. Choose expressive and emotionally significant states instead.

Then, provide:
- 4–5 bullet points supporting why this emoji fits.
- 2–3 bullet points explaining why it might not fully match.

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

    # Extract emoji ID from the first line like 'ID: 33 (joy)'
    lines = classification_result.strip().splitlines()
    first_line = lines[0]
    emoji_id = None
    if "ID:" in first_line:
        try:
            emoji_id = int(first_line.split("ID:")[1].split()[0])
        except:
            emoji_id = None

    user_emotion_profile = "\n".join(lines[1:]).strip()

    # ✅ Save to DB
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
