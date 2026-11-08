# Context: S2 #2793 — Alarm nach Stufenwechsel der Ampel oder großem Sprung

- **Epic:** #2791 „Einstellungen neu“, Scheibe S2 (2 von 10), abhängig von S1 #2792 (geschlossen 2026-11-07, live `535f80146`).
- **ADR:** ADR-0106 (Akzeptiert, P3 = Abbildung der Altstufen); ADR-0043 abgelöst; ADR-0013 teilweise abgelöst („`threshold` bleibt als Sprung-Schwelle“); bestätigt ADR-0009, ADR-0010, ADR-0021, ADR-0046, ADR-0056.
- **Gemessen gegen:** `origin/main` @ `938045c` (2026-11-08).
- **Übergaben:** zwei Kommentare aus #1895 S4 im Issue (Leser von `alert_rules`, Gate-Fälle 1–4, Kanal-Union vor Abbau auf Prod messen).

## 1. Ist: Auslösung

- **Einstieg:** Go-Cron `*/15` (`internal/scheduler/scheduler.go:345,354`) → `api/routers/scheduler.py:101-113` (Trip, `TripAlertService.check_all_trips`, `src/services/trip_alert.py:1117`) bzw. `:128-157` (Orte, `CompareAlertService._check_one_preset`, `src/services/compare_alert.py:254`).
- **Gate „Abo hat aktive Alarmquelle“:** Trip `trip_alert.py:686-700` (send-Pfad) und `:1187-1219` (`check_all_trips`): `alert_preset` ≠ „deaktiviert“ ODER `metric_alert_levels` gesetzt ODER `any(alert_rules.enabled)`.
- **Anker:** Trip `_get_cached_weather` (`trip_alert.py:1328-1505`, datierter Snapshot → rollierender Kanal-Anker → undatierter Rückfall); Orte `CompareWeatherSnapshotService.load` (`compare_alert.py:694`, ≤ 26 h).
- **Aggregation je Segment/Ort** (`src/services/weather_metrics.py:557-580`, `:1020-1028`): Temp min/max, Böen/Wind max, Niederschlag Summe, Gewitter max, Sicht min, Nullgradgrenze Mittel, CAPE max, Beginn-Zeitpunkte.
- **Entscheidung:** `DeviationAlertEngine.evaluate` (`src/services/deviation_alert_engine.py:264-310`) → `_select_detector` (`:175-204`) → `expand_per_metric_levels` (`src/services/alert_preset.py:152`) → `detect_changes` (`src/services/weather_change_detection.py:770-937`): `abs(delta) > threshold` (`:898`); Sicht als Unterschreiten (`:1095-1133`); CAPE mit Modell-Schwelle (`:843-877`); Beginn-Verschiebung (`:939-985`); Gewitter ordinal (`:1012-1036`, `ORDINAL_LEVEL_BOUNDS` `alert_preset.py:117-121`).
- **Δ-Tabelle `_PRESET_TABLE`** (`alert_preset.py:56-80`), entspannt / standard / sensibel: Böen 35/20/12 · Niederschlag 20/10/5 · Nullgradgrenze 600/400/200 · Temp min 8/5/3 · Temp max 10/6/4 · Neuschnee 20/8/2 · CAPE 1200/600/200 · Sicht (Unterschreiten) 500/1000/3000 · Beginn 2/1/1 h · dazu `*_change`-Delta-Metriken.
- **Ohne Eintrag:** Trip → aktive Wetter-Metrik implizit „standard“ (`alert_preset.py:161-170`); Orte → `_STANDARD_METRIC_LEVELS` + `supplement_missing_levels=True` (`compare_alert.py:57,867-878`).
- **Die Profil-Ampel geht heute nicht in die Auslösung ein.** `alarm_ab` wird nur validiert und gespeichert (`src/app/ampel.py:69-70`), aufgelöst wird die Ampel nur fürs Rendern (`notification_service.py:1145,1239,1320,1972`).
- **`alert_rules` liefert keine Schwellen mehr**, nur noch das Gate (veraltete Kommentare `trip_alert.py:675`, `models.py:845`).

## 2. Ist: Dringlichkeit, Dedup, Texte

- **Dringlichkeit** (`src/services/alert_urgency.py:67-71` → `_highest_severity` `deviation_alert_engine.py:251-262`): Verhältnis Δ/Schwelle (≥2 hoch, ≥1,5 mittel, sonst gering; `weather_change_detection.py:1135-1165`), Gewitter nach höherem Niveau (`:988-1009`), Sicht fest mittel. Entwarnung = hoch (`tests/tdd/test_alert_change_urgency_grading.py` AC-5/6). Kanal-Schwelle `split_by_threshold` (`src/services/alert_channel_threshold.py:20-35`), Sperrzeit-Durchbruch (`trip_alert.py:839-886`).
- **Dedup feldselektiv** `|neu − zuletzt| ≥ threshold` (`deviation_alert_engine.py:234-248`); Cooldown, Ruhezeit, Tageslimit unverändert (Fundstellen im Recherche-Bericht, `alert_gate.py:286,484,512`).
- **Texte** (`src/output/renderers/alert/render.py`): Betreff `:1236-1272`, Mail `:1448-1574`, Telegram `:1577-1628`, SMS/Premium-SMS `:1631-1724` (Premium = `sms_body`, `notification_service.py:2046-2060`). Katalog `src/i18n/messages/{de,en}/alarm.json:27-50` (`alarm.abweichung.h1` „{label} {von} → {bis} seit dem Briefing“, `urteil` „… Änderung {seite} deiner Alarm-Schwelle ({schwelle})“). „über/unter Schwelle“ = `over_thr` (`src/output/renderers/alert/model.py:333-346`). Wortlaut-Verträge: `docs/reference/renderer_email_spec.md:206-218`, `sms_format.md` §3.4f, `telegram_format.md:41-51`, `premium_sms_format.md:52-55`.

## 3. Ist: Datenmodell

- **Profil-Ampel** `display_config.ampel` = `{template, metrics:{<katalog_id>:{enabled, lower, upper, alarm_ab}}, thunder:{mittel, hoch}}` (`docs/reference/api_contract.md:1339-1356`). `alarm_ab` ∈ never/yellow/orange/red (`src/app/ampel.py:28`, `internal/handler/ampel.go:15`). Vorgaben je Vorlage in `src/app/ampel_templates.py:24-197` (überwiegend Orange; Vorboten, Luftfeuchte, Bewölkung Nie; Abweichungen z. B. `temperature_night` Nie bei wintersport/radtour/wassersport, `fresh_snow` Nie bei wintersport). Rückfallkette `ampel.py:138-167`.
- **Lücke aus S1:** Die Prüfung lässt `alarm_ab: "yellow"` bei Gewitter zu (`ampel.py:69`, `ampel.go:58-62`), ADR-0106 verlangt Nie/Orange/Rot.
- **Stufe eines Werts:** `ampel_stufe(ampel, metric_id, wert)` (`ampel.py:279-283`), Gewitter `thunder_color` (`ampel.py:256-272`, „leicht“ fest gelb). Schwellen nur für `AMPEL_LESER` (9 Metriken, `ampel.py:197-200`); Nullgradgrenze, CAPE und Beginn-Werte haben keine Ampel.
- **Altfelder:** `metric_alert_levels` (`src/app/models.py:848`), `alert_preset` (`:847`), `alert_on_changes` (`:1145`), `Trip.alert_rules` (`src/app/trip.py:199`). Schlüssel der Altstufen sind AlertMetric-Werte (`wind_gust`, `precipitation_sum`, `temperature_min/max`, `thunder_level`, `thunder_onset` …), Brücke zu Katalog-IDs `_ALERT_METRIC_TO_CATALOG_ID` (`weather_change_detection.py:96-118`) bzw. `internal/model/alert_metric_mapping.generated.json`. Loader-Normalisierung alter Schlüssel `loader.py:780-819`.
- **Persistenz:** Trip und Orte in `data/users/<uid>/briefings/<id>.json`; `_write_trip_locked` merged tief, ersetzt aber `ampel` als ganzen Unterbaum (`loader.py:2083-2086`). Go `mergeConfigMap` nur eine Ebene tief (`internal/handler/config_merge.go:11-22`). Go prüft `metric_alert_levels` nicht.
- **Frontend bis S3a:** Alarm-Empfindlichkeit bleibt bedienbar (`frontend/src/lib/components/alerts-tab/AlertMetricLevelRow.svelte`, `shared/AlarmeTab.svelte:282-291,538-542`, Speichern `shared/alarme-tab/alarmeDeliveryPayload.ts:131-135`, `shared/alarmeVergleichSpeicherung.ts:130,158`).
- **Vorbild Migration:** `scripts/migrate_2792_profil_ampel.py` (`--root`, `--backup-dir`, `--execute`; tar.gz je Nutzer; Schreiben unter `exclusive_lock`, Inhaltsvergleich, atomar; „Nichts zu tun“).

## 4. Analyse

**Was S2 ändert:** Die Auslösung liest `ampel.metrics.<id>.alarm_ab` und die Ampel-Stufe von Anker- und Neuwert statt der Δ-Stufe. Der Δ-Wert aus `_PRESET_TABLE` bleibt nur als **Sprung-Schwelle** (ADR-0013 Nachtrag). Die Altstufen werden einmalig per Migration nach ADR-0106 P3 in `alarm_ab` überführt (relativ zur Vorlage); `metric_alert_levels` bleibt in der Datei erhalten (Read-Modify-Write, kein Löschen).

**Offen und PO-relevant (in dieser Scheibe zu entscheiden):**
1. **Größe des Sprungs:** Das Konzept-Beispiel Böen 65 → 95 (Δ 30) meldet nur, wenn die Sprung-Schwelle ≤ 30 ist: mit der heutigen Spalte „standard“ (20) ja, mit „entspannt“ (35) nicht.
2. **Rückgang, der im Alarmbereich bleibt** (rot → orange bei „Alarm ab Orange“, großer Sprung nach unten innerhalb Rot): Das Issue nennt Entwarnung nur beim Fallen unter die Stufe; ADR-0043 hatte Entwarnung symmetrisch zu jeder Verschärfung.
3. **Dringlichkeit:** Heute aus Δ/Schwelle; mit der Ampel liegt nahe: gelb = gering, orange = mittel, rot = hoch (passt zu S9 „SMS ab mittel, Premium-SMS ab hoch“).
4. **Alarme ohne Ampel:** Nullgradgrenze (Ampel erst mit S7, relativ), Beginn-Verschiebung Gewitter/Starkregen (Zeit, keine Stufe), `*_change`-Delta-Metriken. CAPE-Alarm entfällt laut ADR-0106 P1.

**Technisch, ohne PO-Frage (Spec-Entscheidung):**
- Gate bleibt in S2 wie heute (Gate-Fälle 1–4 aus der #1895-Übergabe); Rückbau von `alert_rules` ist nicht Teil von S2. Zusätzlich gilt: Hat keine alarmfähige Metrik `alarm_ab` ≠ Nie, prüft der Lauf nichts.
- Stufe = Farbe unabhängig von der Seite (Temperatur unten/oben); die Richtung („zu kalt“/„zu warm“) nennt der Text.
- Dedup bleibt feldselektiv, Schlüssel zusätzlich mit Stufe, damit derselbe Stufenwechsel nicht zweimal meldet.
- Gewitter-Prüfung `alarm_ab` ∈ {never, orange, red} in Python und Go nachziehen (Lücke aus S1).
- Frontend bis S3a: Die alte Empfindlichkeitstabelle schreibt nach S2 wirkungslos; nach E2 (S1) darf nichts still wirkungslos sein ⇒ in S2 wie bei S1c-3 nur lesbar mit Hinweis, Migration hat den Wert übernommen.
