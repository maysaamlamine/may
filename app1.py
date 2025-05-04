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

    if 'queryResult' not in data or 'intent' not in data['queryResult']:
        print("Missing queryResult or intent in request body.")
        return jsonify({'fulfillmentText': "Erreur: Requête mal formée, queryResult ou intent manquant."}), 400

    intent = data['queryResult']['intent']['displayName']
    print(f"Processing intent: {intent}")

    if intent == 'Default_Welcome_Intent':
        response = "Bonjour ! Je suis ici pour vous aider à surveiller les niveaux de CO, GPL, température et humidité. Posez-moi une question comme 'Quel est le niveau de CO ?', 'Quel est le niveau de gaz GPL ?' ou 'Est-ce dangereux ?'."
        print(f"Returning response: {response}")
        return jsonify({'fulfillmentText': response}), 200

    if db_ref is None:
        print("Realtime Database not initialized.")
        return jsonify({'fulfillmentText': "Erreur: Base de données non initialisée."}), 500

    try:
        sensor_data_entries = db_ref.get()
        if not sensor_data_entries:
            print("No data found at 'sensor_data' path.")
            return jsonify({'fulfillmentText': "Désolé, je n'ai pas pu récupérer les données des capteurs."}), 200

        print(f"Full sensor data entries: {sensor_data_entries}")

        entries = []
        for key, value in sensor_data_entries.items():
            if not isinstance(value, dict):
                print(f"Skipping entry {key}: value is not a dictionary")
                continue

            if intent == 'temp' and 'temperature' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            elif intent == 'hum' and 'humidity' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            elif intent == 'gpl' and 'mq5' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            elif intent in ['get_co_level', 'check_danger'] and 'mq7' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            else:
                print(f"Skipping entry {key}: missing required field for intent {intent}")

        if not entries:
            print("No valid entries found with required fields.")
            return jsonify({'fulfillmentText': "Désolé, je n'ai pas pu récupérer les données des capteurs."}), 200

        entries.sort(key=lambda x: x['data']['timestamp'], reverse=True)
        sensor_data = entries[0]['data']
        print(f"Latest sensor data: {sensor_data}")

        if intent == 'temp' and sensor_data.get('temperature') is None:
            for entry in entries[1:]:
                if entry['data'].get('temperature') is not None:
                    sensor_data = entry['data']
                    break
        elif intent == 'hum' and sensor_data.get('humidity') is None:
            for entry in entries[1:]:
                if entry['data'].get('humidity') is not None:
                    sensor_data = entry['data']
                    break
        elif intent == 'gpl' and sensor_data.get('mq5') is None:
            for entry in entries[1:]:
                if entry['data'].get('mq5') is not None:
                    sensor_data = entry['data']
                    break

    except Exception as e:
        print(f"Failed to fetch data from Realtime Database: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'fulfillmentText': f"Erreur: Impossible de récupérer les données: {str(e)}"}), 500

    co_level = sensor_data.get('mq7', 0)
    temperature = sensor_data.get('temperature')
    humidity = sensor_data.get('humidity')
    gpl_level = sensor_data.get('mq5')

    print(f"CO level (mq7): {co_level}")
    print(f"Temperature: {temperature}")
    print(f"Humidity: {humidity}")
    print(f"GPL level (mq5): {gpl_level}")

    if intent == 'get_co_level':
        response = f"Le niveau de CO actuel est de {co_level} ppm."
    elif intent == 'check_danger':
        if co_level > CO_DANGER_THRESHOLD:
            response = f"Alerte ! Le niveau de CO est de {co_level} ppm, ce qui est dangereux."
        else:
            response = f"Le niveau de CO est de {co_level} ppm, aucun danger détecté."
    elif intent == 'temp':
        if temperature is not None:
            response = f"La température actuelle est de {temperature}°C."
        else:
            response = "Désolé, la température n'est pas disponible pour le moment."
    elif intent == 'hum':
        if humidity is not None:
            response = f"Le taux d'humidité actuel est de {humidity}%."
        else:
            response = "Désolé, l'humidité n'est pas disponible pour le moment."
    elif intent == 'gpl':
        if gpl_level is not None:
            response = f"Le niveau actuel de gaz GPL est de {gpl_level} ppm."
        else:
            response = "Désolé, le niveau de gaz GPL n'est pas disponible pour le moment."
    else:
        response = "Désolé, je n'ai pas compris votre demande."

    print(f"Returning response: {response}")
    return jsonify({'fulfillmentText': response}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
