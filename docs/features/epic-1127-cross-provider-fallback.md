# Epic 1127: Infrastruktur-unabhängiger Provider-Fallback (Original-Dienste direkt)

**Status:** Slice 0 (#1141, Routing-Unterbau) implementiert (2026-07-09). AT/FR/DE (#1142-#1144)
noch offen, s. Sub-Issues-Tabelle unten.
**Baut auf:** #1115 (Intra-Open-Meteo-Modell-Fallback, live, ADR-0018). #1127 ist die **zweite
Redundanz-Stufe**: greift nur, wenn Open-Meteo als Verteiler **komplett** ausfällt (nicht nur ein
einzelner Modell-Kanal — das fängt #1115 bereits ab).

## Ausgangslage

Der Incident 07./08.07.2026 (#1113/#1115) betraf **einen** Open-Meteo-Modell-Endpoint
(`/v1/dwd-icon`), während Open-Meteo insgesamt weiterlief. #1115 hat dafür einen Modell-Fallback
*innerhalb* von Open-Meteo gebaut. Fällt Open-Meteo als **Verteiler-Infrastruktur** komplett aus
(DNS/CDN/Gesamt-Ausfall des Dienstes selbst, nicht nur ein Modell-Kanal), gibt es aktuell **keine**
Ausweichmöglichkeit — alle Kernpfade (`trip_forecast.py`, `segment_weather.py`,
`comparison_engine.py`, `forecast.py`, `trip_alert.py`, `trip_report_scheduler.py`) rufen hart
`get_provider("openmeteo")` (verifiziert, 7 Fundstellen, s. u.).

**Zentraler, nicht-offensichtlicher Befund dieser Recherche:** Alle im Code bereits vorhandenen
Referenzen auf „AROME-FR"/„ICON-D2" sind **keine** direkten Original-Anbindungen, sondern
Open-Meteo-Re-Distributionen desselben Verteilers:
- `src/services/radar_service.py:245-247` (`_fetch_arome_france_hd`) ruft
  `api.open-meteo.com/v1/forecast?models=arome_france_hd` — nicht Météo-France direkt.
- `src/services/radar_service.py:249-251` (`_fetch_icon_d2`) ruft
  `api.open-meteo.com/v1/forecast?models=icon_d2` — nicht DWD direkt.
- `src/providers/openmeteo.py` `REGIONAL_MODELS` (Z. 103-144) sind alle Endpoints unter
  `api.open-meteo.com` — auch das ist Open-Meteo als Verteiler, nicht die Originalquelle.

Das heißt: **#1127 ist tatsächlich Neuland**, kein Umverdrahten bestehender Direktanbindungen — mit
Ausnahme von GeoSphere AT (dort existiert eine echte Direktanbindung, s. u.) und BrightSky DE
(radar-only, echte DWD-RADOLAN-Direktanbindung über einen Drittanbieter-Spiegel).

## Bestandsaufnahme je Region (verifiziert im Code)

### Frankreich — Météo-France

| Was | Status |
|---|---|
| API-Key | `GZ_METEOFRANCE_APIKEY` existiert, gültig bis 2027-07-06 (Issue #1043) |
| Genutzt für | **Nur** amtliche Warnungen: `src/services/official_alerts/vigilance.py:88` (Vigilance) und `src/services/official_alerts/meteo_forets.py:77` (Waldbrand). Auth-Schema: einfacher `apikey`-Header (`headers={"apikey": key}`, `vigilance.py:90`), **kein** OAuth2, wie ein früherer Issue-Kommentar (#1041) vermutete. |
| Forecast/NWP-Anbindung | **Existiert nicht.** Kein `fetch_forecast`-Äquivalent gegen Météo-France. |
| Offene Kernfrage | Météo-France bietet Vigilance/Forêts über einfache REST/JSON-Endpoints unter `public-api.meteofrance.fr`. Das NWP-Produkt (AROME/ARPEGE Rohdaten) ist auf demselben Portal, aber **typischerweise ein separates API-Produkt** (oft GRIB2-Gitterdaten, nicht simples JSON) — ob der bestehende Schlüssel dieses Produkt bereits freigeschaltet hat, ist **ungeklärt** und nicht im Code verifizierbar (reine Portal-Konfiguration). Muss zu Beginn von Slice FR primär geklärt werden. |

### Deutschland — DWD

| Was | Status |
|---|---|
| `src/providers/brightsky.py` | Liefert **ausschließlich** RADOLAN-**Radar**-Nowcast (`fetch_radar()`, Z. 55-123) über die BrightSky-API (`api.brightsky.dev`, DWD-Datenspiegel, echte DWD-Quelle, aber kein Forecast). **Kein `fetch_forecast()`** — implementiert nicht das `WeatherProvider`-Protocol (`src/providers/base.py:41-64`). Bestätigt PO-Intake-Befund. |
| Coverage-Bounds (Radar) | Bereits vorhanden: `_RADOLAN_LAT_MIN/MAX/LON_MIN/MAX` (Z. 26-29) — RADOLAN-Domäne, **nicht** notwendig identisch mit einer künftigen DWD-Forecast-Domäne. |
| DWD-Forecast (MOSMIX/ICON-D2 Open Data) | **Nichts vorhanden.** `docs/reference/decision_matrix.md` erwähnt MOSMIX als Konzept, ist aber ein **veraltetes Dokument** aus einer früheren Architektur-Phase (referenziert MET Norway als Standard-Provider — das gibt es im aktuellen Provider-Set nicht mehr: `src/providers/__init__.py` registriert nur `geosphere`, `openmeteo`, `brightsky`). Für Slice DE ist eine **neue** Quellenentscheidung nötig (MOSMIX-KMZ/CSV vs. ICON-D2-Rohdaten via `opendata.dwd.de`, beide GRIB/CSV-basiert, keine einfache JSON-API wie Open-Meteo). |
| Fazit | **Größte Lücke des Epics** — DWD-Forecast muss komplett neu gebaut werden, inkl. Parser für ein Rohformat, das (anders als Open-Meteo/GeoSphere) nicht bereits JSON ist. |

### Österreich/Alpen — GeoSphere

| Was | Status |
|---|---|
| `src/providers/geosphere.py` | Implementiert `WeatherProvider`-Protocol vollständig (`fetch_forecast`, Z. 172-208) gegen die echte GeoSphere-API (`dataset.api.hub.geosphere.at`, Z. 48) — **echte** Direktanbindung, kein Verteiler-Umweg. |
| Coverage-Bounds | **Fehlen.** `fetch_forecast`/`fetch_nwp_forecast` prüft lat/lon **nicht** gegen eine AROME-Datenraum-Grenze — jede Koordinate wird ungeprüft an die API geschickt (Verhalten bei Koordinaten außerhalb der GeoSphere-Domäne unbekannt: vermutlich API-seitiger 4xx/leere Antwort, nicht im Code abgefangen). Bestätigt PO-Befund. |
| `enrich_ensemble` | Wird als Parameter akzeptiert, aber bewusst **ignoriert** (Z. 177: `# ignored, GeoSphere has no ensemble support`) — GeoSphere hat schlicht keine Ensemble-API. **Korrektur zum PO-Intake-Befund:** Issue #288 ist ein **anderes, bereits geschlossenes** Issue (Drosselung der Open-Meteo-Ensemble-Call-Frequenz auf 1×/Tag, deployt) — es hat **nichts** mit GeoSphere zu tun. Die Doku-Referenz auf „#288" im Issue #1127 ist ein Fehlzitat; es gibt aktuell **kein** offenes Issue zu „GeoSphere sollte Ensemble unterstützen". Sollte aus der Formulierung des Folge-Slices entfernt werden. |
| **Versteckte Open-Meteo-Abhängigkeit (kritischer Fund):** `fetch_combined()` (Z. 406-458) reichert das AROME-Ergebnis standardmäßig (`include_cloud_layers=True`) über `_fetch_openmeteo_clouds()` (Z. 331-390) mit Wolkenschichten **direkt von `api.open-meteo.com`** an — genau die Infrastruktur, die im Total-Ausfall-Fall nicht erreichbar ist. Fail-soft (Exception → leeres Dict, Z. 388-390), also kein Crash, aber im Ausfallmodus faktisch nutzlos und ein Widerspruch zum Epic-Ziel „infrastruktur-unabhängig". | Muss für Slice AT gelöst werden: `include_cloud_layers=False` im Fallback-Pfad, oder alternative Quelle. |

## Gemeinsamer Unterbau (verifiziert)

- **Datenformat:** `NormalizedTimeseries` (`meta: ForecastMeta` + `data: List[ForecastDataPoint]`,
  `src/app/models.py:74-156`). Jeder neue Provider normalisiert darauf — Pflicht, kein Spielraum.
- **Protocol:** `WeatherProvider` (`src/providers/base.py:18-64`) — `name`-Property +
  `fetch_forecast(location, start, end, enrich_ensemble)`.
- **Registry:** `get_provider(name)` (`src/providers/base.py:110-146`), Provider werden in
  `_load_providers()` (Z. 149-172) lazy registriert. **7 Aufrufstellen** rufen aktuell hart
  `get_provider("openmeteo")` — der DRY-Ansatz für #1127 ist ein **einziger Einhängepunkt** in
  dieser Fabrik (oder ein neuer `get_resilient_provider()`), nicht 7 Einzel-Patches.
- **Nicht-Kaschieren-Fundament aus #1115 (ADR-0018), wiederverwendbar:**
  - `ProviderRequestError.status_code` (`base.py:82-94`) unterscheidet 4xx (Inhaltsfehler, kein
    Ausweichen) von 5xx/Timeout (Ausweichen erlaubt) — dieselbe Regel gilt für #1127.
  - `ForecastMeta.fallback_model` / `fallback_reason` (`app/models.py:83-88`) — für #1127 braucht es
    einen **neuen** `fallback_reason`-Wert (z. B. `"cross_provider_total_outage"`), der sich von
    `"model_5xx"`/`"metric_gap"` unterscheidet.
  - `internal/scheduler/briefing_health.go` — `provider_error_streak_since` /
    `provider_errors_recent_count` (Z. 100-114) zählen bereits **jeden** 5xx/Timeout-Fehler auf den
    Kernquellen `briefing`/`briefing_nacht` (`coreBriefingSources`, Z. 27-30) — das schließt auch
    den Fall „alle Open-Meteo-Modelle erschöpft" ein (dieser Fall erzeugt am Ende ebenfalls einen
    geloggten 5xx/Fehler, bevor `fetch_forecast` die `ProviderRequestError` weiterreicht,
    `openmeteo.py:851-853`). Für #1127 wird dasselbe Signal genutzt — es braucht **keine neue
    Go-Metrik**, wenn der Cross-Provider-Fallback erfolgreich zustellt, aber weiterhin markiert.
    Falls der PO eine **härtere Eskalationsstufe** für „auch der Direkt-Provider ist ausgefallen"
    wünscht (Totalausfall aller Quellen), ist das ein bewusster Zusatz-Scope, kein Bestandteil des
    heutigen Signals — siehe Offene Fragen.
- **Auslöse-Punkt für Total-Ausfall:** `OpenMeteoProvider.fetch_forecast` (`openmeteo.py:748ff`)
  iteriert `candidates` (alle `REGIONAL_MODELS`, die die Koordinate abdecken, inkl. globalem
  ECMWF) und wirft erst dann `last_error` weiter (Z. 850-853: `if response_data is None: raise
  last_error`), wenn **alle** Kandidaten mit 5xx/Timeout gescheitert sind. **Das ist exakt der
  Total-Ausfall-Moment**, an dem #1127 einhängen muss — nicht früher (sonst würde #1115 durch
  #1127 unterlaufen: Quell-Roulette statt geordneter Modell-Fallback zuerst).

## Slice-Schnitt

Der vom PO vorgeschlagene 4er-Schnitt ist im Kern richtig, wird aber an zwei Stellen verfeinert:
(1) Slice 0 wird bewusst **klein** gehalten (Routing + Einhänge-Punkt + Marker, ohne eigene
Netzwerk-Calls) — die Direktanbieter-Anbindungen selbst wandern vollständig in die Regions-Slices,
sonst sprengt Slice 0 das 5-Dateien/250-LoC-Limit (Routing-Logik + Registry-Umbau an 7 Aufrufstellen
+ Go-Health-Erweiterung wäre in Summe zu groß für einen Slice). (2) Die AT-Cloud-Abhängigkeit
(`_fetch_openmeteo_clouds`) wird explizit Teil von Slice AT, sonst bleibt die „Direktanbindung"
GeoSphere heimlich von Open-Meteo abhängig — das würde das Epic-Ziel unterlaufen.

| Slice | Vorschlag Issue-Titel | Inhalt | Abhängigkeit | Größe |
|---|---|---|---|---|
| 0 | „Cross-Provider-Fallback: Routing-Unterbau + Total-Ausfall-Erkennung" | Coverage-Bounds-Routing-Tabelle (Region → Provider-Klasse), ein zentraler Einhänge-Punkt (Registry/Factory statt 7 Einzelstellen), neuer `fallback_reason`-Wert, Renderer-Anpassung `plain.py` für den neuen Marker-Fall, Stub-Direktprovider (wirft strukturierten „noch nicht implementiert"-Fehler pro Region) | #1115 (fundamental) | 4-5 Dateien, ~150-200 LoC |
| FR | „Météo-France direkt für Frankreich-Totalausfall" | Echte NWP-Anbindung gegen Météo-France (Endpoint-Klärung als erster Schritt), Normalisierung auf `NormalizedTimeseries`, Coverage-Bounds FR, Anschluss an Slice-0-Registry | Slice 0; Klärung Portal-Produktzugang | abhängig von API-Format, ggf. 2 Slices nötig (s. Risiken) |
| DE | „DWD direkt für Deutschland-Totalausfall" | Neue DWD-Forecast-Quelle (MOSMIX oder ICON-D2 Open Data), Parser für Rohformat, Coverage-Bounds DE, Anschluss an Slice-0-Registry | Slice 0; Quellenentscheidung MOSMIX vs. ICON-D2-OpenData (siehe Offene Fragen) | größte Unbekannte — ggf. eigener Mini-Spike vor Spec |
| AT | „GeoSphere-Direktfallback vervollständigen (AT/Alpen)" | Coverage-Bounds für GeoSphere ergänzen, `include_cloud_layers=False` im Fallback-Modus (keine versteckte Open-Meteo-Abhängigkeit), Anschluss an Slice-0-Registry | Slice 0 | kleinster Slice — Anbindung existiert bereits |

**Reihenfolge-Empfehlung:** 0 → AT → FR → DE.
- **AT vor FR/DE**, weil die Direktanbindung dort bereits existiert (kleinstes Risiko, beweist die
  Slice-0-Registry end-to-end mit echten Daten, keine Blocker durch API-Zugriffsfragen).
- **FR vor DE**, weil der Météo-France-Schlüssel bereits existiert (kein neuer Registrierungs-Weg
  nötig) — auch wenn das NWP-Produkt-Scope noch zu klären ist, ist der Startpunkt (Account
  vorhanden) besser als DE, wo noch nicht einmal die Quellenart (MOSMIX vs. ICON-D2 Open Data)
  entschieden ist.
- **DE zuletzt**, weil dort die größte technische Unbekannte liegt (kein JSON-API, sondern
  Rohformat-Parsing) und die aktuelle Radar-only-BrightSky-Anbindung zusätzlich zeigt, dass es für
  DWD **keine** bestehende Forecast-Code-Basis zum Ausbauen gibt.

## Use-Cases (JTBD)

1. **„Als Weitwanderer will ich auch bei komplettem Open-Meteo-Ausfall mein planmäßiges Briefing
   bekommen"** — wenn Open-Meteo als Verteiler insgesamt nicht erreichbar ist, weicht das System für
   die Region der Etappe (FR/DE/AT) automatisch auf den Original-Wetterdienst aus, statt das Segment
   als fehlerhaft zu markieren.
2. **„Als Product Owner will ich, dass ein Ausweichen sichtbar bleibt"** — jedes Cross-Provider-
   Ausweichen wird im Briefing markiert (Footer-Hinweis analog #1115) und erzeugt/verlängert dasselbe
   wachsende Health-Signal wie ein Intra-Open-Meteo-Fallback — kein „grün", das einen andauernden
   Zustand verdeckt.
3. **„Als Betreiber will ich wissen, wenn selbst der Direktanbieter ausfällt"** — fällt für eine
   Region sowohl Open-Meteo (alle Modelle) **als auch** der direkte Original-Dienst aus, muss das
   Segment weiterhin sichtbar als fehlerhaft markiert werden (kein drittes stilles Ausweichen) und
   das bestehende Eskalationssignal darf dadurch **nicht** zurückgesetzt werden.

   **PO-Entscheidung (2026-07-08):** KEIN neuer, paralleler Eskalations-Mechanismus. Der
   Totalausfall aller Quellen speist in die **bereits etablierte Alarmkette** ein — dasselbe
   `provider_error_streak`-Signal, das heute Telegram-Benachrichtigung, BetterStack-Monitoring und
   den MQ-Weg (Auto-Healing) auslöst. Slice 0 stellt nur sicher, dass der „auch Direktanbieter tot"-
   Fall dieses bestehende Signal **weiter füttert** (nicht zurücksetzt), statt eine eigene Stufe zu
   bauen. Damit ist die offene Frage 8 (unten) entschieden.

## ACs-Entwurf (Rohfassung, PO verfeinert final in `/3-write-spec` je Slice)

### Slice 0 — Routing-Unterbau

- **AC-1:** Given Open-Meteo hat für eine Koordinate alle abdeckenden Modelle (inkl. globalem
  ECMWF) mit 5xx/Timeout erschöpft, When `fetch_forecast` aufgerufen wird, Then wird statt der
  bisherigen `ProviderRequestError`-Weitergabe die Region der Koordinate bestimmt und ein
  registrierter Direkt-Provider für diese Region aufgerufen.
- **AC-2:** Given keine Region-Zuordnung existiert für die Koordinate (z. B. außerhalb FR/DE/AT),
  When der Total-Ausfall-Fall eintritt, Then wird weiterhin die ursprüngliche `ProviderRequestError`
  geworfen (kein Verhaltensbruch außerhalb der drei abgedeckten Regionen).
- **AC-3:** Given ein Direkt-Provider hat erfolgreich geliefert, When das Ergebnis zurückgegeben
  wird, Then trägt `ForecastMeta.fallback_reason` den Wert `"cross_provider_total_outage"` und
  `fallback_model` den Namen des tatsächlich genutzten Direkt-Providers.
- **AC-4:** Given ein Cross-Provider-Fallback wurde ausgelöst, When die Plain-Text-Mail gerendert
  wird, Then erscheint ein Fallback-Hinweis im Footer, der auch bei leerer `fallback_metrics`-Liste
  lesbar bleibt (kein „Fallback : ..." mit führendem Doppelpunkt-Artefakt).
- **AC-5:** Given ein Direkt-Provider für eine Region ist noch nicht implementiert (Stub), When der
  Total-Ausfall-Fall für diese Region eintritt, Then wird die ursprüngliche `ProviderRequestError`
  unverändert weitergereicht (kein Crash durch den Stub selbst).

### Slice FR/DE/AT (gemeinsames Muster je Region, Platzhalter `<REGION>`/`<PROVIDER>`)

- **AC-1:** Given eine Koordinate liegt innerhalb der Coverage-Bounds von `<PROVIDER>`, When
  `<PROVIDER>.fetch_forecast` aufgerufen wird, Then liefert die Antwort ein valides
  `NormalizedTimeseries` mit befüllten Basis-Feldern (mind. `t2m_c`, `wind10m_kmh`,
  `precip_1h_mm`, `symbol`).
- **AC-2:** Given eine Koordinate liegt außerhalb der Coverage-Bounds von `<PROVIDER>`, When die
  Slice-0-Registry für diese Koordinate aufgerufen wird, Then wird `<PROVIDER>` **nicht** als
  Kandidat gewählt (kein Fehlversuch gegen eine offensichtlich falsche Region).
- **AC-3:** Given `<PROVIDER>` antwortet mit einem 4xx (Inhaltsfehler), When der Aufruf erfolgt,
  Then wird der Fehler sichtbar durchgereicht (kein weiteres, drittes Ausweichen).
- **AC-4 (nur AT):** Given der Cross-Provider-Fallback-Modus ist aktiv, When GeoSphere
  `fetch_combined` aufruft, Then wird `include_cloud_layers=False` erzwungen (keine versteckte
  Open-Meteo-Abhängigkeit im Ausfallmodus).
- **AC-5:** Given `<PROVIDER>` selbst mit 5xx/Timeout fehlschlägt (Direktanbieter ebenfalls down),
  When das Segment verarbeitet wird, Then bleibt das bestehende Fehler-Markierungs-Verhalten
  (`has_error`-Platzhalter) unverändert bestehen — kein drittes stilles Ausweichen.

## Offene Fragen / Risiken

1. **Météo-France NWP-Produktzugang ungeklärt.** Der vorhandene Schlüssel deckt nachweislich nur
   Vigilance/Forêts ab (`vigilance.py`, `meteo_forets.py`). Ob das NWP/AROME-Rohdatenprodukt separat
   freigeschaltet werden muss (Portal-seitig, außerhalb des Codes), ist der **erste** zu klärende
   Punkt vor jeder Implementierung in Slice FR — sonst läuft die Analyse-Phase ins Leere.
2. **DWD-Quellenentscheidung (MOSMIX vs. ICON-D2 Open Data).** `docs/reference/decision_matrix.md`
   ist veraltet (referenziert eine nicht mehr existierende MET-Norway-Standardauswahl) und liefert
   keine verwertbare Vorentscheidung für #1127. Beide DWD-Rohquellen sind GRIB/CSV/KMZ-basiert, kein
   JSON wie Open-Meteo/GeoSphere — Parser-Aufwand ist die größte Unbekannte des ganzen Epics.
3. **Coverage-Bounds sind uneinheitlich zwischen bestehenden Domänen.** Es existieren **drei**
   verschiedene Bounds-Sätze für „Frankreich" im Code (`radar_service._AROME_FR_*`:
   41-51.5N/-5.5-10E; `openmeteo.REGIONAL_MODELS["meteofrance_arome"]`: 38-53N/-8-10E) — beide sind
   *Modell*-Domänen, keine „welches Land ist das"-Grenze. Für die Total-Ausfall-Region-Zuordnung in
   Slice 0 braucht es eine **eigene, bewusst gewählte** Grenze (grobes Land/Alpen-Rechteck), nicht
   blindes Kopieren einer der bestehenden Modell-Bounds.
4. **GeoSphere-Domänegrenzen unbekannt.** Weder Code noch Doku benennen die tatsächliche
   AROME-Datenraumgrenze der GeoSphere-API — muss über echte Grenzwert-Calls (innerhalb/außerhalb
   Österreich) in Slice AT empirisch bestimmt werden (Muster: `openmeteo.py`-Kommentar Z. 147-150,
   „Empirisch ... echte Diagnose-Calls").
5. **Test-Strategie ohne Mocks — echte API-Calls Pflicht.** Für alle drei Regions-Slices müssen
   AC-Tests gegen die **echten** Original-APIs laufen (kein `Mock()`/`patch()`). Für Slice 0 (Routing
   + Total-Ausfall-Erkennung) ist der bereits etablierte Musteransatz aus
   `tests/tdd/test_issue_1115_model_fallback.py` reproduzierbar: echter lokaler
   `ThreadingHTTPServer`, `monkeypatch.setattr("providers.openmeteo.BASE_HOST", ...)` auf
   `http://127.0.0.1:<port>` — alle Kandidaten-Endpoints liefern 503, um den Total-Ausfall-Pfad ohne
   echten Incident zu erzwingen. Für die Regions-Slices selbst müssen Tests dagegen **echt** gegen
   Météo-France/DWD/GeoSphere gehen (Rate-Limit-Risiko, Flakiness — insbesondere Météo-France, falls
   das NWP-Produkt strengere Kontingente als Vigilance hat).
6. **Fehlzitat im Ursprungs-Issue (#1127-Body): „ignoriert `enrich_ensemble` (#288)".** #288 ist ein
   geschlossenes, **anderes** Issue (Ensemble-Call-Frequenz-Drosselung bei Open-Meteo). Es gibt
   aktuell **kein** Issue, das GeoSphere-Ensemble-Unterstützung fordert — sollte aus der finalen
   Slice-AT-Formulierung entfernt werden, um keine Phantom-Abhängigkeit zu erzeugen.
7. **Nebenbefund (nicht Teil dieses Epics, eigenes Follow-up-Issue empfohlen):** Der bestehende
   Footer-Renderer `src/output/renderers/email/plain.py:288` erzeugt bereits **heute** bei einem
   reinen `model_5xx`-Fallback (leere `fallback_metrics`) die Zeile `"Fallback : icon_eu"` (führender
   Doppelpunkt ohne Inhalt davor) — ein kosmetischer Bug aus #1115, unabhängig von #1127. Sollte als
   eigenes kleines Bug-Issue nachgereicht werden, nicht in #1127 mitgelöst.
8. **~~Eskalationsstufe bei Totalausfall aller Quellen~~ — ENTSCHIEDEN (PO, 2026-07-08).** Keine
   eigene, härtere Stufe. Der Fall „auch der Direktanbieter ist ausgefallen" speist in die
   **bestehende Alarmkette** (Telegram + BetterStack + MQ-Auto-Healing) über das vorhandene
   `provider_error_streak`-Signal ein. Slice 0 muss nur garantieren, dass dieses Signal im
   Totalausfall-Fall **weiter gefüttert und nicht zurückgesetzt** wird (siehe Use-Case 3). Kein neuer
   Mechanismus, kein neuer Scope.

## STOP-Bedingungen (an PO)

- **DWD-Quellenentscheidung ist eine eigene fachliche Weichenstellung**, keine reine
  Implementierungsdetail-Frage — MOSMIX (Stationsdaten, kein Gitter) vs. ICON-D2 Open Data
  (Gitterdaten, näher am heutigen Modell-Konzept) haben unterschiedliche Aufwände und
  Metrik-Vollständigkeit. Empfehlung: vor Freigabe von Slice DE einen kurzen Analyse-Spike
  (`/2-analyse`) nur für diese Quellenfrage, bevor die Spec geschrieben wird.
- **Météo-France-Portal-Produktzugang** ist außerhalb des Codes und außerhalb dieser
  Planungs-Session zu klären (Portal-Konto-Konfiguration) — Slice FR sollte **nicht** freigegeben
  werden, bevor diese Zugangsfrage beantwortet ist, sonst läuft die TDD-RED-Phase ins Leere.
- **Slice-0-Größe:** Sollte sich beim Spec-Schreiben zeigen, dass Registry-Umbau (7 Aufrufstellen)
  + Renderer-Fix + neuer `fallback_reason`-Wert das 250-LoC-Limit reißen, ist ein weiterer Schnitt
  (z. B. Registry-Umbau separat von Renderer-Fix) dem LoC-Override vorzuziehen.

## Sub-Issues (angelegt 2026-07-08, PO-freigegeben)

| # | Slice | Reihenfolge | Status |
|---|---|---|---|
| #1141 | Routing-Unterbau + Total-Ausfall-Erkennung (Slice 0) | 1 (Fundament) | ✅ implementiert (2026-07-09) |
| #1142 | GeoSphere-Direktfallback vervollständigen (Slice AT) | 2 | offen |
| #1143 | Météo-France direkt (Slice FR) — Portal-Zugang zuerst klären | 3 | offen |
| #1144 | DWD direkt (Slice DE) — Quellenentscheidung MOSMIX vs. ICON-D2 vorab | 4 | offen |
| #1145 | (Follow-up, unabhängig) Footer-Doppelpunkt-Artefakt aus #1115 | — | offen |

### Slice 0 (#1141) — Implementierungsstand (2026-07-09)

Liefert **nur den Unterbau** — echte Provider-Anbindungen folgen in #1142 (AT)/#1143 (FR)/#1144 (DE):

- **NEU `src/providers/region_routing.py`:** `direct_provider_for(lat, lon)` — bewusst gewählte
  Land/Alpen-Rechtecke für AT/DE/FR (Prüfreihenfolge AT→DE→FR), s. Offene Frage 3 oben.
- **NEU `src/providers/regional_stubs.py`:** `RegionalStubProvider`, registriert als
  `at_direct`/`de_direct`/`fr_direct`, wirft `ProviderNotImplementedError` (AC-5) — kein Crash,
  solange die echten Provider aus #1142-#1144 fehlen.
- **`src/providers/base.py`:** neue Exception `ProviderNotImplementedError`.
- **`src/providers/openmeteo.py:864`:** Einhängepunkt im Total-Ausfall-Fall (alle Modelle inkl.
  ECMWF erschöpft) — bestimmt die Region und ruft den Direkt-Provider auf; neuer
  `fallback_reason="cross_provider_total_outage"` (AC-3), s. auch Offene Frage 3.
- **`src/output/renderers/email/plain.py`:** Footer-Fix für leere `fallback_metrics` (AC-4).
