# Context: fix-2047-s1-wip-sicherung

## Request Summary

Der CI-Schritt „Staging-Verdict schreiben (CI smoke)" fährt bei **jedem** Merge nach `main`
ein `git reset --hard origin/main` im Haupt-Checkout `/home/hem/gregor_zwanzig` — **ohne**
WIP-Sicherung. Uncommittete getrackte Arbeit dort wird zerstört. Scheibe 1 von #2047 setzt
die Sicherung davor, nach dem bereits bewährten Vorbild aus `deploy-gregor-prod.sh`.

**Abgrenzung:** Die Wirkungslosigkeit des Prod-Gates selbst (Kern von #2047, PO-Entscheid
„Weg A mit Automatisierung") ist **Scheibe 2** und wird hier nicht angefasst.

## Related Files

| File | Relevance |
|------|-----------|
| `.github/workflows/ci.yml:473` | Die fragliche Zeile — SSH-Einzeiler mit ungesichertem `git reset --hard` |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh:149-161` | **Vorbild**: `git stash create` + Tag `deploy-safety/<ts>` + Echo mit Wiederherstellungs-Befehl |
| `.claude/hooks/staging_gate.py:97-110` | `_verified_repo_dir()`/`_head_sha()` — cwd-basiert, deshalb ist der Reset funktional nötig |
| `.claude/hooks/_e2e_paths.py:283-308` | Attestations-Ablage im geteilten Hauptrepo; Design setzt den Reset voraus |

## Existing Patterns

**WIP-Sicherung (`deploy-gregor-prod.sh:149-161`)** — das zu kopierende Muster:

```
if ! git diff --quiet || ! git diff --cached --quiet; then
    SAFETY=$(git stash create "pre-deploy-safety $(date -u +%FT%TZ)" || true)
    if [ -n "$SAFETY" ]; then
        TAG="deploy-safety/$(date -u +%Y%m%d-%H%M%S)"
        git tag "$TAG" "$SAFETY" 2>/dev/null || true
        echo "... gesichert: $SAFETY (Tag $TAG)"
```

Kernmechanik: `git stash create` (**nicht** `stash push`) erzeugt ein Stash-Commit-Objekt,
ohne den Arbeitsbaum anzufassen. Das ist wichtig, weil der Haupt-Checkout mit anderen
Sessions geteilt wird — `stash push` würde deren Arbeitsbaum unter den Füßen wegziehen.
Der Tag verankert das Objekt, damit die GC es nicht einsammelt.

## Dependencies

- **Upstream:** Der Schritt braucht `origin/main` als HEAD, weil `staging_gate.py --write-verdict`
  den SHA aus dem cwd zieht (`_head_sha()`). Ein Wegfall des Resets ist deshalb **kein**
  Scheibe-1-Fix.
- **Downstream:** `deploy-gregor-prod.sh` läuft Sekunden später und macht seinerseits einen
  Reset — diesmal mit Sicherung. Die zwei Resets dürfen sich nicht ins Gehege kommen.

## Risks & Considerations

1. **`git stash create` sichert keine untracked Dateien.** Das ist hier unschädlich, weil
   `git reset --hard` untracked Dateien ebenfalls nicht anfasst — die Abdeckung ist also
   deckungsgleich mit dem Schaden.
2. **Der Haupt-Checkout ist zugleich das Produktions-Arbeitsverzeichnis** aller drei
   systemd-Dienste (`gregor-python.service`, `gregor-api.service` → `WorkingDirectory=/home/hem/gregor_zwanzig`).
   → **Nebenbefund für Scheibe 2:** `deploy-gregor-prod.sh` stoppt `gregor-python` *vor* seinem
   Reset (`:274` vor `:285`); der CI-Verdict-Schritt tut das **nicht**. Der Code-Stand wechselt
   also unter laufenden Prod-Diensten. Nicht Teil dieser Scheibe.
3. **Kein Aufräumen der Sicherungs-Tags** ist im Vorbild belegt. Bei jedem Merge ein Tag
   entsteht nur, wenn tatsächlich uncommittete Arbeit vorlag — das ist selten genug, dass
   Wildwuchs unwahrscheinlich ist. Wird beobachtet, nicht vorab gelöst.
4. **Testbarkeit:** `ci.yml` selbst ist nicht ausführbar testbar. Deshalb wandert die
   Sicherungslogik in ein eigenes Shell-Skript, das gegen ein echtes Wegwerf-Git-Repo
   geprüft wird (kein Mock). Die Verdrahtung in `ci.yml` wird separat als
   `# doc-compliance-test` abgesichert.
5. **Henne-Ei beim ersten Lauf:** Ein neues Skript im Repo liegt beim allerersten CI-Lauf
   noch nicht im Arbeitsbaum des Servers (HEAD ist dort der alte Stand). Der Aufruf muss
   das Skript deshalb aus `origin/main` beziehen, nicht aus dem Arbeitsbaum.
