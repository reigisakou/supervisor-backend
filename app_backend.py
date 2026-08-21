from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os
import google.generativeai as genai

app = Flask(__name__)
CORS(app)
DB_FILE = 'supervisor_data.db'

# Configurar IA de Google (Gemini es GRATIS con limitaciones diarias generosas)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

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

# ==================== IA CON GEMINI (GRATIS) ====================
@app.route('/api/predict', methods=['GET'])
def predict_dashboard():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT machine, date FROM reports WHERE affects=1 ORDER BY date DESC LIMIT 5")
rows = c.fetchall()
conn.close()

if not rows or not GEMINI_API_KEY:
return jsonify({"action": "Aún no hay suficientes datos para predecir, o no se configuró la IA."})

prompt = f"Basado en este historial de fallas de máquinas: {rows}, ¿cuál es el componente que probablemente falle pronto y en cuántos días recomiendas hacer un cambio preventivo? Responde en una sola frase corta."
try:
response = model.generate_content(prompt)
return jsonify({"action": response.text})
except Exception as e:
return jsonify({"action": "IA temporalmente no disponible, revisa la conexión."})

@app.route('/api/analyze_machine', methods=['POST'])
def analyze_machine():
data = request.json
machine_name = data.get('machine')
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT issue, q3, q4, minutes FROM reports WHERE machine=? ORDER BY date DESC LIMIT 5", (machine_name,))
rows = c.fetchall()
conn.close()

if not rows or not GEMINI_API_KEY:
return jsonify({"analysis": "No hay fallas previas para esta máquina. Se recomienda inspección visual básica en el próximo paro de fin de semana."})

prompt = f"Soy un supervisor de planta. Estas son las últimas 5 fallas de la máquina '{machine_name}', sus contramedidas Q3 y Q4, y el tiempo de paro en minutos {rows}. Por favor, actúa como un ingeniero de mantenimiento y haz lo siguiente en tu respuesta: 1. Identifica la Causa Raíz más probable de estos fallos. 2. Dame 3 acciones concretas que debo hacer en el próximo Shutdown de fin de semana para que esto no vuelva a pasar."
try:
response = model.generate_content(prompt)
return jsonify({"analysis": response.text})
except Exception as e:
return jsonify({"analysis": "Error al comunicarse con la IA gratuita de Gemini."})

@app.route('/api/get_shutdown_recs', methods=['GET'])
def get_shutdown_recs():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT machine, issue, q4 FROM reports WHERE affects=1 ORDER BY date DESC LIMIT 10")
rows = c.fetchall()
conn.close()

recs = []
if rows and GEMINI_API_KEY:
for r in rows:
recs.append({"machine": r[0], "issue": r[1], "q4": r[2]})
return jsonify(recs)

if __name__ == '__main__':
app.run(host='0.0.0.0', port=10000) # Puerto común para Render
