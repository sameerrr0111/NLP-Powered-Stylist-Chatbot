from getopt import gnu_getopt

from flask import Flask, render_template, request
from aiml import Kernel
from glob import glob
import aiml
import nltk

# Download necessary NLTK resources
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('averaged_perceptron_tagger')
nltk.download('averaged_perceptron_tagger_eng')

# Initialize AIML bot and Flask app
bot = aiml.Kernel()
app = Flask(__name__)


# Load AIML files
aiml_files = glob("aiml_files/*.aiml")
for file in aiml_files:
    bot.learn(file)

# User state storage
user_state = {"gender_asked": False}  # Tracks if the gender question has been asked


# Function to extract key information using POS tagging
def extract_keywords(sentence):
    tokens = nltk.word_tokenize(sentence)
    pos_tags = nltk.pos_tag(tokens)

    # Define keyword categories
    gender = {"male","female","men","women","man","woman","boy","girl","lady","guy"}
    occasions = {"eid", "party", "birthday", "interview", "work", "office", "job", "wedding", "diwali", "new year eve", "new year"}
    weather_conditions = {"rainy", "sunny", "cold", "hot", "windy", "foggy", "snowy"}
    seasons = {"summer", "winter", "spring", "autumn"}
    basic = {"formal", "casual", "jogging", "gym", "today", "breakfast", "lunch", "dinner"}
    outfit_keywords = {"outfit", "clothes", "style", "dress","wear"}
    keywords = {"outfit": False}
    keywords = {
        "outfit": False,  # Checks if the query is outfit-related
        "occasion": None,
        "weather": None,
        "season": None,
        "basic": None,
        "gender": None
    }

    # Identify keywords in the sentence
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
    return render_template("home.html")

@app.route("/get")
def get_bot_response():
    global user_state
    query = request.args.get('msg').strip()

    # Extract keywords using POS tagging
    keywords = extract_keywords(query)
    is_outfit_related = keywords.get("outfit")
    occasion = keywords.get("occasion")
    weather = keywords.get("weather")
    season = keywords.get("season")
    basic = keywords.get("basic")
    gender = keywords.get("gender")

    # If outfit-related and gender has not been asked
    if is_outfit_related and not user_state["gender_asked"]:
        user_state["gender_asked"] = True
        return "Before I suggest an outfit, can you tell me your gender?"

    # If not outfit-related and gender has not been asked
    if not user_state["gender_asked"]:
        response = bot.respond(query)
        user_state["gender_asked"] = True
        return response + " By the way, can you tell me your gender?"

    # Normalize keywords for AIML patterns
    aiml_query = ""
    if occasion:
        aiml_query += occasion.upper() + " "
    if weather:
        aiml_query += weather.upper() + " "
    if season:
        aiml_query += season.upper() + " "
    if basic:
        aiml_query += basic.upper() + " "
    if gender:
        aiml_query += gender.upper() + " "

    # Get AIML response if keywords are present
    if aiml_query.strip():
        response = bot.respond(aiml_query.strip())
        return str(response) if response else "I couldn't find an outfit suggestion for that."

    # Fallback to general AIML response
    response = bot.respond(query)
    return str(response) if response else ":)"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
