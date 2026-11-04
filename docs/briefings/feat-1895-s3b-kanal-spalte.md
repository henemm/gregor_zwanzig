---
spec_file: docs/specs/modules/alert_metric_channels.md
spec_sha256: c0279d873f5cf005992f248052c36b665de90b304e631a5438a8dc133d5c5d0b
spec_frozen_sha256: 78624972eba491a8b5698838cdb4efb0004546670deba8ca0516007354f9c0bd
---

# PO-Briefing: feat-1895-s3b-kanal-spalte

- **Spec:** docs/specs/modules/alert_metric_channels.md
- **Issue:** #1895
- **Erstellt:** 2026-11-03

## Was gebaut wird

Nutzer wählen im Alarme-Reiter je Wettergröße eigene Alarm-Kanäle, in Trip und Ortsvergleich, auch beim Anlegen.

## Definition of Done

Auf Staging lässt sich die Kanalwahl je Wettergröße am Handy und am Desktop setzen, speichern, neu laden und zurücknehmen.

## Wie geprüft wird

Automatische Tests prüfen Speichern, Zurückrollen, zwei Nutzer und den echten Alarm-Versandkanal; Bedienbarkeit und Kontrast prüft ein Browsertest auf Staging.

## Kritische Anmerkungen

- Hinweise „Kanal ohne Empfänger" und „Schwelle über Metrik-Stufe" fehlen bewusst (später, S3b2); bis dahin kann ein Alarm ohne Warnung ausbleiben.
- Radar-, Regen- und amtliche Warnungen folgen nie der neuen Wahl; nur ein Hinweistext sagt das.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
