# sensory_memory_hw.py
import nltk
import datetime
# For Sentiment Analysis
from nltk.sentiment.vader import SentimentIntensityAnalyzer
# For POS Tagging
from nltk.tag import pos_tag

# --- NLTK Setup ---
# It's best practice to run these downloads once from a separate script or your main app's __main__ block.
# They are commented out here to prevent repeated downloads on every script run.
# nltk.download('punkt')
# nltk.download('vader_lexicon')
# nltk.download('averaged_perceptron_tagger') # Required for pos_tag

# Initialize Sentiment Intensity Analyzer globally
sia = SentimentIntensityAnalyzer()

# --- Core Sensory Memory Functions ---

def _create_text_node(driver, user_email, raw_text):
    """
    Creates a (:SensoryMemory:Text) node for the entire user input
    and links it to the User. Returns the elementId of the Text node.
    'CREATE' is used here as each full user input is considered a new unique 'Text' event.
    """
    current_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    query = """
    MATCH (u:User {email: $user_email})
    CREATE (t:SensoryMemory:Text {
        content: $raw_text,
        timestamp: $timestamp_param
    })
    MERGE (u)-[:HAS_TEXT]->(t)
    RETURN elementId(t) AS text_id
    """

    with driver.session(database="neo4j") as session:
        result = session.run(
            query,
            user_email=user_email,
            raw_text=raw_text,
            timestamp_param=current_timestamp
        ).single()

        return result["text_id"] if result else None


def _create_sentence_nodes(driver, text_node_id, raw_text, user_email):
    """
    Tokenizes the raw text into sentences, creates (:SensoryMemory:Sentence) nodes,
    links them to the parent Text node, and performs sentiment analysis.
    """
    sentences = nltk.sent_tokenize(raw_text)
    prev_sentence_id = None

    with driver.session(database="neo4j") as session:
        for i, s_content in enumerate(sentences):
            current_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Sentiment analysis
            sentiment_scores = sia.polarity_scores(s_content)
            compound_score = sentiment_scores['compound']
            if compound_score >= 0.05:
                sentiment_label = "Positive"
            elif compound_score <= -0.05:
                sentiment_label = "Negative"
            else:
                sentiment_label = "Neutral"

            # MERGE per user sentence
            query = """
            MATCH (t) WHERE elementId(t) = $text_id
            MERGE (s:SensoryMemory:Sentence {content: $s_content, owner_email: $user_email})
            ON CREATE SET 
                s.index = $index,
                s.timestamp = $timestamp_param,
                s.sentiment_score = $score,
                s.sentiment_label = $label
            ON MATCH SET 
                s.last_used_at = $timestamp_param
            MERGE (t)-[:HAS_SENTENCE]->(s)
            RETURN elementId(s) AS sentence_id
            """

            result = session.run(
                query,
                text_id=text_node_id,
                s_content=s_content,
                user_email=user_email,
                index=i,
                timestamp_param=current_timestamp,
                score=compound_score,
                label=sentiment_label
            ).single()

            current_sentence_id = result["sentence_id"] if result else None

            if prev_sentence_id and current_sentence_id:
                session.run("""
                    MATCH (s1), (s2)
                    WHERE elementId(s1) = $prev_s_id AND elementId(s2) = $curr_s_id
                    MERGE (s1)-[:NEXT_SENTENCE]->(s2)
                """, prev_s_id=prev_sentence_id, curr_s_id=current_sentence_id)

            prev_sentence_id = current_sentence_id

            # Now, create word nodes for this sentence, including POS tagging
            _create_word_nodes(driver, current_sentence_id, s_content, user_email)


def _create_word_nodes(driver, sentence_node_id, s_content, user_email):
    """
    Tokenizes a sentence into words, creates (:SensoryMemory:Word) nodes (MERGING duplicates
    per user for conceptual uniqueness), links them to their parent Sentence node,
    and performs POS tagging.
    """
    words_and_tags = pos_tag(nltk.word_tokenize(s_content)) # Perform POS tagging here
    prev_word_id = None

    with driver.session(database="neo4j") as session:
        for i, (w_content, tag) in enumerate(words_and_tags): # Iterate through word and its POS tag
            current_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # --- DUPLICATE HANDLING for Words (MERGE per user) ---
            # MERGE the Word node to ensure that for a given user, a word is conceptually unique.
            # If the same user says "plant" multiple times, it links to the same word node.
            word_query = """
            MATCH (s) WHERE elementId(s) = $sentence_id
            MERGE (w:SensoryMemory:Word {
                content: toLower($w_content),
                owner_email: $user_email
            })
            ON CREATE SET 
                w.created_at = $timestamp_param,
                w.index_in_sentence = $index_in_sentence // Store index as property for clarity
            ON MATCH SET
                w.last_used_at = $timestamp_param // Update last used timestamp
            MERGE (s)-[:HAS_WORD]->(w)
            RETURN elementId(w) AS word_id
            """
            result = session.run(
                word_query,
                sentence_id=sentence_node_id,
                w_content=w_content,
                user_email=user_email,
                index_in_sentence=i, # Pass index
                timestamp_param=current_timestamp
            ).single()

            current_word_id = result["word_id"] if result else None

            # --- POS TAGGING (PAM Integration) ---
            if current_word_id:
                pos_tag_query = """
                MATCH (w) WHERE elementId(w) = $word_id
                MERGE (p_tag:PAM:POS_Tag {tag: $pos_tag})
                MERGE (w)-[:HAS_POS_TAG]->(p_tag)
                """
                session.run(pos_tag_query, word_id=current_word_id, pos_tag=tag)
            # --- END POS TAGGING ---

            if prev_word_id and current_word_id:
                session.run("""
                    MATCH (w1), (w2)
                    WHERE elementId(w1) = $prev_w_id AND elementId(w2) = $curr_w_id
                    MERGE (w1)-[:NEXT_WORD]->(w2)
                """, prev_w_id=prev_word_id, curr_w_id=current_word_id)

            prev_word_id = current_word_id


# --- Main Orchestrator for Sensory Memory ---

def store_user_input_sensory_memory(driver, user_email, raw_text):
    """
    Orchestrates the creation of Text, Sentence, and Word nodes
    for a given user input in Sensory Memory, including PAM integrations.
    """
    if not raw_text.strip():
        print("Empty input received for sensory memory, skipping storage.")
        return None

    text_node_id = _create_text_node(driver, user_email, raw_text)

    if text_node_id:
        _create_sentence_nodes(driver, text_node_id, raw_text, user_email)
        print(f"Sensory Memory stored for user '{user_email}' with Text ID: {text_node_id}")
    else:
        print(f"Failed to create Text node for user '{user_email}'.")

    return text_node_id