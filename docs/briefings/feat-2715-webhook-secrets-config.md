---
spec_file: docs/specs/modules/webhook_secrets_config_2715.md
spec_sha256: 142dcf9dcbf8c3ac5303da96d4142c888312c76a0f44c9cf6a364abe7a846957
spec_frozen_sha256: 0d189b3ea6b83f9de33b664722a06f5e9945a9a3d99f67f5f8fb5da37ab0ca2e
---

# PO-Briefing: feat-2715-webhook-secrets-config

- **Spec:** docs/specs/modules/webhook_secrets_config_2715.md
- **Issue:** #2715
- **Erstellt:** 2026-10-31

## Was gebaut wird

Die Zugangsgeheimnisse der Eingänge für Telegram, SMS und E-Mail werden zentral konfiguriert; das Verhalten nach außen bleibt unverändert.

## Definition of Done

Auf Staging weisen Telegram-, SMS- und Mail-Eingang ein falsches Geheimnis mit 403 ab, und die Telegram-Verknüpfung funktioniert weiterhin.

## Wie geprüft wird

Automatische Tests prüfen Konfiguration und alle drei Eingänge (falsch, richtig, leer); der Praxistest auf Staging ist manuell, Prod wird nicht getestet.

## Kritische Anmerkungen

- Ein Tippfehler in der Konfiguration würde auf Prod alle drei Eingänge lahmlegen; Spec sichert das durch Tests und Staging-Nachweis ab.
- Spec nimmt SMS- und Mail-Eingang zusätzlich zu Telegram auf; das ist im Ticket benannt, daher keine Abweichung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
