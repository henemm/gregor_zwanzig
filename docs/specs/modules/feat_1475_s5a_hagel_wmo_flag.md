---
entity_id: feat_1475_s5a_hagel_wmo_flag
type: feature
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [gewitter, hagel, epic-1419, issue-1475]
---

# Hagel als eigenes Kennzeichen — Scheibe S5a (WMO-Code)

## Approval

- [ ] Approved

## Purpose

Hagel wird ein eigenes, rein deskriptives Kennzeichen (`ja`/`unbekannt`, technisch
`Optional[bool]`) — getrennt von der Gewitterstufe (`thunder_level`). Diese
Scheibe (S5a von 3, #1475 zu Epic #1419) nutzt dafür ausschließlich den
bereits überall vorhandenen Open-Meteo `wmo_code`: 96/99 kennzeichnen Gewitter
mit Hagel, wurden bisher aber beim Einlesen zu `ThunderLevel.HIGH` kollabiert
und der Hagel-Anteil verworfen. S5a hebt diese Information, ohne die
Gewitterstufe zu verändern, und zeigt sie als Fakt neben der Stufe in allen
drei Kanälen (E-Mail, Telegram/`GEWITTER`-Kommando, SMS).

## Source

- **File:** `src/app/models.py`, `src/providers/openmeteo.py`,
  `src/output/metric_format.py`, `src/services/weather_metrics.py`
- **Identifier:** `ForecastDataPoint.hail_flag` (neu), `OpenMeteoProvider._parse_hail_flag()`
  (neu), `metric_format.hail_priority()` (neu), `WeatherMetricsService._compute_hail_flag()`
  (neu)

**Schicht:** Python-Core (`src/app/`, `src/providers/`, `src/services/`,
`src/output/`, `api/`). Kein Go-API-DTO-Fund außer der reinen JSON-Passthrough
in `api/routers/compare.py` (Hagel-Wert wird durchgereicht, nicht berechnet).
**Kein Frontend** — Hagel ist keine wählbare Trip-Editor-Metrik (Konvention
analog `confidence_pct`, Issue #710, s. AC-9).

> **Schicht-Hinweis geprüft:** Alle betroffenen Symbole liegen im Python-Core.
> Go-API (`internal/`, `cmd/`) ist nicht betroffen, SvelteKit-Frontend
> (`frontend/src/...`) ist bewusst nicht betroffen (kein Editor-Zugang).

## Estimated Scope

- **LoC:** ~150–250 Produktivcode (`models.py`, `openmeteo.py`,
  `metric_format.py`, `weather_metrics.py`, 3 E-Mail-Renderer,
  `trip_command_processor.py`, SMS-Token-Kette, `compare.py`) + vergleichbarer
  Testumfang
- **Files:** ~9–10 Produktivdateien geändert, keine neue Produktivdatei nötig;
  mind. 4–5 Testdateien geändert/neu
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastDataPoint.wmo_code` (`src/app/models.py:137`) | internes Feld, bereits live für jeden Punkt/jede Region | einzige Datenquelle dieser Scheibe |
| `ThunderLevel` / `thunder_level_from_signals()` (`src/output/metric_format.py:326-370`) | interne Funktion, MUSS **unverändert** bleiben | Abgrenzung Hagel-Flag von der Gewitterstufe (#1419-Konzeptgrenze) |
| Issue #1457 S2 (alle Gewitterquellen live) + #1474/#1474c (Stufenbildung, 4. Signal) | Upstream, geschlossen | Voraussetzung erfüllt, Datenpfad steht bereits produktiv |
| `docs/adr/0007-daten-statt-empfehlungen.md` (aktiv) | Architektur-Entscheidung | verbietet Handlungsempfehlungs-Text, definiert den erlaubten Darstellungsrahmen (nur Fakt, kein Rat) |
| `src/output/tokens/hazard_symbols.py`, `tokens/builder.py` | Referenzmuster (kein direkter Code-Reuse) | Vorbild für ein SMS-Kürzel/Suffix — andere Kategorie (Vorhersage-Token, nicht amtliche Warnung) |
| Trip/Compare-Teilungsinvariante (`CLAUDE.md`) | Architektur-Konvention | Der neue Anzeige-Helfer MUSS von Trip- UND Compare-Renderer sowie `_fmt_gewitter()` gemeinsam genutzt werden — keine dritte Textkopie |
| #1481 DRY-Pflicht | Prozess-Konvention | Ein gemeinsamer Formatierungshelfer statt Textkopie in `_fmt_gewitter` + 3 Mail-Renderern |

## Implementation Details

```
1. Datenmodell (models.py):
   ForecastDataPoint bekommt EIN neues Feld:
     hail_flag: Optional[bool] = None
   Semantik (bewusst NICHT dieselbe wie ein normaler Bool):
     True  = "ja"        -- WMO-Code bestaetigt Hagel (96 oder 99)
     None  = "unbekannt"  -- WMO-Code kann Hagel nur BEJAHEN, nie
                             VERNEINEN; jeder andere Code (inkl. 95) UND
                             ein fehlender Code landen hier
     False = "nein"       -- in S5a strukturell UNERREICHBAR. Reserviert
                             fuer S5b/S5c, sobald eine Quelle existiert,
                             die Hagel aktiv ausschliessen kann
                             (DWD-Schwelle bzw. Meteo-France AROME).
   SegmentWeatherSummary (Tages-/Etappen-Aggregat) bekommt dasselbe Feld
   `hail_flag: Optional[bool] = None` plus einen neuen Eintrag in
   `aggregation_config`: {"hail_flag": "hail_priority"}.

2. openmeteo.py: NEUE, von `_parse_thunder_level` getrennte Funktion
   (gleicher Rohwert `weather_code`, andere Uebersetzung, KEIN Andocken an
   die bestehende Funktion -- unterschiedliche Rueckgabetypen und
   unterschiedliche Aussagekraft):

     def _parse_hail_flag(self, weather_code: Optional[int]) -> Optional[bool]:
         if weather_code in (96, 99):
             return True
         return None   # 95, jeder andere Code, UND fehlender Code

   Aufruf an derselben Stelle wie `_parse_thunder_level`/`wmo_code`
   (openmeteo.py:826-827), zusaetzliche Zeile:
     hail_flag=self._parse_hail_flag(get_int("weather_code", i)),

3. metric_format.py: EINE neue, kleine Funktion (NICHT an
   `_thunder_level_from_ladder` andocken -- das ist fuer 4-stufige Leitern,
   Hagel ist ein 3-wertiges Flag):

     def hail_priority(values: Iterable[Optional[bool]]) -> Optional[bool]:
         """ja > unbekannt > nein. Erwartet die ROHEN (nicht vorgefilterten)
         Werte -- ein blosses `any()`/`max()` waere bei einer Mischung aus
         True/None/False falsch (s. Known Limitations Punkt 3)."""
         vals = list(values)
         if any(v is True for v in vals):
             return True
         if any(v is None for v in vals):
             return None
         if vals:
             return False
         return None

   `thunder_level_from_signals()` bleibt zeichengleich unveraendert (AC-3).

4. weather_metrics.py:
   - NEUE `_compute_hail_flag(timeseries)` (parallel zu
     `_compute_thunder_level`), ruft `hail_priority()` ueber die rohen
     Punkt-Werte auf (NICHT ueber eine vorgefilterte Liste -- Level-1
     bekommt die volle Rohliste, dort ist die Prioritaet korrekt).
   - `compute_basis_metrics()`: neuer Aufruf + Feld auf
     `SegmentWeatherSummary` + `aggregation_config`-Eintrag (s.o.).
   - `summarize_points()` erbt das Feld automatisch (duenner Wrapper um
     `compute_basis_metrics`).
   - `aggregate_stage()` (Level-2, stage-uebergreifend): neuer Zweig fuer
     `agg_rule == "hail_priority"`. WICHTIG (s. Known Limitations Punkt 3):
     der bestehende generische Vorfilter (`if getattr(s, field, None) is
     not None`) entfernt `None`-Werte VOR der Regel-Anwendung -- fuer S5a
     unschaedlich (S5a erzeugt nie `False`), muss aber ueberarbeitet werden,
     BEVOR S5b/S5c ein echtes `False` einfuehren.

5. Renderer (EIN gemeinsamer Helfer, Trip/Compare-Teilungspflicht):
     def format_hail_note(hail_flag: Optional[bool]) -> Optional[str]:
         if hail_flag is True:
             return "Hagel: ja"
         return None   # unbekannt/nein: keine Zusatzanzeige (kein Rauschen)
   Genutzt von `email/plain.py`, `email/html.py`, `email/compare_html.py`
   UND `trip_command_processor._fmt_gewitter()` -- EIN Textbaustein, nicht
   vier. Anzeige rein deskriptiv neben der Gewitterstufe, z.B.
   "Gewitter: hoch · Hagel: ja". KEIN Ratschlagstext (ADR-0007, AC-8).

6. SMS (sms_trip.py, tokens/builder.py, hazard_symbols.py):
   Arbeitshypothese (vor Implementierung gegen `docs/reference/sms_format.md`
   abzugleichen, analog Namensfallen-Warnung #1457 S2b): fixer Suffix am
   bestehenden `FORECAST_TH`-Token, NUR wenn `hail_flag is True` fuer die
   Etappe -- kein eigenes Kuerzel, keine eigene Prioritaetsstufe, kein
   sichtbares Zeichen bei `None`/`False`.

7. api/routers/compare.py: `hail_flag` wird neben `wmo_code`
   (Zeile ~106) in denselben `hourly`-Eintrag serialisiert -- sonst
   Feld-Verlust beim JSON-Export (Praezedenz #1265/#1349).
```

## Expected Behavior

- **Input:** ein Wetterpunkt mit `wmo_code` aus Open-Meteo (jede Region,
  bereits heute befüllt)
- **Output:** derselbe Datenpunkt trägt zusätzlich `hail_flag` (`True` bei
  WMO 96/99, sonst `None`); Tages-/Etappenaggregat trägt denselben Wert nach
  der Priorität ja>unbekannt>nein; alle drei Kanäle zeigen bei `True` einen
  zusätzlichen, rein deskriptiven Hagel-Hinweis neben der Gewitterstufe, bei
  `None` keinen zusätzlichen Text
- **Side effects:** keine zusätzlichen HTTP-Abrufe (derselbe Rohwert wird
  bereits für `thunder_level`/`wmo_code` geholt); die Gewitterstufe selbst
  bleibt in jedem Fall unverändert

## Acceptance Criteria

- **AC-1 (Wirkungsnachweis Ende-zu-Ende, WMO 96/99 → ja):** Given ein
  Wetterpunkt mit WMO-Code 96 oder 99 im **regulären** Open-Meteo-Abrufpfad
  (`OpenMeteoProvider.fetch_forecast`, keine isolierte Methodenprüfung) /
  When eine Vorhersage gebaut und ein Trip-Briefing gerendert wird / Then
  trägt der Datenpunkt `hail_flag=True` UND der gerenderte Text zeigt einen
  Hagel-Hinweis ("Hagel: ja") neben der Gewitterstufe.
  - Test: Eine aufgezeichnete Open-Meteo-Antwort mit `weather_code=96` an
    einer Stunde wird durch den kompletten Weg (`fetch_forecast` →
    Renderer-Text) gespielt, das Textfragment im Ergebnis nachgewiesen.
    Gegenprobe: Wird derselbe Test nur isoliert gegen `_parse_hail_flag()`
    geführt (nicht über den regulären Fetch-Pfad), MUSS er die Wirkung nicht
    beweisen können — dieser AC verlangt ausdrücklich den durchgespielten
    Weg (Lehre aus #1467 AG6: Fähigkeit ≠ Wirkung).

- **AC-2 (WMO 95 und alle anderen Codes → unbekannt, NICHT nein — die
  explizit gelöste Designfrage dieser Spec):** Given ein Wetterpunkt mit
  WMO-Code 95 (Gewitter ohne Hagel-Zusatzcode) ODER ein beliebiger
  Nicht-Gewitter-Code (z.B. 3 = bewölkt) ODER gar kein `wmo_code` (`None`) /
  When das Hagel-Kennzeichen ermittelt wird / Then ist `hail_flag` in **allen
  drei** Fällen `None` ("unbekannt") — niemals `False`.
  - Test: Drei Fixtures (Code 95, ein Nicht-Gewitter-Code, fehlender Code)
    erzeugen jeweils `hail_flag is None`. Ein Test, der für Code 95 `False`
    erwartet, MUSS fehlschlagen: der WMO-Code kann Hagel nur bejahen (96/99
    sind explizite Hagel-Codes), aber nicht verlässlich verneinen.

- **AC-3 (Abgrenzung zur Gewitterstufe — PFLICHT-Mutationsschutz, PO-Vorgabe
  2026-08-03):** Given ein Datenpunkt mit gesetztem `hail_flag` (`True` oder
  `None`) / When `thunder_level_from_signals()` aufgerufen wird / Then bleibt
  die berechnete `ThunderLevel`-Stufe exakt identisch zu einem Lauf ohne
  `hail_flag` — Hagel fließt an keiner Stelle in die Stufenberechnung ein.
  - Test: Regressionstest rendert dieselbe Signalkombination (Wettercode,
    Blitzdichte, CAPE, Blitzpotenzial) einmal mit und einmal ohne
    `hail_flag`, vergleicht `thunder_level_from_signals()` — Ergebnis muss
    identisch sein. Gegenprobe (expliziter Adversary-Mutationskandidat):
    Wird `hail_flag` versehentlich als fünftes Signal in die Fusionsliste
    eingefügt, MUSS dieser Test rot werden.

- **AC-4 (Tagesaggregation, Priorität ja>unbekannt>nein):** Given eine
  Etappe mit mehreren Stunden, davon mindestens einer mit `hail_flag=True`
  und den übrigen `None` / When der Tageswert aggregiert wird
  (`compute_basis_metrics`/`summarize_points`) / Then ist der
  Tages-`hail_flag` `True` — eine einzelne bestätigte Hagelstunde darf nicht
  von umgebenden "unbekannt"-Stunden verdeckt werden.
  - Test: Timeseries mit einer True-Stunde und drei None-Stunden aggregiert
    zu `hail_flag=True` auf `SegmentWeatherSummary`. Gegenprobe: ein blindes
    `max()`/`any()` auf einer falsch kodierten Werteliste würde bei anderer
    Reihenfolge/Kodierung falsch entscheiden — Test nutzt echte
    `Optional[bool]`-Werte, keine numerische Ersatzkodierung.

- **AC-5 (E-Mail, rein deskriptiv, kein Rauschen bei unbekannt):** Given
  eine Etappe mit Tages-`hail_flag=True` und eine zweite Etappe derselben
  Mail mit `hail_flag=None` / When die Trip-Mail gerendert wird (Klartext
  UND HTML) / Then zeigt NUR die erste Etappe einen zusätzlichen
  Hagel-Hinweis neben der Gewitterstufe (z.B. "Gewitter: hoch · Hagel: ja"),
  die zweite bleibt zeichengleich zum Stand ohne diese Scheibe.
  - Test: Zwei gerenderte Mails (Fixture-Etappen) verglichen — der
    Hagel-Zusatz erscheint nachweisbar nur bei der True-Etappe. Läuft gegen
    den echten Mail-Validator-Pfad (`briefing_mail_validator.py`, echte
    zugestellte Staging-Mail), nicht nur ein isolierter Renderer-Aufruf.

- **AC-6 (SMS, kein zusätzliches Rauschen):** Given eine Etappe mit
  `hail_flag=True` und eine zweite mit `hail_flag=None` (bzw. später
  `False`) / When das SMS-Trip-Briefing gerendert wird / Then trägt NUR die
  True-Etappe eine zusätzliche Hagel-Kennzeichnung im Token-Block; die
  andere bleibt zeichengleich zum bisherigen Format; beide bleiben ≤160
  Zeichen.
  - Test: Golden-String-Vergleich zweier SMS-Renderings (mit/ohne
    `hail_flag=True`). Telegram-Kurzform wird als A/B-Pflichtprüfung gegen
    dieselben zwei Fixtures mitgeprüft (Telegram-Kurzform = SMS-Prüfweg).

- **AC-7 (GEWITTER-Kommando, Telegram/Mail-Antwort, DRY):** Given ein
  Nutzer sendet das Kommando `GEWITTER` an einem Tag mit aggregiertem
  `hail_flag=True` / When `_fmt_gewitter()` die Antwort baut / Then enthält
  die Antwort denselben Hagel-Hinweis-Text wie die E-Mail-Renderer — über
  dieselbe geteilte Formatierungsfunktion, nicht über einen zweiten
  Textbaustein.
  - Test: `_fmt_gewitter()` wird gegen eine Fixture-Timeline mit
    `hail_flag=True` aufgerufen, das Textfragment wird nachgewiesen.
    Zusätzlich ein struktureller Test, der belegt, dass Mail-Renderer und
    Kommando-Handler dieselbe Funktion importieren (kein Duplikat, #1481
    DRY-Pflicht).

- **AC-8 (keine Handlungsempfehlung, ADR-0007):** Given jede der oben
  genannten Ausgaben (Mail, SMS, Telegram-Kommando) mit `hail_flag=True` /
  When der tatsächlich sichtbare Text geprüft wird / Then enthält er an
  keiner Stelle einen Ratschlags-/Imperativtext ("Schutz suchen",
  "Vorsicht", "meiden", o.ä.) — nur die faktische Kennzeichnung.
  - Test: Rendert alle drei Kanäle für eine True-Fixture und prüft den
    tatsächlich gerenderten, an den Nutzer gehenden Text auf Abwesenheit
    einer festgelegten Verbotswortliste. Das ist ein Verhaltensnachweis am
    Renderer-Output, keine Ersatzprüfung an einer Quelldatei.

- **AC-9 (kein Frontend/Editor, analog #710):** Given der Trip-Editor bzw.
  die Metrik-Auswahl (`GET /api/metrics`) / When die verfügbaren wählbaren
  Metriken abgerufen werden / Then erscheint kein Hagel-Eintrag in der
  Liste — das Kennzeichen ist nicht wählbar, es erscheint ausschließlich
  automatisch dort, wo Gewitter ohnehin gezeigt wird.
  - Test: Die Response von `GET /api/metrics` enthält keinen Eintrag mit
    hagelbezogener `metric_id`. Ein Test, der eine wählbare
    Hagel-Metrik erwartet, MUSS fehlschlagen.

- **AC-10 (Compare-API-Durchreichung, kein stiller Feldverlust):** Given
  ein Ortsvergleich mit stündlichen Daten, von denen ein Punkt
  `hail_flag=True` trägt / When `api/routers/compare.py` die Stundendaten
  nach JSON serialisiert / Then erscheint `hail_flag` im selben
  `hourly`-Eintrag wie `wmo_code` — kein stiller Feldverlust beim
  Serialisieren (Präzedenzfall #1265/#1349: additive Felder wurden dort
  beim Serialisieren vergessen).
  - Test: JSON-Response eines Compare-Aufrufs mit einer Hagel-Fixture
    enthält `"hail_flag": true` im entsprechenden Stundendatensatz.

## Known Limitations

1. **WMO-Code liefert nur ein "ja", nie ein verlässliches "nein".** Code 95
   und alle anderen Codes (inkl. fehlendem Code) liefern strukturell nur
   "unbekannt" — ein definitives "nein" für einen Ort bräuchte S5b
   (DWD-Schwelle für `hail_potential_grau_gsp`) oder S5c
   (Météo-France-Anbindung), die aktiv eine Nicht-Hagel-Aussage treffen
   können. Das ist eine bewusst akzeptierte Präzisionsgrenze dieser
   Scheibe, keine Kollateralschwäche.
2. **Rest-Europa (EU_REST, kein DWD-/AROME-Pendant) bleibt strukturell auf
   dieses grobe WMO-Signal beschränkt**, bis S5c dort eine eigene Quelle
   anbindet — dort kann "ja" durch S5a/S5b nie widerlegt werden.
3. **`aggregate_stage()`'s generischer Level-2-Aggregationsmechanismus
   filtert `None`-Werte vor der Regel-Anwendung heraus** (bestehendes
   Verhalten für alle Metriken, s. `weather_metrics.py` Zeile ~1122-1129).
   Für S5a ist das unschädlich, weil diese Scheibe strukturell nie `False`
   erzeugt (nur `True`/`None`) — die Priorität ja>unbekannt kollabiert dann
   korrekt auf "gibt es ein True? sonst None". **Sobald S5b/S5c ein echtes
   `False` einführen, MUSS dieser Filter-Mechanismus überarbeitet werden** —
   sonst kann ein `None` ("unbekannt") fälschlich von einem bereits
   gefilterten `False` ("nein") überstimmt werden, statt es laut Prioritäts-
   regel zu übertrumpfen. Explizit als Vorbedingung für S5b/S5c dokumentiert,
   nicht diese Scheibe blockierend.
4. **SMS-Kennzeichen-Zeichen ist eine Arbeitshypothese** (Suffix am
   bestehenden `TH:`-Forecast-Token vs. eigenes Kürzel) — muss vor
   Implementierung gegen `docs/reference/sms_format.md` abgeglichen und dort
   nachgetragen werden (analog Namensfallen-Warnung aus #1457 S2b).
5. **Scope-Punkt 4 des ursprünglichen Issues (Handlungsempfehlung "Schutz
   suchen") ist PO-Entscheidung 2026-08-04 komplett aus dem Umfang entfernt**
   (ADR-0007-Konflikt) — wird in keiner Folgescheibe von #1475 ohne
   vorherige Ablösung von ADR-0007 nachgerüstet.
6. **Kein Frontend-/Editor-Zugang** (analog `confidence_pct`, #710) — auch
   S5b/S5c ändern daran nichts, solange keine neue PO-Entscheidung vorliegt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Bezug auf **ADR-0007** (Daten statt
  Empfehlungen, aktiv, nicht abgelöst).
- **Rationale:** ADR-0007 verbietet handlungsleitende Empfehlungen; diese
  Spec hält sich strikt daran, indem Hagel ausschließlich als deskriptives
  Fakten-Kennzeichen (wie eine amtliche Warnstufe) dargestellt wird, ohne
  Ratschlagstext (AC-8, Known Limitation 5). Damit ist Scope-Punkt 4 des
  ursprünglichen Issues (Handlungsempfehlung) bewusst NICHT Teil dieser
  Spec — kein neues ADR nötig, weil keine neue Architektur-Entscheidung
  getroffen wird, sondern eine bestehende angewendet/eingehalten wird.

## Changelog

- 2026-08-04: Initial spec created (Issue #1475 S5a, Epic #1419;
  PO-Entscheidung 2026-08-04: Scope-Punkt 4 "Handlungsempfehlung" entfällt
  wegen ADR-0007).
