# E2E Test (RED/GREEN Browser Test)

Du startest einen **echten E2E Browser-Test**.

## RED/GREEN Workflow (PFLICHT!)

### Phase 1: RED (vor Implementation)

Führe den Test aus - er MUSS fehlschlagen:

```bash
cd "/Users/hem/Documents/opt/gregor zwanzig"
uv run python3 .claude/hooks/e2e_browser_test.py \
  --check "DEIN_FEATURE_TEXT" \
  --url "/compare" \
  --action "compare" \
  --expect-fail
```

**Erwartetes Ergebnis:** `🔴 RED PHASE OK - Feature fehlt noch`

Wenn der Test NICHT fehlschlägt → Feature existiert bereits → keine Änderung nötig!

### Phase 2: Implementation

Jetzt implementiere das Feature.

### Phase 3: Server Neustart

**KRITISCH:** Server muss neu gestartet werden!

Sage dem User:
> "Bitte starte den Server neu: `python -m src.web.main`"

Warte auf Bestätigung.

### Phase 4: GREEN (nach Implementation)

Führe den Test erneut aus - er MUSS erfolgreich sein:

```bash
cd "/Users/hem/Documents/opt/gregor zwanzig"
uv run python3 .claude/hooks/e2e_browser_test.py \
  --check "DEIN_FEATURE_TEXT" \
  --url "/compare" \
  --action "compare"
```

**Erwartetes Ergebnis:** `🟢 GREEN PHASE OK - Feature funktioniert!`

### Phase 5: Screenshot analysieren

Öffne den Screenshot und prüfe visuell:

```bash
# Screenshot path wird vom Test ausgegeben
```

Verwende das Read-Tool um den Screenshot zu analysieren.

## Beispiel: Windrichtung Feature

```bash
# RED
uv run python3 .claude/hooks/e2e_browser_test.py --check "Windrichtung" --url "/compare" --action "compare" --expect-fail

# ... Implementation ...
# ... Server Neustart ...

# GREEN
uv run python3 .claude/hooks/e2e_browser_test.py --check "Windrichtung" --url "/compare" --action "compare"
```

## NIEMALS

- "E2E Test erfolgreich" sagen ohne GREEN Phase
- Screenshots ignorieren
- Server-Neustart überspringen
