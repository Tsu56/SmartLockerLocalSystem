from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)
DB = "database/device_identity.db"

@app.route('/locations', methods=['GET'])
def get_locations():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM locations")
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

@app.route('/lockers', methods=['GET'])
def get_lockers():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lockers")
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
