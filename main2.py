# main2.py
import json
import os
from flask import Flask, render_template, request, session, redirect, url_for
from aiml import Kernel
from glob import glob
import aiml
import nltk
from neo4j_sensory_mem import updateSensoryMemory, store_relation, query_relation



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
    tokens = nltk.word_tokenize(sentence)
    try:
        pos_tags = nltk.pos_tag(tokens)
    except:
        pos_tags = []

    gender = {"male","female","men","women","man","woman","boy","girl","lady","guy"}
    occasions = {"eid", "party", "birthday", "interview", "work", "office", "job", "wedding", "diwali", "new year eve", "new year"}
    weather_conditions = {"rainy", "sunny", "cold", "hot", "windy", "foggy", "snowy"}
    seasons = {"summer", "winter", "spring", "autumn"}
    basic = {"formal", "casual", "jogging", "gym", "today", "breakfast", "lunch", "dinner"}
    outfit_keywords = {"outfit", "clothes", "style", "dress","wear"}
    
    keywords = {
        "outfit": False,
        "occasion": None,
        "weather": None,
        "season": None,
        "basic": None,
        "gender": None
    }

    for word, tag in pos_tags:
        word_lower = word.lower()
        if word_lower in outfit_keywords:
            keywords["outfit"] = True
        if word_lower in occasions:
            keywords["occasion"] = word_lower
        if word_lower in weather_conditions:
            keywords["weather"] = word_lower
        if word_lower in seasons:
            keywords["season"] = word_lower
        if word_lower in basic:
            keywords["basic"] = word_lower
        if word_lower in gender:
            keywords["gender"] = word_lower

    return keywords

@app.route("/")
def home():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template("home.html", name=session['user_name'])

@app.route("/get")
def get_bot_response():
    global user_state

    # 1️⃣ Get user input
    query = request.args.get('msg', '').strip()
    if not query:
        return ":)"

    # 2️⃣ Store in sensory memory (text, sentence, word)
    updateSensoryMemory(query)

    # 3️⃣ Extract keywords (for outfit flow or other AIML processing)
    keywords = extract_keywords(query)

    # 4️⃣ Outfit flow: ask gender first
    if keywords.get("outfit") and not user_state["gender_asked"]:
        user_state["gender_asked"] = True
        return "Before I suggest an outfit, can you tell me your gender?"

    # 5️⃣ If gender not yet asked, normal AIML response + ask gender
    if not user_state["gender_asked"]:
        response = bot.respond(query)
        user_state["gender_asked"] = True
        return (response or "") + " By the way, can you tell me your gender?"

    # 6️⃣ Build AIML query from extracted keywords (optional, outfit suggestions)
    aiml_query = ""
    if keywords.get("occasion"): aiml_query += keywords["occasion"].upper() + " "
    if keywords.get("weather"): aiml_query += keywords["weather"].upper() + " "
    if keywords.get("season"): aiml_query += keywords["season"].upper() + " "
    if keywords.get("basic"): aiml_query += keywords["basic"].upper() + " "
    if keywords.get("gender"): aiml_query += keywords["gender"].upper() + " "

    if aiml_query.strip():
        return bot.respond(aiml_query.strip()) or "I couldn't find an outfit suggestion."

    # 7️⃣ Default AIML response
    response = bot.respond(query) or ":)"

    # ---------------------------
    # 8️⃣ STORE LEARNED RELATIONSHIPS
    # ---------------------------
    p1 = bot.getPredicate("learn_p1")
    rel = bot.getPredicate("learn_rel")
    p2 = bot.getPredicate("learn_p2")

    if p1 and rel and p2:
        store_relation(p1, rel, p2)

        # clear predicates so it doesn't repeat
        bot.setPredicate("learn_p1", "")
        bot.setPredicate("learn_rel", "")
        bot.setPredicate("learn_p2", "")

    # ---------------------------
    # 9️⃣ HANDLE RELATIONSHIP QUERIES (WHO IS ...) FROM AIML
    # ---------------------------
    q_rel = bot.getPredicate("query_rel")      # e.g., "father"
    q_person = bot.getPredicate("query_person")  # e.g., "Hassan"

    if q_rel and q_person:
        answer = query_relation(q_person, q_rel)
        if answer:
            # Reset predicates after query
            bot.setPredicate("query_rel", "")
            bot.setPredicate("query_person", "")
            return f"{answer} is the {q_rel} of {q_person}."
        else:
            bot.setPredicate("query_rel", "")
            bot.setPredicate("query_person", "")
            return f"I don't have information about the {q_rel} of {q_person}."

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
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)