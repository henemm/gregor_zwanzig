# Konzept: Mitarbeit von Kimi (Kimi Code CLI) an Migration & Refactoring

**Status:** Aktiv. PO-Entscheidung 2026-07-05: **Kimi übernimmt möglichst viel** — Kimi ist
Standard-Implementierer, Claude liefert Review, Gate-Nachweise und Integration (siehe 3.3).
Pilot #1021 (Store-Split) erfolgreich abgeschlossen. Aktuelle Warteschlange:
`docs/project/kimi-auftragsliste.md`.
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

### 3.3 Implementierung (Standard-Arbeitsform seit PO-Entscheidung 2026-07-05)

**Kimi implementiert standardmäßig alle Umsetzungsaufgaben** — auch solche, die Mail-/Kanal-
oder Scheduler-Pfade berühren. Die Grenze verläuft nicht mehr bei der Implementierung, sondern
bei **Nachweis und Integration**: Alles, was Staging-Creds, echte Kanäle oder Gates braucht,
erbringt Claude im Integrationsschritt (Abschnitt 4). Kimi kompensiert das, indem es lokal
alles Testbare beweist.

Anforderungen an jedes Kimi-Paket:

1. **Ein Issue, ein Branch, klein geschnitten** (Richtwert ≤ 250 geänderte Zeilen — Pflicht,
   nicht Richtwert, wenn Mail-Pfade berührt sind).
2. **Lokal beweisbar:** Kimi führt alle ohne Secrets lauffähigen Tests aus (Go-Tests,
   Frontend-Unit-Tests, lokale Python-/Vertragstests wie
   `tests/tdd/test_issue_811_mode_matrix.py`) und liefert das Protokoll mit ab.
3. **Verhaltensneutralität begründen:** Bei Refactorings gehört zur Abgabe eine Aussage, WARUM
   das Verhalten unverändert ist (z. B. „reine Verschiebung, Beweis: identisches
   Funktions-Inventar"), nicht nur „Tests grün".
4. **Staging-pflichtige Nachweise NICHT simulieren:** Kimi versucht nie, Mail-/Telegram-/
   SMS-Zustellung selbst auszulösen oder Validator-Läufe zu faken — das ist explizit Claudes
   Schritt.

**Bei Claude verbleiben nur noch:** Gate-Nachweise + Staging-Validierung + Deploy + Issue-Close,
Änderungen an Gate-/Hook-Dateien selbst (`.claude/`), ADR-/Architektur-**Entscheidungen**
(Kimi setzt beschlossene ADRs um), und Sicherheitsthemen mit Live-Proben (z. B. #1019-Verifikation
am echten Kanal — den Fix danach kann wieder Kimi bauen).

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

## 7. Stand & Warteschlange

- **Pilot bestanden:** Store-Split #1021 (2026-07-05) — rein mechanisch bewiesen, live in Prod.
  Briefing-Lehren daraus: „Push" = Branch `ws/kimi-<issue>` ins lokale Hauptrepo
  (`origin` des Workspace), **kein** GitHub; Test-Protokolle als unversionierte Datei im
  Workspace-Root (`TESTLOG.md`), nicht committen.
- **PO-Entscheidung:** Kimi übernimmt möglichst viel (Standard-Implementierer, siehe 3.3).
- **Aktuelle Aufträge:** `docs/project/kimi-auftragsliste.md` — der Reihe nach abarbeiten,
  abhängige Aufträge erst nach Integration des Vorgängers durch Claude.
