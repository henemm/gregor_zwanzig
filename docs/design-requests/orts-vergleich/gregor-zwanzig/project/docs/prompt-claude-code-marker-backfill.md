# Prompt für Claude Code — Marker nachtragen auf bestehenden Issues

**Ziel:** Bei den 9 GitHub-Issues, die im Audit nur per Titel-Match identifiziert
wurden (kein `stable_id`-Marker im Body), den Marker nachtragen — damit
künftige Audits zuverlässig per Marker dedupen können und nicht raten müssen.

**Voraussetzung:** Der Issue-Status-Audit (`docs/prompt-claude-code-issue-audit.md`)
wurde durchgeführt und du hast eine Liste der Issues mit Titel-Match aber
ohne Marker.

Kopiere den Block unten in Claude Code im Repo-Root.

---

```text
Trage in folgenden GitHub-Issues im Repo henemm/gregor_zwanzig
einen Marker am Anfang des Bodies nach. Format des Markers ist
genau eine HTML-Kommentarzeile:

    <!-- gregor-zwanzig-handoff: stable_id=<slug> -->

Vorgehen pro Issue:

1. Hole den aktuellen Body:
       gh issue view <N> --repo henemm/gregor_zwanzig --json body --jq .body
2. Prüfe, ob der Body bereits eine Zeile mit
   `<!-- gregor-zwanzig-handoff: stable_id=` enthält.
   - JA → SKIP, kein Edit nötig.
   - NEIN → fahre fort.
3. Erzeuge den neuen Body:
   - Erste Zeile: der Marker oben mit der konkreten stable_id
   - Leerzeile
   - Anschließend der unveränderte alte Body
4. Schreibe den neuen Body in eine Temp-Datei und committe per
       gh issue edit <N> --body-file /tmp/issue-<N>-body.md \
         --repo henemm/gregor_zwanzig
5. Verifiziere den Edit:
       gh issue view <N> --repo henemm/gregor_zwanzig --json body --jq .body | head -3

Mapping Issue-Nummer → stable_id (die Issues stammen aus älteren Handoff-
Runden; identifiziere die genaue Nummer in DEINEM gh-Audit vorher und
ersetze N1, N2, ... unten durch die echten Nummern):

    N1  foundation-css-tokens
    N2  foundation-form-controls
    N3  sidebar-logo-and-rebrand
    N4  screen-home-cockpit
    N5  screen-trips-list
    N6  trip-editor-stages-table
    N7  alert-rules-editor-restyle
    N8  edit-weather-section-controls
    N9  edit-report-config-controls
    N10 locations-with-groups        (falls noch ohne Marker; ggf. weglassen wenn schon vorhanden)
    N11 trip-detail-page             (analog)

WICHTIG:
- Lege KEINE neuen Issues an.
- Lösche KEINE existierenden Bodies — nur den Marker davorhängen.
- Mache pro Issue genau einen `gh issue edit`-Call.
- Wenn ein Issue closed ist, ist das OK — der Marker hilft trotzdem für
  künftige Dedup-Audits.
- Gib am Ende eine Tabelle aus: Issue # | stable_id | Aktion (added | skipped | error)
```

---

## Was du mit dem Output machst

- Tabelle hier reinpasten als Beleg, dass alle Marker sitzen.
- Danach ist der nächste Audit (auch für künftige Handoff-Runden) automatisch
  marker-basiert zuverlässig — das pasted_text vom Mai 2026 wird so etwas
  wie »unsicher / nur per Titel« nicht mehr enthalten.
