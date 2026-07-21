---
entity_id: issue_722_email_compact_format
type: module
created: 2026-06-11
updated: 2026-06-11
status: approved
version: "1.0"
tags: [feature, email, compact, plain-text, renderer, byte-size, issue-722, slice-709]
---

<!-- Issue #722 [#709 Slice 2] — E-Mail-Format Kompakt/Nur-Text -->

# Issue #722 — E-Mail-Format Kompakt (Nur-Text, minimal-Byte)

## Approval

- [x] Approved (2026-06-11)

## Purpose

Ein Format-Schalter `email_format: full | compact` für die E-Mail. **full** (Default)
ist die heutige multipart-Mail mit HTML und stündlicher Werte-Tabelle pro Etappe —
unverändert. **compact** sendet eine **reine Text-Mail** (single `text/plain`, kein HTML,
kein multipart) mit **fix nur** Kopf + Metriken-Überblick + Ausblick + Footer als
ausformulierten ASCII-Text — **nie** Stundentabellen. Ziel ist minimale Byte-Größe für
Wanderer mit schlechter Konnektivität (~16 KB → unter 1 KB, ~95 % kleiner).

Architektur (PO-bestätigt, Variante B): compact rechnet **nichts neu**. Es ist ein
weiterer Präsentations-Zweig auf derselben Ebene wie SMS/Telegram — der Formatter erhält
die fertig normalisierten `segments`/`multi_day_trend`/`stability_result` aus der einen
Wetter-Pipeline und delegiert an einen kleinen, isolierten `render_compact()`-Renderer, der
dieselben `helpers.py`-Bausteine (`build_metrics_summary_pills`, Stabilitäts-Texte,
`format_trend_tokens`) nutzt. Der bestehende full-Pfad (`render_html`/`render_plain`) bleibt
**byte-identisch unberührt**.

## Source

- **File:** `src/app/models.py`
- **Identifier:** `TripReportConfig` (neues Feld `email_format`)

- **File:** `src/app/loader.py`
- **Identifier:** report_config Deserialisierung (~Z.351) + Serialisierung (~Z.1065)

- **File:** `src/output/renderers/email/compact.py` (NEU)
- **Identifier:** `render_compact()`, `_ascii()`

- **File:** `src/output/renderers/email/__init__.py`
- **Identifier:** `render_email()` (Gating full vs. compact)

- **File:** `src/formatters/trip_report.py`
- **Identifier:** `TripReportFormatter.format()` (email_format durchreichen, text-only Signal)

- **File:** `src/outputs/email.py`
- **Identifier:** `EmailOutput.send()` (`html=False`-Pfad: reines ASCII → `us-ascii`/7bit statt base64)

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** Sende-Pfad (~Z.499) — compact text-only senden

- **File:** `src/services/preview_service.py`
- **Identifier:** `render_email_preview()` (compact-Vorschau)

- **File:** `frontend/src/lib/types.ts`
- **Identifier:** `ReportConfig`-Interface (Feld `email_format`)

- **File:** `frontend/src/lib/components/edit/reportConfigWrite.ts`
- **Identifier:** UI↔Payload-Mapping

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
- **Identifier:** Format-Schalter + Baustein-Gruppe ausgrauen bei compact

Schicht: **Python-Backend** (`src/`) + **Frontend** (`frontend/src/`).
Go-Modell `internal/model/trip.go` unverändert — `ReportConfig map[string]interface{}` ist
Passthrough; `email_format` reist als JSON-Key automatisch mit.

## Estimated Scope

- **LoC:** ~130 (Backend ~85: compact.py ~50, übrige Durchreichung ~35; Frontend ~45)
- **Files:** 11 (1 neu)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` | Python-Dataclass | Trägt neues Feld `email_format` |
| `render_email()` | Pure Renderer-Orchestrator | Entscheidet full vs. compact |
| `build_metrics_summary_pills` | Helper (`helpers.py`) | Liefert Metriken-Überblick-Pills (geteilt mit full) |
| `format_trend_tokens` | Helper (`helpers.py`) | Liefert Ausblick-/Trend-Tokens (geteilt mit full) |
| `StabilityResult` | Python-Dataclass | Großwetterlage-Label für den Ausblick-Text |
| `EmailOutput.send()` | SMTP-Channel | Sendet single `text/plain` bei compact (`html=False`) |
| `ReportConfig` (TS) | TypeScript-Interface | Frontend-Domänenmodell, neues Feld `email_format` |

## Implementation Details

### Schritt 1 — Model & Persistenz

`TripReportConfig` (models.py) neues Feld:
```python
email_format: str = "full"   # Issue #722: "full" | "compact"
```
loader.py deser: `email_format=rc_data.get("email_format", "full")` — und in `serialize`
`"email_format": trip.report_config.email_format`. Default `"full"` → Alt-Trips byte-identisch.

### Schritt 2 — compact.py (NEU)

Pure Function `render_compact(...)` mit denselben kwargs-Quellen wie `render_plain`
(segments, dc, multi_day_trend, stability_result, tz, report_type, trip_name, stage_name,
stage_stats). Baut **nur**:
1. **Kopf:** Eyebrow (Profil), `{trip_name} - {report_type} Report`, optional Etappenname,
   Datum (Ortszeit), Etappen-Kennzahlen (km/↑/↓) — als ASCII.
2. **Metriken-Überblick:** `build_metrics_summary_pills(...)` → `[TONE] Label`-Zeilen.
3. **Ausblick:** Stabilitäts-Text (aus `stability_result.label`, identische Texte wie
   render_plain), Confidence-Hint (`build_confidence_hint`), „Naechste Etappen" mit
   `format_trend_tokens` pro Etappe.
4. **Footer:** Generated-Zeitstempel + Data/Provider-Zeile.

Baustein-Toggles (show_highlights, daily_summary, show_stage_stats-Detail etc.) greifen
**NICHT** — fix Metriken-Überblick + Ausblick (PO-Entscheidung, maximale Vereinfachung).

`_ascii(text)` transliteriert am Ende den gesamten Body: Umlaute (ä→ae, ö→oe, ü→ue, ß→ss),
gängige Sonderzeichen (· → -, — → -, – → -, ↑ → +, ↓ → -, ° → C, ⚡ → T, ━ → =) und entfernt
übrige Nicht-ASCII (Emoji). Resultat MUSS `str.isascii() == True` erfüllen.

### Schritt 3 — render_email() Gating (__init__.py)

Neuer Parameter `email_format: str = "full"`. Bei `"compact"`:
```python
if email_format == "compact":
    compact_text = render_compact(...)
    return "", compact_text   # html_body == "" signalisiert text-only
```
Sonst der bestehende full-Pfad (unverändert). Leerer html_body ist das Signal an den
Scheduler, text-only zu senden.

### Schritt 4 — Formatter (trip_report.py)

`_email_format = report_config.email_format if report_config else "full"`, als kwarg an
`render_email`. `TripReport.email_html` ist dann `""` bei compact (Plain trägt den Inhalt).

### Schritt 5 — email.py: 7bit für ASCII

Im `html=False`-Pfad (single part): wenn `body.isascii()` →
`MIMEText(body, "plain", "us-ascii")` (CTE 7bit), sonst wie bisher `"utf-8"`. Verhindert die
Python-base64-Default-Falle (utf-8-Charset → base64 auch für reinen ASCII-Text).

### Schritt 6 — Scheduler-Send (trip_report_scheduler.py)

```python
if report.email_html:
    email_output.send(subject=..., body=report.email_html, plain_text_body=report.email_plain)
else:
    email_output.send(subject=..., body=report.email_plain, html=False)   # compact: single text/plain
```

### Schritt 7 — Preview-Service

`render_email_preview` bei compact: gibt den compact-Text zurück, für die Browser-Vorschau in
`<pre>...</pre>` gehüllt (nur Anzeige — die gesendete Mail bleibt nacktes text/plain).

### Schritt 8 — Frontend

`ReportConfig.email_format?: 'full' | 'compact'` (types.ts), Mapping in reportConfigWrite.ts.
In `EditReportConfigSection.svelte` oben ein Schalter (Radio/SegmentedControl)
„Ausführlich (HTML) / Kompakt (Nur-Text)". Bei `compact` wird die „Inhalts-Bausteine"-Gruppe
sichtbar deaktiviert/ausgegraut (Hinweis: „Im Kompakt-Modus werden fix Metriken-Überblick +
Ausblick gezeigt"). Auswahl persistiert über den bestehenden Save-Flow.

## Expected Behavior

- **Input:** Nutzer wählt im E-Mail-Editor `email_format = compact`; Scheduler erzeugt den Report.
- **Output:** Eine `text/plain`-Only-Mail (kein HTML-Part, kein multipart), reines ASCII, mit
  Kopf + Metriken-Überblick + Ausblick + Footer, ohne Stundentabellen, unter ~1 KB.
- **Side effects:** Keine. full-Modus und alle anderen Kanäle (SMS/Telegram) unverändert.

## Acceptance Criteria

**AC-1:** Given ein Trip ohne gesetztes `email_format` oder mit `email_format = "full"` /
When der Scheduler die E-Mail erzeugt und versendet / Then ist die Mail eine multipart-Mail
mit HTML-Teil und stündlichen Werte-Tabellen pro Etappe — exakt wie heute (Backward
Compatibility, keine sichtbare Änderung).
- Test: Backend-E2E gegen Staging — Test-Trip mit `email_format="full"` → Mail an
  gregor-test@henemm.com → IMAP: Content-Type ist `multipart/alternative`, HTML-Part vorhanden,
  Stundentabelle erkennbar.

**AC-2:** Given ein Trip mit `email_format = "compact"` / When der Scheduler die E-Mail erzeugt
und versendet / Then enthält die Mail den Metriken-Überblick UND den Ausblick (Großwetterlage,
Naechste Etappen) als ausformulierten Text und KEINE Stundentabellen.
- Test: Backend-E2E gegen Staging — Test-Trip mit `email_format="compact"` → IMAP-Body enthält
  „Metriken" und „Naechste Etappen"-Block, aber keine stündliche Tabellen-Zeile (kein
  Uhrzeit-Raster pro Segment).

**AC-3:** Given ein Trip mit `email_format = "compact"` / When die Mail versendet wird / Then
ist die Mail eine reine `text/plain`-Mail (kein `multipart`, kein HTML-Part) und deutlich
kleiner als die full-Variante (Größenordnung unter 2 KB Body).
- Test: Backend-E2E gegen Staging — IMAP: Content-Type des Top-Level ist `text/plain` (nicht
  multipart), kein `text/html`-Part vorhanden; Body-Größe < 2000 B.

**AC-4:** Given ein Trip mit `email_format = "compact"` / When die Mail versendet wird / Then
ist der Body reines ASCII (keine Umlaute, keine Emojis, keine Box-Zeichen) und mit 7bit
Content-Transfer-Encoding kodiert.
- Test: Backend-E2E gegen Staging — IMAP: dekodierter Body erfüllt `body.isascii() == True`,
  Content-Transfer-Encoding ist `7bit`.

**AC-5:** Given ein Trip mit `email_format = "compact"`, bei dem zusätzlich Bausteine wie
„Zusammenfassung/Highlights" oder „Tages-Summe" aktiviert sind / When die Mail erzeugt wird /
Then werden diese Bausteine NICHT gerendert — gezeigt werden fix nur Metriken-Überblick +
Ausblick (die Baustein-Auswahl greift im Kompakt-Modus nicht).
- Test: Backend-E2E gegen Staging — Test-Trip compact mit `show_highlights=true`,
  `daily_summary_metrics` gesetzt → IMAP-Body enthält weder den Highlights-Block noch die
  „Tages-Summe"-Überschrift.

**AC-6:** Given der Nutzer öffnet den E-Mail-Editor eines Trips / When er das Format auf
„Kompakt" umschaltet und speichert / Then wird die „Inhalts-Bausteine"-Gruppe sichtbar
deaktiviert/ausgegraut, und die Auswahl `compact` bleibt nach Speichern + erneutem Laden
erhalten.
- Test: Playwright E2E gegen Staging — Format auf „Kompakt" stellen, speichern, Seite neu
  laden → Schalter steht weiter auf „Kompakt", Baustein-Checkboxen sind disabled.

**AC-7:** Given zwei verschiedene Nutzer mit je einem Trip, Nutzer A `email_format="compact"`,
Nutzer B `email_format="full"` / When beide Trips geladen werden / Then trägt jeder Trip exakt
seinen eigenen Wert — keine Vermischung, kein `"default"`-Fallback.
- Test: Backend-E2E gegen Staging — zwei registrierte Nutzer, je ein Trip; GET der Trips liefert
  pro Nutzer den korrekten `email_format`.

## Known Limitations

- Im Kompakt-Modus ist die Baustein-Auswahl bewusst wirkungslos (PO-Entscheidung). Die
  gespeicherten Baustein-Werte bleiben erhalten und greifen wieder, sobald der Nutzer zurück auf
  „Ausführlich" schaltet.
- Die ASCII-Transliteration vereinfacht deutsche Umlaute (ue/ae/oe) und ersetzt Sonderzeichen.
  Das ist die bewusst gewählte „maximal klein/robust"-Variante (PO-Entscheidung), kein Bug.
- Die compact-Vorschau im Frontend hüllt den Text zur Anzeige in `<pre>`; die tatsächlich
  versendete Mail ist nacktes `text/plain` ohne diese Hülle.

## Changelog

- 2026-06-11: Initial spec created
