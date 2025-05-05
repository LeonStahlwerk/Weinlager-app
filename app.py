
from flask import Flask, request, render_template_string, redirect
import csv
import os
from datetime import datetime

app = Flask(__name__)

WEINE_DATEI = 'weine.csv'
LOG_DATEI = 'ausgaben.csv'
KATEGORIEN_DATEI = 'kategorien.csv'

# Helferfunktionen
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

def speichere_wein(barcode, name, jahrgang, kontingent, menge):
    neu = not os.path.exists(WEINE_DATEI)
    with open(WEINE_DATEI, 'a', newline='') as f:
        writer = csv.writer(f)
        if neu:
            writer.writerow(['barcode', 'name', 'jahrgang', 'kontingent', 'menge'])
        writer.writerow([barcode, name, jahrgang, kontingent, menge])

def lade_kategorien():
    if not os.path.exists(KATEGORIEN_DATEI):
        return []
    with open(KATEGORIEN_DATEI, newline='') as f:
        return [zeile.strip() for zeile in f if zeile.strip()]

def speichere_kategorie(kat):
    with open(KATEGORIEN_DATEI, 'a') as f:
        f.write(kat + '\n')

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

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    pw = request.args.get('pw')
    if pw != '1234':
        return 'Zugriff verweigert', 403
    msg = ''
    if request.method == 'POST':
        if 'barcode' in request.form:
            speichere_wein(request.form['barcode'], request.form['name'],
                           request.form['jahrgang'], request.form['kontingent'],
                           request.form['menge'])
            msg = 'Wein gespeichert.'
        elif 'neue_kategorie' in request.form:
            speichere_kategorie(request.form['neue_kategorie'])
            msg = 'Kategorie gespeichert.'
    weine = lade_weine()
    kategorien = lade_kategorien()
    return render_template_string("""
        <h2>Adminbereich</h2>
        <p>{{ msg }}</p>
        <h3>Neuen Wein anlegen</h3>
        <form method="post">
            Barcode: <input name="barcode"><br>
            Name: <input name="name"><br>
            Jahrgang: <input name="jahrgang"><br>
            Kontingent: <input name="kontingent"><br>
            Menge: <input name="menge"><br>
            <input type="submit" value="Speichern">
        </form>
        <h3>Neue Kategorie anlegen</h3>
        <form method="post">
            <input name="neue_kategorie">
            <input type="submit" value="Hinzufügen">
        </form>
        <h3>Bestehende Weine</h3>
        <ul>
        {% for code, w in weine.items() %}
            <li>{{ w['name'] }} ({{ w['jahrgang'] }}) – Barcode: {{ code }}
                <ul>
                {% for k, m in w['kontingente'].items() %}
                    <li>{{ k }}: {{ m }}</li>
                {% endfor %}
                </ul>
            </li>
        {% endfor %}
        </ul>
        <h3>Kategorien</h3>
        <ul>{% for k in kategorien %}<li>{{ k }}</li>{% endfor %}</ul>
    """, msg=msg, weine=weine, kategorien=kategorien)
