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
    return redirect("/admin?pw=1234&tab=verwaltung")

# --- ADMIN TABS ---

TAB_HTML = """<div style='margin-bottom:1em'>
  <a href='/admin?pw=1234&tab=verwaltung'>Verwaltung</a> |
  <a href='/admin?pw=1234&tab=statistik'>Statistik</a> |
  <a href='/admin?pw=1234&tab=weingueter'>Weingüter</a>
</div><hr>"""

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.args.get("pw") != "1234":
        return "Zugriff verweigert"

    tab = request.args.get("tab", "verwaltung")
    msg = ""

    if tab == "verwaltung":
        if request.method == "POST":
            if "edit" in request.form:
                barcode = request.form["barcode"]
                return redirect(f"/edit/{barcode}")

            elif "add_kontingent" in request.form:
                barcode = request.form["barcode"]
                kontingent = request.form["new_kontingent"]
                menge = int(request.form["new_menge"])

                rows = []
                with open("weine.csv", newline="") as f:
                    for row in csv.DictReader(f):
                        rows.append(row)
                rows.append({
                    "barcode": barcode,
                    "name": "",
                    "jahrgang": "",
                    "weingut": "",
                    "kontingent": kontingent,
                    "menge": menge
                })
                with open("weine.csv", "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["barcode", "name", "jahrgang", "weingut", "kontingent", "menge"])
                    writer.writeheader()
                    writer.writerows(rows)
                msg = f"Kontingent {kontingent} mit {menge} Flaschen hinzugefügt."

        weine = {}
        with open("weine.csv", newline="") as f:
            for row in csv.DictReader(f):
                code = row["barcode"]
                if code not in weine:
                    weine[code] = {
                        "name": row["name"],
                        "jahrgang": row["jahrgang"],
                        "weingut": row["weingut"],
                        "kontingente": {}
                    }
                weine[code]["kontingente"][row["kontingent"]] = row["menge"]

        return render_template_string("""<h2>Verwaltung</h2>{{ tabs|safe }}<p>{{ msg }}</p>
            <h3>Weine</h3>
            <ul>
            {% for code, w in weine.items() %}
              <li><b>{{ w['name'] }}</b> – {{ w['weingut'] }} ({{ w['jahrgang'] }})
                <ul>
                  {% for k, m in w['kontingente'].items() %}
                    <li>{{ k }}: {{ m }} Flaschen</li>
                  {% endfor %}
                </ul>
                <form method="post" style="display:inline">
                  <input type="hidden" name="barcode" value="{{ code }}">
                  <select name="new_kontingent">
                    {% for k in kontingente %}<option>{{k}}</option>{% endfor %}
                  </select>
                  <input type="number" name="new_menge" placeholder="Menge">
                  <button type="submit" name="add_kontingent">Kontingent hinzufügen</button>
                </form>
                <form method="post" style="display:inline">
                  <input type="hidden" name="barcode" value="{{ code }}">
                  <button type="submit" name="edit">Bearbeiten</button>
                </form>
              </li>
            {% endfor %}
            </ul>
        """, msg=msg, weine=weine, tabs=TAB_HTML, kontingente=KONTINGENTE)

    elif tab == "statistik":
        ausgaben = []
        with open("ausgaben.csv", newline="") as f:
            ausgaben = list(csv.DictReader(f))

        statistik = {}
        for row in ausgaben:
            b = row["barcode"]
            if b not in statistik:
                statistik[b] = {"gesamt": 0, "kategorien": {}, "kontingente": {}}
            menge = int(row["menge"])
            statistik[b]["gesamt"] += menge
            statistik[b]["kategorien"][row["kategorie"]] = statistik[b]["kategorien"].get(row["kategorie"], 0) + menge
            statistik[b]["kontingente"][row["kontingent"]] = statistik[b]["kontingente"].get(row["kontingent"], 0) + menge

        return render_template_string("""<h2>Statistik</h2>{{ tabs|safe }}
            <ul>
            {% for b, s in statistik.items() %}
              <li><b>{{ b }}</b>: Gesamt: {{ s['gesamt'] }}</li>
            {% endfor %}
            </ul>
        """, tabs=TAB_HTML, statistik=statistik)

    elif tab == "weingueter":
        ausgaben = []
        with open("ausgaben.csv", newline="") as f:
            ausgaben = list(csv.DictReader(f))

        weingueter = {}
        for row in ausgaben:
            w = row["weingut"]
            menge = int(row["menge"])
            kategorie = row["kategorie"]
            if w not in weingueter:
                weingueter[w] = {"gesamt": 0, "winzer": 0, "verkauf": 0}
            weingueter[w]["gesamt"] += menge
            if kategorie == "Winzer":
                weingueter[w]["winzer"] += menge
            elif kategorie == "Verkauf":
                weingueter[w]["verkauf"] += menge

        return render_template_string("""<h2>Weingüter</h2>{{ tabs|safe }}
            <ul>
            {% for w, d in weingueter.items() %}
              <li>{{ w }}: Gesamt {{ d['gesamt'] }} – Winzer {{ d['winzer'] }} – Verkauf {{ d['verkauf'] }}</li>
            {% endfor %}
            </ul>
        """, tabs=TAB_HTML, weingueter=weingueter)

    return redirect("/admin?pw=1234&tab=verwaltung")

@app.route("/edit/<barcode>", methods=["GET", "POST"])
def edit(barcode):
    weine = []
    with open("weine.csv", newline="") as f:
        weine = list(csv.DictReader(f))

    wein = next((w for w in weine if w["barcode"] == barcode), None)
    if not wein:
        return "Wein nicht gefunden."

    if request.method == "POST":
        wein["name"] = request.form["name"]
        wein["jahrgang"] = request.form["jahrgang"]
        wein["weingut"] = request.form["weingut"]
        wein["kontingent"] = request.form["kontingent"]
        wein["menge"] = request.form["menge"]

        with open("weine.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["barcode", "name", "jahrgang", "weingut", "kontingent", "menge"])
            writer.writeheader()
            writer.writerows(weine)
        return redirect("/admin?pw=1234&tab=verwaltung")

    return render_template_string("""<h2>Wein bearbeiten</h2>
        <form method="post">
            Name: <input name="name" value="{{ wein['name'] }}"><br>
            Jahrgang: <input name="jahrgang" value="{{ wein['jahrgang'] }}"><br>
            Weingut: <input name="weingut" value="{{ wein['weingut'] }}"><br>
            Kontingent: <input name="kontingent" value="{{ wein['kontingent'] }}"><br>
            Menge: <input name="menge" value="{{ wein['menge'] }}"><br>
            <button type="submit">Speichern</button>
        </form>
    """, wein=wein)

if __name__ == "__main__":
    app.run(debug=True)
