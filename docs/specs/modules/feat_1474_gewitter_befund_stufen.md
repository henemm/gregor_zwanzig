---
entity_id: feat_1474_gewitter_befund_stufen
type: feature
created: 2026-08-03
updated: 2026-08-03
status: draft
version: "2.4"
tags: [gewitter, alerts, meteofrance, cape, s3, issue-1419]
---

# Gewitter-Befund wird vierstufig — die Stärke bekommt endlich ihre fehlende Stufe (Issue #1474, S3 zu #1419)

## Approval

- [ ] Approved

## Purpose

`ThunderLevel` kennt heute nur drei Werte (`NONE`/`MED`/`HIGH`), von denen `MED` faktisch
tot ist — keine Quelle setzt ihn je, `_parse_thunder_level()` liefert ausschließlich
„kein Gewitter" oder „Gewitter" (WMO 95/96/99). Diese Scheibe gibt der **Stärke**-Skala
(PO-Zitat: „Der bisherige Wert beschreibt die Stärke") ihre vierte, bisher unbesetzte Stufe:
`ThunderLevel.LOW` („leicht"). Die seit `c33e7b28` live anliegende Blitzdichte
(Météo-France, FR/Korsika) und die bereits vorhandene Gewitterenergie (CAPE) speisen
erstmals „leicht"/„mittel"/„schwer" — bisher unerreichbare Stufen werden dadurch real.

**Bewusst NICHT Teil dieser Scheibe:** eine zweite, unabhängige **Wahrscheinlichkeits**-Achse
(„wie sicher ist die Vorhersage") wird als leeres Datenfeld vorbereitet (s. Abschnitt 5), aber
in dieser Scheibe von keiner Quelle befüllt — sie kommt erst mit #1419 S6 (Ensemble-Anbindung,
Kontingent-Messung vorausgesetzt). Ebenso bewusst nicht Teil: „akut"/Radar-Beobachtung — eine
völlig andere Achse (Beobachtung statt Vorhersage), die in dieser Skala keinen Platz hat.

## Source

- **File:** `src/app/models.py`, `src/output/metric_format.py`,
  `src/services/alert_preset.py`, `src/services/weather_change_detection.py`,
  `src/providers/openmeteo.py`, `src/providers/thunder_enrichment.py`,
  `src/services/risk_engine.py`, `src/output/renderers/trip_report.py`,
  `src/output/renderers/sms_trip.py`
- **Identifier:** `ThunderLevel` (Enum), `thunder_level_from_signals()` (neu),
  `ORDINAL_LEVEL_BOUNDS`, `_parse_thunder_level()`, `enrich_thunder()`,
  `RiskEngine._check_thunder()`

**Schicht:** ausschließlich Python-Core (`src/app/`, `src/output/`, `src/services/`,
`src/providers/`). Kein Go, kein Frontend. **Ausdrückliche Ausnahme:**
`src/services/stage_weather.py` (Cockpit-Backend) wird geprüft, aber NICHT geändert — nicht
wegen einer Schichtgrenze (die Go-Seite ist reiner Proxy ohne eigene Farblogik, s. Known
Limitations), sondern weil dem Cockpit eine vierte Farbe für „leicht" fehlt und deren Wahl
eine Design-/Produktentscheidung ist, keine technische.

## Estimated Scope

- **LoC:** ~180-240 Quellcode + ~380-480 Tests — überschreitet voraussichtlich das
  250-LoC-Workflow-Limit (Tests zählen mit); `workflow.py set-field loc_limit_override 500`
  braucht PO-Freigabe vor Implementierungsbeginn.
- **Files:** 14 geändert (0 neu im Produktivcode), 7-9 Testdateien neu/erweitert
- **Effort:** high — viele kleine, aber sicherheitsrelevante Einzelstellen; die
  Alarm-Ordinalskala verschiebt sich real (s. Abschnitt 1), nicht nur additiv am Rand.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` | Vorgänger-Scheibe | liefert `lightning_density_per_km2_3h` regulär für FR/Korsika |
| `docs/adr/0043-empfindlichkeitsstufe-als-niveau-statt-zweiter-alarm-typ.md` | bindende Vorgabe | Bounds-Tabelle ist skalenunabhängig formuliert („die höchste Stufe" bzw. „überhaupt steigt") — s. Abschnitt 2, KEIN wörtliches Zitat zur Stufenzahl beansprucht |
| `docs/adr/0025-...md` | bindende Vorgabe | Sortier- und Render-Skala leben in `metric_format.py`; werden hier zum ersten Mal zahlenmäßig deckungsgleich (s. Abschnitt 1), bleiben aber zwei benannte Funktionen |
| `tests/tdd/test_alert_sensitivity_levels.py` | Regressions-Anker | bestehender Testsatz aus #1460 T1 (AC-4..AC-19) — muss nach dieser Scheibe **unverändert grün** bleiben (s. AC-2) |
| `metric_catalog.py` Eintrag `cape` (`risk_thresholds`) | Quelle | liefert die CAPE-Schwelle 1000 J/kg — bereits produktentschieden, nicht neu erfunden |
| `services.risk_engine.RiskEngine._check_thunder`, `trip_report.py::_RISK_LABELS` (Zeilen 734-745), `sms_trip.py::_SMS_RISK_LABELS` (Zeilen 104-114) | **im Scope** | bekommen je einen `LOW`-Zweig/-Eintrag, s. Abschnitt 4 und AC-12. Beide Konsumenten lesen `assessment.risks` direkt (nicht über `get_max_risk_level()`), deshalb ist die Erweiterung hier eindeutig wirksam |
| `services.stage_weather._compute_one_stage` (`_RISK_TO_COLOR`) | **geprüft, bewusst NICHT im Scope** | Cockpit-Farbe bleibt für `LOW` bei „green" — technisch trivial zu ändern (eine Zeile, Go proxyt nur), aber es fehlt eine vierte Cockpit-Farbe; deren Wahl ist eine Design-Entscheidung außerhalb dieser Scheibe, s. Known Limitations |
| Konzept #1419 (GitHub-Issue, Abschnitt 5) | Namensvorgabe | `thunder_probability_pct` als Feldname für die vorbereitete Wahrscheinlichkeits-Achse |

## Abschnitt 1 — Die Skala bekommt ihre vierte Stufe (KEINE Umdeutung von MED/HIGH)

```
ThunderLevel:   NONE   ->   LOW    ->   MED    ->   HIGH
Bedeutung:      kein        leicht      mittel      hoch/schwer
Ordinal bisher:  0            —           1           2
Ordinal künftig: 0            1           2           3
Render bisher:   0            —           2           3
Render künftig:  0            1           2           3
Token (LEVELS):  -            L           M           H
```

**`LOW` ist der einzige neue Enum-Wert** — der seit jeher unbesetzte Platz `L`
(`metric_format.py:233-236` beschreibt ihn wörtlich als unerreichbar, weil `ThunderLevel`
kein `LOW` kennt). `MED` und `HIGH` behalten Name UND Bedeutung („mittel"/„hoch") — das
bestehende Wort „hoch" (`email/outlook.py:165`) entspricht dem, was in dieser Spec als
„schwer" beschrieben wird; es wird **nicht** umbenannt, um keine unbeauftragte
Textänderung an einem bereits produktiven Label vorzunehmen.

**Render-Skala:** `_THUNDER_LABEL_VALUE` war bereits `{NONE:0, MED:2, HIGH:3}` — additiv um
`LOW:1` ergänzt, bleiben `MED`/`HIGH` auf ihren bisherigen Render-Werten. **Keine
nutzersichtbare Umdeutung eines Bestandswerts.**

**Ordinal-Skala (WICHTIG — hier verschiebt sich real etwas):** `_THUNDER_ORDER` war
`{NONE:0, MED:1, HIGH:2}` — mit `LOW` dazwischen wird sie auf `{NONE:0, LOW:1, MED:2,
HIGH:3}` umgestellt. **`MED` wandert von Ordinal 1 auf 2, `HIGH` von 2 auf 3.** Das ist
kein Nebeneffekt, sondern die eigentliche fachliche Anforderung (eine neue Stufe UNTERHALB
der bisherigen Mittelstufe einzuschieben) — und genau deshalb ist Abschnitt 2 (Alarm-Bounds
auf Namen umstellen) diesmal keine reine Vorsichtsmaßnahme, sondern eine **notwendige
Korrektur**: Jede Stelle, die die Ordinalskala über eine rohe Zahl anspricht, würde sonst
nach dieser Änderung etwas anderes meinen als vorher.

**Konsequenz, positiv:** Sortier- und Render-Skala werden für alle vier Werte **zahlenmäßig
deckungsgleich** (`{0,1,2,3}` in beiden). Sie bleiben trotzdem zwei separate, benannte
Funktionen (`thunder_ordinal()`/`thunder_label_value()`, ADR-0025) — die Konvergenz ist ein
Nebeneffekt dieser einen Erweiterung, keine Fusion der beiden Konzepte, und eine künftige
Änderung an einer der beiden darf sich nicht auf die andere verlassen.

## Abschnitt 2 — Alarm-Bounds auf Namen umstellen (notwendige Korrektur, nicht nur Härtung)

`ORDINAL_LEVEL_BOUNDS` (`alert_preset.py:85-89`) trägt heute rohe Ordinalzahlen
(`entspannt: (2,0)`, `standard: (2,2)`, `sensibel: (1,2)`), die sich auf die **alte**
Ordinalskala beziehen (`2` = „höchste Stufe" = `HIGH`). Bliebe das nach Abschnitt 1
unverändert, bedeutete `2` plötzlich `MED` („mittel") statt `HIGH` — „standard" würde
künftig schon bei „mittel" statt erst bei „hoch" auslösen: eine stille Bedeutungsänderung
einer produktiv laufenden Einstellung, ohne dass der Nutzer etwas geändert hätte.

**Bezug zu ADR-0043** (`docs/adr/0043-empfindlichkeitsstufe-als-niveau-statt-zweiter-alarm-typ.md`,
Zeilen 46-50): Die dortige Zielsemantik-Tabelle ist **skalenunabhängig** formuliert — „die
Gefahrenstufe überhaupt steigt" (sensibel), „die höchste Stufe erreicht wird" (standard), „von
keine Gefahr direkt auf die höchste Stufe" (entspannt) — ohne eine einzige Zahl. Eine vierte
Stufe widerspricht dieser Formulierung nicht: Für „standard" und „entspannt" bleibt „die
höchste Stufe" weiterhin `HIGH` („hoch"), nur „sensibel" bekommt durch `LOW` einen
zusätzlichen, gewollten Auslöser.

**Fix:** `ORDINAL_LEVEL_BOUNDS` wird auf `tuple[ThunderLevel, ThunderLevel]` umgestellt
(`entspannt: (HIGH, NONE)`, `standard: (HIGH, HIGH)`, `sensibel: (MED, HIGH)` — dieselbe
Bedeutung wie heute, jetzt namentlich). `weather_change_detection._ordinal_change_triggers()`
löst die Namen **zur Auswertungszeit** über `thunder_ordinal()` auf. Damit bezieht sich
„standard" nach der Änderung wieder korrekt auf `HIGH` (jetzt Ordinal 3), exakt wie vor der
Skalenerweiterung.

`email/helpers.py:1549` (`thunder_ordinal(lvl) >= 1`) ist vom selben Problem betroffen:
Der Literal `1` meinte bisher „mindestens `MED`" (real nie erreicht) und würde nach der
Verschiebung „mindestens `LOW`" bedeuten — der Satz „Gewitter ab HH:00 · stärkste HH:00"
würde dann bereits bei einem reinen CAPE-Hinweis („leicht", schwächstes und unsicherstes
Signal, s. Abschnitt 3) einen konkreten Uhrzeit-Anspruch erheben. **Entscheidung dieser
Spec:** der Satz bleibt an `MED` („mittel") gebunden — `thunder_ordinal(lvl) >=
thunder_ordinal(ThunderLevel.MED)`. Das erhält das heutige reale Verhalten (bisher löste
nur `HIGH` aus, das bleibt eingeschlossen) und lässt die neue, unsicherste Stufe „leicht"
bewusst außen vor. Dies ist eine Produktentscheidung, keine reine Bugfix-Notwendigkeit —
s. Known Limitations, falls der PO eine andere Grenze wünscht.

`openmeteo._parse_thunder_level()` liefert bei `weather_code is None` künftig `None` statt
`ThunderLevel.NONE` — „kein Wettercode vorhanden" ist keine geprüfte Entwarnung. Für einen
vorhandenen, nicht-Gewitter-Code bleibt `NONE` (das IST eine geprüfte Entwarnung).

## Abschnitt 3 — Fusion: `thunder_level_from_signals()` in `metric_format.py`

Neue reine Funktion (dort wohnt die Skala, ADR-0025 — von Trip **und** Ortsvergleich über
`thunder_enrichment.py` gemeinsam nutzbar):

```
thunder_level_from_signals(
    wettercode_level: Optional[ThunderLevel],   # bereits gesetzt aus _parse_thunder_level()
    lightning_density: Optional[float],          # Blitze/km²/3h
    cape_jkg: Optional[float],
) -> Optional[ThunderLevel]
```

Jedes Signal wird EIGENSTÄNDIG über eine eigene, unabhängige Schwellentabelle in ein
`ThunderLevel` (oder `None` bei keinem Wert) übersetzt — **keine Sonderlogik für die
Blitzdichte**, damit ein künftiges Signal (DWD-Blitzpotenzial, #1457 S2b) mit derselben
Struktur andockt, ohne die Fusion umzubauen:

- **Wettercode:** unverändert durchgereicht (`NONE`/`HIGH`/`None`).
- **Blitzdichte** (Quelle: ECMWF Forecast User Guide §8.1.13 Lightning,
  https://confluence.ecmwf.int/spaces/FUG/pages/673550914/Section+8.1.13+Lightning):
  - `value is None` → kein Signal
  - `0 <= value <= 0,003` → `NONE` (geprüft, unauffällig)
  - `0,003 < value < 0,015` → `LOW` („leicht") — Beleg: „0,1 Blitze/100 km²/h über 3h" als
    ECMWF-Schwelle, ob überhaupt Blitzaktivität zu erwarten ist; umgerechnet auf unser Feld
    (Blitze/km²/3h): `0,1/100 km²/h × 3h = 0,003/km²/3h`.
  - `0,015 <= value < 0,075` → `MED` („mittel") — Beleg: „0,5 Blitze/100 km²/h" als
    ECMWF-Standard-Referenzpunkt, umgerechnet `0,5/100 km²/h × 3h = 0,015/km²/3h`.
  - `value >= 0,075` → `HIGH` („schwer") — 🔴 **NICHT publiziert.** Es gibt keine
    veröffentlichte Skala, die Blitzdichte in leicht/mittel/schwer einteilt (die Fachwelt
    kennt nur „blitzt es überhaupt"-Schwellen). `0,075` ist eine dokumentierte
    Fortschreibung des ECMWF-Verhältnisses (0,003→0,015 ist Faktor 5, einmal weitergeführt),
    **kein belegter Wert** — s. Known Limitations.
  - Plausibilität (real gemessen, kein Beleg für die Grenze selbst): GR20 Refuge de Petra
    Piana, 2026-08-02, Nachmittag mit von vier unabhängigen Quellen bestätigtem Gewitter:
    0,1–0,2 → fällt in „schwer". Dieselbe abgerufene Kachel (201×201 Punkte, 2026-08-03):
    Spanne 0…6,19, davon 470 Punkte > 0 — die Skala hat nach oben viel Luft.
- **CAPE:** eigene, von `display_thresholds["cape"]` (Anzeige-Ampel, Berg-kalibriert
  2026-07-22) ENTKOPPELTE Schwelle: `risk_thresholds["cape"] = {"medium": 1000.0, "high":
  2000.0}` (`metric_catalog.py:317`, bereits produktentschieden, bereits von
  `RiskEngine._check_thunder` für die allgemeine Risiko-Übersicht genutzt).
  - `value is None` → kein Signal
  - `value < 1000` → `NONE`
  - `value >= 1000` → `LOW` („leicht") — **gedeckelt, egal wie hoch der Wert.** CAPE misst
    verfügbare Energie, kein Ereignis — ohne Auslöser passiert trotz hohem CAPE nichts.
    `risk_thresholds["cape"]["high"] = 2000` wird **nicht** für eine Eskalation auf
    `MED`/`HIGH` verwendet und bleibt ausschließlich der bestehenden Risiko-Übersicht
    vorbehalten. Plausibilität (real gemessen, GR20 Refuge de Petra Piana): 2026-08-02
    Nachmittag mit bestätigtem Gewitter CAPE 2630; 2026-08-03, ruhiges Wetter, CAPE 20 — der
    Abstand zur 1000er-Grenze ist in beide Richtungen deutlich.
- **DWD-Blitzpotenzial `lpi` (J/kg, #1457 S2b — vorbereitet, NICHT Teil dieser Scheibe):**
  keine Code-Änderung, nur zur Dokumentation der künftigen Andock-Form:
  `>1` → „leicht", `>=30` → „mittel", `>=50` → „schwer" (Verifikationsstudie
  COSMO-D2/ICON-D2, https://asr.copernicus.org/articles/19/29/2022/ — LPI>1 als
  Blitz-ja/nein-Schwelle; 30/40/50 als geprüfte Schwellen in derselben Fachliteratur). S2b
  fügt hier lediglich einen weiteren Parameter mit eigener Drei-Schwellen-Übersetzung
  hinzu, ohne `thunder_level_from_signals()` selbst umzubauen.

**Fusion:** „Schärfstes vorhandenes Signal gewinnt" über das bereits existierende
`max_thunder()`, angewendet auf die Liste der NICHT-`None`-Einzelsignale. Sind ALLE drei
Signale `None`, liefert die Funktion `None` (keine Aussage). Ist mindestens eines nicht
`None`, liefert sie das höchste unter den vorhandenen — ein `None`-Signal geht NIE als
`NONE` in den Vergleich ein.

**Anschluss** (`thunder_enrichment.enrich_thunder()`, unverändert „DER gemeinsame Anschluss"
für Trip **und** Ortsvergleich, Muster #1457 S2a AC-8/AC-9): nach dem bestehenden Füllen von
`dp.lightning_density_per_km2_3h` ruft die Funktion zusätzlich `thunder_level_from_signals(
dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg)` und überschreibt
`dp.thunder_level` mit dem Ergebnis — außer das Ergebnis ist `None` UND `dp.thunder_level`
trägt bereits einen Wert (dann bleibt der bestehende Wert erhalten).

## Abschnitt 4 — Ausgaben: geteilte Label-Quelle UND die Risiko-Übersicht bewusst erweitert

**Geteilte Quelle statt Kopien** (CLAUDE.md-Teilungspflicht): eine neue
`THUNDER_LABEL_DE: dict[ThunderLevel, str] = {NONE: "kein", LOW: "leicht", MED: "mittel",
HIGH: "hoch"}` in `metric_format.py`. Fünf Ausgabestellen lesen daraus das deutsche Wort für
`LOW`, behalten Farbe/Formatierung aber lokal (Kanal-Styling ist keine fachliche Aussage):

| Datei | Änderung |
|---|---|
| `email/outlook.py:165-166` | `_THUNDER_LEVEL_LABEL`/`_THUNDER_LEVEL_BG` bekommen eine `LOW`-Zeile (Farbe heller als `MED`) |
| `email/compare_html.py:164-165` | `_THUNDER_LEVEL_LABEL` bekommt `LOW: "leicht"`; `_THUNDER_SEV` bekommt `LOW: "caution"` (nächstschwächere Stufe unter `warn`/`danger`, passend zum bestehenden Vier-Ampel-Vokabular `ok/caution/warn/danger`, `compare_html.py:73`) |
| `email/helpers.py:736-758` (`_THUNDER_MAP`) | neue `LOW`-Zeile (`word: "leicht"`, `sms: "GEW-LOW"`, Farbe zwischen `NONE` und `MED`) |
| `email/helpers.py:850` (`_TREND_THUNDER_LABELS`) | 🔴 **ordinal-indiziert, verschiebt sich real** — heute `{1: "MED", 2: "HIGH"}`, referenziert auf die ALTE Ordinalskala. Wird `{1: "leicht", 2: "mittel", 3: "hoch"}` (Ordinal 1 ist jetzt `LOW`, nicht mehr `MED`!). Ohne diese Korrektur würde der Mail-Trend-Block ab sofort „mittel" zeigen, wo tatsächlich nur „leicht" vorliegt — derselbe Fehlertyp wie Abschnitt 2, nur im Renderer statt im Alarm-Wächter. |
| `email/html.py:168-175` (`_thunder_risk_level`) | zusätzlicher `"LOW"`-Zweig → `"watch"` (dieselbe Dringlichkeit wie `MED`; die Funktion kennt nur zwei Nicht-Null-Stufen, `risk`/`watch`) |
| `narrow.py:226-233` | vierte Verzweigung: `sev==0→"kein"`, `sev==1→"leicht"`, `sev==2→"mittel"`, `sev>=3→"hoch"` (heute nur drei Zweige, `sev==1` fiel fälschlich in den `HIGH`-Zweig) |

**Risiko-Übersicht (`RiskEngine._check_thunder`, `trip_report.py::_RISK_LABELS` Zeilen
734-745, `sms_trip.py::_SMS_RISK_LABELS` Zeilen 104-114) — bewusst ERWEITERT, nicht
ausgelassen:** Geprüft, nicht vermutet: `_check_thunder()` (`risk_engine.py:121-130`)
prüft heute `ThunderLevel.HIGH`→`RiskLevel.HIGH` und `ThunderLevel.MED`→`RiskLevel.
MODERATE` namentlich; `LOW` kommt in keinem der beiden Zweige vor. `_RISK_LABELS`
(`trip_report.py:734-745`) und `_SMS_RISK_LABELS` (`sms_trip.py:104-114`) haben ebenfalls
**keinen** Eintrag für `(THUNDERSTORM, RiskLevel.LOW)`. Ohne Erweiterung wäre „leicht" hier
NICHT einfach abwesend, sondern FALSCH beschriftet: beide Konsumenten fallen bei einem
unbekannten `(type, level)`-Paar auf einen generischen, englischen Fallback zurück
(`f"⚠️ {top.type.value.title()}"` bzw. `top.type.value.title()`, ergäbe „Thunderstorm") —
sichtbar unpassend in einer sonst durchgängig deutschen SMS („Gewitter", „Sturm", „Regen",
„Kälte").

Diese Scheibe fügt einen dritten Zweig hinzu:
`elif agg.thunder_level_max == ThunderLevel.LOW: risks.append(Risk(type=RiskType.
THUNDERSTORM, level=RiskLevel.LOW))`. Entscheidend für die Wirksamkeit: **Beide
Konsumenten** (`trip_report.py::_determine_risk`, `sms_trip.py::_detect_risk`) lesen
`assessment.risks` **direkt** — sie prüfen `if not assessment.risks: return (...)` und
nehmen sonst `assessment.risks[0]`. Eine Liste mit einem `LOW`-Risiko ist dabei eindeutig
NICHT dasselbe wie eine leere Liste; die Erweiterung ist an dieser Stelle unzweideutig
wirksam (s. AC-12, geprüft an der fertigen Übersicht, nicht nur an der Beschriftungstabelle).

🔴 **Nicht derselbe Fall — dritter Konsument gefunden, bewusst ausgenommen, aber nicht aus
Schichtgründen:** `services/stage_weather.py::_compute_one_stage` (Cockpit-Backend, Zeilen
97-117) geht NICHT über `assessment.risks`, sondern über `RiskEngine.get_max_risk_level()`
(Aggregations-Helfer über mehrere Segmente hinweg) und färbt anschließend über
`_RISK_TO_COLOR = {HIGH: "red", MODERATE: "yellow"}` (`stage_weather.py:32`) — **ohne**
`LOW`-Eintrag. `.get(max_level, "green")` liefert für `RiskLevel.LOW` denselben Wert wie
für „gar kein Risiko gefunden" (`get_max_risk_level()`s eigener Fallback ist ebenfalls
`RiskLevel.LOW`, `risk_engine.py:116`). Das Cockpit färbt Etappen nach dem höchsten Risiko
(rot/gelb/grün); „leicht" bekäme dort mangels vierter Farbe dieselbe Farbe wie „kein
Risiko" (grün) — sichtbar wird die neue Stufe im Cockpit also zunächst nicht.

**Warum trotzdem nicht in dieser Scheibe behoben — geprüft, nicht angenommen:** Die Go-Seite
(`internal/handler/` — es gibt **kein** `stage_weather.go`, nur
`internal/handler/stage_weather_proxy_test.go`) ist reiner **Proxy** ohne eigene Farblogik:
`stage_weather_proxy_test.go:108` erwartet den von Python durchgereichten Wert
(`"risk":"yellow"`), und `grep '"red"\|"yellow"\|"green"' internal/handler/*.go` findet
**ausschließlich** diese Testfixture. Eine Python-Änderung würde also technisch **sofort**
wirken, ohne dass die Go-Seite angepasst werden müsste — **keine Schichtgrenze blockiert
hier**. Der eigentliche Grund ist eine fehlende **vierte Cockpit-Farbe**: `_RISK_TO_COLOR`
kennt nur rot/gelb (plus den impliziten Grün-Default) — ob „leicht" eine eigene Farbe
bekommt oder sich eine bestehende teilt, ist eine Design-Entscheidung (berührt die
Design-Leitprinzipien, CLAUDE.md), keine technische Blockade, und außerhalb dieser Scheibe.

## Abschnitt 5 — Vorbereitetes, leeres Feld: Gewitter-Wahrscheinlichkeit

Der PO hat klargestellt, dass „Stärke" (diese Scheibe) und „Wahrscheinlichkeit" zwei
**getrennte** Felder sind. Keine der heute angebundenen Quellen liefert eine fertige
Gewitterwahrscheinlichkeit (Météo-France AROME GetCapabilities: 46 Größen, ausschließlich
physikalische Felder — keine Wahrscheinlichkeitsgröße darunter). Ableitbar wäre sie einzig
aus dem Open-Meteo-Ensemble (40 parallele Läufe, Anteil mit Gewittercode = Wahrscheinlichkeit;
gemessen 2026-08-02 GR20: 19/40 = 47 %) — der Ensemble-Abruf holt heute aber nur
`temperature_2m,precipitation` (`openmeteo.py:667`), keinen Wettercode je Lauf. Das
nachzuholen erhöht den Verbrauch am knappen Open-Meteo-Kontingent (#1329) und ist laut
Konzept #1419 ausdrücklich Schritt **S6** mit der Auflage „Verbrauch vorher messen".

**Diese Scheibe:** `ForecastDataPoint.thunder_probability_pct: Optional[int] = None`
(`app/models.py`, neben `lightning_density_per_km2_3h`) wird angelegt. Es bleibt in dieser
Scheibe **von jeder Quelle unbefüllt** (`None`), hat **keinen** Renderer-Anschluss (keine
Spalte, kein Token, keine Mail-Erwähnung) und **keine** Summary-/Aggregations-Gegenstelle.
`None` bedeutet „keine Aussage", nie „0 %" (dieselbe Regel wie bei der Stufe). Befüllung ist
#1419 S6 und braucht die dortige Kontingent-Messung zuerst.

## Known Limitations

- **Die dritte Blitzdichte-Grenze (0,075, „mittel"→„schwer") ist NICHT publiziert.** Sie ist
  eine dokumentierte Fortschreibung des ECMWF-Verhältnisses, keine belegte fachliche Grenze —
  nachjustierbar, ohne dass sich der Mechanismus ändert. Der GR20-Beleg vom 2026-08-02 (ein
  von vier Quellen bestätigtes Gewitter, Blitzdichte 0,1–0,2) fällt zwar klar in „schwer",
  beweist aber nicht, dass dieses konkrete Ereignis tatsächlich „schwer" war — nur, dass die
  Grenze nicht absurd hoch gewählt ist.
- **`email/helpers.py:1549` bindet „Gewitter ab HH:00" an `MED`, nicht an `LOW`** — eine
  Produktentscheidung dieser Spec (Abschnitt 2), kein zwingendes Ergebnis der Analyse. Der PO
  kann eine andere Grenze wünschen (z. B. bereits ab „leicht" einen Zeitpunkt nennen); das
  wäre eine kleine, isolierte Folgeänderung an derselben Zeile.
- **DWD-Blitzpotenzial (#1457 S2b)** ist als Tabelle dokumentiert, aber nicht implementiert —
  keine Code-Änderung in dieser Scheibe.
- **`thunder_probability_pct` bleibt leer, bis #1419 S6 den Ensemble-Wettercode abruft** und
  die dort geforderte Kontingent-Messung vorliegt.
- **Hagel-Unterscheidung (#1475)** bleibt offen — WMO 96/99 (Hagel) fällt weiterhin unter
  `HIGH`.
- **„Leicht" ist die erste real genutzte Instanz von `RiskLevel.LOW` im gesamten System**
  (Abschnitt 4). Alle neun anderen `RiskEngine`-Regeln (Wind, Regen, Sicht, …) kennen
  weiterhin nur `medium`/`high`-Schwellen und erzeugen nie einen `LOW`-Befund — diese Scheibe
  öffnet die Risiko-Übersicht bewusst für genau eine Größe (Gewitter), nicht generell.
- 🔴 **Das Cockpit färbt Etappen nach dem höchsten Risiko (rot/gelb/grün). „Leicht" bekäme
  dort mangels vierter Farbe dieselbe Farbe wie „kein Risiko" (grün) — sichtbar wird die
  neue Stufe im Cockpit also zunächst nicht.** Technisch wäre die Ergänzung eine Zeile in
  `stage_weather.py:32` (die Go-Seite proxyt nur, sie spiegelt keine eigene Farblogik — kein
  `internal/handler/stage_weather.go` vorhanden, nur ein Proxy-Test, der den durchgereichten
  Python-Wert erwartet); es fehlt aber eine vierte Cockpit-Farbe, und deren Wahl ist eine
  Design-/Produktentscheidung außerhalb dieser Scheibe. **Offene Frage für den PO: Welche
  Farbe soll „leicht" im Cockpit bekommen** (eigene Farbe oder Teilung mit einer
  bestehenden)? Sobald beantwortet, ist die Umsetzung eine kleine Folge-Scheibe
  (`stage_weather.py` allein — die Go-Seite braucht dafür keine eigene Änderung).
- **Frontend/Editor unverändert.** Gewitter ist bereits eine normale, wählbare Metrik; diese
  Scheibe ändert nur die interne Werte-Bedeutung, keine Bedienoberfläche.

## Acceptance Criteria

**Fundament**

- **AC-1 (additive Erweiterung, keine Umdeutung von MED/HIGH):** Given der neue Enum-Wert
  `ThunderLevel.LOW` / When `thunder_ordinal()` und `thunder_label_value()` mit allen vier
  Werten aufgerufen werden / Then liefern beide Funktionen für jeden Wert identische Zahlen
  `{NONE:0, LOW:1, MED:2, HIGH:3}`, und `thunder_label_value(MED) == 2` sowie
  `thunder_label_value(HIGH) == 3` bleiben **exakt** wie vor dieser Scheibe (kein
  Render-Sprung für Bestandswerte).
  - Test: direkte Aufrufe beider Funktionen mit allen vier Enum-Werten, Rückgabewerte gegen
    die Tabelle in Abschnitt 1 geprüft; zusätzlich ein Vorher/Nachher-Vergleich für
    `thunder_label_value(MED)`/`(HIGH)`, der beweist, dass sich diese zwei konkreten Werte
    NICHT verändert haben.

- **AC-2 (Pflicht-Zusicherung — Alarm-Auswertung bleibt für Bestandswerte identisch, TROTZ
  Ordinal-Verschiebung):** Given der bestehende Testsatz
  `tests/tdd/test_alert_sensitivity_levels.py` (AC-4..AC-19 aus #1460 T1, deckt alle drei
  Empfindlichkeitsstufen × Verschärfung/Entwarnung mit `ThunderLevel` aus `{NONE, MED,
  HIGH}`) / When er nach dieser Änderung unverändert ausgeführt wird / Then bleibt **jeder
  einzelne Testfall grün mit demselben Ergebnis** wie vorher.
  - Test: `uv run pytest tests/tdd/test_alert_sensitivity_levels.py` läuft ohne
    Code-Änderung an dieser Datei vollständig grün. **Gegenprobe (scharf, weil die
    Ordinalskala sich diesmal wirklich verschiebt):** Bleibt `ORDINAL_LEVEL_BOUNDS`
    fälschlich bei den alten Rohzahlen `(2,0)/(2,2)/(1,2)` statt auf benannte
    `ThunderLevel`-Tupel umgestellt zu werden, MUSS „standard" nach dieser Änderung bereits
    bei `MED` (statt erst bei `HIGH`) auslösen — mindestens einer der bestehenden Testfälle
    (z. B. der heutige AC-6-Fall „standard bei NONE→MED löst NICHT aus") muss dadurch rot
    werden.

- **AC-3 (heimtückischer Literal an eine benannte Stufe gebunden statt an eine Rohzahl):**
  Given eine Etappe, deren Stundenreihe NUR `ThunderLevel.LOW` („leicht", ausschließlich über
  CAPE gesetzt) trägt, nie `MED`/`HIGH` / When die E-Mail-Prosa gerendert wird
  (`email/helpers.py`, Zweig um Zeile 1549) / Then erscheint der Satz „Gewitter ab HH:00 ·
  stärkste HH:00" **nicht**. Given STATTDESSEN mindestens eine Stunde `ThunderLevel.MED`
  („mittel") erreicht / Then erscheint er.
  - Test: zwei gerenderte Mail-Prosa-Fälle (nur `LOW` vs. mindestens eine `MED`-Stunde) gegen
    das Vorhandensein des Satzes geprüft. Gegenprobe: Bleibt der Literal `>= 1` unverändert
    (statt auf `thunder_ordinal(ThunderLevel.MED)` gehärtet), löst bereits der reine
    `LOW`-Fall aus — der erste Testfall muss das fangen.

- **AC-4 („keine Aussage" ≠ „keine Gefahr" beim Wettercode):** Given ein
  Vorhersage-Zeitpunkt ohne Wettercode (`weather_code=None`) / When `_parse_thunder_level()`
  aufgerufen wird / Then liefert sie `None`, **nicht** `ThunderLevel.NONE`. Ein Zeitpunkt mit
  vorhandenem, nicht-Gewitter-Wettercode liefert weiterhin `ThunderLevel.NONE`.
  - Test: `_parse_thunder_level(None)` → `None`; `_parse_thunder_level(1)` (bewölkt, kein
    Gewittercode) → `ThunderLevel.NONE`; `_parse_thunder_level(95)` → `ThunderLevel.HIGH`.

**Fusion**

- **AC-5 (Blitzdichte-Dreiteilung, belegt gegen den echten Messwert):** Given die
  Blitzdichte-Werte 0,0 / 0,004 / 0,02 sowie der GR20-Messwert 0,1–0,2 vom 2026-08-02 / When
  `thunder_level_from_signals()` mit jeweils nur diesem Signal (Wettercode und CAPE `None`)
  aufgerufen wird / Then liefert sie der Reihe nach `NONE` / `LOW` („leicht") / `MED`
  („mittel") / `HIGH` („schwer") — der echte GR20-Wert landet in „schwer", konsistent mit dem
  realen Vier-Quellen-Gewittertag.
  - Test: vier Aufrufe mit den genannten Werten, Rückgaben gegen die Schwellen
    0,003/0,015/0,075 geprüft.

- **AC-6 (CAPE gedeckelt bei „leicht", eskaliert NIE):** Given CAPE-Werte 500, 1200 und 2630
  J/kg (Wettercode und Blitzdichte `None`) / When `thunder_level_from_signals()` aufgerufen
  wird / Then liefert sie `NONE` / `LOW` / `LOW` — **auch der hohe Wert 2630 J/kg (realer
  Messwert eines bestätigten Gewitters) bleibt bei `LOW`**, weil CAPE allein nie über
  „leicht" hinaus auslösen darf.
  - Test: drei Aufrufe, alle drei Rückgaben geprüft — insbesondere, dass 2630 J/kg NICHT
    `MED`/`HIGH` liefert. Gegenprobe: Liest die Funktion `risk_thresholds["cape"]["high"] =
    2000` als Eskalationsschwelle, liefert der 2630er-Fall fälschlich `MED` oder `HIGH` — der
    Test muss das fangen.

- **AC-7 („keine Aussage" ≠ „keine Gefahr" in der Fusion):** Given alle drei Signale sind
  `None` / When `thunder_level_from_signals()` aufgerufen wird / Then liefert sie `None`.
  Given STATTDESSEN mindestens ein Signal ist aktiv geprüft und unauffällig (Wettercode-Level
  `NONE`, die anderen beiden `None`) / Then liefert sie `NONE`.
  - Test: Aufruf `(None, None, None)` → `None`; Aufruf `(ThunderLevel.NONE, None, None)` →
    `ThunderLevel.NONE`. Gegenprobe: Vertauscht die Implementierung diese beiden Fälle, muss
    mindestens einer der Tests rot werden.

- **AC-8 (schärfstes Signal gewinnt):** Given Wettercode liefert `NONE`, Blitzdichte 0,02
  („mittel") und CAPE `None` / When `thunder_level_from_signals()` aufgerufen wird / Then
  liefert sie `MED` — das schärfere der zwei vorhandenen Signale. Zweiter Fall: Wettercode
  `HIGH`, Blitzdichte 0,004 („leicht") → Rückgabe `HIGH` (Wettercode gewinnt, weil schärfer).
  - Test: beide Fälle einzeln geprüft.

- **AC-9 (ein Anschluss, kein Sonderweg — Muster #1457 S2a AC-8/AC-9):** Given ein Ort in
  Frankreich/Korsika mit gefüllter Blitzdichte und CAPE / When eine Vorhersage über den
  regulären Weg (`OpenMeteoProvider.fetch_forecast` → `thunder_enrichment.enrich_thunder()`)
  abgerufen wird, egal ob über den Trip-Pfad oder den Ortsvergleichs-Pfad / Then trägt
  `dp.thunder_level` am Ende die fusionierte Stufe, identisch für beide Aufrufer.
  - Test: zwei Aufrufe von `fetch_forecast()` für denselben Korsika-Ort aus unterschiedlichem
    Aufrufkontext liefern identisches, gefülltes `dp.thunder_level`. Gegenprobe: Enthält
    `thunder_enrichment.py` eine Fallunterscheidung nach Aufrufer-Typ, muss dieser Test rot
    werden.

- **AC-10 (vorbereitetes, leeres Wahrscheinlichkeitsfeld):** Given eine reguläre Vorhersage
  / When sie über den heutigen (unveränderten) Weg abgerufen wird / Then trägt
  `ForecastDataPoint.thunder_probability_pct` bei JEDEM Datenpunkt `None`, und KEINE Ausgabe
  (Mail, SMS, Telegram) erwähnt es.
  - Test: eine reguläre Vorhersage prüft `thunder_probability_pct is None` an mehreren
    Datenpunkten; ein Textsuche-Gegentest über eine gerenderte Beispiel-Mail stellt sicher,
    dass kein Wahrscheinlichkeits-Wort/-Symbol für Gewitter auftaucht.

**Ausgaben**

- **AC-11 (geteilte Quelle statt Kopien — „leicht" erscheint konsistent in Token/Mail/
  Telegram):** Given eine Etappe mit `ThunderLevel.LOW` („leicht", ausschließlich über CAPE
  gesetzt) / When dieselbe Etappe durch E-Mail (Outlook-Tabelle, Compare-HTML, Trend-Block,
  Prosa-Risikofarbe), Telegram-Fußzeile UND SMS-Token gerendert wird / Then zeigt **jeder**
  dieser Kanäle ein erkennbares „leicht" (deutsches Wort in Mail/Telegram, Render-Wert 1 /
  Token `L` im SMS) — keiner fällt auf „kein Gewitter" zurück.
  - Test: eine gemeinsame Fixture mit `thunder_level=LOW` durch alle sechs genannten
    Render-Einstiegspunkte schleusen (Produktionspfad, keine Zwischenschicht, ADR-0025
    Entscheidung 5), jede Ausgabe auf das Wort „leicht" bzw. Token `L` geprüft.

- **AC-12 (Risiko-Übersicht zeigt „leicht" — geprüft an der FERTIGEN Übersicht, nicht an der
  Beschriftungstabelle; Gegenprobe gegen „kein Risiko" schließt Blindheit aus):** Given eine
  Vorhersage, deren einziges Risiko ein leichtes Gewitter ist (`ThunderLevel.LOW`, kein
  `MED`/`HIGH`, keine andere Risikoart) / When die Risiko-Übersicht für diese Etappe erzeugt
  wird (`trip_report.py::_determine_risk` UND `sms_trip.py::_detect_risk`, beide über
  `RiskEngine.assess_segment()`) / Then enthält die **fertige Übersicht** einen Eintrag mit
  dem deutschen Wort für „leicht" — nicht den generischen `type.value.title()`-Fallback.
  Given STATTDESSEN eine Vorhersage **ohne jedes Risiko** (auch kein „leichtes" Gewitter) /
  When dieselben zwei Funktionen laufen / Then liefern sie **keinen** Eintrag
  (`("none", "✓ OK")` bzw. `(None, None)`).
  - Test: zwei Fixtures — (a) `thunder_level_max=ThunderLevel.LOW`, alle anderen Risikofelder
    unauffällig: `trip_report.py::_determine_risk` und `sms_trip.py::_detect_risk` liefern
    je ein von „✓ OK"/`None` verschiedenes Ergebnis mit dem Wort „leicht"; (b) dieselbe
    Fixture ohne jedes Risiko (`thunder_level_max=None`, alle anderen Felder ebenfalls
    unauffällig): beide Funktionen liefern das „kein Risiko"-Ergebnis. **Beide Fälle müssen
    sich unterscheiden** — liefern (a) und (b) dasselbe Ergebnis, ist die Kette blind für
    „leicht" und der Test muss das aufdecken statt es zu verstecken. Gegenprobe: Bleibt
    `_check_thunder()` ohne den neuen `LOW`-Zweig, liefert Fixture (a) dasselbe Ergebnis wie
    (b) — der Test muss das fangen. Regressionsschutz: derselbe Testaufbau mit `MED`/`HIGH`
    liefert unverändert die bisherigen Labels.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe bewegt sich innerhalb bestehender, bindender Entscheidungen.
  ADR-0043s Zielsemantik-Tabelle ist skalenunabhängig formuliert und bleibt für „standard"/
  „entspannt" unverändert gültig, weil sich „die höchste Stufe" nicht ändert (Abschnitt 2).
  ADR-0025 hat die Trennung von Sortier- und Render-Skala sowie deren gemeinsamen Wohnort in
  `metric_format.py` bereits festgelegt — beide Funktionen bleiben bestehen, obwohl ihre
  Werte nach dieser Scheibe erstmals zahlenmäßig übereinstimmen (Abschnitt 1).
  `ThunderLevel.LOW` ist eine additive Erweiterung um einen vierten Wert, keine neue
  Architektur-Entscheidungsfläche. `thunder_probability_pct` ist ein vorbereitetes,
  unbefülltes Feld ohne Auswertungslogik — ebenfalls keine eigene Architektur-Entscheidung.

## Changelog

- 2026-08-03: Initial spec created (Issue #1474, S3 zu #1419).
- 2026-08-03: **v2.0 — vollständige Neufassung nach PO-Korrektur.** Das ursprünglich
  angenommene Modell (Umwidmung von `MED`→„möglich"/`HIGH`→„wahrscheinlich", neuer Wert
  `ACUTE` für „akut") war eine Vermischung zweier unabhängiger Achsen (Stärke vs.
  Sicherheit/Beobachtung) und wurde vom PO verworfen. Ersetzt durch: `ThunderLevel.LOW`
  („leicht") als einzige neue Stufe der bestehenden **Stärke**-Skala.
- 2026-08-03: **v2.1 — zwei Korrekturen nach Team-Lead-Review.** (1) Ein Zitat aus
  ADR-0043 („nicht als eigener vierter Wert") stand in einer Vorfassung dieser Spec — dieses
  Zitat existiert im ADR nicht, es war ein Fehler. Ersetzt durch die korrekte, wörtlich
  zitierte Passage. (2) Die Risiko-Übersicht war fälschlich als „bewusst unverändert"
  eingestuft — nach Prüfung und Team-Lead-Vorgabe jetzt im Scope.
- 2026-08-03: **v2.2 — AC-12 auf die fertige Übersicht geschärft, dritter Konsument
  gefunden.** Die Begründung „unproblematisch, weil `stage_weather.py`s Aggregation ‚nichts
  gefunden' und ‚LOW gefunden' ohnehin gleich behandelt" war falsch herum gelesen — genau
  diese Gleichbehandlung ist ein Risiko, kein Freibrief. Geprüft: `trip_report.py::
  _determine_risk` und `sms_trip.py::_detect_risk` lesen `assessment.risks` direkt (KEINE
  Ambiguität dort). Ein DRITTER Konsument, `services/stage_weather.py::_compute_one_stage`
  (Cockpit-Backend), geht dagegen über `get_max_risk_level()` + `_RISK_TO_COLOR` (kein
  `LOW`-Eintrag) und bleibt für „leicht" tatsächlich blind.
- 2026-08-03: **v2.3 — falsche Begründung fürs Nicht-Beheben des Cockpit-Funds korrigiert.**
  v2.2 behauptete, eine Python-Änderung an `stage_weather.py` würde Cockpit und Briefing
  auseinanderlaufen lassen, weil die Go-Seite die Farblogik „spiegele" — **das ist falsch,
  belegt widerlegt.** `internal/handler/stage_weather.go` existiert nicht; die Go-Seite ist
  ein reiner Proxy (`internal/handler/stage_weather_proxy_test.go:108` erwartet den von
  Python durchgereichten Wert, keine eigene Zuordnung in `internal/handler/*.go`). Eine
  Python-Änderung würde technisch sofort und korrekt wirken. Der tatsächliche Grund, warum
  diese Scheibe das nicht behebt: dem Cockpit fehlt eine **vierte Farbe** für „leicht"
  (`_RISK_TO_COLOR` kennt nur rot/gelb/grün-Default) — deren Wahl ist eine Design-
  /Produktentscheidung, keine technische Blockade. Known Limitation und offene PO-Frage
  entsprechend umformuliert („welche Farbe?" statt „soll das Cockpit ‚leicht' zeigen?").
- 2026-08-03: **v2.4 — Adversary-Findings F001/F002/F003 behoben, Abschnitt 4 jetzt
  vollständig umgesetzt.** F001: `compare_metric_catalog.py`s `ordinalLabels` für
  `thunder_level_max` hatte nur drei statt vier Einträge (fehlendes „leicht") — der
  Ortsvergleichs-Schieberegler konnte „hoch" nicht erreichen; behoben, neuer struktureller
  Wächter-Test leitet die Erwartung aus `ThunderLevel`/`thunder_ordinal()` ab. F002: acht
  Rohwerte in `tests/tdd/test_issue_640_trend_threshold_times.py` bezogen sich noch auf die
  ALTE Ordinalskala (MED=1 statt MED=2) — behoben, plus vollständige Suche über `tests/`
  bestätigt keine weiteren Fundstellen. F003 (ursprünglich als bewusste Abweichung geplant)
  entfällt als Abweichung: `narrow.py`s Telegram-Fußzeile („MED"/„HIGH") wurde beim Beheben
  von F002 sichtbar als einzige verbliebene englische Ausgabe, während `outlook.py` und
  `email/helpers.py` bereits die geteilte deutsche Quelle `THUNDER_LABEL_DE` nutzten — ein
  Sprachwiderspruch innerhalb derselben Telegram-Nachricht (dieselbe Erwägung wie bei
  AC-12, ein Widerspruch innerhalb einer Ausgabe kostet mehr Vertrauen als eine fehlende
  Angabe). `narrow.py:225-231` wurde auf `THUNDER_LABEL_DE` umgestellt (keine vierte eigene
  Wortliste); ~9 betroffene Assertions in `tests/tdd/test_sms_daywindow_aggregation.py`,
  `tests/tdd/test_daywindow_configurable.py`, `tests/tdd/test_sms_thunder_from_hourly_
  timeseries.py` auf die deutschen Wörter nachgezogen (nur der Wortlaut, die geprüfte
  fachliche Aussage blieb unverändert). Abschnitt 4 ist damit für alle sechs
  Ausgabestellen sprachlich konsistent.
