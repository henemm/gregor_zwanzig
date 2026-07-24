---
entity_id: issue_1110_compare_mail_v2
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
issue: 1110
tags: [compare, email, renderer, html, python, redesign]
---

# Issue #1110 — Ortsvergleich-Mail v2 (neues Layout nach Design-Vorlage)

> **⚠️ Teil-Ablösung am 2026-07-24 durch
> [`compare_location_order.md`](../../modules/compare_location_order.md)
> (Issue #1359, Scheibe 2).** Die hier festgeschriebene **alphabetische**
> Orts-Reihenfolge (AC-1, Zeilen 223-227, sowie die Erwähnungen bei „Datenmodell"
> und „Ort-Reihenfolge in HTML und Klartext") ist nicht mehr gültig: Orte
> erscheinen jetzt in der vom Nutzer im Orte-Tab konfigurierten
> Preset-Reihenfolge. Bemerkenswert: die alphabetische Festlegung überstimmte
> 2026-07-08 ihrerseits eine frühere Preset-Reihenfolge-Vorgabe — #1359 Scheibe 2
> stellt exakt jene ältere Vorgabe wieder her. Der Rest (kein Score, kein Winner,
> kein Best-Wert-Highlight) gilt unverändert. Diese Archiv-Datei wird bewusst
> **nicht** umgeschrieben — nur dieser Vermerk verweist auf den aktuellen Stand.

## Approval

- [ ] Approved

## Purpose

Löst den bestehenden Ortsvergleich-Mail-Renderer (Score/Winner-Box, primary/secondary-Matrix)
durch das neue v2-Layout aus der Design-Vorlage `screen-compare-email-v2.jsx` ab: **kein
Score/Ranking mehr**, stattdessen eine Übersichtstabelle (Metriken als Zeilen × Orte als
Spalten, inkl. amtlicher Warnungen als eigener Zeile) und Stundentabellen für **alle** Orte.
Das visuelle Vokabular entspricht 1:1 der Trip-Briefing-Mail (Header/Eyebrow/Tags, 4-stufige
Risk-Zellfärbung, Mono-Tabellen, dunkler Footer). Betrifft ausschließlich den E-Mail-Kanal
(HTML + Klartext); Score bleibt als Datenfeld im Modell erhalten (App-Darstellung unverändert,
separates Folge-Issue).

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `render_compare_html()` (Voll-Neuschrieb)
- **File:** `src/output/renderers/comparison.py`
- **Identifier:** `render_comparison_text()` (Neuschrieb), `render_comparison_html()` (ENTFERNT — bestätigter toter Alt-Renderer, koordiniert mit #1108)
- **File:** `.claude/hooks/email_spec_validator.py` (Kern-Umstellung auf v2-Vertrag)

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen im Python-Core-Backend
> (`src/output/renderers/`, `src/services/`) bzw. im Hook-Tooling (`.claude/hooks/`).
> Kein Frontend- oder Go-API-Code betroffen.

## Estimated Scope

- **LoC:** ~600–900 (Renderer-Neuschrieb + Klartext-Neuschrieb + Validator-Umstellung +
  Tests; toter Alt-Renderer entfällt mit −300). **LoC-Override 600 genehmigt und gesetzt**
  (`workflow.py set-field loc_limit_override 600`, PO-Entscheidung 2026-07-08).
- **Files:** 8 Code/Test-Dateien + 3 Doku-Dateien
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ComparisonEngine.run()` (`src/services/comparison_engine.py`) | intern | Liefert `ComparisonResult` unverändert — keine Datenlagen-Änderung durch dieses Issue |
| `ComparisonResult` / `LocationResult` (`src/app/user.py:148,178`) | intern | `LocationResult.official_alerts`, `.hourly_data`, `.temp_max`, `.wind_max`, `.sunny_hours`, `.cloud_avg`, `.error`; `ComparisonResult.locations` (Anzeige-Reihenfolge = alphabetisch nach Ortsname, **kein** Score-Sort mehr — `.winner`-Property bleibt im Modell, wird von der Mail nicht mehr gelesen; PO-Update 2026-07-08) |
| `ForecastDataPoint` (`src/app/models.py:88`) | intern | Stundenwerte: `t2m_c`, `wind_chill_c` (= „Gefühlt", Open-Meteo `apparent_temperature`, `src/providers/openmeteo.py:305,712`), `wind10m_kmh`, `gust_kmh`, `precip_1h_mm`, `cloud_total_pct`, `uv_index` |
| `OfficialAlert` (`src/services/official_alerts/models.py:15`) | intern | `hazard` (`extreme_heat`, `wildfire_risk`, `access_ban`), `level` (1–4, für Waldbrand-Stufe), `label` (Langform, bereits fertig formatiert z.B. „Zugang eingeschränkt — {Massiv}") |
| `render_official_alerts_html()` (`src/output/renderers/alert/official_alerts.py:24`) | intern | Wiederverwendet für den Langform-Warn-Streifen je Ort (border-left-Div, Level-Farbmapping) — **kein** Copy-Paste (ADR-0011) |
| `profile_signature()` (`src/output/renderers/email/profile_signature.py`) | intern | Liefert weiterhin Eyebrow-Text für den Header-Stat „Profil" |
| `design_tokens.py` (`src/output/renderers/email/design_tokens.py`) | intern | `G_INK`, `G_PAPER`, `G_ACCENT`, `G_SUCCESS`, `G_WARNING`, `FONT_UI`, `FONT_DATA`, `WEB_FONT_LINK` — die 4-stufigen Risk-Zellfarben (`#fbeeb8`/`#fad6b8`/`#f6c5bf`) sind dort NICHT als Konstanten hinterlegt (Bestandsmuster: `html.py` hardcodet sie ebenfalls direkt, Zeile 562–564) → `compare_html.py` übernimmt dasselbe Muster, keine neue Abstraktionsebene |
| `send_one_compare_preset()` (`src/services/scheduler_dispatch_service.py:198`) | intern | Einziger echter Versandpfad; liefert `preset["name"]`, `preset["schedule"]`, `preset["weekday"]` — Basis für Abo-Footer |
| `validator_render_service.py:170` | intern | Zweiter Aufrufer (Preview-Endpoint Issue #464) — `winner_tags`-Parameter entfällt |

## Implementation Details

### 1. Score/Winner-Entfernung (HTML + Klartext)

- `render_compare_html()` liest `result.winner` **nicht mehr**. Kein Score-Badge, keine
  Winner-Card, keine `winner_tags`/`_generate_winner_tags`/`_render_winner_card`/
  `_render_winner_tags`/`_render_tag` — alle vollständig entfernt.
- Ort-Reihenfolge in HTML und Klartext = **alphabetisch nach Ortsname** (deutsch,
  case-insensitiv, z.B. `sorted(locs, key=lambda l: l.location.name.casefold())`) —
  PO-Update 2026-07-08 (überstimmt frühere „Preset-Reihenfolge"). Gilt einheitlich für
  Übersichts-Spalten UND Stundentabellen-Abschnitte.
- `render_comparison_text()` (Klartext) verliert Zeile „🏆 EMPFEHLUNG / Score" komplett.

### 2. Übersichtstabelle (Metriken × Orte)

Fixe Metrik-Liste für den heutigen Metrik-Stand (Konfigurierbarkeit folgt in #1104–#1107):

```python
CV2_METRICS = [
    {"key": "warn",     "label": "Amtliche Warnungen", "kind": "warn"},
    {"key": "temp_max",  "label": "Temp max", "unit": "°C", "sev": _sev_temp,  "highlight": None},
    {"key": "wind_max",  "label": "Wind",     "unit": "km/h", "sev": _sev_wind, "highlight": "min"},
    {"key": "sunny_hours","label": "Sonne",   "unit": "h", "highlight": "max", "decimals": 1},
    {"key": "cloud_avg", "label": "Wolken",   "unit": "%", "highlight": "min"},
    {"key": "uv_max",    "label": "UV max",   "unit": "",  "sev": _sev_uv,   "highlight": None},
]
```

- `uv_max` ist **kein** Feld auf `LocationResult` — wird zur Renderzeit aus
  `max(dp.uv_index for dp in loc.hourly_data if dp.uv_index is not None)` abgeleitet
  (`None` falls keine Stundendaten oder alle `uv_index is None`).
- **#1104-Integration (PO-Entscheidung 2026-07-08, nach Parallel-Landung von #1104 auf
  main):** `render_compare_email`/`render_compare_html` nehmen `enabled_metrics` und
  `top_n_details` wieder an. `enabled_metrics` (Renderer-IDs via
  `resolve_enabled_metrics`, `None` = alle) filtert die numerischen Metrik-Zeilen der
  Übersichtstabelle — die Warn-Zeile erscheint IMMER; Stundentabellen bleiben 8-spaltig
  unberührt. `top_n_details` wird angenommen, hat aber KEINE Wirkung: die Mail zeigt
  immer alle Orte; die „Anzahl Orte"-Einstellung wird in #1105–#1107 auf dem neuen
  Layout neu definiert.
- **KEIN Best-Value-Highlight (PO-Update 2026-07-08, überstimmt JSX-Vorlage in diesem
  Punkt und löst Adversary-Finding F001 auf):** Die grüne „günstigster Wert"-Markierung
  entfällt komplett — `highlight`-Semantik wird nicht implementiert, kein
  `rgba(…)`-Grünton in der Übersichtstabelle, und der Tabellenkopf-Hinweis lautet nur
  „← scrollen" (ohne „grün = günstigster Wert").
- **Zellfarbe ausschließlich Severity:** `temp_max`/`wind_max`/`uv_max` tragen die
  4-Stufen-Risk-Färbung (`_sev_temp`/`_sev_wind`/`_sev_uv`); `sunny_hours`/`cloud_avg`
  bleiben ungefärbt.
- **Warn-Zeile (`kind="warn"`):** Zelle zeigt gestapelte Kurz-Chips, ein Chip pro
  `OfficialAlert` des Ortes. Kürzel-Mapping (dünner Anzeige-Layer, KEINE neue Taxonomie):

  | `hazard` | Kürzel-Text | Severity (Zellfarbe) |
  |---|---|---|
  | `extreme_heat` | `Hitze` | warn (orange) |
  | `wildfire_risk` | `Brand · {level}` | caution (2) / warn (3) / danger (4) je `level` |
  | `access_ban` | `Zugang` | caution |
  | *(unbekannt)* | `alert.label` (Fallback, ungekürzt) | info/grau |

  Keine Warnungen an einem Ort → Zelle zeigt `—` (grauer Platzhalter, kein leeres `<td>`).
- Severity-Schwellen (`_sev_temp`, `_sev_wind`, `_sev_gust`, `_sev_rain`, `_sev_uv`) 1:1 aus der
  Vorlage übernommen: Temp ≥34/31/28 °C, Wind >40/30/20 km/h, Böen >60/45/30 km/h, Regen
  >8/4/1 mm, UV ≥8/6/3 → danger/warn/caution, sonst ok. **Überholt seit Issue #1214
  Scheibe 2 (2026-07-12):** `_sev_wind` ist auf `severity_for()`/Katalog-Schwellen
  umgestellt (`yellow:30, orange:50, red:70` statt der hartcodierten `>40/30/20`) — behebt
  eine Diskrepanz zur Trip-Briefing-Ampel bei 45 km/h (siehe
  `docs/specs/modules/issue_1214_metric_format_slice1_2.md`). Die übrigen Schwellen
  (`_sev_temp`, `_sev_gust`, `_sev_rain`, `_sev_uv`) sind von dieser Migration nicht betroffen.

### 3. Warn-Lead-Block (oben) + Langform-Warn-Streifen (je Ort)

- **Lead-Block:** Akzent-Bar (`border-left:2px solid G_ACCENT`) direkt unter dem Header, NUR
  wenn mindestens ein Ort mindestens eine `official_alerts`-Warnung hat. Aggregat-Satz +
  Tag-Zeile (z.B. „Extreme Hitze · N Orte", „Waldbrand Stufe {max} · {Ort}", „Zugang gesperrt
  · N Gebiete"). Bei 0 Warnungen über alle Orte entfällt der komplette Block (kein leerer
  Rahmen).
- **Langform-Streifen je Ort:** über jeder Ort-Stundentabelle, wiederverwendet
  `render_official_alerts_html()` (bereits vorhandener kanonischer Alert-Renderer,
  ADR-0011) — liefert die border-left-Divs mit `alert.label` (bereits Langform, z.B.
  „Zugang eingeschränkt — Massif des Maures"). Kein Streifen, wenn der Ort keine Warnung hat.

### 4. Stundentabellen (alle Orte)

Für jeden Ort in `result.locations` (nicht nur Top-N) eine Tabelle mit den Spalten Zeit / Temp
/ Gef. / Wind / Böen / Regen / Wolken / UV:

- **Gef.** = `dp.wind_chill_c` (Open-Meteo `apparent_temperature`, identische Quelle wie
  Trip-Mail `html.py:191`), `—` wenn `None`. Feldname ist historisch winterlastig, im Sommer
  = gefühlte Temperatur/Hitzeindex — keine neue Datenquelle nötig.
- Zellfärbung: Temp/Wind/Böen/Regen/UV nach den o.g. Schwellen; Wolken zeigt nur die
  Prozentzahl (keine Färbung, wie in der Vorlage).
- Ort ohne `hourly_data` → Abschnitt für diesen Ort entfällt (kein leerer Tabellenrumpf).
- Fehlerhafter Ort (`loc.error is not None`) → Stundentabelle entfällt für diesen Ort, in der
  Übersichtstabelle zeigen alle seine Zellen `—`.

### 5. Header / Stats / Legende / Abo-Footer / App-Footer

- Header identisch zum Bestandsmuster: Eyebrow „ORTS-VERGLEICH · {profile_signature(profile).eyebrow}",
  Titel (Preset-Name oder generischer Titel), Datum/Zeitfenster.
- Stats-Grid: „Profil" = `profile_signature(profile).eyebrow`, „Orte" = `len(result.locations)`,
  „Horizont" = statisch `+48h` (Bestandsverhalten, nicht Teil dieses Issues), „Erstellt" =
  aktuelle Uhrzeit.
- Legende: 4-stufige Risk-Skala (ok/caution/warn/danger) + Hinweis auf Warn-Kürzel.
- **Abo-Footer:** „Dieses Abo" mit `preset["name"]` + Ortsanzahl + Profil-Label; „Nächster
  Versand" mit berechnetem Termin, falls aus `preset["schedule"]`/`preset["weekday"]`
  ableitbar (daily → nächster Kalendertag; weekly → nächstes Auftreten von `weekday`), sonst
  `—` (Known Limitation, s.u.). `send_one_compare_preset()` reicht dafür `preset["name"]`,
  `preset["schedule"]`, `preset["weekday"]` als neue optionale Renderer-Parameter durch.
- **App-Footer:** dunkler Footer (`G_INK`) mit Marke, Zeitstempel/Quelle, Link-Zeile
  („Vergleich in App öffnen", „Abo bearbeiten", „Orte ändern", „Abmelden" — Ziel-URLs
  bestehende Platzhalter-Konvention, kein neuer Endpoint in diesem Issue).

### 6. Mobile/Desktop (Outlook-fest)

Kein CSS-Grid/Flexbox (JSX-Vorlage nutzt es nur für den Preview-Browser). Stattdessen
bestehendes Doppel-`<table>`-Pattern (vgl. `compare_html.py:364–385` alt): je ein
Desktop- und ein Mobile-Markup-Block, gesteuert über `@media (max-width: 480px)` mit
`display:none`/`display:table`-Umschaltung — analog zum bereits vorhandenen
`header-stats-desktop`/`header-stats-mobile`-Muster. Übersichtstabelle und Stundentabellen
bekommen je einen horizontal scrollbaren Wrapper (`overflow-x:auto`) für schmale Viewports,
statt (wie im alten Renderer) auf Karten-Layout umzuschalten — das entspricht der Vorlage
(„← scrollen"-Hinweis in `CV2SectionHead`), nicht dem alten `mobile-cards`-Pattern.

### 7. Klartext-Angleichung

`render_comparison_text()` wird strukturell an v2 angeglichen: Übersicht (Metrik-Zeilen je
Ort als Text-Tabelle) + Warnungen (Kurzform je Ort via `render_official_alerts_plain()`),
kein 🏆/Score mehr. Stundentabellen für alle Orte bleiben im Klartext-Teil kompakt (analog
Bestandsmuster, aber ohne Rang-Präfix `#N`).

### 8. Validator-Umstellung → DELEGIERT an Issue #1108 (PO-Umscoping 2026-07-08)

`.claude/hooks/email_spec_validator.py` ist eine Gate-Datei und wird in DIESEM Workflow
**nicht** editiert (Regel: Validator-Änderungen = eigener Workflow; PO-Stopp 2026-07-08).
Der bestehende Validator prüft heute u.a. „Recommendation/Empfehlung" als Pflicht-Sektion
und feste englische Zeilen-Labels — beides widerspricht dem v2-Vertrag strukturell.
Die Umstellung (kein „Recommendation"-Pflicht-Check mehr; Struktur-Check auf
Übersichtstabelle mit Warn-Zeile als erste Datenzeile; Stundentabellen für **alle**
gelisteten Orte; Plausibilität statt String-Presence; Marker-Header
`X-GZ-Mail-Type: compare` bleibt) erfolgt vollständig in **Issue #1108** mit eigener Spec,
eigenen ACs und eigener PO-Freigabe. Der zugehörige RED-Test liegt hier skip-markiert bereit
(`test_ac9_…`, Reason „AC-9 → #1108").

**Deploy-Kopplung (verhindert Gate-Erosion, Risiko 1 der Analyse):** #1110 wird erst
E2E-verifiziert und produktiv deployed, NACHDEM #1108 abgeschlossen ist — beide Commits
werden gepusht und dann in EINER gemeinsamen Staging-E2E geprüft (neuer Validator prüft
neue Mail).

## Expected Behavior

- **Input:** `ComparisonResult` mit ≥1 `LocationResult` (Score-Feld weiterhin befüllt, wird
  von der Mail ignoriert), optionales `ActivityProfile`, optional Preset-Metadaten
  (`name`, `schedule`, `weekday`) für den Abo-Footer.
- **Output:** vollständiger HTML-String (DOCTYPE bis `</html>`) ohne Score/Winner-Referenz,
  mit Übersichtstabelle (Warn-Zeile, Zellfärbung nur Severity), Warn-Lead (falls Warnungen vorhanden),
  Stundentabellen für alle Orte, Legende, Abo-/App-Footer. Parallel dazu ein Klartext-String
  mit äquivalenter Struktur. Pure Functions, keine Seiteneffekte.
- **Side effects:** keine — Versandpfad (`send_one_compare_preset`) bleibt unverändert bis auf
  die zusätzlichen Renderer-Parameter für den Abo-Footer.

## Acceptance Criteria

**AC-1** *(präzisiert per PO-Entscheidung 2026-07-08: alphabetisch statt Preset-Reihenfolge)*:
Given eine zugestellte Ortsvergleich-E-Mail (HTML-Teil) / When ich sie öffne / Then
enthält sie an keiner Stelle einen Score-Wert, eine „Bester Standort"/„Empfehlung"-Box oder
Gewinner-Tags — die Orte erscheinen alphabetisch nach Ortsname sortiert (case-insensitiv),
nicht nach Rang.
  - Test: Echte Staging-Mail (Stalwart, `gregor-test@henemm.com`) rendern lassen, HTML-Body auf
    Abwesenheit von „Score"/„Empfehlung"/„Bester Standort" prüfen und Ort-Reihenfolge auf
    alphabetische Sortierung abgleichen (kein Dateiinhalt-Check am Quellcode, sondern an der
    zugestellten Mail).

**AC-2** *(präzisiert per PO-Entscheidung 2026-07-08: Best-Wert-Markierung entfällt komplett)*:
Given dieselbe Mail / When ich auf die Übersichtstabelle schaue / Then sind die
Metriken als Zeilen und die Orte als Spalten angeordnet, die erste Zeile zeigt „Amtliche
Warnungen" mit einem Kürzel-Chip pro aktiver Warnung je Ort, und KEINE Zelle trägt eine
grüne „günstigster Wert"-Markierung — Zellfärbung ausschließlich über die Risk-Skala.
  - Test: Zugestellte Mail parsen, Kopfzeile = Metrik-Label „Amtliche Warnungen" als erste
    Datenzeile bestätigen, Abwesenheit des Grün-Markers und des Hinweistexts
    „günstigster Wert" im gesamten HTML bestätigen; keinen grün markierten
    Zellwert zählen.

**AC-3:** Given ein Ort ohne jede amtliche Warnung / When ich seine Zelle in der
Warn-Zeile ansehe / Then zeigt sie einen grauen `—`-Platzhalter statt einer leeren Zelle
oder eines Chips.
  - Test: Testfall mit einer Location ohne `official_alerts` gegen die zugestellte Mail
    prüfen — Zelleninhalt exakt `—`.

**AC-4:** Given eine Mail-Instanz ohne jede Warnung über alle Orte hinweg / When ich den
Bereich direkt unter dem Header ansehe / Then fehlt der Warn-Lead-Block vollständig (kein
leerer Rahmen, keine Akzent-Bar ohne Inhalt).
  - Test: Testfall mit `official_alerts=[]` für alle Locations gegen die zugestellte Mail —
    kein Element mit dem Lead-Block-Marker vorhanden.

**AC-5:** Given eine Mail mit mindestens einer amtlichen Warnung / When ich zum
Stundentabellen-Bereich eines betroffenen Ortes scrolle / Then steht direkt über dessen
Stundentabelle ein farbcodierter Langform-Warn-Streifen mit dem vollständigen Warnungstext
(z.B. „Zugang eingeschränkt — {Massiv}"), nicht nur dem Kürzel aus der Übersichtstabelle.
  - Test: Zugestellte Mail prüfen — Langform-Text des betroffenen Ortes erscheint zwischen
    Ort-Kopf und dessen Stundentabelle.

**AC-6:** Given dieselbe Mail / When ich die Stundentabelle eines beliebigen Ortes ansehe /
Then hat sie genau die acht Spalten Zeit/Temp/Gef./Wind/Böen/Regen/Wolken/UV in dieser
Reihenfolge, und Zellen mit kritischen Werten (z.B. Temp ≥34 °C oder Wind >40 km/h) sind
entsprechend der vierstufigen Risk-Skala farbig hinterlegt.
  - Test: Zugestellte Mail parsen, Spaltenüberschriften auf exakte Reihenfolge prüfen; für
    mindestens eine bewusst über der Danger-Schwelle liegende Testlocation die
    Hintergrundfarbe der betroffenen Zelle gegen den erwarteten Danger-Hex-Wert prüfen.

**AC-7:** Given ein Ort ohne verfügbare Gefühlt-Temperatur (`wind_chill_c is None`) / When
ich seine Stundentabelle ansehe / Then zeigt die Spalte „Gef." für diese Stunde `—` statt
eines Fehlers oder einer leeren Zelle.
  - Test: Testfall mit `ForecastDataPoint(wind_chill_c=None, ...)` gegen die zugestellte
    Mail — Zellinhalt exakt `—`.

**AC-8:** Given dieselbe Mail, dargestellt auf einer Viewport-Breite ≤480px (Mobile) bzw.
680px (Desktop) / When ich beide Darstellungen vergleiche / Then greift ein
`@media (max-width: 480px)`-Block, der zwischen den zwei vorbereiteten Markup-Varianten
umschaltet (kein clientseitiges CSS-Grid/Flexbox), und Übersichts- sowie Stundentabellen
sind horizontal scrollbar statt clientseitig neu angeordnet.
  - Test: HTML-Quelltext der zugestellten Mail auf Vorhandensein des `@media (max-width:480px)`-
    Blocks sowie zweier klar unterscheidbarer Markup-Container (Desktop/Mobile) prüfen; kein
    Playwright nötig, da E-Mail-Clients kein natives Resizing zulassen — Struktur-Nachweis
    im HTML genügt für diesen Kanal.

**AC-9:** Given der auf den v2-Vertrag umgestellte Mail-Validator aus Issue #1108 / When
`uv run python3 .claude/hooks/email_spec_validator.py` gegen eine frisch zugestellte
v2-Ortsvergleich-Mail läuft / Then endet der Lauf mit Exit-Code 0 — der Validator prüft den
v2-Vertrag (Übersichtstabelle inkl. Warn-Zeile, Stundentabellen für alle in der Übersicht
gelisteten Orte, KEINE Pflicht-Sektion „Recommendation/Empfehlung" mehr).
  - **Erfüllt durch Issue #1108 (eigener Workflow, PO-Umscoping 2026-07-08):**
    `.claude/hooks/email_spec_validator.py` ist eine Gate-Datei und wird NICHT in diesem
    Feature-Workflow editiert (Regel: Validator-Änderungen = eigener Workflow). Der
    Abschluss von #1108 ist Voraussetzung für die E2E-Verifikation und den Prod-Deploy
    von #1110. Der zugehörige RED-Test (`test_ac9_…`) wird in diesem Workflow mit
    `@pytest.mark.skip(reason="AC-9 → #1108")` übergeben und in #1108 aktiviert.
  - Test (in #1108): Echter Validator-Lauf gegen die Staging-Testmailbox
    (`gregor-test@henemm.com`, `GZ_IMAP_*`), Exit-Code 0 als Beweis.

**AC-10:** Given dieselbe Mail / When ich den Klartext-Teil (Fallback-Ansicht) mit dem
HTML-Teil vergleiche / Then enthält auch der Klartext-Teil keine Score-/🏆-Referenz mehr,
sondern dieselbe strukturelle Gliederung (Übersicht je Ort + amtliche Warnungen je Ort).
  - Test: Zugestellte Mail — `text/plain`-Teil extrahieren, auf Abwesenheit von „Score"/„🏆"
    prüfen und auf Vorhandensein einer Übersichts- sowie Warnungssektion je Ort.

## Known Limitations

- **„Nächster Versand" nicht immer ermittelbar:** Der Abo-Footer zeigt den berechneten
  nächsten Versandtermin nur, wenn `preset["schedule"]`/`preset["weekday"]` beim
  Renderer-Aufruf verfügbar sind. Ist die Berechnung nicht möglich (z.B. unbekannter
  `schedule`-Wert), erscheint `—` statt eines Datums — kein Fehler, kein Absturz.
- **Warn-Kürzel-Fallback:** Für `hazard`-Werte außerhalb der drei bekannten Kategorien
  (`extreme_heat`, `wildfire_risk`, `access_ban`) wird `alert.label` ungekürzt als Chip-Text
  verwendet — kann in der Übersichtstabellen-Zelle umbrechen, ist aber kein Fehlerzustand.
- **Fonts in Mail-Clients:** Die Vorlage nutzt Google-Fonts (`Inter Tight`, `JetBrains Mono`);
  viele Mail-Clients laden externe Web-Fonts nicht. Bestehendes `WEB_FONT_LINK`-Muster +
  Font-Stack-Fallbacks (System-Sans/-Mono) greift wie bisher — keine 1:1-Typografie in jedem
  Client garantiert.
- **Horizont-Stat bleibt statisch `+48h`:** Bestandsverhalten aus dem Vorgänger-Renderer,
  keine Regression durch dieses Issue; echte Horizont-Anzeige (24/48/72h je Preset) wäre
  ein separates Follow-up.
- **Score bleibt im Modell:** `LocationResult.score` wird weiterhin berechnet und in der App
  angezeigt (Web-UI unverändert) — nur die E-Mail-Darstellung verliert Score/Ranking. Eine
  konsistente Streichung auch in der App wäre ein separates Folge-Issue (PO-Entscheidung,
  Scope dieses Issues = nur E-Mail).
- **Konfigurierbarkeit der Übersichts-Metriken:** Die Metrik-Liste (`CV2_METRICS`) ist in
  diesem Issue fix (heutiger Metrik-Stand). Nutzer-seitige Auswahl folgt in #1104–#1107 und
  baut auf diesem Layout auf.
- **UV max ohne Persistenz:** `uv_max` wird bei jedem Renderaufruf aus `hourly_data`
  neu abgeleitet (kein zusätzliches Feld auf `LocationResult`) — bei leeren Stundendaten
  liefert die Übersichtszelle `—`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Presentation-Layer-Rewrite (Renderer + Validator) ohne neue
  Architekturentscheidung. Warn-Darstellung baut auf der bestehenden ADR-0011
  (kanonischer Alert-Renderer, `render_official_alerts_html`) auf und dupliziert sie nicht.

## Changelog

- 2026-07-08: Initial spec erstellt — Issue #1110, superseded `docs/specs/modules/issue_253_compare_email.md`.
- 2026-07-12 (Issue #1214, Scheibe 2): Wind-Severity-Schwelle in Section 2 als überholt markiert — `_sev_wind` nutzt jetzt `severity_for()`/Katalog-Schwellen statt der hier ursprünglich dokumentierten hartcodierten `>40/30/20 km/h`. Sichtbare Folge: Wind 45 km/h zeigt in Compare-Mails jetzt gelb statt rot (Angleichung an Trip-Briefing). Siehe `docs/specs/modules/issue_1214_metric_format_slice1_2.md`.
