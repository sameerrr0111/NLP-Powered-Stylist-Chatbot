# pam.py
import nltk
from nltk.corpus import wordnet
from neo4j import GraphDatabase

# Setup Neo4j Connection (using your same credentials)
URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "12345678")
driver = GraphDatabase.driver(URI, auth=AUTH)

# Ensure WordNet and POS Tagger are downloaded
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')

def get_word_definition(word):
    """Fetches the first definition from WordNet for a given word."""
    synsets = wordnet.synsets(word)
    if synsets:
        return synsets[0].definition()
    return None

# MODIFIED: Function now requires 'username' to know which node to link
def process_pam(username, text):
    """
    Identifies nouns in the text and links their Neo4j Word nodes 
    to a Definition node.
    """
    tokens = nltk.word_tokenize(text)
    tagged_words = nltk.pos_tag(tokens)
    nouns = [word for word, tag in tagged_words if tag.startswith('NN')]
    
    formatted_username = f"user {username}"

    with driver.session() as session:
        for noun in nouns:
            definition = get_word_definition(noun)
            
            if definition:
                # MODIFIED: The MATCH clause now finds the user's specific Word node
                query = """
                MATCH (w:SensoryMemory:Word {content: $noun, owner: $username})
                MERGE (d:Definition {text: $definition})
                MERGE (w)-[:has_definition]->(d)
                """
                session.run(query, noun=noun, definition=definition, username=formatted_username)