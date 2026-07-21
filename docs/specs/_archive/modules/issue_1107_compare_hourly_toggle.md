---
entity_id: issue_1107_compare_hourly_toggle
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [compare, preset, hourly, validator, marker-header]
workflow: fix-1107-compare-sections-validator
---

# Ortsvergleich D: Stundenverlauf-Sektion abschaltbar + Validator config-bewusst

## Approval

- [ ] Approved

## Purpose

Ergänzt den Compare-Preset um ein Bool-Feld „Stundenverlauf anzeigen" (`hourly_enabled`,
Default `true`), mit dem ein Nutzer pro Orts-Vergleich die komplette Stundenverlauf-Sektion
(„STUNDEN"-Kopf + alle Orts-Stundentabellen) der Compare-Mail abschalten kann — nicht nur
einzelne Spalten (das leistet bereits `hourly_metrics` aus #1106). Damit der zwingende
Compare-Mail-Validator (`email_spec_validator.py`) eine so konfigurierte Mail nicht fälschlich
als kaputt meldet, wird er über einen neuen Marker-Header config-bewusst gemacht: bei
abgeschalteter Sektion entfällt die Pflicht, für jeden gelisteten Ort eine Stundentabelle zu
finden. Letzter offener Teil-Slice von Issue #1094/#1092 Teil D.

## Source

- **File:** `internal/model/compare_preset.go`, `src/output/renderers/email/compare_html.py`
- **Identifier:** `ComparePreset.HourlyEnabled`, `render_compare_html(hourly_enabled=...)`,
  `.claude/hooks/email_spec_validator.py::validate_structure(hourly_enabled=...)`

> **Schicht-Hinweis:** Go-API (`internal/model/`, `internal/handler/`) für das Preset-Feld +
> RMW. Python-Core (`src/output/renderers/`, `src/services/`, `api/routers/validator.py`) für
> Renderer-Gating, Versand-Wiring und Preview-Parität. `.claude/hooks/` für den Validator
> (kein Produktionscode, aber Pflicht-Gate). SvelteKit-Frontend
> (`frontend/src/lib/components/compare/`) für die UI-Control.

## Estimated Scope

- **LoC:** ~480–560 (Go-Modell+Handler ~10, Go-Tests ~220 analog `compare_preset_official_alerts_test.go`;
  Python-Implementierung [Renderer/Dispatch/Preview/Validator] ~90, Python-Tests ~220;
  Frontend ~25). Nahe/über dem 250-LoC-Standardlimit — `loc_limit_override` während der
  Implementierung wahrscheinlich nötig. **User MUSS explizit gefragt werden, sobald die
  tatsächliche Diff-Größe feststeht — nicht eigenmächtig setzen.**
- **Files:** 16 (2 neu: Go-Test, Python-Test; 14 geändert)
- **Effort:** high (Validator-Gate-Änderung, drei Schichten, Preview/Versand-Parität)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/model/compare_preset.go` | MODIFY | Neues Feld `HourlyEnabled *bool` |
| `internal/handler/compare_preset.go` | MODIFY | RMW-Merge analog `OfficialAlertsEnabled` |
| `internal/handler/compare_preset_hourly_enabled_test.go` | CREATE | Roundtrip + Legacy-Load + RMW + Cross-User-Isolation, echter Filesystem-Test (`t.TempDir()`) |
| `src/output/renderers/email/compare_html.py` | MODIFY | `render_compare_html(hourly_enabled=True)`-Parameter, `hourly_head_html`/`hourly_sections_html` bei `False` leer |
| `src/output/renderers/comparison.py` | MODIFY | `render_compare_email()` reicht `hourly_enabled` durch |
| `src/output/channels/email.py` | MODIFY | `build_mime_message()`/`EmailOutput.send()` neuer optionaler Parameter `compare_hourly_enabled`, setzt Marker-Header `X-GZ-Compare-Hourly-Enabled` |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset()` liest `preset.get("hourly_enabled", True)` (Top-Level-Feld, NICHT `display_config`), reicht an Renderer + Marker-Header durch |
| `src/services/validator_render_service.py` | MODIFY | `render_compare_email_preview()` zieht `hourly_enabled` mit (Anti-#954) |
| `api/routers/validator.py` | MODIFY | `CompareEmailPreviewBody.hourly_enabled: bool = True` |
| `.claude/hooks/email_spec_validator.py` | MODIFY | `_fetch_latest_message()`-Refactor (Header + Body aus derselben IMAP-Runde), `validate_structure(body, hourly_enabled=True)` überspringt Stundentabellen-Pflicht bei `False`, `run_validation()` liest Header |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | Neuer `$state`-Boolean `hourlyEnabled`, Wiring in `saveNewPreset()`/`saveComparePreset()` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `CompareEditorEdits.hourlyEnabled` + Round-Trip-Spread (Top-Level-Feld, analog `officialAlertsEnabled`) |
| `frontend/src/lib/types.ts` | MODIFY | `ComparePreset.hourly_enabled?: boolean` |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | `state.hourlyEnabled = data.preset.hourly_enabled ?? true;` |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | MODIFY | Neue `ChannelToggle`-Instanz „Stundenverlauf" |
| `tests/tdd/test_issue_1107_compare_sections.py` | CREATE | Renderer-Gating, Dispatch-Wiring (Sentinel-Rebind), Validator-Header-Gating, Preview-Parität |

**Korrektur gegenüber der Analyse-Phase:** `frontend/.../compare/CompareEditor.svelte`
benötigt **keine** Änderung — geprüft (`grep officialAlertsEnabled|topN` liefert keinen Treffer
in dieser Datei). Die Bindung läuft ausschließlich über `CompareWizardState`
(Step5Versand-Toggle → `state.hourlyEnabled` → `saveComparePreset()`), analog zu
`officialAlertsEnabled`. `CompareEditor.svelte` ist reine Layout-Hülle ohne Feld-Kenntnis.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/compare_preset.go::OfficialAlertsEnabled *bool` (#1040) | Muster-Referenz | Identisches Pointer-Pattern für additive, optionale Preset-Felder |
| `internal/handler/compare_preset.go::OfficialAlertsEnabled`-Merge (Zeile 214-219) | Muster-Referenz | RMW-Nil-Check-Vorlage im Update-Handler |
| `internal/handler/compare_preset_official_alerts_test.go` | Muster-Referenz | Exaktes Testdatei-Layout: Roundtrip, Legacy-Load, RMW-Preserve, Cross-User-Isolation (4 Tests) |
| `src/output/renderers/email/compare_html.py::hourly_head_html`/`hourly_sections_html` (Zeile 678-684) | Ziel-Codepfad | Bereits als eigene String-Segmente vorhanden — nur das Leer-Setzen bei `False` ist neu |
| `src/output/channels/email.py::build_mime_message(mail_type=, mail_format=)` | Muster-Referenz | Etabliertes optionales-Header-Pattern (`if x is not None: msg["X-GZ-..."] = x`); `compare_hourly_enabled` folgt identisch |
| `.claude/hooks/briefing_mail_validator.py::validate_message()` (liest `msg["X-GZ-Mail-Type"]`) | Muster-Referenz | Zeigt, wie ein Hook-Validator MIME-Header statt nur Body liest — `email_spec_validator.py` tut das bisher NICHT (nur Body), muss dafür erweitert werden |
| `frontend/.../compareEditorSave.ts::officialAlertsEnabled`-Spread (Zeile 88-91) | Muster-Referenz | Round-Trip-Prinzip für ein Top-Level-Bool-Feld (NICHT `display_config`) |
| `frontend/.../steps/Step5Versand.svelte::ChannelToggle` „Amtliche Warnungen" (Zeile 135-142) | Muster-Referenz | Bestehender Bool-Toggle für eine zweite, unabhängige Preset-Eigenschaft |
| Issue #1104 (`top_n`/`enabled_metrics`) | Kontext | Reicht bereits `hourly_metrics` (Spalten-Filter) durch `send_one_compare_preset()` — dieses Slice ergänzt die zusätzliche Sektions-Ebene (ganz/gar nicht) |
| Referenz `reference_preview_vs_dispatch_path_divergence.md` (#954) | Risiko-Referenz | Begründet, warum `validator_render_service.py` zwingend mitgezogen werden muss |

## Implementation Details

```go
// internal/model/compare_preset.go — neues Feld, Pointer-Pattern (wie
// Weekday *int, OfficialAlertsEnabled *bool): fehlt das Feld im JSON
// (Altdaten), decodiert Go zu nil statt zum Zero-Value false. Ein plain
// bool würde Bestandspresets beim nächsten Speichern durch einen Client,
// der das Feld nicht kennt, unbemerkt auf "aus" umstellen.
// Issue #1107 — steuert ob die Stundenverlauf-Sektion (Kopf + alle
// Orts-Stundentabellen) der Compare-Mail gerendert wird. nil/true =
// Sektion sichtbar (Default), false = komplett weggelassen.
HourlyEnabled *bool `json:"hourly_enabled,omitempty"`
```

```go
// internal/handler/compare_preset.go — UpdateComparePresetHandler, direkt
// nach dem OfficialAlertsEnabled-Merge (Zeile 217-219). false ist ein
// gültiger, bewusst gesetzter Wert und darf nicht mit "Feld fehlte"
// verwechselt werden.
// Issue #1107: hourly_enabled erhalten wenn Body es nicht trägt.
if updated.HourlyEnabled == nil {
    updated.HourlyEnabled = original.HourlyEnabled
}
```

`validateComparePreset()` braucht **keine** neue Regel — ein `*bool` hat keinen ungültigen
Wertebereich (anders als `Weekday 0..6`).

```python
# src/output/renderers/email/compare_html.py — render_compare_html(), neuer
# Keyword-Parameter analog top_n_details/enabled_metrics/hourly_metrics.
def render_compare_html(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] | None = None,
    top_n_details: Optional[int] = None,
    enabled_metrics: set | None = None,
    hourly_metrics: set | None = None,
    hourly_enabled: bool = True,          # NEU (Issue #1107)
    preset_name: Optional[str] = None,
    preset_schedule: Optional[str] = None,
    preset_weekday: Optional[int] = None,
) -> str:
    """... (bestehender Docstring) ...

    Args:
        ...
        hourly_enabled: Issue #1107 -- ``False`` laesst die komplette
            Stundenverlauf-Sektion (Kopf "STUNDEN" + alle Orts-
            Stundentabellen) weg. ``hourly_metrics`` (Spalten-Filter,
            #1106) hat dann keine Wirkung mehr, da die Sektion gar nicht
            gerendert wird. Default ``True`` (rueckwaertskompatibel,
            identisch zum Verhalten vor diesem Slice).
    """
    ...
    hourly_head_html = (
        f'<div style="padding:26px 24px 0;">'
        f'{_render_section_head("STUNDEN", "Stundenverlauf · alle Orte", "09–16 Uhr")}</div>'
    ) if hourly_enabled else ""
    hourly_sections_html = (
        "".join(_render_location_section(loc, i, hourly_metrics) for i, loc in enumerate(locations))
        if hourly_enabled else ""
    )
```

```python
# src/output/renderers/comparison.py — render_compare_email(), Parameter
# durchreichen (Zeile 116-157). Docstring-Ergaenzung analog hourly_metrics.
def render_compare_email(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] | None = None,
    top_n_details: Optional[int] = None,
    enabled_metrics: set | None = None,
    hourly_metrics: set | None = None,
    hourly_enabled: bool = True,          # NEU (Issue #1107)
    preset_name: Optional[str] = None,
    preset_schedule: Optional[str] = None,
    preset_weekday: Optional[int] = None,
) -> tuple[str, str]:
    ...
    html_body = render_compare_html(
        result, profile=profile, warnings=warnings, top_n_details=top_n_details,
        enabled_metrics=enabled_metrics, hourly_metrics=hourly_metrics,
        hourly_enabled=hourly_enabled, preset_name=preset_name,
        preset_schedule=preset_schedule, preset_weekday=preset_weekday,
    )
    text_body = render_comparison_text(result, profile=profile)
    return html_body, text_body
```

**Klartext-Renderer bewusst unverändert:** `render_comparison_text()` zeigt bereits keine
separate "STUNDENVERLAUF"-Pflicht-Sektion pro Ort im Sinne eines abschaltbaren Blocks der
HTML-Mail — sie iteriert eigenständig über `loc_result.hourly_data`. Der Klartext-Pfad ist in
`docs/context/fix-1104...` als eigener, nicht synchronisierter Nebenpfad dokumentiert
(`render_comparison_text` hat laut Kontext-Dokument aktuell **keinen** `enabled_metrics`-Parameter,
das ist Issue #1125). Eine `hourly_enabled`-Steuerung für den Klartext-Stundenblock wird daher
bewusst nicht in diesem Slice ergänzt (siehe Known Limitations) — Scope-Konsistenz mit #1125.

```python
# src/output/channels/email.py — build_mime_message(), neuer optionaler
# Parameter analog mail_type/mail_format (beide Branches: html UND plain).
def build_mime_message(
    subject: str,
    body: str,
    from_addr: str,
    to_header: str,
    reply_to: str | None,
    html: bool,
    plain_text_body: str | None,
    mail_type: str | None = None,
    mail_format: str | None = None,
    compare_hourly_enabled: bool | None = None,   # NEU (Issue #1107)
):
    ...
    if mail_type is not None:
        msg["X-GZ-Mail-Type"] = mail_type
    if mail_format is not None:
        msg["X-GZ-Format"] = mail_format
    if compare_hourly_enabled is not None:
        msg["X-GZ-Compare-Hourly-Enabled"] = "true" if compare_hourly_enabled else "false"
    # (identischer Block im html=False-Zweig)
```

`EmailOutput.send()` bekommt denselben neuen Parameter `compare_hourly_enabled: bool | None = None`
und reicht ihn 1:1 an `build_mime_message()` durch (analog `mail_type`/`mail_format`, Zeile
144-193).

```python
# src/services/scheduler_dispatch_service.py — send_one_compare_preset(),
# NACH dem bestehenden #1104/#1106-Block (Zeile 271-273). hourly_enabled
# ist ein TOP-LEVEL Preset-Feld (wie official_alerts_enabled), NICHT im
# display_config-Blob -- direkter preset.get(), kein display_config-Zugriff.
hourly_enabled = preset.get("hourly_enabled", True)  # Issue #1107

html_body, text_body = render_compare_email(
    result,
    profile=profile,
    top_n_details=top_n_details,
    enabled_metrics=enabled_metrics,
    hourly_metrics=hourly_metrics,
    hourly_enabled=hourly_enabled,          # NEU
    preset_name=name,
    preset_schedule=preset.get("schedule"),
    preset_weekday=preset.get("weekday"),
)
EmailOutput(settings).send(
    subject,
    html_body,
    plain_text_body=text_body,
    to=empfaenger,
    compare_hourly_enabled=hourly_enabled,  # NEU -- Marker-Header fuer den Validator
)
```

**Bewusst kein `mail_type="compare"` ergänzt:** `send_one_compare_preset()` setzt heute
(vor diesem Slice) *gar keinen* `X-GZ-Mail-Type`-Header — dieser wird nur im separaten,
älteren `src/app/cli.py:356`-Pfad gesetzt. `email_spec_validator.py::run_validation()` filtert
aktuell nicht nach `X-GZ-Mail-Type` (anders als `briefing_mail_validator.py`), sondern nimmt
immer die zuletzt zugestellte Mail — der neue `X-GZ-Compare-Hourly-Enabled`-Header funktioniert
davon unabhängig. Das Fehlen von `mail_type="compare"` im Dispatch-Pfad ist ein
vorbestehender, unabhängiger Zustand und wird hier nicht mitkorrigiert (siehe Known Limitations).

```python
# src/services/validator_render_service.py — render_compare_email_preview(),
# Parameter durchreichen (Anti-#954: Preview MUSS dasselbe Verhalten wie der
# echte Versand zeigen).
def render_compare_email_preview(body: Any) -> str:
    profile_enum = ActivityProfile(body.profile)
    target_date = date_type.fromisoformat(body.target_date)
    ...
    return render_compare_html(
        result,
        profile=profile_enum,
        hourly_enabled=body.hourly_enabled,   # NEU (Issue #1107)
    )
```

```python
# api/routers/validator.py — CompareEmailPreviewBody, neues optionales Feld
# mit Default True (rueckwaertskompatibel fuer bestehende Preview-Aufrufe
# ohne das Feld, z.B. CompareTabs.svelte vor einem Frontend-Update).
class CompareEmailPreviewBody(BaseModel):
    profile: str
    time_window: list[int] = Field(..., min_length=2, max_length=2)
    target_date: str
    winner_tags: list[WinnerTag] = []
    hourly_enabled: bool = True   # NEU (Issue #1107)
```

```python
# .claude/hooks/email_spec_validator.py — Refactor: gemeinsamer IMAP-Fetch
# fuer Body UND Header (bisher: fetch_latest_email() gibt NUR den Body-
# String zurueck, run_validation() liest KEINE Header). Oeffentlicher
# Vertrag von fetch_latest_email() bleibt UNVERAENDERT (Regressionsschutz
# fuer tests/tdd/test_issue_972_974_975_tooling.py::
# test_email_spec_validator_prefers_test_creds, das `isinstance(html, str)`
# prueft).

def _fetch_latest_message():
    """Gemeinsamer IMAP-Fetch: laedt die neueste Mail als geparstes
    email.message.Message (Body UND Header aus derselben IMAP-Runde,
    Issue #1107). Extrahiert aus der bisherigen fetch_latest_email()."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from app.config import Settings
    settings = Settings()
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")
    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    imap.login(imap_user, imap_pass)
    imap.select('INBOX')
    _, data = imap.search(None, 'ALL')
    all_ids = data[0].split()
    if not all_ids:
        raise ValueError("Keine E-Mails gefunden")
    _, msg_data = imap.fetch(all_ids[-1], '(RFC822)')
    msg = email.message_from_bytes(msg_data[0][1])
    imap.close()
    imap.logout()
    return msg


def _extract_html_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            return part.get_payload(decode=True).decode('utf-8')
    return ''


def fetch_latest_email() -> str:
    """Fetch latest sent email HTML body. Unveraenderter oeffentlicher Vertrag."""
    return _extract_html_body(_fetch_latest_message())
```

```python
# .claude/hooks/email_spec_validator.py — validate_structure() neuer
# optionaler Parameter, Default True erhaelt bestehendes Verhalten fuer
# ALLE existierenden Aufrufer/Tests (test_issue_1046_..., test_issue_1110_...,
# test_issue_1106_...), die validate_structure(html) einparametrig aufrufen.
def validate_structure(body: str, hourly_enabled: bool = True) -> List[str]:
    errors: List[str] = []
    rows = extract_table_rows(body)
    # ... (Uebersichtstabellen-Checks UNVERAENDERT) ...

    locations = extract_locations(body)
    if rows and not locations:
        errors.append("STRUKTUR: Keine Orte in der Uebersichtstabelle-Kopfzeile gefunden")

    # Issue #1107: bei abgeschalteter Stundenverlauf-Sektion entfaellt die
    # gesamte Pflicht-Pruefung (Tabellen-Vorhandensein, Spalten-Vertrag,
    # Cross-Location-Konsistenz) -- eine bewusst abgeschaltete Sektion darf
    # weder Tabellen enthalten noch ist ihr Fehlen ein Fehler.
    if hourly_enabled:
        occurrence_counts: dict = {}
        reference_cols: list | None = None
        reference_name: str | None = None
        for name in locations:
            # ... (UNVERAENDERTER Block, Zeile 255-292 im Bestand) ...
            pass

    score_match = _SCORE_WINNER_RE.search(body)
    if score_match:
        errors.append(...)
    return errors
```

```python
# .claude/hooks/email_spec_validator.py — run_validation() liest den neuen
# Header aus derselben Nachricht, aus der auch der Body extrahiert wird.
def run_validation(min_locations: int = 3) -> Tuple[bool, List[str]]:
    try:
        msg = _fetch_latest_message()
    except Exception as e:
        return False, [f"FEHLER: E-Mail konnte nicht geladen werden: {e}"]

    body = _extract_html_body(msg)
    # Fehlender Header (Alt-Mails vor diesem Feature) oder Wert != "false"
    # => True (bisheriges strenges Verhalten bleibt der sichere Default).
    hourly_enabled = msg.get("X-GZ-Compare-Hourly-Enabled") != "false"

    all_errors = []
    all_errors.extend(validate_structure(body, hourly_enabled=hourly_enabled))
    all_errors.extend(validate_location_count(body, min_locations))
    all_errors.extend(validate_plausibility(body))
    all_errors.extend(validate_format(body))
    all_errors.extend(validate_hourly_table(body))
    return len(all_errors) == 0, all_errors
```

**`validate_hourly_table()` bewusst unverändert:** Bei `hourly_enabled=False` existieren keine
Orts-Stundentabellen im HTML; `_find_location_hour_table()` liefert für jeden Ort `None`, die
Funktion überspringt diese Fälle bereits heute (`if table is None: continue`, Kommentar
"bereits von validate_structure() gemeldet") — ohne Fehler zu erzeugen. Kein Code-Edit nötig,
verifiziert durch AC-3-Test.

```typescript
// frontend/.../compareWizardState.svelte.ts — neuer State (Zeile ~40,
// direkt neben officialAlertsEnabled), Wiring in saveNewPreset() (Zeile
// 159-178, TOP-LEVEL wie official_alerts_enabled, NICHT display_config)
// und saveComparePreset() (Zeile 197-212, via CompareEditorEdits).
hourlyEnabled = $state(true); // Issue #1107: Stundenverlauf-Sektion ein/aus

// saveNewPreset() — payload-Objekt:
hourly_enabled: this.hourlyEnabled, // Issue #1107

// saveComparePreset() — edits-Objekt:
hourlyEnabled: this.hourlyEnabled, // Issue #1107
```

```typescript
// frontend/.../compareEditorSave.ts — CompareEditorEdits (analog
// officialAlertsEnabled, Zeile 26-27) + Round-Trip-Spread (analog Zeile
// 88-91, TOP-LEVEL Feld, NICHT displayConfig).
hourlyEnabled?: boolean; // Issue #1107

// buildComparePresetSavePayload() — body-Objekt:
...(edits.hourlyEnabled !== undefined
    ? { hourly_enabled: edits.hourlyEnabled }
    : {})
```

```typescript
// frontend/src/lib/types.ts — ComparePreset-Interface (Zeile 496, direkt
// nach official_alerts_enabled).
hourly_enabled?: boolean;  // Issue #1107 — Stundenverlauf-Sektion ein/aus
```

```typescript
// frontend/src/routes/compare/[id]/edit/+page.svelte — nach Zeile 36
// (officialAlertsEnabled-Hydration).
state.hourlyEnabled = data.preset.hourly_enabled ?? true; // Issue #1107
```

```svelte
<!-- frontend/.../steps/Step5Versand.svelte — neue ChannelToggle-Instanz
     im bestehenden Kanal-Bereich (nach der "Amtliche Warnungen"-Toggle,
     Zeile 135-142), gleiches Muster. -->
<div>
    <ChannelToggle
        label="Stundenverlauf"
        checked={state.hourlyEnabled}
        onchange={(checked) => (state.hourlyEnabled = checked)}
        testid="compare-step5-hourly-enabled-toggle"
    />
</div>
```

## Expected Behavior

- **Input:** `ComparePreset.hourly_enabled` (Bool oder fehlend/`null`).
- **Output:** Ist der Wert `false`, enthält die tatsächlich versendete Compare-Mail (HTML)
  weder den „STUNDEN"-Sektionskopf noch irgendeine Orts-Stundentabelle; `email_spec_validator.py`
  fordert diese Tabellen für diese Mail nicht ein (Exit 0 trotz Abwesenheit). Ist der Wert
  `true` oder fehlt er (Altdaten), ist das Verhalten identisch zu vor diesem Slice (Sektion
  sichtbar, Validator fordert pro gelistetem Ort eine vollständige Stundentabelle).
- **Side effects:** Bei `false` entfällt ausschließlich das HTML-Rendering der Sektion — kein
  Effekt auf Datenabruf (`ComparisonEngine.run()` holt weiterhin volle Stundendaten, da diese
  auch für Score/andere Zwecke benötigt werden könnten); reiner Rendering-Gate, kein
  struktureller Fetch-Skip wie bei #1040.

## Acceptance Criteria

- **AC-1:** Given ein `ComparisonResult` mit mindestens drei Orten und vollständigen
  Stundendaten, When `render_compare_html(result, hourly_enabled=False)` aufgerufen wird, Then
  enthält das zurückgegebene HTML weder den Sektionskopf „STUNDEN" noch einen „ORT
  <Ortsname>"-Marker für irgendeinen der Orte — die Übersichtstabelle bleibt vollständig
  vorhanden und unverändert.
  - Test: Echten `render_compare_html()`-Aufruf mit `hourly_enabled=False` gegen ein reales
    `ComparisonResult` (Offline-Fixture-Daten, kein Netzwerk) durchführen, HTML-String auf
    Abwesenheit von `"STUNDEN"` und `">ORT<"` prüfen sowie Anwesenheit der Übersichtstabelle
    (mind. eine Zeile mit „Amtliche Warnungen") verifizieren. Kein Dateiinhalt-Check gegen
    Quellcode — Beweis gegen den tatsächlich erzeugten HTML-String.

- **AC-2:** Given dasselbe `ComparisonResult`, When `render_compare_html(result,
  hourly_enabled=True)` bzw. ohne den Parameter (Default) aufgerufen wird, Then enthält das
  HTML den Sektionskopf „STUNDEN" und für jeden Ort einen eigenen „ORT <Ortsname>"-Block mit
  vollständiger Stundentabelle — identisch zum Verhalten vor diesem Slice (Regressionsschutz).
  - Test: Gleicher Aufbau wie AC-1, `hourly_enabled=True` und Default-Aufruf ohne den
    Parameter; Anwesenheit von „STUNDEN" und je einem „ORT"-Block pro Ort prüfen.

- **AC-3:** Given ein Compare-Preset mit `hourly_enabled=false`, When der Versand über
  `send_one_compare_preset()` real ausgelöst und die zugestellte Mail per IMAP aus
  `gregor-test@henemm.com` abgerufen wird, Then trägt die Mail den Header
  `X-GZ-Compare-Hourly-Enabled: false` und enthält keine Stundentabelle. Derselbe Ablauf mit
  `hourly_enabled=true` (bzw. ohne das Feld) zeigt weiterhin die vollständige
  Stundenverlauf-Sektion und trägt den Header `X-GZ-Compare-Hourly-Enabled: true`.
  - Test: Zwei reale Versände (einmal `hourly_enabled=false`, einmal `true`) gegen das
    Stalwart-Test-Postfach, jeweils IMAP-Fetch der zugestellten Mail, Header-Prüfung und
    HTML-Struktur-Prüfung (Sektion vorhanden/fehlt) direkt auf dem abgerufenen Body.

  **Scope-Korrektur (PO-'go' 2026-07-08):** Der ursprünglich hier vorgesehene Teil
  „`email_spec_validator.py` (`run_validation()`) meldet keinen Stundentabellen-bezogenen
  Fehler" ist **AUS DIESEM SLICE AUSGEKLAMMERT** — Validator-Dateien (`.claude/hooks/*`)
  dürfen laut Projektregel nicht im selben Workflow geändert werden, dessen Ergebnis sie
  prüfen sollen (Präzedenzfall #1110/#1108, Memory `feedback_validator_changes_own_workflow`).
  Diese Teilaufgabe ist als eigenes Folge-Issue **#1150** ausgelagert (eigene Spec, eigener
  Workflow, Gold-Standard-Test). Bis #1150 umgesetzt ist, funktioniert der Schalter
  vollständig (Header + Sektion korrekt), aber `email_spec_validator.py` würde eine
  `hourly_enabled=false`-Mail fälschlich als strukturell unvollständig melden — das ist eine
  bekannte, dokumentierte Einschränkung (siehe Known Limitations), keine offene Lücke in
  diesem Slice.

- **AC-4:** Given ein Compare-Preset mit `hourly_enabled=false`, When derselbe Vorschau-Aufruf
  über `POST /api/_validator/compare-email-preview` mit `hourly_enabled: false` im Body
  erfolgt, Then zeigt das zurückgegebene Vorschau-HTML dieselbe Abwesenheit der
  Stundenverlauf-Sektion wie die real versendete Mail aus AC-1/AC-3 — keine Divergenz zwischen
  Vorschau- und Versandpfad (Referenzfall #954).
  - Test: `render_compare_email_preview()` direkt mit einem `body`-Objekt aufrufen, das
    `hourly_enabled=False` trägt, HTML-String auf Abwesenheit von „STUNDEN"/„ORT"-Marker
    prüfen; zweiter Aufruf mit `hourly_enabled=True` (Default) zeigt die Sektion.

- **AC-5:** Given ein bestehendes, persistiertes Compare-Preset **ohne** das Feld
  `hourly_enabled` (simulierte Altdaten) für Nutzer A, When dieses Preset über `PUT
  /api/compare/presets/{id}` gespeichert wird, **ohne** dass der Request-Body das Feld
  `hourly_enabled` mitschickt (nur `name` wird geändert), Then bleibt `hourly_enabled` nach dem
  Speichern `nil`/nicht gesetzt (Handler übernimmt aus `original`), das tatsächliche
  Laufzeitverhalten interpretiert dies als `true` (Sektion sichtbar), und alle anderen,
  unveränderten Felder des Presets sind byte-identisch zum Zustand vor dem Save. Derselbe
  Testablauf wird zusätzlich für Nutzer B mit einem eigenen, unabhängigen Preset (mit explizit
  gesetztem `hourly_enabled=false`) wiederholt, um zu beweisen, dass das Update von Nutzer A's
  Preset Nutzer B's Preset nicht berührt.
  - Test: Über den Go-Handler `UpdateComparePresetHandler` (echter HTTP-Request gegen
    `internal/store`, `t.TempDir()`) ein Preset ohne `hourly_enabled` anlegen, PUT mit
    geändertem `name` und ohne das Feld senden, danach das gespeicherte Preset laden und
    `HourlyEnabled == nil` sowie Unverändertheit der übrigen Felder prüfen. Parallel ein
    zweites Preset für einen anderen `user_id` mit `HourlyEnabled=false` anlegen, Update auf
    Nutzer A durchführen, danach verifizieren, dass Nutzer B's Preset (Name, `HourlyEnabled`,
    `LocationIDs`, `Empfaenger`) unverändert bleibt (Muster:
    `TestUpdateComparePreset_OfficialAlertsEnabledCrossUserIsolation`).

- **AC-6:** Given ein Nutzer hat im Compare-Editor (Step 5 „Kanäle") den Toggle
  „Stundenverlauf" auf aus gestellt, When er ein bestehendes Preset speichert
  (`saveComparePreset()` → `buildComparePresetSavePayload()`), Then enthält der resultierende
  PUT-Payload `hourly_enabled: false`, während alle anderen, nicht angefassten Felder des
  Original-Presets (Empfänger, Zeitfenster, `display_config`) byte-identisch erhalten bleiben
  (Round-Trip-Beweis auf Client-Ebene).
  - Test: Pure-Function-Test (Node, kein Browser, Muster `compareEditorForecastHours.test.ts`):
    `buildComparePresetSavePayload()` mit `edits.hourlyEnabled=false` gegen ein
    `original`-Preset mit mehreren befüllten Feldern aufrufen, `body.hourly_enabled === false`
    und Unverändertheit der übrigen Felder prüfen. Zweiter Fall: `edits.hourlyEnabled`
    `undefined` → `body.hourly_enabled` bleibt aus dem `original`-Spread erhalten (kein
    versehentliches Überschreiben).

## Out of Scope

- **`show_winner`/`show_tags` (aus der ursprünglichen Issue-Beschreibung #1107):** Referenzieren
  Score/Winner/Tags-Konzepte, die #1110 bereits aus dem v2-Layout entfernt hat — es gibt nichts
  mehr, das diese Toggles an-/abschalten könnten. Nicht implementiert.
- **`show_alerts`:** Bereits vollständig durch #1040 (`official_alerts_enabled`) gelöst — ein
  zweiter, redundanter Toggle für dieselbe Sektion würde zwei Wege zum selben Ergebnis schaffen
  und Nutzer verwirren. Nicht implementiert.
- **Übersichtstabelle/„Matrix" abschaltbar:** Bewusst nicht umgesetzt — sie ist der Kerninhalt
  der Compare-Mail; ohne sie bliebe fast nichts übrig, das die Mail noch nützlich macht.
- **`run_comparison_for_subscription()`-Legacy-Pfad:** Der ältere Subscription-Versandpfad
  (`compare_subscription.py`) wird nicht auf `hourly_enabled` umgestellt — er trägt bereits die
  #1104/#1106-Logik nicht und bleibt konsistent zurück. Pfad-Konsolidierung ist ein separates
  Folge-Issue, kein Teil dieses Slices.
- **Klartext-Renderer-Steuerung (`render_comparison_text()`):** Keine eigene
  `hourly_enabled`-Filterung für den Plain-Text-Teil der Mail. Der Text-Pfad hat unabhängig
  davon bereits keinen `enabled_metrics`-Parameter (separates Issue #1125) — eine
  `hourly_enabled`-Ergänzung nur für dieses Slice würde die bestehende Text/HTML-Inkonsistenz
  um eine weitere Dimension vergrößern statt sie zu lösen.
- **Granulare Pro-Ort-Steuerung:** Der Toggle schaltet den Stundenverlauf für ALLE verglichenen
  Orte gemeinsam ein/aus, keine Auswahl einzelner Orte (analog zur Alles-oder-nichts-Grenze von
  `official_alerts_enabled` in #1040).

## Known Limitations

- **`email_spec_validator.py` bleibt in diesem Slice unverändert (ausgelagert nach #1150):**
  Bis Folge-Issue #1150 umgesetzt ist, meldet der Validator eine Mail mit
  `hourly_enabled=false` fälschlich als strukturell unvollständig (fehlende Stundentabelle).
  Der Schalter selbst funktioniert vollständig unabhängig davon (Header, Rendering, Speichern,
  UI) — betroffen ist ausschließlich der automatisierte Post-Send-Validierungsschritt.
- **`run_comparison_for_subscription()`-Legacy-Pfad (`compare_subscription.py`) bewusst
  unverändert:** Wie bereits bei #1104/#1106 dokumentiert, liest dieser ältere
  Subscription-Versandpfad kein `display_config`/Preset-Top-Level-Feld für diese Zwecke; eine
  Konfigurierbarkeit dort müsste separat spezifiziert werden. Folge-Issue wird nach Abschluss
  dieses Workflows angelegt (Pfad-Konsolidierung, nicht Teil dieses Slices).
- **`show_winner`/`show_tags` nicht implementiert:** Referenzieren Score/Winner/Tags-Konzepte,
  die #1110 aus dem v2-Layout bereits entfernt hat — obsolet.
- **`show_alerts` nicht implementiert:** Bereits durch #1040 (`official_alerts_enabled`) gelöst
  — ein zweiter, redundanter Toggle für dieselbe Sektion wäre verwirrend.
- **Übersichtstabelle/Matrix bewusst NICHT abschaltbar:** Kerninhalt der Mail — ohne sie bliebe
  fast nichts übrig, das die Compare-Mail noch nützlich macht.
- **Klartext-Renderer (`render_comparison_text()`) unverändert:** Der Text-Pfad hat aktuell
  ohnehin keinen `enabled_metrics`-Parameter (Issue #1125, separat) und wird hier nicht mit
  einer eigenen `hourly_enabled`-Logik nachgerüstet — Scope-Konsistenz mit dem bereits
  bekannten Nebenpfad-Rückstand.
- **`email_spec_validator.py` prüft nur die zuletzt zugestellte Mail:** Vorbestehende
  Einschränkung (kein `X-GZ-Mail-Type`-Filter wie bei `briefing_mail_validator.py`); bei
  parallelen Sends während der E2E-Verifikation kann die falsche Mail geprüft werden. Nicht
  durch dieses Slice verursacht, wird hier nicht behoben.
- **Kein `mail_type="compare"`-Header im Dispatch-Pfad:** Vorbestehender Zustand (nur
  `src/app/cli.py` setzt ihn), unabhängig vom neuen `X-GZ-Compare-Hourly-Enabled`-Header
  funktionsfähig, wird hier nicht nachgerüstet (kein direkter Bezug zu diesem Slice).
- **`CompareEditor.svelte` unverändert:** Entgegen der ursprünglichen Analyse-Annahme
  (Kontext-Dokument) ist keine Änderung an dieser Datei nötig — die Bindung läuft
  ausschließlich über `CompareWizardState`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Zwei additive, bereits etablierte Muster werden kombiniert, keines davon ist
  neu: (1) Pointer-Pattern-Feld auf `ComparePreset` (identisch zu `Weekday *int`,
  `OfficialAlertsEnabled *bool`, ADR-frei laut #1040-Spec), (2) optionaler Marker-Header nach
  dem exakten Vorbild `X-GZ-Mail-Type`/`X-GZ-Format` (bereits in
  `docs/reference/renderer_email_spec.md` als Konvention dokumentiert — ein dritter Header
  dieser Familie ist eine Anwendung der bestehenden Konvention, keine neue
  Architekturentscheidung). Die Validator-Erweiterung (`validate_structure(hourly_enabled=)`)
  ist eine rückwärtskompatible Parametererweiterung einer bestehenden Funktion, kein neuer
  Mechanismus.

## Changelog

- 2026-07-08: Initial spec created (Issue #1107, letzter Teil-Slice von #1094/#1092 Teil D).
