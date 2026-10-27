# Context: feat-1969-naechstes-briefing

## Request Summary
Issue #1969 (letztes offenes Unter-Issue von Epic #2507): Nutzer sollen sehen, **wann ihr nächstes Briefing tatsächlich verschickt wird**. Heute zeigt die Konto-Seite nur den stündlichen Prüftakt des Go-Schedulers (`trip_reports_hourly`), nicht den echten Versandzeitpunkt. Tech-Lead-Vorschlag (Intake): Anzeige pro Trip/Vergleich im geteilten Versand-Reiter, ggf. zusätzlich im Trip-Cockpit; Konto-Seite nicht der Ort.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:272-281` | `_slot_stunde` — Slot-Stunde aus `report_config.morning_time/evening_time`, nur `.hour`, Default 7/18 |
| `src/services/trip_report_scheduler.py:127, :339, :815` | `NACHHOL_FENSTER_STUNDEN = 3`, Bedingung `stunde <= ortsstunde < stunde+3` |
| `src/services/trip_report_scheduler.py:284-355` | `trip_briefing_due_at(trip, moment, user_id=)` — seiteneffektfreie Fälligkeitsregel (nur „jetzt fällig ja/nein“), genutzt in `src/services/trip_alert.py:1662-1667` |
| `src/services/trip_report_scheduler.py:1157-1219, :1258-1282` | `_get_active_trips` — Ausschlüsse: keine Etappe am Zieltag (morning=Ortstag, evening=Ortstag+1), `paused_at`, `slot_aktiv`, `paused_until` |
| `src/services/trip_report_scheduler.py:821, :829-833` | Idempotenz via `BriefingSlotStore.is_recorded_or_claimed`; `skip_next` wird erst im fälligen Slot verbraucht |
| `src/services/briefing_slots.py:100, :119` | `BriefingSlotStore`, Schlüssel (trip_id, ortstag, slot) |
| `src/services/trip_day.py:29-42, :55-87` | `trip_tz`, `anchor_tz` (Etappe des UTC-Tags → erster Wegpunkt), `trip_local_now`; Fallback UTC |
| `src/app/models.py:1114-1214` | `TripReportConfig` (`enabled`, `morning_enabled/evening_enabled`, `morning_time/evening_time`, `paused_until`, `skip_next`), `slot_aktiv` |
| `src/services/compare_slot_scheduler.py:82-101, :127-132, :142-220` | Ortsvergleich-Fälligkeit `presets_due_for_hour`: exakte Stunde, kein Nachholfenster, `end_date`, Wochentag, `resolve_preset_slots` (Altdaten 06/18) |
| `src/services/compare_alert_guard.py:48-66` | `is_silenced` (paused_at, schedule=="manual", archived_at) |
| `src/output/renderers/email/compare_html.py:1501-1528` | `_compute_next_send` — **abweichende Zweitimplementierung** (nur Datum, daily=„morgen“, ignoriert Slots/end_date/Pause); nur im Compare-Mail-Fuß |
| `frontend/src/lib/utils/cockpitHelpers568.ts:248-283` | `deriveNextSend` — **dritte Implementierung**, rechnet in Browser-Zone (verletzt ADR-0051), nutzt Minuten, ignoriert end_date/paused/archived; genutzt in `CompareTabs.svelte:207`, `CompareStatusRow.svelte:21`, `routes/+page.svelte:561`, `_home/cockpitHelpers.ts:284` |
| `frontend/src/lib/components/shared/VersandTab.svelte:44, :370, :388, :406, :426` | Geteilter Versand-Reiter, `context: 'route'|'vergleich'`, beide Zweige nutzen `VTSchedulePlan` |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte:55-60, :101-113` | Uhrzeit-Auswahl (volle Stunden, #1379); keine „nächstes Briefing“-Anzeige |
| `frontend/src/routes/account/+page.svelte:478-493, :1048-1077` | Konto: „Trip-Checks / Nächste Prüfung“ via `/api/scheduler/status/me`, `formatNextRun` (Browser-Zone + Kürzel, #1727 S5e) |
| `frontend/src/lib/components/.../HubOverview.svelte:113-121` | Trip-Cockpit-Karte „Briefings laufen“ — **fest verdrahtet 06:00/18:00** (Mock-Rest) |
| `frontend/src/routes/_home/cockpitHelpers.ts:156-200` | Startseite „Was geht raus“ (`plannedBriefings`): HH:MM ohne Zone/Datum, Abgleich „gesendet“ über UTC-Tag (`toISOString`, :163) |
| `internal/handler/proxy.go:162-174, :210-233` | `appendUserID` + `StagesWeatherProxyHandler` — Proxy-Muster Go → Python `_internal` |
| `api/routers/internal.py:49, :75-102` | `_internal`-Endpoints (X-GZ-Core-Auth, ADR-0062) — Andockstelle für neuen Endpoint |
| `internal/router/router.go:249` | Route-Registrierung Stages-Weather (Vorbild) |
| `internal/model/trip.go:122, :172-195` · `internal/model/compare_preset.go:24, :33, :131-135` | Go-Modelle; flache Zeitfelder sind abgeleitet, nicht maßgeblich |

## Existing Patterns
- **Fälligkeit wird ausschließlich in Python entschieden** (Go tickt nur stündlich, `internal/scheduler/scheduler.go:341`). Eine Anzeige muss dieselben Bausteine benutzen (`slot_aktiv`, `_slot_stunde`, `anchor_tz`/`trip_local_now`, Etappe am Zieltag, Pausen, `is_recorded`) — sonst Drift.
- **Abgeleitete Werte für das Frontend:** Go-Proxy-Handler mit erzwungener `user_id` aus Auth-Kontext → Python `/api/_internal/...` (Stages-Weather-Muster).
- **Zeit-Anzeige:** ADR-0051 Regel 2/3 — Zone hängt an den Daten (Trip-/Ortszone), mit sichtbarem Kürzel; vorausberechnete Zeitpunkte nie persistieren (Regel 1).
- **Geteilte Bausteine:** Versand-Reiter ist Trip+Vergleich gemeinsam (`context`-Parameter) — Code-Teilungs-Invariante aus CLAUDE.md.

## Dependencies
- Upstream: `TripReportConfig`, `trip_day`-Zonenauflösung, `BriefingSlotStore`, `compare_slot_scheduler`, Trip-/Preset-Store (Python-Loader).
- Downstream (neu): Versand-Reiter (Trip + Vergleich), ggf. HubOverview-Karte, ggf. Startseite. Bestehende Konsumenten der Alt-Implementierungen (`deriveNextSend`, `_compute_next_send`) — Ablösung ist Scope-Frage für die Analyse.

## Existing Specs
- `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` (Regeln :56-69, Fenster/Idempotenz :89-104), `0044-kalendertage-folgen-der-ortszeit.md`, `0023-briefing-subscription-shared-model.md`, `0062-python-core-authentifiziert-gegenueber-go.md`
- `docs/specs/modules/`: `fix_1724_faelligkeit_in_der_ortszone.md`, `fix_1725_faelligkeit_und_idempotenz.md`, `fix_1594_alarm_vorlauf_sperre.md`, `fix_1897_verwaister_briefing_slot.md`, `fix_1726_ruhezeit_und_zaehler_ortszone.md`, `fix_1727_s5c_vorschau_anzeige_ortstag.md`, `fix_1727_s5e_sperrcache_anzeige.md`, `compare_preset_zeitplan.md`, `versand_tab_route.md`, `fix_2422_einstellung_gleich_auslieferung.md`, `fix_2422_s3_kanal_an_aus_kette.md`, `fix_2422_s5_ortsvergleich_kette.md`, `account_page.md`, `account_page_extend.md`, `fix_2149_scheduler_nutzer_sichtbarkeit.md`
- Tests: `tests/tdd/test_briefing_faelligkeit_ortszone.py`, `test_briefing_slot_faelligkeit_und_alarmsperre.py`, `test_briefing_slot_idempotenz.py`, `test_report_config_slot_faelle.py`, `test_trip_alert_briefing_imminent.py`, `test_compare_preset_slot_dispatch.py`, `test_compare_alert_briefing_imminent.py`, `test_vorschau_anzeige_folgen_ortszone.py`; Frontend `compare_next_send_slots.test.ts`, `report_slot_aktiv.test.ts`, `schedulerTime.test.ts`, `compare_send_time_minutes.test.ts`

## Risks & Considerations
- **Drei existierende, voneinander abweichende „nächster Versand“-Rechnungen** (`trip_briefing_due_at`-Bausteine, `_compute_next_send`, `deriveNextSend`). Eine vierte darf nicht entstehen — Ziel: EINE Python-Regel, Anzeigen konsumieren sie. Ob die Alt-Implementierungen im selben Ticket abgelöst werden, klärt die Analyse (Epic-Regel: nicht abspalten).
- **Zone pro Kandidaten-Tag:** Zone hängt an der Etappe des Tages (`anchor_tz`); für künftige Tage pro Tag neu bestimmen. Ohne Wegpunkte fällt sie still auf UTC.
- **Bereits versendet:** heutiger Slot über `is_recorded` ausschließen, sonst „heute 07:00“ obwohl schon raus.
- **Trip in der Zukunft:** erstes Briefing ist evening am Vortag der ersten Etappe; Trip vorbei → keines; Etappen-Lücken überspringen.
- **`skip_next`:** nächster Slot wird übersprungen — Anzeige muss das berücksichtigen/kennzeichnen.
- **Minuten:** Python ignoriert Minuten (`.hour`), Frontend `deriveNextSend` nicht → Anzeige muss HH:00 zeigen.
- **Ist-Versand = HH:00 + Laufzeit** (bis +2 h bei ausgefallenem Tick, Nachholfenster) — Anzeige ist „geplant“, nicht Zusicherung.
- **Kein Versand ansteht** (pausiert, deaktiviert, beendet): Darstellung + ob Grund genannt wird → Spec/PO.
- **Ortsvergleich-Regel weicht ab** (exakte Stunde, kein Fenster/Idempotenz, Wochentag, end_date) — eine geteilte Anzeige braucht zwei Python-Ableitungen hinter einem gemeinsamen Ausgabeformat.
- **Mandantentrennung:** neuer Endpoint mit `user_id` aus Auth-Kontext; `appendUserID` reicht bei leerer userID die Client-Query durch (`proxy.go:163-165`) — Test mit zwei Nutzern Pflicht.
- **HubOverview-Karte ist Mock** (fest 06:00/18:00) — falsche Info heute schon sichtbar; naheliegender Mit-Fix.

## Analysis

### Type
Feature

### Kernbefund
Es gibt heute **drei** voneinander abweichende „nächster Versand“-Rechnungen, keine davon für Trips mit Zone:
- Python-Scheduler (maßgeblich für den echten Versand): Trip `trip_briefing_due_at` / `_get_active_trips`, Ortsvergleich `presets_due_for_hour`.
- Mail-Fuß Ortsvergleich `compare_html.py:1501 _compute_next_send` (nur Datum, daily = „morgen“, ignoriert Slots/end_date/Pause).
- Frontend `cockpitHelpers568.ts:248 deriveNextSend` (Browser-Zone, Minuten, ignoriert end_date/Pause) — speist Ortsvergleich-Detail, Vergleichsliste, Startseite.
- Trip-Seite: `HubOverview.svelte:114` **fest 06:00/18:00** (heute schon sichtbar falsch); `_home/cockpitHelpers.ts:156-200 plannedBriefings` mit Fallback 07:00/18:00.
- Uneinheitliche Fallbacks (06:00 vs 07:00), nirgends ein Zonenkürzel.

Selbst gelesen (Hauptkontext): `trip_briefing_due_at` (`trip_report_scheduler.py:284-355`) prüft dieselben Ausschlüsse wie `_get_active_trips` (`:1157-1219`): `paused_at`, `paused_until`, `slot_aktiv`, Etappe am Zieltag (morning = Ortstag, evening = Ortstag+1), plus Nachholfenster `stunde <= ortsstunde < stunde+3` und `is_recorded`. `skip_next` wird dort NICHT verbraucht (nur `_skip_next_verbrauchen`, schreibt via `save_trip`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/next_briefing.py` | CREATE | EINE reine Ableitung `next_trip_briefing(trip, now_utc, slot_store)` + `next_compare_briefing(preset, locations, now_utc)`, gemeinsames Ausgabeformat; Kandidaten-Slots aufzählen und vorhandene Prädikate fragen (keine neue Regel) |
| `src/services/trip_report_scheduler.py` | MODIFY | Ausschlüsse/Slot-Prädikat aus `trip_briefing_due_at` + `_get_active_trips` in freie Funktionen ziehen (verhaltensneutral), damit Scheduler und Anzeige denselben Code nutzen |
| `src/services/compare_slot_scheduler.py` | MODIFY (ggf.) | `presets_due_for_hour` wiederverwenden; ggf. Grund-Ermittlung (manual/paused/ended) als freie Funktion |
| `api/routers/internal.py` | MODIFY | `GET /api/_internal/next-briefings?user_id=[&trip_id=|&preset_id=]` |
| `internal/handler/proxy.go`, `internal/router/router.go` | MODIFY | Go-Proxy `GET /api/next-briefings` mit `appendUserID` aus Auth-Kontext (Muster `StagesWeatherProxyHandler`) |
| `frontend/src/lib/components/shared/VersandTab.svelte` (+ `versand-tab/VTSchedulePlan.svelte` o. neuer geteilter Baustein) | MODIFY | Anzeige „Nächstes Briefing“ für Trip UND Ortsvergleich (geteilter Baustein, `context`) |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | echte Zeiten statt fest 06:00/18:00 |
| `frontend/src/lib/utils/cockpitHelpers568.ts` (`deriveNextSend`, `resolvePresetSlots`, `primarySendSlot`) | MODIFY/DELETE | Ablösung durch Backend-Wert |
| `frontend/src/lib/components/compare/CompareTabs.svelte`, `molecules/CompareStatusRow.svelte`, `routes/+page.svelte`, `routes/_home/cockpitHelpers.ts` | MODIFY | Konsumenten auf Backend-Wert umstellen |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` (`formatNextSend`) | MODIFY | Formatierung inkl. Zonenkürzel, „manuell“ |
| `frontend/src/routes/trips/[id]/+page.server.ts`, `compare/[id]/+page.server.ts`, `routes/+page.server.ts` | MODIFY | Endpoint laden |
| `src/output/renderers/email/compare_html.py` (`_compute_next_send`, `_render_abo_footer`) | MODIFY | Mail-Fuß auf zentrale Ableitung (Renderer-Gate!) |
| `HubSchedule.svelte`, `organisms/HomeHeroCompare.svelte` | DELETE (zu verifizieren) | vermutlich toter Code mit festen Zeiten — vor Löschen grep auf Importeure |
| Tests: `tests/tdd/test_next_briefing.py` (CREATE), Go-Proxy-Test mit zwei Nutzern (CREATE), Frontend-Tests anpassen: `compare_next_send_slots.test.ts`, `compare_send_time_minutes.test.ts`, `issue_571_home_cockpit_hero.test.ts`, `issue_647_home_fidelity.test.ts`, `cockpitHelpers.test.ts`, `issue_579_home_screen.test.ts`, `issue_578_molecules_organisms.test.ts`; Python `test_vorschau_anzeige_folgen_ortszone.py:657-708` | CREATE/MODIFY | |

### Scope Assessment
- Files: ~20 (davon ~8 Tests)
- Estimated LoC (produktiv, ohne Tests): Python ~250, Go ~50, Frontend ~250–350 ⇒ **~550–650**. Liegt über 250 und über Override 500 ⇒ `loc_limit_override` ~800 nötig (in `/40` bzw. `/50` setzen). Nicht schönrechnen, nicht abspalten (Epic-Regel).
- Risk Level: **MEDIUM** — neue Logik ist rein lesend, aber Refactor berührt die Versand-Fälligkeit (Bestandstests sichern ab) und der Mail-Fuß löst Renderer-Gate + `email_spec_validator.py` gegen echte Staging-Mail aus.

### Technical Approach (Empfehlung, Tech-Lead-Entscheid)
1. **Auslieferung als eigener Sammel-Abruf, kein Feld am Trip-/Preset-JSON.** Grund: `GET /api/trips` (`internal/handler/trip.go:30`) und `GET /api/compare/presets` (`internal/handler/compare_preset.go:178`) liefert Go allein aus dem Store; ein Feld dort hieße Go→Python pro Objekt (N+1) und berührt den ETag der Objekte. ADR-0051 Regel 1 verbietet zudem persistierte vorausberechnete Zeitpunkte.
   - `GET /api/next-briefings` → `{trips:{<id>:NextBriefing}, compare:{<id>:NextBriefing}}`, optional `?trip_id=` / `?preset_id=`.
2. **Keine neue Fälligkeitsregel.** Kandidaten (Ortstag × Slot-Stunde, Zone je Kandidatentag via `anchor_tz`, UTC via `local_dt`) werden aufgezählt und mit den Scheduler-Prädikaten geprüft. Trip: Prädikat aus `trip_briefing_due_at` in freie Funktion ziehen, die Scheduler, Alarm-Sperre (`trip_alert.py:1662`) und Anzeige teilen. Ortsvergleich: `presets_due_for_hour([preset], locations, candidate_utc)` direkt.
3. **Grund separat bestimmen, nicht aus der leeren Suche schließen** (`is_silenced` steckt im Prädikat ⇒ sonst immer „none“): Reihenfolge manual → paused (paused_at / paused_until) → disabled (kein Slot aktiv) → ended (Trip/end_date vorbei) → none.
4. **„Strikt nach jetzt“-Option:** Der Mail-Fuß wird in der fälligen Stunde gerendert — dort darf der gerade laufende Versand nicht als „nächster“ erscheinen. Eigene AC.
5. **Nachholfenster:** Ist der heutige Slot noch nicht vermerkt und das Fenster offen, ist er der nächste (Anzeige = Slot-Stunde, Kennzeichen „überfällig/läuft“).
6. **`skip_next`** nur lesen; Darstellung → PO-Frage.
7. Suchfenster: ab Ortstag heute bis letzte Etappe (Trip; inkl. Vorabend vor Etappe 1), Ortsvergleich daily 2 / weekly 8 Tage, Obergrenze 14 Tage. DST: Offset je Kandidat. Zonen-Fallback UTC wird ehrlich als „UTC“ angezeigt.
8. Uhrzeit immer **HH:00** (Versand ignoriert Minuten — gilt für Trip `_slot_stunde` und Compare `compare_slot_scheduler.py:211-214`). `compare_send_time_minutes.test.ts` pinnt eine Frontend-Fiktion (07:30) und wird angepasst. Wortlaut „geplant“ (Ist-Versand = HH:00 + Laufzeit, bei ausgefallenem Tick bis +2 h).
9. Format (vorläufig): `{at: ISO-8601 mit Offset | null, local_date, local_time: "HH:00", tz: IANA, tz_abbr, slot: morning|evening, skipped?: bool, overdue?: bool, reason?: manual|paused|disabled|ended|none}`; `at == null` ⇒ `reason` Pflicht.

### Reihenfolge (Scheiben im selben Ticket)
- **S1** Python-Refactor (grün mit Bestandstests) → `next_briefing.py` + Tests (Zonen, DST, Auckland, skip_next, Pause, Nachholfenster, bereits vermerkt, end_date, weekly, manual) → `_internal`-Endpoint → Go-Proxy + Zwei-Nutzer-Test. Danach Format für #2346 einfrieren.
- **S2** Anzeige im geteilten Versand-Reiter (Trip + Ortsvergleich), HubOverview echt.
- **S3** Ablösung `deriveNextSend` + Konsumenten, `plannedBriefings`-Fallbacks, toter Code, Mail-Fuß `_compute_next_send` (Renderer-Gate + Validator).

### Bestehende ACs, die erhalten bleiben müssen (Regression)
issue_1268 AC-9/10 (echte Versandzeit statt hour_from) · issue_571 AC-4/4b/4c (vor/nach Slot, manual = kein Versand) · issue_647 AC-4 (echter Wert statt „—“) · issue_1229 AC-4 (Zeile „Nächster Versand“ im Versand-Tab) · fix_1727_s5c AC-5 (Mail-Fuß in Ortszone) · feat_1435 AC-12 (Screenshots HubOverview bei Layoutänderung) · versand_tab_route AC-7/AC-8 (testids, kein Datenmodell-Umbau).

### Dependencies
- Upstream: `TripReportConfig`/`slot_aktiv`, `trip_day` (anchor_tz, trip_local_now), `BriefingSlotStore` (nur lesen), `compare_slot_scheduler`, `compare_alert_guard.is_silenced`, Loader `load_all_trips(user_id)` / `load_compare_presets(user_id)`, Locations.
- Downstream: Versand-Reiter, HubOverview, Startseite, Vergleichsliste, Compare-Mail-Fuß; **#2346** (Startseiten-Kachel, Sitzung gregor-zwanzig-33) verdrahtet sich auf `GET /api/next-briefings` — Feldname/Format nach Spec-Freigabe an sie melden.

### Abstimmung mit #2346 (2026-10-23)
- #2346 baut KEINE eigene Rechnung, markiert „nächster Versand“ in AC-1 als abhängig von #1969, fasst `deriveNextSend` nicht an.
- Liefer-Ort korrigiert: eigener Abruf `GET /api/next-briefings`, nicht Feld am Trip-Objekt.
- Anfrage #2346: `last_briefing` für Trips mit ins Paket? Entscheid #1969: **nicht in diesem Ticket** (Scope bereits ~600 LoC, Ticket-Thema ist „nächstes“). Da der Abruf getrennt vom Go-DTO ist, entsteht keine DTO-Kollision; #2346 kann `last_briefing` nach dem Merge von S1 in denselben Endpoint ergänzen (eine Ableitung je Thema, kein zweiter Endpoint).

### Mandantentrennung
`appendUserID` überschreibt `user_id` aus Auth-Kontext; Go-Test mit zwei Nutzern + Python-Test, dass fremde IDs nicht auftauchen; ohne Auth-Kontext nicht erreichbar.

### Open Questions (PO)
- [x] Anzeige bei „nächstes Briefing überspringen“ → **PO 2026-10-23: übernächster (tatsächlich versendeter) Termin + Hinweis auf den übersprungenen** (z. B. „Do 18:00 (CEST) — Do 07:00 wird übersprungen“).
- [x] Wenn nichts ansteht → **PO 2026-10-23: Grund nennen** („pausiert bis …“, „Trip beendet“, „nur manueller Versand“, „Briefings abgeschaltet“).
- Keine weiteren offenen Fragen.
