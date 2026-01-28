# neo4j_sensory_mem.py
import nltk
from neo4j import GraphDatabase
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Setup NLTK
nltk.download('punkt')
nltk.download('vader_lexicon')

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "12345678") 
driver = GraphDatabase.driver(URI, auth=AUTH)


sia = SentimentIntensityAnalyzer()

# --- SENSORY MEMORY (bot_agent) ---

def createTextNode(username, Text):
    # REMOVED: No more relation_agent
    query = """
    MERGE (a:Agent {name: 'bot_agent'})
    
    // Create/Match the specific User node
    MERGE (u:User {name: $username})
    MERGE (a)-[:HAS_USER]->(u)
    
    // Create the Text node linked to the User
    CREATE (t:SensoryMemory:Text {content: $text, time: timestamp()})
    MERGE (u)-[:has_text]->(t)
    RETURN elementId(t) AS text_id
    """
    with driver.session() as session:
        formatted_username = f"user {username}"
        result = session.run(query, username=formatted_username, text=Text)
        return result.single()["text_id"]

def createSentenceNode(text_id, Text, username):
    sentences = nltk.sent_tokenize(Text)
    prev_s = None
    formatted_username = f"user {username}"
    with driver.session() as session:
        for s_content in sentences:
            # --- NEW: Perform sentiment analysis here ---
            sentiment_scores = sia.polarity_scores(s_content)
            compound_score = sentiment_scores['compound']
            if compound_score >= 0.05:
                sentiment_label = "Positive"
            elif compound_score <= -0.05:
                sentiment_label = "Negative"
            else:
                sentiment_label = "Neutral"

            # MODIFIED: MERGE query now creates the node with sentiment properties
            session.run("""
                MATCH (t) WHERE elementId(t) = $t_id
                // MERGE now includes owner and sentiment properties from the start
                MERGE (s:SensoryMemory:Sentence {
                    content: $s_content, 
                    owner: $username, 
                    sentiment_score: $score, 
                    sentiment_label: $label
                })
                MERGE (t)-[:has_sentence]->(s)
            """, t_id=text_id, s_content=s_content, username=formatted_username, 
                 score=compound_score, label=sentiment_label)

            if prev_s:
                session.run("""
                    MATCH (s1:SensoryMemory:Sentence {content: $p, owner: $username}), 
                          (s2:SensoryMemory:Sentence {content: $c, owner: $username})
                    MERGE (s1)-[:next_sentence]->(s2)
                """, p=prev_s, c=s_content, username=formatted_username)
            prev_s = s_content

def createWordNode(Text, username): # ADDED username parameter
    sentences = nltk.sent_tokenize(Text)
    formatted_username = f"user {username}" # Use formatted username
    with driver.session() as session:
        for s_content in sentences:
            words = nltk.word_tokenize(s_content)
            prev_w = None
            for w_content in words:
                # MODIFIED: MATCH and MERGE now include the owner
                session.run("""
                    MATCH (s:SensoryMemory:Sentence {content: $s_content, owner: $username})
                    // MERGE now includes the owner for isolation
                    MERGE (w:SensoryMemory:Word {content: $w_content, owner: $username})
                    MERGE (s)-[:has_word]->(w)
                """, s_content=s_content, w_content=w_content, username=formatted_username)

                if prev_w:
                    # MODIFIED: MATCH must now find owner-specific words
                    session.run("""
                        MATCH (w1:SensoryMemory:Word {content: $pw, owner: $username}), 
                              (w2:SensoryMemory:Word {content: $cw, owner: $username})
                        MERGE (w1)-[:next_word]->(w2)
                    """, pw=prev_w, cw=w_content, username=formatted_username)
                prev_w = w_content

# --- RELATIONSHIPS (Integrated) ---

def store_relation(username, p1, rel_type, p2):
    rel_name = f"is_{rel_type.lower()}"
    formatted_username = f"user {username}"
    
    with driver.session() as session:
        if p2.lower() == "my":
            # MODIFIED: MERGE on Word must include the owner
            query = f"""
            MATCH (u:User {{name: $username}})
            MERGE (w1:SensoryMemory:Word {{content: $p1, owner: $username}})
            MERGE (w1)-[:{rel_name}]->(u)
            """
            session.run(query, username=formatted_username, p1=p1)
        else:
            # MODIFIED: MERGE on both Words must include the owner
            query = f"""
            MERGE (w1:SensoryMemory:Word {{content: $p1, owner: $username}})
            MERGE (w2:SensoryMemory:Word {{content: $p2, owner: $username}})
            MERGE (w1)-[:{rel_name}]->(w2)
            """
            session.run(query, p1=p1, p2=p2, username=formatted_username)

def query_relation(username, p_name, rel_type):
    rel_name = f"is_{rel_type.lower()}"
    formatted_username = f"user {username}"
    
    # MODIFIED: All MATCH clauses must filter by owner
    query = f"""
    // Check for user's relative (now includes owner check on the Word)
    OPTIONAL MATCH (subject:SensoryMemory:Word {{owner: $username}})-[:{rel_name}]->(u:User {{name: $username}})
    WHERE $p_name = 'my'
    
    // Check for third-party relative (now includes owner check on all Words)
    OPTIONAL MATCH (subject2:SensoryMemory:Word {{owner: $username}})-[:{rel_name}]->(target:SensoryMemory:Word {{content: $p_name, owner: $username}})
    
    RETURN coalesce(subject.content, subject2.content) AS result
    """
    with driver.session() as session:
        result = session.run(query, username=formatted_username, p_name=p_name.lower())
        record = result.single()
        return record["result"].capitalize() if record and record["result"] else None

def updateUserGender(username, gender):
    formatted_username = f"user {username}"
    query = "MERGE (u:User {name: $username}) SET u.gender = $gender"
    with driver.session() as session:
        session.run(query, username=formatted_username, gender=gender)

def get_stored_gender(username):
    formatted_username = f"user {username}"
    query = "MATCH (u:User {name: $username}) RETURN u.gender AS gender"
    with driver.session() as session:
        result = session.run(query, username=formatted_username)
        record = result.single()
        if record and record["gender"] and record["gender"] != "Not Told":
            return record["gender"]
        return None
        
def updateSensoryMemory(username, Text):
    # MODIFIED: Must pass username down to the sub-functions
    tid = createTextNode(username, Text)
    createSentenceNode(tid, Text, username)
    createWordNode(Text, username)