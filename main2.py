# main2.py
import json
import os
from flask import Flask, render_template, request, session, redirect, url_for
from aiml import Kernel
from glob import glob
import aiml
import nltk
from neo4j_sensory_mem import updateSensoryMemory, store_relation, query_relation, updateUserGender, get_stored_gender
from pam import process_pam


# Download necessary NLTK resources safely
try:
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng')
except:
    pass

# Initialize AIML bot
bot = aiml.Kernel()

app = Flask(__name__)
app.secret_key = 'secret_key'
USER_DB = 'users.json'

def load_users():
    if not os.path.exists(USER_DB):
        return {}
    with open(USER_DB, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USER_DB, 'w') as f:
        json.dump(users, f, indent=4)

# Load AIML files
aiml_files = glob("aiml_files/*.aiml")
for file in aiml_files:
    bot.learn(file)

user_state = {"gender_asked": False} 

def extract_keywords(sentence):
    tokens = [w.lower() for w in nltk.word_tokenize(sentence)]

    gender_map = {"male":"male", "men":"male", "man":"male", "boy":"male", "guy":"male",
                  "female":"female", "women":"female", "woman":"female", "girl":"female", "lady":"female"}
    occasions = {"eid", "party", "birthday", "interview", "work", "office", "job", "wedding", "diwali"}
    weather = {"rainy", "sunny", "cold", "hot", "windy", "foggy", "snowy"}
    seasons = {"summer", "winter", "spring", "autumn"}
    # ADD THIS LIST BACK
    basic = {"formal", "casual", "jogging", "gym", "today", "breakfast", "lunch", "dinner"}
    outfit_triggers = {"outfit", "clothes", "style", "dress", "wear", "clothing", "suit", "look"}
    
    return {
        "outfit": any(w in outfit_triggers for w in tokens),
        "gender": next((gender_map[w] for w in tokens if w in gender_map), None),
        "occasion": next((w for w in tokens if w in occasions), None),
        "weather": next((w for w in tokens if w in weather), None),
        "season": next((w for w in tokens if w in seasons), None),
        "basic": next((w for w in tokens if w in basic), None) # ADD THIS KEY
    }

@app.route("/")
def home():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template("home.html", name=session['user_name'])

@app.route("/get")
def get_bot_response():
    # 1️⃣ Get the current user's name from the session. This is the main fix.
    username = session.get('user_name')
    if not username:
        # If for some reason the user is not logged in, stop.
        return "Error: You are not logged in."

    # 1️⃣ Get user input
    query = request.args.get('msg', '').strip()
    if not query:
        return ":)"
    
    # 1. Look for the current user's gender
    user_gender = session.get('user_gender') or get_stored_gender(username)
    
    if user_gender:
        session['user_gender'] = user_gender
        # 🔥 SYNC: Tell AIML specifically for THIS user
        bot.setPredicate("gender", user_gender, sessionID=username)
    else:
        # 🔥 SYNC: Clear AIML memory specifically for THIS user
        bot.setPredicate("gender", "unknown", sessionID=username)


    updateSensoryMemory(username, query)
    

    # 2. 🔥 NEW: Process PAM (Backend Dictionary/Definitions)
    try:
        # MODIFIED: Pass the 'username' to process_pam
        process_pam(username, query)
    except Exception as e:
        print(f"PAM Error: {e}")


    keywords = extract_keywords(query)

    # --- 2. GENDER INPUT RECOGNITION ---
    # If the user says "I am female" or "male"
    if keywords["gender"]:
        g = keywords["gender"]
        session['user_gender'] = g
        bot.setPredicate("gender", g, sessionID=username)
        updateUserGender(username, g) # Save to sidebar property
        
        # If they previously asked for an outfit (e.g. Eid), fulfill it NOW
        pending = session.pop('pending_outfit_request', None)
        if pending:
            prev_k = extract_keywords(pending)
            occasion = (prev_k.get("occasion") or "").upper()
            return bot.respond(occasion if occasion else pending, sessionID=username)
        
        return bot.respond(query, sessionID=username)

    # 5️⃣ OUTFIT LOGIC
    if keywords["outfit"]:
        # If no gender in Session/Neo4j for THIS user
        if not session.get('user_gender'):
            session['pending_outfit_request'] = query
            return "I'd love to help with your style! But first, are you looking for male or female outfits?"
        else:
            # Re-sync before responding
            bot.setPredicate("gender", session['user_gender'], sessionID=username)
            occ = (keywords.get("occasion") or "").upper()
            if occ:
                # This will now correctly pick from the Male/Female list in AIML
                return bot.respond(occ, sessionID=username)
            return bot.respond(query, sessionID=username)

    # 6️⃣ Build AIML query from extracted keywords (for Direct Outfit Questions)
    # If the user says "Show me male outfits for a party" in one go
    if keywords["outfit"] and session.get("user_gender"):
        aiml_query = ""
        if keywords["occasion"]: aiml_query += keywords["occasion"].upper() + " "
        if keywords["weather"]: aiml_query += keywords["weather"].upper() + " "
        if keywords["season"]: aiml_query += keywords["season"].upper() + " "
        if keywords["basic"]: aiml_query += keywords["basic"].upper() + " "
        
        # Add the gender from session
        aiml_query += session.get("user_gender").upper()
        
        # This will send a query like "RAINY EID MALE" to AIML
        response = bot.respond(aiml_query.strip())
        if response and response != ":)":
            return response

    # 7️⃣ Default AIML response
    response = bot.respond(query, sessionID=username) or ":)"

    # ---------------------------
    # 8️⃣ STORE LEARNED RELATIONSHIPS
    # ---------------------------
    p1 = bot.getPredicate("learn_p1", sessionID=username)
    rel = bot.getPredicate("learn_rel", sessionID=username)
    p2 = bot.getPredicate("learn_p2", sessionID=username)

    print(f"DEBUG AIML Predicates: p1='{p1}', rel='{rel}', p2='{p2}'")

    if p1 and rel and p2:
        store_relation(username, p1, rel, p2)

        # clear predicates so it doesn't repeat
        bot.setPredicate("learn_p1", "", sessionID=username)
        bot.setPredicate("learn_rel", "", sessionID=username)
        bot.setPredicate("learn_p2", "", sessionID=username)

    # 9️⃣ HANDLE RELATIONSHIP QUERIES (WHO IS ...) FROM AIML
    # ---------------------------
    q_rel = bot.getPredicate("query_rel", sessionID=username)      # e.g., "father"
    q_person = bot.getPredicate("query_person", sessionID=username)  # e.g., "my" or "Raza"

    if q_rel and q_person:
        answer = query_relation(username, q_person, q_rel)
        
        # Clear predicates so they don't trigger on the next message
        bot.setPredicate("query_rel", "", sessionID=username)
        bot.setPredicate("query_person", "", sessionID=username)

        if answer:
            # Check if the user was asking about themselves ("my")
            if q_person.lower() == "my":
                return f"{answer} is your {q_rel}."
            else:
                return f"{answer} is the {q_rel} of {q_person}."
        else:
            # If no answer found, provide a clean "I don't know" message
            person_label = "you" if q_person.lower() == "my" else q_person
            return f"I don't have information about who the {q_rel} of {person_label} is."

    # ---------------------------
    # 10️⃣ Return final response
    # ---------------------------
    return response



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        
        users = load_users()
        
        if email in users:
            return redirect(url_for('signup', error='email_exists'))
        
        users[email] = {"name": name, "password": password}
        save_users(users)
        
        return redirect(url_for('signup', success='signup'))
        
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        users = load_users()
        
        if email in users and users[email]["password"] == password:
            session['user_name'] = users[email]["name"]
            return redirect(url_for('home'))
        else:
            return redirect(url_for('login', error='invalid'))
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user_name', None)
    session.pop('user_gender', None)
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)