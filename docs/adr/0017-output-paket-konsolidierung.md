# ADR-0017: Ein Output-Paket — `src/output/` mit `renderers/` und `channels/`, `formatters/` und `outputs/` aufgelöst

- **Status:** Akzeptiert (PO-„go" 2026-07-06)
- **Datum:** 2026-07-06
- **Bezug:** [ADR-0015](0015-dual-stack-zielarchitektur.md) (Python = Rendering-Owner),
  [ADR-0011](0011-alert-render-single-backend-renderer.md) (kanonischer Alert-Renderer),
  Roadmap Phase 2.5 (`docs/project/architektur-roadmap-2026-07.md`), Drift-Analyse Rev. 2
  Abschnitt 3.3, Issues #1022–#1024 (NotificationService als einziger Versand-Orchestrierer)

## Kontext

Die Ausgabe-Schicht des Python-Core ist historisch auf drei Top-Level-Pakete verteilt:

| Paket | Inhalt heute | Problem |
|-------|--------------|---------|
| `src/output/` | Renderer (`renderers/email`, `renderers/alert`, `renderers/sms`, `renderers/text_report`, `comparison.py`, `narrow.py`), `tokens/`, `adapters/`, `subject.py` | — (das ist die Zielstruktur) |
| `src/outputs/` | Transport-Kanäle: `email.py` (SMTP), `telegram.py` (Bot-API), `sms.py` (seven.io), `console.py`, `base.py` — plus eine verirrte Testdatei `test_email.py` | Singular/Plural-Verwechslung mit `output/`; Transport und Darstellung nicht unterscheidbar benannt |
| `src/formatters/` | `trip_report.py` (TripReportFormatter — orchestriert das komplette Briefing-Rendering), `sms_trip.py`, `compact_summary.py` | „weder Fisch noch Fleisch": faktisch Renderer-Orchestrierung, liegt aber außerhalb der Renderer-Struktur |

Seit #1022–#1024 ruft ausschließlich der `NotificationService` Renderer und Transporte auf —
die Aufrufer-Seite ist bereits konsolidiert. Was fehlt, ist die konsistente Ablage der
aufgerufenen Bausteine. Umbau-Radius (Import-Zählung 2026-07-06): `from outputs` in 43,
`formatters` in 57, `from output.` in 56 Dateien — der Umzug ist rein mechanisch, aber breit.

## Entscheidung

**Ein einziges Ausgabe-Paket `src/output/` mit zwei klar benannten Unterschichten:**

```
src/output/
├── renderers/     # Darstellung: erzeugt Inhalte (HTML, Plain, Bubbles, SMS-Wire, Subjects)
│   ├── email/  alert/  sms/  text_report/
│   ├── comparison.py  narrow.py  channel_layout.py
│   ├── trip_report.py      ← aus src/formatters/trip_report.py
│   ├── sms_trip.py         ← aus src/formatters/sms_trip.py
│   └── compact_summary.py  ← aus src/formatters/compact_summary.py
├── channels/      # Transport: versendet Inhalte
│   ├── email.py  telegram.py  sms.py  console.py  base.py   ← aus src/outputs/
├── tokens/  adapters/  subject.py   (unverändert)
```

- `src/outputs/` und `src/formatters/` werden **ersatzlos entfernt** (keine Import-Shims:
  alle Nutzer sind repo-intern, jeder Slice stellt seine Importe im selben Commit um).
- Merkregel: **renderers erzeugen, channels versenden.** Kein Modul in `channels/` baut
  Inhalte, kein Modul in `renderers/` öffnet Verbindungen.
- Die verirrte `src/outputs/test_email.py` zieht nach `tests/` um oder entfällt (Slice 3).

### Umsetzung in drei Slices (je ein Kimi-Auftrag, je ≤ Umbau eines Pakets)

| Slice | Inhalt | Pflicht-Nachweise |
|-------|--------|-------------------|
| 1 | `src/outputs/` → `src/output/channels/` + alle Import-/Patch-Ziel-Umstellungen | CI-äquivalent Exit 0; **Gate-Selbsttests grün**; Staging: Briefing-Send + briefing_mail_validator Exit 0 |
| 2 | `src/formatters/` → `src/output/renderers/` + Import-Umstellungen | wie Slice 1 + Modus-Matrix-Test |
| 3 | Aufräumen: leere Pakete löschen, `test_email.py` verlagern, Doku (`AGENTS.md`, architecture.md) nachziehen | CI-äquivalent Exit 0; Doku-Grep |

### Gate-Kopplung (härteste Randbedingung)

`renderer_mail_gate.py`, `briefing_mail_validator.py`/`email_spec_validator.py` und
`data_schema_backup`-Trigger referenzieren Pfadmuster (`src/output/renderers/email/*`,
`src/formatters/*`, `src/outputs/email.py`). **Im selben Commit wie jeder Umzug** werden die
Muster erweitert (Übergangsphase: alte UND neue Pfade), nach Slice 3 auf die neuen reduziert.
Ein Umzug ohne Muster-Nachzug wäre stiller Schutzverlust — deshalb gehört zu jedem Slice der
**Gate-Selbsttest** als Abnahme (z. B. `tests/tdd/test_issue_811_mode_matrix.py` +
Gate-eigene Tests). Gate-Änderungen sind Claude-Aufgabe (`.claude/` ist für Kimi tabu) —
Kimi liefert den Umzug, Claude zieht die Gate-Muster im Integrations-Commit nach.

## Verworfene Alternativen

- **Zwei Top-Level-Pakete `src/renderers/` + `src/channels/`** — verworfen: löst die
  Singular/Plural-Falle, erzeugt aber wieder zwei Wurzeln für eine Schicht; `output/`
  existiert bereits mit der richtigen Binnenstruktur, der Umzugsradius ist so am kleinsten.
- **`formatters/` behalten und nur `outputs/` umziehen** — verworfen: TripReportFormatter
  IST der Briefing-Renderer-Orchestrierer; ein drittes Paket bliebe unerklärbar.
- **Import-Shims/Deprecation-Phase** — verworfen: keine externen Konsumenten; Shims würden
  die Gate-Pfadmuster-Übergangsphase unnötig verlängern und Import-Drift kaschieren.
- **Nichts tun** — verworfen: die Verwechslungsgefahr `output`/`outputs` produziert
  nachweislich Fehler (Drift-Analyse 3.3; wiederholte Review-Befunde in Phase 2).

## Konsequenzen

- **Positiv:** Eine Wurzel für alles Ausgabe-Seitige; Paketname beantwortet „erzeugt oder
  versendet?"; Gate-Muster werden nach Slice 3 einfacher (ein Präfix statt drei).
- **Preis:** ~100 Dateien mit Import-Umstellungen (mechanisch, in 3 Slices, testgesichert);
  Test-Patch-Ziele ändern sich (`outputs.email` → `output.channels.email`) — betroffene
  Tests werden im selben Slice umgestellt (nur Patch-Ziele, keine Assertion-Änderungen).
- **Folgepflichten:** `AGENTS.md`/`architecture.md`-Pfadangaben (Slice 3); Merge-Fenster
  koordinieren (breite Renames kollidieren mit parallelen Sessions — Slices zügig
  integrieren); `docs/reference/mail_validators.md` Pfadangaben aktualisieren.
