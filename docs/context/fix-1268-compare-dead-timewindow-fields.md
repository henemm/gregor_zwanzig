# Context: fix-1268-compare-dead-timewindow-fields

Issue: #1268 — „Verworfene Zeitfenster-/Horizont-Felder leben im Editor-Layout-Tab weiter (PO-Korrektur nie eingelöst)"
Erstellt: 2026-07-16

## Request Summary

Der Ortsvergleich-Editor rendert im Layout-Tab zwei Felder — „Zeitfenster" (Start-/End-Stunde) und „Horizont" (24/48/72 h) — die laut PO-Korrektur vom 2026-07-11 (Spec-Constraint 2 in #1256) verworfen wurden. Sie sollen samt Persistenz-Zufluss verschwinden; Datenfelder dürfen deprecated bestehen bleiben.

## Zentraler Widerspruch (blockiert die Spec)

Das Issue nennt die Felder „verworfen" und „von keiner Scheibe gebucht". Der Code zeigt jedoch: **beide Felder haben echte Wirkung.**

| Feld | UI | Wirkung im Produkt | Tot? |
|---|---|---|---|
| Zeitfenster (`hour_from`/`hour_to`, Default 9–16) | `CompareInhaltSection.svelte:107-136` (Inputs) + Kachel `:76-80` | `scheduler_dispatch_service.py:289-294` → `ComparisonEngine.run(time_window=(hour_from, hour_to))`. Bestimmt, **welche Tagesstunden bewertet werden**, und steht sichtbar in der Vergleichs-Mail-Kopfzeile (`compare_html.py:587-589` → „09:00 – 16:00") | **Nein — voll wirksam** |
| Horizont (`forecast_hours`, Default 48) | `CompareInhaltSection.svelte:95-104` (Select) + Kachel `:81-91` | `scheduler_dispatch_service.py:296` → `ComparisonEngine.run(forecast_hours=…)` → steuert, wie viele Stunden Vorhersage geholt werden (`comparison_engine.py:74`) | **Halb** — wirksam beim Datenholen, aber die Mail zeigt **hartkodiert** „+48h" (`compare_html.py:594`), unabhängig vom gewählten Wert |

**Vermutete Ursache des Widerspruchs:** Die PO-Korrektur vom 2026-07-11 betraf ausweislich der Design-Quelle den **Versand-Rhythmus**, nicht das Bewertungs-Zeitfenster. `docs/design-requests/…/versand-tab.jsx:93-96` wörtlich:

> „VT_ZeitfensterInfo ENTFERNT (PO 2026-07-11): „Rhythmus" + „rollierend, jedes Wochenende" waren kein gewolltes Feature. Der Vergleich-Versand funktioniert identisch zum Trip — nur Briefing-Uhrzeiten (Morgen = heutiger Tag, Abend = morgen)."

Spec `docs/specs/modules/issue_1256_compare_ui_rewire.md:184-188` fasst es dann breiter:

> „Versand wie Trip: Morgen-Briefing = heute, Abend-Briefing = morgen, editierbare Uhrzeiten — KEIN rollierendes Zeitfenster, KEIN separater Versandrhythmus, KEIN Horizont-Feld (PO-Korrektur 2026-07-11, verworfen)."

Ob „Zeitfenster" hier den **Versandrhythmus** („rollierend, jedes Wochenende") oder das **Bewertungsfenster** („welche Tagesstunden zählen") meint, ist die offene Frage. → **PO-Entscheid nötig, siehe Analyse.**

## PO-Entscheid 2026-07-16 (nach Vorlage des Widerspruchs, Diskussion im Workflow)

Der Widerspruch wurde dem PO mit Gegenargument vorgelegt (Zeitfenster ist Bewertungs-, nicht Anzeigefilter; Nachtwerte verzerren Tiefsttemperatur/Böen; Sonnenanteil wird gedeckelt). Prüfung ergab zusätzlich: der Dispatch-Pfad ist **live und gepflegt** (Go-Cron → `api/routers/scheduler.py:137` → `run_compare_presets_daily` → `ComparisonEngine.run`; Job `compare_presets_daily` im Prod-Scheduler; jüngste Kommentare #1232 Scheibe 2a / #1250 S7b) — **kein Relikt**.

**Entscheidungen:**

1. **Zeitfenster:** Einstellfeld entfällt. Bewertung läuft künftig über den **ganzen Tag**; Zeitangabe verschwindet aus Mail-Kopfzeile und Textbaustein. PO nimmt die Nachtwert-Verzerrung ausdrücklich in Kauf (→ Known Limitation, wörtlich in die Spec).
2. **Horizont:** Einstellfeld entfällt, Datenbeschaffung fest 48 h. Begründung: kein Anzeige-Horizont, sondern Beschaffungstiefe — „24 h" schneidet dem Abend-Briefing (Zieltag = morgen) die Daten ab. Die hartkodierte „+48h" in `compare_html.py:594` wird dadurch von einer Lüge zur Wahrheit.
3. **Feature-Idee (separat):** Kurz-Zusammenfassung je Ort im Trip-Stil unter den Orten → eigenes `enhancement`-Issue, **nicht** Teil von #1268.

**Von der Spec zu klären:**
- „Ganzer Tag" = `(0, 23)`? Damit `window_hours = 24` → Sonnenanteil-Bonus (#366) rechnet gegen 24 statt gegen die Tageslichtstunden. Vorschlag: auf Tageslichtstunden normieren; sonst Known Limitation.
- `hour_from`/`hour_to`/`forecast_hours` bleiben als deprecated Datenfelder erhalten (158 Bestands-Presets) — Lesepfad im Dispatch entfällt, Werte werden nicht gelöscht.
- Behandlung der Preview-/Validator-Schnittstellen (`api/routers/compare.py:15-17` Query-Parameter, `api/routers/validator.py:305-324` DTO).

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/CompareInhaltSection.svelte` | Rendert alle betroffenen Felder. Selbstdeklarierte „Zwischenlösung" (Kommentar Z. 2-15), aus #1232 Scheibe 2b |
| `frontend/src/lib/components/compare/CompareEditor.svelte:955` | Bindet `CompareInhaltSection` in den Layout-Tab ein (Desktop Z. 1307, Mobile Z. 1478) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:41-43,100-102` | State + Payload-Bau (CREATE): `hour_from`, `hour_to`, `forecast_hours` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Payload-Bau (EDIT) |
| `frontend/src/routes/compare/[id]/edit/+page.svelte:59-64` | Hydration der Felder aus dem Preset |
| `internal/model/compare_preset.go:27-29` | Persistenz: `HourFrom`, `HourTo`, `ForecastHours` |
| `internal/handler/compare_preset.go:349-357` | Read-Modify-Write; `forecast_hours`-Fallback 48 (#764/#781) |
| `src/services/scheduler_dispatch_service.py:289-296` | Verbraucher: baut `time_window`-Tupel und reicht `forecast_hours` durch |
| `src/output/renderers/email/compare_html.py:587-594` | Mail-Kopfzeile: Zeitfenster echt, Horizont hartkodiert „+48h" |

## Existing Patterns

- **Geteilter Layout-Tab existiert bereits:** `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte`, genutzt von Trip (`context="route"`) und Compare (`context="vergleich"`, `CompareEditor.svelte:909`). Er kennt Zeitfenster/Horizont **nicht** — nur Kanal-Umschalter + Kappungs-Hinweis.
- **`CompareInhaltSection` ist Compare-eigen ohne Trip-Pendant.** Nach der Teilungs-Invariante (CLAUDE.md) ist das ein Default-Fehler — hier aber bewusst als Zwischenlösung deklariert.
- **Horizont beim Trip funktioniert anders:** pro Metrik über `HorizonChips` (heute/morgen/übermorgen) in `trip-detail/MetricCheckbox.svelte`. Compare hat stattdessen einen globalen 24/48/72-Select. Kein geteilter Baustein.
- **Bewertungs-Zeitfenster beim Trip:** existiert als UI **nicht**. `Waypoint.time_window` (types.ts:38) ist etwas anderes (Ankunftsfenster pro Wegpunkt).

## Dependencies

- **Upstream:** `compareWizardState`, geteilter `LayoutTab`, Go-Handler `compare_preset.go`
- **Downstream:** Scheduler-Dispatch (`scheduler_dispatch_service.py`), `ComparisonEngine`, Vergleichs-Mail-Renderer (`compare_html.py`), Validator-Preview (`api/routers/validator.py:305-324`, `api/routers/compare.py:15-17`)

## Existing Specs

- `docs/specs/modules/issue_1256_compare_ui_rewire.md` — Constraint 2 (Z. 184-188), Stale-Spuren-Regel (Z. 247-257)
- Design-Quellen: `layout-tab.jsx` (kennt die Felder nicht), `versand-tab.jsx:93-96` (dokumentiert Entfernung), `screen-compare-editor.jsx`

## Risks & Considerations

1. **Funktionsverlust statt Aufräumen:** Ersatzloses Entfernen der Zeitfenster-Inputs nimmt dem Nutzer die Kontrolle darüber, welche Tagesstunden bewertet werden. Der Wert bliebe still auf dem gespeicherten Stand (bzw. 9–16) — die Mail zeigt ihn weiter an. Das ist kein toter Code, sondern ein aktives Feature.
2. **Bestandsdaten:** 158 gespeicherte Presets nutzen `hour_from`/`hour_to`. Read-Modify-Write im Go-Handler schützt sie, solange das Frontend die Felder schlicht nicht mehr mitschickt. Ersatzloses Löschen im Payload ist unkritisch; Löschen im Backend wäre Datenverlust.
3. **Nebenbefund — Anzeige-Lüge:** `compare_html.py:594` schreibt hartkodiert „+48h“ in die Mail, auch wenn 24 oder 72 gewählt wurde. Unabhängig vom Ausgang dieses Issues falsch.
4. **Screenshot fehlt:** `docs/artifacts/audit-1256-prod/04-edit-layout-desktop.png` (im Issue referenziert) existiert im Repo nicht.
5. **Reihenfolge zu #1273:** Dieses Issue läuft bewusst vor Epic #1273 (Hub wird der Editor), damit keine Felder umziehen, die danach wegfallen.
