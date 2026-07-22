# Context: KHW-Briefing — Gitter-Verlust (Handy) + Kurzform↔Tabelle-Divergenz

## Ausgangslage (Nutzermeldung 2026-07-22)

Am 12:00-KHW-Briefing (nachgeholt) fielen zwei Dinge auf:
1. Die Zusammenfassung (SMS/Kurzform) warnt vor Gewitter/Regen, der sich in der
   Stundentabelle nicht wiederfindet.
2. Das Tabellengitter im Mailing fehlt auf dem Handy.

## Ermittlung (belegt)

**Quellen:** tatsächlich ausgelieferte Mails aus dem Resend-Sent-Log (Montag
20.07 16:00 = mit Gitter; heute 22.07 12:00 = ohne Gitter), Server-Logs, echte
Trip-Config aus `briefings/` (als claude-gregor gelesen).

**Gitter-Verlust:** Das Mobil-Gitter (`_render_mobile_compact_rows`, email/html.py)
ist an `build_html_indicator_keys(dc)` gekoppelt (≥1 ampel-fähige Metrik mit
`use_friendly_format=True`). Der Nutzer hat cape am 20.07 19:15 bewusst auf „roh"
gestellt (Server-Log: echte App-Bearbeitung `PUT /api/trips/5f534011/weather-config`),
weil die CAPE-Ampel immer grün zeigte. cape war die letzte friendly-Ampel →
`indicator_keys` leer → gitterloser `<pre>`. KEIN Editor-Bug, KEIN Renderer-Umbau.

**CAPE „immer grün":** `severity_for("cape", v)` arbeitet korrekt gegen
`display_thresholds={yellow:1000, orange:2500, red:3500}` (Flachland-Skala).
Reale Berg-CAPE-Werte liegen meist <1000 → dauergrün, obwohl „⚡" gewarnt wird.
Schwellen für Berg-Sicherheit zu hoch.

**Kurzform↔Tabelle:** Kurzform wertet das Tagesfenster (`day_window`, 04–19 h)
aus, die Tabelle nur echte Wander-/Ankunft-/Nacht-Stunden. Peak um 16:00 (nach
Wanderende 11:18) → Warnung ohne Tabellenzeile.

## Sofort-Restore (erledigt)

`briefings/5f534011.json`: cape `use_friendly_format` False→True (RMW+Merge,
Backup). Gitter kommt beim nächsten Briefing zurück. Diese Arbeit macht cape
dauerhaft sinnvoll (CAPE-Kalibrierung) und behebt die Kurzform-Divergenz.

## PO-Entscheidungen

- CAPE-Schwellen neu: grün <300, gelb 300–799, orange 800–1499, rot ≥1500 J/kg.
- Kurzform darf nichts melden, was nicht in der Tabelle steht (Fenster angleichen).
- Gitter-Entkopplung vom Ampel-Modus: optionaler Folgeschritt, nicht in diesem Fix.
