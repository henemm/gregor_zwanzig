# Context: fix-1866-claim-freigabeweg

## Request Summary
Issue #1866: Der dokumentierte Notausgang des Datei-Claim-Gates (`export GZ_FILE_CLAIM_OVERRIDE=1`)
ist unerreichbar, weil das Gate als eigener Prozess läuft und das `export` einer Bash-Tool-Aufrufs
den Hook-Prozess nicht erreicht. Der einzige wirksame Ort (`.claude/settings.local.json`) ist durch
`edit_gate.py` (Plugin, Orchestrator-Domäne) gesperrt. PO-Entscheid aus der Intake-Runde: Vorschlag
1 (`--release`-CLI-Befehl) und Vorschlag 2 (Verfall an Aktivität statt nur an der Uhr) umsetzen,
Vorschlag 3 (`edit_gate` differenzieren) **nicht** — das liegt im Plugin-Repo `agent-os-openspec`,
nicht in diesem Repo, und wird durch Vorschlag 1 ohnehin überflüssig.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/file_claim_gate.py` | Das Gate selbst — einziger zu ändernder Ort. Liegt im Projekt-Repo (nicht im Plugin), keine Kollisionsgefahr mit `agent-os-openspec`. Aktuell 243 Zeilen, **keine Tests**. |
| `.claude/settings.json:109-117` | Hook-Registrierung: `PreToolUse` auf Matcher `Write\|Edit`, ruft `file_claim_gate.py` ohne Argumente auf (liest stdin-JSON). Ein CLI-Aufruf mit `--release` läuft **außerhalb** dieses Hook-Pfads, als normaler Bash-Befehl. |
| `.claude/file_claims.json` | Die geteilte Registry (worktree-übergreifend im Hauptrepo). Aktuell 114 Einträge, 7 aktive Sessions. |

## Existing Patterns

- **Fail-open überall:** Jeder Fehlerpfad in `file_claim_gate.py` gibt `0` zurück (nie blockieren wegen eigenem Defekt). Diese Eigenschaft muss der neue `--release`-Pfad übernehmen — ein Fehler beim Release darf nie eine Exception nach oben werfen, die den Bash-Aufruf abbrechen lässt, aber auch nie eine bestehende, tatsächlich aktive Belegung stillschweigend löschen.
- **Locking:** `_acquire_lock()` mit `fcntl.flock`, 2s Timeout, dann fail-open. Der neue Release-Pfad muss dasselbe Lock verwenden (gleiche Registry-Datei, gleichzeitige Hook-Läufe anderer Sessions möglich).
- **Session-Kennung:** Worktree-Ordnername (`_session_id()`), nicht der freie Anzeigename der Claude-Session — bereits als Falle dokumentiert (`SendMessage` an den Anzeigenamen scheitert, siehe Issue-Text). Der `--release`-Befehl arbeitet daher über den **Registry-Key** (Datei-Pfad) bzw. den **Worktree-Ordnernamen**, nicht über Anzeigenamen.
- **`bash_gate.py` (Plugin):** blockiert `python3 -c` und Schreib-Indikatoren (`sed -i`, `>`, `open(`, …) auf Pfaden, die `\.claude/hooks/[^\s]*\.py` matchen — aber **nur wenn zusätzlich ein Schreib-Indikator vorliegt**. Ein reiner Skript-Aufruf `python3 .claude/hooks/file_claim_gate.py --release <pfad>` (kein `-c`, kein Redirect) hat keinen Schreib-Indikator und läuft ungeblockt durch. Geprüft am aktuellen Plugin-Stand 3.11.4.

## Dependencies
- **Upstream:** `hook_utils.find_project_root()` (Plugin) für die Hauptrepo-Auflösung — nur Import, kein Änderungsbedarf.
- **Downstream:** Keine anderen Skripte rufen `file_claim_gate.py` derzeit direkt auf (kein Treffer bei `grep -rl file_claim`). Der neue CLI-Modus ist rein additiv.

## Existing Specs
Keine vorhandene Spec zu diesem Gate (PO-Feature vom 2026-08-13, nicht spezifiziert dokumentiert).

## Risks & Considerations
- **Vorschlag 2 (Aktivitäts-Verfall)** braucht Git-Vergleiche (Worktree-Pfad ermitteln, Datei-Inhalt im Worktree vs. `origin/main`, Status auf saubere Arbeitskopie für den Pfad). Jeder Git-Fehler muss konservativ in Richtung "nicht automatisch verfallen" auflösen (bestehendes Blockier-Verhalten bleibt bestehen) — nicht in Richtung "freigeben", sonst higher Blast Radius als der bestehende Bug.
- **`--release` ohne Zugriffsschutz:** Jede Session kann jede Belegung lösen. Das ist beabsichtigt (Zweck des Befehls ist genau die Behebung fremder Fehlbelegungen), aber die Ausgabe muss die gelöschte Belegung (Session, Branch, Zeitpunkt) nennen, damit der Vorgang nachvollziehbar bleibt (kein stiller Eingriff).
- **Kein Test vorhanden:** Neue Logik (`--release`, `--release-session`, Aktivitäts-Verfall) braucht neue Tests. Ort: `tests/unit/` (Hooks sind reine Python-Skripte, Kern-Schicht ohne Netz — passt zur deterministischen Schicht der Zwei-Schichten-Testpolitik).
- **Regel-Budget-Prüfdatum** des Gates selbst (2026-11-11) bleibt unverändert; dieser Fix ändert nichts daran.

## Next Step
Weiter mit `/30-write-spec`.
