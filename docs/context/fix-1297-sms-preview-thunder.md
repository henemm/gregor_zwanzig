# Kontext: fix-1297-sms-preview-thunder

**Issue:** #1297 — SMS-Vorschau zeigt immer `TH+:-`, die echte SMS den echten Wert.
**Familie:** #1275 / ADR-0025 („eine Gewitter-Quelle für alle Briefing-Kanäle"). Der Preview-Pfad war dort nicht im Scope.

## Ursache (am Code verifiziert, aus dem Issue übernommen und gegengeprüft)

`src/services/preview_service.py` übergibt in keinem Render-Aufruf `thunder_forecast` (`grep -c thunder_forecast` → 0). Der echte Versandweg reicht es durch: `src/services/trip_report_scheduler.py:904` und `:998`. `sms_trip.py` baut `tomorrow_day` nur bei vorhandenem `thunder_forecast` — in der Vorschau ist es `None`, `TH+` bleibt strukturell leer.

Beobachtete Folge (Staging, dieselbe Tour, derselbe Folgetag): E-Mail „⚡ Starkes Gewitter erwartet ab 02:00" vs. SMS-Vorschau `TH+:-`. Ein Nutzer, der die Vorschau prüft, sieht „kein Gewitter" und bekommt eine SMS mit Gewitter — oder umgekehrt.

## Warum kein Test es fing

`tests/tdd/test_sms_preview_matches_sent.py` — der Wächter „Vorschau == versendet" — schließt laut eigenem Setup-Kommentar (Zeile 11, 39-41) die `thunder`-Metrik bewusst aus. Er ist konstruktionsbedingt blind für genau die Metrik, die divergiert.

## Fix-Richtung (Lehre aus #1275: bewährte Quelle wiederverwenden, keine Parallel-Implementierung)

1. `preview_service.py` erzeugt/übergibt `thunder_forecast` über **dieselbe** Kette wie der Scheduler. Erzeuger existieren: `trip_report_scheduler.py:1495-1583` (Trend-Primärpfad) und `:1641-1719` (Fetch-Fallback). Prüfen, ob die Kette als aufrufbare Einheit exponiert ist oder minimal extrahiert werden muss (Extraktion = eine Quelle, Scheduler + Preview rufen dieselbe Funktion).
2. Wächter-Test um einen Fall **mit** aktivierter Gewitter-Metrik und echtem `thunder_forecast` erweitern — sonst bleibt er blind.

## Betroffene Kanäle in der Vorschau

`preview_service` rendert E-Mail und SMS (und Telegram-Text, prüfen). Der Fix muss alle Vorschau-Render-Aufrufe versorgen, die `thunder_forecast` konsumieren — nicht nur SMS. Gleiche Quelle für alle (ADR-0025).

## Randbedingungen

- **Kein Umbau des Versandwegs** — der ist seit #1275 korrekt und adversary-verifiziert. Nur die Vorschau zieht nach.
- Multi-User: Preview läuft mit `user_id`-Parameter; Fix darf keine `"default"`-Abkürzungen einführen.
- Nebenwirkung dokumentiert in #1275: Der Staging-E2E-Nachweis für dessen AC-3 lief über den Preview-Endpunkt und war wertlos. Nach diesem Fix kann der Preview-Endpunkt wieder als E2E-Beweisfläche für `TH+` dienen — das ist der Verifikationsweg für Staging.
- Parallel-Arbeit beachten: Epic #1301 (Scheiben A2 ff.) arbeitet am Compare-Datenpfad, NICHT an `preview_service`/`trip_report_scheduler` — keine Kollision. #1273 arbeitet frontendseitig am Compare-Hub — keine Kollision.
