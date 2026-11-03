---
spec_file: docs/specs/modules/fix_2774_staging_mailweg.md
spec_sha256: caba2d4eb612e9d7e1626bd31a1cc7ec5cf65771b376f330452d44aabc0672eb
spec_frozen_sha256: e9dbfe2774fbd78acf37a59f22423fa62a82b2d7fa8830e13215d0132a58df19
---

# PO-Briefing: staging-mailweg-2774

- **Spec:** docs/specs/modules/fix_2774_staging_mailweg.md
- **Issue:** #2774
- **Erstellt:** 2026-11-03

## Was gebaut wird

Ein Prüfwerkzeug stellt Trip- und Vergleichs-Mail auf Staging wirklich zu und prüft sie mit dem passenden Validator.

## Definition of Done

Ein Aufruf stellt beide Mails zu, der Validator meldet Erfolg, und das dafür angelegte Testkonto ist danach wieder gelöscht.

## Wie geprüft wird

Tests prüfen Aufbau, Zugangsschutz, Aufräumen und Exit-Codes ohne Netz; die echte Zustellung wird nur live in /e2e-verify nachgewiesen.

## Kritische Anmerkungen

- Das im Ticket verlangte Szenario „Ausblick ohne Winddaten" wird nicht auf Staging gebaut, sondern nur als Grenze dokumentiert und lokal belegt.
- Das kompakte Mail-Format ist nur abgedeckt, falls es per Staging-Konfiguration setzbar ist; sonst nur lokal belegt.

## Freigabe-Frage

Akzeptierst du, dass der Fall „Ausblick ohne Winddaten" nur lokal und nicht auf Staging geprüft wird?

## Ampel

Ampel: rot
