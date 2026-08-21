from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os

app = Flask(__name__)
CORS(app)
DB_FILE = 'supervisor_data.db'

# --- INTENTO DE CARGAR LA IA (Si falla, el resto de la app funciona) ---
try:
import google.generativeai as genai
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
IA_ACTIVA = True
else:
IA_ACTIVA = False
except Exception as e:
IA_ACTIVA = False

def init_db():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, line TEXT, machine TEXT, issue TEXT, q3 TEXT, q4 TEXT, start TEXT, end TEXT, minutes INTEGER, affects INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS machines (id INTEGER PRIMARY KEY AUTOINCREMENT, line TEXT, area TEXT, name TEXT, lifespan INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS maintenance (id INTEGER PRIMARY KEY AUTOINCREMENT, line TEXT, task TEXT)''')
conn.commit()
conn.close()
init_db()

@app.route('/api/login', methods=['POST'])
def login():
data = request.json
if data.get('user') == 'Palomino' and data.get('pass') == 'Billclave':
return jsonify({"status": "ok"})
return jsonify({"status": "error"}), 401

@app.route('/api/get_reports', methods=['GET'])
def get_reports():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT date, line, machine, issue, q3, q4, start, end, minutes, affects FROM reports ORDER BY date DESC")
rows = c.fetchall()
conn.close()
return jsonify([{"date":r[0], "line":r[1], "machine":r[2], "issue":r[3], "q3":r[4], "q4":r[5], "start":r[6], "end":r[7], "minutes":r[8], "affects":r[9]} for r in rows])

@app.route('/api/add_report', methods=['POST'])
def add_report():
data = request.json
minutes = 0
if data.get('start') and data.get('end'):
try:
s = datetime.datetime.strptime(data['start'], "%H:%M")
e = datetime.datetime.strptime(data['end'], "%H:%M")
minutes = int((e - s).total_seconds() / 60)
except:
minutes = 0
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("INSERT INTO reports (date, line, machine, issue, q3, q4, start, end, minutes, affects) VALUES (?,?,?,?,?,?,?,?,?,?)",
(data['date'], data['line'], data['machine'], data['issue'], data['q3'], data['q4'], data['start'], data['end'], minutes, 1 if data['affects'] else 0))
conn.commit()
conn.close()
return jsonify({"status": "ok"})

@app.route('/api/get_machines', methods=['GET'])
def get_machines():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT line, area, name, lifespan FROM machines")
rows = c.fetchall()
conn.close()
return jsonify([{"line":r[0], "area":r[1], "name":r[2], "lifespan":r[3]} for r in rows])

@app.route('/api/add_machine', methods=['POST'])
def add_machine():
data = request.json
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("INSERT INTO machines (line, area, name, lifespan) VALUES (?,?,?,?)", (data['line'], data['area'], data['name'], data['lifespan']))
conn.commit()
conn.close()
return jsonify({"status": "ok"})

@app.route('/api/get_maintenance', methods=['GET'])
def get_maintenance():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT line, task FROM maintenance")
rows = c.fetchall()
conn.close()
return jsonify([{"line":r[0], "task":r[1]} for r in rows])

@app.route('/api/add_maintenance', methods=['POST'])
def add_maintenance():
data = request.json
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("INSERT INTO maintenance (line, task) VALUES (?,?)", (data['line'], data['task']))
conn.commit()
conn.close()
return jsonify({"status": "ok"})

# --- FUNCIONES DE IA (Solo si está activa) ---
@app.route('/api/predict', methods=['GET'])
def predict_dashboard():
if not IA_ACTIVA:
return jsonify({"action": "El backend está funcionando, pero la IA de Google no pudo cargarse porque el entorno de Render aún no la soporta. El resto de la app funciona perfectamente."})
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT machine, date FROM reports WHERE affects=1 ORDER BY date DESC LIMIT 5")
rows = c.fetchall()
conn.close()
if not rows: return jsonify({"action": "Aún no hay datos para predecir."})
prompt = f"Basado en este historial de fallas: {rows}, ¿cuál es el componente que probablemente falle pronto y en cuántos días recomiendas hacer un cambio preventivo? Responde en una sola frase corta."
try:
response = model.generate_content(prompt)
return jsonify({"action": response.text})
except: return jsonify({"action": "IA temporalmente desconectada."})

@app.route('/api/analyze_machine', methods=['POST'])
def analyze_machine():
if not IA_ACTIVA:
return jsonify({"analysis": "El sistema de gestión funciona perfectamente. La IA de Google no está activa momentáneamente por la versión de Python. Pero te recomiendo: Revisar el histórico de fallos manualmente para preparar el Shutdown."})
data = request.json
machine_name = data.get('machine')
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT issue, q3, q4, minutes FROM reports WHERE machine=? ORDER BY date DESC LIMIT 5", (machine_name,))
rows = c.fetchall()
conn.close()
if not rows: return jsonify({"analysis": "Sin fallas previas. Inspección visual."})
prompt = f"Últimas 5 fallas de {machine_name}: {rows}. Identifica Causa Raíz y 3 acciones concretas para el próximo Shutdown."
try:
response = model.generate_content(prompt)
return jsonify({"analysis": response.text})
except: return jsonify({"analysis": "IA temporalmente inactiva."})

@app.route('/api/get_shutdown_recs', methods=['GET'])
def get_shutdown_recs():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT machine, issue, q4 FROM reports WHERE affects=1 ORDER BY date DESC LIMIT 10")
rows = c.fetchall()
conn.close()
return jsonify([{"machine": r[0], "issue": r[1], "q4": r[2]} for r in rows])

if __name__ == '__main__':
app.run(host='0.0.0.0', port=10000)
