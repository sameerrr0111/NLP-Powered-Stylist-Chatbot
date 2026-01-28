# neo4j_sensory_mem.py
import nltk
from neo4j import GraphDatabase

# Setup NLTK
nltk.download('punkt')

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "12345678") 
driver = GraphDatabase.driver(URI, auth=AUTH)

# --- ASSIGNMENT 3: SENSORY MEMORY (bot_agent) ---

def createTextNode(username, Text):
    query = """
    MERGE (a:Agent {name: 'bot_agent'})
    MERGE (ra:Agent {name: 'relation_agent'})
    MERGE (a)-[:HAS_SUB_AGENT]->(ra)
    
    // Create/Match the specific User node
    MERGE (u:User {name: $username})
    MERGE (a)-[:HAS_USER]->(u)
    
    // Create the Text node linked to the User
    CREATE (t:SensoryMemory:Text {content: $text, time: timestamp()})
    MERGE (u)-[:has_text]->(t)
    RETURN elementId(t) AS text_id
    """
    with driver.session() as session:
        # We prepend 'user ' as requested: "user Ali"
        formatted_username = f"user {username}"
        result = session.run(query, username=formatted_username, text=Text)
        return result.single()["text_id"]

def createSentenceNode(text_id, Text):
    sentences = nltk.sent_tokenize(Text)
    prev_s = None
    with driver.session() as session:
        for s_content in sentences:
            session.run("""
                MATCH (t) WHERE elementId(t) = $t_id
                MERGE (s:SensoryMemory:Sentence {content: $s_content})
                MERGE (t)-[:has_sentence]->(s)
            """, t_id=text_id, s_content=s_content)

            if prev_s:
                session.run("""
                    MATCH (s1:SensoryMemory:Sentence {content: $p}), (s2:SensoryMemory:Sentence {content: $c})
                    MERGE (s1)-[:next_sentence]->(s2)
                """, p=prev_s, c=s_content)
            prev_s = s_content

def createWordNode(Text):
    sentences = nltk.sent_tokenize(Text)
    with driver.session() as session:
        for s_content in sentences:
            words = nltk.word_tokenize(s_content)
            prev_w = None
            for w_content in words:
                session.run("""
                    MATCH (s:SensoryMemory:Sentence {content: $s_content})
                    MERGE (w:SensoryMemory:Word {content: $w_content})
                    MERGE (s)-[:has_word]->(w)
                """, s_content=s_content, w_content=w_content)

                if prev_w:
                    session.run("""
                        MATCH (w1:SensoryMemory:Word {content: $pw}), (w2:SensoryMemory:Word {content: $cw})
                        MERGE (w1)-[:next_word]->(w2)
                    """, pw=prev_w, cw=w_content)
                prev_w = w_content

# --- ASSIGNMENT 2: RELATIONSHIPS (relation_agent) ---


def store_relation(username, p1, rel_type, p2):
    """
    If p2 is 'my', link Word(p1) -> User(username)
    Otherwise, link Word(p1) -> Word(p2)
    """
    rel_name = f"is_{rel_type.lower()}"
    formatted_username = f"user {username}"
    
    with driver.session() as session:
        if p2.lower() == "my":
            # Scenario: "Ali is my father" -> (Word:Ali)-[:is_father]->(User:user Olive)
            query = f"""
            MATCH (u:User {{name: $username}})
            MERGE (w1:SensoryMemory:Word {{content: $p1}})
            MERGE (w1)-[:{rel_name}]->(u)
            """
            session.run(query, username=formatted_username, p1=p1)
        else:
            # Scenario: "Usman is father of Raza" -> (Word:Usman)-[:is_father]->(Word:Raza)
            query = f"""
            MERGE (w1:SensoryMemory:Word {{content: $p1}})
            MERGE (w2:SensoryMemory:Word {{content: $p2}})
            MERGE (w1)-[:{rel_name}]->(w2)
            """
            session.run(query, p1=p1, p2=p2)

def query_relation(username, p_name, rel_type):
    """
    Checks if someone is the relation of the User OR another person
    """
    rel_name = f"is_{rel_type.lower()}"
    formatted_username = f"user {username}"
    
    query = f"""
    // Check if searching for User's relative
    OPTIONAL MATCH (subject:SensoryMemory:Word)-[:{rel_name}]->(u:User {{name: $username}})
    WHERE $p_name = 'my'
    
    // OR Check if searching for a third-party relative (e.g., father of Raza)
    OPTIONAL MATCH (subject2:SensoryMemory:Word)-[:{rel_name}]->(target:SensoryMemory:Word {{content: $p_name}})
    
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
        # If gender is missing or is the default "Not Told", return None
        if record and record["gender"] and record["gender"] != "Not Told":
            return record["gender"]
        return None
        
def updateSensoryMemory(username, Text):
    tid = createTextNode(username, Text)
    createSentenceNode(tid, Text)
    createWordNode(Text)


