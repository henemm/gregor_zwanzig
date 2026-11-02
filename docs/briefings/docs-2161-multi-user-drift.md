---
spec_file: docs/specs/modules/multi_user_doc_drift.md
spec_sha256: 9556ed1407cf51517c41c8411396974a85bfe57b02d9cb336bf63db89531e50f
spec_frozen_sha256: 4cd1b61597effe6a00487f2429b09a5d4b683b50e515c9636c840ca615e7baf4
---

# PO-Briefing: docs-2161-multi-user-drift

- **Spec:** docs/specs/modules/multi_user_doc_drift.md
- **Issue:** #2161
- **Erstellt:** 2026-11-02

## Was gebaut wird

Veraltete Einzelnutzer-Aussagen in Specs und Doku werden auf den Mehrbenutzer-Stand gebracht; eine wirkungslose Empfänger-Prüfung entfällt.

## Definition of Done

Die Doku nennt keine Einzelnutzer-Annahmen mehr, dein Entscheid steht festgehalten, und ein Preset mit beliebigem Empfängereintrag lässt sich speichern.

## Wie geprüft wird

Automatische Tests belegen Speichern und Nutzertrennung bei Presets; die Doku-Änderungen prüft nur eine manuelle Textsuche, kein Test.

## Kritische Anmerkungen

- Das Empfänger-Feld bleibt bewusst gespeichert statt entfernt, damit Bestandsdaten nicht verloren gehen; das Ticket erwartete evtl. Entfernen.
- Zusätzlich zum Ticket erhalten drei weitere veraltete Dokumente (Web-Oberfläche, SvelteKit-Entwurf, API-Vertrag) Korrekturen oder Hinweise.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
