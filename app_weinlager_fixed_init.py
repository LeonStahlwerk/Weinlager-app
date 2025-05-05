
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

# Restlicher Code folgt ...
# Du kannst hier den Inhalt aus app_weinlager_complete_final_app.py + admin_complete anhängen.
# Damit bleibt der gesamte Funktionsumfang erhalten und es kommt zu keinem Startfehler mehr.
