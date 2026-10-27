# Context: fix-2052-now-aufenthaltsort

Issue: [#2052](https://github.com/henemm/gregor_zwanzig/issues/2052) · Milestone „Tour KHW 2026-08" · `priority:high`, `type:bug`, `area:alerts`
Track: Standard (Intake-Summe 3) · Workflow `fix-2052-now-aufenthaltsort`

## Request Summary

Der Telegram-/Mail-Befehl `/now` (Alias `/jetzt`) holt den Radar-Nowcast am **ersten Wegpunkt der heutigen Etappe** statt am **Aufenthaltsort des Nutzers zum Abfragezeitpunkt**. Fragt der Wanderer um 16:00 mitten auf der Etappe „regnet es gleich?", antwortet der Bot für den Ausgangspunkt vom Morgen. Fachlich dieselbe Ursache wie #2017 (dort für den Alarm-Pfad behoben), anderer Codepfad.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py:1499-1543` | `_show_now` — der Prüfling. `wp = stage.waypoints[0]` (:1525), `svc.get_nowcast(wp.lat, wp.lon, elevation_m=wp.elevation_m, priority="user_briefing")` (:1529-1531), `tz_for_coords(wp.lat, wp.lon)` (:1536). Importiert `position_at_time` an keiner Stelle. |
| `src/services/trip_segments.py:469` | `position_at_time(trip, active: TripSegment, segment_date: date, at: datetime) -> GPXPoint` — der zu nutzende geteilte Baustein (#2017). Fail-soft: liefert **immer** einen `GPXPoint`. Höhe wird **roh** interpoliert. |
| `src/services/trip_segments.py:363-413` | `resolve_current_segment(trip, now_utc, today) -> Optional[Tuple[TripSegment, date]]` — die fehlende Brücke von Etappe zu Segment. Signatur passt **exakt** auf das, was `_show_now` bereits hat. |
| `src/services/trip_segments.py:108-342` | `convert_trip_to_segments(trip, target_date)` — zerlegt die Wegpunkte einer Stage in Segmente + ein ortsfestes „Ziel"-Segment, das am Tagesfenster-Ende schließt (#1584/#1599). |
| `src/services/trip_alert.py:1173, 1291-1333` | Referenz-Aufrufstelle A (Alarm). Muster: `resolve_current_segment(...)` → `_at = now_utc + RADAR_ONSET_THRESHOLD_MIN // 2` → `position_at_time(...)` in eigenem `try` → `int(round(_pos.elevation_m))` → `tz_for_coords(lat, lon)` am **neuen** Punkt. |
| `src/services/trip_report_scheduler.py:1750-1859` | Referenz-Aufrufstelle B (Starkregen-Hinweis im Briefing). Segmentwahl **lokal** statt über `resolve_current_segment()`, bewusst ohne Vortags-Rückgriff. `_at = now_utc + NOWCAST_HORIZON_MIN // 2`. |
| `tests/test_success_status_guard.py:1855` | 🔴 Struktureller AST-Wächter (#1405) mit **fester Zahl**: `"src/services/trip_command_processor.py::_show_now": 1`. Ein zusätzlicher Aufruf mit unzugewiesenem Rückgabewert in `_show_now` macht ihn rot. Muss bei der Implementierung mitlaufen. |
| `tests/helpers/nowcast_gate_fixtures.py:89-437` | `make_trip()`/`trip_stage()` — der zentrale Helfer für Zwei-Wegpunkt-Etappen mit steuerbaren Ankunftszeiten. Basis für den neuen Test. |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:213-265, 1111-1233` | 🟢 **Die Testvorlage.** `_erwartete_messposition()` rechnet den Sollpunkt unabhängig vom Prüfling nach, `_Aufzeichnend(RadarNowcastService)` fängt die Parameter ab, `test_2017_ac8_...` prüft zusätzlich **Nicht-Trivialität** (Abstand zum Startpunkt > 0.01°). |
| `tests/tdd/test_radar_alert_follows_ortstag.py:174-258` | Zweistufiger Koordinatennachweis: (1) Punkt liegt auf der Strecke der erwarteten Etappe, (2) an der zum Zeitanteil erwarteten Stelle. |
| `docs/specs/modules/fix_2017_nowcast_messpunkt.md:343-345` | Nennt `/jetzt` **wörtlich** als bewusst ausgeklammerten Nebenbefund: „Andere Fehlerklasse (kein Onset-Zirkel, sondern falscher Bezugspunkt für eine Sofortabfrage) — eigener Befund". Genau dieses Ticket. |
| `docs/specs/modules/radar_nowcast.md:106-113` | Known Limitations mit der Verfeinerungskette `waypoints[0]` (#656) → `active.start_point` (#822) → interpolierte Position (#2017). Muss um `/now` fortgeschrieben werden. |

## Existing Patterns

- **Positionsbestimmung ist geteilt, nicht kopiert.** `position_at_time()` ist seit #2017 der einzige Ort, an dem interpoliert wird. Die Aufrufstellen liefern nur `(active, segment_date, at)` und normalisieren danach.
- **Höhen-Normalisierung wohnt an der Aufrufstelle**, nicht im Baustein: `int(round(_pos.elevation_m)) if ... is not None else None`. Grund (#1991): `get_nowcast` führt `elevation_m` **roh** im Cache-Schlüssel — `1000` und `1000.0` erzeugten zwei Einträge für denselben Punkt.
- **Zeitzone folgt dem Messpunkt**, nicht dem Etappenstart: `tz_for_coords(lat, lon)` auf die interpolierten Koordinaten (A macht es so).
- **Fehler an der Positionsbestimmung bekommen einen eigenen `try`**, nicht den des Abrufs — damit die Meldung unterscheidbar bleibt (Adversary-Finding F-ADV1 in #2017).
- **Testmuster:** echte `RadarNowcastService`-Subklasse als Aufzeichner statt `Mock()`; Sollwert unabhängig vom Prüfling nachgerechnet; explizite Nicht-Trivialitäts-Assertion.

## Dependencies

- **Upstream** (was `_show_now` nutzen wird): `trip_local_today()`, `resolve_current_segment()`, `position_at_time()`, `tz_for_coords()`, `RadarNowcastService.get_nowcast/format_now_text`.
- **Downstream** (was `_show_now` nutzt): der Telegram-Befehlspfad inkl. Callback `🔄 Aktualisieren` (`callback_data: "now"`), der Mail-Inbound-Pfad (`### now`), `_CALLBACK_QUERY_MAP`, `BOT_COMMANDS`.

## Befunde aus der Recherche

### 1. 🔴 Der Messpunkt von `/now` ist heute durch **keinen einzigen** Test geschützt

Das Ticket listet vier Testdateien, die „mitziehen müssen". Die Prüfung aller 15 einschlägigen Testfunktionen ergibt: **keine davon bricht**, weil überall entweder nur ein Wegpunkt pro Etappe existiert, gar keine Koordinaten geprüft werden, oder nur Routing/Text zugesichert wird.

| Datei | Einschlägige Tests | Bricht bei Umstellung? |
|---|---|---|
| `tests/tdd/test_befehlspfade_folgen_ortszone.py` | `test_ac3_jetzt_nimmt_den_wegpunkt_der_ortstag_etappe:188`, `..._nicht_der_systemuhr[jetzt]:602` | Nein — je Etappe genau **ein** Wegpunkt, Interpolation liefert denselben Punkt |
| `tests/tdd/test_issue_731_unified_commands.py` | `:268`, `:274`, `:368` | Nein — reines Routing/Parser-Mapping |
| `tests/tdd/test_issue_704_telegram_interactive_navigation.py` | `:161`, `:177`, `:194`, `:223` | Nein — keine Koordinaten-Assertion (obwohl `:194` als einziger ein Zwei-Wegpunkt-Szenario durchläuft) |
| `tests/unit/test_radar_budget_and_priority.py` | `test_jetzt_command_uses_user_briefing_priority_explicitly:243` | Nein — zeichnet nur `priority` und `tz` auf, nicht `lat/lon` |

Das ist der eigentliche Befund: nicht „Tests müssen angepasst werden", sondern **es gibt nichts, was den Messpunkt bewacht**. Der neue Test schließt eine offene Flanke, er ersetzt keine bestehende Zusicherung. Zwei Mitläufer sind zu beachten: `tests/tdd/test_feature_656_radar_nowcast.py` (fünfte `/now`-Testdatei, im Ticket nicht genannt, ebenfalls koordinaten-unabhängig) und der Struktur-Wächter `tests/test_success_status_guard.py:1855`.

### 2. 🟢 Die Brücke Etappe → Segment existiert und passt ohne Umbau

`_show_now` hat bereits `trip` und `now_utc` und berechnet `today = trip_local_today(trip, now_utc)` (:1512). `resolve_current_segment(trip, now_utc, today)` verlangt exakt diese drei Werte. Es entsteht **keine** neue Auswahllogik — die Intake-Sorge, hier müsse eine Auflösungsschicht gebaut werden, ist damit ausgeräumt.

### 3. 🔴 Offene Designentscheidung: welcher Zeitpunkt wird gemessen?

Die beiden bestehenden Aufrufstellen messen **nicht** zum Abfragezeitpunkt, sondern zur Mitte des Vorhersagefensters (A: `now + 55//2` Min, B: `now + 180//2` Min). Grund in #2017: der Alarm ist eine **Vorwarnung** — relevant ist, wo der Wanderer sein wird, wenn das Ereignis eintritt.

Für `/jetzt` ist das nicht übertragbar. Der Nutzer steht an einem Ort und fragt nach genau diesem Ort. Eine Fenstermitte-Messung könnte „hier ist es trocken" antworten, während er im Regen steht — eine offensichtlich falsche Antwort auf eine Frage nach dem Jetzt. **Empfehlung: `at = now_utc`.** Das ist kein Sonderweg, sondern die wörtliche Anwendung derselben Regel: gemessen wird dort, wo der Nutzer zum relevanten Zeitpunkt ist — und bei `/jetzt` ist der relevante Zeitpunkt jetzt.

Der Zirkelschluss-Vorbehalt aus #2017 („onset-frei") greift hier nicht: `now_utc` ist ein fester, aus dem Nowcast-Ergebnis nicht ableitbarer Wert. Die Anforderung bleibt also gewahrt.

### 4. 🟡 Randfall spät abends: `resolve_current_segment()` liefert `None`

Die Vorrangkette deckt ab: aktives Segment heute → aktives Segment gestern → Vorschau vor dem Start. Das Ziel-Segment schließt am Tagesfenster-Ende (typisch 22:00 Ortszeit inklusiv, also 23:00). Fragt der Nutzer danach `/jetzt`, kommt `None` zurück.

- Heutiges Verhalten in diesem Fall: `waypoints[0]` — der Etappenstart, also die **volle Etappenlänge** daneben.
- Frühmorgens vor dem Start greift Stufe 3 (Vorschau) → `position_at_time` gibt `start_point` zurück → **bitgleich** zu heute. Kein Randfall.

Zu entscheiden ist, ob der `None`-Fall auf dem heutigen Verhalten bleibt (minimalinvasiv, aber die Nacht-Antwort bleibt falsch) oder auf den letzten Wegpunkt geht (inhaltlich richtig, aber eine Auswahlentscheidung über das Ticket hinaus). Kommt als AC in die Spec.

### 5. 🟢 Bestätigt: kein Verstoß gegen bestehende Entscheidungen

`docs/specs/modules/fix_2017_nowcast_messpunkt.md:414-420` hält fest, dass dieser Bereich keine ADR-Grundsatzentscheidung berührt. `/jetzt` ist dort ausdrücklich als Folge-Issue vorgesehen. `docs/adr/ADR-0044` (Ortstag) bleibt unberührt: der Etappen**tag** bestimmt weiterhin, **welche** Etappe gilt — geändert wird nur, **wo auf ihr** gemessen wird.

## Risks & Considerations

| Risiko | Umgang |
|---|---|
| **Struktur-Wächter `success_status_guard` wird rot** — ein zusätzlicher `try/except` mit `logger.error` in `_show_now` verändert die B18-Zählung (Restlisten-Wert `1` bei `:1855`) | Bei der Implementierung mitlaufen lassen; `logger.error` gehört in den **except**-Zweig, nie in den Normalpfad |
| **Cache-Schlüssel-Vervielfachung (#1991)** — die interpolierte Höhe ist ein `float` und wandert bei jedem Abruf | `int(round(...))` an der Aufrufstelle, wie A und B es tun. Zusätzlich: jede `/jetzt`-Abfrage erzeugt jetzt einen neuen Cache-Schlüssel, weil die Position wandert — bei `priority="user_briefing"` (nie gedrosselt) unkritisch, aber im Budget-Verhalten zu prüfen |
| **Zeitzone wandert mit** — `tz_for_coords()` auf den interpolierten Punkt statt auf `waypoints[0]` | Beabsichtigt (Muster A). Der bestehende Ortszonen-Test (`test_ac3_jetzt_...`) bleibt grün, weil dort je Etappe nur ein Wegpunkt existiert |
| **`priority="user_briefing"` muss erhalten bleiben** (#1329 C2) — eine Nutzeraktion wird nie gedrosselt | Als Negativ-AC festnageln; `test_radar_budget_and_priority.py:243` bewacht es bereits |
| **Falscher Fallback bei `None`** | Siehe Befund 4 — explizite AC statt stiller Annahme |
| **Kein Live-Netz im Test** | Aufzeichnende `RadarNowcastService`-Subklasse per `monkeypatch.setattr` (`_show_now` hat keinen Konstruktor-DI-Seam) — Muster aus `test_radar_budget_and_priority.py:243-248` |

## Bewusst nicht Teil dieses Tickets

- `src/services/trip_day.py:41,51` — nutzt ebenfalls `stage.waypoints[0]`, dort aber zur Zeitzonen-Bestimmung des Etappentags. Eigene Frage (Etappe über Zeitzonengrenze), im Ticket ausdrücklich ausgeklammert.
- Die Trip-Konfiguration des PO wird nicht angefasst.
- Die Tages-/Ortszonen-Logik von `_show_now` (#1402, #1727 S5a, ADR-0044) bleibt unverändert.
