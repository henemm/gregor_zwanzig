---
entity_id: bug_545_549_550_retrospective_fixes
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [bug, backend, frontend, compare-email, trip-detail, cleanup]
---

# Bug #545 / #549 / #550 — Retrospektive Adversary-Fixes (Gruppe C+D, Issue #510)

## Approval

- [ ] Approved

## Purpose

Drei Bugs aus dem Adversary-Review-Sprint (Issue #510, Gruppe C+D) werden zusammen
behoben. Bug #545 behebt einen Python-Typ-Mismatch in `compare_html.py`, der im
Produktionspfad `AttributeError` auslöst, weil `_generate_winner_tags()` Tupel
zurückgibt, aber `_render_winner_tags()` Dicts erwartet. Bug #549 entfernt einen
inline editierbaren Etappen-Editor aus der Leseansicht (`TripTabs.svelte`), der
gegen AC-2 der Spec `issue_503_wegpunkt_editor_fix.md` verstößt. Bug #550 legt zwei
fehlende Wrapper-Komponenten an, die laut Spec `issue_190_alter_wizard_cleanup.md`
AC-2 in `frontend/src/lib/components/edit/` existieren müssen.

## Source

- **File (Backend):** `src/output/renderers/email/compare_html.py`
  - **Identifier:** `_generate_winner_tags()` (Zeile 143), `_render_winner_tags()` (Zeile 272)
- **File (Test):** `tests/tdd/test_compare_html_email.py`
  - **Identifier:** `TestWinnerTags::test_ac1_render_html_enthält_snow_tag` + 2 Assertions auf Tupel-Format
- **File (Frontend):** `frontend/src/lib/components/trip-detail/TripTabs.svelte`
  - **Identifier:** stages-Tab-Content (Zeilen 115–118)
- **File (Frontend, NEU):** `frontend/src/lib/components/edit/EditStagesSection.svelte`
- **File (Frontend, NEU):** `frontend/src/lib/components/edit/EditWeatherSection.svelte`

> Schicht: Python-Backend (`src/output/renderers/email/`) für #545,
> SvelteKit-Frontend (`frontend/src/lib/components/`) für #549 und #550.

## Estimated Scope

- **LoC:** ~35 (Backend: 5, Tests: 10, Frontend: 20)
- **Files:** 5 (1 modify backend, 1 modify test, 1 modify frontend, 2 neue Svelte-Dateien)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/compare_html.py` | Python-Modul (vorhanden) | Enthält `_generate_winner_tags()` (fix return type) und `_render_winner_tags()` (Aufrufer, kein Umbau nötig) |
| `tests/tdd/test_compare_html_email.py` | Pytest-Testdatei (vorhanden) | `TestWinnerTags` — 1 fehlschlagender Test + 2 Assertions auf Tupel-Format werden auf Dict umgestellt |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Svelte-Komponente (vorhanden) | stages-Tab: `EditStagesPanelNew` inline → Redirect-Link zu `/trips/{id}/edit` |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Svelte-Komponente (vorhanden) | Wird in `EditStagesSection.svelte` re-exportiert (thin wrapper) |
| `frontend/src/lib/components/edit/WeatherSummaryCard.svelte` | Svelte-Komponente (vorhanden) | Wird in `EditWeatherSection.svelte` re-exportiert (thin wrapper) |

## Implementation Details

### Fix #545 — `_generate_winner_tags()` gibt `list[dict]` zurück

`_render_winner_tags()` ruft `tag.get("tone")` auf und erwartet damit `dict`-Objekte.
`_generate_winner_tags()` erzeugt aber aktuell `list[tuple[str, str]]`.

Änderung in `compare_html.py`, Funktion `_generate_winner_tags()`:

```python
# VORHER (gibt Tupel zurück):
return tags  # tags = [(tone, label), ...]

# NACHHER (gibt Dicts zurück):
return [{"tone": t, "label": l} for t, l in tags]
```

Der Return-Type-Hint der Funktion wird entsprechend auf `list[dict[str, str]]` angepasst.

### Fix #545 — Test-Assertions in `TestWinnerTags` auf Dict-Format umstellen

In `tests/tdd/test_compare_html_email.py`, Klasse `TestWinnerTags`:

Zwei Assertions, die aktuell auf Tupel-Format prüfen:
```python
# VORHER:
assert ("good", "Über den Wolken") in tags
```

werden auf Dict-Format umgestellt:
```python
# NACHHER:
assert {"tone": "good", "label": "Über den Wolken"} in tags
```

Der fehlschlagende Test `test_ac1_render_html_enthält_snow_tag` wird danach grün.

### Fix #549 — stages-Tab in `TripTabs.svelte`: inline-Editor entfernen

Zeilen 115–118 in `TripTabs.svelte` rendern derzeit `<EditStagesPanelNew>` inline.
Dies wird ersetzt durch einen Redirect-Hinweis mit Link zu `/trips/{id}/edit`.

```svelte
<!-- VORHER: inline EditStagesPanelNew -->
{#if activeTab === 'stages'}
  <EditStagesPanelNew {trip} bind:localStages />
{/if}

<!-- NACHHER: Leseanzeige mit Redirect-Link -->
{#if activeTab === 'stages'}
  <div class="stages-redirect">
    <p>Etappen und Wegpunkte können im Editor bearbeitet werden.</p>
    <a href="/trips/{trip.id}/edit" class="btn btn-primary">Zum Editor</a>
  </div>
{/if}
```

Import von `EditStagesPanelNew` und die `localStages`-State-Variable werden entfernt.

### Fix #550 — Zwei fehlende Wrapper-Komponenten anlegen

`EditStagesSection.svelte` (thin wrapper):

```svelte
<script>
  import EditStagesPanelNew from '$lib/components/edit/EditStagesPanelNew.svelte';
  export let trip;
  export let localStages = [];
</script>

<EditStagesPanelNew {trip} bind:localStages />
```

`EditWeatherSection.svelte` (thin wrapper):

```svelte
<script>
  import WeatherSummaryCard from '$lib/components/edit/WeatherSummaryCard.svelte';
  export let trip;
</script>

<WeatherSummaryCard {trip} />
```

Beide Dateien landen in `frontend/src/lib/components/edit/`.

## Expected Behavior

- **Input (#545):** `render_compare_html()` mit einem Gewinner-Objekt, das `snow_depth_cm=120` enthält und `ActivityProfile.WINTERSPORT` als Profil
- **Output (#545):** HTML-String ohne Exception; enthält `#dcf2e1` (good-Ton-Farbe) und `Schneehöhe 120 cm`
- **Input (#549):** User öffnet `/trips/{id}` und wechselt auf Tab „Etappen & Wegpunkte"
- **Output (#549):** Kein editierbares Formular mit Save-Button — stattdessen Hinweis-Text und Link zu `/trips/{id}/edit`
- **Side effects (#550):** `EditStagesSection.svelte` und `EditWeatherSection.svelte` existieren als importierbare Komponenten in `edit/`

## Acceptance Criteria

**AC-1:** Given `render_compare_html()` wird mit `winner_tags=_generate_winner_tags(winner, ActivityProfile.WINTERSPORT)` aufgerufen und `winner.snow_depth_cm=120` / When die Funktion läuft / Then wirft sie KEINE Exception und das HTML enthält `#dcf2e1` und `Schneehöhe 120 cm`.
  - Test: (populated after /tdd-red)

**AC-2:** Given `_generate_winner_tags()` wird aufgerufen und erzeugt Tags / When der Rückgabewert inspiziert wird / Then ist er `list[dict]` mit Schlüsseln `"tone"` und `"label"` — keine Tupel.
  - Test: (populated after /tdd-red)

**AC-3:** Given der User öffnet einen Trip auf `/trips/{id}` und klickt auf den Tab „Etappen & Wegpunkte" / When der Tab-Content gerendert wird / Then sieht er KEIN editierbares Formular mit Save-Button — stattdessen einen Hinweis mit Link.
  - Test: (populated after /tdd-red)

**AC-4:** Given der User klickt im stages-Tab auf den Weiterleitungs-Link / When der Klick verarbeitet wird / Then landet er auf `/trips/{id}/edit`.
  - Test: (populated after /tdd-red)

**AC-5:** Given der Cleanup abgeschlossen ist / When man `frontend/src/lib/components/edit/` auflistet / Then existieren `EditStagesSection.svelte` UND `EditWeatherSection.svelte`.
  - Test: (populated after /tdd-red)

## Affected Files

| Datei | Bug | Änderung |
|-------|-----|---------|
| `src/output/renderers/email/compare_html.py` | #545 | `_generate_winner_tags()`: Return `[{"tone": t, "label": l} for t, l in tags]` statt roher Tupel-Liste; Return-Type-Hint auf `list[dict[str, str]]` |
| `tests/tdd/test_compare_html_email.py` | #545 | 2 Assertions von Tupel-Format auf Dict-Format umstellen; `test_ac1_render_html_enthält_snow_tag` wird grün |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | #549 | stages-Tab: `<EditStagesPanelNew>` ersetzen durch Redirect-Link zu `/trips/{id}/edit`; Import + `localStages`-State entfernen |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | #550 | NEU: thin wrapper, re-exportiert `EditStagesPanelNew` |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | #550 | NEU: thin wrapper, re-exportiert `WeatherSummaryCard` |

## Known Limitations

- Bug #545 ändert nur die Return-Struktur von `_generate_winner_tags()`. Die restliche
  Logik der Funktion (Tonauswahl, Label-Berechnung) bleibt unverändert.
- Bug #549 entfernt den inline-Editor vollständig aus der Leseansicht. Falls der `localStages`-State
  in anderen Teilen von `TripTabs.svelte` genutzt wird, muss dort ebenfalls aufgeräumt werden —
  laut Analyse ist `localStages` ausschließlich für `EditStagesPanelNew` eingeführt worden.
- Bug #550 legt nur Wrapper-Dateien an. Da kein Aufrufer diese Namen aktuell erwartet,
  ist das Risiko eines Regressions-Seiteneffekts null.

## Changelog

- 2026-06-02: Initial spec erstellt (Bugs #545, #549, #550 — Adversary-Retrospektive aus Issue #510, Gruppe C+D).
