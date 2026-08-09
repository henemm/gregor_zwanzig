# Context: fix-1628-nowcast-datenluecke

**Issue:** #1628 — „NowCast-Radardaten schlagen fuer Grenzregionen ohne dedizierte Radarquelle fehl
(503 minutely_15) — still als 'kein Regen' gewertet"
**Track:** Full Process · **Erstellt:** 2026-08-09 · **Branch:** `fix-1628-nowcast-datenluecke`

## Request Summary

Der NowCast-Radarpfad kann für einen Trip ohne jede Sichtbarkeit ausfallen: jede Fehlerursache —
HTTP-Fehler, Zeitüberschreitung, Kontingent-Bremse, Parsefehler, fehlende Abdeckung — endet im
gleichen Ergebnis wie „geprüft, es regnet nicht". Weder Nutzer noch Betrieb können die beiden
Fälle unterscheiden.

## 🔴 Die Ursachenkette des Issues ist an ihrem ersten Glied widerlegt

Das Issue behauptet (Schritt 1 seiner Kette), für die Grenzkoordinaten 46.73042/12.321643 greife
**keine** regionale Quelle und es werde ausschließlich der generische Open-Meteo-Fallback erreicht
(„Bounding-Box-Lücke direkt an der Staatsgrenze"). Gemessen am 2026-08-09:

**a) Die Koordinate liegt in drei Bounding-Boxen** (`radar_service.py:30-58`):

| Quelle | Box | 46.73 / 12.32 |
|---|---|---|
| RADOLAN (DE) | lat ab 47.0 | draußen |
| **INCA (AT)** | 46.3–49.1 / 9.5–17.2 | **drin** |
| DPC (IT) | 36.0–47.5 / 6.5–19.0 | **drin** |
| ICON-D2 | 44.0–58.0 / 2.0–19.0 | **drin** |

**b) Der echte Produktivpfad liefert INCA-Daten.** `RadarNowcastService().get_nowcast(46.73042,
12.321643)` gegen die Live-Dienste:

```
source            = INCA
frames            = 12
onset_minutes     = None
convective_checked= True
throttled         = False
```

**c) Der Dienst selbst antwortet.** Direktabruf des INCA-Nowcast-Endpunkts für dieselbe Koordinate:
HTTP 200, 12 Zeitstempel, `rr`-Werte vorhanden. Kontrollpunkt Innsbruck ebenfalls 200.

### Was stattdessen die wahrscheinliche Erklärung ist

Der INCA-Zweig ruft einen **Beiabruf für die Gewitter-Kennzeichnung** auf, weil INCA kein
Gewitter-Feld führt: `sidecar = self._fetch_openmeteo_15(lat, lon)` (`radar_service.py:381`) —
**ohne** `models`-Parameter. Genau das steht in der Logzeile des Issues (`models=None`).
Schlägt er fehl, setzt der Code `self._convective_checked = False` (`:389`) und liefert die
INCA-Regenbilder unverändert zurück.

Das passt zum Journal vom 2026-08-08 ohne jede Zusatzannahme: **keine einzige**
`GeoSphere INCA failed`- oder `Radar-DPC failed`-Zeile, und auch keine mit
`models=icon_d2`/`models=italia_meteo_arpae_icon_2i` — nur `models=None`.

**Folge, falls diese Lesart stimmt:** Der Regen-NowCast funktionierte. Ausgefallen ist die
**Gewitter-Prüfung**. `is_convective` bleibt dann auf allen Bildern `False`, die Intensitätsstufe
„Starker Hagel/Gewitter" (`INTENSITY_CONVECTIVE`) kann nicht mehr entstehen — ein Hagelgewitter
im Radarbild würde als bloßer Regen gemeldet.

### Die Alternative ist ausgeschlossen (Nachtrag Phase 2)

Die Gegenthese wäre: INCA war am 08.08. gestört und die Kette fiel bis zum letzten, generischen
Abruf durch. Das ist durch eine zweite Messung widerlegt.

**Gemessen 2026-08-09:** ICON-D2 liefert für 46.73042/12.321643 echte Werte
(`precipitation: [0.0, 0.0, …]`), **nicht** die All-None-Antwort, die still zur nächsten Stufe
durchfallen lässt.

Daraus folgt zwingend:

- Wäre die Kette durchgefallen, hätte **ICON-D2 vorher gegriffen** und Bilder geliefert
  (`_fetch_frames_with_fallback` `:310-313`) — der generische Abruf wäre nie erfolgt, es gäbe
  keine `models=None`-Zeile.
- Wäre ICON-D2 selbst gescheitert, stünde `models=icon_d2` im Log. Nicht beobachtet.
- Ein stiller Pfad dorthin existiert nicht: die Sperre `_openmeteo_unavailable_this_call` greift
  erst **nach** einem bereits geloggten Fehlschlag. Der vorangehende ARPAE-Versuch hätte mit
  `models=italia_meteo_arpae_icon_2i` geloggt. Ebenfalls nicht beobachtet.

**Es bleiben genau zwei Lesarten** — INCA lieferte Bilder und der Beiabruf scheiterte, oder DPC
lieferte Bilder und der Beiabruf scheiterte. Beide bedeuten dasselbe: **Radarbilder lagen vor,
ausgefallen ist ausschließlich die Gewitter-Prüfung.** Die Aussage des Issue-Titels („still als
'kein Regen' gewertet") trifft auf diesen Vorfall nicht zu.

Der zugrundeliegende blinde Fleck bleibt trotzdem real und ist der Kern des Issues: mehrere
Zwischenstufen steigen lautlos aus — `fetch_nowcast` fängt `httpx.HTTPStatusError` und gibt `None`
zurück **ohne Log** (`providers/geosphere.py:348-349`), der All-None-Guard returnt ohne Log
(`radar_service.py:460-461`). Dass die Rekonstruktion oben überhaupt nötig war — und nur über eine
nachträgliche Live-Messung gelang — ist selbst der Befund.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/radar_service.py` | Quellenkette `_fetch_frames_with_fallback` (`:283-316`), Beiabruf-Aufrufe (`:353,381`), Open-Meteo-Funnel `_fetch_openmeteo_15` (`:410-482`), `_derive_result` (`:525-573`), `NowcastResult` (`:80-92`), Textausgabe `format_now_text` (`:227-277`) |
| `src/providers/geosphere.py` | `fetch_nowcast` (`:330-349`) — schluckt jeden HTTP-Fehlerstatus **ohne Log**; Nicht-HTTP-Fehler fliegen bis zum breiten `except` im Aufrufer |
| `src/providers/radar_dpc.py` | `fetch_nowcast` (`:114-149`) — alles in einem `try/except Exception`, NODATA gilt als trocken |
| `src/providers/brightsky.py` | `fetch_radar` (`:55-123`) — wirft `ProviderRequestError` bei HTTP-Status, degradiert erst im Aufrufer |
| `src/services/radar_cache.py` | Prozess-Cache, Schlüssel `lat_lon_region`, TTL 300 s; **Negativ-Ergebnisse werden nie gecacht** (`:90-97`) |
| `src/services/forecast_budget.py` | `ForecastBudgetGate`, Tagesbudget 9000, Schwellen 0.80/0.95, fail-open; `snapshot()` (`:93-119`) im Produktivcode nie aufgerufen |
| `src/services/trip_alert.py` | `radar_alert_due` (`:82-85`), `check_radar_alerts` (`:819-860`) |
| `src/services/compare_radar_alert.py` | Ortsvergleich-Parallelpfad, importiert `radar_alert_due` (`:30,243`) |
| `src/services/alert_gate.py` | gemeinsamer Freigabe-Baustein beider NowCast-Pfade (#1467 S3) — Ruhezeit/Sperrzeit/Tageslimit, **nicht** Datengrundlage |
| `src/services/official_alerts/warn_egress.py` | **Vorbild-Muster** für Beobachtbarkeit (s.u.) |
| `src/output/renderers/email/unavailable_hint.py` | **Vorbild-Muster** für den Nutzerhinweis (#1348) |

## Vier Aufrufer des NowCast

| Aufrufer | Datei:Zeile | Priorität |
|---|---|---|
| `TripAlertService.check_radar_alerts()` | `trip_alert.py:819` | `polling` |
| `CompareRadarAlertService._detect_triggered_locations()` | `compare_radar_alert.py:239` | `polling` |
| `TripCommandProcessor._show_now()` (`/jetzt`) | `trip_command_processor.py:1293` | `user_briefing` |
| `TripReportScheduler._build_starkregen_hint()` | `trip_report_scheduler.py:1170` | `polling` |

## Der eigentliche Befund: alles konvergiert auf denselben Endzustand

`frames=[]` → `onset_minutes=None` → `intensity_label="Kein Niederschlag"` → `radar_alert_due()`
liefert `False` → `continue`. Erreicht wird dieser Zustand durch **jede** der folgenden Ursachen,
ununterscheidbar:

1. echter HTTP-Fehler (503/500/timeout) in jedem Kettenglied
2. Kontingent-Bremse des Budget-Gates
3. All-None-Antwort eines Regionalmodells (Punkt außerhalb des rotierten Gitters)
4. Parse-/Formatfehler beim Provider
5. tatsächlich trockene Lage

### Das eine vorhandene Signal ist doppelt wirkungslos

`NowcastResult.throttled` (`radar_service.py:88-92`) soll „keine Datengrundlage" anzeigen. Es ist:

- **falsch verdrahtet:** `throttled = bool(self._budget_throttled_this_call) and not frames`
  (`:563`) — hängt allein an der Kontingent-Bremse. Ein echter 503 setzt
  `_openmeteo_unavailable_this_call`, **nicht** `throttled`. Der Fall aus #1628 lässt es auf `False`.
- **unbenutzt:** kein einziger Lesezugriff im Produktivcode. Einziger Treffer repoweit:
  `tests/unit/test_radar_budget_and_priority.py:131`.

`convective_checked=False` ist das zweite Teilsignal und funktioniert dem Prinzip nach richtig
(ADR-0018-Muster, Spec `radar_convective_stage.md`) — erzeugt die Zeile „Gewitter-Check nicht
verfügbar." in `format_now_text` (`:271-272`). Aber: **diese Zeile erscheint nur in einer Meldung,
die nur bei erkanntem Regen verschickt wird.** An einem trockenen Tag ist der Ausfall unsichtbar.

## Existing Patterns — was NICHT neu erfunden werden darf

**a) Beobachtbarkeit über fail-soft-Grenzen hinweg — `warn_egress.py` (#1348/#1422):**
- JSONL-Journal `data/diagnostics/warn_service_calls.jsonl`; Felder `ts, service, host, status,
  cache_hit, retry_after, ok, self_throttled`. Jeder Schreibvorgang in `try/except: pass` —
  „Observability darf den Abruf NIE beeinträchtigen".
- `contextvars`-basierter Beobachtungs-Kontext `observe_fetch_failure()` (`:69-96`) erkennt über
  mehrere fail-soft-Aufrufe hinweg, ob mindestens eine **zuständige** Quelle real scheiterte →
  `unavailable = covering > 0 and failed >= 1` (`base.py:146`).
- Unterscheidet ausdrücklich „nicht zuständig" (fachlicher Erfolg, leeres Ergebnis) von
  „Abruf tot" — `not_covered_statuses` (`:431-444`).
- Go-Seite aggregiert dieselbe Datei (`internal/scheduler/warn_service_health.go`) und liefert
  **Rohdaten ohne Schwellenentscheidung** in `/api/scheduler/status`; die Bewertung liegt extern
  in `check-gregor20.sh`.

**b) Nutzerhinweis — `unavailable_hint.py` (#1348):** ein Modul, drei Verpackungen (HTML-Danger-Box,
Plain-Zeile, Kompaktform), eingebunden in `email/plain.py:265`, `email/html.py:1608`,
`email/compact.py:205`, `email/compare_html.py:1548`. Wortlaut-Prinzip: *„'keine Warnung' bedeutet
hier nicht sicher 'alles ruhig'."*

**c) Egress-Zähler `data/diagnostics/openmeteo_calls.jsonl`** (`src/providers/call_log.py`):
Python und Go schreiben in dieselbe Datei; `source` per Stack-Introspektion aus einer Marker-Liste.
🔴 **Der komplette Radarpfad fehlt darin** — `radar_service._fetch_openmeteo_15` baut seinen
`httpx`-Call selbst, ohne `log_api_call`. Die Marker-Liste kennt weder `radar` noch `nowcast`.
Auch BrightSky, GeoSphere-INCA und Radar-DPC haben keinen Egress-Zähler. Dokumentiert in
`docs/reference/decision_matrix.md:192-197`.

**d) Gate-Unterdrückungs-Protokoll `alert_log.py:45-57`** (`REASON_QUIET_HOURS` etc., #1467 S3):
strukturell nah, aber bewusst nur für Zustellungs-Gates. Ein `REASON_NO_DATA` o.ä. existiert nicht.

## ADRs

- **ADR-0018 „Provider-Fallback ohne Kaschieren"** (akzeptiert 2026-07-08) — jedes Ausweichen wird
  markiert, geloggt und im Health-Aggregat sichtbar; „stilles Ausweichen ohne Sichtbarkeit"
  ausdrücklich verworfen. Der Konsequenzen-Abschnitt fordert bereits: *„Neue degradierbare
  Datenpfade müssen dieselbe Nicht-Kaschieren-Invariante erfüllen"* — der Radarpfad ist dort nicht
  erwähnt und erfüllt sie nicht. **Das ist der tragende Anker für #1628.**
- **ADR-0041 „Zuständigkeit nach Art des Endpunkts — drei Muster"** (aus #1397): A echte Geometrie,
  B Auskunft des Fremdendpunkts auswerten, C Rechteck + stiller Filter, solange kein Ausfall
  entsteht. Verbindliche Prüffrage je Quelle: *kann ein nicht-zuständiger Punkt einen
  Ausfall-Hinweis auslösen?* Gilt bisher nur für **Warn**-Quellen; der Radarpfad benutzt reine
  Rechtecke, und die Warn-Quellen haben ihre Rechtecke ursprünglich **aus** `radar_service.py`
  übernommen.
- **ADR-0047** (Gewitter-Vertretung zwischen Direktquellen) — betrifft die Grundvorhersage, nicht
  den Radarpfad.
- Kein ADR behandelt den Radar-/NowCast-Pfad direkt.

## Existing Specs

| Spec | Kern | Bezug zu #1628 |
|---|---|---|
| `radar_nowcast.md` (#656) | Grund-Spec der Quellenkette | keine Aussage zu Kettentotalausfall |
| `fix_1329_c2_radar_nowcast_cache.md` (#1329 C2) | Cache + Budget-Gate + `throttled` | **Known Limitation nimmt #1628 teilweise vorweg:** „`radar_alert_due()` unterscheidet nicht zwischen 'echt kein Regen' und 'gedrosselt'" — deckt aber nur Drosselung ab, nicht echte Fehler |
| `radar_nowcast_inca_fix.md` (#770) | **Präzedenzfall:** falsche Attributnamen ließen den INCA-Zweig bei JEDEM AT-Abruf scheitern → still auf ICON-D2 zurückgefallen, monatelang unbemerkt | identischer Fehlermodus |
| `radar_convective_stage.md` (#660) | Stufe „Starker Hagel/Gewitter"; `convective_checked` als ADR-0018-Marker | betrifft genau den vermuteten Ausfall |
| `rework_1467_s3_nowcast.md` (#1467 S3) | gemeinsamer Freigabe-Baustein `alert_gate.py` | Datengrundlage außerhalb Scope |
| `fix_1555_nowcast_alert_priority.md` (#1555) | Budget-Reserve für `reason=nowcast` | gleicher Symptomraum, andere Ursache |

## Tests — Ist-Stand

Radar-Tests existieren für Cache (`test_radar_nowcast_cache_sharing.py`), Budget/Priorität
(`test_radar_budget_and_priority.py`), Offline-Fixture (`test_radar_offline_fixture_mode.py`) und
diverse Alt-Issues unter `tests/tdd/`.

🔴 **Es gibt keinen Test für einen fehlgeschlagenen Abruf als Verhaltensfrage.** Über alle
Radar-Testdateien: **null Treffer** für `503`, `HTTPStatusError`, `ConnectError`, `ReadTimeout`.
Der einzige Fehlschlag-Test
(`test_radar_budget_and_priority.py::test_no_second_openmeteo_branch_attempted_after_first_failure_in_same_call`)
prüft nur, dass kein zweiter HTTP-Versuch erfolgt — nicht, ob ein Signal entsteht.

**Fixtures:** nur `fixtures/radar/minutely_15.json` (5 Bilder, bewusst trocken). Keine
Fehlerfall-Variante, keine Fixtures für BrightSky/INCA/DPC.

## Gemessene Produktionsdaten (2026-08-08, Trip „KHW 403", Nutzer `henning`)

- **18** Zeilen mit 503 im Python-Journal des Tages, davon **15** aus `radar_service` (alle
  `models=None`), der Rest aus dem normalen Vorhersage-Pfad (`providers.openmeteo`).
- **71** Läufe von `radar-alert-checks` für `henning` an diesem Tag → die Fehlschläge betrafen rund
  ein Fünftel der Läufe, nicht „14 von 14" wie im Issue angegeben.
- 🔴 **Alle Fehlschläge liegen auf `:00` oder `:30`** — nie auf `:15`/`:45`, obwohl die Prüfung im
  15-Minuten-Takt läuft. Die Job-Verteilung erklärt das nicht: zu `:15` und `:45` laufen dieselben
  sechs `*/15`-Jobs (`internal/scheduler/scheduler.go:145-153`), nur `:00` hat zusätzlich den
  stündlichen Briefing-Versand. **Ungeklärt — gehört in die Analyse.**
- **Am 2026-08-09 (heute): null** Radar-Fehlschläge. Der Zustand ist zeitweilig, nicht dauerhaft.

## Dependencies

- **Upstream:** GeoSphere INCA, BrightSky/RADOLAN, Radar-DPC, Open-Meteo (`minutely_15`, Modelle
  `arome_france_hd`/`icon_d2`/`italia_meteo_arpae_icon_2i`), `ForecastBudgetGate`, Radar-Cache.
- **Downstream:** Trip-Radaralarm, Ortsvergleich-Radaralarm, `/jetzt`-Telegram-Kommando,
  Starkregen-Hinweis im Briefing; Renderer über `OnsetEvent`
  (`src/output/renderers/alert/model.py:31`).

## Risks & Considerations

1. **Kontingent.** Jede zusätzliche Absicherung (Wiederholversuch, zweite Quelle) trifft direkt den
   Verbraucher, der laut #1329 das Open-Meteo-Kontingent dominiert. Mehr Abrufe sind keine Lösung.
2. **Sprengweite des lauten Scheiterns.** #1467 S3 F004 (CRITICAL): „laut scheitern" ohne Begrenzung
   riss den ganzen NowCast-Lauf ab, gesunde Nachbarn wurden nie erreicht. Vertrag in der
   Schreibfunktion, `try/except` je Entität am Aufrufer.
3. **Trip/Ortsvergleich teilen.** Der Ortsvergleich hat einen eigenen Parallelpfad
   (`compare_radar_alert.py`, 1:1 vom Trip übernommen). Jede Lösung muss beide erreichen —
   Teilungsregel ist ein Gate, keine Präferenz.
4. **Nicht alarmieren, wo nichts ist.** ADR-0041-Lehre: ein Ausfall-Hinweis für einen
   nicht-zuständigen Punkt ist selbst ein Fehler (Dauer-Warnung „nicht abrufbar"). Die Kette hat
   fünf Regionalquellen mit Rechteck-Abdeckung — „Quelle X lieferte nichts" ist für die meisten
   Punkte der **Normalfall**, kein Störfall.
5. **Zuschnitt.** Das Issue enthält drei Aufgaben: (a) Ursachendiagnose des 503, (b) Sichtbarkeit
   fehlender Datengrundlage, (c) Quellenkette für Grenzregionen. (c) ist nach obiger Messung
   voraussichtlich gegenstandslos. Erwartung: Scheiben, nicht ein Wurf.
6. **Regel-Budget.** Ein neues Journal + neuer Status-Block wäre neue Dauerpflicht — entweder
   Ersatz für Bestehendes oder mit Prüfdatum.

---

# Analysis (Phase 2)

## Type

**Bug** — mit einer Betriebsmaßnahme als erster Scheibe.

## 🔴 Es sind ZWEI getrennte Defekte, und der dominante steht nicht im Issue-Titel

Messung im Prod-Journal über 9 Tage (2026-08-01 bis 08-09), Verteilung aller Radar-503:
**1643× `models=arome_france_hd`** gegen **362× `models=None`**.

### Defekt A — totale NowCast-Blindheit (dominant, 1643 Vorkommen)

Betroffen: fünf **echte Nutzerorte** in der Provence (Nutzer `henning`, Ortsvergleich
`cp-eb6ba0b239d90e37`, u.a. `locations/collobri-res.json`): 43.2447/6.2628, 43.1533/6.3438,
43.0396/6.1064, 43.1364/5.8922, 43.2805/5.2155 — je ~167 Fehlschläge in 9 Tagen.

Für diese Koordinaten ist die Kette nach dem ersten Fehlschlag **strukturell zu Ende**
(`radar_service.py:28-58, 283-316`):

| Stufe | Bedingung | 43.24 / 6.26 |
|---|---|---|
| RADOLAN | lat ≥ 47.0 | nein |
| INCA | lat ≥ 46.3 | nein |
| DPC | lon ≥ 6.5 | nein (6.26) |
| **AROME-FR** | 41.0–51.5 / −5.5–10.0 | **ja → 503** |
| ICON-D2 | lat ≥ 44.0 | nein (43.24) |
| generischer `minutely_15` | — | aufgerufen, **lautlos leer** |

Der 503 setzt `_openmeteo_unavailable_this_call` (`:481`); die Sperre am Funktionsanfang
(`:421-428`) gibt danach ohne Logzeile `[]` zurück. Ergebnis: `frames=[]` → `onset_minutes=None`
→ „Kein Niederschlag" → kein Alarm. **`throttled` bleibt `False`, weil es ein echter Fehler war
und keine Kontingent-Bremse.** Damit ist die Kernaussage des Issues bestätigt — an anderen
Koordinaten als dort behauptet.

### Defekt B — abgeschwächter Gewitter-Alarm (362 Vorkommen)

An Orten **mit** Regionalquelle (INCA/DPC): Bilder liegen vor, nur der Gewitter-Beiabruf scheitert
→ `convective_checked=False`, `is_convective` bleibt überall `False`, die Stufe „Starker
Hagel/Gewitter" kann nicht entstehen. Der Alarm wird **abgeschwächt zugestellt**, nicht unterdrückt.

### Beide laufen durch dieselbe Code-Stelle

AROME-FR-Abruf (A) und Gewitter-Beiabruf (B) rufen beide `_fetch_openmeteo_15` auf und setzen im
selben `except`-Zweig dasselbe `_openmeteo_unavailable_this_call` (`:481`). **Eine einzige
Verdrahtung dieses bereits vorhandenen Zustands nach außen deckt beide Defekte ab.**

## Ursache: extern, aber mit einem selbstverursachten Anteil

- **Ausschließlich HTTP 503, im gesamten 9-Tage-Fenster kein einziger 429.** Antwortkörper immer
  wörtlich `{"error":true,"reason":"The service is overloaded"}` — Open-Meteos eigenes Format.
  Das schließt unsere Kontingent-Bremse als Ursache aus (die erzeugt gar keinen Aufruf).
- **Häufung exakt auf Minute `:00` und `:30`** (699 / 609 von 1416) gegen 28 auf `:15` und 32 auf
  `:45`. **Kein Zählartefakt:** die Prüfläufe verteilen sich gleichmäßig (1176/1180/1170/1187).
  Fehlerquote grob 60 % zu `:00` gegen 3 % zu `:15`.
- Weder Go-Scheduler noch System-Cron noch die praktisch inaktive Staging-Instanz erklären eine
  Kopplung an `:00`+`:30`. Der Sockel ist **vermutlich extern** (fremde Scheduler konvergieren auf
  runde Minuten, und/oder ein 30-Minuten-Ingest-Zyklus bei Open-Meteo) — plausibel, aus unserem
  Journal **nicht beweisbar**.
- **Gemessen dagegen:** die zusätzliche Überhöhung zu `:00` gegenüber `:30` korrespondiert mit
  unserem eigenen `briefing_dispatch` (`scheduler.go:141`, `0 * * * *`), der sich dort auf die
  sechs `*/15`-Jobs stapelt.
### 🔴 Warum die Fehler am 2026-08-04 aufhörten — Defekt A ist NICHT behoben, nur schlafend

AROME-FR-Fehlschläge je Tag: 238 · 233 · 229 · 123 (01.–04.08.) · **danach null**.

Ursache gemessen, nicht vermutet:

- Der betroffene Ortsvergleich „Le Var" (`cp-eb6ba0b239d90e37`, 8 Orte) trägt
  `paused_at: 2026-07-31T20:08:12Z`, `schedule: manual`.
- Bis zum 04.08. **ignorierte der Radar-Pfad diese Pause** und fragte weiter ab. Commit `b55bcc49`
  („feat(#1467 S2 AG6): pausierte und archivierte Ortsvergleiche schweigen") hat genau das
  abgestellt — `is_silenced(preset)` (`compare_alert_guard.py:39-54`) sitzt seither vor jedem
  Nowcast-Abruf (`compare_radar_alert.py:94-99`).

**Folge:** Defekt A ist nicht verschwunden, sondern es fragt niemand mehr. Sobald der PO diesen
Ortsvergleich wieder aktiviert — oder irgendein anderer Ort südlich 44° N ins Spiel kommt — ist er
sofort wieder da. Klassische Falle „Verbrauchstest grün, weil der Dienst tot ist".

**Zum GR20 — die Herleitung war falsch, die Messung korrigiert sie.** Vermutet war, Korsika falle
in dieselbe Lücke, weil der italienische Radar es nicht abdecke. Gemessen am 2026-08-09 mit dem
echten Produktivpfad für drei GR20-Wegpunkte (Calenzana 42.5083/8.8556, Vizzavona 42.1244/9.1339,
Conca 41.7383/9.3475):

- Boxen-Treffer überall nur **DPC + AROME-FR** — ICON-D2 greift wegen lat < 44.0 nicht.
- `get_nowcast(42.1244, 9.1339)` → **`source = DPC`**, 1 Bild. Der italienische Radar deckt
  Korsika also sehr wohl ab; AROME-FR wird gar nicht erst erreicht.

**Korrigierte Aussage:** Der GR20 steht heute nicht im selben Loch wie die Provence-Orte, sitzt aber
auf demselben Sackgassen-Ast: Fällt DPC aus, folgen ARPAE und AROME-FR, und danach ist bei lat < 44
ebenfalls Schluss — mit demselben lautlosen `[]`. Eine Schicht mehr Puffer, dieselbe Endlage.

⚠️ **Nebenbefund (nicht Teil dieses Issues):** DPC liefert **ein einziges** Bild (SRI = momentane
Regenrate, kein Vorhersage-Verlauf). Für Korsika beantwortet der NowCast damit „regnet es jetzt?",
nicht „regnet es in 20 Minuten?" — `radar_alert_due(..., threshold_min=20)` kann dort praktisch nur
bei bereits laufendem Regen auslösen. Gehört gebucht (#1199 oder Bezug zu #1174).

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `internal/scheduler/scheduler.go` | MODIFY | S0: Cron-Ausdruck der zwei Radar-Jobs (`:149`, `:152`) |
| `src/services/radar_service.py` | MODIFY | S1: Feld auf `NowcastResult` + Speisung; S3: Textzeile |
| `src/providers/geosphere.py` | MODIFY | S2: Logzeile an der Schluck-Stelle (`:348-349`) |
| `src/providers/radar_dpc.py`, `brightsky.py` | MODIFY | S2: Äquivalente prüfen |
| `src/providers/call_log.py` | MODIFY | S4: Radarpfad in die Marker-Liste (nach #1633) |
| `tests/unit/test_radar_*.py` | CREATE/MODIFY | erster Test überhaupt für fehlgeschlagenen Abruf |

**Nicht** anzufassen: `trip_alert.py`, `compare_radar_alert.py` — beide lesen dieselbe
`NowcastResult`-Instanz derselben Klasse. Eine Felderweiterung erreicht beide Pfade automatisch;
das ist der Idealfall der Teilungsregel (eine Quelle, zwei Konsumenten).

## Technical Approach

Das Vorbild `warn_egress.py` (#1348) wird **bewusst nicht** übernommen. Begründung: dort iteriert
`base.py:120-148` über mehrere **unabhängig zuständige** Quellen und braucht `contextvars`, weil
der Fehlschlag tief in einer fremden Quelle passiert. Der Radarpfad ist eine **Kaskade in einem
einzigen Aufrufstack derselben Instanz** — er besitzt die Unterscheidung bereits als
Instanzattribut und verwirft sie nur. Übertragen wird die *Formel* („Drosselung ≠ Anbieter-
Ausfall", `self_throttled` ↔ `throttled`) und das Wortlaut-Prinzip aus `unavailable_hint.py`.

**Wo die Grenze „nicht zuständig" ↔ „zuständig, aber ausgefallen" verläuft** — nicht bei „liegt der
Punkt in der Box" (laut ADR-0041 nur ein netzfreier Vorfilter), sondern bei „erzeugte die konkrete
Anfrage einen Fehlerstatus, oder eine strukturierte Leerantwort ohne Fehlerstatus":

- **Regionalmodell-Zweige:** Unterscheidung existiert bereits sauber — All-None-Guard (`:460-461`,
  kein Flag, kein Log, korrektes ADR-0041-Muster B) vs. echte Ausnahme (Flag **und** Log).
- **Gewitter-Beiabruf:** die Frage stellt sich gar nicht — der All-None-Guard greift nur
  `if models and …`, der Beiabruf läuft **ohne** `models`. Ein leeres Ergebnis kann dort nur
  Fehlschlag oder Drosselung sein. Der in #1628 beobachtete Fall ist damit der **einfachste** der
  ganzen Kette.
- **INCA/DPC-Primärabruf:** Unterscheidung fehlt **vollständig**. `geosphere.py:348-349` schluckt
  `httpx.HTTPStatusError` zu `None` ohne jeden Log — der äußere `except` in `radar_service.py:358`
  sieht den Fehler nie. Hier muss sie erst geschaffen werden.

**Wo das Signal endet:** Nutzertext ja (einziger Ort, der die Wirkung adressiert; Präzedenz
`unavailable_hint.py`). Journal/Status-Endpunkt später (blockiert durch #1633). **Kein**
`REASON_NO_DATA` in `alert_log.py` — schon #1348 hat dort bewusst keinen Eintrag bekommen, und
`append_suppressed_entry` hängt an einer **Unterdrückung**; hier wird der Alarm zugestellt.

**Kein Wiederholversuch, keine Ersatzquelle, kein Zurückhalten des Alarms** bei Defekt B: das
Projekt hat diese Abwägung bereits getroffen („a missed poll beats a quota outage",
`radar_service.py:91-92`) — ein abgeschwächter Alarm ist besser als keiner.

## Scope Assessment

| Scheibe | Dateien | LoC (geschätzt) | Risiko |
|---|---|---|---|
| S0 Zeitversatz | 1 (+Test) | < 20 | LOW |
| S1 Ursachen-Feld | 1 (+Tests) | < 80 | LOW |
| S2 Provider-Log | 1–3 (+Tests) | < 60 | LOW |
| S3 Nutzertext | 1 (+Tests) | < 60 | LOW |
| S4 Journal/Status | 1–2 | < 80 | MEDIUM (nach #1633) |

**Keine Scheibe fügt einen einzigen neuen HTTP-Aufruf hinzu** — das ist die harte Nebenbedingung
aus #1329 und wird durchgehend eingehalten.

## Reihenfolge und Begründung

- **S0 — Zeitversatz der beiden Radar-Jobs** (`radar_alert_checks`, `compare_radar_alert_checks`)
  weg von `:00/:15/:30/:45`, z. B. `7,22,37,52 * * * *`. Größte gemessene Wirkung auf Defekt A,
  eine Zeile, trivial rückgängig zu machen. **Kein Kaschieren im ADR-0018-Sinn**, weil die Ursache
  nachweislich extern ist (503 mit fremdem Overload-Text, kein 429) — einer bekannten zyklischen
  Lastspitze eines Fremddienstes auszuweichen ist Betriebsführung, nicht das Verstecken eines
  eigenen Defekts. **Nur diese zwei Jobs**, nicht alle sechs: für die übrigen liegt keine
  vergleichbare Messung vor, `data_write_selftest` hat gar keinen externen Bezug, und eine
  pauschale Verschiebung wäre Scope-Kriechen in #1329.
- **S1 — Ursachen-Feld auf `NowcastResult`**, gespeist aus `_openmeteo_unavailable_this_call`.
  Deckt A und B mit derselben Änderung ab, erreicht beide Aufrufer automatisch. **Zwingend, nicht
  optional:** S0 senkt die Häufigkeit, beseitigt aber weder die Restrate (~3 %) noch künftige
  Ausfälle außerhalb des Zeitmusters. Ohne S1 bleiben die lautlos.
- **S2 — Log-Lücke im INCA/DPC-Primärabruf.** Betrifft nur Defekt B (Defekt-A-Koordinaten
  erreichen INCA/DPC nie). Einzeln nützlich: schon ein Log verbessert jede künftige Fehlersuche.
- **S3 — Nutzertext**, hängt an S1.
- **S4 — Journal/Status-Endpunkt**, **blockiert durch #1633**. Dann zwingend den bestehenden
  `call_log.py`-Zähler erweitern, **kein neues Journal** — das ist zugleich der einzige Teil, der
  legitim als Beitrag zu #1337 zählt.

## Regel-Budget

S0–S3 erzeugen **keine neue Dauerpflicht** — kein neues Journal, kein Status-Block, kein Gate. Sie
lösen eine **bestehende, unerfüllte** Zusage ein (ADR-0018: „Neue degradierbare Datenpfade müssen
dieselbe Nicht-Kaschieren-Invariante erfüllen"). Ersatz, kein Neuzugang, kein Prüfdatum nötig.
S4 wäre eine echte neue Pflicht → Prüfdatum oder ausdrücklicher Ersatz des heute ungelesenen
`throttled`.

## Verhältnis zu offenen Issues

- **#1633** (Diagnose-Journale schreiben in den Programmordner, Überwachung seit 2026-08-08 blind):
  **Vorbedingung nur für S4.** S0–S3 sind unabhängig lieferbar, sie schreiben in kein Journal.
  Selbst nachgeprüft: `warn_egress.py:100`, `call_log.py:21`, `openmeteo.py:78` tragen relative
  Pfade; `forecast_budget.py` und `alert_log.py` sind korrekt.
- **#1581** (Health-Signal aus ADR-0018 für Gewitter-Direktquellen nie nachgezogen): **gleiche
  Regel, nicht zwingend gleicher Code.** Kein gemeinsames Modul vorab bauen — ob dessen Pfad die
  Cross-Boundary-Form hat, ist ungeprüft.
- **#1337** (zentraler Egress-Wächter): S4 ist ein echter kleiner Beitrag. Befund dazu:
  `_fetch_openmeteo_15` (`:447`) baut seinen `httpx`-Aufruf **komplett am zentralen Zähler vorbei**
  — genau das von #1337 benannte Muster.

## Open Questions (für den PO)

- [ ] **S0 ist eine Betriebsmaßnahme, kein Bugfix.** Zusammen mit S1 in dieses Issue, oder
      getrennt? (Empfehlung: zusammen, S0 zuerst — der Nutzen ist sofort und messbar.)
- [ ] **Reicht der Schnitt bis S3 für dieses Issue**, mit S4 als eigenem Folge-Issue hinter #1633?
- [ ] Der Einbruch der Fehlerrate ab 2026-08-05 bei konstanter Last ist ungeklärt. Nachgehen oder
      als Rauschen behandeln?
