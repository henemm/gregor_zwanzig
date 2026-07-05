# Konzept: Mitarbeit von Kimi (Kimi Code CLI) an Migration & Refactoring

**Status:** Konzept, PO-Freigabe ausstehend
**Autor:** Claude (Tech Lead), 2026-07-05
**Bezug:** `docs/project/architektur-roadmap-2026-07.md`, `docs/analysis/architektur-drift-2026-07-05.md`

## 1. Ausgangslage und Grundidee

Die Drift-Analyse hat gezeigt: Kimi liefert **präzise Faktenarbeit** (Zahlen fast durchgehend
exakt), aber **ohne Kenntnis der Projekt-Kontexte** (Gate-System in `.claude/`, ADR-Geltungsbereiche,
bewusste PO-Entscheidungen wie „keine Mocks"). Daraus folgt das Grundmuster:

> **Kimi produziert, Claude verifiziert und integriert, der PO entscheidet.**

Kimi arbeitet außerhalb des Claude-Code-Harness. Alle Qualitäts-Gates dieses Projekts
(OpenSpec-Workflow, Worktree-Pflicht, Adversary, Mail-Validatoren, Staging-Gates, Commit-Hooks)
sind an dieses Harness gebunden — für Kimi greifen sie **nicht automatisch**. Deshalb darf
Kimi-Arbeit `main` nie direkt erreichen; die Integration läuft immer durch die bestehende
Gate-Kette.

## 2. Rollenmodell

| Rolle | Wer | Was |
|-------|-----|-----|
| Analyst / Reviewer | Kimi | Read-only-Analysen, Drift-Reports, Code-Reviews, Refactoring-Vorschläge |
| Implementierer (begrenzt) | Kimi | Mechanische, testgesicherte Refactorings in eigenem Branch |
| Verifikation & Integration | Claude | Gegencheck jeder Analyse; Validierung, Staging-Nachweise, Merge, Deploy |
| Entscheidungen | PO | Zielarchitektur, ADRs, Priorisierung, Freigaben |

## 3. Drei Arbeitsformen

### 3.1 Analyse-Aufträge (sofort einsetzbar, geringstes Risiko)

Genau das Muster der Drift-Analyse — mit einer Pflicht-Ergänzung:

- **Auftrag:** als GitHub Issue mit Scope (z. B. „Duplikat-Analyse `src/formatters/` vs.
  `src/output/renderers/`").
- **Ergebnis:** Markdown-Report nach `docs/analysis/<thema>-<datum>.md`, jede Behauptung mit
  Beleg (`datei:zeile`, Kommando, Zählung).
- **Pflicht-Gegencheck:** Vor jeder Entscheidung auf Basis eines Kimi-Reports verifiziert Claude
  die Kernbehauptungen am Code und schreibt eine Revision (wie Rev. 2 der Drift-Analyse). Der
  ungeprüfte Report ist **keine** Entscheidungsgrundlage.
- **Kontext-Paket:** Kimi bekommt im Auftrag explizit die Pflicht-Lektüre genannt:
  `AGENTS.md`, betroffene ADRs (`docs/adr/`), und den Hinweis, dass die Qualitätssicherung in
  `.claude/` liegt (nicht nur `ci.yml`) und `tests/tdd/` bewusst staging-gebunden ist. Das
  adressiert die beiden blinden Flecken der ersten Analyse.

### 3.2 Code-Review (zweite Meinung)

- Kimi reviewt Diffs/PRs zu Refactoring-Issues und postet Findings als Issue-/PR-Kommentar
  (Format: Behauptung + `datei:zeile` + konkretes Fehlerszenario).
- Einsatz gezielt bei großen mechanischen Diffs (z. B. Store-Split), wo ein zweites Augenpaar
  Umbenennungs-/Vergessens-Fehler findet.
- Findings sind Input, kein Gate: Claude entscheidet pro Finding (fix/ablehnen mit Begründung).

### 3.3 Mechanische Refactorings (nach bewährtem Ablauf in 3.1/3.2)

Nur Aufgaben, die **alle vier** Kriterien erfüllen:

1. **Verhaltensneutral** (reine Struktur: Dateien aufteilen, Duplikate zusammenführen,
   Imports umhängen).
2. **Testgesichert:** vorhandene Tests decken das Verhalten ab und laufen ohne Staging-Creds
   (Go-Tests, Frontend-Unit-Tests, secrets-freie Python-Tests).
3. **Gate-frei:** berührt keine Pfade mit Sondergates (kein `src/output/renderers/email/`,
   `src/formatters/`, `src/outputs/email.py` → `renderer_mail_gate`; keine Schema-Dateien →
   `data_schema_backup`; nichts unter `.claude/`).
4. **Klein geschnitten:** ein Issue, ein Branch, Diff in einer Review-Sitzung erfassbar
   (Richtwert ≤ 250 geänderte Zeilen, analog zum Workflow-LoC-Limit).

**Geeignete Pakete aus der Roadmap:**

| Paket | Phase | Warum geeignet |
|-------|-------|----------------|
| `internal/store/store.go` in Entitäts-Dateien aufteilen | 1.1 | 51 Go-Testdateien als Netz, reine Dateiorganisation |
| Router-Auszug aus `cmd/server/main.go` | 1.2 | mechanisch, Go-Tests |
| Frontend-API-Base zentralisieren (20 Duplikate) | 3.1 | Unit-Tests + `svelte-check` als Netz |
| `svelte-check`-Fehler abbauen (40 → 0) | 3.2 | objektiv messbar, kein Verhalten |
| `haversine`/`degrees_to_compass` deduplizieren | 2.5 | klein, per Test abgedeckt — **Ausnahme prüfen:** berührt `formatters/` → dann Claude |

**Ungeeignet für Kimi (bei Claude bleibend):** alles mit Staging-/Kanal-Nachweispflicht
(Mail-Renderer, Telegram, SMS), Scheduler-/Alert-Logik, Auth/Mandantentrennung, Deploy,
Gate-/Hook-Dateien, ADR-pflichtige Strukturentscheidungen.

## 4. Technischer Ablauf für Implementierungs-Aufträge

1. **Issue** beschreibt Scope, Nicht-Ziele, betroffene Tests, Definition of Done.
2. **Arbeitskopie:** Kimi arbeitet in einem eigenen isolierten Workspace
   (`bash .claude/tools/gz-workspace new kimi-<issue>` → Branch `ws/kimi-<issue>`) —
   **niemals** im Haupt-Working-Tree `/home/hem/gregor_zwanzig` (dort laufen Produktion und
   Claude-Sessions; die Ein-Session-Regel gilt sinngemäß auch für Kimi).
3. **Harte Verbote für Kimi** (im Auftragstext wiederholen):
   - kein `git push` nach `main`, kein Merge, kein Deploy;
   - keine Änderungen unter `.claude/`, an Workflow-State, Gates oder `e2e_verified.json`;
   - kein Zugriff auf Secrets/Creds (`validator.env*`, `.env`, `/etc/henemm/secrets.env`);
   - keine Läufe gegen Produktion; keine Test-Mails/-Telegram-Sends (Live-Sends sind ohnehin
     opt-in, `GZ_TELEGRAM_LIVE=1` bleibt ungesetzt);
   - kein `git stash`, kein `git add -A` (geteilte Repo-Umgebung).
4. **Abgabe:** Branch gepusht (`ws/kimi-<issue>`), Testlauf-Protokoll im Issue-Kommentar.
5. **Integration durch Claude:** Review + Gegencheck → Rebase auf `origin/main` → Tests →
   Push nach `main` → Staging-Validierung → Prod-Deploy → Issue-Close. Damit durchläuft
   Kimi-Code exakt dieselbe Gate-Kette wie jede andere Änderung.

## 5. Definition of Done (für jeden Kimi-Auftrag)

- Analyse: Report liegt in `docs/analysis/`, Claude-Gegencheck (Revision) existiert.
- Implementierung: betroffene Tests grün (protokolliert), Diff ≤ Scope des Issues,
  Claude-Review bestanden, über Staging verifiziert und in Produktion.
- In beiden Fällen: **Issue geschlossen erst nach End-to-End-Abschluss** (Projektregel).

## 6. Eskalation

- Widerspricht ein Claude-Gegencheck einem Kimi-Befund → beide Fassungen mit Begründung an den
  PO; der Report wird korrigiert (wie Rev. 2), nicht gelöscht.
- Braucht ein Kimi-Paket doch Staging-Nachweise oder ADR → Paket zurück an Claude, Issue bleibt
  offen, Zuschnitt wird korrigiert.
- Kimi-Branch kollidiert mit parallel gelandeter Arbeit → Claude rebased; bei inhaltlichem
  Konflikt neuer Zuschnitt statt Force-Lösung.

## 7. Einstiegspfad (Empfehlung)

1. **Jetzt:** Arbeitsform 3.1 (Analysen) produktiv nutzen — sie hat sich bewiesen.
2. **Nach Phase 0 der Roadmap:** ein Pilot-Paket aus 3.3 (Vorschlag: Store-Split, Phase 1.1),
   eng geschnitten, mit vollem Review.
3. **Danach:** Umfang je nach Pilot-Ergebnis erweitern oder auf Analyse/Review begrenzen.
