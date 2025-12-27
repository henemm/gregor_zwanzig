# Documentation - Gregor Zwanzig

Diese Dokumentation folgt der **OpenSpec-Struktur** fuer spec-first Entwicklung.

## Struktur

```
docs/
├── specs/              # Entity-Spezifikationen
│   ├── modules/        # Modul-Specs (CLI, Provider, Engine, etc.)
│   ├── functions/      # Einzelne Funktions-Specs
│   └── _template.md    # Spec-Template
│
├── reference/          # Technische Referenz
│   ├── api_contract.md # Datenstrukturen & DTOs
│   ├── provider_mapping.md
│   ├── decision_matrix.md
│   ├── symbol_mapping.md
│   ├── sms_format.md
│   ├── debug_format.md
│   └── renderer_email_spec.md
│
├── features/           # Feature-Dokumentation
│   ├── scope.md        # Projektvision & Scope
│   ├── architecture.md # Systemarchitektur
│   └── cli_spec.md     # CLI-Spezifikation
│
└── project/            # Projekt-Management
    └── backlog.md      # Backlog (PO-Ansicht)
```

## Workflow

Dieses Projekt nutzt den **OpenSpec 4-Phasen-Workflow**:

1. `/analyse` - Request verstehen, Codebase recherchieren
2. `/write-spec` - Spezifikation erstellen
3. User: "approved" - Spec freigeben
4. `/implement` - Implementieren nach Spec
5. `/validate` - Validieren vor Commit

## Quick Links

### Specs (Module)
- [CLI](specs/modules/cli.md) - Einstiegspunkt
- [SMTP Mailer](specs/modules/smtp_mailer.md) - E-Mail-Versand
- [DebugBuffer](specs/modules/debug_buffer.md) - Debug-Sammlung
- [Provider MET](specs/modules/provider_met.md) - MET Norway Adapter (draft)
- [Provider MOSMIX](specs/modules/provider_mosmix.md) - DWD Adapter (draft)
- [Risk Engine](specs/modules/risk_engine.md) - Risiko-Bewertung (draft)
- [Report Formatter](specs/modules/report_formatter.md) - Report-Generierung (draft)

### Reference
- [API Contract](reference/api_contract.md) - Single Source of Truth fuer Datenformate
- [Decision Matrix](reference/decision_matrix.md) - Provider-Auswahl-Regeln

### Features
- [Scope](features/scope.md) - Was ist Gregor Zwanzig?
- [Architecture](features/architecture.md) - Wie ist es aufgebaut?
