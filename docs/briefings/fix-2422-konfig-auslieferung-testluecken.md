---
spec_file: docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md
spec_sha256: cb6134634aa06408d76ec8e09bc2b867d7f07f1d92eb561b4441a49ab9126602
---

# PO-Briefing: fix-2422-konfig-auslieferung-testluecken

- **Spec:** docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md
- **Issue:** #2422
- **Erstellt:** 2026-09-26

## Was gebaut wird

Ein automatischer Test prüft künftig, ob die Editor-Einstellung tatsächlich in E-Mail, Telegram und SMS ankommt.

## Definition of Done

Fertig ist es, wenn der Test bekannte Lücken zuverlässig aufdeckt und neue Abweichungen zwischen Einstellung und Auslieferung automatisch meldet.

## Wie geprüft wird

14 Testfälle decken die Testlogik selbst ab; der Bug aus dem Beispiel wird nicht behoben, nur sichtbar gemacht.

## Kritische Anmerkungen

- Der Bug aus dem Beispiel (fehlende Windchill-Anzeige) wird hier nicht behoben, nur dokumentiert und befristet toleriert.
- Dies ist nur Scheibe 1 von 6 — Alarme, Kanal-Ein/Aus, Versandzeiten und Ortsvergleich bleiben vorerst ungetestet.
- Wie die Anzeige im Editor selbst korrekt bleibt, prüft eine spätere Scheibe, nicht diese.

## Freigabe-Frage

Reicht es Ihnen, jetzt nur den Prüf-Mechanismus zu bekommen — mit bekannten Fehlern noch unbehoben — oder soll zuerst der Bug selbst behoben werden?
