# Context: fix-2869-naechster-versand-zeitzone

## Request Summary
Issue #2869 (Nebenbefund aus #2845, Epic #2345 Strang B): Kachel „Nächster Versand" zeigte am 07.11.2026 auf Staging
beim Trip `So 06:00 (CEST)`, beim Ortsvergleich `So 06:00 (CET)` für denselben Sonntag 08.11.2026 (Winterzeit, korrekt: CET).
Ziel: Ursache finden, aus Nutzersicht rot nachweisen, beheben — oder belegt ausschließen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/next_briefing.py` | EINE Ableitung „Nächstes Briefing" je Trip/Vergleich; `_termin()` setzt `tz_abbr = vor_ort.tzname()` |
| `src/services/trip_day.py` | `trip_tz`, `display_tz`, `anchor_tz`, `trip_local_now` — Zonenwahl des Trip-Pfads (alle `ZoneInfo`, Rückfall `UTC`) |
| `src/utils/timezone.py` | `tz_for_coords` (TimezoneFinder → `ZoneInfo`), `local_dt`, `to_utc` |
| `src/services/trip_report_scheduler.py` | `trip_slot_due`, `_slot_stunde` — Bestätigung der Kandidaten |
| `src/services/compare_slot_scheduler.py` | `_preset_ortszeit`, `presets_due_for_hour` — Vergleich-Pfad |
| `api/routers/internal.py:216` | `GET /api/_internal/next-briefings` — echte Uhr, keine Zeitverschiebung, kein Cache |
| `internal/handler/proxy.go:250` | Go-Proxy `/api/next-briefings` (reicht nur durch, `user_id` aus Auth) |
| `frontend/src/lib/components/shared/versand-tab/nextBriefingText.ts` | `formatNextBriefing`: Wochentag aus `local_date`, Text `${wt} ${local_time} (${tz_abbr})` — rechnet selbst keine Zone |
| `frontend/src/lib/components/shared/versand-tab/naechstesBriefingLader.svelte.ts` | geteilter Lader (Trip + Vergleich), kein eigener Zwischenspeicher |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:201/271` | Hub-Kennzahl „Nächster Versand" je kind über denselben Formatierer |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte:46` | Karte „Briefings laufen": Slot-Stunde aus `report_config` + `tz_abbr` des Backends |
| `frontend/src/service-worker.ts:403` | `/api/*` wird nicht angefasst (kein veralteter Offline-Wert) |
| `tests/tdd/test_next_briefing.py` | AC-5 deckt Kandidat über die Umstellung 24.→25.10. ab (CEST→CET), PDT-Zonenwechsel, UTC-Rückfall |

## Befund der Kontextphase (gemessen 2026-11-11)
- Frontend ist reine Anzeige: das Kürzel kommt 1:1 aus `tz_abbr` des Backends, beide kinds nutzen denselben Formatierer und Lader.
  Kein E2E-/Skript-Mock von `next-briefings` (`frontend/e2e` ohne `page.route` darauf), Service-Worker lässt `/api/*` aus.
- Python: alle Zonen sind `ZoneInfo` (oder `UTC`); `tzname()` hängt am Wandzeit-Datum des Termins. Ein europäischer Termin
  am 08.11. kann daraus nicht `CEST` ergeben. Code-Lektüre findet KEINEN Pfad, der das Kürzel eines anderen Datums nimmt:
  - strict-Zweig: `trip_local_now(trip, moment)` je Kandidat;
  - nicht-strict-Zweig (`at = vor_ort.replace(hour=…)`): gleicher Ortstag wie `now`, `ZoneInfo` rechnet Kürzel aus Wandzeit neu.
- Nachrechnung mit Staging-Code gegen Staging-Daten (lesend, `sudo -n -u claude-gregor … uv run --project gregor_zwanzig_staging`,
  Messskript im Scratchpad `probe.py`): beide Trips mit Termin → `CET` (`Europe/Madrid`, `Europe/Vienna`). Der Trip von der
  Abnahme am 07.11. existiert nicht mehr (Testdaten rollieren); die Fresh-Eyes-Bilder lagen im gelöschten Worktree
  `cozy-hugging-pancake`, die Beobachtung steht nur im Body von #2845 (kein Bild, keine Trip-ID).
- Prod-Nachrechnung vom Auto-Modus als „Production Reads" geblockt (nicht nötig für den Nachweis, nicht umgangen).

## Existing Patterns
- ADR-0051: Zeit nur als Parameter, Anzeige nie aus Browser-Zone, Kürzel aus dem Termin-Moment.
- EINE Ableitung für beide kinds (Epic #2345): eine Korrektur gehört in `next_briefing.py`/`trip_day.py`, nicht ins Frontend.
- Testmuster `_lokal(PARIS_TZ, D24, 20)` + `_trip(...)`/`_preset(...)` in `tests/tdd/test_next_briefing.py` (deterministisch, ohne Netz).

## Dependencies
- Upstream: `zoneinfo`/System-tzdata, `timezonefinder`, Trip-Etappen (`stages[].date`, `waypoints`), `report_config`.
- Downstream: Hub-Übersicht (Trip/Vergleich), Versand-Reiter, Startseiten-Kachel, Cockpit (`cockpitHelpers.ts`),
  Vergleichs-Mail (`compare_html.py:1622` nutzt `tz_abbr` ebenfalls).

## Existing Specs
- `docs/specs/modules/feat_1969_naechstes_briefing.md` — Vertrag des Termin-Formats (AC-5 Kürzel je Kandidatentag)
- `docs/specs/modules/rework_2845_hub_reiterleiste.md` — Non-Goal-Vermerk, Herkunft des Nebenbefunds

## Offene Hypothesen für /20-analyse
1. Etappe ohne Wegpunkte / Zonenwechsel zwischen Etappen → andere Zone, aber Kürzel bliebe zum Datum passend (eher nicht `CEST`).
2. Laufender Staging-Prozess mit anderem Code-Stand am 07.11. (Deploy-Historie von Staging prüfen).
3. Fehlablesung der Fresh-Eyes-Bildprüfung (Bild → Text); Beobachtung ohne Beleg.
4. Kombinationen, die die Tests nicht abdecken: nicht-strict-/überfällig-Zweig am Umstellungstag, `skip_next` (übernächster
   Termin über die Umstellung), Abend-Slot des Vorabends (`evening` am Tag vor der Etappe) über die Umstellung.
Vorgehen: Matrix-Test Trip × Vergleich × (morning/evening/skip_next/overdue) über 25.10.2026 und 28.03.2027 (Frühjahr)
deterministisch; dazu Staging-Live-Messung beider kinds am selben Tag über die echte API. Bleibt alles grün:
Regressionstest behalten, Issue begründet als nicht reproduzierbar schließen (kein Fix ohne roten Nachweis).

## Risks & Considerations
- Kein Fix auf Verdacht: Bug-Politik verlangt roten Nachweis aus Nutzersicht.
- Zeitumstellung im Frühjahr (28.03.2027) ist der nächste reale Prüfpunkt.
- Vergleichs-Mail nutzt dasselbe Feld — eine Änderung am Format bricht ggf. `email_spec_validator.py`.

## Analysis

### Type
Bug-Meldung → Ergebnis: **kein Zonen-Fehler**, sondern mehrdeutige Anzeige (Wochentag ohne Datum).

### Ursache (belegt, 2026-11-11)
- Die Fresh-Eyes-Paare der Abnahme #2837 S1 stammen aus `frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts`, Seed über
  `seedHub` → `seedRumpf` (`frontend/e2e/helpers.ts:680`): der Trip hat **eine einzige Etappe am 2027-08-01** (Sonntag),
  Korsika (42.0/9.0 → `Europe/Paris`), `morning_time 06:00`. Der Vergleich (Innsbruck/Stubai, daily 06:00) hat seinen
  Termin am nächsten Tag, Sonntag 08.11.2026.
- Nachrechnung mit genau diesem Seed (Scratchpad `probe2869.py`, `now = 2026-11-07 17:00 UTC`):
  `{'local_date': '2027-08-01', 'local_time': '06:00', 'tz': 'Europe/Paris', 'tz_abbr': 'CEST', 'slot': 'morning'}` —
  **korrekt** (August = Sommerzeit). „Derselbe Sonntag" war eine Fehlannahme der Bildprüfung: zwei verschiedene Sonntage,
  neun Monate auseinander.
- Warum die Fehlannahme entsteht: `formatNextBriefing` (`frontend/src/lib/components/shared/versand-tab/nextBriefingText.ts:89`)
  zeigt nur `Wochentag HH:00 (Kürzel)`. Liegt der Termin mehr als eine Woche entfernt, ist „So 06:00" mehrdeutig. Spec
  `feat_1969_naechstes_briefing.md` „Anzeige-Wortlaut" sagt „Wochentag/Datum aus `local_date`", Beispiele zeigen nur
  den Wochentag; Fernfall nicht geregelt.
- Hypothesen 1–4 der Kontextphase damit gegenstandslos (kein roter Nachweis eines Zonenfehlers möglich, Backend korrekt).

### Affected Files (falls Anzeige-Änderung freigegeben)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/versand-tab/nextBriefingText.ts` | MODIFY | Datum ergänzen, wenn Termin nicht in den nächsten 6 Tagen liegt (EIN Formatierer für Trip + Vergleich + Startseite + Hub) |
| `frontend/src/lib/components/shared/versand-tab/__tests__/naechstes_briefing_text.test.ts` | MODIFY | Fälle nah/fern, de/en, skip_next |
| i18n-Katalog `versand.naechstes.*` | MODIFY ggf. | Muster mit Datum (de „So 01.08. 06:00 (CEST)", en analog) |
| `tests/tdd/test_next_briefing.py` | MODIFY | Regressionstest: Seed-Trip 2027-08-01 Paris ⇒ `CEST`, Vergleich 08.11.2026 ⇒ `CET` |
| `docs/specs/modules/feat_1969_naechstes_briefing.md` | MODIFY | Anzeige-Wortlaut um Fernfall ergänzen |
| `frontend/src/routes/_home/cockpitHelpers.ts:193` | prüfen | eigener Kurzwortlaut `HH:00 (Kürzel)` ohne Wochentag |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte:46` | prüfen | Karte zeigt Slot-Stunden + Kürzel des nächsten Termins |

Nebenbefund (nur Testdaten): `f6VersandSsr.ts:88` hat `tz_abbr: 'CEST'` bei `2026-10-28T07:00+01:00` (müsste `CET`).

### Scope Assessment
- Files: 3–5 · Estimated LoC: +40/-5 · Risk Level: LOW (reine Anzeige, ein geteilter Formatierer, keine Backend-Änderung)
- Compare-Mail-Fuß (`compare_html.py:1622`) zeigt schon Datum + Uhrzeit + Kürzel → nicht betroffen.

### Technical Approach
Backend bleibt unverändert (Ableitung korrekt, ADR-0051 eingehalten). Empfehlung: im geteilten Formatierer das Datum
anhängen, sobald `local_date` mehr als 6 Tage nach dem heutigen Ortstag liegt („So 01.08. 06:00 (CEST)"); innerhalb der
Woche bleibt der kurze Wortlaut. Bezugstag „heute" muss aus dem Backend kommen (ADR-0051: keine Browser-Zone) —
entweder neues Feld (z. B. `days_ahead`) im `next-briefings`-Objekt oder Datum immer zeigen. Entscheidung PO nötig.

### Open Questions
- [ ] PO: Datum anzeigen? (immer / nur bei fernem Termin / gar nicht, Issue als Fehlalarm schließen)

### PO-Entscheidung (2026-11-11, AskUserQuestion)
**Datum immer anzeigen:** „Nächster Versand" überall als `Wochentag TT.MM. HH:00 (Kürzel)` (de „So 08.11. 06:00 (CET)",
en „Sun 8 Nov 06:00 (CET)"), für Trip und Vergleich gleich, über den einen geteilten Formatierer. Kein neues Backend-Feld
nötig (Datum steht schon in `local_date`). Backend-Ableitung bleibt unverändert; Regressionstest hält die korrekte Zone fest.
Offene Frage damit erledigt. Prüfen in der Spec: alle Konsumenten des Formatierers (Hub, Versand-Reiter, Startseite,
Status-Zeile) und der eigene Kurzwortlaut in `cockpitHelpers.ts:193`; skip_next-Zusatz ebenfalls mit Datum.

### Hinweis für /50-implement
- Changelog der Spec nennt im Beispiel für den 29.10. „CEST"; richtig ist CET (wie AC-4). Beim Nachziehen von feat_1969 und Spec-Changelog mitkorrigieren.
