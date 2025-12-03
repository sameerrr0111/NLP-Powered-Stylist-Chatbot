import json
import os
from getopt import gnu_getopt
from flask import Flask, render_template, request, session, redirect, url_for
from aiml import Kernel
from glob import glob
import aiml
import nltk
import pytholog as pl

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

RULES_PATH = "prolog/rules.pl"
USERS_DIR = "prolog/users"

if not os.path.exists(USERS_DIR):
    os.makedirs(USERS_DIR)

def get_user_kb():
    username = session.get('user_name', 'default_user').replace(" ", "_").lower()
    user_file_path = f"{USERS_DIR}/{username}.pl"

    if not os.path.exists(user_file_path):
        with open(user_file_path, "w") as f:
            f.write(f"% Facts for {username}\n")

    new_kb = pl.KnowledgeBase("family")
    
    # Load rules then user facts
    try:
        new_kb.from_file(RULES_PATH)
        new_kb.from_file(user_file_path)
    except Exception as e:
        print(f"Error loading KB: {e}")
    
    return new_kb, user_file_path

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

def check_prolog_action():
    kb, user_file_path = get_user_kb()
    prolog_response = None

    # --- 1. LEARN RELATIONSHIP ---
    relation = bot.getPredicate("learn_rel")
    person1 = bot.getPredicate("learn_p1")
    person2 = bot.getPredicate("learn_p2")
    
    if relation and person1 and person2:
        relation = relation.strip().lower()
        p1 = person1.strip().lower()
        p2 = person2.strip().lower()
        
        # --- TRANSLATION LOGIC STARTS HERE ---
        # We convert complex relations (son/daughter) into basic facts (father/male)
        # to avoid conflicting with Rules in rules.pl
        
        facts_to_save = []
        
        if relation == 'son':
            # "Ali is son of Hassan" -> father(hassan, ali), male(ali)
            facts_to_save.append(f"father({p2},{p1}).")
            facts_to_save.append(f"male({p1}).")
        elif relation == 'daughter':
            facts_to_save.append(f"father({p2},{p1}).")
            facts_to_save.append(f"female({p1}).")
        elif relation == 'father':
            facts_to_save.append(f"father({p1},{p2}).")
            facts_to_save.append(f"male({p1}).")
        elif relation == 'mother':
            facts_to_save.append(f"mother({p1},{p2}).")
            facts_to_save.append(f"female({p1}).")
        elif relation == 'brother':
            # For siblings, we assume they share a father (placeholder) or just store sibling
            # But simple storage is safest:
            facts_to_save.append(f"brother({p1},{p2}).")
            facts_to_save.append(f"male({p1}).")
        elif relation == 'sister':
            facts_to_save.append(f"sister({p1},{p2}).")
            facts_to_save.append(f"female({p1}).")
        else:
            # Fallback for others
            facts_to_save.append(f"{relation}({p1},{p2}).")

        # --- SAVE TO FILE ---
        try:
            with open(user_file_path, "a") as f:
                for fact in facts_to_save:
                    f.write("\n" + fact + "\n")
            prolog_response = f"I have learned that {person1} is the {relation} of {person2}."
        except Exception as e:
            print(f"File write error: {e}")
            prolog_response = "I couldn't save that relationship."
        
        bot.setPredicate("learn_rel", "")
        bot.setPredicate("learn_p1", "")
        bot.setPredicate("learn_p2", "")

    # --- 2. LEARN GENDER ---
    gen_person = bot.getPredicate("other_gender_person")
    gen_type = bot.getPredicate("other_gender")
    
    if gen_person and gen_type:
        gen_person = gen_person.strip().lower()
        gen_type = gen_type.strip().lower()
        
        fact = f"{gen_type}({gen_person})."
        
        try:
            with open(user_file_path, "a") as f:
                f.write("\n" + fact + "\n")
            prolog_response = f"Noted, {gen_person} is {gen_type}."
        except:
            prolog_response = "I couldn't save that gender info."
        
        bot.setPredicate("other_gender_person", "")
        bot.setPredicate("other_gender", "")

    # --- 3. QUERY RELATIONSHIP ---
    q_rel = bot.getPredicate("query_rel")
    q_person = bot.getPredicate("query_person")
    
    if q_rel and q_person:
        q_rel = q_rel.strip().lower()
        q_person = q_person.strip().lower()
        
        try:
            if q_rel in ['male', 'female']:
                query_str = f"{q_rel}({q_person})"
                result = kb.query(pl.Expr(query_str))
                if result:
                    prolog_response = f"Yes, {q_person} is {q_rel}."
                else:
                    prolog_response = f"No, {q_person} is not {q_rel}."
            else:
                # Query logic: who is the X of Y?
                query_str = f"{q_rel}(X, {q_person})"
                result = kb.query(pl.Expr(query_str))
                
                if result:
                    answers = set()
                    for res in result:
                        if isinstance(res, dict) and 'X' in res:
                            answers.add(str(res['X']).capitalize())
                    
                    if answers:
                        prolog_response = f"The {q_rel} of {q_person} is {', '.join(answers)}."
                    else:
                        prolog_response = f"I don't know who the {q_rel} of {q_person} is."
                else:
                    prolog_response = f"I don't know who the {q_rel} of {q_person} is."
        except Exception as e:
            print(f"Prolog Logic Error: {e}")
            prolog_response = "I couldn't process that relationship request."
            
        bot.setPredicate("query_rel", "")
        bot.setPredicate("query_person", "")

    return prolog_response

@app.route("/")
def home():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template("home.html", name=session['user_name'])

@app.route("/get")
def get_bot_response():
    global user_state
    query = request.args.get('msg').strip()

    # 1. Keywords / Outfit Logic
    keywords = extract_keywords(query)
    
    if keywords.get("outfit") and not user_state["gender_asked"]:
        user_state["gender_asked"] = True
        return "Before I suggest an outfit, can you tell me your gender?"

    if not user_state["gender_asked"]:
        response = bot.respond(query)
        user_state["gender_asked"] = True
        return response + " By the way, can you tell me your gender?"

    aiml_query = ""
    if keywords.get("occasion"): aiml_query += keywords["occasion"].upper() + " "
    if keywords.get("weather"): aiml_query += keywords["weather"].upper() + " "
    if keywords.get("season"): aiml_query += keywords["season"].upper() + " "
    if keywords.get("basic"): aiml_query += keywords["basic"].upper() + " "
    if keywords.get("gender"): aiml_query += keywords["gender"].upper() + " "

    if aiml_query.strip():
        response = bot.respond(aiml_query.strip())
        return str(response) if response else "I couldn't find an outfit suggestion."
        
    # 2. RUN AIML FIRST to parse the user text and set predicates
    aiml_response = bot.respond(query)
    
    # 3. RUN PROLOG SECOND to execute logic based on AIML's parsing
    prolog_response = check_prolog_action()
    
    if prolog_response:
        return prolog_response
        
    return aiml_response or ":)"

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