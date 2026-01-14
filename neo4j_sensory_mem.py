# neo4j_sensory_mem.py
import nltk
from neo4j import GraphDatabase

# Setup NLTK
nltk.download('punkt')

# --- Neo4j Connection ---
URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "12345678") 
driver = GraphDatabase.driver(URI, auth=AUTH)

def createTextNode(Text):
    query = """
    MERGE (a:Agent {name: 'bot_agent'})
    MERGE (t:SensoryMemory:Text {content: $text})
    ON CREATE SET t.time = timestamp()
    MERGE (a)-[:has_text]->(t)
    RETURN elementId(t) AS text_id
    """
    with driver.session() as session:
        result = session.run(query, text=Text)
        return result.single()["text_id"]


def createSentenceNode(text_id, Text):
    sentences = nltk.sent_tokenize(Text)
    prev_sentence_node = None

    with driver.session() as session:
        for s_content in sentences:
            # Create/Merge the sentence node
            # Link it to the specific Text node we just created
            query = """
            MATCH (t) WHERE elementId(t) = $t_id
            MERGE (s:SensoryMemory:Sentence {content: $s_content})
            MERGE (t)-[:has_sentence]->(s)
            RETURN s
            """
            session.run(query, t_id=text_id, s_content=s_content)

            # Link current sentence to the previous one (Horizontal Link)
            if prev_sentence_node:
                link_query = """
                MATCH (s1:SensoryMemory:Sentence {content: $prev_content})
                MATCH (s2:SensoryMemory:Sentence {content: $curr_content})
                MERGE (s1)-[:next_sentence]->(s2)
                """
                session.run(link_query, prev_content=prev_sentence_node, curr_content=s_content)
            
            prev_sentence_node = s_content

def createWordNode(Text):
    sentences = nltk.sent_tokenize(Text)

    with driver.session() as session:
        for s_content in sentences:
            words = nltk.word_tokenize(s_content)
            prev_word_node = None

            for w_content in words:
                # 1️⃣ Check if this word is already a Person node
                query = """
                MERGE (w:Word {content: $w_content})
                MERGE (p:Person {name: $w_content})
                MERGE (w)-[:is_person]->(p)
                RETURN w, p
                """
                session.run(query, w_content=w_content)

                # 2️⃣ Link word to parent sentence
                query2 = """
                MATCH (s:Sentence {content: $s_content})
                MATCH (w:Word {content: $w_content})
                MERGE (s)-[:has_word]->(w)
                """
                session.run(query2, s_content=s_content, w_content=w_content)

                # 3️⃣ Link current word to previous word (Horizontal Link)
                if prev_word_node:
                    link_query = """
                    MATCH (w1:Word {content: $prev_w})
                    MATCH (w2:Word {content: $curr_w})
                    MERGE (w1)-[:next_word]->(w2)
                    """
                    session.run(link_query, prev_w=prev_word_node, curr_w=w_content)
                
                prev_word_node = w_content

def store_relation(p1, relation, p2):
    """
    Store semantic relationship (Ali -[:FATHER_OF]-> Hassan)
    without creating duplicates
    """
    rel = relation.upper().replace(" ", "_")

    query = f"""
    MERGE (e1:Person {{name: $p1}})
    MERGE (e2:Person {{name: $p2}})
    MERGE (e1)-[r:{rel}]->(e2)
    """
    with driver.session() as session:
        session.run(query, p1=p1, p2=p2)

    # Also connect the corresponding Word nodes from sensory memory
    query_words = """
    MATCH (w1:Word {content: $p1})
    MATCH (w2:Word {content: $p2})
    MERGE (w1)-[r2:%s]->(w2)
    """ % rel
    with driver.session() as session:
        session.run(query_words, p1=p1, p2=p2)



def query_relation(person, relation):
    rel = relation.upper().replace(" ", "_")

    query = f"""
    MATCH (p1:Person)-[:{rel}]->(p2:Person {{name: $person}})
    RETURN p1.name AS result
    """

    with driver.session() as session:
        result = session.run(query, person=person)
        record = result.single()
        return record["result"] if record else None


def updateSensoryMemory(Text):
    # This matches the flow you wanted perfectly
    tid = createTextNode(Text)
    createSentenceNode(tid, Text)
    createWordNode(Text)