# Adversary Dialog — F11a Generic Locations

## Date: 2026-04-04

## Checklist

- [x] SavedLocation with activity_profile="wandern" — test_explicit_activity_profile PASSED
- [x] JSON contains activity_profile, display_config null — test_json_contains_activity_profile PASSED
- [x] WANDERN defaults: 9 correct metrics — test_wandern_defaults PASSED
- [x] Legacy JSON defaults to ALLGEMEIN — test_backward_compat_no_activity_profile PASSED
- [x] display_config round-trip — test_save_load_with_display_config PASSED
- [x] Profile change preserves display_config — independent fields, code inspection verified

## Deferred (F11b)

- Profile badge on card (UI)
- Wetter-Metriken dialog (UI)
- Save metrics config (UI)

### Runde 1

Adversary prüfte alle 6 Core-Punkte gegen Tests und Code. 5/6 sofort bewiesen via Test-Output. Punkt 6 (profile change preserves display_config) via Code-Inspection bestätigt — activity_profile und display_config sind unabhängige Felder.

### Runde 2

Adversary fand Defekt: `ValueError` bei korruptem activity_profile String crasht `load_all_locations()`. Except-Clause fing nur `(json.JSONDecodeError, KeyError)`. Fix: `ValueError` hinzugefügt. Nach Fix: 41/41 Tests PASS.

### Runde 3

Re-Verification nach Fix: Alle 20 Feature-Tests + 21 Regressions-Tests bestanden. Kein weiterer Defekt gefunden.

## Verdict
**VERIFIED**
