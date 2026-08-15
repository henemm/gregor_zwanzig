# Context: fix-1851-alarm-zeitfenster-fixtures

Issue: [#1851](https://github.com/henemm/gregor_zwanzig/issues/1851) · `priority:high`, `session:taskforce`, `type:bug`
Klassenfix der Fehlerart: #1709 · Gefunden bei: #1557

## Request Summary

Drei Tests in `tests/unit/test_alarm_zeitfenster_ziel.py` schlagen fehl
(`assert []` — keine Alarm-Mail zugestellt). Sie blockieren den CI-`test`-Job
und damit jede Auslieferung. **Der Mechanismus ist NICHT ermittelt.**

## Gemessen (Fakten)

| # | Messung | Ergebnis |
|---|---|---|
| 1 | CI `test`-Job auf `main`, Commit `57e36375`, 2026-08-14 20:22 UTC | **grün** |
| 2 | CI `test`-Job auf PR #1853 (Basis `57e36375`), 2026-08-15 05:29 UTC | **rot**, exakt diese 3 Tests, keine weiteren |
| 3 | Lokal, Vergleichs-Worktree auf **unverändertem** `origin/main`, 04:33 UTC | **3 failed, 9 passed** |
| 4 | Lokal im Arbeitszweig (mit #1557-Fixture), 04:33 UTC | identisch `3 failed, 9 passed` |

Aus 3+4 folgt: **unabhängig von #1557.** Aus 1+2 folgt: **derselbe Code, zwei
Zeitpunkte, zwei Ergebnisse.**

Betroffen:
- `test_ac1_gewitter_17_uhr_am_tagesziel_wird_zugestellt`
- `test_ac2a_gewitter_1845_knapp_vor_fensterende_wird_zugestellt`
- `test_ac3_spaetankunft_2030_faellt_nicht_aus_der_ueberwachung`

Nicht betroffen (grün): `test_ac2b_…1915_knapp_nach_fensterende_bleibt_aus`
(erwartet **keine** Mail) und die neun übrigen Fälle der Datei.

> Bemerkenswert: die drei Roten erwarten alle **eine Mail**, der grüne
> Grenzfall erwartet **keine**. Ein Zustand, in dem generell keine Alarme
> entstehen, würde exakt dieses Muster erzeugen — ist aber nicht belegt.

## Was NICHT die Ursache ist (bereits ausgeschlossen)

- **Nicht die #1557-Änderung** (Messung 3 vs. 4).
- **Nicht der Tagesfenster-Randfall.** Bei AC-1 erscheint **keine**
  `Ziel-Segment … liegt nach dem Tagesfenster-Ende`-Warnung. Der
  Produktivcode `src/services/trip_segments.py:250-295` verhält sich
  #1584-konform: das Zielsegment endet am Tagesfenster (19:00 Ortszeit),
  nicht bei Ankunft+2h. Die „Ankunft + 2 h"-Formulierung steht nur im
  **Assertion-Text des Tests** und beschreibt den alten Bug von #1584 —
  nicht das beobachtete Verhalten.
- **Rechnerisch müsste AC-1 grün sein:** Ankunft 13:18 Ortszeit (Europe/Vienna,
  UTC+2) = 11:18 UTC, Fensterende 19:00 Ortszeit = 17:00 UTC, Gewitter 17:00
  Ortszeit = 15:00 UTC — liegt im Segment.

## Offene Frage (Kern der Analyse)

**Warum entsteht kein Alarm, obwohl das Segment das Gewitter abdeckt?**

Prüfrichtungen, keine davon bestätigt:

1. **Erster Verdacht — #1594.** Der Basis-Commit `57e36375` ist der Merge von
   `fix-1594-alarm-vorlauf-sperre`, also einer Änderung an der
   **Alarm-Zeitsteuerung**. Wenn dort ein Vorlauf-Fenster eingeführt wurde
   („nicht mehr als N Stunden im Voraus alarmieren"), erklärt das ein
   Ergebnis, das von der Differenz zwischen Wanduhr und Gewitterzeitpunkt
   abhängt. Zu prüfen: Was genau tut die Sperre, und greift sie hier?
2. **Filterung im Alarmpfad.** `src/services/trip_alert.py` filtert Segmente
   nach Zeitbezug (laut Projektwissen um `:1147-1150` herum „bereits
   absolviert"). Der Helfer `_alarm_mails` (`:168-208`) umgeht laut eigenem
   Docstring nur die `datetime.now()`-Filter der **Frisch-Beschaffung**, nicht
   die des Alarm-Laufs selbst.
3. **Geteilter Wetter-Cache.** `_alarm_mails` baut
   `SegmentWeatherService(provider)` **ohne** expliziten Cache
   (`:193`) — es greift der Prozess-Singleton. Die Datei hat zwar eine eigene
   Reset-Fixture (`:60-64`), aber der Zusammenhang ist zu prüfen, nicht
   anzunehmen.

## Related Files

| Datei | Relevanz |
|---|---|
| `tests/unit/test_alarm_zeitfenster_ziel.py:168-208` | Helfer `_alarm_mails` — baut Etappe auf `date.today()`, Ankunft als Ortszeit-String |
| `tests/unit/test_alarm_zeitfenster_ziel.py:113-145` | `_trip()` — Wegpunkte MIT `arrival_calculated`, Default-Tagesfenster 4/19 |
| `tests/unit/test_alarm_zeitfenster_ziel.py:220-394` | **gehärtete** Fixture-Familie (Reykjavik UTC+0 / Auckland) aus #1667 S1 — die drei roten Fälle nutzen sie NICHT |
| `src/services/trip_segments.py:250-295` | Zielsegment-Ende am Tagesfenster (#1584) inkl. Mindestfenster-Randfall |
| `src/services/trip_alert.py` | Alarmlauf, Zeitfilter, `check_and_send_alerts` |
| `src/app/day_window.py` | `DAY_WINDOW_END_HOUR = 19` |
| #1594 / Commit `57e36375` | Alarm-Vorlaufsperre — erster Verdacht |

## Risks & Considerations

1. **Test- oder Produktdefekt ist offen — und das ist der Kern.** Wird hier
   die Fixture „wanduhrunabhängig" gemacht, ohne den Mechanismus zu kennen,
   und die Ursache liegt in Wahrheit im Alarmpfad, dann wird ein **echter,
   nutzersichtbarer Ausfall zugekleistert**: Alarme am Tagesziel, die zu
   bestimmten Zeiten nicht rausgehen. Genau das war der Fehler von #1584, und
   genau dieser Fall zählt auf dem Karnischen Höhenweg.
2. **Vorgeschichte mahnt zur Vorsicht.** Zu dieser Rot-Familie wurden bereits
   **drei** Erklärungen als belegt behandelt, **zwei davon widerlegt**
   („Ruhezeit unterdrückt nachts Alarme" stand 5 h falsch in #1196; dann ein
   frei vermessenes Zeitfenster; erst die dritte Messung traf). Eine
   wiederholte Beobachtung ist keine Ursache.
3. **Nicht die Grenze vermessen.** Der dokumentierte Fehlgriff ist, das
   Rot-Fenster immer feiner einzugrenzen, statt zu fragen *warum dort*.
4. **Rerun ist nicht die Lösung.** Ein günstiger Zeitpunkt macht die Ampel
   grün, ohne etwas zu beheben — im Projekt bereits einen Abend teuer gewesen.

---

# Analysis (Phase 2)

## Ursache — gemessen, nicht hergeleitet

```
uv run pytest "tests/unit/test_alarm_zeitfenster_ziel.py::test_ac1_…" \
  --allow-hosts=127.0.0.1,::1 -p no:randomly --log-cli-level=DEBUG
→ DEBUG trip_alert:trip_alert.py:242 Alert suppressed: briefing imminent for trip t-221d3bd1
```

Die Alarme werden von der **Vorlaufsperre aus #1594** unterdrückt.

Kette:
1. `src/services/trip_alert.py:241` fragt `_is_briefing_imminent(trip, now_utc)`
   **vor** jedem Abruf — der gemeinsame Adapter beider Trip-Alarmarten (`:715-741`).
2. Der Adapter ruft `check_briefing_imminent` (`src/services/alert_gate.py:200`)
   mit dem Fälligkeits-Prädikat `trip_briefing_due_at`
   (`src/services/trip_report_scheduler.py:135`).
3. Die Sperre ist wahr, wenn innerhalb von `BRIEFING_VORLAUF_MINUTEN` (60) ein
   geplantes Briefing fällig **und** noch nicht versucht ist. Dann wird die
   Meldung **ersetzt**, nicht verschluckt (ADR-0009): sie kommt Minuten später
   vollständig im Briefing an.
4. Die Test-Trips aus `_trip()` (`tests/unit/test_alarm_zeitfenster_ziel.py:113`)
   tragen ein aktives `TripReportConfig` mit Vorgabe-Briefingzeiten. Je nach
   echter Uhrzeit ist damit ein Briefing fällig — der Alarm wird
   **planmäßig** unterdrückt und die Zusicherung „Mail kommt an" scheitert.

## Test- oder Produktdefekt? → **Test**

Der Produktivcode verhält sich **korrekt und beabsichtigt**. Die Sperre ist die
zugesicherte Wirkung von #1594; sie unterdrückt nicht, sondern ersetzt.

Die drei Tests stammen aus **#1584** und wurden geschrieben, **bevor** die
Sperre existierte. Sie sichern zu „Gewitter am Tagesziel ⇒ Alarm wird
zugestellt", ohne die Vorbedingung „und es steht kein Briefing an"
herzustellen. Damit behaupten sie ein Verhalten, das das Produkt in diesem
Zustand bewusst nicht zeigt.

**Meine Diagnose in #1851 war falsch** („Fixture nimmt an, im Wandertag zu
laufen"; Fixture-Ort nach Reykjavik verlegen). Sie war plausibel, passte zur
Beobachtung „zeitabhängig" — und ist widerlegt: bei AC-1 erscheint keine
Tagesfenster-Warnung, und die Rechnung liegt sauber im Segment. Wäre sie
umgesetzt worden, hätte sie nichts behoben. Issue #1851 ist korrigiert.

## Nebenbefund mit Gewicht: die Lücke ist beim Einbau der Sperre entstanden

#1594 hat drei bestehende, fremde Tests von grün auf zeitabhängig-rot gekippt,
**ohne dass es auffiel** — die eigene CI-Ampel lief abends, außerhalb der
Briefing-Vorlauffenster. Der Effekt zeigt sich erst zu Tageszeiten, zu denen
niemand liefert. Das ist keine Nachlässigkeit einer Person, sondern eine
strukturelle Lücke: eine Verhaltensänderung im Alarmpfad kann bestehende
Alarm-Tests kippen, und die Ampel misst das nur zu ihrer Laufzeit.

## Lösungsrichtung

Die drei Testfälle müssen die Vorbedingung **explizit herstellen**, statt sie
vom Zufall der Uhrzeit abhängig zu machen: der Test-Trip darf kein fälliges
Briefing haben. Kandidaten (in der Spec zu entscheiden):

- `report_config.enabled = False` — laut `trip_briefing_due_at`-Docstring ein
  zwingender Aktiv-Filter; das Prädikat wird damit immer falsch.
- `paused_at` / `paused_until` setzen — dieselbe Wirkung über einen anderen Filter.

Wichtig ist die **Absicht im Test sichtbar zu machen**: „dieser Trip hat kein
geplantes Briefing, deshalb ist der Alarm die einzige Zustellform". Ein bloßes
Verschieben der Uhrzeit wäre wieder nur eine Wanduhr-Wette.

Der grüne Grenzfall `test_ac2b_…1915_knapp_nach_fensterende_bleibt_aus` erwartet
**keine** Mail und ist deshalb heute aus dem falschen Grund grün — er würde
auch bei generell unterdrückten Alarmen bestehen. Er gehört mitgehärtet, sonst
bleibt eine Zusicherung ohne Aussagekraft.

## Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `tests/unit/test_alarm_zeitfenster_ziel.py` | MODIFY | Test-Trips ohne fälliges Briefing; Absicht dokumentieren |
| Produktivcode | — | **unverändert** |

## Scope Assessment

- Dateien: 1 · LoC: Produktiv +0, Test ca. +10/−2 · Risiko: **LOW**

## Open Questions

- Keine offenen fachlichen Fragen. Ursache gemessen, Zuordnung eindeutig.
