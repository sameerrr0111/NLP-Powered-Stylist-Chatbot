# pam.py
import nltk
from nltk.corpus import wordnet
from neo4j import GraphDatabase
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Setup Neo4j Connection (using your same credentials)
URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "12345678")
driver = GraphDatabase.driver(URI, auth=AUTH)

# Ensure WordNet and POS Tagger are downloaded
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')
nltk.download('vader_lexicon')

# Initialize the sentiment analyzer once
sia = SentimentIntensityAnalyzer()

# --- NEW, FOCUSED FUNCTION ---
def analyze_full_text_sentiment(username, text):
    """Analyzes sentiment of the full text block and updates the :Text node."""
    full_text_sentiment = sia.polarity_scores(text)
    compound_score = full_text_sentiment['compound']
    
    if compound_score >= 0.05: sentiment_label = "Positive"
    elif compound_score <= -0.05: sentiment_label = "Negative"
    else: sentiment_label = "Neutral"

    formatted_username = f"user {username}"
    with driver.session() as session:
        # This query remains the same, targeting the :Text node
        session.run("""
            MATCH (u:User {name: $username})-[:has_text]->(t:Text {content: $text})
            SET t.sentiment_score = $score, t.sentiment_label = $label
        """, username=formatted_username, text=text, score=compound_score, label=sentiment_label)


def get_word_definition(word):
    """Fetches the first definition from WordNet for a given word."""
    synsets = wordnet.synsets(word)
    if synsets:
        return synsets[0].definition()
    return None

# MODIFIED: The entire function is enhanced but the signature remains the same.
def process_pam(username, text):
    """
    Identifies POS tag for every word and links its Neo4j Word node to a 
    Definition node if it is a noun.
    """
    tokens = nltk.word_tokenize(text)
    tagged_words = nltk.pos_tag(tokens) # This gives us a list like [('word', 'TAG'), ...]
    
    formatted_username = f"user {username}"

    with driver.session() as session:
        # MODIFIED: We now loop through EVERY tagged word, not just nouns.
        for word, tag in tagged_words:
            
            # --- NEW FEATURE: Add POS Tag to every Word node ---
            # This query finds the user's specific word and sets its POS tag.
            pos_query = """
            MATCH (w:SensoryMemory:Word {content: $word, owner: $username})
            SET w.pos_tag = $tag
            """
            session.run(pos_query, word=word, tag=tag, username=formatted_username)

            # --- PRESERVED FEATURE: Add definition link for Nouns ---
            # We check if the tag from the current word is a noun.
            if tag.startswith('NN'):
                definition = get_word_definition(word)
                
                if definition:
                    # This is the original query to link a definition.
                    def_query = """
                    MATCH (w:SensoryMemory:Word {content: $noun, owner: $username})
                    MERGE (d:Definition {text: $definition})
                    MERGE (w)-[:has_definition]->(d)
                    """
                    # We use 'word' from our loop as the noun content.
                    session.run(def_query, noun=word, definition=definition, username=formatted_username)