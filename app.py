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
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Weinlager App</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 text-gray-800">
        <nav class="bg-blue-500 p-4 text-white">
            <div class="container mx-auto flex justify-between">
                <div>
                    <a href="/scanform" class="mr-4 hover:underline">Scan</a>
                    <a href="/admin?pw=1234&tab=verwaltung" class="mr-4 hover:underline">Verwaltung</a>
                    <a href="/admin?pw=1234&tab=statistik" class="hover:underline">Statistik</a>
                </div>
            </div>
        </nav>
        <h1 class="text-3xl font-bold text-center mt-10">Willkommen zur Weinlager App</h1>
    </body>
        <h1 class="text-3xl font-bold text-center mt-10">Willkommen zur Weinlager App</h1>
    </body>
    </html>
    """)

@app.route("/scanform", methods=["GET", "POST"])
def scanform():
    if request.method == "POST":
        barcode = request.form.get("barcode")
        return redirect(f"/scan/{barcode}")
    return render_template_string("""
        <h2>Barcode scannen oder eingeben</h2>
        <form method="post" class="space-y-4 bg-white p-6 rounded-lg shadow-md max-w-md mx-auto mt-10">
            <div>
                <label for="barcode" class="block text-gray-700 font-medium">Barcode</label>
                <input name="barcode" id="barcode" type="text" placeholder="Barcode scannen oder eingeben"
                       class="w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500" autofocus>
            </div>
            <button type="submit" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
                Weiter
            </button>
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

if __name__ == "__main__":
    threading.Thread(target=autosave, daemon=True).start()
    app.run(debug=True)

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
            if "add_kontingent" in request.form:
                barcode = request.form["barcode"]
                kontingent = request.form["new_kontingent"]
                menge = int(request.form["new_menge"])

                # Update CSV with new kontingent entry
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

            else:
                with open("weine.csv", "a", newline="") as f:
                    csv.writer(f).writerow([
                        request.form["barcode"],
                        request.form["name"],
                        request.form["jahrgang"],
                        request.form["weingut"],
                        request.form["kontingent"],
                        request.form["menge"]
                    ])
                msg = "Wein gespeichert."

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

            <table class="min-w-full bg-white rounded-lg shadow-md">
                <thead class="bg-gray-200">
                    <tr>
                        <th class="px-6 py-3 text-left text-gray-700 font-medium">Barcode</th>
                        <th class="px-6 py-3 text-left text-gray-700 font-medium">Name</th>
                        <th class="px-6 py-3 text-left text-gray-700 font-medium">Jahrgang</th>
                        <th class="px-6 py-3 text-left text-gray-700 font-medium">Weingut</th>
                        <th class="px-6 py-3 text-left text-gray-700 font-medium">Kontingente</th>
                    </tr>
                </thead>
                <tbody>
                    {% for code, w in weine.items() %}
                    <tr class="border-t">
                        <td class="px-6 py-4">{{ code }}</td>
                        <td class="px-6 py-4">{{ w['name'] }}</td>
                        <td class="px-6 py-4">{{ w['jahrgang'] }}</td>
                        <td class="px-6 py-4">{{ w['weingut'] }}</td>
                        <td class="px-6 py-4">
                            <ul>
                                {% for k, m in w['kontingente'].items() %}
                                <li>{{ k }}: {{ m }} Flaschen</li>
                                {% endfor %}
                            </ul>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <a href='/download/vorlage.csv'>Gesamte Weine als CSV herunterladen</a>
        """, msg=msg, weine=weine, tabs=TAB_HTML, kontingente=KONTINGENTE)

    elif tab == "statistik":
        return render_template_string("<h2>Statistik</h2><p>Statistiken werden hier angezeigt.</p>{{ tabs|safe }}", tabs=TAB_HTML)

    elif tab == "weingueter":
        return render_template_string("<h2>Weingüter</h2><p>Weingüter-Daten werden hier angezeigt.</p>{{ tabs|safe }}", tabs=TAB_HTML)

    return redirect("/admin?pw=1234&tab=verwaltung")

@app.route("/edit/<barcode>", methods=["GET", "POST"])
def edit_wine(barcode):
    # Daten aus der CSV lesen
    weine = []
    with open("weine.csv", newline="") as f:
        weine = list(csv.DictReader(f))
    
    # Wein suchen
    wein = next((row for row in weine if row["barcode"] == barcode), None)
    if not wein:
        return "Wein nicht gefunden."

    if request.method == "POST":
        # Neue Werte aus dem Formular übernehmen
        wein["name"] = request.form["name"]
        wein["jahrgang"] = request.form["jahrgang"]
        wein["weingut"] = request.form["weingut"]
        wein["kontingent"] = request.form["kontingent"]
        wein["menge"] = request.form["menge"]

        # Änderungen in `ausgaben.csv` loggen
        with open("ausgaben.csv", "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now(), barcode, wein["name"], wein["menge"], 
                wein["kontingent"], "Bearbeitung", wein["weingut"]
            ])
        
        # CSV aktualisieren
        with open("weine.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["barcode", "name", "jahrgang", "weingut", "kontingent", "menge"])
            writer.writeheader()
            writer.writerows(weine)

        return redirect("/admin?pw=1234&tab=verwaltung")

      return render_template_string(
        """
        <h2>Wein bearbeiten</h2>
        <form method="post">
            Name: <input name="name" value="{{ wein['name'] }}"><br>
            Jahrgang: <input name="jahrgang" value="{{ wein['jahrgang'] }}"><br>
            Weingut: <input name="weingut" value="{{ wein['weingut'] }}"><br>
            Kontingent: 
            <select name="kontingent">
                {% for k in kontingente %}
                <option value="{{k}}" {% if wein['kontingent'] == k %}selected{% endif %}>{{k}}</option>
                {% endfor %}
            </select><br>
            Menge: <input name="menge" type="number" value="{{ wein['menge'] }}"><br><br>
            <button type="submit">Speichern</button>
        </form>
        <a href='/admin?pw=1234&tab=verwaltung'>Zurück</a>
        """,
        wein=wein,
        kontingente=KONTINGENTE,
    )

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
        daten["übrig"] = daten["gesamt"] - (daten["verkauf"] + daten["winzer"])

    # CSV-Datei erstellen
    out_file = "vorlage_export.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        # Kopfzeile schreiben
        writer.writerow([
            "Wein Name:", "Jahrgang:", "Weingut:", "Gesamtanzahl gelieferte Flaschen:",
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
