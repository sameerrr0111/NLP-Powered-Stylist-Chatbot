# neo4j_sensory_mem.py
import nltk
from neo4j import GraphDatabase

# Setup NLTK
nltk.download('punkt')

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "12345678") 
driver = GraphDatabase.driver(URI, auth=AUTH)

# --- ASSIGNMENT 3: SENSORY MEMORY (bot_agent) ---

def createTextNode(Text):
    query = """
    MERGE (a:Agent {name: 'bot_agent'})
    CREATE (t:SensoryMemory:Text {content: $text, time: timestamp()})
    MERGE (a)-[:has_text]->(t)
    RETURN elementId(t) AS text_id
    """
    with driver.session() as session:
        result = session.run(query, text=Text)
        return result.single()["text_id"]

def createSentenceNode(text_id, Text):
    sentences = nltk.sent_tokenize(Text)
    prev_s = None
    with driver.session() as session:
        for s_content in sentences:
            # Create Sentence and link to Text
            session.run("""
                MATCH (t) WHERE elementId(t) = $t_id
                MERGE (s:SensoryMemory:Sentence {content: $s_content})
                MERGE (t)-[:has_sentence]->(s)
            """, t_id=text_id, s_content=s_content)

            # Link sentences (Horizontal)
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
                # 1️⃣ Create Sensory Word ONLY (No Person labels here!)
                session.run("""
                    MATCH (s:SensoryMemory:Sentence {content: $s_content})
                    MERGE (w:SensoryMemory:Word {content: $w_content})
                    MERGE (s)-[:has_word]->(w)
                """, s_content=s_content, w_content=w_content)

                # 2️⃣ Link words (Horizontal)
                if prev_w:
                    session.run("""
                        MATCH (w1:SensoryMemory:Word {content: $pw}), (w2:SensoryMemory:Word {content: $cw})
                        MERGE (w1)-[:next_word]->(w2)
                    """, pw=prev_w, cw=w_content)
                prev_w = w_content

# --- ASSIGNMENT 2: RELATIONSHIPS (relation_agent) ---

def store_relation(p1, rel_type, p2):
    rel_name = f"is_{rel_type.lower()}"
    query = f"""
    MERGE (ra:Agent {{name: 'relation_agent'}})
    MERGE (n1:Person {{name: $p1}})
    MERGE (n2:Person {{name: $p2}})
    MERGE (ra)-[:is_person]->(n1)
    MERGE (ra)-[:is_person]->(n2)
    MERGE (n1)-[:{rel_name}]->(n2)
    """
    with driver.session() as session:
        session.run(query, p1=p1.lower(), p2=p2.lower())

def query_relation(p_name, rel_type):
    rel_name = f"is_{rel_type.lower()}"
    query = f"""
    MATCH (ra:Agent {{name: 'relation_agent'}})-[:is_person]->(target:Person {{name: $p_name}})
    MATCH (subject:Person)-[:{rel_name}]->(target)
    RETURN subject.name AS result
    """
    with driver.session() as session:
        result = session.run(query, p_name=p_name.lower())
        record = result.single()
        return record["result"].capitalize() if record else None

def updateSensoryMemory(Text):
    tid = createTextNode(Text)
    createSentenceNode(tid, Text)
    createWordNode(Text)