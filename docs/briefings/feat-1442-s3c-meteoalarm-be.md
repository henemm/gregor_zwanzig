---
spec_file: docs/specs/modules/feat_1442_s3c_meteoalarm_be.md
spec_sha256: 00ee4e642d11397052c9cdba5cefb56ab0fd30c20084fcd5deec845b2c959867
spec_frozen_sha256: 22dce9aa78e2d0fd07f334a3c236a026ef98a8d7cc25d30b619e99869ac4fef7
---

# PO-Briefing: feat-1442-s3c-meteoalarm-be

- **Spec:** docs/specs/modules/feat_1442_s3c_meteoalarm_be.md
- **Issue:** #1442
- **Erstellt:** 2026-10-31

## Was gebaut wird

Wanderer in Belgien bekommen amtliche Unwetterwarnungen über alle vier Kanäle, in Trip und Ortsvergleich.

## Definition of Done

Für Orte in Belgien erscheinen aktuelle amtliche Warnungen mit Stufe, Art und Zeitraum; ohne Warnung bleibt es ruhig, ohne falschen Ausfallhinweis.

## Wie geprüft wird

Tests mit echtem Belgien-Feed-Auszug belegen Zuordnung, Aktualisierung, Ausfallverhalten und Kanäle; der Live-Test kann mangels aktiver Warnung übersprungen werden.

## Kritische Anmerkungen

- Statt der geplanten Eurostat-Grenzen (nicht kommerziell nutzbar) kommen EMMA-Zonen plus Zuordnungstabelle zum Einsatz; Lizenz der Zonendatei bleibt ungeklärt.
- Brabant, Brüssel und beide Brabant-Hälften sind nicht trennbar: lieber eine Warnung zu viel.
- Der Abdeckungstest nutzt keine echte Landmaske; die 0,03-Prozent-Lücke stammt aus manueller Messung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
