# Prompt für Claude Code — Issue-Status-Audit

**Ziel:** Prüfen, welche GitHub-Issues in `henemm/gregor_zwanzig` aus dem
Spec-Material in der Design-Sandbox (`gregor-zwanzig` Projekt) bereits
geschlossen sind, damit die Sandbox-Quelldateien gefahrlos gelöscht werden
können.

Kopiere den Block unten in Claude Code, nachdem du das Repo geöffnet und
`gh auth status` grün ist.

---

```text
Lies die Datei `claude-code-handoff/issues.json` in diesem Repo (oder im
gepaarten Handoff-Paket, falls nicht eingecheckt) und führe für jeden
Eintrag folgendes aus:

1. Extrahiere `stable_id` und `title`.
2. Suche auf GitHub im Repo `henemm/gregor_zwanzig` nach offenen UND
   geschlossenen Issues mit dem Marker im Body:
       gh issue list \
         --state all \
         --search "in:body gregor-zwanzig-handoff: stable_id=$stable_id" \
         --json number,state,title,url \
         --repo henemm/gregor_zwanzig
   Bei mehreren Treffern (sollte nicht passieren) das mit der niedrigsten
   Nummer nehmen.
3. Wenn KEIN Treffer per Marker: Fallback per Titel-Match —
       gh issue list --state all --search "$title in:title" --repo henemm/gregor_zwanzig
   Maximal 3 Kandidaten anzeigen; nicht raten welcher der richtige ist,
   sondern als "unsicher" markieren.
4. Status klassifizieren:
   - "closed"      — Marker-Match + state=closed
   - "open"        — Marker-Match + state=open
   - "not-created" — kein Treffer, weder per Marker noch per Titel
   - "unsicher"    — Treffer nur per Titel, kein Marker; oder mehrere Marker-Treffer
5. Für jedes "closed" Issue prüfe zusätzlich, ob das im Issue-Body
   referenzierte Soll-Mockup noch gebraucht wird:
   - Lies `body_file` aus `issues.json`
   - Suche im Body nach `soll-mockups/` und nach Screenshot-Pfaden
     `.github/issue-assets/`
   - Liste die referenzierten Dateien als "kann nach Sandbox-Cleanup
     entfallen, sofern keine andere Spec sie noch braucht"

Output als Markdown-Tabelle:

| stable_id | Issue # | Title | Status   | Sandbox-Dateien zum Löschen (wenn closed) |
|-----------|---------|-------|----------|--------------------------------------------|
| foundation-css-tokens | #N | ... | closed | tokens.css? — Kernfile, NICHT löschen |
| ...       | ...    | ...  | ...      | ...                                       |

Am Ende drei Listen ausgeben:

**Closed (sicher löschbar in der Design-Sandbox):**
- `Datei A` (Quelle für Issue #N "Titel")
- `Datei B` ...

**Open (Soll-Mockup weiterhin als Spec gebraucht):**
- ...

**Unsicher / nicht erstellt (manuell prüfen):**
- ...

WICHTIG:
- Lege KEINE Issues an. Lösche KEINE Dateien. Nur Status berichten.
- Wenn `gh` nicht installiert oder nicht authentifiziert ist:
  STOP und sag dem User welcher Befehl fehlt.
- Wenn das Repo `henemm/gregor_zwanzig` nicht erreichbar ist: STOP.
```

---

## Was Du mit dem Output anfängst

Kopiere den Output zurück in unseren Chat. Ich gleiche dann die
"Closed"-Liste mit der Sandbox ab und schlage konkrete Löschaktionen vor
(jede zur Bestätigung) — ohne nochmals voreilig zuzuschlagen.
