# Context: Issue #814 — Einfach/Roh-Ampel endgültig korrekt

## Request Summary
Die vier Ampel-Metriken (wind, gust, precip, pop) sollen im HTML-Briefing **nur in
„Einfach" (`use_friendly_format=True`) den 4-stufigen Ampelpunkt** und in „Roh"
(`use_friendly_format=False`) die **Zahl** zeigen. Aktuell (Live, nach #810-Patch)
zeigen **beide** Modi Zahlen → Default „Einfach" ist defekt. `use_friendly_format`
soll die alleinige, deterministische Quelle werden; abgesichert durch einen
verpflichtenden Beide-Modi-Matrix-Test (#811-Muster), der die vier Metriken
**spezifisch** prüft.

## Root Cause (verifiziert)
- `_resolve_format_mode({use_friendly_format:True}, m)` liefert für wind/gust/
  precipitation/rain_probability den **Katalog-Default `"raw"`** — `use_friendly_format`
  überschreibt ihn nicht (`metric_catalog`: `default_format_mode="raw"`, format_modes
  nur `("raw","simplified")` bzw. `("raw",)` für pop — **kein** Indikator-Mode).
- `build_format_modes(dc)` kollabiert damit Einfach **und** Roh auf denselben Wert
  `"raw"`. Das #810-Kriterium `if html and mode != "raw"` (helpers.py:447,462,503)
  kann die beiden Modi prinzipiell **nicht** trennen → Ampel in beiden Modi unterdrückt.
- Direkt belegt: `_render(full, raw=False)` → `>55<`,`>85<`,`>8.0<` (nackte Zahlen)
  für die vier; die 6 Ampel-Emojis stammen von **CAPE** (eigene Emoji-Logik).

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py` | `fmt_val` (447/462/503 die fehlerhaften `mode != "raw"`-Checks); `build_format_modes` (771); `build_friendly_keys` (750); `_effective_format_mode` (42); `ampel_dot` (369); `_AMPEL_KEY_TO_METRIC_ID` (396) |
| `src/app/loader.py` | `_resolve_format_mode` (40) — kollabiert use_friendly_format→"raw" |
| `src/app/metric_catalog.py` | `default_format_mode`/`format_modes` der vier (alle "raw") |
| `src/output/renderers/email/html.py` | ruft `fmt_val(..., html=True, format_modes=...)` (104,143) |
| `src/output/renderers/email/plain.py` | ruft `fmt_val(..., format_modes=...)` (47,62) — muss numerisch bleiben (AC-3) |
| `src/app/models.py` | `MetricConfig.use_friendly_format: bool = True` (491) |
| `tests/tdd/test_issue_811_mode_matrix.py` | Matrix-Test (full/compact × Einfach/Roh × briefing/alert). **Lücke:** `test_friendly_full_html_has_ampel` prüft nur „≥1 Ampel irgendwo" → passt fälschlich via CAPE. Stale `_XFAIL_810` xpasst aktuell strict → FAIL. AC-5/AC-6 müssen hier ansetzen. |
| `tests/tdd/test_issue_759_email_ampel.py` | #759-Test — koppelt Ampel an `html=True` ohne format_modes; AC-6 verlangt Anpassung |
| `tests/tdd/test_issue_810_raw_format_ampel.py` | #810-Test mit handgesetztem `format_modes={"wind":"raw"}` — genau das von AC-5 verbotene Muster |

## Existing Patterns
- **format_modes-Dict** col_key→mode wird einmal in `email/__init__.py:91` gebaut und an
  html/plain durchgereicht. `fmt_val` entscheidet pro Zelle.
- **`friendly_keys`-Set** (separater Plumbing-Pfad, Legacy-Fallback in fmt_val:428) —
  enthält die vier NIE, weil `_effective_format_mode=="raw"`.
- **Ampel-SSoT** `ampel_dot(value, display_thresholds)` (#759) — Schwellen aus Katalog.

## Fix-Richtung (Empfehlung für Spec)
**Direktion #1 (bevorzugt, niedriger Regressionsradius):** ein per-Spalte
`use_friendly_format`-Signal **direkt aus `mc`** (nicht über das kollabierende
`_resolve_format_mode`) bis `fmt_val` durchreichen und die HTML-Ampel der vier Keys
**daran** koppeln (Ampel ⇔ use_friendly_format==True), statt an `mode`. Plain bleibt
unberührt (Ampel-Zweig ist ohnehin `html`-gegated → AC-3 automatisch). Berührt **nicht**
die globale mode-Semantik (#435/#444/#629).
Direktion #2 (Katalog/Indikator-Mode) verworfen: globaler Regressionsradius.

## Risks & Considerations
- **#811-Renderer-Gate** (`renderer_mail_gate.py`) blockt den Commit bis Matrix-Nachweis
  vorliegt — Workflow ist faktisch erzwungen.
- AC-5-Test muss die vier Metriken **spezifisch** prüfen (nicht „≥1 Ampel global") —
  sonst maskiert CAPE den Bug erneut.
- AC-6: stale `_XFAIL_810`-Marker entfernen (xpasst strict → rote Suite) + #759-Test.
- `_make_dc(raw=False)` im Matrix-Test setzt `format_mode=None` → repräsentiert den
  echten Default-Pfad korrekt.
- Plain-Pfad darf nicht kippen (AC-3); cape/visibility/cloud/sunshine/temp unverändert (AC-4).

## Existing Specs
- `docs/specs/modules/issue_810_raw_format_ampel.md` — der fehlerhafte Patch-Ansatz
- `docs/specs/modules/issue_811_mail_quality_gate.md` — Matrix/Gate-Infrastruktur
- `docs/specs/modules/issue_759_669_email_ampel_gewitter.md` — Ursprung Ampel
