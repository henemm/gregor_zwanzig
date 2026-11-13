# Context: feature-2795-s3b-teil1-zustellung

Issue #2795 (Epic #2791 „Einstellungen neu“, Scheibe S3b), **Teil 1 = Teil B des Issues: Reiter „Zustellung“ komplett**.
Teil A („Inhalt je Kanal und Fläche“ im Reiter Wetter, 3-Tages-Ausblick-Vereinheitlichung, Kurzstil-Umzug) folgt als Teil 2 in einem eigenen Workflow.

## Request Summary
Der Reiter Zustellung (Trip und Orte, ein Code) wird nach Mockup Fassung 3 (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, `viewZustellung()` Zeile 539–590) neu gebaut: Morgen-/Abend-Briefing mit Uhrzeitfeld (keine Schnellwahl), Laufzeit, Warnungen „Kein Kanal für Briefings/Alarme“, eine Kanal-Tabelle (Kanal · Briefing · Alarme · Alarm schon ab Dringlichkeit) für alle vier Kanäle mit Status, Konto-Hinweis und Sperren, Stille Stunden, „Anpassen“ mit Cooldown. Alte Versand-/Alarm-Bausteine im Reiter werden in derselben Scheibe entfernt (Epic-Regel 4: senkrecht, sichtbar, alte Bausteine weg). Abnahme: Elementliste Scope `zustellung` lückenlos + Soll/Ist-Bild an den PO.

## Soll (Mockup, Kernaussagen)
- Kopf: „Zustellung — Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.“
- Zwei Karten nebeneinander: Morgen-Briefing (07:00, Schalter; Trip „für die Etappe des Tages“, Orte „für heute“), Abend-Briefing (18:00; Trip „für die Etappe von morgen“, Orte „für morgen“). Uhrzeit frei eintippbar (AC-Skizze 06:45).
- Laufzeit: Trip „{Daten}. Die Briefings enden nach der letzten Etappe. Die Daten pflegst du in den Etappen.“ + „Etappen öffnen →“; Orte Segment „Bis auf Weiteres · Bis Datum“ + Datumsfeld, je Wahl eigener Erklärsatz.
- Warnboxen (role=alert) nur wenn 0 Briefing- bzw. 0 Alarm-Kanäle.
- Kanal-Tabelle: Kopf „Briefings über {n} {Kanal|Kanäle} · Alarme über {m} …“, Unterzeile „Ein Kanal ohne Verbindung ist gesperrt, bis du ihn im Konto einrichtest.“; je Zeile Statuspunkt + Text + Ziel; ohne Verbindung Hinweis + „Im Konto {verbinden|bestätigen|prüfen} →“, Briefing-Schalter gesperrt, Alarm-Zelle „gesperrt: {Grund}“; Dringlichkeit-Segment gering/mittel/hoch nur wenn Alarm an, sonst „–“. Legende: „Die SMS kostet wenig … Premium-SMS … nur bei ‚hoch‘.“
- Stille Stunden von–bis + Schalter, darunter `<details>` „Anpassen“: „Mindestabstand zwischen zwei Alarmen — derselben Metrik — {10} Minuten“.
- Elementliste (`docs/context/einstellungen_neu/elementliste.json`) enthält je Kontext Abschnitte abschnittskopf, briefing-zeiten, laufzeit, kanaele, stille-stunden in Zuständen normal/laedt/fehler/luecken (462 Zeilen für zustellung).

## Related Files (FE = frontend/src/lib)
| Datei | Relevanz |
|---|---|
| FE/components/shared/zustellung-tab/ZustellungTab.svelte | Heutiger Übergangs-Reiter: rendert `WetterMetrikenVersandPanel bereich="zustellung"` (:37) + Alarme (:39-45). Wird zum neuen Reiter. |
| FE/components/shared/WetterMetrikenVersandPanel.svelte | Rendert WeatherMetricsTab (Abschnitte layout_kanal, stundenverlauf, ausblick, report_config, nachtblock, sms_schwellen; `weatherMetricsTabSections.ts:88`) + `<section id="versand">` (:70-95). Kanalinhalt-Teile gehören zu Teil 2 (Wetter → Inhalt je Kanal). |
| FE/components/shared/versand-tab/* | VersandTab, VTBriefingChannels, VTSchedulePlan (Stunden-Select + Mehrtages-Trend), VTLaufzeitRoute/Vergleich, VTNextBriefing; Helfer. Behalten (außerhalb benutzt): channelConnectionStatus, premiumSmsChannelState, nextBriefing*, reportConfigPayload/mergeReportConfig, dayWindowClamp, sendTargetLabel, channelContactLabel. |
| FE/components/shared/AlarmeTab.svelte | Heute im Reiter Zustellung: Abschnitte official-warnings, [radar], metric-levels, channels (AlertChannelPicker), cooldown (AlertCooldownCard), quiet-hours (AlertQuietHoursCard), sample; AlertMetricChannelsBlock; Telegram-Kurzstil (Vergleich :574-586). Speichert konsolidiert (Owner `alarme`). |
| FE/components/trip-detail/TripTabs.svelte :215 · compare/CompareTabs.svelte :816-876 | Montage des Reiters; Vergleich mountet erst nach Hydration (versand/alarme/wetter). |
| FE/components/trip-detail/BriefingScheduleTab.svelte :47-56 · AlarmeScheduleTab.svelte | Trip-Speicherwege (PUT /api/trips/{id}, pickEigenfelder Owner `versand`/`alarme`). |
| FE/components/shared/versandVergleichSpeicherung.ts :128-187 · alarmeVergleichSpeicherung.ts :120-132 | Vergleich-Speicherwege (Diff-Gate, Queue, Rollback). |
| FE/components/shared/alarme-tab/alarmeDeliveryPayload.ts :85-138 · tripChannelReconstruction.ts · premiumSmsAlarmGate.ts :46-56 | Alarm-Nutzlast, Kanal-Rekonstruktion, „Tarif wird geprüft“. |
| FE/components/shared/subscriptionTabs.ts :43-152 | Reiterdefinition, Alt-Kennungen → zustellung, `#versand`-Anker. |
| FE/components/shared/hub-uebersicht/hubUebersichtModell.ts :101 · HubUebersicht.svelte :99-194 | „Bearbeiten →“ zielt schon auf zustellung#versand (U2), „Nächstes Briefing“ bleibt (V13). |
| routes/compare/[id]/+page.svelte :368-370 | „Setup abschließen“ → `?tab=zustellung#versand` (K13 schon erfüllt). |
| trip-new/TripNewEditor.svelte :930-1218 · compare-new/CompareNewEditor.svelte :606-612 | Anlegeseiten nutzen VersandTab/AlarmeTab ebenfalls — Abhängigkeit beim Entfernen. |
| FE/types.ts :267-305, :392-452, :709-788 | ReportConfig, Trip, ComparePreset. |
| internal/handler/trip.go :317 · compare_preset.go :384 · auth.go :913-990 | PUT-Merge (If-Match), Profil mit Kanalstatus/Tier/Premium-SMS-Zustand. |
| src/app/trip.py :176ff · src/app/models.py :1114-1182, :1309ff | Python-Modelle. |
| scripts/elementliste_aus_mockup.ts · scripts/elementliste_abgleich.ts · e2e/elementliste_abgleich_logik.ts · docs/context/einstellungen_neu/elementliste_freigaben.json | Abnahme-Werkzeug (`npm run elementliste:abgleich -- --scope zustellung`), DOM-Marker `data-abschnitt="…"`. |
| .claude/agents/mockup-bildpruefer.md | Bildvergleich am Scheibenende. |

## Existing Patterns
- Ein Code für Trip/Orte über `context="route"|"vergleich"` (ADR-0097); Organismen unter `FE/components/organisms/wetter-tab/` aus S3a als Vorbild (Atomic Design, ADR-0112: nur Design-System-Bausteine).
- Abschnitte im DOM mit `data-abschnitt` markieren (S3a `WarnungenRadarKarte.svelte:28`), damit der Elementlisten-Abgleich greift.
- Speichern: Trip über PUT mit pickEigenfelder-Owner-Schlüsseln (Server-Merge, If-Match); Vergleich über Diff-Gate-Queue. Zwei Owner (`versand`, `alarme`) existieren schon; der neue Reiter darf keine zweiten Speicherer für dieselben Felder erzeugen (Test `s3a2794_speicher_owner_waechter`).
- Kanalstatus aus `GET /api/auth/profile` + `channelConnectionStatus.ts` (heute dreimal geladen).
- Texte nur über Kataloge de/en (ADR-0104), heute Präfixe `versand.*`, `alarme.*`; noch keine `zustellung.*`-Schlüssel; Glossar ohne „Zustellung“, „Stille Stunden“, „Dringlichkeit“.

## Dependencies
- Upstream: Profil-Endpunkt, Trip-/Preset-PUT, Kataloge, Design-System-Atome (Schalter, Segment, Eingabefeld).
- Downstream: Scheduler (Python `compare_slot_scheduler.py` liest `morning_time` als volle Uhrzeit `HH:MM` → Minuten werden backendseitig schon unterstützt; Frontend wählt heute nur Stunden, `versandzeit_stundenwahl.md`), Alarmversand (alert_channels, alert_channel_thresholds, cooldown, quiet hours), Übersicht/Kopf (Sprungziele), Anlegeseiten.

## Existing Specs
- docs/specs/modules/feat_2794_s3a_reiter_wetter.md (+ teil2/3/4/4b) — Vorgänger, nennt S3b.
- versand_tab_route.md, versand_tab_vergleich.md, versand_channel_toggle_persistence.md, versandzeit_stundenwahl.md, fix_2422_s3_kanal_an_aus_kette.md, rework_2276_s5/s6e_versand.md.
- feat_1461_s3b2a_kanal_schwelle.md, feat_1461_s3b2b_compare_kanal_schwelle.md, feat_2293_s2_compare_alarm_kanaele.md, fix_1745_a_alarm_kanal_premium_sms_ui.md, alert_metric_channels.md, user_profile_channels.md.
- ADR-0046 (Alarm-Kanal-Schwelle), ADR-0049 (Premium-SMS), ADR-0095 (Kanal-Parität), ADR-0097, ADR-0109 (Reiterstruktur), ADR-0112.

## Risks & Considerations
1. **Vergleich hat kein `send_email`** (types.ts ComparePreset, VersandTab.svelte:58, VERSAND_TOP lässt es aus): die Tabelle zeigt für Orte einen E-Mail-Briefing-Schalter, der heute nicht gespeichert wird. Klären: Modellfeld nachziehen (Go/Python, Read-Modify-Write) oder E-Mail-Briefing bei Orten fest an.
2. **Uhrzeit:** Mockup/AC verlangt freies Uhrzeitfeld (06:45); heute Stunden-Select (Spec versandzeit_stundenwahl). Backend parst HH:MM; Scheduler-Taktung prüfen (Slot-Versatz, Viertelstunden-Raster?).
3. **Was aus AlarmeTab wohin:** amtliche Warnungen/Radar wohnen schon im Wetter-Reiter (WarnungenRadarKarte) → Doppelung im Zustellung-Reiter entfernen; „Alarm ab“ je Metrik ist im Wetter-Reiter (S3a); AlertMetricChannelsBlock (Kanäle je Metrik) und „sample“ haben im Mockup keinen Platz → Abgleich `abgleich-alt-neu.html` prüfen, nicht still entfernen.
4. **Telegram-Kurzstil** sitzt heute im Versand (Trip) bzw. Alarme (Vergleich); Ziel ist Wetter → Telegram (Teil 2). In Teil 1 darf er nicht ersatzlos verschwinden → bis Teil 2 an alter Stelle belassen oder Teil 2 vorziehen.
5. **Inhalt-je-Kanal-Teile** (layout_kanal, ausblick, report_config, nachtblock, sms_schwellen) hängen heute im Zustellung-Reiter über WetterMetrikenVersandPanel; Ziel Wetter-Reiter (Teil 2). Teil 1 muss sie entweder mitnehmen oder vorübergehend sichtbar lassen — Bedienelemente dürfen nicht verloren gehen.
6. **Anlegeseiten** (TripNewEditor, CompareNewEditor) nutzen VersandTab/AlarmeTab; Entfernen alter Bausteine nur, wo nichts mehr importiert.
7. **Zwei Speicherer**: Kanal-Tabelle mischt Briefing (Owner versand) und Alarme (Owner alarme) in einer Zeile → Speicherwege sauber getrennt halten, keine Doppel-Schreiber; Vergleich-Hydration-Gate beachten.
8. **Mandantentrennung:** keine neuen Endpunkte geplant; falls doch, Zwei-Nutzer-Test.
9. **Premium-SMS-Status sicherheitsrelevant** (V5): verfallene Rückadresse → Alarm-Zelle gesperrt mit Grund, Hinweis „Schick eine Nachricht vom Gerät …“.
10. Vielzahl bestehender Tests/E2E-Specs auf VersandTab/AlarmeTab (28 + ~20 node-Tests, ~15 Playwright-Specs) — beim Entfernen gezielt anpassen oder löschen.

## Analysis

### Type
Feature (Scheibe S3b Teil 1 = Issue-Teil B, Reiter Zustellung)

### Befunde, die den Kontext korrigieren
- **Minuten werden NICHT unterstützt** (Gegenbefund zu „backendseitig schon unterstützt“): Go kappt beim Schreiben und Lesen auf volle Stunde (`internal/handler/compare_preset.go:57-59`, `internal/handler/trip.go:403-405`, `internal/store/slot_hour_normalization.go`); Python wertet nur `.hour` (`src/services/trip_report_scheduler.py:259-268`, `src/services/briefing_slots.py:62-67` `fenster_offen`, Nachholfenster 3 h); Go-Cron `briefing_dispatch` stündlich (`internal/scheduler/scheduler.go:341`); Claim-TTL 900 s an Stunden-Takt gebunden (`briefing_slots.py:44-47`); `MORGEN_SLOT_VERSATZ` (`compare_slot_scheduler.py:226`). Ein freies Feld ohne Backend-Umbau = stille Verfälschung (06:45 → 06:00), verboten.
- **ComparePreset hat kein `send_email`**; E-Mail-Briefing bei Orten immer an (`src/services/scheduler_dispatch_service.py:723-731`, `src/services/compare_alert_channels.py:46`). Mockup zeigt Schalter → Feld nachziehen, Default true bei fehlendem Feld (Alt-Presets dürfen nicht verstummen), Tests fehlt/true/false.
- Cooldown: `alert_cooldown_minutes`, Default 120 (Trip `trip_alert.py:560,1733`, Vergleich `compare_alert.py:59`). Die „10“ im Mockup ist Beispielwert → Feld zeigt den echten Wert, Default bleibt.
- Kanal-Schwelle `alert_channel_thresholds` {email,telegram,sms,premium_sms} LOW|MODERATE|HIGH (fehlend = LOW) für Trip und Vergleich → Segment gering/mittel/hoch.
- Stille Stunden `alert_quiet_from/_to` „HH:MM“; Laufzeit Orte `end_date` (nil = bis auf Weiteres), Trip abgeleitet aus Etappen.

### Zuordnung alter Elemente (Plan `docs/context/einstellungen_neu.md` §3.2/3.3)
| Element | Ziel |
|---|---|
| Briefing-Kanäle V1, Uhrzeit V9 (Schnellwahl V11 weg), Laufzeit V14/V15 | Zustellung (neu) |
| AlertChannelPicker A7/A8, Cooldown A12, Stille Stunden A13 | Zustellung (neu) |
| Amtliche Warnungen/Radar, Alarm ab je Metrik | bereits Reiter Wetter (S3a) → im Zustellung-Reiter entfernen |
| Nächstes Briefing V13 | Übersicht (schon da) |
| Telegram-Kurzstil, Layout je Kanal, Ausblick/Mehrtages-Trend, Nachtblock | Teil 2 (Wetter → Inhalt je Kanal); bis dahin Übergangsblock |
| Beispiel-Alarm A14 | Kopf „Test schicken“ (S5 #2797); bis dahin Übergangsblock |
| SMS-Schwellen W13, Empfindlichkeit A4 | entfallen (Ampel) |
| **AlertMetricChannelsBlock „Kanäle je Wettergröße“** | **keine PO-Entscheidung, kein Platz im Mockup → PO-Frage** |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| internal/store/slot_hour_normalization.go, internal/handler/trip.go, internal/handler/compare_preset.go | MODIFY | Kappen auf Raster statt Stunde (abh. PO-Entscheid) |
| internal/scheduler/scheduler.go | MODIFY | Cron-Takt briefing_dispatch passend zum Raster |
| src/services/briefing_slots.py, trip_report_scheduler.py, compare_slot_scheduler.py | MODIFY | Fälligkeit in Minuten, Claim-TTL, Dedupe je Slot prüfen |
| internal/model/compare_preset.go, src/app/models.py, src/services/scheduler_dispatch_service.py, compare_alert_channels.py | MODIFY | `send_email` für Orte, Default true |
| FE/components/organisms/zustellung-tab/* (BriefingZeitenKarten, LaufzeitKarte, KanalTabelle, KanalWarnboxen, StilleStundenKarte) | CREATE | Organismen mit `data-abschnitt` |
| FE/components/shared/zustellung-tab/zustellungModell.ts, zustellungSpeicherung.ts | CREATE | Modell + EIN Reiter-Speicherer mit zwei Nutzlast-Teilen (Owner `versand` / `alarme` bleiben, Wächter s3a2794 grün) |
| FE/components/shared/zustellung-tab/ZustellungTab.svelte | MODIFY | Container; Übergangsblock (WetterMetrikenVersandPanel ohne `<section id="versand">`) |
| FE/components/shared/versandVergleichSpeicherung.ts, trip-detail/BriefingScheduleTab.svelte, alarmeVergleichSpeicherung.ts | MODIFY | Nutzlast-Bau als reine Funktionen herauslösen |
| FE/i18n Kataloge de/en | MODIFY | `zustellung.*`-Schlüssel, Glossar |
| FE/types.ts | MODIFY | ComparePreset.send_email |
| Tests Go/Python/node/Playwright | CREATE/MODIFY | siehe Scope |

### Scope Assessment
- Backend ~10-14 Dateien, +250/-40 LoC (inkl. Tests); Frontend-Neubau ~12-15 Dateien, +900/-200; Aufräumen danach ~-1500 inkl. Tests.
- Risk Level: MEDIUM-HIGH (Versandzeitpunkt aller Briefings; zwei Speicherwege in einer Tabelle).

### Technical Approach (Empfehlung)
Teil 1 in drei Scheiben: **1a Backend** (Uhrzeit-Raster + `send_email` Orte, eigener PR, kein UI; Tests: 06:45 überlebt Schreiben+Lesen, genau ein Versand je Slot über mehrere Ticks, Alt-Preset ohne Feld sendet E-Mail) → **1b Neubau Reiter** (Organismen, ein Speicherer, Profil einmal laden, Kataloge, Übergangsblock für Teil-2-Inhalte + Beispiel-Alarm + ggf. Kanäle je Wettergröße, sichtbar als Übergang im Soll/Ist-Bild; Elementliste Scope zustellung) → **1c Aufräumen** (nicht mehr importierte Alt-Bausteine, Anlegeseiten beachten). Anlegeseiten (TripNewEditor/CompareNewEditor) bleiben vorerst auf VersandTab/AlarmeTab.
Abgrenzung zu paralleler Sitzung #2913: Abgleich-Werkzeuge fasse ich nicht an; Marker im Reiter Zustellung setze ich.

### Dependencies
Owner-Wächter `frontend/src/lib/components/shared/__tests__/s3a2794_speicher_owner_waechter.test.ts`; Vergleich-Hydration-Gate CompareTabs; Anker `#versand` (subscriptionTabs, HubUebersicht U2, Setup K13).

### Open Questions
- [x] PO 2026-11-12: **Viertelstunden-Raster** (06:00/06:15/06:30/06:45 eintippbar und eingehalten) → Backend-Scheibe 1a
- [x] PO 2026-11-12: **„Kanäle je Wettergröße“ entfällt**; Alarme gehen über die Kanal-Tabelle, je Kanal steuert die Dringlichkeit. Bestehende `alert_metric_channels`-Sonderregeln beim Umstieg auflösen (Read-Modify-Write, keine Datenverluste anderer Felder); Verhalten danach: Kanal-Tabelle gilt für alle Metriken
- [ ] Tech: Dedupe-Schlüssel in briefing_slots.json (Stunde vs. Slot-Name) in 1a prüfen

## RED-Stand Teilschritt 1a (Phase 5, 2026-11-12)

Testdateien (neu): `internal/store/slot_quarter_hour_2795_test.go`, `internal/handler/zustellung_2795_test.go`, `internal/scheduler/briefing_dispatch_15min_2795_test.go`, `tests/test_2795_viertelstunden_faelligkeit.py`, `tests/test_2795_send_email_orte.py`, `tests/test_2795_alert_metric_channels_ignoriert.py`, `tests/test_2795_migration_alert_metric_channels.py`. Belege: `docs/artifacts/feature-2795-s3b-teil1-zustellung/test-red-output-{go,python}.txt` (Python 25 rot / 20 grün, Go 17 FAIL). Teilschritte 1b/1c bekommen eigene RED-Runden.

**Erwartete Migrations-Schnittstelle** (Muster `scripts/migrate_2793_alarm_ab.py`): `scripts/migrate_2795_alert_metric_channels.py --root <data/users> [--backup-dir <pfad>] [--execute]`, Exit 0. Nutzer = Unterordner ohne `.`/`_`-Präfix, Dateien `<root>/<uid>/briefings/*.json` (Trip + Vergleich). Ohne `--execute`: Probelauf, schreibt nichts, Protokoll trotzdem. Mit `--execute`: je betroffenem Nutzer zuerst `*.tar.gz` in `--backup-dir`, dann Read-Modify-Write, entfernt nur obersten Schlüssel `alert_metric_channels`. Protokoll stdout je Nutzer `== Nutzer <uid> ==` mit Abo-Kennung, Metrik-ID, eingeschaltete Kanäle der alten Regel. Zweiter Lauf byte-gleich, kein `default`-Ordner.

**Abweichungen Code ↔ Spec (für /50-implement):**
- Orte-Fälligkeit steckt in `presets_due_for_hour` (`compare_slot_scheduler.py`, `fenster_offen(zeit.hour, hour)`), nicht in `_due`.
- `fenster_offen(slot_stunde:int, ortsstunde:int)` in `briefing_slots.py:62`; Trip: `_slot_stunde` (:259–268) und `nachhol_fenster_offen` (:339–342, `vor_ort.hour`). Tests binden sich nicht an eine neue Signatur.
- `_compare_slot(..., slot_hour:int)` in `scheduler_dispatch_service` (Nachholversand, Vermerk) trägt ebenfalls nur die Stunde — mit umstellen.
- Orts-Briefing-Kanäle: `_effective_compare_briefing_channels` (`scheduler_dispatch_service.py:720`, Aufruf :864); Regel „E-Mail immer“ in `compare_alert_channels.py` (`channels = {"email"}`).
- Dedupe-Schlüssel ist bereits (Abo, Slot, Ortstag); `CLAIM_TTL` 900 s = neuer Takt.
- Trip-Zeiten in `report_config.morning_time`, Flachfelder abgeleitet in `store/trip.go:102`; Kappen zusätzlich in `CreateTripHandler` (`trip.go:180`). Trip-PUT hat heute keine 400-Prüfung → neu.
- Cron `scheduler.go:341` „Briefing Dispatch (hourly)“; Teil-Job-Bezeichnungen nennen auch „hourly“.
- Go-Preset: typisierter Unmarshal verwirft `send_email` → Feld ins Modell.

**Überholte Bestandstests (anpassen/entfernen in 1a):** `internal/store/slot_hour_normalization_test.go`, `internal/handler/compare_preset_slot_hour_normalization_test.go`, `internal/handler/trip_report_config_slot_hour_normalization_test.go` (Kappen auf Stunde); `internal/scheduler/radar_cron_offset_test.go` (Feuer-Minute 0 → 15); Python #1895: `tests/tdd/test_alert_metric_channel_reader.py`, `test_alert_metric_channel_keys.py`, `test_alarm_abweichung_kette.py`, `test_compare_alarm_einstellung_auslieferung_kette.py`, vermutlich `test_alert_metric_channel_migration.py`. Helfer aus `tests/tdd/test_briefing_slot_idempotenz.py` bleiben in Gebrauch.
