# Epic: Render-Pipeline-Konsolidierung

> **Status:** DRAFT (Skizze zur Review, kein GitHub-Issue)
> **Erstellt:** 2026-04-25
> **Quelle:** Bug #89 Reframing — User-Mandat "Alles soll durch eine Pipeline gehen, kein doppelter Code"
> **SSOT:** `docs/reference/sms_format.md` v2.0 §11

## Motivation

Die Render-Pipeline existiert heute **vier-mal parallel**:

| Pfad | Datei | LoC | Verantwortlich für |
|---|---|---|---|
| Trip → E-Mail | `src/formatters/trip_report.py::format_email` | 1145 | HTML/Text-Tabellen, Token-Line, Subject |
| Trip → SMS | `src/formatters/sms_trip.py::format_sms` | 238 | Token-Line ≤160 Zeichen |
| Wintersport | `src/formatters/wintersport.py::format_compact` | 240 | Profil-Variante mit SN/SFL/AV/WC |
| Subscription | `src/services/compare_subscription.py` | 132 | Vergleichs-Report Location vs. Trip |
| _(zusätzlich)_ | `src/formatters/compact_summary.py` | 364 | Compact-Summary-Block |

**Das Problem ist nicht, dass die Outputs kaputt sind** — sie funktionieren visuell und werden seit Monaten verschickt. Das Problem ist, dass jede Änderung an Token-Logik, Threshold-Format, oder Aggregation **drei- bis viermal** nachgezogen werden muss. Drift ist unausweichlich.

`sms_format.md` v2.0 §11 (APPROVED 2026-04-25) verankert die Soll-Architektur:

> **Single Source of Truth:** Die Token-Zeile ist die einzige verbindliche Output-Repräsentation. Alle Channels (SMS, E-Mail Subject, E-Mail Body, Push) leiten sich aus ihr ab. Implementierungen, die SMS-Text und E-Mail-Subject getrennt erzeugen, sind als **Bug** zu betrachten.

Heute ist das **Soll**, nicht **Ist**.

## Beziehung zu Bug #89

Bug #89 (Weather-Metrics-Dialog-Unification) ist **die UI-Schicht** dieses Refactors:

- Drei drift-ende Dialoge → eine Render-Funktion + Strategy-Dispatch
- Spec approved, Tests RED, Variante A bestätigt
- **Scope:** ~140 LoC, 2 Dateien
- **Bleibt eigenständig** — Bug #89 wird vor diesem Epic gemerged

Der Epic adressiert die **Output-Schicht** (Token-Builder + Channel-Renderer).

## Architektur-Vision (Soll-Zustand)

```
                ┌──────────────────────┐
                │  Aggregierte Daten   │
                │  (NormalizedForecast │
                │   + UnifiedConfig)   │
                └──────────┬───────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  build_token_line()     │  ← EINE Stelle
              │  (src/output/tokens.py) │
              └────────┬────────────────┘
                       │
                       ▼
              ┌────────────────────────┐
              │  TokenLine (DTO)       │
              │  + structured payload  │
              └─┬────────┬─────────┬───┘
                │        │         │
        ┌───────┘        │         └───────┐
        ▼                ▼                 ▼
   render_sms()    render_email()    render_push()
   (≤160 chars)    (HTML+Subject)    (future)
```

**Drei harte Regeln:**

1. Token-Line wird **genau einmal** gebaut.
2. E-Mail-Subject ist ein **Subset** der Token-Line (per Filter-Funktion), keine eigene Logik.
3. Wintersport / Trip / Location / Subscription unterscheiden sich nur in der **Eingabe-Konfiguration**, nicht im Renderer.

## Scope (Was rein, was raus)

### IN

- Neuer Modul-Pfad `src/output/`:
  - `tokens.py` — `TokenLine` DTO, `build_token_line(forecast, config) -> TokenLine`
  - `truncation.py` — Priorität-basiertes Kürzen ≤160 Zeichen (sms_format.md §6)
  - `subject.py` — `build_email_subject(token_line, etappe, report_type) -> str`
  - `renderers/sms.py` — Channel-Renderer SMS
  - `renderers/email.py` — Channel-Renderer E-Mail (HTML + Text)
- Migration der vier bestehenden Pfade auf den neuen Builder
- Backwards-Compat-Tests: Alte und neue Pipeline produzieren **bit-identische** Outputs für ein Set Golden-Master-Trips
- Wintersport-Profil als **Config-Flag** (nicht eigener Renderer)

### OUT

- Keine UI-Änderungen (separater Bug #89)
- Keine neuen Output-Channels (Push/Signal kommen später)
- Kein Loader-Refactor (loader.py ist bereits vollständig)
- Keine Änderung an Provider-Adaptern oder Risk-Engine

## Phasen-Plan (sequenziell, jede Phase eigene Spec + PR)

### Phase β1 — Token-Builder extrahieren (~250 LoC)

- Spec: `docs/specs/modules/output_token_builder.md`
- Neue Datei: `src/output/tokens.py` mit `build_token_line()` aus den **bestehenden** Implementierungen extrahiert
- Golden-Master-Tests: Snapshot der heutigen Outputs für 5 Trip-Profile
- **Akzeptanz:** Der neue Builder produziert exakt die heutige Token-Line von `sms_trip.format_sms`

### Phase β2 — E-Mail-Subject ableiten (~100 LoC)

- Spec: `docs/specs/modules/output_subject_filter.md`
- `trip_report.format_email` ruft `build_email_subject(token_line, ...)` statt eigener Subject-Logik
- **Akzeptanz:** Subject-Diff vs. heutige Outputs ist 0 Zeichen

### Phase β3 — Channel-Renderer-Split (~400 LoC)

- Spec: `docs/specs/modules/output_channel_renderers.md`
- `render_sms()` und `render_email()` als dünne Wrapper über Token-Line + Format-Helpers
- Migration: `sms_trip.py` und `trip_report.py` werden Adapter, ihre Logik zieht in `src/output/renderers/`
- **Akzeptanz:** End-to-End-Tests grün, alle Goldens stable

### Phase β4 — Wintersport als Config-Flag (~150 LoC)

- Spec: `docs/specs/modules/wintersport_profile_consolidation.md`
- `wintersport.format_compact` wird gelöscht; Tokens SN/SN24+/SFL/AV/WC sind im Standard-Builder unter `if profile == "wintersport"`
- **Akzeptanz:** Wintersport-Trip produziert identische Outputs wie heute

### Phase β5 — Subscription auf Pipeline (~200 LoC)

- Spec: `docs/specs/modules/subscription_pipeline_migration.md`
- `services/compare_subscription.py` nutzt `build_token_line()` statt eigener String-Concat-Logik
- **Akzeptanz:** Vergleichs-Reports unverändert; F14b-Alerts werden im Token-Builder evaluiert

### Phase β6 — Cleanup & Doku (~100 LoC)

- Tote Code-Pfade in den vier Original-Dateien entfernen
- `docs/features/architecture.md` aktualisieren
- Devloop-Docs für neue Output-Module

## Geschätzter Gesamt-Scope

| Phase | LoC neu | LoC weg | Netto | Dateien |
|---|---|---|---|---|
| β1 | +250 | 0 | +250 | 3 |
| β2 | +100 | -50 | +50 | 2 |
| β3 | +400 | -300 | +100 | 5 |
| β4 | +150 | -240 | -90 | 3 |
| β5 | +200 | -100 | +100 | 2 |
| β6 | 0 | -200 | -200 | 6 |
| **Σ** | **+1100** | **-890** | **+210** | **~15** |

**Realistisch: 3-5 Wochen** bei sequenzieller Umsetzung mit Spec-Approval pro Phase.

## Risiken

1. **Output-Drift während Migration:** Golden-Master-Tests sind die einzige Sicherung. Müssen vor β1 stehen.
2. **Subject-Format ist subtil:** E-Mail-Clients zeigen die ersten 78 Zeichen prominent. Subject-Filter muss exakt die "Headline-Tokens" extrahieren — nicht raten.
3. **Wintersport-Tokens haben Sonderfälle:** `AV` (Lawinenwarnstufe) und `WC` (Windchill) sind nicht für jeden Provider verfügbar. β4 darf keine Tokens "verlieren".
4. **Subscription-Vergleich hat eigene Tabellen-Struktur:** β5 darf den Vergleichs-Modus nicht zu einem normalen Trip-Report degradieren.
5. **Bug #89 darf nicht warten:** UI-Drift verursacht User-Friction sofort. β startet **nach** Bug #89 GREEN.

## Akzeptanzkriterien (Epic-Level)

- [ ] Genau eine Funktion `build_token_line()` existiert und wird von allen Channels genutzt
- [ ] `grep -r "build_token_line\|format_sms\|format_email" src/` zeigt: Aufrufer in tests + 1-2 Adapter, Definition genau einmal
- [ ] Golden-Master-Tests für 5 Trip-Profile bestehen vor und nach jeder Phase
- [ ] E-Mail-Subject ist messbar ein Token-Line-Subset (Property-Test)
- [ ] Wintersport-Code-Pfad existiert nicht mehr als eigener Renderer
- [ ] sms_format.md §11 ist nicht mehr "Soll", sondern "Ist"

## Offene Fragen (vor GitHub-Issue klären)

1. Soll der Token-Builder Python-only bleiben, oder ist die Go-API (`gregor-api`, Port 8090) im Scope? Heute hat Go eine eigene Token-Implementierung in `gregor-api/internal/...`.
2. Wie wird der Übergang gelivert — Big-Bang nach β6 oder phasenweise im Prod-Betrieb?
3. Welche 5 Trip-Profile werden Golden-Master? Vorschlag: GR20 Sommer, GR20 Frühjahr, GR221 Mallorca, Wintersport Arlberg, Vigilance-Region.

## Bezug zu existierenden Specs

| Spec | Status | Berührungspunkt |
|---|---|---|
| `sms_format.md` v2.0 | APPROVED | SSOT — Epic implementiert §11 |
| `weather_config.md` v2.3 | APPROVED | Liefert `MetricConfig`-Eingabe für Builder |
| `weather_metrics_ux.md` v1.1 | APPROVED | Friendly-Toggle landet im Builder, nicht im Renderer |
| `subscription_metrics.md` v1.0 | DRAFT | β5 macht den DRAFT zur Realität |
| `weather_metrics_dialog_unification.md` v1.0 | APPROVED | Bug #89, läuft parallel zur Epic-Vorbereitung |

## Nächster Schritt

Nach Review dieser Skizze:

1. User-Feedback einarbeiten
2. GitHub-Epic als Issue mit Label `epic` anlegen
3. β1-Spec schreiben
4. Bug #89 GREEN → erst dann β1 starten
