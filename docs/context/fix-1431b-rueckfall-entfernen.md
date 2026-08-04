# Kontext: fix-1431b-rueckfall-entfernen

**Übergabe an die nächste Sitzung.** Aufräum-Nachlauf zu #1431 (geschlossen, live).
Vorgang angelegt, PO-Freigabe erteilt, Arbeit nicht begonnen — das Agenten-Kontingent
der Ursprungs-Sitzung war erschöpft.

## Ausgangslage

Mit #1431 (`65a0ea1e`) bekamen drei Wächter eine tokenbasierte Commit-Erkennung aus
`hook_utils.is_git_subcommand`. Weil das Werkzeug-Paket damals noch nicht ausgeliefert
war, fangen sie den fehlenden Import mit `try/except` ab und fallen auf die alte
Teilstring-Prüfung zurück:

- `.claude/hooks/renderer_mail_gate.py`
- `.claude/hooks/e2e_commit_gate.py`
- `.claude/hooks/auto_restart_server.py`

Jede Stelle trägt den Block `UEBERGANGS-RUECKFALL — NACH AUSLIEFERUNG DES PLUGINS
ENTFERNEN (Issue #1431)`.

**Die Auslieferung ist erfolgt** (2026-08-04): installiert und registriert ist
`agent-os-openspec 3.10.0`. Am laufenden Stand nachgemessen: `is_git_subcommand` und
`is_pure_git_command` vorhanden und korrekt (14 Erkennungsfälle, 7 Fälle der
Selbst-Freigabe-Sperre, Belege im Abschluss-Kommentar von #1431).

**Warum das raus muss:** Der Rückfall ist eine stille Zweitfassung genau des Defekts,
den #1431 beseitigt hat. Fällt der Import künftig aus, schaltet der Wächter unbemerkt
auf die umgehbare Prüfung zurück, statt den Fehler zu zeigen.

## Auftrag

1. **In allen drei Dateien** den `try/except`-Rückfall entfernen, Import direkt stellen.
   Kommentarblock entfällt; ein knapper Herkunftshinweis (`#1431`) darf bleiben.

2. **Vorher klären, was bei fehlendem Import passieren soll.** Ein `ImportError` beim
   Hook-Start ist etwas anderes als ein stiller Rückfall — aber auch etwas anderes als
   ein Absturz, der jeden Befehl blockiert. `tests/tdd/test_issue_384_hook_fail_open.py`
   beschreibt die Erwartung (fehlende Hook-Datei darf nicht blockieren); daran richten.
   **Das ist der heikle Teil, nicht das Löschen.**

3. **Test, der den Rückfall dauerhaft ausschließt.** Heute würde niemand merken, wenn
   ihn jemand wieder einbaut. Tragfähiger Weg: die Erkennungsfunktion im Wächter-Modul
   ersetzen und messen, dass sich die *Entscheidung* ändert — dann hängt der Test an der
   Wirkung, nicht am Text.

4. **Wirkungstests wie in #1431**, gegen die echten Gate-Subprozesse:
   - `renderer_mail_gate`, Mail-Datei gestaged ohne Nachweis: `git -C <repo> commit` ⇒
     blockiert · kanonische Form ⇒ blockiert · `grep -rn "git commit" …` ⇒ läuft durch
   - `auto_restart_server`: Diagnose-Kommando ⇒ kein Neustart · echter Commit ⇒ löst aus

5. **Gegenprobe:** Rückfall testweise wieder einbauen ⇒ der neue Test muss rot werden.

## Randbedingungen

- Nur die drei Dateien plus Tests. Kein Werkzeug-Paket, kein Plugin-Cache.
- `.claude/hooks/` ist geschützt — **PO-Freigabe liegt vor**
  (`.claude/user_override_token.json`, Eintrag `fix-1431b-rueckfall-entfernen`).
  Der Token hängt am Workflow-Namen: den Vorgang per `workflow.py switch
  fix-1431b-rueckfall-entfernen` übernehmen, nicht neu anlegen — sonst ist die Freigabe weg.
- Kein `uv run pytest` ohne konkret benannte Testdateien (#1476).
- Kein `git stash`/`checkout`/`reset`; Mutationen per String-Ersetzung mit externer Sicherung.
- Vor dem Commit `git fetch origin` und Rückstand prüfen — der Commit-Wächter misst das
  Verzeichnis, aus dem der Befehl kommt, **nicht** das Repo, in dem committet wird.
  Das hat am 2026-08-04 zweimal blockiert und beide Male anders ausgesehen, als es war.

## Umfang

Klein: drei `try/except`-Blöcke plus eine Testdatei. Risiko liegt allein in Punkt 2.
