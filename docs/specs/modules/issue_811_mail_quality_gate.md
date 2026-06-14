---
entity_id: issue_811_mail_quality_gate
type: module
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [tooling, gate, mail, quality, enforcement]
---

# Issue #811 — Briefing-Mail-Qualität erzwingen

## Approval

- [ ] Approved

## Purpose

Erzwingungs-**Infrastruktur** (kein Inhalts-Fix), die Mail-Defekte wie #806/#807/#808/#810
künftig vor dem Merge fängt: ein **Artefakt-Vertragstest** gegen die echt gerenderte
Briefing-Mail über die Matrix `{full, compact} × {Einfach, Roh}` und ein
**un-überspringbarer Renderer-Gate**, der Commits am Mail-Inhalts-Pfad blockiert, bis der
Vertragstest grün lief **und** ein `briefing_mail_validator.py`-Erfolgsnachweis im aktiven
Workflow hinterlegt ist. Macht die heute folgenlose CLAUDE.md-„PFLICHT" technisch durchsetzbar.

## Source

- **Datei (neu):** `tests/tdd/test_issue_811_mode_matrix.py` — Komponente A (Vertragstest)
- **Datei (neu):** `.claude/hooks/renderer_mail_gate.py` — Komponente B (Gate + Nachweis-Recorder)
- **Datei (Änderung):** `.claude/settings.json` — Hook in der Bash/`git commit`-Kette registrieren
- **Datei (Änderung):** `openspec.yaml` — `renderer_mail_gate.py` als `e2e_validators` schützen
- **Identifier:** `render_email` (`src/output/renderers/email/__init__.py`), `fmt_val`/`ampel_dot` (`helpers.py`)

> **Schicht:** Reines **Tooling/Test** (Python-Hooks + pytest). Keine Frontend-/Go-/produktive
> Python-Backend-Änderung. Der Vertragstest ruft den **echten** Python-Renderer `render_email`
> auf (`src/output/renderers/email/`).

## Estimated Scope

- **LoC:** ~280 (Vertragstest ~120, Gate-Hook ~140, settings.json/openspec.yaml ~20) → **loc_limit_override 400**
- **Files:** 2 neu, 2 geändert
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `render_email` (`src/output/renderers/email/__init__.py`) | Python | echter Render-Einstieg, gibt `(html, plain)` |
| `briefing_mail_validator.py` | Hook | Validator-Erfolgs-Log (`.claude/workflows/_log/*_briefing_validation.yaml`, Feld `passed`) |
| `workflow_state_multi.py` | Hook | aktiver Workflow + State-Datei (`get_active_workflow`) |
| `pre_commit_gate.py` | Hook | Vorbild: `git diff --cached --name-only`, Exit 2 blockiert |

## Implementation Details

### Komponente A — Modus-Matrix-Vertragstest (`tests/tdd/test_issue_811_mode_matrix.py`)

```
Realistisches Fixture (eine Etappe, Stundentabelle mit wind/gust/precip/pop/temp/
cloud/sunshine/cape-Werten oberhalb der Gelb-Schwellen, damit jede fmt_val-Verzweigung
greift) via build_default_display_config + dp_to_row (mock-frei).

Parametrisierung: format ∈ {full, compact} × modus ∈ {Einfach(use_friendly), Roh(raw)}
                  × variante ∈ {briefing (changes=None), alert/"Update" (changes=[WeatherChange,...])}.
Pro Fall: render_email(...) ECHT aufrufen → (html, plain).

Begründung der Alert-Variante: Die Alert-/„Update"-Mail (Wetteränderung) läuft über
format_email (src/formatters/trip_report.py:76) → DENSELBEN render_email → fmt_val/ampel_dot
wie das Briefing (Aufruf aus src/services/trip_alert.py:664). Sie hat damit exakt dasselbe
#810-Risiko und muss vom Vertrag mit-abgedeckt werden — inkl. des zusätzlichen Änderungs-Blocks
(html.py:230 `changes`). Der Radar-Alert (trip_alert.py:565, format_now_text) ist reiner Text
ohne Metrik-Tabelle/Ampel → nicht #810-anfällig, außen vor.

Vertrag (nicht Einzelwerte):
- Roh + full (HTML): KEIN Ampel-Emoji 🟢🟡🟠🔴 in den Daten-Zellen der Stundentabelle;
  jede aktivierte Metrik-Zelle ist ein Zahl-/Einheit-Token. (Gegenprobe: plain numerisch.)
- Einfach + full (HTML): Ampel/Indikator vorhanden, wo spezifiziert (≥1 Ampel-Emoji).
- compact (beide Modi): reines ASCII, KEIN Emoji, keine Stundentabelle.
- Abdeckung über die volle aktivierte Metrik-Liste (eine vergessene fmt_val-Verzweigung
  wie wind/gust/precip/pop in #810 wird garantiert rot).

#810-Reproduktion: Die Parametrisierungen „Roh + full" für wind/gust/precip/pop sind
mit @pytest.mark.xfail(strict=True, reason="#810 — Roh-HTML-Ampel-Bug, GREEN nach Fix")
markiert. Tech-Lead-Entscheidung: #811 ist reine Infrastruktur; der Verhaltens-Fix #810
gehört in seinen eigenen Workflow (inkl. Anpassung des zementierenden 759-Tests). strict=True
erzwingt nach dem #810-Fix die Marker-Entfernung (xpass → Suite rot). Der RED-Beweis wird im
TDD-RED-Artefakt OHNE Marker einmal festgehalten (Test fängt #810 nachweislich).
```

### Komponente B — Renderer-Gate (`.claude/hooks/renderer_mail_gate.py`)

```
Geschützte Mail-Inhalts-Pfade (Regex):
  src/output/renderers/email/.*\.py$
  src/formatters/.*\.py$
  src/outputs/email\.py$

Hook-Modus (registriert in settings.json PreToolUse → Bash-Matcher, Kette nach
pre_commit_gate): stdin-JSON mit tool_input.command == "git commit ...".
  1. staged Dateien lesen (git diff --cached --name-only).
  2. Berührt KEINE Mail-Inhalts-Datei → Exit 0 (no-op).
  3. Aktiven Workflow laden (GZ_ACTIVE_WORKFLOW → .claude/workflows/<name>.json).
  4. Nachweis prüfen (beide Pflicht):
     (a) Matrix-Test-Nachweis: workflow.state["gates"]["renderer_mail"]["matrix"]
         mit {passed: true, mail_files_hash: <sha256>}; der Hash MUSS dem sha256
         der aktuell gestagten Mail-Inhalts-Dateien entsprechen (Anti-Stale: jede
         Renderer-Änderung invalidiert den Nachweis → Test muss neu laufen).
     (b) Validator-Nachweis: jüngstes .claude/workflows/_log/*_briefing_validation.yaml
         mit workflow_id == aktiver Workflow UND passed: true UND validated_at frischer
         als der letzte Mail-Datei-mtime (Validator lief NACH der letzten Renderer-Änderung).
  5. Beide vorhanden & gültig → Exit 0. Sonst → Exit 2 + stderr mit konkreter Abhilfe
     (welcher Nachweis fehlt, welches Kommando ihn erzeugt).

Recorder-Subkommando: `renderer_mail_gate.py record-matrix` — berechnet den sha256 der
Mail-Inhalts-Dateien und schreibt ihn nach state["gates"]["renderer_mail"]["matrix"].
Wird vom Vertragstest (Komponente A) bei grünem Lauf via Session-Teardown aufgerufen —
KEIN manuelles „ich verspreche"-Flag; der Nachweis entsteht nur durch den echten Testlauf.

Anti-Bypass (AC-3): Nachweis liegt AUSSCHLIESSLICH pro Workflow in .claude/workflows/<name>.json
(kein globales Flag, kein ENV-Override). Hash- bzw. mtime-Bindung verhindert stale Nachweise.
```

### settings.json / openspec.yaml

```
settings.json: neuen command-Hook in PreToolUse → Bash-Matcher-Kette einfügen
  (if [ -f .../renderer_mail_gate.py ]; then python3 .../renderer_mail_gate.py; fi).
openspec.yaml protected_paths: Pattern "\.claude/hooks/renderer_mail_gate\.py$"
  mit spec_type "e2e_validators" (darf nicht ohne Workflow geschwächt werden).
```

## Expected Behavior

- **Input:** Commit, der eine Mail-Inhalts-Datei staged; aktiver Workflow-State.
- **Output:** Exit 0 (Nachweise vollständig & frisch) ODER Exit 2 + handlungsleitende stderr-Meldung.
- **Side effects:** Recorder schreibt `gates.renderer_mail.matrix` in die Workflow-State-Datei.

## Acceptance Criteria

- **AC-1:** Given ein realistisches Mail-Fixture / When der parametrisierte Test die echte
  Mail in `{full,compact}×{Einfach,Roh}×{briefing, alert/Update}` über alle aktivierten
  Metriken rendert / Then er schlägt fehl, sobald in „Roh"+full eine Metrik-HTML-Zelle ein
  Ampel-Emoji 🟢🟡🟠🔴 statt einer Zahl zeigt — **für beide Versandvarianten** (Briefing UND
  Alert/„Update", da beide denselben render_email-Pfad nutzen); die #810-Parametrisierungen
  (wind/gust/precip/pop, Roh+full) sind `xfail(strict=True)` und flippen nach dem #810-Fix.
  - Test: `tests/tdd/test_issue_811_mode_matrix.py` — echter `render_email`-Aufruf (briefing:
    `changes=None`; alert: `changes=[WeatherChange,...]`), Emoji-Scan der HTML-Datenzellen;
    ohne xfail-Marker reproduziert die Roh+full-Parametrisierung #810 RED.
- **AC-2:** Given ein Commit, der `src/output/renderers/email/*`, `src/formatters/*` oder
  `src/outputs/email.py` staged / When im aktiven Workflow KEIN gültiger Matrix-Test-Nachweis
  ODER kein `briefing_mail_validator.py`-Erfolgsnachweis vorliegt / Then blockiert der Hook den
  Commit mit Exit 2 und nennt den fehlenden Nachweis.
  - Test: Echtes Temp-Git-Repo, Mail-Datei stagen, `renderer_mail_gate.py` als Subprozess mit
    git-commit-stdin → Exit 2; nach Hinterlegung beider Nachweise → Exit 0. Commit, der KEINE
    Mail-Datei berührt → Exit 0 (kein False-Positive).
- **AC-3:** Given ein hinterlegter Nachweis / When er geprüft wird / Then er ist
  ausschließlich an den aktiven Workflow gebunden (in `.claude/workflows/<name>.json`, kein
  globaler Bypass) und wird durch eine spätere Renderer-Änderung invalidiert (Hash-/mtime-Bindung).
  - Test: Nachweis hinterlegen → Mail-Datei ändern → Gate blockiert erneut (Hash mismatch);
    Nachweis ist nicht über ENV/globales Flag erzeugbar.
> Die drei ACs oben (AC-1..AC-3) sind die **bindenden** Akzeptanzkriterien dieses Tickets.

## Optional / Spätere Erweiterung (nicht bindend)

- **C (Golden-HTML-Snapshots):** Für je ein full- und ein compact-Fixture in beiden Modi wird das
  gerenderte HTML als Golden-Snapshot abgelegt; eine Renderer-Änderung ohne aktualisierten Golden
  schlägt fehl (bewusste Abnahme bei Diff). Nur umzusetzen, wenn das LoC-Budget es zulässt — als
  eigenes Folge-Issue, falls gewünscht.

## Out of Scope

- Inhalts-Fixes #806/#807/#808/#810 — dieses Ticket liefert nur die Erzwingungs-Infrastruktur.
- Golden-HTML-Snapshots (C) — optional, nicht in diesem Ticket umgesetzt.
