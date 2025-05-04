from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db
import traceback
import os
import json

app = Flask(__name__)
CORS(app)

# Référence globale à Firebase
db_ref = None

# Chargement des identifiants Firebase
try:
    firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")

    if firebase_credentials:
        cred_dict = json.loads(firebase_credentials)
        print("Identifiants Firebase chargés depuis la variable d'environnement.")
    elif os.path.exists("firebase_config.json"):
        with open("firebase_config.json") as f:
            cred_dict = json.load(f)
        print("Identifiants Firebase chargés depuis firebase_config.json.")
    else:
        raise ValueError("Aucun identifiant Firebase trouvé (ni variable d'environnement, ni fichier json).")

    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://projet-fin-d-etude-4632f-default-rtdb.firebaseio.com/'
    })
    db_ref = db.reference('sensor_data')
    print("Connexion à Firebase réussie.")

except Exception as e:
    print(f"Erreur d'initialisation Firebase : {str(e)}")
    print(traceback.format_exc())

CO_DANGER_THRESHOLD = 400  # Seuil de danger du CO en ppm

@app.route('/')
def home():
    return jsonify({"status": "API Flask en fonctionnement."})

@app.route('/process_command', methods=['POST'])
def process_command():
    try:
        data = request.get_json()
        if not data or 'queryResult' not in data or 'intent' not in data['queryResult']:
            return jsonify({"error": "Requête mal formée (JSON invalide ou intent manquant)."}), 400
    except Exception as e:
        return jsonify({"error": f"Erreur de parsing JSON : {str(e)}"}), 400

    intent = data['queryResult']['intent']['displayName']
    print(f"Intent reçu : {intent}")

    if db_ref is None:
        return jsonify({"fulfillmentText": "Erreur : la connexion Firebase a échoué."}), 500

    try:
        sensor_data_entries = db_ref.get()
        if not sensor_data_entries:
            return jsonify({"fulfillmentText": "Désolé, aucune donnée disponible dans Firebase."})

        entries = []
        for key, value in sensor_data_entries.items():
            if isinstance(value, dict) and all(k in value for k in ['mq7', 'temperature', 'humidity', 'timestamp']):
                entries.append({'key': key, 'data': value})

        if not entries:
            return jsonify({"fulfillmentText": "Désolé, aucune donnée exploitable trouvée dans Firebase."})

        entries.sort(key=lambda x: x['data'].get('timestamp', '1970-01-01T00:00:00Z'), reverse=True)
        latest_data = entries[0]['data']
        print(f"Dernières données : {latest_data}")

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"fulfillmentText": f"Erreur lors de la récupération des données : {str(e)}"}), 500

    co_level = latest_data.get('mq7', 0)
    temperature = latest_data.get('temperature')
    humidity = latest_data.get('humidity')

    if intent == 'Get CO Level':
        response = f"Le niveau de CO actuel est de {co_level} ppm."
    elif intent == 'Check Danger':
        if co_level > CO_DANGER_THRESHOLD:
            response = f"Alerte. Le niveau de CO est de {co_level} ppm, ce qui est dangereux."
        else:
            response = f"Le niveau de CO est de {co_level} ppm, aucun danger détecté."
    elif intent == 'Temp':
        response = f"La température actuelle est de {temperature} °C." if temperature is not None else "Désolé, la température actuelle n'est pas disponible."
    elif intent == 'hum':
        response = f"Le taux d'humidité actuel est de {humidity} %." if humidity is not None else "Désolé, le taux d'humidité actuel n'est pas disponible."
    elif intent == 'Default Welcome Intent':
        response = "Bonjour. Je suis votre assistant environnemental. Que puis-je faire pour vous ?"
    else:
        response = "Désolé, je n'ai pas compris votre demande. Vous pouvez me demander par exemple : Quel est le niveau de CO ?, Est-ce dangereux ?, Quelle est la température ?, ou Quel est le taux d'humidité ?"

    print(f"Réponse envoyée : {response}")
    return jsonify({"fulfillmentText": response})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
