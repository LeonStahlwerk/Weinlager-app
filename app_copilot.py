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

# App logic from app.py starts here
GITHUB_TOKEN = "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"
REPO_OWNER = "LeonStahlwerk"
REPO_NAME = "Weinlager-app"
FILES = ["weine.csv", "ausgaben.csv"]

KATEGORIEN = ["Winzer", "Verkauf"]

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

# Rest of the admin and additional logic follows
# (e.g., admin, statistics, wine details, etc.)

if __name__ == "__main__":
    threading.Thread(target=autosave, daemon=True).start()
    app.run(debug=True)
