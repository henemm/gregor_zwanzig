---
spec_file: docs/specs/modules/feat_2799_s7_ampel_weitere.md
spec_sha256: 8cad40d3cb06b433f848698af744ed0c2df603e73d6bff2314b134a65406ad8b
spec_frozen_sha256: ac8b596079c9ffc289ab4d3500a722e38e7e80f23559adf50b7991e15c2eb355
---

# PO-Briefing: feat-2799-ampel-weitere

- **Spec:** docs/specs/modules/feat_2799_s7_ampel_weitere.md
- **Issue:** #2799
- **Erstellt:** 2026-11-28

## Was gebaut wird

Weitere Wetterwerte, darunter Nullgrad- und Schneefallgrenze relativ zur Höhe, werden in allen vier Kanälen farbig bewertet und teils alarmieren.

## Definition of Done

Alle genannten Werte erscheinen in E-Mail, Telegram, SMS und Premium-SMS mit gleicher Farbe, und Alarme kommen genau einmal je Stufenwechsel.

## Wie geprüft wird

Automatische Tests prüfen Farben, Höhenbezug, Alarme und Zwei-Nutzer-Trennung je Kanal, echte Staging-Mails kommen hinzu; Optik jenseits der Validatoren bleibt ungeprüft.

## Kritische Anmerkungen

- Zusätzlich zur Anfrage: Nacht-Tiefsttemperatur wird gefärbt und alarmiert; frühere freigegebene Specs hatten sie auf diesen Schritt verschoben.
- SMS-Werte für Nullgrad- und Schneefallgrenze wechseln von absolut auf relativ mit Vorzeichen; Empfänger sehen ein anderes Format (PO-Entscheid).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
