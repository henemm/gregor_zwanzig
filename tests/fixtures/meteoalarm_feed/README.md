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

## `edr_snapshot_it.json` — Äquivalenz-Aufzeichnung, EDR-Seite

- **Herkunft:** `https://api.meteoalarm.org` (der bisherige, kontingentierte
  EDR-Weg), abgerufen über den echten Produktivcode
  (`MeteoAlarmSource.fetch()` je Tourpunkt) — kein nachbearbeitetes Ergebnis.
- **Aufgezeichnet:** 2026-08-01, **16:06:28 UTC**. Die Feed-Seite derselben
  Minute liegt als `feed_italy_equivalence.json` daneben; nur weil beide Seiten
  zeitgleich gezogen wurden, ist der Vergleich überhaupt aussagekräftig.
- **Umfang:** 8 Tourpunkte, zusammen 62 Warnungs-Einträge (Rohausgabe inklusive
  der von der Quelle mehrfach gelieferten identischen Einträge — bewusst nicht
  entdoppelt), ~14 KB.
- **Auswahl der 8 Punkte** (je eine andere EMMA-Zone, Nord/Mitte/Süd/Insel):

  | Punkt | Koordinate | DPC-Zone | EMMA | Warum |
  |---|---|---|---|---|
  | Trentino (Karnischer Höhenweg) | 46.7248, 12.2254 | Tren-A | IT002 | grenznaher Tourpunkt aus #1397 S4 |
  | Veneto (Karnischer Höhenweg) | 46.6508, 12.6476 | Vene-A1 | IT006 | grenznaher Tourpunkt aus #1397 S4 |
  | Friaul (Karnischer Höhenweg) | 46.6283, 12.8023 | Friu-B | IT020 | grenznaher Tourpunkt aus #1397 S4 |
  | Rom | 41.9028, 12.4964 | Lazi-D | IT012 | Referenzpunkt der übrigen Tests |
  | Mailand | 45.4642, 9.1900 | Lomb-09 | IT003 | Referenzpunkt der übrigen Tests |
  | Florenz | 43.7696, 11.2558 | Tosc-A3 | IT009 | Mittelitalien |
  | Neapel | 40.8518, 14.2681 | Camp-1 | IT016 | Süditalien |
  | Palermo | 38.1157, 13.3615 | Sici-C | IT018 | Insel, eigene Warnarten (Regen) |

  Die drei grenznahen Punkte sind Pflicht: genau sie waren der Nutzerbefund von
  #1397 S4. Die fünf übrigen decken das Land breit ab und bringen alle im
  Aufzeichnungszeitraum vorkommenden Warnarten mit
  (`thunderstorm`, `extreme_heat`, `rain`).
- **Unverändert:** Die Felder sind die normalisierten `OfficialAlert`-Werte der
  Quelle (`hazard`, `level`, `label`, `region_label`, `valid_from`, `valid_to`),
  1:1 wie geliefert. `region_label` ist **Pflichtfeld** — die Vergleichskennung
  `_alert_identitaet` zieht es heran; fehlt es beim Einlesen, meldet das Gate
  flächendeckend falsche Abweichungen.
- **Ergebnis des Gates** (`test_ac3_...` in
  `tests/tdd/test_meteoalarm_feed_italien.py`): **keine einzige fehlende
  Warnung** — der Feed ist für jeden der 8 Punkte eine echte Obermenge, an zwei
  Punkten (Mailand, Neapel) sogar mit einer zusätzlichen Warnung. Die
  frühere `xfail`-Markierung des Tests ist damit ersatzlos entfallen.

## `feed_italy_equivalence.json` — Äquivalenz-Aufzeichnung, Feed-Seite

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-italy`
  (öffentlicher, kontingentfreier CAP-Feed, kein Auth).
- **Aufgezeichnet:** 2026-08-01, **16:06:28 UTC** — dieselbe Minute wie
  `edr_snapshot_it.json`.
- **Auswahl:** 205 von 433 Einträgen des Vollabrufs. Kriterium ist rein
  mechanisch: **alle** Einträge der 8 von den Tourpunkten betroffenen
  EMMA-Zonen (IT002: 16, IT003: 34, IT006: 25, IT009: 26, IT012: 32, IT016: 27,
  IT018: 33, IT020: 12). Keine inhaltliche Vorauswahl — sonst wäre die
  Obermengen-Aussage wertlos.
- **Unverändert:** Jedes `warnings[]`-Element ist eine 1:1-Kopie aus dem
  Originalabruf (kein Feld umgeschrieben, keine Erfindung).
- **Größe:** ~600 KB (kompakt formatiert, ohne Einrückung).
- **Nur für das AC-3-Gate.** Alle übrigen Tests benutzen weiterhin
  `feed_italy_sample.json`; diese kuratierte 10-Einträge-Auswahl kann
  strukturell nie Obermenge eines vollständigen EDR-Index sein.

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

## `edr_snapshot_at.json` — Äquivalenz-Aufzeichnung, EDR-Seite

- **Herkunft:** `https://api.meteoalarm.org` (der bisherige, kontingentierte
  EDR-Weg), abgerufen über den echten Produktivcode
  (`MeteoAlarmSource.fetch()` je Tourpunkt) — kein nachbearbeitetes Ergebnis.
- **Aufgezeichnet:** 2026-08-01, **16:19:43 UTC**. Die Feed-Seite
  (`feed_austria_equivalence.json`) und die Zonenzuordnung
  (`zamg_snapshot_at.json`) derselben Minute liegen daneben; nur weil alle drei
  Seiten zeitgleich gezogen wurden, ist der Vergleich überhaupt aussagekräftig.
- **Lückenlos geblättert:** Anders als bei Italien (~3 Abrufe) ist der
  österreichische EDR-Index mehrseitig. Er wurde **vollständig über die Seiten
  1–38** geblättert — 3678 Roheinträge, nach Entduplizierung 1536. Ein
  Teilabruf hätte die Obermengen-Aussage wertlos gemacht: fehlende EDR-Einträge
  können im Vergleich nicht als Lücke auffallen.
- **Umfang:** 8 Tourpunkte, zusammen 118 Warnungs-Einträge (Rohausgabe
  inklusive der von der Quelle mehrfach gelieferten identischen Einträge —
  bewusst nicht entdoppelt), ~25 KB.
- **Auswahl der 8 Punkte:**

  | Punkt | Koordinate | `gemeindenr` | EMMA | Warnungen | Warum |
  |---|---|---|---|---|---|
  | Sillian (Karnischer Höhenweg) | 46.7597, 12.4177 | 70728 | AT707 | 20 | Tourpunkt des Nutzerbefunds #1397 S4 |
  | Lienz | 46.8296, 12.7698 | 70716 | AT707 | 20 | zweiter Punkt derselben Tour |
  | Zell am See | 47.3230, 12.7951 | 50628 | AT506 | 20 | Alpen/Salzburg, hohe Warndichte |
  | Wien | 48.2082, 16.3738 | 90101 | AT901 | 12 | Referenzpunkt der übrigen Tests |
  | Innsbruck | 47.2692, 11.4041 | 70101 | AT701 | 18 | Referenzpunkt der übrigen Tests |
  | Graz | 47.0707, 15.4395 | 60101 | AT601 | 10 | Steiermark |
  | Eisenstadt | 47.8457, 16.5237 | 10101 | AT101 | 8 | Burgenland, Osten |
  | Sankt Pölten | 48.2047, 15.6256 | 30201 | AT302 | 10 | Niederösterreich, einzige `wind_gust`-Warnung |

  Die beiden Punkte am Karnischen Höhenweg sind Pflicht: genau sie waren der
  Nutzerbefund von #1397 S4. Die sechs übrigen decken das Land breit ab und
  bringen alle im Aufzeichnungszeitraum vorkommenden Warnarten mit
  (`thunderstorm`, `extreme_heat`, `wind_gust`).
- **Ehrlich zur Aussagekraft — es sind 7 unabhängige Zonen, nicht 8:** Sillian
  (70728) und Lienz (70716) fallen beide auf die EMMA-Zone **AT707** und
  liefern deshalb *identische* Warnungsmengen mit `region_label: "Lienz"`.
  Der Vergleich läuft zwar über 8 Punkte, prüft aber 7 unabhängige Zonen
  (AT101, AT302, AT506, AT601, AT701, AT707, AT901). „8 Punkte“ darf nicht als
  „8 unabhängige Prüfungen“ gelesen werden.
- **Unverändert:** Die Felder sind die normalisierten `OfficialAlert`-Werte der
  Quelle (`hazard`, `level`, `label`, `region_label`, `valid_from`, `valid_to`),
  1:1 wie geliefert. `region_label` ist **Pflichtfeld** — die Vergleichskennung
  `_alert_identitaet` zieht es heran; fehlt es beim Einlesen, meldet das Gate
  flächendeckend falsche Abweichungen (F004-Lehre aus S1).
- **24 der 118 Warnungen waren zum Aufnahmezeitpunkt bereits abgelaufen.**
  Deshalb vergleicht das Gate auf BEIDEN Seiten die rohe Quellenausgabe
  (`MeteoAlarmFeedSource.fetch()` statt
  `get_official_alerts_with_status(now=…)`): eine einseitige `now`-Filterung
  der Feed-Seite hätte genau diese 24 als vermeintliche Lücken gemeldet —
  Fehlalarme, die allein aus der ungleichen Behandlung stammten. Der
  Rohvergleich ist damit zugleich die **strengere** Variante: er verlangt vom
  Feed auch die abgelaufenen Warnungen. Anders als in Italien, wo die
  EDR-Aufzeichnung nichts Abgelaufenes trug, ist das hier gemessen und wird im
  Test als Aufbauprüfung mitgeführt.
- **Ergebnis des Gates** (`test_ac5_...` in
  `tests/tdd/test_meteoalarm_feed_oesterreich.py`): **keine einzige fehlende
  Warnung** — der Feed ist für jeden der 8 Punkte eine echte Obermenge und
  reicht zeitlich sogar weiter zurück als der EDR-Index. Die frühere
  `xfail`-Markierung des Tests ist damit ersatzlos entfallen.

## `feed_austria_equivalence.json` — Äquivalenz-Aufzeichnung, Feed-Seite

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-austria`
  (öffentlicher, kontingentfreier CAP-Feed, kein Auth).
- **Aufgezeichnet:** 2026-08-01, **16:19:43 UTC** — dieselbe Minute wie
  `edr_snapshot_at.json` und `zamg_snapshot_at.json`.
- **Auswahl:** 90 von 1358 Einträgen des Vollabrufs. Kriterium ist rein
  mechanisch: **alle** Einträge der 7 von den Tourpunkten betroffenen
  EMMA-Zonen (AT101: 9, AT302: 9, AT506: 16, AT601: 10, AT701: 16, AT707: 20,
  AT901: 10). Keine inhaltliche Vorauswahl — sonst wäre die Obermengen-Aussage
  wertlos.
- **Unverändert:** Jedes `warnings[]`-Element ist eine 1:1-Kopie aus dem
  Originalabruf (kein Feld umgeschrieben, keine Erfindung).
- **Größe:** ~175 KB (kompakt formatiert, ohne Einrückung).
- **Nur für das AC-5-Gate.** Alle übrigen Tests benutzen weiterhin
  `feed_austria_sample.json`; diese kuratierte 6-Einträge-Auswahl kann
  strukturell nie Obermenge eines vollständigen EDR-Index sein — gemessen
  2026-08-01 meldete das Gate mit ihr an allen 8 Tourpunkten Abweichungen.

## `zamg_snapshot_at.json` — Äquivalenz-Aufzeichnung, Zonenzuordnung (Adversary-Fund F2, S3 Fix-Loop)

- **Herkunft:** `https://warnungen.zamg.at/wsapp/api/getWarningsForCoords`, die
  vollständige, unveränderte Antwort je Tourpunkt.
- **Aufgezeichnet:** 2026-08-01, **16:19:43 UTC** — dieselbe Minute wie die
  beiden anderen Seiten. Das ist zwingend: Österreichs Punkt→Zone-Auflösung
  läuft über ZAMG, eine später gezogene Zuordnung vergliche gegen einen anderen
  Zustand als den aufgezeichneten.
- **Umfang:** 8 Einträge (dieselben Koordinaten wie `edr_snapshot_at.json`),
  ~84 KB. Alle acht Punkte sind Erfolgsfälle (`response`), kein `status`-Eintrag
  — die aufgezeichneten `gemeindenr`-Werte stehen in der Tabelle oben.
- **Warum die Datei überhaupt existiert (F2):** ohne sie dürfte `test_ac5_…`
  nicht laufen, ohne entweder gegen den *aktuellen* ZAMG-Zustand zu vergleichen
  (statt gegen den zum Aufnahmezeitpunkt gültigen) oder — schlimmer — echt
  gegen `warnungen.zamg.at` zu greifen (verletzt die Kern-Testschicht-Regel
  „kein Netz“; eine Störung oder Ratenbremse dort erzeugte irreführende
  Fehlschläge). Der Test speist damit einen lokalen `_ZamgServer` und prüft
  zusätzlich, dass die Aufzeichnung **jeden** Tourpunkt abdeckt — ein fehlender
  Punkt liefe sonst still in den 404-Zweig und gälte fälschlich als „nicht
  zuständig“.

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
