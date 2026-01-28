import re
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError


class PrologToNeo4jBridge:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            self.driver.verify_connectivity()
            print("✅ Connection Verified!")
        except AuthError:
            print("❌ AUTH ERROR: Check your credentials.")
            raise

    def close(self):
        self.driver.close()

    def run_conversion(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()

        # Regex captures: predicate(arg1, arg2) or predicate(arg1)
        facts = re.findall(r'(\w+)\s*\(([^)]+)\)\s*\.', content)

        if not facts:
            print("⚠️ No facts found. Ensure lines end with a period (.).")
            return

        with self.driver.session() as session:
            print(f"--- Step 1: Loading {len(facts)} Facts ---")
            for predicate, args in facts:
                # Cleaning arguments (removing quotes and whitespace)
                params = [p.strip().strip("'").strip('"') for p in args.split(',')]

                try:
                    # 1. Handle Genders (male/female)
                    if predicate.lower() in ['male', 'female']:
                        label = predicate.capitalize()
                        session.run(f"MERGE (p:Person {{name: $n}}) SET p:{label}", n=params[0])

                    # 2. Handle direct Parent Link (parent_of)
                    elif predicate.lower() == 'parent_of' and len(params) == 2:
                        session.run("""
                            MERGE (p1:Person {name: $p_name})
                            MERGE (p2:Person {name: $c_name})
                            MERGE (p1)-[:PARENT_OF]->(p2)
                        """, p_name=params[0], c_name=params[1])

                except Exception as e:
                    print(f"Skipping fact {predicate}({args}): {e}")

            print("--- Step 2: Materializing Rules (Rules -> Edges) ---")
            # These Cypher queries replicate your Prolog rules exactly
            inferences = {
                "FATHER_OF": "MATCH (f:Male)-[:PARENT_OF]->(c) MERGE (f)-[:FATHER_OF]->(c)",
                "MOTHER_OF": "MATCH (m:Female)-[:PARENT_OF]->(c) MERGE (m)-[:MOTHER_OF]->(c)",
                "GRANDFATHER": "MATCH (gp:Male)-[:PARENT_OF]->(z)-[:PARENT_OF]->(c) MERGE (gp)-[:GRANDFATHER_OF]->(c)",
                "GRANDMOTHER": "MATCH (gm:Female)-[:PARENT_OF]->(z)-[:PARENT_OF]->(c) MERGE (gm)-[:GRANDMOTHER_OF]->(c)",
                "SIBLINGS": "MATCH (a)-[:PARENT_OF]-(p)-[:PARENT_OF]->(b) WHERE a <> b MERGE (a)-[:SIBLING_OF]->(b)",
                "UNCLE": "MATCH (u:Male)-[:SIBLING_OF]-(p)-[:PARENT_OF]->(c) MERGE (u)-[:UNCLE_OF]->(c)",
                "AUNT": "MATCH (a:Female)-[:SIBLING_OF]-(p)-[:PARENT_OF]->(c) MERGE (a)-[:AUNT_OF]->(c)"
            }

            for name, query in inferences.items():
                session.run(query)
                print(f"✅ Materialized {name}")

        print("\n🚀 SUCCESS! All facts and rules are now in Neo4j.")


if __name__ == "__main__":
    URI = "neo4j://localhost:7687"
    USER = "neo4j"
    PASSWORD = "123456789"
    FILE_PATH = r"C:\Users\Hp\PycharmProjects\KRR-F2025\Prolog files\social.pl"

    bridge = PrologToNeo4jBridge(URI, USER, PASSWORD)
    try:
        bridge.run_conversion(FILE_PATH)
    finally:
        bridge.close()