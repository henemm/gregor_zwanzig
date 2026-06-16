# Test-Spec Bug #838 — day_comparison Kwarg Regression

Tests für `tests/tdd/test_bug_838_day_comparison_kwarg.py`.

## ac1_format_email_has_no_day_comparison_param
Prüft per inspect.signature, dass format_email() keinen day_comparison-Parameter mehr hat.

## ac2_scheduler_does_not_pass_day_comparison
Prüft per AST-Analyse, dass kein format_email()-Aufruf im Scheduler day_comparison übergibt.

## ac2_scheduler_has_no_dead_day_comparison_block
Prüft, dass der tote Berechnungsblock (day_comparison = None) aus dem Scheduler entfernt wurde.

## ac1_send_trip_report_no_typeerror
Prüft, dass _send_trip_report() keinen TypeError durch day_comparison wirft.
