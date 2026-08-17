---
entity_id: fix_1945_nowcast_horizon
type: bugfix
created: 2026-08-17
updated: 2026-08-17
status: approved
---

## Approval

- [x] Approved

## Purpose

Issue #1945 ("Alarm unklar"): Der Radar-Nowcast-Alarm zeigte bei zwei unabhängigen Alarmen für
denselben Trip (KHW 403, 15:52 und 17:07 Uhr, 75 Min auseinander) beide Male denselben
Countdown-Wert. Root Cause: `_NOWCAST_HORIZON_MIN` in `src/services/radar_service.py` deckelt den
Suchhorizont künstlich auf 60 Minuten, obwohl die GeoSphere-INCA-API selbst live nachgewiesen bis
zu 180 Minuten (3 Stunden) Vorschau im 15-Minuten-Raster liefert (Endpunkt
`nowcast-v1-15min-1km`). Weil der Alarm nur den ERSTEN nassen Frame innerhalb des 60-Min-Fensters
sucht, löst er praktisch immer erst aus, wenn der NÄCHSTE 15-Minuten-Rasterpunkt nass wird — der
Scheduler prüft alle 15 Minuten (`7,22,37,52 * * * *`), das ist strukturell immer ~8 Minuten vor
dem nächsten Rasterpunkt. Ergebnis: `onset_minutes` ist fast immer ≈8, unabhängig vom realen
Wettergeschehen, und der Nutzer bekommt praktisch nie mehr als 8-23 Minuten Vorlauf, obwohl die
Datenquelle mehr hergäbe.

## Source

Issue #1945, PO-Bericht mit zwei realen Produktions-Alarmen (bestätigt über
`/var/lib/gregor/users/henning/alert_log.json`, `sent_at` 2026-08-17T13:52:02Z und
15:07:02Z UTC, exakt 75 Min = 5×15-Min-Raster auseinander). Root Cause live gegen den echten
GeoSphere-INCA-Endpunkt verifiziert (`curl` gegen `dataset.api.hub.geosphere.at`, Antwort liefert
12 Zeitstempel im 15-Min-Raster über 3 Stunden voraus).

## Dependencies

| Was | Wovon abhängig |
|-----|-----------------|
| `_derive_result()` (radar_service.py) | `_NOWCAST_HORIZON_MIN`-Konstante |
| `check_radar_alerts()` (trip_alert.py) | Horizont-Guard nutzt denselben Wert über den Alias `NOWCAST_HORIZON_MIN` |
| Zwei Bestandstests | Harte `assert NOWCAST_HORIZON_MIN == 60`-Prüfung, muss mit angepasst werden |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/radar_service.py` | MODIFY | `_NOWCAST_HORIZON_MIN` von 60 auf 180 |
| `tests/tdd/test_nowcast_horizon_180min.py` | CREATE | Neuer Regressionstest (AC-1/2/3) |
| `tests/tdd/test_radar_alert_follows_ortstag.py` | MODIFY | Assert + Fern-Fall-Offset an neuen Horizont anpassen |
| `tests/tdd/test_starkregen_kurzfristhinweis.py` | MODIFY | Assert + Fern-Fall-Offset an neuen Horizont anpassen |

### Estimated Changes

~1 Zeile Produktivcode, ~3 Testdateien (1 neu, 2 angepasst) — weit unter dem 250-LoC-Standardbudget.

### Explizit AUSGESCHLOSSEN (gehört zu anderen, bereits vergebenen Tickets)

- **Rendering/Format der Onset-Nachricht** (SMS-Token `TH!8`/`R!8`, Umstieg auf absolute Uhrzeit,
  Segment-Kopf, Einheit) — gehört zu **#1948** (PO-Entscheid: einheitliches Alarm-Format über alle
  drei Zweige). `src/output/renderers/alert/render.py` NICHT anfassen.
- **Frühwarnung aus der Stundenvorhersage** (weiter im Voraus, gröber) — eigenes Ticket **#1493**.
- **Amtliche Warnungen** (`official_alerts.py`) — **#1929**, andere Session, NICHT anfassen.

## Implementation Details

`src/services/radar_service.py`, Zeile ~62: `_NOWCAST_HORIZON_MIN = 60` → `= 180`. Der öffentliche
Alias `NOWCAST_HORIZON_MIN` (Zeile ~65) übernimmt den Wert automatisch. Einzige funktionale
Verwendung: `_derive_result()`, Zeile ~522, `horizon = now + timedelta(minutes=_NOWCAST_HORIZON_MIN)`.

Zwei Bestandstests haben `assert NOWCAST_HORIZON_MIN == 60` als Testvoraussetzung UND nutzen einen
"Fern"-Fall mit 90 Minuten Abstand (bei altem Horizont=60 außerhalb, bei neuem Horizont=180
plötzlich innerhalb) — reine Zahlenänderung im Assert würde die Testsemantik kippen. Der Fern-Fall
muss auf einen Offset > 180 Min angehoben werden (z.B. 200 Min), damit "außerhalb Horizont"
weiterhin geprüft wird:
- `tests/tdd/test_radar_alert_follows_ortstag.py::test_ac4_horizont_guard_fern_kein_abruf_nah_ein_abruf`
- `tests/tdd/test_starkregen_kurzfristhinweis.py::test_ac2_zeitfenster_guard_kein_fetch_ausserhalb_horizon`

## Expected Behavior

Ein Nowcast-Alarm kann ab sofort auch dann auslösen, wenn der erste nasse Rasterpunkt bis zu 180
Minuten (statt bisher 60) in der Zukunft liegt — dadurch verteilen sich die gezeigten
Countdown-Werte über mehr Rasterpunkte (23/38/53/68/83/98/113/128/143/158/173 Min), und Nutzer
bekommen im typischen Fall deutlich mehr Vorlauf vor einem Wetterereignis.

## Acceptance Criteria

- **AC-1:** Given `_NOWCAST_HORIZON_MIN` in `src/services/radar_service.py` / When das Modul
  importiert wird / Then ist der Wert `180`, nicht mehr `60`.
  - Test: `assert radar_service.NOWCAST_HORIZON_MIN == 180` direkt gegen das importierte Modul.

- **AC-2:** Given eine Frame-Liste mit einem nassen Frame bei `now + 90 Minuten` (precip_mm_h=2.0)
  und ausschließlich trockenen Frames davor / When `RadarNowcastService()._derive_result(frames,
  "test-source", now=now)` aufgerufen wird / Then ist `result.onset_minutes == 90` statt `None`.
  - Test: `tests/tdd/test_nowcast_horizon_180min.py`, echte `RadarFrame`-Objekte (kein Mock),
    reproduziert das Nutzersymptom (Alarm bleibt aus, obwohl Regen in 90 Minuten kommt) — MUSS vor
    der Konstanten-Änderung rot sein (`onset_minutes is None`) und danach grün.

- **AC-3:** Given dieselbe Frame-Liste wie in AC-2, zusätzlich ein nasser Frame bei
  `now + 200 Minuten` / When `_derive_result()` aufgerufen wird / Then bleibt der 200-Minuten-Frame
  außerhalb des Fensters unberücksichtigt und `onset_minutes` referenziert weiterhin den
  90-Minuten-Frame — der Horizont ist auf 180 begrenzt, nicht unbegrenzt geöffnet.
  - Test: Assert im selben Testfall wie AC-2, prüft `onset_minutes == 90` und NICHT `200`.

## Known Limitations

- Die absolute Genauigkeit bleibt weiterhin auf das 15-Minuten-Datenraster begrenzt (physikalische
  Grenze der Quelle, kein Implementierungsfehler) — mit größerem Horizont verteilen sich die Werte
  nur über mehr Rasterpunkte, werden aber nicht "krummer".
- Zwei Bestandstests (`test_radar_alert_follows_ortstag.py`,
  `test_starkregen_kurzfristhinweis.py`) müssen mit angepasst werden, sonst werden sie durch diese
  Änderung selbst rot (siehe Implementation Details).

## Architektur-Entscheidung (ADR)

Keine — reine Konstanten-Anpassung innerhalb bestehender Architektur, kein neues
Architektur-Muster, keine Breaking Changes an Datenmodell/Persistenz/Kanälen.

## Changelog

- 2026-08-17: Spec erstellt und PO-freigegeben (AC-1/2/3). Nach Verlust des ursprünglichen
  Worktrees (fremder Cleanup-Lauf) inhaltsgleich rekonstruiert im neuen Worktree
  `replicated-cuddling-sphinx`.
