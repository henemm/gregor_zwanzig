# Context: #629 — Format-Modell auf Roh/Einfach reduzieren

## Request Summary
PO-Entscheidung #620 umsetzen: App-weit bietet die UI bei Wetter-Kennzahlen nur noch
**Roh**/**Einfach** an; die #435-Modi **Skala** (`scale`) und **Symbol** (`symbol`)
verschwinden aus der Oberfläche. Briefing-Darstellung bleibt **unverändert**; Bestandsdaten
werden datensicher angeglichen.

## Wichtigster Befund: Thema ist NICHT gelöst — aber es gibt Vorarbeit (Geister-Workflow)
- Kein `#629`-Commit auf irgendeinem Branch; Katalog/Loader/Frontend unverändert (17× scale/symbol im Katalog).
- Eine tote Session hat in Worktree `inherited-noodling-pebble` **uncommittet** abgelegt:
  - `docs/context/issue-629-format-reduktion.md`
  - `docs/specs/modules/issue_629_format_reduktion.md` (gut durchdacht, status:draft, Approved unchecked)
  - `tests/tdd/test_issue_629_format_reduktion.py` (6 Backend-Migrationstests, AC-3/4/5)
- Workflow-State `issue-629-format-reduktion` steht auf **Validation / „VERIFIED 6 passed"** — aber
  **LoC-Delta +0/300**, keine Implementierung. Das Verdict ist **hohl** (Tests wären ROT, da der
  Loader scale/symbol heute unverändert durchreicht). → Muster wie #616 (Geister-Arbeit + falsches Verdict).

## Die eigentliche Knacknuss (vom Spec sauber gelöst)
Naives „scale/symbol → default_format_mode zurücksetzen" ist widersprüchlich, weil der Katalog
für mehrere Metriken **selbst** `default_format_mode = scale|symbol` hat (Gewitter sogar nur `("symbol",)`).
Render-Ebene (`tokens/builder.py`, `email/helpers.py`): es gibt faktisch nur **zwei** Verhalten —
`raw` = numerisch, alles andere = „friendly" (Emoji/Kompass/Kurztext).

**Spec-Lösung (output-erhaltend):** Katalog & Renderer **nicht** anfassen. Nur die UI schrumpfen
(4-Wert-Dropdown → Boolean-Toggle `use_friendly_format`, exakt wie v2 #587). Migration beim Laden:
persistiertes `format_mode in {scale,symbol}` → `None` + `use_friendly_format=true`. Da der
Katalog-Default dieser Metriken IST scale/symbol, rendert alles **bit-identisch**.

## Related Files
| File | Relevanz |
|------|----------|
| `src/app/loader.py` (`_resolve_format_mode`, `_trip_to_dict`, Load-Pfad ~430-505) | Migration scale/symbol→None+friendly |
| `src/app/metric_catalog.py` | **bleibt unverändert** (4-wertig; sonst bricht thunder, ändert Defaults) |
| `src/output/renderers/email/helpers.py` (`fmt_val`, `should_merge_wind_dir`) | **bleibt unverändert**; wind_dir-Kompass-Merge hängt an `_effective_format_mode=="scale"` → über Katalog-Default erhalten |
| `frontend/.../WeatherConfigDialog.svelte` (Orte, **live** /locations) | 4-Wert-`<Select>` (Z. ~239) → Boolean-Toggle |
| `frontend/.../trip-wizard/steps/Step3Weather.svelte` (Wizard `/trips/new`, **live**) | `FORMAT_MODE_LABELS` 4-Wert → Boolean-Toggle |
| `frontend/.../trip-detail/WeatherV2Reihenfolge.svelte` (v2-Tab) | **schon konform** (Boolean Roh/Einfach via `use_friendly_format`) |

## Dependencies
- Upstream: `metricsEditor.ts::indicatorCapable` (Single Source: welche Metriken den Toggle bekommen), `ActiveMetricRow.svelte`/v2 als Toggle-Vorbild.
- Downstream: Briefing-Renderer (muss bit-identisch bleiben → Golden/Pipeline-Test).

## Realdaten
- `data/users/`: **0** persistierte `format_mode`-Werte → Migration praktisch No-op, Roundtrip-Test = Garantie.

## Risks & Considerations
- Verwaister Workflow-State mit falschem VERIFIED → muss **ehrlich** neu validiert werden (kein Vertrauen ins Alt-Verdict).
- Schema-Rework-Regel: `loader.py` schema-relevant → Pre-Snapshot-Hook + Roundtrip-Test (beides vorhanden/erfüllt).
- Wizard `/trips/new` ist noch live (TripWizardShell→Step3Weather) → AC-2 gilt, nicht überspringen.
- Frontend-ACs (AC-1/2/6) brauchen echte Playwright-Verifikation gegen Staging.
