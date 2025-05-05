
from flask import Flask, request, render_template_string, redirect
import csv
import os
from datetime import datetime

app = Flask(__name__)

WEINE_DATEI = 'weine.csv'
LOG_DATEI = 'ausgaben.csv'
KATEGORIEN_DATEI = 'kategorien.csv'

def lade_weine():
    weine = {}
    if os.path.exists(WEINE_DATEI):
        with open(WEINE_DATEI, newline='') as f:
            for zeile in csv.DictReader(f):
                barcode = zeile['barcode']
                if barcode not in weine:
                    weine[barcode] = {
                        'name': zeile['name'],
                        'jahrgang': zeile['jahrgang'],
                        'kontingente': {}
                    }
                weine[barcode]['kontingente'][zeile['kontingent']] = int(zeile['menge'])
    return weine

def lade_kategorien():
    if not os.path.exists(KATEGORIEN_DATEI):
        return []
    with open(KATEGORIEN_DATEI, newline='') as f:
        return [zeile.strip() for zeile in f if zeile.strip()]

@app.route('/')
def home():
    return redirect('/scanform')

@app.route('/scanform', methods=['GET', 'POST'])
def scanform():
    if request.method == 'POST':
        barcode = request.form.get('barcode')
        return redirect(f'/scan/{barcode}')
    return render_template_string("""
        <h2>Scanne oder gib den Barcode ein</h2>
        <form method="post">
            <input type="text" name="barcode" autofocus placeholder="Barcode eingeben">
            <input type="submit" value="Weiter">
        </form>
    """)

@app.route('/scan/<barcode>', methods=['GET', 'POST'])
def scan(barcode):
    weine = lade_weine()
    kategorien = lade_kategorien()
    if barcode not in weine:
        return 'Wein nicht gefunden', 404
    wein = weine[barcode]
    if request.method == 'POST':
        menge = int(request.form['menge'])
        kategorie = request.form['kategorie']
        kontingent = request.form['kontingent']
        bestand = wein['kontingente'][kontingent]
        if bestand >= menge:
            wein['kontingente'][kontingent] -= menge
            rows = []
            with open(WEINE_DATEI, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['barcode'] == barcode and row['kontingent'] == kontingent:
                        row['menge'] = str(wein['kontingente'][kontingent])
                    rows.append(row)
            with open(WEINE_DATEI, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['barcode', 'name', 'jahrgang', 'kontingent', 'menge'])
                writer.writeheader()
                writer.writerows(rows)
            with open(LOG_DATEI, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now(), barcode, wein['name'], menge, kontingent, kategorie])
            return f'<h3>{menge} Flasche(n) gespeichert! Rest: {wein["kontingente"][kontingent]}</h3><a href="/">Zurück</a>'
        else:
            return '<h3>Fehler: Nicht genug Bestand im Kontingent!</h3><a href="/">Zurück</a>'
    return render_template_string("""
        <h2>{{ wein['name'] }} ({{ wein['jahrgang'] }})</h2>
        <form method="post">
            <label>Menge:</label><br><input type="number" name="menge"><br><br>
            <label>Kategorie:</label><br>
            <select name="kategorie">
                {% for kat in kategorien %}
                    <option value="{{ kat }}">{{ kat }}</option>
                {% endfor %}
            </select><br><br>
            <label>Kontingent:</label><br>
            <select name="kontingent">
                {% for k in wein['kontingente'] %}
                    <option value="{{ k }}">{{ k }} (verfügbar: {{ wein['kontingente'][k] }})</option>
                {% endfor %}
            </select><br><br>
            <input type="submit" value="Buchen">
        </form>
    """, wein=wein, kategorien=kategorien)
