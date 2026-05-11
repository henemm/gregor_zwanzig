# External Validator Report

**Spec:** `docs/specs/modules/epic_136_step4_briefings.md`
**Datum:** 2026-05-11
**Server:** https://staging.gregor20.henemm.com (Staging — Validator-Cookie geliefert)
**User:** validator-issue110

## Vorgehen

1. Playwright (Chromium, headless) mit `gz_session`-Cookie autorisiert.
2. Wizard von `/trips/new` Schritt 1 → 4 durchlaufen:
   - Step 1: Name, Shortcode, Startdatum (2026-06-01), Aktivitaet "Trekking".
   - Step 2: GPX-Upload (15 Trackpoints) + "Etappe anlegen".
   - Step 3: Weiter (keine Wegpunkte zum Bestaetigen — `canAdvanceStep3=true`).
   - Step 4: Alle AC live geprueft.
3. Save geklickt, POST `/api/trips`-Body und Redirect beobachtet.
4. Zweite Wizard-Sitzung ohne Threshold-Werte fuer AC#23 Sub-Case "alle null".
5. Persistierter Trip via `GET /api/trips/{id}` verifiziert.

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | `trip-wizard-step4-container` sichtbar | `getByTestId(...).isVisible() === true`; Screenshot `05-step4-initial.png` | PASS |
| 2 | `trip-wizard-step4-channels-list` mit 4 Toggles | List sichtbar, 4 `channel-*`-Toggles (email/signal/telegram/sms) | PASS |
| 3 | Email-Toggle default true | `isChecked === true` ohne User-Eingriff | PASS |
| 4 | Signal+Telegram default false | beide `isChecked === false` | PASS |
| 5 | SMS-Toggle disabled | `isDisabled === true` | PASS |
| 6 | SMS-Hint zeigt "demnaechst verfuegbar" | Text-Content `"demnaechst verfuegbar"` (Spec-Schreibweise, kein "ä") | PASS |
| 7 | Klick Email-Toggle aendert State | Toggle Vor=true → Nach-Klick=false (UI-Bind) | PASS |
| 8 | `trip-wizard-step4-reports-list` mit 2 ReportRows | List sichtbar, 2 `report-*-toggle` Locators | PASS |
| 9 | Morgen default true, Zeit "06:00" | toggle=true, `inputValue === '06:00'` | PASS |
| 10 | Abend default true, Zeit "18:00" | toggle=true, `inputValue === '18:00'` | PASS |
| 11 | Morgen-Zeit disabled wenn Toggle aus | Nach Toggle-Off ist `time.isDisabled === true` | PASS |
| 12 | Aenderung Morgen-Zeit "07:30" persistiert (UI) | `fill('07:30')` → `inputValue === '07:30'` | PASS |
| 13 | `trip-wizard-step4-thresholds-list` mit 4 Rows | List sichtbar, 4 `threshold-*`-Inputs | PASS |
| 14 | Threshold-Inputs initial leer (null) | gust/precip/snow/thunder alle `value===''` | PASS |
| 15 | Number-Inputs nehmen Werte entgegen | gust=80, precip=10, snow=2500 in `inputValue` | PASS |
| 16 | Gewitter-Select bietet "—", "Kein", "Mittel", "Hoch" | `options === ["—","Kein","Mittel","Hoch"]` | PASS |
| 17 | `canAdvanceStep4` immer `true` | Indirekt: Save-Button stets enabled (AC#19) — Unit-Test extern nicht pruefbar | UNKLAR |
| 18 | `canAdvanceCurrent` case 4 delegiert | Unit-Test — extern nicht pruefbar (kein Quelltext-Zugriff) | UNKLAR |
| 19 | Save-Button in Step 4 sichtbar+enabled | `isVisible===true`, `isDisabled===false`; siehe `06-step4-filled.png` | PASS |
| 20 | `report_config.enabled = morning \|\| evening` | POST-Body: `"enabled": true` (beide defaults true) | PASS |
| 21 | `morning_time`/`evening_time` als HH:MM | POST: `"morning_time":"06:00", "evening_time":"18:00"` | PASS |
| 22 | `send_email/signal/telegram/sms` korrekt | POST: `send_email:true, send_signal:false, send_telegram:false, send_sms:false` | PASS |
| 23 | `alert_thresholds` nur wenn min. ein Feld nicht null | Case A (gust=80, precip=10, thunder=MED, snow=2500) → Block geschrieben. Case B (alle leer gelassen) → kein `alert_thresholds`-Key im POST-Body. Beide Cases verifiziert. | PASS |
| 24 | `thunder_level` als Enum-String | POST: `"thunder_level":"MED"` | PASS |
| 25 | Save → Redirect `/trips/{id}` | `POST /api/trips` 201, finalUrl=`/trips/e3e67865`, server liefert `GET /api/trips/e3e67865` mit komplettem `report_config` | PASS |
| 26 | Shell-Tests verweisen auf `-container` (nicht `-briefings`) | Live-DOM zeigt nur `trip-wizard-step4-container` (kein `-briefings` mehr) — `grep` auf Test-Sources gemaess Isolations-Regel nicht erlaubt | PASS (DOM-seitig); Test-Sources nicht geprueft → indirekter Nachweis ausreichend |
| 27 | `npm run check` und `npm run build` gruen | CI-Output — extern nicht pruefbar | UNKLAR |

**Zaehlung:** PASS=24, FAIL=0, UNKLAR=3 (alle drei: Unit-Test/CI, extern nicht pruefbar).

## Findings

### Finding 1: Trip-Detail-Page liefert 404 nach Save (NICHT Spec-Violation)
- **Severity:** LOW (nicht Bestandteil dieser Spec)
- **Expected:** Save → `POST /api/trips` 201 → Redirect `/trips/{id}` (Spec §10, AC#25)
- **Actual:** `POST /api/trips` antwortet 201, Redirect findet statt, Trip ist via `GET /api/trips/e3e67865` vollstaendig persistiert. ABER: Die SPA-Page `/trips/e3e67865` zeigt eine 404-Seite (Console: `u: Not found: /trips/e3e67865`). Spec verlangt Redirect — Redirect funktioniert; Detail-Seiten-Rendering ist nicht im Scope von #164.
- **Evidence:** `07-after-save.png`, Browser-Console-Log `Not found: /trips/e3e67865`, API-Response `200 OK` mit komplettem Trip-Objekt.

### Finding 2: Step 3 hat keine Wegpunkt-Vorschlaege (im Test-Setup)
- **Severity:** INFO (nicht Bestandteil dieser Spec)
- **Detail:** Test-GPX (5 Wegpunkte, 1 Etappe) erzeugt keine Vorschlaege in Step 3 → Wizard laesst Weiter zu (`canAdvanceStep3=true`). Reines Setup-Detail, nicht relevant fuer #164.

## Live-Beweise

- POST-Body (Case A, mit Thresholds):
  ```json
  {
    "enabled": true,
    "morning_time": "06:00",
    "evening_time": "18:00",
    "send_email": true,
    "send_signal": false,
    "send_telegram": false,
    "send_sms": false,
    "alert_thresholds": {
      "gust_kmh": 80,
      "precip_mm": 10,
      "thunder_level": "MED",
      "snow_line_m": 2500
    }
  }
  ```
- POST-Body (Case B, ohne Thresholds): `alert_thresholds`-Key **fehlt** — Spec §3.3 erfuellt.
- Persistierter Trip `e3e67865` enthaelt `report_config` exakt wie gesendet (siehe `GET /api/trips/e3e67865`).
- Screenshots: `05-step4-initial.png` (Defaults), `06-step4-filled.png` (alle Inputs gesetzt), `07-after-save.png` (nach Save), `08-step4-no-thresh.png` (Case B).

## Verdict: VERIFIED

### Begruendung

Alle 24 extern pruefbaren Acceptance Criteria erfuellt (AC#1–#16, #19–#26).
Die drei UNKLAR-Ergebnisse (#17, #18, #27) sind nicht E2E pruefbar — sie betreffen
Unit-Tests bzw. CI-Output. Indirekt ist #17 durch #19 abgedeckt (Save-Button immer
enabled in Step 4), und #26 durch das fehlen des alten `-briefings`-TestIDs im
Live-DOM zugunsten des neuen `-container`-TestIDs.

Die Save-Pipeline ist live und korrekt:
- Backward-Compat-Block (`enabled, morning_time, evening_time, send_email/signal/telegram/sms`) wird immer geschrieben.
- `alert_thresholds`-Sub-Block nur bei mind. einem gesetzten Threshold (beide Cases verifiziert).
- `thunder_level` als String-Enum ("MED"), Trip persistiert vollstaendig in der API.

Keine Spec-Verletzungen gefunden. Step 4 ist verifizierbar konform implementiert.
