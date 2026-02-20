# neo4j_connector.py
from neo4j import GraphDatabase
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import datetime
import socket


# --- DATABASE CONNECTION ---
URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "12345678")  # Use your Neo4j credentials
driver = GraphDatabase.driver(URI, auth=AUTH)

# Define the credentials for the default ESP device that will be created on startup
DEFAULT_DEVICE_ID = "ESP-001"
DEFAULT_ACTIVATION_CODE = "1234-5678" # This is the secret code the user will enter

def get_server_ip():
    """
    Returns the local IP address of the machine where this code runs.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))   # Doesn't send data, just used to detect outbound IP
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# --- INITIALIZATION ---
def initialize_system():
    server_ip = get_server_ip()
    """
    Initializes the graph with a static structure based on the user's diagram.
    This function is idempotent and can be run safely every time the app starts.
    """
    # Use the activation code to create a HASH for secure storage
    device_secret_hash = generate_password_hash(DEFAULT_ACTIVATION_CODE)

    with driver.session(database="neo4j") as session:
        # 1. Create constraints for unique properties
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:ESPDevice) REQUIRE d.device_id IS UNIQUE")

        # 2. MERGE the three Creator nodes, the Agent node, and the idle ESPDevice node
        session.run("""
        MERGE (a:Agent {name: 'PlantBot'})
        ON CREATE SET a.role = 'Agent', a.ip_address = $server_ip, a.created_at = timestamp(),
            a.job = 'Assistant for Plant Monitoring',
            a.description = 'This device is designed to monitor plant health by collecting data on soil moisture, temperature, humidity, and light levels. It serves as an assistant for plant monitoring and care.',
            a.capabilities = 'Soil Moisture Sensor, Temperature Sensor, Humidity Sensor, Light Sensor, Buzzer, Red Light, Green Light, Yellow Light'
        MERGE (c1:Person:Creator {name: 'Sameer'})
        ON CREATE SET c1.role = 'Creator', c1.ip_address = $server_ip, c1.created_at = timestamp(), c1.email = 'sameerjavaid1234@gmail.com', c1.age = 23, c1.gender = 'Male', c1.expertise = 'Neo4j, Python', c1.bio = 'Sameer is a passionate software developer with expertise in Neo4j and Python. He has a strong background in graph databases and enjoys creating innovative solutions to complex problems. With a keen interest in IoT and smart systems, Sameer is dedicated to building efficient and scalable applications that leverage the power of graph technology.', c1.institution = 'University of Management and Technology, Lahore'
        MERGE (c2:Person:Creator {name: 'Ghani'})
        ON CREATE SET c2.role = 'Creator', c2.ip_address = $server_ip, c2.created_at = timestamp(), c2.email = 'ghani@gmail.com', c2.age = 22, c2.gender = 'Male', c2.expertise = 'Python, IoT', c2.bio = 'Ghani is a skilled developer with expertise in Python and IoT technologies. He is passionate about building smart systems that integrate seamlessly with graph databases.', c2.institution = 'University of Management and Technology, Lahore'
        MERGE (c3:Person:Creator {name: 'Talha'})
        ON CREATE SET c3.role = 'Creator', c3.ip_address = $server_ip, c3.created_at = timestamp(), c3.email = 'talhanadeem.works@gmail.com', c3.age = 22, c3.gender = 'Male', c3.expertise = 'Python, IoT, Micropython', c3.bio = 'Talha is an enthusiastic developer with a strong background in Python, IoT, and Micropython. He is dedicated to creating innovative solutions that leverage the power of graph databases and smart technologies.', c3.institution = 'University of Management and Technology, Lahore'
        MERGE (c4:Person:Creator {name: 'Noor Ul Hassan'})
        ON CREATE SET c4.role = 'Creator', c4.ip_address = $server_ip, c4.created_at = timestamp(), c4.email = 'noorulhassan@gmail.com', c4.age = 22, c4.gender = 'Male', c4.expertise = 'Python, IoT', c4.bio = 'Noor Ul Hassan is a dedicated developer with expertise in Python and IoT technologies. He is passionate about building smart systems that integrate seamlessly with graph databases.', c4.institution = 'University of Management and Technology, Lahore'

        // The ESP Device is created as 'unassigned' with a pre-defined ID and hashed secret
        MERGE (d:ESPDevice {device_id: $device_id})
        ON CREATE SET
            d.status = 'unassigned',
            d.device_secret_hash = $secret_hash,
            d.registered_at = timestamp(),
            d.ip_address = $server_ip

        // 3. MERGE the relationships between Creators and the Agent
        MERGE (c1)-[:CREATED]->(a) MERGE (a)-[:CREATED_BY]->(c1)
        MERGE (c2)-[:CREATED]->(a) MERGE (a)-[:CREATED_BY]->(c2)
        MERGE (c3)-[:CREATED]->(a) MERGE (a)-[:CREATED_BY]->(c3)
        MERGE (c4)-[:CREATED]->(a) MERGE (a)-[:CREATED_BY]->(c4)
        MERGE (a)-[:HAS_DEVICE]->(d)
        """, device_id=DEFAULT_DEVICE_ID, secret_hash=device_secret_hash, server_ip=server_ip)

        # --- CREATE DEFAULT SENSORS WITH LIMIT ATTRIBUTES ---
        default_sensors = {
            "temperature": {"limit": 30, "name": "Temperature Sensor"},
            "humidity": {"limit": 70, "name": "Humidity Sensor"},
            "soil": {"limit": 50, "name": "Soil Moisture Sensor"},
            "ldr": {"limit": 800, "name": "Light Sensor"}
        }

        # --- DEFAULT ACTUATORS ---
        default_actuators = {
            "buzzer": {"name": "Buzzer", "type": "buzzer"},
            "red_light": {"name": "Red Light", "type": "red_light"},
            "green_light": {"name": "Green Light", "type": "green_light"},
            "yellow_light": {"name": "Yellow Light", "type": "yellow_light"}
        }

        for sensor_type, props in default_sensors.items():
            session.run("""
                MATCH (d:ESPDevice {device_id: $d_id})
                MERGE (s:Sensor {type: $sensor_type})
                ON CREATE SET 
                    s.name = $sensor_name,
                    s.limit = $limit
                MERGE (s)-[:ATTACHED_TO]->(d)
            """, sensor_type=sensor_type, sensor_name=props["name"], limit=props["limit"], d_id=DEFAULT_DEVICE_ID)
        
        for actuator_key, props in default_actuators.items():
            session.run("""
                MATCH (d:ESPDevice {device_id: $d_id})
                MERGE (a:Actuator {type: $actuator_type})
                ON CREATE SET a.name = $actuator_name
                MERGE (a)-[:ATTACHED_TO]->(d)
            """, actuator_type=props["type"], actuator_name=props["name"], d_id=DEFAULT_DEVICE_ID)  

    print(f"System initialization complete. Default device '{DEFAULT_DEVICE_ID}' is ready for activation.")


# --- USER MANAGEMENT ---
def create_user(name, email, password, ip_address):
    """Creates a new User node and connects them to the central Agent."""
    password_hash = generate_password_hash(password)
    user_id = str(uuid.uuid4())

    with driver.session(database="neo4j") as session:
        result = session.run("MATCH (u:User {email: $email}) RETURN u", email=email).single()
        if result:
            return None  # User already exists

        # --- THIS QUERY IS THE FIX ---
        # The change is changing "MATCH (a:Agent...)" to "MERGE (a:Agent...)"
        # This makes the function robust and prevents the crash.
        query = """
        MERGE (a:Agent {name: 'PlantBot'})
        CREATE (u:Person:User {
            user_id: $user_id,
            name: $name,
            email: $email,
            role: 'User',
            password_hash: $password_hash,
            created_at: timestamp(),
            ip_address: $ip_address
        })
        MERGE (u)-[:USES]->(a)
        MERGE (a)-[:HAS_USER]->(u)
        RETURN u
        """
        result = session.run(query, user_id=user_id, name=name, email=email, password_hash=password_hash, ip_address=ip_address)
        # This line will now be safe because the query is guaranteed to return the new user.
        return result.single()[0]


def verify_user(email, password):
    """Verifies a user's credentials."""
    with driver.session(database="neo4j") as session:
        query = "MATCH (u:User {email: $email}) RETURN u.password_hash AS hash, u.name AS name"
        result = session.run(query, email=email).single()
        if result and check_password_hash(result['hash'], password):
            return {"name": result['name']}
        return None

# --- DEVICE MANAGEMENT ---

def activate_device(user_email, device_id, activation_code, plant_name):
    """
    Allows a user to activate a device.
    - If it's the first user, it registers the plant name.
    - If it's a subsequent user, it verifies the plant name before granting access.
    """
    with driver.session(database="neo4j") as session:
        # First, authenticate the device ID and activation code. This is the main gatekeeper.
        auth_query = """
        MATCH (d:ESPDevice {device_id: $device_id})
        RETURN d.device_secret_hash AS hash, d.status AS status
        """
        device_data = session.run(auth_query, device_id=device_id).single()

        # Fail if device doesn't exist or code is wrong
        if not device_data or not check_password_hash(device_data['hash'], activation_code):
            return {"success": False, "message": "Invalid Device ID or Activation Code."}

        # --- NEW LOGIC STARTS HERE ---

        # Case 1: Device is 'unassigned'. This is the FIRST user activating it.
        if device_data['status'] == 'unassigned':
            # This user sets the plant name for the device.
            first_activation_query = """
            MATCH (u:User {email: $user_email})
            MATCH (d:ESPDevice {device_id: $device_id})
            // Create the new Plant node
            MERGE (p:Plant {name: $plant_name})
            // Link everything together
            MERGE (d)-[:MONITORS]->(p)
            MERGE (u)-[:HAS_ACCESS]->(d)
            // Set the device status to active
            SET d.status = 'active'
            """
            session.run(first_activation_query, user_email=user_email, device_id=device_id, plant_name=plant_name)
            print(f"First activation: User '{user_email}' registered plant '{plant_name}' for device '{device_id}'.")
            return {"success": True, "message": "Device activated and plant registered successfully!"}

        # Case 2: Device is already 'active'. This is a SECOND or subsequent user.
        elif device_data['status'] == 'active':
            # We must verify the plant name matches the one already linked to the device.
            plant_check_query = """
            MATCH (d:ESPDevice {device_id: $device_id})-[:MONITORS]->(p:Plant)
            RETURN p.name AS existing_plant_name
            """
            plant_result = session.run(plant_check_query, device_id=device_id).single()

            # If the plant name matches, grant access.
            if plant_result and plant_result['existing_plant_name'] == plant_name:
                shared_access_query = """
                MATCH (u:User {email: $user_email})
                MATCH (d:ESPDevice {device_id: $device_id})
                MERGE (u)-[:HAS_ACCESS]->(d)
                """
                session.run(shared_access_query, user_email=user_email, device_id=device_id)
                print(f"Shared access granted to '{user_email}' for device '{device_id}'.")
                return {"success": True, "message": "Shared access granted successfully!"}
            else:
                # If the plant name is wrong, deny access.
                return {"success": False, "message": "Invalid Plant Name. Please enter the name of the plant already being monitored by this device."}
        
        # Fallback for any other status
        return {"success": False, "message": "Device is not in a valid state for activation."}

def get_user_device_status(user_email):
    """Checks if a user already owns a device."""
    with driver.session(database="neo4j") as session:
        query = "MATCH (:User {email: $user_email})-[:HAS_ACCESS]->(d:ESPDevice) RETURN d"
        result = session.run(query, user_email=user_email).single()
        return result is not None

# --- SENSOR DATA INGESTION & RETRIEVAL ---
# These functions remain the same as they are already compatible with the new structure.
def store_sensor_reading(device_id, device_secret, readings):
    """Stores a new sensor reading from an authenticated device."""
    with driver.session(database="neo4j") as session:
        auth_query = "MATCH (d:ESPDevice {device_id: $device_id}) RETURN d.device_secret_hash AS hash"
        result = session.run(auth_query, device_id=device_id).single()

        if not result or not check_password_hash(result['hash'], device_secret):
            return {"status": "error", "message": "Invalid device credentials"}

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        reading_query = """
        MATCH (d:ESPDevice {device_id: $device_id})
        UNWIND keys($readings) AS sensor_type
        MERGE (s:Sensor {type: sensor_type})-[:ATTACHED_TO]->(d)
        CREATE (r:Reading {value: $readings[sensor_type], timestamp: $timestamp})
        CREATE (s)-[:HAS_READING]->(r)
        """
        session.run(reading_query, device_id=device_id, readings=readings, timestamp=timestamp)
        return {"status": "success", "message": "Data stored"}


def get_latest_sensor_data(user_email):
    """
    Fetches the latest readings from all sensors of the user's device.
    Returns a dictionary: {"soil": 65, "temperature": 28, "humidity": 50, "ldr": 1234}
    """
    query = """
    MATCH (u:User {email: $user_email})-[:HAS_ACCESS]->(device:ESPDevice)
    MATCH (sensor:Sensor)-[:ATTACHED_TO]->(device)
    MATCH (sensor)-[:HAS_READING]->(reading:Reading)
    WITH sensor.type AS sensor_type, reading.value AS value, reading.timestamp AS timestamp
    ORDER BY timestamp DESC
    RETURN sensor_type, value
    """

    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        latest_data = {}
        # Keep only the latest reading per sensor type
        for record in result:
            if record["sensor_type"] not in latest_data:
                latest_data[record["sensor_type"]] = record["value"]

    return latest_data



# Run initialization every time the application starts
initialize_system()