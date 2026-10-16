---
entity_id: avalanche_report_bulletin
type: feature
created: 2026-10-13
updated: 2026-10-14
status: draft
version: "1.2"
tags: [official_alerts, avalanche, eaws, avalanche-report, sms, telegram, premium-sms, email, egress, wintersport]
workflow: feat-1441-s1-lawinenlagebericht
---

# Amtlicher Lawinen-Lagebericht (avalanche.report, EAWS-Stufe 1-5)

## Approval

- [ ] Approved

## Purpose

Der amtliche Lawinen-Lagebericht der Lawinenwarndienste (EAWS-Gefahrenstufe 1-5 mit Höhengrenze und
Lawinenproblem) ist für Weitwanderer im Winter und Frühjahr die zentrale Sicherheitsinformation,
fehlt der App aber bisher; MeteoAlarm liefert nur eine grobe Awareness-Stufe 1-4. Diese Spec führt den
Lagebericht als neue amtliche Warnquelle mit eigener Gefahrenart `avalanche_bulletin` ein (Issue
#1441 Slice 1, Epic #2258), zeigt Stufe und Wortlaut des Warndienstes unverändert in allen vier Kanälen
(E-Mail, Telegram, SMS, Premium-SMS) und erledigt damit zugleich den SMS-Token `AV` aus #1473.

## Source

- **File:** `src/services/official_alerts/avalanche_report.py` (neu) — Quelle `AvalancheReportSource`
- **File:** `src/services/official_alerts/region_mapper.py` (neu) — generischer Punkt-in-Region-Mapper
- **File:** `src/services/official_alerts/models.py` — `OfficialAlert` (additive Felder)
- **File:** `src/output/renderers/alert/official_alerts.py` — Stufen-Renderstellen, Eskalation
- **Identifier:** `AvalancheReportSource`, `RegionMapper`, `OfficialAlert`, `_wintersport`

**Schicht:** ausschließlich Python-Core (`src/services/`, `src/output/`, `src/app/egress_guard.py`)
plus die Go-Egress-Liste `internal/egress/inventory.go` (nur Host-Eintrag, Drift-Test). Kein neuer
Endpoint, kein Frontend-Code, keine Persistenzänderung (`OfficialAlert` wird nirgends serialisiert).

## Datenquellen-Antrag (PENDING — wird mit Spec-Freigabe genehmigt)

Nach `docs/specs/data_sources.md` ("Prozess für neue Datenquellen") ist vor der Implementierung ein
Antrag mit Genehmigung durch Henning nötig. Die Freigabe dieser Spec gilt als Genehmigung; der Eintrag
in `data_sources.md` ist Teil der Umsetzung (siehe Affected Files).

| Punkt | Inhalt |
|-------|--------|
| Quelle | Lawinenlagebericht der Euregio Tirol-Südtirol-Trentino und des Lawinenwarndienstes Kärnten über `avalanche.report` (Format CAAML v6, JSON) |
| Hosts | `static.avalanche.report` (Bulletin-Dateien; leitet per 301 auf `avalanche.report` weiter) und `avalanche.report` (Weiterleitungsziel, Bulletin-Link). Nur diese zwei Hosts kommen ins Egress-Inventar. |
| Abdeckung Slice 1 | Tirol (AT-07), Südtirol (IT-32-BZ), Trentino (IT-32-TN), Kärnten (AT-02). **PO-Entscheid 2026-10-13 ("Belegte zuerst").** Salzburg, Bayern und übrige österreichische Länder sind nicht Teil von Slice 1 (Lizenz der dortigen Dienste nicht belegt); sie werden nach Lizenzzusage per Konfigurationseintrag freigeschaltet. |
| Lizenz Bulletins | CC BY 4.0 — Namensnennung und Link zur Quelle sind Pflicht und stehen in Mail und Telegram-Vollform (Quellenname + Bulletin-URL); SMS und Telegram-Kurzstil (= SMS-Text) ohne |
| Lizenz Regionen-Geometrie | CC0 (EAWS-Regions, `regions.avalanches.org`, nur `latest/`); vier GeoJSON-Dateien werden eingecheckt, kein Laufzeitabruf |
| Zugang | Kein Schlüssel, kein veröffentlichtes Limit; statische Dateien mit ETag; Abruf nur über `cached_fetch` (TTL 1800 s) |
| Nicht beantragt | `lawinen-warnung.eu`, EU-Sammelfeed `eaws_bulletins`, SLF (Schweiz, Slice 2) |

## Estimated Scope

- **LoC:** ca. +400 bis +540 / -20 (produktiv), `loc_limit_override 500` ist gesetzt
- **Files:** 15 produktiv/Daten, 8 Testdateien plus Fixtures
- **Effort:** high (Haftungsrelevanz, Zustandslogik, außerhalb der Saison kein Live-Nachweis)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `warn_egress.cached_fetch` | Modul | Abruf mit TTL (1800 s ok / 60 s Fehler), Call-Log, 429-Backoff, single-flight |
| `OfficialAlertSource` (`base.py`) | Protokoll | `name`, `covers`, `fetch`; Registrierung in `__init__.py` (ADR-0016) |
| `get_official_alerts_with_status` | Modul | Fail-soft/`unavailable`, Zusammenführen je Gefahrenart (`base.py:209-232`) |
| `geo_ray_cast._point_in_ring` | Modul | Point-in-Polygon (einzige Implementierung, Mapper baut darauf auf) |
| `tz_for_coords` / `local_dt` | Modul | Ortszeit für Gültigkeitsprüfung (ADR-0044) |
| `egress_guard.py`, `internal/egress/inventory.go` | Modul | Host-Inventar Python + Go, Drift-Test `test_egress_inventory_drift.py` |
| `hazard_symbols.py` | Modul | Kürzel, Bedeutung DE/EN, Reihenfolge der neuen Gefahrenart |
| `alert_urgency.py` | Modul | Dringlichkeit aus amtlicher Stufe |
| `tokens/builder.py` (`_official_alerts`, `_wintersport`) | Modul | SMS-Token `AV<Ziffer>` |
| `compare_html._ALERT_LEVEL_CELL` | Modul | Ortsvergleich-Chip |
| ADR-0016, 0018, 0041, 0044 | ADR | additiver Warntyp, fail-soft ohne Maskierung, Zuständigkeitsmuster, Ortszeit |
| `fix_1430_meteoalarm_lawine` (Spec) | Spec | MeteoAlarm-Gefahrenart `avalanche` (Kürzel `AW`) bleibt unverändert daneben bestehen |
| #1473 | Issue | Token `AV` — wird mit diesem Slice erledigt |

## Implementation Details

### 1. Quelle und Konfigurationstabelle

`AvalancheReportSource` registriert sich in `official_alerts/__init__.py`. Eine Konfigurationstabelle
(Region-Kennung → URL-Muster `https://static.avalanche.report/bulletins/latest/{X}_de_CAAMLv6.json`,
Regionsdatei, Anzeigename) enthält in Slice 1 genau vier Einträge: `AT-07`, `IT-32-BZ`, `IT-32-TN`,
`AT-02`. Ein weiteres Land wird später durch einen weiteren Tabelleneintrag plus Regionsdatei und
Egress-Host freigeschaltet, ohne Codeänderung an Parser oder Renderern. `covers(lat, lon)` prüft nur die
Bounding-Boxen der Tabelleneinträge; ein Punkt außerhalb löst weder Abruf noch Hinweis "nicht abrufbar"
aus (ADR-0041, `mark_not_covered`).

### 2. Parser (CAAML v6)

Pro Bulletin und getroffener Mikroregion: `mainValue` low/moderate/considerable/high/very_high wird auf
1-5 abgebildet. Die Höhengrenze (`elevation.lowerBound`/`upperBound`) ist entweder eine Zahl oder die
Zeichenkette `treeline`; beides wird verarbeitet, `treeline` erscheint wörtlich als "Waldgrenze". Tageszeit
`all_day`/`earlier`/`later`. Gemeldet wird je Bulletin und Region **ein** Alert mit der höchsten Stufe
des Bulletins und der Höhenangabe des Ratings, das sie trägt; die Tageszeit steht nur dann als Zusatz,
wenn Vor- und Nachmittag verschiedene Stufen haben. Lawinenprobleme (`problemType`) werden als
CAAML-Codes (inklusive `no_distinct_avalanche_problem`, `favourable_situation`, `cornices`) mitgeführt.

### 3. Modell (`OfficialAlert`, additiv)

Optionale Felder mit Defaults, die den Bestand unverändert lassen: `scale` (Bestand: Awareness 1-4;
neu: `eaws`), `native_level` (1-5), Höhenangabe (Wert + Richtung oberhalb/unterhalb, wörtlich inkl.
`Waldgrenze`), `problems` (Tupel), `time_of_day`. `level` bleibt Pflichtfeld und wird für
`avalanche_bulletin` nur für die Farbe abgeleitet (1 → 1, 2 → 2, 3 → 3, 4 und 5 → 4).
**Abweichung vom PO-Kommentar in #1441, begründet:** die toten DTOs `AvalancheDanger`/
`AvalancheProblemInfo`/`AvalancheReport` in `src/app/models.py` werden nicht wiederbelebt (anderes
Modul, unvollständige Problem-Enum, nirgends verdrahtet, einziger Nutzer `tests/test_models.py`); das Ziel
(Stufe 1-5, Höhe, Problem) trägt `OfficialAlert`. Ein Feld `avalanche_level` an
`SegmentWeatherSummary` o. Ä. ist **nicht** nötig (siehe Abschnitt 6).

### 4. Eigene Gefahrenart `avalanche_bulletin`

Neben die MeteoAlarm-Gefahrenart `avalanche` (Awareness 1-4, Kürzel `AW`) tritt `avalanche_bulletin`
(EAWS 1-5). **Bewusste Doppelung:** zwei amtliche Aussagen auf zwei Skalen dürfen parallel erscheinen; die
Zusammenführung "höchste Stufe gewinnt" (`base.py:209-232`) vergleicht nie über Skalen hinweg. Eintrag
in `_HAZARD_LABELS`, `HAZARD_SMS_SYMBOLS` (Kürzel `AV`, in der Sortierung direkt hinter `avalanche`),
`HAZARD_BEDEUTUNG_EN/_DE`. Die Kollisionsprüfung aus `fix_1430` (`AV` ist für die Lawinenstufe reserviert)
bleibt gültig: `AV` ist die Lawinenstufe, `AW` die MeteoAlarm-Warnung.

### 5. Zustände, TTL und Gültigkeit

Drei Zustände ohne neues Flag:
- **nicht abrufbar** = Fetch-Fehler (Netz, 5xx): `unavailable` wie bisher, Hinweis wird gezeigt.
- **kein aktueller Bericht** = HTTP 404 oder `validTime.endTime` liegt vor jetzt (Ortszeit, ADR-0044;
  Euregio liefert außerhalb der Saison HTTP 200 mit dem Bulletin vom 2026-05-02): leere Ergebnisliste,
  **kein** "nicht abrufbar". 404 darf nicht in `not_covered_statuses` stehen, weil dort die 24-h-TTL gilt.
  Die leere Antwort wird höchstens 1800 s gecacht (gleich der ok-TTL), damit ein neues Bulletin
  (Ausgabe täglich 17:00) nicht bis zu 24 h unsichtbar bleibt.
- **Stufe 1** = sichtbarer Alert (Info), ausdrücklich nicht "kein Bericht".
Kein sichtbarer "Saison"-Text in Slice 1.

### 6. SMS-Weg: Token `AV<Ziffer>` genau einmal (Entscheidung)

Befund im Code: `_wintersport()` (`builder.py:306-333`) erzeugt `AV` aus `day.avalanche_level`, aber nur
wenn die Metrik `AV` (`MetricSpec`) für den Nutzer/Berichtstyp sichtbar ist (`_visible`: `enabled`,
`morning_enabled`, `evening_enabled`, `threshold`). `AV` ist also **nicht immer sichtbar**; zudem
liefert der Adapter `avalanche_level=None` (`adapters/trip_result.py:81`).
**Festlegung:** `avalanche_bulletin` steht in der Briefing-SMS **ausschließlich im `!`-Block der
amtlichen Warnungen** (`_official_alerts()`, Tripel `(Kürzel, Stufenbuchstabe, Stunde)`), als Token
`AV<Originalstufe>` ohne Doppelpunkt und ohne L/M/H-Buchstaben (z. B. `!AV4`), mit der Kürzungspriorität
amtlicher Warnungen (fallen zuletzt). Damit kommt die Stufe unabhängig von der Metrik-Einstellung an
(Kanalparität). Der `AV`-Eintrag in `_wintersport()` und im Adapter bleibt unbefüllt und wird aus der
`pairs`-Liste entfernt, sodass nie zwei `AV`-Token entstehen. Das Metrik-Kürzel `AV` bleibt im Register
nur wegen Bedeutung/Priorität. Der Stufenfilter (Default ab Stufe 2) gilt wie bei allen amtlichen
Warnungen. Alarm-SMS und Premium-SMS (Pfad `send_official_alert`) zeigen Kürzel und Originalziffer
(`AV4`), keine Umdeutung nach L/M/H; `LEVEL_LETTERS` {2,3,4} und `MIN_SMS_LEVEL=3` in
`hazard_symbols.py` gelten für `avalanche_bulletin` nicht (eigene Ziffern-Darstellung).

### 7. Darstellung: jede Stufen-Renderstelle bekommt eine explizite Zuordnung für 1 und 5

Zentraler Helfer erzeugt den Text "Lawinenstufe 4 (groß) oberhalb 2200 m · Triebschnee" mit den
EAWS-Wörtern 1 gering, 2 mäßig, 3 erheblich, 4 groß, 5 sehr groß. Die Leiter "Warnstufe X · n/3" entfällt
für diese Gefahrenart. Explizite Zuordnung für 1-5 an: `_LEVEL_WORDS`, `_LEVEL_POSITION`, `_LEVEL_CLASS`,
`level_colors` (zwei Stellen), `_SMS_LEVEL_LETTERS` in `official_alerts.py`; `_ALERT_LEVEL_CELL` und
`_warn_short` in `compare_html.py` (Stufe 5 → `danger`, nicht der Default `warn`); `alert_urgency.py`
(Stufe 1 ist nicht HIGH). Nur Daten, keine Handlungsempfehlung. Stufe, Höhenangabe und Problemnamen des
Warndienstes bleiben unverändert (Haftung). `_SOURCE_LABELS` führt den Quellennamen ("Lawinenwarndienst
Tirol/Südtirol/Trentino/Kärnten, avalanche.report"); Mail (Trip-Briefing, Ortsvergleich und
eigenständige Warnungs-Mail) und Telegram in Vollform enthalten Quellenname und Bulletin-URL
`https://avalanche.report/bulletin/{YYYY-MM-DD}?region={microRegionID}` (CC BY 4.0). Telegram im
Kurzstil sendet wie bisher genau den SMS-Text (PO-Vorgabe: Kurzform folgt der SMS) und trägt daher
wie die SMS weder Quellenname noch URL.

### 8. Eskalation und Dublettenwahl

Eskalation (`official_alerts.py:487`, `:549`) und Dublettenwahl (`base.py:209-232`) vergleichen für
`avalanche_bulletin` die Originalstufe `native_level`. Stufe 4 → 5 eskaliert (abgeleitetes `level` bliebe
4). Neue Gültigkeitsperiode am Folgetag (17:00) mit gleicher Stufe löst keinen neuen Alarm aus
(`_identity_hazard_prefix`, #1685). Eine Absenkung wird in dieser Scheibe wie bei allen amtlichen
Warnungen nicht als neue Warnung gemeldet; das Melde-Gedächtnis behält den alten Höchstwert. Die
Entwarnung (Absenkung/Ende) mit der Dringlichkeit des alten Werts für alle amtlichen Warnungen liefert
Scheibe S2 von #1441 (PO-Entscheid 13.10.2026); der Helfer `urgency_from_official_transition` liegt bereit.

**Nachzug #1441 S2 (ADR-0090):** Eine Absenkung der Lawinenstufe (z. B. 4 → 2, verglichen über
`native_level`) löst jetzt eine Entwarnung über alle vier Kanäle aus, mit der Dringlichkeit der alten
Stufe; SMS-Form `+AV4>2`, bei Ende `+AV4>0`. Verschwindet der Lagebericht bei gesunder Quelle in zwei
aufeinanderfolgenden Alarm-Läufen, gilt die Warnung als vorzeitig beendet. Ablauf der Gültigkeit
(planmäßig) und Quellenausfall sind keine Entwarnung. Ein zugestelltes Briefing, das die Senkung schon
zeigte, senkt das Gedächtnis ⇒ kein Entwarnungs-Alarm. Details: `feat_1441_s2_entwarnung.md`.

### 9. RegionMapper

Neues Modul `region_mapper.py`: GeoJSON laden (fail-soft, Cache), Punkt → alle getroffenen Regionen, ein
Point-in-Polygon über `geo_ray_cast`. Trifft ein Punkt mehrere Mikroregionen (Grenzpunkt), gilt die
höchste Stufe, bei Gleichstand die kleinste Regions-ID (deterministisch). Die Dublette in
`meteoalarm.py:1008` wird auf den Mapper umgestellt; die vier Bestandskonsumenten (`dwd_zones`, `dpc`,
`massif_zones`, `department_mapper`) werden nicht migriert (vier verschiedene Trefferpolitiken,
Regressionsrisiko ohne Nutzerwert).

### 10. Egress

`static.avalanche.report` und `avalanche.report` kommen in `src/app/egress_guard.py` und
`internal/egress/inventory.go`; der Call-Log-Servicename `avalanche_report` wird in
`internal/…/warn_service_health.go` geprüft/ergänzt.

### 11. Verifikationsdesign außerhalb der Saison

Kern-Tests nutzen echte aufgezeichnete Bulletins als versionierte Fixtures (in `/40` per echtem Abruf der
datierten Dateien `.../bulletins/{D}/{D}_{X}_de_CAAMLv6.json` aufgezeichnet): ein Winter-Bulletin
(z. B. 2026-03-01) für AT-07 und AT-02, das Mai-Bulletin 2026-05-02 als "veraltet", ein 404-Fall und ein
Grenzpunkt. Sie laufen durch die echten Kanal-Renderer. Live/Staging: für einen Tirol-Punkt "sauber leer,
kein 'nicht abrufbar'". Der echte Live-Nachweis einer Stufe ab Saisonstart ist Folgebeobachtung, keine
Voraussetzung für den Deploy.

## Expected Behavior

- **Input:** Trip-Etappe, Ortsvergleichs-Ort oder Alarm-Prüfung mit Koordinaten in Tirol, Südtirol,
  Trentino oder Kärnten; aktuelles CAAML-v6-Bulletin.
- **Output:** `OfficialAlert(hazard="avalanche_bulletin", native_level=1..5, level=abgeleitet, Höhe,
  Probleme, Bulletin-URL)`; Darstellung in Trip-Briefing-Mail, Ortsvergleich-Mail, Telegram, SMS
  (`!AV<Ziffer>`), Premium-SMS und Alarm. Ohne aktuelles Bulletin: leer, ohne Hinweis.
- **Side effects:** Abrufe über `cached_fetch` (Call-Log); keine Persistenz.

## Acceptance Criteria

- **AC-1:** Given ein aufgezeichnetes Winter-Bulletin für Tirol (AT-07) mit Stufe 3 oberhalb 2200 m und
  einem Wegpunkt in einer Tiroler Mikroregion / When der Lagebericht für diesen Punkt abgerufen wird /
  Then entsteht genau ein amtlicher Alert der Gefahrenart `avalanche_bulletin` mit Originalstufe 3,
  Höhenangabe "oberhalb 2200 m", dem Lawinenproblem aus dem Bulletin und der Bulletin-URL der getroffenen Region.
  - Test: `tests/test_avalanche_report_source.py` — Fixture AT-07 (datiert) durch die echte Quelle.

- **AC-2:** Given ein Bulletin, dessen Höhengrenze statt einer Zahl den Wert `treeline` trägt, und ein
  Bulletin mit eigenem Höhensplit für den Nachmittag / When der Parser läuft / Then erscheint die
  Höhenangabe wörtlich als "Waldgrenze", es wird kein Zahlenwert erfunden, und die höchste Stufe des
  Bulletins wird mit der Höhenangabe des Ratings gemeldet, das sie trägt.
  - Test: `tests/test_avalanche_report_parser.py` — aufgezeichnete Bulletins mit Zahl, `treeline`, `later`-Split.

- **AC-3:** Given die Stufen low/moderate/considerable/high/very_high im Bulletin / When sie verarbeitet
  werden / Then entstehen die Originalstufen 1 bis 5 (5 wird nie auf 4 gequetscht) und das abgeleitete
  Farb-`level` ist 1, 2, 3, 4, 4.
  - Test: `tests/test_avalanche_report_parser.py` — je Stufe ein Bulletin-Ausschnitt aus Fixtures.

- **AC-4:** Given das Euregio-Bulletin vom 2026-05-02 (HTTP 200, `validTime.endTime` in der Vergangenheit)
  / When ein Tiroler Punkt abgefragt wird / Then ist das Ergebnis leer, es erscheint weder eine Stufe noch
  der Hinweis "amtliche Warnungen nicht abrufbar".
  - Test: `tests/test_avalanche_report_states.py` — Mai-Fixture; Assertion auf `[]` und `unavailable == False`.

- **AC-5:** Given die Antwort HTTP 404 für ein Gebiet ohne Bulletin / When abgefragt wird / Then ist das
  Ergebnis leer und kein "nicht abrufbar"; bei Netzfehler oder HTTP 5xx dagegen erscheint der Hinweis
  "nicht abrufbar" wie bei den übrigen Quellen.
  - Test: `tests/test_avalanche_report_states.py` — 404-Fixture, simulierter 5xx über die echte Abrufschicht.

- **AC-6:** Given ein leeres Ergebnis wegen 404 oder abgelaufenem Bulletin / When zwischen zwei Abrufen
  mehr als 1800 Sekunden vergehen und ein neues gültiges Bulletin ausgeliefert wird / Then erscheint die
  neue Stufe beim zweiten Abruf; die Cache-Dauer für "kein aktueller Bericht" beträgt höchstens 1800 s,
  nicht 24 Stunden.
  - Test: `tests/test_avalanche_report_states.py` — Zeitsteuerung (Uhr-Parameter), Mutation 1800 → 86400 macht den Test rot.

- **AC-7:** Given ein Punkt außerhalb der vier Regionen (z. B. Salzburg, München oder Zürich) / When die
  amtlichen Warnungen abgefragt werden / Then findet kein Abruf bei `avalanche.report` statt und es wird
  weder ein Lagebericht noch "nicht abrufbar" gemeldet.
  - Test: `tests/test_avalanche_report_coverage.py` — Egress-Guard/Call-Log zählt null Abrufe.

- **AC-8:** Given die Länderliste ist eine Konfigurationstabelle / When in einem Test ein zusätzlicher
  Eintrag samt Regionsdatei ergänzt wird / Then wird das Land abgerufen und ausgewertet, ohne dass Parser
  oder Renderer geändert werden; ohne den Eintrag bleibt es wie in AC-7 unberührt.
  - Test: `tests/test_avalanche_report_coverage.py` — Tabelle per Parameter erweitert.

- **AC-9:** Given ein Grenzpunkt, der in zwei Mikroregionen mit Stufe 2 und Stufe 4 liegt / When er
  abgefragt wird / Then wird die höchste Stufe (4) gemeldet, bei jedem Lauf gleich, mit der URL der
  Region, die diese Stufe trägt.
  - Test: `tests/test_avalanche_report_region_mapper.py` — Grenzpunkt-Fixture, mehrfach ausgeführt.

- **AC-10:** Given die MeteoAlarm-Dublette `meteoalarm.py:1008` / When der Punkt-in-Region-Test dort
  läuft / Then nutzt er den gemeinsamen `RegionMapper` und liefert für die bestehenden MeteoAlarm-Testfälle
  dieselben Treffer wie vorher.
  - Test: `tests/test_avalanche_report_region_mapper.py` und bestehende `tests/tdd/test_meteoalarm_source.py` bleiben grün.

- **AC-11:** Given zwei amtliche Warnungen am selben Ort: MeteoAlarm-Lawine (`avalanche`, Stufe 3 von 4)
  und Lagebericht (`avalanche_bulletin`, Stufe 4 von 5) / When die Warnungen zusammengeführt werden / Then
  bleiben beide als getrennte Gefahrenarten erhalten, keine verdrängt die andere, und die Stufen werden
  nie über Skalen hinweg verglichen.
  - Test: `tests/test_avalanche_report_dedup.py` — `get_official_alerts_with_status` mit beiden Quellen.

- **AC-12:** Given die zuletzt gemeldete Lawinenstufe 4 und ein neuer Bericht mit Stufe 5 / When der
  Alarm-Lauf prüft / Then wird ein Alarm ausgelöst (4 → 5 eskaliert); bei Stufe 4 → 4 in einer neuen
  Gültigkeitsperiode am Folgetag (17:00) entsteht kein neuer Alarm.
  - Test: `tests/test_avalanche_report_escalation.py` — echter Eskalationspfad (`official_alerts.py`), beide Fälle.

- **AC-13:** Given zuletzt gemeldete Stufe 4 und aktuelle Stufe 2 / When der Lagebericht ausgewertet
  wird / Then wird die Absenkung nicht als neue Warnung gemeldet und das Melde-Gedächtnis behält Stufe 4.
  Die Entwarnung mit der Dringlichkeit des alten Werts liefert Scheibe S2 von #1441 (PO-Entscheid
  13.10.2026: Entwarnung für alle amtlichen Warnungen).
  **Nachzug S2:** Die Absenkung 4 → 2 erzeugt jetzt eine Entwarnung (`+AV4>2`) mit der Dringlichkeit von
  Stufe 4 (AC siehe `feat_1441_s2_entwarnung.md`); das Gedächtnis wird erst nach der Entwarnung (bzw. einem
  zugestellten Briefing mit der Senkung) auf Stufe 2 gesenkt. Die Aussage „nicht als neue Warnung gemeldet"
  bleibt richtig — die Entwarnung ist ein eigener, additiver Typ.
  - Test: `tests/test_avalanche_report_escalation.py` — Absenkungsfall (nicht gemeldet, Gedächtnis behält den alten Höchstwert).

- **AC-14:** Given Lagebericht-Stufe 1 (gering) / When die Trip-Briefing-Mail und die Ortsvergleichs-Mail
  gerendert werden / Then ist Stufe 1 als Info sichtbar ("Lawinenstufe 1 (gering)"), unterscheidbar von
  "kein Bericht", und die Dringlichkeit ist nicht HIGH.
  - Test: `tests/test_avalanche_report_channels.py` und `tests/test_alert_urgency.py` — Stufe 1 aus Fixture.

- **AC-15:** Given Lagebericht-Stufe 5 (sehr groß) / When die Ortsvergleichs-Mail, Telegram und die
  Trip-Briefing-Mail gerendert werden / Then erscheint Stufe 5 als "Lawinenstufe 5 (sehr groß)", im
  Ortsvergleich mit Schwere `danger` (nicht schwächer als Stufe 4) und ohne die Zeile "Warnstufe 0/3" oder
  "n/3".
  - Test: `tests/test_avalanche_report_channels.py` — Renderer pro Kanal mit Stufe-5-Alert.

- **AC-16:** Given Stufe 4 oberhalb der Waldgrenze mit Problem Triebschnee / When die Trip-Briefing-Mail
  und Telegram erzeugt werden / Then lautet der Text "Lawinenstufe 4 (groß) oberhalb Waldgrenze ·
  Triebschnee", enthält Quellenname und Bulletin-URL (CC BY 4.0) und keine Handlungsempfehlung. Auch die
  eigenständige Warnungs-Mail (Trip und Ortsvergleich) trägt Quellenname und Bulletin-URL, im HTML- und
  im Klartext-Teil.
  - Test: `tests/test_avalanche_report_channels.py` — Winter-Fixture durch `render_warn_block` und `render_official_alert_telegram`;
    eigenständige Warnungs-Mail über den echten Versandweg: `test_ac16_eigenstaendige_warn_mail_traegt_quellenname_und_bulletin_url`,
    `test_ac16_ortsvergleich_warn_mail_traegt_quellenname_und_bulletin_url`.

- **AC-17:** Given Lagebericht Stufe 4 für den Tag einer Trip-Etappe, sowohl mit sichtbarer als auch mit
  ausgeschalteter Metrik `AV` / When die Trip-Briefing-SMS erzeugt wird / Then enthält sie das Token `AV4`
  genau einmal, im `!`-Block der amtlichen Warnungen, in beiden Einstellungen.
  - Test: `tests/test_avalanche_report_sms.py` — echter `SMSTripFormatter().format_sms`, Zählung `AV4 == 1`, beide Metrik-Zustände.

- **AC-18:** Given eine Eskalation auf Stufe 5 / When Alarm-SMS und Premium-SMS (Pfad
  `send_official_alert`) erzeugt werden / Then enthalten beide `AV5` mit der Originalziffer und keinen
  L/M/H-Buchstaben, und jede Nachricht liegt im Längenbudget ihres Kanals.
  - Test: `tests/test_avalanche_report_sms.py` — `render_official_alert_sms` und Premium-Textfunktion.

- **AC-19:** Given Nutzer A mit Trip in Tirol (Winter-Fixture, Stufe 3) und Nutzer B mit Trip in
  München / When für beide die Trip-Briefing-SMS und -Mail erzeugt werden / Then enthält nur die von
  Nutzer A den Lagebericht; die von Nutzer B bleibt unverändert ohne Lagebericht und ohne Hinweis.
  - Test: `tests/test_avalanche_report_channels.py` — zwei Nutzerkontexte nacheinander (kein neuer Endpoint, daher kein HTTP-Zwei-Nutzer-Test).

- **AC-20:** Given die neuen Hosts / When das Egress-Inventar in Python und Go geprüft wird / Then
  enthalten beide genau `static.avalanche.report` und `avalanche.report` neu (und weder `lawinen-warnung.eu`
  noch einen EU-Sammelfeed), und der Drift-Test ist grün.
  - Test: `tests/test_egress_inventory_drift.py` (bestehend) plus Assertion in `tests/test_avalanche_report_coverage.py`.

- **AC-21:** Given Trips mit Konfiguration ohne `avalanche_level`-Metrik / When die Briefing-SMS
  erzeugt wird / Then entsteht nie ein zweites `AV`-Token aus `_wintersport()`; die `pairs`-Liste enthält
  `AV` nicht mehr, der Adapter liefert weiter `avalanche_level=None`.
  - Test: `tests/test_avalanche_report_sms.py` — Token-Liste des Builders auf `AV`-Vorkommen.

- **AC-22:** Given die Datenquellen-Spec / When die Umsetzung abgeschlossen ist / Then enthält
  `docs/specs/data_sources.md` den Antrag (genehmigt mit Freigabe dieser Spec) und die
  Änderungshistorie 1.3; ein Hinweis auf die Doppelung `avalanche`/`avalanche_bulletin` steht in der
  SMS-Format-Doku.
  - Test: `# doc-compliance-test` in `tests/test_avalanche_report_docs.py` (Dokukonformität, kein Verhaltensnachweis).

## Test Plan

| AC | Testdatei | Art |
|----|-----------|-----|
| AC-1, AC-2, AC-3 | `test_avalanche_report_source.py`, `test_avalanche_report_parser.py` | Kern, aufgezeichnete Bulletins |
| AC-4, AC-5, AC-6 | `test_avalanche_report_states.py` | Kern, Mai-/404-Fixture, Uhr gesteuert |
| AC-7, AC-8, AC-20 | `test_avalanche_report_coverage.py` | Kern, Call-Log/Egress-Guard |
| AC-9, AC-10 | `test_avalanche_report_region_mapper.py` | Kern |
| AC-11 | `test_avalanche_report_dedup.py` | Kern |
| AC-12, AC-13 | `test_avalanche_report_escalation.py` | Kern, echter Eskalationspfad |
| AC-14 bis AC-16, AC-19 | `test_avalanche_report_channels.py`, `test_alert_urgency.py` | Kern, echte Kanal-Renderer |
| AC-17, AC-18, AC-21 | `test_avalanche_report_sms.py` | Kern |
| AC-22 | `test_avalanche_report_docs.py` | `# doc-compliance-test` |

Die Fixtures liegen in `tests/fixtures/avalanche_report/` und werden in `/40` per echtem Abruf
aufgezeichnet (Winter AT-07 und AT-02 vom 2026-03-01, Mai-Bulletin 2026-05-02, 404-Antwort, Grenzpunkt).
Live/Staging: Tirol-Punkt "sauber leer, kein nicht abrufbar" über `/e2e-verify`; Mail-Validatoren
(`briefing_mail_validator.py` für Trip-Briefing, `email_spec_validator.py` für Ortsvergleich) gegen echt
zugestellte Staging-Mails. Adversary: Mutations-Gegenprobe pflichtig (TTL 1800 → 86400, Eskalation
`native_level` → `level`, Stufe-5-Zuordnung, doppeltes `AV`, Gültigkeitsprüfung entfernen) und die Frage
"hätte das ein geteilter Trip/Ortsvergleich-Baustein sein müssen" (nur geteilte Renderer genutzt, kein
Compare-spezifischer Code außer `_ALERT_LEVEL_CELL`).

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/avalanche_report.py` | CREATE | Quelle, Konfigurationstabelle, CAAML-v6-Parser, Gültigkeit, Maximum |
| `src/services/official_alerts/region_mapper.py` | CREATE | generischer Polygon-Mapper |
| `src/services/official_alerts/data/avalanche_regions_*.geojson.json` (4 Dateien) | CREATE | Mikroregionen AT-07, IT-32-BZ, IT-32-TN, AT-02 (CC0) |
| `src/services/official_alerts/data/README.md` | MODIFY | Herkunftsnachweis |
| `src/services/official_alerts/models.py` | MODIFY | additive Felder, abgeleitetes `level` |
| `src/services/official_alerts/__init__.py` | MODIFY | Registrierung |
| `src/services/official_alerts/base.py` | MODIFY | Dublettenwahl mit Originalstufe |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | Dublette auf `RegionMapper` |
| `src/services/official_alerts/warn_egress.py` | MODIFY (ggf.) | TTL "kein aktueller Bericht" ≤ 1800 s |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Stufen-Helfer, Weichen 1-5, Eskalation `native_level`, Labels |
| `src/output/renderers/email/compare_html.py` | MODIFY | Chip, Stufe 5 → `danger` |
| `src/output/tokens/hazard_symbols.py` | MODIFY | Kürzel `AV`, Bedeutung, Reihenfolge |
| `src/output/tokens/builder.py` | MODIFY | `AV` aus `_wintersport()` entfernen, Ziffern-Token im Warnblock |
| `src/services/alert_urgency.py` | MODIFY | Stufe 1 nicht HIGH |
| `src/app/egress_guard.py`, `internal/egress/inventory.go` | MODIFY | zwei Hosts |
| `internal/…/warn_service_health.go` | MODIFY (prüfen) | Servicename `avalanche_report` |
| `docs/specs/data_sources.md` | MODIFY | Antrag #6 (Nummern #2-#5 vergeben), Änderungshistorie 1.3 |
| `docs/reference/sms_format.md` | MODIFY | `AV` im Warnblock, Abgrenzung zu `AW` |
| `docs/adr/0087-…md` und `docs/adr/README.md` | CREATE/MODIFY | ADR zur zweiten Skala (siehe unten) |
| `tests/fixtures/avalanche_report/` | CREATE | aufgezeichnete Bulletins |
| `tests/test_avalanche_report_*.py` (9 Dateien), `tests/test_alert_urgency.py` | CREATE/MODIFY | Tests laut Test Plan |

## Known Limitations

- Nur vier Regionen; Salzburg, Bayern, übrige Länder erst nach Lizenzzusage (Eintrag in der Tabelle).
- Außerhalb der Saison keine Live-Stufe messbar; Echtnachweis ist Folgebeobachtung ab Saisonstart.
- Das `latest/`-Bulletin deckt nur den aktuellen Gültigkeitszeitraum ab; Etappen jenseits davon erhalten keine Stufe (kein Bericht ≠ Entwarnung, Anzeige bleibt leer).
- Das Morgen-Update wird laut Quelle in-place ersetzt (nicht verifiziert); die 1800-s-TTL begrenzt die Verzögerung.
- Alte DTOs in `src/app/models.py` bleiben ungenutzt (bewusst nicht wiederbelebt).
- Entwarnung (#1441 S2, ADR-0090): „kein Bericht ≠ Entwarnung" gilt weiter — ein fehlendes `latest/`-Bulletin
  bei ungesunder Quelle oder außerhalb der Gültigkeit erzeugt keine Entwarnung; „vorzeitig beendet" braucht
  zwei aufeinanderfolgende Läufe bei gesunder Quelle (Verzögerung um ein Prüfintervall).

## Out of Scope

SLF (Schweiz) = Slice 2; Bayern, Salzburg und übrige AT-Länder (nach Lizenzzusage); EU-Sammelfeed;
`lawinen-warnung.eu`; Handlungsempfehlungen; sichtbarer "Saison"-Text; Migration der vier
Bestands-Mapper.

## Risiken

- Stufe 5 und Stufe 1 laufen sonst still in Default-Zweige (Farbe, "0/3", SMS-Buchstabe) — AC-14/15/18.
- Veraltetes Bulletin im Sommer (HTTP 200) wäre eine Haftungsfalle — AC-4.
- 24-h-"nicht zuständig"-Cache würde ein neues Bulletin verbergen — AC-5/AC-6.
- Zwei Skalen unter einem Namen würden verglichen — durch eigene Gefahrenart AC-11.
- Bestehender Kollisionstest in `test_hazard_symbols.py` (`AV` reserviert) muss die absichtliche Nutzung
  von `AV` für `avalanche_bulletin` ausdrücklich erlauben.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0087 (neu, nächste freie Nummer nach ADR-0086), Titel sinngemäß "Lawinen-Lagebericht
  als zweite Skala neben der Awareness-Skala", Status Akzeptiert, ergänzt ADR-0016.
- **Rationale:** ADR-0016 deckt den additiven Quellentyp und die Registry ab, legt `OfficialAlert.level`
  aber auf 1-4 fest. Eine eigene Gefahrenart mit nativer 1-5-Skala, abgeleitetem Farb-`level` und
  Vergleichen über `native_level` (Eskalation, Dublettenwahl) ist eine Datenmodell-Entscheidung mit
  Wirkung auf alle Kanäle und wird als Teil der Umsetzung dokumentiert. Index-Konsistenz erzwingt
  `tests/test_adr_index_drift.py`.

## Changelog

- 2026-10-13: Initial spec created (Issue #1441 Slice 1, Epic #2258; erledigt #1473)
- 2026-10-13 v1.1: AC-13 und Abschnitt 8 auf den Umfang von S1 begrenzt (Absenkung nicht gemeldet, Gedächtnis behält Höchstwert). Die Entwarnung mit alter Dringlichkeit für alle amtlichen Warnungen kommt in Scheibe S2 von #1441 (PO-Entscheid 13.10.2026). Anlass: Adversary-Finding F003, Helfer ohne Aufrufer.
- 2026-10-14 v1.2: Lizenzpflicht präzisiert — Quellenname und Bulletin-URL auch in der eigenständigen Warnungs-Mail (vorher fehlte die URL dort); Telegram-Kurzstil folgt der SMS ohne URL. Anlass: Adversary-Findings F011/F014.
- 2026-10-16 v1.3: Nachzug #1441 S2 (ADR-0090) — Abschnitt 8, AC-13 und Known Limitations: Absenkung/Ende der Lawinenstufe löst Entwarnung mit alter Dringlichkeit aus (`+AV4>2`, `+AV4>0`); Version-Header der Spec unverändert.
