---
entity_id: issue_1207_versand_orchestrator
type: bugfix
created: 2026-07-16
updated: 2026-07-16
status: approved
version: "3.0"
tags: [compare, dispatch-orchestrator, rate-limit]
workflow: feat-1207-compare-sendepause-fehler
---

<!-- Issue #1207 — DRITTE Fassung. Zwei Vorfassungen wurden zurueckgezogen,
     weil parallele Sessions denselben Zielbereich schneller geliefert haben
     (#1270, dann 3ca3be14). Siehe Changelog — die Historie ist bewusst
     erhalten, sie ist die eigentliche Lehre dieses Issues. -->

# Compare-Sendepause: `inter_mail_delay` 0 → 2.0 (#1207)

## Approval

- [x] Approved — PO-Freigabe 2026-07-16 (getipptes „go" auf die Spec-Zusammenfassung)

## Purpose

Der Compare-Briefing-Versand pausiert nicht zwischen zwei Mails. Der Trip-Versand
tut das seit #766 (2 Sekunden, Rate-Limit-Schutz). Seit **#1270** versendet
Compare **drei Kanäle** (E-Mail + Telegram + SMS) pro Preset — bei mehreren zur
selben vollen Stunde fälligen Abos entsteht ein Burst gegen Resend/Telegram ohne
jede Drosselung.

`3ca3be14 refactor(#1207)` hat den geteilten Orchestrator
(`src/services/dispatch_orchestrator.py`) gebaut und die Pause-Mechanik bereits
korrekt implementiert (`run_briefing_dispatch:179-183`, inkl. „nicht nach der
letzten"). Nur der Wert der Compare-Strategie steht auf `0` — dort als bewusstes
Non-Goal, weil jener Commit ein **verhaltensneutraler Refactor** war.

**Diese Spec revidiert genau dieses eine Non-Goal.**

## Source

- **Datei:** `src/services/dispatch_orchestrator.py:92`
- **Identifier:** `CompareDispatchStrategy.inter_mail_delay`
- **Mechanik (unverändert, bereits vorhanden):** `run_briefing_dispatch:179-183`
- **Vorbild:** `TripDispatchStrategy.inter_mail_delay = 2.0` (`:41`)

## Scope

### Affected Files

| Datei | Art | Änderung |
|---|---|---|
| `src/services/dispatch_orchestrator.py` | Python | `inter_mail_delay: 0` → `2.0`; Docstring + Schleifen-Kommentar |
| `docs/specs/modules/dispatch_orchestrator.md` | Doku | Non-Goal-Zeile durchgestrichen (nicht gelöscht) + Changelog |
| `tests/tdd/test_dispatch_orchestrator.py` | Test | `test_compare_inter_mail_delay_is_zero` → `..._is_two_seconds`; neuer Verhaltens-Test |

### Estimated Changes

- Anrechenbar: **+3 LoC** (Produktivcode). Doku zählt nicht.

## Acceptance Criteria

**AC-1:** Given zwei im selben Lauf fällige Compare-Presets, When
`run_briefing_dispatch` sie versendet, Then liegt zwischen den beiden Sends eine
Pause von ~2 Sekunden — gemessen an echter Wanduhr, nicht an einem gemockten
`sleep`.

**AC-2:** Given ein einzelnes fälliges Compare-Preset, When der Lauf es
versendet, Then wird **nach** dem letzten Send **nicht** pausiert (die
bestehende `if i < len(due) - 1`-Mechanik bleibt unangetastet).

**AC-3:** Given `TripDispatchStrategy`, When `AC-1` umgesetzt wird, Then bleibt
der Trip-Pfad unverändert bei 2.0s und alle bestehenden Trip-Tests grün ohne
Anpassung.

**AC-4:** Given jemand setzt `CompareDispatchStrategy.inter_mail_delay` später
wieder auf 0, When die Testsuite läuft, Then wird sie rot — der Verhaltens-Test
**erbt** den Produktivwert, statt ihn zu duplizieren.

**AC-5:** Given die frühere Non-Goal-Entscheidung aus `3ca3be14`, When sie
revidiert wird, Then bleibt sie in `dispatch_orchestrator.md` sichtbar
(durchgestrichen, mit Datum, PO-Bezug und Begründung) — nicht gelöscht.

## Edge Cases

| Fall | Verhalten |
|---|---|
| Genau ein fälliges Preset | keine Pause (`AC-2`) |
| Null fällige Presets | Schleife läuft nicht, keine Pause |
| Preset-Versand wirft | Fehler-Isolation bleibt wie gebaut (`3ca3be14`); die Pause-Mechanik ist davon unberührt |
| Viele Presets zur selben Stunde | jeweils 2s Abstand — das ist der Zweck |

## Known Limitations

- **Verschluckte Fehler bleiben.** `run_compare_presets_daily` liefert weiter
  `-> int` und meldet nur Erfolge; Störungen sind in `/api/scheduler/status`
  unsichtbar. `3ca3be14` hat das als Non-Goal dokumentiert („Status-Semantik:
  beide Tally-Formen bleiben 1:1 erhalten"). **Bewusst nicht Teil dieser Spec** —
  der Rückgabe-Vertrag zu ändern zieht fünf Testdateien mit und gehört nicht in
  einen Drei-Zeilen-Fix. Offener Punkt an #1207.
- **Der Testlauf dauert ~2s länger.** Der ehrliche Preis eines echten
  Wanduhr-Nachweises statt eines gemockten `sleep`.
- **Fälligkeitslogik bleibt doppelt** (Trip inline vs. `presets_due_for_hour`) —
  descoped, s. `docs/context/feat-1207-versand-orchestrator.md` „Naht B".
- **Renderer-Templates bleiben getrennt** — E9 aus #1230, ausdrücklich gewollt.

## Changelog

- **2026-07-16 v3.0** — Neufassung auf `inter_mail_delay 0 → 2.0`. Grund:
  `3ca3be14 refactor(#1207)` (14:52) hat den Orchestrator-Rahmen samt
  Pause-Mechanik geliefert; die Änderung schrumpft damit von ~90 LoC auf 3.
  Die Fehler-Semantik wird als offener Punkt abgetrennt.
- **2026-07-16 v2.0 — ZURÜCKGEZOGEN.** Fassung „Sendepause + sichtbare Fehler"
  mit eigenem Modul `mail_dispatch_pacing.py` und `(sent, failed)`-Vertrag.
  Überholt von `3ca3be14`, das den Orchestrator anders und besser schnitt. Die
  Arbeit (+45 LoC, 8 grüne Tests) wurde verworfen, weil sie fremde Arbeit
  teilweise revertiert hätte.
- **2026-07-16 v1.0 — ZURÜCKGEZOGEN.** Fassung „S1 NotificationService-Anbindung
  + S3 Compare-Fahrtenbuch + ADR-Entwurf". S1 war bereits durch **#1270**
  geliefert (`NotificationService.send_compare_report`, `:597`) — die Spec
  entstand auf einem 8 Commits veralteten Stand und hätte ein Duplikat erzeugt.
  Die damals vorgesehene ADR-Nummer 0024 ist inzwischen an #1272 vergeben und
  hat mit diesem Issue nichts zu tun.
- **Lehre (dokumentiert in `feedback_refetch_before_spec_and_implement`):** Bei
  parallelen Sessions verfällt ein Codestand binnen Stunden. `git fetch` gehört
  an den Anfang **jeder Phase**, nicht der Session.
