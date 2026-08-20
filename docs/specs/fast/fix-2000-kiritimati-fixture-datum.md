# Mini-Spec: Kiritimati-Fixture-Datum verschieben (#2000)

## Was ändert sich
- In `tests/tdd/test_import_und_fremdquellen_folgen_ortstag.py` beide Vorkommen von
  `now_utc = datetime(2026, 8, 19, 20, 0, 0, tzinfo=timezone.utc)` /
  `erwarteter_ortstag = date(2026, 8, 20)` (Zeilen ~111-113 und ~307-309) auf ein
  sicher-vergangenes Datumspaar verschieben, z.B.
  `now_utc = datetime(2026, 5, 1, 20, 0, 0, tzinfo=timezone.utc)` /
  `erwarteter_ortstag = date(2026, 5, 2)` — gleiche Semantik (UTC-Abend → nächster Tag
  in der Kiritimati-Zone UTC+14), nur ohne Kollision mit dem echten Kalendertag.

## Was darf sich nicht ändern
- Die geprüfte Logik selbst (`gpx_to_stage_data`, `trigger_radar_alert`) bleibt unangetastet.
- Die Zeitzonen-Semantik des Tests (UTC-Abend + Kiritimati-Zone ⇒ Ortstag = UTC-Tag + 1)
  bleibt exakt erhalten — nur die konkreten Datumswerte ändern sich.
- Keine anderen Dateien.

## Manuelle Test-Schritte
1. `uv run pytest tests/tdd/test_import_und_fremdquellen_folgen_ortstag.py -v --disable-socket --allow-unix-socket`
2. Beide vorher rot gemeldeten Tests (`test_ac1_gpx_rueckfalltag_folgt_der_zone_des_ersten_wegpunkts`,
   `test_ac6_debug_trigger_radar_alert_today_folgt_trip_local_today`) müssen grün sein.
3. Restliche Tests derselben Datei weiterhin grün (keine Regression).

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Kein neuer Test nötig — bestehende Tests sind der Nachweis (waren rot wegen
      Kalenderkollision, müssen nach der Verschiebung grün sein).
