# Context: Issue #241 — ActivityProfile durch Mail-Pipeline + Profil-Marker im Header

Sub-Issue 3b von Epic #236. Setzt #240 (Design-Tokens) und #238 (Profil-Signaturen Frontend) voraus.

## Request Summary

`ActivityProfile` von `Trip.aggregation.profile` durch die Render-Pipeline
(Scheduler → Formatter → Renderer) reichen und im Mail-Header sichtbar
markieren (Akzent + Eyebrow + Icon pro Profil). Wintersportler-Mail erkennbar
≠ Wanderer-Mail.

## Aktuelle Pipeline (Post #240)

```
trip_report_scheduler._send_trip_report(trip: Trip)
  Z. 230, hat trip.aggregation.profile verfügbar
  ↓ Z. 339
self._formatter.format_email(
    segments=...,
    display_config=trip.display_config,   ← KEIN profile-Feld
    ...                                    ← KEIN profile-Parameter
)
  ↓
render_email(token_line, **kwargs)         ← 15 kwargs, KEIN profile
  ↓
render_html(**kwargs)                      ← 17 kwargs, KEIN profile
  ↓ Z. 288-291
Header: <div class="header">
  <h1>{trip_name}</h1>
  <h2>{stage_name}</h2>
  <p>{report_type} – {date} | {stats}</p>
</div>
```

## Datenmodell

| Pfad | Datei:Zeile | Wert |
|------|-------------|------|
| `Trip.aggregation` | `src/app/trip.py:179` | `AggregationConfig` (default `field`) |
| `AggregationConfig.profile` | `src/app/trip.py:125` | `ActivityProfile = WINTERSPORT` (Default!) |
| Enum `ActivityProfile` | `src/app/profile.py:24-27` | `"wintersport"`, `"wandern"`, `"summer_trekking"`, `"allgemein"` |
| `UnifiedWeatherDisplayConfig` | `src/app/models.py:470` | KEIN profile-Feld (bleibt so — Memory-Regel zu Schema-Reworks!) |

## Was geändert werden muss

### 1. Profile als separater Parameter durch die Kette

| Datei | Funktion | Was |
|-------|----------|-----|
| `src/services/trip_report_scheduler.py:339` | `_send_trip_report` | `profile=trip.aggregation.profile` an Formatter |
| `src/formatters/trip_report.py:48` | `format_email` | `profile: Optional[ActivityProfile] = None` |
| `src/output/renderers/email/__init__.py:25` | `render_email` | `profile: Optional[ActivityProfile] = None` |
| `src/output/renderers/email/html.py:101` | `render_html` | `profile: ActivityProfile = ActivityProfile.ALLGEMEIN` (Default ALLGEMEIN für Backward-Kompat) |
| `src/services/preview_service.py` | `render_email_preview` und Hilfsfunktion `_build_report` | gleiche Durchreichung |
| `src/output/renderers/email/__init__.py` | `render_plain` (Plain-Text-Variante) | Prefix-Zeile `{icon} {eyebrow}` vor Trip-Namen — sonst geht der Profil-Marker im Plain-Text verloren |

### 2. Neuer Helper

`src/output/renderers/email/profile_signature.py` — Python-Port von
`frontend/src/lib/utils/profileSignature.ts`. Liefert pro Profil
`{accent_hex, icon, eyebrow}`. Werte identisch:

| Profil | accent_hex | icon | eyebrow |
|--------|------------|------|---------|
| wintersport | `#4a7fb5` | `❄` | `Wintersport` |
| wandern | `#3a7d44` | `🥾` | `Wandern` |
| summer_trekking | `#c45a2a` | `🏔` | `Sommer-Trekking` |
| allgemein | `#6b675c` | `◯` | `Allgemein` |

### 3. Header in `html.py`

- `.header`-Background ersetzt `{G_ACCENT}` durch `{profile_accent_hex}` (CSS-Subst pro Profil)
- Neuer Eyebrow-Block oberhalb des `<h1>` im Header:
  ```html
  <div class="eyebrow">{icon} {eyebrow}</div>
  <h1>{trip_name}</h1>
  ```
- Eyebrow-CSS-Regel: kleine Caps, opaque white auf Profil-Akzent

## Test-Strategie

**Pure-Function** (`tests/tdd/test_email_profile_pipeline.py`):
- `profile_signature(profile)` für alle 4 Profile + Fallback (analog Frontend-Test)
- Pipeline-Durchreichung: Renderer mit jedem Profil → Output enthält Profil-Akzent + Eyebrow
- Default-Verhalten ohne `profile`-Argument: rendert weiterhin (kein Crash)

**Real-Gmail** (deferred): Infra-Problem aus #240 noch ungelöst — wir verifizieren
in-process + visuell im Preview-Iframe.

**Bestehende Suite**: `tests/unit/test_renderers_email.py`, `tests/tdd/test_email_design_tokens.py` müssen grün bleiben (Default-Verhalten unverändert).

## LoC-Schätzung

| Datei | Δ |
|-------|---|
| `src/output/renderers/email/profile_signature.py` (neu) | +50 |
| `src/output/renderers/email/html.py` | ~+20 (Header + CSS-Variable) |
| `src/output/renderers/email/__init__.py` | +3 |
| `src/formatters/trip_report.py` | +5 |
| `src/services/trip_report_scheduler.py` | +3 |
| `src/services/preview_service.py` | +5 |
| Tests (`test_email_profile_pipeline.py` neu) | +120 |
| Tests-Manifest (`docs/specs/tests/...`) | 0 (Doku) |

Total Code: ~206 LoC. Innerhalb 250er-Budget mit kleinem Puffer.

## Risiken

- **Default-Wert**: `AggregationConfig.profile = WINTERSPORT` ist Default — bestehende
  Trips ohne explizites Profil bekommen Wintersport-Look. Ist das ok? Tech-Lead-Empfehlung:
  ja, weil dasselbe Verhalten heute schon implizit in Scoring/Display-Config gilt.
- **Backward-Kompat**: alle Pipeline-Aufrufer (Tests, alte Code-Pfade) müssen
  weiter funktionieren — daher `profile: Optional = None` mit Fallback auf
  ALLGEMEIN-Signatur im Renderer
- **Outlook-Tauglichkeit**: Eyebrow als plain `<div>` mit Inline-Style. KEINE
  CSS-Variablen im Output
- **Visuelle Regression**: Header ändert Look pro Profil — manuelle Sicht-Prüfung
  im Preview-iframe Pflicht (AC-7-Pattern aus #240)
- **Real-Gmail-Test geblockt** durch laufende Infra-Störung (Gmail→Stalwart Relay).
  AC-5 äquivalent muss in-process + Preview verifiziert werden, MQ-Message 20834
  an infra hängt noch
- **Icon-Glyphs in Outlook**: `❄ 🥾 🏔 ◯` sind Unicode — Outlook könnte sie als
  Emoji-Fallback rendern (Tofu-Boxen). Mitigation: Eyebrow + Akzent zusammen
  reichen aus, Icon ist Bonus

## Out of Scope

- **Inhalt** der Mail (welche Daten in welchen Block)
- **Trip-Alert-Mail** (Sub-Issue 4)
- **Subscription-Mail** (Sub-Issue 7)
- **Refactor** der Render-Funktion
- **`UnifiedWeatherDisplayConfig.profile`**-Feld einführen — explizit verboten
  (Memory `data_schema_reworks`: keine Schema-Erweiterung)
- **Inhaltliche Profil-Logik** (β4 hat das im Text-Renderer)

## Verwandte Specs

- `docs/specs/modules/issue_238_profile_signatures.md` — Frontend-Pattern, Vorbild
- `docs/specs/modules/issue_240_email_design_tokens.md` — Design-Tokens, frisch live
- `docs/specs/modules/output_channel_renderers.md` — β3-Renderer-Spec
- `docs/specs/modules/activity_profile.md` — Enum-Doku
