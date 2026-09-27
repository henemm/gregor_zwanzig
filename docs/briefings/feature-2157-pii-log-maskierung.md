---
spec_file: docs/specs/modules/pii_log_masking.md
spec_sha256: a49e2627968db932347295738c7483f4271d71837a236b8a47ad4ddb56c7d395
---

# PO-Briefing: feature-2157-pii-log-maskierung

- **Spec:** docs/specs/modules/pii_log_masking.md
- **Issue:** #2157
- **Erstellt:** 2026-09-27

## Was gebaut wird

E-Mail-Adressen und Telegram-Kennungen werden in Protokollen und Logs automatisch maskiert statt im Klartext gespeichert.

## Definition of Done

Neue Fremdnutzer-Adressen und Chat-IDs erscheinen in Server-Protokollen nur noch verkürzt; zwei bekannte interne Testadressen bleiben lesbar — bei mehreren Adressen in einem Feld wird jede einzeln geprüft, an jeder betroffenen Stelle.

## Wie geprüft wird

Tests prüfen konkrete Protokollzeilen und einen Namens-Wächter gegen neuen Code. Eine unabhängige Gegenprüfung fand zwei weitere betroffene Stellen und zwei fehlende Tests — beide ergänzt.

## Kritische Anmerkungen

- Zwei interne Testadressen bleiben bewusst im Klartext — "überall maskiert" gilt nicht ausnahmslos.
- Ticket verlangte Hash statt Verkürzung für gespeicherte Adressen; Spec nutzt dieselbe Verkürzung wie in den Protokollen.
- Nachträglich ohne neue Entscheidung ergänzt: drei weitere Chat-ID-Stellen, eine Formkorrektur der Kriterien, sowie mehrere Fundstellen derselben Mehrfach-Adressen-Lücke — zuletzt zwei zusätzliche, von einer Gegenprüfung gefundene Stellen im Versand-Code plus zwei ergänzte Tests.

## Freigabe-Frage

Sind die zwei internen Testadressen im Klartext und die Verkürzung statt Hash für gespeicherte Adressen für Sie akzeptabel?
