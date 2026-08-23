# Kontext — fix-2096-paritaets-regex-tagesbezug

**Issue:** [#2096](https://github.com/henemm/gregor_zwanzig/issues/2096) — CI-Ampel wird abends rot
**Typ:** Bug (Testfehler, kein Produktivdefekt)
**Branch:** `fix-2096-paritaets-regex-tagesbezug` (von `origin/main` @ `f56e01fd`)

## Symptom

Ab ~21:05 UTC scheitert der CI-Check `test` auf **jedem** PR im Repo, unabhängig vom Inhalt.
Belegt an PR #2095 (ändert ausschließlich zwei Markdown-Dateien).

## Gemessener Blast Radius

Nachgemessen am 2026-08-22 zwischen 23:05 und 23:15 UTC auf `origin/main`, Testlauf mit den
echten CI-Flags (`--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost`).
**Sieben** Tests rot — das Ticket nannte nur vier davon.

| # | Datei | Tests | Mechanismus |
|---|---|---|---|
| 1 | `tests/tdd/test_onset_reichweite_guete_kanalparitaet.py` | 2 | A |
| 2 | `tests/tdd/test_onset_ende_kanalparitaet.py` | 2 | A |
| 3 | `tests/tdd/test_alert_preview_nowcast_replay.py` | 1 | A |
| 4 | `tests/tdd/test_onset_ende_textstellen.py` | 1 | A |
| 5 | `tests/tdd/test_952_onset_alert_fidelity.py` | 2 | B |

**Acht** rote Tests in **fünf** Dateien. Das Ticket nannte vier davon.

### Mechanismus A — Uhrzeit-Regex trifft den Tagesbezug nicht

Die Tests ankern per Regex unmittelbar auf `\d{1,2}:\d{2}`:

| Ort | Regex |
|---|---|
| `test_onset_reichweite_guete_kanalparitaet.py:80` | `r"Radar reicht bis (\d{1,2}:\d{2})"` |
| `test_onset_reichweite_guete_kanalparitaet.py:81` | `r"Ortsangabe ab (\d{1,2}:\d{2}) unscharf"` |
| `test_onset_reichweite_guete_kanalparitaet.py:83` | `r"@(?P<beginn>\d{1,2}:\d{2})\?"` |
| `test_onset_ende_kanalparitaet.py:60` | `r"letzter Regen gegen (\d{1,2}:\d{2})"` |
| `test_alert_preview_nowcast_replay.py:335` | `r"Radar reicht bis (\d{2}:\d{2})"` |
| `test_onset_ende_textstellen.py:61` (`_LANGFORM_RE`, wirksam ab `:382`) | `letzter Regen gegen (\d{1,2}:\d{2})` |

Fällt die Zeitangabe auf den Folgetag, stellt der Renderer korrekt einen Qualifier voran und der
Anker trifft nicht mehr:

| Fläche | Erzeuger | Ist-Text |
|---|---|---|
| Langform | `src/output/renderers/alert/render.py:214-240` (`_time_with_day`) | `Radar reicht bis morgen 00:12` |
| Kurzform | `src/output/renderers/alert/render.py:1387` (Wochentagskürzel) | `Seg 1: R3.0@23:25@So1:35?` |

Gemessene Ist-Texte:

```
Wo & wann: km 2–6 · ab 23:28 · letzter Regen gegen morgen 01:38
           · Radar reicht bis morgen 02:03 · Ortsangabe ab morgen 00:08 unscharf
Trip          = 'Seg 1: R3.0@23:25@So1:35?'
Ortsvergleich = 'Reykjavik-Paritaet-S3: R3.0@23:25@So1:35?'
```

**Kipp-Zeitpunkt je Anker** (Fixture-Offsets ab `jetzt`, Trip-Zone UTC+0):

| Anker | Offset | kippt ab |
|---|---|---|
| Quellen-Reichweite | +175 Min | 21:05 UTC |
| Ereignis-Ende (Reichweiten-Datei) | +150 Min | 21:30 UTC |
| Ereignis-Ende (Ende-Datei) | +80 Min | 22:40 UTC |
| Onset | +20 Min | 23:40 UTC |

### Mechanismus B — Ortszeit-Fenster mit Systemdatum gestempelt

`tests/tdd/test_952_onset_alert_fidelity.py:125-148` (`_active_window`) rechnet das Etappenfenster
in **Ortszeit** (`tz_for_coords(42.20, 9.10)` → `Europe/Paris`, UTC+2), aber
`:172` (`_trip_with_active_segment`) stempelt es mit `date_type.today()` — dem **Systemdatum** (UTC).

Ab 22:00 UTC weichen lokales Datum und Systemdatum um einen Tag ab. Das Segment landet damit rund
24 Stunden in der Vergangenheit, die Aktivitätsprüfung `seg.start_time <= now_utc <= seg.end_time`
schlägt fehl und `check_radar_alerts()` liefert `0` statt `1`.

## Kein Produktivdefekt

Der Tagesbezug **entfernt** nichts, er macht die Angabe eindeutig (`morgen 00:12` statt eines
mehrdeutigen `00:12`) — genau das, wofür die Spec das Feld `source_reach_day_offset` vorsieht
(`docs/specs/modules/feat_2051_s3_reichweite_und_guete.md:291-294`). Der einzige Pfad, auf dem die
Reichweite tatsächlich entfällt, ist E5 (`event_ongoing_beyond_horizon`,
`src/output/renderers/alert/project.py:91-92`) — bewusst, dokumentiert, tageszeitunabhängig.

Mechanismus B trifft nur die Fixture: echte Trips tragen echte `stage.date`-Werte, die nicht aus
dem Systemdatum abgeleitet werden.

**Gegengeprüft durch `analysis-challenger`** (Auftrag: Behauptung aktiv widerlegen) — Urteil
BESTÄTIGT für alle drei Mechanismen. Der entscheidende Nachweis für den Produktivpfad:
`src/services/trip_alert.py:1246-1249` löst „heute" **nicht** über `date.today()` auf, sondern über
`trip_local_today(trip, now_utc)` (`src/services/trip_day.py:90-96`, Ortszeit der Tour, ADR-0044),
und `resolve_current_segment` (`src/services/trip_segments.py:449-499`) fällt am Tagesrand
zusätzlich auf „gestern" zurück (#1667 S3). Echte Trips tragen ein fest zugewiesenes
Kalenderdatum — die Inkonsistenz der Fixture kann dort strukturell nicht entstehen.

Zwei Punkte des Berichts waren falsch und sind nachgemessen korrigiert: `test_starkregen_kurzfristhinweis.py`
ist nicht rot (Mechanismus C), `test_onset_ende_textstellen.py` ist rot (er hatte den falschen Test
in der Datei geprüft).

## Wächterlücke

`grep -rn "source_reach_day_offset" tests/` liefert **null** Treffer. Ausgerechnet der Zweig, der
die Ampel rot färbt, ist von keinem Test bewacht. Eine bloße Regex-Aufweichung (`(?:morgen )?`)
ließe ihn weiterhin ungeprüft — das Muster „Test prüft die Form statt des Werts", das in dieser
Scheibe bereits viermal zugeschlagen hat.

## Mechanismus C — Test überspringt sich still statt rot zu werden

`tests/tdd/test_starkregen_kurzfristhinweis.py:125` trägt denselben verwundbaren Anker
(`:485,501`, Offset `datetime.now(timezone.utc) + timedelta(minutes=120)`), hat aber einen eigenen
Wächter, der bei Nähe zur Mitternachtsgrenze `pytest.skip` auslöst:

```
SKIPPED [1] tests/tdd/test_starkregen_kurzfristhinweis.py:125:
  Testzeitpunkt zu nah an einer Mitternachtsgrenze (UTC) fuer Offset-Segment
```

Keine rote Ampel — aber auch **keine Prüfung**. Der Zweig, der abends interessant wäre, ist genau
der, den der Test dann nicht mehr durchläuft. Blindheit statt Rot; gehört in denselben Zuschnitt.

## Latente Zwillinge (noch grün)

Ankern onset-nah (+20 Min), kippen erst in den letzten 20 Minuten vor Mitternacht:

- `tests/tdd/test_onset_kurzform_menge.py:51,239`
- `tests/tdd/test_onset_reichweite_guete_sms.py:262`

Bereits abgesichert (stellt die Uhr per `@freeze_time`, Offsets überqueren nie Mitternacht) und
damit das Vorbild für die richtige Bauart:

- `tests/tdd/test_onset_ende_untergrenze_abgrenzung.py:201ff`
- `tests/tdd/test_ortsschaerfe_grenze_laufzeitbindung.py:49,81,151`

## Ausgeschlossen: produktive Verbraucher des Tagesbezugs

`grep` über `src/`, `api/`, `internal/` nach Uhrzeit-Regexen liefert genau **einen** Treffer:
`internal/handler/compare_preset.go:39` — `^\d{2}:\d{2}(:\d{2})?$`, validiert ein Eingabefeld für
Vergleichs-Presets, nicht den Alarmtext. Kein Produktivpfad zerlegt gerenderten Alarmtext per
Uhrzeit-Regex; der vorangestellte Tagesbezug kann dort also nichts brechen.

## Vorhandene Bausteine

| Baustein | Ort | Was |
|---|---|---|
| `frozen_active_window(hour_utc=12)` | `tests/helpers/nowcast_gate_fixtures.py:438-473` | Contextmanager, stellt die Uhr per `freezegun` |
| — | — | **Kein** Helfer, der `(Tageswort, "HH:MM")` aus einem Text zieht |

## Technischer Ansatz

Die Klammer über allen drei Mechanismen: **der Test hängt an der Wanduhr**. Vier Bausteine, die
nur zusammen wirken — einzeln tauscht man eine Lücke gegen eine andere.

1. **Geteilter Test-Helfer statt nackter HH:MM-Regexe.** Neu in `tests/helpers/`: eine Funktion,
   die aus dem Text ein **Paar** `(Tagesbezug, "HH:MM")` zieht (Langform: `morgen`/`heute`/`gestern`/
   `in N Tagen`; Kurzform: Wochentagskürzel `Mo`…`So`), und ein Gegenstück, das das erwartete Paar
   aus der Ziel-UTC-Zeit **herleitet** (Datumsvergleich gegen `jetzt` in der Trip-Zone).
   Damit ist der Tagesbezug erstmals bewacht — das schließt die `source_reach_day_offset`-Lücke.
2. **Uhr stellen statt Wanduhr.** `frozen_active_window()`
   (`tests/helpers/nowcast_gate_fixtures.py:438-473`) in den betroffenen Dateien einsetzen.
3. **Eigener Spätuhr-Testfall je Mechanismus.** Punkt 2 friert den Tagesübergangs-Zweig sonst weg,
   und Punkt 1 bewachte nichts. Jeder Anker braucht einen Fall mit später Uhr, der den Überlauf
   tatsächlich durchläuft.
4. **Fixture-Datum aus der Ortszeit ableiten** (`test_952_onset_alert_fidelity.py:172`), nicht aus
   `date_type.today()`.

**Warum keine Regex-Aufweichung** (`(?:morgen )?`): sie macht die Ampel grün und lässt den
Tagesbezug ungeprüft — genau das Muster „Test prüft die Form statt des Werts", das in dieser
Scheibe schon viermal zugeschlagen hat (`reference_test_prueft_die_form_statt_des_werts`).

**Mechanismus C** (stiller Skip) verschwindet mit Punkt 2 von selbst: bei gestellter Uhr gibt es
keinen „zu nah an Mitternacht"-Zufall mehr, den der Wächter abfangen müsste.

## Scope

| | |
|---|---|
| Dateien | 5 Testdateien (MODIFY) + 1 Helfer (CREATE) + 1–2 latente Zwillinge (MODIFY, falls günstig) |
| Produktivcode | **keiner** |
| Geschätzte LoC | ~+220 / -70 — nah am 250er-Limit, `loc_limit_override 500` vermutlich nötig |
| Risiko | MEDIUM — viele Testdateien, aber kein Produktionsrisiko |

## Offene Punkte

- [x] Urteil des `analysis-challenger` zu Behauptung C — BESTÄTIGT
- [x] Zuschnitt — die 8 roten plus Mechanismus C; latente Zwillinge nur, wenn der Helfer sie
      ohnehin abdeckt
- [ ] Nebenbefund für #1199: Ein Test, der sich bei ungünstiger Uhrzeit still selbst überspringt
      (`test_starkregen_kurzfristhinweis.py:125`), ist als Bauart ein Wächter-Loch — lohnt eine
      generelle Prüfung, ob es weitere solcher Selbst-Skips gibt.
