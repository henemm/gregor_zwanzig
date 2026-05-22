# Context: Issue #323 — Hex-Fallbacks in SmsPhoneFrame + profileSignature bereinigen

## Request Summary

Bug AP-007 Restdrift: Zwei Stellen in `SmsPhoneFrame.svelte` und `profileSignature.ts` enthalten noch Hex-Farbliterale, die gegen das Design-System-Anti-Pattern AP-007 verstoßen. Issue #277 hatte 26 Komponenten bereinigt, diese zwei wurden ausgelassen.

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | Haupt-Target: 14 Hex-Literale in CSS, einige als var()-Fallbacks, einige standalone |
| `frontend/src/lib/utils/profileSignature.ts` | Haupt-Target: `accentFallback`-Feld mit 4 Hex-Literalen |
| `frontend/src/lib/utils/profileSignature.test.ts` | Muss angepasst werden wenn `accentFallback` entfernt wird |
| `frontend/src/routes/_design/+page.svelte:158` | Zeigt `{sig.accentFallback}` — muss bei Entfernung angepasst werden |
| `frontend/src/app.css` | Token-Definitionen: `--g-paper`, `--g-ink`, `--g-ink-faint`, `--g-warning`, `--g-danger`, `--g-ink-muted`, `--g-profile-*` |
| `docs/design-system/ANTI-PATTERNS.md` | Regel AP-007 mit Grep-Kommando |
| `docs/specs/modules/issue_238_profile_signatures.md` | Spec die `accentFallback` eingeführt hat (AC-3, AC-5) |
| `docs/specs/modules/issue_277_css_variable_fallbacks.md` | Vorherige Bereinigung — Referenz |

## Existing Patterns

- **AP-007:** `grep -rn -E '#[0-9a-fA-F]{3,6}' frontend/src/ | grep -v 'tokens.css' | grep -v '.md:'` — matcht auch 3-stellige Hex wie `#000`
- **Pattern aus #277:** Hex-Fallbacks aus `var(token, #hex)` → `var(token)` entfernen, wenn Token definiert ist
- **Issue #278 (closed):** Bestätigt dass alle referenzierten Tokens in `app.css` definiert sind

## Token-Mapping (für SmsPhoneFrame)

Alle verwendeten Tokens sind in `app.css` definiert:
- `--g-paper: #f6f4ee` ✓
- `--g-ink: #1a1a18` ✓
- `--g-ink-faint: #9c9a90` ✓
- `--g-ink-muted: #5c5a52` ✓
- `--g-warning: #c8882a` ✓
- `--g-danger: #b33a2a` ✓ (ersetzt `#b03a2e` — nahezu gleicher Wert)

## Änderungsplan pro Datei

### SmsPhoneFrame.svelte — 14 Hex-Stellen

| Zeile | Alt | Neu | Begründung |
|-------|-----|-----|------------|
| 76 | `var(--g-ink, #1a1a18)` | `var(--g-ink)` | Token definiert |
| 76 | `var(--g-warning, #c8882a)` | `var(--g-warning)` | Token definiert |
| 79 | `background: #1a1a18` | `background: var(--g-ink)` | Gleicher Wert wie Token |
| 85 | `background: #000` | `background: black` | CSS-Keyword, kein Token nötig, Phone-Notch-Dekoration |
| 88 | `var(--g-paper, #f6f4ee)` | `var(--g-paper)` | Token definiert |
| 92 | `var(--g-paper, #f6f4ee)` | `var(--g-paper)` | Token definiert |
| 92 | `var(--g-ink, #1a1a18)` | `var(--g-ink)` | Token definiert |
| 95 | `var(--g-ink-faint, #9c9a90)` | `var(--g-ink-faint)` | Token definiert |
| 97 | `var(--g-ink, #1a1a18)` | `var(--g-ink)` | Token definiert |
| 98 | `color: #b03a2e` | `color: var(--g-danger)` | Nächster Token (`#b33a2a`) |
| 103 | `var(--g-ink, #1a1a18)` | `var(--g-ink)` | Token definiert |
| 104 | `var(--g-warning, #b67700)` | `var(--g-warning)` | Token definiert |
| 105 | `color: #b03a2e` | `color: var(--g-danger)` | Nächster Token (`#b33a2a`) |
| 108 | `var(--g-ink-muted, #5c5a52)` | `var(--g-ink-muted)` | Token definiert |

### profileSignature.ts — accentFallback entfernen

`accentFallback` wird **nur** in `_design/+page.svelte:158` zur Anzeige verwendet — **nicht** in funktionalem Code. Mail-Rendering erfolgt in Python (kein Zugriff auf dieses TS-Modul).

- `ProfileSignature` Typ: `accentFallback: string` entfernen
- `SIGNATURES` Objekte: `accentFallback` Felder entfernen
- `_design/+page.svelte:158`: Zeile mit `{sig.accentFallback}` entfernen
- `profileSignature.test.ts`: alle `accentFallback`-Assertions entfernen

### Konflikt mit Spec #238

Spec Issue #238 AC-3 und AC-5 fordern `accentFallback` mit Hex-Werten. Bug #323 ist ein nachträglicher Bug-Report der diese Werte als AP-007-Verstoß einstuft. Bug #323 hat Priorität — `accentFallback` war nur für Mail-Renderer gedacht, der Python-seitig implementiert ist.

## Dependencies

- **Upstream:** `app.css` (Token-Definitionen) — bereits korrekt
- **Downstream:** `_design/+page.svelte` (zeigt `accentFallback`), `profileSignature.test.ts` (testet Hex-Pattern)

## Risks & Considerations

1. **`#000` für Phone-Notch:** Kein Token für reines Schwarz — CSS-Keyword `black` ist sauberer als `rgba(0,0,0,1)` und wird vom Grep nicht gematcht
2. **`#b03a2e` ≠ `#b33a2a`:** Kleiner Farbunterschied (2 Hex-Steps). Da `--g-danger` der Semantik-Token für Fehler/Over ist, ist er der richtige Ersatz
3. **`#b67700` Warning-Text:** Fallback-Wert unterscheidet sich vom Token `#c8882a`. Das war ein undokumentierter "dunklerer Warning-Ton für Text". Beim Ersetzen mit `var(--g-warning)` ändert sich die Warning-Text-Farbe leicht (vom Test mit Staging zu prüfen)
4. **Test-Update:** `profileSignature.test.ts` enthält Hex-Pattern-Checks — müssen ebenfalls bereinigt werden (kein externer Regressions-Risiko, da `accentFallback` nicht funktional war)

## Acceptance Criteria (aus Issue)

1. `grep -rn -E '#[0-9a-fA-F]{3,6}' frontend/src/ | grep -v 'tokens.css' | grep -v '.md:'` → keine Treffer in `SmsPhoneFrame.svelte`
2. `profileSignature.ts` enthält keine Hex-Literale mehr
3. Visueller Vergleich: SmsPhoneFrame sieht identisch aus (Tokens waren bereits korrekt definiert)
