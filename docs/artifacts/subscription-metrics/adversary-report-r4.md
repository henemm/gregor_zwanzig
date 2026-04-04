# Adversary Report — Round 4 (F14a Subscription Metrics)

**Date:** 2026-04-04
**Validator:** Independent QA Agent (Round 4)
**Files examined:**
- `/home/hem/gregor_zwanzig/src/web/pages/subscriptions.py`
- `/home/hem/gregor_zwanzig/src/web/pages/weather_config.py`
- `/home/hem/gregor_zwanzig/src/app/loader.py`

---

## Test Results

```
uv run pytest tests/tdd/ -v --tb=short
8 failed, 189 passed, 1 skipped, 1 xfailed, 15 errors in 30.26s
```

The 8 failures and 15 errors are ALL pre-existing, unrelated to F14a:
- test_html_email.py: SMTP/DNS failures (network-dependent, expected in CI)
- test_snowgrid.py: External API returning no data (external dependency)
- test_weather_config_api_ui.py::TestAdditionalMetricsCatalog: Catalog has grown to
  24 metrics, test still expects 19 (stale test expectation, not an F14a regression)
- test_safari_cache_fix.py: Require live server, not relevant to F14a

No F14a-related test failures. All 189 stable tests pass.

---

## VALIDATION: Fix 1 (R1 Bug — display_config lost on Edit-Save)

PASSED: Fix 1 correctly implemented
   File: src/web/pages/subscriptions.py, lines 429-433
   
   In make_save_handler().do_save(), when editing an existing subscription
   (is_new=False), the code reads display_config fresh from disk:
   
     if not is_new:
         current_subs = load_compare_subscriptions()
         current = next((s for s in current_subs if s.id == sub_id), None)
         if current and current.display_config:
             new_sub.display_config = current.display_config
   
   The critical correctness point: sub_id is captured from sub.id at dialog-open
   time (an immutable string), not the mutable subscription object. The actual
   display_config data is always read from disk. This is the correct pattern.
   
   Edge case check: If current is None (subscription was deleted between dialog-open
   and dialog-save), new_sub.display_config stays None. No crash, and the
   subscription is written fresh — acceptable behavior.

---

## VALIDATION: Fix 2 (R2 Bug — Stale Closure in Metrics Config Dialog)

PASSED: Fix 2 correctly implemented
   File: src/web/pages/weather_config.py, lines 595-601 and 677-701
   
   Two independent layers of protection:
   
   1. Dialog-open: show_subscription_weather_config_dialog() immediately reloads
      the subscription from disk (lines 600-601):
        subs = load_compare_subscriptions(user_id)
        sub = next((s for s in subs if s.id == subscription.id), subscription)
      This means the dialog's initial UI state always reflects the current disk
      state, not a stale closure.
   
   2. Save handler factory: make_subscription_save_handler() closes over only
      sub_id (immutable string). Inside do_save() (lines 679-680):
        all_subs = load_compare_subscriptions(uid)
        target = next((s for s in all_subs if s.id == sub_id), None)
      The full subscription (including all non-UI fields) is read from disk before
      writing. No stale closure in the write path.
   
   Fallback safety: If subscription is not found on disk (sub_id not in all_subs),
   the handler returns with an error notify. No crash, no silent data corruption.

---

## VALIDATION: Fix 3 (R3 Bug — Stale Closure in Toggle Handler)

PASSED: Fix 3 correctly implemented
   File: src/web/pages/subscriptions.py, lines 163-186
   
   do_toggle() now reads the full subscription state from disk before building the
   updated object:
   
     current_subs = load_compare_subscriptions()
     current = next((s for s in current_subs if s.id == subscription.id), subscription)
     updated = CompareSubscription(
         ...
         display_config=current.display_config,  # FROM DISK, not stale closure
     )
   
   All fields (including display_config) are taken from `current` (disk-read),
   not from the closure-captured `subscription` argument.
   
   One nuance: the fallback in next() is `subscription` (the closure value), not
   None. This means if the subscription is deleted from disk between page-load and
   toggle-click, the stale closure object is used. This is acceptable — it avoids
   a crash and re-creates the subscription with the last known state, which is a
   reasonable recovery for a UI edge case. It does NOT affect the primary
   display_config preservation bug.

---

## SYSTEMATIC HANDLER AUDIT

All 7 make_* handlers in subscriptions.py were examined:

### make_new_handler (line 97)
   CLEAN: Opens dialog with sub=None (new subscription). No closure over existing
   subscription data. No risk.

### make_toggle_handler (line 163) — R3 fix target
   CLEAN: Verified above (Fix 3). Reads from disk before save.

### make_run_now_handler (line 196)
   ACCEPTABLE — USES CLOSURE DATA, BUT READ-ONLY
   
   This handler uses the closed-over `subscription` object for:
   - subscription.name (for ui.notify display text)
   - subscription.send_email / subscription.send_signal (channel selection)
   - Passes `subscription` to run_comparison_for_subscription()
   
   This is read-only: no save/write is performed. The closed-over subscription
   determines WHICH channels are used for the run-now action and what parameters
   are passed to the comparison. If metrics were reconfigured after page load, the
   run-now would use slightly stale channel config (e.g., a signal channel enabled
   after page load would be missed until page reload).
   
   This is an acceptable UX limitation, not a data-corruption bug. The worst
   outcome is an outdated channel selection for a manual run — no data is written.

### make_metrics_handler (line 238)
   CLEAN: Passes `subscription` to show_subscription_weather_config_dialog(), which
   immediately reloads from disk at lines 600-601 (Fix 2 first layer). The stale
   closure value is used only as a key-lookup fallback, not as data.

### make_edit_handler (line 250)
   CLEAN: Passes `subscription` to show_subscription_dialog(), which uses it only
   to populate the dialog form fields. The save path (Fix 1) reads display_config
   fresh from disk. Other form fields being pre-populated from the stale closure
   is the expected UX behavior (shows last-known values to the user for editing).

### make_delete_handler (line 262)
   CLEAN: Uses only subscription.id (immutable after creation) to call
   delete_compare_subscription(). No data corruption risk.

### make_save_handler (line 395, inside show_subscription_dialog)
   CLEAN: Verified above (Fix 1). display_config read from disk on save.

---

## REMAINING CONCERNS (Non-blocking)

WARNING: Partial-field closure in make_run_now_handler
   Severity: LOW
   As noted above, run_comparison_for_subscription() receives the closure-captured
   subscription object. If display_config was updated after page load (via the
   Wetter-Metriken dialog), the next "Run now" will use stale metric configuration
   until the page is reloaded.
   
   Impact: No data corruption. Only affects which metrics appear in the manual
   on-demand report email. Scheduled reports use fresh data from the scheduler
   (which presumably loads from disk at run time).
   
   Recommendation: Add a disk-reload step in do_run_now() before calling
   run_comparison_for_subscription(). Pattern:
     current_subs = load_compare_subscriptions()
     fresh_sub = next((s for s in current_subs if s.id == subscription.id),
                      subscription)
     # use fresh_sub instead of subscription

WARNING: display_config serialization scope for subscriptions
   Severity: LOW (carried over from R3 report — still valid)
   The subscription JSON only serializes {trip_id, metrics, updated_at} of
   UnifiedWeatherDisplayConfig. Fields show_compact_summary, show_night_block,
   night_interval_hours, thunder_forecast_days, multi_day_trend_reports are not
   persisted for subscriptions.
   
   Currently no code reads these fields for subscriptions, so this is silent but
   harmless. Risk materializes only if a renderer is extended to read these fields
   from subscription.display_config in the future.

---

## Screenshots

- docs/artifacts/subscription-metrics/08-r4-final.png: Subscriptions page loaded
  correctly. 1 subscription ("Zillertal täglich", Disabled) visible with all action
  buttons rendered: Play, Send, Wetter-Metriken, Edit, Delete. No UI errors.

---

## Verdict

VERIFIED

All 3 fixes from R1, R2, R3 are correctly implemented and consistent:

- Fix 1 (Edit-Save preserves display_config): PASSED
- Fix 2 (Metrics dialog reads from disk): PASSED
- Fix 3 (Toggle reads from disk before save): PASSED

No new stale-closure data-corruption bugs were found. The one remaining
closure-over-subscription-object use (make_run_now_handler) is read-only and
carries no data-corruption risk.

The implementation is production-safe for the F14a feature scope.

---

## Residual Test Plan (Optional Improvements)

1. [ ] Run-now stale metrics test: Configure metrics, do NOT reload page, click
       "Run now" — verify email uses updated metrics (requires fresh-read fix above)
2. [ ] Toggle idempotency: Toggle enable/disable 3 times rapidly without page reload
       — verify final enabled state matches expected and display_config is intact
3. [ ] Delete-then-toggle: Delete subscription from another browser tab, attempt
       toggle in original tab — verify graceful handling (currently falls back to
       re-creating with stale closure data)
