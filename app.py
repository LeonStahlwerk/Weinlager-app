from flask import Flask, request, render_template_string, redirect, send_file
import csv
import os
import threading
import time
import base64
import requests
from datetime import datetime

app = Flask(__name__)

# Sicherstellen, dass CSV-Dateien vorhanden sind
for file, header in [
    ("weine.csv", ["barcode", "name", "jahrgang", "weingut", "kontingent", "menge"]),
    ("ausgaben.csv", ["datum", "barcode", "wein", "menge", "kontingent", "kategorie", "weingut"])
]:
    if not os.path.exists(file):
        with open(file, "w", newline="") as f:
            csv.writer(f).writerow(header)

GITHUB_TOKEN = "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"
REPO_OWNER = "LeonStahlwerk"
REPO_NAME = "Weinlager-app"
FILES = ["weine.csv", "ausgaben.csv"]

KATEGORIEN = ["Winzer", "Verkauf"]
KONTINGENTE = ["Freie Ware", "Kommissionsware"]

def github_commit(file_path, commit_message):
    token = GITHUB_TOKEN
    file_name = os.path.basename(file_path)
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    r = requests.get(api_url, headers=headers)
    sha = r.json().get('sha', None)
    with open(file_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")
    data = {
        "message": commit_message,
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        data["sha"] = sha
    requests.put(api_url, json=data, headers=headers)

def autosave():
    while True:
        for file in FILES:
            if os.path.exists(file):
                github_commit(file, "Autosave")
        time.sleep(300)

@app.route("/")
def home():
    return redirect("/scanform")

@app.route("/scanform", methods=["GET", "POST"])
def scanform():
    if request.method == "POST":
        barcode = request.form.get("barcode")
        return redirect(f"/scan/{barcode}")
    return render_template_string("""
        <h2>Barcode scannen oder eingeben</h2>
        <form method="post">
            <input name="barcode" placeholder="Barcode" autofocus>
            <button type="submit">Weiter</button>
        </form>
    """)

@app.route("/scan/<barcode>", methods=["GET", "POST"])
def scan(barcode):
    weine = {}
    with open("weine.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["barcode"] not in weine:
                weine[row["barcode"]] = {
                    "name": row["name"],
                    "jahrgang": row["jahrgang"],
                    "weingut": row["weingut"],
                    "kontingente": {}
                }
            weine[row["barcode"]]["kontingente"][row["kontingent"]] = int(row["menge"])

    if barcode not in weine:
        return f"<h3>Wein {barcode} nicht gefunden.</h3><a href='/'>Zurück</a>"

    wein = weine[barcode]
    if request.method == "POST":
        menge = int(request.form["menge"])
        kontingent = request.form["kontingent"]
        kategorie = request.form["kategorie"]
        bestand = wein["kontingente"][kontingent]

        if bestand < menge:
            return f"<h3>Nur noch {bestand} Flaschen verfügbar!</h3><a href='/'>Zurück</a>"

        wein["kontingente"][kontingent] -= menge

        # Update CSV
        rows = []
        with open("weine.csv", newline="") as f:
            for row in csv.DictReader(f):
                if row["barcode"] == barcode and row["kontingent"] == kontingent:
                    row["menge"] = str(wein["kontingente"][kontingent])
                rows.append(row)
        with open("weine.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["barcode", "name", "jahrgang", "weingut", "kontingent", "menge"])
            writer.writeheader()
            writer.writerows(rows)

        with open("ausgaben.csv", "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now(), barcode, wein["name"], menge,
                kontingent, kategorie, wein["weingut"]
            ])

        return f"<h3>{menge}x {wein['name']} gebucht.</h3><a href='/'>Zurück</a>"

    return render_template_string("""
        <h2>{{ wein['name'] }} ({{ wein['jahrgang'] }})</h2>
        <form method="post">
            Menge: <input name="menge" type="number"><br>
            Kategorie:
            <select name="kategorie">
                {% for k in kategorien %}<option>{{k}}</option>{% endfor %}
            </select><br>
            Kontingent:
            <select name="kontingent">
                {% for k, v in wein['kontingente'].items() %}
                <option value="{{k}}">{{k}} ({{v}} Flaschen)</option>
                {% endfor %}
            </select><br><br>
            <button type="submit">Buchen</button>
        </form>
    """, wein=wein, kategorien=KATEGORIEN)

@app.route("/download/vorlage.csv")
def download_vorlage():
    # Daten aus den CSV-Dateien lesen
    bestand = []
    ausgaben = []

    # "weine.csv" laden
    with open("weine.csv", newline="") as f:
        bestand = list(csv.DictReader(f))

    # "ausgaben.csv" laden
    with open("ausgaben.csv", newline="") as f:
        ausgaben = list(csv.DictReader(f))

    # Datenstruktur für die Berechnung vorbereiten
    weine = {}
    for row in bestand:
        barcode = row["barcode"]
        if barcode not in weine:
            weine[barcode] = {
                "name": row["name"],
                "jahrgang": row["jahrgang"],
                "weingut": row["weingut"],
                "gesamt": 0,
                "freie_ware": 0,
                "kommissionsware": 0,
                "verkauf": 0,
                "winzer": 0,
                "übrig": 0
            }
        menge = int(row["menge"])
        weine[barcode]["gesamt"] += menge
        if row["kontingent"] == "Freie Ware":
            weine[barcode]["freie_ware"] += menge
        elif row["kontingent"] == "Kommissionsware":
            weine[barcode]["kommissionsware"] += menge

    # Verkäufe und Winzerverbrauch hinzufügen
    for row in ausgaben:
        barcode = row["barcode"]
        menge = int(row["menge"])
        kategorie = row["kategorie"]
        if barcode in weine:
            if kategorie == "Verkauf":
                weine[barcode]["verkauf"] += menge
            elif kategorie == "Winzer":
                weine[barcode]["winzer"] += menge

    # Übrige Flaschen berechnen
    for barcode, daten in weine.items():
        daten["übrig"] = daten["gesamt"]

    # CSV-Datei erstellen
    out_file = "vorlage_export.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        # Kopfzeile schreiben
        writer.writerow([
            "Wein Name:", "Jahrgang:", "Weingut:", "Gesamtanzal gelieferte Flaschen:",
            'Gelieferte Flaschen "Freie Ware"', 'Gelieferte Flaschen "Kommisionsware"',
            "Verkaufte Flaschen", "Von Winzern verbrauchte Flaschen", "Übrige Flaschen"
        ])
        # Daten schreiben
        for daten in weine.values():
            writer.writerow([
                daten["name"], daten["jahrgang"], daten["weingut"], daten["gesamt"],
                daten["freie_ware"], daten["kommissionsware"], daten["verkauf"],
                daten["winzer"], daten["übrig"]
            ])

    # Datei zum Download bereitstellen
    return send_file(out_file, as_attachment=True)

if __name__ == "__main__":
    threading.Thread(target=autosave, daemon=True).start()
    app.run(debug=True)
