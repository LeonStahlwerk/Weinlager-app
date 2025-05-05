
from flask import Flask, request, render_template_string
import csv
from datetime import datetime

app = Flask(__name__)

WEINE = {
    '4712345678901': {'name': 'Riesling 2022', 'kontingente': {'Privat': 120, 'Gastro': 80}},
    '9876543210987': {'name': 'Spätburgunder 2021', 'kontingente': {'Privat': 100, 'Gastro': 60}},
}

LOG_DATEI = 'ausgaben.csv'

FORMULAR_TEMPLATE = """<!doctype html>
<title>Wein-Ausgabe</title>
<h2>{{ wein['name'] }}</h2>
<form method="post">
  <label>Menge:</label><br>
  <input type="number" name="menge" required><br><br>
  <label>Ausgabekategorie:</label><br>
  <select name="kategorie">
    <option value="Kunde">Kunde</option>
    <option value="Ausschank">Ausschank</option>
  </select><br><br>
  <label>Kontingent:</label><br>
  <select name="kontingent">
    {% for k in wein['kontingente'].keys() %}
      <option value="{{ k }}">{{ k }} (verfügbar: {{ wein['kontingente'][k] }})</option>
    {% endfor %}
  </select><br><br>
  <input type="submit" value="Speichern">
</form>"""

@app.route('/')
def home():
    return '<h2>Bitte Barcode in URL scannen, z. B. /scan/4712345678901</h2>'

@app.route('/scan/<barcode>', methods=['GET', 'POST'])
def scan(barcode):
    if barcode not in WEINE:
        return 'Wein nicht gefunden', 404

    wein = WEINE[barcode]

    if request.method == 'POST':
        menge = int(request.form['menge'])
        kategorie = request.form['kategorie']
        kontingent = request.form['kontingent']

        if wein['kontingente'][kontingent] >= menge:
            wein['kontingente'][kontingent] -= menge
            with open(LOG_DATEI, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now(), barcode, wein['name'], menge, kontingent, kategorie])
            return '<h3>Buchung gespeichert!</h3><a href="/">Zurück</a>'
        else:
            return '<h3>Fehler: Nicht genug Bestand im Kontingent!</h3><a href="/">Zurück</a>'

    return render_template_string(FORMULAR_TEMPLATE, wein=wein)

# Wichtig: app muss auf oberster Ebene definiert sein!
