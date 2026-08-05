---
entity_id: fix_1492_s1_wettercode_fallback
status: draft
type: module
created: 2026-08-05
updated: 2026-08-05
version: "1.0"
tags: [gewitter, provider, openmeteo, merge, fallback, s1]
---

# Wettercode-Fallback: Gewitteraussage und Hagel-Kennzeichen überleben den Modell-Metrik-Ausfall

## Approval

- [x] Approved — PO-Freigabe 2026-08-05 („approved")

## Purpose

Fehlt dem Open-Meteo-Primärmodell `weather_code`, wird zwar automatisch ein
Ersatzmodell abgerufen, das den Wert liefert — beim Zusammenführen wird er
aber heute **still verworfen**, weil `weather_code` in der
Parameter-Feld-Tabelle des Merge-Mechanismus fehlt. Diese Scheibe schließt
genau diese Lücke: der Wettercode wird gemergt, und Gewitteraussage
(`thunder_level`) sowie Hagel-Kennzeichen (`hail_flag`) werden danach aus dem
gemergten Rohcode nachgeleitet — mit derselben Ableitung, die der reguläre
Parse-Pfad ohnehin verwendet.

Erste von zwei Scheiben aus Issue #1492 (`docs/context/feat-1492-gewitter-fallback-kette.md`,
Abschnitt 2 und 7, PO-Entscheidung F1). Scheibe 2 (Vertretung bei Ausfall der
Direktquellen Météo-France/DWD) folgt als eigener Workflow mit eigenem ADR.

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `OpenMeteoProvider._PARAM_TO_FIELD` (Zeile 378, neuer
  Eintrag), `OpenMeteoProvider._merge_fallback` (Zeile 423, ein Aufruf mehr),
  `OpenMeteoProvider._derive_thunder_fields` (neu, private Methode)

**Schicht:** Python-Core (`src/providers/`). Keine Go-API, kein Frontend.
`src/providers/merge.py` (`merge_missing_fields`) wird **nicht** verändert —
PO-Entscheidung F1: kein Eingriff an der gemeinsam genutzten 1:1-Merge-
Signatur, die auch den Schnee-Merge trägt (Weg (c) aus der Analyse wurde
verworfen).

## Estimated Scope

- **LoC:** ~40–60 Produktivcode (ein Dict-Eintrag, eine neue private Methode,
  ein zusätzlicher Aufruf in `_merge_fallback`) + Tests
- **Files:** 1 geändert (`src/providers/openmeteo.py`), 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.merge.merge_missing_fields` | intern | Füllt `wmo_code` fill-only aus dem Ersatzmodell — unverändert, liefert nur den Rohcode |
| `OpenMeteoProvider._parse_thunder_level` (Zeile 621) | intern | Dieselbe Ableitungsfunktion, die der reguläre Parse-Pfad (Zeile 846) nutzt — hier zur Nachableitung wiederverwendet, nicht neu gebaut |
| `OpenMeteoProvider._parse_hail_flag` (Zeile 645) | intern | Analog, aus #1475 S5a |
| `OpenMeteoProvider._find_fallback_model` (Zeile 399) | intern | Wählt das Ersatzmodell anhand von `missing_params` — AC-5 prüft, dass `weather_code` diesen Weg wie jede andere Metrik durchläuft |
| `PROBE_PARAMS` (openmeteo.py:207-214) | Konstante | Sondierungsliste, über die eine Metrik überhaupt als „fehlend" erkannt werden kann — enthält `weather_code` bereits heute |
| `app.models.ForecastDataPoint.{thunder_level,wmo_code,hail_flag}` | Datenmodell | Bereits vorhanden, keine Schema-Änderung |
| `app.models.ThunderLevel` | Enum | `NONE` ≠ Python `None` (Issue #1474 AC-4) — trägt die Überschreib-Invariante dieser Scheibe |

## Implementation Details

```
1. _PARAM_TO_FIELD (openmeteo.py:378-397) bekommt EINEN neuen Eintrag:
       "weather_code": "wmo_code",
   Damit erkennt merge_missing_fields den Rohcode als fuellbares 1:1-Feld
   und fuellt ihn fill-only (Invariante aus merge.py unveraendert: "ueberschreibt
   nie einen vorhandenen Wert").

2. Neue private Methode _derive_thunder_fields(self, ts: NormalizedTimeseries) -> None:
       fuer jeden dp in ts.data:
           wenn dp.wmo_code is None: naechster dp (keine Grundlage zum Ableiten)
           wenn dp.thunder_level is None:
               dp.thunder_level = self._parse_thunder_level(dp.wmo_code)
           wenn dp.hail_flag is None:
               dp.hail_flag = self._parse_hail_flag(dp.wmo_code)
   Liest bewusst dp.wmo_code (den GEMERGTEN Wert je Zeitpunkt), nicht den
   rohen API-Parameter -- funktioniert damit unabhaengig davon, ob wmo_code
   aus dem Primaer- oder dem Ersatzmodell stammt. Die beiden "is None"-Checks
   sind die Ueberschreib-Invariante: ein bereits vom regulaeren Parse-Pfad
   gesetzter Wert (auch ThunderLevel.NONE, das ist NICHT None) bleibt
   unangetastet.

3. _merge_fallback (openmeteo.py:423-428) bekommt EINEN Aufruf mehr, direkt
   nach dem bestehenden merge_missing_fields-Aufruf:
       filled = merge_missing_fields(primary, fallback, missing_params, self._PARAM_TO_FIELD)
       if "weather_code" in filled:
           self._derive_thunder_fields(primary)
       return filled
   Die Nachableitung laeuft NUR, wenn tatsaechlich mindestens ein wmo_code-Wert
   gemergt wurde -- im Normalfall (kein Metrik-Ausfall) ist "weather_code"
   nie in `missing_params`, der Zweig greift nicht, keine Verhaltensaenderung
   fuer den unveraenderten Pfad.

KEINE Aenderung an merge.py, an _parse_response, an thunder_routing.py oder
an der Einstufungslogik (thunder_level_from_signals) -- diese Scheibe fuellt
ausschliesslich einen fehlenden Wert nach, entscheidet nichts neu ein.
```

## Expected Behavior

- **Input:** Eine Vorhersage, bei der das Primärmodell `weather_code` nicht
  liefert (Metrik-Lücke, `weather_code` landet in `missing_params`), während
  das automatisch ermittelte Ersatzmodell für denselben Zeitpunkt einen
  gültigen WMO-Code liefert.
- **Output:** `thunder_level`, `wmo_code` und `hail_flag` sind am
  betroffenen Datenpunkt identisch zu dem, was ein direkter Parse desselben
  Rohcodes ergäbe — statt wie heute bei allen drei `None` zu bleiben.
- **Side effects:** keine zusätzlichen HTTP-Abrufe (der Ersatzmodell-Abruf
  existiert bereits im WEATHER-05b-Mechanismus); keine Änderung an
  `timeseries.meta.fallback_metrics` außer dass `"weather_code"` jetzt darin
  auftauchen kann, wenn dieser Fall eintritt (unverändertes Verhalten von
  `merge_missing_fields`, nicht neu in dieser Scheibe).

## Acceptance Criteria

- **AC-1 (Wirkungsnachweis über den produktiv verdrahteten Merge-Pfad):**
  Given ein Primär-Datenpunkt ohne `weather_code` (`thunder_level`,
  `wmo_code`, `hail_flag` alle `None`) und ein Ersatz-Datenpunkt mit
  demselben Zeitstempel und `weather_code=96` (Gewitter mit Hagel) / When
  `OpenMeteoProvider._merge_fallback(primary, fallback, ["weather_code"])`
  aufgerufen wird — derselbe Aufruf, den `fetch_forecast` bei jeder
  Metrik-Lücke produktiv ausführt (`openmeteo.py:1142`) / Then trägt der
  Datenpunkt danach `thunder_level=ThunderLevel.HIGH`, `wmo_code=96` und
  `hail_flag=True`.
  - Test: Reproduziert den Bug aus Nutzersicht — vor dem Fix bleiben alle
    drei Felder `None` trotz Gewittercode im Ersatzmodell (RED), nach dem
    Fix sind alle drei korrekt gefüllt (GREEN). Kein neuer, unverdrahteter
    Pfad: `_merge_fallback` wird bereits heute von `fetch_forecast`
    aufgerufen (Zeile 1142) — diese Scheibe erweitert nur seinen Rumpf, baut
    keinen neuen Aufrufer.

- **AC-2 (Überschreib-Invariante, allgemein):** Given ein Primär-Datenpunkt
  hat für denselben Zeitstempel bereits `thunder_level=ThunderLevel.HIGH`,
  `wmo_code=95` und `hail_flag=None` gesetzt (regulär vom eigenen Primärmodell
  geparst), das Ersatzmodell liefert für denselben Zeitstempel einen
  abweichenden Code `weather_code=96` / When `_merge_fallback` läuft / Then
  bleiben `thunder_level`, `wmo_code` und `hail_flag` exakt beim
  ursprünglichen Wert (`HIGH`, `95`, `None`) — der abweichende Ersatzwert
  wird nirgends übernommen.
  - Test: Zwei Datenpunkte in derselben Reihe — einer bereits vollständig
    gesetzt (wie oben), einer mit einer echten Lücke (alle drei `None`).
    Nach dem Merge ist nur der Lücken-Datenpunkt verändert, der bereits
    gesetzte bleibt Byte-für-Byte identisch. Gegenprobe: Prüft `_derive_
    thunder_fields` nur global (z. B. per `if filled: ...` ohne den
    `is None`-Check pro Feld), muss dieser Test rot werden.

- **AC-3 (Nicht-Gewitter-Code ist eine geprüfte Entwarnung, kein Loch —
  Issue #1474 AC-4):** Given ein Primär-Datenpunkt trägt die geprüfte
  Entwarnung `thunder_level=ThunderLevel.NONE` (NICHT Python `None`),
  **während sein Rohcode `wmo_code` fehlt** — der Merge füllt den Rohcode
  also tatsächlich aus dem Ersatzmodell, und zwar mit dem Gewittercode `96`
  / When `_merge_fallback` läuft / Then bleibt `thunder_level` exakt
  `ThunderLevel.NONE` — wird weder auf Python `None` zurückgesetzt noch aus
  dem frisch gemergten Ersatz-Rohcode zu `HIGH` hochgestuft.
  - 🔴 **Die Konstellation „Entwarnung gesetzt, Rohcode fehlt" ist für dieses
    AC konstitutiv.** Trüge der Datenpunkt seinen eigenen Rohcode (z. B. `1`),
    liefe die Nachableitung auf denselben Wert `NONE` hinaus und der Test
    könnte eine fehlerhafte Implementierung **nicht** von einer richtigen
    unterscheiden — die Gegenprobe unten wäre wirkungslos. Gemessen
    2026-08-05: mit gesetztem eigenem Rohcode bleibt die Mutation grün, mit
    fehlendem Rohcode wird sie rot (`NONE` → `HIGH`).
  - Test: Prüft konkret die Unterscheidung „Feld ist leer" vs. „Feld trägt
    die geprüfte Entwarnung". Gegenprobe: Behandelt die Implementierung die
    geprüfte Entwarnung als Lücke — etwa
    `if dp.thunder_level in (None, ThunderLevel.NONE):` statt
    `if dp.thunder_level is None:` — muss dieser Test rot werden: der
    bereits geprüfte `NONE`-Wert würde dann fälschlich durch den
    Gewittercode `96` des Ersatzmodells zu `HIGH` überschrieben.
    - *Nicht* als Gegenprobe geeignet und deshalb ausdrücklich nicht
      gefordert: ein falsy-Check (`if not dp.thunder_level`). `ThunderLevel`
      ist `(str, Enum)` mit `NONE = "NONE"` und damit **truthy** — der
      falsy-Check verhält sich für diesen Fall identisch zum `is None`-Check,
      die Mutation bliebe grün. (Gemessen 2026-08-05, Review-Fund team-lead.)

- **AC-4 (Fail-soft, beide Modelle ohne Wert):** Given weder Primär- noch
  Ersatzmodell liefern für einen Zeitpunkt einen `weather_code` / When
  `_merge_fallback` läuft / Then bleiben `thunder_level`, `wmo_code` und
  `hail_flag` an diesem Zeitpunkt `None` — kein Absturz, keine Ausnahme.
  - Test: Ersatz-Datenpunkt ohne `weather_code`-Wert für den betroffenen
    Zeitstempel; nach dem Merge bleiben alle drei Felder `None`, der Aufruf
    wirft nichts.

- **AC-5 (Erkennungs-Vorbedingung — schließt die Kette am schwächsten
  Glied):** Given die Erkennungs- und Auswahlkette, über die eine Metrik
  überhaupt als „fehlend" erkannt und ein Ersatzmodell dafür gefunden wird /
  When geprüft wird, ob `weather_code` diese Kette wie jede andere Metrik
  durchläuft / Then ist `weather_code` (a) in `PROBE_PARAMS`
  (`openmeteo.py:207-214`) enthalten — Voraussetzung, um überhaupt als
  fehlend erkannt zu werden — und (b) wird von `_find_fallback_model`
  (`openmeteo.py:399`) genauso behandelt wie jede andere fehlende Metrik,
  nicht speziell ausgefiltert.
  - Test: Zwei Assertions gegen echten Produktivcode, kein Netz.
    (1) `assert "weather_code" in PROBE_PARAMS`.
    (2) `OpenMeteoProvider()._find_fallback_model(primary_id, lat, lon,
    ["weather_code"])` gegen eine Fake-Availability-Cache (Muster
    `TestFindFallbackModel` aus `tests/unit/test_model_metric_fallback.py`),
    in der ein Ersatzmodell `"weather_code"` als `available` führt — der
    Aufruf muss dieses Modell zurückgeben.
    Gegenprobe: Wird `weather_code` aus `PROBE_PARAMS` entfernt, wird (1)
    rot; enthielte `_find_fallback_model` eine Sonderbehandlung, die
    `weather_code` aus der Auswahl ausschließt, würde (2) rot.
  - Begründung für dieses AC: AC-1 bis AC-4 prüfen ausschließlich das
    Verhalten *innerhalb* von `_merge_fallback`, mit `missing_params`
    bereits als Eingabe. Bricht die Vorbedingung — `weather_code` landet gar
    nicht erst in `missing_params`, weil es aus `PROBE_PARAMS` verschwindet
    oder `_find_fallback_model` es ausschließt — ist die gesamte Scheibe
    **wirkungslos, während AC-1 bis AC-4 weiterhin grün blieben** (sie
    bekommen `missing_params` ja synthetisch vorgegeben). Dass die letzte
    Meile — der reine String-Join `",".join(missing)` beim Aufbau der
    Ersatz-Request-Parameter (`openmeteo.py:1133`) — ungefiltert bleibt,
    folgt aus Code-Inspektion (keine Filterlogik zwischen `missing` und
    diesem Join) und wird nicht separat getestet, s. Known Limitations.

## Known Limitations

1. **Vertretung bei Ausfall der Direktquellen (Météo-France/DWD) ist NICHT
   Teil dieser Scheibe.** Das ist Scheibe 2 (A2 aus der Analyse), eigener
   Workflow, eigenes ADR (`thunder_routing.py`, `thunder_enrichment.py`
   bleiben unangetastet).
2. **Fehlwert-Marker im rohen `weather_code`-API-Parameter** (z. B. ein
   API-seitiger Sentinel) werden von dieser Scheibe nicht neu behandelt —
   das bestehende Parsing (`get_int("weather_code", i)`) liefert bereits
   `None` bei fehlendem Rohwert, unverändert.
3. **Zeitpunkt-Zuordnung** zwischen Primär- und Ersatzreihe läuft über den
   bestehenden `ts`-Join in `merge_missing_fields` — diese Scheibe fügt
   keine eigene Zuordnungslogik hinzu.
4. **Keine Änderung an der Einstufung.** `thunder_level_from_signals` und
   jede Fusion mit Direktquellen-Signalen (#1457) bleiben unverändert; diese
   Scheibe füllt ausschließlich den WMO-Code-Pfad nach.
5. **AC-5 prüft die Erkennungs- und Auswahlkette, nicht den vollen
   HTTP-Roundtrip.** Dass der Ersatzabruf `weather_code` tatsächlich als
   Query-Parameter sendet, ist eine reine String-Join-Operation
   (`",".join(missing)`, `openmeteo.py:1133`) ohne Filterschritt dazwischen
   — dafür ist kein zusätzlicher Test nötig, das folgt aus AC-5(b) plus
   Code-Inspektion.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Lückenschließung an einem bereits produktiven
  Mechanismus (WEATHER-05b Model-Metric-Fallback, Issue #1302/Epic #1301) —
  ein fehlender Eintrag in einer bestehenden Parameter-Feld-Tabelle wird
  ergänzt, plus eine kleine Nachableitung, die dieselben Parse-Funktionen
  wiederverwendet, die der reguläre Pfad ohnehin nutzt. Es entsteht keine
  neue Entscheidungsfläche: die 1:1-Merge-Signatur (`merge.py`) bleibt exakt
  wie sie ist (PO-Entscheidung F1, Weg (b) statt des generischen 1:N-Umbaus
  Weg (c)), keine neue Quelle, kein neues Routing, kein neues Meldefeld. Das
  verwandte, bereits akzeptierte Muster für Transparenz bei Modellausfall
  (ADR-0018 „Modell-Fallback ohne Kaschieren") ist hier nicht zusätzlich
  berührt, weil diese Scheibe keine neue Fallback-*Quelle* einführt, sondern
  nur einen Wert innerhalb der bereits bestehenden, bereits markierten
  Fallback-Kette (`fallback_model`/`fallback_metrics`) vollständiger macht.
  Scheibe 2 bringt die neue Entscheidungsfläche (Vertretung zwischen
  Direktquellen) und damit das eigene ADR.

## Changelog

- 2026-08-05 (Mutations-Gegenprobe nach GREEN): **AC-3 Szenario korrigiert.**
  Die Mutations-Gegenprobe deckte auf, dass die AC-3-Fassung ihre eigene
  Gegenprobe nicht auslösen konnte: Im ursprünglich beschriebenen Szenario
  trug der Datenpunkt seinen **eigenen** Rohcode (`wmo_code=1`), den der
  fill-only-Merge gar nicht ersetzt — eine Nachableitung daraus ergibt wieder
  `NONE`, die Mutation blieb also grün. Gemessen: mit fehlendem Rohcode
  (`wmo_code=None`, vom Ersatzmodell mit `96` gefüllt) wird dieselbe Mutation
  rot (`NONE` → `HIGH`). AC-3 verlangt jetzt genau diese Konstellation.
  Gegenprobe-Belege: Mutation „Schutz ganz entfernen" → rot über AC-2
  (bestätigt); Mutation „Entwarnung als Lücke behandeln" → im alten Szenario
  grün, im neuen rot.
- 2026-08-05 (Review): **AC-3 Gegenprobe korrigiert** — die ursprünglich
  geforderte Mutation (falsy-Check statt `is None`) ist strukturell nicht
  auslösbar: `ThunderLevel` ist `(str, Enum)` mit `NONE = "NONE"` und damit
  truthy, beide Checks verhalten sich für diesen Fall identisch, die Mutation
  wäre grün geblieben. Ersetzt durch die fachlich naheliegende Mutation
  `in (None, ThunderLevel.NONE)`, gegen die der Test tatsächlich wirkt.
  **AC-5 nachgetragen und präzisiert** — die Erkennungs-Vorbedingung
  (`weather_code` in `PROBE_PARAMS` und bei `_find_fallback_model` nicht
  ausgefiltert) war ungetestet; bricht sie, ist die Scheibe wirkungslos, ohne
  dass AC-1 bis AC-4 rot würden. Test konkretisiert auf zwei Assertions gegen
  echten Produktivcode (`PROBE_PARAMS`-Membership,
  `_find_fallback_model`-Aufruf), Zeilenverweis auf den String-Join
  (`openmeteo.py:1133`) statt der ungenauen ursprünglichen `:1112`-Angabe
  (das war nur der Kommentar-Marker, nicht der Aufruf selbst) korrigiert.
- 2026-08-05: Initial spec created (Issue #1492 Scheibe 1, Analyse
  `docs/context/feat-1492-gewitter-fallback-kette.md` Abschnitt 2 und 7,
  PO-Entscheidung F1 vom 2026-08-05: Weg (b) — `weather_code` → `wmo_code`
  mergen, `thunder_level`/`hail_flag` danach aus dem gemergten Rohcode
  nachableiten, Merge-Signatur unangetastet).
