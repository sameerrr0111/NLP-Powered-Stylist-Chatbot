# hardware_main.py
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from aiml import Kernel
import neo4j_connector as db
import sensory_memory_hw as sm
import requests

app = Flask(__name__)
app.secret_key = 'a_very_secret_key_for_sessions'

# Initialize AIML Bot
bot = Kernel()
bot.learn("aiml_files/*.aiml")

# --- COMMAND KEYWORDS ---
HONK_KEYWORDS = ["honk", "horn", "honkk", "beep"]
RED_LIGHT_KEYWORDS = ["red light", "red on", "turn red", "red led"]
GREEN_LIGHT_KEYWORDS = ["green light", "green on", "turn green", "green led"]
YELLOW_LIGHT_KEYWORDS = ["yellow light", "yellow on", "turn yellow", "yellow led"]
SOIL_KEYWORDS = ["soil", "soil moisture", "moisture", "soil data"]
TEMP_KEYWORDS = ["temperature", "temp", "humidity", "dht", "weather"]
LDR_KEYWORDS = ["ldr", "light sensor", "light level", "brightness"]
SET_LIMIT_KEYWORDS = ["set", "change", "update"]

# --- MAIN & CHATBOT ROUTES ---
@app.route("/")
def home():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    # Check if the user already has a device to decide which view to show
    has_device = db.get_user_device_status(session['user_email'])
    
    return render_template(
        "home.html", 
        name=session.get('user_name', 'User'),
        has_device=has_device,
        default_device_id=db.DEFAULT_DEVICE_ID # Pass the default ID to the template
    )

def log_action_in_neo4j(actuator_name, action_name, text_node_id):
    """
    Logs an action in Neo4j and links it to the existing Text node from Sensory Memory.
    """
    with db.driver.session() as session:
        session.run("""
            MERGE (act:Actuator {name: $actuator_name})
            CREATE (a:Action {name: $action_name, timestamp: timestamp()})
            WITH act, a
            MATCH (cmd:SensoryMemory:Text) WHERE elementId(cmd) = $text_node_id
            MERGE (act)-[:PERFORMED]->(a)
            MERGE (a)-[:TRIGGERED_BY]->(cmd)
        """, actuator_name=actuator_name, action_name=action_name, text_node_id=text_node_id)
@app.route("/get")
def get_bot_response():
    user_email = session.get('user_email')
    if not user_email: return "Authentication error."

    user_message = request.args.get('msg', '').strip().lower()

    text_node_id = sm.store_user_input_sensory_memory(db.driver, user_email, user_message)

    import re

    # --- SET SENSOR LIMIT ---
    if any(k in user_message for k in SET_LIMIT_KEYWORDS) and "limit" in user_message:
        
        match = re.search(r"(temperature|humidity|soil|ldr).*?(\d+)", user_message)

        if match:
            sensor = match.group(1)
            value = int(match.group(2))

            success = send_limit_to_esp(sensor, value, user_email)

            if success:
                return f"✅ {sensor.capitalize()} limit updated to {value}"
            else:
                return "Device not reachable."

    # --- ESP BUZZER COMMAND ---
    if any(keyword in user_message for keyword in HONK_KEYWORDS):
        success = send_command_to_esp("honk", user_email)
        if success:
            bot.setBotPredicate("last_action", "honk")

            
            # --- NEW: Log Action ---
            log_action_in_neo4j("Buzzer", "Beep", text_node_id)

            return bot.respond("HONK COMMAND")


        else:
            return "Device not reachable."

    # --- ESP RED LIGHT ---
    if any(keyword in user_message for keyword in RED_LIGHT_KEYWORDS):
        success = send_command_to_esp("red", user_email)
        if success:
            log_action_in_neo4j("Red Light", "Turned On", text_node_id)
            return bot.respond("RED LIGHT")
        else:
            return "Device not reachable."


    # --- ESP GREEN LIGHT ---
    if any(keyword in user_message for keyword in GREEN_LIGHT_KEYWORDS):
        success = send_command_to_esp("green", user_email)
        if success:
            log_action_in_neo4j("Green Light", "Turned On", text_node_id)
            return bot.respond("GREEN LIGHT")
        else:
            return "Device not reachable."


    # --- ESP YELLOW LIGHT ---
    if any(keyword in user_message for keyword in YELLOW_LIGHT_KEYWORDS):
        success = send_command_to_esp("yellow", user_email)
        if success:
            log_action_in_neo4j("Yellow Light", "Turned On", text_node_id)
            return bot.respond("YELLOW LIGHT")
        else:
            return "Device not reachable."

    # --- SOIL MOISTURE DATA ---
    if any(keyword in user_message for keyword in SOIL_KEYWORDS):
        latest_data = db.get_latest_sensor_data(user_email)
        if latest_data and "soil" in latest_data:
            return f"🌱 Soil Moisture: {latest_data['soil']}%"
        else:
            return "No soil moisture data available."

    # --- TEMPERATURE & HUMIDITY DATA ---
    if any(keyword in user_message for keyword in TEMP_KEYWORDS):
        latest_data = db.get_latest_sensor_data(user_email)
        if latest_data and "temperature" in latest_data and "humidity" in latest_data:
            return f"🌡 Temperature: {latest_data['temperature']}°C | 💧 Humidity: {latest_data['humidity']}%"
        else:
            return "No temperature/humidity data available."

    # --- LDR LIGHT DATA ---
    if any(keyword in user_message for keyword in LDR_KEYWORDS):
        latest_data = db.get_latest_sensor_data(user_email)
        if latest_data and "ldr" in latest_data:
            return f"💡 Light Intensity: {latest_data['ldr']}"
        else:
            return "No light sensor data available."



    if "sensor" in user_message or "plant" in user_message or "data" in user_message:
        latest_data = db.get_latest_sensor_data(user_email)
        if latest_data:
            response_parts = ["Here are the latest readings:"]
            for sensor, value in latest_data.items():
                response_parts.append(f"- {sensor.capitalize()}: {value}")
            return " ".join(response_parts)
        else:
            return "I couldn't find any sensor data. Make sure your device is active and sending data."
    
    response = bot.respond(user_message)
    return response if response else "I'm not sure how to respond to that."



def send_limit_to_esp(sensor, value, user_email):
    device_query = """
    MATCH (:User {email: $user_email})-[:HAS_ACCESS]->(d:ESPDevice)
    RETURN d.device_id AS device_id
    """
    with db.driver.session(database="neo4j") as session:
        result = session.run(device_query, user_email=user_email).single()
        if not result:
            return False
        device_id = result["device_id"]

    try:
        response = requests.post(
            "http://192.168.100.117:8000/command",
            json={
                "device_id": device_id,
                "command": "set_limit",
                "sensor": sensor,
                "value": value
            },
            timeout=5
        )

        success = response.status_code == 200

        if success:
            # Update the Sensor node's limit in Neo4j
            with db.driver.session() as session:
                session.run("""
                    MATCH (d:ESPDevice {device_id: $device_id})<-[:ATTACHED_TO]-(s:Sensor {type: $sensor})
                    SET s.limit = $value
                """, device_id=device_id, sensor=sensor, value=value)

        return success

    except Exception as e:
        print("Error sending limit to ESP:", e)
        return False

@app.route("/get-default-limits", methods=["GET"])
def get_default_limits():
    # Fetch limits for the default device
    device_id = db.DEFAULT_DEVICE_ID
    with db.driver.session() as session:
        result = session.run("""
            MATCH (d:ESPDevice {device_id: $device_id})<-[:ATTACHED_TO]-(s:Sensor)
            RETURN s.type AS type, s.limit AS limit
        """, device_id=device_id)
        limits = {record["type"]: record["limit"] for record in result}
    return jsonify({"status": "success", "limits": limits})

# --- SECURE IOT DATA ENDPOINT ---
@app.route("/sensor-data", methods=["POST"])
def receive_sensor_data():
    data = request.get_json()
    device_id = data.get('device_id')
    device_secret = data.get('device_secret')
    readings = data.get('readings')

    if not all([device_id, device_secret, readings]):
        return jsonify({"status": "error", "message": "Missing required data"}), 400

    result = db.store_sensor_reading(device_id, device_secret, readings)
    
    if result["status"] == "success":
        print(f"Received data from Device {device_id}: {readings}")
        return jsonify(result), 200
    else:
        return jsonify(result), 403

def send_command_to_esp(command, user_email):
    device_query = """
    MATCH (:User {email: $user_email})-[:HAS_ACCESS]->(d:ESPDevice)
    RETURN d.device_id AS device_id
    """
    with db.driver.session(database="neo4j") as session:
        result = session.run(device_query, user_email=user_email).single()
        if not result:
            print("No device found for user")
            return False

        device_id = result["device_id"]

    try:
        response = requests.post(
            "http://192.168.100.117:8000/command",
            json={
                "device_id": device_id,
                "command": command
            },
            timeout=5
        )

        print("ESP Response Code:", response.status_code)
        print("ESP Response Text:", response.text)

        return response.status_code == 200

    except Exception as e:
        print("ESP Communication Error:", e)
        return False


# --- AUTH & DEVICE ACTIVATION ROUTES ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name, email, password = request.form.get("name"), request.form.get("email"), request.form.get("password")
        if not all([name, email, password]):
            flash("All fields are required.", "error")
            return render_template("signup.html")
            
        ip_address = get_client_ip()
        user = db.create_user(name, email, password, ip_address)
        if user:
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("An account with this email already exists.", "error")
            return render_template("signup.html")
    return render_template("signup.html")

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email,password = request.form.get("email"),request.form.get("password")
        user = db.verify_user(email,password)

        if user:
            ip_address = get_client_ip()

            # Update IP in Neo4j
            with db.driver.session() as neo4j_session:
                neo4j_session.run("""
                    MATCH (u:User {email: $email})
                    SET u.ip_address = $ip_address
                """, email=email, ip_address=ip_address)

            session['user_email'] = email
            session['user_name'] = user['name']
            return redirect(url_for('home'))
        else:
            flash("Invalid email or password.", "error")
            return render_template("login.html")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/activate", methods=["POST"])
def activate():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    device_id = request.form.get("device_id")
    activation_code = request.form.get("activation_code")
    # --- CHANGE IS HERE ---
    # Get the plant name from the form. The key 'plant_name' MUST match the 'name' attribute in the HTML.
    plant_name = request.form.get("plant_name")
    
    # --- AND CHANGE IS HERE ---
    # Pass the new plant_name variable to the database function.
    result = db.activate_device(session['user_email'], device_id, activation_code, plant_name)
    
    flash(result["message"], "success" if result["success"] else "error")
    return redirect(url_for('home'))

# --- RUN APP ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)