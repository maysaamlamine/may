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
        raise ValueError("Aucun identifiant Firebase trouvé.")

    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://projet-fin-d-etude-4632f-default-rtdb.firebaseio.com/'
    })
    db_ref = db.reference('sensor_data')
    print("Connexion à Firebase réussie.")

except Exception as e:
    print(f"ERREUR Firebase : {str(e)}")
    print(traceback.format_exc())

CO_DANGER_THRESHOLD = 400  # Seuil CO en ppm

@app.route('/')
def home():
    return jsonify({"status": "API opérationnelle"})

@app.route('/process_command', methods=['POST'])
def process_command():
    try:
        data = request.get_json()
        if not data or 'queryResult' not in data:
            return jsonify({"error": "Requête invalide"}), 400
    except Exception as e:
        return jsonify({"error": f"Erreur JSON : {str(e)}"}), 400

    intent = data['queryResult']['intent'].get('displayName', '')
    print(f"Intent détecté : {intent}")

    if db_ref is None:
        return jsonify({"fulfillmentText": "Erreur : Base de données indisponible."}), 500

    try:
        # Récupération et tri des données
        sensor_data = db_ref.get()
        latest_entry = sorted(
            [v for v in sensor_data.values() if isinstance(v, dict)],
            key=lambda x: x.get('timestamp', '1970-01-01'),
            reverse=True
        )[0] if sensor_data else None

        if not latest_entry:
            return jsonify({"fulfillmentText": "Aucune donnée disponible."})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"fulfillmentText": f"Erreur de données : {str(e)}"}), 500

    # Récupération des valeurs avec fallback
    co_level = latest_entry.get('mq7', 0)
    temperature = latest_entry.get('temperature') or latest_entry.get('temp')
    humidity = latest_entry.get('humidity') or latest_entry.get('hum')

    # Gestion des réponses
    if intent == 'Get CO Level':
        response = f"Niveau de CO : {co_level} ppm."
    
    elif intent == 'Check Danger':
        if co_level > CO_DANGER_THRESHOLD:
            response = f"DANGER ! Niveau de CO à {co_level} ppm !"  # Sans emoji
        else:
            response = f"Niveau de CO normal : {co_level} ppm."
    
    elif intent == 'temp':
        response = f"Température : {temperature} °C" if temperature else "Donnée indisponible"
    
    elif intent == 'hum':
        response = f"Humidité : {humidity} %" if humidity else "Donnée indisponible"
    
    elif intent == 'Default Welcome Intent':
        response = "Bonjour ! Je peux vous fournir les données de CO, température ou humidité."
    
    else:
        response = "Requête non reconnue. Essayez avec 'CO', 'température' ou 'humidité'."

    return jsonify({"fulfillmentText": response})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
