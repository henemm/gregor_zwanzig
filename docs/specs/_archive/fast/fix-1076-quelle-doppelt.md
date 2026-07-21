# Mini-Spec: fix-1076-quelle-doppelt

## Was ändert sich
- `src/output/renderers/alert/render.py:135` — Fußzeile `footer = f"Stand: heute {msg.stand_at} · Quelle: {e.source_label}"` verliert den Suffix `· Quelle: {e.source_label}`, wird zu `footer = f"Stand: heute {msg.stand_at}"`.
- Ergebnis: „Quelle:" erscheint nur noch einmal (im Datenblock, Zeile 130), nicht mehr zusätzlich in der Fußzeile.

## Was darf sich nicht ändern
- Der Datenblock-Eintrag `("Quelle", e.source_label)` (render.py:130) bleibt unverändert bestehen.
- Die Fußzeile behält `Stand: heute {msg.stand_at}` als Präfix.
- Kein `km`-Bezug in der Fußzeile (bestehende Erwartung aus `test_952_onset_alert_fidelity.py`).

## Manuelle Test-Schritte
1. `uv run pytest tests/tdd/test_issue_822_radar_nowcast_segment.py::test_ac4_mail_body_contains_segment_label_and_cooldown -v`
2. `uv run pytest tests/tdd/test_issue_883_acute_danger_override.py::test_ac4_override_mail_wording_not_unannounced -v`
3. `uv run pytest tests/tdd/test_952_onset_alert_fidelity.py tests/tdd/test_952_onset_alert_e2e.py -v` (Regressionscheck: Datenblock-Labels + Fußzeilen-Regex bleiben grün)

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Bestehende Tests aus #1076 (s.o.) werden von rot auf grün gebracht — kein neuer Test nötig, da bereits vorhanden und die erwartete Semantik (`count("Quelle:") == 1`) prüfen.
