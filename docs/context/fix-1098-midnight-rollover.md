# Context: fix-1098-midnight-rollover

## Request Summary
`convert_trip_to_segments` verliert die Tages-Rollover-Info: `_interpolate_missing_times`
löst über Mitternacht laufende Zeiten intern zwar monoton auf (#1091), gibt aber nackte
`time`-Objekte zurück. Beim Neukombinieren mit einem einzigen `target_date` (Zeilen 166–175)
erhält eine echt über Mitternacht laufende Etappe (z. B. `arrival_override` 22:00 → None → 00:30)
eine falsche Ziel-Ankunftszeit und das Über-Nacht-Segment läuft still in den
`end_dt <= start_dt`-Klemm-Guard (Zeile 177) statt korrekt mit `target_date + 1 Tag` gebildet zu werden.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_segments.py` | **Fix-Ort.** `_interpolate_missing_times` (Z.57–103, gibt nackte `time` via `.time()` Z.102), `convert_trip_to_segments` (Z.106–250). Kombination mit einzelnem `target_date` Z.166–175, Klemm-Guard Z.177–188 |
| `tests/tdd/test_issue_1004_startzeit_ssot.py` | Bestehende Tests: AC-5 Mitternachts-Klemme (Z.203–241), #1091 Interpolations-Monotonie (Z.424–464). Hier kommt der neue RED-Test dazu |
| `src/core/naismith.py` | Quelle der 23:59-Klemme (`_format_hhmm` clamped) — Ursache des AC-5-Falls, den der Guard weiterhin abfangen MUSS |

## Existing Patterns
- **#1091-Muster:** `_interpolate_missing_times` rechnet bereits intern mit vollen `datetime`
  über die Tagesgrenze (Z.83–89: `nxt += timedelta(days=1)` wenn `nxt < base`) — kollabiert
  das Ergebnis aber via `.time()` (Z.102) wieder auf nackte Uhrzeit. Der Fix muss diese
  Tages-Info bis zur Kombination durchreichen.
- **Klemm-Guard als Doppelnutzung (Z.177):** `end_dt <= start_dt` fängt zwei Fälle ab:
  (1) AC-5 Naismith-23:59-Klemme → Zeiten kollabieren auf **gleiche** Uhrzeit (`==`),
  (2) echt über Mitternacht → wp2 ist **strikt kleiner** als wp1 (Wrap). Der Fix muss (1)
  weiter verwerfen und nur (2) mit Folgetag retten.
- **Ziel-Segment (Z.221–248):** nutzt `segments[-1].end_time` (bereits volle UTC-`datetime`) —
  erbt den korrekten Tag automatisch, sobald das letzte reguläre Segment richtig gebildet ist.
  Kein separater Fix nötig.

## Dependencies
- **Upstream:** `_known_time_for_index`, `_interpolate_missing_times`, `tz_for_coords`,
  `datetime.combine`. `stage.start_time`, `arrival_override`, `arrival_calculated`.
- **Downstream (Aufrufer von `convert_trip_to_segments`):** `trip_forecast.py`,
  `trip_report_scheduler.py`, `preview_service.py`, `trip_command_processor.py`,
  `trip_alert.py`. **Alle** erhalten `List[TripSegment]` — Signatur bleibt unverändert,
  Aufrufer sind nicht betroffen (nur interne Datumszuordnung ändert sich).

## Existing Specs
- `docs/specs/modules/issue_1004_startzeit_ssot.md` — SSoT-Startzeit-Kette + AC-5-Klemme (Vorlage/Invariante)
- `docs/specs/modules/issue_1090_trip_forecast_endtime.md` — invertierte Wetterfenster-Guard (#1090), verwandter Schutz
- `docs/specs/modules/issue_822_radar_nowcast_segment.md` — SSoT-Extraktion, geteilte Segment-Konvertierung

## Risks & Considerations
- **Regressions-Risiko AC-5:** Der neue Tag-Offset darf gleiche (`==`) Zeiten NICHT rollen
  (sonst wird die geklemmte Etappe fälschlich gerettet). Nur strikt fallende Uhrzeit = Folgetag.
  Der bestehende AC-5-Test (Z.203) ist die Regressions-Wache.
- **None-Fallback:** Bei `wp_start is None` greift `cumulative_time`-Fallback (Z.156/163).
  Der Tag-Offset muss sich auf die tatsächlich verwendete Zeit stützen, nicht auf das rohe
  `wp_times`-Element.
- **Mehrfach-Rollover:** Theoretisch mehrere Mitternachtsübergänge in einer Etappe (sehr lang) —
  monotoner Tag-Zähler statt Boolean, um robust zu bleiben.
- **Mischfall 22:00 → 23:59(Klemme) → 00:30(echt):** Grenzfall, in dem Klemm-Artefakt und
  echter Übergang zusammentreffen — in der Analyse-Phase entscheiden, ob 00:30 als Folgetag
  gerettet oder das geklemmte Zwischensegment weiter verworfen wird. Priorität MEDIUM, Sonderfall.
- **#1091 kein Regress:** Vor #1091 kollabierte derselbe Input auf 0 Segmente; #1091 rettet 1
  echtes Segment. Dieser Fix vervollständigt die korrekte Ziel-Ankunftszeit.

## Analysis

### Type
Bug (Adversary-Folge #1091, Root-Cause vollständig belegt: `trip_segments.py:166-175` kombiniert
alle `wp_times` mit einzelnem `target_date`; Tag-Rollover aus `_interpolate_missing_times` geht
via `.time()` Z.102 verloren).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_segments.py` | MODIFY | In `convert_trip_to_segments`: Tag-Offset-Walk über `wp_times`, dann `datetime.combine(target_date + timedelta(days=wp_days[i]), …)` für start_dt/end_dt |
| `tests/tdd/test_issue_1004_startzeit_ssot.py` | MODIFY | Neuer #1098-Test: echt über Mitternacht → Ziel-Ankunft 00:30 (nicht 01:15), Segment überlebt. AC-5- und #1091-Tests bleiben grün (Regressions-Wächter) |

### Scope Assessment
- Files: 1 Quell-Datei + 1 Testdatei
- Estimated LoC: +~20/-~4 (Tag-Offset-Liste + zwei `combine`-Aufrufe angepasst)
- Risk Level: MEDIUM (berührt geteilten Briefing-/Alert-SSoT; Regression nur über AC-5-Guard denkbar → durch bestehenden Test abgesichert)

### Technical Approach
Nach `wp_times = _interpolate_missing_times(known_times)` einen parallelen `wp_days`-Vektor bilden:
```
day = 0; prev = None
for t in wp_times:
    if t is not None and prev is not None and t < prev:   # STRIKT fallend = Tagesgrenze
        day += 1
    wp_days.append(day)
    if t is not None: prev = t
```
Dann in der Segment-Schleife:
`datetime.combine(target_date + timedelta(days=wp_days[i]),   wp1_start)` (start_dt)
`datetime.combine(target_date + timedelta(days=wp_days[i+1]), wp2_start)` (end_dt)

Der `end_dt <= start_dt`-Guard (Z.177) bleibt **unverändert** — er fängt weiterhin nur gleiche
(`==`) Zeiten ab (AC-5-Klemme), nicht mehr den echten Übergang. Ziel-Segment erbt korrekten Tag
über `segments[-1].end_time` — keine Änderung nötig.

### Dependencies
- Rückgabetyp `List[TripSegment]` **unverändert** → alle 5 Aufrufer (`trip_forecast`,
  `trip_report_scheduler`, `preview_service`, `trip_command_processor`, `trip_alert`) unberührt.

### Open Questions
- [x] Trennung AC-5-Klemme vs. echter Übergang? → **strikt `<` rollt, `==` nicht** (durchgetraced, siehe Tabelle in Zusammenfassung).
- [x] Ziel-Ankunftszeit korrekt? → erbt über `segments[-1].end_time`, kein Extra-Fix.
- [ ] **Grenzfall-Entscheid für Spec:** Mischfall `22:00 → 23:59(Klemme) → 00:30(echt)` — der
  Tag-Walk rettet das `23:59→00:30`-Segment (31 Min) statt es zu verwerfen. Bewertung: akzeptabel
  und konsistent, aber KEIN Ziel-AC (Sonderfall außerhalb #1098-Scope). In Spec als Known Behavior
  dokumentieren, nicht als AC prüfen.

