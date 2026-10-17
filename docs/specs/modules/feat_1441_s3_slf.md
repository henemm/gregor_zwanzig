---
entity_id: feat_1441_s3_slf
type: module
created: 2026-10-17
updated: 2026-10-17
status: draft
version: "1.0"
tags: [official-alert, avalanche, slf, schweiz, eaws, caaml, vier-kanaele, ortsvergleich, entwarnung, issue-1441]
workflow: feat-1441-s3-slf
---

# Amtlicher Schweizer Lawinen-Lagebericht (SLF, #1441 Scheibe S3)

## Approval

- [ ] Approved

## Purpose

Der amtliche Lawinen-Lagebericht des WSL-Instituts für Schnee- und Lawinenforschung SLF (`aws.slf.ch`, CAAML6-JSON, ganze Schweiz) wird als weitere Quelle neben avalanche.report (S1) angebunden. Er erscheint in allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS) und im Ortsvergleich in derselben Darstellung wie der Tiroler, Südtiroler, Trentiner und Kärntner Bericht — inklusive Eskalation und Entwarnung (S2). Zusätzlich zeigt die Langform (Mail, Telegram) die amtliche Feinstufe („Lawinenstufe 3- (erheblich)"). Das Produkt liefert dabei nur Daten (Stufe, Höhe, Problemnamen im Wortlaut des SLF), nie eine Handlungsempfehlung.

## Beschlossene Vorgaben (Product Owner)

- **16.10.2026:** SLF bleibt in #1441; das Issue bleibt offen, bis SLF live ist.
- **17.10.2026, Datenquellen-Antrag #7:** SLF-Daten werden genutzt mit der Quellenangabe „WSL-Institut für Schnee- und Lawinenforschung SLF", einem Link zum Originalbericht (`https://www.slf.ch/de/lawinenbulletin-und-schneesituation/`, die API hat kein Link-Feld) und dem Hinweis, dass der Originalbericht maßgeblich ist. Parallel geht eine schriftliche Anfrage an das SLF (Entwurf: `docs/artifacts/feat-1441-s3-slf/anfrage_slf_entwurf.md`, Versand durch den PO). **Lehnt das SLF ab, wird die Quelle abgeschaltet** (Registrierung entfernen) — das muss mit einer Zeile möglich sein.
- **17.10.2026, Feinstufe:** Die amtliche Feinstufe (`dangerRatings[].customData.CH.subdivision`: minus/neutral/plus → „3-", „3", „3+") erscheint in der Mail (Trip-Briefing, Ortsvergleich, eigenständige Warnungs-Mail) und in der Telegram-Langform („Lawinenstufe 3- (erheblich)"). SMS, Premium-SMS und Telegram-Kurzform bleiben `AV<Ziffer>` (ADR-0089, Kurzform folgt der SMS).
- **Projektvorgaben:** Alle vier Kanäle sind gleichrangig und müssen jede Frage mit demselben Inhalt beantworten. Nur Daten, nie Handlungsempfehlung. Stufe, Höhe und Problemnamen wörtlich (Haftung); nichts erfinden. Telegram-Kurzform folgt der SMS-Auswahl (beschlossen, nicht erneut fragen).

## Source

- **Schicht:** Python-Core (`src/services/official_alerts/`, `src/output/renderers/alert/`) plus Egress-Inventar in Go (`internal/egress/inventory.go`) und der Mail-Validator unter `.claude/hooks/`. Scope: **full-stack** wegen der Go-Datei (kein Frontend).
- **Neue Dateien:** `src/services/official_alerts/caaml.py` (reine CAAML-Funktionen, aus `avalanche_report.py` herausgelöst, plus Höhe-aus-Problem und Feinstufe), `src/services/official_alerts/slf.py` (`SlfSource`), `src/services/official_alerts/data/avalanche_regions_CH.geojson.json` (EAWS-CH-Mikroregionen, 149 Umrisse, CC0, aus `docs/artifacts/feat-1441-s3-slf/raw/CH_micro-regions.geojson.json`; Eintrag im `data/README.md`).
- **Identifier:** neu `SlfSource` (Registry-Name `slf_bulletin`), `caaml.parse_region_alert` (S1-Parser, jetzt geteilt), `caaml.elevation_from_problems`; geändert `AvalancheReportSource` (importiert aus `caaml.py`, Verhalten unverändert), `OfficialAlert` (ein optionales Feld `level_modifier`), `avalanche_bulletin_text`, `_SOURCE_LABELS`.
- **Geänderte Dateien:** `src/services/official_alerts/avalanche_report.py`, `src/services/official_alerts/__init__.py`, `src/services/official_alerts/models.py`, `src/output/renderers/alert/official_alerts.py`, `src/app/egress_guard.py`, `internal/egress/inventory.go`, `.claude/hooks/official_alert_mail_validator.py`.

## Estimated Scope

Ehrliche Schätzung produktiver **hinzugefügter** Zeilen (nur `src/`, `internal/`, Validator; Tests, Doku und die Daten-Datei zählen nicht):

| Datei | LoC (ca.) | Inhalt |
|---|---|---|
| `src/services/official_alerts/caaml.py` (neu) | 150 | ~110 reine Verschiebung aus `avalanche_report.py` (`_parse_time`, `_elevation`, `_time_of_day`, `_carrier`, `_problems`, `_rated`, `_find_region`, `parse_region_alert`, Konstanten), ~30 Höhe-aus-Problem, ~10 Feinstufe |
| `src/services/official_alerts/slf.py` (neu) | 95 | `SlfSource`: ein Abruf für die ganze Schweiz, `covers()` per Polygon, Zustände (leer/Fehler), Bulletin-Link, Gültigkeitsfilter |
| `src/services/official_alerts/avalanche_report.py` | 5 | Import aus `caaml.py` (die verschobenen ~110 Zeilen entfallen hier, zählen aber nicht als Abzug) |
| `src/services/official_alerts/__init__.py` | 3 | Registrierung direkt nach `AvalancheReportSource`, `__all__` |
| `src/services/official_alerts/models.py` | 3 | Feld `level_modifier` (Default `None`) |
| `src/output/renderers/alert/official_alerts.py` | 14 | Quellenlabel, Maßgeblichkeitshinweis, Feinstufe in `avalanche_bulletin_text` und Telegram-Kopf |
| `src/app/egress_guard.py` + `internal/egress/inventory.go` | 8 | `aws.slf.ch` als `BLOCKED` |
| `.claude/hooks/official_alert_mail_validator.py` | 8 | Feinstufe und SLF-Quellenkennung erkennen |
| **Summe (brutto, wie der Workflow zählt)** | **~290** | davon ~110 Verschiebung; netto ~180 |

- **Files:** 7 geänderte produktive + 2 neue Module + 1 Daten-Datei, 4 neue Testdateien, 4 Fixture-Gruppen, 5 Doku-Dateien + 1 ADR.
- **Effort:** medium. **Risk:** MEDIUM — die zentrale Lawinen-Quelle wird umsortiert (reine Funktionen verschoben); die neue Quelle ist erst zur Wintersaison live belegbar.
- **LoC-Limit:** Der Workflow zählt hinzugefügte Zeilen je Datei (`git diff --numstat`, Spalte „added"), keinen Abzug für Gelöschtes. Die Verschiebung nach `caaml.py` zählt deshalb voll mit: ~290 > 250. Der Workflow braucht `workflow.py set-field loc_limit_override 500`. Ein Verzicht auf die Verschiebung (Parser kopieren) wird bewusst verworfen: zwei Pflegestellen für dieselbe CAAML-Logik (ADR-0091).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `warn_egress.cached_fetch`, `observe_fetch_failure`, `mark_not_covered` | Upstream | Abruf, Zustände „nicht abrufbar" / „nicht zuständig", Pro-Quelle-Journal (#1422) |
| `RegionMapper.regions_at`, `geo_ray_cast` | Upstream | Punkt-in-Polygon gegen die CH-Mikroregionen |
| `base.py` (`get_official_alerts_with_status` :199 ff., `get_official_alerts_with_sources`) | Upstream | Kompensationsregel, Dublettenwahl, Pro-Quelle-Ergebnis für die Entwarnung |
| `egress_guard.py`, `internal/egress/inventory.go`, `tests/test_egress_inventory_drift.py` | Upstream | Host-Klassifikation Python/Go |
| Alert-Renderer (`official_alerts.py`), Trip-Briefing, Ortsvergleich (`compare_html.py`, `compare_official_alert.py`), SMS-Token (`hazard_symbols.py`) | Downstream | quellenneutral über die Gefahrenart `avalanche_bulletin` |
| `official_alert_allclear.py` (S2) | Downstream | Entwarnung bindet an den Registry-Namen `slf_bulletin` |
| ADR-0016, 0041, 0089, 0090, 0091 | Entscheidungen | Registry, Zuständigkeit, zweite Skala, Entwarnung, SLF als eigene Quelle |

## Implementation Details

### 1. Aufteilung: `caaml.py` und zwei Quellen (Variante A, ADR-0091)

`caaml.py` enthält nur reine Funktionen ohne Netz und ohne Quellen-Konfiguration. `avalanche_report.py` behält Tabelle, URL-Muster, `AvalancheReportSource` und importiert die Funktionen; sein Verhalten und alle S1-Tests bleiben unverändert (AC-7). `slf.py` enthält `SlfSource` mit Registry-Name `slf_bulletin`, `source="slf_bulletin:CH-xxxx"`, `dedup_id="avalanche_bulletin:CH-xxxx"`, Gefahrenart `avalanche_bulletin`, `scale="eaws"`, `native_level` 1–5, `level=min(native,4)`.

### 2. Abruf und Zustände

- **Ein Abruf für ganz CH** (`https://aws.slf.ch/api/bulletin/caaml/de/json`, ohne `activeAt`; die API liefert dann genau die gerade gültige Ausgabe) über `warn_egress.cached_fetch`, Cache 1800 s. Alle Punkte in der Schweiz teilen sich diesen einen Abruf.
- **Gültigkeit wie S1:** ein Bulletin zählt nur, wenn `validTime.endTime >= now`. Die Abend-Ausgabe gilt 16:00Z → Folgetag 16:00Z (`nextUpdate` 07:00Z), das Morgen-Update 07:00Z → 16:00Z und löst sie ab.
- **Leere Saison:** HTTP 200 mit `{"bulletins":[]}` → „kein aktueller Bericht": leere Ergebnisliste, **kein** Ausfallhinweis, Cache höchstens 1800 s (nicht die 24-h-TTL von `not_covered`, S1 Abschnitt 5), im Pro-Quelle-Journal (#1422) als erfolgreiche Antwort. 
- **Nicht abrufbar:** Netzfehler, HTTP 5xx, kaputtes JSON, fehlende `bulletins`-Liste → wie S1 `fetch_failed`/unavailable.

### 3. Zuständigkeit: Polygon, nicht BBox

`SlfSource.covers(lat, lon)` ist wahr, wenn `RegionMapper.regions_at` den Punkt in mindestens einer CH-Mikroregion der eingecheckten Datei findet. Eine BBox reicht bis Vorarlberg, Westtirol, Aosta und den Schwarzwald und würde dort „SLF nicht abrufbar" auslösen. **Tragend** für die Bestandstests `tests/test_avalanche_report_ausfall_sichtbarkeit.py` (:40 lässt `slf_bulletin` in der Registry; ihre Testpunkte Tirol und Zell am See dürfen SLF nicht als zuständig werten).

### 4. Mittelland und nie bewertete Regionen

Keine Ausschlussliste: 149 Umrisse stehen 120–135 bewerteten Regionen je Termin gegenüber, und die Zahl schwankt (fünf Stichproben 2025-12-20 bis 2026-04-10). Ein Punkt in einer Mikroregion, die im aktuellen Bulletin nicht vorkommt (z. B. `CH-9211` Zürich/Bern, in keiner Stichprobe bewertet), liefert **keine** Warnung und gilt als „nicht zuständig" (`mark_not_covered`, F001-Semantik): das kompensiert keinen fremden Ausfall und löst keinen Ausfallhinweis aus. **Belegter Befund zur Kompensation:** Für Schweizer Punkte liefert keine weitere Quelle der Registry Warnungen (MeteoAlarm-Feeds nur IT, AT, DE). `meteofrance_vigilance` und `dpc` melden per grobem `covers()` zwar „zuständig“ für Zürich/Bern (gemessen 17.10.2026), stellen beim Abruf aber „nicht zuständig“ fest und zählen dann nicht mehr (`base.py:269-275`, #1681) — als Kompensationspartner taugen sie nicht. Fällt der SLF-Abruf aus, bevor die Region bekannt ist, zählt SLF als zuständig und ausgefallen — im Mittelland erscheint dann der generische Ausfallhinweis (AC-14, Known Limitation).

### 5. Höhe aus dem Problem (nur wenn das Rating keine `elevation` hat)

SLF-Ratings tragen keine Höhe, sie steht in `avalancheProblems[].elevation`. Regel (nur für Ratings ohne `elevation`; S1-Bulletins bleiben unberührt):

1. Träger-Rating bestimmen wie S1 (`_carrier`: höchste Stufe, bei Gleichstand nach Tageszeit-Rang).
2. Kandidaten: Probleme mit `dangerRatingValue == mainValue` des Träger-Ratings **und** passender `validTimePeriod` (`all_day` oder gleich der Tageszeit des Träger-Ratings).
3. Hat jeder Kandidat dieselbe Grenze (gleiche Richtung, gleicher Wert), wird sie wörtlich übernommen (`lowerBound` → „oberhalb", `upperBound` → „unterhalb").
4. Verschiedene Grenzen, ein Kandidat ohne Grenze, kein Kandidat oder `lowerBound 0` (= keine Begrenzung) → **keine Höhe** (nichts erfinden, #1405).

### 6. Feinstufe

`dangerRatings[].customData.CH.subdivision` des Träger-Ratings: `minus` → „-", `plus` → „+", `neutral` oder fehlend → keine Angabe. Sie wird in dem neuen optionalen Feld `OfficialAlert.level_modifier` getragen und nur von `avalanche_bulletin_text` (Mail, Telegram-Langform, inkl. Telegram-Kopfzeile „Lawinenstufe 3-") ausgegeben. SMS-Token, Premium-SMS und Telegram-Kurzform lesen weiter nur `native_level`. Eskalation, Dublette und Melde-Gedächtnis vergleichen weiter nur `native_level` — ein Wechsel „3+ → 3-" ist daher weder neue Warnung noch Entwarnung (AC-27).

### 7. Quellenangabe, Link, Maßgeblichkeit

`_SOURCE_LABELS` führt „WSL-Institut für Schnee- und Lawinenforschung SLF" für `slf_bulletin` (Registry-Name, Entwarnungs-Mail) und für jede Region `slf_bulletin:CH-xxxx` (Auflösung über den Präfix vor dem ersten `:`). `OfficialAlert.url` ist konstant `https://www.slf.ch/de/lawinenbulletin-und-schneesituation/`. In Mail und Telegram-Langform folgt auf Quellenname und Link der Satz „Maßgeblich ist der Originalbericht des SLF." SMS, Premium-SMS und Telegram-Kurzform tragen weder Name noch Link (wie S1).

### 8. Egress

`aws.slf.ch` wird in `src/app/egress_guard.py` und `internal/egress/inventory.go` exakt wie `avalanche.report` klassifiziert (`BLOCKED`: Test und Staging erreichen den Host nicht real). Der Drift-Test `tests/test_egress_inventory_drift.py` bewacht die Gleichheit beider Listen.

### 9. Registrierung und Abschaltbarkeit

`register_official_alert_source(SlfSource())` steht in `official_alerts/__init__.py` **direkt nach** `AvalancheReportSource()` (AT/CH-Polygone sind disjunkt; die Reihenfolge ist per Test festgeschrieben). Die Registrierungszeile ist der einzige Schalter: ohne sie ist die Quelle vollständig inaktiv, ohne dass ein anderer Test oder eine andere Quelle bricht (AC-17). Der Import der Klasse und die Daten-Datei dürfen stehen bleiben.

### 10. Entwarnung (S2) und Eskalation (S1 Abschnitt 8)

Der Registry-Name `slf_bulletin` ist die `source`-Bindung der Entwarnung. Eine Absenkung (4 → 2, über `native_level`) ergibt eine Entwarnung in allen vier Kanälen; die Entwarnung nennt Ziffern („Stufe 4 → 2", SMS `+AV4>2`), die Feinstufe erscheint dort nicht (Gedächtnis und S2-Darstellung kennen nur die Ziffer). Ein Quellenausfall, die leere Saison und das Verschwinden der Region aus dem Bericht sind keine Entwarnung (der Quellenzustand ist dann „nicht abrufbar" bzw. „nicht zuständig", S2: `ok` nur ohne `fetch_failed`/`not_covered`).

## Expected Behavior

- **Input:** Koordinate eines Trip-Segments bzw. Ortsvergleich-Orts in der Schweiz; das aktuelle SLF-Bulletin (CAAML6).
- **Output:** Null oder eine `OfficialAlert` der Gefahrenart `avalanche_bulletin` je Punkt (Stufe 1–5 mit Wortlaut, Höhe, Probleme, Tageszeit, Feinstufe), in den vier Kanälen und im Ortsvergleich wie der S1-Bericht; Quellenzeile mit Name, Link und Maßgeblichkeitshinweis in Mail und Telegram-Langform.
- **Side effects:** Ein HTTP-Abruf je Cache-Zeitraum für die ganze Schweiz; Pro-Quelle-Journal (#1422) und Melde-Gedächtnis wie bei jeder amtlichen Quelle.

## Acceptance Criteria

Fixtures (aufgezeichnet am 17.10.2026 per `GET https://aws.slf.ch/api/bulletin/caaml/de/json?activeAt=<ISO>`, in `/40` von `docs/artifacts/feat-1441-s3-slf/raw/` nach `tests/fixtures/slf/` übernommen, Dateinamen unverändert): `at_2025-12-20T08:00:00Z.json`, `at_2026-01-15T08:00:00Z.json`, `at_2026-02-10T08:00:00Z.json`, `at_2026-03-01T08:00:00Z.json` (Morgen), `at_2026-03-01T17:30:00Z.json` (Abend-Ausgabe), `at_2026-03-02T06:00:00Z.json` (dieselbe Abend-Ausgabe, früh am Folgetag), `at_2026-03-02T08:00:00Z.json` (Morgen-Update), `at_2026-04-10T08:00:00Z.json`, `CH_micro-regions.geojson.json` (149 Umrisse). Die leere Saison ist die aufgezeichnete Antwort vom 16.10.2026 (`GET https://aws.slf.ch/api/bulletin/caaml/de/json` ohne `activeAt`, Inhalt wörtlich `{"bulletins":[]}`) als `tests/fixtures/slf/leer.json`. Die aufgezeichneten Bulletins enthalten höchstens Stufe 3; wo ein Test Stufe 4 oder eine Absenkung braucht, leitet er die Variante im Test aus einer aufgezeichneten Datei ab (nur `mainValue`/`dangerRatingValue` geändert) und nennt das im Testnamen („abgeleitet"). Punkte in Mikroregionen bestimmt der Test aus dem Umriss der Fixture-Datei.

### Parser und Modell

- **AC-1:** [Grundfall] Given das Bulletin `at_2026-03-01T08:00:00Z.json` und ein Punkt in der Mikroregion `CH-7231` (Rating erheblich/minus, Problem Altschnee ab 2000 m) / When die Warnungen für diesen Punkt abgerufen werden / Then liefert die Quelle genau eine Warnung der Gefahrenart `avalanche_bulletin` mit `source="slf_bulletin:CH-7231"`, `dedup_id="avalanche_bulletin:CH-7231"`, `scale="eaws"`, `native_level=3`, `level=3`, Höhe „oberhalb 2000", dem Problem `persistent_weak_layers` und der konstanten SLF-Link-URL.
  - Test: `tests/test_slf_bulletin_parser.py` — echte `SlfSource` mit Fixture-Transport; alle genannten Felder werden geprüft.

- **AC-2:** [Höhe aus dem Problem, eindeutig] Given das Bulletin `at_2026-03-01T17:30:00Z.json`, Region `CH-7231` (Rating erheblich; Problem Altschnee ab 2000 m = erheblich, Problem Nassschnee bis 2200 m = mäßig) und das Bulletin `at_2026-01-15T08:00:00Z.json`, Region `CH-1311` (zwei erhebliche Probleme, beide ab 2000 m) / When die Warnungen abgerufen werden / Then steht in beiden Fällen „oberhalb 2000 m"; das mäßige Nassschnee-Problem mit abweichender Grenze zählt im ersten Fall nicht mit, weil es das Träger-Rating nicht trägt.
  - Test: `tests/test_slf_bulletin_parser.py` — beide Fixtures; Höhe wörtlich „2000"/„oberhalb"; Gegenprobe: dasselbe Bulletin mit dem Nassschnee-Problem auf „erheblich" gesetzt (abgeleitet) ergibt keine Höhe (AC-4).

- **AC-3:** [Höhe nur nach unten] Given das Bulletin `at_2026-04-10T08:00:00Z.json`, Region `CH-1246` (Rating erheblich; Nassschnee-Problem bis 2400 m; das mäßige/geringe Zweitproblem ab 2000 m trägt das Rating nicht) / When abgerufen wird / Then lautet die Höhe „unterhalb 2400 m", im gerenderten Text „… unterhalb 2400 m …".
  - Test: `tests/test_slf_bulletin_parser.py` — Feld `elevation_direction="below"`, Wert „2400"; `tests/test_slf_bulletin_kanaele.py` — gerenderter Mail-/Telegram-Text enthält „unterhalb 2400 m".

- **AC-4:** [Mehrdeutig ⇒ keine Höhe] Given das Bulletin `at_2026-03-01T17:30:00Z.json`, Region `CH-5112` (Rating mäßig; Altschnee ab 2000 m **und** Nassschnee bis 2200 m, beide mäßig) / When abgerufen wird / Then wird die Stufe 2 ohne jede Höhenangabe geliefert (weder „oberhalb 2000" noch „unterhalb 2200"); im gerenderten Text steht keine Höhe.
  - Test: `tests/test_slf_bulletin_parser.py` — `elevation_value is None`, `native_level == 2`; `tests/test_slf_bulletin_kanaele.py` — kein „oberhalb"/„unterhalb" im Mail-Text dieser Warnung.

- **AC-5:** [Keine Grenze vorhanden] Given (a) das Bulletin `at_2026-03-01T08:00:00Z.json`, Region `CH-8112` (Stufe 1, Gleitschnee mit `lowerBound 0`) und (b) das Bulletin `at_2026-04-10T08:00:00Z.json`, Region `CH-1311` (Träger-Rating erheblich „nachmittags", das tragende Nassschnee-Problem hat keine `elevation`) / When abgerufen wird / Then trägt keine der beiden Warnungen eine Höhe, und (b) trägt die Tageszeit „nachmittags".
  - Test: `tests/test_slf_bulletin_parser.py` — (a) und (b); `elevation_value is None`, bei (b) `time_of_day == "later"`.

- **AC-6:** [Feinstufe im Modell] Given Ratings mit `subdivision` minus (`CH-7231`, 2026-03-01 Morgen), plus (`CH-5112`, 2026-01-15), neutral (`CH-1246`, 2026-03-01 Morgen) und ohne Feinstufe (Stufe 1, `CH-8112`) / When abgerufen wird / Then ist `level_modifier` „-", „+", `None`, `None` und die Ziffer (`native_level`) bleibt 3, 3, 2, 1.
  - Test: `tests/test_slf_bulletin_parser.py` — vier Fälle, `native_level` und `level_modifier`.

- **AC-7:** [S1 unverändert] Given die Auslösung der CAAML-Funktionen nach `caaml.py` / When die S1-Tests der Quelle avalanche.report laufen / Then bleiben sie unverändert grün — insbesondere liefert ein Rating mit eigener `elevation` weiter diese Höhe (die Höhe-aus-Problem-Regel greift nur ohne Rating-`elevation`), und `avalanche_report.py` enthält keine eigene Kopie der verschobenen Funktionen.
  - Test: `tests/test_avalanche_report_parser.py`, `tests/test_avalanche_report_source.py` (unverändert, nachlaufen lassen); `tests/test_slf_bulletin_parser.py` — ein S1-Fixture-Bulletin läuft durch `caaml.parse_region_alert` und liefert dasselbe Ergebnis wie `AvalancheReportSource`.

### Zustände, Zuständigkeit, Abruf

- **AC-8:** [Gültigkeit, Abend- und Morgen-Ausgabe] Given die Abend-Ausgabe (`at_2026-03-02T06:00:00Z.json`, gültig bis 2026-03-02T16:00Z) / When um 2026-03-02T06:00Z abgerufen wird / Then gilt sie und liefert die Warnung; um 2026-03-02T17:00Z mit derselben (nun abgelaufenen) Antwort / Then ist das Ergebnis leer **ohne** Ausfallhinweis; und das Morgen-Update `at_2026-03-02T08:00:00Z.json` liefert um 08:00Z seine eigene Gültigkeit (07:00Z–16:00Z).
  - Test: `tests/test_slf_bulletin_abdeckung.py` — drei Zeitpunkte mit injiziertem `now`; leer, `unavailable=False`.

- **AC-9:** [Leere Saison] Given die aufgezeichnete Antwort `leer.json` (HTTP 200, `{"bulletins":[]}`) / When ein Punkt in Graubünden abgefragt wird / Then ist das Ergebnis leer, `unavailable=False` (kein Ausfallhinweis), im Pro-Quelle-Journal steht die Quelle als erfolgreich beantwortet, und die leere Antwort wird höchstens 1800 s gecacht — 1801 s später löst der nächste Abruf eine neue Anfrage aus (ein neues Bulletin bleibt nicht 24 h unsichtbar).
  - Test: `tests/test_slf_bulletin_abdeckung.py` — Fixture-Transport mit Abrufzähler und injizierter Uhr; Journal über `collect_source_queries`.

- **AC-10:** [Abruffehler] Given ein Netzfehler, HTTP 503, kaputtes JSON bzw. ein 200 ohne `bulletins`-Liste / When ein Punkt in Graubünden abgefragt wird / Then gilt die Quelle als nicht abrufbar (`unavailable=True`, da keine zweite Quelle zuständig ist), und der Ausfallhinweis erscheint im Trip-Briefing.
  - Test: `tests/test_slf_bulletin_abdeckung.py` — vier Fehlerarten; `unavailable=True`; `tests/test_slf_bulletin_kanaele.py` — Hinweiszeile im gerenderten Briefing.

- **AC-11:** [Ein Abruf für ganz CH] Given drei Punkte in verschiedenen Mikroregionen (Graubünden, Wallis, Berner Oberland) / When sie innerhalb des Cache-Zeitraums nacheinander abgefragt werden / Then entsteht genau ein HTTP-Abruf an `aws.slf.ch`, und jeder Punkt erhält die Warnung seiner Mikroregion.
  - Test: `tests/test_slf_bulletin_abdeckung.py` — Zähler am Fixture-Transport == 1.

- **AC-12:** [Zuständigkeit per Polygon] Given Innsbruck (47.27 / 11.39), Bregenz/Vorarlberg (47.50 / 9.75), Aosta (45.74 / 7.32), Feldberg/Schwarzwald (47.87 / 8.00) sowie ein Punkt in `CH-7231` / When `covers()` bzw. die Registry befragt wird / Then ist SLF nur für den Schweizer Punkt zuständig; für die vier anderen Punkte findet kein Abruf statt und es entsteht kein Ausfallhinweis. Die Bestandstests `test_avalanche_report_ausfall_sichtbarkeit.py` (Tirol, Zell am See) bleiben grün, obwohl `slf_bulletin` in der Registry steht.
  - Test: `tests/test_slf_bulletin_abdeckung.py` — Abrufzähler 0 für die vier Punkte; `tests/test_avalanche_report_ausfall_sichtbarkeit.py` (unverändert, nachlaufen lassen).

- **AC-13:** [Mittelland, keine Ausschlussliste] Given ein Punkt in `CH-9211` (Zürich, 47.37 / 8.54), der im Bulletin `at_2026-03-01T08:00:00Z.json` nicht vorkommt / When abgefragt wird / Then ist das Ergebnis leer ohne Ausfallhinweis (Region nicht im Bulletin ⇒ „nicht zuständig", `mark_not_covered`). Given eine Mikroregion, die in `at_2026-02-10T08:00:00Z.json` bewertet ist und in `at_2025-12-20T08:00:00Z.json` nicht (der Test bestimmt sie aus den Fixtures) / Then liefert dieselbe Quelle sie im einen Bulletin und im anderen nicht — im Code steht keine feste Liste ausgeschlossener Regionen.
  - Test: `tests/test_slf_bulletin_abdeckung.py` — Zürich leer, `unavailable=False`, Journal „nicht zuständig"; Region-Differenz zweier Fixtures; abgeleitetes Bulletin mit allen Mikroregionen liefert für jede ihre Warnung (Verhaltensnachweis „keine Ausschlussliste", ersetzt den früheren Quelltext-Check — #765-Hygiene-Gate).

- **AC-14:** [SLF-Ausfall im Mittelland] Given der SLF-Abruf schlägt fehl und der Punkt liegt in `CH-9211` (Zürich) / When die Warnungen mit Status abgefragt werden / Then ist das Verhalten dasselbe wie in Graubünden (AC-10): `unavailable=True` und der generische Ausfallhinweis erscheint, weil kein Kompensationspartner zuständig ist (Kompensationsregel `base.py` ab :199 greift erst ab zwei zuständigen Quellen). Der Test hält das als bekannte, ausdrücklich beschriebene Eigenschaft fest, damit sie nicht unbemerkt kippt.
  - Test: `tests/test_slf_bulletin_abdeckung.py` — Zürich bei 503: `unavailable=True`; Gegenprobe: derselbe Punkt bei erfolgreicher Antwort ohne Region: `unavailable=False`.

- **AC-15:** [Egress] Given der neue Host / When das Egress-Inventar in Python und Go geprüft wird / Then führen beide `aws.slf.ch` mit derselben Klassifikation wie `avalanche.report` (`BLOCKED`), kein weiterer neuer Host, und der Drift-Test ist grün; ein echter Abruf aus der Test-Umgebung wird blockiert.
  - Test: `tests/test_egress_inventory_drift.py` (bestehend); `tests/test_slf_bulletin_abdeckung.py` — Klassifikation von `aws.slf.ch` == Klassifikation von `avalanche.report`.

- **AC-16:** [Registry-Reihenfolge] Given die echte Standard-Registry / When die Quellen aufgelistet werden / Then heißt die Quelle `slf_bulletin`, steht unmittelbar nach `avalanche_report`, und beide liegen nach allen übrigen Quellen.
  - Test: `tests/test_slf_bulletin_abdeckung.py` — Namen und Indizes der Registry.

- **AC-17:** [Abschaltbar mit einer Zeile] Given die Registry ohne die SLF-Registrierung (Zeile entfernt bzw. im Test entfernt) / When ein Punkt in Graubünden und ein Punkt in Tirol abgefragt werden und die Bestandssuite der Lawinenquellen läuft / Then entsteht keine SLF-Warnung, kein Abruf an `aws.slf.ch` und kein Ausfallhinweis, und kein anderer Test und keine andere Quelle ändert ihr Verhalten.
  - Test: `tests/test_slf_bulletin_abdeckung.py` — Registry ohne `slf_bulletin`, Abrufzähler 0, Tirol-Ergebnis identisch zum Lauf mit SLF.

### Darstellung in den Kanälen (am gerenderten Text)

- **AC-18:** [Quellenangabe, Link, Maßgeblichkeit] Given eine SLF-Warnung (`CH-7231`, 2026-03-01 Morgen) / When Trip-Briefing-Mail, Ortsvergleichs-Mail, eigenständige Warnungs-Mail und Telegram-Langform gerendert werden / Then enthält jeder dieser Texte „WSL-Institut für Schnee- und Lawinenforschung SLF", den Link `https://www.slf.ch/de/lawinenbulletin-und-schneesituation/` und den Satz „Maßgeblich ist der Originalbericht des SLF."; SMS, Premium-SMS und Telegram-Kurzform tragen keines der drei Elemente.
  - Test: `tests/test_slf_bulletin_kanaele.py` — sechs gerenderte Ausgaben (vier mit, drei ohne die Elemente); Quellenlabel auch für `slf_bulletin` allein (Entwarnungs-Mail).

- **AC-19:** [Feinstufe in der Mail] Given eine SLF-Warnung Stufe 3 mit Feinstufe minus, Höhe oberhalb 2000 m und Problem Altschnee / When Trip-Briefing-Mail, Ortsvergleichs-Mail und eigenständige Warnungs-Mail gerendert werden / Then lautet die Stufenzeile in allen drei „Lawinenstufe 3- (erheblich) oberhalb 2000 m · Altschnee" (Problemname wie im Namensverzeichnis des Renderers); bei Feinstufe neutral „Lawinenstufe 3 (erheblich)", bei plus „Lawinenstufe 3+ (erheblich)".
  - Test: `tests/test_slf_bulletin_kanaele.py` — drei Mail-Arten × drei Feinstufen, Text- und HTML-Teil.

- **AC-20:** [Feinstufe in Telegram] Given dieselbe Warnung / When die Telegram-Langform gerendert wird / Then steht dort „Lawinenstufe 3- (erheblich)" (Zeile und Kopfzeile „Lawinenstufe 3-"); die Telegram-Kurzform ist identisch zum SMS-Text (`AV3`, ohne Feinstufe).
  - Test: `tests/test_slf_bulletin_kanaele.py` — Lang- und Kurzform; Kurzform == SMS-Text.

- **AC-21:** [SMS und Premium-SMS ohne Feinstufe] Given dieselbe Warnung (Stufe 3, Feinstufe minus) / When Briefing-SMS, Alarm-SMS und Premium-SMS gerendert werden / Then enthalten sie `AV3` (im Briefing-SMS-Block `!AV3`), niemals `AV3-`, „3-" oder einen Quellennamen, und genau ein `AV`-Token.
  - Test: `tests/test_slf_bulletin_kanaele.py` — Token-Liste der drei SMS-Wege; Regex auf `AV\d[-+]` negativ.

- **AC-22:** [Alarm: vier Kanäle × zwei Flächen] Given eine Eskalation auf Stufe 4 in der Schweiz (abgeleitet aus `at_2026-03-01T08:00:00Z.json`, `CH-7231`) / When der Alarm im Trip-Alarm und im Ortsvergleich-Alarm versendet wird / Then kommt er in beiden Flächen über E-Mail, Telegram, SMS und Premium-SMS an — Premium-SMS ausdrücklich auch im Ortsvergleich — jeweils mit demselben Inhalt (Stufe, Region bzw. Ort, Höhe) in kanalgerechter Form; Stufe 5 würde dieselben Wege nehmen (`level=4` bleibt abgeleitet).
  - Test: `tests/test_slf_bulletin_kanaele.py` — 4 × 2 parametrisiert an den echten Versandpfaden (`send_official_alert`, `send_multi_location_official_alert`) mit aufgezeichnetem Transport; jede Zelle prüft Zustellung und Inhalt.

- **AC-23:** [Ortsvergleich-Quellenfilter] Given ein Ortsvergleich mit einem Ort in Graubünden / When die Warnungen ohne `sources`-Filter, mit `sources=["slf_bulletin"]` und mit `sources=["meteoalarm"]` abgefragt werden / Then erscheint die SLF-Warnung im ersten und zweiten Fall und fehlt im dritten (Quellenname = Teil vor dem ersten „:").
  - Test: `tests/test_slf_bulletin_kanaele.py` — drei Filterfälle gegen `compare_official_alert`; Ortsvergleichs-Mail zeigt Stufe, Feinstufe und Quellenzeile.

- **AC-24:** [Eskalation und Folgeausgabe] Given zuletzt gemeldete Stufe 3 und neue Stufe 4 (abgeleitet), dann Stufe 4 → 5 (abgeleitet), und die Abend-Ausgabe 2026-03-01 gefolgt vom Morgen-Update 2026-03-02 mit gleicher Stufe / When der Alarm-Lauf jeweils läuft / Then eskalieren 3 → 4 und 4 → 5 (Vergleich über `native_level`), und die Folgeausgabe mit gleicher Stufe in derselben Mikroregion löst **keinen** neuen Alarm aus (Identität = Mikroregion, nicht die wechselnde Bulletin-ID).
  - Test: `tests/test_slf_bulletin_kanaele.py` — Alarm-Kette mit Gedächtnis; zwei Eskalationen, ein „still".

- **AC-25:** [Zwei Nutzer] Given Nutzer A mit einem Trip in Graubünden (Winter-Fixture) und Nutzer B mit einem Trip in München / When für beide Trip-Briefing-Mail und -SMS erzeugt werden / Then enthält nur die von A den SLF-Bericht; die von B bleibt unverändert ohne Lagebericht und ohne Hinweis, und das Melde-Gedächtnis von A enthält keinen Eintrag von B und umgekehrt.
  - Test: `tests/test_slf_bulletin_kanaele.py` — zwei Nutzerkontexte nacheinander (kein neuer Endpoint, daher kein HTTP-Zwei-Nutzer-Test).

### Entwarnung (S2)

- **AC-26:** [Absenkung ⇒ Entwarnung über vier Kanäle] Given im Melde-Gedächtnis steht die SLF-Warnung Stufe 4 (`source="slf_bulletin"`) und der aktuelle Lauf liefert bei gesunder Quelle Stufe 2 für dieselbe Mikroregion (abgeleitet aus `at_2026-03-01T08:00:00Z.json`) / When der Alarm-Lauf läuft / Then erhält der Nutzer genau eine Entwarnung „Stufe 4 → 2" (SMS `+AV4>2`) über E-Mail, Telegram, SMS und Premium-SMS (Dringlichkeit des alten Werts), die Mail nennt als Quelle das SLF, und das Gedächtnis steht danach auf 2.
  - Test: `tests/test_slf_bulletin_entwarnung.py` — Trip-Alarm und Ortsvergleich-Alarm, vier Kanäle am echten Versandpfad, Gedächtnis danach.

- **AC-27:** [Feinstufenwechsel ist keine Entwarnung] Given gemeldete Stufe 3 mit Feinstufe plus und ein Folgelauf mit Stufe 3 und Feinstufe minus (und umgekehrt) / When der Alarm-Lauf läuft / Then entsteht weder eine Entwarnung noch ein neuer Alarm, und das Gedächtnis bleibt bei Stufe 3.
  - Test: `tests/test_slf_bulletin_entwarnung.py` — beide Richtungen; keine Nachricht in keinem Kanal.

- **AC-28:** [Quellenwechsel AT↔CH ist keine Entwarnung] Given im Melde-Gedächtnis steht eine Warnung der Quelle `avalanche_report` (AT) für einen Ort-Schlüssel und der Lauf liefert für denselben Schlüssel (Koordinate jetzt in der Schweiz) eine Warnung der Quelle `slf_bulletin` / When der Alarm-Lauf läuft / Then wird die frühere AT-Warnung nicht als „gesenkt" oder „beendet" gemeldet (die AT-Quelle antwortet dort „nicht zuständig", nicht gesund), und die SLF-Warnung wird nach den gewöhnlichen Regeln für neue Warnungen behandelt.
  - Test: `tests/test_slf_bulletin_entwarnung.py` — Gedächtnis mit AT-Eintrag, Lauf in CH; keine Entwarnungs-Notice, genau eine neue Warnung.

- **AC-29:** [Ausfall, leere Saison und verschwundene Region sind keine Entwarnung] Given gemeldete SLF-Stufe 3 / When der nächste Lauf (a) einen SLF-Abruffehler hat, (b) die leere Saison-Antwort `{"bulletins":[]}` erhält, (c) die Region im Bulletin nicht mehr findet, jeweils zwei Läufe hintereinander / Then entsteht in keinem der drei Fälle eine Entwarnung („gesenkt" oder „beendet"), und das Gedächtnis bleibt unverändert.
  - Test: `tests/test_slf_bulletin_entwarnung.py` — drei Fälle × zwei Läufe; keine Nachricht, Gedächtnis gleich.

### Mail-Validator und Doku

- **AC-30:** [Mail-Validator kennt Feinstufe und SLF] Given eine SLF-Warnungs-Mail mit „Lawinenstufe 3- (erheblich)" und Quelle SLF / When `official_alert_mail_validator.py` sie prüft / Then wird sie als Lawinenmail erkannt und besteht (Exit 0); „Lawinenstufe 3- (mäßig)" bleibt ein Fehler (Ziffer und EAWS-Wort müssen zusammenpassen), und eine Mail ohne Quelle bleibt ein Fehler.
  - Test: `tests/tdd/test_official_alert_mail_validator.py` (bestehend, erweitert) — drei Mails: gültig, falsches Wort, ohne Quelle.

- **AC-31:** [Doku] Given die Umsetzung / When sie abgeschlossen ist / Then enthalten `docs/specs/data_sources.md` den Antrag #7 samt Auflagen und Version 1.4, `docs/adr/` das ADR-0091 mit Index-Eintrag (ADR-0089 verweist darauf), `docs/specs/modules/avalanche_report_bulletin.md` den Verweis auf diese Spec statt „Slice 2", und `docs/artifacts/feat-1441-s3-slf/anfrage_slf_entwurf.md` den Entwurf der Anfrage.
  - Test: `# doc-compliance-test` in `tests/test_slf_bulletin_docs.py` (Dokukonformität, kein Verhaltensnachweis); `tests/test_adr_index_drift.py` (bestehend).

## Test Plan

Kern-Schicht (deterministisch, ohne Netz; aufgezeichnete Bulletins als Fixtures, Transport über den Fixture-Mechanismus der Lawinen-Tests):

- [ ] `tests/test_slf_bulletin_parser.py` — AC-1 bis AC-7
- [ ] `tests/test_slf_bulletin_abdeckung.py` — AC-8 bis AC-17 (Zustände, Zuständigkeit, Egress, Registry, Abschaltbarkeit)
- [ ] `tests/test_slf_bulletin_kanaele.py` — AC-3/4 (Text), AC-10 (Hinweis), AC-18 bis AC-25 (Darstellung, Matrix, Ortsvergleich, Eskalation, Zwei Nutzer)
- [ ] `tests/test_slf_bulletin_entwarnung.py` — AC-26 bis AC-29
- [ ] `tests/tdd/test_official_alert_mail_validator.py` (erweitert) — AC-30
- [ ] `tests/test_slf_bulletin_docs.py` — AC-31 (`# doc-compliance-test`)
- [ ] Bestandstests nachlaufen lassen: `tests/test_avalanche_report_*.py` (Parser, Quelle, Coverage, Ausfall-Sichtbarkeit, Kanäle, Eskalation, SMS), `tests/test_egress_inventory_drift.py`, `tests/test_adr_index_drift.py`, `tests/tdd/test_official_alert_allclear*.py`

Mutations-Gegenprobe (Pflicht für den Adversary), jede an der Stelle, an der es wirkt: (1) `covers()` auf BBox umstellen → AC-12 muss rot werden (Innsbruck/Bregenz); (2) Höhenregel „erste Grenze statt Eindeutigkeit" → AC-4 rot; (3) `lowerBound 0` als Höhe → AC-5 rot; (4) Feinstufe in den SMS-Token einfügen → AC-21 rot; (5) Feinstufe aus der Mail entfernen → AC-19 rot; (6) leere Saison als `fetch_failed` → AC-9 rot; (7) leere Antwort mit 24-h-TTL cachen → AC-9 (1801 s) rot; (8) Registrierungsreihenfolge tauschen → AC-16 rot; (9) Vergleich in der Eskalation auf `level` statt `native_level` → AC-24 rot; (10) Feinstufenwechsel als Absenkung werten → AC-27 rot; (11) Maßgeblichkeitssatz aus der Telegram-Langform streichen → AC-18 rot; (12) feste Ausschlussliste einbauen → AC-13 rot.

Live-Schicht: nicht möglich (Abschnitt „E2E- und Staging-Strecke").

## Weitere betroffene Tests (nicht umzudrehen, aber nachlaufen lassen)

`tests/test_avalanche_report_ausfall_sichtbarkeit.py` (:40, Registry-Isolierung per Name), `tests/test_avalanche_report_coverage.py` (:32/:64 Zürich „nicht abgedeckt" bezieht sich auf die S1-Quelle, isoliert per `only_source`; :189-196 Zählung je Name), `tests/test_avalanche_report_source.py`, `tests/test_avalanche_report_parser.py`, `tests/tdd/test_official_alert_allclear_source_health.py`, `tests/tdd/test_official_alert_mail_validator.py` (Spiegel der Gefahrenart-Wörter), Hilfsmodul `tests/helpers/avalanche_report_support.py`. Keine Alt-Tests werden bewusst umgedreht.

## E2E- und Staging-Strecke

Staging und Test blockieren Warn-Hosts (`aws.slf.ch` ist wie `avalanche.report` `BLOCKED`, AC-15); ein echter Abruf ist dort nicht möglich. Der Beleg „funktioniert" kommt deshalb aus den Kern-Tests mit aufgezeichneten Bulletins, die durch die echten Kanal-Renderer laufen (Matrix AC-22, Entwarnung AC-26). Der Mail-Validator ist `.claude/hooks/official_alert_mail_validator.py` (Header `X-GZ-Mail-Type: official-alert`); er läuft in der Kern-Schicht gegen die aus Fixtures gerenderte SLF-Mail (AC-30). Auf Staging gilt die übliche Verifikation des Gesamtstands (HTTP-Smoke, Trip-Briefing eines Wegwerf-Nutzers `gregor-test+…` mit Test-Trip, kein Sammelversand): geprüft wird, dass bestehende Lawinen-Strecken (Tirol) unverändert bleiben und ein Schweizer Punkt wegen des Egress-Blocks ohne Absturz durchläuft (der Block zählt wie ein Abruffehler, AC-10; dass dort ein Ausfallhinweis erscheint, ist kein Befund); **nur Exit 0** der Validatoren erlaubt „E2E bestanden". Staging-Verdict, `/e2e-verify`, Prod-Deploy und Selftest laufen wie üblich am Stück. Der erste echte Live-Beleg einer Stufe aus `aws.slf.ch` ist Folgebeobachtung zur Wintersaison (der Dienst liefert außerhalb der Saison `[]`); bis dahin gilt das Verhalten „sauber leer, kein Ausfallhinweis" (AC-9). **Das Issue #1441 bleibt offen, bis SLF live belegt ist** (PO-Entscheid 16.10.2026).

## Doku-Lieferumfang

- Neues ADR `docs/adr/0091-slf-eigene-lawinenquelle.md` plus Index-Eintrag in `docs/adr/README.md` und Verweis in ADR-0089 (Drift-Test `tests/test_adr_index_drift.py`).
- `docs/specs/data_sources.md`: Antrag #7 SLF (genehmigt mit Auflagen, 17.10.2026), Änderungshistorie 1.4.
- `docs/specs/modules/avalanche_report_bulletin.md`: „Slice 2" (Datenquellen-Antrag und Out of Scope) verweist auf diese Spec.
- `docs/artifacts/feat-1441-s3-slf/anfrage_slf_entwurf.md`: Entwurf der schriftlichen Anfrage an das SLF (Versand durch den PO).
- Nachzug in `/70`: `src/services/official_alerts/data/README.md` (CH-Datei), `docs/reference/sms_format.md` (SLF nutzt dasselbe Token `AV`), `docs/reference/decision_matrix.md` (Quelle SLF).

## Known Limitations

- **Nutzungsklärung offen:** Das SLF veröffentlicht keine ausdrückliche Weiterverwendungs-Lizenz für die API (nur Haftungsausschluss und Eigenverantwortung). Betrieb auf PO-Entscheid mit Auflagen; Ablehnung ⇒ Registrierungszeile entfernen (AC-17).
- **SLF-Ausfall im Mittelland:** Mikroregionen, die das SLF nie bewertet (z. B. `CH-9211` Zürich/Bern), sind per Polygon „zuständig", bis der Abruf die Region als nicht im Bulletin ausweist. Fällt der Abruf aus, erscheint dort der generische Ausfallhinweis, weil keine weitere Quelle die Schweiz abdeckt (AC-14). Eine Ausschlussliste wurde bewusst verworfen (schwankende Regionenzahl 120–135). Dieselbe Eigenschaft besteht heute schon für `meteofrance_vigilance` und `dpc` an Schweizer Punkten (fällt einer der beiden aus, bevor er „nicht zuständig“ feststellt, erscheint der Hinweis ebenso) — S3 führt also keine neue Fehlerklasse ein; eine allgemeine Lösung („letzte bekannte Zuständigkeit bei Ausfall“) betrifft alle Quellen und ist nicht Teil dieser Scheibe.
- **Kein „beendet" bei SLF:** Verschwindet eine Region aus dem Bericht, gilt sie als „nicht zuständig" ⇒ keine Entwarnung (AC-29). Nur eine echte Absenkung (4 → 2) ergibt eine Entwarnung. Das ist die sichere Richtung (im Zweifel keine Schein-Entwarnung).
- **Höhe nicht immer angegeben:** Bei mehrdeutigen Problemen (verschiedene Grenzen) und bei Stufe 1 mit `lowerBound 0` zeigt das Briefing keine Höhe; der Originalbericht (Link) enthält sie.
- **Keine MeteoAlarm-Lawine für die Schweiz:** Die bewusste Doppelung `avalanche` (AW) / `avalanche_bulletin` (AV) aus S1 bleibt gültig, hat für die Schweiz aber heute keinen Gegenpart, weil keine registrierte MeteoAlarm-Quelle die Schweiz abdeckt. Würde eine solche Quelle ergänzt, gilt S1 AC-11 sinngemäß (nie skalenübergreifend vergleichen).
- **Stufe 4/5 nur abgeleitet getestet:** Die aufgezeichneten Bulletins (Dezember bis April) enthalten höchstens Stufe 3; Eskalation und Entwarnung sind mit abgeleiteten Varianten belegt, der echte Beleg folgt zur Saison.
- **Feinstufe in der Entwarnung:** Die Entwarnungs-Meldung nennt nur Ziffern („Stufe 4 → 2"), nicht die Feinstufe.

## Out of Scope

- Weitere Länder oder Dienste (Bayern, Salzburg, übrige AT-Länder, EU-Sammelfeed, `lawinen-warnung.eu`).
- Mehrsprachige SLF-Texte (nur `de`), SLF-Schneehöhen-/Messstationsdaten und Freitext-Beschreibungen des Bulletins (`coreZoneText` u. ä.).
- Handlungsempfehlungen („Route meiden").
- Feinstufe in SMS, Premium-SMS und Telegram-Kurzform (PO-Entscheid 17.10.2026, ADR-0089).
- Ausschlusslisten für nie bewertete Regionen; Anzeige eines „Saison"-Textes.
- Änderung der Warnerkennung, der Kanal-Schwellen, der Go-API oder des Frontends.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0091 (neu, mit dieser Scheibe; ergänzt ADR-0089)
- **Rationale:** ADR-0089 sagt „ein weiteres Land ist ein Tabelleneintrag, kein Parser-Code". Für das SLF trägt das nicht (ein Dokument für die ganze Schweiz, Höhe im Problem statt im Rating, kein Link-Feld, Leere = HTTP 200). Die Abweichung wird dokumentiert, damit sie nicht still als Muster für andere Länder oder als Rückbau-Anlass missverstanden wird.

## Changelog

- 2026-10-17: Initial spec created (v1.0, draft). Grundlage: Kontext-Dokument `docs/context/feat-1441-s3-slf.md` (Analyse 16.10., Nachmessung und PO-Entscheide 17.10.2026), Datenquellen-Antrag #7.
