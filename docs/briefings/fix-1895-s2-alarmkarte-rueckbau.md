---
spec_file: docs/specs/modules/fix_1895_s2_alarmkarte_rueckbau.md
spec_sha256: bb792d9b1ba8d63f7f56b97e28efae8d1d8577f45eb2726a0be0acd3eff6d70d
---

# PO-Briefing: fix-1895-s2-alarmkarte-rueckbau

- **Spec:** docs/specs/modules/fix_1895_s2_alarmkarte_rueckbau.md
- **Issue:** #1895
- **Erstellt:** 2026-09-21

## Was gebaut wird

Alarmregel-Karte im Trip-Editor zeigt nur noch Metrik, Kanäle, Aktiv-Haken; Schwelle, Zeitfenster, Wert und Δ-Zeichen entfallen.

## Definition of Done

In Bearbeiten- und Ansichtskarte fehlen Schwelle, Zeitfenster, Wert und Δ-Zeichen, Kanalwahl und Aktiv-Haken funktionieren weiter.

## Wie geprüft wird

Browser-Tests belegen fehlende Felder und funktionierende Kanäle; Logik-Tests belegen das Durchreichen alter Werte, nicht aber die Karte selbst.

## Kritische Anmerkungen

- Mehrere Zusicherungen hängen an manueller Durchsicht statt Tests; stilles Überschreiben alter Werte bliebe unsichtbar.
- „Variante A" und Rückbau der Ansichtskarte samt Δ-Zeichen stehen nicht im Ticket, nur im Kontext.
- Ticket verlangt in Schritt 2 auch Kanalzuordnung je Metrik; fehlt hier, #1895 bleibt halb erledigt und offen.

## Freigabe-Frage

Soll der Rückbau von Schwelle, Zeitfenster, Wert und Δ-Zeichen freigegeben werden, obwohl die Kanalzuordnung je Metrik offen bleibt?
