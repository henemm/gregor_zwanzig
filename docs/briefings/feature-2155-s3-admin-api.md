---
spec_file: docs/specs/modules/admin_rolle_s3_admin_api.md
spec_sha256: d422bd4a2b495277a46ae3e47eab8635cc8c12c4d6b9c3f2cb69dfa4ba896682
---

# PO-Briefing: feature-2155-s3-admin-api

- **Spec:** docs/specs/modules/admin_rolle_s3_admin_api.md
- **Issue:** #2155
- **Erstellt:** 2026-09-29

## Was gebaut wird

Ein Admin kann Nutzer auflisten, deren Tarifstufe ändern und Konten sperren; gesperrte Konten erhalten und bewirken nichts mehr.

## Definition of Done

Nur Admins erreichen die drei Funktionen; ein gesperrtes Konto kann sich nicht anmelden, bekommt keine Briefings und Befehle werden ignoriert.

## Wie geprüft wird

Automatische Tests mit zwei Nutzern prüfen alle Kriterien außer dem Staging-Nachweis, der von Hand erfolgt.

## Kritische Anmerkungen

- Zusatz: Sperre wirkt auch auf Briefings und Befehle; im Issue standen nur Liste, Tarifstufe, Sperre.
- Restrisiko: Gleichzeitiges Speichern durch den Nutzer kann eine Sperre still aufheben; kein Schutz vorgesehen.
- Staging-Nachweis ist manuell, nicht automatisiert.

## Freigabe-Frage

Ist die umfassende Sperre samt dem Restrisiko einer selten verlorenen Sperre für dich freigabefähig?
