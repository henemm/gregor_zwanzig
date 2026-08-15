
# API Contract — Gregor Zwanzig

**Updated:** 2026-08-14 (Issue #1756 — Send-Idempotenz-Lock: `POST /api/trips/{trip_id}/send`
lehnt einen zweiten Sendeversuch für denselben `(user_id, trip_id, report_type)`-Schlüssel,
während ein erster noch läuft, jetzt mit neuem Statuscode 409 ab statt einen echten
Doppelversand auszulösen (Prozess-lokaler `threading.Lock`, keine Persistenz); Go-Proxy-Timeout
in `SendTripReportProxyHandler` von 120s auf 300s angehoben, da der reguläre Erfolgsfall durch
den vollständigen Mehrtages-Ausblick 3–4 Minuten dauern kann. Details Section 14.5, Spec
`docs/specs/modules/fix_1756_send_idempotenz_lock.md`); 2026-08-11 (Issue #1719 Scheibe S3, `fix-1719-s3-aus-ist-ein-zustand` — die
Live-Vorschau „So kommt es an" ist auf PO-Entscheid ersatzlos entfernt:
`WeatherV2MailPreview.svelte` (der einzige Live-Konsument des unten beschriebenen
`/api/_validator/sms-fidelity-preview`) ist gelöscht, ebenso `trip-detail/smsFidelityPreview.ts`.
Der Endpoint selbst bleibt registriert, ist damit aber **toter Code** — nicht Teil dieser
Scheibe, s. `docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md` „Known Limitations". Der
darunterstehende #923b-Eintrag beschreibt entsprechend nur noch den historischen Stand);
2026-08-06 (Issue #923b, `fix-923b-wire-live-sms-preview` — Korrektur zu #923:
der am selben Tag gebaute Endpoint `POST /api/_validator/sms-fidelity-preview` war korrekt,
aber gegen tote Komponenten verdrahtet (`ChannelFidelitySMS.svelte`, `ChannelPreviewCard.svelte`
— nie von einer Route importiert, nur über den Organisms-Barrel erreichbar). Live konsumiert
wurde der Endpoint ab #923b, über `WeatherV2MailPreview.svelte`
(`frontend/src/lib/components/shared/weather-metrics-tab/`, eingebunden in
`WeatherMetricsTab.svelte`), bei `context==='route'`. Bei `context==='vergleich'`
(Ortsvergleich-Editor) blieb die SMS-Kachel bewusst ausgeblendet — kein Aufruf. Die fünf toten
Komponenten wurden gelöscht. Spec: `docs/specs/modules/fix_923b_wire_live_sms_preview.md`);
2026-08-06 (Issue #1461 Scheibe S3b-2b, `feat-1461-s3b2b-compare-kanal-schwelle` —
`alert_channel_thresholds` (s. S3b-2a-Eintrag darunter) gilt jetzt auch für **Ortsvergleiche**:
dasselbe additive Geschwisterfeld (`AlertChannelThresholdsConfig`, kein neuer Typ) auf
`ComparePreset`, gleicher zweistufiger Datenverlustschutz (Objekt- **und** Feld-Ebene), gleiche
zwei Schreibwege (`PUT /api/compare/presets/{id}` und `PUT /api/briefings/{id}?kind=vergleich`).
Zusätzlich zwei Verhaltensänderungen: der Compare-Regenradar-Alarm ging bisher hart verdrahtet
nur per E-Mail raus (unabhängig vom Telegram-/SMS-Opt-in) — jetzt über denselben Kanal-Resolver
wie die anderen beiden Compare-Alarmwege. Und der `!`-Warn-Block-Filter des Compare-SMS-/
Telegram-**Berichts** (nicht der Alarm-Versand) geht von der festen `MIN_SMS_LEVEL`-Schwelle auf
die Startschwelle „gering" über (s. Abschnitt „alert_channel_thresholds" unten). Details ADR-0046,
Spec `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md`);
2026-08-06 (Issue #923, `fix-923-sms-fidelity-backend` — neuer zustandsloser
Endpoint `POST /api/_validator/sms-fidelity-preview` (Python-Core `api/routers/validator.py`)
hinter neuer Go-Proxy-Route (`internal/router/router.go`, `SmsFidelityPreviewProxyHandler` in
`internal/handler/proxy.go`): Browser → Go-API (`AuthMiddleware` greift, aber **kein**
`user_id`-Durchreichen an den Python-Core, da zustandslos/beispielwertbasiert wie
`alert-preview`/`compare-email-preview`) → Python-Core. Löst die Metrik-Editor-SMS-Vorschau
(`ChannelFidelitySMS.svelte`, `ChannelPreviewCard.svelte`) von einer hartcodierten
TypeScript-Simulation (`SMS_TOK`/`smsRender`) ab, analog zur bereits umgesetzten
Alert-Vorschau (#918, ADR-0011). Spec: `docs/specs/modules/fix_923_sms_fidelity_backend.md`); 2026-08-05 (Issue #1461
Scheibe S3b-2a, `feat-1461-s3b2-kanal-schwelle` — neues
additives Geschwisterfeld `alert_channel_thresholds` auf `Trip` (`AlertChannelThresholdsConfig`,
je Kanal `"LOW"`/`"MODERATE"`/`"HIGH"`, Startwert `"LOW"`): stellt je Alarm-Kanal (E-Mail ·
Telegram · SMS) ein, ab welcher Dringlichkeit eine ausgelöste Alarm-Meldung diesen Kanal
erreicht. Bewusst **neben** `alert_channels`, nicht darin — Top-Level-`nil`-Erbe **und**
Feld-Level-Merge innerhalb des Unterobjekts (fehlender Kanal-Key im PUT-Body bewahrt dessen
Bestandswert). Betraf zunächst ausschließlich **Trips**; der Ortsvergleich zog mit S3b-2b nach
(s. Eintrag darüber). Details Abschnitt „alert_channel_thresholds (Issue #1461 S3b-2a)“, ADR-0046,
Spec `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md`); 2026-08-04 (Issue #1461 Scheibe S3a, `feat-1461-s3a-kanal-dringlichkeit` — die
Antworten von `GET /api/cockpit/status` (Feld `alerts[]`) und `GET /api/archive/stats`
tragen je Alarm-Eintrag weiterhin ein Feld `severity` — **Form unverändert, Bedeutung
korrigiert:** `severity` wird jetzt aus den tatsächlich vorliegenden Werten **abgeleitet**
(`src/services/alert_urgency.py`) statt konstant gesetzt. Vorher schrieb Radar/Nowcast
immer `"HIGH"`, eine amtliche Warnung immer `"MODERATE"` — unabhängig vom Sachverhalt
(leichter Nieselregen in 19 Minuten stand als `HIGH` im Protokoll, eine rote amtliche
Unwetterwarnung als `MODERATE`). Amtliche Warnung: `OfficialAlert.level` über die
bestehende Abbildung `hazard_symbols.LEVEL_LETTERS` ({2:"L"→LOW, 3:"M"→MODERATE,
4:"H"→HIGH}, unbekannte Stufe konservativ → `HIGH`, nie leiser als die Wirklichkeit);
Radar: konvektiv oder starker Regen → `HIGH`, mäßiger Regen → `MODERATE`, leichter →
`LOW`; Vorhersage-Änderung bleibt inhaltlich unverändert (weiterhin über
`DeviationAlertEngine._highest_severity()`). Werden mehrere Quellen im selben Lauf in
einem Eintrag gebündelt (z.B. Δ-Änderung + amtliche Warnung, mehrere Orte im
Ortsvergleich), gewinnt die höchste beteiligte Dringlichkeit (`highest_urgency()`).
**Keine Versand-Wirkung:** kein Alarm wird anders gesendet, weder ob noch über welchen
Kanal noch wann; `AlertCountByTrip()` und die Cockpit-Kachel „Alarme · letzte 24h" zählen
unverändert nur `entries` (D4 aus #1459 bleibt gewahrt) — einzige nutzersichtbare Wirkung
ist die Farbe des Alarm-Punkts im Cockpit (`frontend/src/routes/+page.svelte:400-404`),
die jetzt zum tatsächlichen Sachverhalt passt statt dagegen. Spec:
`docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md`); 2026-08-04 (Issue #1457 S2c, `feat-1457-s2c-icon-eu-luekenfueller` — DWD ICON-EU (~6,5 km) schließt die Landkarte der Gewittersignal-Beschaffung: neuer Provider `DwdEuDirectProvider` (`src/providers/dwd_eu.py`, registriert als `eu_direct`) liefert Blitzpotenzial (`lpi_con_max`, extern verifiziert gegen `opendata.dwd.de`) für alle europäischen Orte, die weder Météo-France (FR/Korsika, S2a) noch ICON-D2 (DE/Alpen/Österreich, S2b) abdecken. **Kein neues Feld** — `lightning_potential_lpi_jkg` wird jetzt aus zwei Quellen befüllt (ICON-D2 für DE/Alpen/AT, ICON-EU für den Rest), unterscheidbar über die Position, nicht über das Feld. Neue Catch-all-Zeile `EU_REST` (first-match-wins, letzte Zeile) in `providers/thunder_routing.py`. **Kein Hagel-Signal bei ICON-EU** — `hail_potential_grau_gsp` bleibt für Rest-Europa dauerhaft `None`, beabsichtigt. Fehlwert-Behandlung unterscheidet sich von ICON-D2: ICON-EU trägt **keinen** festen Sentinel (9999.0 gilt dort nicht), stattdessen wird die Fehlwert-Markierung der GRIB2-Antwort selbst geprüft. `thunder_enrichment.py` und `models.py` unverändert — nutzt die bestehende S2b-Struktur (Signal-Key `"lpi"`) direkt weiter. Damit ist #1457 (Konzept #1419 Schritt S2) vollständig. Spec: `docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md`);; 2026-08-04 (Issue #1474, Folge-Scheibe `fix-1474-gewitterschwelle-cockpit` — zwei
Lücken geschlossen, die die vorherige Scheibe bewusst offen ließ: **(1)** Drei Stellen
beantworteten bisher getrennt, ab welcher Gewitter-**Stärke** gemeldet wird (SMS-Kürzel `TH:`
folgte der pro Trip einstellbaren `MetricConfig.sms_threshold`, Mail-Trend-Block und
Mail-Prosa-Satz „Gewitter ab HH:00" hingen fest an `1.0` bzw. `ThunderLevel.MED`) — alle drei
lesen jetzt dieselbe Erwähnungsschwelle; Standard bleibt `1.0` („ab leicht"), SMS/Trend-Block
bit-identisch, der Prosa-Satz meldet künftig schon ab „leicht" statt erst ab „mittel". Toter,
seit #795 nie gelesener Parameter `thresholds` (befüllt mit `mc.alert_threshold`, ADR-0043-fremde
Achse) an `_pill_for_metric()`/`build_metrics_summary_pills()` entfernt, ersetzt durch
`sms_mention_thresholds` (aus `mc.sms_threshold`). **(2)** `GET
/api/_internal/trips/{trip_id}/stages-weather` (Section 23): das `risk`-Feld unterscheidet jetzt
„kein Risiko erkannt" (weiterhin `green`) von „mindestens ein Risiko, auch nur Stufe leicht"
(neu `yellow`, vorher fälschlich ebenfalls `green` — `get_max_risk_level()`s eigener
`RiskLevel.LOW`-Fallback bei leerer Risikoliste verdeckte den Unterschied). `MODERATE`/`HIGH`
bleiben unverändert `yellow`/`red`. **Bewusst keine vierte Farbe** — weiterhin nur
`green`/`yellow`/`red`/`null`, kein API-Vertragsbruch. Frontend (`WeatherMetricsTab.svelte`)
bekommt zusätzlich korrekte Beschriftung der Gewitter-Schwellen-Knöpfe: `Leicht→1.0` /
`Mittel→2.0` / `Hoch→3.0` statt der seit der #1474-Ordinalverschiebung falschen `MED→1.0` /
`HIGH→2.0` (Bestandsdaten unberührt, Zuordnung läuft über den Zahlenwert). Offener Restpunkt:
im Alarm-Editor ist dieselbe Beschriftung weiterhin verschoben — Issue #1488 (geteilte
Wortquelle für Trip, Vergleich und Alarme). Spec:
`docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md`);; 2026-08-03 (Issue #1457 S2b, `feat-1457-s2b-dwd-alpen` — DWD ICON-D2 liefert ab sofort **Blitzpotenzial** (`lpi`, J/kg) und **Hagel-Potenzial** (`grau_gsp`, Akkumulation) für Deutschland/Alpen/Österreich. Zwei neue optionale Felder auf `ForecastDataPoint`: `lightning_potential_lpi_jkg` und `hail_potential_grau_gsp` (jeweils Optional[float]). **Bewusst getrennt von S2a** (Météo-France Blitzdichte): DWD liefert ein Potenzial (Energiegröße in J/kg, Messwerte ~88), Météo-France eine Dichte (Blitze je Fläche/3h, Messwerte ~0,1–0,2) — verschiedene Größen, verschiedene Skalen. Befüllung über `providers/dwd.py::fetch_thunder_signals_named()`, angehängt im gemeinsamen Weg `providers/thunder_enrichment.py` analog S2a. Zuständigkeitstabelle `providers/thunder_routing.py` erweitert um Eintrag `DE_ALPEN`. Hagel-Akkumulation gegenüber dem Nullpunkt-Lauf gerechnet (Anker-Abruf). Fehlwert-Marker empirisch ermittelt: **9999.0** (NICHT −999.0). `None` heißt **„keine Aussage"**, nie „kein Signal". **Keine Stufenbildung/Ausgabe-Wirkung** in dieser Scheibe — reine Rohdaten. Spec: `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md`); 2026-08-03 (Issue #1474, `860a3baf` — die Gewitter-**Stärke** `ThunderLevel` wird vierstufig: `LOW` („leicht") besetzt den seit jeher unerreichbaren Token-Platz `L` (`tokens/metrics.LEVELS`); `MED`/`HIGH` behalten Name und Bedeutung, die Render-Skala wird nur **additiv** ergänzt (`{NONE:0, LOW:1, MED:2, HIGH:3}`). Gespeist wird die neue Stufe aus **mehreren** Signalen statt aus einem einzigen Wettercode: Blitzdichte (Météo-France, FR/Korsika) und Gewitterenergie CAPE (überall). Schwellen sind publiziert, nicht gesetzt: Blitzdichte `>0,003` / `>=0,015` aus dem ECMWF Forecast User Guide 8.1.13, CAPE `>=1000 J/kg` aus `risk_thresholds["cape"]["medium"]`. **CAPE deckelt bei „leicht"** und eskaliert nie — es misst verfügbare Energie, kein Ereignis. Neue reine Funktion `output/metric_format.thunder_level_from_signals()` fusioniert je Signal mit **eigener** Schwellentabelle („schärfstes vorhandenes Signal gewinnt", über `max_thunder()`); der DWD-Blitzpotenzial-Pfad (#1457 S2b) dockt dort mit **einer** Tabellenzeile an. Angeschlossen im gemeinsamen Weg `providers/thunder_enrichment.py`. `None` heißt weiterhin **„keine Aussage"**, `NONE` heißt „geprüft, unauffällig" — `_parse_thunder_level(None)` liefert jetzt korrekt `None` statt `NONE`. 🔴 **Die Ordinalskala verschiebt sich** (MED 1→2, HIGH 2→3): `ORDINAL_LEVEL_BOUNDS` (`alert_preset.py`) trägt deshalb jetzt **benannte** `ThunderLevel`-Tupel statt roher Zahlen — ohne diese Umstellung würde die Nutzereinstellung „standard" still schon bei „mittel" alarmieren statt erst bei „hoch". Über vier Adversary-Runden kamen **neun** lokale Kopien derselben Zuordnung ans Licht, drei davon mit Absturz (`trip_report_scheduler.py:1536` KeyError im Briefing-Versand, `trip_command_processor.py:810/904` ValueError bei Telegram `/glance` bzw. Tagesleiste) und drei mit falscher Aussage (u.a. „leicht" → „Starkes Gewitter erwartet"); alle behoben, durchgängig über die geteilten Funktionen. Wächter gegen die zehnte: #1480. Nutzersichtbar: Gewitterstufen heißen jetzt durchgängig deutsch (kein/leicht/mittel/hoch) aus **einer** geteilten Wortquelle `THUNDER_LABEL_DE` statt fünf Kopien — vorher zeigte dieselbe Nachricht teils „mittel", teils „MED". Bestandsdaten unberührt: alle gespeicherten Gewitterwerte sind Namen, keine Ordinalzahlen. Details `docs/specs/modules/feat_1474_gewitter_befund_stufen.md`); 2026-08-03 (Issue #1457 S2a **Fix**, `c33e7b28` — die Blitzdichte wurde beim echten Dienst unter einem Namen abgefragt, den es dort nicht gibt: `LITOTA3` kommt in `GetCapabilities` **0-mal** vor, korrekt ist die ausgeschriebene Form `AVERAGE_LIGHTNING_STRIKE_DENSITY_OVER_3HOURS__GROUND_OR_WATER_SURFACE`. Zusätzlich war der Sicherheitsabstand zur Wahl des GRIB-Laufs mit 3 h zu knapp — der errechnete Lauf war noch nicht veröffentlicht (live: um 09:27Z war der jüngste fertige Lauf 6,5 h alt). **Jeder** Abruf endete damit in 404, lautlos, weil fail-soft korrekt griff; das Feld blieb in Produktion dauerhaft leer. Behoben: Coverage-Konstante korrigiert, **eigener** Sicherheitsabstand `THUNDER_RUN_SAFETY_HOURS=6` nur für die Lauf-Wahl (der Nullpunkt der Stunden-Offsets bleibt der 3-h-Lauf der Grundvorhersage — ein global erhöhter Abstand hätte die Blitzdichte still gegen die Grundvorhersage verschoben), Rückfall auf bis zu zwei ältere Läufe bei 404. Neuer Live-Test `tests/tdd/test_thunder_coverage_name_live.py` prüft den **im Produktivcode stehenden** Namen und den ermittelten Lauf gegen `GetCapabilities` — fängt künftige Umbenennungen, auch für S2b/S2c. **Lehre:** die Kurznamen aus der Konzept-Tabelle in #1419 (`lpi`, `grau_gsp`, `cape_ml`, `DIAG_GRELE`) sind **keine** Abrufnamen; vor jeder Umsetzung gegen `GetCapabilities` des Zielsystems prüfen. Verifiziert in Produktion: 24 Datenpunkte mit Wert statt vorher 0); 2026-08-03 (Issue #1467 Scheibe S1 — Alarm-Protokoll trägt EINE Kennung: `AlertLogEntry` hat statt `trip_id`/`preset_id` jetzt `entity_id` + `entity_type` (`"trip"` | `"compare"`); `trip_id` bleibt nur als optionales Altfeld für Bestandsdateien (`omitempty`). Betrifft die Antworten von `GET /api/cockpit/status` (Feld `alerts[]`) und `GET /api/archive/stats`, dessen `alerts`-Map jetzt nach `"<typ>:<kennung>"` schlüsselt statt nach blosser Tour-Kennung — vorher landeten ALLE Vergleichs-Alarme gemeinsam unter dem leeren Schlüssel `""`. `briefings` bleibt unverändert nach Tour-Kennung geschlüsselt. Bestandsdateien werden NICHT migriert; Go leitet fehlende Felder beim Lesen ab (`entity_id := trip_id`, `entity_type := "trip"`). Spec: `docs/specs/modules/rework_1467_s1_alarm_kennung.md`); 2026-08-02 (Issue #1457 S2a, nachgetragen AC-7…AC-12 — `ForecastDataPoint` bekommt ein neues optionales Feld `lightning_density_per_km2_3h` (Météo-France `LITOTA3`, erwartete Blitzdichte je km² und 3h); befüllt über den **gemeinsamen**, regulären Anreicherungsweg (`providers/thunder_enrichment.py`, hängt im Normalpfad von `OpenMeteoProvider.fetch_forecast`, nicht nur im Totalausfall-Fall), gesteuert über eine **eigene** Zuständigkeitstabelle `providers/thunder_routing.py` (getrennt von `region_routing.py` — Gewitter-Zuständigkeit ist größenabhängig, s. ADR-0041-Muster) und das optionale Protokoll `ThunderSignalProvider` (`providers/base.py`); heute nur `fr_direct` eingetragen. Sammelabruf über mehrere Orte im selben Fenster geht über einen geteilten Zwischenspeicher `providers/thunder_window_cache.py` (Kachelgitter, TTL 600s, Deckel 48 Einträge/32 MiB) — Grund ist das Météo-France-Rate-Limit von 100 Anfragen/Minute pro Konto (s. `docs/reference/decision_matrix.md`). Orte außerhalb des geladenen Fensters bekommen `None`, nicht den Randwert eines fremden Ortes. **Bewusst eigenes Feld** — NICHT zusammengelegt mit dem DWD-Blitzpotenzial: Météo-France liefert eine **Dichte** (Blitze je Fläche/3h, Messwerte ~0,1–0,2), DWD ein **Potenzial** (Energiegröße in J/kg, Messwerte ~88) — verschiedene Größen, verschiedene Skalen. `None` heißt **„keine Aussage"**, nie „kein Gewitter". Details `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md`); 2026-07-31 (Issue #1435 Etappe E1a-1 — Alarmfähigkeit wird eine Eigenschaft des zentralen Wetter-Namensregisters (`src/app/metric_catalog.py`): neue Felder `alert_metrics`/`change_alert_metric` auf `MetricDefinition`, neuer Resolver `alert_metric_for(metric_id, aggregation)`. `GET /api/metrics` liefert je Auswertung `alert_metric` und je Größe `change_alert_metric` (`null`, wenn keine Alarm-Identität existiert); `GET /api/compare/metrics` liefert an allen 26 Einträgen zusätzlich `alertMetric` (`null` möglich) — `alarmCapable` ist ab jetzt dessen Boolean-Sicht (`alertMetric is not None`) statt einer zweiten, handgepflegten Liste. `compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` bleibt das tatsächlich alarmauslösende Modul, unverändert; die Menge bleibt identisch dieselben 10 Compare-Keys — verhaltensneutral. Luftfeuchtigkeit bleibt bewusst unregistriert (Auswertungskette kennt sie nicht, Epic #1374 Invariante 1). Details `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md`); (Issue #1395 S6 — Nebenlaeufigkeitsschutz jetzt auch fuer Orts-Vergleiche: ETag an GET/PUT auf /api/compare/presets/{id} UND am Umgehungsweg /api/briefings/{id}?kind=vergleich, If-Match-Pruefung an beiden Schreibwegen, geteilte Sperre/Fingerabdruck verhindert dass der eine Weg den anderen umgeht. Details im Abschnitt „Nebenlaeufigkeit"); 2026-07-27 (Issue #1361 Befund 2 + #1368, S3 Scheibe A von Epic #1372 — 3-Tages-Ausblick der Vergleichs-Mail konfigurierbar: neues `display_config.outlook_metrics` (Neuformat, kein viertes Vokabular) wählt aus allen 24 Katalog-Größen mit Tagesauswertung statt der bisherigen festen sieben; neues `ComparePreset.OutlookEnabled *bool` (`json:"outlook_enabled,omitempty"`) schließt die Lücke, in der der Wert bei PUT über die Go-API still verloren ging. Trip-Mail byte-identisch, ADR-0037); 2026-07-27 (Issue #1395 — Nebenlaeufigkeitsschutz fuer Touren: `ETag` an `GET`/`PUT`, `If-Match`-Pruefung an `PUT /api/trips/{id}` und `PUT /api/trips/{id}/weather-config`, neuer Statuscode `412`; fehlender Header wird angenommen. Kein Schemafeld, keine Migration — der Stempel ist ein Fingerabdruck der Rohdatei. Betrifft nur Touren, nicht Orte und noch nicht Orts-Vergleiche. Details im Abschnitt „Nebenlaeufigkeit" unter den weather-config-Endpunkten, ADR-0036); 2026-07-22 (Issue #1342 — Drift-Sanierung: Trip/Stage/Waypoint/ComparePreset-DTOs auf Struct-Wahrheit, Auth-Fehler-Bodies auf Code-Wortlaut, vollständiges Endpunkt-Inventar Sektion 0.5, Routing-Verweise auf internal/router/router.go; abgesichert durch tests/test_api_contract_drift.py); 2026-07-16 (Issue #1278 + #1285 — Vergleichs-Mail-Kurzzusammenfassung je Ort (geteilter Trip-Baustein) + fünf reparierte, bisher still verworfene Tages-Aggregate; `LocationResult` bekommt 5 additive optionale Felder (`precip_sum_mm`/`thunder_level_max`/`visibility_min_m`/`uv_index_max`/`pop_max_pct`), keine Persistenz/kein Wire-Format betroffen; Details s. Changelog-Abschnitt unten); 2026-07-16 (Issue #1270 — neuer Endpoint `POST /api/preview/compare/{preset_id}`: EIN Aufruf liefert `{subject, email_html, telegram, sms, sms_char_count}` aus einem einzigen `ComparisonEngine.run()`, ADR-0011-Muster (Erweiterung `alert-preview`), bewusste Abweichung von der älteren Trip-Preview-Routenform je Kanal; neuer `ComparePreviewService`; Compare-Briefing-Versand wird ab jetzt tatsächlich auch über Telegram/SMS zugestellt (`NotificationService.send_compare_report`), nicht mehr nur E-Mail — der Alarm-Pfad (`compare_alert.py`/`compare_radar_alert.py`) bleibt unverändert E-Mail-only. Details Section 20 und `docs/specs/modules/compare_channel_preview_dispatch.md`); 2026-07-16 (Issue #1250 S7b — ComparePreset-Persistenz per-Datei briefings/{id}.json (kind="vergleich"), Store-Muster wie Trip-Store; Alt-compare_presets.json nur Migrations-Quelle/Rollback; load_compare_presets partial-tolerant; kind-scoped Migrations-Refresh migrate_1250_briefings.py --kind vergleich); 2026-07-15 (Issue #1258 S1 — `official_warnings {enabled, sources?}` neu auf Trip UND ComparePreset, löst `official_alert_triggers_enabled` funktional ab (jetzt deprecated, bleibt in den Daten); idempotente Migration `internal/store/migrate_1258.go`/`scripts/migrate_1258_official_warnings.py` übernimmt Ist-Verhalten des Bestands unverändert, Neuanlage-Default `enabled=false`; PUT-RMW mit Feld-Level-Preserve für `sources`; Legacy-Fallback bei fehlendem/leerem Feld — Details Section 10.5); 2026-06-13 (Issue #795 — Metriken-Überblick-Pills: Inhalt analog SMS (ausgeschrieben, gleiche Schwellen), Farbe via Ampel-System #759 (🟢🟡🟠🔴 = HTML-Vollfarb-Kapsel + weißer Text WCAG-AA, Plain = 4 Emojis, Compact = ASCII-Schwerezeichen); Bug #775 — Trip-Shortcode-Routing für Inbound-E-Mail-Replies: RFC-2047-Dekodierung, toleranter Whitespace↔Underscore-Lookup, neuer GZ#-Shortcode-Key als primärer Routing-Identifier, persistiert als `Trip.shortcode`; Issue #764 — ComparePreset forecast_hours Persistierung: neues Feld im Go-Modell/TS-Type (24|48|72 h), Hydration im Editor, Konsum im Python-Scheduler, Legacy-Default 48 h; Horizont-Select im Editor auf Design-System Select.svelte umgestellt); 2026-06-11 (Issue #747 — Datierter Forecast-Snapshot-Speicher: WeatherSnapshotService erweitert um `save_dated(trip_id, target_date, segments)`, `load_dated(trip_id, target_date)` und `_prune_dated_snapshots(trip_id)`. Speichert Snapshots nach Datum (`{trip_id}_{YYYY-MM-DD}.json`, max. 7 Dateien pro Trip, mtime-sortiert). Fundament für Vortag-Vergleich im Trip-Briefing. Bestehende `save()`/`load()`-Methoden für Alert-Pfad bleiben byte-identisch. Scheduler ruft `save_dated()` nach bestehendem `save()` auf. Siehe Issue #747.); 2026-06-11 (Issue #731 — Abruf-zentrierte Befehle: bare Keywords (HEUTE/MORGEN/JETZT/GEWITTER/RUHETAG/STATUS/STOP/WEITER/HILFE) ersetzen alte Abonnenten-Befehle (PAUSE/SKIP/CONFIG). Persistenzfelder paused_until/skip_next bleiben für Bestandsdaten erhalten. TripCommandProcessor.process() neu mit _resume_trip() für WEITER-Befehl. Keine Datenstruktur-Änderungen. Siehe Issue #731.); 2026-06-10 (Issue #715 — Wettermetriken-Darstellung: GET /api/metrics filtert auf `selectable=true` — `confidence` (Vorhersage-Verlässlichkeit/Ensemble) ist KEINE pro-Etappe wählbare Metrik mehr, nur noch Vorhersage-Hinweis + SMS-Symbol; Vorschau-Emojis in WeatherV2MailPreview + Step3Weather angepasst; Beispieldaten eindeutig gekennzeichnet; Bug #716 — Test-Briefing: stiller Versagensfall weg. POST /api/trips/{id}/send gibt jetzt HTTP 422 + detail-Feld zurück wenn keine Etappendaten für Zieldatum vorhanden (statt HTTP 200). Frontend zeigt konkrete Fehlermeldung im Toast; Issue #707 — Trip-Datum-Overwrite-Bug: PUT `/api/trips/{id}` mit minimalem Body (nur geänderte Felder) statt kompletter `trip`-Spread — verhindert stale-data-Überschreibung von Etappen; Issue #690 — Eigene Wetter-Metriken-Profile: eindeutiger Name (HTTP 409 name_exists, 400 name_required), Profil sofort aktiv + persistent, "Eigene"-Markierung in Preset-Leiste, trip-übergreifend pro Nutzer); 2026-06-09 (Issue #674 — Fahrradtour als Aktivitätstyp: 3 neue ActivityType-Varianten (fahrrad_15/20/25 km/h) mit korrekten Naismith-Raten (600/1000 Hm/h); #680 — Compare-Editor Slice 3 Fidelity: display_config.active_metrics — ausgewählte Metriken pro Vergleich; #675 — Etappen-Startzeiten editierbar; #671 — Bot-Menü automatisch beim Service-Start; #638 — Alerts-Tab Karten-Modell, Severity-Falle, pro-Alert Kanäle; #664 — Metriken-Überblick-Pille; #621 — E-Mail-Elemente abschaltbar); 2026-06-08 (Issues #672/#671 — Telegram E2E-Pipeline-Tests + Bot-Menü-Vertrag; #642 — User-Anzeigename display_name; #655 — Telegram Hybrid-Navigation: callback_query + editMessageText); 2026-06-07 (Issues #627/#631 — Compare-Preset Sofortversand + Wochen-Rhythmus-Erhalt)

## 0) Konventionen
- Zeit: ISO-8601 UTC (`Z`)
- Einheiten im Feldnamen: `*_c`, `*_kmh`, `*_mmph`, `*_mm`, `*_pct`, `*_hpa`, `*_jkg`, `*_m`, `*_cm`
- Provider (Ist-Stand, s. `docs/reference/decision_matrix.md`): `openmeteo` (Standard) | `geosphere` | `brightsky` | `at_direct`/`de_direct`/`fr_direct` (Fallback) — `radar_dpc` seit #1648 ersatzlos entfernt

---

## 0.5) Endpunkt-Inventar (vollständig, generiert aus `internal/router/router.go`)

> Stand 2026-07-22 (#1342). Dieses Inventar listet JEDE registrierte Go-Route.
> Der Drift-Test `tests/test_api_contract_drift.py` erzwingt: neue Route im
> Router ⇒ Zeile hier, sonst rot. Detail-Sektionen weiter unten decken nicht
> jede Route ab — das Inventar ist die Vollständigkeits-Garantie.

| Pfad | Methoden |
|------|----------|
| `/api/_internal/trip/{id}/loaded` | GET |
| `/api/_validator/compare-email-preview` | POST |
| `/api/_validator/detector-thresholds` | GET |
| `/api/_validator/format-metric` | GET |
| `/api/_validator/metrics-for-channel` | GET |
| `/api/_validator/sms-fidelity-preview` | POST |
| `/api/archive/stats` | GET |
| `/api/auth/account` | DELETE |
| `/api/auth/forgot-password` | POST |
| `/api/auth/google/callback` | GET |
| `/api/auth/google/init` | GET |
| `/api/auth/login` | POST |
| `/api/auth/logout` | POST |
| `/api/auth/magic-link` | POST |
| `/api/auth/magic-link/verify` | POST |
| `/api/auth/passkey/credentials/{id}` | DELETE |
| `/api/auth/passkey/discoverable/begin` | POST |
| `/api/auth/passkey/discoverable/finish` | POST |
| `/api/auth/passkey/login/begin` | POST |
| `/api/auth/passkey/login/finish` | POST |
| `/api/auth/passkey/register/begin` | POST |
| `/api/auth/passkey/register/finish` | POST |
| `/api/auth/passkey/register/public/begin` | POST |
| `/api/auth/passkey/register/public/finish` | POST |
| `/api/auth/password` | PUT |
| `/api/auth/profile` | GET, PUT |
| `/api/auth/register` | POST |
| `/api/auth/reset-password` | POST |
| `/api/auth/telegram-link` | GET |
| `/api/auth/telegram-status` | GET |
| `/api/auth/tier-change-request` | POST |
| `/api/auth/verify-email` | POST |
| `/api/briefings` | GET, POST |
| `/api/briefings/{id}` | DELETE, GET, PUT |
| `/api/cockpit/status` | GET |
| `/api/compare` | GET |
| `/api/compare/metrics` | GET |
| `/api/compare/presets` | GET, POST |
| `/api/compare/presets/{id}` | DELETE, GET, PUT |
| `/api/compare/presets/{id}/send` | POST |
| `/api/compare/presets/{id}/state` | PATCH |
| `/api/config` | GET |
| `/api/debug/trigger-radar-alert` | POST |
| `/api/forecast` | GET |
| `/api/gpx/parse` | POST |
| `/api/groups` | GET, POST |
| `/api/groups/{id}` | DELETE, PATCH |
| `/api/health` | GET |
| `/api/internal/telegram-connect` | POST |
| `/api/locations` | GET, POST |
| `/api/locations/resolve` | POST |
| `/api/locations/{id}` | DELETE, GET, PATCH, PUT |
| `/api/locations/{id}/weather-config` | GET, PUT |
| `/api/metric-presets` | GET, POST |
| `/api/metric-presets/{id}` | DELETE, PATCH |
| `/api/metrics` | GET |
| `/api/notify/test` | POST |
| `/api/preview/compare/{preset_id}` | POST |
| `/api/preview/{trip_id}/email` | GET |
| `/api/preview/{trip_id}/signal` | GET | — **tote Route** (Python-Core kennt Signal nicht mehr, #610; Abbau → Sammel-Issue #1199)
| `/api/preview/{trip_id}/sms` | GET |
| `/api/preview/{trip_id}/telegram` | GET |
| `/api/scheduler/alert-checks` | POST |
| `/api/scheduler/inbound-commands` | POST |
| `/api/scheduler/status` | GET |
| `/api/scheduler/trip-reports` | POST |
| `/api/sms-symbols` | GET |
| `/api/templates` | GET |
| `/api/trips` | GET, POST |
| `/api/trips/{id}` | DELETE, GET, PUT |
| `/api/trips/{id}/alert-preview` | POST |
| `/api/trips/{id}/briefing-history` | GET |
| `/api/trips/{id}/send` | POST |
| `/api/trips/{id}/stages/weather` | GET |
| `/api/trips/{id}/state` | PATCH |
| `/api/trips/{id}/waypoints/{waypointId}/confirm` | PATCH |
| `/api/trips/{id}/weather-config` | GET, PUT |
| `/api/webhooks/telegram/{secret}` | POST |

(76 Pfade, 96 Routen-Registrierungen.)

---

## 1) Provider Adapter
### Input
- `coords: (lat, lon)`
- `start: datetime`
- `end: datetime`

### Output
Ein **Normalized Forecast Timeseries**-Objekt (siehe unten), bestehend aus `meta` + `data[]`.

---

## 2) Normalized Forecast Timeseries

### Beispiel
```json
{
  "meta": {
    "provider": "openmeteo",
    "model": "ECMWF",
    "run": "2025-08-29T06:00Z",
    "grid_res_km": 9,
    "interp": "point_grid",
    "stations_used": [
      {"id": "10091", "name": "Fehmarn", "dist_km": 20.3, "elev_diff_m": 40}
    ]
  },
  "data": [
    {
      "ts": "2025-08-29T12:00Z",
      "t2m_c": 18.5,
      "wind10m_kmh": 22.0,
      "gust_kmh": 38.0,
      "precip_rate_mmph": 0.4,
      "precip_1h_mm": 0.4,
      "cloud_total_pct": 85,
      "symbol": "lightrain",
      "thunder_level": "MED",
      "cape_jkg": 950,
      "pop_pct": null,
      "pressure_msl_hpa": 1013,
      "humidity_pct": 78,
      "dewpoint_c": 17.0
    }
  ]
}
```

### Feldliste (Datenpunkte)

#### Basis-Felder (immer)
| Feld               | Typ              | Beschreibung                                   |
|--------------------|-----------------|------------------------------------------------|
| ts                 | datetime        | Zeitpunkt (UTC ISO-8601). Hausnorm: **naive UTC** — aware Eingaben werden bei Konstruktion nach UTC konvertiert und das tzinfo entfernt (`ForecastDataPoint.__post_init__`, #1345) |
| t2m_c              | float           | 2 m-Temperatur [°C]                            |
| wind10m_kmh        | float           | 10 m-Windgeschwindigkeit [km/h]                |
| gust_kmh           | float           | Böenspitze [km/h]                              |
| precip_rate_mmph   | float           | Niederschlagsrate [mm/h] zum Zeitpunkt         |
| precip_1h_mm       | float           | 1-h-Akkumulation [mm]                          |
| cloud_total_pct    | integer (0–100) | Gesamtbewölkung [%]                            |
| symbol             | enum            | Normalisiertes Symbol (siehe SYMBOL_MAPPING)   |
| thunder_level      | enum            | Gewitter-**Stärke** {NONE, LOW, MED, HIGH} — seit #1474 vierstufig |
| cape_jkg           | float           | CAPE [J/kg]                                    |
| pop_pct            | integer (0–100) | Niederschlagswahrscheinlichkeit [%]            |
| pressure_msl_hpa   | float           | Bodendruck [hPa]                               |
| humidity_pct       | integer (0–100) | Luftfeuchtigkeit [%]                           |
| dewpoint_c         | float           | Taupunkt [°C]                                  |

#### Wintersport-Felder (optional, null wenn nicht verfuegbar)
| Feld               | Typ              | Beschreibung                                   |
|--------------------|-----------------|------------------------------------------------|
| snow_depth_cm      | float           | Gesamtschneehoehe [cm]                         |
| snow_new_24h_cm    | float           | Neuschnee letzte 24h [cm]                      |
| snow_new_acc_cm    | float           | Neuschnee akkumuliert seit Forecast-Start [cm] |
| snowfall_limit_m   | integer         | Schneefallgrenze [m]                           |
| swe_kgm2           | float           | Schneewasseraequivalent [kg/m²]                |
| precip_type        | enum            | Niederschlagstyp {RAIN, SNOW, MIXED, FREEZING_RAIN, null} |
| freezing_level_m   | integer         | Nullgradgrenze [m]                             |
| wind_chill_c       | float           | Gefuehlte Temperatur [°C]                      |
| visibility_m       | integer         | Sichtweite [m]                                 |

#### Zusätzliche Felder (optional, aus Issue #497)
| Feld               | Typ              | Beschreibung                                   |
|--------------------|-----------------|------------------------------------------------|
| cloud_low_pct      | integer (0–100) | Tiefwolken-Anteil [%]                          |
| pop_pct            | integer (0–100) | Niederschlagswahrscheinlichkeit [%] (Duplikat deprecated — siehe pop_pct Basis-Feld) |
| wind_dir_deg       | integer (0–359) | Windrichtung [Grad]                            |

#### Gewitter-Zusatzfeld Météo-France (optional, Issue #1457 S2a)
| Feld                          | Typ           | Beschreibung                                   |
|-------------------------------|---------------|-------------------------------------------------|
| lightning_density_per_km2_3h  | float \| None | Erwartete Blitzdichte [Blitze/km²/3h], Météo-France AROME, Coverage `AVERAGE_LIGHTNING_STRIKE_DENSITY_OVER_3HOURS__GROUND_OR_WATER_SURFACE` (Konstante `providers.meteofrance.LIGHTNING_COVERAGE`; die Kurzform `LITOTA3` existiert beim Dienst **nicht** — sie war bis `c33e7b28` eingetragen und ließ jeden Abruf lautlos in 404 laufen, s. #1457). Der GRIB-Lauf wird mit **eigenem** Sicherheitsabstand von 6 h gewählt (`THUNDER_RUN_SAFETY_HOURS`) und fällt bei 404 auf bis zu zwei ältere Läufe zurück; der Nullpunkt der Stunden-Offsets bleibt der 3-h-Lauf der Grundvorhersage, sonst driftete die Blitzdichte-Zeitachse gegen sie. Befüllt über den **gemeinsamen** Anreicherungsweg `providers/thunder_enrichment.py::enrich_thunder`, der im regulären Rückgabeweg von `OpenMeteoProvider.fetch_forecast` hängt (nicht nur bei Totalausfall der Hauptquelle) — kennt keinen Providernamen, sondern schlägt die zuständige Quelle in der **eigenen** Zuständigkeitstabelle `providers/thunder_routing.py` nach (getrennt von der Grundvorhersage-Tabelle `providers/region_routing.py`, weil die Zuständigkeit **größenabhängig** ist, s. `docs/reference/decision_matrix.md`) und ruft sie über das optionale Protokoll `ThunderSignalProvider` (`providers/base.py`). Heute trägt nur `fr_direct` (Frankreich/Korsika) diese Tabelle ein; ein zweiter Dienst wird wirksam, indem er das Protokoll erfüllt und eine Zeile in `thunder_routing.py` bekommt — ohne dass diese Anreicherungsstelle angefasst wird. Orte außerhalb des geladenen Abfragefensters bekommen `None` (verworfen), nicht den Randwert eines fremden Ortes. **Bewusst eigenes Feld** — NICHT zusammengelegt mit dem DWD-Blitzpotenzial (`cape_jkg`/`thunder_level`): Météo-France liefert eine **Dichte** (Blitze je Fläche/3h, Messwerte ~0,1–0,2), DWD ein **Potenzial** (Energiegröße in J/kg, Messwerte ~88) — verschiedene Größen, verschiedene Skalen, ein gemeinsames Feld mit einer Schwelle wäre ein stiller Fehler. `None` heißt **„keine Aussage"**, nie „kein Gewitter". |
| thunder_probability_pct  | integer \| None | **Vorbereitet, in dieser Scheibe von keiner Quelle befüllt** (#1474). Gewitter-**Wahrscheinlichkeit** 0–100 % — die zweite, von der Stärke unabhängige Achse (PO-Vorgabe 2026-08-03: *Der bisherige Wert beschreibt die Stärke*). `None` heißt **keine Aussage**, nie 0 %. Kein Dienst liefert sie fertig: Météo-France AROME führt 46 Größen, alle physikalisch, keine Wahrscheinlichkeit. Ableitbar allein aus dem Open-Meteo-Ensemble (Anteil der 40 Modellläufe mit Gewitter — gemessen 2026-08-02 am GR20: 19 von 40 = 47 %). Befüllung braucht den Wettercode je Lauf im Ensemble-Abruf, der heute nur Temperatur und Niederschlag anfordert (`openmeteo.py`, `/v1/ensemble`) — erhöht das Kontingent (#1329), deshalb eigener Schritt: Konzept #1419 S6. **Kein Renderer-Anschluss**, das Feld erscheint in keiner Ausgabe, solange es leer ist. |

#### Gewitter-Zusatzfelder DWD (optional, Issue #1457 S2b + S2c)
| Feld                          | Typ           | Beschreibung                                   |
|-------------------------------|---------------|-------------------------------------------------|
| lightning_potential_lpi_jkg   | float \| None | DWD-Blitzpotenzial (`lpi`, J/kg) — **zwei Quellen, ein Feld**: für Deutschland/Alpen/Österreich liefert ICON-D2 (2,2 km, S2b, Messwerte typisch ~88, Fehlwert-Marker 9999.0 empirisch ermittelt), für den Rest Europas liefert ICON-EU (~6,5 km, S2c, externer Abrufname `lpi_con_max`, live gegen `opendata.dwd.de` verifiziert). ICON-EU kennt **keinen** festen Fehlwert-Sentinel — dort wird stattdessen die Fehlwert-Markierung der GRIB2-Antwort selbst geprüft (`dataset.nodata`/NaN). Welcher der beiden Dienste einen konkreten Wert geliefert hat, steht **nicht im Feld selbst**, sondern ist im Regelfall über die Position rekonstruierbar (`providers/thunder_routing.py::thunder_provider_for` → `de_direct` oder `eu_direct`) — fachlich dieselbe Energiegröße, deshalb bewusst kein zweites Feld. **Seit #1492 Scheibe 2a / ADR-0047 gilt diese Rückrechnung nicht mehr uneingeschränkt:** fällt die zuständige Quelle wirklich aus, liefert eine benannte Vertretung (`de_direct → eu_direct`, `fr_direct → eu_direct`); die Position nennt dann nur noch den *Zuständigen*, nicht den tatsächlichen *Lieferanten*. Maßgeblich ist ab dann `ForecastMeta.fallback_model` / `fallback_reason` (`"thunder_source_unavailable"`) / `fallback_metrics` — wobei `fallback_model` einen bereits vorhandenen Grundvorhersage-Fallback (#1115) nicht überschreibt (Merge-Schutz), der Gewitter-Wechsel also unter Umständen **nur** in `fallback_metrics` steht. ⚠️ Bei Vertretung von `fr_direct` wechselt zudem die Messgröße: statt der Blitz**dichte** (`lightning_density_per_km2_3h`, Météo-France) wird das Blitz**potenzial** dieses Feldes befüllt — verschiedene Skalen, deshalb schreibt die Vertretung strukturell in das Feld der Ersatzquelle und nie in das der Primärquelle. Befüllt über den gemeinsamen Anreicherungsweg `providers/thunder_enrichment.py::enrich_thunder`, angehängt im regulären Rückgabeweg von `OpenMeteoProvider.fetch_forecast`. Zuständigkeitstabelle `providers/thunder_routing.py::thunder_provider_for` trägt seit S2b den Eintrag `DE_ALPEN` (43.17–58.09 N / −3.95–20.35 O) → `de_direct`, seit S2c zusätzlich die Catch-all-Zeile `EU_REST` (ganze Welt, first-match-wins **letzte** Zeile) → `eu_direct`. **Bewusst getrennt von S2a** (Météo-France Blitzdichte): DWD liefert ein **Potenzial** (Energiegröße), Météo-France eine **Dichte** (Blitze je Fläche/3h) — verschiedene Größen, verschiedene Skalen, ein gemeinsames Feld mit einer Schwelle wäre ein stiller Fehler. `None` heißt **„keine Aussage"**, nie „kein Signal". **Seit #1474c viertes Signal in der Gewitterstufen-Fusion** (`thunder_level_from_signals()`, `output/metric_format.py`) — **seit #1679 gebietsabhängige** Schwellentabelle (`model_registry.LPI_THRESHOLDS_JKG`/`lpi_thresholds_jkg()`, s. `docs/reference/decision_matrix.md`): DE_ALPEN (ICON-D2, `de_direct`) unter 1 J/kg → `NONE`, 1 bis unter 30 → `LOW`, 30 bis unter 50 → `MED`, ab 50 → `HIGH` (alle drei Werte belegt, Bína et al., Atmospheric Research/ASR Copernicus 2022); EU_REST (ICON-EU, `eu_direct`) bleibt als Interim **unverändert** bei unter 5 → `NONE`, 5 bis unter 20 → `LOW`, 20 bis unter 50 → `MED`, ab 50 → `HIGH` (5/50 belegt, 20 interpoliert), bis #1678 eine eigene Eichung liefert. Beide Gebiete befüllen dasselbe Feld, aber über getrennte Schwellen. |
| hail_potential_grau_gsp       | float \| None | DWD ICON-D2 Hagel-Potenzial (`grau_gsp`, Graupel-Akkumulation) für Deutschland/Alpen/Österreich. Akkumulation gegenüber dem Nullpunkt-Lauf gerechnet (Anker-Abruf wie `precip_1h_mm` / `tot_prec`-Muster). Fehlwert-Marker 9999.0. Befüllung analog `lightning_potential_lpi_jkg`, über `de_direct` → `thunder_enrichment.py`. **Bleibt für ICON-EU-Gebiete (S2c, `eu_direct`) dauerhaft `None`** — ICON-EU liefert kein Hagel-Pendant zu `grau_gsp`, beabsichtigt, keine offene Lücke. **Reine Rohdaten**, kein Anschluss an Renderer und **keine Stufenbildung** — anders als `lightning_potential_lpi_jkg` (s. dort) bleibt Hagel außen vor, das ist S5/#1475. `None` heißt **„keine Aussage"**. |

#### Gewitter-Rohgrößen DWD (optional, Issue #1531)
Sieben zusätzliche DWD-Größen, reiner Datenabruf — **keine Einstufung, keine Schwellen, kein
Renderer-Anschluss** (Scope-Abgrenzung der Spec `docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md`).
Fehlwert-Marker 9999.0 (außerhalb Modellgebiet) wird bei allen sieben zu `None`.

| Feld                              | Typ           | Beschreibung                                   |
|------------------------------------|---------------|-------------------------------------------------|
| supercell_index_sdi2_1s           | float \| None | Superzellenindex (`sdi_2`, 1/s) — nur ICON-D2 (DE/Alpen/AT), **vorzeichenbehaftet** (antizyklonale Rotation bleibt negativ im Feld). |
| convective_inhibition_jkg         | float \| None | Konvektionshemmung (`cin_ml`, J/kg) — ICON-D2 **und** ICON-EU. **Zweiter** Fehlwert-Marker −999,9 (ICON-D2, ca. 46 % der Gitterpunkte) wird zusätzlich zu 9999,0 zu `None`. |
| cape_ml_jkg                       | float \| None | Mixed-Layer-CAPE (`cape_ml`, J/kg) — ICON-D2 **und** ICON-EU, **eigenes** Feld getrennt von `cape_jkg` (andere Quelle, #1419 §3.1/§5: je Größe ein eigenes Feld). |
| lightning_potential_max_lpi_jkg   | float \| None | Blitzpotenzial-Maximum (`lpi_max`, J/kg) — nur ICON-D2 (ICON-EU liefert stattdessen `lpi_con_max` in `lightning_potential_lpi_jkg`, s. o.). |
| updraft_helicity_max_m2s2         | float \| None | Updraft-Helizität, Gesamtsäule (`uh_max`, m²/s²) — nur ICON-D2. |
| updraft_helicity_max_med_m2s2     | float \| None | Updraft-Helizität, mittlere Schicht (`uh_max_med`, m²/s²) — nur ICON-D2. |
| updraft_helicity_max_low_m2s2     | float \| None | Updraft-Helizität, untere Schicht (`uh_max_low`, m²/s²) — nur ICON-D2. |

Alle drei `uh_max*`-Varianten werden bewusst parallel geholt, weil die DWD-Felddefinition der
Schichtgrenzen nicht auffindbar ist (s. Spec „Known Limitations"). ICON-EU liefert außerdem
`cape_con` providerintern (`src/providers/dwd_eu.py`), aber **ohne** eigenes Modellfeld —
kein Zwilling zu `cape_ml_jkg`.

### Provenance (Meta, Pflicht)
- `provider`, `model`, `run`, `interp`, `grid_res_km`, optional `stations_used[]`

---

## 3) Risk Engine
### Input
- Liste von Forecast Timeseries
- Konfiguration mit Schwellenwerten (z. B. `max_wind_kmh = 50`, `thunder_level = HIGH`)

### Output
```json
{
  "risks": [
    { "type": "thunderstorm", "level": "high", "from": "14:00Z" },
    { "type": "rain", "level": "moderate", "amount_mm": 12 }
  ]
}
```

---

## 4) Report Formatter
### Input
- Forecast DTOs
- Risk Output
- DebugBuffer

### Output (String)
```
Abendbericht: Morgen 25°C, leichter Wind (22 km/h), Regenwahrscheinlichkeit 20%.
Risiko: Gewitter ab 14:00 Uhr wahrscheinlich.
```

**Debug-Block**: wird 1:1 aus `DebugBuffer.email_subset()` übernommen und an E-Mail angehängt; die Console zeigt zusätzlich die vollständige Debug-Ausgabe.

---

## 5) Thunder Logic (Ultra-MVP)
- **MOSMIX**: `ww ∈ {95,96,99} ⇒ HIGH`; elif `CAPE ≥ 800 ⇒ MED`; else `NONE`
- **MET**: `symbol_code` enthält `"thunder"` ⇒ HIGH, sonst NONE
- **NOWCASTMIX**: `nowcast_thunder == true` ⇒ HIGH, sonst NONE

---

## 6) Avalanche Report (Separates DTO)

Lawinenlagebericht als eigenstaendiges Datenobjekt (nicht Teil von NormalizedTimeseries).

### Beispiel
```json
{
  "meta": {
    "provider": "EUREGIO",
    "region_id": "AT-07",
    "region_name": "Tirol",
    "valid_from": "2025-12-27T17:00Z",
    "valid_to": "2025-12-28T17:00Z",
    "published": "2025-12-27T16:00Z"
  },
  "danger": {
    "level": 3,
    "level_text": "erheblich",
    "elevation_above_m": 2000,
    "level_below": 2,
    "trend": "steady"
  },
  "problems": [
    {
      "type": "wind_slab",
      "aspects": ["N", "NE", "E", "NW"],
      "elevation_from_m": 2000,
      "elevation_to_m": 3000
    }
  ],
  "snowpack": {
    "structure": "moderate",
    "description": "Die Schneedecke ist maessig verfestigt..."
  }
}
```

### Feldliste

#### Meta
| Feld          | Typ      | Beschreibung                          |
|---------------|----------|---------------------------------------|
| provider      | enum     | SLF, EUREGIO, ZAMG                    |
| region_id     | string   | Regions-ID (z.B. "AT-07")             |
| region_name   | string   | Regionsname (z.B. "Tirol")            |
| valid_from    | datetime | Gueltigkeit Start                     |
| valid_to      | datetime | Gueltigkeit Ende                      |
| published     | datetime | Veroeffentlichungszeitpunkt           |

#### Danger
| Feld             | Typ     | Beschreibung                                |
|------------------|---------|---------------------------------------------|
| level            | int 1-5 | Europaeische Lawinengefahrenskala           |
| level_text       | string  | gering/maessig/erheblich/gross/sehr gross   |
| elevation_above_m| integer | Hoehengrenze (Stufe gilt oberhalb)          |
| level_below      | int 1-5 | Stufe unterhalb der Hoehengrenze (optional) |
| trend            | enum    | increasing, steady, decreasing              |

#### Problems (Array)
| Feld             | Typ      | Beschreibung                             |
|------------------|----------|------------------------------------------|
| type             | enum     | new_snow, wind_slab, persistent_weak, wet_snow, gliding_snow |
| aspects          | string[] | Expositionen (N, NE, E, SE, S, SW, W, NW) |
| elevation_from_m | integer  | Untergrenze                              |
| elevation_to_m   | integer  | Obergrenze                               |

---

## 7) Erweiterte Risk Engine

### Neue Risiko-Typen (Wintersport)
```json
{
  "risks": [
    {"type": "thunderstorm", "level": "high", "from": "14:00Z"},
    {"type": "rain", "level": "moderate", "amount_mm": 12},
    {"type": "avalanche", "level": "high", "danger_level": 4, "problems": ["wind_slab"]},
    {"type": "snowfall", "level": "moderate", "amount_cm": 30, "from": "18:00Z"},
    {"type": "wind_chill", "level": "high", "feels_like_c": -25},
    {"type": "poor_visibility", "level": "moderate", "visibility_m": 50}
  ]
}
```

### Schwellenwerte (konfigurierbar)
| Risiko         | LOW       | MODERATE    | HIGH      |
|----------------|-----------|-------------|-----------|
| avalanche      | Stufe 1-2 | Stufe 3     | Stufe 4-5 |
| snowfall (24h) | <10 cm    | 10-30 cm    | >30 cm    |
| wind_chill     | >-10°C    | -10 bis -20°C| <-20°C   |
| visibility     | >200 m    | 50-200 m    | <50 m     |
| gust           | <50 km/h  | 50-80 km/h  | >80 km/h  |

---

## 8) GPX Trip Planning (Story 1, 2, 3)

### Story 1: GPX Upload & Segment-Planung

#### GPXTrack
| Feld                 | Typ                   | Beschreibung                              |
|----------------------|-----------------------|-------------------------------------------|
| points               | list[GPXPoint]        | Track-Points (Koordinaten + Elevation)     |
| waypoints            | list[GPXWaypoint]     | Optional Waypoints (Gipfel, Hütten)        |
| total_distance_km    | float                 | Gesamt-Distanz der Route [km]              |
| total_ascent_m       | float                 | Gesamt-Aufstieg [m]                        |
| total_descent_m      | float                 | Gesamt-Abstieg [m]                         |

#### GPXPoint
| Feld                    | Typ            | Beschreibung                               |
|-------------------------|----------------|--------------------------------------------|
| lat                     | float          | Breitengrad                                 |
| lon                     | float          | Längengrad                                  |
| elevation_m             | float \| None  | Höhe über Meer [m]                          |
| distance_from_start_km  | float          | Kumulative Distanz vom Start [km]           |

#### GPXWaypoint
| Feld         | Typ            | Beschreibung                  |
|--------------|----------------|-------------------------------|
| name         | str            | Name des Wegpunkts             |
| lat          | float          | Breitengrad                    |
| lon          | float          | Längengrad                     |
| elevation_m  | float \| None  | Höhe über Meer [m]             |

#### DetectedWaypoint
| Feld         | Typ               | Beschreibung                                     |
|--------------|-------------------|--------------------------------------------------|
| type         | WaypointType      | GIPFEL, TAL, PASS                                 |
| point        | GPXPoint          | Koordinaten + Elevation                           |
| prominence_m | float             | Höhen-Prominenz [m]                               |
| name         | str \| None       | Optional aus GPX-Waypoint                         |

#### TripSegment
| Feld         | Typ       | Beschreibung                                     |
|--------------|-----------|--------------------------------------------------|
| segment_id   | int       | Segment-Nummer (1-basiert)                        |
| start_point  | GPXPoint  | Start-Koordinaten + Elevation                     |
| end_point    | GPXPoint  | End-Koordinaten + Elevation                       |
| start_time   | datetime  | Start-Zeit (berechnet)                            |
| end_time     | datetime  | End-Zeit (berechnet)                              |
| duration_hours | float   | Segment-Dauer [h]                                 |
| distance_km  | float     | Segment-Distanz [km]                              |
| ascent_m     | float     | Segment-Aufstieg [m]                              |
| descent_m    | float     | Segment-Abstieg [m]                               |
| adjusted_to_waypoint | bool | Hybrid-Segmentierung angewendet?            |
| waypoint     | DetectedWaypoint \| None | Wegpunkt (falls angepasst)        |

#### EtappenConfig
| Feld               | Typ      | Beschreibung                                |
|--------------------|----------|---------------------------------------------|
| gpx_file           | str      | Pfad zur GPX-Datei                           |
| start_time         | datetime | Start-Zeit der Etappe                        |
| speed_flat_kmh     | float    | Gehgeschwindigkeit Ebene [km/h] (z.B. 4.0)   |
| speed_ascent_mh    | float    | Steig-Geschwindigkeit [Hm/h] (z.B. 300)      |
| speed_descent_mh   | float    | Abstiegs-Geschwindigkeit [Hm/h] (z.B. 500)   |

---

### Story 2: Wetter-Engine für Trip-Segmente

#### SegmentWeatherData
| Feld        | Typ                      | Beschreibung                               |
|-------------|--------------------------|--------------------------------------------|
| segment     | TripSegment              | Segment aus Story 1                        |
| timeseries  | NormalizedTimeseries \| None | Volle stündliche Wetterdaten (None bei Fehler) |
| aggregated  | SegmentWeatherSummary    | Aggregierte Werte (MIN/MAX/AVG)            |
| fetched_at  | datetime                 | Zeitpunkt des API-Abrufs                   |
| provider    | str                      | Verwendeter Provider (GEOSPHERE, etc.)     |
| has_error   | bool                     | True wenn Provider-Fehler nach Retry-Exhaustion (WEATHER-04) |
| error_message | str \| None            | Fehlernachricht bei has_error=True (WEATHER-04) |

#### SegmentWeatherSummary
| Feld                  | Typ                  | Beschreibung                                    |
|-----------------------|----------------------|-------------------------------------------------|
| temp_min_c            | float \| None        | Minimale Temperatur im Segment [°C]              |
| temp_max_c            | float \| None        | Maximale Temperatur im Segment [°C]              |
| temp_avg_c            | float \| None        | Durchschnittstemperatur [°C]                     |
| wind_max_kmh          | float \| None        | Maximale Windgeschwindigkeit [km/h]              |
| gust_max_kmh          | float \| None        | Maximale Böengeschwindigkeit [km/h]              |
| precip_sum_mm         | float \| None        | Gesamt-Niederschlag [mm]                         |
| cloud_avg_pct         | int \| None          | Durchschnittliche Bewölkung [%]                  |
| cloud_low_avg_pct     | int \| None          | Durchschnittliche tiefe Bewölkung [%] (#1392)    |
| cloud_mid_avg_pct     | int \| None          | Durchschnittliche mittelhohe Bewölkung [%] (#1392) |
| cloud_high_avg_pct    | int \| None          | Durchschnittliche hohe Bewölkung [%] (#1392)     |
| humidity_avg_pct      | int \| None          | Durchschnittliche Luftfeuchtigkeit [%]           |
| thunder_level_max     | ThunderLevel \| None | Maximale Gewitter-**Stärke** (NONE, LOW, MED, HIGH — seit #1474 vierstufig) |
| visibility_min_m      | int \| None          | Minimale Sichtweite [m]                          |
| dewpoint_avg_c        | float \| None        | Durchschnittlicher Taupunkt [°C]                 |
| pressure_avg_hpa      | float \| None        | Durchschnittlicher Luftdruck [hPa]               |
| wind_chill_min_c      | float \| None        | Minimale gefühlte Temperatur [°C]                |
| snow_depth_cm         | float \| None        | Schneehöhe [cm] (optional, Winter)               |
| freezing_level_m      | int \| None          | Nullgradgrenze [m] (optional, Winter)            |
| snowfall_limit_m      | int \| None          | Schneefallgrenze [m] — MIN über das Segment (#1391) |
| aggregation_config    | dict[str, str]       | Metadata: Aggregations-Funktionen pro Metrik     |

#### SegmentWeatherCache
| Feld        | Typ                  | Beschreibung                         |
|-------------|----------------------|--------------------------------------|
| segment_id  | str                  | Eindeutige Segment-ID                 |
| data        | SegmentWeatherData   | Gecachte Wetterdaten                  |
| fetched_at  | datetime             | Zeitpunkt des Cache-Eintrags          |
| ttl_seconds | int                  | Time-to-Live [s] (default: 3600)      |

#### WeatherChange
| Feld        | Typ               | Beschreibung                                      |
|-------------|-------------------|----------------------------------------------------|
| metric      | str               | Metrik-Name (z.B. "temperature", "wind")           |
| old_value   | float             | Alter Wert                                         |
| new_value   | float             | Neuer Wert                                         |
| delta       | float             | Absolute Änderung                                  |
| threshold   | float             | Konfigurierbarer Schwellenwert                     |
| severity    | str               | "minor", "moderate", "major"                       |
| direction   | str               | "increase", "decrease"                             |
| segment_id  | str               | ID der Etappe, in der die Änderung erkannt wurde (z.B. "1", "2", "Ziel"); Default `""`, wird vom Detector befüllt (Issue #131). |
| occurred_at | datetime \| None  | Zeitpunkt des auslösenden Spitzenwerts, UTC-aware; `None` wenn nicht bestimmbar (Best-effort). Die Formatierung in die Ortszeit passiert erst in der Projektionsschicht (`output/renderers/alert/project.py`), nicht beim Erzeugen dieses DTOs (Issue #1386). |

#### TripWeatherConfig
| Feld            | Typ           | Beschreibung                                |
|-----------------|---------------|---------------------------------------------|
| trip_id         | str           | Trip-Identifier                              |
| enabled_metrics | list[str]     | Ausgewählte Metriken (Subset von 13)         |
| updated_at      | datetime      | Zeitpunkt der letzten Änderung               |

---

### Story 3: Trip-Reports (Email/SMS)

#### TripReport
| Feld           | Typ                      | Beschreibung                                    |
|----------------|--------------------------|-------------------------------------------------|
| trip_id        | str                      | Trip-Identifier                                  |
| trip_name      | str                      | Trip-Name (für Subject/Anzeige)                  |
| report_type    | str                      | "morning", "evening", "alert"                    |
| generated_at   | datetime                 | Generierungszeitpunkt                            |
| segments       | list[SegmentWeatherData] | Alle Segmente mit Wetterdaten (Story 2)          |
| email_subject  | str                      | E-Mail Subject-Zeile                             |
| email_html     | str                      | HTML-Version des Reports                         |
| email_plain    | str                      | Plain-Text-Version des Reports                   |
| sms_text       | str \| None              | SMS-Text (≤160 chars)                            |
| triggered_by   | str \| None              | "schedule" oder "change_detection"               |
| changes        | list[WeatherChange]      | Liste der Änderungen (bei Alert)                 |

#### TripReportConfig
| Feld                            | Typ         | Beschreibung                                          |
|---------------------------------|-------------|-------------------------------------------------------|
| trip_id                         | str         | Trip-Identifier                                        |
| enabled                         | bool        | Reports aktiv? (default: true)                         |
| morning_time                    | time        | Morgen-Report Zeit (default: 07:00)                    |
| evening_time                    | time        | Abend-Report Zeit (default: 18:00)                     |
| timezone                        | str         | Zeitzone (default: "Europe/Vienna")                    |
| send_email                      | bool        | E-Mail senden? (default: true)                         |
| send_sms                        | bool        | SMS senden? (default: false)                           |
| send_premium_sms                | bool        | Premium-SMS (Garmin inReach) senden? (default: false, Issue #1676 S2a) — eigenständiger vierter Kanal `premium_sms`, **nur Trip-Briefing** (Alarmpfad/Ortsvergleich erst mit #1701, s. ADR-0049); Empfänger ist ausschließlich die in Scheibe S1 gelernte Rückadresse aus `user.json`, nie `sms_to`. Seit #1717 S3 auch in der Oberfläche schaltbar (Trip-Anlage + Trip-Detail) und als abgeleitetes Go-Struct-Feld `Trip.SendPremiumSms` vorhanden — `report_config.send_premium_sms` bleibt die autoritative Quelle. |
| alert_on_changes                | bool        | Alerts bei Änderungen? (default: true)                 |
| change_threshold_temp_c         | float       | Temp-Änderungs-Schwelle [°C] (default: 5.0)            |
| change_threshold_wind_kmh       | float       | Wind-Änderungs-Schwelle [km/h] (default: 20.0)         |
| change_threshold_precip_mm      | float       | Niederschlags-Schwelle [mm] (default: 10.0)            |
| include_metrics                 | list[str]   | Anzuzeigende Metriken (default: 5 Basis-Metriken)      |
| wind_exposition_min_elevation_m | float/null  | Wind-Exposition Höhen-Schwelle [m]; null = 1500m (F7c)|
| show_stage_stats                | bool        | Etappen-Kennzahlen-Raster anzeigen? (default: true, Issue #621) |
| show_quick_take_tags            | bool        | Quick-Take-Chips in HTML anzeigen? (default: true, Issue #621) |
| show_stability                  | bool        | Großwetterlage-Label anzeigen? (default: true, Issue #621) |
| show_highlights                 | bool        | Highlights/Zusammenfassung anzeigen? (default: true, Issue #621) |
| daily_summary_metrics           | list[str]   | Metriken in der Tages-Summe (default: `["precipitation","wind","visibility","thunder"]`, Issue #621) |
| show_metrics_summary            | bool        | Optionaler Metriken-Überblick am Beginn (default: false, Issue #664/795) — wenn true: farbige Pillen pro konfigurierter Metrik mit SMS-identischen Erwähnungsschwellen. **Pill-Inhalts-Format (Issue #795):** Ereignis-Metriken (wind/gust/precip/pop/thunder/visibility/humidity) zeigen „<Label> ab HH:00 · Spitze <X> um HH:00" (oder ruhige Form unter Schwelle); Bereichs-Metriken (temp/wind_chill/cloud/freezing_level/dewpoint/uv/sunshine) zeigen „<Label> min–max <Einheit>" ohne Uhrzeit. **Pill-Farbe (Issue #759/#795):** EIN Ampel-System (🟢🟡🟠🔴) pro Spitzenwert via `display_thresholds` + `ampel_dot`-Logik; HTML = WCAG-AA-Vollfarb-Kapsel (weißer Text ≥4.5:1); Plain = dieselben 4 Emojis wie die Stundentabelle; Compact (7bit/ASCII) = ASCII-Schwerezeichen (grün→kein, gelb→`!`, orange→`!!`, rot→`!!!`). Ersetzt Quick-Take und blendet Tages-Summe aus. |
| show_outlook                    | bool        | Ausblick-Block anzeigen? (default: true, Issue #721) — verschmilzt Großwetterlage (Kopf) + Tabelle der nächsten Etappen mit Uhrzeiten und Vorhersage-Sicherheit (`confidence_pct` pro Etappe). Gilt für HTML **und** Plain-Text. `false` blendet den gesamten Block aus (Großwetterlage zusätzlich an `show_stability` gekoppelt). |
| email_format                    | str         | E-Mail-Format-Schalter (default: `"full"`): `"full"` = multipart-HTML mit Stundentabellen (unverändert); `"compact"` = reine text/plain-Mail, nur ASCII, ohne HTML, mit fix Kopf + Metriken-Überblick + Ausblick + Footer, ~95% kleiner. Baustein-Toggles greifen bei compact NICHT. Siehe Issue #722. |
| show_yesterday_comparison       | bool        | Vortag-Vergleich-Sektion in E-Mail anzeigen? (default: true, Issues #750 #752) — wenn true und Vortag-Snapshot vorhanden: zeigt Delta-Tabelle in HTML und Plain; fehlender Snapshot führt zu sanftem Überspringen (kein Fehler). Der Toggle wirkt einheitlich auf beide Kanäle: `format_email` nullt `day_comparison` bei `false`, sodass auch die Vortag-Zeile in der Telegram-Kurzübersicht-Bubble (`render_telegram_bubbles()`, Issue #1001) entfällt. |
| day_window_start_hour           | int \| null | Start des konfigurierbaren Tagesfensters für SMS/Kurzzusammenfassung/Metriken-Pillen/Telegram-Fußzeile (default/null: 4, Epic #1319 Scheibe B). Ungültige Werte (außerhalb 0–23, `start >= end`) werden beim Laden still auf `null` zurückgesetzt. |
| day_window_end_hour             | int \| null | Ende des konfigurierbaren Tagesfensters, inklusive (default/null: 19, Epic #1319 Scheibe B). Dieselbe Klemmung wie `day_window_start_hour`; `compute_has_gap()` nutzt dasselbe Fenster (keine Divergenz zwischen Anzeige und Gap-Erkennung). |
| updated_at                      | datetime    | Zeitpunkt der letzten Config-Änderung                  |

#### MetricConfig (Issue #435, erweitert Issue #624)
| Feld                | Typ              | Beschreibung                                          |
|---------------------|------------------|-------------------------------------------------------|
| metric_id           | str              | Metrik-ID (z.B. `wind`, `cloud_total`, `sunshine`)     |
| enabled             | bool             | Metrik aktiv im Report? (default: true)                |
| aggregations        | list[str]        | Aggregations-Funktionen pro Segment (default: `["min","max"]`). **Seit Issue #1357, 2026-07-28 bis 2026-08-14** vom Renderer gelesen: bestimmt, welche Tagesauswertung in der Kachelzeile der Briefing-Mail erscheint. **Einzelwahl, keine Menge** (PO 2026-07-28: „Es gibt kein zusätzlich: entweder oder") — genau eine von vier sich ausschließenden Möglichkeiten galt: Spanne (`["min","max"]`), nur Tiefstwert (`["min"]`), nur Höchstwert (`["max"]`), nur Mittelwert (`["avg"]`, nur bei Größen mit `avg` im Katalog, z. B. Temperatur — bei der gefühlten Temperatur entfiel diese Möglichkeit). Fehlt das Feld ⇒ Katalog-Vorgabe (`metric_catalog.pill_default_aggregations()`, `{min,max}` ∩ berechenbar); leere Liste `[]` ⇒ bewusst keine Kachel; eine gespeicherte Liste ohne Entsprechung in den vier Möglichkeiten (Altbestand, z. B. `["min","avg"]`) wurde zur Anzeigezeit auf die nächstliegende Möglichkeit abgebildet und per `logger.warning` gemeldet — Ausnahme: der Katalog-Schreib-Default `["min","max","avg"]` bildete ohne Meldung auf Spanne ab. Bedienfläche (Segmented Control) nur für Größen mit mehr als einer berechenbaren Auswertung (heute Temperatur und gefühlte Temperatur); Details `docs/specs/modules/trip_aggregation_selection.md`.<br>**Korrektur 2026-08-15 (Issue #1728 Scheibe 1):** Dieser Wirkmechanismus auf die Kachelzeile ist entfallen — alle drei E-Mail-Pillen-Wirkorte (HTML/Plain/Compact) zeigen für „Temperatur"/„Gefühlte Temperatur" jetzt **unbedingt** die Spanne (`min`/`max`), unabhängig vom gespeicherten Wert dieses Felds; `mc.aggregations` wird an keinem dieser drei Wirkorte mehr gelesen. Das Feld selbst bleibt im Modell bestehen und `GET /api/metrics` liefert weiterhin `metrics[].aggregations` (s. oben) — nur die hier beschriebene **Wirkung** entfällt. Sichtbarkeit von `K`/`D`/`FK`/`FD` in der SMS hängt seit derselben Scheibe an vier eigenen Katalog-Größen (`temperature_day_low`/`temperature_day_high`/`wind_chill_day_low`/`wind_chill_day_high`), nicht mehr an diesem Feld — s. `docs/reference/sms_format.md` v2.27. Der Trip-Editor zeigt bis Scheibe 2 weiterhin die (jetzt wirkungslose) Auswertungswahl an — bewusste Übergangslücke. Details: `docs/specs/modules/feat_1728_s1_temp_aufloesung.md` |
| morning_enabled     | bool \| None     | Override Morgen-Report (None = globale Einstellung)    |
| evening_enabled     | bool \| None     | Override Abend-Report (None = globale Einstellung)     |
| use_friendly_format | bool             | @deprecated (seit Issue #435) — nutze `format_mode`    |
| format_mode         | str \| None      | Format-Modus: `"raw"` \| `"scale"` \| `"simplified"` \| `"symbol"`. None = Katalog-Default |
| alert_enabled       | bool             | Alert bei Änderung dieser Metrik? (default: false)     |
| alert_threshold     | float \| None    | Schwellenwert für Alert (z.B. 5.0 für Temperatur)      |
| horizons            | dict \| None     | Pro-Metrik-Zeithorizont-Filter (None = alle sichtbar)  |
| bucket              | str              | Spalten-Gruppierung: `"primary"` (eigene Spalte) \| `"secondary"` (Detail-Zeile), default: `"primary"` |
| order               | int              | Sortier-Reihenfolge innerhalb des Buckets (default: 0) |
| sms_threshold       | float \| None    | **Neu Issue #624:** Schwellenwert für SMS-/Telegram-Kurzform (R/PR/W/G). None = Catalog/DEFAULTS-Fallback. Nur für threshold-fähige Metriken sichtbar (Niederschlag, Regenwahrscheinlichkeit, Wind, Böen) |

**Format Mode Details:**
- `raw`: Numerischer Wert mit Einheit (z.B. `18.5°C`, `22 km/h`)
- `scale`: Kategorisierte Skala (z.B. `wind_direction` → `N`, `NE`, `E`, ...)
- `simplified`: Adjektiv-Kürzel ohne Zahl (z.B. `wind: schwach`, `precip: mäßig`)
- `symbol`: Emoji-Darstellung (z.B. `cloud_total: ☁️`, `sunshine: ☀️`)

**Backward Compatibility:**
- Bestandsdaten mit nur `use_friendly_format: bool` werden beim Laden automatisch auf `format_mode` gemappt
- Schreib-Pfade persistieren beide Felder parallel: `format_mode="symbol"` → `use_friendly_format=true`; `format_mode="raw"` → `use_friendly_format=false`

---

---

## 9) GPX Proxy Endpoint (M5a)

### POST /api/gpx/parse

Leitet GPX-Upload vom SvelteKit-Frontend via Go-Proxy an Python FastAPI weiter. Die Python-Seite ruft `gpx_to_stage_data()` auf und gibt Stage-Daten mit Waypoints zurueck.

**Pfad:** Go (:8090) → Python FastAPI (:8000), beide unter `/api/gpx/parse`

#### Request

- Content-Type: `multipart/form-data`
- Body field `file`: GPX-Datei (`.gpx`)
- Query-Param `stage_date` (optional): `YYYY-MM-DD`
- Query-Param `start_hour` (optional): Integer 0–23, default `8`

#### Response 200

```json
{
  "name": "Tag 1: von Valldemossa nach Deià",
  "date": "2026-04-14",
  "waypoints": [
    {
      "id": "G1",
      "name": "Puig des Teix",
      "lat": 39.752,
      "lon": 2.785,
      "elevation_m": 1064,
      "time_window": "08:00-10:00"
    }
  ]
}
```

#### Error Responses

| Status | Body | Szenario |
|--------|------|----------|
| 400 | `{"error":"invalid_gpx","detail":"..."}` | Kein `file`-Field oder GPX nicht parsebar |
| 503 | `{"error":"core_unavailable"}` | Python-Backend nicht erreichbar oder Timeout (>30s) |

#### Source Files

| Datei | Aenderung |
|-------|-----------|
| `api/routers/gpx.py` | NEU — FastAPI Router mit `parse_gpx()` |
| `api/main.py` | +`app.include_router(gpx.router)` |
| `internal/handler/proxy.go` | +`GpxProxyHandler` — Multipart+Query-Param Forwarding, 30s Timeout |
| `internal/router/router.go` | `r.Post("/api/gpx/parse", handler.GpxProxyHandler(...))` |

---

---

## 10) Orts-Vergleich-Presets & Briefing-Abos (ersetzt Subscriptions CRUD)

> Die alte `CompareSubscription`-Abstraktion und alle `/api/subscriptions`-Routen
> wurden entfernt und liefern absichtlich 404
> (`internal/router/legacy_subscription_routes_removed_test.go`). Ebenso entfernt:
> die Legacy-Scheduler-Routen `/api/scheduler/morning-subscriptions|evening-subscriptions|subscriptions-status`.
> Historische Details: Git-Historie dieses Dokuments.

Heute existieren zwei getrennte Domänenobjekte:

| Domäne | Pfad-Prefix | Handler | Persistenz |
|---|---|---|---|
| **Compare-Presets** (Orts-Vergleich) | `/api/compare/presets` (CRUD, `PATCH …/{id}/state`, `POST …/{id}/send`), Vorschau: `POST /api/preview/compare/{preset_id}` | `internal/handler/compare_preset.go` | `data/users/{userID}/briefings/` (kind=vergleich) |
| **Briefing-Subscriptions** (Trip-Briefing-Abos, ADR-0023) | `/api/briefings` | `internal/handler/briefing_subscription.go` | `data/users/{userID}/briefings/` |

Feld-Definitionen und Validierungsregeln: massgeblich sind die Go-Structs in
`internal/model/` und die Handler-Validierung — hier nicht dupliziert.

---

## 10.5) Trip Model and Activity Types (Issue #674)

Trip-Daten werden als JSON unter `data/users/{userID}/trips/{trip_id}.json` gespeichert. Das Kernmodell definiert Etappen, Wegpunkte und Konfiguration.

### Trip DTO

```go
type Trip struct {
    ID                      string                 `json:"id"`
    Name                    string                 `json:"name"`
    Stages                  []Stage                `json:"stages"`
    AvalancheRegions        []string               `json:"avalanche_regions,omitempty"`
    Aggregation             map[string]interface{} `json:"aggregation,omitempty"`
    WeatherConfig           map[string]interface{} `json:"weather_config,omitempty"`
    DisplayConfig           map[string]interface{} `json:"display_config,omitempty"`
    ReportConfig            map[string]interface{} `json:"report_config,omitempty"`
    AlertRules              []AlertRule            `json:"alert_rules"`
    AlertCooldownMinutes    *int                   `json:"alert_cooldown_minutes,omitempty"`
    AlertQuietFrom          *string                `json:"alert_quiet_from,omitempty"`
    AlertQuietTo            *string                `json:"alert_quiet_to,omitempty"`
    Shortcode               string                 `json:"shortcode,omitempty"`
    Activity                string                 `json:"activity,omitempty"`
    Region                  string                 `json:"region,omitempty"`
    PausedAt                *time.Time             `json:"paused_at,omitempty"`
    ArchivedAt              *time.Time             `json:"archived_at,omitempty"`
    OfficialAlertsEnabled   *bool                  `json:"official_alerts_enabled,omitempty"` // Issue #1087, Pointer-Muster analog ComparePreset (#1040): nil = Default true; false = kein Fetch amtlicher Warnungen für diesen Trip
    OfficialAlertTriggersEnabled *bool             `json:"official_alert_triggers_enabled,omitempty"` // @deprecated (Issue #1258, ersetzt durch official_warnings.enabled) — bleibt in den Daten fuer Rollback-Sicherheit, wird ab #1258 von UI und Pipeline nicht mehr geschrieben/gelesen. Vormals: nil = Default true; false = amtliche Warnungen lösen keinen eigenständigen Sofort-Alert aus (Briefing-Anzeige bleibt unberührt)
    OfficialWarnings        *OfficialWarningsConfig `json:"official_warnings,omitempty"`      // Issue #1258 — s. „official_warnings (Issue #1258)" unten
    AlertChannels            *AlertChannelsConfig   `json:"alert_channels,omitempty"`          // Issue #1258 Scheibe S3 — s. „alert_channels (Issue #1258)" unten
    Corridors               []Corridor             `json:"corridors"`                         // Issue #1231 Slice 1, additiv neben AlertRules — s. Section 24
    // Issue #1250 Scheibe 4 — flache Slot-/Kanal-Felder + EndDate, ABGELEITET aus
    // ReportConfig/Stages bei jedem Load (store.normalizeTrip). NICHT autoritativ:
    // ReportConfig bleibt die einzige Wahrheit fuer den Versand. nil = nicht ableitbar.
    MorningTime             *string                `json:"morning_time,omitempty"`
    EveningTime             *string                `json:"evening_time,omitempty"`
    MorningEnabled          *bool                  `json:"morning_enabled,omitempty"`
    EveningEnabled          *bool                  `json:"evening_enabled,omitempty"`
    SendEmail               *bool                  `json:"send_email,omitempty"`
    SendSms                 *bool                  `json:"send_sms,omitempty"`
    SendTelegram            *bool                  `json:"send_telegram,omitempty"`
    SendPremiumSms          *bool                  `json:"send_premium_sms,omitempty"`        // Issue #1717 S3 — vierter Kanal (Premium-SMS)
    EndDate                 *string                `json:"end_date,omitempty"`                // max(stage.date), ISO
    Kind                    string                 `json:"kind,omitempty"`                    // ADR-0023-Diskriminator ("route"); nur Migration schreibt ihn
}

// OfficialWarningsConfig — Issue #1258, geteilt zwischen Trip und ComparePreset
type OfficialWarningsConfig struct {
    Enabled bool     `json:"enabled"`
    Sources []string `json:"sources,omitempty"`
}

// AlertChannelsConfig — Issue #1258 Scheibe S3, additives Trip-Kanal-Set fuer
// die Alert-Zustellung. Seit Issue #1701 (S2b, D3) VIER Felder, alle *bool
// mit Feld-Level-Merge (die fruehere All-or-nothing-Praemisse ist abgeloest —
// ein PUT ohne ein Feld laesst dessen Bestandswert unangetastet).
type AlertChannelsConfig struct {
    Email      *bool `json:"email,omitempty"`
    Telegram   *bool `json:"telegram,omitempty"`
    Sms        *bool `json:"sms,omitempty"`
    PremiumSms *bool `json:"premium_sms,omitempty"` // Issue #1701 S2b
}

// AlertChannelThresholdsConfig — Issue #1461 S3b-2a, additives Geschwister-
// feld zu AlertChannelsConfig (NICHT darin). Je Kanal die Dringlichkeits-
// Schwelle als String-Pointer, damit "Kanal fehlt im Body" (Feld-Level-Merge
// bewahrt den Bestandswert) von "Kanal explizit gesetzt" unterscheidbar bleibt.
// PremiumSms (Issue #1701 S2b, D6) ist das vierte Geschwisterfeld.
type AlertChannelThresholdsConfig struct {
    Email      *string `json:"email,omitempty"`    // "LOW"|"MODERATE"|"HIGH"
    Telegram   *string `json:"telegram,omitempty"`
    Sms        *string `json:"sms,omitempty"`
    PremiumSms *string `json:"premium_sms,omitempty"`
}
```

### alert_channels (Issue #1258, seit #1701 S2b vier Kanäle)

Trip-weites Kanal-Set für den Alert-Versand (Abweichungs-Alerts und amtliche Sofort-Alerts), Pointer-Feld analog `official_warnings`:

```json
{"alert_channels": {"email": true, "telegram": false, "sms": false, "premium_sms": true}}
```

| Feld | Typ | Semantik |
|------|-----|----------|
| `alert_channels` | Objekt \| `null`/nicht gesetzt | **`null`/fehlend (Legacy-Verhalten):** Alert-Kanäle erben die aktiven Briefing-Kanäle aus `report_config` (`send_email`/`send_telegram`/`send_sms`/`send_premium_sms`) — kein Verhaltenswechsel für Bestand. **Gesetzt:** ersetzt beim Alert-Versand den geerbten Briefing-Anteil, seit #1701 (D3) mit **Feld-Level-Merge**: ein PUT, das ein Feld nicht mitschickt (z. B. ein älterer Frontend-Build ohne `premium_sms`), lässt dessen Bestandswert unverändert statt ihn auf `false` zurückzusetzen |
| `alert_channels.email`/`.telegram`/`.sms`/`.premium_sms` | bool | einzelne Kanal-Flags; `premium_sms` gated zusätzlich über `premium_sms_allowed()` (Tier-Gate, NICHT `sms_allowed()`) |

Präzedenz unverändert: per-Regel-`channels`-Overrides (Issue #638, s. „Versand-Logik (Kanal pro Alert)" oben) gewinnen weiterhin über den geerbten/gesetzten Trip-Anteil; das SMS-/Premium-SMS-Tier-Gate bleibt in jedem Fall aktiv. Quelle: `internal/model/trip.go` (`AlertChannelsConfig`), Spec `docs/specs/_archive/modules/issue_1258_alarme_tab_official_warnings.md` Abschnitt 9, Spec `docs/specs/modules/feat_1701_alarm_premium_sms.md` (vierter Kanal, D3).

### alert_channel_thresholds (Issue #1461 S3b-2a Trip · S3b-2b Ortsvergleich · #1701 S2b vierter Kanal)

Additives Geschwisterfeld zu `alert_channels`/`send_telegram`+`send_sms`+`send_premium_sms`: je Alarm-Kanal die Dringlichkeitsstufe, ab der eine ausgelöste Alarm-Meldung diesen Kanal erreichen darf. Identischer Vertrag auf `Trip` **und** `ComparePreset` — derselbe Go-Typ (`AlertChannelThresholdsConfig`), kein zweiter.

```json
{"alert_channel_thresholds": {"email": "LOW", "telegram": "HIGH", "sms": "MODERATE", "premium_sms": "HIGH"}}
```

| Feld | Typ | Semantik |
|------|-----|----------|
| `alert_channel_thresholds` | Objekt \| `null`/nicht gesetzt | **`null`/fehlend:** kein Kanal hat eine Schwelle gesetzt — Startwert `"LOW"` je Kanal (Python-Vorgabewert, nicht persistiert). **Gesetzt:** je Kanal maßgeblich für den Versand-Filter |
| `alert_channel_thresholds.email`/`.telegram`/`.sms`/`.premium_sms` | `"LOW"`\|`"MODERATE"`\|`"HIGH"` \| fehlend | fehlender Kanal-Key im PUT-Body → **Feld-Level-Merge** bewahrt den Bestandswert (AC-7 Trip / AC-10 Compare); ein GANZ fehlendes `alert_channel_thresholds` im Body bewahrt das ganze Unterobjekt (Top-Level-`nil`-Erbe, AC-6 Trip / AC-9 Compare) |

Wirkung: eine ausgelöste Meldung erreicht einen eingeschalteten Kanal nur, wenn ihre Dringlichkeit (`services.alert_urgency`, `LOW`/`MODERATE`/`HIGH`) die dort eingestellte Schwelle erreicht oder übertrifft (`services.alert_channel_threshold.split_by_threshold()`). Das an das Alarm-Protokoll übergebene Kanal-Set bleibt dabei das **rohe**, unveränderte Opt-in — nur der tatsächliche Versand wird gefiltert (ADR-0046). Vollständig unterdrückte Meldungen erscheinen im nächsten Briefing im Block „ZURÜCKGEHALTEN — so hast du es eingestellt" mit dem Grund „unter deiner Schwelle" (`below_channel_threshold`, S3b-1-Sichtbarkeit). Die frühere Formulierung „als nicht zugestellt" steht seit #1750 nicht mehr in der Mail — sie behauptete für die planmäßigen Sperrgründe einen Fehler.

**Ortsvergleich (S3b-2b), zwei Besonderheiten:**
- Der Compare-Regenradar-Alarm (`compare_radar_alert.py`) war bis S3b-2b hart auf `{"email"}` verdrahtet — die Kanal-Schwelle greift dort seither über denselben Resolver (`effective_compare_channels()`) wie bei den beiden anderen Compare-Alarmwegen (Verhaltensänderung: Regenradar-Alarme erreichen jetzt auch Telegram/SMS).
- Der Compare-SMS-/Telegram-**Bericht** (`comparison.py`, kein Alarm-Versand) zeigt amtliche Warnungen seit S3b-2b ab der Startschwelle „gering" statt der vormals festen `MIN_SMS_LEVEL` (orange) — unabhängig von einer je Kanal gesetzten Alarm-Schwelle desselben Ortsvergleichs (zwei getrennte Wirkungsorte, s. `docs/reference/sms_format.md`).

Quelle: `internal/model/trip.go` / `internal/model/compare_preset.go` (`AlertChannelThresholdsConfig`), ADR-0046, Spec `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md` (Trip), `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md` (Ortsvergleich).

### official_warnings (Issue #1258)

Löst `official_alert_triggers_enabled` (#1088) funktional ab: `official_warnings.enabled`
steuert, ob amtliche Warnungen für diesen Trip/ComparePreset einen Sofort-Alarm auslösen
(Briefing-Anzeige selbst bleibt unberührt, s. `official_alerts_enabled` #1087). Gilt identisch
für Trip UND ComparePreset (Go `*OfficialWarningsConfig`, Python `Optional[dict]`).

```json
{"official_warnings": {"enabled": true, "sources": ["vigilance"]}}
```

| Feld | Typ | Semantik |
|------|-----|----------|
| `enabled` | bool | `true` = amtliche Warnungen lösen einen Sofort-Alarm aus; `false` = kein Sofort-Alarm |
| `sources` | string[] \| omitted | Quellen-Filter (Namen aus `src/services/official_alerts/__init__.py`-Registry). Unset/leer = alle registrierten Quellen fließen ein (unverändertes Verhalten). Gesetzt = nur die genannten Quellen fließen in die Alarmentscheidung ein, andere werden ignoriert |

**Fehlend/`nil`:** unmigrierter Bestand — Pipeline (`trip_alert.py`, `compare_official_alert.py`)
fällt fail-soft auf das Legacy-Feld `official_alert_triggers_enabled` zurück (`nil`/`true` →
Alarm aktiv, `false` → kein Alarm). Ein `{}`-Wert (Key vorhanden, `enabled` fehlt) wird wie
`nil` behandelt (Legacy-Fallback), nicht wie `enabled=false` — Go und Python sind hierin
identisch (Fix-Loop F003, s. Changelog #1258).

**Neuanlage-Default:** `enabled: false` — bewusster Verhaltenswechsel gegenüber Bestand (der per
Migration den alten Ist-Zustand behält, s.u.).

**Migration (`internal/store/migrate_1258.go`, `scripts/migrate_1258_official_warnings.py`):**
idempotente Batch-Migration nach Vorbild `migrate_1257.go` — pro Trip/ComparePreset unter
`data/users/*/`: `official_warnings.enabled := (official_alert_triggers_enabled != false)`
(nil/true → true, false → false), damit ändert sich das gesendete Alarmverhalten für Bestand
NICHT. Zweiter Lauf ändert an bereits migrierten Objekten nichts (Idempotenz-Check über
`officialWarningsRawHasEnabledKey()`/`"enabled" in ow`).

**PUT-RMW (Read-Modify-Write, `internal/handler/trip.go`, `internal/handler/compare_preset.go`):**
Feld im Body ganz weglassen → Bestand bleibt unverändert (Objekt-Ebene). Wird `official_warnings`
mitgeschickt, aber `sources` darin weggelassen (Key fehlt im JSON) → bestehende `sources[]`
bleiben erhalten (Feld-Level-Preserve, Fix-Loop F002); ein explizites `"sources": []` löscht die
Liste bewusst. `enabled` ist innerhalb eines mitgeschickten `official_warnings`-Objekts immer
Pflicht-Wert der Anfrage (kein separates Preserve für `enabled` selbst).

**Isolation:** wie jedes trip-/presetgebundene Feld strikt über `user_id` — kein Cross-User-Leck
(s. `CLAUDE.md` Mandantenfähigkeits-Pflicht).

**Invariante — nie `null` (Issue #205, gehärtet Issue #1244):** `Stages`, jedes
`Stage.Waypoints`, `AlertRules` und `Corridors` sind immer als `[]` serialisiert, niemals als
`null` — sowohl in der Datei auf Platte als auch in jeder HTTP-Response. Durchgesetzt von
`normalizeTrip()` (`internal/store/trip.go`), das sowohl im Schreibpfad (`SaveTrip`, nimmt seit
#1244 einen Pointer statt eines Value-Receivers) als auch im Lesepfad (`LoadTrip`, `LoadTrips`)
läuft. Der Python-Loader (`src/app/loader.py`) heilt zusätzlich `null` beim Lesen fail-soft
(`data.get("x") or []`) für Bestandsdateien, die noch nicht über `SaveTrip` neu geschrieben
wurden. Bestandsdaten: `scripts/migrate_1244_null_lists.py`, s. `operations_playbook.md`.

### Activity Types (Issue #674)

Das Feld `activity` definiert die Art der Fortbewegung und damit die Geschwindigkeitsannahmen für Ankunftszeit-Berechnungen (Naismith-Formel).

| ActivityType | Flachgeschwindigkeit | Aufstieg [m/h] | Abstieg [m/h] | Verwendungsfall |
|---|---|---|---|---|
| `"trekking"` | 4.0 km/h | 300 | 500 | Standard-Wanderung (default) |
| `"skitour"` | 3.5 km/h | 250 | 400 | Skitour ohne Trails |
| `"hochtour"` | 3.0 km/h | 300 | 400 | Hochgebirgstouren mit Felsen/Schnee |
| `"klettersteig"` | 2.0 km/h | 150 | 200 | Klettersteig-Passagen |
| `"mtb"` | 4.0 km/h | 300 | 500 | Mountainbike (aktuell Wandertempo) |
| `"fahrrad_15"` | **15.0 km/h** | **600** | **1000** | Tourenrad, moderate Tempo (Issue #674) |
| `"fahrrad_20"` | **20.0 km/h** | **600** | **1000** | Tourenrad, zügig (Issue #674) |
| `"fahrrad_25"` | **25.0 km/h** | **600** | **1000** | Tourenrad, schnell (Issue #674) |

**Leeres oder unbekanntes Activity-Feld:** Fallback auf `"trekking"` (4.0 km/h, 300/500 m/h) für Backward Compatibility mit bestehenden Trips.

**Naismith-Formel:**
```
Fahrzeit [h] = Distanz [km] / FlatKmh + Aufstieg [m] / AscentMh + Abstieg [m] / DescentMh
```

**Höhenmeter-Begründung für Fahrradtypen:** Radfahrer überwinden Steigungen effizienter als Fußgänger (bessere Kraftübertragung, Schwungtechnik bei Abfahrten). Die 600/1000-Raten entsprechen der doppelten Geschwindigkeit von Wanderern (300/500).

### Shortcode (Bug #775)

Das Feld `shortcode` dient als eindeutiger, pro Nutzer stabiler Routing-Identifier für Inbound-E-Mail-Replies.

| Feld | Beschreibung |
|------|-------------|
| `shortcode` | Format: `GZ#XXXX` oder `GZ#XXXX<n>` (z.B. `GZ#HERM`, `GZ#HERM2` bei Kollision). Generiert aus den ersten 4 alphanumerischen Großbuchstaben des Trip-Namens. Wird lazy persistiert beim ersten Versand. Immun gegen RFC-2047-Encoding-Artefakte (Leerzeichen→Underscore). Präfix im E-Mail-Betreff: `[GZ#HERM]` ermöglicht Shortcode-Prioritäts-Lookup; Fallback: toleranter Namensvergleich (Whitespace/Underscore-agnostisch). |

### Stage DTO

```go
type Stage struct {
    ID        string     `json:"id"`
    Name      string     `json:"name"`
    Date      string     `json:"date"`                  // YYYY-MM-DD
    Waypoints []Waypoint `json:"waypoints"`
    StartTime *string    `json:"start_time,omitempty"`  // HH:MM (Issue #675)
}
```

> Distanz/Auf-/Abstieg/Dauer sind KEINE persistierten Stage-Felder — sie werden
> zur Anzeige aus den Waypoints berechnet (Frontend) bzw. via Naismith abgeleitet.
> Ankunftszeiten leben pro Waypoint (`arrival_calculated`), nicht auf der Stage.

### Waypoint DTO

```go
type Waypoint struct {
    ID                string  `json:"id"`
    Name              string  `json:"name"`
    Lat               float64 `json:"lat"`
    Lon               float64 `json:"lon"`
    ElevationM        int     `json:"elevation_m"`
    TimeWindow        *string `json:"time_window,omitempty"`
    ArrivalCalculated *string `json:"arrival_calculated,omitempty"` // Issue #296 — "HH:MM", Backend-berechnet (Naismith)
    Origin            string  `json:"origin,omitempty"`             // "manual" | "algorithmic"; leer = "manual" (Issue #303)
    Confirmed         *bool   `json:"confirmed,omitempty"`          // *bool: false bleibt serialisierbar
    ArrivalOverride   *string `json:"arrival_override,omitempty"`   // User-Override "HH:MM"
}
```

**Berechnung `arrival_calculated`:**
- Frontend: `computeArrivalTimes(stage, startTime, activityToSpeed(trip.activity))` → gibt Array von HH:MM-Strings
- Backend (Go): `ComputeStageArrivals(stage, ActivitySpeed(trip.activity))` → mutiert Waypoints mit berechneter Zeit
- TypeScript: `function activityToSpeed(activity?: ActivityType): number` — 15/20/25 für Fahrrad, 4.0 default

**Segment-Startzeit-Prioritätskette (Issue #1004, SSoT):** `Waypoint.time_window` ist
ausschließlich ein GPX-Import-Artefakt ohne jeden manuellen Schreibpfad im Produkt und hat
in `convert_trip_to_segments()` (`trip_segments.py`) **keine** Autorität mehr — kein Flag,
keine Migration, gilt sofort für alle Trips inkl. Bestand. Die einzige Kette:
`arrival_override` (Issue #303, manuell) > `stage.start_time` (nur für Segment 1 einer Etappe)
> `arrival_calculated` (Naismith-Kaskade, immer frisch ab `stage.start_time`) > Default 08:00
> letzter bekannter Zeitpunkt (Folgesegmente). `time_window` selbst bleibt als
Roundtrip-/Anzeige-Feld am DTO erhalten, wird aber nirgends mehr als Zeitquelle gelesen.
Der zuvor eingeführte Python-interne Flag-Ansatz `Waypoint.time_window_origin` (Issue #995)
wurde als wirkungslos entfernt (nie persistiert, Bestandstrips blieben ausgenommen).

**Beispiel (Fahrrad 20 km/h):**
```json
{
  "id": "w1",
  "name": "Alp Blenio",
  "lat": 46.45,
  "lon": 8.65,
  "elevation_m": 1500,
  "arrival_calculated": "09:00"
}
```
Bei `start_time = "08:00"`, `activity = "fahrrad_20"` und 20 km kumulierter Distanz
(aus den GPX-Punkten berechnet — KEIN persistiertes Waypoint-Feld im Go-Struct):
20 km ÷ 20 km/h = 1 h → 09:00 ✓

---

## 11) Weather Config Endpoints (M5c)

Convenience-Layer ueber die bestehenden CRUD-Handler. Erlaubt gezieltes Lesen und Schreiben des `display_config`-Subfelds auf Trip- und Location-Entitaeten ohne Uebertragung des gesamten Objekts. Alle Config-schreibenden Endpoints (Trip, Location, ComparePreset) mergen feldweise ueber den gemeinsamen `mergeConfigMap`-Helfer (`internal/handler/config_merge.go`, #1159) — Teil-Updates loeschen keine anderen `display_config`-Keys mehr. Der fruehere Subscription-Endpoint wurde mit #1250 Scheibe 0 entfernt.

**Handler:** `internal/handler/weather_config.go` (NEU) | **Routing:** `internal/router/router.go`

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/trips/{id}/weather-config` | 200 / 404 | `display_config` eines Trips lesen — Antwort traegt `ETag` (#1395 S2) |
| PUT | `/api/trips/{id}/weather-config` | 200 / 400 / 404 / **412** | `display_config` eines Trips setzen — prueft `If-Match`, Antwort traegt neuen `ETag` (#1395 S2) |
| GET | `/api/locations/{id}/weather-config` | 200 / 404 | `display_config` einer Location lesen |
| PUT | `/api/locations/{id}/weather-config` | 200 / 400 / 404 | `display_config` einer Location setzen — **kein** `ETag`/`If-Match` (Orte liegen auf einer anderen Datei-Ebene) |

### Nebenlaeufigkeit: `ETag` / `If-Match` (Issue #1395, seit 2026-07-27, Orts-Vergleiche seit S6 2026-07-31)

Betrifft **Touren UND Orts-Vergleiche** (beide teilen sich dieselbe
Datei-Ebene `briefings/<id>.json`, unterschieden durch `kind=route`/
`kind=vergleich`) — Orte (`locations/<id>.json`) bleiben weiterhin nicht
betroffen.

| Endpunkt | `ETag` in der Antwort | prueft `If-Match` |
|---|---|---|
| `GET /api/trips/{id}` | ja | — |
| `PUT /api/trips/{id}` | ja (der **neue** Stand) | **ja** |
| `GET /api/trips/{id}/weather-config` | ja | — |
| `PUT /api/trips/{id}/weather-config` | ja (der **neue** Stand) | **ja** |
| `POST /api/trips` | nein | — |
| `PATCH /api/trips/{id}/state` | nein | nein |
| `PATCH /api/trips/{id}/waypoints/{wp}/confirm` | nein | nein |
| `DELETE /api/trips/{id}` | — | nein |
| `GET /api/compare/presets/{id}` | ja | — |
| `PUT /api/compare/presets/{id}` | ja (der **neue** Stand) | **ja** |
| `POST /api/compare/presets` | nein | — |
| `DELETE /api/compare/presets/{id}` | — | nein |
| `PATCH /api/compare/presets/{id}/state` | nein | nein |
| `GET /api/briefings/{id}?kind=vergleich` | ja | — |
| `PUT /api/briefings/{id}?kind=vergleich` | ja (der **neue** Stand) | **ja** |

- **Wert:** `ETag: "<sha256-hex>"` in Anfuehrungszeichen (RFC 7232). Der Stempel
  ist ein Inhalts-Fingerabdruck der **Rohdatei**, kein Feld im Dokument —
  Begruendung in `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md`
  (Kurzfassung: der Python-Kern schreibt dieselben Dateien; ein nur von Go
  gepflegter Zaehler waere nach jedem Python-Schreibvorgang still falsch).
- **Beide `GET`-Endpunkte liefern denselben Wert**, weil sie dieselbe Datei
  betreffen. Ein Client fuehrt den Stempel deshalb **je Tour**, nicht je Adresse.
- **Fehlender oder leerer `If-Match` wird ANGENOMMEN.** Rollout-Politik: sonst
  waere die Auslieferungsreihenfolge Go↔Frontend eine Sollbruchstelle und jeder
  Bestandsclient braeche.
- **Falscher `If-Match` → `412`** mit
  `{"error":"precondition_failed","detail":"<deutscher Text>"}`, **ohne**
  `ETag`-Header und **ohne** dass geschrieben wird. Der Client soll neu laden,
  nicht blind wiederholen.
- `If-Match: *` und Kommalisten (ein Treffer genuegt) werden akzeptiert.
- **Ein erfolgreicher `PUT` liefert immer den NEUEN Stempel zurueck.** Pflicht,
  nicht Bequemlichkeit: Der Server heilt beim Lesen in-memory ohne
  Rueckschreiben, der naechste Save persistiert die Heilung — die Datei aendert
  sich also auch, wenn der Nutzer inhaltlich nichts geaendert hat. Ohne
  Rueckgabe liefe der zweite Klick desselben Nutzers in einen Konflikt mit sich
  selbst.
- **Der Flush beim Verlassen der Seite** (`keepalive`) sendet bewusst **ohne**
  `If-Match` — sonst liefe er in einen unsichtbaren Konflikt und die Aenderung
  waere weg, ohne dass es jemand erfaehrt.
- **Orts-Vergleiche haben zwei Schreibwege auf dieselbe Datei** —
  `PUT /api/compare/presets/{id}` (dediziert) und
  `PUT /api/briefings/{id}?kind=vergleich` (Umgehungsweg, `UpdateBriefingHandler`) —
  und teilen sich Fingerabdruck UND serverseitige Sperre. Ein veralteter
  Schreibversuch ueber den einen Weg wird deshalb auch dann mit `412`
  abgelehnt, wenn zuletzt ueber den JEWEILS ANDEREN Weg geschrieben wurde
  (Issue #1395 S6) — kein Weg ist eine Umgehung des anderen. Namensraum-Kollision
  mit Trip-IDs ist ausgeschlossen, da Compare-Preset-IDs das Praefix `cp-`
  tragen.

### Response Format

**GET 200 (config vorhanden):**
```json
{"show_precipitation": true, "show_wind": false}
```

**GET 200 (config nicht gesetzt):**
```json
null
```

**PUT Request Body:** Beliebiges gueltiges JSON-Objekt (opaque, kein Schema). Response: gespeichertes `display_config`.

### Error Responses

| Status | Body | Szenario |
|--------|------|----------|
| 400 | `{"error":"bad_request"}` | Request-Body ist kein gueltiges JSON (PUT) |
| 404 | `{"error":"not_found"}` | Parent-Entitaet nicht gefunden |

### Notes

- `display_config` wird als `map[string]interface{}` ohne Schema-Validierung round-getrippt (opaque JSON)
- `userID` hardcodiert auf `"default"` (V1)
- Kein File-Locking: Race Conditions bei parallelen PUT-Requests akzeptiert (Single-User V1)

### Source Files

| Datei | Aenderung |
|-------|-----------|
| `internal/handler/weather_config.go` | 4 HTTP-Handler (Get/Put fuer Trip, Location) |
| `internal/handler/config_merge.go` | NEU (#1159) — gemeinsamer `mergeConfigMap`-Helfer fuer feldweisen Merge, genutzt von Trip-, Location- und ComparePreset-Endpoints |
| `internal/router/router.go` | Route-Registrierungen |

---

## 12) Scheduler Status Endpoint (Epic #134)

Exposes scheduler job metadata for dashboard display (BriefingsTimeline component).

**Handler:** `internal/handler/scheduler_status.go` | **Routing:** `internal/router/router.go`

### GET /api/scheduler/status

Returns current scheduler state with per-job metadata (next_run, last_run).

**Response 200:**

```json
{
  "running": true,
  "timezone": "Europe/Vienna",
  "jobs": [
    {
      "id": "morning",
      "name": "Morgenbriefing",
      "next_run": "2026-05-10T07:00:00Z",
      "last_run": {
        "time": "2026-05-09T07:00:00Z",
        "status": "ok",
        "error": null
      }
    },
    {
      "id": "evening",
      "name": "Abendbriefing",
      "next_run": "2026-05-09T18:00:00Z",
      "last_run": {
        "time": "2026-05-09T17:55:00Z",
        "status": "error",
        "error": "forecast_api_timeout"
      }
    },
    {
      "id": "alert_checks",
      "name": "Alert Checks (every 15 min)",
      "next_run": "2026-08-01T13:15:00Z",
      "last_run": {
        "time": "2026-08-01T12:00:00Z",
        "status": "ok",
        "error": null
      },
      "overlap": {
        "skipped_since_last_run": 3,
        "last_skipped_at": "2026-08-01T13:00:00Z"
      }
    }
  ],
  "briefing_health": {
    "provider_error_streak_since": "2026-08-09T14:32:00Z",
    "provider_errors_recent_count": 1,
    "briefing_dispatch_error_streak_since": "2026-08-10T09:00:00Z",
    "briefing_dispatch_errors_recent_count": 2,
    "alert_anchor_rejected_streak_since": "2026-08-10T11:15:00Z",
    "alert_anchor_rejected_recent_count": 4
  },
  "tier_request_health": {
    "open_count": 1,
    "oldest_open_age_hours": 192.4
  }
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| running | bool | Is scheduler process active |
| timezone | string | Scheduler timezone (default: "Europe/Vienna") |
| jobs[] | array | List of scheduled jobs |
| jobs[].id | string | Job identifier (morning, evening, alert, trip_reports_hourly) |
| jobs[].name | string | Human-readable job name |
| jobs[].next_run | datetime \| null | ISO-8601 UTC datetime of next scheduled run |
| jobs[].last_run | object \| null | Metadata of last execution (null if never run) |
| jobs[].last_run.time | datetime | ISO-8601 UTC timestamp of the last **actually executed** run — never overwritten by a skipped (overlapping) tick |
| jobs[].last_run.status | enum | `ok`, `partial` (Issue #1447 S2a — a per-user run reported `status: "partial"` without `failed`, e.g. the alert-run deadline from S1) or `error` |
| jobs[].last_run.error | string \| null | Error code/message if status='error' or 'partial' |
| jobs[].overlap | object \| null (Issue #1447 S2a) | Present **only** when at least one tick has been skipped since the last executed run of this job, because the previous run of the same job ID was still in progress (`sync.Mutex.TryLock()` in `recordRun`). Absent field means no overlap is occurring — never an error signal. |
| jobs[].overlap.skipped_since_last_run | int | Number of consecutive ticks skipped since the last executed run; resets to 0 (and the `overlap` field disappears) the next time the job actually runs, regardless of outcome |
| jobs[].overlap.last_skipped_at | datetime | ISO-8601 UTC timestamp of the most recently skipped tick |
| briefing_health | object (Issues #1115, #1421, #1629, #1661) | Health metrics for scheduler services (provider/weather, briefing dispatch, deviation-alert anchors). Privacy-safe aggregate across all users — only numeric and timestamps, no `user_id`/`trip_id`/reason appears here. |
| briefing_health.provider_error_streak_since | string \| null (Issue #1115, ADR-0018) | ISO-8601 UTC timestamp when the current unbroken series of provider (weather/forecast API) errors started, or `null` if no error streak is active. External monitor calculates `now - provider_error_streak_since` to escalate with outage duration. Gap threshold (for streak detection): 2 hours. |
| briefing_health.provider_errors_recent_count | int (Issue #1115, ADR-0018) | Count of provider errors in the last 24 hours. Used to distinguish temporary transients from persistent outages. |
| briefing_health.briefing_dispatch_error_streak_since | string \| null (Issue #1629) | ISO-8601 UTC timestamp when the current unbroken series of trip/compare briefing dispatch (send) errors started, or `null` if no dispatch error streak is active. Tracks send failures separately from weather data availability. Gap threshold: 26 hours (briefings run 1–2 times daily per user, so a 2-hour threshold would mask single failures). |
| briefing_health.briefing_dispatch_errors_recent_count | int (Issue #1629) | Count of briefing dispatch errors in the last 24 hours (recorded in `users/<uid>/diagnostics/briefing_dispatch_failures.jsonl`). |
| briefing_health.alert_anchor_rejected_streak_since | string \| null (Issue #1661) | ISO-8601 UTC timestamp when the current unbroken series of **rejected deviation-alert anchors** started, or `null` if no streak is active. An anchor is rejected when it describes a different calendar day than today (`wrong_day`), is older than the 26 h fallback limit (`too_old`), or is missing entirely while the trip is already running (`missing`) — in each case the deviation guard has no valid comparison point and stays silent. Gap threshold: **60 minutes** (the alert check runs every 15 minutes, so an hour without a further rejection ends the series; the 26 h threshold used for briefings would keep the same fault invisible for days). |
| briefing_health.alert_anchor_rejected_recent_count | int (Issue #1661) | Count of rejected deviation-alert anchors in the last 24 hours (recorded in `users/<uid>/diagnostics/alert_anchor_rejected.jsonl`). Only the timestamp is decoded on the Go side — neither the trip id nor the rejection reason leaves the Python core (#252). |
| tier_request_health | object (Issue #1555) | Privacy-safe aggregate of open tier-change requests (`POST /api/auth/tier-change-request`, Issue #1071) across ALL users. Purely numeric — the endpoint is public, so no `user_id`, `display_name` or e-mail ever appears here (#252). A request counts as **done** when `requested_tier` is empty OR equals the effective `tier`; only otherwise it is **open**. |
| tier_request_health.open_count | int | Number of currently open tier-change requests across all users. `0` when none are pending. |
| tier_request_health.oldest_open_age_hours | float | Age in hours of the **oldest** open request (from its `requested_at`); `0.0` when `open_count` is 0 or no open request carries a `requested_at`. Raw hours only — the 7-day overdue threshold is evaluated by the external monitor (`check-gregor20.sh`), not here. |

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 503 | `{"error":"scheduler_unavailable"}` | Scheduler process not reachable |

---

## 13) Forecast Query Endpoint (Epic #134)

Client-side forecast fetch for dashboard weather display (non-blocking).

**Handler:** Proxies to Python weather provider | **Routing:** `internal/router/router.go`

### GET /api/forecast

Fetches normalized weather forecast for a given coordinate.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | yes | Latitude (-90 to 90) |
| lon | float | yes | Longitude (-180 to 180) |
| hours | integer | no | Forecast range in hours (default: 24) |

**Response 200:**

```json
{
  "meta": {
    "provider": "GEOSPHERE",
    "model": "INCA-LC",
    "run": "2026-05-09T06:00:00Z",
    "grid_res_km": 1,
    "interp": "point_grid"
  },
  "data": [
    {
      "ts": "2026-05-09T12:00:00Z",
      "t2m_c": 18.5,
      "wind10m_kmh": 22.0,
      "gust_kmh": 38.0,
      "precip_1h_mm": 0.4,
      "cloud_total_pct": 85,
      "symbol": "lightrain",
      "humidity_pct": 78,
      "dewpoint_c": 17.0
    }
  ]
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid_coords"}` | lat/lon out of range or missing |
| 503 | `{"error":"provider_unavailable"}` | Weather provider API unreachable |

---

## 14) Trip-Reports Trigger Endpoint (Epic #134)

Manually triggers briefing generation for immediate test/delivery.

**Handler:** `internal/handler/scheduler_status.go` | **Routing:** `internal/router/router.go`

### POST /api/scheduler/trip-reports

Enqueues immediate trip report (morning/evening/alert) generation and send for active trip.

**Request Body:** `{}` (empty, report type inferred from scheduler config)

**Response 202 (Accepted):**

```json
{
  "message": "Trip report enqueued",
  "job_id": "trip-reports-1234",
  "report_type": "evening"
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"no_active_trip"}` | No trip with today's stage found |
| 503 | `{"error":"scheduler_unavailable"}` | Scheduler not available |

---

## 14.5) Manual Test-Briefing Send Endpoint (Issue #695, Bug #716)

Sends an immediate test briefing for a specific trip via the user's configured email.

**Handler:** `api/routers/scheduler.py` | **Route:** `POST /api/trips/{trip_id}/send`

### POST /api/trips/{trip_id}/send

Triggers immediate test briefing send for one trip. Returns success/failure based on whether stage data exists for the target date.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | `"default"` | User identifier (multi-tenant scoping) |
| `report_type` | string | `"evening"` | `"morning"` (today's stages) or `"evening"` (tomorrow's stages) |

**Response 200 (Success):**

```json
{
  "status": "ok",
  "trip_id": "gr20-2026",
  "report_type": "evening",
  "sent": true
}
```

**Error Responses:**

| Status | Scenario | Detail |
|--------|----------|--------|
| 404 | Trip `trip_id` not found for user | `"Trip {trip_id} not found"` |
| 409 | Another send for the same `(user_id, trip_id, report_type)` is already in progress (Issue #1756) | `"Versand für {report_type} läuft bereits — bitte warten"` |
| 422 | SMTP not configured for user (Issue #474) | `"SMTP not configured for this user"` |
| 422 | No stages for target date (Bug #716 — AC-1) | `"Kein Briefing für {report_type} — keine Etappendaten für das aktuelle Datum"` |
| 422 | Invalid `report_type` | `"Invalid report_type: {value}"` |

**Idempotenz (Issue #1756):** Ein zweiter Aufruf für denselben `(user_id, trip_id, report_type)`-Schlüssel während ein erster Versand noch läuft (z. B. wiederholter Klick nach vorzeitigem Proxy-Timeout) wird mit HTTP 409 abgewiesen statt einen zweiten echten Versand auszulösen. Der Lock ist prozesslokal (`threading.Lock`, In-Memory), keine Persistenz. Der Go-Proxy (`SendTripReportProxyHandler`) hat außerdem einen auf 300s (vorher 120s) angehobenen Timeout, da der reguläre Erfolgsfall durch den vollständigen Mehrtages-Ausblick 3–4 Minuten dauern kann.

**Multi-Tenant Behavior:**
- `user_id` query parameter determines which user's data (trip, email config) is used
- Trip must exist in `data/users/{user_id}/trips/` directory
- Email sent to `settings.mail_to` for that user (set via `/api/auth/profile`)
- Default `user_id="default"` provided for backwards compatibility (e.g. test-mode without auth)

**Bug #716 Fix (2026-06-10):**
- Prior: silent failure (HTTP 200 even when no email sent) when stages missing for target date
- Now: explicit HTTP 422 with descriptive error message in `detail` field (AC-1)
- Frontend reads `detail` field and displays in error toast (AC-4, `frontend/src/routes/trips/[id]/+page.svelte`)

---

## 14.6) Alert-Checks Trigger Endpoint (Issue #1447 Scheibe S1)

Triggers `TripAlertService.check_all_trips()` for one user. Called by the Go
scheduler every 30 minutes. Since Issue #1447 (S1), the run is bounded by a
hard time budget (`ALERT_RUN_DEADLINE_SECONDS = 90.0`, `src/services/trip_alert.py`)
— well under the 120s the Go scheduler's shared `http.Client` waits per user
before aborting the request. The response now reflects whether the run
completed fully or was cut off by that budget.

**Handler:** `api/routers/scheduler.py::trigger_alert_checks`

### POST /api/scheduler/alert-checks

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | yes | User identifier (multi-tenant scoping) |

**Response 200 — full run:**

```json
{
  "status": "ok",
  "count": 2,
  "checked": 5,
  "skipped": 0,
  "duration_s": 1.34
}
```

**Response 200 — run aborted by the time budget:**

```json
{
  "status": "partial",
  "count": 1,
  "checked": 3,
  "skipped": 2,
  "duration_s": 90.02,
  "reason": "deadline"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` (full run) or `"partial"` (deadline hit) |
| `count` | int | Alerts actually sent (`AlertCheckRunResult.alerts_sent`) |
| `checked` | int | Trips actually checked before the run ended |
| `skipped` | int | Trips not reached because the deadline was hit (0 on a full run) |
| `duration_s` | float | Actual wall-clock runtime of this run |
| `reason` | string | Present only when `status: "partial"` — currently always `"deadline"` |

**Resolved by Scheibe S2a (Issue #1447):** the limitation described below no
longer applies — `internal/scheduler/scheduler.go::triggerEndpointForUser`
now also evaluates `status`. A `"partial"` response (without `failed`) is
classified as a `partialRunError` and recorded as `Status: "partial"` in
`/api/scheduler/status` (see §12). S2a additionally adds a per-job
overlap-skip guard covering all nine scheduler jobs, not just
`alert_checks` — see §12 for the `jobs[].overlap` field. Kept below for
historical context (S1 was written and shipped before S2a).

**Known limitation of S1 alone (superseded by S2a, see above):** the Go
scheduler (`internal/scheduler/scheduler.go`) only evaluates the `failed`
field of this response, which this endpoint never sets. A `"partial"`
response therefore still records as `Status: "ok"` in
`/api/scheduler/status` — the Go-side evaluation of `status`/`reason` is
Scheibe S2 (separate spec), not part of S1. Until then, the WARNING/INFO
log lines from `configure_logging()` (see below) are the only visible
signal of a deadline abort.

**Root-Logger configuration (Issue #1447 Teil B):** `api/main.py::configure_logging()`
now configures the Python-Core root logger at import time (previously
unconfigured — every `logger.info`/`.warning` call from `src/` was silently
dropped). Minimum visible level is controlled via the `GZ_LOG_LEVEL`
environment variable (default `INFO`); format includes timestamp, level and
module name. Does not affect uvicorn's own `uvicorn`/`uvicorn.error`/
`uvicorn.access` loggers (configured separately by uvicorn, `propagate=False`).

**Side effect and mitigation (Adversary finding F001):** activating the root
logger also makes third-party library INFO/DEBUG lines visible. `httpx`
logs the full request URL on every call, and the Telegram Bot API encodes
the access token as a URL path segment (`.../bot{token}/sendMessage`) — the
Telegram bot token would otherwise have leaked in cleartext into the process
log (`journalctl -u gregor-python`) on every alert and every briefing.
`configure_logging()` therefore pins `httpx` and `httpcore` to `WARNING`
unconditionally, regardless of `GZ_LOG_LEVEL` (including `DEBUG`). Covered by
`tests/unit/test_logging_configuration.py` (real Telegram API call against a
local test socket, asserts a placeholder token never appears in captured log
output).

---

## 15) Metric Catalog Endpoint (Issue #435)

Provides metadata about available weather metrics, including per-metric format modes.

**Handler:** `api/routers/config.py` | **Routing:** `internal/router/router.go`

### GET /api/metrics

Returns catalog of all available weather metrics with format mode options and defaults.

**Response 200:**

```json
{
  "metrics": [
    {
      "id": "temperature",
      "name": "Temperature",
      "unit": "°C",
      "format_modes": ["raw"],
      "default_format_mode": "raw"
    },
    {
      "id": "wind_direction",
      "name": "Wind Direction",
      "unit": "degrees",
      "format_modes": ["raw", "scale"],
      "default_format_mode": "scale"
    },
    {
      "id": "cloud_total",
      "name": "Cloud Cover (Total)",
      "unit": "%",
      "format_modes": ["raw", "symbol"],
      "default_format_mode": "symbol"
    },
    {
      "id": "sunshine",
      "name": "Sunshine",
      "unit": "hours",
      "format_modes": ["raw", "symbol"],
      "default_format_mode": "symbol"
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| metrics[] | array | List of available metrics (only selectable ones — meta-metrics like `confidence` and `cape` (#1585) are excluded) |
| metrics[].id | string | Metric identifier (e.g., `wind_direction`, `cloud_total`) |
| metrics[].name | string | Human-readable metric name |
| metrics[].unit | string | Unit of measurement |
| metrics[].format_modes | string[] | Supported format modes for this metric (`raw`, `scale`, `simplified`, `symbol`) |
| metrics[].default_format_mode | string | Recommended default format mode (must be in `format_modes`) |
| metrics[].selectable | bool | Whether this metric appears in the user-facing selector (Wizard/Editor). Backend internal metrics have `selectable=false`: `confidence` (Issue #710) and, since 2026-08-10, `cape` (Issue #1585, precedent-following the confidence pattern per ADR-0005) — these are never returned by `/api/metrics` but used internally for aggregation/forecast-hints resp. thunderstorm-level fusion (UI-Auswahl heißt heute Editor-Metrik-Auswahl, kein Wizard) |
| metrics[].trip_default_enabled | bool | **Neu Issue #1552.** Ob die Größe zur Vorbelegung eines **neu angelegten Trips** gehört — unabhängig von `default_enabled` (das weiterhin die Orte-/Abonnement-Konfiguration über `build_default_display_config()` versorgt; vor #1552 zeigte der Anlege-Dialog `default_enabled` als Vorbelegung an, während der Versand eines nie eingestellten Trips tatsächlich einem anderen Siebener-Satz folgte — Überschneidung nur 5 von 10). Quelle: `MetricDefinition.trip_default_rank is not None` (`metric_catalog.py`). **Seit Issue #1728 Scheibe 1 (2026-08-15) tragen neun statt sieben Größen einen Rang:** `temperature`(1), `wind`(2), `gust`(3), `precipitation`(4), `thunder`(5), `freezing_level`(6), `visibility`(7), `temperature_day_low`(8), `temperature_day_high`(9) — die beiden neuen Ränge sind angehängt, die ursprünglichen sieben unverändert. `wind_chill_day_low`/`wind_chill_day_high` bekommen bewusst **keinen** Rang (folgen der Lage von `wind_chill` selbst, das ebenfalls keinen Rang trägt) — dieselbe Rangfolge, aus der `DEFAULT_TRIP_METRIC_IDS` (`src/output/renderers/trip_metric_ids.py`) abgeleitet wird, statt sie hart zu listen |
| metrics[].sms_code | string | GSM-7-safe short token for the metric in SMS/Subject/Telegram alert tokens (e.g., `W`, `G`, `R`, `PR`, `TH`, `CP`, `SL`, `VS`, `HU`). Single source for alert renderers (Issue #914 Slice 1); the metric catalog is the only place these are defined |
| metrics[].decimals | int \| null | Rounding precision for display (e.g., `precipitation: 1`, `visibility: 1`, most metrics `0`). `null` ⇒ fall back to the unit-based heuristic in `format_metric_value()` |
| metrics[].aggregations | `{id, label, alert_metric}[]` | **Neu Issue #1357, `alert_metric` neu #1435 E1a:** die für diese Größe tatsächlich berechenbaren Tagesauswertungen in fester Reihenfolge (`min`, `max`, `avg`, `sum`), mit deutschem Label. Quelle: `metric_catalog.available_aggregations()`/`aggregation_label_de()` über `MetricDefinition.summary_fields` — **nicht** `default_aggregations` (verspricht bei `snowfall_limit`/`freezing_level` mehr, als berechenbar ist). Weniger als zwei Einträge ⇒ der Editor zeigt keine Auswahl (kein wirkungsloses Bedienelement) |
| metrics[].aggregations[].alert_metric | string \| null | **Neu #1435 E1a.** Die absolute Alarm-Identität DIESER Auswertung (`MetricDefinition.alert_metrics.get(aggregation_id)`), `null` wenn diese Auswertung keinen eigenen Alarm auslöst. Bewusst **ohne** den `change_alert_metric`-Rückfall aus `alert_metric_for()` — der gehört zur Größe als Ganzes, nicht zu einer einzelnen Auswertung, und steht als eigenes Feld (`metrics[].change_alert_metric`) daneben. Beispiel (Staging verifiziert): `gust.aggregations` → `{id: "max", alert_metric: "wind_gust"}`; `wind.aggregations` → `{id: "max", alert_metric: null}` (Wind selbst hat keinen absoluten Alarm, nur den Änderungs-Alarm über `change_alert_metric`) |
| metrics[].change_alert_metric | string \| null | **Neu #1435 E1a.** Der Änderungsraten-Alarm der Größe (`MetricDefinition.change_alert_metric`), `null` wenn die Größe keinen kennt. Orthogonal zu `aggregations[].alert_metric` — Änderungsraten sind keine Auswertung, sondern an die Größe als Ganzes gekoppelt (analog `default_change_threshold`). Beispiele (Staging verifiziert): `temperature.change_alert_metric = "temperature_change"`, `wind.change_alert_metric = "wind_change"`, `humidity.change_alert_metric = null` (Luftfeuchtigkeit ist bewusst nicht alarmfähig, Issue #889/ADR-0010 — die Auswertungskette `weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID` kennt `AlertMetric.HUMIDITY` nicht) |
| metrics[].cmp | string | Comparison direction: `"über"` or `"unter"`. Single source for the direction/arrow used by deviation and absolute alert detection (Issue #914 Slice 1) — replaces the former hand-coded `_ALERT_METRIC_COMPARISON` dict. **Not** a threshold comparator for the deviation-alert (live) path: per ADR-0013, an event triggers there when `abs(value_to − value_from) ≥ threshold` regardless of `cmp`; `cmp` remains a literal exceeds/falls-below comparator only for `ABSOLUTE`-kind rules (`_detect_absolute_changes()`), which is unused in the send path (`include_absolute=False`) |

**Format Mode Reference:**

| Mode | Description | Example Metrics |
|------|-------------|-----------------|
| `raw` | Numeric value with unit | `temperature: 18.5°C`, `wind: 22 km/h` |
| `scale` | Categorized scale representation | `wind_direction: N (345°)` as compass point |
| `simplified` | Adjective shorthand without value | `wind: schwach`, `precipitation: mäßig` |
| `symbol` | Emoji or icon representation | `cloud_total: ☁️`, `sunshine: ☀️` |

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 503 | `{"error":"service_unavailable"}` | Metric catalog not initialized |

**Notes:**

- Frontend uses `format_modes` to filter dropdown options in der Metrik-Auswahl der Editoren (WeatherMetricsTab, WeatherConfigDialog)
- `MetricConfig.format_mode` in persisted configs (e.g., `trips.json`, `locations.json`) refers to one of the values in the corresponding metric's `format_modes` array
- Legacy code may use `MetricConfig.use_friendly_format` (deprecated boolean) — loader automatically maps to `format_mode` for backward compatibility
- **Confidence (`confidence`) is NOT a selectable per-stage weather metric** (Issue #710): Forecast reliability is a meta-attribute (Ensemble API, multi-day validity) and appears only as forecast-reliability hints in email/SMS output (e.g., "From Wednesday, forecast confidence is lower") and as SMS icon indicators. The metric definition exists internally for aggregation/scoring but is marked `selectable=false` and filtered from `/api/metrics` — **never appears in Trip Editor/Wizard/Metric Selector UI, even for legacy trips with saved `confidence` metric configs** (configs load silently, metric ignored in render paths). This rule (since 2026-06-10) prevents the metric from re-appearing across future versions.

- **Severity-Schwellen (Issue #814):** Die HTML-Ampel (🟢🟡🟠🔴) der Severity-Metriken nutzt die bestehenden `display_thresholds` des Katalogs (`{"yellow": N, "orange": M, "red": K}`). #814 setzt CAPE auf die Standard-Konvektionsskala `{"yellow": 1000, "orange": 2500, "red": 3500}` (J/kg); wind/gust/precip/pop bleiben unverändert. Welche Metriken überhaupt einen Ampelpunkt bekommen, ist in `src/output/renderers/email/helpers.py` über das frozenset `_AMPEL_CAPABLE_METRIC_IDS` = {wind, gust, precipitation, rain_probability, cape} festgelegt — der Ampel-Indikator wird pro Spalte aus `use_friendly_format` via `build_html_indicator_keys()` abgeleitet (nur HTML-Einfach).
  - Der **Roh/Einfach-Umschalter im Trip-Editor** wird NICHT vom Backend-Feld `has_friendly_format` gesteuert, sondern frontend-seitig über die `INDICATOR_MAP` in `frontend/src/lib/components/trip-detail/metricsEditor.ts` (seit #814: `visibility` entfernt, `precipitation` ergänzt).

- **Metric Display Contract (Issue #814):** Der vollständige Einfach/Roh-Vertrag aller Metriken ist nun kodifiziert in `docs/reference/renderer_email_spec.md` § „Metric Display Contract". `use_friendly_format=true` → HTML-Ampelpunkte für Severity-Metriken (**seit #1491 auch für Gewitter** — kein ⚡-Symbol mehr in der Spalte), Emojis für Wetterbild-Piktogramme; `use_friendly_format=false` → nackte Zahlen überall, keine Ampel-Emojis/-Punkte. Plain-Text immer numerisch (außer Gewitter = deutsches Wort). **Zell-Tönung (`cell_bg`) gilt IMMER** — unabhängig von Roh/Einfach-Modus (#911, PO-approved; Doku-Abgleich #985/#1198): Roh-Zellen werden bei Schwellwert-Überschreitung getönt (Ampel-Zellen nach Katalog-Ampel-Level, Roh-Modus nach den Legacy-Schwellen aus #888). Nie gewollt und weiterhin ausgeschlossen sind inline-**Highlights** (`highlight_color`, z.B. Gelb bei CAPE).

- **Alarmfähigkeit ist jetzt eine Registereigenschaft (Issue #1435 Etappe E1a-1):** `alert_metric`/`change_alert_metric` beantworten „kann diese Größe (bzw. diese Auswertung dieser Größe) einen Alarm auslösen?" zentral über `metric_catalog.alert_metric_for(metric_id, aggregation)`. Vorher gab es dafür drei unabhängige, teils widersprüchliche Antworten (`compare_alert.py` 10 Größen, `compareMetricMapping.ts` 6 Größen — eine davon kreuzverdrahtet —, `alertMetricTable.ts` 13 Größen). Der Resolver registriert eine Identität nur, wenn `weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID` sie tatsächlich auswerten kann (Epic #1374 Invariante 1, „kein Element ohne Wirkung") — deshalb bleibt `humidity.change_alert_metric = null`, obwohl Luftfeuchtigkeit sonst wie eine alarmfähige Größe aussieht. `compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` bleibt das tatsächlich alarmauslösende Modul und ist von dieser Etappe unverändert. Details: `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md`.

---

## 15.1) Compare-Metrik-Katalog-Endpoint (Issue #1350, Teil 1)

Read-only Backend-Katalog der 26 Ortsvergleich-Metriken (Label/Einheit/
Wertebereich/`higherIsBetter`/Ordinal-/Enum-Angaben), aus einer einzigen
Backend-Quelle. **Teil 1 der Strangler-Migration:** der Endpoint wird nur
bereitgestellt, das Frontend konsumiert ihn noch nicht (weiterhin
`compareMetricDefs.ts::ALL_METRICS`) — keine sichtbare Änderung im
Ortsvergleich-Editor. (Ursprünglich 25 Einträge bei Einführung 2026-07-23;
seit 2026-07-24 26 Einträge durch den neuen `wind_chill_max_c`-Eintrag,
Issue #1351 Teil 1.)

**Handler:** `api/routers/compare.py` | **Datenquelle:**
`src/output/renderers/compare_metric_catalog.py` | **Routing:**
`internal/router/router.go` (generischer `ProxyHandler`, kein `user_id`-Bezug)

### GET /api/compare/metrics

Kein Query-Parameter. Antwort: `{"metrics": [...]}`, genau 26 Einträge,
Reihenfolge deckungsgleich mit `ALL_METRICS` im Frontend.

**Response 200:**

```json
{
  "metrics": [
    {
      "key": "snow_depth_cm",
      "label": "Schneehöhe",
      "unit": "cm",
      "decimals": 0,
      "higherIsBetter": true,
      "kind": "range",
      "rangeMin": 0,
      "rangeMax": 200,
      "step": 5,
      "metric_id": "snow_depth",
      "aggregation": "max",
      "alertMetric": null,
      "alarmCapable": false
    },
    {
      "key": "thunder_level_max",
      "label": "Gewitter",
      "unit": "",
      "decimals": 0,
      "higherIsBetter": false,
      "kind": "ordinal",
      "ordinalLabels": ["kein", "mittel", "hoch"],
      "metric_id": "thunder",
      "aggregation": "max",
      "alertMetric": "thunder_level",
      "alarmCapable": true
    },
    {
      "key": "precip_type_dominant",
      "label": "Niederschlagsart",
      "unit": "",
      "decimals": 0,
      "higherIsBetter": false,
      "kind": "enum",
      "enumValues": ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"],
      "metric_id": "precip_type",
      "aggregation": "max",
      "alertMetric": null,
      "alarmCapable": false
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| metrics[].key | string | Identisch zu `compare_metric_ids.FRONTEND_TO_RENDERER_METRIC_ID`-Keys (keine sechste Kopie der Keyliste) |
| metrics[].kind | string | `range` (23 Einträge, mit `rangeMin`/`rangeMax`/`step`), `enum` (`precip_type_dominant`, mit `enumValues`) oder `ordinal` (`thunder_level_max`, mit `ordinalLabels` — übernimmt die im Editor tatsächlich sichtbare 3-Stufen-Darstellung statt des rohen Enum, PO-Entscheidung 2026-07-12) |
| metrics[].higherIsBetter | bool | Richtung für die Compare-Winner-Box (`true` = höherer Wert gewinnt) |
| metrics[].alertMetric | string \| null | **Neu #1435 E1a-1.** Die Alarm-Identität des Paares (Größe, Auswertung), aufgelöst über `metric_catalog.alert_metric_for(metric_id, aggregation)` — `null`, wenn diese Zeile keinen Alarm auslösen kann. Steht an **allen 26** Einträgen, auch den nicht alarmfähigen (dort `null`). Ersetzt die vorherige, unabhängig gepflegte Herkunft von `alarmCapable` |
| metrics[].alarmCapable | bool | Seit Teil 3 (#1350). Ab #1435 E1a-1 die **Boolean-Sicht auf `alertMetric`** (`alertMetric is not None`), nicht mehr eine zweite, handgepflegte Liste — steuert unverändert die „Warnen"-Button-Sperre im Schwellen-Editor. Die Menge ist verhaltensneutral identisch geblieben: genau dieselben 10 Keys wie zuvor aus `compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` (nachgewiesen in `tests/unit/test_alert_metric_identity_delivery.py`); `compare_alert.py` bleibt das tatsächlich alarmauslösende Modul und ist von dieser Etappe unverändert |
| metrics[].metric_id | string | Seit Issue #1373 S2 Scheibe A. Kennung der zugrundeliegenden Größe im zentralen Wetterkatalog (`src/app/metric_catalog.py`), z. B. `"temperature"` |
| metrics[].aggregation | string | Seit Issue #1373 S2 Scheibe A. Die Auswertung dieser Größe, die der Eintrag zeigt (`min`/`max`/`avg`/`sum`), z. B. `"max"` |

Jeder Compare-Eintrag ist damit nachweisbar an eine Größe des zentralen
Wetterkatalogs gebunden — der Katalog bleibt jedoch eine **kuratierte**
Tabelle (Label/Wertebereich/Bedienstruktur bleiben redaktionell gepflegt in
`src/output/renderers/compare_metric_catalog.py`); `metric_id`/`aggregation`
werden nicht **daraus erzeugt**, sondern nur **gegen** ihn geprüft. Drei
Tests in `tests/unit/test_compare_catalog_derives_from_central_catalog.py`
stellen sicher: (a) jede wählbare Größe des zentralen Katalogs hat
mindestens einen Compare-Eintrag, (b) jeder Compare-Eintrag verweist auf
eine tatsächlich existierende zentrale Größe, (c) die angegebene
`aggregation` ist eine der zentral vorgesehenen Auswertungen dieser Größe.
Die benannte Ausnahmeliste (`AGGREGATION_CHECK_EXEMPTIONS`) ist seit
2026-07-26 **leer**: die vier ehemals ausgenommenen Größen haben ihr
Tages-Auswertungsfeld bekommen — `cloud_low`/`cloud_mid`/`cloud_high` über
neue `SegmentWeatherSummary`-Felder (#1392), `snowfall_limit` über den
korrigierten Katalogeintrag samt Befüllung im Trip-Pfad (#1391). Die Liste
darf nur schrumpfen — ein eigener Test erzwingt das, und er hat gehalten.

**Notes:**

- Additiv, rein lesend, keine Persistenz-/Render-/Frontend-Änderung. Keine
  Auswirkung auf `active_metrics`/`corridors`-Persistenz oder
  `resolve_enabled_metrics()` durch DIESEN Endpoint selbst. Die
  `metric_id`/`aggregation`-Herkunftsfelder, die er hier zusätzlich liefert,
  sind aber die Grundlage des Umkehr-Index, über den die Folgelieferung
  Scheibe B (#1373, s. `active_metrics` in Section 16) das
  Persistenzformat der Metrik-Auswahl umstellt.
- `precip_type_dominant` bleibt `enum`, obwohl der Corridor-Editor es intern
  über den generischen `range`-Zweig rendert (bestehende Frontend-Eigenart,
  nicht Teil dieses Endpoints).
- Seit Teil 3 (#1350, `compare_metric_ssot_final.md`) ist dieser Endpoint die
  einzige verbleibende Quelle für den Schwellen-Editor des Ortsvergleichs
  (`corridorEditorState.ts`) — `compareMetricDefs.ts` existiert nicht mehr.
- **Seit #1435 E1a-1** kommt `alarmCapable` nicht mehr aus der eigenen
  `_SUMMARY_KEY_TO_CATALOG_ID.keys()`-Prüfung dieses Moduls, sondern aus dem
  zentralen Register (`alertMetric is not None`) — s. Feldtabelle oben und
  `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md`. Das
  Ergebnis ist unverändert (dieselben 10 Keys); der `_SUMMARY_KEY_TO_CATALOG_ID`-Import
  bleibt als eigener Subset-Drift-Guard bestehen.

---

## 15.5) MetricPreset CRUD Endpoints (Issue #690)

Manages persisted custom weather metric profiles (user's own presets for metric selection, format modes, and horizons).

**Handler:** `internal/handler/metric_preset.go` | **Storage:** `data/users/{userID}/metric_presets.json` | **Routing:** `internal/router/router.go`

### MetricPreset DTO

```go
type MetricPreset struct {
    ID          string           `json:"id"`                      // "p-{hex}", auto-generated
    Name        string           `json:"name"`                    // User-chosen name, unique per user (case-insensitive, trimmed)
    Description string           `json:"description,omitempty"`   // Optional user notes
    IsDefault   bool             `json:"is_default"`              // Exactly one per user is marked as default
    Metrics     []DisplayMetric  `json:"metrics"`                 // List of selected metrics with horizons + format modes
    CreatedAt   time.Time        `json:"created_at"`              // Server-managed creation timestamp (UTC)
}
```

**DisplayMetric** (per-metric config within preset):

```go
type DisplayMetric struct {
    MetricID          string   `json:"metric_id"`            // e.g., "temperature", "wind_direction"
    Enabled           bool     `json:"enabled"`              // Include in preset
    UseFriendlyFormat bool     `json:"use_friendly_format"`  // Applies friendly format mode if available
    Horizons          Horizons `json:"horizons"`             // Which forecast days to show
}

type Horizons struct {
    Today     bool `json:"today"`
    Tomorrow  bool `json:"tomorrow"`
    DayAfter  bool `json:"day_after"`
}
```

### GET /api/metric-presets

Returns all metric presets for the authenticated user.

**Response 200:**

```json
{
  "presets": [
    {
      "id": "p-a1b2c3d4",
      "name": "Bergtour",
      "description": "Alpine with wind focus",
      "is_default": false,
      "metrics": [
        {
          "metric_id": "temperature",
          "enabled": true,
          "use_friendly_format": false,
          "horizons": {"today": true, "tomorrow": true, "day_after": false}
        },
        {
          "metric_id": "wind_direction",
          "enabled": true,
          "use_friendly_format": true,
          "horizons": {"today": true, "tomorrow": true, "day_after": true}
        }
      ],
      "created_at": "2026-06-10T14:32:45Z"
    }
  ]
}
```

**Notes:**
- Includes both built-in system presets (if exposed in future) and user's own custom presets
- User is identified from Auth-Context (user_id); presets from other users are never returned

### POST /api/metric-presets

Creates a new custom metric preset for the authenticated user.

**Request Body:**

```json
{
  "name": "Bergtour",
  "description": "Alpine with wind focus",
  "is_default": false,
  "metrics": [
    {
      "metric_id": "temperature",
      "enabled": true,
      "use_friendly_format": false,
      "horizons": {"today": true, "tomorrow": true, "day_after": false}
    },
    {
      "metric_id": "wind_direction",
      "enabled": true,
      "use_friendly_format": true,
      "horizons": {"today": true, "tomorrow": true, "day_after": true}
    }
  ],
  "friendly_ids": []
}
```

**Field Definitions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Preset name; must be unique per user (case-insensitive match, leading/trailing whitespace trimmed); max 100 chars |
| description | string | No | Optional user notes |
| is_default | boolean | Yes | If `true`, all other presets for this user are set to `is_default=false` (exactly one default per user) |
| metrics | array | Yes | List of metric configurations with horizons |
| friendly_ids | array | No | Legacy field (deprecated); ignored if `metrics` is properly structured |

**Response 201 (Created):**

```json
{
  "id": "p-a1b2c3d4",
  "name": "Bergtour",
  "description": "Alpine with wind focus",
  "is_default": false,
  "metrics": [...],
  "created_at": "2026-06-10T14:32:45Z"
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"name_required"}` | `name` is empty or contains only whitespace |
| 400 | `{"error":"bad_request"}` | Request body is malformed JSON |
| 409 | `{"error":"name_exists"}` | A preset with this name (case-insensitive) already exists for this user |
| 500 | `{"error":"store_error"}` | Internal storage error |

**Notes:**
- User ID is extracted from Auth-Context; no `user_id` field is accepted in the request
- Name is trimmed and case-insensitive for uniqueness comparison (Issue #690)
- Newly created preset becomes immediately active on the trip if workflow so directs (frontend responsibility)
- If `is_default=true` and multiple presets exist, server atomically ensures exactly one default

### DELETE /api/metric-presets/{id}

Deletes a metric preset (must belong to authenticated user).

**Response 204 (No Content):** Preset deleted successfully.

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 404 | `{"error":"not_found"}` | Preset does not exist or belongs to a different user |
| 500 | `{"error":"store_error"}` | Internal storage error |

### PATCH /api/metric-presets/{id}

Updates selected fields of a metric preset (name, description, metrics, is_default).

**Request Body (partial update):**

```json
{
  "name": "Bergtour Updated",
  "description": "Alpine with focus on wind and precipitation",
  "metrics": [...]
}
```

**Response 200:**

```json
{
  "id": "p-a1b2c3d4",
  "name": "Bergtour Updated",
  ...
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"name_required"}` | Attempted to set name to empty/whitespace only |
| 404 | `{"error":"not_found"}` | Preset does not exist or belongs to a different user |
| 409 | `{"error":"name_exists"}` | New name already exists for this user (case-insensitive) |
| 500 | `{"error":"store_error"}` | Internal storage error |

---

## 16) ComparePreset CRUD Endpoints (Issue #458)

Manages persisted Compare-Preset configurations for automatic, multi-location comparison reports (foundation for Epic #456 — Auto-Briefings).

**Handler:** `internal/handler/compare_preset.go` | **Storage:** `data/users/{userID}/briefings/{id}.json` (per-Datei, `kind="vergleich"`; Legacy `data/users/{userID}/compare_presets.json` nur noch Migrations-Quelle/Rollback, Issue #1250 S7b) | **Routing:** `internal/router/router.go`

### ComparePreset DTO

```go
type ComparePreset struct {
    ID                   string                 `json:"id"`                                    // "cp-{hex}", auto-generated
    Name                 string                 `json:"name"`
    UserID               string                 `json:"user_id"`                               // set from Auth-Context, server-managed
    LocationIDs          []string               `json:"location_ids"`                          // 2+ locations to compare
    Schedule             string                 `json:"schedule"`                              // DEPRECATED für Zeitplan-Zwecke (Issue #1232 Scheibe 2a): trägt nur noch Pause-Semantik — "manual" = pausiert, jeder andere Wert ("daily"|"weekly"|Altdaten wie "daily_morning"/"daily_evening") = aktiv. Der tatsächliche Rhythmus kommt aus den Slot-Feldern unten.
    PreviousSchedule     string                 `json:"previous_schedule,omitempty"`           // schedule saved before pause (Issue #631, server-managed)
    Profil               string                 `json:"profil"`                                // ActivityProfile: WINTERSPORT|ALPINE_TOURING|SUMMER_TREKKING|ALLGEMEIN
    HourFrom             int                    `json:"hour_from"`                             // @deprecated Issue #1268: nicht mehr vom Dispatch/Editor gelesen; bleibt in der Persistenz zur Bestandssicherung. Neue Presets erhalten 0 (Go Zero-Value). Der Versand rechnet fest über den ganzen Tag (0–23).
    HourTo               int                    `json:"hour_to"`                               // @deprecated Issue #1268: nicht mehr vom Dispatch/Editor gelesen; bleibt in der Persistenz zur Bestandssicherung. Der Versand rechnet fest über den ganzen Tag (0–23).
    ForecastHours        int                    `json:"forecast_hours"`                        // @deprecated Issue #1268: nicht mehr vom Dispatch gelesen; bleibt in der Persistenz zur Bestandssicherung. Der Dispatch verwendet fest 96 h (Issue #1305, zuvor 48 h). Legacy-Erklärung: 24 | 48 | 72 — Vorhersage-Horizont für Compare-Versand (Issue #764, default 48)
    Empfaenger           []string               `json:"empfaenger"`                            // @deprecated Issue #1452 (2026-08-02): inert für den Versand — bleibt persistiert (Read-Modify-Write-Pflicht, Bestandsschutz), wird aber weder von den drei Alert-Services noch vom regulären Compare-Dispatch mehr gelesen. Einzige Empfänger-Quelle ist seither `Settings().with_user_profile(user_id)` (`mail_to`/`telegram_chat_id`/`sms_to`), analog `trip_alert.py:125`.
    LetzterVersand       *time.Time             `json:"letzter_versand,omitempty"`             // last send timestamp (server-managed)
    TopOrtLetzterVersand *string                `json:"top_ort_letzter_versand,omitempty"`     // highest-ranked location from last send (server-managed)
    DisplayConfig        map[string]interface{} `json:"display_config,omitempty"`              // opaque config (Issue #680: active_metrics, ideal_ranges, etc.)
    HourlyEnabled        *bool                  `json:"hourly_enabled,omitempty"`              // Issue #1107, Pointer-Muster analog OfficialAlertsEnabled (#1040): nil/true = Stundenverlauf-Sektion sichtbar (Default), false = komplett weggelassen (Mail behält Übersichtstabelle). Seit Issue #1299 (C2 von Epic #1301) im Hub-Layout-Tab (`CompareTabs.svelte`, `activeTab==="layout"`) bedienbar — vorher nur über den seit S3 weggeleiteten Legacy-`CompareEditor` erreichbar.
    OutlookEnabled       *bool                  `json:"outlook_enabled,omitempty"`             // Issue #1361/#1368 (S3 Scheibe A von Epic #1372, 2026-07-27), Pointer-Muster wie HourlyEnabled: nil/true = 3-Tages-Ausblick je Ort gerendert (Python-Default true, `report_config_resolver.py`), false = komplett weggelassen. Feld fehlte bis dahin im Struct — ein PUT verlor den Wert beim Decode still (nil-Preserve-Block in `internal/handler/compare_preset.go` analog `HourlyEnabled`). Bedienbar in `CompareOutlookLayoutControls.svelte` (Wetter-Metriken-Reiter, `context="vergleich"`).
    MorningEnabled       *bool                  `json:"morning_enabled,omitempty"`             // Issue #1232 Scheibe 2a: Zwei-Slot-Zeitplan analog Trip. nil = Altdaten vor Migration (Load-Migration setzt echten Wert), sonst true/false
    MorningTime          *string                `json:"morning_time,omitempty"`                // "HH:MM:SS", Fälligkeits-Check nur auf volle Stunde (Minuten ignoriert, KL-2)
    EveningEnabled       *bool                  `json:"evening_enabled,omitempty"`             // wie MorningEnabled, für den Abend-Slot
    EveningTime          *string                `json:"evening_time,omitempty"`                // "HH:MM:SS"; Abend-Versand zielt auf target_date = morgen (Ankündigungs-Charakter, wie Trip-Abendbriefing)
    EndDate              *string                `json:"end_date,omitempty"`                    // "YYYY-MM-DD", nil = unbegrenzte Laufzeit; gesetzt+<heute (Europe/Vienna) = Versand-Guard greift. Bekannte Lücke: kann per PUT nicht auf nil zurückgesetzt werden (KL-7, Sammel-Issue #1199)
    Corridors            []Corridor             `json:"corridors"`                             // Issue #1231 Slice 1, additiv neben display_config["ideal_ranges"] — s. Section 24
    OfficialAlertTriggersEnabled *bool          `json:"official_alert_triggers_enabled,omitempty"` // @deprecated (Issue #1258, ersetzt durch official_warnings.enabled) — bleibt in den Daten fuer Rollback-Sicherheit
    OfficialWarnings     *OfficialWarningsConfig `json:"official_warnings,omitempty"`           // Issue #1258, identische Semantik wie Trip — s. Section 10.5 „official_warnings (Issue #1258)"
    Weekday              *int                   `json:"weekday,omitempty"`                     // 0=Mo…6=So; DEPRECATED seit #1232 (Wochenrhythmus entfällt) — nur Altdaten-Träger
    PausedAt             *time.Time             `json:"paused_at,omitempty"`                   // Issue #1250 Scheibe 2: aus schedule=="manual" abgeleitet (Dual-Write); nil = nicht pausiert
    ArchivedAt           *time.Time             `json:"archived_at,omitempty"`                 // Issue #611: nil = aktiv, gesetzt = archiviert
    OfficialAlertsEnabled *bool                 `json:"official_alerts_enabled,omitempty"`     // Issue #1040: nil/true = amtliche Quellen abgefragt (Default), false = kein Fetch
    RadarAlertEnabled    *bool                  `json:"radar_alert_enabled,omitempty"`         // Issue #1041 Slice 1b: UMGEKEHRTER Default — nil/fehlend = AUS (opt-in, Netzwerkkosten je Ort)
    AlertCooldownMinutes *int                   `json:"alert_cooldown_minutes,omitempty"`      // Issue #1170: nil = Default in compare_alert.py
    AlertQuietFrom       *string                `json:"alert_quiet_from,omitempty"`            // Issue #1170
    AlertQuietTo         *string                `json:"alert_quiet_to,omitempty"`              // Issue #1170
    SendTelegram         *bool                  `json:"send_telegram,omitempty"`               // Issue #1216 Slice 2b: Alarm-Kanal-Opt-in (Default falsy = E-Mail-only)
    SendSms              *bool                  `json:"send_sms,omitempty"`                    // Issue #1216 Slice 2b
    SendPremiumSms       *bool                  `json:"send_premium_sms,omitempty"`            // Issue #1701 S2b (D8): eigenes Feld statt alert_channels-Sub-Objekt (Ortsvergleich hat keins)
    Kind                 string                 `json:"kind,omitempty"`                        // ADR-0023-Diskriminator ("vergleich"); nur Migration schreibt ihn
    CreatedAt            time.Time              `json:"created_at"`
}
```

**Invariante — nie `null` (Issue #1244):** `Corridors`, `LocationIDs` und `Empfaenger` sind
immer als `[]` serialisiert, niemals als `null` — Datei und HTTP-Response gleichermaßen.
Durchgesetzt von `NormalizeComparePreset()` (`internal/store/compare_preset.go`), aufgerufen
sowohl aus dem Schreibpfad (`SaveComparePresets`) als auch aus dem Lesepfad
(`LoadComparePresets`) sowie direkt aus dem Handler, wenn ein frisch erstelltes/aktualisiertes
Preset in der HTTP-Response gespiegelt wird. Bestandsdaten: `scripts/migrate_1244_null_lists.py`.

**Vollständigkeit (seit 2026-07-22, #1342):** Diese Struct-Auflistung ist vollständig gegen
`internal/model/compare_preset.go` abgeglichen und wird durch den Drift-Test
`tests/test_api_contract_drift.py` abgesichert — jedes neue JSON-Tag im Go-Struct macht den
Test rot, bis die Doku nachgezogen ist.

**Zwei-Slot-Zeitplan (Issue #1232 Scheibe 2a, additiv zu `schedule`):** Analog zum Trip-Briefing
(Morgen/Abend) trägt `ComparePreset` jetzt einen eigenen Zeitplan statt eines groben
`daily`/`weekly`-Rhythmus. `schedule` bleibt als reines Pause-Flag bestehen (`manual` = pausiert,
via `previous_schedule` reversibel — Issue #631, unverändert). Neue Presets erhalten per Default
`morning_enabled=true, morning_time="07:00:00", evening_enabled=false, evening_time="18:00:00",
end_date=nil`. Bestandspresets ohne diese Felder werden beim ersten Go-`LoadComparePresets`-Lauf
idempotent migriert (Default `morning_enabled=true, morning_time="06:00:00",
evening_enabled=false` — verhaltensidentisch zum vormaligen 06:00-Uhr-Cron; Presets mit dem
Alt-Wert `schedule="daily_evening"` migrieren stattdessen auf einen aktiven Abend-Slot, siehe
Details in `docs/specs/modules/compare_preset_zeitplan.md`). `weekday` gilt als deprecated
(Altdaten-Lesbarkeit, kein neuer Schreibpfad, kein Wochenrhythmus mehr — Presets mit
`schedule="weekly"` versenden seither täglich). Der stündliche Go-Cron `compare_presets_daily`
("Compare Presets Slot-Check (hourly)", vormals einmal täglich 06:00 UTC) prüft pro Preset, ob
die aktuelle Stunde **in der Ortszone dieses Presets** (erster auflösbarer Ort seiner
konfigurierten Reihenfolge, seit #1726; davor fest `Europe/Vienna`) mit
`morning_time`/`evening_time` übereinstimmt; Morgen-Slot
versendet für `target_date=heute`, Abend-Slot für `target_date=morgen`. Guards vor jedem Versand:
siehe `compare_alert_guard.is_silenced()` (Issue #1467 S2 AG6: `paused_at` gesetzt, `schedule=="manual"`,
oder `archived_at` gesetzt); zusätzlich `end_date` gesetzt und `< heute`.

**DisplayConfig Keys (Issue #680 onwards):**
- `active_metrics`: Ausgewählte Metriken für den Vergleich. **Speicherformat seit
  Issue #1373 S2 Scheibe B (2026-07-26):** eine Liste, deren Reihenfolge
  bedeutungstragend ist (Metrik-Reihenfolge, #1335/#1359), mit zwei gültigen
  Elementformen, die auch **gemischt in derselben Liste** vorkommen dürfen und
  pro Element aufgelöst werden:
  - **Neuformat (einzig geschriebenes Format ab dieser Lieferung):**
    `[{"metric_id": "temperature", "aggregation": "max"}, ...]` — Größe +
    Auswertung. Aufgelöst über den Umkehr-Index `key_for(metric_id,
    aggregation)` in `src/output/renderers/compare_metric_catalog.py`, der auf
    den `metric_id`/`aggregation`-Herkunftsfeldern des Vergleichs-Katalogs
    aufsetzt (Scheibe A, `373d3970`).
  - **Altformat (z.B. `["temp_max_c", "wind_max_kmh", "precip_sum_mm"]`):**
    Liste von Anzeige-Schlüsseln, wie vor dieser Lieferung. Wird **dauerhaft**
    weiter gelesen, seit dieser Lieferung aber **nie mehr geschrieben**.
    „Dauerhaft" statt nur übergangsweise bis zur Migration, weil eine im
    Browser stehengebliebene Sitzung mit altem Frontend-Code jederzeit wieder
    Altformat schreiben kann (Restrisiko R1,
    `feat_1373_s2b_metrik_speicherformat.md`) — der tolerante Leser ist daher
    fester Codebestandteil, keine befristete Übergangshilfe.
  - Leere Liste `[]` bleibt von einem fehlenden Feld unterscheidbar (#1191):
    `[]` = bewusst alles abgewählt, fehlendes Feld = Legacy-Fallback (s.u.).
    Dieses Verhalten ändert sich durch das neue Speicherformat nicht. **Seit
    Issue #1366 (S3 Scheibe B von Epic #1372, 2026-07-26)** gilt das
    einheitlich auch für den Render-/Übersichtspfad (`resolve_enabled_metrics()`
    unten) — vorher fiel dort `[]` fälschlich auf „alle" zurück. Eine
    Auswahl, die sich vollständig auf keine bekannte Renderer-ID abbilden
    lässt, verhält sich seither identisch zu einer bewussten Leerauswahl
    (`[]`), nicht mehr wie ein fehlendes Feld.
  - Zwei unabhängige Leser lösen pro Element auf: `resolve_enabled_metrics()`
    in `src/output/renderers/compare_metric_ids.py` (Render-/Übersichtspfad)
    und `_display_config_from_active_metrics()` in
    `src/services/compare_alert.py` (Δ-Alarm-Pfad, normalisiert Neuformat-
    Einträge vor der bestehenden `_SUMMARY_KEY_TO_CATALOG_ID`-Übersetzung).
  - Bestandsumstellung:
    `scripts/migrate_1373_compare_active_metrics_format.py` (Read-Modify-
    Write, tar.gz-Sicherung, idempotent — s.
    `docs/reference/operations_playbook.md`).
  - Spec: `docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md`.

  Default: Profil-spezifische Metriken aus `PROFILE_METRICS_WITH_SCALES`. Seit
  #1191 im Idealwerte-Tab um 4 weitere, bislang schalter-lose alarmfähige
  Metriken wählbar: `gust_max_kmh` (Böen), `cape_max_jkg`
  (Gewitter-Energie/CAPE), `freezing_level_m` (Nullgradgrenze), `temp_min_c`
  (Min-Temperatur). **Semantik für den Compare-Δ-Alarm (#1191):** Feld fehlt
  ganz (Key absent/`None`) = Legacy-Preset vor der Migration → konservativer
  Fallback, alle alarmfähigen Metriken feuern. Feld vorhanden — auch als leere
  Liste `[]` — = Nutzer hat im Editor bewusst (de-)aktiviert; nur gelistete
  Metriken feuern im Alarm, eine bewusst leere Liste unterdrückt sämtliche
  Compare-Δ-Alarme. Übersetzung Summary-Key → Alarm-Katalog-ID:
  `src/services/compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID`. **Schreiber
  seit #1311 (C1 von Epic #1301):** Der neue geteilte Hub-Tab
  „Wetter-Metriken" (`frontend/src/lib/components/shared/WeatherMetricsTab.svelte`,
  `context="vergleich"`) ist jetzt die EXKLUSIVE Schreib-Quelle für
  `active_metrics`. Das `notify`-Häkchen der Korridore im Wertebereiche-Tab
  schreibt `active_metrics` seither NICHT mehr
  (`corridorEditorState.ts::buildCompareCorridorSavePayload`) — es steuert nur
  noch `metric_alert_levels` (Alarm-Schwelle je Metrik), unverändert. Die
  Legacy-Semantik (absent = alle alarmfähigen feuern) bleibt davon unberührt.
- `ideal_ranges`: `Record<string, IdealRange>` — Min/Max-Idealwerte pro Metrik (z.B. `{"temp_max_c": {"min": 15, "max": 35}, ...}`). Wird vom Compare-Engine zur Bewertung verwendet.
- `hourly_metrics`: `string[]` — Ausgewählte Größen für die STUNDEN-Sektion der Vergleichs-Mail. **Seit Issue #1406 Scheibe B (E2 von #1435, 2026-08-01):** kein eigenständiges Compare-Vokabular mehr — der Vorrat ist der zentrale Wetterkatalog (`src/app/metric_catalog.py`, 24 wählbare Größen; 22 davon bekommen eine Wert-Spalte, s.u.). **Geschrieben werden Katalog-IDs** (`"temperature"`, `"humidity"`, …). **Gelesen wird dauerhaft beides:** die zehn historischen Kurzschlüssel (`temp_c`, `wind_chill_c`, `wind_kmh`, `gust_kmh`, `precip_mm`, `uv_index`, `thunder_level`, `pop_pct`, `visibility_m`, `wind_dir_deg`) bleiben als Lese-Alias bestehen — keine Migration, kein Datenumbau. Einzige Auflösungsquelle: `src/output/renderers/compare_hourly_metric_ids.py` (`FRONTEND_TO_HOURLY_METRIC_ID` = Alias-Tabelle, `resolve_hourly_metrics()` = Auflösung nach `dp_field`); die früheren Frontend-Module `compareHourlyMetricDefs.ts::ALL_HOURLY_METRICS` und `compareHourlyCatalogIds.ts` sind ersatzlos entfallen, die Bedienfläche speist sich aus derselben Katalogantwort wie Übersicht und Ausblick (`GET /api/compare/metrics`). **Zwei benannte Ausnahmen** ohne eigene Spalte: `wind_direction` (reines Merge-Signal, wandert als Kompasstext in die Wind-Zelle) und `sunshine` (`HOURLY_EXCLUDED_METRIC_IDS`, AC-11 — stündlich nur als Einstrahlung in W/m² verfügbar; die Katalogantwort meldet das als `hourlySelectable=false` samt Begründung). **Key absent/`None` heißt seit #1406 B nicht mehr „alle Spalten", sondern die ausgesprochene Vorgabemenge der neun historischen Spalten** (`HOURLY_DEFAULT_METRIC_IDS`: Temp, Feels, Wind, Gust, Rain, UV, Thdr, Rain%, Visib) — sonst spränge jeder nie eingestellte Vergleich ungefragt von 9 auf 22 Spalten. **Seit Issue #1366 + #1361 Befund 3 (S3 Scheibe B von Epic #1372, 2026-07-26):** Key absent = Default „alle sichtbar" (Legacy-Fallback); Feld vorhanden und `[]` (bewusst leer) oder vollständig unauflösbar = „keine Spalten" — der Stundenverlauf-Block entfällt dafür ganz (nicht nur die Uhrzeit-Spalte übrig), weil der Resolver diesen Fall zusätzlich auf `hourly_enabled=False` abbildet. Eine Leerauswahl im UI wird seither unbedingt als `[]` gesendet, der Key wird beim Speichern nicht mehr weggelassen (vorher: „leer/absent → alle sichtbar", `buildComparePresetSavePayload`/`buildNewComparePresetPayload` in `compareEditorSave.ts`). Details: `docs/specs/modules/compare_empty_metric_selection.md`. **Schreiber seit Issue #1299 (C2 von Epic #1301):** bedienbar im Hub-Layout-Tab (`CompareTabs.svelte`, `activeTab==="layout"`, `flushPendingLayoutSave`/`hydrateLayoutFieldsFromPreset`/`rollbackLayoutSnapshot` in `compareHubWizardBridge.ts`, Muster wie die C1-Wetter-Metriken-Bridge). Vorher nur über den seit S3 weggeleiteten Legacy-`CompareEditor` (`CompareInhaltSection.svelte`) erreichbar.
- `outlook_metrics`: **Neuformat**, ausschließlich `[{"metric_id": "temperature", "aggregation": "max"}, ...]` — dieselbe Elementform wie `active_metrics` seit #1373, KEIN Altformat, kein viertes Vokabular. Ausgewählte Größen für den 3-TAGES-AUSBLICK-Block je Ort (Katalog: alle 24 `selectable=True`-Größen mit `summary_fields` aus `src/app/metric_catalog.py` — seit #1406 B derselbe Vorrat wie beim Stundenverlauf, der früher eigene 9er-Katalog ist entfallen). Aufgelöst über `src/output/renderers/compare_outlook_metric_ids.py` gegen `compare_metric_catalog.key_for()` + `metric_catalog._METRICS`; unbekannte/ungültige Paare werden verworfen und per `logger.warning` protokolliert, Reihenfolge bleibt Auswahlreihenfolge. **Seit Issue #1361 Befund 2 + #1368 (S3 Scheibe A von Epic #1372, 2026-07-27):** Key absent/`None` = Default „die bisherigen sieben Spalten" (Temp min/max, Regen, Regen-Wahrscheinlichkeit, Wind, Böen, Gewitter, wie vor dieser Lieferung); Feld vorhanden und `[]` (bewusst leer) = der 3-Tages-Ausblick-Block entfällt für alle Orte vollständig (Überschrift UND Tabelle), analog zur `hourly_metrics`-Kopplung an `hourly_enabled=False` in `resolve_compare_render_options()`. Spaltenköpfe kommen aus `compare_metric_catalog.label` (deutsch, eindeutig), nicht aus `metric_catalog.col_label` (liefert für mehrere Temperatur-Auswertungen denselben Text „Temp"). Schreiber: `CompareOutlookLayoutControls.svelte` im Wetter-Metriken-Reiter (`context="vergleich"`, kein Trip-Pendant — der Trip bekommt keine Auswahlfläche, ADR-0037). Details: `docs/adr/0037-datengetriebener-ausblick-aus-metrik-katalog.md`, Spec `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md`.
- `output_layout`: opaque (zukünftig) — Spalten-Reihenfolge, Formatierung per Kanal
- `schedule_config`: opaque (zukünftig) — Wiederholungs-Details

**Note:** Das Feld `forecast_hours` (24|48|72 h) ist ein Top-Level-Feld von `ComparePreset`, nicht Teil von `display_config` (Issue #764).

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/compare/presets` | 200 | List all presets for authenticated user ([] if none) |
| GET | `/api/compare/presets/{id}` | 200 / 404 | Get single preset by ID (for detail-page view, Issue #491) |
| POST | `/api/compare/presets` | 201 / 400 | Create new preset; ID auto-generated, user_id from auth context |
| PUT | `/api/compare/presets/{id}` | 200 / 400 / 404 | Update preset (user_id, created_at preserved from stored record) |
| DELETE | `/api/compare/presets/{id}` | 204 / 404 | Delete preset |
| POST | `/api/compare/presets/{id}/send` | 200 / 400 / 404 | Immediate send: executes comparison & emails all configured recipients regardless of schedule (Issue #627); ignores `schedule='manual'` |

### Validation Rules (POST/PUT)

| Field | Constraint |
|-------|-----------|
| `name` | not empty |
| `schedule` | in `{"daily", "weekly", "manual"}` |
| `profil` | valid per `internal/model/activity_profile.go` `IsValidProfile()` (seit #1215 in model) |
| `hour_from` | 0–23 — **weiterhin von `validateComparePreset` erzwungen** (`internal/handler/compare_preset.go:120`). @deprecated Issue #1268: nicht mehr vom Editor/Versand gelesen; bestehende Werte in Request-Body werden per RMW-Spread erhalten (Bestandsschutz). Neue Presets erhalten 0 (Go Zero-Value, von der Validierung zugelassen). |
| `hour_to` | 0–23 **und** `hour_to >= hour_from` — **beide Regeln gelten weiter** (`compare_preset.go:123,126`); die API lehnt Verstöße auch nach #1268 ab. @deprecated: nicht mehr vom Editor/Versand gelesen; bestehende Werte per RMW-Spread erhalten. |
| `forecast_hours` | @deprecated Issue #1268: nicht mehr vom Versand gelesen; der Dispatch verwendet fest 96 h (Issue #1305, zuvor 48 h). Bestehende Werte werden per RMW-Spread erhalten. Frontend sends dieses Feld nicht mehr mit. |
| `empfaenger[]` | each contains `@` (basic email check) |

### Error Responses

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"validation_error","detail":"..."}` | Validation failed (see above) |
| 400 | `{"error":"bad_request"}` | JSON not decodable |
| 404 | `{"error":"not_found"}` | ID not found in user's preset list |

### Notes

- **User Isolation:** Every preset belongs to one user (read from Auth-Context). No user can see/modify another user's presets.
- **Server-Managed Fields:** On CREATE, `id` is auto-generated (`cp-{hex}`) and `user_id` is set from context. On UPDATE, `user_id` and `created_at` are never overwritten from request body. `letzter_versand`, `top_ort_letzter_versand`, and `previous_schedule` are server-managed (not client-writable).
- **forecast_hours (Issue #764, @deprecated #1268):** Vorhersage-Horizont — Legacy-Erklärung: (24|48|72 Stunden) wurde beim Orts-Vergleich-Versand verwendet. **Seit Issue #1268:** Das Feld ist deprecated und wird vom Dispatch nicht mehr gelesen. Der Versand verwendet fest 96 h (Issue #1305, zuvor 48 h — geteilte Konstante `COMPARE_FORECAST_HOURS` in `src/services/comparison_engine.py`). Beim Bearbeiten wird der Wert aus dem Preset nicht mehr hydratisiert und nicht mehr in den Request-Body geschrieben. Die Go-API akzeptiert den Wert bei PUT zum Bestandsschutz (RMW-Spread), schreibt ihn aber nicht selbst. Neue Presets erhalten 0 (Go Zero-Value, keine Editor-Eingabe). Bekannte Limitation #1280 (s. Spec #1268): Versandzeit-Genauigkeit (Minuten vs. Stunden) sichtbar geworden; **PO-Entscheid liegt vor** (2026-07-16: Eingabe auf volle Stunden begrenzen), Umsetzung in #1280.
- **display_config (Issue #680):** Opaque JSON object stored as `map[string]interface{}` (no server-side schema validation). Contains `active_metrics` (persisted Metrik-Auswahl), `ideal_ranges` (Bewertungs-Schwellwerte), und zukünftig `output_layout` + `schedule_config`. Round-Trip beim Update: Server gibt `display_config` unverändert zurück, Frontend reicht nur geänderte Felder. Bestandsfelder erhalten sich automatisch (RMW-Semantik). **Fix #1191:** `CompareAlertService._build_eval_config` reicht `display_config` seither auch in die Δ-Alarm-Auswertung durch (vorher immer `None`, wodurch der #961-Deaktivierungs-Filter für Compare-Presets wirkungslos blieb — analog zum Trip-Pfad in `trip_alert.py`). Migrations-Skript `scripts/migrate_1191_compare_active_metrics.py` setzt auf Bestands-Presets ohne `active_metrics` einmalig den vollen Metrik-Satz (bewahrt „alles feuert", jetzt explizit + abschaltbar).
- **POST /api/compare/presets/{id}/send:** Immediate send endpoint (Issue #627). Executes comparison engine and emails `settings.mail_to` immediately, regardless of `schedule` value (bypasses time-based gating). **Seit Issue #1452 (2026-08-02):** `empfaenger` wird für die Empfängerermittlung nicht mehr gelesen — s. Section 18 für Details. If `mail_to` is missing, the send fails. Returns HTTP 200 with `{"status":"ok","winner":"<top_location>","empfaenger_count":N}` on success (`empfaenger_count` ist seit #1452 stets 1). Updates `letzter_versand` and `top_ort_letzter_versand` server-side.
- **previous_schedule Field (Issue #631):** When a preset is paused (`schedule='manual'`), the frontend sets `previous_schedule` to the prior schedule value (`"daily"` or `"weekly"`). On reactivation, `schedule` is restored from `previous_schedule`. This field is preserved across reloads (backend-persistent); altdata without this field remain unaffected (omitempty).
- **LocationIDs Validation:** Backend does not validate that referenced location IDs exist in `data/users/{userID}/locations.json`. Invalid IDs cause errors only during send.
- **official_warnings (Issue #1258):** Identische Semantik wie beim Trip — s. Section 10.5 „official_warnings (Issue #1258)" für Feld-Format, Legacy-Fallback (`official_alert_triggers_enabled`), Migration und PUT-RMW-Verhalten (inkl. Feld-Level-Preserve von `sources`).

### Source Files

| File | Change |
|------|--------|
| `internal/model/compare_preset.go` | ComparePreset struct |
| `internal/store/compare_preset.go` | LoadComparePresets(), SaveComparePresets(), NormalizeComparePreset() |
| `internal/handler/compare_preset.go` | Handler + newComparePresetID(), validateComparePreset() |
| `internal/router/router.go` | Route-Registrierungen |

---

## 17) Google OAuth Login Endpoints (Issue #425)

**Handler:** `internal/handler/auth_oauth.go` (NEW) | **Routing:** `internal/router/router.go`

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/auth/google/init` | 302 / 501 | Initiate Google OAuth flow (redirects to Google consent screen) |
| GET | `/api/auth/google/callback` | 302 / 400 | Handle Google OAuth callback (exchanges code for session) |

### GET /api/auth/google/init

Initiates the Google OAuth 2.0 Authorization Code flow.

**Prerequisites:**
- `GZ_GOOGLE_CLIENT_ID` must be configured (non-empty)

**Behavior:**

1. Generate random 16-byte state token (hex-encoded)
2. Set `gz_oauth_state` cookie (HttpOnly, SameSite=Lax, MaxAge=600s, Secure on HTTPS only)
3. Redirect to Google OAuth consent URL with scopes `openid email profile`

**Response:**

| Status | Behavior |
|--------|----------|
| 302 | Redirect to `https://accounts.google.com/o/oauth2/v2/auth?...state=<token>...` |
| 501 | Not Implemented — feature disabled (`GZ_GOOGLE_CLIENT_ID` not set) |

**Error Cases:**

- Config not loaded: HTTP 501
- `GZ_GOOGLE_CLIENT_ID` empty: HTTP 501

### GET /api/auth/google/callback

Handles the OAuth callback from Google. Exchanges authorization code for ID token, verifies the user, and issues a session.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| code | string | yes | OAuth authorization code from Google |
| state | string | yes | CSRF protection token (must match cookie) |

**Behavior:**

1. Read `gz_oauth_state` cookie; validate against `state` query param (constant-time comparison)
2. Delete `gz_oauth_state` cookie (MaxAge=-1)
3. Exchange `code` for ID token via `oauth2.Exchange()`
4. Fetch user info from `https://www.googleapis.com/oauth2/v3/userinfo`
5. Validate `email_verified: true` in userinfo
6. Lookup user by `OAuthProvider: "google"` + `OAuthSub: sub`
   - **Found:** Issue `gz_session` cookie, redirect to `/`
   - **Not Found:** Generate new User-ID (`g-{8hex}`), create new user, issue `gz_session` cookie, redirect to `/`
7. On any error: Redirect to `/login?error=oauth_failed` (no stack traces exposed)

**Response:**

| Status | Behavior |
|--------|----------|
| 302 | Redirect to `/` (success) or `/login?error=oauth_failed` (failure) |
| 400 | Invalid query parameters or malformed request |

**Error Cases:**

| Scenario | Response |
|----------|----------|
| State mismatch (CSRF attempt) | 302 to `/login?error=oauth_failed` |
| `email_verified: false` | 302 to `/login?error=oauth_failed` |
| Google userinfo endpoint unavailable | 302 to `/login?error=oauth_failed` |
| ID collision after 3 generation attempts | 302 to `/login?error=oauth_failed` |
| Network error during token exchange | 302 to `/login?error=oauth_failed` |

**Side Effects:**

- New `data/users/g-{8hex}/user.json` created for first-time Google users
- Session cookie `gz_session` set with 7-day expiry
- Existing users with matching `oauth_sub` skip creation and reuse their account

### User Data Model (Modified)

**`internal/model/user.go`:**

```go
type User struct {
    // ... existing fields ...
    OAuthProvider string `json:"oauth_provider,omitempty"`
    OAuthSub      string `json:"oauth_sub,omitempty"`
}
```

- `OAuthProvider`: OAuth provider name (e.g., `"google"`)
- `OAuthSub`: OAuth subject claim (unique ID from provider)
- Fields optional (omitempty) for backward compatibility with password-auth users

### Config Parameters

**Environment Variables:**

| Var | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| GZ_GOOGLE_CLIENT_ID | string | no | (unset) | Google OAuth 2.0 Client ID |
| GZ_GOOGLE_CLIENT_SECRET | string | no | (unset) | Google OAuth 2.0 Client Secret |
| GZ_GOOGLE_REDIRECT_URL | string | no | (unset) | Callback URL (e.g., `https://gregor20.henemm.com/api/auth/google/callback`) |

**Feature Gate:**
- If `GZ_GOOGLE_CLIENT_ID` is empty or unset:
  - Frontend buttons hidden (`data.googleEnabled = false`)
  - `/api/auth/google/init` returns HTTP 501
  - Google login is disabled

### Frontend Integration

**Login/Registration Pages:**
- `frontend/src/routes/login/+page.server.ts` — exposes `data.googleEnabled` flag
- `frontend/src/routes/register/+page.server.ts` — exposes `data.googleEnabled` flag
- Conditional button: `{#if data.googleEnabled} <a href="/api/auth/google/init">Mit Google anmelden</a> {/if}`

### Session Handling

Google OAuth users receive the same session mechanism as password-auth users:
- Cookie: `gz_session` (format: `{userId}.{timestamp}.{sig}`)
- User-ID format for OAuth users: `g-{8hex}` (no dots to prevent session parsing errors)
- Session verification: `frontend/src/lib/auth.ts` → `verifySession()` handles split defensively

---

## 17) Compare-Preset Model (Issue #458)

Das neue `ComparePreset`-Datenmodell für Auto-Briefings (Orts-Vergleiche) mit CRUD-Endpoints.

### ComparePreset Structure

```json
{
  "id": "cp-a1b2c3d4e5f6g7h8",
  "name": "Alpenvergleich",
  "user_id": "alice@example.com",
  "location_ids": ["loc-001", "loc-002", "loc-003"],
  "schedule": "daily",
  "profil": "WINTERSPORT",
  "hour_from": 6,
  "hour_to": 8,
  "empfaenger": ["alice@example.com", "bob@example.com"],
  "letzter_versand": "2026-05-29T07:00:00Z",
  "top_ort_letzter_versand": "Andermatt",
  "created_at": "2026-05-20T14:30:00Z"
}
```

### Feldliste

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | string | Eindeutige ID (`cp-{8hex}`) |
| name | string | Benutzer-definierter Name |
| user_id | string | Besitzer-User-ID |
| location_ids | string[] | 1–5 Orts-IDs zum Vergleichen |
| schedule | enum | `"daily"` \| `"weekly"` \| `"manual"` |
| profil | enum | `"WINTERSPORT"` \| `"ALPINE_TOURING"` \| `"SUMMER_TREKKING"` \| `"ALLGEMEIN"` |
| hour_from | integer | @deprecated Issue #1268: nicht mehr vom Versand gelesen; der Versand rechnet fest über den ganzen Tag (0–23). Bleibt in Bestandsdaten zur Bestandssicherung. Neue Presets erhalten 0. |
| hour_to | integer | @deprecated Issue #1268: nicht mehr vom Versand gelesen; der Versand rechnet fest über den ganzen Tag (0–23). Bleibt in Bestandsdaten zur Bestandssicherung. |
| empfaenger | string[] | E-Mail-Adressen (Validierung: muss `@` enthalten) |
| letzter_versand | datetime \| null | ISO-8601 UTC des letzten Versands |
| top_ort_letzter_versand | string \| null | Ort mit höchstem Score beim letzten Versand |
| created_at | datetime | Erstellungszeitpunkt (ISO-8601 UTC) |

### Endpoints

| Method | Path | Verhalten |
|--------|------|-----------|
| `GET` | `/api/compare/presets` | Alle Presets des eingeloggten Users; `[]` falls keine |
| `POST` | `/api/compare/presets` | Neues Preset anlegen → `201 Created` + Preset-JSON |
| `PUT` | `/api/compare/presets/{id}` | Preset komplett aktualisieren → `200 OK` + Preset-JSON |
| `DELETE` | `/api/compare/presets/{id}` | Preset löschen → `204 No Content`; `404` falls nicht gefunden |
| `POST` | `/api/compare/presets/{id}/send` | Versand triggern (Stub: `{"status":"queued"}` mit `200`) — echte Versand-Logik folgt #461 |

### Validierung

- `name`: erforderlich, nicht leer
- `schedule`: einer von `["daily", "weekly", "manual"]`
- `profil`: einer von `["WINTERSPORT", "ALPINE_TOURING", "SUMMER_TREKKING", "ALLGEMEIN"]`
- `hour_from`, `hour_to`: Integers in [0..23], `hour_from <= hour_to`
- `empfaenger`: Array von Strings mit mindestens `@`-Zeichen (einfache Email-Validierung)
- `location_ids`: Array (leer erlaubt, aber mind. 1 Ort bei Versand sinnvoll)

### User-Isolation

Alle Endpoints filtern nach dem eingeloggten User (via `middleware.UserIDFromContext()`). Queries auf fremde Presets (`user_id ≠ authenticated user`) werden ignoriert/404.

---

## 17) Compare-Presets Daily Dispatch Endpoint (Issue #461, Slot-Zeitplan seit #1232 Scheibe 2a)

**Veraltet (bis #1232 Scheibe 2a):** Dispatch lief einmal täglich um 06:00 UTC und filterte grob
auf `schedule='daily'`. **Aktuell:** Der Go-Cron `compare_presets_daily` läuft **stündlich**
(`0 * * * *`, Job-Beschreibung „Compare Presets Slot-Check (hourly)"); der Python-Endpoint prüft
pro Preset die Zwei-Slot-Felder (`morning_time`/`evening_time`, s. Abschnitt 16) gegen die aktuelle
Stunde (Europe/Vienna) statt eines einzigen festen Filters. `schedule` wirkt nur noch als
Pause-Flag (`manual` = pausiert). Details: `docs/specs/modules/compare_preset_zeitplan.md`.

**Handler:** `api/routers/scheduler.py` (`run_compare_presets_daily`) | **Routing:** `internal/router/router.go`

### POST /api/scheduler/compare-presets-daily

Prüft für jeden Nutzer alle Compare-Presets auf Slot-Fälligkeit zur aktuellen Stunde
(optionaler Query-Parameter `hour`, Default: aktuelle Stunde Europe/Vienna — Muster
`trigger_trip_reports`). Fällige Presets: Morgen-Slot → Compare Engine mit `target_date=heute`,
Abend-Slot → `target_date=morgen`. Guards vor Versand: siehe `compare_alert_guard.is_silenced()`
(Issue #1467 S2 AG6: `paused_at` gesetzt, `schedule=="manual"`, oder `archived_at` gesetzt);
zusätzlich `end_date` gesetzt und in der Vergangenheit. Rendert/sendet E-Mails,
aktualisiert `letzter_versand` und `top_ort_letzter_versand`.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | no | User identifier (default: "default" for V1) |
| hour | int | no | Stunde [0..23] gegen die Slot-Fälligkeit geprüft wird (Issue #1232 Scheibe 2a, Muster `trigger_trip_reports`). Default: aktuelle Stunde Europe/Vienna. |

**Response 200:**

```json
{
  "status": "ok",
  "count": 2,
  "failed": 0
}
```

Bei mindestens einem fehlgeschlagenen fälligen Preset (seit Issue #1290, identisches Schema zu `/api/scheduler/trip-reports`, Issue #766):

```json
{
  "status": "partial",
  "count": 1,
  "failed": 1
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| status | enum | `"ok"` wenn alle fälligen Presets erfolgreich versendet wurden, `"partial"` sobald `failed > 0` (Issue #1290; HTTP bleibt in beiden Fällen 200) |
| count | int | Anzahl erfolgreich versendeter fälliger Presets (Morgen- oder Abend-Slot), die zur geprüften Stunde fällig waren |
| failed | int | Anzahl fälliger Presets, deren Versand fehlgeschlagen ist (Issue #1290; zuvor nur intern als `error_count` geloggt, jetzt Teil der Response) |

**Internal Behavior (seit Issue #1232 Scheibe 2a):**

1. Load über den zentralen Loader `load_compare_presets()`/`compare_preset_to_dict()` (`src/app/loader.py`, Issue #1250 Scheibe 1, `strict=True`) — liest seit Issue #1250 S7b per-Datei `data/users/{user_id}/briefings/*.json`, invers gefiltert auf `kind == "vergleich"` (partial-tolerant) statt der alten Single-File `compare_presets.json` (nur noch Migrations-Quelle/Rollback) — Rückgabe bleibt dieselbe Dict-Liste wie zuvor (`compare_preset_to_dict()` liefert den unveränderten Roh-Dict je Preset)
2. Für jedes Preset: Guards prüfen — via `compare_alert_guard.is_silenced()` (Issue #1467 S2 AG6): `paused_at` gesetzt → skip (pausiert); `schedule == "manual"` → skip (pausiert); `archived_at` gesetzt → skip; zusätzlich `end_date` gesetzt und `< heute` (Europe/Vienna) → skip
3. Slot-Werte lesen (Preset ohne Slot-Felder — z. B. weil die Go-Migration die Datei noch nicht neu geschrieben hat — bekommt dieselben Fallback-Defaults wie `LoadComparePresets`); Morgen-Slot fällig wenn `morning_enabled` und `morning_time.hour == hour` (`target_date=heute`), Abend-Slot fällig wenn `evening_enabled` und `evening_time.hour == hour` (`target_date=morgen`)
4. Für jedes fällige Preset:
   - Validate `location_ids` (warn if empty, increment `error_count`)
   - Convert `preset["profil"]` (Uppercase Go string → lowercase Python enum, fallback ALLGEMEIN)
   - Call Compare Engine with `target_date` (s. o.), `forecast_hours=COMPARE_FORECAST_HOURS` (feste geteilte Konstante, 96 h — Issue #1305, zuvor 48 h seit #1268; `preset["forecast_hours"]` wird nicht gelesen), `hour_from`, `hour_to`, `activity_profile`
   - Render Compare-Email template
   - Send via Resend to `settings.mail_to` (**seit Issue #1452, 2026-08-02:** ausschließlich die Konto-Settings des Users; `preset["empfaenger"]` wird nicht mehr gelesen — fehlt `mail_to`, wird das Preset mit `ValueError` übersprungen, s. `error_count`/Notes)
   - Call `_save_preset_status(user_id, preset_id, top_ort)` to update JSON
   - On any error: log warning, increment `error_count`, continue (no job abort)
5. Go scheduler (Cron `0 * * * *`, stündlich statt vormals einmal täglich 06:00 UTC) pingt den BetterStack Heartbeat (`GZ_HEARTBEAT_COMPARE_PRESETS` / Go `HeartbeatComparePresets`). Seit **Issue #1346** ist dieser Ping in `briefingDispatch()` **konsolidiert** und deckt den gesamten stündlichen Briefing-Versand ab: er feuert nur, wenn im selben Tick **beide** Teil-Jobs erfolgreich sind — `compare_presets_daily` (`error_count == 0`) **und** `trip_reports_hourly` (Status `ok`). Ein Trip-Briefing-Totalausfall unterdrückt den Ping (früher verdeckt) und löst zusätzlich einen edge-getriggerten MQ-Alarm an `infra` aus.

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 200 | `{"status":"ok","count":0,"failed":0}` | No daily presets found (not an error) |
| 200 | `{"status":"ok","count":2,"failed":0}` | 2 presets processed erfolgreich, keine Fehlschläge |
| 200 | `{"status":"partial","count":1,"failed":1}` | 1 Preset erfolgreich, 1 Preset fehlgeschlagen — HTTP bleibt 200, `status` zeigt `"partial"` (Issue #1290) |

**Side Effects:**

- `data/users/{user_id}/briefings/{id}.json` (kind=vergleich) per-Datei-RMW via `save_compare_preset_status` updated with `letzter_versand` (ISO-datetime UTC) and `top_ort_letzter_versand` (string or null) for each successfully sent preset (unbekannte Felder bleiben erhalten; Issue #1250 S7b — Legacy `compare_presets.json` wird nicht mehr geschrieben)
- Email sent to `settings.mail_to` (seit Issue #1452, 2026-08-02 — nicht mehr `preset["empfaenger"]`)
- Log entries on WARNING for each failed preset

**Notes:**

- Endpoint always returns HTTP 200 regardless of `error_count`; seit Issue #1290 zeigt das `status`-Feld (`"ok"`/`"partial"`) den Fehlerfall aber im Response-Body selbst an (job success daneben weiterhin über Go-Scheduler `recordRun()` getrackt)
- Python-side heartbeat ping (`GZ_HEARTBEAT_COMPARE_PRESETS` ENV) is not called by Python; the Go scheduler handles this via `pingHeartbeat()` — seit Issue #1346 nicht mehr in `comparePresetsDaily()` selbst, sondern zentral in `briefingDispatch()` nach beiden Teil-Jobs
- BetterStack Heartbeat is pinged only when the **full briefing dispatch** succeeds: `compare_presets_daily` `error_count == 0` **and** `trip_reports_hourly` status `ok` (Readiness Principle, Issue #1346). Any preset-level error OR a trip-briefing total outage blocks the ping; the trip outage additionally fires an MQ alarm to `infra` (edge-triggered ok→error, recovery on error→ok)

---

## 18) Compare-Preset Immediate Send (Issue #627)

On-demand send for a single Compare-Preset: triggers comparison engine and emails all configured recipients immediately, bypassing schedule-based gating.

**Handler:** `api/routers/scheduler.py` (Python endpoint) | `internal/handler/compare_preset.go` (Go proxy) | **Routing:** `internal/router/router.go`

### POST /api/scheduler/compare-presets/{id}/send

Executes comparison and sends report for a single preset immediately (regardless of `schedule` value).

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | yes (via appendUserID) | User identifier (appended by Go proxy; anti-spoofing via Auth-Context) |

**Response 200 (Success):**

```json
{
  "status": "ok",
  "winner": "Säntis",
  "empfaenger_count": 1
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| status | enum | `"ok"` on success |
| winner | string | Highest-ranked location name from comparison |
| empfaenger_count | int | Number of recipients the email was sent to — **seit Issue #1452 (2026-08-02) stets `1`**, da `mail_to` ein einzelnes Settings-Feld ist (kein Preset-`empfaenger`-Array mehr als Quelle) |

**Behavior:**

1. Go proxy (`SendComparePresetHandler`) extracts `{id}` from URL, appends `user_id` from Auth-Context to query string
2. Proxy forwards POST to Python endpoint: `/api/scheduler/compare-presets/{id}/send?user_id=...`
3. Python endpoint:
   - Loads über `load_compare_presets(strict=True)` (Issue #1250 Scheibe 1) — liest seit Issue #1250 S7b per-Datei `data/users/{user_id}/briefings/*.json` mit `kind == "vergleich"` statt der alten Single-File `compare_presets.json` (nur noch Migrations-Quelle/Rollback)
   - Finds preset by `id` (404 if not found)
   - Validates `settings.mail_to` is non-empty (**seit Issue #1452, 2026-08-02:** `preset["empfaenger"]` ist inert — keine Lese-Quelle mehr für den Versand, ausschließlich die Konto-Settings des Users zählen)
   - Calls Compare Engine with `target_date=today`, `forecast_hours=COMPARE_FORECAST_HOURS` (feste geteilte Konstante, 96 h — Issue #1305, zuvor 48 h seit #1268; `preset["forecast_hours"]` wird nicht gelesen; uses preset's `hour_from`, `hour_to`, `profil`)
   - Renders Compare-Email template and sends via Resend to all recipients
   - Updates `letzter_versand` (current ISO-datetime UTC) and `top_ort_letzter_versand` (winner) in preset
   - Returns HTTP 200 with winner and recipient count

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 422 | `{"detail":"Preset <id>: kein Empfaenger — mail_to fehlt in den Konto-Settings"}` | Keine `mail_to`-Adresse in den Konto-Settings des Users (dokumentierte Korrektur 2026-08-02, Issue #1452 — vorheriger Stand dieser Zeile beschrieb einen `400`/`no_recipients`-Fehlerkörper, der im Code nicht mehr existiert) |
| 404 | `{"error":"not_found"}` | Preset ID not found in user's preset list |
| 500 | `{"error":"send_failed","detail":"..."}` | Email dispatch failed (network/Resend error) |

**Side Effects:**

- Email sent to `settings.mail_to` (seit Issue #1452, 2026-08-02 — nicht mehr `preset["empfaenger"]` oder ein Fallback darauf)
- `data/users/{user_id}/briefings/{id}.json` (kind=vergleich) per-Datei-RMW via `save_compare_preset_status` updated with `letzter_versand` (ISO-datetime) and `top_ort_letzter_versand` (location name) — Issue #1250 S7b
- No effect on `schedule` — paused presets (`schedule='manual'`) can still be sent immediately

**Notes:**

- Ignores `schedule` value entirely (sends even if `schedule='manual'` or `'weekly'`)
- User isolation enforced via Go proxy's `appendUserID()` function — client cannot spoof another user's `user_id`
- Idempotent for recipients (same `mail_to` re-sent on retry), but updates `letzter_versand` each time

---

## 19) Authentication Endpoints (Session + Passkey)

**Scope:** User registration, password-based login, and FIDO2 passkey-based authentication.

**Handler:** `internal/handler/auth.go` | **Middleware:** `internal/middleware/auth.go` | **Routing:** `internal/router/router.go`

### A) Password-based Authentication

#### POST /api/auth/register

User registration with username + password + email (HTTP 201 on success, 409 if user exists).

**Request Body:**
```json
{"username": "alice", "password": "geheim123", "email": "alice@example.com"}
```

**Response 201:**
```json
{"id": "alice"}
```

**Validation:**
- `username`: 3–50 characters, alphanumeric + underscore
- `password`: ≥8 characters
- `email`: required (Issue #1226), minimal format check (`strings.Contains(email, "@")` — no `net/mail` parsing, no uniqueness check)

**Check order (Issue #1517):** format checks (username length/regex, password length) → existence check (`s.UserExists`) → email presence/format. The existence check runs **before** the email checks, so a request for an already-registered username returns 409 regardless of whether `email` is set — previously a missing `email` on an existing username produced a misleading 400 `validation failed`.

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid request"}` | JSON malformed (`internal/handler/auth.go:36`) |
| 400 | `{"error":"validation failed"}` | username/password missing, too short, or wrong format (auth.go:43-56) |
| 409 | `{"error":"user already exists"}` | User with this ID already registered (auth.go:62-67 — Klartext mit Leerzeichen, KEIN snake_case; checked before email validation) |
| 400 | `{"error":"validation failed"}` | `email` missing (auth.go:75-79) |
| 400 | `{"error":"invalid_email"}` | `email` present but without `@` (auth.go:81-85) |
| 500 | `{"error":"internal error"}` / `{"error":"store_error"}` | Hashing-/Persistenz-Fehler (auth.go:88-93,102-106) |

Since Issue #1226, a valid `email` also triggers the existing `dispatchVerificationMail` helper (from #1219) after account creation — same Double-Opt-In flow as profile email changes. Google-OAuth account creation (`createOAuthUser`) and passkey-public account creation (`PasskeyRegisterPublicFinishHandler`) trigger the same dispatch on first-time account creation (not on existing-user login).

#### POST /api/auth/login

User login with username + password, returns session cookie.

**Request Body:**
```json
{"username": "alice", "password": "geheim123"}
```

**Response 200:**
```json
{"id": "alice"}
```

**Side Effects:**
- Sets `Set-Cookie: gz_session=<userId>.<timestamp>.<hmacSig>; HttpOnly; SameSite=Lax; MaxAge=86400; Secure` (Secure flag active on HTTPS)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid request"}` | JSON malformed (auth.go:124 — Klartext, KEIN snake_case) |
| 401 | `{"error":"invalid credentials"}` | User not found or password incorrect — same message for both (auth.go:132,139; Klartext mit Leerzeichen) |

### B) Passkey Authentication (WebAuthn/FIDO2)

**Issue #450** — Add WebAuthn (Face ID, Touch ID, Windows Hello, etc.) as alternative auth method alongside password. V1 is add-on (existing users keep passwords).

**Issue #467** — Discoverable credentials (login without username) via Conditional UI. Browser shows Passkeys as native autofill suggestions on username field focus (`mediation: 'conditional'`).

**Key Configuration:**
- **RP-ID (Relying Party):** Prod `gregor20.henemm.com`, Staging `staging.gregor20.henemm.com` (isolated)
- **Rate-Limit:** 30 requests/hour per IP (all 7 endpoints)
- **Body-Size-Cap:** 64 KB (`http.MaxBytesReader`)
- **Challenge-TTL:** 5 minutes (in-memory store with garbage collection)

#### POST /api/auth/passkey/discoverable/begin

Initiate discoverable passkey login (no username required, public endpoint). Browser shows registered passkeys as native autofill suggestions on username field focus.

**Request Body:** `{}` (empty)

**Response 200:**
```json
{
  "mediation": "conditional",
  "publicKey": {
    "challenge": "<base64url-string>",
    "timeout": 300000,
    "rpId": "gregor20.henemm.com",
    "userVerification": "preferred"
  }
}
```

**Key Difference from V1 Login:** Top-level includes `"mediation":"conditional"` (required for browser to show autofill picker). No `allowCredentials` array (browser discovers all passkeys for this RP-ID).

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |
| 500 | `{"error":"begin_failed"}` | WebAuthn library error (rare) |

#### POST /api/auth/passkey/discoverable/finish

Complete discoverable passkey login. Browser provides `userHandle` from stored credential; backend looks up user by `userHandle`.

**Request Body:**
```json
{
  "id": "<base64url-credentialId>",
  "rawId": "<base64url-raw>",
  "response": {
    "clientDataJSON": "<base64url-json>",
    "authenticatorData": "<base64url-data>",
    "signature": "<base64url-sig>",
    "userHandle": "<base64url-userId>"
  },
  "type": "public-key"
}
```

**Response 200:**
```json
{"id": "alice"}
```

**Side Effects:**
- Sets `Set-Cookie: gz_session=<userId>.<timestamp>.<hmacSig>; HttpOnly; SameSite=Lax; MaxAge=86400; Secure`
- Updates `last_used_at` timestamp on the used credential
- Increments `sign_count` on the credential (cloning detection)
- ChallengeStore entry is destroyed after successful `Take()` (replay protection)

**Implementation Note:** Backend calls `DiscoverableUserHandler` callback with `userHandle` ([] byte) from response to load user by ID. User lookup fails if `userHandle` is empty or user does not exist.

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | `{"error":"invalid_credentials"}` | Challenge invalid, expired (5 min), signature verification failed, user handle empty/invalid, or user not found |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/register/begin

Initiate passkey registration (requires valid session cookie).

**Request Body:** `{}` (empty)

**Response 200:**
```json
{
  "publicKey": {
    "challenge": "<base64url-string>",
    "rp": {
      "name": "Gregor Zwanzig",
      "id": "gregor20.henemm.com"
    },
    "user": {
      "id": "<base64url-userId>",
      "name": "<userId>",
      "displayName": "<userId>"
    },
    "pubKeyCredParams": [
      {"type": "public-key", "alg": -7},
      {"type": "public-key", "alg": -257}
    ],
    "timeout": 300000,
    "attestation": "direct",
    "authenticatorSelection": {
      "authenticatorAttachment": "platform",
      "residentKey": "preferred",
      "userVerification": "preferred"
    }
  }
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | (via `AuthMiddleware`) | No valid session cookie |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/register/finish

Complete passkey registration (requires valid session cookie, challenge from `register/begin`).

**Request Body:**
```json
{
  "id": "<base64url-credentialId>",
  "rawId": "<base64url-raw>",
  "response": {
    "clientDataJSON": "<base64url-json>",
    "attestationObject": "<base64url-object>"
  },
  "type": "public-key",
  "label": "MacBook"  // optional: user-provided device name
}
```

**Response 201:**
```json
{
  "id": "<base64url-credentialId>",
  "label": "MacBook",
  "created_at": "2026-05-30T12:00:00Z"
}
```

**Side Effects:**
- `user.json` updated with new entry in `passkey_credentials[]` array
- Profile endpoint now returns `"has_passkey": true`

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"challenge_expired_or_missing"}` | Challenge not in store or expired (5 min timeout) |
| 400 | `{"error":"attestation_invalid"}` | WebAuthn library signature/attestation verification failed |
| 401 | (via `AuthMiddleware`) | No valid session cookie |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/login/begin

Initiate passkey login (public, no auth required).

**Request Body:**
```json
{"username": "alice"}
```

**Response 200:**
```json
{
  "publicKey": {
    "challenge": "<base64url-string>",
    "timeout": 300000,
    "rpId": "gregor20.henemm.com",
    "allowCredentials": [
      {
        "type": "public-key",
        "id": "<base64url-credentialId-1>",
        "transports": ["platform", "usb"]
      }
    ],
    "userVerification": "preferred"
  }
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | `{"error":"invalid_credentials"}` | User not found or has no passkeys |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/login/finish

Complete passkey login (public, no auth required).

**Request Body:**
```json
{
  "id": "<base64url-credentialId>",
  "rawId": "<base64url-raw>",
  "response": {
    "clientDataJSON": "<base64url-json>",
    "authenticatorData": "<base64url-data>",
    "signature": "<base64url-sig>"
  },
  "type": "public-key"
}
```

**Response 200:**
```json
{"id": "alice"}
```

**Side Effects:**
- Sets `Set-Cookie: gz_session=<userId>.<timestamp>.<hmacSig>; HttpOnly; SameSite=Lax; MaxAge=86400; Secure`
- Updates `last_used_at` timestamp on the used credential
- Increments `sign_count` on the credential (cloning detection)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | `{"error":"invalid_credentials"}` | Challenge invalid, expired (5 min), signature verification failed, or user deleted |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### DELETE /api/auth/passkey/credentials/{id}

Remove a registered passkey (requires valid session cookie).

**Path Parameter:**
- `id`: Base64URL-encoded credential ID

**Response 200:**
```json
{"status": "deleted"}
```

**Validation & Safety:**
- Returns 400 if user has no password hash AND this is their only credential (lock-out prevention)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"cannot_remove_last_passkey_without_password"}` | User would be locked out (no password, last passkey) |
| 401 | (via `AuthMiddleware`) | No valid session cookie |
| 404 | `{"error":"not_found"}` | Credential ID not found in user's list |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

### C) Profile & Session Status

#### GET /api/auth/profile

Returns authenticated user profile (requires valid session cookie).

**Response 200:**
```json
{
  "id": "alice",
  "display_name": "Alice Schmidt",
  "email": "alice@example.com",
  "mail_to": "alice@example.com",
  "sms_to": "+49151XXXXXXXX",
  "tier": "free",
  "sms_allowed": false,
  "requested_tier": "standard",
  "requested_at": "2026-07-07T14:00:00Z",
  "premium_sms_allowed": false,
  "premium_sms_reply_state": "none",
  "premium_sms_reply_to": "15551234567",
  "premium_sms_reply_at": "2026-08-05T12:00:00Z",
  "has_passkey": true,
  "passkeys": [
    {
      "id": "<base64url-credentialId>",
      "label": "MacBook",
      "authenticator_name": "iCloud Keychain",
      "created_at": "2026-05-30T12:00:00Z",
      "last_used_at": "2026-05-30T15:30:00Z"
    },
    {
      "id": "<base64url-credentialId-2>",
      "label": "iPhone",
      "authenticator_name": "Windows Hello",
      "created_at": "2026-05-25T10:00:00Z",
      "last_used_at": "2026-05-29T08:15:00Z"
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| id | string | User identifier (immutable; also used as fallback display if `display_name` empty) |
| display_name | string | User's chosen display name (optional, max 50 chars); shown in UI instead of `id` if set; null/empty if not configured |
| email | string | Email address (for display only) |
| mail_to | string | Email recipient for trip reports (can differ from email) |
| sms_to | string | SMS recipient phone number (international format, e.g. `+49151XXXXXXXX`); empty if not configured |
| tier | string | User's level: `free`/`standard`/`premium` (Issue #1068, Slice 1 of Epic #1067); always present, defaults to `free` if unset on the underlying `user.json` (fallback happens only at read time, never written back); display-only in this slice, no channel or alert-frequency enforcement yet |
| sms_allowed | bool | Whether SMS channel is available for this user (Issue #1069, Slice 2 of Epic #1067); `true` if `tier` is `standard` or `premium`, `false` for `free`; determines server-side channel-gating in report-dispatch and alert-dispatch |
| requested_tier | string | Level change requested by the user via `POST /api/auth/tier-change-request` (Issue #1071, Slice 4 of Epic #1067); `omitempty` — absent/empty if no request is pending. Does not change `tier` itself; only the PO setting `tier` manually clears the pending state (once `requested_tier == tier`, the frontend Pending-hint disappears) |
| requested_at | string (RFC3339) | Timestamp of the pending tier-change request set alongside `requested_tier`; pointer type server-side so it is omitted entirely (not a zero-value timestamp) when no request is pending |
| premium_sms_allowed | bool | Whether the Premium-SMS channel (Garmin inReach) is available (Issue #1717 S3); **always present**. Own tariff gate `model.PremiumSmsAllowed` — `true` **only** for `tier == "premium"`, deliberately NOT derived from `sms_allowed` (which also lets `standard` through). Otherwise a `standard` user could tick a channel the dispatch path blocks anyway (#1676 S2a AC-8) |
| premium_sms_reply_state | string | Server-derived state of the learned reply address (Issue #1717 S3): `none` (device never reported), `stale` (reported but past the expiry), `fresh` (valid); **always present**. Derived from `PremiumSmsReplyTo`/`PremiumSmsReplyAt` via `model.DerivePremiumSmsReplyState` against `model.PremiumSmsReplyTTL` (30 days, Go pendant of `PREMIUM_SMS_REPLY_TTL` in `src/output/channels/premium_sms.py`; drift guard: `tests/test_premium_sms_ttl_drift.py`). The UI follows this field only and never recomputes the deadline — otherwise a third copy of the number would exist |
| premium_sms_reply_to | string | The learned Garmin reply address (Issue #1717 S3, raw value); `omitempty` — absent while the device has never reported. Read-only: the sole writer is the internal endpoint `POST /api/internal/premium-sms-learn` (#1676 S1), `PUT /api/auth/profile` does **not** accept it |
| premium_sms_reply_at | string (RFC3339) | When that address was learned (Issue #1717 S3, raw value — here the timestamp *is* the payload, unlike `email_verified_at` which is never exposed); pointer server-side so it is omitted entirely instead of a zero-value timestamp. Same read-only rule as `premium_sms_reply_to` |
| has_passkey | bool | Whether user has registered any passkeys |
| passkeys | array | List of registered WebAuthn credentials (empty if `has_passkey=false`) |

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | (via `AuthMiddleware`) | No valid session cookie or session expired |

#### PUT /api/auth/profile

Update authenticated user profile (requires valid session cookie).

**Request Body:**
```json
{
  "display_name": "Alice S.",
  "mail_to": "alice+briefings@example.com",
  "sms_to": "+49151XXXXXXXX"
}
```

**Response 200:**
Returns updated profile object (same as `GET /api/auth/profile`).

**Validation:**
- `display_name`: Optional, max 50 characters; trimmed (leading/trailing whitespace removed); empty or whitespace-only strings unset the field (reverts to fallback: `id`)
- `mail_to`: Optional, any non-empty string (no format validation)
- `sms_to`: Optional, any non-empty string (no format validation; validation happens during send via SMS provider)
- Empty strings allowed (unset field)
- **Not accepted (Issue #1717 S3, AC-7):** `premium_sms_reply_to`, `premium_sms_reply_at`,
  `premium_sms_reply_state`, `premium_sms_allowed`. The decode struct does not contain them, so
  sending them is silently a no-op — the learned reply address stays writable **only** by the
  internal learning endpoint (#1676 S1). Were it editable, the S2a promise "recipient is
  exclusively the learned reply address, never configuration" would collapse: a user could enter a
  foreign number and have paid Premium-SMS delivered there. Guarded by
  `internal/handler/profile_test.go::TestUpdateProfileHandlerIgnoresPremiumSmsReplyFields`

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"bad_request"}` | JSON not decodable |
| 401 | (via `AuthMiddleware`) | No valid session cookie or session expired |

#### POST /api/auth/tier-change-request

Requests a level change (Free/Standard/Premium) for the authenticated user (Issue #1071, Slice 4
of Epic #1067). Vermerkt den Antrag per Read-Modify-Write in `user.json`
(`requested_tier`/`requested_at`) und löst eine asynchrone Benachrichtigungsmail an den PO aus
(`PO_EMAIL`/`cfg.PoEmail`). Das effektive `tier`-Feld wird durch diesen Endpoint **nicht**
verändert — Freigabe erfolgt weiterhin manuell durch den PO.

**Request Body:**
```json
{
  "requested_tier": "standard"
}
```

**Response 200:**
```json
{"status": "ok"}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid request"}` | JSON not decodable |
| 400 | `{"error":"invalid_tier"}` | `requested_tier` not one of `free`/`standard`/`premium` |
| 400 | `{"error":"already_current_tier"}` | `requested_tier` equals the user's current effective `tier` |
| 404 | `{"error":"not_found"}` | No user found for the authenticated `user_id` |
| 500 | `{"error":"store_error"}` | `SaveUser` failed |
| 401 | (via `AuthMiddleware`) | No valid session cookie or session expired |

**Notes:**
- Mail-Versand ist "fire and forget" (Goroutine + 20s-Timeout, analog `ForgotPasswordHandler`): ein
  fehlschlagender/timeout-behafteter Mailversand oder ein leeres `PO_EMAIL`/`SMTP_HOST` blockiert
  die bereits gesendete `200`-Antwort nicht — der Antrag ist unabhängig vom Mail-Ergebnis
  persistiert.
- Kein Dedup, kein Clear-Endpoint, kein Rate-Limiting über die Session-Auth hinaus — siehe
  `docs/specs/_archive/modules/issue_1071_tier_change_request.md` (Known Limitations).

### User Model Extensions

**File:** `internal/model/user.go`

```go
type User struct {
    ID                 string                 `json:"id"`
    Email              string                 `json:"email,omitempty"`
    PasswordHash       string                 `json:"password_hash,omitempty"`  // now optional (omitempty)
    PasskeyCredentials []WebAuthnCredential   `json:"passkey_credentials,omitempty"`  // NEW (Issue #450)
    CreatedAt          time.Time              `json:"created_at"`
    MailTo             string                 `json:"mail_to,omitempty"`
    SmsTo              string                 `json:"sms_to,omitempty"`  // NEW (Issue #609) — SMS recipient phone number
    TelegramChatID     string                 `json:"telegram_chat_id,omitempty"`
    OAuthProvider      string                 `json:"oauth_provider,omitempty"`
    OAuthSub           string                 `json:"oauth_sub,omitempty"`
    DisplayName        string                 `json:"display_name,omitempty"`  // NEW (Issue #642) — user's chosen display name; omitempty if not set
    Tier               string                 `json:"tier,omitempty"`  // NEW (Issue #1068, Slice 1 of Epic #1067) — free/standard/premium; empty defaults to "free" at read time
    RequestedTier      string                 `json:"requested_tier,omitempty"`  // NEW (Issue #1071, Slice 4 of Epic #1067) — pending level-change request
    RequestedAt        *time.Time             `json:"requested_at,omitempty"`  // NEW (Issue #1071) — pointer type: plain time.Time's omitempty doesn't work, would serialize as zero-value "0001-01-01T00:00:00Z" instead of being omitted
    PremiumSmsReplyTo  string                 `json:"premium_sms_reply_to,omitempty"`  // NEW (Issue #1676, Scheibe S1) — vom Garmin inReach zuletzt gelernte Rückadresse (seven.io-Journal, Kennzeichen `inreachlink.com`); einziger Schreiber bleibt der interne Endpoint `POST /api/internal/premium-sms-learn`. REVIDIERT durch #1717 S3: `GET /api/auth/profile` gibt den Wert seither LESEND aus (`premium_sms_reply_to` + abgeleitetes `premium_sms_reply_state`), damit die Oberfläche zeigen kann, wohin gesendet wird und ob die Adresse noch gilt — `PUT /api/auth/profile` nimmt ihn weiterhin NICHT an (AC-7)
    PremiumSmsReplyAt  *time.Time             `json:"premium_sms_reply_at,omitempty"`  // NEW (Issue #1676, Scheibe S1) — Empfangszeitpunkt des Go-Endpoints (nicht der seven.io-`timestamp`); pointer-Muster analog RequestedAt
}

type WebAuthnCredential struct {
    ID              []byte                `json:"id"`                  // Credential-ID (raw bytes)
    PublicKey       []byte                `json:"public_key"`          // COSE-encoded
    AttestationType string                `json:"attestation_type"`
    Transport       []string              `json:"transport,omitempty"`
    Flags           webauthn.CredentialFlags `json:"flags"`
    Authenticator   webauthn.Authenticator   `json:"authenticator"`    // AAGUID, SignCount, CloneWarning
    CreatedAt       time.Time             `json:"created_at"`
    LastUsedAt      time.Time             `json:"last_used_at,omitempty"`
    Label           string                `json:"label,omitempty"`    // User-provided device name
}
```

**Backward Compatibility:**
- Existing `user.json` files without `passkey_credentials` field deserialize cleanly (`nil` slice maps to empty list)
- `PasswordHash` field now optional; existing users retain their password hash
- Profile endpoint includes `has_passkey` boolean and `passkeys[]` array (excludes `public_key` and raw crypto fields)
- Passkey profile entry may include optional `authenticator_name` field (Issue #468 — resolved AAGUID mappings; missing if AAGUID unknown or zero)
- Existing `user.json` files without `tier` deserialize with an empty string, treated as `free` at read time only (never written back, no forced rewrite of existing files)
- Existing `user.json` files without `requested_tier`/`requested_at` deserialize cleanly (`omitempty`/`nil` pointer); both fields are absent from the `GET /api/auth/profile` response until the user submits a tier-change request

---

## 20) Preview Endpoints (Issue #189, #483, #1270)

Provides preview rendering of trip reports in Email, SMS, or Telegram formats (Signal wurde app-weit entfernt, Issue #610). Supports both live weather and fixture-based demo mode. Seit Issue #1270 zusätzlich: EIN Compare-Preview-Endpoint, der alle Kanäle eines Orts-Vergleich-Presets in einer Antwort liefert (s. `POST /api/preview/compare/{preset_id}` unten).

**Handler:** `api/routers/preview.py` | **Routing:** `internal/router/router.go` (Trip-Routen), `internal/router/router.go:161-167` (Compare-Proxy)

### GET /api/preview/{trip_id}/email

Render trip report preview in HTML format (Email).

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| type | enum | no | Report type: `morning` or `evening` (default: `morning`) |
| date | string | no | Target date ISO-8601 (default: today, format: `YYYY-MM-DD`) |
| demo | boolean | no | Use fixture data instead of live weather (default: `false`, Issue #483) |

**Response 200:**

```
Content-Type: text/html
<html>...</html>  <!-- Full HTML rendered trip report -->
```

**Example:**
```
GET /api/preview/gr20/email?type=morning&date=2026-05-31&demo=1
GET /api/preview/gr20/email?type=evening
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid_trip_or_date"}` | Trip not found or date unparseable |
| 400 | `{"error":"invalid_type"}` | `type` parameter not in `["morning", "evening"]` |
| 400 | `{"error":"no_segments"}` | Trip has no stages/segments for the given date |
| 503 | `{"error":"weather_unavailable"}` | Weather provider API unreachable (only when `demo=false`) |

**Notes:**

- `demo=1` (or any truthy value) enables fixture-based demo mode (Issue #483): FixtureProvider loads predefined weather data from `fixtures/openmeteo/` instead of calling live APIs
- `demo=0` or absent: live weather via configured provider (GEOSPHERE, MET, etc.)
- If weather fetch fails with `demo=false`, the endpoint returns 503; with `demo=true`, it returns 400 if fixtures are unavailable
- Demo mode is ideal for testing preview rendering on past trips (where live weather is unavailable)

### GET /api/preview/{trip_id}/sms

Render trip report preview as SMS text (≤160 characters per message).

**Query Parameters:** Same as `/email` (type, date, demo)

**Response 200:**

```
Content-Type: text/plain
Grüße! Morgen: 18°C, Wind 22 km/h, Regenwahrscheinlichkeit 20%.
```

**Error Responses:** Same as `/email`

### GET /api/preview/{trip_id}/telegram

Render trip report preview for Telegram channel. Seit Issue #1001 rendert das Backend
das Briefing als mehrere einzelne Nachrichten ("Bubbles": Kopf, Kurzübersicht, je
Segment, Ziel, optional Ausblick, Aktionen) statt einer einzelnen Prosa-Nachricht —
siehe `docs/adr/0014-telegram-multi-bubble-format.md`.

**Query Parameters:** Same as `/email` (type, date, demo)

**Response 200:**

```json
{
  "subject": "...",
  "body": "<alle Bubbles, verbunden mit \"\\n\\n---\\n\\n\">",
  "char_count": 0,
  "max_line_width": 0,
  "bubbles": ["<Bubble 1: Kopf>", "<Bubble 2: Kurzübersicht>", "..."]
}
```

`bubbles` ist additiv seit #1001 (AC-7) — `body` bleibt aus Rückwärtskompatibilität
erhalten und ist die mit `"\n\n---\n\n"` verbundene Kette aller Bubbles. Das dazugehörige
`reply_markup` (Inline-Keyboard der Aktionen-Bubble) ist im Preview-JSON **nicht**
enthalten; es wird ausschließlich beim tatsächlichen Versand über
`TripReport.telegram_actions_markup` an die letzte Nachricht angehängt.

**Error Responses:** Same as `/email`

**Notes:**

- All preview endpoints are **read-only** and do not send messages or modify state
- Preview rendering uses the same Report Formatter and Channel Renderers as the scheduler (integrity guarantee)
- Frontend may call multiple preview endpoints (e.g., email + SMS) to render side-by-side tabs

### POST /api/preview/compare/{preset_id}

Render **alle** Kanäle der Vorschau eines Orts-Vergleich-Presets in **einer**
Antwort (Issue #1270, ADR-0011-Muster — Erweiterung des bestehenden
`alert-preview`-Musters). Bewusste Abweichung von der Trip-Preview-Routenform
oben (eine `GET`-Route je Kanal): ADR-0011 verlangt „die fertig gerenderten
Kanäle über EINEN Backend-Endpunkt"; die Trip-Preview-Routen entstanden vor
ADR-0011 (2026-06-29) und wurden nicht rückwirkend migriert (Nebenbefund,
#1199).

**Handler:** `api/routers/preview.py::preview_compare` — ruft
`src/services/compare_preview_service.py::ComparePreviewService.render_all_channels`
| **Go-Proxy:** `internal/handler/preview_proxy.go::ComparePreviewProxyHandler`
(`router.go:167`)

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| preset_id | string | Compare-Preset-ID |

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | yes | Session-User; vom Go-Proxy aus dem Auth-Kontext injiziert — ein client-seitig mitgeschickter Wert wird verworfen (Anti-Spoofing, ADR-0003) |
| date | string | no | Ziel-Datum ISO-8601 (`YYYY-MM-DD`), Default: heute |

Kein Request-Body erforderlich — der Go-Proxy leitet den Body zwar durch, der
Python-Handler liest ihn nicht.

**Response 200:**

```json
{
  "subject": "...",
  "email_html": "<html>...</html>",
  "telegram": "...",
  "sms": "...",
  "sms_char_count": 137
}
```

| Feld | Type | Description |
|------|------|-------------|
| subject | string | Betreffzeile (`build_compare_preset_subject`) |
| email_html | string | Vollständiges HTML der E-Mail-Vorschau (`render_compare_email`) |
| telegram | string | Fertiger Telegram-Nachrichtentext (`render_compare_telegram`) — kein Score/Rang (#1110) |
| sms | string | Budgetierte SMS-Zeile (`render_compare_sms`, Budget über `CHANNEL_LIMITS`, #360) |
| sms_char_count | integer | `len(sms)` |

**Error Responses:**

| Status | Scenario |
|--------|----------|
| 404 | Preset für diese `user_id` nicht gefunden — auch bei einem Preset, das einem anderen Nutzer gehört (Multi-User-Isolation, AC-6) |
| 422 | fehlende/leere `user_id` (kein `"default"`-Fallback, ADR-0003) · Preset ohne konfigurierte Orte · konfigurierte Orte nicht auflösbar (gelöschte Location-Referenz) · ungültiges `date`-Format |
| 503 | Wetter-Provider nicht erreichbar (`ComparisonEngine.run()` scheitert) |

Der Router mappt `FileNotFoundError`/`LookupError` → 404, `ValueError` → 422,
`RuntimeError` → 503; `detail` enthält den Ausnahme-Text (kein fester
Error-Code wie bei den älteren Trip-Preview-Routen).

**Notes:**

- Read-only wie die anderen Preview-Endpoints — kein Versand, kein
  Logbuch-Eintrag.
- `ComparisonEngine.run()` läuft genau **einmal** je Aufruf; alle drei
  Kanäle sitzen auf demselben `ComparisonResult` (AC-7) — ein Kanalwechsel
  im Vorschau-Tab löst **keinen** weiteren Request aus, daher kein Cache
  nötig.
- Ersetzt fachlich den Validator-Stub
  `POST /api/_validator/compare-email-preview` (#464) als Datenquelle für
  die UI-Vorschau (Stub rendert einen hartcodierten Ort). Der Stub selbst
  bleibt unverändert bestehen — er gehört dem externen Validator.
- Details, Architektur-Begründung (ADR-0011) und AC-Mapping:
  `docs/specs/modules/compare_channel_preview_dispatch.md`.

---

---

## 21) Briefing History Endpoint (Issue #559)

Lists all sent briefings (morning/evening) for an archived trip, ordered chronologically.

**Handler:** `internal/handler/briefing_history.go` | **Routing:** `internal/router/router.go`

### GET /api/trips/{id}/briefing-history

Retrieves briefing delivery log for a specific trip (archived or active).

**Path Parameter:**
- `id`: Trip identifier

**Response 200:**

```json
[
  {
    "sent_at": "2026-06-01T07:00:00Z",
    "kind": "morning",
    "channels": ["email"]
  },
  {
    "sent_at": "2026-06-01T18:15:00Z",
    "kind": "evening",
    "channels": ["email"]
  }
]
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| sent_at | datetime | ISO-8601 UTC timestamp of briefing send |
| kind | enum | Briefing type: `"morning"` or `"evening"` |
| channels | string[] | Delivery channels used (e.g., `["email"]`, `["email", "telegram"]`) |

**Failure Modes:**

- Trip not found or no briefing log: returns empty array `[]` (fail-soft, Issue #559 AC-4)
- Missing log file on disk: returns `[]` (never 500 error)
- Unauthorized (no session): HTTP 401

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | (via `AuthMiddleware`) | No valid session cookie |

**Notes:**

- Endpoint is read-only; designed for archive page "Briefing-Verlauf" modal (Issue #559 AC-1)
- Order: chronological ascending (oldest first)
- Returns `[]` if trip ID matches no entries (no 404 distinction for missing logs vs. no entries)

---

## 22) Alert Rules (Issue #638)

**Alerts-Tab Redesign: Karten-Modell, Severity-Falle beseitigen, pro-Alert Kanäle**

Alerts sind personalisierbare Benachrichtigungen bei Wetteränderungen auf einem Trip. Jeder Alert hat eine Metrik (z.B. Wind-Böen), einen Schwellenwert, und wird jetzt mit eigenen Kanälen versandt (vorbelegt aus Briefing-Kanälen).

### AlertRule DTO

```go
// internal/model/trip.go (Go)
type AlertRule struct {
    ID          string   `json:"id"`
    Kind        string   `json:"kind"`                   // "absolute" | "delta"
    Metric      string   `json:"metric"`                 // wind_gust, precipitation_sum, … (AlertMetric-Konstanten, internal/model/trip.go:38-48)
    Threshold   float64  `json:"threshold"`
    Unit        string   `json:"unit,omitempty"`
    Severity    string   `json:"severity"`               // "info", "warning", "critical" (Label nur; nicht mehr für Versand-Entscheidung)
    Enabled     bool     `json:"enabled"`
    PairID      *string  `json:"pair_id,omitempty"`      // Issue #297
    DeltaWindow *string  `json:"delta_window,omitempty"` // Issue #297
    Channels    []string `json:"channels,omitempty"`     // pro-Alert Kanal-Override (empty = erbe Briefing-Kanäle, Issue #638)
}
```

```python
# src/app/models.py (Python)
@dataclass
class AlertRule:
    id: str
    kind: AlertRuleKind         # ABSOLUTE | DELTA
    metric: AlertMetric         # WIND_GUST, PRECIPITATION_SUM, etc.
    threshold: float
    severity: AlertSeverity     # INFO | WARNING | CRITICAL (Label only; not used for send decision)
    enabled: bool
    unit: str = ""
    channels: list[str] = field(default_factory=list)  # NEW: pro-Alert Kanal-Override
```

```typescript
// frontend/src/lib/types.ts
export interface AlertRule {
  id: string;
  kind: "absolute" | "delta";
  metric: string;
  threshold: number;
  severity: "info" | "warning" | "critical";
  enabled: boolean;
  unit?: string;
  channels?: string[];  // NEW: pro-Alert Kanal-Override
}
```

### Feldliste

| Feld | Typ | Beschreibung |
|------|-----|------------|
| id | string | Eindeutige Alert-ID (z.B. `alert-gust-1`) |
| kind | enum | `"absolute"` (Schwellenwert überschritten) oder `"delta"` (Änderung größer als Schwelle) |
| metric | enum | Gemessene Metrik (AlertMetric-Werte, klein): wind_gust, precipitation_sum, temperature_min/max, thunder_level, snow_line, temperature/wind/precipitation_change. Hinweis: `freezing_level` ist KEINE AlertMetric-Konstante, sondern eine Katalog-ID, die via `catalogIDToAlertMetrics` auf `snow_line` mappt (ADR-0019). Seit Issue #1435 Etappe E5 ist `catalogIDToAlertMetrics` (`internal/model/trip.go`) kein Go-Literal mehr, sondern wird per `go:embed` aus der generierten Datei `internal/model/alert_metric_mapping.generated.json` geladen, die wiederum aus der Python-Quelle `catalog_id_to_alert_metrics()` erzeugt wird (ADR-0046). |
| threshold | float | Schwellenwert (z.B. `50.0` für 50 km/h Wind-Böen) |
| severity | enum | `"info"`, `"warning"`, `"critical"` — nur noch Label am Alert, **nicht mehr** für Versand-Filterung (behebt Severity-Falle: Info-Alerts werden nicht mehr still verschluckt) |
| enabled | bool | Alert aktiv? (default: true) |
| unit | string | Einheit (optional, z.B. `"km/h"`, `"mm"`) |
| channels | string[] | **NEW (Issue #638):** Kanäle für diesen Alert (`["email", "telegram"]`). Leer = erbe aktive Briefing-Kanäle aus `TripReportConfig`. Pro Alert überschreibbar. |

### Versand-Logik (Kanal pro Alert)

**Effektive Kanäle eines Alerts:**
- Falls `alert.channels` nicht leer: nutze exakt diese Kanäle
- Falls `alert.channels` leer oder nicht gesetzt: erbe aktive Briefing-Kanäle aus `report_config` (`send_email`, `send_telegram`, `send_sms`)

**Beispiel:**
```json
{
  "report_config": {
    "send_email": true,
    "send_telegram": false,
    "send_sms": false
  },
  "alert_rules": [
    {
      "id": "alert-gust-1",
      "metric": "wind_gust",
      "threshold": 50,
      "channels": [],  // leer → erbe Email (send_email=true)
      "enabled": true
    },
    {
      "id": "alert-thunder-1",
      "metric": "thunder_level",
      "threshold": "HIGH",
      "channels": ["telegram"],  // überschreibe: versand nur über Telegram, auch wenn Email aktiv ist
      "enabled": true
    }
  ]
}
```

### Migration & Backward Compatibility

- **Bestands-Alerts ohne `channels`-Feld:** Laden mit `channels: []` (default). Bei Versand erben sie die aktiven Briefing-Kanäle (RMW — Read-Modify-Write).
- **`severity` bleibt erhalten:** Bestandsdaten mit `"severity":"info"` bleiben lesbar. Die Ableitung von `severity` folgt weiterhin der Logik in `weather_change_detection.py`, wird aber **nicht mehr** für Versand-Filterung genutzt (Severity-Falle beseitigt).

### Frontend Alerts-Tab (JSX / Karten-Modell)

**Komponente:** `AlertsTab.svelte` → `AlertCard.svelte` pro Alert

**Karten-Struktur:**
- Label + `Metrik · Bedingung` (Monospace-Schriftart)
- An/Aus-Switch (`enabled` toggle)
- Kanal-Chips (toggle pro aktivem Briefing-Kanal)
- Infozeile: „Alert-Kanäle werden mit den aktiven Kanälen aus Wetter-Metriken vorgefüllt — jeder Alert kann separate Kanäle haben"
- „+ Neuen Alert hinzufügen"-Button (entfernt die alte Severity-Dropdown-UI)

**Keine Severity-Auswahl mehr:** Die alte UI-Severity-Auswahl ist entfernt (beseitigt die Severity-Falle, die Info-Alerts still verschluckt hat).

### Behavioral Changes (Issue #638)

| Aspekt | Vorher | Nachher |
|--------|--------|---------|
| **Severity-Filter** | `trip_alert.py:_filter_significant_changes` gab nur MODERATE/MAJOR durch; INFO-Alerts wurden still verschluckt | Jeder von einer aktiven Regel ausgelöste Change wird durchgereicht (kein MINOR/INFO-Filter mehr) |
| **Kanal-Routing** | Ein Alert = alle Briefing-Kanäle | Ein Alert = pro-Alert Kanal-Override; vorbelegt aus Briefing-Kanälen |
| **Severity in UI** | User konnte Severity wählen | Severity ist jetzt rein Label; wird von `weather_change_detection.py` abgeleitet |

---

## 23) Stage-Weather Internal Endpoint (Issue #1212, Slice R1)

Interner, nicht versionsstabiler Endpoint (Python FastAPI, Port 8000, **kein** Go-Proxy in
diesem Slice). Liefert pro Etappe eine Wetter-Zusammenfassung + Risiko-Ampel, berechnet über
die Python-`RiskEngine` — künftige Single Source of Truth der Cockpit-Risiko-Kacheln
(ADR-0015). Ersetzt die eigene Go-Risk-Logik erst in Slice R2 (dann Proxy).

**Handler:** `api/routers/internal.py` | **Service:** `src/services/stage_weather.py::compute_stage_weather()`

### GET /api/_internal/trips/{trip_id}/stages-weather

**Query-Parameter:** `user_id: str` (Pflicht — kein Fallback auf `"default"`)

**Response 200:**

```json
{
  "results": {
    "<stage_id>": {
      "weather_summary": {
        "temp_min_c": 8.5,
        "temp_max_c": 16.0,
        "wind_max_kmh": 42.0,
        "precip_mm": 3.2,
        "wmo_code": 61,
        "is_day": 1
      },
      "risk": "yellow"
    }
  }
}
```

- Nullbare Felder werden **explizit als `null`** serialisiert (nicht weggelassen).
- Ein Stage-Result ist entweder komplett `null` (Fail-soft, s.u.) oder trägt sowohl
  `weather_summary` (non-null) als auch `risk` (non-null).
- `risk` ∈ `"green"` \| `"yellow"` \| `"red"` — Maximum über alle Segmente der Etappe
  (identisch zur Briefing-Bewertung derselben Segmente, inkl. Wind-Exposition Regel 9).
  **Seit Issue #1474 Folge-Scheibe (`fix-1474-gewitterschwelle-cockpit`, 2026-08-04):**
  `green` heißt „kein Segment hatte irgendein erkanntes Risiko"; `yellow` deckt sowohl
  `RiskLevel.MODERATE` als auch `RiskLevel.LOW` ab, sobald **mindestens ein** Segment
  überhaupt ein Risiko hatte (z. B. ein leichtes Gewitter) — vorher zeigte eine Etappe mit
  ausschließlich leichtem Gewitter fälschlich `green`, weil `get_max_risk_level()` bei
  leerer Risikoliste ebenfalls `RiskLevel.LOW` liefert und diese Doppeldeutigkeit ungeprüft
  blieb; `red` unverändert bei `RiskLevel.HIGH`. Implementierung:
  `src/services/stage_weather.py::_compute_one_stage()` (Feld `has_any_risk`). Bewusst
  keine vierte Ampelfarbe für „leicht" — Spec:
  `docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md`.
- Etappen ohne ID (`stage.id == ""`) erscheinen **nicht** als Schlüssel in `results`.
- Etappen ohne Datum/Waypoints oder mit fehlgeschlagenem Wetter-Fetch liefern `null` statt
  eines 5xx (Fail-soft pro Etappe).

### Error Responses

| Status | Body | Szenario |
|--------|------|----------|
| 404 | `{"error":"not_found"}` | `trip_id` für den gegebenen `user_id` nicht gefunden |
| 500 | `{"error":"store_error"}` | Interner Lade-/Store-Fehler |

### Known Limitations

- Ensemble/Confidence (Regel 10) wird bewusst **nicht** gefetcht — farbneutral, siehe
  `docs/specs/modules/stage_weather_python_endpoint.md` Sektion „Known Limitations".
- Latenz-Parität zum alten Go-Handler wird erst in Slice R2 (Proxy live) verifiziert.

**Spec:** `docs/specs/modules/stage_weather_python_endpoint.md`

---

## 24) Corridor DTO (Issue #1231, Slice 1)

**Wertebereiche-Editor:** vereinheitlicht bisherige Trip-Alert-Schwellwerte (`AlertRule`,
Section 22) und Compare-Idealbereiche (`display_config["ideal_ranges"]`, Section 16) auf **einer**
gemeinsamen, rein additiven Datenstruktur. User-facing Label: „Wertebereich(e)"; Code-/Datenterm
bleibt `corridor`. Ein `Corridor` trägt zwei unabhängig kombinierbare Wirkungen: `notify` (warnen,
wenn ein Wert den Bereich verlässt) und `mark` (im Briefing markieren, solange ein Wert im
Bereich liegt).

**`notify` löst seit #1460 T1 (2026-08-03, ADR-0043) KEINEN Alarm mehr aus.** Zwischen #1444 S1
(2026-08-01) und #1460 T1 gab es kurzzeitig einen eigenen, additiven Schwellen-Alarm
(ADR-0040): `services/corridor_threshold.py::evaluate_corridor_thresholds()` prüfte je
Alarm-Lauf die Korridore mit `notify: true` gegen die frische Vorhersage und meldete eine
gerissene Grenze auch bei unveränderter Vorhersage, unabhängig von der Empfindlichkeitsstufe.
Das widersprach ADR-0009 (Alarme sind Abweichungs-Wächter, keine absolute Grenze) und ist mit
#1460 T1 zurückgebaut: Die Empfindlichkeitsstufe (`metric_alert_levels`) ist wieder der
**einzige** Alarm-Regler. Der Aufruf von `_evaluate_corridors()` in `trip_alert.py` ist
entfernt; `corridor_hits` ist strukturell immer eine leere Liste. `services/corridor_threshold.py`
(`evaluate_corridor_thresholds()`, `resolve_corridor_summary_field()`, `CorridorHit`) bleibt
unverändert im Repo bestehen, hat aber keinen Aufrufer mehr — ebenso der Render-Vertrag
(`CorridorEvent`, `to_corridor_events()`) und `alert_log.register_pairs_from_corridor_hits()`.
Eine Tour, deren einzige Alarmquelle Korridore mit `notify` waren, alarmiert seither wieder
gar nicht mehr, bis eine Empfindlichkeitsstufe gesetzt wird — beabsichtigt, nicht stillschweigend
in Kauf genommen. `corridors[].notify` bleibt Feld in Datenmodell und Persistenz (kein
Datenverlust), nur wirkungslos. `corridors[].mark` (Anzeige-Markierung) ist davon unberührt.
Spec: `docs/specs/modules/rework_1460_t1_relevanzfilter.md`, ADR: `docs/adr/0043-empfindlichkeitsstufe-als-niveau-statt-zweiter-alarm-typ.md`.

**Bei Gefahrenstufen-Größen (aktuell: Gewitter/`thunder_level_max`) wirkt die
Empfindlichkeitsstufe seit #1460 T1 über das erreichte Niveau, nicht über die Sprunggröße**
(löst den Rest des ADR-0040-Anliegens auf, ohne einen zweiten Alarm-Typ zu brauchen):
„sensibel" meldet jeden Stufenwechsel, „standard" das Erreichen/Verlassen der höchsten Stufe,
„entspannt" nur den vollen Sprung zwischen „kein Gewitter" und der höchsten Stufe — **symmetrisch
für Verschärfung UND Entwarnung**. `weather_change_detection.py::detect_changes()` vergleicht für
alle anderen (stetigen) Größen unverändert `abs(delta) > threshold`. Details: ADR-0043.

**`corridors[].metric` trug zwei Namensräume** (#1444 S2a, aus `resolve_corridor_summary_field()`
in `corridor_threshold.py`): eine `AlertMetric`-Kennung (die 5 fest verdrahteten Zeilen, z.B.
`wind_gust`, `snow_line`) ODER einen Katalog-`key` (die 18 seit #1425 aus dem Katalog gespeisten
Zeilen, z.B. `thunder_level_max`, `snow_depth_cm`). Seit #1460 T1 ist dieser Auflösungspfad ohne
Aufrufer aus `trip_alert.py` (s. o.) — die Beschreibung bleibt als Code-Doku für
`corridor_threshold.py` gültig, betrifft aber keinen Alarm-Auslöser mehr. Die doppelte
`corridor:<metrik>:<etappe>`-Namensraum-Problematik (#1455) betraf ausschließlich diesen nun
unerreichbaren Melde-Gedächtnis-Schlüsselraum.
Spec: `docs/specs/modules/feat_1444_s2a_schwellen_namensraum.md`.

```go
// internal/model/trip.go + internal/model/compare_preset.go (Go)
type Corridor struct {
    Metric string     `json:"metric"`           // kontextabhängige Metrik-ID (route: seit #1425 S2 die 6 AlertableMetrics + 17 weitere Katalog-Größen aus GET /api/compare/metrics, thunder_level ausgenommen; vergleich: Compare-Summary-Keys)
    Range  [2]*float64 `json:"range"`            // [min, max]; nil-Seite = offen (einseitig erlaubt)
    Notify bool       `json:"notify"`
    Mark   bool       `json:"mark"`
    Prio   string     `json:"prio,omitempty"`    // "hoch" | "mittel" | "niedrig" — nur Anzeige-Reihenfolge, kein Rang/Score
}
```

```python
# src/app/models.py (Python)
@dataclass
class Corridor:
    metric: str
    range: tuple[float | None, float | None]
    notify: bool
    mark: bool
    prio: str | None = None
```

```typescript
// frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts
export interface Corridor {
  metric: string;
  range: [number | null, number | null];
  notify: boolean;
  mark: boolean;
  prio?: "hoch" | "mittel" | "niedrig";
}
```

### Feldliste

| Feld | Typ | Beschreibung |
|------|-----|------------|
| metric | string | Metrik-ID, kontextabhängig: `route` bot ursprünglich (Issue #1231) nur die 6 `AlertableMetrics` (`wind_gust`, `precipitation_sum`, `temperature_min`, `temperature_max`, `thunder_level`, `snow_line`) — seit #1425 S2 kommen 17 weitere Größen aus dem zentralen Katalog (`GET /api/compare/metrics`) hinzu (23 insgesamt), `thunder_level` bleibt bewusst ausgenommen (weiterhin Prozent-Skala statt Katalog-Ordinalskala; Vereinheitlichung ist ein separater Folge-Workflow). `vergleich` nutzt die 10 Compare-Summary-Keys (`temp_max_c`, `temp_min_c`, `wind_max_kmh`, `gust_max_kmh`, `precip_sum_mm`, `thunder_level_max`, `visibility_min_m`, `snow_new_sum_cm`, `cape_max_jkg`, `freezing_level_m`) für `notify` — diese Liste selbst ist unverändert, ihre Herkunft im Backend seit #1435 E1a-1 aber nicht mehr die eigenständige `alarmCapable`-Prüfung des Compare-Katalogs, sondern dessen register-abgeleitetes `alertMetric` (s. Section 15.1); darüber hinaus stehen beiden Kontexten inzwischen dieselben Katalog-Größen als `mark`-fähige Wertebereiche zur Verfügung. `confidence_pct` (`selectable=false`, #710) darf in keinem der beiden Pools erscheinen. |
| range | `[min\|null, max\|null]` | Wertebereich; jede Seite unabhängig auf `null` (offen) setzbar, mind. eine Seite muss gesetzt sein (Editor-Validierung, UI-seitig — Slice 3+). `corridorInside(v, min, max)`: `v==null → null`; `v<min → false`; `v>max → false`; sonst `true` (`<`/`>` exklusiv geprüft, Grenzwert exakt gilt als „innen"). |
| notify | bool | Seit #1460 T1 (ADR-0043) **ohne Alarm-Wirkung** — verbleibt aus Bestandsschutz im Datenmodell (kein Feld-Entfernen), wird aber von keiner Auswertung mehr gelesen. Alarme laufen ausschließlich über `display_config.metric_alert_levels[metric]` (entspannt/standard/sensibel), unabhängig von diesem Schalter. Die Stufen-Feinwahl ist im CorridorEditor nicht einzeln wählbar (Known Limitation, gespeicherter Wert bleibt erhalten). |
| mark | bool | Markiert im Compare-Mail-Renderer (`compare_html.py`) die Zelle grün, solange `corridorInside(value)===true` — additiv zur bestehenden Severity-Färbung, ohne Einfluss auf `comparison_scoring.py::calculate_score()`. |
| prio | enum \| optional | `"hoch"` \| `"mittel"` \| `"niedrig"` — **nur** Anzeige-Reihenfolge im Editor, kein Rang-/Score-Einfluss. |

### Single-Source-Matchlogik `corridorInside()`

Wortgleich an drei Stellen implementiert (keine Duplikate zulässig):

| Ort | Datei | Zweck |
|---|---|---|
| Frontend-Util | `frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts` | ersetzt `shared/layout-tab/ltIdealRange.ts::isIdealGood()`, Basis für Editor-Live-Vorschau |
| Python-Port | `src/services/corridor_match.py::corridor_inside()` | Compare-Mail-Renderer (`compare_html.py`) |

```js
function corridorInside(value, min, max) {
  if (value == null) return null;               // kein Messwert → neutral
  if (min != null && value < min) return false; // unter dem Korridor
  if (max != null && value > max) return false; // über dem Korridor
  return true;                                  // im Korridor
}
```

### Additivität & Datenerhalt

- **Trip (`internal/model/trip.go`) und ComparePreset (`internal/model/compare_preset.go`):**
  `corridors` steht **additiv neben** `AlertRules` bzw.
  `display_config["ideal_ranges"]` — beide bestehenden Mechanismen bleiben bis zu einem
  späteren, hier nicht enthaltenen Cutover die technische Wahrheit für den Δ-Wächter. Bestandsdaten
  ohne `corridors` laden mit leerem Slice, kein Feldverlust (Read-Modify-Write beim Speichern).
  Seit Issue #1244 gilt das nicht mehr nur beim Speichern, sondern symmetrisch auch beim Laden
  (`LoadTrip`/`LoadTrips`/`LoadComparePresets`) — s. Invarianten-Hinweis in Section 10.5 und 16.
- **Loader-Normalisierung (`src/app/loader.py`):** ein malformed `range` macht nie den Trip
  unladbar — defensiver Float-Cast, `isfinite`-Prüfung, Skalar/`null`/Kurz-Array-Eingaben werden
  still auf `[None, None]` normalisiert statt einer Exception.
- **Migration (`scripts/migrate_1231_corridors.py`, Slice 2):** überführt Bestands-`AlertRule`s
  nach `corridors[notify]` und Compare-`ideal_ranges` nach `corridors[mark]`, verlustfrei
  (Report `alt → neu` je Eintrag), respektiert #1191-Erhalt (`active_metrics: []` bleibt leer).

**Spec:** `docs/specs/_archive/modules/issue_1231_korridor_editor.md`

---

## Changelog

- 2026-08-11: Issue #1745 Scheibe A — Premium-SMS als vierter Kanal in der Alarm-Kanal-Auswahl
  (Alarme-Reiter, Trip UND Ortsvergleich). **Keine DTO-/Feld-Änderung** — `alert_channels.premium_sms`
  und `alert_channel_thresholds.premium_sms` (s. Abschnitte unten) existieren bereits seit #1701 S2b;
  diese Scheibe macht sie erstmals über die Oberfläche bedienbar (vierte Kanalzeile „Premium-SMS
  (Garmin inReach)" direkt unter SMS, gesperrt mit Hinweis unter Tarif `standard`, eigene
  Dringlichkeits-Schwelle). Reines Frontend (`frontend/src/lib/components/shared/AlarmeTab.svelte`
  u.a.), kein Go-/Python-Code geändert. Klarstellung, da leicht zu verwechseln: das gilt nur für den
  **Alarm**-Pfad — der **Versand**-Pfad (`send_premium_sms`, Trip-Briefing) bleibt seit #1676 S2a
  bewusst auf Trips beschränkt, kein Ortsvergleich-Versand; die Alarm-Kanal-Auswahl war schon seit
  #1701 ausdrücklich auch für den Vergleich vorgesehen (#1701 AC-4) und ist das jetzt auch in der
  Oberfläche. Regen-/Radar-Alarme lesen weiterhin nur das Briefing-Flag, unverändert durch diese
  Scheibe (Scheibe B, #1752, offen). Spec: `docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md`.
- 2026-08-11: Issue #1717 Scheibe S3 — Premium-SMS in der Oberfläche. `GET /api/auth/profile`
  liefert vier neue, **rein lesende** Felder: `premium_sms_reply_to`/`premium_sms_reply_at`
  (Rohwerte, `omitempty`), `premium_sms_reply_state` (`none`/`stale`/`fresh`, immer vorhanden,
  serverseitig aus `model.PremiumSmsReplyTTL` abgeleitet) und `premium_sms_allowed` (immer
  vorhanden, eigenes Tarif-Gate `model.PremiumSmsAllowed` — nur `premium`, NICHT von
  `sms_allowed` abgeleitet). `PUT /api/auth/profile` nimmt keins davon an (AC-7) — die gelernte
  Rückadresse bleibt allein durch den internen Lernpfad (#1676 S1) schreibbar. `Trip` bekommt
  das vierte abgeleitete Flach-Feld `send_premium_sms` (nicht autoritativ, aus
  `report_config.send_premium_sms` bei jedem Load neu abgeleitet und zuvor auf `nil` zurückgesetzt).
  Die Verfallsfrist existiert damit zwangsläufig zweimal (Python-Sendepfad + Go-Ableitung) und wird
  von `tests/test_premium_sms_ttl_drift.py` gegeneinander bewacht.
- 2026-08-11: Issue #1701 Scheibe S2b — Premium-SMS wird vierter Kanal im
  Alarm- UND Ortsvergleich-Pfad (Vorgänger: S2a #1676, ausschließlich
  Trip-Briefing). `AlertChannelsConfig` bekommt `PremiumSms *bool` — dabei
  entfällt die frühere „All-or-nothing"-Prämisse: alle vier Felder (Email/
  Telegram/Sms/PremiumSms) sind jetzt `*bool` mit **Feld-Level-Merge**
  (Vorbild `AlertChannelThresholdsConfig`), ein PUT ohne ein Feld lässt
  dessen Bestandswert unangetastet statt ihn auf `false` zurückzusetzen.
  `AlertChannelThresholdsConfig` bekommt `PremiumSms *string` als viertes
  Geschwisterfeld (ADR-0046-Pflicht). `ComparePreset.SendPremiumSms *bool`
  neu (eigenes Feld, kein `alert_channels`-Sub-Objekt im Ortsvergleich).
  Tier-Gate `premium_sms_allowed()` (NICHT `sms_allowed()`) an allen drei
  Alarmpfaden (Änderung/Radar/amtlich) und beiden Kontexten (Trip/Compare).
  Siehe `docs/specs/modules/feat_1701_alarm_premium_sms.md`.
- 2026-08-10: Issue #1676 Scheibe S2a (ADR-0049) — `TripReportConfig.send_premium_sms`
  (bool, default `false`) macht Premium-SMS (Garmin inReach) zum vierten, eigenständigen
  Versandkanal `premium_sms` — **ausschließlich fürs Trip-Briefing**. Fester Absender
  `4916092172595` (unabhängig von `sms_from`), Empfänger ausschließlich die in Scheibe S1
  gelernte Rückadresse aus `user.json` (nie `sms_to`), Verfall nach 30 Tagen, fail-closed mit
  auswertbarem Grund. Lebt bislang nur im freien `report_config`-Schlüssel, kein eigenes
  Go-Struct-Feld analog `send_sms`/`send_telegram` (folgt erst mit S3). **Ausdrücklich nicht
  betroffen:** `AlertChannelsConfig`/`AlertChannelThresholdsConfig` — Premium-SMS ist bis
  #1701 kein Alarm-Kanal.
- 2026-08-10: Issue #1679 (LPI-Teil) — `lightning_potential_lpi_jkg`-Schwellentabelle in der
  Gewitterstufen-Fusion ist jetzt **gebietsabhängig** statt einer globalen 5/20/50-Leiter:
  DE_ALPEN (ICON-D2) bekommt die belegte 1/30/50 J/kg (Bína et al.), EU_REST (ICON-EU) bleibt
  als Interim unverändert bei 5/20/50, bis #1678 eine eigene Eichung liefert. Kein DTO-/Feld-
  Wechsel, nur die interne Schwellenquelle (`app.model_registry.LPI_THRESHOLDS_JKG`/
  `lpi_thresholds_jkg()`). Siehe `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md`.
- 2026-08-09: Issue #1517 — `POST /api/auth/register` prüft die Existenz des Usernamens
  (`s.UserExists`) jetzt VOR der #1226-E-Mail-Pflichtprüfung; Reihenfolge der reinen
  Format-Validierungen (Username-Länge/-Regex, Passwort-Länge) bleibt unverändert davor.
  Bug: ein Register-Aufruf ohne `email`-Feld gegen einen bereits existierenden Username
  lieferte fälschlich 400 `validation failed` statt 409 `user already exists` — brach u.a.
  `scripts/setup-validator-user.sh`, das nie ein `email`-Feld sendet. Kein neues Feld, keine
  DTO-Änderung, nur Prüfreihenfolge in `internal/handler/auth.go`. Siehe
  `docs/specs/modules/fix_1517_validator_register_order.md`.
- 2026-08-07: Issue #1552 — `GET /api/metrics` liefert je Größe zusätzlich
  `trip_default_enabled` (bool), gesetzt aus dem neuen Registerfeld
  `trip_default_rank` (`src/app/metric_catalog.py`). Es markiert die
  Vorbelegung eines **neu angelegten Trips** und ist bewusst unabhängig von
  `default_enabled` (das weiterhin `build_default_display_config()` und damit
  die Orte-/Abonnement-Konfiguration versorgt und dafür unverändert bleibt).
  Anlass: Anlege-Dialog zeigte bislang `default_enabled` (10 Größen) als
  Vorbelegung, während ein nie eingestellter Trip tatsächlich einen anderen
  Siebener-Satz (`DEFAULT_TRIP_METRIC_IDS`) verschickte — Überschneidung nur
  5. Seit #1552 gilt einheitlich der Sieben-Satz mit expliziter Rangfolge
  (`temperature`(1) … `visibility`(7)); `DEFAULT_TRIP_METRIC_IDS`
  (`src/output/renderers/trip_metric_ids.py`) wird jetzt aus dem Register
  abgeleitet statt hart gelistet. Frontend-Typ `MetricEntry.trip_default_enabled`
  (`frontend/src/lib/types.ts`) ist bewusst optional, um bestehende
  Test-/Mock-Kataloge nicht nachrüsten zu müssen — die echte Serverantwort
  liefert das Feld unbedingt. Section 15 aktualisiert. Siehe
  `docs/specs/modules/fix_1552_neuanlage_metrikauswahl.md`.
- 2026-08-03: Issue #1460 Teil 1 (Epic #1458 Scheibe 2, ADR-0043 löst ADR-0040 ab) —
  `corridors[].notify` fällt als Alarm-Auslöser weg; die Empfindlichkeitsstufe
  (`metric_alert_levels`) ist wieder der einzige Regler. Bei Gefahrenstufen-Größen
  (aktuell Gewitter/`thunder_level_max`) wirkt sie über das erreichte Niveau statt die
  Sprunggröße, symmetrisch für Verschärfung und Entwarnung. `AlertStateService.reset()`
  löscht beim Briefing-Versand nur noch den Änderungs-Schlüsselraum, der amtliche Raum
  (Präfix `official_alert:`) bleibt erhalten. Amtliche Warnungen bekommen für Trip und
  Ortsvergleich ein eigenes Zeitfenster je Ort/Etappe statt jede irgendwann gültige
  Warnung an jeder Koordinate der Restroute zu melden. Reiner Python-Kern-Umbau, kein
  DTO-Feld entfernt/hinzugefügt. Section 24 aktualisiert. Siehe
  `docs/specs/modules/rework_1460_t1_relevanzfilter.md`.
- 2026-08-01: Issue #1406 Scheibe B (E2 von #1435, Epic #1372) — der
  Ortsvergleich-Stundenverlauf schöpft aus dem zentralen Wetterkatalog statt aus
  einem eigenen Zehner-Vokabular. Die Zuordnung Stundenverlaufs-Kennung →
  Wettergröße wurde bis dahin an VIER Stellen gepflegt und ist jetzt EINE:
  `src/output/renderers/compare_hourly_metric_ids.py`. Wire-Format von
  `display_config.hourly_metrics` unverändert `string[]`; geschrieben werden ab
  jetzt Katalog-IDs, die zehn historischen Kurzformen bleiben dauerhaft lesbar
  (keine Migration). Neue, rein additive Felder in der Antwort von
  `GET /api/compare/metrics`: `hourlySelectable`, `hourlyNotSelectableReason`,
  `hourlyDefault`, `hourlyMergeOnly`, `hourly_legacy_keys` — damit die
  Bedienfläche weder eine eigene Alias-Tabelle noch eigenes Wissen über
  Ausnahmen braucht. `POST /api/_validator/compare-email-preview` nimmt neu ein
  optionales `hourly_metrics` entgegen (vorher zeigte die Vorschau immer die
  volle Spaltenmenge). Details:
  `docs/specs/modules/feat_1406b_stundenverlauf_katalog.md`.
- 2026-08-01: Issue #1447 Scheibe S1 — `POST /api/scheduler/alert-checks`
  (Section 14.6, neu dokumentiert) bekommt eine harte Zeitobergrenze
  (`ALERT_RUN_DEADLINE_SECONDS = 90.0`, deutlich unter den 120s des
  Go-Client-Timeouts) und meldet einen Deadline-Abbruch jetzt als
  `status: "partial"` mit `checked`/`skipped`/`reason` statt unverändert
  `status: "ok"`. `TripAlertService.check_all_trips()` liefert dafür ein
  `AlertCheckRunResult` statt eines blossen `int`. Zusätzlich konfiguriert
  `api/main.py::configure_logging()` erstmals den Python-Core-Root-Logger
  (Stufe über `GZ_LOG_LEVEL`) — vorher wurden alle `logger.info`/`.warning`-
  Zeilen aus `src/` verworfen. `httpx`/`httpcore` fest auf `WARNING`
  gehalten (Adversary-Befund F001 — sonst Telegram-Bot-Token im Log, s.
  Section 14.6). ADR-0038. Der Go-Scheduler wertet die neuen
  Felder noch nicht aus (Scheibe S2, separate Spec).
- 2026-07-31: Issue #1435 Etappe E1a-1 — Alarmfähigkeit wird eine
  Eigenschaft des zentralen Wetter-Namensregisters. `MetricDefinition`
  bekommt zwei neue Felder, `alert_metrics` (Auswertung → absolute
  Alarm-Identität) und `change_alert_metric` (Änderungsraten-Alarm der
  Größe, orthogonal zu `alert_metrics`), plus den Resolver
  `alert_metric_for(metric_id, aggregation)`. `GET /api/metrics` liefert
  je Auswertung `alert_metric` und je Größe `change_alert_metric` (beide
  `null` möglich, s. Section 15). `GET /api/compare/metrics` liefert an
  allen 26 Einträgen zusätzlich `alertMetric`; `alarmCapable` ist ab
  jetzt dessen Boolean-Sicht statt einer zweiten, handgepflegten Liste
  (s. Section 15.1). Verhaltensneutral: die register-abgeleitete
  `alarmCapable`-Menge bleibt exakt dieselben 10 Compare-Keys wie zuvor;
  `compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` bleibt das tatsächlich
  alarmauslösende Modul, unverändert. Luftfeuchtigkeit bleibt bewusst
  unregistriert (Epic #1374 Invariante 1, „kein Element ohne Wirkung") —
  die Auswertungskette (`weather_change_detection.py`) kennt
  `AlertMetric.HUMIDITY` nicht. Siehe
  `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md`.
- 2026-07-28: Issue #1357 (Epic #1372 Scheibe S4a) — `MetricConfig.aggregations`
  dokumentiert. Renderer liest das Feld erstmals: bestimmt, welche
  Tagesauswertung (Spanne/Tiefst-/Höchst-/Mittelwert) in der
  Kachelzeile der Trip-Briefing-Mail erscheint — **Einzelwahl über vier
  sich ausschließende Möglichkeiten**, keine Mengen-Wahl (PO 2026-07-28:
  „Es gibt kein zusätzlich: entweder oder"). Betrifft heute Temperatur und
  gefühlte Temperatur (einzige Größen mit mehr als einer berechenbaren
  Auswertung). Siehe `docs/specs/modules/trip_aggregation_selection.md`.
  **Korrektur 2026-08-15 (Issue #1728 Scheibe 1):** Dieser Wirkmechanismus
  ist seither entfallen — die Kachelzeile zeigt für Temperatur/Gefühlte
  Temperatur jetzt unbedingt die Spanne. Details in der `MetricConfig`-
  Feldreferenz oben (`aggregations`-Zeile).
- 2026-07-26: Issues #1366 + #1361 Befund 3 (S3 Scheibe B von Epic #1372) —
  `resolve_enabled_metrics()`/`resolve_hourly_metrics()` unterscheiden jetzt
  „Feld fehlt" (Legacy-Fallback: alle Größen/Spalten) von „Feld vorhanden und
  leer bzw. vollständig unauflösbar" (keine Größen/Spalten) — vorher fielen
  beide Fälle auf „alle" zurück, das genaue Gegenteil einer bewussten
  Leerauswahl. Für den Stundenverlauf bildet `resolve_compare_render_options()`
  eine leere/unauflösbare Auswahl zusätzlich auf `hourly_enabled=False` ab,
  damit der Block ganz entfällt statt einer Tabelle nur mit Uhrzeit-Spalte.
  Unauflösbare Stundenverlauf-Kennungen werden jetzt geloggt statt still
  verworfen. Section 16 (`active_metrics`/`hourly_metrics`) aktualisiert.
  Siehe `docs/specs/modules/compare_empty_metric_selection.md`.
- 2026-07-26: Issue #1373 S2 Scheibe B (`1f413a54`) — Speicherformat von
  `display_config.active_metrics` (Compare-Preset, `kind=vergleich`)
  umgestellt: geschrieben wird ab dieser Lieferung ausschließlich
  `[{"metric_id": ..., "aggregation": ...}, ...]` statt der bisherigen
  Anzeige-Schlüsselliste (`["temp_max_c", ...]`). Das Altformat bleibt
  dauerhaft lesbar (nicht nur übergangsweise, s. Section 16), eine gemischte
  Liste aus Alt- und Neuformat ist gültige Eingabe und wird pro Element
  aufgelöst. Reihenfolge (#1335/#1359) und die #1191-Unterscheidung
  `[]` vs. fehlendes Feld bleiben unverändert. Migration:
  `scripts/migrate_1373_compare_active_metrics_format.py` (s.
  `docs/reference/operations_playbook.md`). Details, Restrisiken (R1
  Mischlisten durch alte Browser-Sitzungen, R2 Rollback-Absturz):
  `docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md`.
- 2026-07-26: Issues #1391/#1392 — `SegmentWeatherSummary` bekommt drei
  additive Felder `cloud_low_avg_pct`/`cloud_mid_avg_pct`/`cloud_high_avg_pct`
  (Optional, Default `None`; Tages-Mittel mit `round()` wie `cloud_avg_pct`).
  Der Ortsvergleich rechnete diese Werte zuvor an zwei Stellen selbst mit
  `int()`-Abschneiden — jetzt eine kanonische Rechnung, von Trip- und
  Compare-Pfad genutzt; `LocationResult` und der Vergleichs-Renderer bleiben
  unverändert (Datenmodell-Konvergenz ist #1230). Zusätzlich trägt
  `snowfall_limit` im zentralen Katalog jetzt `summary_fields={"min":
  "snowfall_limit_m"}`, und `compute_extended_metrics()` befüllt das bereits
  existierende Feld auch im Trip-Pfad — vorher konnte der
  Abweichungs-Alarm der Schneefallgrenze strukturell nie feuern. Keine
  Persistenz-Migration nötig (additiv, Bestands-Schnappschüsse laden mit
  `None`). Damit ist `AGGREGATION_CHECK_EXEMPTIONS` (s. #1373 Scheibe A)
  leer. See `docs/context/fix-1391-1392-tageswerte.md`.
- 2026-07-26: Issue #1373 S2 Scheibe A — `GET /api/compare/metrics` trägt
  pro Eintrag zusätzlich `metric_id` und `aggregation`, gebunden an die
  Größen des zentralen Wetterkatalogs (`src/app/metric_catalog.py`). Der
  Compare-Katalog bleibt eine kuratierte Tabelle — die neuen Felder
  belegen die Beziehung, erzeugen den Katalog aber nicht. `key` bleibt
  unverändert für Rückwärtskompatibilität. Weiterhin genau 26 Einträge.
  Siehe Section 15.1.
- 2026-07-26: Issues #1383/#1385/#1386 — Alarm-Zeitstempel liefen in
  mehreren Renderpfaden in UTC statt Ortszeit (Radaralarm-Ortsvergleich,
  gebündelte Mehr-Orte-Alarme, Abweichungs-Alarm-Ereigniszeit). Ursache
  durchgängig: zu frühe String-Bildung, bevor die ortskennende Schicht die
  Zeitzone auflösen konnte. `WeatherChange.occurred_at` (oben ergänzt,
  vorher in dieser Tabelle fehlend seit #914) ist Teil des Fixes für #1386.
  Dabei die `WeatherChange`-Tabelle auf Vollständigkeit gegen den
  Dataclass-Ist-Stand geprüft: `segment_id` fehlte ebenfalls (seit #131) —
  jetzt ergänzt. Tabelle deckt damit alle neun Felder von `WeatherChange`
  (`src/app/models.py`) ab.
- 2026-07-24: Issue #1351 (Teil 1 + Teil 2) — Zwei unabhängige Compare-
  Änderungen. **Teil 1:** Neuer Katalog-Eintrag `wind_chill_max_c`
  („Gefühlte Temp. max") im Compare-Metrik-Katalog
  (`src/output/renderers/compare_metric_catalog.py`) — `GET
  /api/compare/metrics` liefert damit **26** statt 25 Einträge (Section
  15.1 aktualisiert). Ortsvergleich wählbar und in der Vergleichs-Mail
  (HTML + Plain/SMS) darstellbar; im Trip-Briefing weiterhin NICHT
  verfügbar (ausgegliedert nach #1357 — dem Trip fehlt ein
  Auswahl-Pfad für Aggregationen). **Teil 2:** `channel_layouts` wird im
  Compare-Pfad nicht mehr mitgeführt — `buildComparePresetSavePayload`
  (`compareEditorSave.ts`) entfernt den Key beim Speichern jetzt aktiv aus
  `display_config`, statt ihn wie bisher über den `...original`-Spread
  round-zu-trippen. Einmalige Migration
  `scripts/migrate_1351_drop_compare_channel_layouts.py` (idempotent,
  Backup vor Schreiben, nur `kind=vergleich`) räumt Bestandsdaten. **Der
  Trip-Pfad ist unverändert** — dort bleibt `channel_layouts` eine echte,
  gelesene Funktion. Macht die „round-trippt unverändert weiter"-Aussage
  zu `channel_layouts` im #1299/#1291/#1287-Eintrag vom 2026-07-18 (unten)
  für den Compare-Pfad obsolet — die dortige `top_n`-Aussage bleibt
  unverändert gültig. Siehe `docs/specs/modules/rework_1351_compare_catalog.md`.
- 2026-07-24: Issue #1350 Teil 3 (SSoT-Abschluss) — `GET /api/compare/metrics`
  trägt pro Eintrag zusätzlich `alarmCapable: bool` (D1 Hybrid). Der
  Schwellen-Editor des Ortsvergleichs (`corridorEditorState.ts`) bezieht seine
  Metrik-Definitionen jetzt aus diesem Endpoint statt aus dem gelöschten
  `compareMetricDefs.ts`. Siehe Section 15.1.
- 2026-07-23: Issue #1350 Teil 1 (Strangler-Migration) — neuer read-only
  Endpoint `GET /api/compare/metrics` liefert den 25-Einträge-Ortsvergleich-
  Metrik-Katalog aus einer einzigen Backend-Quelle
  (`src/output/renderers/compare_metric_catalog.py`), Go-Proxy analog
  `/api/metrics`. Rein additiv — Teil 1 stellt den Endpoint nur bereit, das
  Frontend konsumiert ihn noch nicht (`compareMetricDefs.ts` bleibt Quelle
  bis Teil 2). Siehe Section 15.1.
- 2026-07-23: Issue #1346 — Stiller Briefing-Totalausfall wird laut. Der
  BetterStack-Heartbeat (`HeartbeatComparePresets`) ist von `comparePresetsDaily()`
  nach `briefingDispatch()` verlagert und deckt nun den gesamten stündlichen
  Briefing-Versand ab: Ping nur wenn `trip_reports_hourly` **und**
  `compare_presets_daily` erfolgreich sind (vorher hing er allein am Ortsvergleich
  und verdeckte einen Trip-Totalausfall). Zusätzlich edge-getriggerter MQ-Alarm an
  `infra` bei `trip_reports_hourly` ok→error (high) + Recovery error→ok (normal),
  analog `dataWriteSelftest`. Kein neuer BetterStack-Heartbeat (Kontingent).
  Reine Go-Änderung (`internal/scheduler/scheduler.go`).
- 2026-07-18: Issue #1290 (E1 von Epic #1301, ergänzend #1288/E2) —
  `POST /api/scheduler/compare-presets-daily` liefert jetzt `failed` als neues
  Response-Feld, identisches Schema zu `/api/scheduler/trip-reports` (Issue
  #766): `status` wird `"partial"` sobald `failed > 0`, `count` zählt weiterhin
  nur erfolgreich versendete fällige Presets. `run_compare_presets_daily`/
  `CompareDispatchStrategy.result()` liefern dafür `tuple[int, int]`
  (sent, failed) statt der bisherigen internen `error_count`-Zählung ohne
  Response-Sichtbarkeit. HTTP-Statuscode bleibt immer 200.
- 2026-07-18: Issue #1299/#1291/#1287 (Scheibe C2 von Epic #1301) —
  `display_config.hourly_metrics`/`hourly_enabled` sind jetzt im Hub-
  Layout-Tab (`CompareTabs.svelte`, `activeTab==="layout"`) bedienbar,
  vorher nur über den seit Scheibe S3 weggeleiteten Legacy-`CompareEditor`
  erreichbar. Neue reine Persist-Bridge-Funktionen
  `hydrateLayoutFieldsFromPreset`/`flushPendingLayoutSave`/
  `rollbackLayoutSnapshot` in `compareHubWizardBridge.ts`, Muster wie die
  C1-Wetter-Metriken-Bridge (Issue #1311). `top_n` und die
  „Spalte/Detail"-Zuordnung (`channel_layouts`) sind aus der Bedienung
  entfernt (Attrappen, #1287/#1291), round-trippen aber unverändert weiter
  (kein Feldverlust, Read-Modify-Write). Kein neues Wire-Format-Feld —
  beide Felder existierten bereits (#1106/#1107), nur der Schreib-Zugang
  ändert sich. Siehe `docs/specs/modules/compare_hub_hourly_metrics.md`.
  **Überholt seit 2026-07-24 (#1351, s.o.) für `channel_layouts`:** das
  Feld round-trippt im Compare-Pfad nicht mehr, sondern wird beim Speichern
  aktiv entfernt. Die `top_n`-Aussage hier bleibt unverändert gültig.
- 2026-07-16: Issue #1278 + #1285 (eine Arbeit, gemeinsame Datenbasis) —
  Vergleichs-Mail bekommt je Ort einen Kurz-Zusammenfassungssatz (geteilter
  Trip-Baustein, kein Compare-eigener Formatierungscode) und fünf bisher
  still verworfene Tages-Aggregate werden repariert. **`LocationResult`**
  (`src/app/user.py:117`, rein transientes Objekt, keine Persistenz) bekommt
  fünf neue, **additive optionale Felder mit Default `None`**:
  `precip_sum_mm: float|None`, `thunder_level_max: ThunderLevel|None`,
  `visibility_min_m: int|None`, `uv_index_max: float|None`,
  `pop_max_pct: int|None`. Bestehende Konstruktoren ohne diese Keyword-
  Argumente (`dict_to_comparison_result()`, `validator_render_service.py`)
  funktionieren unverändert; der Renderer leitet den Wert dann live aus
  `hourly_data` ab. `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`
  bekommt fünf neue Einträge (`precip_sum_mm`, `thunder_level_max`,
  `visibility_min_m`, `uv_index_max`, `pop_max_pct`) — vorher wurden diese
  Metriken bei der Matrix-Auswahl still verworfen. Neues additives Frontend:
  eine Katalog-Zeile `pop_max_pct` (Regenwahrscheinlichkeit) in
  `frontend/src/lib/components/compare/compareMetricDefs.ts::ALL_METRICS`
  (kein neues UI-Element, nur ein Datensatz mehr in einer bestehenden Liste).
  Nebenbefund mitgefixt: der Kopf der STUNDEN-Sektion in der Vergleichs-Mail
  (`compare_html.py`) zeigte fest verdrahtet "09–16 Uhr" — ein toter Rest des
  mit #1268 abgeschafften Zeitfensters, jetzt entfernt. Kein Wire-Format-
  Impact auf Go/TS (`ComparisonResult`/`LocationResult`-DTOs sind reine
  Python-interne Render-Objekte, nicht Teil der Go-/REST-Schicht). Siehe
  `docs/specs/modules/compare_location_summary.md` und
  `docs/specs/modules/compact_summary.md`.
- 2026-07-16: Issue #1270 — Echte Kanal-Vorschau + tatsächlicher Telegram/SMS-Versand
  für den Orts-Vergleich. Neuer Endpoint `POST /api/preview/compare/{preset_id}`
  (`api/routers/preview.py`, Go-Proxy `internal/handler/preview_proxy.go::ComparePreviewProxyHandler`,
  `router.go:167`) liefert `{subject, email_html, telegram, sms, sms_char_count}` aus
  **einem** `ComparisonEngine.run()` — ADR-0011-Muster, bewusst EINE Route statt der
  Drei-Routen-Form der älteren Trip-Preview-Endpoints (die vor ADR-0011 entstanden).
  Neuer `src/services/compare_preview_service.py::ComparePreviewService` lädt Preset +
  echte Orte des Nutzers (ersetzt den Stub-Ort aus dem Validator-Endpoint #464 als
  Datenquelle der UI-Vorschau; der Stub selbst bleibt unverändert). Neue Renderer
  `render_compare_telegram`/`render_compare_sms` (`src/output/renderers/comparison.py`,
  kein Score/Rang, Budget über `CHANNEL_LIMITS`). Verhaltensänderung: Compare-Briefings
  waren bis dahin Ende-zu-Ende E-Mail-only (`send_telegram`/`send_sms` wurden
  gespeichert, aber beim Versand nie gelesen) — jetzt sendet
  `NotificationService.send_compare_report(...)` tatsächlich über Telegram/SMS, mit
  Kanal-Gate (Opt-in UND `can_send_*()` UND `sms_allowed()`) und Fail-soft je Kanal;
  `send_one_compare_preset` ist darauf umgehängt. Der Alarm-Pfad
  (`compare_alert.py`/`compare_radar_alert.py`) bleibt unverändert E-Mail-only.
  Bugfix nebenbei: `presetChannels()` (`subscriptionHelpers.ts`) liest jetzt
  `send_telegram`/`send_sms` statt `display_config.channel_layouts`-Keys. Siehe
  Section 20 und `docs/specs/modules/compare_channel_preview_dispatch.md`.
- 2026-07-13: Issue #1250 (Scheibe 1) — die 5 rohen `json.loads`-Lese-Call-Sites für
  `compare_presets.json` (3 Compare-Alert-Services, Scheduler-Dispatch Daily und
  Einzelversand) laufen jetzt über den zentralen Loader `load_compare_presets()` /
  `compare_preset_from_dict()` / `compare_preset_to_dict()` (`src/app/loader.py`, neue
  `ComparePreset`-Dataclass in `src/app/models.py`). Reiner Lese-Kontrakt ohne
  Normalisierung; Rückgabe (Dict-Liste) bleibt für bestehende Konsumenten unverändert.
  Der Schreibpfad (`save_compare_preset_status`) bleibt unverändert Dict-basiert. Kein
  API-/Schema-/Verhaltens-Change. Siehe Abschnitte 17 und 18.
- 2026-07-13: Issue #1244 — Null-Listenfelder brechen den Trip-Loader: `Trip.Stages`,
  `Stage.Waypoints`, `Trip.AlertRules`, `Trip.Corridors` sowie `ComparePreset.Corridors`/
  `LocationIDs`/`Empfaenger` sind jetzt **immer** `[]`, nie `null` — durchgesetzt in beide
  Richtungen (Schreiben UND Lesen, inkl. HTTP-Response) via `normalizeTrip()`
  (`internal/store/trip.go`) und `NormalizeComparePreset()` (`internal/store/compare_preset.go`).
  `SaveTrip` nimmt seit diesem Fix einen Pointer statt eines Value-Receivers, damit der Aufrufer
  die normalisierten Werte sieht. Python-Loader (`src/app/loader.py`) heilt `null` zusätzlich
  fail-soft beim Lesen (`data.get("x") or []`); `load_all_trips()` loggt einen nicht ladbaren
  Trip jetzt als `ERROR` statt `warning`. Bestandsdaten-Migration:
  `scripts/migrate_1244_null_lists.py` (Dry-Run-Default, `--execute`, tar.gz-Backup, idempotent).
  Erweitert die bisherige AlertRules-only-Coercion aus Issue #205. Siehe
  `docs/specs/_archive/modules/fix_1244_null_list_fields.md`.
- 2026-07-12: Issue #1231 (Slice 1 von Epic #29 „Briefing-Abo-Chassis") — neues additives
  Datenmodell `Corridor{metric, range:[min|null,max|null], notify, mark, prio?}` an
  `Trip.Corridors` (Go) und `ComparePreset.Corridors` (Go), Python-Pendant in
  `src/app/models.py`. Vereinheitlicht künftig Trip-Alert-Schwellwerte und Compare-Idealbereiche
  hinter einem gemeinsamen Editor (Slices 3–7, folgen), ohne den bestehenden Δ-Wächter
  (`AlertRule`/`metric_alert_levels`) zu verändern — rein additiv. Single-Source-Matchlogik
  `corridorInside()` in Python (`src/services/corridor_match.py`) und TS
  (`frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts`). Loader normalisiert malformed
  `range` defensiv (nie trip-unladbar). Siehe Section 24 und
  `docs/specs/_archive/modules/issue_1231_korridor_editor.md`.
- 2026-07-11: Issue #1226 — `POST /api/auth/register` bekommt neues Pflichtfeld `email`
  (minimale `strings.Contains(email, "@")`-Prüfung, kein Uniqueness-Check); neue
  Fehlerantworten `validation failed` (fehlend) und `invalid_email` (kein `@`). Bei
  gültiger Adresse wird nach Kontoanlage der bestehende Verifikations-Dispatch
  `dispatchVerificationMail` (aus #1219) ausgelöst — analog dazu jetzt auch bei
  Google-OAuth-Erstanmeldung (`createOAuthUser`) und Passkey-Public-Registrierung
  (`PasskeyRegisterPublicFinishHandler`), nicht mehr nur bei Profil-E-Mail-Änderungen.
  Kein Dispatch bei OAuth-Login eines bestehenden Nutzers. Siehe
  `docs/specs/_archive/modules/fix_1226_register_verify.md`.
- 2026-07-10: Issue #1212 (Slice R1) — neuer interner Endpoint `GET
  /api/_internal/trips/{trip_id}/stages-weather` (`api/routers/internal.py`,
  `src/services/stage_weather.py::compute_stage_weather()`): liefert pro Etappe
  Wetter-Zusammenfassung + Risiko-Ampel (green/yellow/red) über die Python-`RiskEngine`,
  künftige SSoT der Cockpit-Risiko-Kacheln (ADR-0015). Ersetzt die Go-Risk-Logik erst in
  Slice R2 (dann Proxy); R1 ist rein additiv, kein Go/Frontend-Impact. Siehe Section 23 und
  `docs/specs/modules/stage_weather_python_endpoint.md`.
- 2026-07-08: Issue #1110 — Ortsvergleich-Mail v2: Die HTML-/Klartext-Darstellung der
  Compare-E-Mail (`compare_html.py::render_compare_html()`) zeigt keinen Score/Winner mehr —
  Winner-Box, Score-Badge und Winner-Tags (eingeführt in #253/#460) entfallen vollständig,
  ersetzt durch eine Übersichtstabelle (Metriken × Orte, inkl. Zeile „Amtliche Warnungen") und
  Stundentabellen für alle Orte (alphabetisch sortiert). Betrifft ausschließlich die
  Mail-Darstellung: `ComparisonResult`/`LocationResult`-DTOs selbst sind unverändert
  (`.winner`/`.score` bleiben im Modell und in der App-Anzeige erhalten, siehe Section 18
  oben — der `winner`-Response-Wert bei `POST /api/scheduler/compare-presets/{id}/send` ist
  von diesem Issue nicht betroffen). Der Observability-Endpoint aus Issue #464
  (`POST /api/_validator/compare-email-preview`) nimmt das Request-Feld `winner_tags`
  weiterhin an, ignoriert es aber (Parameter im Renderer entfernt; Body-Schema
  unverändert für Abwärtskompatibilität). Siehe `docs/specs/_archive/modules/issue_1110_compare_mail_v2.md`
  (löst `docs/specs/_archive/modules/issue_253_compare_email.md` und
  `docs/specs/_archive/modules/issue_460_compare_email_template.md` ab, beide als `status: superseded`
  markiert).
- 2026-07-07: Issue #1071 (Slice 4 aus Epic #1067 Nutzerlevel Free/Standard/Premium, letztes
  Slice — Epic damit VOLLSTÄNDIG) — neuer Endpoint `POST /api/auth/tier-change-request` für
  Level-Änderungs-Anträge; `GET /api/auth/profile` liefert zusätzlich `requested_tier`/
  `requested_at` (beide `omitempty`, `requested_at` serverseitig Pointer-Typ). Antrag wird per
  Read-Modify-Write in `user.json` vermerkt und löst eine asynchrone Mail an `PO_EMAIL` aus; das
  effektive `tier`-Feld ändert sich dadurch nicht. Siehe
  `docs/specs/_archive/modules/issue_1071_tier_change_request.md`.
- 2026-07-07: Issue #1068 (Slice 1 aus Epic #1067 Nutzerlevel Free/Standard/Premium) — `GET
  /api/auth/profile` liefert neu ein Feld `tier` (`free`/`standard`/`premium`, immer vorhanden,
  Default `free` falls im `user.json` nicht gesetzt, Fallback nur beim Lesen, kein Rückschreiben).
  Reine Anzeige (Badge im Account-Bereich), kein Channel-Gating, keine Alert-Frequenz-Logik in
  diesem Slice. Siehe `docs/specs/_archive/modules/issue_1068_tier_model_display.md`.
- 2026-07-03: Issue #1004 — SSoT-Fix Segment-Startzeit (Re-Fix von #995 Gruppe A, verworfener
  Flag-Ansatz): das nie persistierte `Waypoint.time_window_origin` (siehe Eintrag #995 unten)
  wird ersatzlos entfernt. Es gibt genau EINE massgebliche Startzeit pro Etappe —
  `stage.start_time` — die neue Kette in `convert_trip_to_segments()` ist
  `arrival_override` > `stage.start_time` (Segment 1) > `arrival_calculated` (Naismith) >
  Default 08:00; `time_window` fliegt komplett aus dem Vergleich (bleibt nur Roundtrip-Feld),
  gilt sofort für ALLE Trips inkl. Bestand ohne Migration. Kein Wire-Format-Impact. See
  `docs/specs/_archive/modules/issue_1004_startzeit_ssot.md`.
- 2026-07-03: Issue #1001 — Telegram-Ausgabe neu gebaut (Multi-Bubble-Format): `GET
  /api/preview/{trip_id}/telegram` liefert zusätzlich `bubbles: list[str]` neben dem
  bestehenden `body`-Feld (additiv, rückwärtskompatibel — `body` bleibt die mit
  `"\n\n---\n\n"` verbundene Kette aller Bubbles). Betrifft nur den Telegram-Kanal;
  E-Mail/SMS-Preview unverändert. Siehe `docs/adr/0014-telegram-multi-bubble-format.md`
  und `docs/specs/modules/feat_1001_telegram_redesign.md`.
- 2026-07-03: Issue #995 — E-Mail-Fehler-Bündel: (A) neues Python-internes Feld
  `Waypoint.time_window_origin` (`src/app/trip.py`, Werte `"imported"`/`None`≈"manual") —
  ein GPX-importiertes `time_window` verliert in `convert_trip_to_segments()` seinen Vorrang
  vor einer nachträglich geänderten `stage.start_time`; kein Wire-Format-Feld, kein Go/TS-DTO-
  Impact (siehe Abschnitt „Waypoint DTO"); (B) HTML-Mail-Zellhintergrund jetzt direkt inline auf
  `<td>` statt Span/Negativ-Margin-Trick (`html.py`), keine DTO-Änderung; (C) Python liest jetzt
  auch `Trip.paused_at` (`src/app/loader.py`, Read-Modify-Write analog `archived_at`/#805) und
  `trip_report_scheduler.py::_get_active_trips()` überspringt pausierte Trips beim automatischen
  Versand — das Go-Feld `PausedAt` selbst war bereits seit Issue #153 Teil des Trip-DTOs (siehe
  oben), neu ist nur die Python-seitige Auswertung. Manueller Test-Versand und Alert-Dispatch
  bleiben unberührt. See `docs/specs/_archive/modules/issue_995_mail_bugs_bundle.md`.
- 2026-06-11: Issue #733 — Briefing-Mail-Validator (Marker-Headers + Plausibilität-Gate): `build_mime_message()` erweitert um optionale Parameter `mail_type` / `mail_format` (setzen `X-GZ-Mail-Type` / `X-GZ-Format` Header additiv, rückwärts-kompatibel). Scheduler + CLI taggen ausgehende Mails deterministisch: `trip-briefing/full|compact` (Briefing) vs. `compare/full` (Orts-Vergleich). Neuer Validator `.claude/hooks/briefing_mail_validator.py`: dispatcht auf Header, prüft **Trip-Briefing-Mails format-spezifisch auf Plausibilität** (full: multipart/alternative, HTML+Plain, ≥1 Stundentabelle, Werte self-konsistent; compact: single text/plain, 7bit, isascii, <2 KB, keine Stundentabelle). Compare-Mails bekommen No-Op-Klassifikation (Exit 0). Marker-Header ermöglichen deterministische Routing zu kanonischen Validatoren: `email_spec_validator.py` (Orts-Vergleich, fest auf Winner-Box verdrahtet) / `briefing_mail_validator.py` (Briefing). CLAUDE.md Sektion „BRIEFING-MAIL-VALIDATOR" dokumentiert Pflicht-Gate + Scope-Trennung. Siehe `docs/reference/renderer_email_spec.md` Sektion „Marker Headers and Validation Routing" und `docs/specs/modules/briefing_mail_validator.md`.
- 2026-06-11: Issue #722 [#709 Slice 2] — E-Mail-Format Kompakt (Nur-Text, minimal-Byte): Neuer Format-Schalter `TripReportConfig.email_format: 'full' | 'compact'` (default `'full'`). `'full'` = bestehende multipart-HTML-Mail mit stündlichen Werte-Tabellen (byte-identisch unverändert). `'compact'` = reine `text/plain`-Mail (single part, kein HTML, kein multipart), reines ASCII (7bit-CTE), mit fix nur Kopf + Metriken-Überblick + Ausblick + Footer (ohne Baustein-Toggles), ~95% kleiner (~1 KB für Wanderer mit schlechter Konnektivität). Backend: neuer isolierter `render_compact()`-Renderer (`src/output/renderers/email/compact.py`, ~50 LoC), `build_mime_message()` extrahiert (`html=False` → `us-ascii`/7bit), Scheduler leitet Email-Format durch. Frontend: Format-Schalter in `EditReportConfigSection.svelte`, Baustein-Gruppe bei compact deaktiviert (UI-Hinweis). Go-Modell `ReportConfig` Passthrough (no changes). Tests: Backend E2E gegen Staging (AC-1–5 Multipart-Strukturverifizierung + ASCII-Validierung + Baustein-Ignorance), Playwright E2E (AC-6 UI-Persistenz), Multi-User (AC-7). See `docs/specs/_archive/modules/issue_722_email_compact_format.md`.
- 2026-06-10: Issue #702 — Alerts-Tab Mobile-Parität TM2 (Frontend CSS-only, Epic #700 Slice 2/2): `AlertsTab.svelte`, `AlertCard.svelte`, `AlertCooldownCard.svelte`, `AlertQuietHoursCard.svelte` mit `@media (max-width: 899px)` Breakpoint-spezifischen Touch-Target-Sizing: Channel-Chips ≥36px Höhe, Threshold-Input ≥120px breit, Cooldown/Time-Inputs ≥44px Höhe + 16px font-size (verhindert iOS-Auto-Zoom). Desktop Layout bleibt byte-identisch. `.actions`-Bar auf mobil ausgeblendet, Mobile-Footer-Button sichtbar (bestehend). Keine API/DTO-Änderungen. Tests: Playwright E2E gegen Staging @375px Viewport (AC-1/AC-2/AC-3/AC-5 Touch-Targets, AC-4 Desktop-Regression). See `docs/specs/_archive/modules/issue_702_alerts_mobile_parity.md`.
- 2026-06-10: Issue #721 (Slice 1 von #709) — E-Mail-Ausblick verschmolzen: neues additives Feld `TripReportConfig.show_outlook` (bool, default true). Verschmilzt Großwetterlage (als Kopf), Tabelle der nächsten Etappen mit Uhrzeiten (`format_trend_tokens`, #640) und neuer Vorhersage-Sicherheit pro Etappe (`confidence_pct` aus `SegmentWeatherSummary.confidence_pct_min`, propagiert über `_build_stage_trend`) zu **einem** Ausblick-Block. `show_outlook=false` blendet den gesamten Block in HTML **und** Plain-Text aus (Großwetterlage zusätzlich an `show_stability` gekoppelt; fehlt `confidence_pct`, entfällt nur die Prozentangabe — kein „0%"). Altfelder (`show_stability`/`show_compact_summary`/`show_highlights`) bleiben erhalten (kein Schema-Removal). UI-Schalter folgt in Slice 3 (#723). See `docs/specs/_archive/modules/issue_721_email_outlook.md`.
- 2026-06-10: Issue #690 — Eigene Wetter-Metriken-Profile (MetricPreset CRUD): Section 15.5 hinzugefügt. 4 REST-Endpoints: GET/POST/DELETE/PATCH `/api/metric-presets{/{id}}`. MetricPreset DTO mit Name (eindeutig pro Nutzer, case-insensitive, getrimmt), Metrics ([]DisplayMetric mit Horizons), is_default, CreatedAt. POST antwortet mit HTTP 201 bei Erfolg; HTTP 400 bei leerem Name (`"name_required"`); HTTP 409 bei Duplikat-Name (`"name_exists"`, case-insensitive). Bestands-Daten: Single-File Storage `metric_presets.json` pro Nutzer; User-Isolation via Auth-Context (`user_id`). Frontend: Dialog zeigt Client-Validierung (Duplikat-Check), neues Profil wird nach Speichern sofort aktiv auf Trip (`display_config.preset_name = preset.id`), "Eigene"-Markierung in Preset-Leiste (unterscheidet User-Profile von System-Vorlagen), trip-übergreifend sichtbar. See `docs/specs/_archive/modules/issue_690_custom_metric_presets.md`.
- 2026-06-09: Issue #674 — Fahrradtouren als Aktivitätstypen (15 / 20 / 25 km/h): Neue `ActivityType`-Werte `"fahrrad_15"`, `"fahrrad_20"`, `"fahrrad_25"` in Go + TypeScript mit korrekten Naismith-Raten (600 m/h Aufstieg, 1000 m/h Abstieg — doppelt so schnell wie Wanderer). Section 10.5 hinzugefügt (Trip Model und Activity Types). Trip.activity Feld existierte bereits (Epic #136), wird jetzt dokumentiert mit vollständiger Aktivitäts-Tabelle. `ComputeStageArrivals()` Signatur erweitert auf `ActivitySpeeds`-Parameter statt hardcodiert; `ActivitySpeed(trip.activity)` Hilfsfunktion in Go. Frontend: `activityToSpeed(activityType?)` Hilfsfunktion, `computeArrivalTimes()` akzeptiert optionalen `speedFlatKmh`-Parameter. Wizard Step 3 zeigt 3 neue Fahrrad-Optionen im Dropdown. EditStagesPanelNew erhält `activityType`-Prop, leitet Speed weiter. Backward-Compatibility: unbekannte/leere Activity → Wanderer-Default (4.0 km/h, 300/500 Hm/h). Keine Python-Erweiterung (OUT OF SCOPE, Folge-Issue für EtappenConfig). See `docs/specs/_archive/modules/issue_674_aktivitaetstyp_fahrrad.md`.
- 2026-06-09: Issue #680 — Compare-Editor Slice 3 Fidelity-Tabs „Orte" + „Idealwerte" (Epic #677): ComparePreset DTO erweitert um opaque `display_config` field (Section 16). Keys: `active_metrics` ([]string — ausgewählte Metriken pro Vergleich), `ideal_ranges` (min/max-Idealwerte für Bewertung), zukünftig `output_layout` + `schedule_config`. Frontend RMW-Semantik: nur geänderte Felder senden, Server roundtrippt alles (bestandsfelder erhalten). Zero-schema-validation im Backend. Neue UI-Komponenten: `RangeSlider.svelte` (Dual-Handle für range-Metriken), Segmented-Control (Enum-Metriken). compareMetricDefs.ts: `ALL_METRICS`-Katalog + `deriveIdealText()`. compareWizardState.svelte.ts: `activeMetricKeys`, `metricsManuallyEdited`. Step2Orte: nummerierte Picked-Liste mit Entfernen, Region-gruppierte Bibliothek (Checkbox). Step3Idealwerte: Slider, Add/Remove-Metrik, Persistenz. See `docs/specs/_archive/modules/issue_680_compare_editor_slice3.md`.
- 2026-06-09: Issue #675 — Etappen-Startzeiten editierbar (Frontend-only, no API changes): (1) New `StageTimeField.svelte` component (analog `StageDateField`) renders `<input type="time">` within `.box` wrapper with label "STARTZEIT"; (2) Editor displays default `08:00` when `stage.start_time` is unset (displayValue fallback); (3) `EditStagesPanelNew.svelte` handler `handleStartTimeChange()` implements immutable update: setting empty string removes `start_time` (returns to default), otherwise sets to user-chosen time; (4) Component renders in both Desktop header (.stage-header-fields) and Mobile markup (@media ≤899px) for Desktop–Mobile parity; (5) Skipped for pause stages (`activeIsPause === true`); (6) Live Naismith `$derived arrivals` recalculates from changed `start_time` without explicit save (feature display); (7) Existing `Stage.start_time?: string` field (already present in model, Naismith, and Backend RMW) requires no data migration; unset trips remain byte-equal on open+save (alt-treu). ACs 1–7 verified via Playwright E2E + staging_validator. See `docs/specs/_archive/modules/issue_675_etappen_startzeiten.md`.
- 2026-06-09: Issue #638 — Alerts-Tab Karten-Modell + Severity-Falle + pro-Alert Kanäle: (1) Added section 22 — AlertRule DTO with new `channels: list[str]` field (empty = inherit active briefing channels; non-empty = override); (2) `AlertRule.severity` now label-only (not used for send filtering anymore — eliminates severity trap where info-alerts were silently dropped); (3) Frontend Alerts-Tab moved from table paradigm to card model via AlertCard.svelte; Severity dropdown UI removed; Channel chips per alert with toggle UI; (4) Versand-Logik: per-alert kanal-routing via `trip_alert.py:_send_alert()` gruppiert Changes nach effektiven Kanälen; (5) Backward compatibility: bestandsdaten ohne `channels` laden mit leerer Liste (RMW bei Versand); `severity` bleibt lesbar. See `docs/specs/_archive/modules/issue_638_alerts_redesign.md`.
- 2026-06-02: Issue #559 — Archive page completion: (1) Added `GET /api/trips/{id}/briefing-history` endpoint (section 21) to display chronological list of sent briefings (morning/evening) with timestamps and channels; (2) Frontend `BriefingHistoryDialog.svelte` modal with formatted timestamps (DD.MM.YYYY HH:MM) and localized kind labels; (3) "Als Vorlage" (Use as Template) button on archive page copies trip config via query param `?from={id}` to wizard page, with `templateTrip` loaded in `+page.server.ts`; (4) "Was passiert ist" (What Happened) column shows formatted event summary via `formatEventSummary(briefings, alerts)` helper. See `docs/specs/_archive/modules/issue_559_archiv_fertigstellen.md`.
- 2026-06-01: Issue #523 — Code-Debt Cleanup: Removed `Waypoint.Suggested` (bool) and `Waypoint.SuggestionReason` (*string) fields from backend Go model (`internal/model/trip.go`). Legacy normalization block in `ConfirmWaypointHandler` removed. Frontend TypeScript `Waypoint` interface no longer declares `suggested?` and `suggestion_reason?` properties. Utility function `stripSuggested()` and all callers removed from waypoint editor. UI component `WaypointPin.suggested` property and dashed-stroke visualization deleted. Cleanup fulfills Constraint C8 from Issue #506 (Remove AI-Suggestion UI). 13 files edited, ~-190 LoC net deletion. Backward compatibility: bestandsdaten mit `"suggested":true` im JSON bleiben lesbar (Go ignoriert unknown JSON fields bei deserialisierung). See `docs/specs/_archive/modules/issue_523_suggested_flag_cleanup.md`.
- 2026-06-01: Issue #497 (BugFix) — Preview SMS Stage-Name + Fixture Fields: ForecastDataPoint from FixtureProvider now reads all 4 demo-mode fields (`cloud_low_pct`, `pop_pct`, `snowfall_limit_m`, `wind_dir_deg`) from fixture JSONs. Preview SMS rendering fixed: `.split(":", 1)[0].strip()` for correct Stage-Name extraction.
- 2026-05-31: Issue #483 — Demo-Modus im Vorschau-Tab: Added `demo: bool` Query-Parameter to all 4 preview endpoints (`/api/preview/{trip_id}/[email|sms|signal|telegram]`). When `demo=1`, endpoints use FixtureProvider instead of live weather; demo mode ideal for testing preview rendering on past trips. Supports AC-1–AC-6 for demo banner UX and fallback to live weather. See section 20 (new) and `docs/specs/_archive/modules/issue_483_demo_mode_preview.md`.
- 2026-05-31: Issue #495 — MapCanvas Leaflet-Karte: `MapCanvas.svelte` vollständig auf Leaflet 1.9.4 mit OpenTopoMap-Tiles umgestellt. `buildMapPositions()` und `MapPosition`-Typ aus `frontend/src/lib/utils/waypointEditor.ts` entfernt — Leaflet übernimmt Projektion und Zoom. Wegpunkt-Editor zeigt jetzt geografisch korrekte Höhenschichtlinien-Karte mit Marker-Popups und Polyline. 3 Dateien geändert: `package.json` (+leaflet, +@types/leaflet), `MapCanvas.svelte` (~180 LoC Rewrite), `waypointEditor.ts` (-buildMapPositions, -MapPosition).
- 2026-05-30: Issue #467 — Passkey V3 Discoverable Credentials + Conditional UI: 2 new public endpoints (`POST /api/auth/passkey/discoverable/begin` and `/finish`) enable login without username. Browser shows registered passkeys as native autofill suggestions on username field focus via WebAuthn `mediation: 'conditional'`. Begin returns full assertion object with top-level `"mediation":"conditional"` flag. Finish accepts `userHandle` from authenticator and looks up user via `DiscoverableUserHandler` callback. Rate-limit 30/h per IP (same as V1). Frontend: `loginWithDiscoverablePasskey()` function in `passkey.ts` + `onMount` conditional UI init in login page with `autocomplete="username webauthn"` attribute. Tests: 6 mock-free roundtrip tests covering success path, empty userHandle, unknown user, challenge replay, and TTL expiry. See `docs/specs/_archive/modules/issue_467_discoverable_credentials.md`.
- 2026-05-30: Issue #464 — Compare-E-Mail Observability-Endpoint `POST /api/_validator/compare-email-preview` (Tooling-API, nicht versionsstabil): Macht den Compare-HTML-Renderer von außen direkt aufrufbar für Validator-Observability. Go-Proxy + Python-Handler (validator.py). Request-Body: `{profile, time_window, target_date, winner_tags}`. Response: `{html: "..."}` mit gerendertem HTML. Stub-LocationResult mit score=85, keine echten Wetterdaten. AC-1/2/3 prüfbar per `curl | grep`. Siehe `docs/specs/_archive/modules/issue_464_compare_email_preview_validator.md`.
- 2026-05-30: Issue #468 — AAGUID-Labels in der Passkey-Liste: GET `/api/auth/profile` Passkey-Einträge zeigen neu optionales Feld `authenticator_name` (z.B. "iCloud Keychain", "Windows Hello") basierend auf AAGUID-Mapping. Field omitempty bei Zero/Unknown-AAGUID. Frontend zeigt kombiniert `"{authenticator_name} · {label}"`. Siehe `docs/specs/modules/aaguid_labels.md`. Implementation: ~90 LoC (`aaguid.go`, `auth.go`, `account/+page.svelte`).

---

## Backend Services

Diese Sektion dokumentiert interne Service-Klassen, die nicht über REST-Endpoints verfügbar sind.

### WeatherSnapshotService — Dated Snapshot Storage (Issue #747)

**Pfad:** `src/services/weather_snapshot.py`

**Purpose:** Erweitert den bestehenden `WeatherSnapshotService` um datiertes Speichern und Laden von Wetter-Snapshots. Ermöglicht Abruf der gestrigen Vorhersage für Vortag-Vergleich im Trip-Briefing.

**Datei-Schema:**
- **Bestehend (Alert-Nutzung, unverändert):** `data/users/<user_id>/snapshots/{trip_id}.json`
- **Neu (datiert):** `data/users/<user_id>/snapshots/{trip_id}_{YYYY-MM-DD}.json`

**Methoden:**

| Methode | Signatur | Verhalten |
|---------|----------|----------|
| `save_dated()` | `(trip_id: str, target_date: date, segments: List[SegmentWeatherData]) → None` | Schreibt datierte Kopie zu `{trip_id}_{YYYY-MM-DD}.json`. Ruft intern `_prune_dated_snapshots()` auf. Fehler werden geloggt, nicht geworfen. |
| `load_dated()` | `(trip_id: str, target_date: date) → Optional[List[SegmentWeatherData]]` | Lädt datierte Snapshot-Datei für den angegebenen Tag. Gibt `None` zurück wenn Datei nicht vorhanden (kein Absturz). Deserialisialisiert `SegmentWeatherData` mit Enum-Rekonstruktion. |
| `_prune_dated_snapshots()` | `(trip_id: str) → None` | Löscht älteste datierte Snapshots für diesen Trip, behält maximal 7 (mtime-sortiert). Fehler beim Löschen werden geloggt. |
| `save()` | _(bestehend, unverändert)_ | Speichert auf `{trip_id}.json` für Alert-Pfad. Byte-identisch vor/nach Issue #747. |
| `load()` | _(bestehend, unverändert)_ | Lädt von `{trip_id}.json` für Alert-Pfad. Byte-identisch vor/nach Issue #747. |

**Retention-Policy:**

Beim Aufruf von `save_dated()`:
1. Snapshot wird geschrieben
2. `_prune_dated_snapshots()` wird aufgerufen
3. Alle Dateien `{trip_id}_*.json` werden nach `mtime` sortiert
4. Nur die 7 jüngsten Dateien bleiben, älter werden gelöscht
5. Fehler beim Löschen (OSError) werden geloggt, brechen nicht ab

**Integration:**

`trip_report_scheduler.py` ruft nach bestehendem `save()`-Aufruf zusätzlich `save_dated()` auf:
```python
_snapshot_svc = WeatherSnapshotService(self._user_id)
_snapshot_svc.save(trip_id, segment_weather, target_date)        # bestehend
_snapshot_svc.save_dated(trip_id, target_date, segment_weather)  # neu, Issue #747
```

**User-Isolation:**

`WeatherSnapshotService.__init__(user_id)` empfängt `user_id` aus Auth-Kontext. Snapshots pro Nutzer isoliert unter `data/users/<user_id>/snapshots/`.

**Backward Compatibility:**

- Bestehende `save()`-/`load()`-Methoden sind byte-identisch
- Alert-Pfad (`trip_alert.py`) nutzt nur `save()`/`load()` — keine Verhaltensänderung
- Bestandsdaten in `{trip_id}.json` bleiben unverändert
- 2026-05-30: Issue #461 — Compare-Presets Daily Dispatch (Cronjob): New `POST /api/scheduler/compare-presets-daily` endpoint (section 17) triggered daily by Go scheduler at 06:00 UTC. Filters presets by `schedule='daily'`, runs Compare Engine, renders/sends emails via Resend, updates `letzter_versand` and `top_ort_letzter_versand` fields. Per-preset error isolation; BetterStack Heartbeat pinged only on `error_count==0` (Readiness Principle). Config field `HeartbeatComparePresets` added to Go config; Go scheduler job count increased from 5 to 6. Tests: 11 new comprehensive tests in `test_issue_461_compare_preset_dispatch.py`.
- 2026-05-30: Added section 18 — Authentication Endpoints (Issue #450 Passkey/WebAuthn V1): 5 passkey endpoints (register/begin|finish, login/begin|finish, delete), password auth methods (register, login), profile endpoint with `has_passkey`+`passkeys[]`. User model extended with `PasskeyCredentials[]` and `PasswordHash` now optional. Rate-limit 30/h per IP (alle 5 Endpoints), challenge TTL 5 min, RP-ID isolation (prod vs staging), 64 KB body cap.
- 2026-05-30: Issue #459 — Auto-Briefings Sidepanel Frontend (ComparePreset-System): AutoReportsOverview, SavePresetDialog, subscriptionHelpers (presetScheduleLabel, formatLastSent), ComparePreset-Interface in types.ts; +page.server.ts lädt `/api/compare/presets`; AutoReportCard und AutoReportsOverview auf ComparePreset umgebaut mit manuellem Versand-Button. Spec #458-Backend-Endpoints vorausgesetzt (`GET /api/compare/presets`, `/send`).
- 2026-05-31: Issue #475 — OutputLayoutEditor Organisms-Migration (Pure Frontend): OutputLayoutEditor verliert direkten `ui/card`-Import, nutzt stattdessen `atoms/Card.svelte`. Komponente wird als vierter Eintrag in `organisms/index.ts` re-exportiert. Consumer-Imports (Step4Layout×2, WeatherMetricsTab) auf `$lib/components/organisms` umgestellt. Keine API/DTO-Änderungen.
- 2026-05-30: Issue #458 — Compare-Preset Backend (CRUD+Endpoints): Neues `ComparePreset`-Datenmodell (separate Entität von `CompareSubscription`); 5 REST-Endpoints: GET/POST/PUT/DELETE + `/send`-Stub; Single-File Storage `compare_presets.json`; User-Isolation; Validierung. Siehe Abschnitt 16.
- 2026-05-29: Issue #455 — Compare-Hauptbühne Frontend `/compare` route implemented (pure frontend, no API changes). 3-column layout: LocationsRail (left 320px) | CompareMatrix/RecommendationBanner/HourlyMatrix (center flex) | AutoReportsOverview (right 320px). POST `/api/compare/run` contract unchanged; frontend wires existing Go-backend endpoint. See `docs/specs/_archive/modules/issue_455_compare_main_stage.md`.
- 2026-05-29: Issue #448 — Validator-Endpoint `GET /api/_validator/metrics-for-channel` ergänzt (Tooling-API, nicht versionsstabil): Macht die dreistufige Kaskade von `get_metrics_for_channel()` (per_report → per_channel → global) von außen prüfbar. Response: `{"source": "per_report|per_channel|global", "metric_ids": [...]}`. Params: `trip`, `channel`, `report`, `user_id` (via Go-Proxy injiziert).
- 2026-05-29: Issue #442 — Compare-Wizard Step 4 Layout (Pure Frontend): Step4Layout component added to Compare-Wizard, enabling per-channel metric configuration (Email/Telegram/Signal/SMS) with reusable OutputLayoutEditor component (Issue #431). Wizard calls GET /api/metrics (required), GET /api/templates (optional), GET /api/metric-presets (optional) on mount. No backend changes; `channel_layouts` field added to CompareSubscription state (frontend-only persistence via `save()`).
- 2026-05-29: Issue #446 — Format-Mode-Validierung in `_resolve_format_mode()`: Unbekannte `format_mode`-Strings (z.B. `"Symbol"` mit Großbuchstabe, `"raw_v2"`) werden jetzt gegen `MetricDefinition.format_modes` validiert und auf `default_format_mode` zurückgefallen, mit WARNING-Log.
- 2026-05-29: Added section (legacy 16, neu nummeriert) — Google OAuth Login Endpoints (Issue #425): GET /api/auth/google/init (initiates flow, redirect to Google), GET /api/auth/google/callback (code exchange, user creation/lookup, session issuance). User model extended with `OAuthProvider` and `OAuthSub` fields. Feature-gated via `GZ_GOOGLE_CLIENT_ID` config. New User-ID format `g-{8hex}` for OAuth users (prevents session parse errors).
- 2026-05-29: Added section 15 — Metric Catalog Endpoint (Issue #435): GET /api/metrics exposes `format_modes[]` and `default_format_mode` per metric for frontend UI filtering and backward-compatibility mapping.
- 2026-05-29: Issue #440 — Orts-Vergleich-Wizard Phase 1 — Extended CompareSubscription model with `activity_profile` (optional, validProfiles: wintersport|wandern|summer_trekking|allgemein). Frontend: CompareWizard Shell + Step 1 (Name/Region/Profile) + Step 2 (Smart-Import + Library). Stepper component made reusable via testidPrefix + onStepClick props. See `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md`.
- 2026-05-10: Epic #136 Trip-Wizard Master-Spec Fundament — Extended Trip model with `shortcode` and `activity` fields; Waypoint.suggested transient flag for wizard UI; Backend Trip.validateTrip() now accepts pause stages (waypoints: []). See `docs/specs/_archive/modules/epic_136_trip_wizard.md`.
- 2026-05-09: Added sections 12, 13, 14 — Scheduler Status, Forecast Query, Trip-Reports Trigger Endpoints (Epic #134). Support for dashboard briefing timeline, non-blocking client-side weather, and manual report trigger via API.
- 2026-04-14: Added section 11 — Weather Config Endpoints (M5c): 6 GET/PUT-Endpoints fuer display_config auf Trip, Location und Subscription als opaque JSON.
- 2026-04-14: Added section 10 — Subscriptions CRUD Endpoints (M5b): 5 REST-Endpoints fuer CompareSubscription, Single-File Storage, Validierung, Legacy-Migration.
- 2026-04-14: Added section 9 — GPX Proxy Endpoint (M5a): POST /api/gpx/parse, Go-to-Python Multipart Proxy, Stage+Waypoints Response DTO.
- 2026-02-18: Added `TripReportConfig.wind_exposition_min_elevation_m` (F7c Wind-Exposition Config) — per-trip configurable elevation threshold for wind exposition detection. Default null uses global 1500m threshold (lowered from 2000m).
