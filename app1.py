from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db
import traceback
import os
import json

app = Flask(__name__)
CORS(app)

# Initialize Firebase Realtime Database
try:
    firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
    if not firebase_credentials:
        raise ValueError("FIREBASE_CREDENTIALS environment variable not set")

    cred_dict = json.loads(firebase_credentials)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://projet-fin-d-etude-4632f-default-rtdb.firebaseio.com/'
    })
    db_ref = db.reference('sensor_data')
    print("Firebase Realtime Database initialized successfully.")
except Exception as e:
    print(f"Failed to initialize Firebase: {str(e)}")
    db_ref = None

# CO danger threshold (in ppm)
CO_DANGER_THRESHOLD = 400

@app.route('/')
def home():
    return "Flask app is running!"

@app.route('/process_command', methods=['POST'])
def process_command():
    print("Received request at /process_command")
    print("Request headers:", request.headers)
    try:
        data = request.get_json()
        if data is None:
            print("Invalid JSON payload received.")
            return jsonify({'fulfillmentText': "Erreur: Payload JSON invalide."}), 400
        print("Request body:", data)
    except Exception as e:
        print(f"Failed to parse JSON: {str(e)}")
        return jsonify({'fulfillmentText': f"Erreur: Impossible de parser le JSON: {str(e)}"}), 400

    # Check if queryResult and intent are present
    if 'queryResult' not in data or 'intent' not in data['queryResult']:
        print("Missing queryResult or intent in request body.")
        return jsonify({'fulfillmentText': "Erreur: Requête mal formée, queryResult ou intent manquant."}), 400

    intent = data['queryResult']['intent']['displayName']
    print(f"Processing intent: {intent}")

    # Handle Default Welcome Intent
    if intent == 'Default_Welcome_Intent':
        response = "Bonjour ! Je suis ici pour vous aider à surveiller les niveaux de CO. Posez-moi une question comme 'Quel est le niveau de CO ?' ou 'Est-ce dangereux ?'."
        print(f"Returning response: {response}")
        return jsonify({
            'fulfillmentText': response
        }), 200

    # For other intents, proceed with Firebase data fetching
    if db_ref is None:
        print("Realtime Database not initialized.")
        return jsonify({'fulfillmentText': "Erreur: Base de données non initialisée."}), 500

    try:
        # Fetch all sensor data entries
        sensor_data_entries = db_ref.get()
        if not sensor_data_entries:
            print("No data found at 'sensor_data' path.")
            return jsonify({
                'fulfillmentText': "Désolé, je n'ai pas pu récupérer les données des capteurs."
            }), 200

        print(f"Retrieved sensor data: {sensor_data_entries}")

        # Convert to a list of entries with timestamps
        entries = []
        for key, value in sensor_data_entries.items():
            if not isinstance(value, dict):
                print(f"Skipping entry {key}: value is not a dictionary")
                continue
            if 'mq5' in value and 'mq7' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            else:
                print(f"Skipping entry {key}: missing required fields (mq5 or mq7)")

        if not entries:
            print("No valid entries found with required fields.")
            return jsonify({
                'fulfillmentText': "Désolé, je n'ai pas pu récupérer les données des capteurs."
            }), 200

        entries.sort(key=lambda x: x['data']['timestamp'], reverse=True)
        sensor_data = entries[0]['data']
        print(f"Latest sensor data: {sensor_data}")
    except Exception as e:
        print(f"Failed to fetch data from Realtime Database: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'fulfillmentText': f"Erreur: Impossible de récupérer les données: {str(e)}"}), 500

    co_level = sensor_data.get('mq7', 0)
    print(f"CO level (mq7): {co_level}")

    if intent == 'get_co_level':
        response = f"Le niveau de CO actuel est de {co_level} ppm."
    elif intent == 'check_danger':
        if co_level > CO_DANGER_THRESHOLD:
            response = f"Alerte ! Le niveau de CO est de {co_level} ppm, ce qui est dangereux."
        else:
            response = f"Le niveau de CO est de {co_level} ppm, aucun danger détecté."
    else:
        response = "Désolé, je n'ai pas compris votre demande."

    print(f"Returning response: {response}")
    return jsonify({
        'fulfillmentText': response
    }), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)