from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db
import traceback
import os
import json

app = Flask(__name__)
CORS(app)

# Initialisation de la base de données Firebase
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

CO_DANGER_THRESHOLD = 400

@app.route('/')
def home():
    return "Flask app is running!"

@app.route('/process_command', methods=['POST'])
def process_command():
    print("Requête reçue sur /process_command")

    try:
        data = request.get_json()
        if data is None:
            return jsonify({'fulfillmentText': "Erreur: Payload JSON invalide."}), 400
    except Exception as e:
        return jsonify({'fulfillmentText': f"Erreur: Impossible de parser le JSON: {str(e)}"}), 400

    if 'queryResult' not in data or 'intent' not in data['queryResult']:
        return jsonify({'fulfillmentText': "Erreur: Requête mal formée, queryResult ou intent manquant."}), 400

    intent = data['queryResult']['intent']['displayName']
    print(f"Intent détectée : {intent}")

    if intent == 'Default_Welcome_Intent':
        response = "Bonjour ! Je suis ici pour vous aider à surveiller les niveaux de CO, GPL, température et humidité. Posez-moi une question comme 'Quel est le niveau de CO ?' ou 'Quel est le niveau de GPL ?'."
        return jsonify({'fulfillmentText': response}), 200

    if db_ref is None:
        return jsonify({'fulfillmentText': "Erreur: Base de données non initialisée."}), 500

    try:
        sensor_data_entries = db_ref.get()
        if not sensor_data_entries:
            return jsonify({'fulfillmentText': "Désolé, je n'ai pas pu récupérer les données des capteurs."}), 200

        entries = []
        for key, value in sensor_data_entries.items():
            if not isinstance(value, dict):
                continue

            if intent == 'temp' and 'temperature' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            elif intent == 'hum' and 'humidity' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            elif intent in ['get_co_level', 'check_danger'] and 'mq7' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})
            elif intent == 'gpl' and 'mq5' in value:
                value['timestamp'] = value.get('timestamp', '1970-01-01T00:00:00Z')
                entries.append({'key': key, 'data': value})

        if not entries:
            return jsonify({'fulfillmentText': "Désolé, je n'ai pas pu récupérer les données des capteurs."}), 200

        # Trier les entrées par date
        entries.sort(key=lambda x: x['data']['timestamp'], reverse=True)
        sensor_data = entries[0]['data']

        # Recherche alternative si valeur manquante
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
        print(traceback.format_exc())
        return jsonify({'fulfillmentText': f"Erreur: Impossible de récupérer les données: {str(e)}"}), 500

    # Extraction des données
    co_level = sensor_data.get('mq7')
    gpl_level = sensor_data.get('mq5')
    temperature = sensor_data.get('temperature')
    humidity = sensor_data.get('humidity')

    # Génération de la réponse
    if intent == 'get_co_level':
        response = f"Le niveau de CO actuel est de {co_level} ppm." if co_level is not None else "Désolé, la valeur de CO n'est pas disponible."
    elif intent == 'check_danger':
        if co_level is not None and co_level > CO_DANGER_THRESHOLD:
            response = f"Alerte ! Le niveau de CO est de {co_level} ppm, ce qui est dangereux."
        elif co_level is not None:
            response = f"Le niveau de CO est de {co_level} ppm, aucun danger détecté."
        else:
            response = "Désolé, la valeur de CO n'est pas disponible pour l'évaluation du danger."
    elif intent == 'temp':
        response = f"La température actuelle est de {temperature}°C." if temperature is not None else "Désolé, la température n'est pas disponible pour le moment."
    elif intent == 'hum':
        response = f"Le taux d'humidité actuel est de {humidity}%." if humidity is not None else "Désolé, l'humidité n'est pas disponible pour le moment."
    elif intent == 'gpl':
        response = f"Le niveau de gaz de pétrole liquéfié (GPL) est de {gpl_level} ppm." if gpl_level is not None else "Désolé, le niveau de GPL n'est pas disponible."
    else:
        response = "Désolé, je n'ai pas compris votre demande."

    return jsonify({'fulfillmentText': response}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)


