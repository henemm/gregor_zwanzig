# Context: fix-1397-wiederanlauf-ausbruch

Erstellt: 2026-07-31 · Issue: #1397 (offen, `priority:critical`, `area:alerts`, `bug`)

## Request Summary

Der MeteoAlarm-Dienst für amtliche Unwetterwarnungen wird seit dem 27.07.2026 **täglich** vom Anbieter für 24 h gesperrt (HTTP 429, `x-ratelimit-reset` ≈ 86399 s). Zwischen zwei Sperren liegen nur ein bis zwei Stunden nutzbare Zeit; den Rest des Tages sind die Warndaten veraltet. Der in #1397 noch offene Wirkungsnachweis („voller Tag ohne 429") kann unter diesen Bedingungen strukturell nicht erbracht werden.

## Ausgangsmessung (Produktion, 2026-07-31)

| Beobachtung | Wert |
|---|---|
| Echter Anbieter-429 | `2026-07-31T15:45:25Z`, `meteoalarm:IT:p1`, `retry_after` 86399,15 |
| Daraus `observed_reset_ts` | `2026-08-01T15:45:25Z` |
| Index-Abrufe im Fenster davor | **65** (`host = api.meteoalarm.org`), verteilt auf 14:15–15:45 UTC |
| Zählerdatei | `{"date": "2026-07-31", "calls": 65, "observed_reset_ts": 1785599125.0}` |
| Blockierte Abrufe seither | 221 Zeilen `self_throttled: true` |
| 429-Historie | 27.07. 12:00 · 29.07. 09:30 · 30.07. 14:00 · 31.07. 15:45 (UTC) |

**Korrektur zur ersten Ablesung:** Die zunächst gemeldete Diskrepanz „Zähler 65 vs. 120 echte Abrufe" ist **widerlegt**. Von den 120 Journalzeilen gehen 55 an `meteo.fra1.digitaloceanspaces.com` (CAP-XML und Geometrie, präsigniert, auth-frei) und zählen bewusst nicht gegen das Index-Budget — belegt durch `meteoalarm.py:938-945` und `:955-962`, Kommentar `:749-750`. Die 65 gegen `api.meteoalarm.org` stimmen **exakt** mit dem Zählerstand überein. Der Verbrauchszähler arbeitet korrekt.

**Die daraus folgende, weit ernstere Frage:** Der Anbieter sperrte bereits nach 65 Index-Abrufen — bei einem eigenen Budget von 100 und einer bisher angenommenen realen Grenze von ~160. Entweder liegt die reale Grenze deutlich niedriger als gemessen, oder der Anbieter zählt anders als wir (anderes Fenster, andere Abrufklassen). Das ist in der Analyse-Phase zu klären; ohne diese Zahl ist jede Budget-Einstellung geraten.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `src/services/official_alerts/meteoalarm.py` | Abruf-Steuerung: Fensterberechnung (`_index_query_window`, :389-429), Blättern (`_get_cached_index`, :744-835), Zählpunkt (`:706-712`), Slot-Takt (`_SLOT_MINUTES = 60`, :122) |
| `src/services/official_alerts/meteoalarm_budget.py` | Tagesbudget-Schranke: `allow()` (:96-111), `record_call()` (:113-118), `record_observed_reset()` (:120-129), Roll-Over in `_load_state()` (:172-206) |
| `src/services/official_alerts/warn_egress.py` | Journal (`log_warn_service_call`, :212-254), Cache/429-Politik (`cached_fetch`, :286 ff.), `RateLimitRetryPolicy.is_long_lived` (:182-190), **Journalpfad ist CWD-relativ** (:100) |
| `internal/scheduler/warn_service_health.go` | Beobachtbarkeit an `/api/scheduler/status`; kein Rate-Feld vorhanden (s. Risiken) |
| `internal/scheduler/scheduler.go:110,118` | Auslöser: `alert_checks` + `compare_official_alert_checks` im **15-Minuten-Takt je Nutzer** |

## Wirkkette (aus dem Code belegt)

1. Fortschrittsmarke `last_complete` liegt **nur im Prozess-Speicher** (`meteoalarm.py:284-286`, `_index_cache` :492). Prozess-Neustart oder ein langer Ausfall ⇒ Kaltstart.
2. Kaltstart **oder** alte Marke ⇒ Fenster wird auf die volle Rückschau von **23 h** aufgezogen (`:424-428`).
3. 23-h-Fenster ⇒ maximale Seitenzahl beim Anbieter (Messwerte 17–21, aufgezeichnet bis 79) **× 2 Länder** ⇒ Größenordnung 35–45 Index-Abrufe für einen vollständigen Zyklus.
4. Pro Einzelaufruf bremsen 20 s Zeitbudget + 4 s Abstand auf ~5 neue Seiten — aber der Scheduler ruft alle 15 Minuten je Nutzer erneut auf, sodass sich der Nachholbedarf innerhalb desselben Slots trotzdem summiert.
5. Läuft ein Slot nicht vollständig durch, wird `last_complete` **nicht** gesetzt (`:822-835`) und der Seiten-Cache beim Slot-Wechsel verworfen (`:432-460`) ⇒ die nächste Stunde beginnt wieder bei Seite 1 mit 23-h-Fenster.
6. Ergebnis: **Jede Sperre erzeugt beim Wiederanlauf den Ausbruch, der die nächste Sperre auslöst.** Es gibt keine Rampe, die das Fenster nach einer Sperre schrittweise verbreitert.

## Existing Specs

- `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md` — AC-2: <100 echte Netz-Abrufe je **gleitendem** 24-h-Fenster; AC-3: Kaltstart fragt bewusst das 23-h-Breitband. Known Limitations Z. 105/106 benennen den Prozess-Neustart-Fall bereits als bekannte Schwäche.
- `docs/specs/modules/warn_service_consumption.md` — AC-1..AC-11: TTL, 429-Backoff, Journalfelder (#1348/#1337).
- `docs/specs/modules/fix_1422_warn_ausfall_alarm.md` — AC-2/AC-6 trennen selbst auferlegten Rückzug von echter Anbieterstörung.
- `docs/context/fix-1397-warnungen-vollstaendig.md` — Kontext der ersten Scheibe.

## ADRs

Zu Egress-/Kontingent-Management existiert **kein** ADR; die drei einschlägigen Specs tragen ausdrücklich „ADR-Nr.: keine". Relevant als Muster:
- **ADR-0016** „Amtliche Warnungen als additiver externer Alert-Typ" (Akzeptiert) — von #1397 als weiter gültig bestätigt.
- **ADR-0018** „Modell-Fallback bei Wetter-Quell-Ausfall — mit Ausweichen, ohne Kaschieren" (Akzeptiert, PO-go 2026-07-08) — enthält das mit der Ausfalldauer **wachsende Signal**; auf der Warn-Seite fehlt dieses Pendant.

Ob die hier zu treffende Entscheidung (Rampe/Staffelung nach Sperre, ggf. Priorisierung von Abrufen) ADR-würdig ist, entscheidet die Spec-Phase.

## Tests

- `tests/tdd/test_meteoalarm_index_coverage.py` — zentrale Verbrauchstests gegen lokalen HTTP-Server mit Abrufzähler und injizierter Uhr; bildet die 24-h-Grenze der echten API nach (HTTP 400 ab Fensterbreite ≥ 24 h).
- `tests/tdd/test_meteoalarm_source.py` — Blätter-/Slot-/429-Mechanik, u. a. `test_beobachteter_daily_reset_sperrt_budget_ueber_echten_pfad`.
- `tests/unit/test_meteoalarm_budget_gate.py` — Gate-Verhalten ohne HTTP.
- `tests/tdd/test_warn_service_egress.py` — `cached_fetch`-Kern inkl. Kurzzeit- vs. Tageskontingent-429.

**Lücke (entscheidend):** Es existiert **kein Test „Sperre läuft ab → wie viele Abrufe fallen in der ersten Stunde danach an"**. Grund: Die autouse-Fixture `_kalter_prozess` setzt in allen zählenden Tests `GZ_METEOALARM_DAILY_BUDGET=100000`, schaltet das Gate also bewusst ab; die Tests mit echter Sperre haben umgekehrt keinen Abrufzähler über einen Zeitverlauf. Der Ausbruch ist damit strukturell unmessbar — genau deshalb ist er durch alle bisherigen Scheiben gefallen.

## Dependencies

- **Upstream:** `api.meteoalarm.org` (EDR-Index, Bearer-Auth, Tageskontingent unbekannter Höhe), `meteo.fra1.digitaloceanspaces.com` (CAP-XML/Geometrie, präsigniert, kontingentfrei).
- **Downstream:** `src/services/trip_alert.py:954` und `src/services/compare_official_alert.py:162` über `base.py:179` — d. h. Trip-Briefings **und** Ortsvergleiche zeigen die Warnungen bzw. den Hinweis „nicht abrufbar".

## Risks & Considerations

1. **Sicherheitsfunktion, beide Richtungen gefährlich.** Zu sparsam ⇒ eine gültige Warnung wird nicht gesehen (der Ursprungsdefekt von #1397). Zu großzügig ⇒ Dauersperre und veraltete Daten. Eine reine Budget-Senkung ist deshalb keine Lösung.
2. **Die reale Anbietergrenze ist unbekannt** und liegt nach dieser Messung womöglich unter 100. Ohne belastbare Zahl ist jede Einstellung geraten — das ist die erste Frage der Analyse.
3. **Ausfall darf nicht kaschiert werden** (ADR-0018-Muster, AC-4 der bestehenden Spec): Wer den Wiederanlauf streckt, riskiert längere Phasen unvollständiger Daten — diese Phasen müssen weiterhin ehrlich als „nicht abrufbar" erscheinen.
4. **Kein Gedächtnis über Neustarts.** Fortschrittsmarke und Bestand liegen nur im Prozess-Speicher; jeder Deploy erzeugt einen Kaltstart-Ausbruch. Eine Persistenz wäre wirksam, berührt aber die Regel „Bestandsdaten bei Persistenz-Änderungen erhalten".
5. **Fehlende Beobachtbarkeit.** `/api/scheduler/status` liefert nur kumulative Zählerstände, keine Rate. Ein Ausbruch von 45 Abrufen in drei Minuten ist von außen nicht erkennbar — ohne dieses Signal ist die Wirkung eines Fixes nicht belegbar.
6. **Mehr Länder geplant** (#1442: CH, Skandinavien, Rest-EU) am selben Tagesbudget — jede Lösung muss mit der Länderzahl skalieren, nicht gegen sie.
7. **Nebenbefund für später (nicht Teil dieser Arbeit):** `WARN_CALLS_PATH` ist CWD-relativ (`warn_egress.py:100`), der Zähler dagegen `GZ_DATA_DIR`-relativ. Weichen beide auseinander, landen Journal und Zähler in verschiedenen Verzeichnissen.

## Verwandte offene Issues

#1348 (Vorgänger, Budget-Gate), #1337 (Dach: Egress-Wächter), #1329 (gleiches Muster bei open-meteo), #1442 (Ländererweiterung, erhöht den Verbrauch), #1430 (Lawinenwarnungen verworfen), #1440 (DWD als weitere Quelle).

---

# Analysis

## Type

**Bug** — nutzersichtbares Fehlverhalten mit Sicherheitsbezug: amtliche Warnungen sind den größten Teil des Tages veraltet.

## Befund 1 — die Anbietergrenze ist nicht stationär und liegt unter unserem Budget

Gemessen aus dem Produktions-Journal, echte Netz-Abrufe gegen `api.meteoalarm.org` zwischen zwei Sperren:

| Öffnungszeitraum | offen | Abrufe bis zum nächsten 429 |
|---|---|---|
| 28.07. 12:00 → 29.07. 09:30 | 21,5 h | 138 |
| 30.07. 09:30 → 30.07. 14:00 | 4,5 h | 95 |
| 31.07. 14:00 → 31.07. 15:45 | 1,7 h | **64** |

Tagesverbrauch davor: 23.07. 2281 · 24.07. 967 · 25.07. 2978 · 26.07. 3214 · 27.07. 1465 (Blätter-Exzess vor dem S1-Fix). Danach Sperrbetrieb: 52 · 87 · 96 · 65.

**Die durchgelassene Menge sinkt monoton.** Keine geprüfte Fensterbreite (24 h / 48 h / 72 h / 7 d) ergibt eine konstante Grenze. Damit ist jede Budget-Zahl geraten — auch die aktuellen 100/Tag, die über der zuletzt real durchgelassenen Menge (64) liegen. Möglicher Treiber: Reputationsfolge des Exzesses vom 23.–27.07.

## Befund 2 — kontingentfreie Alternativquelle, live geprüft

`https://feeds.meteoalarm.org/api/v1/warnings/feeds-{austria,italy}`, HTTP 200, ohne Auth:

- **Ein Abruf je Land** statt bis zu 21 Seiten. AT 2,4 MB / 1220 Einträge (709 gültig), IT 1,4 MB / 457 (195 gültig), < 1,4 s.
- Vollständiger CAP-Inhalt im JSON (`event`, `severity`, `onset`, `expires`, `awareness_level`, `awareness_type`, `areaDesc`), AT **auf Deutsch**.
- Rückschau **5,8 Tage** statt der harten 23-h-Grenze der EDR-API ⇒ AC-1 verbessert sich; die in der Spec als „strukturell unerreichbar" dokumentierte Restlücke schließt sich.
- Der Feed ist eine Momentaufnahme der **gültigen** Fassungen (0 von 335 referenzierten Vorgängern enthalten) ⇒ AC-5 verbessert sich; ein Rückzug verschwindet automatisch.
- Kein ETag, kein gzip ⇒ jede Auffrischung kostet die volle Größe.

## Befund 3 — Punkt-in-Fläche über EMMA-ID braucht keine neue Geodatei

Das war der einzige offene Punkt gegen einen Quellenwechsel; er ist ausgeräumt:

- **Italien:** `src/services/official_alerts/data/dpc_zones.json` trägt 187 Zonen mit genau 20 Regionspräfixen — 1:1 zu IT001…IT020. `dpc._zone_at()` (`dpc.py:77-83`) löst den Punkt bereits auf. Es fehlt eine 20-zeilige Präfix→EMMA-Tabelle.
- **Österreich:** `geosphere_warn._get_cached_warnings()` (`geosphere_warn.py:69-104`) ruft für jeden AT-Punkt ohnehin schon ZAMG ab und cacht 30 min; die Antwort trägt `gemeindenr`, deren erste drei Stellen die EMMA-Kennung sind (gemessen: Villach 20201→AT202, Tamsweg 50510→AT505, Wien 90101→AT901). **Null zusätzliche Abrufe.**

Nicht restlos bewiesen ist, dass die EDR-Fläche identisch mit der EMMA-Zone ist (Indiz: `featureType: "geocode"` mit genau einer Area, bezirksgroße Bbox). Deshalb ist ein Äquivalenztest Pflicht-Gate vor dem Umschalten.

## Befund 4 — der Ausbruch ist doppelt unmessbar

Neben dem bekannten `GZ_METEOALARM_DAILY_BUDGET=100000` (`test_meteoalarm_index_coverage.py:92`) ersetzt `_uhr_einsetzen(..., gekoppelt=False)` (`:135`) auch `_SLEEP_FN` durch einen No-Op. Die 4-s-Bremse und das 20-s-Seitenbudget kosten im Test also keine Zeit — der Zweig, der in Produktion `incomplete=True` setzt, feuert in fast allen Tests nie. Messung mit dem bestehenden Harness: `gekoppelt=False` ⇒ 16 Abrufe im ersten Tick und Fortschrittsmarke sofort gesetzt; `gekoppelt=True` ⇒ 7/13/16 über drei Ticks, Marke erst ab Tick 2.

**Verstärker (plausibel, nicht verifiziert):** `gate.record_call()` liegt *innerhalb* von `request_fn` (`meteoalarm.py:706-712`), und die Kurzzeit-429-Wiederholung ruft `request_fn` bis zu dreimal auf (`warn_egress.py:168`) — eine Seite kann bis zu drei Kontingent-Einheiten kosten.

## Befund 5 — MeteoAlarm bietet einen Push-Kanal (MQTT), live verifiziert

PO-Einwurf 2026-07-31, geprüft in derselben Sitzung. MeteoAlarm 2.0 / MeteoGate stellt neben REST einen MQTT-Dienst bereit. **Selbst getestet gegen `mqtts://mqtt.meteoalarm.org:8883`:**

| Prüfung | Ergebnis |
|---|---|
| TLS | gültiges Zertifikat `*.meteoalarm.org` |
| CONNECT (`api` / vorhandener API-Schlüssel) | **CONNACK rc=0 — akzeptiert**, kein separater Zugang nötig |
| SUBSCRIBE `warnings-AT`, `warnings-IT` | **SUBACK rc=0 — beide angenommen** |
| Retained Messages | **keine** — direkt nach dem Abonnieren kam nichts; der Broker liefert nur neue/geänderte Warnungen |
| Port 1883 (unverschlüsselt) | geschlossen |

Laut Anbieter-FAQ ist der REST-Weg **10 Minuten verzögert**, MQTT dagegen „near realtime"; für MQTT sind **keine Rate-Limits dokumentiert**. Topic je Land (`warnings-AT`, `warnings-DE`, …), Nutzlast im selben GeoJSON-Format wie REST.

**Bewertung:** Das ist der strukturell richtige Bezugsweg — er beseitigt das Kontingentproblem nicht durch bessere Dosierung, sondern durch Wegfall des Pollings. Zusätzlich sinkt die Verzögerung von bis zu 60 Minuten (Slot-Raster) auf Sekunden, was für ein Warnwerkzeug der eigentliche Gewinn ist.

**Was MQTT allein nicht kann:** Ohne Retained Messages hat ein frisch verbundener Abonnent **keinen Bestand** — er erfährt nur, was ab dem Verbindungszeitpunkt passiert. Push braucht deshalb zwingend einen Anfangsbestand, und genau den liefert der öffentliche Feed aus Befund 2 mit einem einzigen kontingentfreien Abruf je Land.

## Technical Approach (Empfehlung)

**Zielbild: Feed als Anfangsbestand + MQTT als laufende Aktualisierung; der kontingentierte EDR-Index entfällt ersatzlos.**

1. **Start / Wiederverbindung:** ein Feed-Abruf je Land füllt den Bestand (kontingentfrei, ~2,4 MB AT / 1,4 MB IT).
2. **Betrieb:** MQTT-Abonnement je Land hält den Bestand aktuell — Push statt Polling, kein Kontingent, Sekunden statt Minuten.
3. **Verbindungsabriss:** Wiederverbindung mit erneutem Feed-Snapshot, um die Lücke zu schließen; solange kein gültiger Bestand vorliegt, gilt `unavailable=True` (nie „keine Warnung").
4. **Bestand über Neustarts persistieren** — sonst kehrt das Kaltstart-Problem in anderer Form zurück.

Damit sinkt der Verbrauch gegen `api.meteoalarm.org` auf **null** und der Feed-Verbrauch auf ~2 Abrufe je Prozessstart statt heute 84–120 kontingentierter Abrufe pro Tag.

**Offene Betriebsfragen für die Spec:** Wo läuft der Abonnent (Python-Core als Hintergrund-Task vs. eigener Dienst)? Was passiert bei mehreren Arbeitsprozessen (mehrere Verbindungen)? Wie wird die Verbindung überwacht (`last_message_at` an `/api/scheduler/status`, Heartbeat-Pflicht)?

**Fallback-Position, falls sich der Push-Betrieb als zu aufwendig erweist:** Feed-Polling allein (ein Abruf je Land je Slot) löst das Kontingentproblem bereits vollständig und ist deutlich einfacher — es kostet nur die Aktualität, die MQTT zusätzlich brächte.

**Verworfen: Quellenwechsel allein auf den Feed ohne Push** war die Empfehlung vor dem MQTT-Befund; sie bleibt als Zwischenstufe gültig (S2/S3 unten) und ist Voraussetzung für den Push-Betrieb, weil sie den Anfangsbestand liefert.

**Kein dauerhafter Parallelbetrieb mit dem EDR.** Begründung: Die unbekannte, schrumpfende Regel der Gegenseite wird dadurch gegenstandslos statt geraten; zwei Akzeptanzkriterien verbessern sich; der Aufwand pro zusätzlichem Land (#1442) sinkt von ~20 Abrufen auf einen.

**Kein dauerhafter Parallelbetrieb.** `base.py:146` setzt `unavailable = covering > 0 and failed >= 1` — bliebe der gesperrte EDR registriert, kippte seine 429-Sperre den Hinweis „nicht abrufbar" für alle, obwohl der Feed liefert. Der Quellenvergleich gehört in einen Fixture-Test, nicht in die Registry.

| Scheibe | Inhalt | Scope |
|---|---|---|
| **S1** | Messbarkeit: `gekoppelt=True` als Standard, neuer Test „Wiederanlauf nach 24-h-Sperre" mit scharfem Gate, Test „zählen Kurzzeit-Wiederholungen gegen das Budget?" | ~100 LoC, 1 Datei, kein Produktivcode |
| **S2** | Feed-Quelle Italien: neues `meteoalarm_feed.py` über `cached_fetch`, Präfix-Tabelle IT001…IT020, Punkt→Zone über `dpc._zone_at()`; CAP-Mapper in „sammeln" und „mappen" trennen | ~160–200 LoC, 3 Dateien + Tests — eng am 250er-Limit |
| **S3** | Feed-Quelle Österreich (EMMA aus `gemeindenr`), danach entfällt der gesamte Index-Apparat in `meteoalarm.py` | netto stark negativ in LoC |
| **S4** | **MQTT-Abonnent:** Dauerverbindung je Land, Bestand aus S2/S3 als Anfangszustand, Wiederverbindung mit Feed-Auffrischung, `last_message_at` an `/api/scheduler/status`, Heartbeat | eigener Workflow, mittel |
| **S5** | Ehrlichkeit + Beobachtbarkeit: unbekannter EMMA-Code ⇒ `mark_fetch_incomplete()` statt stiller Leere; Raten-Feld in `warn_service_health.go` | klein |
| S6 | optional/später: Rückfall-Geometrie AT ohne ZAMG, Ländererweiterung #1442 | — |

Reihenfolge S1 → S2 → S3 → S4 → S5. S2 zuerst, weil Italien ohne die 24-h-Grenze auskommt und ohne neue Geodatei fertig wird — Lernscheibe mit kleinem Risiko. Die Entlastung beim Verbrauch bringt bereits S3 (Österreich ist mit 17–21 Seiten der Hauptverbraucher); **S4 ist die Kür**, nicht die Rettung: Nach S3 ist das Kontingentproblem gelöst, MQTT bringt zusätzlich die Aktualität von Minuten auf Sekunden. Diese Reihenfolge ist bewusst so gewählt, dass der Push-Betrieb auf einem bereits funktionierenden Bestand aufsetzt statt ihn mitzuerfinden.

## Risk Level: HIGH

1. **Übersehene Warnung durch falsche Zonen-Zuordnung** — der einzige wirklich gefährliche Fehler. Gegenmaßnahme: Äquivalenztest gegen einen zur selben Minute aufgezeichneten EDR-Snapshot, als Pflicht-Gate vor S2/S3.
2. **`gemeindenr`→Bezirk ist eine Konvention**, an vier Punkten belegt — vor Auslieferung gegen alle 116 im Feed vorkommenden AT-Codes prüfen.
3. **AT hängt danach an ZAMG.** Ausfall dort ⇒ keine EMMA-ID ⇒ muss `unavailable=True` erzeugen, nie „keine Warnung". Beachte `geosphere_warn.py:82-89` (404 = „nicht zuständig", 24 h gecacht).
4. **IT-Punkte außerhalb aller DPC-Zonen** (Küste, Lagune, Seen) — Nächste-Zone-Rückfall, Muster in `department_mapper.py:263`.
5. **Unbekanntes Limit des Feed-Hosts** — bekannte Sperre gegen unbekannte Regel getauscht. Gegenmaßnahme: gleiche Egress-Disziplin, 2 Abrufe/Stunde statt heute 20–40.
6. **Bandbreite skaliert mit Ländern**, nicht mit Warnungen (CH 19,1 MB, DE 11,9 MB je Abruf) — für #1442 eigenes Auffrischraster je Land.
7. **`Cancel`-Verhalten unbeobachtet** — im Snapshot kamen nur `Alert`/`Update` vor.

## Beweisführung

1. **S1-Test „Wiederanlauf":** misst heute 16 Abrufe je Kaltstart, nach S2/S3 müssen es **2** sein (ein Feed-Abruf je Land).
2. **Äquivalenz-Fixture (Pflicht-Gate):** in der nächsten offenen Stunde einmalig EDR-Vollsnapshot (~24 Abrufe) **und** Feed derselben Minute aufzeichnen; für eine Liste realer Tourpunkte muss die Feed-Menge eine Obermenge der EDR-Menge sein.
3. **Produktion nach S3:** Journalzeilen mit `host == api.meteoalarm.org` fallen auf **0**. Damit ist #1397 abschließbar, ohne auf einen „vollen Tag ohne 429" zu warten, den es unter der aktuellen Sperre nicht geben kann.
4. **Zonen-Auflösung deterministisch** je Test aus den gemessenen Paaren (AT202/AT505/AT901, IT004/IT012).

## Open Questions

- [ ] PO: Quellenwechsel bestätigen (ersetzt die bisherige Bezugsquelle für amtliche Warnungen — ADR-würdig, zu entscheiden in der Spec-Phase)?
- [ ] PO: Überbrückung parallel bauen (~80 LoC Palliativ: Fortschrittsmarke und Bestand über Neustarts persistieren) oder direkt den Zielweg gehen?
- [ ] Technisch, in S1 zu klären: Zählen Kurzzeit-429-Wiederholungen mehrfach gegen das Kontingent?
