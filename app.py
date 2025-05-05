
from flask import Flask, request, render_template_string, redirect, send_file
import csv
import os
import threading
import time
import base64
import requests
from datetime import datetime

app = Flask(__name__)

# GitHub Setup
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

if not os.path.exists("weine.csv"):
    with open("weine.csv", "w", newline="") as f:
        csv.writer(f).writerow(["barcode", "name", "jahrgang", "weingut", "kontingent", "menge"])

if not os.path.exists("ausgaben.csv"):
    with open("ausgaben.csv", "w", newline="") as f:
        csv.writer(f).writerow(["datum", "barcode", "wein", "menge", "kontingent", "kategorie", "weingut"])

@app.route("/")
def home():
    return redirect("/scanform")

@app.route("/scanform", methods=["GET", "POST"])
def scanform():
    if request.method == "POST":
        return redirect(f"/scan/{request.form.get('barcode')}")
    return render_template_string("""
        <h2>Scanne oder gib den Barcode ein</h2>
        <form method="post">
            <input type="text" name="barcode" autofocus placeholder="Barcode eingeben">
            <input type="submit" value="Weiter">
        </form>
    """)

@app.route("/scan/<barcode>", methods=["GET", "POST"])
def scan(barcode):
    weine = {}
    with open("weine.csv", newline='') as f:
        for row in csv.DictReader(f):
            if row['barcode'] not in weine:
                weine[row['barcode']] = {
                    "name": row['name'],
                    "jahrgang": row['jahrgang'],
                    "weingut": row['weingut'],
                    "kontingente": {}
                }
            weine[row['barcode']]['kontingente'][row['kontingent']] = int(row['menge'])

    if barcode not in weine:
        return f"Wein mit Barcode {barcode} nicht gefunden.<br><a href='/'>Zurück</a>"

    wein = weine[barcode]
    if request.method == "POST":
        menge = int(request.form['menge'])
        kategorie = request.form['kategorie']
        kontingent = request.form['kontingent']
        bestand = wein['kontingente'][kontingent]
        if bestand >= menge:
            wein['kontingente'][kontingent] -= menge
            rows = []
            with open("weine.csv", newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['barcode'] == barcode and row['kontingent'] == kontingent:
                        row['menge'] = str(wein['kontingente'][kontingent])
                    rows.append(row)
            with open("weine.csv", "w", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["barcode", "name", "jahrgang", "weingut", "kontingent", "menge"])
                writer.writeheader()
                writer.writerows(rows)
            with open("ausgaben.csv", "a", newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now(), barcode, wein['name'], menge, kontingent, kategorie, wein['weingut']])
            return f"{menge} Flasche(n) gebucht!<br><a href='/'>Zurück</a>"
        else:
            return f"Nicht genug Bestand (nur {bestand})<br><a href='/'>Zurück</a>"

    return render_template_string("""
        <h2>{{ wein['name'] }} ({{ wein['jahrgang'] }})</h2>
        <form method="post">
            <label>Menge:</label><br><input type="number" name="menge"><br><br>
            <label>Kategorie:</label><br>
            <select name="kategorie">
                {% for kat in kategorien %}<option value="{{ kat }}">{{ kat }}</option>{% endfor %}
            </select><br><br>
            <label>Kontingent:</label><br>
            <select name="kontingent">
                {% for k, v in wein['kontingente'].items() %}<option value="{{ k }}">{{ k }} ({{ v }})</option>{% endfor %}
            </select><br><br>
            <input type="submit" value="Buchen">
        </form>
    """, wein=wein, kategorien=KATEGORIEN)

# Weitere Routen folgen in der nächsten Iteration falls nötig...
