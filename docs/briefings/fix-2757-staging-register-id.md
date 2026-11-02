---
spec_file: docs/specs/fast/fix-2757-staging-register-id.md
spec_sha256: 7b3da1dfaabe209a3a246c82bf6696d426b64dcea74b0c354cc79d15554059dd
spec_frozen_sha256: c5aa53cd9d70001198840519b98fa431bde6cad47eea01f7c6634a22b17d5486
---

# PO-Briefing: fix-2757-staging-register-id

- **Spec:** docs/specs/fast/fix-2757-staging-register-id.md
- **Issue:** #2757
- **Erstellt:** 2026-11-02

## Was gebaut wird

Das Staging-Prüfwerkzeug für E-Mail-Befehle funktioniert wieder, weil es die vom Server vergebene Nutzerkennung verwendet.

## Definition of Done

Der Staging-Lauf mit allen Szenarien geht durch, der Wegwerf-Nutzer ist danach gelöscht und das verwaiste Testkonto existiert nicht mehr.

## Wie geprüft wird

Automatische Tests mit realistischem Server-Verhalten fangen den Fehler; der echte Staging-Lauf und das Aufräumen des Altkontos werden nur manuell nachgewiesen.

## Kritische Anmerkungen

- Die Ursprungsanfrage konnte nur über den Titel geprüft werden, der Issue-Volltext war nicht lesbar; Abgleich daher begrenzt.
- Aufräumen des Altkontos (Löschung auf Staging) ist ein Zusatz ohne automatischen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
