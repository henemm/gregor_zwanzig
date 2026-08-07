---
entity_id: feat_1492_s2b_fallback_sichtbarkeit
type: module
created: 2026-08-06
updated: 2026-08-06
status: draft
version: "1.0"
tags: [gewitter, fallback, sichtbarkeit, email, telegram, s2b]
workflow: feat-1492-s2b-fallback-sichtbarkeit
---

# Fallback-Sichtbarkeit: Gewitter- und Grundvorhersage-Vertretung im Klartext-Briefing

## Approval

- [x] Approved — PO-Freigabe 2026-08-07 (Orchestrierer-Sitzung, Beleg als
  Kommentar an Issue #1492). Freigegeben: die zehn Acceptance Criteria auf
  Deutsch, der Ausgaben-Umfang (Trip-Mail Vollversion + Kompakt + Telegram-
  Langform; **ohne** Ortsvergleich, Alarm-Mails, SMS, Telegram-Kurzform), der
  Wortlaut-Stil „Quelle in Klartext + Folge in Klammern", sowie
  `loc_limit_override = 400` mit der ausdrücklichen Auflage, den Testumfang
  dafür **nicht** zu kürzen.

## Purpose

Scheibe 2a (`feat_1492_s2a_thunder_vertretung.md`, ADR-0047) hält seit dem
2026-08-06 intern fest, *dass* eine Gewitter-Direktquelle vertreten wurde —
in `ForecastMeta.fallback_model` / `fallback_metrics` / `fallback_reason`.
Der Nutzer sieht davon nichts, weil kein Renderer diese Felder für die
Gewitter-Domäne liest. Diese Scheibe macht die Vertretung in drei
Briefing-Ausgaben sichtbar (Trip-Mail Vollversion, Trip-Mail Kompakt,
Telegram-Langform), stellt dabei den bestehenden technischen
Grundvorhersage-Hinweis (`Fallback {metrics}: {model}`) auf Klartext um
und behebt gleichzeitig einen Darstellungsfehler: die heutige Formulierung
verknüpft `fallback_metrics` und `fallback_model` ungeprüft, obwohl beide
im Kollisionsfall aus zwei unabhängigen Mechanismen stammen können. Issue
#1492 Scheibe 2b.

## Source

- **File:** `src/output/renderers/fallback_notice.py` (neu, geteilte
  Formulierungslogik), `src/output/renderers/email/plain.py`,
  `src/output/renderers/email/html.py`, `src/output/renderers/email/compact.py`,
  `src/output/renderers/narrow.py`
- **Identifier:** `fallback_notice.build_fallback_lines` (neu),
  `TripReportFormatter.format_email` (Plain/HTML-Aufrufpfad, unverändert),
  `_tg_day_footer` (Telegram-Aufrufpfad, erweitert)

> **Schicht-Hinweis:** Reine Python-Core-Renderer-Schicht
> (`src/output/renderers/`). Keine Go-API, kein Frontend, kein
> Datenmodell-Eingriff — es werden ausschließlich bereits vorhandene
> `ForecastMeta`-Felder gelesen (`app/models.py:90-95`), keine neuen
> geschrieben.

## Bezug

- ADR-0018 (`docs/adr/0018-provider-fallback-ohne-kaschieren.md`) —
  Ursprung der Nicht-Kaschieren-Invariante für den Grundvorhersage-Fallback.
- ADR-0047 (`docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md`) —
  Folgepflicht „Sichtbarkeit ist 2b", inkl. der `fallback_metrics`-Auflage.
- ADR-0034 (`docs/adr/0034-herkunftsfusszeile-reale-datenquelle.md`) —
  bestehendes Muster „Herkunftsangabe als Fakt, nicht als Empfehlung".
- ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) —
  betrifft die Ausgabequelle (`dp.thunder_level`), nicht die
  Herkunftsanzeige der Rohsignal-Felder; von dieser Scheibe unberührt.
- Issue #1492 (Kopf-Issue, Scheibe 2b).

## Estimated Scope

- **LoC:** Produktivcode ~110–130 (`fallback_notice.py` ~70 inkl.
  Übersetzungstabellen und Kollisionslogik, `plain.py`/`html.py`/`compact.py`
  je ~5–10 Zeilen Verpackung, `narrow.py` ~15–20 Zeilen). Tests ~140–180
  (neue Formulierungslogik-Suite `test_fallback_notice.py` ~90–110, plus
  Ergänzungen/Anpassungen der drei Renderer-Suiten). **Zusammen ~250–310
  LoC.**
- **Files:** 1 neu (`fallback_notice.py`), 4 geändert
  (`plain.py`, `html.py`, `compact.py`, `narrow.py`), 3 Testdateien
  geändert (`test_model_metric_fallback.py`,
  `test_issue_1141_cross_provider_fallback.py`,
  `test_telegram_footer_metric_gating.py` sofern Ergänzung dort statt in
  neuer Datei nötig), 1 Testdatei neu (`test_fallback_notice.py`), 2
  Doku-Stellen (`docs/reference/api_contract.md`,
  `docs/reference/decision_matrix.md` — sofern der alte technische Wortlaut
  dort zitiert wird, zählt nicht gegen LoC).
- **Effort:** medium (drei Ausgabeorte, eine geteilte Formulierungslogik,
  fünf Bestandstests müssen mitgezogen werden, Renderer-Commit-Gate #811
  greift).
- **LoC-Einschätzung ehrlich:** Die Schätzung (~250–310) liegt an oder
  knapp über dem Standard-Limit von 250 LoC/Workflow. Ob ein
  `loc_limit_override` nötig wird, entscheidet der PO nach Prüfung des
  tatsächlichen Diffs — hier keine Vorfestlegung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.ForecastMeta.{fallback_model,fallback_metrics,fallback_reason}` | Datenmodell | Bereits vorhanden (#1115/ADR-0018, erweitert 2a/ADR-0047) — diese Scheibe **liest nur**, schreibt kein neues Feld |
| `providers.thunder_enrichment._SIGNAL_ZU_FELD` / `_EINZELWERT_FELD` | intern | Quelle der Wahrheit für die drei Gewitter-Feldnamen (`thunder_enrichment.py:36-43`): `lightning_density_per_km2_3h`, `lightning_potential_lpi_jkg`, `hail_potential_grau_gsp` |
| `providers.openmeteo.OpenMeteoProvider._PARAM_TO_FIELD` | intern | Quelle der Wahrheit für die Open-Meteo-Parameternamen in `fallback_metrics` bei Grundvorhersage-Fallbacks (`openmeteo.py:378-398`, 18 Einträge) |
| `output.renderers.email.helpers.build_origin_footer` | intern | Bestehende, geteilte Herkunfts-Fußzeile (Zeile 2: reale Datenquelle) — bleibt unverändert, der neue Fallback-Hinweis ist ein zusätzlicher, davon unabhängiger Baustein |
| `output.renderers.trip_report.TripReportFormatter.format_email` | intern | Bestehender Aufrufpfad für Plain/HTML — unverändert in der Signatur |
| `output.renderers.narrow.render_telegram_bubbles` / `_tg_day_footer` | intern | Bestehender Telegram-Aufrufpfad — `segments` ist bereits vorhanden, keine Signaturerweiterung nötig |
| `pendant_gate.py` (Commit-Gate) | Tooling | Blockiert `trip_`/`compare_`-präfigierte Neuanlagen unter `src/output/renderers/**` — `fallback_notice.py` ist bewusst neutral benannt, kein Verstoß |
| `renderer_mail_gate.py` (Commit-Gate #811) | Tooling | Löst bei jedem Commit auf `email/plain.py`, `email/html.py`, `email/compact.py` aus — Voraussetzung: `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Lauf bestanden |

## Implementation Details

**R6 — Geteiltes Modul statt dritter Kopie.** Heute dupliziert `html.py`
die Formulierungslogik von `plain.py` bewusst (Kommentar „spiegelt
plain.py"). Eine dritte, unabhängige Kopie für Telegram wäre ein Verstoß
gegen die Projektregel zur Code-Teilung. Neues Modul
`src/output/renderers/fallback_notice.py` liefert **fertige Textzeilen**;
die drei Renderer bestimmen nur noch die Verpackung (HTML-`div` /
Plaintext-Zeile / Telegram-Zeile unter der Tagesfußzeile). Der Name trägt
bewusst **kein** `trip_`/`compare_`-Präfix, weil `pendant_gate.py`
präfigierte Neuanlagen unter `src/output/renderers/**` blockiert — das
Modul ist ohnehin kein Trip/Compare-Pendant-Fall (Telegram und Mail teilen
sich EIN Modul, keine zwei parallelen Bauteile). Die Ablage liegt bewusst
**nicht** in `email/helpers.py`: dieses Modul gehört zum E-Mail-Zweig
(`src/output/renderers/email/`), Telegram (`narrow.py`) liegt aber eine
Ebene höher und importiert heute nichts aus `email/`. Ein gemeinsamer Ort
auf der Ebene *über* beiden Kanal-Zweigen vermeidet einen Import von
Telegram-Code in ein E-Mail-Modul oder umgekehrt.

**Öffentliche Funktion:**

```
def build_fallback_lines(meta: ForecastMeta) -> list[str]:
    """Liefert 0, 1 oder 2 fertige Klartext-Zeilen zur Herkunfts-
    Vertretung. Reine Funktion, kein Rendering-Format -- die drei
    Renderer entscheiden selbst ueber Verpackung (HTML/Plain/Telegram)."""
```

**R1 — Zwei unabhängige Zeilen:**

1. *Gewitterzeile* — erscheint genau dann, wenn `meta.fallback_metrics`
   mindestens einen der drei Gewitter-Feldnamen enthält
   (`lightning_density_per_km2_3h`, `lightning_potential_lpi_jkg`,
   `hail_potential_grau_gsp` — Quelle der Wahrheit:
   `thunder_enrichment.py:36-43`, `_SIGNAL_ZU_FELD` + `_EINZELWERT_FELD`,
   **nicht** hartkodiert in `fallback_notice.py`, sondern von dort
   importiert, damit eine künftige vierte Gewittergröße automatisch erkannt
   wird).
2. *Wetterzeile* — erscheint genau dann, wenn `meta.fallback_model`
   gesetzt ist UND `meta.fallback_reason != "thunder_source_unavailable"`.

**R2 — Warum nicht `fallback_model` für die Gewitterzeile.** 2a setzt
`fallback_model`/`fallback_reason` nur, wenn sie noch `None` sind
(Merge-Schutz gegen #1115, `thunder_enrichment.py:217-219`). Hat zuvor ein
Grundvorhersage-Fallback geschrieben, steht dort dessen Modellname, obwohl
eine Gewitter-Vertretung stattfand. `fallback_metrics` ist davon nicht
betroffen (immer `extend`) — deshalb ist es die einzige zuverlässige
Erkennung der Gewitterzeile (ADR-0047 Folgepflicht, 2a-Spec KL-3).

**R3 — Kollisionsfall.** Haben beide Mechanismen gefeuert, erscheinen
BEIDE Zeilen. Die Gewitterzeile nennt dann **keinen** Quellennamen:
„Gewitterdaten von einer Ersatzquelle (gröbere Auflösung)" — der Name der
tatsächlichen Ersatzquelle (`eu_direct`) ist über die verfügbaren Felder
nicht zuverlässig rekonstruierbar, weil `fallback_model` in diesem Fall
bereits vom Grundvorhersage-Mechanismus belegt ist. Die Gewitterzeile darf
**niemals** `meta.fallback_model` lesen oder anzeigen, wenn die
Wetterzeile aktiv ist — das wäre der Name des falschen Ersatzmodells. Der
Renderer leitet die Gewitterquelle auch nicht aus Koordinaten/der
Routing-Tabelle (`thunder_routing.thunder_provider_for`) ab — das wäre
eigene Fachlogik im Ausgabe-Kanal und verstieße gegen ADR-0025 (eine
Gewitter-Quelle für die Ausgabe, keine Parallel-Ableitung).

**R4 — Metrikliste der Wetterzeile.** `meta.fallback_metrics` **abzüglich**
der drei Gewitter-Feldnamen, in Klartext übersetzt (Tabelle unten). Ist
die Restliste nach Abzug leer, entfällt die Klammer **ersatzlos** — kein
`()`, kein `Wetterzeile: `-Präfix ohne Inhalt. Das behebt/erhält das
`" : "`-Artefakt aus #1145.

**R5 — Behobener Darstellungsfehler.** Die heutige Zeile
`Fallback {metrics}: {model}` (`plain.py:365`, `html.py:533`) verknüpft
Metrikliste und Modellnamen ungeprüft in einem String und behauptet im
Kollisionsfall (Gewitter-Metrik + Grundvorhersage-Modell gleichzeitig in
`fallback_metrics`) einen Zusammenhang, den es nicht gibt. R1–R4 beheben
das mit; ausdrücklich Teil des Umfangs dieser Scheibe, kein separater
Nebenbefund.

**R7 — Unbekannte Werte brechen nichts.** Für eine Modell- oder
Metrik-Kennung ohne hinterlegte Übersetzung erscheint der Rohwert
unverändert (kein `KeyError`, kein `.get(..., "")` das den Eintrag
verschluckt) — kein Absturz, keine stille Auslassung.

**R8 — Datenzugriff ohne Signaturerweiterung.** `segments` ist in allen vier
Ausgaben bereits erreichbar (Belege: `plain.py:362`, `html.py:528`,
`compact.py:259`, `narrow.py:215-224`/`733-742`) — keine
Signaturerweiterung nötig.

**R9 — EINE Segmentauswahl für alle vier Ausgaben (Fix-Loop-Nachtrag
2026-08-07, Adversary-Befund F001).** Die Erstumsetzung hatte ZWEI
Auswahlregeln: die drei Mail-Renderer lasen starr `segments[0]`,
`narrow.py` das erste fehlerfreie Segment mit Zeitreihe. Für einen Trip,
dessen erstes Segment einen Abruffehler hat und dessen zweites eine
Vertretung trägt, zeigte Telegram den Hinweis und die Mail nichts.

Beide Varianten sind falsch, nicht nur eine: „erstes Segment" — in
jeder Spielart — verschweigt eine Vertretung, die erst eine spätere
Etappe betraf, und zwar in allen Kanälen gleichermaßen still. Das
widerspricht ADR-0018/ADR-0047 („Fallback ohne Kaschieren"), also dem
Zweck dieser Scheibe.

Verbindlich ist deshalb die geteilte Funktion
`fallback_notice.select_fallback_meta(segments)`: sie durchsucht **alle**
Segmente und liefert das **erste** `meta` mit einer Fallback-Markierung
(`fallback_model` gesetzt ODER `fallback_metrics` nicht leer); findet sie
keines, liefert sie `None`. Ein Segment ohne Zeitreihe wird
**übersprungen**, nicht als Abbruch behandelt. Alle vier Ausgaben
benutzen ausschließlich diese Funktion — keine kanal-eigene Segmentwahl
mehr.

**R10 — Der Hinweis darf das Briefing nicht mitreißen (Fix-Loop-Nachtrag
2026-08-07, Adversary-Befund F002).** `_gewitter_felder()` importierte
`providers.thunder_enrichment` bei **jedem** Aufruf mit `meta != None` —
auch im Normalfall ganz ohne Fallback. Ein kaputter Provider-Import riss
damit die gesamte Mail- und Telegram-Rendering-Kette mit, für Trips ohne
jeden Fallback. Zwei Vorkehrungen: (a) der Import läuft nur bei
nicht-leerer `fallback_metrics`, (b) er ist gegen `ImportError`
abgesichert — schlägt er fehl, entfällt die Gewitterzeile und das
Briefing rendert weiter. Begründung: **ADR-0047 Entscheidung 3** hält
fest, dass ein Ausfall der Gewitterquelle die Grundvorhersage nie kippen
darf; für den Anzeigeweg gilt dasselbe Prinzip. Die Herleitung der
Feldnamen aus dem Produktivcode (SSoT, R1) bleibt im Normalfall
unverändert erhalten — sie entfällt nur im Fehlerfall.

**R11 — Keine falsche Zuschreibung: lieber gar keine Werte nennen
(Fix-Loop-Nachtrag 2026-08-07, Adversary-Befund F003).** Fällt der
Provider-Import aus (R10), kennt die Formulierungsfunktion die
Gewitter-Feldnamen nicht mehr und kann Gewitter- von Wetterwerten nicht
mehr **trennen**. Der R4-Abzug greift dann nicht: im Kollisionsfall
(`fallback_metrics` trägt gleichzeitig einen Gewitter- und einen
Nicht-Gewitter-Feldnamen) landete der Gewitter-Feldname in der Klammer
der **Wetterzeile** und wurde damit dem Ersatzmodell der Grundvorhersage
zugeschrieben — einer Quelle, die mit den Blitzdaten nichts zu tun hat
(AC-8-Verstoß).

Regel: **ist die Trennung nicht möglich, entfällt die Klammer der
Wetterzeile vollständig.** Die Zeile lautet dann nur noch
`Einzelne Wetterwerte von Ersatzmodell: <Quelle>`. Weniger Information
ist hinnehmbar, eine falsche Zuschreibung nicht.

Umsetzung: `_gewitter_felder()` unterscheidet „nicht ermittelbar"
(`None`) von „ermittelt, es gibt keine" (leeres `frozenset`). Bewusst
**keine** Rückfall-Konstante mit den drei bekannten Feldnamen: das wäre
eine zweite Wahrheitsquelle und würde genau die SSoT-Eigenschaft
aufweichen, wegen der R1 so gebaut ist.

**Wortlaut-Muster (PO-Auswahl, E2 — Klartext auch für den
Bestandshinweis):**

```
Gewitterdaten von Ersatzquelle: DWD Europa (gröbere Auflösung)
Einzelne Wetterwerte von Ersatzmodell: DWD Europa (Wolken, Sicht)
```

Kollisionsfall (R3), Gewitterzeile ohne Quelle:

```
Gewitterdaten von einer Ersatzquelle (gröbere Auflösung)
Einzelne Wetterwerte von Ersatzmodell: DWD Europa (Wolken, Sicht)
```

Verpackung je Kanal:

- **Plain/Compact:** je eine eigene Zeile im Footer-Block, an derselben
  Stelle, an der heute `Fallback {metrics}: {model}` steht.
- **HTML:** derselbe `fallback_row`-`<div>`, eine `<div>` je Zeile (0–2
  `<div>`s statt heute maximal 1).
- **Telegram:** dieselbe(n) Zeile(n), als eigene Zeile(n) **unter** der
  bestehenden Tagesfußzeile (`⚡ … · Sicht … · 0°C-Grenze …`) in derselben
  Kurzübersicht-Bubble, vor dem `_tg_vortag_line`-Block. Kein `_wrap()`
  auf über 56 Zeichen nötig, da die Zeilen kurz sind — sofern doch
  Umbruch nötig wird, gilt dasselbe `_wrap(..., _TG_PROSE_WIDTH)`-Muster
  wie für die übrigen Kurzübersicht-Zeilen.

**Übersetzungstabelle Quellen (`fallback_model` → Klartext):**

| Rohwert | Klartext | Zusatz |
|---|---|---|
| `eu_direct` | DWD Europa | (gröbere Auflösung) |
| `de_direct` | DWD Deutschland | — |
| `fr_direct` | Météo-France | — |
| `at_direct` | GeoSphere Österreich | — |
| `icon_eu` | DWD Europa | (gröbere Auflösung) |
| `icon_d2` | DWD Deutschland | — |
| `meteofrance_arome` | Météo-France | — |
| `metno_nordic` | MET Norway | — |
| `ecmwf_ifs04` | ECMWF | (gröbere Auflösung) |
| alles andere | Rohwert unverändert (R7) | — |

**Übersetzungstabelle Metriken (`fallback_metrics` → Klartext).**
Vollständig gegenüber allen 18 Einträgen von
`OpenMeteoProvider._PARAM_TO_FIELD` (`openmeteo.py:378-398`) plus den
beiden Schnee-Feldnamen und den drei Gewitter-Feldnamen (letztere nur zur
Vollständigkeit der Tabelle — sie erscheinen wegen R4 nie in der
Wetterzeile, nur zur Erkennung der Gewitterzeile relevant):

| Rohwert | Klartext |
|---|---|
| `temperature_2m` | Temperatur |
| `apparent_temperature` | gefühlte Temperatur |
| `relative_humidity_2m` | Luftfeuchtigkeit |
| `dewpoint_2m` | Taupunkt |
| `pressure_msl` | Luftdruck |
| `cloud_cover` | Bewölkung |
| `cloud_cover_low` | Tiefe Wolken |
| `cloud_cover_mid` | Mittelhohe Wolken |
| `cloud_cover_high` | Hohe Wolken |
| `wind_speed_10m` | Wind |
| `wind_direction_10m` | Windrichtung |
| `wind_gusts_10m` | Böen |
| `precipitation` | Niederschlag |
| `precipitation_probability` | Niederschlagswahrscheinlichkeit |
| `visibility` | Sicht |
| `cape` | Gewitterenergie |
| `freezing_level_height` | 0°C-Grenze |
| `uv_index` | UV-Index |
| `weather_code` | Wetterlage |
| `snow_depth` | Schneehöhe |
| `swe_tot` | Wasseräquivalent Schnee |
| `lightning_density_per_km2_3h` | Blitzdichte |
| `lightning_potential_lpi_jkg` | Blitzpotenzial |
| `hail_potential_grau_gsp` | Hagelsignal |
| alles andere | Rohwert unverändert (R7) | — |

**Ergänzt gegenüber der Startliste des Auftrags:** `relative_humidity_2m`
(Luftfeuchtigkeit), `dewpoint_2m` (Taupunkt), `pressure_msl` (Luftdruck),
`cloud_cover_low` (Tiefe Wolken), `cloud_cover_mid` (Mittelhohe Wolken),
`cloud_cover_high` (Hohe Wolken), `wind_direction_10m` (Windrichtung) —
alle sieben stammen aus `_PARAM_TO_FIELD` (`openmeteo.py:378-398`) und
fehlten in der ursprünglichen Tabelle des Auftrags; die Klartext-Labels
sind identisch zu den bestehenden `label_de`-Werten in
`app/metric_catalog.py` übernommen (Zeilen 165/178/382/397/412/233/485),
damit derselbe Begriff nicht doppelt benannt im System existiert.

## Expected Behavior

- **Input:** Ein Segment, dessen `timeseries.meta` (a) keinen, (b) nur
  einen Gewitter-, (c) nur einen Grundvorhersage-, oder (d) beide
  Fallback-Typen trägt.
- **Output:** Je nach Fall 0, 1 oder 2 Klartext-Zeilen in der Mail
  (Vollversion HTML+Text, Kompakt) bzw. in der Telegram-Kurzübersicht-
  Bubble. Kein technischer Rohwert (`icon_eu`, `at_direct`, `cape`,
  `Fallback`) mehr sichtbar außer im R7-Fallback-Fall einer unbekannten
  Kennung.
- **Side effects:** Keine. Reine Lesefunktion auf bereits vorhandenen
  Feldern, kein zusätzlicher Abruf, keine Zustandsänderung.

## Test Plan

### Bestandstests, die planmäßig brechen und MITGEZOGEN werden müssen

| Test | Datei:Zeile | Zu erhaltende Zusicherung |
|---|---|---|
| `test_html_footer_shows_fallback` | `tests/unit/test_model_metric_fallback.py:214` | HTML-Mail zeigt bei gesetztem Grundvorhersage-Fallback einen Herkunftshinweis — Assertion wechselt von `"fallback" in html.lower()` + `"icon_eu" in html` auf den neuen deutschen Wortlaut + `"DWD Europa"` |
| `test_plain_footer_shows_fallback` | `tests/unit/test_model_metric_fallback.py:224` | Dasselbe für die Plaintext-Mail |
| `test_footer_empty_metrics_no_colon_artifact` | `tests/unit/test_model_metric_fallback.py:234` | Bewacht Bug #1145 (kein `" : "`-Artefakt bei leerer `fallback_metrics`) — Zusicherung bleibt inhaltlich erhalten, Assertion auf deutschen Wortlaut umgestellt: bei leerer Restliste nach R4-Abzug entfällt die Klammer ersatzlos, keine leere Klammer `()`, kein `: ` ohne Inhalt |
| `test_no_fallback_no_hint` | `tests/unit/test_model_metric_fallback.py:248` | ⚠️ Überlebt eine Eindeutschung wörtlich, bewacht danach aber nichts mehr — er sucht `"fallback" not in body.lower()`, was im deutschen Text nie vorkommt. MUSS auf den deutschen Wortlaut umgestellt werden (z. B. `"Ersatzquelle" not in body` UND `"Ersatzmodell" not in body`), sonst ist er ein Test, der nicht mehr scheitern kann (Regel „Test, der nicht scheitern KANN, bewacht nichts") |
| `test_plain_email_footer_no_leading_colon_on_empty_metrics` | `tests/tdd/test_issue_1141_cross_provider_fallback.py:430` | Bewacht denselben #1145-Fall für den Cross-Provider-Totalausfall-Pfad (`fallback_model="at_direct"`, leere `fallback_metrics`) — Assertion auf `"GeoSphere Österreich"` statt `"at_direct"`, Leerzeichen-vor-Doppelpunkt-Artefakt bleibt verboten |

### Automatisierte Tests (TDD RED) — neu

Testdatei-Namen nach **Verhalten**, nicht nach Issue-Nummer
(`test_naming_gate.py` blockt Issue-nummerierte Neuanlagen hart).

- [ ] `tests/unit/test_fallback_notice.py::test_no_fallback_returns_no_lines` —
  GIVEN `ForecastMeta` ohne jeden Fallback WHEN `build_fallback_lines`
  aufgerufen wird THEN liefert die Funktion eine leere Liste.
- [ ] `tests/unit/test_fallback_notice.py::test_thunder_only_shows_thunder_line_with_source` —
  GIVEN `fallback_metrics=["lightning_potential_lpi_jkg"]`,
  `fallback_model="eu_direct"`, `fallback_reason="thunder_source_unavailable"`
  WHEN `build_fallback_lines` läuft THEN enthält die Rückgabe genau eine
  Zeile mit „DWD Europa" und keine zweite Zeile.
  🔧 **Korrigiert 2026-08-07 (Befund aus der RED-Phase).** Die Erstfassung
  gab `fallback_model=None` vor und verlangte trotzdem den Quellennamen
  „DWD Europa" — unerfüllbar, weil ohne `fallback_model` kein Name
  vorliegt und R3 jede andere Ableitung verbietet. Nachgemessen an
  `thunder_enrichment.py:286-288`: im Gewitter-**Alleinfall** sind die
  Singularfelder noch unbesetzt, 2a schreibt also sehr wohl
  `fallback_model="eu_direct"` **und**
  `fallback_reason="thunder_source_unavailable"`. Genau dadurch
  unterdrückt R1.2 die Wetterzeile, und die Gewitterzeile darf den Namen
  führen — der Verzicht auf den Namen nach R3 gilt **ausschließlich** im
  Kollisionsfall. Der Fixture-Zustand bildet damit ab, was das Produkt
  tatsächlich schreibt.
- [ ] `tests/unit/test_fallback_notice.py::test_weather_only_shows_weather_line_translated` —
  GIVEN `fallback_model="icon_eu"`, `fallback_reason="model_5xx"`,
  `fallback_metrics=["cape", "visibility"]` WHEN `build_fallback_lines`
  läuft THEN enthält die Rückgabe genau eine Zeile mit „Gewitterenergie,
  Sicht" und „DWD Europa", kein `icon_eu`, kein `Fallback`.
- [ ] `tests/unit/test_fallback_notice.py::test_collision_shows_both_lines_thunder_without_source` —
  GIVEN `fallback_metrics=["cape", "lightning_potential_lpi_jkg"]`,
  `fallback_model="icon_eu"`, `fallback_reason="model_5xx"` (Grundvorhersage
  hat zuerst geschrieben) WHEN `build_fallback_lines` läuft THEN enthält
  die Rückgabe zwei Zeilen; die Gewitterzeile enthält NICHT „DWD Europa"
  oder „icon_eu"; die Wetterzeile enthält „Gewitterenergie" (aus `cape`),
  NICHT „Blitzpotenzial" (Gewitter-Feldname wurde nach R4 abgezogen).
- [ ] `tests/unit/test_fallback_notice.py::test_weather_line_empty_bracket_omitted` —
  GIVEN `fallback_model="at_direct"`, `fallback_metrics=[]` WHEN
  `build_fallback_lines` läuft THEN enthält die Wetterzeile keine Klammer
  `()` und kein doppeltes Leerzeichen/Doppelpunkt-Artefakt.
- [ ] `tests/unit/test_fallback_notice.py::test_unknown_model_shows_raw_value` —
  GIVEN `fallback_model="unbekanntes_modell_xyz"`,
  `fallback_metrics=["ein_unbekanntes_feld"]` WHEN `build_fallback_lines`
  läuft THEN enthält die Wetterzeile den Rohwert `unbekanntes_modell_xyz`
  und `ein_unbekanntes_feld` unverändert (R7), kein Absturz.
- [ ] `tests/unit/test_model_metric_fallback.py::test_compact_footer_shows_fallback` (neu, in
  bestehender Datei ergänzt) — GIVEN Kompakt-Mail mit gesetztem
  `fallback_model` WHEN `TripReportFormatter.format_email` den
  Kompakt-Body rendert THEN enthält der Body die deutsche Wetterzeile
  (heute: 0 Treffer, s. Kontext-Doc „2 von 7 Ausgaben").
- [ ] `tests/tdd/test_telegram_footer_metric_gating.py` (ergänzt) —
  GIVEN Segmente mit `meta.fallback_metrics` enthält
  `lightning_potential_lpi_jkg` WHEN `render_telegram_bubbles` die
  Kurzübersicht-Bubble baut THEN enthält deren Text die Gewitterzeile
  unter der bestehenden `⚡ …`-Fußzeile; GEGENPROBE: ohne Fallback keine
  zusätzliche Zeile.

Muster für echte Renderer-Aufrufe (keine Mock-Theater): analog
`TestFooterFallbackInfo._make_segment_data`
(`tests/unit/test_model_metric_fallback.py:182-212`) — echte
`SegmentWeatherData`/`NormalizedTimeseries`-Objekte, echter Aufruf von
`TripReportFormatter.format_email` bzw. `render_telegram_bubbles`, keine
gemockten Renderer-Methoden.

## Acceptance Criteria

- **AC-1:** Given ein Segment, dessen `fallback_metrics` einen der drei
  Gewitter-Feldnamen enthält (z. B. `lightning_potential_lpi_jkg`), When
  die Trip-Briefing-Mail Vollversion gerendert wird, Then enthält sowohl
  der HTML- als auch der Text-Body eine Klartext-Zeile, die eine
  Gewitter-Ersatzquelle benennt (z. B. „DWD Europa").
  - Test: `test_thunder_only_shows_thunder_line_with_source` plus
    Ergänzung an `test_html_footer_shows_fallback`/
    `test_plain_footer_shows_fallback` mit Gewitter-Feldname statt `cape`.

- **AC-2:** Given ein Segment mit gesetztem `fallback_model` (Grundvorhersage-
  Fallback), When die Kompakt-Mail gerendert wird, Then enthält der Body
  eine Klartext-Herkunftszeile — heute (vor dieser Scheibe) zeigt die
  Kompakt-Mail in diesem Fall gar keinen Hinweis.
  - Test: `test_compact_footer_shows_fallback` (neu).

- **AC-3:** Given ein Segment mit gesetztem Fallback (Gewitter oder
  Grundvorhersage), When die Telegram-Langform-Nachricht gerendert wird,
  Then erscheint in der Kurzübersicht-Bubble eine zusätzliche Klartext-
  Zeile unter der bestehenden Tagesfußzeile (`⚡ … · Sicht … ·
  0°C-Grenze …`) — heute erscheint dort kein Hinweis.
  - Test: Ergänzung in `tests/tdd/test_telegram_footer_metric_gating.py`.

- **AC-4:** Given ein Grundvorhersage-Fallback mit mehreren betroffenen
  Metriken, When eine der drei Ausgaben gerendert wird, Then sind die
  Metriknamen in deutschem Klartext lesbar (z. B. „Sicht",
  „Gewitterenergie") und nirgends in der gerenderten Ausgabe erscheint
  mehr das Wort „Fallback" oder eine technische Kennung wie `icon_eu`
  bzw. `eu_direct`.
  - Test: `test_weather_only_shows_weather_line_translated` plus
    Anpassung von `test_html_footer_shows_fallback`/
    `test_plain_footer_shows_fallback` auf die neue Assertion „kein
    `Fallback` im Text, kein `icon_eu` im Text, `DWD Europa` vorhanden".

- **AC-5:** Given ein Segment, bei dem sowohl ein Gewitter- als auch ein
  Grundvorhersage-Fallback gleichzeitig vorliegen (Kollisionsfall), When
  eine der drei Ausgaben gerendert wird, Then erscheinen zwei getrennte
  Zeilen, die Gewitterzeile nennt dabei keinen Quellennamen, und in
  keiner der beiden Zeilen erscheint der Name des Grundvorhersage-
  Ersatzmodells in der Gewitterzeile.
  - Test: `test_collision_shows_both_lines_thunder_without_source`.

- **AC-6:** Given ein Segment ganz ohne jeden Fallback (Normalfall), When
  eine der drei Ausgaben gerendert wird, Then erscheint in keiner
  Ausgabe eine Herkunfts-/Ersatzzeile, kein leerer Rahmen (kein leeres
  `<div>`, keine leere Zeile an der Fallback-Position) und kein
  Klammer- oder Doppelpunkt-Artefakt.
  - Test: `test_no_fallback_no_hint` (umgestellt auf deutschen Wortlaut)
    plus `test_no_fallback_returns_no_lines` für die geteilte Funktion
    direkt.

- **AC-7:** Given ein Segment mit gesetztem Fallback, When die SMS oder
  die Telegram-Kurzform gerendert wird, Then enthält die Ausgabe keinen
  Fallback-Hinweis und die SMS bleibt innerhalb ihres 160-Zeichen-
  Budgets — strukturell erfüllt, weil die Kurzform `report.sms_text`
  sendet und `narrow.py`/`_tg_day_footer` dabei nicht durchlaufen wird
  (`notification_service.py:353-372`).
  - Test: SMS wird für **dasselbe** Segment gerendert, das in AC-1/AC-5
    den Hinweis erzeugt; geprüft wird am erzeugten SMS-Text, dass weder
    „Ersatzquelle" noch „Ersatzmodell" noch ein Quellen-Klartextname
    darin vorkommt und die Länge ≤ 160 Zeichen bleibt.
    **Kein Dateiinhalt-Check** (kein „Import X kommt in Datei Y nicht
    vor") — das wäre kein Verhaltensnachweis.

- **AC-8:** Given ein Grundvorhersage-Fallback mit `fallback_metrics`, die
  sowohl einen Gewitter- als auch einen Nicht-Gewitter-Feldnamen
  enthalten, When die Wetterzeile gebildet wird, Then enthält die Klammer
  der Wetterzeile ausschließlich die Nicht-Gewitter-Feldnamen — kein
  Gewitter-Feldname erscheint dort.
  - Test: Teil von `test_collision_shows_both_lines_thunder_without_source`
    (Prüfung, dass „Blitzpotenzial" NICHT in der Wetterzeile steht).

- **AC-9:** Given `fallback_model` oder `fallback_metrics` enthält eine
  Kennung ohne hinterlegte Übersetzung, When eine der drei Ausgaben
  gerendert wird, Then erscheint der Rohwert unverändert in der Ausgabe
  und das Rendering wirft keine Ausnahme.
  - Test: `test_unknown_model_shows_raw_value`.

- **AC-10:** Given derselbe Fallback-Zustand (Gewitter, Grundvorhersage
  oder Kollision), When alle drei Ausgaben (HTML-Mail, Plain/Kompakt-Mail,
  Telegram) für dasselbe Segment gerendert werden, Then enthalten alle
  drei denselben Kern-Wortlaut der Herkunftsangabe (gleiche Quellen-
  Klartextnamen, gleiche Metrik-Klartextnamen) — nur die Verpackung
  (HTML-`div`, Text-Zeile, Telegram-Zeile) unterscheidet sich.
  - Test: Ein parametrisierter Vergleich über die drei
    Renderer-Testfälle (HTML/Plain/Telegram) mit identischem
    `ForecastMeta`-Fixture, der denselben übersetzten Kernstring in allen
    drei Ausgaben nachweist.

## Known Limitations

- **Ortsvergleichs-Mail bleibt ohne Hinweis** (`compare_html.py:1388-1391`
  nutzt weiterhin den festen String `build_origin_footer("compare",
  source="Open-Meteo")`). Grund: dort existieren mehrere Orte mit je
  eigener Herkunft — die Frage „welcher Ort hatte die Ersatzquelle?" ist
  eigenständig zu entscheiden (eigene Darstellungslogik nötig, kein
  einfacher Wiederverwendungsfall dieser Scheibe). Eigene Folgescheibe.
- **Telegram-Kurzform bleibt ohne Hinweis**, obwohl es „Telegram" ist.
  Begründung: bei `telegram_style="kurzform"` sendet
  `notification_service.py:353-372` den bereits gerenderten
  `report.sms_text` (`SMSTripFormatter`, 160-Zeichen-Budget) — die
  Telegram-Bubbles und damit `_tg_day_footer` werden für diesen Versandweg
  nie gelesen. Ein Hinweis dort würde das 160-Zeichen-Budget sprengen und
  wäre PO-Entscheidung E1 zufolge ohnehin nicht vorgesehen.
- **Kollisionsfall zeigt die Gewitterquelle namenlos** (R3). Der
  tatsächliche Ersatzquellenname ist über die verfügbaren Felder nicht
  zuverlässig rekonstruierbar, sobald `fallback_model` bereits vom
  Grundvorhersage-Mechanismus belegt wurde (Merge-Schutz aus 2a). Eine
  Ableitung über Koordinaten/Routing-Tabelle wäre möglich, verstieße aber
  gegen ADR-0025 (keine Fachlogik-Ableitung im Ausgabe-Kanal) und ist
  bewusst nicht Teil dieser Scheibe.
- **Bei mehreren betroffenen Etappen gewinnt die erste gefundene**
  (R9, Fix-Loop 2026-08-07). Tragen zwei Segmente unterschiedliche
  Vertretungen, nennt die Ausgabe nur die des ersten markierten Segments.
  Begründung: die Aussage lautet „hier wurde ausgewichen", nicht „auf
  Etappe N wurde ausgewichen" — eine etappengenaue Zuordnung (Zeile je
  Etappe, oder Etappennummer im Text) wäre eine eigene
  Produktentscheidung mit eigener Darstellungsfrage, keine
  Implementierungsdetail-Wahl. Bewusst nicht Teil dieser Scheibe.
- **Fällt der Gewitter-Provider-Import aus, verschwindet die
  Gewitterzeile still — und die Wetterzeile nennt zusätzlich keine
  Werte mehr** (R10/R11, präzisiert im Fix-Loop 2026-08-07 nach Befund
  F003). Das Briefing rendert dann vollständig weiter, aber (a) ohne den
  Gewitter-Vertretungshinweis und (b) mit einer Wetterzeile **ohne
  Klammer**: `Einzelne Wetterwerte von Ersatzmodell: <Quelle>`. Der
  zweite Punkt ist der Preis dafür, dass ohne die Feldnamen keine
  Trennung möglich ist — die frühere Fassung dieser Zeile behauptete nur
  „die Gewitterzeile verschwindet"; tatsächlich konnte ein
  Gewitter-Feldname in der Wetterzeilen-Klammer landen und dort dem
  falschen Ersatzmodell zugeschrieben werden. Beides — der fehlende
  Hinweis wie die fehlende Werteliste — geschieht ohne eigenes Signal,
  dass etwas fehlt. Bewusster Vorzug gegenüber den Alternativen
  „gesamte Briefing-Ausgabe fällt aus" (ADR-0047 Entscheidung 3) und
  „falsche Zuschreibung anzeigen" (R11). Der Fall setzt einen defekten
  `src/providers/`-Zweig voraus, der ohnehin über den regulären
  Fehlerpfad auffällt.
- **Alarm-/Warnmails bleiben außen vor** (`alert/*`). Dort wäre der
  Herkunftshinweis Rauschen — der Nutzer erwartet in einer Warnmail eine
  Handlungsaufforderung, keine Provider-Herkunftsinformation.
- **Vollständigkeit der Modell-Übersetzungstabelle ist nicht mit einem
  Wächter abgesichert.** Ein künftiges neues `fallback_model`-Vokabular
  (neue Direktquelle, neues Open-Meteo-Rechenmodell) fällt ohne
  Testanpassung auf R7 (Rohwert-Anzeige) zurück — funktional korrekt,
  aber ohne Klartext, bis die Tabelle nachgezogen wird. Kein
  automatischer Erkennungsmechanismus für „neue Kennung ohne Übersetzung"
  ist Teil dieser Scheibe.
- **Die Metrik-Klartextnamen sind mit `app/metric_catalog.py` abgeglichen,
  aber nicht mechanisch daran gekoppelt.** Die Labels wurden bei der
  Erstellung 1:1 aus den `label_de`-Werten des Katalogs übernommen, damit
  derselbe Begriff im Produkt nicht zweimal verschieden heißt. Eine
  automatische Ableitung ist bewusst **nicht** gebaut: `fallback_metrics`
  ist mit **Open-Meteo-Parameternamen** bzw. Datenpunkt-**Feldnamen**
  geschlüsselt, der Katalog dagegen mit **Metrik-IDs** — die Brücke
  zwischen beiden Namensräumen wäre eine eigene, fehleranfällige
  Abbildung ohne heutigen Nutzen. Preis: Wird ein `label_de` im Katalog
  umbenannt, driftet diese Tabelle still. Als Sammel-Eintrag für #1199
  vorzumerken, falls das Muster sich wiederholt.

## Validierung

**Renderer-Commit-Gate #811 (un-überspringbar).** Diese Scheibe ändert
`src/output/renderers/email/plain.py`, `email/html.py` und
`email/compact.py` — alle drei stehen auf der Sperrliste von
`renderer_mail_gate.py`. Vor dem Commit müssen **beide** vorliegen:
(1) `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün,
(2) ein erfolgreicher `briefing_mail_validator.py`-Lauf gegen eine echt
zugestellte Staging-Mail (Marker-Header `X-GZ-Mail-Type: trip-briefing` +
`X-GZ-Format: full|compact`). Erst bei Exit 0 darf „E2E bestanden" gesagt
werden.

`narrow.py` löst keines der beiden Mail-Gates aus (nicht in der
Sperrliste), unterliegt aber dem allgemeinen Commit-Gate „Tests der
berührten Dateien" (#1481 A).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (kein neues ADR nötig)
- **Rationale:** Diese Scheibe führt keine neue, dauerhafte
  Architekturentscheidung ein — sie wendet die bereits akzeptierten
  Invarianten aus ADR-0018 (Nicht-Kaschieren) und ADR-0047 (Gewitter-
  Vertretung markieren) auf die Ausgabeschicht an und behebt einen
  bestehenden Darstellungsfehler (R5). Die einzige neue strukturelle
  Entscheidung — ein geteiltes Modul statt Renderer-eigener Kopien (R6)
  — ist eine Implementierungsentscheidung im Rahmen der bereits
  etablierten Projektregel zur Code-Teilung, keine neue
  Architekturfrage.

## Changelog

- 2026-08-06: Initial spec created (Issue #1492 Scheibe 2b, Kontext
  `docs/context/feat-1492-s2b-fallback-sichtbarkeit.md`, PO-Entscheidungen
  E1/E2/E3, Tech-Lead-Regeln R1–R8).
- 2026-08-07: Fix-Loop nach Adversary-Verdict BROKEN. R8 präzisiert, R9
  (eine geteilte Segmentauswahl über alle vier Ausgaben, Befund F001) und
  R10 (Provider-Import nur bei Bedarf und `ImportError`-fest, Befund F002)
  ergänzt; zwei Known Limitations nachgetragen.
- 2026-08-07 (Fix-Loop 2): zweiter Adversary-Durchgang, Verdict BROKEN
  (F003 HIGH, F004 MEDIUM). R11 ergänzt („keine falsche Zuschreibung —
  ist die Trennung nicht möglich, entfällt die Klammer der Wetterzeile
  vollständig", Befund F003); die R10-Known-Limitation entsprechend
  korrigiert — sie behauptete zu wenig. F004 war ein reiner Testbefund
  (die AC-3-Reihenfolge-Zusicherung verglich gegen das erste „⚡" im
  Text statt gegen die echte Tagesfußzeile und konnte deshalb nicht
  scheitern); der Prüfling blieb unverändert, die Zusicherung ist jetzt
  an `_tg_day_footer()` verankert.
