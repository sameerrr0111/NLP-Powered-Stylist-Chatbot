# llm.py
import os
import json
from dotenv import load_dotenv
from langchain_openai import OpenAI
from langchain_core.prompts import PromptTemplate
import gender_guesser.detector as gender
from neo4j_sensory_mem import store_relation, get_stored_gender

# Load environment variables from .env file
load_dotenv()

# Check if the API key is loaded
if "OPENAI_API_KEY" not in os.environ:
    raise ValueError("OpenAI API key not found. Please set it in your .env file.")

# Initialize the Language Model
llm = OpenAI(temperature=0.2)

# Initialize the gender detector
gender_detector = gender.Detector()

def get_gender_from_name(name):
    """Guesses the gender of a given first name."""
    # gender_guesser works best with the first name
    first_name = name.split()[0].capitalize()
    gender_result = gender_detector.get_gender(first_name)
    
    # Standardize the output
    if "female" in gender_result:
        return "female"
    elif "male" in gender_result:
        return "male"
    else:
        return "unknown"

def get_opposite_relation(relation):
    prompt = PromptTemplate(
        input_variables=["relation"],
        template="""
        You are a logical reasoner.

        Given a family or social relationship, return the male and female opposites.

        Examples:
        aunt → nephew (male), niece (female)
        teacher → student (both)
        husband → wife (female)

        Return ONLY valid JSON in this format:
        {"male": "...", "female": "..."}

        Relationship: {relation}
        """
    )

    # Runnable pipeline (modern LangChain)
    runnable = prompt | llm

    try:
        response = runnable.invoke({"relation": relation})

        cleaned = (
            response.strip()
            .replace("```", "")
            .replace("json", "")
        )

        return json.loads(cleaned)

    except Exception as e:
        print("LLM error or JSON parse failure:", e)
        print("Raw response:", response)
        return None


def process_and_store_bidirectional_relation(username, p1, rel, p2, user_gender=None):
    """
    The main orchestrator function.
    1. Stores the original relation.
    2. Infers the opposite relation.
    3. Determines the correct gendered term.
    4. Stores the opposite relation.
    """
    # Step 1: Store the original, forward relationship
    print(f"Storing forward relation: {p1} -> {rel} -> {p2}")
    store_relation(username, p1, rel, p2)
    
    # Step 2: Get the opposite relationship terms from the LLM
    opposite_relations = get_opposite_relation(rel)
    if not opposite_relations:
        print("Could not determine opposite relation. Halting.")
        return

    # Step 3: Determine the gender of the subject of the new relationship
    # The new subject is the old object (p2)
    subject_gender = "unknown"
    if p2.lower() == "my":
        # The subject is the user. We get their stored gender.
        subject_gender = user_gender or get_stored_gender(username) or "unknown"
    else:
        # The subject is a named person. We guess their gender.
        subject_gender = get_gender_from_name(p2)
        
    print(f"Determined gender of '{p2}' as: {subject_gender}")

    # Step 4: Choose the correct opposite relation based on gender
    opposite_rel = ""
    if subject_gender == "female" and "female" in opposite_relations:
        opposite_rel = opposite_relations["female"]
    elif subject_gender == "male" and "male" in opposite_relations:
        opposite_rel = opposite_relations["male"]
    else:
        # Fallback for unknown/neutral gender
        opposite_rel = opposite_relations.get("male") or opposite_relations.get("female")

    if not opposite_rel:
        print(f"Could not select a valid opposite relation from {opposite_relations}")
        return

    # Step 5: Store the new, backward relationship
    # The old p2 is the new p1, and the old p1 is the new p2.
    print(f"Storing backward relation: {p2} -> {opposite_rel} -> {p1}")
    store_relation(username, p2, opposite_rel, p1)