from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

@app.route('/')
def index():
    return "Device Identity Service is running. And Backoffice URL is " + os.getenv("BACKOFFICE_URL")

@app.route('/device-identity/sync', methods=['POST'])
def sync_device_identity():
    try:
        req_data = request.get_json()
        locker_id = req_data.get('locker_id')
        pair_code = req_data.get('pair_code')

        if not locker_id or not pair_code:
            return jsonify({"status": "error", "message": "Missing locker_id or pair_code"}), 400
        
        headers = {"Authorization": f"Bearer {pair_code}"}
        response = requests.post(os.getenv("BACKOFFICE_URL") + "/api/device-identity/sync", json={"locker_id": locker_id}, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return jsonify({"status": "success", "data": data}), 200
        else:
            return jsonify({"status": "error", "message": response.text}), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)