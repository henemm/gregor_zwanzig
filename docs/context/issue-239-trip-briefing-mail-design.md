# Context: Issue #239 — Trip-Briefing-Mail auf Design-System + Profil-Signatur

Teil von Epic #236, Sub-Issue 3. Voraussetzung erfüllt: #238 (Profil-Signaturen
im Design-System).

## Request Summary

`src/output/renderers/email/html.py::render_html()` auf die neuen Design-Tokens
umstellen und das `ActivityProfile` durch die Render-Pipeline reichen, damit
Wintersportler/Wanderer/Summer-Trekker/Allgemein sichtbar unterscheidbare
Mails bekommen — sowohl beim echten Versand als auch im Preview-Iframe
(Epic #140).

## Renderer-Anatomie (`html.py`, 13 KB)

**Signatur** (Z. 95–113): 16 Parameter, **kein `ActivityProfile`** dabei.
Empfängt nur `dc: UnifiedWeatherDisplayConfig` (Metriken-Auswahl), nicht das
Profil das die Metriken einst auswählte.

**Blockstruktur** (Z. 256–302 = HTML-Wrapper):

| Block | Zeilen |
|-------|--------|
| Header (gradient #1976d2→#42a5f5) | 280–284 |
| Compact-Summary (Box #f0f7ff) | 220–222, 286 |
| Confidence-Hint (Box #fff8e1) | 230–235, 287 |
| Daylight/Stirnlampe (Box #fffde7) | 237–239, 288 |
| Weather Changes | 241–251, 289 |
| Segment-Tabellen | 130–154, 290 |
| Nacht am Ziel | 156–168, 291 |
| Gewitter-Vorschau | 170–183, 292 |
| Multi-Day-Trend (Box #f5f5f5) | 185–206, 293 |
| Highlights | 208–215, 294 |
| Footer | 296–299 |

**Hartkodierte Hex-Werte**: 18 Stück
- Im `<style>` (8): `#f5f5f5`, `#1976d2`, `#42a5f5`, `#333`, `#e3f2fd`, `#90caf9`, `#888`, `#ddd`
- Inline pro Block (10): `#666`, `#fffde7`, `#f9a825`, `#fff3e0`, `#e65100`, `#999`, `#555`, `#f0f7ff`, `#fff8e1`, `#fbc02d`

**Schriften**: nur Z. 262 — `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`. Inter Tight / JetBrains Mono fehlen komplett.

**Layout**: bereits `<table>`-basiert (Outlook-tauglich). HTML-Skelett ist vollständig (DOCTYPE→/html), nicht nur Body-Fragment.

## Pipeline-Pfad — wo das Profil verloren geht

```
Trip.aggregation.profile (WINTERSPORT/WANDERN/…)
  ↓ src/app/loader.py:222
build_default_display_config_for_profile(profile)
  ↓
Trip.display_config: UnifiedWeatherDisplayConfig  ← KEIN .profile-Feld!
  ↓ src/services/trip_report_scheduler.py:335
format_email(display_config=trip.display_config)
  ↓ src/formatters/trip_report.py:68,111
render_email(display_config=dc)
  ↓ src/output/renderers/email/__init__.py:25
render_html(dc=dc)  ← Profil-Info ist hier schon weg
```

**Bruchstelle**: `UnifiedWeatherDisplayConfig` (`src/app/models.py:470-540`) hat
kein `profile`-Feld. Das Profil wird beim Trip-Laden konsumiert um Metriken zu
wählen, danach weggeworfen.

**Empfehlung**: Separater Parameter durch die Kette reichen (Option B aus der
Analyse), **nicht** das Dataclass-Schema anfassen — geringere Blast-Radius,
keine Daten-Migrations-Frage (vgl. Memory `bug_dataloss_gr221`).

## Test-Infrastruktur

**Real-Gmail-E2E-Pattern** (`tests/tdd/test_html_email.py::TestRealGmailE2E`):
- `Settings.for_testing()` (`src/app/config.py:136`) routet Test-User auf Gmail-SMTP
- Subject mit Unique-UUID für IMAP-Suche
- IMAP4_SSL Abruf, Multipart/alternative-Check, HTML-Asserts auf DOCTYPE/`<table>`/`<style>`
- Marker `@pytest.mark.email`, Selektion via `-m email`

**Existierende Renderer-Tests**:
- `tests/unit/test_renderers_email.py` — Pure-Function-Tests
- `tests/unit/test_trip_report_formatter_v2.py` — Format-Pipeline
- `tests/integration/test_cli_wintersport.py` — End-to-End

## Preview-Endpoint (Epic #140)

- `src/services/preview_service.py:104-118` — `render_email_preview()` ruft
  `formatter.format_email()` mit Trip-DisplayConfig auf, kein Versand
- `api/routers/preview.py:28-50` — GET `/api/preview/{trip_id}/email` → `HTMLResponse`
- `frontend/src/lib/components/preview/EmailIframe.svelte:15-41` — iframe `srcdoc`,
  rendert vollständiges HTML inkl. `<style>`

**Konsequenz**: Wenn der Renderer profil-bewusst wird, wird auch die Vorschau
automatisch profil-bewusst — kein separater Code-Pfad.

## Existierende Specs

- `docs/specs/modules/output_channel_renderers.md` (β3) — beschreibt
  `render_email()` als pure function
- `docs/specs/modules/output_text_report_renderer.md` (β4) — Text-Renderer
  ist bereits profil-bewusst, **inspirieren** für HTML-Pfad
- `docs/specs/modules/activity_profile.md` — Enum
- `docs/specs/modules/issue_238_profile_signatures.md` — Frontend-Tokens & Helper

## Verwandte Issues

- Epic #133 (Design-System) — Token-Quelle
- Epic #140 (Vorschau) — wird durch diesen Umbau automatisch korrekt
- #238 (Profil-Signaturen) — geliefert, hier wird gespiegelt
- Bug #125 (Safari-HTML-Cache) — relevant beim Versand-Test

## Risiken & Scope

1. **LoC-Budget**: 250 reicht ggf. nicht — Renderer (13 KB) + Pipeline (4 Dateien)
   + neuer Python-Token-Helper + Tests = realistisch 200–300 LoC
2. **Visuelle Regression**: 18 Hex-Werte austauschen — falscher Token kann
   gesamten Block-Look kippen, ohne Test-Failure (nur per Auge sichtbar)
3. **Outlook**: keine CSS-Variablen → alle Werte als Hex inline / im `<style>`
4. **Daten-Schema**: `UnifiedWeatherDisplayConfig` **nicht erweitern** (Memory
   `data_schema_reworks` — Bestandsdaten könnten Felder verlieren). Profil als
   separater Parameter durch die Kette
5. **Real-Mail-Test-Flake**: Gmail-Sendungen können bei API-Limits scheitern

## Empfohlener Schnitt (zur Diskussion in Phase 2)

**Option A — Ein Workflow**: AC-1 bis AC-7 in einem Rutsch. Risiko: LoC > 250,
großer Diff, schwerere Reviews.

**Option B — Zwei Workflows**:
- **#239a** Pure Styling: Design-Tokens-Modul (Python-Port von app.css), Hex
  ersetzen, Fonts hinzufügen — **ohne** Profil. AC-2 + AC-4. Sichtbarer Win:
  Mail sieht aus wie das Design-System. ~150 LoC.
- **#239b** Profil-Pfad: Profile durch Pipeline reichen, Header-Marker pro
  Profil, Real-Mail-Test pro Profil, Preview-Parität. AC-1 + AC-3 + AC-5 + AC-6
  + AC-7. ~150 LoC.

**Tech-Lead-Empfehlung**: **Option B**. Begründung:
- Visueller Fortschritt nach 3a sofort sichtbar (Design-Look in Mails)
- 3a niedrig-risiko (reine Konstanten-Substitution), 3b hat höhere
  Pipeline-Komplexität — saubere Trennung
- LoC bleibt in jedem Workflow im Budget
- Wenn 3a Real-Mail-Probleme zeigt, ist 3b-Profil-Layer nicht betroffen

## Next Step

Phase 2 (Analyse) — Cut bestätigen, Datei-Liste pro Workflow finalisieren,
Token-Werte und Plain-Python-Port-Pattern definieren.
