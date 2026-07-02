---
entity_id: fix_888_896_902_mail_bundle
type: module
created: 2026-07-02
updated: 2026-07-02
status: draft
version: "1.1"
tags: [briefing-mail, renderer, day-comparison, outlook, bugfix-bundle]
---

# Fix-Bundle: Ampel/Tönung-Widerspruch, Vortags-Salienz, Outlook-Spaltenlinien (#888, #896, #902)

## Approval

- [x] Approved (PO 'go', 2026-07-02)

## Purpose

Drei unabhängige Adversary-Nebenbefunde im Briefing-Mail-Renderer werden gebündelt behoben:
(#888) eine Tabellenzelle kann gleichzeitig ein grünes Ampel-Emoji und einen gelben/orangen
Warn-Hintergrund zeigen (zwei entkoppelte Schwellenquellen widersprechen sich sichtbar);
(#896) die Vortags-Vergleichszeile nennt Vorboten-Metriken (Luftfeuchte, Bewölkung, Luftdruck,
gefühlte Temperatur, Taupunkt) zu häufig, weil ihre Anzeige-Salienz seit #889/ADR-0010 auf
einen zu niedrigen Fallback-Wert fällt; (#902) Outlook-Desktop entfernt den `<style>`-Block der
Mail und damit die senkrechten Spaltenlinien der Datenzellen, weil diese absichtlich ohne
Inline-Border gerendert werden (Test-Regex-Kontrakt aus #900/#911).

## Source

- **File:** `src/output/renderers/email/html.py` (`_render_html_table`, Zeilen 455-580; `<style>`-Block, Zeilen 1425-1453)
- **File:** `src/services/day_comparison.py` (`_get_threshold`, `_SALIENCE_FACTOR`, Zeilen 229-245)
- **Identifier:** `_render_html_table`, `_get_threshold`, `_summarize_metric_driven`

> **Schicht:** Reiner Python-Backend-Pfad (`src/output/renderers/email/`, `src/services/`) —
> FastAPI-Core über `render_email` / Briefing-Scheduler. Kein Frontend-, kein Go-API-Code
> betroffen.

## Estimated Scope

- **LoC:** ~85 (geschätzt: #888 ~25, #896 ~20, #902 ~15 Renderer + ~10 Testdatei-Regex-Fixes + neue Tests ~40-60)
- **Files:** 5 bestehende (2 Source, 3 Test) + 1-3 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/helpers.py::ampel_dot` | Upstream | Liefert Ampel-Emoji aus Katalog-`display_thresholds` — seine Level-Ermittlung wird als wiederverwendbare Funktion extrahiert und ist die einzige Schwellenquelle für Ampel-Zellen (#888) |
| `src/output/renderers/email/helpers.py::fmt_val` (`_use_ampel`-Dispatch) | Upstream | Bestimmt, ob eine Zelle ein Ampel-Emoji trägt (`indicator_keys`) — wird von `_render_html_table` konsultiert, um cell_bg aus dem Ampel-Level abzuleiten statt aus den hartcodierten Schwellen |
| `src/app/metric_catalog.py::get_metric` | Upstream | `default_change_threshold` (teils `None` seit ADR-0010) — Basis des #896-Fallbacks |
| `tests/tdd/test_issue_759_email_ampel.py:294` | Downstream | Strikter `data-label`-Regex — muss #902-Inline-Styles zulassen |
| `tests/tdd/test_issue_811_mode_matrix.py:144,574` | Downstream | Gleicher Regex, zusätzlich Pflicht-Nachweis für `renderer_mail_gate.py` (Commit-Gate) |
| `docs/adr/0010-vorboten-metriken-kein-alert-ausloeser.md` | Konzeptuell | Begründet, warum `default_change_threshold=None` für Vorboten-Metriken korrekt ist — #896 entkoppelt nur die *Anzeige*-Salienz, ändert ADR-0010-Verhalten nicht |

## Implementation Details

### #888 — Zell-Tönung folgt dem Ampel-Level (PO-Entscheidung 2026-07-02: beide Signale bleiben)

In `_render_html_table` (`html.py:531-564`) wird `cell_bg` aktuell aus **eigenen hartcodierten
Schwellen** (`_WIND_THRESHOLD=20.0` etc., `html.py:496-501`) bestimmt — unabhängig vom
Ampel-Emoji, das aus den **Katalog-`display_thresholds`** kommt (wind: yellow=30/orange=50/
red=70). Bei Wind=25 entsteht so 🟢 auf gelbem Hintergrund.

**Fix:** Ampel-Emoji UND Hintergrund-Tönung bleiben beide erhalten, beziehen aber dieselbe
Schwellenquelle: Für Ampel-Zellen (`key in indicator_keys`) wird `cell_bg` aus dem
**Ampel-Level** abgeleitet statt aus den hartcodierten Schwellen:

| Ampel-Level | Emoji | cell_bg |
|-------------|-------|---------|
| green | 🟢 | keine Tönung |
| yellow | 🟡 | `#fbeeb8` |
| orange | 🟠 | `#fad6b8` |
| red | 🔴 | `#f6c5bf` |

Dazu wird die Level-Ermittlung aus `ampel_dot` (`helpers.py:371-394`) als wiederverwendbare
Funktion extrahiert (z. B. `ampel_level(metric_id, value) -> Optional[str]`, Rückgabe
`"green"|"yellow"|"orange"|"red"`); `ampel_dot` nutzt sie intern weiter (Emoji-Stufen ändern
sich nicht). `_render_html_table` mappt dabei col_key → Katalog-metric_id (`wind`→`wind`,
`gust`→`gust`, `precip`→`precipitation`, `pop`→`rain_probability`, `cape`→`cape` — analog zum
bestehenden Mapping in `build_html_indicator_keys`, `helpers.py:814-834`).

Nicht-Ampel-Zellen (Roh-Modus, oder Metriken ohne Ampel-Fähigkeit wie `thunder`/`vis`) behalten
die bestehende hartcodierte Tönungslogik unverändert (`_WIND_THRESHOLD` etc. bleiben für diese
Fälle bestehen — kein Umbau).

```python
# nachher (Prinzip):
_is_ampel_cell = key in (indicator_keys or set())
if _is_ampel_cell:
    level = ampel_level(_col_key_to_metric_id(key), numeric)   # Katalog-Schwellen
    cell_bg = {"yellow": "#fbeeb8", "orange": "#fad6b8", "red": "#f6c5bf"}.get(level)
else:
    # bestehende hartcodierte Logik unverändert (Roh-Modus / Nicht-Ampel-Metriken)
    ...
```

`indicator_keys` ist bereits Parameter von `_render_html_table` (Zeile 461) und wird 1:1 an
`fmt_val` durchgereicht (Zeile 527) — dieselbe Quelle entscheidet also sowohl über das
Ampel-Rendering in `fmt_val` als auch über die Level-basierte Tönung. Emoji und Hintergrund
können sich damit strukturell nie mehr widersprechen.

### #896 — Vortags-Salienz von `default_change_threshold` entkoppeln

`_get_threshold` (`day_comparison.py:232-245`) bekommt eine modulinterne Konstante mit den
effektiven Werten von vor #889 für Metriken, deren `default_change_threshold` seit ADR-0010
`None` ist:

```python
# day_comparison.py, vor _get_threshold:
# Issue #896: Anzeige-Salienz für die Vortags-Zeile, entkoppelt vom Alert-Katalog
# (metric_catalog.default_change_threshold). Seit #889/ADR-0010 ist der Katalog-Wert für
# Vorboten-Metriken None (kein Alert-Trigger) — das ist korrekt für Alerts, aber ungeeignet
# als Anzeige-Schwelle: der _get_threshold-Fallback (3.0) macht die Vortags-Zeile für
# %-Metriken (humidity, cloud_total) zu geschwätzig. Werte = effektiver Stand vor #889.
_DISPLAY_SALIENCE_OVERRIDES: dict[str, float] = {
    "humidity": 12.0,
    "rain_probability": 12.0,
    "cloud_total": 18.0,
    "pressure": 6.0,
    "wind_chill": 3.0,
    "dewpoint": 3.0,
}


def _get_threshold(metric_id: str) -> float:
    if metric_id in _DISPLAY_SALIENCE_OVERRIDES:
        return _DISPLAY_SALIENCE_OVERRIDES[metric_id]
    try:
        from app.metric_catalog import get_metric
        m = get_metric(metric_id)
        if m.default_change_threshold is not None:
            return float(m.default_change_threshold) * _SALIENCE_FACTOR
    except Exception:
        pass
    return 3.0
```

Metriken mit gesetztem `default_change_threshold` (z. B. `wind` = 20.0, `precipitation` = 10.0)
sind NICHT in der Override-Tabelle — für sie bleibt `default_change_threshold * 0.6` unverändert
wirksam (Negativ-AC). `metric_catalog.default_change_threshold` selbst wird nicht angefasst
(ADR-0010-Verhalten für Alerts bleibt exakt bestehen).

### #902 — Inline-Borders auf Datenzellen (Outlook-fest) + Regex-Verallgemeinerung

`_render_html_table` (`html.py:565`) rendert Datenzellen aktuell ohne Inline-Style:
`tds += f'<td data-label="{label}">{cell}</td>'`. Fix: identisches Inline-Border-Paar wie
`_td_grid` (Zeile 510, bereits für die Time-Zelle genutzt, Zeile 519) ergänzen:

```python
tds += f'<td style="{_td_grid}" data-label="{label}">{cell}</td>'
```

Das entfernt keine bestehende `<style>`-Block-Regel (Zeilen 1442-1448 bleiben als Fallback für
Clients, die `<style>` respektieren) — es ergänzt nur die von Outlook gestrippte Inline-Ebene.

Die drei blockierenden Test-Regexes werden von `<td data-label="[^"]*">(.*?)</td>` auf
`<td[^>]*data-label="[^"]*"[^>]*>(.*?)</td>` verallgemeinert (matcht sowohl mit als auch ohne
zusätzliche Attribute vor/nach `data-label`):

- `tests/tdd/test_issue_759_email_ampel.py:294` (`_data_cells_759`)
- `tests/tdd/test_issue_811_mode_matrix.py:144` (`_data_cells`)
- `tests/tdd/test_issue_811_mode_matrix.py:574` (`_data_cells_mobile`)

Hook-Validatoren (`briefing_mail_validator.py:127`, `email_spec_validator.py:128`) nutzen
bereits den toleranten Regex `<td[^>]*>` — keine Änderung dort nötig, kein Bruchrisiko am
Renderer-Commit-Gate-Nachweis (`test_issue_811_mode_matrix.py` bleibt Pflicht-Grün-Lauf).

## Expected Behavior

- **Input:** Segment-Stundenzeilen mit Wind=25.0 / 35.0 / 55.0 / 75.0 km/h, Einfach-Modus (Ampel aktiv über `indicator_keys={"wind"}`; Katalog-Schwellen yellow=30/orange=50/red=70).
- **Output (#888):** Wind-Zellen zeigen `🟢` OHNE Tönung, `🟡` MIT `background:#fbeeb8`, `🟠` MIT `background:#fad6b8`, `🔴` MIT `background:#f6c5bf` — Tönung folgt exakt dem Ampel-Level.
- **Input:** Gleiche Zeile, `format_modes={"wind":"raw"}`, `indicator_keys=set()` (Roh-Modus).
- **Output (#888, Negativ):** Zelle zeigt Zahl `25` MIT `background:#fbeeb8`-Span (Tönung unverändert aktiv, da kein Ampel-Indikator greift).
- **Input:** Zwei aufeinanderfolgende Tage mit Luftfeuchte-Differenz Ø 8 Prozentpunkte, sonst neutral.
- **Output (#896):** Vortags-Zeile nennt Luftfeuchte NICHT (8 < 12), vorher (Fallback 3.0) hätte sie es genannt.
- **Input:** Gleiche Konstellation, Wind-Differenz Ø 15 km/h (< 20*0.6=12 → tatsächlich salient, da 15>12).
- **Output (#896, Negativ):** Wind-Vergleich unverändert nach bisheriger Formel (`default_change_threshold*0.6`), da `wind` keinen Override hat.
- **Input:** Beliebige gerenderte Stundentabelle, geöffnet in Outlook Desktop (kein `<style>`-Support).
- **Output (#902):** Jede Datenzelle zeigt rechte/untere Rahmenlinie (`#f0ece1`) via Inline-Style, identisch zur bereits Outlook-festen Time-Zelle.
- **Side effects:** Keine Änderung an Spalten-Labels, Header-Rendering, Ampel-Stufen-Logik (`ampel_dot`), Alert-Auslösung (`from_display_config`/`from_alert_rules` bleiben auf `metric_catalog.default_change_threshold` basiert) oder Plain-Text-Renderer (`plain.py`).

## Acceptance Criteria

- **AC-1:** Given Stundenzeilen mit Wind=25.0/35.0/55.0/75.0 km/h im Einfach-Modus (`indicator_keys={"wind"}`, Katalog-Schwellen yellow=30/orange=50/red=70), When die HTML-Tabelle gerendert wird, Then zeigen die Wind-Zellen `🟢` OHNE Tönung, `🟡` MIT `background:#fbeeb8`, `🟠` MIT `background:#fad6b8` und `🔴` MIT `background:#f6c5bf` — Emoji und Hintergrund stammen aus derselben Katalog-Schwellenquelle und widersprechen sich nie.
  - Test: `_render_html_table` bzw. `render_email` mit echten Segmentdaten (Wind=25.0/35.0/55.0/75.0, Einfach-Modus) aufrufen, für jede Wind-Zelle das Emoji-Level und die exakt dazu passende (bzw. bei 🟢 fehlende) `background`-Deklaration prüfen.

- **AC-2 (Negativ):** Given eine Stundenzeile mit Wind=25.0 km/h im Roh-Modus (`format_modes={"wind":"raw"}`, kein Ampel-Indikator), When die HTML-Tabelle gerendert wird, Then behält die Wind-Zelle die bestehende Warn-Tönung (`background:#fbeeb8`) — Roh-Modus-Verhalten bleibt exakt wie vor dem Fix.
  - Test: Gleicher Aufruf mit `format_modes={"wind":"raw"}`, prüft dass `background:#fbeeb8` weiterhin in der Zelle steht.

- **AC-3:** Given zwei Vergleichstage mit einer durchschnittlichen Luftfeuchte-Differenz von 8 Prozentpunkten (unter dem neuen 12.0-Schwellenwert) und sonst neutralen Werten, When der Vortags-Vergleichstext erzeugt wird (`_summarize_metric_driven`), Then erwähnt der Text Luftfeuchte NICHT.
  - Test: `_summarize_metric_driven` bzw. `day_comparison`-Pfad direkt mit echten `DayComparison`-Objekten (humidity-Delta=8.0, alle anderen Metriken neutral) aufrufen, geprüft wird, dass "feucht" NICHT im Ergebnisstring vorkommt.

- **AC-4 (Negativ):** Given eine Wind-Differenz von 15 km/h zwischen zwei Vergleichstagen (über der unveränderten `20.0*0.6=12.0`-Schwelle aus `metric_catalog`), When der Vortags-Vergleichstext erzeugt wird, Then erwähnt der Text Wind (Verhalten für Metriken mit gesetztem `default_change_threshold` bleibt unverändert von diesem Fix).
  - Test: Gleicher Aufruf mit wind-Delta=15.0, prüft dass "windiger"/"ruhiger" im Ergebnisstring vorkommt.

- **AC-5:** Given eine gerenderte HTML-Stundentabelle, When der Quelltext einer beliebigen Datenzelle (`<td data-label="...">`) inspiziert wird, Then trägt sie ein Inline-`style`-Attribut mit `border-right:1px solid #f0ece1;border-bottom:1px solid #f0ece1;` — identisch zur Time-Zelle, unabhängig davon ob der E-Mail-Client den `<style>`-Block respektiert.
  - Test: `render_email` mit echten Segmentdaten aufrufen, resultierenden HTML-String parsen, für jede `<td data-label=...>`-Zelle das `style`-Attribut auf die Border-Deklaration prüfen.

- **AC-6:** Given die drei bestehenden Test-Regexes (`test_issue_759_email_ampel.py:294`, `test_issue_811_mode_matrix.py:144`, `:574`), When sie nach der #902-Anpassung auf den (nun mit Inline-Style versehenen) HTML-Output angewendet werden, Then extrahieren sie weiterhin exakt dieselbe Zellinhalts-Liste wie vor dem Fix (keine Regression der Ampel-Modus-Matrix-Tests).
  - Test: Bestehende Testsuiten `test_issue_759_email_ampel.py` und `test_issue_811_mode_matrix.py` vollständig grün (echte `render_email`-Aufrufe, keine Mocks).

- **AC-7:** Given eine Metrik ohne Ampel-Fähigkeit (z. B. `thunder`, `vis`/`visibility`), When die HTML-Tabelle mit Warn-relevanten Werten gerendert wird, Then bleibt deren bestehende Zell-Tönungslogik unverändert (kein Einfluss der #888-Änderung auf Nicht-Ampel-Metriken).
  - Test: `_render_html_table` mit Sichtweite < 500m aufrufen, prüft weiterhin `background:#f6c5bf` in der Sicht-Zelle.

## Known Limitations

- #902s Nutzen ist bewusst klein (Zielgruppe liest primär mobil, wo `<style>` meist funktioniert) — der Fix behebt nur den Outlook-Desktop-Randfall, kein grundsätzlicher Rendering-Umbau.
- Die #896-Salienz-Tabelle ist eine bewusste Übergangslösung (Werte = Stand vor #889); eine dauerhafte, im Katalog modellierte Trennung zwischen "Alert-Schwelle" und "Anzeige-Salienz" wäre ein größerer Umbau (`MetricDefinition` bräuchte ein zweites Feld) und ist nicht Teil dieses Bundles.
- `_get_threshold` war vor diesem Fix ungetestet (kein bestehender Test ruft die Funktion direkt auf) — dieses Bundle liefert die erste direkte Testabdeckung.

## Invarianten (dürfen sich NICHT ändern)

- Spalten-Labels/Kürzel (`Wind`, `Gust`, `Rain`, `Rain%`, `Cloud`, `hPa`, etc.) bleiben unverändert (PO-Regel: keine Spalten-Label-Änderungen, Issue #884-Feedback).
- Time-Zellen-Rendering (`html.py:519`) bleibt unverändert.
- Ampel-Emoji-Stufen und deren Herkunft (`ampel_dot`, `helpers.py:371-394`, Katalog-`display_thresholds`) bleiben exakt wie bisher — die begleitende Tönung wird bei Ampel-Zellen künftig aus demselben Level abgeleitet; das Emoji selbst und seine Schwellen ändern sich nicht.
- `metric_catalog.default_change_threshold` bleibt für ALLE Metriken unverändert (insbesondere weiterhin `None` für humidity/cloud_total/pressure/wind_chill/dewpoint) — Alert-Auslösung (`from_display_config`, `from_alert_rules`, ADR-0010-Verhalten) ist von diesem Fix nicht betroffen, da nur die modulinterne `_get_threshold`-Anzeigelogik in `day_comparison.py` geändert wird.
- Hook-Validator-Kompatibilität (`briefing_mail_validator.py`, `email_spec_validator.py`) bleibt gewahrt — beide nutzen bereits tolerante `<td[^>]*>`-Regexes, keine Anpassung nötig.
- Plain-Text-Renderer (`plain.py`) ist von #888/#902 nicht betroffen (reine HTML-Belange); der #896-Vergleichstext (`_summarize_metric_driven`) wird sowohl in HTML- als auch Plain-Mail verwendet (`html.py:1272-1276`, `plain.py:129-130`) — beide Pfade profitieren gleichermaßen vom selben Fix, kein separater Code nötig.
- Renderer-Commit-Gate (`renderer_mail_gate.py`, Issue #811) bleibt scharf: Modus-Matrix-Vertragstest UND `briefing_mail_validator.py`-Lauf gegen Staging-Mail müssen im selben Commit/Workflow frisch grün sein.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; referenziert ADR-0010 (`docs/adr/0010-vorboten-metriken-kein-alert-ausloeser.md`)
- **Rationale:** #896 entkoppelt bewusst nur die *Anzeige*-Salienz der Vortags-Zeile von der
  *Alert*-Schwelle im Metrik-Katalog. Das folgt der Absicht von ADR-0010 (Vorboten-Metriken
  lösen keinen Alert aus), erweitert sie aber nicht — die Katalog-Werte (`default_change_threshold
  =None`) bleiben für Alerts unangetastet. Da dies eine lokale, modulinterne Zusatztabelle ohne
  Architektur-Auswirkung ist (kein neues Datenmodell, keine neue Schnittstelle), ist keine neue
  ADR nötig. #888 und #902 sind reine Bugfixes innerhalb bestehender Renderer-Konventionen
  (Ampel als Single-Source-Signal, Outlook-Inline-Style-Pattern) ohne Architektur-Entscheidung.

## Changelog

- 2026-07-02: Initial spec created (Bundle #888 + #896 + #902)
- 2026-07-02: v1.1 — PO-Feedback: #888 behält BEIDE Signale (Ampel + Hintergrund); Tönung wird aus dem Ampel-Level (Katalog-Schwellen) abgeleitet statt unterdrückt. AC-1, Implementation Details, Expected Behavior entsprechend geändert.
