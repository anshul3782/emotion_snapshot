from flask import Flask, request, jsonify
import phonenumbers
from phonenumbers import geocoder
from flask_cors import CORS
import requests
import json
import pymysql
import ssl

# Initialize Flask App
app = Flask(__name__)

# ✅ Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Groq API configuration
API_KEY = "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"
MODEL = "llama-3.1-8b-instant"

# Users that should ALWAYS use LLM prediction (ignore database)
FORCE_LLM_USERS = ["Bob"]  # Add usernames here that should skip database

# ✅ Emoji Map (same as your second app)
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

# Database connection details
db_config = {
    'host': 'db-mysql-nyc3-54076-do-user-19716193-0.k.db.ondigitalocean.com',
    'port': 25060,
    'user': 'doadmin',
    'password': 'AVNS_oAN9S2VKGNizJx9BtBA',
    'database': 'overall',
}

def get_city_from_number(phone_number):
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        full_location = geocoder.description_for_number(parsed, "en")
        return full_location.split(",")[0].strip()
    except:
        return "Unknown"

def get_db_connection():
    """Create and return database connection with SSL"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    return pymysql.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
        port=db_config['port'],
        ssl={'ssl': ssl_context}
    )

def transform_old_emotion_format(old_emotion_data):
    """
    Transform old database emotion format to new standardized format
    """
    if not old_emotion_data:
        return None
        
    # Check if it's already in new format
    if "predicted_emoji_id" in old_emotion_data:
        return old_emotion_data
        
    # Transform old format to new format
    try:
        # Extract sentiment and convert to emoji_id
        sentiment = old_emotion_data.get("what_is_their_sentiment", "neutral")
        
        # Map sentiment to emoji ID
        emoji_id = 46  # default neutral
        if sentiment == "positive":
            emoji_id = 70  # smile
        elif sentiment == "negative":
            emoji_id = 56  # sad
        elif sentiment == "excited":
            emoji_id = 34  # joy
        
        # Create behavior factors from thinking patterns
        thinking = old_emotion_data.get("what_are_people_thinking", [])
        caring = old_emotion_data.get("what_do_people_care", [])
        
        behavior_factors = f"Behavioral analysis based on social patterns:\n\n"
        behavior_factors += f"**Thinking Patterns**: {', '.join(thinking[:3]) if thinking else 'No specific patterns detected'}\n\n"
        behavior_factors += f"**Care Factors**: {', '.join(caring[:3]) if caring else 'No specific concerns identified'}\n\n"
        behavior_factors += f"**Overall Sentiment**: {sentiment.title()}"
        
        # Create health factors (simulated since old format doesn't have this)
        health_factors = f"Health indicators inferred from social sentiment analysis:\n\n"
        health_factors += f"• Social engagement level: {'High' if sentiment == 'positive' else 'Moderate'}\n"
        health_factors += f"• Stress indicators: {'Low' if sentiment == 'positive' else 'Moderate'}\n"
        health_factors += f"• Overall wellness: Based on {sentiment} social sentiment patterns"
        
        # Create emotion profile
        user_emotion_profile = f"Social sentiment analysis indicates {sentiment} emotional state:\n\n"
        if thinking:
            user_emotion_profile += f"• Primary concerns: {thinking[0] if thinking else 'None identified'}\n"
        if caring:
            user_emotion_profile += f"• Key interests: {caring[0] if caring else 'None identified'}\n"
        user_emotion_profile += f"• Overall mood appears {sentiment} based on social engagement patterns"
        
        return {
            "predicted_emoji_id": emoji_id,
            "health_factors": health_factors,
            "behavior_factors": behavior_factors,
            "user_emotion_profile": user_emotion_profile
        }
        
    except Exception as e:
        print(f"Error transforming emotion format: {e}")
        return {
            "predicted_emoji_id": 46,
            "health_factors": "Legacy data - health analysis unavailable",
            "behavior_factors": "Legacy data - behavioral analysis unavailable", 
            "user_emotion_profile": "Legacy emotion data - unable to provide detailed analysis"
        }

def check_user_emotion(username):
    """
    Check if user exists in user_emotions table by username.
    Returns latest emotion JSON in standardized format if found, None if not found.
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Get the latest emotion entry for the user
            query = """
            SELECT emotion FROM user_emotions 
            WHERE username = %s 
            ORDER BY created_at DESC 
            LIMIT 1
            """
            cursor.execute(query, (username,))
            result = cursor.fetchone()
            
            print(f"🔍 Database query for username '{username}': {result is not None}")
            
            if result:
                # Parse JSON if it's stored as string, otherwise return as-is
                emotion_data = result[0]
                if isinstance(emotion_data, str):
                    emotion_data = json.loads(emotion_data)
                
                print(f"📊 Found emotion data for '{username}' with keys: {list(emotion_data.keys()) if isinstance(emotion_data, dict) else 'Not a dict'}")
                
                # Transform to standardized format
                return transform_old_emotion_format(emotion_data)
            
            print(f"❌ No emotion data found for username '{username}'")
            return None
            
    except Exception as e:
        print(f"❌ Error checking user emotion for '{username}': {e}")
        return None
    finally:
        if connection:
            connection.close()

def fetch_latest_top_data():
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = "SELECT data FROM sentiment_main ORDER BY analyzed_at DESC LIMIT 1;"
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            else:
                return None

    except Exception as e:
        print(f"Error: {e}")
        return None

    finally:
        if connection is not None:
            connection.close()

def get_city_sentiment(city):
    """Get city sentiment data from the database"""
    full_data = fetch_latest_top_data()
    if full_data and city in full_data:
        return full_data[city]
    return {}

def save_emotion_to_database(username, emotion_data):
    """
    Save emotion data to user_emotions table
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_emotions (username, emotion)
                VALUES (%s, %s)
                """,
                (username, json.dumps(emotion_data))
            )
            connection.commit()
            print(f"✅ Saved emotion data for {username} to database")
            return True
    except Exception as e:
        print(f"❌ Error saving emotion data for {username}: {e}")
        return False
    finally:
        if connection:
            connection.close()

def call_groq_model(prompt):
    """
    Call Groq API using requests
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        else:
            print("❌ Error in Groq response:")
            print(json.dumps(result, indent=2))
            return None
    except Exception as e:
        print(f"❌ Error calling Groq API: {e}")
        return None

def build_health_factors_prompt(city, city_sentiment):
    """Enhanced prompt for generating realistic health factors"""
    return f"""
Analyze the city sentiment data for {city} and generate realistic health metrics and factors that would be typical for someone in this location.

City Data: {json.dumps(city_sentiment, indent=2)}

Based on this city sentiment data, generate a comprehensive health analysis that includes:

1. Simulated health metrics (resting heart rate, calories, exercise data) based on typical city lifestyle
2. Stress indicators from city environment and concerns
3. Energy levels based on positive/negative city sentiment
4. Overall wellness factors

Format your response as a detailed health analysis that sounds like it came from actual health monitoring data. Include specific numbers and realistic health observations. Make it sound like a comprehensive health report that considers the user's city environment and local conditions.

Focus on making this sound authentic and health-focused, similar to what a fitness tracker or health app would generate.
"""

def build_behavior_factors_prompt(username, city, city_sentiment):
    """Enhanced prompt for generating realistic behavior factors"""
    return f"""
Create a detailed behavioral analysis for user '{username}' based on their location in {city} and the local sentiment data.

City: {city}
City Sentiment Data: {json.dumps(city_sentiment, indent=2)}

Generate a comprehensive behavioral profile that includes:

1. **Behavioral Patterns**: How someone in {city} typically behaves based on local conditions
2. **Flags**: Notable behavioral indicators based on city sentiment and environment  
3. **Habits**: Daily routines and habits typical for this location
4. **Traits**: Personality traits that might be influenced by living in {city}

Make this sound like it came from actual behavior tracking data - include references to device usage, app interactions, location patterns, and daily routines. Base the behavioral analysis on what would be typical for someone living in {city} given the current city sentiment.

Format as a detailed behavioral log analysis with specific patterns, flags, and observations.
"""

def build_emotion_classification_prompt(username, city, city_sentiment, health_analysis, behavior_analysis):
    """Enhanced prompt for emotion classification"""
    emoji_reference = "\n".join([f"{k}: {v}" for k, v in EMOJI_MAP.items()])
    
    return f"""
Based on the comprehensive data below, classify the emotional state for user '{username}' living in {city}.

EMOJI OPTIONS (ID: name):
{emoji_reference}

USER DATA:
- Username: {username}
- Location: {city}
- Health Analysis: {health_analysis[:500]}...
- Behavior Analysis: {behavior_analysis[:500]}...

CITY SENTIMENT: {json.dumps(city_sentiment, indent=2)}

Choose the most appropriate emotional state and respond EXACTLY in this format:

ID: [number] ([emoji_name])

Then provide 4-5 bullet points explaining why this emotion fits:
• [detailed reasoning point 1]
• [detailed reasoning point 2] 
• [detailed reasoning point 3]
• [detailed reasoning point 4]
• [detailed reasoning point 5]

Then add 2-3 reasons why it may not fully fit:
However, it may not fully fit because:
• [limitation 1]
• [limitation 2]
• [limitation 3]

Focus on choosing expressive, meaningful emotions rather than neutral ones. Consider the user's environment, health data, and behavioral patterns.
"""

def predict_emotion_with_llm(username, city, city_sentiment, save_to_db=False):
    """
    Enhanced LLM prediction that ALWAYS generates the correct new format
    """
    try:
        print(f"🔍 Generating LLM prediction for {username} in {city}")
        
        # Generate health factors analysis
        health_prompt = build_health_factors_prompt(city, city_sentiment)
        health_result = call_groq_model(health_prompt)
        
        # Generate behavior factors analysis  
        behavior_prompt = build_behavior_factors_prompt(username, city, city_sentiment)
        behavior_result = call_groq_model(behavior_prompt)
        
        # Generate emotion classification based on all data
        emotion_prompt = build_emotion_classification_prompt(username, city, city_sentiment, 
                                                           health_result or "", behavior_result or "")
        emotion_result = call_groq_model(emotion_prompt)
        
        print(f"📝 LLM Responses received for {username}")
        print(f"Health: {bool(health_result)}")
        print(f"Behavior: {bool(behavior_result)}")  
        print(f"Emotion: {bool(emotion_result)}")
        
        # ALWAYS return the new format structure
        if not emotion_result or not health_result or not behavior_result:
            return {
                "predicted_emoji_id": 46,
                "health_factors": health_result or f"Health analysis for {city} location - limited data available",
                "behavior_factors": behavior_result or f"Behavioral analysis for user in {city} - general patterns inferred",
                "user_emotion_profile": emotion_result or "Unable to generate detailed emotion profile"
            }
        
        # Parse emoji ID from emotion result
        emoji_id = 46  # default to neutral
        user_emotion_profile = emotion_result
        
        try:
            lines = emotion_result.strip().splitlines()
            first_line = lines[0].strip()
            if "ID:" in first_line:
                # Extract number from "ID: 33 (joy)" format
                id_part = first_line.split("ID:")[1].strip()
                emoji_id = int(id_part.split()[0])
                
                # Get the rest as emotion profile
                user_emotion_profile = "\n".join(lines[1:]).strip()
        except Exception as e:
            print(f"❌ Error parsing emotion ID: {e}")
            print(f"Raw emotion result: {emotion_result[:200]}...")
        
        # FORCE the correct format - never return city sentiment format
        final_result = {
            "predicted_emoji_id": emoji_id,
            "health_factors": health_result,
            "behavior_factors": behavior_result,
            "user_emotion_profile": user_emotion_profile
        }
        
        print(f"✅ Generated LLM prediction for {username}: emoji_id={emoji_id}")
        
        # Save to database if requested
        if save_to_db:
            save_emotion_to_database(username, final_result)
        
        return final_result
            
    except Exception as e:
        print(f"❌ Error in LLM prediction for {username}: {e}")
        error_result = {
            "predicted_emoji_id": 46,
            "health_factors": f"Error analyzing health data for {city}: {str(e)}",
            "behavior_factors": f"User location: {city} - Error in behavioral analysis: {str(e)}",
            "user_emotion_profile": f"LLM prediction failed for {username}: {str(e)}"
        }
        
        # Save to database if requested, even for error cases
        if save_to_db:
            save_emotion_to_database(username, error_result)
        
        return error_result

@app.route('/get_user_emotion', methods=['POST'])
def get_user_emotion():
    """
    Check if username exists in user_emotions table.
    If yes, return existing emotion data
    If no, use LLM prediction with exact format
    """
    try:
        data = request.json
        username = data.get("username")
        phone_number = data.get("phone_number")
        
        if not username:
            return jsonify({"error": "Username is required"}), 400
        if not phone_number:
            return jsonify({"error": "Phone number is required"}), 400
        
        city = get_city_from_number(phone_number)
        
        # Check if user should be forced to use LLM
        force_llm = username in FORCE_LLM_USERS
        if force_llm:
            print(f"🔄 {username} is in FORCE_LLM_USERS - skipping database, using LLM")
            user_emotion = None  # Force LLM path
        else:
            # Check if user exists in user_emotions table
            user_emotion = check_user_emotion(username)
        
        if user_emotion:
            # User found in database - return existing data
            return jsonify({
                "username": username,
                "phonenumber": phone_number,
                "city": city,
                "emotion": user_emotion
            })
        
        # User not found OR forced LLM - use LLM prediction
        city_sentiment = get_city_sentiment(city)
        # Only save to DB if user doesn't exist (not if forced LLM)
        save_to_db = not force_llm
        predicted_emotion = predict_emotion_with_llm(username, city, city_sentiment, save_to_db=save_to_db)
        
        return jsonify({
            "username": username, 
            "phonenumber": phone_number,
            "city": city,
            "emotion": predicted_emotion
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_contacts_sentiment', methods=['POST'])
def get_contacts_sentiment():
    """
    Enhanced contacts sentiment with proper LLM fallback and debugging
    """
    try:
        contacts = request.json.get("contacts", {})
        if not isinstance(contacts, dict):
            return jsonify({"error": "Invalid input format, expected dict."}), 400

        result = {}
        for username, number in contacts.items():
            print(f"\n🔍 Processing contact: {username} with number: {number}")
            
            city = get_city_from_number(number)
            print(f"📍 Detected city: {city}")
            
            # Check if user should be forced to use LLM
            force_llm = username in FORCE_LLM_USERS
            if force_llm:
                print(f"🔄 {username} is in FORCE_LLM_USERS - skipping database, using LLM")
                user_emotion = None  # Force LLM path
            else:
                # Check if user exists in user_emotions table
                user_emotion = check_user_emotion(username)
            
            if user_emotion:
                print(f"✅ Found {username} in database with emotion format: {type(user_emotion)}")
                print(f"Keys in emotion: {list(user_emotion.keys()) if isinstance(user_emotion, dict) else 'Not a dict'}")
                
                # User found in database
                result[username] = {
                    "number": number,
                    "city": city,
                    "emotion": user_emotion
                }
            else:
                print(f"❌ {username} NOT found in database (or forced LLM), using LLM prediction")
                
                # User NOT found OR forced LLM - generate emotion using enhanced LLM
                city_sentiment = get_city_sentiment(city)
                print(f"🏙️ City sentiment data keys: {list(city_sentiment.keys()) if city_sentiment else 'No city data'}")
                
                # Only save to DB if user doesn't exist (not if forced LLM)
                save_to_db = not force_llm
                llm_emotion = predict_emotion_with_llm(username, city, city_sentiment, save_to_db=save_to_db)
                print(f"🤖 LLM generated emotion keys: {list(llm_emotion.keys()) if isinstance(llm_emotion, dict) else 'Not a dict'}")
                
                # ENSURE we never return city sentiment format
                if "what_are_people_thinking" in llm_emotion or "what_do_people_care" in llm_emotion:
                    print(f"⚠️ WARNING: LLM returned old format for {username}, forcing new format")
                    llm_emotion = {
                        "predicted_emoji_id": 46,
                        "health_factors": f"Health analysis for {city} - data processing error",
                        "behavior_factors": f"Behavioral analysis for {username} in {city}",
                        "user_emotion_profile": "Error in emotion analysis - using neutral state"
                    }
                
                result[username] = {
                    "number": number,
                    "city": city,
                    "emotion": llm_emotion
                }

        return jsonify({"contacts": result})
    except Exception as e:
        print(f"❌ Error in get_contacts_sentiment: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_contacts_emotions', methods=['POST'])
def get_contacts_emotions():
    """
    Enhanced version with proper format for all contacts
    """
    try:
        contacts = request.json.get("contacts", {})
        if not isinstance(contacts, dict):
            return jsonify({"error": "Invalid input format, expected dict."}), 400

        result = {}
        for username, phone_number in contacts.items():
            city = get_city_from_number(phone_number)
            
            # Check if user should be forced to use LLM
            force_llm = username in FORCE_LLM_USERS
            if force_llm:
                print(f"🔄 {username} is in FORCE_LLM_USERS - skipping database, using LLM")
                user_emotion = None  # Force LLM path
            else:
                # Check if user exists in user_emotions table
                user_emotion = check_user_emotion(username)
            
            if user_emotion:
                # User found in database
                result[username] = {
                    "username": username,
                    "phonenumber": phone_number,
                    "city": city,
                    "emotion": user_emotion
                }
            else:
                # User not found OR forced LLM - use enhanced LLM prediction
                city_sentiment = get_city_sentiment(city)
                # Only save to DB if user doesn't exist (not if forced LLM)
                save_to_db = not force_llm
                predicted_emotion = predict_emotion_with_llm(username, city, city_sentiment, save_to_db=save_to_db)
                
                result[username] = {
                    "username": username,
                    "phonenumber": phone_number, 
                    "city": city,
                    "emotion": predicted_emotion
                }

        return jsonify({"contacts": result})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
