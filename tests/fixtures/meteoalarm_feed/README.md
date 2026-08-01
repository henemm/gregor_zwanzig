# Fixtures: MeteoAlarm-Feed Italien (Issue #1445, Scheibe S1)

## `feed_italy_sample.json`

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-italy` (öffentlicher,
  kontingentfreier CAP-Feed, kein Auth).
- **Aufgezeichnet:** 2026-07-31 (Vollabruf 1,4 MB / 457 Einträge, davon 195 zum
  Aufzeichnungszeitpunkt gültig).
- **Auswahl:** 10 reale, unveränderte Einträge (`warnings[].alert`) aus dem
  Vollabruf, ausgewählt für Testabdeckung:
  - Regionen: Lazio (`IT012`), Valle d'Aosta (`IT004`), Piemonte (`IT005`),
    Lombardia (`IT003`), Trentino Alto Adige (`IT002`), Sicilia (`IT018`),
    Basilicata (`IT017`).
  - `awareness_type`: Thunderstorm (3), Wind (1), Rain (10), High-temperature (5)
    — die vier im Vollabruf vorkommenden Warnarten (keine Schnee-/Hochwasser-/
    Waldbrand-Warnungen im Sommer-Zeitraum der Aufzeichnung).
  - `awareness_level`: grün/1 (gefiltert, `level < 2`), gelb/2, orange/3, rot/4.
  - Gültigkeitsstatus bezogen auf Test-Referenzzeitpunkt `2026-08-01T12:00:00Z`:
    mehrere bereits abgelaufene Einträge, zwei aktuell gültige (Lazio
    Extreme-Heat orange, Lombardia Extreme-Heat orange), ein noch nicht
    begonnener (Basilicata Extreme-Heat rot, Onset 2026-08-02).
- **Unverändert:** Jedes ausgewählte `warnings[]`-Element ist eine 1:1-Kopie aus
  dem Originalabruf (kein Feld umgeschrieben, keine Erfindung).
- **Größe:** ~45 KB (Ziel < 200 KB deutlich unterschritten).

## `edr_snapshot_it.json` — NOCH NICHT AUFGEZEICHNET

Für den Äquivalenznachweis (AC-3, Spec Implementation Details Punkt 3 /
Randbedingung 1) fehlt noch ein zur selben Minute wie ein Feed-Abruf
aufgezeichneter EDR-Ausschnitt (`api.meteoalarm.org`) für dieselbe Liste realer
Tourpunkte. Der kontingentierte Zugang war zum Zeitpunkt dieser RED-Phase
gesperrt (Tageskontingent, Reset 2026-08-01T15:45 UTC laut
`docs/context/fix-1397-wiederanlauf-ausbruch.md`). Der zugehörige Test
(`test_ac3_...`) in `tests/tdd/test_meteoalarm_feed_italien.py` schlägt deshalb
bewusst fehl (nicht übersprungen) bis diese Datei nachgezogen ist.

## Regions-Präfix → EMMA-ID (verifiziert)

Aus dem echten Feed-Datensatz extrahiert (`area[].geocode[].valueName ==
"EMMA_ID"`, `area[].areaDesc`) und gegen alle 187 `zona`-Codes in
`src/services/official_alerts/data/dpc_zones.json` abgeglichen — jeder Code
trägt als ersten Bestandteil (vor dem `-`, fest 4 Zeichen) genau einen der
folgenden Regionspräfixe:

| Präfix | Region | EMMA-ID |
|---|---|---|
| Cala | Calabria | IT001 |
| Tren | Trentino Alto Adige | IT002 |
| Lomb | Lombardia | IT003 |
| VDAo | Valle d'Aosta | IT004 |
| Piem | Piemonte | IT005 |
| Vene | Veneto | IT006 |
| Ligu | Liguria | IT007 |
| Emil | Emilia e Romagna | IT008 |
| Tosc | Toscana | IT009 |
| Umbr | Umbria | IT010 |
| Marc | Marche | IT011 |
| Lazi | Lazio | IT012 |
| Abru | Abruzzo | IT013 |
| Moli | Molise | IT014 |
| Pugl | Puglia | IT015 |
| Camp | Campania | IT016 |
| Basi | Basilicata | IT017 |
| Sici | Sicilia | IT018 |
| Sard | Sardegna | IT019 |
| Friu | Friuli Venezia Giulia | IT020 |

Deckt sich mit den drei in der Spec vorab genannten, live geprüften Paaren
(`VDAo→IT004`, `Lazi→IT012`, `Ligu→IT007`).

---

# Fixtures: MeteoAlarm-Feed Österreich (Issue #1445, Scheibe S3)

## `feed_austria_sample.json`

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-austria` (öffentlicher,
  kontingentfreier CAP-Feed, kein Auth, deutschsprachig).
- **Aufgezeichnet:** 2026-07-31, 20:21 UTC (Vollabruf 2,4 MB / 1220 Einträge über
  116 EMMA-Zonen).
- **Auswahl:** 6 reale, unveränderte Einträge (`warnings[].alert`) aus dem
  Vollabruf, ausgewählt für Testabdeckung:
  - Zonen: Lienz (`AT707`, **zweimal** — Karnischer Höhenweg/Sillian, PFLICHT
    laut Spec), Tamsweg (`AT505`), Wien Innere Stadt (`AT901`), Wiener
    Neustadt (Stadt) (`AT304`), Graz (Stadt) (`AT601`).
  - `awareness_type`: Gewitter (3), Hitze (5), Wind (1) — die drei im
    Vollabruf vorkommenden Warnarten (keine Schnee-/Hochwasser-/
    Waldbrand-Warnungen im Sommer-Zeitraum der Aufzeichnung; identisch mit
    der Beobachtung im Kontext-Dokument `docs/context/fix-1397-wiederanlauf-ausbruch.md`).
  - `awareness_level`: nur gelb/2 und orange/3 kommen im Vollabruf vor (kein
    grün/1, kein rot/4).
  - Gültigkeitsstatus bezogen auf Test-Referenzzeitpunkt `2026-08-01T12:00:00Z`:
    drei bereits abgelaufene Einträge (Lienz Gewitter, Tamsweg Gewitter,
    Wiener Neustadt Wind), drei aktuell gültige (Lienz Hitze gelb, Wien Hitze
    orange, Graz Hitze orange).
  - `msgType`: sowohl `Alert` (4×) als auch `Update` (2×) vertreten (kein
    `Cancel` im Vollabruf — Cancel-Verhalten bleibt unbeobachtet, wie schon in
    der S1-Spec unter Known Limitations vermerkt).
  - Zone `AT101` (Eisenstadt) und `AT202` (Villach) sind BEWUSST NICHT in der
    Auswahl enthalten — sie dienen in den Tests als "erfolgreich aufgelöste,
    aber warnungsfreie Zone" (AC-3).
- **Unverändert:** Jedes ausgewählte `warnings[]`-Element ist eine 1:1-Kopie
  aus dem Originalabruf (kein Feld umgeschrieben, keine Erfindung).
- **Größe:** ~20 KB (Ziel < 200 KB deutlich unterschritten).

## `edr_snapshot_at.json` — NOCH NICHT AUFGEZEICHNET

Für den Äquivalenznachweis (AC-5) fehlt noch ein zur selben Minute wie ein
Feed-Abruf aufgezeichneter EDR-Ausschnitt (`api.meteoalarm.org`) für dieselbe
Liste realer österreichischer Tourpunkte. Anders als bei Italien (~3 Abrufe)
kostet die EDR-Vergleichsaufnahme für Österreich **17–21 Abrufe** (mehrseitige
Blätterei) — der kontingentierte Zugang war zum Zeitpunkt dieser RED-Phase
gesperrt (Tageskontingent, Reset laut
`docs/context/fix-1397-wiederanlauf-ausbruch.md`). Der zugehörige Test
(`test_ac5_...`) in `tests/tdd/test_meteoalarm_feed_oesterreich.py` schlägt
deshalb bewusst fehl (nicht übersprungen) bis diese Datei nachgezogen ist.

## `zamg_snapshot_at.json` — NOCH NICHT AUFGEZEICHNET (Adversary-Fund F2, S3 Fix-Loop)

Dritte, zwingend zur SELBEN Minute wie `edr_snapshot_at.json` zu ziehende Aufzeichnung
für AC-5: die echte ZAMG-Antwort (`warnungen.zamg.at`) je Tourpunkt der Vergleichsliste.
Ohne sie dürfte `test_ac5_...` nicht laufen, ohne entweder gegen den *aktuellen*
ZAMG-Zustand zu vergleichen (statt gegen den zum Aufnahmezeitpunkt gültigen) oder — schlimmer —
echt gegen `warnungen.zamg.at` zu greifen (verletzt die Kern-Testschicht-Regel „kein Netz“,
Störung/Ratenbremse dort erzeugte irreführende Fehlschläge). Der Test prüft deshalb explizit
auf diese Datei und bleibt rot mit einer Meldung, die genau benennt, welche der beiden
Aufzeichnungen (EDR- oder ZAMG-Snapshot) fehlt.

**Format:** eine JSON-Liste, ein Eintrag je Tourpunkt (`lat`, `lon` identisch zu den
Koordinaten in `edr_snapshot_at.json`), plus GENAU eines von:
- `"response"`: die vollständige, unveränderte ZAMG-JSON-Antwort (Erfolgsfall, Form wie
  `_zamg_body()` in den Tests — `properties.location.properties.gemeindenr` als Ganzzahl).
- `"status"`: der HTTP-Statuscode als Ganzzahl (z. B. `404` für „nicht zuständig“, kein
  österreichischer Tourpunkt).

```json
[
  {"lat": 46.7597, "lon": 12.4177, "response": {"properties": {"location": {"properties": {"gemeindenr": 70728, "name": "Sillian"}}}}}
]
```

## ZAMG-Antwortform (`gemeindenr`) — live verifiziert 2026-08-01

`https://warnungen.zamg.at/wsapp/api/getWarningsForCoords` liefert unter
`properties.location.properties` das Feld `gemeindenr` als **Ganzzahl**
(nicht als String) neben `name`/`urlname`. Live gemessen:

| Ort | Koordinate | `gemeindenr` | EMMA-Zone (erste 3 Ziffern) |
|---|---|---|---|
| Innsbruck | 47.2692, 11.4041 | `70101` | AT701 |
| Sillian (Karnischer Höhenweg, IT-Grenze) | 46.7597, 12.4177 | `70728` | AT707 |
| Graubünden-Grenzgebiet (real ausserhalb AT) | 46.85, 9.53 | — (HTTP 404) | — |

Aus dem Kontext-Dokument zusätzlich gemessen: Villach `20201`→AT202, Tamsweg
`50510`→AT505, Wien `90101`→AT901. Die Spec-Formulierung „EMMA-Zone =
`"AT" + gemeindenr[:3]`" setzt eine String-Slicing-Operation voraus — da
`gemeindenr` real eine Ganzzahl ist, muss die Implementierung `str(gemeindenr)`
bilden, bevor sie die ersten drei Zeichen nimmt, sonst wirft `gemeindenr[:3]`
einen `TypeError`.
