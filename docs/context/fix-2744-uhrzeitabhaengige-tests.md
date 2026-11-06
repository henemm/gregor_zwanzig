# Context: fix-2744-uhrzeitabhaengige-tests

## Request Summary
Python-Tests, die die echte Uhr lesen, werden kurz vor UTC-Mitternacht (und am Minutenwechsel) rot und blockieren Merges. Sie sollen die Uhr fest setzen und zu jeder Tageszeit grün laufen (#2744, Epic #1196, Bezug #1199).

## Nachgestellt (2026-11-06)
`GZ_TEST_WALL_CLOCK_UTC=2026-11-05T23:40:00+00:00` + die vier Issue-Tests:
- ROT: `test_f002_ruhezeit_folgt_der_heutigen_etappe_nicht_der_ersten`, `test_f002_tageszaehler_folgt_der_heutigen_etappe_nicht_der_ersten` (Assert `abrufe_bei_vollem_la >= 1` ist 0).
- Bei 12:00 UTC beide GRÜN.
- Die zwei Gestern-Zone-Tests kippten unter dem Schalter nicht: sie lesen die echte Zeit bewusst per Subprozess `date -u` (#2096). Sie hängen an der echten Laufzeit, nicht an der gestellten Uhr.

## Related Files
| File | Relevance |
|------|-----------|
| tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py:125-148 | `fenster_um_jetzt()` und `ortstag()` lesen `datetime.now(UTC)` selbst; Zeilen 1636/1663 die roten f002-Tests |
| tests/helpers/nowcast_gate_fixtures.py:300 | `seed_daily_counter` / `local_today(zone)`: Zählertag je Zone aus der echten Uhr |
| tests/tdd/test_prozesszonen_schalter.py:90-100, 182-205 | `_gestern_zone_fuer_jetzt`: Marquesas bis 09:30 UTC, danach `<-2330>+23:30` (trägt nur bis 23:30 UTC) |
| tests/tdd/test_ortstag_helfer.py:217-244 | gleiche Zonenwahl, aber Grenze `hour < 9` statt 09:30: Lücke 09:00–09:30 UTC |
| tests/unit/test_briefing_html_sprache.py:138 + tests/helpers/briefing_html_sprache_fixture.py:92 | `render_reich()` zweimal gerendert; Zeitstempel `11:16` gegen `11:17 CET` am Minutenwechsel |
| tests/conftest.py:711 `_gestellte_wanduhr`, tests/helpers/wanduhr.py | vorhandener Session-Schalter (freeze_time, tick=True) |

## Befund (Hypothese, teils nachgestellt)
1. Zonenwahl der "Gestern-Zone" deckt 23:30–24:00 UTC nicht ab (POSIX `+23:30` = UTC−23:30; ab 23:30 UTC ist dort wieder derselbe Tag). Noch nicht nachgestellt.
2. Grenze 09:00 gegen 09:30 UTC ist zwischen zwei Dateien uneinheitlich. Noch nicht nachgestellt.
3. Die f002-Tests mischen Auckland/LA-Ortstage aus der echten Uhr. Um UTC-Mitternacht fallen "heute" je Zone auseinander, das ±45-min-Fenster kippt über Mitternacht. Nachgestellt bei 23:40 UTC.
4. Briefing-HTML enthält einen Erzeugungszeitstempel; zwei Renderläufe können über den Minutenwechsel laufen. Aus Issue-Kommentar übernommen, noch nicht nachgestellt.

## Existing Patterns
- `freeze_time` aus freezegun (Suite-Standard), Session-Schalter `GZ_TEST_WALL_CLOCK_UTC`.
- Tests mit Subprozess lesen die echte Zeit bewusst per `date -u` (#2096).

## Dependencies
- Upstream: freezegun, `tests/conftest.py` Prozesszonen-Knopf `GZ_TEST_PROCESS_TZ`; Prüflinge `trip_alert` / `alert_daily_limit` (unverändert).
- Downstream: CI-Job `test` (Merge-Gate).

## Existing Specs
- Specs zu #2096 (Wanduhr-Schalter) und #2314 (Prozesszone): in /20-analyse prüfen.

## Analyse (Phase 2, 2026-11-06)

### Ursachen (je eigene Fehlerklasse)
1. **f002-Tests (nachgestellt 23:40 UTC):** `fenster_um_jetzt`, `ortstag`, `trip_zwei_zonen`, `local_today` lesen `datetime.now(UTC)` selbst; der Trip legt Etappe 2 auf den UTC-Tag. Um UTC-Mitternacht ist der Ortstag in Auckland schon der Folgetag, das gesetzte Los-Angeles-Kontingent trägt nicht mehr. Fix: pro Test `freeze_time` auf einen festen Mittags-Zeitpunkt (alle Zonen am selben Kalendertag wie UTC). Prüflinge bleiben unverändert (freezegun patcht `datetime.now` überall).
2. **Gestern-Zone-Tests:** Zonenwahl `<-2330>+23:30` trägt nur bis 23:30 UTC; 23:30–24:00 UTC ist ungedeckt. Die Tests müssen die ECHTE Zeit lesen (Subprozess, #2096), Einfrieren hilft nicht. Fix: Zonenwahl an EINER Stelle (Hilfsfunktion in `tests/helpers/`), die auch 23:30–24:00 abdeckt (Kandidat `<-24>+24`; ob glibc Stunden bis 24 akzeptiert, ist in /30 per Messung zu belegen, sonst zweite Zone), Grenze einheitlich 09:30 statt 09:00 in `test_ortstag_helfer.py`.
3. **Briefing-HTML-Test:** `render_reich()` wird zweimal gerendert, der Zeitstempel kann über den Minutenwechsel laufen. Fix: `freeze_time` um beide Renderläufe.
4. **`R@Mo0:03`-Format-Test (aus Issue):** nicht eindeutig zugeordnet; Quelle in /30 suchen, sonst eigenes Nebenbefund-Issue.

### Offen
- Ob der rote LA-Lauf um 23:40 UTC nur ein Testartefakt oder ein echter Produktfehler ist (Etappenwahl bei Tageswechsel), ist nicht geklärt. Vor /30 unter `freeze_time(23:40)` reproduzieren.
- Mutations-Gegenprobe Pflicht: Verfälschung `anchor_tz`→`trip_tz` muss unter gefrorener Uhr weiter beide f002-Tests rot machen.

### Umfang
Nur Testcode, 4–6 Dateien, deutlich unter 250 LoC.

## Risks & Considerations
- Nur Tests ändern, kein Produktivcode.
- Die Gestern-Zone-Tests prüfen die Wirkung des Schalters im echten Prozess. Einfrieren darf diese Aussage nicht aushöhlen (Mutations-Gegenprobe Pflicht).
- Kein Mock-Theater: `freeze_time` ist erlaubt, kein Mock der Prüflinge.
- Das Fenster 23:30–24:00 UTC braucht eine tragende Zone oder eine fest gesetzte Uhr.
