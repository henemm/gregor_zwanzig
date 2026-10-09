---
spec_file: docs/specs/bugfix/interne_endpunkte_core_auth.md
spec_sha256: 90627c3fb9e54be1a964aa376a70a7c9b9f69113cb4990f8483790260ff8b4d9
---

# PO-Briefing: fix-2159-interne-endpunkte-secret

- **Spec:** docs/specs/bugfix/interne_endpunkte_core_auth.md
- **Issue:** #2159
- **Erstellt:** 2026-10-09

## Was gebaut wird

Zwei interne Schnittstellen (Telegram verknüpfen, Premium-SMS lernen) akzeptieren nur noch Aufrufe mit dem gemeinsamen Geheimnis.

## Definition of Done

Aufrufe ohne oder mit falschem Geheimnis werden abgelehnt und ändern keine Nutzerdaten; Telegram-Verknüpfung und Premium-SMS-Lernen funktionieren mit Geheimnis weiter wie bisher.

## Wie geprüft wird

Automatische Tests mit echtem Router und lokalen Testservern beweisen Ablehnung und Weiterbetrieb; ob der Vergleich zeitkonstant ist, wird nicht gemessen.

## Kritische Anmerkungen

- Ohne manuellen Eintrag in der Staging-Konfiguration scheitern dort Telegram-Verknüpfung und SMS-Lernen; das liegt außerhalb des Codes.
- Nicht verlangt: Staging-Fehlverbindung zur Produktion wird mitbehoben und ein Health-Feld ergänzt.
- Dokumentations-Anforderung (AC-12) hat keinen automatischen Test. Prüfung nur im Review.

## Freigabe-Frage

Soll die Spec inklusive der mitgenommenen Härtungen aus #2163 und der Staging-Korrektur freigegeben werden?
