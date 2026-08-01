---
entity_id: fix_1435_e3b_sms_kuerzel
type: bugfix
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [metric-catalog, sms, trip, naming, register]
workflow: fix-1435-e3b-sms-kuerzel
---

# Fix #1435 Etappe E3b — Touren-SMS übernimmt die Register-Kürzel für Schnee

## Approval

- [x] Approved — PO Henning, 2026-08-01 („Go")

## Purpose

Die Touren-SMS benennt drei Wettergrößen mit anderen Kürzeln als das zentrale
Wetter-Namensregister (`metric_catalog.py`): Schneehöhe heißt dort `SN` statt
`SD`, Schneefallgrenze `SFL` statt `SL`, Neuschnee `SN24+` statt `NS24+`.
Dadurch bedeutet `SN` in derselben SMS-Zeile zwei verschiedene Dinge: die
amtliche Schneewarnung (`HAZARD_SMS_SYMBOLS["snow"] = "SN"`, Form `!SN:H@14`)
und die Schneehöhe (`SN180`). Nur die Position im Format trennt beide, nicht
die Bedeutung — ein Nutzer, der mitten in der SMS liest, kann sie nicht
unterscheiden. E3b vereinheitlicht alle drei Kürzel auf die Register-Werte
und beendet damit die Doppelbedeutung von `SN`.

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/output/`), keine
> Go-Beteiligung, keine Frontend-Änderung (das Frontend liest die Kürzel zur
> Laufzeit über `/api/sms-symbols`, führt keine eigene Liste).

- **File:** `src/output/renderers/sms_trip.py`
- **Identifier:** `SMS_SYMBOL_BY_METRIC` (Modul-Konstante, Zeile 55)
- **File:** `src/output/tokens/builder.py`
- **Identifier:** `PRIORITY` (Zeile 37), `POSITIONAL` (Zeile 60), `_wintersport()` (Zeile 183)
- **File:** `src/output/tokens/render.py`
- **Identifier:** `DROP_ORDER` (Zeile 10)
- **File:** `src/output/adapters/trip_result.py`
- **Identifier:** `_wintersport_default_config()` (Zeile 196)

## Estimated Scope

- **LoC:** ~60-90 Produktivcode (reine Literal-Umbenennung an vier Stellen +
  Ableitung von `SMS_SYMBOL_BY_METRIC` aus dem Register statt Literal-Dict) +
  ~200-300 Testcode (neue Ratsche mit Wirksamkeitsnachweis + Anpassung von
  ~14 bestehenden Testdateien/Golden-Dateien, s. „Betroffene Tests") +
  ~80-150 Doku-Zeilen (Wire-Format-Referenz + zwei Spezifikationen + ADR-
  Nachtrag + Archiv-Annotation, s. „Mitzuziehende Dokumentation"). Der
  Produktivcode-Anteil bleibt **unter** dem 250-Zeilen-Deckel des Workflows —
  keine Override-Anfrage nötig. Gesamtsumme (inkl. Tests/Doku, die laut
  CLAUDE.md nicht auf den Deckel angerechnet werden) liegt bei ~340-540
  Zeilen; das ist plausibel für „drei Literale an vier eng verzahnten
  Stellen ersetzen plus Wirksamkeitsnachweis", nicht beschönigt.
- **Files:** 4 Produktivdateien geändert (`sms_trip.py`, `builder.py`,
  `render.py`, `trip_result.py`), 0 neu; 1 neue Testdatei (Ratsche), ~13
  bestehende Testdateien angepasst, 2 Golden-Dateien angepasst; 4
  Doku-Dateien inhaltlich geändert, 2 Doku-Dateien annotiert (Archiv-Spec,
  ADR-0011).
- **Effort:** low-medium — die Änderung selbst ist eine reine
  Literal-Umbenennung; der Aufwand steckt im lückenlosen Mitziehen aller
  Verbraucher-Stellen (Risiko 3 im Kontext-Dokument) und im
  Wirksamkeitsnachweis der Ratsche.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py::get_sms_code()` | READ (neue Quelle) | Liefert `sms_code` für `snow_depth`→`SD`, `snowfall_limit`→`SL`, `fresh_snow`→`NS`; wird ab E3b in `sms_trip.py` gelesen (analog `alert/render.py:12,90`, `comparison.py:23,519`) |
| `src/output/tokens/dto.py::MetricSpec` | UNVERÄNDERT | Trägt `symbol` als String-Schlüssel — Träger der Umstellung, keine strukturelle Änderung |
| `src/output/renderers/trip_report.py` (Schwellwerte #624, Zeilen 263-267; Abwahl #944, Zeilen 270-276) | READ (Verbraucher) | Baut `_sms_thr`/`_disabled_sms_specs` aus `SMS_SYMBOL_BY_METRIC.items()` — zieht automatisch mit, sobald die Konstante die neuen Werte liefert |
| `api/routers/config.py::get_sms_symbols()` | READ (Verbraucher) | Serialisiert `SMS_SYMBOL_BY_METRIC` unverändert generisch — kein eigener Code-Pfad nötig |
| `src/output/tokens/hazard_symbols.py::HAZARD_SMS_SYMBOLS["snow"]` | UNVERÄNDERT | Bleibt `"SN"` (amtliche Schneewarnung) — Grund der Umstellung, nicht ihr Gegenstand |
| `docs/specs/_archive/modules/issue_917_alert_renderer.md` | ANNOTIERT | AC-9 friert `SFL` ein — wird als durch E3b aufgehoben markiert |
| `docs/adr/0011-alert-render-single-backend-renderer.md` | ERGÄNZT (Nachtrag) | Ziel 3 („doppelte Mappings entfernen") war für den Briefing-SMS-Pfad ausgenommen; die Ausnahme wird revoziert |

## Implementation Details

### 1. `SMS_SYMBOL_BY_METRIC` wird aus dem Register abgeleitet

`src/output/tokens/` importiert bewusst nichts aus `src/app/` (geprüfte
Schichtgrenze: nur `utils`, `dto`, `metrics`) — dort bleiben die Kürzel
Literale. `src/output/renderers/` darf das Register lesen und tut es bereits
(`alert/render.py`, `comparison.py`). Deshalb wird ausschließlich
`sms_trip.py::SMS_SYMBOL_BY_METRIC` umgebaut:

```
"snow_depth": get_sms_code("snow_depth"),       # -> "SD"
"snowfall_limit": get_sms_code("snowfall_limit"), # -> "SL"
"thunder": "TH:",                                 # benannte Ausnahme: Grammatik
```

`precipitation`/`rain_probability`/`wind`/`gust` bleiben unverändert (Werte
sind bereits identisch zum Register). `thunder` bleibt ausdrücklich als
Literal stehen — `TH:` ist Grammatikform (Doppelpunkt), keine Register-ID.
Nach diesem Umbau kann `SMS_SYMBOL_BY_METRIC` für diese Größen nicht mehr
vom Register abweichen — es ist keine gepflegte Liste mehr, sondern eine
Ableitung.

**Neuschnee (`fresh_snow`) ist kein Eintrag von `SMS_SYMBOL_BY_METRIC`** —
das Symbol `SN24+`/`NS24+` entsteht literal in `builder.py::_wintersport()`
und `render.py::DROP_ORDER` (Suffix `24+` ist Grammatik, kein Register-Feld).
Diese Stellen werden unten unter Punkt 2 als Literal umgeschrieben, nicht
über das Register abgeleitet — konsistent mit dem `TH:`-Muster.

### 2. Literale in der app-freien Formatschicht umschreiben

Vier Fundstellen, die **gemeinsam** ziehen müssen (Risiko 3 im
Kontext-Dokument — zieht eine nicht mit, greift ein Schwellwert-Filter oder
die Abwahl lautlos nicht mehr):

| Datei | Fundstelle | Alt → Neu |
|---|---|---|
| `builder.py:38` | `PRIORITY` | `"SFL": 2, "SN24+": 2, "SN": 2` → `"SL": 2, "NS24+": 2, "SD": 2` |
| `builder.py:70-71` | `POSITIONAL` | `("SN", …), ("SN24+", …), ("SFL", …)` → `("SD", …), ("NS24+", …), ("SL", …)` |
| `builder.py:186-190` | `_wintersport()` Paare | `("SN", day.snow_depth_cm)`, `("SN24+", day.snow_new_24h_cm)`, `("SFL", day.snowfall_limit_m)` → `("SD", …)`, `("NS24+", …)`, `("SL", …)` |
| `builder.py:198` | inverse Schwellwertlogik (#873) | `if sym == "SFL":` → `if sym == "SL":` |
| `render.py:10` | `DROP_ORDER` | `["DBG", "WC", "AV", "SFL", "SN24+", "SN", …]` → `["DBG", "WC", "AV", "SL", "NS24+", "SD", …]` (Reihenfolge der Einträge unverändert, nur die Kürzel selbst) |
| `trip_result.py:206-208` | `_wintersport_default_config()` | `MetricSpec(symbol="SN", …)`, `MetricSpec(symbol="SN24+", …)`, `MetricSpec(symbol="SFL", …)` → `symbol="SD"`, `symbol="NS24+"`, `symbol="SL"` |

`PRIORITY[sym]` in `builder.py:204` ist ungeschützt (Kontext-Dokument Risiko
4) — ein vergessener Schlüssel bricht die SMS-Erzeugung mit einem Absturz,
nicht mit einer stillen Auslassung. Das ist in diesem Fall hilfreich: eine
unvollständige Umbenennung fällt hier laut auf, nicht lautlos wie beim
Schwellwert-Filter.

`AV` (Lawinenstufe) und `WC` (gefühlte Temperatur) bleiben in allen drei
Tabellen unverändert stehen.

### 3. Ratsche (neuer Test, Testschicht darf beides importieren)

Neue Datei `tests/unit/test_sms_token_symbol_register_ratchet.py` (Name nach
Verhalten, nicht nach Issue-Nummer). Sie vergleicht die in `builder.py`,
`render.py` und `trip_result.py` tatsächlich verwendeten Symbole gegen
`metric_catalog.get_sms_code()` und benennt jede Abweichung konkret (welche
Größe, welches Symbol erwartet, welches gefunden). Ausnahmen stehen als
ausdrückliche, kommentierte Liste im Test — keine stille Auslassung:

- `AV` — kein Registereintrag (Lawinenstufe)
- `WC`/`FN`/`FK`/`FD` — vier Kürzel für eine Größe (`wind_chill`/`TF`),
  strukturell nicht aus einem einzelnen `sms_code`-Feld ableitbar
- `TH:` — Grammatikform (Doppelpunkt), Register kennt nur `TH`
- `24+`-Suffix bei `NS24+` — Grammatik, kein Registerfeld

Die Ratsche prüft `PRIORITY`, `POSITIONAL` und `DROP_ORDER` gegen dieselbe
Ausnahmeliste, damit eine künftige Änderung an einer der drei Stellen ohne
Mitziehen der anderen auffällt.

## Expected Behavior

- **Input:** Ein Nutzer mit aktiviertem Wintersport-Profil und den Metriken
  Schneehöhe, Neuschnee, Schneefallgrenze erhält ein Touren-Briefing (morgens
  oder abends) per E-Mail/Telegram mit eingebetteter SMS-Kurzform.
- **Output:** Die SMS-Zeile trägt `SD180` (statt `SN180`), `NS24+25` (statt
  `SN24+25`), `SL1800` (statt `SFL1800`). Eine in derselben Zeile vorhandene
  amtliche Schneewarnung bleibt `!SN:H@14` — jetzt ohne Doppelbedeutung, weil
  kein anderes Token mehr mit `SN` beginnt außer der Warnung selbst.
- **Side effects:** Bereits konfigurierte Schwellwerte (`sms_threshold` für
  Schneehöhe/Schneefallgrenze) und Metrik-Abwahlen bleiben wirksam — sie sind
  über `metric_id` gespeichert, nicht über das Symbol (s. AC-10). Kein
  Migrations-Schritt nötig.

## Acceptance Criteria

- **AC-1:** Given eine SMS-Zeile wird mit Wintersport-Profil und vorhandenen
  Schneedaten erzeugt / When sie gerendert wird / Then trägt sie die Kürzel
  `SD` für Schneehöhe, `NS24+` für Neuschnee und `SL` für Schneefallgrenze —
  nicht mehr `SN`, `SN24+`, `SFL`. Gilt für beide Berichtsarten
  (morning/evening) gleichermaßen.
  - Test: `tests/golden/sms/arlberg-winter-morning.txt` und die
    Wintersport-Zeile in `tests/golden/text_report/stubaier-skitour-evening.txt`
    zeigen die neuen Kürzel; ergänzend ein direkter Aufruf von
    `build_token_line(..., profile="wintersport")` für beide `report_type`-Werte.
  - **Formulierungs-Korrektur 2026-08-01 (RED-Phase):** Die ursprüngliche
    Fassung lautete „…When der Nutzer ein Trip-Briefing erhält…". Das ist
    heute **nicht erfüllbar** — s. Known Limitation „Der Briefing-Pfad
    erzeugt keine Wintersport-Token" und Issue #1450. Das AC prüft deshalb
    den Token-Erzeuger mit Wintersport-Profil, denselben Pfad, den auch die
    Golden-Tests fahren. Nutzersichtbar wirksam wird E3b heute über AC-8
    (die Kürzel-Anzeige im Editor).

- **AC-2:** Given ein Nutzer hat für Schneehöhe einen SMS-Schwellwert
  konfiguriert (z. B. „nur anzeigen ab 50 cm") / When die aktuelle
  Schneehöhe unter diesem Schwellwert liegt / Then bleibt der
  Schneehöhe-Token in der SMS weiterhin unterdrückt — der Schwellwert-Filter
  (#624) wirkt nach der Umstellung identisch wie davor.
  - Test: `trip_report.py`-Pfad mit gesetztem `sms_threshold` für
    `snow_depth` und einem Tageswert unterhalb der Schwelle aufrufen; Token
    `SD…` erscheint NICHT in der gerenderten Zeile. Gegenprobe mit einem Wert
    oberhalb der Schwelle: Token erscheint.

- **AC-3:** Given ein Nutzer hat für Schneefallgrenze einen SMS-Schwellwert
  konfiguriert / When die aktuelle Schneefallgrenze ÜBER diesem Schwellwert
  liegt / Then bleibt der Schneefallgrenze-Token weiterhin unterdrückt (die
  Logik ist bei dieser Größe umgekehrt: hoch = irrelevant, #873) — nicht
  umgekehrt und nicht ausgeschaltet. Ein Wert UNTER dem Schwellwert erzeugt
  weiterhin den Token.
  - Test: `_wintersport()` bzw. der volle Trip-Pfad mit `sms_threshold` für
    `snowfall_limit` und je einem Tageswert über und unter der Schwelle;
    Token `SL…` erscheint nur im Unter-Schwelle-Fall.

- **AC-4:** Given ein Nutzer hat im Trip die Metrik Schneehöhe (oder
  Schneefallgrenze) nicht ausgewählt / When er ein Briefing mit
  Wintersport-Profil erhält / Then erscheint der zugehörige Token trotz
  vorhandener Schneedaten nicht in der SMS — die Abwahl (#944) wirkt nach
  der Umstellung weiterhin.
  - Test: Trip-Konfiguration ohne `snow_depth` in `dc.metrics`, Vorhersage
    mit vorhandenem `snow_depth_cm`; gerenderte SMS enthält kein `SD…`-Token.

- **AC-5:** Given eine SMS-Zeile mit allen Wintersport-Token / When die
  Token-Reihenfolge geprüft wird / Then erscheinen `SD`, `NS24+`, `SL`, `AV`,
  `WC` in exakt derselben relativen Reihenfolge wie vor der Umstellung — nur
  die Kürzel selbst haben sich geändert, nicht ihre Position im Format.
  - Test: Golden-Vergleich `tests/golden/sms/arlberg-winter-morning.txt`
    (Positions-Check über die gesamte Zeile, nicht nur Substring-Suche).

- **AC-6:** Given eine SMS-Zeile überschreitet das 160-Zeichen-Limit / When
  die Kürzungslogik (§6) greift / Then fallen dieselben Token in derselben
  Reihenfolge wie vor der Umstellung — Schneehöhe, Neuschnee und
  Schneefallgrenze fallen weiterhin an der bisherigen Stelle der
  Drop-Reihenfolge, nur unter ihrem neuen Kürzel.
  - Test: bestehender Truncation-Test aus `tests/unit/test_token_builder.py`
    (Regex-Nachweis, s. „Betroffene Tests") mit auf `SD`/`NS24+`/`SL`
    angepasstem Muster; Reihenfolge der wegfallenden Symbole bleibt
    identisch zum Vorzustand.

- **AC-7:** Given eine SMS-Zeile mit amtlicher Schneewarnung UND
  Schneehöhe-Token gleichzeitig / When die Zeile zugestellt wird / Then
  heißt die amtliche Warnung weiterhin `SN` (`!SN:H@14`), während kein
  anderer Token in derselben Zeile mehr mit `SN` beginnt — die
  Doppelbedeutung ist behoben, ohne dass die Warnung selbst umbenannt wurde.
  - Test: Fixture mit `official_alerts` enthält eine Schneewarnung UND
    aktivem Wintersport-Profil; gerenderte Zeile enthält `!SN:` genau einmal
    und `SD`/`NS24+`/`SL`, aber kein zweites `SN`-Präfix.

- **AC-8:** Given das Frontend ruft `GET /api/sms-symbols` ab / When die
  Antwort ausgewertet wird / Then zeigt sie für Schneehöhe/Schneefallgrenze
  die neuen Kürzel `SD`/`SL` — ohne dass im Frontend-Code eine eigene Liste
  gepflegt werden musste (der Endpunkt serialisiert `SMS_SYMBOL_BY_METRIC`
  weiterhin generisch).
  - Test: API-Contract-Test (FastAPI TestClient) gegen `/api/sms-symbols`,
    prüft `metric_id="snow_depth"` → `sms_symbol="SD"` und
    `metric_id="snowfall_limit"` → `sms_symbol="SL"`.

- **AC-9:** Given ein Symbol in `PRIORITY`, `POSITIONAL` oder `DROP_ORDER`
  wird versehentlich künftig wieder vom Register abweichend geändert / When
  die Ratsche läuft / Then schlägt sie fehl und benennt die betroffene
  Wettergröße und das gefundene sowie das erwartete Symbol konkret.
  - Test: `tests/unit/test_sms_token_symbol_register_ratchet.py` — s.
    Abschnitt „Wirksamkeitsnachweis der Ratsche" für die Lieferbedingung.

- **AC-10:** Given ein Nutzer hat vor dieser Änderung einen SMS-Schwellwert
  oder eine Metrik-Auswahl gespeichert / When diese Änderung ausgeliefert
  wird, ohne dass der Nutzer etwas tut / Then bleibt die gespeicherte
  Einstellung unverändert wirksam — Einstellungen liegen als `metric_id`
  (z. B. `"snow_depth"`) vor, nie als SMS-Symbol; kein gespeicherter Wert
  wird durch die Kürzel-Umstellung entwertet.
  - Test: Bestandsprüfung, dass in `data/` kein gespeichertes `"SN"`/`"SFL"`
    als Symbol-Literal existiert (nur `metric_id`-Schlüssel); ergänzend ein
    Roundtrip-Test, der eine Fixture mit gesetztem `sms_threshold` für
    `snow_depth` vor und nach der Code-Änderung lädt und byteidentische
    Werte nachweist.

## Wirksamkeitsnachweis der Ratsche

**Prüfdatum: 2026-10-30** (Regel-Budget, CLAUDE.md).

Erfahrung aus Etappe E3a: zwei Wächter waren grün, ohne je etwas geprüft zu
haben. Die Ratsche aus AC-9 gilt deshalb erst als geliefert, wenn folgender
Nachweis erbracht und im PR/Commit protokolliert ist:

1. Eines der drei Symbole (`SD`, `NS24+` oder `SL`) wird in einer lokalen,
   nicht committeten Kopie absichtlich verfälscht (z. B. `PRIORITY["SD"]`
   umbenannt in `PRIORITY["SN"]`, ohne die anderen beiden Stellen
   mitzuziehen).
2. Der Ratschen-Test wird gegen diese verfälschte Kopie ausgeführt.
3. Die Ausgabe wird protokolliert und muss zeigen: (a) der Test schlägt
   fehl (nicht grün, nicht übersprungen), (b) die Fehlermeldung nennt die
   betroffene Wettergröße beim Namen (nicht nur „assertion failed" ohne
   Kontext).
4. Die Verfälschung wird danach zurückgenommen; der reguläre, korrekte Code
   läuft grün.

Ohne diesen protokollierten Nachweis gilt die Ratsche als nicht abgenommen,
unabhängig davon, ob sie „grün" ist — grün beweist an dieser Stelle nichts,
solange nicht auch belegt ist, dass sie bei einem echten Fehler rot wird.

## Aufgehobene Festlegungen

E3b hebt zwei zusammenhängende, dokumentierte Festlegungen mit
**PO-Entscheid vom 2026-08-01** ausdrücklich auf:

1. **`docs/specs/_archive/modules/issue_917_alert_renderer.md:173` (AC-9).**
   Diese AC friert `SFL` (und implizit `SN`/`SN24+`) als „stehendes
   Briefing-Kürzel, unveränderlich" ein. Wird durch E3b widerrufen — die
   Datei bleibt als Archiv-Dokument bestehen, bekommt aber eine sichtbare
   Annotation, dass AC-9 seit 2026-08-01/#1435-E3b nicht mehr gilt, mit
   Verweis auf diese Spec.
2. **Die PO-Präzisierung vom 2026-06-30** (dieselbe Datei, Abschnitt
   „Architektur-Entscheidung (ADR)", ~Zeile 218): „ADR-0011 Ziel-3
   (‚doppelte Mappings entfernen') gilt für den Alert-`sms_code`, **nicht**
   für die Briefing-SMS-Token-Grammatik". Diese Ausnahme wird für die drei
   betroffenen Schnee-Größen aufgehoben — sie fallen ab E3b unter Ziel 3.
   Ausdrücklich **nicht** aufgehoben: die Ausnahme für `TH:` (Grammatikform)
   und für `WC`/`FN`/`FK`/`FD` (strukturell nicht auf ein einzelnes
   `sms_code`-Feld abbildbar) — diese bleiben bewusste, weiterhin gültige
   Sonderfälle (s. Known Limitations).

**ADR-Konsequenz — vorgeschlagene Variante: Nachtrag in ADR-0011, keine
neue ADR-Nummer.** Begründung: Der Inhalt der widerrufenen Ausnahme steht
nicht im ADR-0011-Dokument selbst, sondern nur in der referenzierenden Spec
(`issue_917_alert_renderer.md`, Abschnitt „Architektur-Entscheidung"). Das
ADR-0011-Dokument (`docs/adr/0011-alert-render-single-backend-renderer.md`)
selbst wird durch E3b nicht widersprochen, sondern **vollständiger erfüllt**
— Ziel 3 („doppelte Mappings entfernen") galt für den Briefing-SMS-Pfad
bisher nur teilweise, jetzt vollständig für alle nicht-grammatikalischen
Kürzel. Ein „Abgelöst durch ADR-XXXX" (README-Regel für revidierte
Entscheidungen) passt nur, wenn die ADR-*Entscheidung selbst* zurückgenommen
wird — hier wird umgekehrt eine frühere Ausnahme von ihr zurückgenommen. Die
sauberere, proportionale Variante: ADR-0011 bekommt eine neue Sektion
„## Nachtrag 2026-08-01 (#1435 E3b)" mit zwei bis drei Sätzen: die
2026-06-30-Ausnahme ist revoziert, Ziel 3 gilt jetzt auch für
Schneehöhe/Schneefallgrenze/Neuschnee im Briefing-SMS-Pfad, die verbleibenden
Sonderfälle (`TH:`, `WC`-Quartett) sind bewusst und bleiben. Status des ADR
bleibt **Akzeptiert** (unverändert), kein neuer Index-Eintrag nötig.

## Mitzuziehende Dokumentation

**Pflicht (Wire-Format-Referenz):**
- `docs/reference/sms_format.md` — Zeilen 45, 60, 203 (Nachbar-Kontext des
  Hazard-`SN`), 226 (Kollisions-Erläuterung), 292-294, 331, 365, 419
  (Beispielzeile), 453, 471.

**Spezifikationen mit wörtlichen Kürzeln:**
- `docs/specs/modules/output_token_builder.md` — Zeilen 60, 82, 138, 213,
  221, 253, 297, 384 (Format-Beispiele, Token-Tabellen, Testnamen-Referenz).
- `docs/specs/wintersport_extension.md` — Zeilen 233-235, 242
  (Token-Definitionen, Beispielzeile).
- `docs/specs/modules/feat_873_snow_thresholds.md` — durchgehend `SN`/`SFL`
  in ACs, Implementierungsbeispiel und Beispielwerten; braucht die
  umfangreichste Überarbeitung der drei Spezifikationen, da fast jede AC das
  alte Kürzel nennt.

**Annotation (Archiv, kein inhaltlicher Rewrite):**
- `docs/specs/_archive/modules/issue_917_alert_renderer.md` — AC-9 und
  „Architektur-Entscheidung (ADR)"-Abschnitt bekommen eine sichtbare
  Aufhebungs-Notiz mit Verweis auf diese Spec.
- `docs/adr/0011-alert-render-single-backend-renderer.md` — Nachtrag-Sektion
  (s. oben).

## Betroffene Tests

**Golden-Dateien (müssen die neuen Kürzel zeigen):**
- `tests/golden/sms/arlberg-winter-morning.txt:1`
- `tests/golden/text_report/stubaier-skitour-evening.txt:6`

**Tests, die literale `SN`/`SN24+`/`SFL`-Symbole prüfen und angepasst werden
müssen:**
- `tests/tdd/test_issue_917_alert_renderer.py:641-643` —
  `test_sfl_symbol_unchanged` behauptet heute `SMS_SYMBOL_BY_METRIC["snowfall_limit"]
  == "SFL"` als „unveränderlich". Diese Behauptung wird durch E3b inhaltlich
  falsch. Der Test wird umbenannt/umgeschrieben, um die **neue** Invariante
  zu prüfen (`== "SL"`), mit Verweis auf die Aufhebung der ursprünglichen
  AC-9 statt sie stillschweigend zu löschen.
- `tests/unit/test_token_builder.py` (Zeilen 130-132, 233-240, 263-274) —
  `MetricSpec(symbol="SN", …)` etc. sowie Regex-Nachweise `re.search(r"...SN\d", …)`
  müssen auf `SD`/`NS24+`/`SL` umgestellt werden.
- `tests/unit/test_trip_result_adapter.py` — prüft vermutlich
  `_wintersport_default_config()`; Symbol-Erwartung anpassen.
- `tests/unit/test_renderers_text_report.py` — Wintersport-Zeile im
  Text-Report-Renderer, analog Golden-Datei.
- `tests/tdd/test_873_snow_thresholds.py` — Kern-Testdatei des
  Schwellwert-Features (#873); prüft die inverse `SFL`-Logik direkt, muss
  auf `SL` umgestellt werden, ohne die Testlogik selbst zu verändern (AC-3).
- `tests/tdd/test_issue_944_disabled_metrics_sms.py` — Abwahl-Test (#944)
  für `SN`/`SFL`-Symbole; Symbol-Literale anpassen (AC-4).
- `tests/tdd/test_night_temp_evening_only.py` — falls dort Wintersport-Token
  in Beispielzeilen vorkommen, Symbole mitziehen (Grep-Fund, Umfang prüfen).
- `tests/tdd/test_sms_official_alert_tokens.py` — enthält Beispielzeilen mit
  amtlicher `SN`-Warnung neben Wintersport-Token; AC-7 direkt betroffen,
  prüfen, dass Warnung und Schneehöhe-Token nach der Umstellung nicht mehr
  kollidieren.
- `tests/tdd/test_issue_914_slice1_foundation.py` — referenziert `"SN"` im
  Kontext der PO-Korrektur 2026-07-29 (Neuschnee-`sms_code`); kein
  Verhaltens-Test dieser Etappe, ggf. nur Kommentar-Referenz, prüfen ob
  Anpassung nötig.
- `tests/tdd/test_hazard_symbol_catalog_docs.py` — enthält `"SN"` als
  **Hazard**-Symbol (`HAZARD_SMS_SYMBOLS`), NICHT als Metrik-Symbol — bleibt
  unverändert, wird hier nur zur Abgrenzung genannt (Verwechslungsgefahr).

**Neu:**
- `tests/unit/test_sms_token_symbol_register_ratchet.py` — die Ratsche aus
  AC-9, s. „Wirksamkeitsnachweis der Ratsche".

## Known Limitations

- **Vollständige Registerherrschaft wird mit E3b nicht erreicht.**
  `wind_chill` bleibt mit vier Kürzeln (`WC`/`FN`/`FK`/`FD`) außerhalb —
  strukturell nicht aus einem einzelnen `sms_code`-Feld ableitbar, da eine
  Größe drei Auswertungsformen (Nacht/Tiefst/Höchst) plus eine
  Zusammenfassung (`WC`) im Token-Format braucht. `AV` (Lawinenstufe) bleibt
  außerhalb, weil das Register dafür keinen Eintrag führt (keine
  Katalog-Größe). E3b beseitigt die **Widersprüche** zwischen Trip-SMS und
  Register, nicht die **Zweigleisigkeit** dieser zwei Sonderfälle — das
  bleibt einer möglichen Folge-Etappe von #1435 vorbehalten.
- **Kein automatisierter Cross-Language-Wächter zum Frontend.** Das
  Frontend liest die Kürzel bereits zur Laufzeit über `/api/sms-symbols`
  (kein eigenes Vokabular) — ein separater Frontend-Guard ist deshalb nicht
  nötig, anders als bei rein statisch gepflegten Vokabularen (Muster aus
  E1a/E1b).
- **Ausgeliefertes Format ändert sich zu einem Stichtag, ohne
  Übergangsphase.** Eine SMS hat kein Feld für Erklärungen; wer `SN180`
  gewohnt war, sieht ab dem Deploy `SD180`. Kein Rollback-Pfad außer
  Code-Revert.
- **Der Briefing-Pfad erzeugt heute gar keine Wintersport-Token** —
  gefunden in der RED-Phase am 2026-08-01, Issue **#1450**.
  `sms_trip.py:417` ruft `build_token_line()` ohne `profile=` auf, die
  Vorgabe ist `"standard"`, und der Wintersport-Block entsteht nur unter
  `profile == "wintersport"` (`builder.py:294`). Einziger Aufrufer mit
  Wintersport-Profil ist die Legacy-CLI (`cli.py:228`), laut CLAUDE.md ein
  Debug-Werkzeug. **Folge für E3b:** Die geänderten Kürzel sind heute
  nutzersichtbar allein über die Kürzel-Anzeige im Editor (AC-8), nicht in
  einer zugestellten SMS. Die Umstellung ist trotzdem vollständig
  auszuliefern — sie stellt sicher, dass die Werte am Tag des Anschließens
  (#1450) sofort die richtigen Namen tragen, statt dann ein zweites Mal
  angefasst zu werden. **PO-Entscheid 2026-08-01:** #1450 wird nicht in
  E3b gezogen, weil das Anschließen eine eigene Produktabwägung erfordert
  (160-Zeichen-Budget, Verdrängungsreihenfolge).
- **Ein Bestandstest ist dadurch vakuum-grün** und bleibt es nach E3b:
  `test_issue_944_disabled_metrics_sms.py::test_disabled_snow_metrics_not_in_sms`
  (`:93-106`) geht über `SMSTripFormatter.format_sms()` — also über den
  Briefing-Pfad ohne Wintersport-Profil — und prüft die Abwesenheit eines
  Tokens, der dort ohnehin nie entsteht. E3b stellt ihm einen nicht-vakuösen
  Test zur Seite (`test_disabled_snow_metrics_use_register_symbols`), schreibt
  ihn aber nicht um; die Sanierung gehört zu #1450, wo der Pfad erst wirksam
  wird.
  **Korrektur 2026-08-01 (Adversary-Befund F001):** Eine frühere Fassung
  dieses Absatzes zählte auch zwei „Token fehlt"-Tests in
  `test_873_snow_thresholds.py` dazu. Das ist **falsch** — jene Tests rufen
  `_wintersport()` direkt auf (`:17,39ff.`), umgehen den Briefing-Pfad und
  sind per Mutationstest nachweislich nicht-vakuös. Die Behauptung stammte
  aus dem Implementierungsbericht und war bei der Aufnahme in diese Spec
  nicht nachgeprüft worden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (bestehend, Nachtrag) — kein neues ADR.
- **Rationale:** s. Abschnitt „Aufgehobene Festlegungen". E3b hebt eine
  2026-06-30 gewährte, lokale Ausnahme von ADR-0011 Ziel 3 für drei
  Schnee-Kürzel auf und erfüllt das bestehende Ziel damit vollständiger,
  statt eine ADR-Entscheidung selbst zurückzunehmen. Kein neuer
  Architektur-Grundsatz im Sinne der CLAUDE.md-ADR-Trigger (Kanäle,
  Provider, Auth, Editor-Paradigma, Test-/Deploy-Strategie unberührt) — die
  Registerherrschaft über Renderer-Vokabulare ist bereits etablierte Praxis
  (ADR-0011 selbst, fortgeführt in E1a/E1b/E3a dieser Themenreihe).

## Changelog

- 2026-08-01: Initial spec created. Umfang, Risiken und technischer Ansatz
  aus `docs/context/fix-1435-e3b-sms-kuerzel.md` übernommen, PO-Entscheidung
  zu Neuschnee (`NS24+`) eingearbeitet. Alle Fundstellen (Code + Doku) gegen
  den aktuellen Stand verifiziert, nicht aus dem Kontext-Dokument
  übernommen.
