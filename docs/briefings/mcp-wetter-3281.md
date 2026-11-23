# PO-Briefing: mcp-wetter-3281

- **Spec:** docs/specs/modules/mcp_wetter_konnektor.md
- **Issue:** #3281
- **Erstellt:** 2026-11-22

## Was gebaut wird

Du kannst in der Claude-App beliebige Wetterfragen zu jedem Ort stellen und bekommst stündliche Rohwerte.

## Definition of Done

Auf Staging fragst du in der Claude-App nach Frankfurt und Münster und bekommst Ortsname und Stundenwerte als Antwort.

## Wie geprüft wird

Automatische Tests belegen Anmeldung, Zugangsbeschränkung, Datentrennung und Wetterwerte; das Hinzufügen in der echten Claude-App prüft nur der Abschlusstest auf Staging.

## Kritische Anmerkungen

- Anmeldung nutzt dein bestehendes Gregor-Konto statt Friedas E-Mail-Code; sonst wie bei Frieda.
- Regenfragen sind nur stundengenau beantwortbar, kein Regenradar; maximal 7 Tage pro Abfrage.
- Der Staging-Test braucht eine zusätzliche Freischaltung im Server-Repository; Lieferung erfolgt in zwei Teilen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
