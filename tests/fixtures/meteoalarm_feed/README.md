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
  EDR-Weg), abgerufen über den damaligen Produktivcode (die EDR-Klasse in
  `meteoalarm.py`, je Trip-Punkt) — kein nachbearbeitetes Ergebnis.
- **Eingefroren (#2266):** Der Snapshot ist eingefroren und wird nie neu
  aufgezeichnet; ein Aufzeichnungsskript existiert nicht im Repo (der Abruf war
  ein einmaliger Ad-hoc-Lauf, und die EDR-Klasse ist mit #2266 zurückgebaut).
  Die Datei bleibt unverändert als Referenz des Kern-Tests
  `tests/tdd/test_meteoalarm_feed_aequivalenz_snapshots.py`.
- **Aufgezeichnet:** 2026-08-01, **16:06:28 UTC**. Die Feed-Seite derselben
  Minute liegt als `feed_italy_equivalence.json` daneben; nur weil beide Seiten
  zeitgleich gezogen wurden, ist der Vergleich überhaupt aussagekräftig.
- **Umfang:** 8 Trip-Punkte, zusammen 62 Warnungs-Einträge (Rohausgabe inklusive
  der von der Quelle mehrfach gelieferten identischen Einträge — bewusst nicht
  entdoppelt), ~14 KB.
- **Auswahl der 8 Punkte** (je eine andere EMMA-Zone, Nord/Mitte/Süd/Insel):

  | Punkt | Koordinate | DPC-Zone | EMMA | Warum |
  |---|---|---|---|---|
  | Trentino (Karnischer Höhenweg) | 46.7248, 12.2254 | Tren-A | IT002 | grenznaher Trip-Punkt aus #1397 S4 |
  | Veneto (Karnischer Höhenweg) | 46.6508, 12.6476 | Vene-A1 | IT006 | grenznaher Trip-Punkt aus #1397 S4 |
  | Friaul (Karnischer Höhenweg) | 46.6283, 12.8023 | Friu-B | IT020 | grenznaher Trip-Punkt aus #1397 S4 |
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
  mechanisch: **alle** Einträge der 8 von den Trip-Punkten betroffenen
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
  EDR-Weg), abgerufen über den damaligen Produktivcode (die EDR-Klasse in
  `meteoalarm.py`, je Trip-Punkt) — kein nachbearbeitetes Ergebnis.
- **Eingefroren (#2266):** Der Snapshot ist eingefroren und wird nie neu
  aufgezeichnet; ein Aufzeichnungsskript existiert nicht im Repo (der Abruf war
  ein einmaliger Ad-hoc-Lauf, und die EDR-Klasse ist mit #2266 zurückgebaut).
  Die Datei bleibt unverändert als Referenz des Kern-Tests
  `tests/tdd/test_meteoalarm_feed_aequivalenz_snapshots.py`.
- **Aufgezeichnet:** 2026-08-01, **16:19:43 UTC**. Die Feed-Seite
  (`feed_austria_equivalence.json`) und die Zonenzuordnung
  (`zamg_snapshot_at.json`) derselben Minute liegen daneben; nur weil alle drei
  Seiten zeitgleich gezogen wurden, ist der Vergleich überhaupt aussagekräftig.
- **Lückenlos geblättert:** Anders als bei Italien (~3 Abrufe) ist der
  österreichische EDR-Index mehrseitig. Er wurde **vollständig über die Seiten
  1–38** geblättert — 3678 Roheinträge, nach Entduplizierung 1536. Ein
  Teilabruf hätte die Obermengen-Aussage wertlos gemacht: fehlende EDR-Einträge
  können im Vergleich nicht als Lücke auffallen.
- **Umfang:** 8 Trip-Punkte, zusammen 118 Warnungs-Einträge (Rohausgabe
  inklusive der von der Quelle mehrfach gelieferten identischen Einträge —
  bewusst nicht entdoppelt), ~25 KB.
- **Auswahl der 8 Punkte:**

  | Punkt | Koordinate | `gemeindenr` | EMMA | Warnungen | Warum |
  |---|---|---|---|---|---|
  | Sillian (Karnischer Höhenweg) | 46.7597, 12.4177 | 70728 | AT707 | 20 | Trip-Punkt des Nutzerbefunds #1397 S4 |
  | Lienz | 46.8296, 12.7698 | 70716 | AT707 | 20 | zweiter Punkt desselben Trips |
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
  mechanisch: **alle** Einträge der 7 von den Trip-Punkten betroffenen
  EMMA-Zonen (AT101: 9, AT302: 9, AT506: 16, AT601: 10, AT701: 16, AT707: 20,
  AT901: 10). Keine inhaltliche Vorauswahl — sonst wäre die Obermengen-Aussage
  wertlos.
- **Unverändert:** Jedes `warnings[]`-Element ist eine 1:1-Kopie aus dem
  Originalabruf (kein Feld umgeschrieben, keine Erfindung).
- **Größe:** ~175 KB (kompakt formatiert, ohne Einrückung).
- **Nur für das AC-5-Gate.** Alle übrigen Tests benutzen weiterhin
  `feed_austria_sample.json`; diese kuratierte 6-Einträge-Auswahl kann
  strukturell nie Obermenge eines vollständigen EDR-Index sein — gemessen
  2026-08-01 meldete das Gate mit ihr an allen 8 Trip-Punkten Abweichungen.

## `zamg_snapshot_at.json` — Äquivalenz-Aufzeichnung, Zonenzuordnung (Adversary-Fund F2, S3 Fix-Loop)

- **Herkunft:** `https://warnungen.zamg.at/wsapp/api/getWarningsForCoords`, die
  vollständige, unveränderte Antwort je Trip-Punkt.
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
  zusätzlich, dass die Aufzeichnung **jeden** Trip-Punkt abdeckt — ein fehlender
  Punkt liefe sonst still in den 404-Zweig und gälte fälschlich als „nicht
  zuständig“.

**Format:** eine JSON-Liste, ein Eintrag je Trip-Punkt (`lat`, `lon` identisch zu den
Koordinaten in `edr_snapshot_at.json`), plus GENAU eines von:
- `"response"`: die vollständige, unveränderte ZAMG-JSON-Antwort (Erfolgsfall, Form wie
  `_zamg_body()` in den Tests — `properties.location.properties.gemeindenr` als Ganzzahl).
- `"status"`: der HTTP-Statuscode als Ganzzahl (z. B. `404` für „nicht zuständig“, kein
  österreichischer Trip-Punkt).

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

---

# Fixtures: MeteoAlarm-Feed Deutschland (Issue #1681)

## `feed_germany_sample.json`

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-germany`
  (öffentlicher, kontingentfreier CAP-Feed, kein Auth; Inhalt: amtliche
  DWD-Warnungen).
- **Aufgezeichnet:** 2026-09-19, ca. 16:50 MESZ (Vollabruf ~5 MB / 254
  Einträge, davon 39 mit `responseType: ["AllClear"]`, 215 mit
  `["Prepare"]`). Der Feed führt bereits abgelaufene Einträge der Vortage
  weiter — die Stichprobe nutzt das: die Bayern-Einträge stammen vom
  Unwettertag 16.09.2026 und sind zum Test-Referenzzeitpunkt
  `2026-09-16T15:40:00Z` (17:40 MESZ) gültig.
- **Auswahl:** 7 reale, unveränderte `warnings[]`-Elemente (Index im
  Vollabruf in Klammern), ausgewählt für Testabdeckung:

  | # | Index | Art / Stufe | `responseType` | Gültig (MESZ) | Warnzellen (Auszug) | Zweck |
  |---|---|---|---|---|---|---|
  | 1 | 108 | STARKREGEN, orange (3; Rain) | Prepare | 16.09. 14:00–23:00 | Garmisch-Partenkirchen `109180000`, Weilheim-Schongau, Ostallgäu, … | orange DE-Warnung für die Kanal-Parität (AC-10) |
  | 2 | 141 | STARKES GEWITTER, orange (3; Thunderstorm) | Prepare | 16.09. 14:00–15:00 | Landsberg am Lech `109181000` | orange Gewitter DE vs. orange Gewitter IT (AC-10) |
  | 3 | 211 | GEWITTER, gelb (2; Thunderstorm) | Prepare | 16.09. 17:25–18:30 | Garmisch-Partenkirchen `109180000`, Landsberg, Bad Tölz, Kaufbeuren, … | aktive gelbe Warnung Bayerische Alpen (AC-1, AC-11) |
  | 4 | 216 | STARKES GEWITTER, orange (3; Thunderstorm) | **AllClear** | 16.09. 16:57–17:47 | Starnberg `109188000`, München `909184999`, Weilheim, … | Aufhebung mit zum Testzeitpunkt noch zukünftigem `expires` (AC-5) |
  | 5 | 244 | WINDBÖEN, gelb (1; Wind) | Prepare | 19.09. 00:00–20.09. 00:00 | Kreis Cuxhaven – Küste `903352002`, Borkum, … | küstennahe **Kreis**-Zelle (Präfix `9…`) als Positivkontrolle neben der Seezelle (AC-7) |
  | 6 | 245 | NEBEL, gelb (4; Fog) | Prepare | 19.09. 05:10–08:00 | Altötting, Mühldorf, `909187999` (Kreis und Stadt Rosenheim) | `9…`-Sammelzelle; Grundlage der konstruierten Drift-Kopie im Drift-Wächter (AC-9) |
  | 7 | 246 | BÖEN, gelb (7; coastalevent) | Prepare | ab 19.09. 05:31, **ohne `expires`** | `501000004` (Elbe von Hamburg bis Cuxhaven) | Küsten-/Seezelle ohne Geometrie (AC-7) |

- **Prüfpunkte (Ray-Cast gegen DWD-Layer `dwd:Warngebiete_Kreise`, 402 Flächen,
  abgerufen 2026-09-19):** Garmisch-Partenkirchen 47.4921/11.0958 →
  `109180000`; Lenggries 47.6800/11.5760 → `109173000` (Bad Tölz-Wolfratshausen,
  nördlich der DPC-Bbox-Grenze 47,5 N); Starnberg 47.9990/11.3400 → `109188000` (einziger Eintrag der
  Stichprobe für diese Zelle ist die Aufhebung #4); Landsberg 48.0480/10.8830
  → `109181000`; Peine 52.32/10.23 → `103157000` (kein Eintrag in der
  Stichprobe ⇒ deutscher Punkt ohne Warnung); Cuxhaven 53.8615/8.6944 →
  `903352002`; Freilassing 47.8406/12.9767 → `109172000`; Weil am Rhein
  47.5947/7.6206 → `108336000`. Innsbruck, Salzburg, Basel → kein Treffer.
- **Drift-Befund der Aufzeichnung:** 290 distinkte `WARNCELLID`s im Vollabruf;
  alle bis auf die acht Küsten-/Seezellen `501000001…501000008` liegen im
  Kreis-Layer. Einen echten Drift-Fall enthält die Aufzeichnung daher nicht —
  der Drift-Wächter-Test konstruiert ihn im Testcode aus einer Kopie von #6
  (Vorbild `test_dpc_zone_drift.py`), die Fixture selbst bleibt unverändert.
- **Unverändert:** Jedes ausgewählte `warnings[]`-Element ist eine 1:1-Kopie
  aus dem Originalabruf (kein Feld umgeschrieben, keine Erfindung), kompakt
  serialisiert (~140 KB).

## `feed_switzerland_sample.json` (Issue #1442, Scheibe S1)

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-switzerland` (öffentlicher,
  kontingentfreier CAP-Feed, kein Auth).
- **Aufgezeichnet:** 2026-10-29 (Vollabruf 5,2 MB / 131 Einträge: 118 Alert, 13 Update, **kein**
  Cancel; je Eintrag 5 Sprachblöcke en/de/fr/it/rm × 1 `info`; je Gebiet nur `areaDesc`,
  `altitude`, `ceiling`, `polygon` — **kein Geocode**).
- **Polygon-Form:** `area.polygon` ist eine Liste von Strings, ein String je Ring, Paare
  `"lat,lon lat,lon …"` (Leerzeichen-getrennt).
- **Reale, unveränderte Einträge (8):** Thalwil-Wetzikon (Zürich), Bern-Sense, Luzern-Alpnach,
  Brienz-Interlaken, Basel (Alert + echtes Update `responseType: AllClear`, grün), Sarganserland,
  Mendrisiotto (Bodenfrost, Höhenband 0–600 m). Lugano (Luganese) ist **bewusst nicht** enthalten
  (Test „Punkt in der Schweiz ohne Treffer-Polygon").
- **Synthetische Einträge (4), Kennung endet auf `.SYNTH-*`** — aus einem echten Eintrag abgeleitet,
  weil der Feed sie nicht liefert (kein Cancel, kein Update mit vorhandenem Vorgänger, kein
  Mehrfachring):
  - `.SYNTH-CANCEL` — Cancel ohne `info`, `references` auf den Sarganserland-Alert.
  - `.SYNTH-UPDATE` — Update zum Brienz-Interlaken-Alert, Stufe orange (3) statt gelb.
  - `.SYNTH-LOCH` — Gebiet „Synthetisch Lochgebiet" (Grimsel-Raum) aus Außenring und Innenring (Loch),
    Höhenband 1800–2500 m.
  - `.SYNTH-KAPUTT` — an erster Stelle; `info` ist eine Liste, ein Gebiet trägt ein unlesbares Polygon.
- **Im Test abgeleitete Varianten (synthetisch, nicht in der Datei)** — `test_meteoalarm_feed_ch.py`
  verändert eine Kopie der Fixture: Brienz-Interlaken-Alert auf Orange plus `.SYNTH-UPDATE` auf
  Gelb (Herabstufung); vorangestellter Alert ohne `info` (`.SYNTH-OHNE-INFO`) und ein Nicht-Objekt-
  Eintrag; Gewitter-Kopie des Thalwil-Wetzikon-Alerts (`.SYNTH-GEWITTER`, `awareness_type` 3);
  ganz verdorbener Feed (alle `info` entfernt / `polygon`-Schlüssel überall umbenannt / alle
  Polygone unlesbar) und leerer Feed `{"warnings": []}`; Thalwil-Wetzikon-Alert mit
  vorangestelltem zweitem Gebiet (Bern-Sense-Polygon); Cancel **mit** `info` samt Gebiet
  (`.SYNTH-CANCEL-ABGELEITET`, Kopie der Thalwil-Wetzikon-`info`, `references` auf sie) sowie ein
  Feed nur aus einem solchen Cancel mit `info: []`.
- **Test-Referenzzeitpunkte:** Wind `2026-10-25T12:00Z`, Bodenfrost `2026-10-29T02:00Z`.
- **Größe:** ~390 KB (5 Sprachblöcke je Eintrag, Polygone unverändert).

---

# Fixtures: MeteoAlarm-Feed Norwegen, Schweden, Finnland (Issue #1442, Scheibe S2)

Alle drei Dateien: Herkunft `https://feeds.meteoalarm.org/api/v1/warnings/feeds-norway` bzw.
`-sweden` / `-finland` (öffentlicher, kontingentfreier CAP-Feed, kein Auth). **Aufgezeichnet:
2026-10-30** (Vollabrufe NO 362 KB / 52 Einträge, SE 402 KB / 28, FI 100 KB / 26). Reale Einträge
sind 1:1-Kopien (`warnings[]`), kompakt serialisiert. Synthetische Einträge tragen die Kennung
`….SYNTH-*`.

## `feed_norway_sample.json` (12 Einträge)

- **Sprachen:** `no` + `en-GB`; Polygone (`area.polygon`, Liste von Ring-Strings `"lat,lon …"`),
  teils mit `altitude`/`ceiling`; kein Geocode. `areaDesc` unterscheidet sich zwischen den
  Sprachblöcken („Skomvær" / „Skomvaer") — der Mapper darf nicht daran gruppieren.
- **Real (8):** Flomfare gelb + orange (Ostland, 2 Ringe), Kuling Skomvær–Melbu (Lofoten, Höhenband
  0–900 m), Høy vannstand Hordaland und Rogaland, Kuling Bodø–Lødingen, Kuling Støtt–Hekkingen,
  Kansellert kulingvarsel (grün, `Update`).
- **Synthetisch (4):** `.SYNTH-CANCEL` (Cancel, `references` auf die Lofoten-Kuling, ohne `info`),
  `.SYNTH-UPDATE` (Update der echten Kuling-Warnung Bodø–Lødingen, `references` auf sie, `sent`
  2026-10-25T09:00Z, Stufe orange; zuvor auf „Høy vannstand" Hordaland abgeleitet — das ist
  `awareness_type` 7, Küstenereignis, und wird vom geteilten Mapper bewusst verworfen),
  `.SYNTH-LOCH` (Außen- und Innenring
  im Raum Dovre, Höhenband 900–1800), `.SYNTH-KAPUTT` (an erster Stelle, unlesbare Polygone).
- Tromsø liegt bewusst in keinem Polygon („Punkt im Land ohne Treffer").
- **Zeitstand beachten:** Die Aufzeichnung enthält Meldungen verschiedener Versandtage. Die Kuling
  Støtt–Hekkingen (versandt 2026-10-28T15:00Z) überdeckt Bodø und die Lofoten; Tests mit `now`
  am 25.10. werten den Feed deshalb über `_stand_bis(feed, now)` aus (nur Meldungen mit
  `sent <= now`). „Høy vannstand" (Hordaland, Rogaland) ist Typ 7 und erzeugt keine Warnung.

## `feed_sweden_sample.json` (9 Einträge)

- **Sprachen:** `sv-SE` + `en-GB`; Polygone; kein Geocode.
- **Die echte Aufzeichnung führte nur grüne Einträge** (`awareness_level` 1, `responseType`
  `AllClear`). Real (6): Götaland (Malmö, Göteborg, Ystad), Värmland (Karlstad), Stockholm, Gotland,
  Västernorrland, Jämtland-Berge — alle grün, also keine aktive Warnung (Malmö = „ruhig").
- **Synthetisch (3), aus echten Einträgen abgeleitet:** `.SYNTH-GUL` (Stockholm, Stufe 2),
  `.SYNTH-ORANGE` (Karlstad, Stufe 3), `.SYNTH-CANCEL` (Cancel auf die Gotland-Meldung).

## `feed_finland_sample.json` (9 Einträge: 8 real, 1 synthetisch)

- **Synthetisch (1, am Ende angehängt, Indizes 0–7 unverändert):** `.SYNTH-KYMENLAAKSO` — Kopie
  des echten Eintrags 5 (Landwind, 27.10. 22:00Z–28.10. 03:00Z), Gebiet ersetzt durch `FI036`
  Kymenlaakso. Zweck: Küstenort Kotka liegt in Landzone FI036 UND Seezone FI805; nur die
  Landzone ist gewarnt (Gegenstück zu Helsinki, wo nur die Seezone FI806 gewarnt ist).

- **Sprachen:** `fi-FI` + `sv-SE` + `en-GB`; **kein Polygon**, nur `geocode` `EMMA_ID`:
  Landzonen `FI029` (Pohjanmaa), `FI032` (Varsinais-Suomi), `FI043` (Ahvenanmaa), Seegebiete
  `FI801`–`FI813`. Die Einträge „Wind warning for land areas" teilen sich eine Kennung (`Update`
  und `Alert`) — nicht als eindeutigen Schlüssel verwenden.
- Auswahl: Seegebiete FI806 (Sturm), FI812/FI803 (Wellenhöhe orange), FI801/FI810/FI809, Land
  FI032/FI029 und FI043/FI029, FI809, FI810/FI809.

## Referenzzeitpunkte der Tests (UTC)

NO Ostland `2026-10-25T12:00Z`, NO Lofoten/Bodø-Update `2026-10-25T20:00Z`, NO Bodø
(Støtt–Hekkingen) `2026-10-28T16:00Z`, SE `2026-10-25T09:00Z`, FI Land `2026-10-27T20:00Z`
(Turku, Eintrag 4) / `23:00Z` (Vaasa, Mariehamn, Eintrag 5 — versandt 22:00Z), FI See
`2026-10-26T01:00Z`.

## `feed_spain_sample.json` (13 Einträge: 8 real, 5 synthetisch) — Issue #1442 S3

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-spain` (AEMET, kontingentfrei),
  Vollabruf 2026-10-30 (97 Einträge, **kein Polygon**, nur `EMMA_ID`; Sprachen `es-ES` + `en-GB`).
- **Real (8, 1:1):** ES115 Regen gelb (`Update`, Mallorca Nord/Nordost, mit `references`), ES113
  Regen gelb (Ibiza, abgelaufen), ES225 Regen gelb (`Update`, abgelaufen), ES206 Nebel gelb, ES126
  Regen gelb (Kanaren, `.PRP1…`; nur der erste Eintrag der Gruppe ES125–127, die Fixture trägt
  davon nur `ES126`), Wind grün (169 Zonen), Küstenereignis grün
  (Typ 7, 40 Seezonen), Lawinen grün.
- **Synthetisch (5, aus dem echten ES115-Eintrag abgeleitet, Kennung `.SYNTH-*`, gültig
  2026-10-31 00:00Z–23:59Z, versandt 2026-10-30 11:00Z):** `.SYNTH-ES114` (Sierra Tramontana, orange,
  Regen — GR221), `.SYNTH-ES117` (Sur de Mallorca, gelb, Regen), `.SYNTH-ES874` (Costa Sur de
  Mallorca, gelb, Wind — Küstenort = Land + See), `.SYNTH-ES233` (Grenzstreifen Hendaye, gelb),
  `.SYNTH-ES182` (Grenzstreifen Bourg-Madame, gelb). Grund: am Aufzeichnungstag war für Mallorcas
  GR221-Zonen außer ES115 nichts amtlich gewarnt.
- **Referenzzeitpunkt der Tests:** `2026-10-31T09:00Z`.
- **Test 7 (unbekannte Zone `ES999`)** wird im Test aus dem Fixture abgeleitet, nicht eingecheckt.

## `feed_{portugal,netherlands,poland}_sample.json` — Issue #1442 S3a

Herkunft: `https://feeds.meteoalarm.org/api/v1/warnings/feeds-portugal` / `-netherlands` / `-poland`
(IPMA, KNMI, IMGW; kontingentfrei), Vollabrufe 2026-10-30 (PT 5, NL 754, PL 156 Einträge; **kein
Polygon**, nur `EMMA_ID`; Sprachen Landessprache + `en-GB`). Reale Einträge sind unverändert
übernommen; synthetische tragen die Kennung `.SYNTH-*`, sind aus einem echten Eintrag desselben Landes
abgeleitet und gelten 2026-10-30 00:00Z–2026-11-01 23:59Z. Rückzüge (`.SYNTH-*-CANCEL`) sind
CAP-konform ohne `info[]`. Zuordnung der Testorte zu den Zonen: `src/services/official_alerts/data/README.md`.

- **`feed_portugal_sample.json` (14 Einträge: 5 real, 9 synthetisch).** Real: Azoren `PT001`–`PT003`
  Regen gelb (abgelaufen), Madeira `PT023`/`PT024` Regen gelb als `Update` (`MD-10-1166`/`-1167`,
  Vorgänger nicht im Feed). Synthetisch: `.SYNTH-KAPUTT` (erster Eintrag, ohne awareness-Parameter,
  unlesbarer Beginn, `PT010`; AC-9), `.SYNTH-PT016` (Lissabon, orange, Regen), `.SYNTH-PT009` (Porto,
  gelb, Wind), `.SYNTH-PT018` (Elvas, gelb, Regen), `.SYNTH-PT021-ALT` + `.SYNTH-PT021-UPDATE` (Faro,
  gelb → orange per `Update`), `.SYNTH-PT015-AUFGEHOBEN` + `.SYNTH-PT015-CANCEL` (Nazaré),
  `.SYNTH-PT013-CANCEL-MIT-INFO` (letzter Eintrag; Adversary F001: ein `Cancel` **mit** vollständigem
  `info[]`, gelb, Wind, Zone `PT013` Coimbra, gültig 30.10. 00:00Z–01.11. 23:59Z, abgeleitet aus dem
  echten `AZ-10-661`; `references` zeigt auf eine Kennung, die NICHT im Feed steht, damit allein die
  Regel „ein Rückzug ist nie eine aktive Warnung" ihn unterdrückt). Grund: am Aufzeichnungstag war
  das Festland ohne Warnung.
- **`feed_netherlands_sample.json` (32 Einträge: 28 real, 4 synthetisch).** Real: nur Stufe grün
  (Wind, Schnee/Eis, Gewitter, Nebel) für `NL007`, `NL011`, `NL012`, `NL013`, `NL015`, `NL019`, `NL806`,
  davon 8 `Update` (`*_C`, Vorgänger nicht im Feed). Synthetisch: `.SYNTH-NL011` (Amsterdam, gelb,
  Wind; info-Blöcke in der Reihenfolge **`en-GB` vor `nl-NL`**, Adversary F002: in allen echten
  Einträgen steht `en-GB` zuletzt, eine Sprachwahl „letzter Block" fiele sonst nicht auf),
  `.SYNTH-NL806` (Waddenzee, gelb, Regen), `.SYNTH-NL012` (Venlo, gelb, Regen),
  `.SYNTH-NL013` (Baarle-Nassau, orange, Wind).
- **`feed_poland_sample.json` (15 Einträge: 6 real, 9 synthetisch).** Real: `PL2402` Wind orange
  (`Update`, abgelaufen 25.10.), Nebel gelb `PL3262`/`PL1210`/`PL1211`/`PL1217` (Zakopane) und Nebel
  orange `PL803` (alle **Typ 4**). Synthetisch: `.SYNTH-PL1465` (Warschau, gelb, Wind; AC-8-Fall
  `pl-PL` + `en-GB`), `.SYNTH-PL1261` (Krakau, orange, Regen), `.SYNTH-PL2261` (Danzig, gelb, Regen),
  `.SYNTH-PL805` (Coastal Zone East, gelb, Wind), `.SYNTH-PL0805` (Słubice, gelb, Regen),
  `.SYNTH-PL0663-ALT` + `-UPDATE` (Lublin, gelb → orange), `.SYNTH-PL2061-AUFGEHOBEN` + `-CANCEL`
  (Białystok). Die `pl-PL`-Texte (`description`) der aus dem Nebel-Eintrag abgeleiteten SYNTH-Einträge
  nennen weiterhin Nebel; ausgewertet wird nur `en-GB`.
- **Achtung Warnarten:** Der geteilte CAP-Mapper verwirft `awareness_type` 4 (Nebel) und 7
  (Küstenereignis) bewusst (Issue #1430, `meteoalarm._DISCARDED_TYPES`). Einträge dieser Typen erzeugen
  in keinem Land eine Warnung. Die echte Nebelwarnung `…2544112.PL1217` (Zakopane) dient deshalb als
  **Negativprüfung auf echten Daten** (`test_ac1_echte_pl_nebelwarnung_zakopane_wird_verworfen`: keine
  Warnung, kein Ausfallhinweis).
- **Abweichung vom RED-Stand (Commit `e3ff2b85e`), korrigiert in Phase 6:** Die SYNTH-Einträge trugen
  Warnarten, die der Mapper verwirft, und konnten so nie eine Warnung erzeugen: `.SYNTH-NL806` und
  `.SYNTH-PL805` Typ 7 (Küstenereignis), `.SYNTH-NL013` Typ 4 (Nebel). Korrektur: nur
  `awareness_type` (alle Sprachen) sowie `en-GB`-`event`/`headline` (PL805 auch `pl-PL`), Stufe, Zone,
  Kennung, Zeitfenster und Sprachen unverändert. `.SYNTH-NL013` und `.SYNTH-PL805` → `1; Wind`
  (Vorbild `.SYNTH-ES874`). `.SYNTH-NL806` → `10; Rain` statt Wind: Mit Wind hätte die Seewarnung
  dieselbe Gefahr und dasselbe Zeitfenster wie `.SYNTH-NL011` (Wind, Noord-Holland) und wäre im
  Registry-Kollaps #1086 (exakte Dublette je Gefahr) mit ihr verschmolzen; AC-5 (Land + See je
  einmal) wäre dann nicht prüfbar. Außerdem trug der RED-Stand die Prämisse „Zakopane: echte gelbe
  Warnung erscheint" (AC-1 und AC-8 PL). Sie ist falsch, weil die Warnung vom Typ Nebel ist. AC-1
  Zakopane wurde zur Negativprüfung oben, AC-8 PL nutzt jetzt `.SYNTH-PL1465` (Warschau).
- **Referenzzeitpunkte der Tests (UTC):** PT `2026-10-31T22:00Z`, NL `2026-10-31T09:00Z`, PL
  `2026-10-30T06:00Z`.
- **Drift-Test (`PT999`, `NL999`, `PL9999`)** wird im Test aus dem Fixture abgeleitet, nicht eingecheckt.

## `feed_uk_sample.json` — Vereinigtes Königreich (Issue #1442, Scheibe S3b)

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-united-kingdom` (öffentlich,
  kontingentfrei). Der UK-Feed trägt nur Polygone (kein Geocode) und nur `en-GB`.
- **Aufgezeichnet:** 2026-10-31 (Vollabruf, 4 Einträge, 33 KB).
- **Reale, unveränderte Einträge (4):** Windwarnung gelb Irische See/Westküste (`…61bc9a69.v1.0.W`,
  26.10. 18:00Z–27.10. 03:00Z), Windwarnung gelb Nordschottland/Shetland (`…011bc9b4.v3.0.W`, echtes
  `Update`, dessen Vorgänger nicht mehr im Feed stehen, 27.10. 03:00Z–18:00Z) und zwei gelbe
  Nebelwarnungen (`…cd0a7b87.v1.0.F`, `…fb133494.v1.0.F`; Typ Nebel verwirft der geteilte Mapper
  bewusst, `meteoalarm._DISCARDED_TYPES`).
- **Synthetische Einträge (3), Kennung endet auf `.SYNTH-*`** — aus echten Einträgen abgeleitet,
  weil der Feed sie nicht liefert:
  - `.SYNTH-UPDATE` — Update zur Nordschottland-Windwarnung (v3), Stufe orange (3) statt gelb, der
    Vorgänger steht weiter im Feed.
  - `.SYNTH-CANCEL` — Cancel ohne `info`, `references` auf die Irische-See-Windwarnung (v1).
  - `.SYNTH-KAPUTT` — an erster Stelle; Windwarnung mit unlesbarem Polygon.
- **Referenzzeitpunkte der Tests (UTC):** Irische See `2026-10-26T22:00Z`, Nordschottland
  `2026-10-27T10:00Z`, Nebel `2026-10-31T07:00Z`.

## `feed_belgium_sample.json` (Issue #1442, S3c)

- **Herkunft:** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-belgium` (kontingentfreier CAP-Feed).
- **Aufgezeichnet:** 2026-10-31 (Vollabruf 152 KB / 38 Warnungen, 4 Sprachen `nl-BE`, `fr-BE`, `en-GB`, `de-DE`).
- **Echte, unveränderte Einträge (6):** Küstenwarnung `…20261024195121.1618968` (nur `NUTS2` BE23, gelb,
  `coastalevent`) und `…1618969` (BE21); Nebel `…20261031060158.1619001` (BE23), `…1618999` (`EMMA_ID` BE801),
  `…1619004` (`EMMA_ID` BE004); ein `Update` `…20261031070505.1619011` (`EMMA_ID` BE004, grün).
  **Keine echte Warnung ist auswertbar:** alle echten Einträge sind Nebel (`4; Fog`) oder Küste
  (`7; coastalevent`), beide verwirft der geteilte Mapper bewusst (#1430); belegt durch
  `test_ac4_echte_kuesten_und_nebelwarnungen_verwirft_der_mapper`. Deshalb die synthetischen Ableitungen.
- **Synthetisch (Kennung `…SYNTH-*`, aus der echten Küstenwarnung 1618968 abgeleitet; geändert sind nur
  Kennung, Stufe, Zeitraum 30.10. 01:00 bis 01.11. 23:59 (+01:00), Gebietskennung und `awareness_type`
  `7; coastalevent` → `1; wind` (unterstützter Typ); Texte unverändert, sie sprechen daher weiter von
  „Sturmflut"):**
  `SYNTH-BE23`, `SYNTH-BE801`, `SYNTH-BE24`, `SYNTH-BE10`, `SYNTH-BE31` (Stufe gelb); `SYNTH-BE004-ORANGE`
  (`EMMA_ID` BE004, orange); `SYNTH-BE10-UND-BE004` (beide Kennungsarten in einer Fläche); `SYNTH-BE99`
  (unbekannter NUTS2-Code); `SYNTH-UPD-ALT-BE23` (gelb) + `SYNTH-UPD-NEU-BE23` (`Update`, orange, `references`
  auf die gelbe); `SYNTH-CANCEL-ALT-BE23` + `SYNTH-CANCEL-BE23` (`Cancel` ohne `info`).
