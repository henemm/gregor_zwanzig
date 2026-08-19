# Context: fix-1948-s3-sms-sofortfix

## Request Summary
Scheibe S3 des freigegebenen Alarm-Format-Konzepts v3 (#1948, `docs/analysis/alarm-format-konzept-2026-08.md` §8):
Δ-Alarm-SMS (Zweig a) — Vergleichszeitpunkt-Präfix `@HH:MM` komplett aus dem SMS-Kopf entfernen
(löst Auslöser-Bug #1948 UND #1939 strukturell), `->`-Notation ohne Vorzeichen-Präfix einführen (§3),
`LEVELS`-Stufenbuchstaben in `_sms_token()` verdrahten (§9). Zielbild: `Ziel: TH:M->H@16` · `Ziel: VS1400->280@14`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py` | EINZIGE Quelldatei. `render_sms` Z.793-794 (`@{reference_at}`-Präfix), `_sms_token` Z.707-713 (`{sign}{code}{von}>{bis}` + `@{occurred_at[:2]}`), `_code` Z.104 (`get_sms_code`) |
| `src/output/tokens/metrics.py:14` | `LEVELS = {0:"-",1:"L",2:"M",3:"H"}` — existiert, wird nur vom Briefing-Builder genutzt |
| `src/app/metric_catalog.py:415-431` | thunder-Metrik: `sms_code="TH"`, `dp_field="thunder_level"`, `default_format_mode="symbol"` — Kandidat für Level-Erkennung |
| `src/output/tokens/builder.py:18,479` | Briefing-Referenz: `FORECAST_TH = "TH:"` (Doppelpunkt hardcoded), `is_level=True` nur dort |
| `tests/tdd/test_alert_reference_timestamp.py` | 6 Tests aus #1916 — SMS-Assertions drehen auf „kein `@HH:MM` mehr"; E-Mail-Assertions bleiben |
| `tests/tdd/test_alert_sms_segment_head.py` | #1935/#1779: assertet `-VS1400>280`, `+G30>80@15`, `+R2>30@16` → auf `->`-Notation umstellen |
| `tests/tdd/test_alert_sms_location_positions.py` | #1939 K1-K4 (`live`-markiert): erwarten kopflosen Compare-Pfad OHNE Zeitstempel — werden durch S3 grün |

## Existing Patterns
- Briefing-SMS ist lebende Referenz: `TH:M@14(H@18)` via `render_threshold_peak_value(is_level=True)` + `LEVELS` (`metrics.py`). Doppelpunkt gehört zum TH-Symbol (`FORECAST_TH="TH:"`), numerische Metriken ohne Doppelpunkt (`VS1400`).
- `@` = Beginn-Zeitpunkt, Stundenauflösung ohne führende Null im Briefing (`sms_format.md:52`); `_sms_token` nutzt heute `occurred_at[:2]` (ergibt `@09` MIT führender Null).
- Compare-Änderungspfad (`location_positions is not None`): kopflos, Token `{sign}{code}{bis}` — Ortsvergleich ist im Konzept ZURÜCKGESTELLT, Token bleibt byte-identisch (#1467 AC-9).

## Dependencies
- Upstream: `AlertEvent` (`model.py:12`, `value_from/value_to/occurred_at/metric_id`), `get_sms_code` (`metric_catalog.py:1213`), `AlertMessage.reference_at` (bleibt im DTO — E-Mail nutzt ihn weiter, Z.547/602).
- Downstream: Premium-SMS nutzt denselben Renderer (kein eigener) → erbt automatisch. Telegram zeigt `reference_at` heute gar nicht → S6-Frage, hier tabu. Dedupe-Schlüssel basiert auf Events, nicht auf gerendertem Text (#1954) — unberührt.

## Existing Specs
- Obsolet: `docs/specs/modules/fix_1948_1939_alarm_sms_referenzzeitpunkt.md` (laut Konzept v3 §8 durch S3 VOLLSTÄNDIG ersetzt — „entfernen statt umformulieren").
- Konzept (PO-freigegeben, Runde 4): `docs/analysis/alarm-format-konzept-2026-08.md`.

## Risks & Considerations
- **Level-Erkennung im Alarm-Pfad existiert nicht** — Briefing hardcodet `is_level=True` im TH-Zweig. S3 braucht eine Erkennungsregel aus dem Katalog (kein Renderer-Hardcode); Kandidat: thunder-spezifische Katalog-Eigenschaft. Doppelpunkt-Form `TH:` muss für Level-Token erzeugt werden (Katalog liefert `TH` ohne Doppelpunkt).
- Mehrere Bestandstests asserten das alte Format byte-genau — Anpassung ist Teil der Scheibe, KEIN Ausweichen auf „Tests grün lassen".
- Compare-Pfad-Invariante (byte-identisch) darf nicht kippen; #1939-K-Tests sind `live`-markiert und laufen nicht im Commit-Gate.
- Verifikation lt. Konzept-Leitprinzip: echte S1-Aufzeichnungen über S2 (`/api/trips/{id}/alert-preview`, changes-Payload) einspeisen, sonst Fixtures.
