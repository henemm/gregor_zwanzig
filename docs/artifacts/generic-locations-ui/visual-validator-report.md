# Visual Validator Report — F11b Generic Locations UI

**Date:** 2026-04-04
**Validator:** Independent QA (Validation Agent)
**Spec:** `docs/specs/modules/generic_locations_ui.md`
**Screenshots evaluated:** 4

---

## Methodology

Each Expected Behavior point from the spec is checked against screenshot evidence only.
Verdict categories:
- PASS — clear visual evidence confirms the spec requirement
- FAIL — spec requires X, screenshot shows the opposite or X is absent
- NOT VERIFIABLE — screenshot does not provide enough information to decide

---

## Check 1: Create Dialog has "Aktivitätsprofil" dropdown with default "Allgemein"

**Screenshot:** 02-create-dialog.png

**What the spec says:**
> profile_select = ui.select(..., value=LocationActivityProfile.ALLGEMEIN.value, label="Aktivitätsprofil")

**What I see:**
The "New Location" dialog has a dropdown field labeled "Aktivitätsprofil" (label visible above the control). The selected value shown is "Allgemein". The dropdown appears at the bottom of the form, after the Bergfex Slug field, exactly as spec positions it.

**Finding: PASS**

The label text in the screenshot reads "Aktivit ät sprofil" — the characters are split with spaces around "ät", which looks like a rendering artifact or font-kerning issue in the screenshot but could be an actual label encoding problem. The word "Aktivitätsprofil" contains "ä" (U+00E4). If the label was defined as a plain ASCII string with escaped unicode or as split words, the rendered label would appear broken. This is a minor UI issue but the label is still readable.

**Secondary finding: WARNING — label rendering has unexpected spacing ("Aktivit ät sprofil")**

---

## Check 2: Badge on every Location Card shows the profile (e.g., "Allgemein")

**Screenshot:** 01-locations-page.png

**What the spec says:**
> ui.badge(loc.activity_profile.value.capitalize(), color="blue-grey")
> Badge "Wandern" shown on card

**What I see:**
Every visible card has a badge. All five visible cards show an "Allgemein" badge (grey-blue background, white text). The badge appears first in the badge row, before region and bergfex badges. The color appears to be a grey-blue, consistent with "blue-grey".

**Finding: PASS**

One observation: all 13 locations show "Allgemein". This is consistent with the fact that no location in the dataset has had a profile other than the default assigned. This does not prove the badge would update for a "Wandern" location (the scenario in the spec), but the display mechanism is functioning correctly for "Allgemein". The spec's expected output ("Badge 'Wandern' shown on card") is not demonstrated by any screenshot — that scenario would require a test location saved with profile=wandern.

**Coverage gap: The "Wandern" badge variant is not shown in any screenshot.**

---

## Check 3: "Wetter-Metriken" Button on every Location Card

**Screenshot:** 01-locations-page.png

**What the spec says:**
> ui.button("Wetter-Metriken", icon="settings", on_click=...).props("flat color=primary")
> Button in location card (right button group, before Edit)

**What I see:**
Every visible card has a gear icon followed by "WETTER-METRIKEN" text rendered in blue. It appears before the pencil (edit) icon and the delete icon. The icon matches "settings" (gear symbol). The color is blue, consistent with "color=primary".

**Finding: PASS**

---

## Check 4: Weather-Metriken Dialog shows metrics grouped by category

**Screenshot:** 04-weather-config-dialog.png

**What the spec says:**
> ├─ Per category:
> │  ├─ Category separator + label
> └─ Per metric: Checkbox + Aggregation multi-select

**What I see:**
The dialog shows three visible category headers: "Temperatur", "Wind", "Niederschlag". Each category header acts as a separator row with the category name as a label. Under each header, individual metric rows are shown (e.g., "Temperatur (Temp)", "Gefühlte Temperatur (Feels)", "Luftfeuchtigkeit (Humid)", "Taupunkt (Cond°)" under Temperatur; "Wind (Wind)", "Boen (Gust)", "Windrichtung (WDir)" under Wind; "Niederschlag (Rain)", "Regenwahrscheinlichkeit [cut off]" under Niederschlag).

The dialog is truncated at the bottom — it appears the full list extends below the visible area. This is expected as the scroll is mid-dialog.

**Finding: PASS**

---

## Check 5: Dialog shows Profile-Info (e.g., "Profil: Allgemein")

**Screenshot:** 04-weather-config-dialog.png

**What the spec says:**
The spec dialog structure does not explicitly mandate a "Profil:" label line in the dialog body. However it shows `location.activity_profile` should be used to build defaults. The spec says:

> Initializes config from location.display_config or build_default_display_config_for_profile(location.id, location.activity_profile)

Looking at the screenshot title: "Wetter-Metriken: Hochkönig/Sonnberg". Directly below the title, in smaller text, the label "Profil: Allgemein" is visible.

**What I see:**
The line "Profil: Allgemein" is present in small text directly below the dialog title and above the "Metrik | Aggregation" header row. This is consistent with the implementation showing which profile governs the metric defaults.

**Finding: PASS**

Note: This element is not explicitly in the spec's dialog structure diagram, but it is present and provides useful information. It does not conflict with the spec.

---

## Check 6: Metrics have Checkboxes (enable/disable) and Aggregation selection

**Screenshot:** 04-weather-config-dialog.png

**What the spec says:**
> ├─ Checkbox (enabled/disabled, grayed if provider unavailable)
> └─ Aggregation multi-select (Min/Max/Avg/Sum)

**What I see:**
Each metric row has a checkbox on the left. Some are checked (Temperatur/Temp: checked, Wind: checked, Boen: checked, Niederschlag: checked). Some are unchecked (Gefühlte Temperatur, Luftfeuchtigkeit, Taupunkt, Windrichtung, and Regenwahrscheinlichkeit row is partially visible).

To the right of each metric, there is a dropdown control. Visible values are: "Min, Max, Avg", "Min", "Avg", "Avg", "Max", "Max", "Avg", "Sum".

**Issue with aggregation control type:** The spec says "Aggregation multi-select (Min/Max/Avg/Sum)". A multi-select would allow selecting multiple values simultaneously. The visible dropdowns each show a single selected value (e.g., "Min", "Avg", "Max"). If these are standard single-select dropdowns, they do not fulfill the "multi-select" requirement. The "Temperatur (Temp)" row shows "Min, Max, Avg" which does appear to be multiple values selected, suggesting this IS a multi-select that shows comma-separated selected values. The other rows showing single values may have only one value selected.

**Finding: PASS** — The evidence is consistent with multi-select dropdowns showing comma-separated selected values where multiple are chosen.

---

## Check 7: Edit Dialog has "Aktivitätsprofil" Dropdown with current value

**Screenshot:** 03-edit-dialog.png

**What the spec says:**
> profile_select = ui.select(..., value=loc.activity_profile.value, label="Aktivitätsprofil")

**What I see:**
The "Edit Location: Hochkönig/Sonnberg" dialog has a dropdown labeled "Aktivit ät sprofil" (same spacing artifact as in create dialog). The selected value is "Allgemein", which matches the badge displayed on the card for this location.

**Finding: PASS**

**Same secondary finding applies: WARNING — label "Aktivit ät sprofil" has unexpected space characters around "ät"**

---

## Additional UI Issues

### Issue A: Label Encoding Artifact — "Aktivit ät sprofil"

Both the create dialog (screenshot 02) and the edit dialog (screenshot 03) show the label "Aktivit ät sprofil" with visible spaces around the "ät" characters. The expected label is "Aktivitätsprofil" as a single word.

This could indicate:
1. The `ä` character (U+00E4) is being broken by the rendering engine (unlikely in NiceGUI)
2. The label string in source code has literal spaces: `"Aktivit ät sprofil"` (typo in source)
3. A font or CSS rendering artifact in the screenshot tool

**Severity:** Medium. The label is still recognizable, but it is grammatically incorrect and looks unprofessional. If the source string has literal spaces this is a code defect.

### Issue B: Dialog is cropped / not scrollable in screenshot

Screenshot 04 shows the dialog cuts off mid-dialog with "Regenwahrscheinlichkeit" partially visible. The dialog appears to extend beyond the viewport. This may be intentional (the screenshot captures the dialog in a scrolled state) or may indicate the dialog lacks proper scrolling behavior and is clipped.

**Severity:** Low if scrollable. The spec does not specify dialog height constraints. Cannot determine from static screenshot whether the dialog scrolls correctly to reveal all metrics.

### Issue C: Aggregation dropdown values not cross-checked against spec list

The spec specifies aggregation options "Min/Max/Avg/Sum". The visible dropdown values in screenshot 04 include "Min", "Max", "Avg", "Sum" — all spec-compliant. No non-spec values are visible.

### Issue D: Provider graying not verifiable from screenshots

The spec requires:
> Checkbox (enabled/disabled, grayed if provider unavailable)
> GeoSphere-only metrics grayed out with tooltip (for non-Austria locations)

All visible metrics have standard black text and normal-looking checkboxes. No grayed-out metrics are visible. Since all test locations appear to be in Austria (coordinates 47.x N, 10-13 E), GeoSphere is available for all of them. The grayed-out state for non-Austria locations cannot be verified from these screenshots.

**Severity:** NOT VERIFIABLE from current screenshots.

---

## Summary Table

| # | Spec Requirement | Verdict | Notes |
|---|-----------------|---------|-------|
| 1 | Create Dialog: "Aktivitätsprofil" dropdown, default "Allgemein" | PASS | Label has spacing artifact |
| 2 | Badge on every card showing profile | PASS | Only "Allgemein" shown; "Wandern" variant not tested |
| 3 | "Wetter-Metriken" button on every card | PASS | Gear icon, correct position, correct color |
| 4 | Dialog groups metrics by category | PASS | Temperatur / Wind / Niederschlag headers visible |
| 5 | Dialog shows "Profil: Allgemein" info | PASS | Visible in subtitle below dialog title |
| 6 | Checkboxes and aggregation multi-select | PASS | Multi-value selection visible ("Min, Max, Avg") |
| 7 | Edit Dialog: dropdown with current value | PASS | Shows "Allgemein" matching card badge |

---

## Coverage Gaps (Not Verifiable)

| Gap | Reason | Recommended Test |
|-----|--------|-----------------|
| "Wandern" badge on card | No location with profile != Allgemein in dataset | Create location with Wandern profile, verify badge |
| Provider graying (non-Austria) | All test locations are in Austria | Open Wetter-Metriken for a Corsica/GR20 location |
| Dialog scrolling | Static screenshot does not show scroll behavior | Manually scroll dialog in browser |
| "Wintersport" profile option | No location shows it, dropdown options not expanded | Open dropdown in create dialog, verify all options |
| Saving metric config | No "after save" screenshot | Save config, reopen dialog, verify persistence |
| Edit: profile change reflected in badge | No screenshot after profile change | Change profile via edit, verify badge updates |

---

## Defects Found

### DEFECT-01: Label Rendering — "Aktivit ät sprofil"

**Location:** Create dialog (screenshot 02), Edit dialog (screenshot 03)
**Expected:** "Aktivitätsprofil" as a single word
**Observed:** "Aktivit ät sprofil" with spaces around "ät"
**Impact:** Minor cosmetic defect; label is still readable
**Action required:** Verify source code string. If source contains spaces, fix the string. If it is a rendering artifact, investigate font/CSS handling of German umlauts in NiceGUI.

### No functional defects found in the verified checks.

---

## Test Plan

### Automated Tests

- [ ] Unit test: Save new location with profile="wandern", reload, verify `activity_profile == WANDERN`
- [ ] Unit test: `get_available_providers_for_location()` — lat=47.3, lon=11.4 returns {"openmeteo", "geosphere"}
- [ ] Unit test: `get_available_providers_for_location()` — lat=42.0, lon=9.0 returns {"openmeteo"} only
- [ ] Unit test: `build_default_display_config_for_profile(id, WANDERN)` returns exactly 9 metrics
- [ ] Unit test: Save metric config with 0 enabled metrics triggers validation error

### Manual / Visual Tests

- [ ] Create location with profile "Wandern" — verify badge shows "Wandern" (not "wandern" or "WANDERN")
- [ ] Create location with profile "Wintersport" — verify badge shows "Wintersport"
- [ ] Verify label "Aktivitätsprofil" renders as one word (no extra spaces around ä)
- [ ] Open Wetter-Metriken for non-Austria location (e.g., GR20/Corsica) — verify GeoSphere metrics are grayed
- [ ] Open Wetter-Metriken for Austria location — verify NO metrics are grayed
- [ ] Scroll Wetter-Metriken dialog to bottom — verify all metric categories visible, no content clipped
- [ ] Change profile in Edit dialog (Allgemein -> Wandern), save, verify badge updates on card
- [ ] Save metric config, navigate away, return — verify persistence (dialog opens with saved state)
- [ ] Attempt to save metric config with all checkboxes off — verify warning notification appears
- [ ] Verify aggregation multi-select allows selecting all four options: Min, Max, Avg, Sum simultaneously
