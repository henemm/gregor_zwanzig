---
entity_id: issue_241_email_profile_pipeline
type: module
created: 2026-05-17
updated: 2026-05-17
status: draft
version: 1.0.0
tags: [email, design-system, activity-profile, issue-241, epic-236]
parent: epic_236_email_design_system
phase: phase3_spec
---

<!-- Issue #241 — ActivityProfile durch Mail-Pipeline + Profil-Marker im Header (Epic #236 Sub-Issue 3b) -->

# Issue #241 — ActivityProfile durch Mail-Pipeline + Profil-Marker im Header

## Approval

- [x] Approved

## Zweck

`ActivityProfile` von `Trip.aggregation.profile` durch die gesamte Render-Pipeline
(Scheduler → Formatter → Renderer) reichen und im Mail-Header pro Profil sichtbar
markieren: Akzentfarbe (Inline-Hex), Eyebrow-Label und Icon. Damit ist eine
Wintersportler-Mail auf den ersten Blick erkennbar verschieden von einer
Wanderer-Mail — ohne Inhalt oder Datenstruktur zu ändern.

Dieses Sub-Issue ergänzt ausschließlich den Profil-Kanal durch die Pipeline. Inhalt,
Tabellen-Layout und Render-Logik bleiben unverändert.

## Kontext

Setzt voraus:
- **#240** (`issue_240_email_design_tokens`) — Design-Tokens-Modul `design_tokens.py`,
  Solid-Burnt-Orange-Header
- **#238** (`issue_238_profile_signatures`) — Frontend-Helper `profileSignature.ts`
  als Vorbild für den Python-Port

Teil von Epic #236. Die Mail wird live versendet UND im Vorschau-iframe (Epic #140)
gezeigt — ein Renderer-Fix repariert beides automatisch.

## Quelle / Source

**Neue Dateien:**
- `src/output/renderers/email/profile_signature.py` — Python-Port von `frontend/src/lib/utils/profileSignature.ts`
- `tests/tdd/test_email_profile_pipeline.py` — Pure-Function-Tests für alle ACs

**Geänderte Dateien:**
- `src/output/renderers/email/html.py` — Header-Background auf Profil-Akzent, neuer Eyebrow-Block
- `src/output/renderers/email/__init__.py` — `render_email` + `render_plain` erhalten `profile`-kwarg
- `src/formatters/trip_report.py` — `format_email` erhält `profile`-kwarg
- `src/services/trip_report_scheduler.py` — übergibt `trip.aggregation.profile` an Formatter
- `src/services/preview_service.py` — reicht `profile` durch für Preview-Iframe

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/profile.py::ActivityProfile` | Python-Enum | Eingabe-Typ für Helper und alle Signaturen; 4 Werte |
| `src/app/trip.py::AggregationConfig.profile` | Datenfeld | Quelle für Profil-Wert im Scheduler (`trip.aggregation.profile`) |
| `src/output/renderers/email/design_tokens.py` | Modul (#240) | `G_ACCENT` als Fallback-Referenz; Inline-Hex-Pattern wird hier gespiegelt |
| `src/output/renderers/email/html.py::render_html()` | Funktion | Empfänger von `profile`-kwarg; Header-Background + Eyebrow-Block |
| `src/output/renderers/email/__init__.py::render_email()` | Funktion | Durchreiche-Stelle von `render_plain` und `render_html` |
| `src/output/renderers/email/__init__.py::render_plain()` | Funktion | Erhält `profile` für Prefix-Zeile im Plain-Text-Fallback |
| `src/formatters/trip_report.py::format_email()` | Funktion | Durchreiche-Stelle zwischen Scheduler und Renderer |
| `src/services/trip_report_scheduler.py::_send_trip_report()` | Methode | Liefert `trip.aggregation.profile` als Einstiegspunkt |
| `src/services/preview_service.py` | Modul | Reicht `profile` durch damit Preview-Iframe profil-spezifisch rendert |
| `frontend/src/lib/utils/profileSignature.ts` | TS-Helper (#238) | Vorbild für Python-Port; Werte (Hex, Icon, Eyebrow) werden 1:1 übernommen |

## Profil-Signaturen

| Profil | accent_hex | icon | eyebrow |
|--------|------------|------|---------|
| `wintersport` | `#4a7fb5` | `❄` | `Wintersport` |
| `wandern` | `#3a7d44` | `🥾` | `Wandern` |
| `summer_trekking` | `#c45a2a` | `🏔` | `Sommer-Trekking` |
| `allgemein` | `#6b675c` | `◯` | `Allgemein` |

**Wichtig:** Eyebrow für `summer_trekking` ist `Sommer-Trekking` (ö, Bindestrich,
deutsch) — konsistent mit Frontend-Helper aus #238 nach Adversary-Finding F002.

Fallback bei `None` oder unbekanntem Wert: ALLGEMEIN-Signatur.

## Implementation Details

### 1. Neuer Helper `profile_signature.py`

**`src/output/renderers/email/profile_signature.py`** (~50 LoC):

```python
"""Profil-Signaturen fuer Mail-Renderer.

Python-Port von frontend/src/lib/utils/profileSignature.ts (Issue #238).
Liefert pro ActivityProfile Akzentfarbe (Inline-Hex), Icon und Eyebrow-Label.
Outlook ignoriert CSS-Variablen -- daher direkte Hex-Werte, kein var(--g-profile-...).

Bei None oder unbekanntem Wert wird die Signatur von ALLGEMEIN zurueckgegeben.

SPEC: docs/specs/modules/issue_241_email_profile_pipeline.md
VORBILD: frontend/src/lib/utils/profileSignature.ts
"""
from dataclasses import dataclass
from typing import Optional
from app.profile import ActivityProfile


@dataclass(frozen=True)
class ProfileSignature:
    accent_hex: str   # Inline-Hex fuer Outlook-kompatibles Inline-CSS
    icon: str         # Unicode-Glyph
    eyebrow: str      # Sichtbares Label


_SIGNATURES: dict[ActivityProfile, ProfileSignature] = {
    ActivityProfile.WINTERSPORT: ProfileSignature(
        accent_hex='#4a7fb5',
        icon='❄',
        eyebrow='Wintersport',
    ),
    ActivityProfile.WANDERN: ProfileSignature(
        accent_hex='#3a7d44',
        icon='🥾',
        eyebrow='Wandern',
    ),
    ActivityProfile.SUMMER_TREKKING: ProfileSignature(
        accent_hex='#c45a2a',
        icon='🏔',
        eyebrow='Sommer-Trekking',
    ),
    ActivityProfile.ALLGEMEIN: ProfileSignature(
        accent_hex='#6b675c',
        icon='◯',
        eyebrow='Allgemein',
    ),
}

_FALLBACK = _SIGNATURES[ActivityProfile.ALLGEMEIN]


def profile_signature(profile: Optional[ActivityProfile]) -> ProfileSignature:
    if profile is None:
        return _FALLBACK
    return _SIGNATURES.get(profile, _FALLBACK)
```

### 2. Profil-kwarg durch die Kette

Jede Funktion erhält `profile: Optional[ActivityProfile] = None` und reicht ihn
an den nächsten Aufrufer durch. Keine Business-Logik ändert sich, nur die Signatur
und die Weitergabe.

| Datei | Funktion | Änderung |
|-------|----------|----------|
| `trip_report_scheduler.py:~339` | `_send_trip_report(trip)` | `profile=trip.aggregation.profile` als kwarg an `format_email` |
| `trip_report.py:~48` | `format_email(...)` | `profile: Optional[ActivityProfile] = None` hinzu, Weitergabe an `render_email` |
| `email/__init__.py:~25` | `render_email(...)` | `profile: Optional[ActivityProfile] = None` hinzu, Weitergabe an `render_html` und `render_plain` |
| `email/html.py:~101` | `render_html(...)` | `profile: Optional[ActivityProfile] = None` hinzu; ruft `profile_signature(profile)` auf |
| `email/__init__.py` | `render_plain(...)` | `profile: Optional[ActivityProfile] = None` hinzu; Prefix-Zeile `{sig.icon} {sig.eyebrow}` vor Trip-Namen |
| `preview_service.py` | `render_email_preview` + `_build_report` | `profile` durchreichen an `render_email` |

### 3. Header-Änderungen in `html.py`

**Background:** Der `.header`-Block nutzte nach #240 den Token `G_ACCENT` (`#c45a2a`)
als Solid-Background. In #241 wird dieser Wert durch `profile_accent_hex` ersetzt,
sodass jedes Profil eine eigene Farbe bekommt:

```css
/* vorher (nach #240): */
.header { background: #c45a2a; ... }

/* nachher: */
.header { background: {profile_accent_hex}; ... }
```

**Eyebrow-Block:** Direkt vor `<h1>` im Header wird ein neuer `<div>` eingefügt:

```html
<div class="eyebrow"
     style="font-size:11px;font-variant:small-caps;
            letter-spacing:0.08em;opacity:0.85;
            color:#ffffff;margin-bottom:4px;">
  {icon} {eyebrow}
</div>
<h1>{trip_name}</h1>
```

Inline-Style statt CSS-Klasse — Outlook ignoriert `<style>`-Regeln auf verschachtelten
Elementen zuverlässig. Die CSS-Klasse `eyebrow` bleibt als Hook für moderne Clients.

### 4. Plain-Text-Variante

`render_plain` erhält `profile` und fügt eine Prefix-Zeile vor den Trip-Namen ein:

```
{icon} {eyebrow}
{trip_name}
...
```

Profil-Marker geht auch im Text-Fallback (ältere Mail-Clients, SMS-Weiterleitung)
nicht verloren.

### 5. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/output/renderers/email/profile_signature.py` (neu) | +50 | ja |
| `src/output/renderers/email/html.py` | +20 | ja |
| `src/output/renderers/email/__init__.py` | +5 | ja |
| `src/formatters/trip_report.py` | +5 | ja |
| `src/services/trip_report_scheduler.py` | +3 | ja |
| `src/services/preview_service.py` | +5 | ja |
| `tests/tdd/test_email_profile_pipeline.py` (neu) | +120 | ja |
| `docs/specs/tests/issue_241_email_profile_pipeline_tests.md` (neu) | 0 | nein (Doku) |
| **Gesamt** | **~208** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input** (`profile_signature`): `Optional[ActivityProfile]` — einer der 4 Enum-Werte oder `None`
- **Output** (`profile_signature`): `ProfileSignature`-Dataclass mit `accent_hex`, `icon`, `eyebrow`; bei `None` oder unbekanntem Wert → ALLGEMEIN-Signatur
- **Input** (`render_html`): alle bisherigen kwargs + neues `profile: Optional[ActivityProfile] = None`
- **Output** (`render_html`): HTML-String mit profil-spezifischem Header-Background und Eyebrow-Block; ohne `profile`-kwarg rendert wie bisher (ALLGEMEIN-Fallback, kein Crash)
- **Input** (`render_plain`): alle bisherigen kwargs + neues `profile: Optional[ActivityProfile] = None`
- **Output** (`render_plain`): Plain-Text-String mit Prefix-Zeile `{icon} {eyebrow}` vor Trip-Namen; ohne `profile`-kwarg ebenfalls mit ALLGEMEIN-Fallback
- **Side effects:** Keine — alle Funktionen bleiben pure functions

## Acceptance Criteria

- **AC-1:** Given `src/output/renderers/email/profile_signature.py` importiert wird / When `profile_signature(ActivityProfile.WINTERSPORT)` aufgerufen wird / Then liefert es `ProfileSignature(accent_hex='#4a7fb5', icon='❄', eyebrow='Wintersport')`; analog für `WANDERN` (`#3a7d44`, `🥾`, `Wandern`), `SUMMER_TREKKING` (`#c45a2a`, `🏔`, `Sommer-Trekking`), `ALLGEMEIN` (`#6b675c`, `◯`, `Allgemein`)
  - Test: (populated after /tdd-red)

- **AC-2:** Given `render_html` aus `src/output/renderers/email/html.py` / When mit `profile=ActivityProfile.WANDERN` aufgerufen / Then enthält der HTML-String `background:#3a7d44` im Header-Inline-Style und `<div class="eyebrow"` mit `🥾 Wandern` vor dem `<h1>`-Tag; analog für alle 4 Profile mit ihren jeweiligen Hex-Werten und Eyebrow-Labels
  - Test: (populated after /tdd-red)

- **AC-3:** Given `render_email` aus `src/output/renderers/email/__init__.py` / When mit `profile=ActivityProfile.WINTERSPORT` aufgerufen / Then reicht es `profile` an `render_html` und `render_plain` durch, sodass beide Varianten das Profil korrekt abbilden
  - Test: (populated after /tdd-red)

- **AC-4:** Given `format_email` in `src/formatters/trip_report.py` / When mit `profile=ActivityProfile.SUMMER_TREKKING` aufgerufen / Then reicht es `profile` an `render_email` durch, sodass der gerenderte HTML-Body `background:#c45a2a` und `Sommer-Trekking` enthält
  - Test: (populated after /tdd-red)

- **AC-5:** Given `_send_trip_report(trip)` in `src/services/trip_report_scheduler.py` / When ein `Trip`-Objekt mit `trip.aggregation.profile = ActivityProfile.WANDERN` übergeben wird / Then wird `format_email` mit `profile=ActivityProfile.WANDERN` aufgerufen — Profil-Wert geht beim Aufruf nicht verloren
  - Test: `@pytest.mark.email`, deferred (Real-Gmail-Infra-Problem aus #240 unverändert, MQ 20834); in-process + Preview-Iframe-Verifikation als Ersatz
  - Test: (populated after /tdd-red)

- **AC-6:** Given der HTML-Body einer gerenderten Mail mit beliebigem Profil / When der `<div class="header">` untersucht wird / Then enthält er zuerst einen `<div class="eyebrow">`-Block mit `{icon} {eyebrow}`, danach `<h1>` mit Trip-Namen — Reihenfolge im DOM ist eyebrow → h1
  - Test: (populated after /tdd-red)

- **AC-7:** Given `render_plain` aus `src/output/renderers/email/__init__.py` / When mit `profile=ActivityProfile.WINTERSPORT` aufgerufen / Then beginnt der Plain-Text-Output (oder die Trip-Namen-Zeile) mit der Prefix-Zeile `❄ Wintersport` vor dem Trip-Namen
  - Test: (populated after /tdd-red)

- **AC-8:** Given `tests/unit/test_renderers_email.py` und `tests/tdd/test_email_design_tokens.py` / When beide Suiten ohne `profile`-kwarg laufen / Then bleiben alle bestehenden Tests grün — alle Aufrufe ohne `profile` fallen auf ALLGEMEIN-Fallback, kein Crash, keine semantische Regression
  - Test: (populated after /tdd-red)

- **AC-9:** Given `src/services/preview_service.py` / When `render_email_preview` für einen Trip mit gesetztem Profil aufgerufen wird / Then enthält der gerenderte HTML-Body des Preview-Iframes den profil-spezifischen Akzent-Hex und Eyebrow — visuell identisch mit der versendeten Mail
  - Test: (populated after /tdd-red, manuell-visuell via Staging-Vorschau)

- **AC-10:** Given `profile_signature` / When mit `None` oder einem unbekannten String-Wert aufgerufen / Then liefert es die ALLGEMEIN-Signatur (`accent_hex='#6b675c'`, `icon='◯'`, `eyebrow='Allgemein'`) ohne Exception
  - Test: (populated after /tdd-red)

## Known Limitations

- **Outlook-Unicode-Glyphs:** `❄ 🥾 🏔 ◯` können in Outlook als Tofu-Boxen rendern.
  Mitigation: Eyebrow-Text + Akzentfarbe reichen als Profil-Marker; Icon ist Bonus,
  kein alleiniger Träger der Information
- **Real-Gmail-Test deferred:** Gmail→Stalwart-Relay-Infra-Problem aus #240 weiterhin
  aktiv (MQ 20834 an infra). AC-5 wird in-process + visuell im Preview-Iframe
  verifiziert, nicht via Real-Gmail-E2E
- **CSS-Variable wäre eleganter**, aber Inline-Hex ist das Outlook-kompatible Pattern
  aus #240 — bleibt konsistent
- **`AggregationConfig.profile` default ist WINTERSPORT:** Bestehende Trips ohne
  explizit gesetztes Profil bekommen Wintersport-Akzent (blau). Akzeptabel, weil
  dasselbe Default heute bereits implizit in Scoring/Display-Config gilt

## Out of Scope

- **Trip-Alert-Mail** (Sub-Issue 4 von Epic #236)
- **Subscription-Mail** (Sub-Issue 7)
- **Service-Error-Mail** (Sub-Issue 5)
- **Inhalt der Mail** — welche Daten in welchen Block, Tabellen-Layout
- **Refactor des `render_html()`-Monolithen** — eigenes Ticket bei Bedarf
- **`UnifiedWeatherDisplayConfig.profile`-Feld einführen** — explizit verboten
  (Memory-Regel zu Daten-Schema-Reworks; das Feld wird nicht in das Modell aufgenommen)
- **Inhaltliche Profil-Logik** — β4 hat das im Text-Renderer; hier nur visuelle
  Signatur im Header
- **Frontend-Komponenten** — keine Änderung an Svelte/CSS-Dateien

## Risiken & Migration

1. **Default WINTERSPORT:** `AggregationConfig.profile = WINTERSPORT` ist der Default.
   Bestehende Trips ohne explizites Profil erhalten Wintersport-Akzent (`#4a7fb5`).
   Tech-Lead-Entscheidung: akzeptabel, weil dasselbe Default auch im Scoring/Display gilt.

2. **Backward-Kompat:** Alle bestehenden Aufrufer (Tests, alte Code-Pfade) übergeben
   kein `profile`-kwarg. `profile: Optional[ActivityProfile] = None` mit ALLGEMEIN-Fallback
   im Helper sichert Kompatibilität ohne Änderungen an bestehenden Aufrufstellen.

3. **Outlook-Tauglichkeit:** Eyebrow als plain `<div>` mit Inline-Style. KEINE
   CSS-Variablen im Output. Pattern konsistent mit #240.

4. **Visuelle Regression:** Header ändert Farbe pro Profil. Manuelle Sicht-Prüfung
   im Preview-Iframe auf Staging ist Pflicht vor Prod-Deploy (AC-9).

5. **Real-Gmail deferred:** AC-5 wird strukturell in-process verifiziert. Sobald
   MQ 20834 (Infra-Instanz) gelöst ist, kann der Real-Gmail-Marker ergänzt werden.

## Tests / Verifikation

- **Pure-Function** (`tests/tdd/test_email_profile_pipeline.py`):
  - `profile_signature()` für alle 4 Profile → korrekter Hex, Icon, Eyebrow
  - `profile_signature(None)` + `profile_signature("unknown")` → ALLGEMEIN-Fallback
  - `render_html(profile=X)` für alle 4 Profile → HTML enthält Akzent-Hex + Eyebrow-Block
  - `render_plain(profile=X)` für alle 4 Profile → Prefix-Zeile vor Trip-Namen
  - `render_html()` ohne `profile`-kwarg → kein Crash, rendert mit ALLGEMEIN-Fallback
- **Bestehende Suiten:** `tests/unit/test_renderers_email.py` + `tests/tdd/test_email_design_tokens.py` bleiben grün
- **Real-Gmail** (`@pytest.mark.email`): deferred bis MQ 20834 gelöst
- **Manuell-visuell:** Browser-Tab auf `https://staging.gregor20.henemm.com/trips/<id>` → Tab „Vorschau" → Mail-iframe inspizieren, für mind. 2 verschiedene Profile

## Changelog

- 2026-05-17: Initial spec (Epic #236 / Sub-Issue 3b). Setzt #240 + #238 voraus.
