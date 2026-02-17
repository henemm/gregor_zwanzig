# E2E Production Verification

**PFLICHT vor jedem Commit!** Mechanische Verifikation, dass der neue Code produktiv funktioniert.

Du MUSST jeden Schritt vollstaendig ausfuehren. Kein Schritt darf uebersprungen werden.
Am Ende schreibst du `.claude/e2e_verified.json` — ohne diese Datei blockiert der Pre-Commit-Hook.

## Schritt 1: Server neu starten

```bash
# Alten Server killen
fuser -k 8080/tcp 2>/dev/null || true
sleep 1

# Neuen Server starten mit aktuellem Code
nohup uv run python3 -m src.web.main --port 8080 > /tmp/gregor_server.log 2>&1 &
sleep 3

# PRUEFEN dass Server wirklich laeuft (PID + HTTP)
SERVER_PID=$(fuser 8080/tcp 2>/dev/null | awk '{print $1}')
echo "Server PID: $SERVER_PID"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
```

**STOP wenn:** Kein PID oder HTTP != 200. Server-Log pruefen!

## Schritt 2: Test-Trip erstellen

Erstelle einen Test-Trip via API oder Loader. **NIEMALS** Produktiv-Trips (GR221 etc.) verwenden!

```python
uv run python3 -c "
from src.app.loader import Loader
loader = Loader()
# Erstelle minimalen Test-Trip mit 2 Stages
import json
test_trip = {
    'id': 'e2e-verify-test',
    'name': 'E2E Verify Test',
    'stages': [
        {
            'id': 'S1', 'name': 'Stage 1', 'date': '$(date -d '+1 day' +%Y-%m-%d)',
            'waypoints': [
                {'id': 'W1', 'name': 'Start', 'lat': 47.0, 'lon': 11.0, 'elevation_m': 500},
                {'id': 'W2', 'name': 'Ziel', 'lat': 47.1, 'lon': 11.1, 'elevation_m': 800}
            ],
            'start_time': '09:00:00'
        },
        {
            'id': 'S2', 'name': 'Stage 2', 'date': '$(date -d '+2 days' +%Y-%m-%d)',
            'waypoints': [
                {'id': 'W1', 'name': 'Start', 'lat': 47.1, 'lon': 11.1, 'elevation_m': 800},
                {'id': 'W2', 'name': 'Ziel', 'lat': 47.2, 'lon': 11.2, 'elevation_m': 600}
            ],
            'start_time': '09:00:00'
        }
    ]
}
loader.save_trip('default', test_trip)
print('Test-Trip erstellt: e2e-verify-test')
"
```

## Schritt 3: Report senden

Sende BEIDE Report-Typen (morning + evening) via TripReportSchedulerService:

```python
uv run python3 -c "
import asyncio
from src.services.trip_report_scheduler import TripReportSchedulerService
from src.app.loader import Loader

async def send():
    loader = Loader()
    scheduler = TripReportSchedulerService(loader)
    # Morning
    result_m = await scheduler.send_report('default', 'e2e-verify-test', 'morning')
    print(f'Morning: {result_m}')
    # Evening
    result_e = await scheduler.send_report('default', 'e2e-verify-test', 'evening')
    print(f'Evening: {result_e}')

asyncio.run(send())
"
```

**STOP wenn:** Fehler beim Senden. Logs pruefen!

## Schritt 4: E-Mails abrufen und SYSTEMATISCH pruefen

Rufe BEIDE E-Mails via IMAP ab. Pruefe den Inhalt SYSTEMATISCH — nicht nur stichprobenartig!

```python
uv run python3 -c "
import imaplib, email, os, time
time.sleep(5)  # Warten auf Zustellung

user = os.environ['GZ_SMTP_USER']
pw = os.environ['GZ_SMTP_PASS']

imap = imaplib.IMAP4_SSL('imap.gmail.com')
imap.login(user, pw)
imap.select('INBOX')

# Letzte 5 E-Mails holen
_, data = imap.search(None, 'ALL')
ids = data[0].split()[-5:]

for mid in ids:
    _, msg_data = imap.fetch(mid, '(RFC822)')
    msg = email.message_from_bytes(msg_data[0][1])
    subj = msg.get('Subject', '')
    date = msg.get('Date', '')
    print(f'--- {subj} ({date}) ---')

    # HTML Body extrahieren
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            html = part.get_payload(decode=True).decode('utf-8')
            print(f'HTML Laenge: {len(html)} Zeichen')
            # Ersten 2000 Zeichen ausgeben fuer Pruefung
            print(html[:2000])
            print('...')
            break
    print()

imap.close()
imap.logout()
"
```

### Was du PRUEFEN musst (Checkliste):

Fuer JEDE E-Mail:
- [ ] Subject enthaelt Trip-Name und Report-Typ
- [ ] HTML-Body ist nicht leer
- [ ] Tabelle mit Wetterdaten vorhanden
- [ ] Alle konfigurierten Metriken haben Spalten (Temperature, Wind, etc.)
- [ ] Werte sind plausibel (nicht "N/A" ueberall, nicht "None")
- [ ] Timestamp der E-Mail ist NACH dem Sendevorgang (nicht alte E-Mail!)

**Feature-spezifisch:**
- Bei Formatter-Features: HTML UND Plain-Text pruefen
- Bei Config-Features: ALLE betroffenen Config-Optionen einzeln pruefen
- Bei Metrik-Features: Spaltenheader, Werte und Units-Legend pruefen

## Schritt 5: Test-Trip aufraeumen

```python
uv run python3 -c "
from src.app.loader import Loader
loader = Loader()
loader.delete_trip('default', 'e2e-verify-test')
print('Test-Trip geloescht')
"
```

## Schritt 6: Verified-JSON schreiben

NUR wenn ALLE Schritte erfolgreich waren:

```bash
python3 -c "
import json, datetime
data = {
    'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'server_restarted': True,
    'test_trip_created': True,
    'reports_sent': ['morning', 'evening'],
    'emails_checked': True,
    'test_trip_cleaned': True,
    'feature_checks': ['HIER BESCHREIBEN WAS GEPRUEFT WURDE']
}
with open('.claude/e2e_verified.json', 'w') as f:
    json.dump(data, f, indent=2)
print('e2e_verified.json geschrieben')
"
```

## VERBOTEN

- Schritte ueberspringen
- "Sieht gut aus" ohne systematische Pruefung sagen
- Alte E-Mails als Verifikation akzeptieren (Timestamp pruefen!)
- Python-Funktionen direkt aufrufen statt echte E-Mails zu senden
- Produktiv-Trips verwenden
- `.claude/e2e_verified.json` schreiben OHNE alle Schritte durchlaufen zu haben
