# Context: feat-2800-trip-radar-alarm

Issue #2800 · Epic #2791 „Einstellungen neu“ · Scheibe S8 · Abgleich N1 (PO: „unbedingt rein“), Inventar A2.
Abhängigkeiten S2 (#2793) und S3a (#2794) sind geschlossen.

## Request Summary
Radar-Regen-Alarm („Regen in der nächsten Stunde auf deiner Etappe“) soll auch für Trips einstellbar sein:
Schalter im Reiter Wetter, Karte „Amtliche Warnungen & Radar“, Zustellung an alle Alarm-Kanäle (ADR-0095),
Texte DE/EN, Trip-Variante der Radar-Mail mit Validator.

## Kernbefund (widerspricht der Annahme im Issue)
**Der Trip-Radar-Alarm existiert im Backend bereits und läuft für jeden Trip ohne Schalter** (#822):
`TripAlertService.check_radar_alerts_run()` `src/services/trip_alert.py:2034`, Schleife `_check_radar_trips` `:2102`.
Er liest nur `alert_channels`, `alert_channel_thresholds`, `alert_cooldown_minutes`, `alert_quiet_from/to`, `alert_rules`;
es gibt **keine** `radar_alert_enabled`-Prüfung (verifiziert: kein Treffer in `trip_alert.py`). Bei leeren effektiven Kanälen wird übersprungen (`:2693`).
`docs/context/einstellungen_neu.md:132/:140` und `feat_2794_s3a_reiter_wetter.md:323` („nur im Ortsvergleich“) sind damit überholt.

Folge für den Umfang: Fachlogik (Punktwahl, Tempo, GPS-Fix, Gate, Zustellung) ist vorhanden. Es fehlt:
1. Schalter `radar_alert_enabled` am Trip: Python-Modell, Go-Struct + PUT-Dreizustand, API-Contract, Drift-Tests.
2. Prüfung des Schalters im Trip-Radarlauf (vor Nowcast-Abruf, wie Compare `:228`).
3. **Default-Entscheidung:** Compare = aus (None → aus). Trip heute faktisch = an. Bestandstrips dürfen nicht still verstummen.
4. Frontend: `MIT_RADAR.route` auf `true`, Trip-Speicherpfad, Typ, Text mit „deine Etappe“.
5. Validator/Doku/Elementliste: freigegebene Abweichung „Trip ohne Radar-Zeile“ entfernen, Specs AC-3/AC-9 (feat_2913_scheibe_c), AC-21 (feat_2794) gelten als abgelöst.

## Related Files
| File | Relevance |
|------|-----------|
| src/services/trip_alert.py:2034-2950 | Trip-Radarlauf; Schalter-Prüfung einbauen |
| src/services/compare_radar_alert.py:210-260 | Vorbild: `radar_alert_enabled`-Prüfung `:228`, Default aus |
| src/app/trip.py:176-226 | Trip-Modell (Alarm-Felder `:201-226`), `extra` für unbekannte Keys |
| src/app/models.py:1364, src/app/loader.py:278 | Compare-Feld + Loader |
| internal/model/trip.go:114-195 | Go-Trip-Struct (typisiert, kein Catch-all → neues Feld nötig) |
| internal/handler/trip.go:300-330, :466 | PUT-Request, Dreizustand `Optional[bool]`/`ApplyPtr` |
| internal/model/trip_schema_drift_test.go, tests/test_trip_schema_drift.py | Drift-Gate beide Seiten |
| internal/handler/compare_preset_radar_alert_enabled_test.go | Vorbild Go-Test |
| docs/reference/api_contract.md §10.5 :1018-1060, :1221-1224 | Trip-DTO, Dreizustandsliste |
| frontend/.../organisms/wetter-tab/WetterTabInhalt.svelte:51,:298 | `MIT_RADAR = {route:false, vergleich:true}` |
| frontend/.../organisms/wetter-tab/WarnungenRadarKarte.svelte, warnungenRadarZeilen.ts | Karte, Radar-Zeile nur bei `mitRadar` |
| frontend/.../shared/wetter-tab/wetterZustand.ts:101 | `radarAn` aus `abo.radar_alert_enabled === true` |
| frontend/.../ampelSchreiben.ts:143 (trip), :212 (vergleich); wetterTabSpeicherung.ts:95 | Speicherpfade; Trip ohne Radar |
| frontend/src/lib/types.ts ~:436 (Trip), :742 (Compare) | Typen |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json:99-101 | `wetter.radar.*`, Beschreibung mit `{orte}` |
| docs/context/einstellungen_neu/elementliste_freigaben.json; frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts:129 | freigegebene Abweichung „Trip ohne Radar“ |
| .claude/hooks/radar_alert_mail_validator.py | bereits Trip-förmig (P-1 Etappe, P-2 Uhrzeit, P-3 Intensität, P-4 Cooldown) |
| api/routers/debug.py:46 | Debug-Trigger Trip-Radar (für Staging-E2E) |
| api/routers/scheduler.py:198/:208; internal/scheduler/scheduler.go:355/:358 | Cron + Endpunkte (unverändert) |

## Existing Patterns
- Compare-Schalter: `Optional[bool]`, None → aus; Go `*bool` mit generischem Merge; Prüfung vor Nowcast-Abruf (Budget-schonend).
- Trip-Dreizustandsfelder (z. B. `official_alerts_enabled`) über `Optional[bool]` + `ApplyPtr` (Read-Modify-Write, kein Replace).
- Trip-Radar: `_resolve_alert_segment` → `resolve_current_segment` (ADR-0044), `points_with_passage_times` mit Naismith-Tempo aus `activity` und GPS-Fix-Übersteuerung (ADR-0102), `check_nowcast_gate` Scope `radar` (Stille Stunden → Cooldown → Tageslimit), Kanal-Auflösung `effective_alert_channels`, Schwelle `split_by_threshold`, Versand `send_radar_alert`.
- Frontend teilt Wetter-Reiter über `context="route"|"vergleich"` (ADR-0097/0109).

## Dependencies
- Upstream: RadarNowcastService, `check_nowcast_gate`, `alert_channels.resolve_alert_channels`, `alert_channel_threshold`, NotificationService, i18n-Kataloge.
- Downstream: Go-Store/Drift-Gates, Frontend-Wetter-Reiter, Elementliste/Abgleich-Tests, Validator, Staging-E2E (Debug-Trigger), api_contract.

## Existing Specs
- docs/specs/_archive/modules/issue_822_radar_nowcast_segment.md (Trip-Radar), issue_1041*_ (Compare-Radar + Toggle), issue_830 (Validator)
- docs/specs/modules/radar_nowcast.md, fix_1752_radar_folgt_alarm_kanaelen.md, fix_2480_radar_alle_messpunkte.md, feat_2261_a2s2_radar_takt.md
- docs/specs/modules/feat_2794_s3a_reiter_wetter.md (AC-21 Trip ohne Radar), feat_2913_scheibe_c_wetter_rest.md (AC-3/AC-9)

## ADR-Lage
- 0095 Kanal-Parität (alle vier Kanäle, auch Radar). 0096 Radar-Onset absolute Schwelle, Trip unterdrückt bereits angekündigten Regen.
- 0102 GPS-Fix übersteuert Planposition. 0103 betrifft Parallel-Slots, **nicht** Abruf-Begrenzung; maßgeblich sind 0082 (Radar-Budget, Takt `3-58/5`) und 0117.
- 0109 vier Reiter, Wetter enthält Warnungen + Radar (Punkt 3 abgelöst durch 0124).

## Risks & Considerations
- **Default am Trip:** None → an (Bestand behält Verhalten) vs. None → aus (Parität zu Compare, aber Bestandsnutzer verlieren still einen laufenden Alarm). Tech-Lead-Tendenz: an (keine stille Regression, PO-Wunsch „unbedingt“).
- Go-Struct ohne Catch-all: Feld fehlt im Go-Modell ⇒ wird beim Speichern verworfen; Drift-Gates erzwingen beide Seiten.
- Nowcast-Budget: Schalter-Prüfung muss **vor** dem Abruf liegen (ADR-0082).
- Mandantentrennung: PUT-Test mit zwei Nutzern.
- Abgelöste ACs in S3a/Scheibe-C-Specs und Elementlisten-Freigabe sauber nachziehen (Tests würden sonst rot).
- Validator: Compare-Mails nutzen denselben Mail-Typ; Trip-Variante ist schon abgedeckt — prüfen, ob Trip-Mail heute Exit 0 liefert.

## Analysis

### Type
Feature (Schalter für einen im Backend schon laufenden Trip-Radar-Alarm, #822).

### Technische Entscheidungen (Tech Lead)
- **Default am Trip: None → AN** (`radar_alert_enabled is not False`), Vorbild `official_alerts_enabled` (`src/app/trip.py:209`, `src/services/amtliche_warnungen_schalter.py:31`). Begründung: Der Radarlauf läuft heute für jeden Trip; None → aus würde Bestandstrips still verstummen lassen (Regression ohne Migration). Compare bleibt bei None → aus (`compare_radar_alert.py:228`), Abweichung wird in Spec und `api_contract.md` dokumentiert.
- **Ort der Prüfung:** `_check_radar_trips` direkt nach `reached[trip.id] = …` (`trip_alert.py:~2113`), im `try`, als `continue` — vor Segmentwahl, Kanal-Auflösung und Nowcast-Abruf (ADR-0082-Budget). Stempel „zuletzt erreicht" bleibt gesetzt, faire Reihenfolge unberührt; `progress["checked"]` zählt weiter.
- **Punktwahl / Abrufbegrenzung (Issue-Auftrag Punkt 2):** unverändert aus #822/#2480/#2261 übernehmen — aktives bzw. nächstes Segment über `_resolve_alert_segment` → `resolve_current_segment` (ADR-0044), Punkte mit Durchgangszeit nach Naismith-Tempo (`points_with_passage_times`, `activity`), plausibler GPS-Fix übersteuert die Planposition (ADR-0102); Abrufbegrenzung über Takt `3-58/5`, Laufzeitgrenze `RADAR_RUN_DEADLINE_SECONDS` und faire Reihenfolge (ADR-0082/0117). Keine neue Fachlogik.
- **Frontend-Default nach Kontext:** `wetterZustand.ts:101` liest für `route` `!== false`, für `vergleich` weiter `=== true`. `MIT_RADAR.route = true` (`WetterTabInhalt.svelte:51`). `tripSpeicherPayload` (`ampelSchreiben.ts:~143`) schreibt `radar_alert_enabled` mit dem Zustand des Reiters (Read-Modify-Write, kein stilles `false` beim Laden eines Bestandstrips, weil der Zustand `true` gelesen wird).
- **Text:** eigene Variante für den Trip („deine Etappe" / „your stage") statt `{orte}`-Umschaltung; neue Katalogschlüssel DE/EN in `wetter.json`, Glossar prüfen.
- **Test-Alarm (S5, #2797):** testet den Kanal, nicht das Wetter → umgeht den Schalter. Nicht Teil dieser Scheibe; Hinweis in #2797-Kontext reicht.
- **Staging-E2E:** Debug-Trigger `api/routers/debug.py:46` läuft über denselben Lauf → Seed-Trip mit Schalter an (oder None), plus Gegenprobe Schalter aus = keine Mail. Radar-Mail-Validator (`.claude/hooks/radar_alert_mail_validator.py`) ist Trip-förmig; einmal gegen echte Trip-Radar-Mail auf Staging laufen lassen (Exit 0).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/app/trip.py | MODIFY | `radar_alert_enabled: Optional[bool] = None` |
| src/app/loader.py | MODIFY | Lesen (:277/:746), Schreiben nur wenn nicht None (:1894), `KNOWN_TOP_LEVEL` (:701) |
| src/services/trip_alert.py | MODIFY | Schalter-Prüfung in `_check_radar_trips` vor Nowcast |
| internal/model/trip.go | MODIFY | `RadarAlertEnabled *bool \`json:"radar_alert_enabled,omitempty"\`` |
| internal/handler/trip.go | MODIFY | PUT `Optional[bool]` + `ApplyPtr` (Dreizustand) |
| internal/model/trip_schema_drift_test.go, tests/test_trip_schema_drift.py | MODIFY | Drift beide Seiten |
| internal/handler/trip_radar_alert_enabled_test.go | CREATE | PUT-Dreizustand, zwei Nutzer (Vorbild `trip_official_alerts_test.go`) |
| tests/tdd/test_trip_radar_schalter.py | CREATE | aus → kein Nowcast-Abruf, kein Versand; None/True → Lauf; Mandant |
| frontend/src/lib/types.ts | MODIFY | Trip-Typ `radar_alert_enabled?: boolean` |
| frontend/.../wetter-tab/WetterTabInhalt.svelte | MODIFY | `MIT_RADAR.route = true` |
| frontend/.../shared/wetter-tab/wetterZustand.ts | MODIFY | kontextabhängiger Default |
| frontend/.../shared/wetter-tab/ampelSchreiben.ts, wetterTabSpeicherung.ts | MODIFY | Trip-Speicherpfad mit `radar_alert_enabled` |
| frontend/.../organisms/wetter-tab/WarnungenRadarKarte.svelte, warnungenRadarZeilen.ts | MODIFY | Trip-Text „deine Etappe" |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | MODIFY | neuer Beschreibungstext Trip |
| docs/context/einstellungen_neu/elementliste_freigaben.json (:9), frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts (:129) | MODIFY | Freigabe „Trip ohne Radar" entfernen (gleichzeitig) |
| docs/specs/modules/feat_2794_s3a_reiter_wetter.md (AC-21, :323), feat_2913_scheibe_c_wetter_rest.md (AC-3/AC-9) | MODIFY | als abgelöst durch #2800 markieren; zugehörige Frontend-Tests anpassen |
| docs/reference/api_contract.md §10.5 (:1018-1060, :1221-1224) | MODIFY | Trip-DTO + Dreizustandsliste |
| docs/context/einstellungen_neu.md (:132/:140) | MODIFY | „nur Ortsvergleich" korrigieren |

### Scope Assessment
- Files: ~15-18
- Estimated LoC: Produktiv ~+70, Tests ~+200, Doku ~+40
- Risk Level: MEDIUM (Go/Python-Drift, Default-Asymmetrie Trip/Compare, Elementlisten- und Alt-AC-Tests), Fachlogik selbst unverändert
- Eine Scheibe, nicht teilbar (Drift-Gate + Elementliste verlangen alle Seiten gleichzeitig)

### Dependencies
- Upstream: RadarNowcastService, `check_nowcast_gate`, `resolve_alert_channels`, `alert_channel_threshold`, NotificationService.send_radar_alert, i18n-Kataloge.
- Downstream: Go-Store/Drift-Gates, Wetter-Reiter, Elementlisten-Abgleich, Radar-Validator, Staging-E2E (Debug-Trigger), api_contract.

### Nebenbefund (ausgelagert)
- **#3186:** pausierte Trips bekommen weiter Alarme (kein Pause-Riegel in den Trip-Alarmpfaden, Compare hat `is_silenced`). Betrifft alle Trip-Alarmarten → bewusst nicht in #2800.

### Open Questions
- keine Produktfrage offen (Default „an" folgt Vorbild amtliche Warnungen und vermeidet stille Regression).

## Übergabe RED → GREEN (Phase 5, 2026-11-19)
- `tests/fixtures/trip_schema_full.json` bekommt `"radar_alert_enabled": false` erst mit der Implementierung (Commit-Gate: vorher grüne Roundtrip-Tests Go/Python dürfen in RED nicht rot werden). Danach müssen `TestTripSchemaDrift_RoundtripSchluesselmengen` und der Python-Roundtrip grün sein.
- `tripSpeicherPayload` nimmt `radarAn` an und schreibt `tripFelder.radar_alert_enabled` (Tests `feat2800_trip_felder_tragen_radar_alert_enabled_aus_dem_stand`, `feat2800_trip_radar_wetter.test.ts`).
- `elementliste_freigaben.json` geht auf `"freigaben": []`; Abgleich-Tests nutzen eine Muster-Freigabe und vertragen das.
- Trip-Text laut `elementliste.json`: DE „Alarm, wenn in der nächsten Stunde Regen auf deine Etappe zukommt“, EN „… towards your stage …“.
- Staging-Playwright `frontend/e2e/s3a2794-teil3-karten.spec.ts` und `…-zwei-nutzer-karten.spec.ts` sind schon auf Radar im Trip umgestellt.
