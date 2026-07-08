---
entity_id: issue_253_compare_email
type: module
created: 2026-05-20
updated: 2026-07-08
status: superseded
superseded_by: issue_1110_compare_mail_v2.md (2026-07-08)
version: "1.0"
issue: 253
tags: [compare, email, renderer, html, python, heartbeat, scheduler]
---

# Issue #253 — Compare-Email: HTML-Renderer + Versand-Integration

## Approval

- [ ] Approved

## Purpose

Implementiert einen neuen profil-bewussten HTML-E-Mail-Renderer für Compare-Ergebnisse (`render_compare_html`) als Pure Function im Python-Backend, der die bisherige Behelfslösung in `comparison_renderers.py` ablöst. Der Renderer ist Design-System-konform, zeigt einen Winner-Banner, eine metrikgefilterte Vergleichsmatrix und einen Stunden-Verlauf für Top-N Locations — und wird direkt im `compare_subscription.py`-Versandpfad verankert, ergänzt durch einen fail-soft Heartbeat für den Scheduler.

## Source

- **NEU:** `src/output/renderers/email/compare_html.py` — Pure-Function-Renderer, Haupt-Implementierung (~300 LoC)
- **EDIT:** `src/services/compare_subscription.py` — Import umkoppeln, `warnings`-Parameter übergeben (~15 LoC-Delta)
- **EDIT:** `api/routers/scheduler.py` — `_ping_heartbeat_compare()` Helper + `success_count`-Tracking (~20 LoC-Delta)
- **NEU:** `tests/tdd/test_compare_html_email.py` — Unit- + E2E-Tests (~90 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `design_tokens.py` (`src/output/renderers/email/design_tokens.py`) | intern | Farbkonstanten: G_SUCCESS, G_INK, G_PAPER, G_ACCENT, G_WARNING, G_SURFACE_1, FONT_UI — Single Source of Truth für alle Mail-Design-Werte |
| `profile_signature(profile)` (`src/output/renderers/email/profile_signature.py`) | intern | Liefert `ProfileSignature`-Objekt mit `eyebrow`-Text und Profilfarbe für den E-Mail-Header |
| `ComparisonResult` / `LocationResult` / `CompareSubscription` (`src/app/user.py`) | intern | Eingabe-DTOs: `ComparisonResult.winner`, `.valid_locations`, `LocationResult.score`, `.hourly_data`, `.error`, alle Metrikfelder |
| `ActivityProfile` (`src/app/models.py`) | intern | Enum-Werte WINTERSPORT / WANDERN / SUMMER_TREKKING / ALLGEMEIN; steuert CE_PROFILES-Mapping |
| `WeatherMetricsService` (implizit via `hourly_data: List[ForecastDataPoint]`) | intern | Stundenwerte werden aus `LocationResult.hourly_data` entnommen; kein direkter Service-Import, Daten kommen per Parameter |
| `render_comparison_text()` (`src/services/comparison_renderers.py`) | intern | Plain-Text-Renderer bleibt unverändert und wird weiterhin für den Plain-Text-Part der Versand-Mail genutzt |
| `EmailOutput.send(subject, html, plain_text_body)` (`src/outputs/email.py`) | intern | Versandkanal; wird in `compare_subscription.py` mit dem neuen HTML aufgerufen |
| `html.py` (`src/output/renderers/email/html.py`) | intern | Strukturvorlage (334 Zeilen); Pattern für Inline-CSS, `@media`-Block, HourlyCell-Stil — wird nicht importiert, nur als Referenz genutzt |

## Implementation Details

### §1 `src/output/renderers/email/compare_html.py` — Pure-Function-Renderer

**CE_PROFILES Modul-Konstante** (steuert Spaltenauswahl je Profil):

```python
CE_PROFILES: dict[ActivityProfile, dict] = {
    ActivityProfile.WINTERSPORT: {
        "primary":   ["snow_depth_cm", "snow_new_cm", "sunny_hours"],
        "secondary": ["wind_max", "cloud_avg", "score"],
    },
    ActivityProfile.WANDERN: {
        "primary":   ["sunny_hours", "wind_max", "cloud_avg"],
        "secondary": ["snow_depth_cm", "temp_max", "score"],
    },
    ActivityProfile.SUMMER_TREKKING: {
        "primary":   ["sunny_hours", "cloud_avg", "wind_max"],
        "secondary": ["gust_max", "temp_max", "score"],
    },
    ActivityProfile.ALLGEMEIN: {
        "primary":   ["score", "sunny_hours", "wind_max"],
        "secondary": ["snow_depth_cm", "cloud_avg", "temp_max"],
    },
}
```

**Öffentliche Signatur:**

```python
def render_compare_html(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] = [],
    top_n_details: int = 3,
    enabled_metrics: set | None = None,
) -> str:
```

**Aufbau des HTML-Dokuments (Inline-CSS-Only, kein externes Stylesheet):**

1. **DOCTYPE + Head:** `charset=UTF-8`, `viewport=width=device-width,initial-scale=1`, kein externer Link
2. **`@media (max-width: 480px)`-Block** im `<style>`-Tag: Matrix kippt zu Karten-Layout (je Location ein `<div>` statt Tabellenzeile), Schriftgröße reduziert, `secondary`-Spalten ausgeblendet (`display:none`)
3. **Profil-Eyebrow:** `profile_signature(profile).eyebrow` als schmaler Subheader-Banner (Hintergrundfarbe `G_SURFACE_1`)
4. **Winner-Card:**
   - `border-left: 4px solid G_SUCCESS`
   - Location-Name als `<h2>`, Score als Badge (`background: G_SUCCESS`, weiße Schrift)
   - Tags als Pill-Liste (aus `ComparisonResult.winner.tags` falls vorhanden, sonst leer)
   - Nur wenn `result.winner` nicht `None` ist
5. **Warnungen:** Wenn `warnings` nicht leer, einen orangefarbenen Banner-Block (`G_WARNING` Hintergrund) pro Eintrag — kein String-Replace auf dem fertigen HTML
6. **Vergleichs-Matrix:**
   - `<table>`-basiert, `width=640px`, `max-width=100%`
   - Kopfzeile: Location-Namen
   - Zeilen: eine pro Metrik aus `CE_PROFILES[profile]["primary"] + CE_PROFILES[profile]["secondary"]`
   - `secondary`-Spalten haben CSS-Klasse `secondary-col`; im `@media`-Block `display:none`
   - Best-Value-Zelle (Maximum bei positiven Metriken, Minimum bei negativen) erhält `background: G_SUCCESS` mit 30% Opacity
   - Wenn `enabled_metrics` gesetzt: nur Zeilen für Metriken in `enabled_metrics` rendern
   - Fehlerhafte Locations (`LocationResult.error` nicht None): Zellen zeigen `—`, Score-Badge in `G_WARNING`
7. **Stunden-Verlauf:** Top-`top_n_details` Locations (nach Score, nur `valid_locations`)
   - Pro Location eine kompakte Tabelle mit Uhrzeit + Icon-Zellen (Temperatur, Wind, Wolken) analog zu HourlyCell-Pattern in `html.py`
   - Daten aus `LocationResult.hourly_data` (Liste von `ForecastDataPoint`)
   - Wenn `hourly_data` leer: Abschnitt wird für diese Location ausgelassen
8. **Footer:** `background: G_INK (#1a1a18)`, weiße Schrift, Datums-Angabe aus `result.target_date`

**Best-Value-Logik:**

```python
METRIC_DIRECTION = {
    "score":        "max",
    "sunny_hours":  "max",
    "snow_depth_cm":"max",
    "snow_new_cm":  "max",
    "temp_max":     "max",
    "wind_max":     "min",   # weniger Wind = besser
    "gust_max":     "min",
    "cloud_avg":    "min",
}
```

### §2 `src/services/compare_subscription.py` — Umkopplung

- Import-Zeile ersetzen: `from src.output.renderers.email.compare_html import render_compare_html`
- `comparison_renderers.render_comparison_html(...)` → `render_compare_html(result, profile=sub.profile, warnings=collected_warnings)`
- `collected_warnings: list[str]` wird aus bisheriger Logik befüllt (keine inhaltliche Änderung)
- `render_comparison_text()` aus `comparison_renderers` bleibt als Plain-Text-Part unverändert importiert

### §3 `api/routers/scheduler.py` — Heartbeat

```python
def _ping_heartbeat_compare() -> None:
    """Fail-soft: sendet Heartbeat-Ping wenn GZ_HEARTBEAT_COMPARE gesetzt."""
    url = os.getenv("GZ_HEARTBEAT_COMPARE", "")
    if not url:
        logger.debug("GZ_HEARTBEAT_COMPARE nicht gesetzt — kein Heartbeat-Ping")
        return
    try:
        httpx.get(url, timeout=5)
    except Exception as e:
        logger.warning("Heartbeat-Ping fehlgeschlagen: %s", e)
```

In `_run_subscriptions_by_schedule()`:
- `success_count = 0` vor der Schleife initialisieren
- Nach jedem erfolgreichen Versand: `success_count += 1`
- Nach der Schleife: `if success_count > 0: _ping_heartbeat_compare()`
- Bei SMTP-Fehler: kein Inkrement, kein Ping

### §4 `tests/tdd/test_compare_html_email.py`

**Test 1 — `TestCompareHTMLRenderer` (kein SMTP, schnell):**
- Erstellt minimales `ComparisonResult` mit 2 `LocationResult`-Fixtures (einer mit Score 80, einer mit Score 55)
- Ruft `render_compare_html(result, profile=ActivityProfile.WINTERSPORT)` auf
- Assertions: HTML enthält `<!DOCTYPE`, `@media`, Winner-Locationname, `G_SUCCESS`-Farbwert (`#3a7d44`), Spaltenheader für `snow_depth_cm` und `snow_new_cm`

**Test 2 — `TestCompareEmailE2E` (`@pytest.mark.email`):**
- Analog zu `TestRealStalwartE2E` in bestehenden Tests
- Echter SMTP-Send via `EmailOutput.send()` an `gregor-test@henemm.com`
- IMAP-Verifikation: Mail abrufbar, Subject enthält "Compare", HTML-Body enthält Winner-Locationname
- Kein Mock, keine Patches

### §5 LoC-Schätzung

| Datei | Inhalt | LoC |
|-------|--------|-----|
| `src/output/renderers/email/compare_html.py` | Renderer, CE_PROFILES, METRIC_DIRECTION, Helper | ~300 |
| `src/services/compare_subscription.py` | Import-Umkopplung, warnings-Parameter | ~15 |
| `api/routers/scheduler.py` | Heartbeat-Helper + success_count | ~20 |
| `tests/tdd/test_compare_html_email.py` | Unit + E2E Tests | ~90 |
| **Summe** | | **~425 LoC** |

LoC-Limit-Override vor Implementierungsstart setzen: `workflow.py set-field loc_limit_override 450`

## Expected Behavior

- **Input:** `ComparisonResult` mit mindestens einer gültigen `LocationResult`, optionales `ActivityProfile`, optionale `warnings`-Liste
- **Output:** Vollständiger HTML-String (DOCTYPE bis `</html>`) mit Inline-CSS, `@media`-Block, Winner-Card, Vergleichsmatrix und Stunden-Verlauf. Kein Side-Effect (Pure Function).
- **Side effects (Scheduler-Integration):**
  - `compare_subscription.py` sendet die generierte HTML-Mail via `EmailOutput.send()`
  - `scheduler.py` pingt `GZ_HEARTBEAT_COMPARE` ausschließlich wenn mindestens ein Versand in der Schleife erfolgreich war
  - Kein Heartbeat-Ping bei leerem `GZ_HEARTBEAT_COMPARE` (fail-soft, nur DEBUG-Log)
  - `last_run`-Status in `/api/scheduler/status` reflektiert Erfolg oder Fehler des Versands

## Acceptance Criteria

**AC-1:** Given ein `ComparisonResult` mit zwei Locations und `profile=WINTERSPORT` / When `render_compare_html()` aufgerufen wird / Then enthält das zurückgegebene HTML den Winner-Locationnamen, den `G_SUCCESS`-Farbwert (`#3a7d44`) im Winner-Banner und Spaltenheader für `snow_depth_cm` sowie `snow_new_cm` (aus dem CE_PROFILES-Mapping für WINTERSPORT).
  - Test: `TestCompareHTMLRenderer::test_ac1_wintersport_profile_zeigt_schnee_spalten`

**AC-2:** Given das generierte HTML / When es auf einer Viewport-Breite ≤ 480px dargestellt wird / Then greift der `@media (max-width: 480px)`-Block: `secondary-col`-Spalten sind `display:none`, jede Location wird als eigenständige Karte (Block-Element) dargestellt statt als Tabellenzeile.
  - Test: `TestCompareHTMLRenderer::test_ac2_media_query_fuer_mobile_vorhanden`

**AC-3:** Given ein erfolgreicher Compare-Versandlauf mit `success_count >= 1` / When `/api/scheduler/status` abgefragt wird / Then zeigt der zugehörige Job `last_run: ok` und der Heartbeat-Ping wurde an `GZ_HEARTBEAT_COMPARE` gesendet.
  - Test: `TestCompareEmailE2E::test_ac8_echter_versand_imap_verifikation` (implizit via Scheduler-Run)

**AC-4:** Given ein SMTP-Fehler beim Compare-Versand / When der Scheduler-Lauf endet / Then ist `success_count` gleich 0, es wird kein Heartbeat-Ping gesendet, und `/api/scheduler/status` zeigt `last_run: error` für den Job.
  - Test: `TestHeartbeatIntegration::test_ac4_kein_ping_bei_keinen_subscriptions`

**AC-5:** Given `warnings=["Lückenhafter Forecast für Location X"]` als Parameter / When `render_compare_html()` aufgerufen wird / Then enthält das HTML einen orangefarbenen Warnungs-Banner mit dem übergebenen Text — kein String-Replace auf dem fertigen HTML-String ist involviert.
  - Test: `TestCompareHTMLRenderer::test_ac5_warnings_parameter_kein_string_replace`

**AC-6:** Given eine Location mit `error` gesetzt (z.B. Provider-Timeout) / When der Renderer die Vergleichsmatrix aufbaut / Then zeigt die Spalte dieser Location in allen Metrik-Zeilen `—` und der Score-Badge verwendet die Warnfarbe `G_WARNING` statt `G_SUCCESS`.
  - Test: `TestCompareHTMLRenderer::test_ac6_fehlerhafte_location_zeigt_strich`

**AC-7:** Given `GZ_HEARTBEAT_COMPARE` ist nicht als Umgebungsvariable gesetzt / When der Scheduler-Lauf erfolgreich endet / Then wirft der Scheduler keine Exception und schreibt einen DEBUG-Log-Eintrag — kein Absturz, kein Error-Log.
  - Test: `TestHeartbeatIntegration::test_ac7_kein_heartbeat_ohne_env_var`

**AC-8:** Given die generierte Compare-Mail / When sie über echten SMTP an `gregor-test@henemm.com` gesendet und via IMAP abgerufen wird / Then ist die Mail im Postfach auffindbar, der Subject enthält "Compare" und der HTML-Body enthält den Winner-Locationnamen (echter Send, kein Mock).
  - Test: `TestCompareEmailE2E::test_ac8_echter_versand_imap_verifikation` (`@pytest.mark.email`)

## Known Limitations

- **Plain-Text bleibt `comparison_renderers.py`:** `render_comparison_text()` wird nicht in `compare_html.py` zusammengeführt. Bei zukünftigen Anpassungen am Plain-Text-Format muss `comparison_renderers.py` separat angefasst werden.
- **Tags aus `LocationResult`:** Der Winner-Banner zeigt Tags nur wenn `ComparisonResult.winner` (via `LocationResult`) ein `tags`-Feld befüllt hat. Liegt kein `tags`-Attribut vor, bleibt die Pill-Liste leer — kein Fehler.
- **Stunden-Verlauf ohne WeatherMetricsService-Import:** Die Stundenwerte kommen direkt aus `LocationResult.hourly_data`. Sollte WeatherMetricsService in Zukunft Aggregationen berechnen, die nicht in `ForecastDataPoint` stehen, muss der Renderer erweitert werden.
- **`enabled_metrics`-Parameter ohne UI-Anbindung:** Das optionale `enabled_metrics`-Set ist als Erweiterungspunkt für den Metriken-Editor (Epic #138) vorgesehen; im MVP-Scope von Issue #253 wird es nicht von `compare_subscription.py` befüllt.
- **Cache-Invalidierung:** Der Renderer selbst ist zustandslos. Veraltete Compare-Ergebnisse (> 15 Min) können durch den Cache der Compare-Engine (Issue #250) durchgereicht werden — das betrifft die Datenlage, nicht den Renderer.

## Changelog

- 2026-05-20: Initial spec — Issue #253. Neuer HTML-Renderer `compare_html.py` als Pure Function, Umkopplung in `compare_subscription.py`, fail-soft Heartbeat in `scheduler.py`, Unit + E2E Tests ohne Mocks. ~425 LoC, LoC-Override auf 450 erforderlich.
- 2026-07-08: **Superseded** durch `docs/specs/modules/issue_1110_compare_mail_v2.md` (Issue #1110). Der hier spezifizierte Score/Winner-basierte Renderer wurde vollständig durch das v2-Layout (Übersichtstabelle Metriken×Orte ohne Score/Winner, Stundentabellen für alle Orte) abgelöst. Inhalt dieser Spec unverändert als historische Referenz belassen.
