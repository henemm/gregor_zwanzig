# Context: Issue #253 — Compare-Email Renderer + Versand-Integration

## Request Summary

Einen neuen, design-system-konformen HTML-Renderer für Compare-Emails bauen
(`src/output/renderers/email/compare_html.py`) und in den bestehenden Versand-Flow
integrieren, sodass Auto-Briefings eine fertig gestaltete Compare-Mail versenden.

## Abhängigkeiten

- **EPIC 2 (#246):** Orts-Vergleich-Hauptbühne (übergeordnet)
- **Epic #236 Sub-Issue 9:** Compare-Email-Template-Design — EPIC 9 ist **CLOSED**;
  die Design-Vorgaben sind in der Issue-Beschreibung und in Epic #236 vollständig
  beschrieben. Die Referenz-Datei `screen-compare-email.jsx` ist kein Repo-File,
  sondern ein Design-Bundle-Artefakt — Layout-Details stehen direkt im Issue-Text.
- **Auto-Briefings (Sub-Issue 6):** ruft den Versand-Service auf (muss nach #253 verknüpft werden)

## Ist-Zustand — was bereits existiert

### Existierender (alter) Renderer
`src/services/comparison_renderers.py` — `render_comparison_html()` und `render_comparison_text()`
- Funktional, aber hardkodierte Farben/Styles (nicht aus design_tokens.py)
- Kein Mobile-@media-Layout
- Kein CE_PROFILES (profil-spezifische Spalten)
- Nicht im `output/renderers/email/`-Paket (falsche Codestelle)

### Orchestrierung
`src/services/compare_subscription.py` — `run_comparison_for_subscription()`
- Ruft `ComparisonEngine.run()` auf
- Ruft alten Renderer auf (`render_comparison_html`, `render_comparison_text`)
- Sendet via `EmailOutput` (SMTP)
- **Muss auf neuen Renderer umgekoppelt werden**

### Scheduler
`api/routers/scheduler.py` → `_run_subscriptions_by_schedule()`
- Ruft `run_comparison_for_subscription()` auf
- Looping über `CompareSubscription`-Objekte
- Heartbeat fehlt noch

### Engine
`src/services/comparison_engine.py` — `ComparisonEngine.run()`
- Liefert `ComparisonResult` (sortierte `LocationResult`-Liste, Winner, Stunden-Daten)
- Ist Production-ready, braucht keine Änderungen

### Design-System-Bausteine
| Datei | Inhalt |
|-------|--------|
| `src/output/renderers/email/design_tokens.py` | G_ACCENT, G_PAPER, G_INK, G_SURFACE_1, FONT_UI, WEB_FONT_LINK, G_SUCCESS, G_WARNING |
| `src/output/renderers/email/profile_signature.py` | `profile_signature(profile)` → ProfileSignature(icon_html, eyebrow, accent_hex) |
| `src/output/renderers/email/html.py` | Trip-Briefing-Renderer (Muster-Implementierung) |
| `src/outputs/email.py` | `EmailOutput.send(subject, html, plain_text_body)` — Multipart, Retry |

### DTOs (Python-Seite)
```python
# src/app/user.py
@dataclass
class ComparisonResult:
    locations: List[LocationResult]   # Sortiert nach Score
    time_window: Tuple[int, int]
    target_date: date
    created_at: datetime

@dataclass
class LocationResult:
    location: SavedLocation           # .name, .elevation_m, .id
    score: int
    snow_depth_cm: Optional[float]
    snow_new_cm: Optional[float]
    temp_min, temp_max: Optional[float]
    wind_max, gust_max: Optional[float]
    wind_chill_min: Optional[float]
    wind_direction_avg: Optional[int] # Grad 0-360
    cloud_avg: Optional[int]          # %
    cloud_low_avg: Optional[int]      # % für Wolkenlage
    sunny_hours: Optional[int]
    above_low_clouds: bool
    hourly_data: List[ForecastDataPoint]
```

## Was neu gebaut werden muss

### 1. Neuer Renderer: `src/output/renderers/email/compare_html.py`

**Zweck:** Design-system-konformer HTML-Renderer, analog zu `html.py`

**Layout-Anforderungen:**

*Desktop (680px):*
- Profil-Eyebrow (aus `profile_signature()`) im Kopfbereich
- 4-spaltige Stats: Profil | #Orte | Zeitfenster | Erstellt
- Winner-Card: Score-Badge + Begründungs-Tags (Schnee, Sonne)
- Vergleichs-Matrix: alle Spalten, Best-Value grün markiert
- Stunden-Verlauf: Top-3 Orte × Zeitfenster als Tabelle
- Dunkler Footer (G_INK Hintergrund, weißer Text)

*Mobile (380px) via `@media (max-width: 480px)`:*
- Kompakter Header (Eyebrow + Brand in einer Zeile)
- 2-spaltige Stats
- Matrix kippt zu Karten (eine Karte pro Ort, nur `primary`-Spalten)
- Stunden als kompakte horizontale Streifen je Ort
- Footer einzeilig

**CE_PROFILES (profil-spezifische Spalten):**
Müssen als Mapping definiert werden (kein externes File — im Renderer):
| Profil | Primary-Spalten | Alle Spalten |
|--------|-----------------|--------------|
| WINTERSPORT | Schnee, Neuschnee, Sonne | + Wind, Wolken, Score |
| ALPINE_TOURING | Wind, Gust, Sonne | + Schnee, Wolken, Score |
| SUMMER_TREKKING | Sonne, Wolken, Wind | + Gust, Temp, Score |
| ALLGEMEIN | Score, Sonne, Wind | + alle anderen |

**Inline-CSS-Pflicht:** Kein externes Stylesheet. Design-Tokens als CSS-Custom-Properties am Wurzel-Element mit Hex-Fallback.

### 2. `CompareEmailSender` Service

Neues Modul (oder Erweiterung von `compare_subscription.py`):
```python
class CompareEmailSender:
    def send(
        self,
        result: ComparisonResult,
        subscription: CompareSubscription,
        settings: Settings,
    ) -> bool:  # True = Erfolg
        # 1. render_compare_html(result) → html_body
        # 2. render_compare_text(result) → text_body  (bestehend, kann bleiben)
        # 3. EmailOutput(settings).send(subject, html_body, text_body)
        # 4. Heartbeat-Ping NUR bei Erfolg
        # 5. last_run-Status aktualisieren
```

### 3. Scheduler-Integration

In `api/routers/scheduler.py` / `compare_subscription.py`:
- `run_comparison_for_subscription()` auf neuen Renderer umschalten
- Heartbeat-Ping: `GZ_HEARTBEAT_COMPARE` ENV-Variable (fail-soft wenn leer)
- `last_run`-Tracking für `/api/scheduler/status`-Endpoint

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/email/html.py` | Muster für Renderer-Struktur |
| `src/output/renderers/email/design_tokens.py` | Token-Palette |
| `src/output/renderers/email/profile_signature.py` | Eyebrow-Komponente |
| `src/services/comparison_renderers.py` | Alter Renderer (wird ersetzt/umgekoppelt) |
| `src/services/compare_subscription.py` | Orchestrierung (wird angepasst) |
| `src/services/comparison_engine.py` | Engine (kein Änderungsbedarf) |
| `src/outputs/email.py` | SMTP-Sender |
| `src/app/user.py` | CompareSubscription + ComparisonResult DTOs |
| `api/routers/scheduler.py` | Scheduler-Trigger-Endpoints |
| `docs/specs/compare_email.md` | Bestehende Spec (v4.3, veraltet aber referenzierbar) |

## Existing Patterns

- **Renderer-Pattern:** `html.py` → `render_html(segments, ..., profile) → str` — Pure Function, keine Seiteneffekte
- **Profile-Signatur:** `profile_signature(profile)` liefert Eyebrow-HTML, Icon, Accent-Hex
- **Multipart-Mail:** `EmailOutput.send(subject, html_body, plain_text_body=text_body)`
- **Heartbeat-Pflicht:** Ping NUR nach fachlichem Erfolg (alle Empfänger erreicht, kein SMTP-Fehler)
- **last_run-Tracking:** Status-Endpoint zeigt `last_run: {time, status, error}` pro Job

## Risks & Considerations

1. **Alte Renderer nicht löschen:** `comparison_renderers.py` → `render_comparison_html()` wird von
   `compare_subscription.py` importiert. Erst nach Umkopplung kann der alte Code entfernt werden.
2. **`screen-compare-email.jsx` nicht im Repo:** Design-Details müssen aus Issue-Text + Epic #236
   abgeleitet werden — kein direktes Vorbild-File vorhanden.
3. **CE_PROFILES Definition:** Muss im neuen Renderer definiert werden; kein vorhandenes Mapping.
4. **Mobile @media in Mail-Clients:** Nur Apple Mail und Gmail (iOS) unterstützen @media zuverlässig;
   Outlook ignoriert es → kein Problem, Outlook bekommt Desktop-Layout.
5. **Heartbeat-Env-Var:** `GZ_HEARTBEAT_COMPARE` muss in `.env`/Systemd-Unit ergänzt werden.
6. **Spec-Abhängigkeit:** `docs/specs/compare_email.md` v4.3 ist die bestehende Referenz für
   Plain-Text-Format und HourlyCell — bleibt gültig, HTML-Teil wird von neuer Spec überschrieben.
