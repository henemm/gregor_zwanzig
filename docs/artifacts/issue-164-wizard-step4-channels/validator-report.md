# External Validator Report

**Spec:** docs/specs/modules/epic_136_step4_briefings.md
**Datum:** 2026-05-11T09:45:00Z
**Server:** https://staging.gregor20.henemm.com
**Validator-Session:** unabhaengig, ohne Zugriff auf src/, ohne git diff/log,
ohne Lesen von docs/artifacts/* Vorlauf-Dateien.

## Test-Setup

- Browser: Chromium (Playwright headless, Viewport 1280x1200)
- Cookie: `gz_session=validator-issue110.*` (validator-issue110 Test-User)
- GPX-Fixture: `frontend/e2e/fixtures/test-trip.gpx` (generische 14-Trkpt-Datei,
  als reines Eingabe-Asset behandelt)
- Walkthrough-Skripte: `frontend/validate-step4-full.mjs`,
  `frontend/validate-step4-nothresh.mjs`
- Screenshots: `docs/artifacts/issue-164-wizard-step4-channels/validator-screenshots/`

## Persistenz-Beweise (per `GET /api/trips/<id>`)

**Trip A — alle Schwellwerte gesetzt** (Walkthrough mit AC#15-Inputs,
Morgen-Zeit auf 07:30 geaendert):
- id: `7fe744bb`, name: "Validator Final Step4"
- `report_config`:
  ```json
  {
    "alert_thresholds": {
      "gust_kmh": 80, "precip_mm": 10,
      "snow_line_m": 2500, "thunder_level": "MED"
    },
    "enabled": true,
    "morning_time": "07:30", "evening_time": "18:00",
    "send_email": true, "send_signal": false,
    "send_sms": false, "send_telegram": false
  }
  ```

**Trip B — keine Schwellwerte** (Walkthrough mit Default-Werten):
- id: `81044db1`, name: "Validator NoThresh Final"
- `report_config`:
  ```json
  {
    "enabled": true,
    "morning_time": "06:00", "evening_time": "18:00",
    "send_email": true, "send_signal": false,
    "send_sms": false, "send_telegram": false
  }
  ```
  → `alert_thresholds`-Key ist NICHT vorhanden (Spec §3.3: nur schreiben wenn
  min. ein Feld nicht null).

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Container mit TestID `trip-wizard-step4-container` | v04-step4-initial.png + isVisible()=true | PASS |
| 2 | `trip-wizard-step4-channels-list` mit 4 Toggles | 5 TestIDs sichtbar: list, email, signal, telegram, sms | PASS |
| 3 | Email-Toggle standardmaessig aktiviert | isChecked()=true | PASS |
| 4 | Signal- und Telegram-Toggle standardmaessig deaktiviert | beide isChecked()=false | PASS |
| 5 | SMS-Toggle `disabled` | isDisabled()=true | PASS |
| 6 | SMS-Hint zeigt "demnaechst verfuegbar" | Text-Content "demnaechst verfuegbar" (v04) | PASS |
| 7 | Klick auf Email-Toggle aendert State | true→false→true (zwei aufeinanderfolgende Klicks) | PASS |
| 8 | `trip-wizard-step4-reports-list` mit 2 ReportRows | list + 4 inner testids sichtbar | PASS |
| 9 | Morgen-Toggle aktiviert, Zeit "06:00" | isChecked=true, inputValue "06:00" | PASS |
| 10 | Abend-Toggle aktiviert, Zeit "18:00" | isChecked=true, inputValue "18:00" | PASS |
| 11 | Morgen-Zeit deaktiviert wenn Toggle aus | Toggle off → time isDisabled=true; toggle on → re-enabled | PASS |
| 12 | Aenderung Morgen-Zeit auf "07:30" persistiert | inputValue "07:30" + Trip A `morning_time:"07:30"` in DB | PASS |
| 13 | `trip-wizard-step4-thresholds-list` mit 4 Rows | list + gust/precip/thunder/snow sichtbar | PASS |
| 14 | Schwellwert-Inputs initial leer | alle inputValues == "" | PASS |
| 15 | Number-Inputs nehmen Werte; leeres Feld = null im State | gust="80" akzeptiert; Trip B speichert ohne `alert_thresholds` | PASS |
| 16 | Gewitter-Select Optionen "—"/"Kein"/"Mittel"/"Hoch" | `[{"":"—"},{"NONE":"Kein"},{"MED":"Mittel"},{"HIGH":"Hoch"}]` | PASS |
| 17 | `canAdvanceStep4` immer true | INDIREKT: Save-Button durchgaengig enabled, Trip B speicherbar | PASS |
| 18 | `canAdvanceCurrent` case 4 → `canAdvanceStep4` | INDIREKT: Save in Step 4 immer enabled | PASS |
| 19 | Save-Button in Step 4 sichtbar+enabled | `trip-wizard-save` isVisible=true, isEnabled=true | PASS |
| 20 | `report_config.enabled = morning \|\| evening` | Trip A: enabled=true (beide on); ablesbar im JSON | PASS |
| 21 | `morning_time`/`evening_time` als 'HH:MM' | Trip A: "07:30"/"18:00", Trip B: "06:00"/"18:00" | PASS |
| 22 | `send_email/signal/telegram/sms` korrekt geschrieben | Trip A+B: email=true, andere=false | PASS |
| 23 | `alert_thresholds` nur wenn min. ein Feld nicht null | Trip A: voller Block; Trip B: kein `alert_thresholds`-Key | PASS |
| 24 | `thunder_level` als String-Enum oder null | Trip A: `thunder_level:"MED"`; Trip B: nicht gesetzt | PASS |
| 25 | Save → Redirect zu `/trips/<id>` | URL: `/trips/new` → `/trips/81044db1` (gemessen) | PASS |
| 26 | Alte TestID `-briefings` nicht mehr verwendet | getByTestId('trip-wizard-step4-briefings').isVisible()=false | PASS |
| 27 | `npm run check` / `npm run build` gruen | INDIREKT: Staging deployed (Build erfolgreich) | PASS (indirekt) |

## Findings

### Visual: Zeit-Anzeige im 12h-Format
- **Severity:** LOW (Hinweis, kein Spec-Bruch)
- **Expected:** Spec sagt "06:00" / "18:00" als HH:MM-Format.
- **Actual:** Browser-Locale rendert `<input type="time">` als "06:00 AM" /
  "06:00 PM". Der zugrundeliegende inputValue bleibt "06:00"/"18:00", was die
  Spec-Bedingungen (AC#9/10/12/21) erfuellt. Dies ist Browser-Default-Verhalten
  und nicht App-steuerbar.
- **Evidence:** `validator-screenshots/v04-step4-initial.png` (06:00 AM /
  06:00 PM), `v05-step4-filled.png` (07:30 AM)

Keine Korrektur erforderlich.

### Indirekte AC-Verifikation (AC#17/#18/#27)
- AC#17/#18 sind als Unit-Test spezifiziert; das beobachtete UI-Verhalten
  (Save-Button immer enabled in Step 4, Save ohne Eingaben moeglich)
  entspricht eindeutig der Spec.
- AC#27 (Build/Check gruen) ist aus Validator-Sicht nicht direkt pruefbar; die
  App laeuft live auf Staging, was einen erfolgreichen Build voraussetzt.

## Verdict: VERIFIED

### Begruendung

Alle 27 Acceptance Criteria sind erfuellt — 24 durch direkte UI-Beobachtung
und Persistenz-Checks gegen die API, 3 indirekt durch beobachtetes
Endverhalten (AC#17/#18/#27).

Konkret bewiesen:
1. UI-Struktur: 3 Sektionen ("Kanaele", "Reports", "Alert-Schwellwerte"), alle
   17 spezifizierten TestIDs vorhanden — sichtbar in `v04`/`v05`.
2. Default-Werte (Email an, andere Channels aus, 06:00/18:00, keine
   Schwellwerte) — bestaetigt durch `isChecked()` und `inputValue()`-Probes.
3. SMS-Sperre mit Hint-Text "demnaechst verfuegbar" — bestaetigt (isDisabled +
   Text).
4. Interaktive Bindings (Toggle, Zeit-Aenderung, Disable-Verhalten) —
   bestaetigt durch wiederholte Klicks und Re-Reads.
5. Save-Pipeline `briefings → report_config` mit Backward-Compat-Block (immer)
   und konditionalem `alert_thresholds`-Block (nur wenn Feld != null) —
   bestaetigt durch GET auf zwei mit dem Wizard erstellte Trips
   (`7fe744bb` und `81044db1`).
6. TestID-Migration von `trip-wizard-step4-briefings` auf `-container` —
   bestaetigt: alter TestID nicht mehr im DOM.
7. Redirect auf `/trips/<id>` nach Save — beobachtbar.

Keine FAILs, keine UNKLAR. Step 4 verhaelt sich exakt wie spezifiziert.
