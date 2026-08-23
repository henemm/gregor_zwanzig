# ADR-0021: Gemeinsame `DeviationAlertEngine` für Trip- und künftige Compare-Alarme

- **Status:** Akzeptiert (PO-„go" 2026-07-09)
- **Datum:** 2026-07-09
- **Bezug:** GitHub-Issue #1168 (Scheibe 1/3, Epic #1095), Spec
  `docs/specs/_archive/modules/issue_1168_alert_engine_extract.md`, Architektur-Gegenüberstellung
  `docs/context/feat-1095-compare-alerts.md` (Abschnitt „Architektur-Gegenüberstellung
  Trip ↔ Compare"); verwandt [ADR-0011](0011-alert-render-single-backend-renderer.md)
  (kanonischer Alert-Renderer), [ADR-0017](0017-output-paket-konsolidierung.md)
  (`NotificationService` als einziger Versand-Orchestrierer); Folge-Issues #1169
  (Scheibe 2 — Compare-Anbindung, live seit 2026-07-09), #1170 (Scheibe 3 — Config-UI, offen)

## Kontext

Der Orts-Vergleich (Epic #1095) soll künftig eigene Abweichungs-Alarme auslösen können,
analog zu den bestehenden Trip-Alarmen (Issue #816 ff.). Der heutige
Deviation-Alert-Auswertungskern lebt vollständig in `TripAlertService`
(`src/services/trip_alert.py`) und liest an mehreren Stellen `trip.*`-Felder direkt
(Cooldown, Ruhezeiten, Alarmregeln, Kanäle). Eine Analyse des Kerns zeigt jedoch, dass
die eigentliche Entscheidungslogik — Change-Detection, Filter significant,
Filter-gegen-Melde-Gedächtnis, Severity-Bestimmung, Quiet-Hours (inkl.
Mitternachts-Wrap), Cooldown, Kanalwahl — bereits **location-generisch** ist: sie
operiert auf Wetterdaten-pro-Punkt + Konfigurationswerten, nicht auf `Trip`-,
`Stage`- oder `Waypoint`-Strukturen. Rendering (ADR-0011) und Versand (ADR-0017) sind
bereits als geteilte Services etabliert — nur der Auswertungskern selbst war noch nicht
herausgelöst.

## Entscheidung

Der Deviation-Alert-Auswertungskern wird in einen eigenständigen Shared-Service
extrahiert: `DeviationAlertEngine` (`src/services/deviation_alert_engine.py`), der auf
generischen DTOs operiert (`PointWeatherData`, `AlertEvaluationConfig`, beide in
`src/services/point_weather.py`) und **kein** `Trip`-Objekt kennt.
`TripAlertService` wird zum dünnen Adapter: er baut `AlertEvaluationConfig` aus
Trip-Feldern, wandelt `List[SegmentWeatherData]` verlustfrei über
`TripSegmentWeatherAdapter` in `List[PointWeatherData]`, ruft
`DeviationAlertEngine.evaluate(...)` auf und delegiert Rendering/Versand unverändert
weiter. Ein künftiger Compare-Adapter (Scheibe 2, #1169) baut dieselbe
`AlertEvaluationConfig` aus einem `ComparePreset` und ruft dieselbe Engine — ohne die
Auswertungslogik zu duplizieren.

Das Alert-Melde-Gedächtnis (`AlertStateService`, Issue #816) wird parallel auf einen
generischen `entity_id`-Parameter umgestellt (statt `trip_id`); das Dateipfad-Schema
`data/users/<user_id>/alert_state/<entity_id>.json` bleibt unverändert, sodass
bestehende `<trip_id>.json`-Dateien ohne Migration gültig bleiben.

Diese Scheibe (#1168) ist ein reiner Umbau ohne Verhaltensänderung: Trip-Alarme
verhalten sich danach bit-identisch. Die Compare-Anbindung selbst ist NICHT Teil
dieser Scheibe (Scheibe 2, #1169).

## Verworfene Alternativen

- **Separate Compare-Engine duplizieren** — verworfen: eine zweite,
  eigenständige Auswertungs-Engine für den Orts-Vergleich hätte Change-Detection,
  Filter-, Severity- und Quiet-Hours-/Cooldown-Logik dupliziert. Jede künftige
  Korrektur (z. B. an der Severity-Klassifikation oder der Mitternachts-Wrap-Logik)
  müsste dann an zwei Stellen synchron gehalten werden — ein bekanntes
  Divergenzrisiko (vgl. die bereits konsolidierten Renderer-/Versand-Schichten in
  ADR-0011/ADR-0017).
- **`TripAlertService` direkt um Compare-Fälle erweitern (Trip-Objekt optional
  machen)** — verworfen: hätte `Trip`-Kopplung tief in den Auswertungskern
  hineingezogen (z. B. `trip.display_config`-Backfill-Logik) und die Abgrenzung
  zwischen „location-generischem Kern" und „Trip-spezifischem Adapter" verwischt.
- **Nichts tun, bis Scheibe 2 (#1169) beginnt** — verworfen: die Extraktion selbst
  ist eine unabhängig verifizierbare Einheit (bit-identisches Trip-Verhalten als
  Hard-Gate) und reduziert das Risiko für Scheibe 2, da die Engine bereits gegen
  echte Trip-Alarm-Läufe (AC-1/AC-2/AC-4) verifiziert ist, bevor ein zweiter
  Consumer angeschlossen wird.

## Konsequenzen

- **Positiv:** Ein gemeinsames „Alarm-Gehirn" für Trip und künftigen Compare;
  Korrekturen an Severity/Quiet-Hours/Cooldown/Filter-Logik wirken künftig für beide
  Consumer gleichzeitig. `TripAlertService` wird spürbar dünner (Change-Detection,
  Filter-gegen-State und Severity-Bestimmung sind nicht mehr in `trip_alert.py`
  dupliziert).
- **Preis:** Ein interner Adapter (`_PointShim`/`_SegmentIdShim` in
  `deviation_alert_engine.py`) übersetzt zwischen dem generischen `PointWeatherData`
  und dem von `WeatherChangeDetectionService.detect_changes()` erwarteten
  Attribut-Shape (`.segment.segment_id`/`.start_time`/`.end_time`), damit
  `PointWeatherData` selbst frei von `TripSegment`-Kopplung bleibt. Trip-spezifische
  Detektor-Wahl (`_select_change_detector`, abhängig von `trip.display_config`) bleibt
  bewusst im Adapter — die Engine erhält den fertigen Detektor als Override-Parameter,
  statt die Weather-Tab-Aktivierungs-Nuancen selbst nachzubilden.
- **Folgepflichten:** Scheibe 2 (#1169, live seit 2026-07-09) hat den Compare-Adapter gebaut
  (`CompareAlertService`/`compare_alert.py`, eigener `AlertEvaluationConfig`-Builder mit
  hartkodierten Defaults, `compare_location_weather_source.py` als
  `LocationWeatherSource`-Implementierung) und den Orts-Vergleich als **zweiten, realisierten
  Consumer** an dieselbe Engine angeschlossen — siehe
  `docs/specs/_archive/modules/issue_1169_compare_alert_consumer.md`. Scheibe 3 (#1170, offen) ergänzt
  die Config-UI. Tageslimit (`alert_daily_limit`), Alert-Log und Radar-Onset-Pfad
  bleiben vorerst Trip-spezifisch im Adapter (siehe „Known Limitations" der Spec) —
  eine Verallgemeinerung dieser Bausteine ist separat zu betrachten, falls Compare
  sie ebenfalls benötigt.
- **Nachtrag (Issue #1461 S3b-2b, 2026-08-06):** der Radar-Onset-Pfad ist kein
  Trip-Sonderweg mehr — `compare_radar_alert.py` löste seine Kanalliste bis
  dahin hart auf `{"email"}` verdrahtet auf, unabhängig vom Kanal-Opt-in des
  Nutzers (verfallene Begründung: „Compare-Presets besitzen keine
  Telegram-/SMS-Empfänger-Zuordnung", überholt seit #1467 S2 AG1). Seit S3b-2b
  nutzt auch dieser Pfad den einen Compare-Kanal-Resolver
  (`effective_compare_channels()`) — derselbe Resolver wie die beiden anderen
  Compare-Alarmwege. Tageslimit und Alert-Log bleiben unverändert Trip-spezifisch
  im Adapter (kein Compare-Bedarf bekannt).
- **Nachtrag (Issue #1467 S3, 2026-08-08):** der letzte Satz des vorigen
  Nachtrags ist überholt. Die **Tages-Obergrenze gilt seit dieser Scheibe
  gemeinsam** für den Trip- und den Ortsvergleich-Nowcast — beide laufen über
  den geteilten Freigabe-Baustein `services/alert_gate.py` mit der festen
  Reihenfolge Ruhezeit → Sperrzeit → Tages-Obergrenze. Der Ortsvergleich hatte
  bis dahin **gar keine** Tages-Obergrenze (die Bremse gegen Meldungsfluten
  fehlte vollständig) und führte seine Sperrzeit in einer eigenen, ungesicherten
  Datei; beides ist auf die geteilten Bausteine gezogen (`ThrottleStore`, neuer
  Scope `compare_radar`). Das **Alert-Log** ist ebenfalls kein Trip-Sonderweg
  mehr: beide Nowcast-Pfade protokollieren jetzt auch, WARUM eine Meldung
  unterdrückt wurde (`REASON_QUIET_HOURS`/`REASON_COOLDOWN`/
  `REASON_DAILY_LIMIT`) —
  Änderungs- und amtlicher Alarm bewusst weiterhin nicht
  (offene Lücke O3 in `feat_1459_alert_protokoll.md`). Kein neues
  Architekturprinzip: das bestehende aus diesem ADR wird auf den letzten noch
  abweichenden Pfad angewandt. Details:
  `docs/specs/modules/rework_1467_s3_nowcast.md`.
- **Nachtrag (Issue #1752, 2026-08-12):** was der Nachtrag zu #1461 S3b-2b für den
  **Ortsvergleich** vollzogen hat, ist jetzt auch für den **Trip** eingelöst. Der
  Trip-Radar-Pfad löste seine Kanäle bis dahin über eine eigene Fassung
  (`_radar_effective_channels()`) auf, die **ausschließlich die Briefing-Flags**
  las und `trip.alert_channels`/`trip.alert_rules` nie — die im Alarme-Reiter
  getroffene Auswahl war für Regen-Alarme also wirkungslos (#1745, Befund 2).
  Die Sonderfassung ist ersatzlos entfallen; das Kanal-Set wird einmal über
  `_effective_alert_channels()` aufgelöst und im ganzen Radar-Pfad geteilt
  (Unterdrückungs-Protokoll, Leer-Check, Versand). Damit gibt es **einen**
  Auflösungsweg für alle vier Trip-Alarmtypen. **Kein neues Architekturprinzip**
  — dasselbe Muster wie bei S3b-2b, angewandt auf den letzten Pfad, der noch
  abwich. Zwei benannte Folgen: Radar erbt damit auch die `alert_rules`-Union
  mit, und ein Alarmversuch ohne erreichbaren Kanal hinterlässt jetzt einen
  Protokoll-Eintrag statt spurlos abzubrechen. Details:
  `docs/specs/modules/fix_1752_radar_folgt_alarm_kanaelen.md`.
- **Nachtrag (Issue #1594, 2026-08-14):** `services/alert_gate.py` beherbergt seit
  dieser Scheibe **zwei voneinander unabhängige Funktionen**, nicht mehr nur die
  eine Kette. Die im #1467-S3-Nachtrag beschriebene Reihenfolge
  Ruhezeit → Sperrzeit → Tages-Obergrenze (`check_nowcast_gate()`) gilt
  unverändert und **ausschließlich für NowCast**. Daneben steht neu
  `check_briefing_imminent()`: eine rein lesende Stufe, die einen
  **Änderungsalarm oder eine amtliche Warnung** unterdrückt, wenn für dieselbe
  Entität innerhalb von 60 Minuten ein geplantes Briefing ansteht, das **noch
  nicht versucht** wurde. Sie ist an drei Stellen eingehängt
  (`trip_alert._is_quiet_hours`-Umfeld für beide Trip-Alarmarten,
  `compare_alert.py`, `compare_official_alert.py`) und wird von
  `check_nowcast_gate()` **nicht** gerufen — die NowCast-Ausnahme ist damit
  baulich, nicht durch Sorgfalt an den Aufrufstellen.
  **Kein neues Architekturprinzip:** die fachliche Zulässigkeit trägt ADR-0009
  (Alerts sind Δ-Wächter gegen den letzten Briefing-Snapshot) — die Meldung wird
  durch das folgende Briefing **ersetzt**, nicht ersatzlos verschluckt, weil das
  Briefing Anker und Melde-Gedächtnis selbst zurücksetzt.
  Drei benannte Folgen: (1) Die Fälligkeit wird bei den vorhandenen Rechnern
  **erfragt** (`presets_due_for_hour()` bzw. ein aus `trip_report_scheduler`
  herausgelöstes reines Prädikat), nicht neu gerechnet — eine eigene
  Zeitrechnung wäre die vierte Fassung derselben Regel. (2) Das Prädikat trägt
  bewusst **keinen** `skip_next`-Verbrauch; `_get_active_trips()` schreibt beim
  Lesen (`save_trip()`) und darf deshalb aus dem 15-Minuten-Alarmtakt nicht
  gerufen werden. (3) Die Sperre endet mit dem Briefing-**Versuch**, nicht mit
  dessen Erfolg — `last_briefing_at()` bedeutet „versucht", weil der Anker seit
  #1629 auch im Fehlerzweig geschrieben wird; eine an den Erfolg gebundene
  Sperre hätte nach einem gescheiterten Versand bis zu vier Stunden geschwiegen.
  Eine Unterdrückung durch diese Stufe erzeugt **keinen** Protokolleintrag (Lücke
  O3 aus dem vorigen Nachtrag bleibt bewusst offen). Details:
  `docs/specs/modules/fix_1594_alarm_vorlauf_sperre.md`.
- **Nachtrag (Issue #1467 S4a, 2026-08-16):** was der Nachtrag zu #1467 S3 für die
  beiden **Nowcast**-Pfade vollzogen hat, gilt jetzt auch für die beiden
  **amtlichen** Pfade. `trip_alert.py::_send_official_alert_only` und
  `compare_official_alert.py::_check_one_preset` führten bis dahin je eine eigene
  Inline-Prüfkette; beide laufen seit dieser Scheibe über denselben geteilten
  Ablauf-Baustein `services/alert_gate.py::check_official_alert_gate()` mit der
  festen Reihenfolge Ruhezeit → Tages-Obergrenze. Der Satz zur
  Unterdrückungs-Protokollierung aus dem S3-Nachtrag bleibt unverändert richtig
  (der amtliche Pfad protokolliert weiterhin keine Gründe); überholt ist allein,
  was er zusätzlich implizierte — dass der amtliche Pfad keinen geteilten
  Ablauf-Baustein nutzt.
  Zwei bewusste Verhaltensänderungen: (1) Der amtliche **Trip**-Pfad **liest** den
  geteilten Sperrzeit-Topf `"trip"` nicht mehr — ein zugestellter Änderungsalarm
  verschluckte bis dahin bis zu 120 Minuten lang jede amtliche Eskalation;
  **geschrieben** wird der Topf weiterhin, die harmlose Gegenrichtung bleibt
  also zu. Der Baustein kennt deshalb **keinen** Cooldown-Parameter: die
  Zusicherung ist eine Eigenschaft des Funktionstyps, nicht eine Disziplin der
  Aufrufstelle. (2) Der **Ortsvergleich** prüft die Tages-Obergrenze jetzt VOR dem
  Warnungs-Abruf statt danach — ein erschöpftes Kontingent kostet keinen
  Fremd-Abruf mehr. `check_briefing_imminent()` bleibt in beiden Pfaden ein
  eigener Aufruf unmittelbar NACH dem Baustein, `is_silenced` bleibt
  Compare-eigen und außerhalb. Kein neues Architekturprinzip. Details:
  `docs/specs/modules/rework_1467_s4a_amtlich.md`.
- **Nachtrag (Issue #1467 S4b, 2026-08-16):** seit dieser Scheibe existiert eine
  **quellenübergreifende** Ereignis-Identität-Prüfung — `services/alert_gate.py::
  check_event_identity_gate()` —, als **letzte, gemeinsame** Stufe für Nowcast-
  UND amtliche Trip-Alarme (`trip_alert.py::check_radar_alerts`,
  `_send_official_alert_only`). Anders als die bisherigen Stufen (Ruhezeit,
  Sperrzeit, Tages-Obergrenze), die je Quelle in getrennten Töpfen laufen,
  entdoppelt diese Stufe **über beide Quellen hinweg**: gleiche Gefahrenklasse
  (T2-Kanon, EINE Klasse `wet`) + gleicher Ortsbezug + überlappendes Zeitfenster
  ⇒ nur die erste Meldung geht raus, außer eine echte Verschärfung (V2,
  strukturell erster Zweig) oder eine wesentliche zeitliche Erweiterung (V1-
  Ausnahme) durchbricht die Unterdrückung. Der amtliche Pfad protokolliert für
  diesen EINEN neuen Grund (`REASON_EVENT_DUPLICATE`) erstmals eine
  Unterdrückung — die Aussage aus dem S3-Nachtrag zur
  Unterdrückungs-Protokollierung bleibt für Ruhezeit/Tageslimit unverändert
  gültig (der amtliche Pfad protokolliert dafür weiterhin nichts). Kein neues
  Architekturprinzip: derselbe geteilte-Baustein-Ansatz aus diesem ADR,
  erstmals angewandt auf einen Vergleich ÜBER Quellen hinweg statt innerhalb
  einer Quelle. Details: `docs/specs/modules/rework_1467_s4b_entdopplung.md`.
- **Nachtrag (Issue #1917 S4b-2, 2026-08-19):** die quellenübergreifende
  Ereignis-Identität-Prüfung gilt seit dieser Scheibe auch für den
  **Ortsvergleich** — `compare_radar_alert.py::_check_one_preset` und
  `compare_official_alert.py::_check_one_preset` rufen denselben,
  **unveränderten** Baustein (`check_event_identity_gate()`/
  `record_event_identity()`) an derselben Position im Ablauf wie die
  Trip-Pfade. Alle Aussagen des S4b-1-Nachtrags oben bleiben unverändert
  gültig; diese Scheibe fügt keine neue Kernlogik hinzu, sondern verdrahtet
  den bereits entitätsparametrisiert gebauten Baustein an zwei zusätzlichen
  Aufrufstellen. Zwei Compare-Eigenheiten: (1) die Registertrennung läuft über
  die Ort-Datei `f"{preset_id}:{loc_id}"`, `segment_ids` trägt trotzdem die
  Ortskennung (eine leere Segment-Menge erzeugt strukturell nie ein Match und
  wäre ein stiller No-Op); (2) ein amtlicher Alert kann mehrere Orte
  betreffen — er wird pro Ort geprüft und auf die verbleibende Orts-Teilmenge
  reduziert statt als Ganzes verworfen. Details:
  `docs/specs/modules/rework_1917_s4b2_compare_entdopplung.md`.
- **Nachtrag (Issue #2018, 2026-08-21):** die quellenübergreifende
  Ereignis-Identität-Prüfung kennt seit dieser Scheibe einen **dritten,
  GERICHTETEN und MENGENERHALTENDEN** Ausgang. `check_event_identity_gate()`
  entscheidet nicht mehr nur „zustellen / unterdrücken", sondern zusätzlich
  „**als Nachtrag zustellen**" — und das **ausschließlich** in der Richtung
  **amtliche Warnung zuerst, Radar-Nowcast danach UND MIT echter Eskalation**
  (`alert_urgency.exceeds`). Anlass war ein realer Fall: binnen 22 Minuten
  gingen zwei volle Gewitter-Alarme für dasselbe Segment raus, weil die
  V2-Eskalations-Ausnahme `HIGH` (Radar) und `MODERATE` (amtlich ORANGE) als
  zwei Punkte EINER Skala verglich, obwohl es zwei Skalen mit gleichen
  Etiketten sind. Die zweite Meldung wird deshalb nicht mehr als voller
  Zweit-Alarm, sondern als kurzer Nachtrag mit Bezug auf die vorige Meldung
  zugestellt („Ergänzung zur amtlichen Warnung von 16:15"). **Jede andere
  Konstellation bleibt exakt wie zuvor**: gleiche Quelle, die Gegenrichtung
  (Nowcast zuerst, amtlich danach — eigenständig über #1467 S4b freigegeben)
  sowie die **stillen** amtlich→Nowcast-Fälle ohne Eskalation und ohne
  V1-Abdeckungs-Ausnahme werden weiterhin **unterdrückt**; aus Stille wird nie
  ein Nachtrag. Harte Invariante dieser Scheibe: die **Menge** der zugestellten
  Meldungen ist vor und nach ihr identisch — es ändert sich allein die **Form**
  genau einer Meldungsart. Alle Aussagen der Nachträge zu #1467 S4b-1 und
  #1917 S4b-2 bleiben **unwiderrufen** gültig, insbesondere die Beschreibung
  des Registers (der Quellenvermerk `source` ist ein additives Feld in der
  bestehenden Nutzlast, kein neuer Präfix; Alt-Einträge ohne das Feld leiten
  ihre Quelle aus `point_at` ab) und der Ortsvergleich-Verdrahtung. Der
  **Ortsvergleich bleibt ausdrücklich unverändert**: die zwischenzeitlich
  erwogene Bedingung `allowed and not is_addendum` an den beiden
  Compare-Aufrufstellen wurde **zurückgenommen**, weil sie eine heute
  zugestellte Meldung unterdrückt und damit die Mengen-Invariante gebrochen
  hätte; Compare liest `is_addendum` schlicht nie. Kein neues
  Architekturprinzip — derselbe geteilte Baustein, nur mit einem dritten,
  eng umgrenzten Ausgang. Details:
  `docs/specs/modules/alert_nachtragsmeldung.md`.

- **Nachtrag (Issue #2065, 2026-08-22):** die feste Reihenfolge Ruhezeit →
  **Sperrzeit** → Tages-Obergrenze bekommt an genau EINER Stufe eine
  Ausnahme: eine **quantitativ deutliche Verschärfung überholt die
  Sperrzeit**. Anlass war ein gemessener Fall — ein Radar-Alarm über ~10 mm
  bucht 120 Minuten Sperre, 90 Minuten später schweigt eine auf ~27,5 mm
  verdreifachte Lage mit Protokollgrund `cooldown`. „Deutlich schlimmer" ist
  quantitativ definiert (`radar_overtakes_cooldown()`: Menge ≥ 2,0 × zuletzt
  gemeldete Menge UND ≥ 2,0 mm im 60-Minuten-Vergleichsfenster) und lebt
  **nicht** im geteilten Baustein: `check_nowcast_gate()` bleibt in Signatur
  UND Verhalten unverändert, den Vergleich führt allein der Trip-Zweig
  (`trip_alert.py::check_radar_alerts`) durch, nachdem das Gate `cooldown`
  gemeldet hat. **Ruhezeit und Tages-Obergrenze bleiben unbrechbar** — die
  Ruhezeit per PO-Entscheid (#1955), die Tages-Obergrenze wird im
  Durchbruchspfad ausdrücklich ERNEUT geprüft, weil die Kette bisher schon an
  der Sperrzeit kurzschloss. Weil die dreistufige Schwere-Skala bei 4 mm/h
  sättigt, reist dieselbe Mengen-Feststellung als optionales
  `quantitative_escalation` in `check_event_identity_gate()` mit; ohne diese
  zweite Hälfte wechselte nur der Protokollgrund von `cooldown` auf
  `event_duplicate` und der Alarm bliebe trotzdem aus. Der **Ortsvergleich
  bekommt diese Ausnahme NICHT**: er ist PO-seitig zurückgestellt, und die
  Ausnahme braucht eine Vergleichsbasis (die zuletzt gemeldete Menge im
  `ThrottleStore`), die im Ortsvergleich niemand schreibt. Genau deshalb liegt
  der Vergleich im Trip-Pfad statt im geteilten Gate — so bleibt
  `compare_radar_alert.py` unberührt, ohne Signatur-Passagiere und ohne toten
  Default. Eine spätere Übernahme in den Ortsvergleich wäre eine eigene,
  spezifizierte Entscheidung. Details:
  `docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md`.

- **Nachtrag (Issue #2050 S3b, 2026-08-23):** zwei Aussagen früherer Nachträge
  werden hier abgelöst.

  **(a) Der amtliche Pfad protokolliert.** Der Nachtrag zu #1467 S3 hielt fest,
  dass der Geltungsbereich der Unterdrückungs-**Protokollierung** strikt
  Nowcast-only bleibt und die Lücken O3 (Änderungsalarm) und E3 (amtliche
  Warnung) bewusst offen sind. Das gilt nicht mehr: **jede** Unterdrückung
  bekommt einen benannten Grund. Der **amtliche** Pfad protokolliert seither
  seine **Ruhezeit**- und seine **Tages-Obergrenzen**-Unterdrückung — in
  BEIDEN Flächen (`trip_alert.py::_send_official_alert_only`,
  `compare_official_alert.py::_check_one_preset`). Neues Verhalten war dort
  nicht nötig: `check_official_alert_gate()` liefert den passenden
  `GateResult.reason` seit #1467 S4a mit, der Aufrufer verwarf ihn nur. Ebenso
  protokolliert der **Vorhersage-Änderungsalarm** seine drei Stufen
  (Ruhezeit/Sperrzeit/Tages-Obergrenze) und der Trip-Radarzweig den
  **Doppel-Alarm-Guard** (#818) unter dem eigenen Grund `double_alert_guard` —
  er sitzt auf `AlertStateService`-Ebene, nicht auf dem Sperrzeit-Topf, und ist
  deshalb kein `cooldown`. **Bewusst weiterhin still bleibt allein der
  Briefing-Vorlauf** (#1233/ADR-0009, vier Stellen): dort wird die Meldung
  ersetzt, nicht verschluckt.

  **(b) Die Tages-Obergrenze bekommt eine Ausnahme.** Der Nachtrag zu #2065
  sagte, die Tages-Obergrenze bleibe unbrechbar. Sie bekommt jetzt — wie zuvor
  die Sperrzeit — genau EINE Ausnahme: eine **akute Eskalation der
  Dringlichkeitsstufe** bricht ein erschöpftes Tagesbudget. Die Bedingung ist
  UND-verknüpft: die Stufe dieses Abrufs übersteigt echt die höchste heute in
  dieser Zone bereits **zugestellte** Stufe (`alert_urgency.exceeds`, kein
  dritter Eskalationsbegriff), UND der Deckel von **einem Durchbruch je Tag und
  Zone** ist noch frei. Zustand dafür sind zwei additive Felder im Zonen-Eintrag
  von `alert_daily_count.json` (`max_urgency_sent`, `escalation_breakthroughs`),
  fortgeschrieben ausschließlich nach erfolgreicher Zustellung
  (F001-Symmetrie). Reichweite: **nur Nowcast/Radar**, dort aber in BEIDEN
  Flächen (Trip und Ortsvergleich). Struktur wie bei #2065:
  `check_nowcast_gate()` bleibt in Signatur UND Verhalten unverändert — die zur
  Entscheidung nötige Dringlichkeit entsteht erst aus dem Abruf, also nach dem
  Gate; entschieden wird deshalb Caller-seitig. Die **Reihenfolge Ruhezeit →
  Sperrzeit → Tages-Obergrenze bleibt unverändert**, und die **Ruhezeit bleibt
  unbrechbar** (PO-Ablehnung #1955). Beide Ausnahmen wirken unabhängig: ein Lauf
  kann an Sperrzeit UND Tagesbudget hängen und beide durchbrechen. Details:
  `docs/specs/modules/feat_2050_s3b_budget_und_unterdrueckungsgrund.md`.
