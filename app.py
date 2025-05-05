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

        return render_template_string("""<h2>Verwaltung</h2>{{ tabs|safe }}<p>{{ msg }}</p>
            <form method="post">
              Barcode: <input name="barcode"><br>
              Name: <input name="name"><br>
              Jahrgang: <input name="jahrgang"><br>
              Weingut: <input name="weingut"><br>
              Kontingent: <input name="kontingent"><br>
              Menge: <input name="menge"><br>
              <button type="submit">Speichern</button>
            </form>
            <h3>Weine</h3>
            <ul>
            {% for code, w in weine.items() %}
              <li><b>{{ w['name'] }}</b> – {{ w['weingut'] }} ({{ w['jahrgang'] }})
                <ul>{% for k, m in w['kontingente'].items() %}
                  <li>{{ k }}: {{ m }} Flaschen</li>
                {% endfor %}</ul>
              </li>
            {% endfor %}
            </ul>
            <a href='/download/weine.csv'>📥 Gesamte Weine als CSV</a>
        """, msg=msg, weine=weine, tabs=TAB_HTML)

    elif tab == "statistik":
        ausgaben = []
        bestand = {}

        with open("weine.csv", newline="") as f:
            for row in csv.DictReader(f):
                bestand[row["barcode"]] = int(row["menge"])

        with open("ausgaben.csv", newline="") as f:
            ausgaben = list(csv.DictReader(f))

        statistik = {}
        for row in ausgaben:
            barcode = row["barcode"]
            name = row["wein"]
            if barcode not in statistik:
                statistik[barcode] = {
                    "name": name,
                    "verkauf": 0,
                    "winzer": 0,
                    "bestand": bestand.get(barcode, 0)
                }
            menge = int(row["menge"])
            kategorie = row["kategorie"]
            if kategorie == "Verkauf":
                statistik[barcode]["verkauf"] += menge
            elif kategorie == "Winzer":
                statistik[barcode]["winzer"] += menge

        return render_template_string("""
        <h2>Statistik</h2>{{ tabs|safe }}
        <ul>
        {% for barcode, daten in statistik.items() %}
            <li>
                <a href="/wein/{{ barcode }}"><b>{{ daten['name'] }}</b></a>:
                {{ daten['verkauf'] }} Flaschen verkauft,
                {{ daten['winzer'] }} Flaschen an Winzer,
                {{ daten['bestand'] }} Flaschen noch im Bestand
            </li>
        {% endfor %}
        </ul>
        """, statistik=statistik, tabs=TAB_HTML)

    elif tab == "weingueter":
        ausgaben = []
        with open("ausgaben.csv", newline="") as f:
            ausgaben = list(csv.DictReader(f))

        weingueter = {}
        for row in ausgaben:
            w = row["weingut"]
            m = int(row["menge"])
            k = row["kategorie"]
            if w not in weingueter:
                weingueter[w] = {"gesamt": 0, "winzer": 0, "verkauf": 0}
            weingueter[w]["gesamt"] += m
            if k == "Winzer":
                weingueter[w]["winzer"] += m
            elif k == "Verkauf":
                weingueter[w]["verkauf"] += m

        return render_template_string("""<h2>Weingüter</h2>{{ tabs|safe }}
        <ul>
        {% for w, d in weingueter.items() %}
          <li>{{ w }}: Gesamt {{ d['gesamt'] }} – Winzer {{ d['winzer'] }} – Verkauf {{ d['verkauf'] }}</li>
        {% endfor %}
        </ul>
        """, weingueter=weingueter, tabs=TAB_HTML)

@app.route("/wein/<barcode>")
def wein_detail(barcode):
    ausgaben = []
    with open("ausgaben.csv", newline="") as f:
        ausgaben = [r for r in csv.DictReader(f) if r["barcode"] == barcode]
    if not ausgaben:
        return "Keine Daten"
    name = ausgaben[0]["wein"]
    kategorien = {}
    for r in ausgaben:
        kategorien[r["kategorie"]] = kategorien.get(r["kategorie"], 0) + int(r["menge"])
    return render_template_string("""<h2>{{ name }}</h2>
      <a href='/admin?pw=1234&tab=statistik'>Zurück</a> |
      <a href='/download-log/{{ barcode }}'>📥 Log Export</a>
      <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
      <canvas id='chart'></canvas>
      <script>
      new Chart(document.getElementById('chart'), {
        type: 'pie',
        data: {
          labels: {{ kategorien.keys()|list }},
          datasets: [{ data: {{ kategorien.values()|list }}, backgroundColor: ['#007bff', '#28a745'] }]
        }
      });
      </script>
      <ul>{% for r in ausgaben %}<li>{{ r['datum'] }} – {{ r['menge'] }} Flaschen – {{ r['kontingent'] }} / {{ r['kategorie'] }}</li>{% endfor %}</ul>
    """, barcode=barcode, name=name, kategorien=kategorien, ausgaben=ausgaben)

@app.route("/download/<filename>")
def download_file(filename):
    return send_file(filename, as_attachment=True)

@app.route("/download-log/<barcode>")
def download_log(barcode):
    out = f"log_{barcode}.csv"
    with open("ausgaben.csv", newline="") as f, open(out, "w", newline="") as w:
        reader = csv.DictReader(f)
        writer = csv.DictWriter(w, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if row["barcode"] == barcode:
                writer.writerow(row)
    return send_file(out, as_attachment=True)
@app.route("/download/weine.csv")
def download_weine():
    # Daten aus den CSV-Dateien laden
    bestand = []
    ausgaben = []

    # "weine.csv" lesen
    with open("weine.csv", newline="") as f:
        bestand = list(csv.DictReader(f))

    # "ausgaben.csv" lesen
    with open("ausgaben.csv", newline="") as f:
        ausgaben = list(csv.DictReader(f))

    # Statistiken berechnen
    gesamt_fl = sum(int(row["menge"]) for row in bestand)
    kontingent_statistik = {}
    for row in bestand:
        kontingent = row["kontingent"]
        menge = int(row["menge"])
        kontingent_statistik[kontingent] = kontingent_statistik.get(kontingent, 0) + menge

    winzer_fl = sum(int(row["menge"]) for row in ausgaben if row["kategorie"] == "Winzer")
    verkauf_fl = sum(int(row["menge"]) for row in ausgaben if row["kategorie"] == "Verkauf")

    # Verbleibender Bestand berechnen
    verbleibend = {}
    for row in bestand:
        barcode = row["barcode"]
        original_menge = int(row["menge"])
        ausgegeben = sum(int(a["menge"]) for a in ausgaben if a["barcode"] == barcode)
        verbleibend[barcode] = original_menge - ausgegeben

    # CSV-Datei erstellen
    out_file = "weine_statistik.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.writer(f)
        # Kopfzeile hinzufügen
        writer.writerow(["Gesamtanzahl Flaschen", gesamt_fl])
        writer.writerow([])
        writer.writerow(["Kontingent", "Anzahl Flaschen"])
        for kontingent, menge in kontingent_statistik.items():
            writer.writerow([kontingent, menge])
        writer.writerow([])
        writer.writerow(["An Winzer ausgegeben", winzer_fl])
        writer.writerow(["Im Verkauf ausgegeben", verkauf_fl])
        writer.writerow([])
        writer.writerow(["Verbleibender Bestand"])
        writer.writerow(["Barcode", "Übrig"])
        for barcode, menge in verbleibend.items():
            writer.writerow([barcode, menge])

    # Datei zum Download bereitstellen
    return send_file(out_file, as_attachment=True)
