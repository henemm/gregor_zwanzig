# Context: fix-952-onset-alert-fidelity

## Request Summary

Issue #952 (reopened 2026-07-02): Radar-/Onset-Alerts („Regen in X Min") weichen in E-Mail
und Telegram weiterhin deutlich von der Claude-Design-Vorlage ab. Der PO fordert: das
Claude-Design-Projekt via `claude_design` MCP importieren und
`Gregor 20 - Alert Mail Vorschläge.html` 1:1 implementieren. Zusätzlich (PO-Recherche,
Scope-Entscheidung Intake): der fehlende SMS-Versand im Radar-Pfad (`check_radar_alerts`)
kommt mit in den Scope.

## Zentrale Diagnose (Intake, code-verifiziert)

Die #952/#957-Fixes sind deployed (Commits `3a20502b`, `bdfcd5c9` in Prod-/Staging-HEAD).
Aber: Der kanonische Alert-Renderer hat **zwei Zweige** — Deviation und Onset
(Verzweigung über `msg.source is not None`). Nur der Deviation-Zweig wurde auf
Design-Tokens/Vorlagen-Struktur gebracht. Die IST-Screenshots des PO sind Onset-Alerts.

### Befunde Onset-Zweig (IST-Screenshots + Code)

1. **E-Mail ungebrandet:** `_render_email_onset()` (`src/output/renderers/alert/render.py:69-92`)
   baut Ad-hoc-HTML (`font-family:sans-serif`, `#555`) ohne `design_tokens.py` — im
   Gegensatz zum Deviation-Zweig (`render_email`, Z. 185-244: FONT_UI/FONT_DATA, G_*-Farben,
   Verdikt-Badge, umrandeter Datenblock).
2. **Float-Rauschen:** `_render_email_onset` und `_render_telegram_onset` interpolieren
   `e.km_from`/`e.km_to` roh → „km 9.8–15.200000000000001". Der Betreff (`_render_subject_onset`,
   Z. 65) castet dagegen `int()` → Inkonsistenz Betreff vs. Body. Deviation-Zweig hat
   `_km_str()` mit `int(round())`.
3. **Doppelte Zeit + verirrter Punkt:** `check_radar_alerts` (`src/services/trip_alert.py:793-797`)
   setzt `intensity_label = format_now_text(...)` — ein ganzer Satz inkl. „ab ca. 13:10
   (in ~10 Min)." plus Suffix „, im Briefing nicht angekündigt". Der Renderer hängt dann
   selbst „ab {onset_time}" an (render.py:73) → „…ab ca. 13:10 (in ~10 Min)., im Briefing
   nicht angekündigt ab 13:10". SOLL laut Spec/Design: kurzes Label „leichter Regen".
4. **Telegram roh:** `TelegramOutput.send()` (`src/outputs/telegram.py:67,72`) stellt
   `[{subject}]\n\n` voran und sendet OHNE `parse_mode` → `**…**` erscheint wörtlich,
   Betreff wird dupliziert. SOLL: fette erste Zeile, keine Betreff-Zeile.
   **Achtung:** betrifft auch den Deviation-Zweig (render_telegram nutzt ebenfalls `**`).
5. **SMS-Versand fehlt im Radar-Pfad:** `check_radar_alerts` (trip_alert.py:654-845)
   versendet nur E-Mail + Telegram. `_render_sms_onset` (R!/TH!-Token) existiert und ist
   getestet, wird aber nie versendet. Deviation-Pfad `_send_alert` (trip_alert.py:955-996)
   hat den SMS-Ast bereits (SMSOutput, Issue #914 Slice 4) → Vorbild.

### Design-Vorlage: Repo-Version veraltet

`docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html`
(19 KB) enthält **keine Onset-Variante** (kein „Regen in X Min"). Das aktuelle SOLL liegt
im Claude-Design-Projekt:
`https://claude.ai/design/p/019dfcf4-1e69-73f2-b094-c19e157014a2?file=Gregor+20+-+Alert+Mail+Vorschläge.html`
→ Import via `claude_design` MCP (`https://api.anthropic.com/v1/design/mcp`, Auth via
`/design-login`) ist Pflichtschritt VOR der Spec (PO-Anweisung im Issue-Kommentar
2026-07-02). Regel: JSX/Vorlage ist die Wahrheit, Struktur 1:1 übernehmen, keine Prosa-Annäherung.

### SOLL laut PO-Screenshots (Issue-Kommentare 2026-07-02)

- **E-Mail (Deviation-Beispiel als Referenz-Optik):** Badge „↑ 3 SCHWELLEN ÜBERSCHRITTEN",
  großer H1, umrandeter Datenblock mit Zeilen (Label links, Mono-Werte rechts,
  „über"-Badges), Fußzeile „Stand: … · verglichen mit dem letzten Briefing · km 0–4".
- **Telegram (Onset):** `GR20 · km 5–18 · Regen in 12 Min` **fett** (gerendert, nicht
  `**`-Literale), zweite Zeile `14:35 · leichter Regen · Radar (DWD)`. Keine
  `[Betreff]`-Zeile davor.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py` | Kanonischer Renderer; Onset-Funktionen `_render_subject_onset`/`_render_email_onset`/`_render_telegram_onset`/`_render_sms_onset` = Hauptbaustelle |
| `src/output/renderers/alert/model.py` | `AlertMessage`, `OnsetEvent`, Helper (`km_span`, `severity`, …) |
| `src/services/trip_alert.py` | `check_radar_alerts` (Z. 654-845): baut OnsetEvent/AlertMessage, `intensity_label`-Fehlbefüllung, fehlender SMS-Ast; `_send_alert` (Deviation) als SMS-Vorbild |
| `src/services/radar_service.py` | `format_now_text` (Satz-Format), `source_label`; ggf. neues kurzes Intensitäts-Label nötig |
| `src/outputs/telegram.py` | `send()`: `[subject]`-Präfix + fehlender `parse_mode` — Änderung betrifft ALLE Telegram-Caller (Briefings, Bot) → rückwärtskompatibel gestalten (optionaler Parameter) |
| `src/outputs/sms.py` | `SMSOutput.send()` — für SMS-Ast im Radar-Pfad |
| `src/output/renderers/email/design_tokens.py` | Marken-Tokens (G_*, FONT_UI/FONT_DATA) — im Onset-E-Mail-HTML anzubinden |
| `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html` | Repo-Kopie der Vorlage — VERALTET (keine Onset-Variante), via Design-MCP zu aktualisieren |
| `tests/tdd/test_952_alert_mail_design_fidelity.py` | Bestehende Fidelity-Tests (Deviation) — nicht brechen |
| `tests/tdd/test_957_alert_mail_literal_structure.py` | Literal-Struktur-Tests Deviation-Mail |
| `tests/tdd/test_914_slice4_alert_sms_dispatch.py` | SMS-Dispatch-Tests Deviation — Vorbild für Radar-SMS-Tests |
| `tests/tdd/test_issue_919_*` / Radar-Tests | Bestehende Onset-Renderer-Tests — Format-Assertions werden sich ändern |

## Existing Patterns

- **Deviation-E-Mail** (`render_email`, render.py:185-244): design_tokens-Import, Verdikt-Badge
  (inline-block, border-radius, G_DANGER/G_SUCCESS), Datenblock-Zeilen mit `FONT_DATA`,
  Fußzeile `G_INK_MUTED` — dieselbe Mechanik für Onset übernehmen.
- **km-Formatierung:** `_km_str()`/`_km_str_events()` mit `int(round())` — für Onset nachziehen
  (Issue #931 „inkonsistente km-Rundung" ist verwandt/offen!).
- **SMS-Dispatch:** `_send_alert`-SMS-Ast (trip_alert.py:989-996) mit `can_send_sms()`-Guard.
- **Marker-Header:** E-Mail-Versand nutzt `mail_type="radar-alert"` bzw. `"deviation-alert"`.

## Dependencies

- **Upstream:** `metric_catalog` (Labels/Rundung — Onset nutzt es kaum), `design_tokens.py`,
  `radar_service` (NowcastResult, Quellen-Labels: BrightSky/RADOLAN DE, GeoSphere INCA AT,
  Open-Meteo minutely_15 Fallback — Spec `radar_nowcast.md`/#656).
- **Downstream:** `check_radar_alerts`-Scheduler (Prod), Alert-Preview-Endpoint (#918,
  4 Kanäle), Telegram-Bot/Briefing-Versand (bei `TelegramOutput.send`-Änderung!),
  `briefing_mail_validator`/`email_spec_validator` (greifen NICHT für Alerts —
  Verifikation muss über echte Staging-Zustellung laufen).

## Existing Specs

- `docs/specs/modules/issue_919_radar_alert_canonical.md` — Onset-Integration in kanonisches Schema (Formate: Betreff/E-Mail/Telegram/SMS-Token R!/TH!; SMS-Versand dort als Folge-Issue markiert)
- `docs/specs/modules/issue_917_alert_renderer.md` — kanonisches Renderer-Schema (#914/ADR-0011)
- `docs/specs/modules/radar_nowcast.md` (#656) — Quellen-Wahl je Koordinate
- `docs/specs/modules/issue_818_radar_briefing_integration.md`, `issue_883_acute_danger_override.md`, `issue_830_radar_alert_validator.md` — Umfeld

## Risks & Considerations

- **Regression Deviation-Zweig:** frisch repariert (#952/#957) — Tests test_952/test_957
  müssen grün bleiben; Adversary muss BEIDE Zweige prüfen.
- **`TelegramOutput.send`-Änderung strahlt auf alle Caller** (Briefings, Bot-Antworten) —
  rückwärtskompatible Signatur (z.B. `parse_mode=None`-Default, Opt-in ohne Subject-Präfix).
- **Verifikationslücke = Teil des Problems:** Onset-Alerts sind auf Staging schwer
  auszulösen (echtes Radar-Ereignis nötig). Bisherige „verifiziert"-Aussagen liefen über
  den Deviation-Preview. Die Spec muss einen realistischen E2E-Weg für den Onset-Pfad
  definieren (z.B. Preview-Endpoint #918 mit Onset-Beispiel + echte Staging-Zustellung
  an gregor-test@henemm.com).
- **Design-Import zuerst:** Ohne aktuelles Design-Projekt (Onset-Varianten) keine Spec —
  Reihenfolge: MCP-Import → Vorlage ins Repo → Spec mit Zeilennummern-Referenzen
  (Memory-Regel: „Struktur 1:1, nicht Prosa").
- **Offenes verwandtes Issue #931** (km-Rundung inkonsistent) wird durch die km-Fixes
  hier voraussichtlich miterledigt → beim Abschluss prüfen/schließen.
- **Issue #954** (Telegram-Fußzeile/SMS-Preview veraltet) grenzt an, ist aber eigener Scope.

## Scope-Entscheidung (Intake, PO abwesend — nach Regelwerk entschieden)

- Track: **Full Process** (Score 5: Scope 1, Blast 2, Unsicherheit 2)
- SMS-Versand im Radar-Pfad: **im Scope** (Bündel-Regel)

## Analysis

### Type
Bug (Design-Fidelity-Abweichung + fehlender Versandpfad). Challenger-Verdict: **CONFIRMED**
(alle 5 Befunde code-verifiziert; `_render_email_onset` ist die EINZIGE Onset-Mail-Quelle,
`src/outputs/radar_alert.py` wurde bei #919 gelöscht — kein zweiter Codepfad).

### Design-SOLL importiert (2026-07-02)
Aktuelle Vorlage via Design-MCP geholt und ins Repo geschrieben
(`docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html`,
+89 Zeilen, 0 Löschungen — Onset-Sektion ist reiner Zuwachs, Deviation-SOLL unverändert).
Onset-SOLL (Zeilen ~370-455 der Vorlage):
- **E-Mail:** Verdikt-Badge accent-getönt (`Radar-Nowcast …`), H1 `Regen in 12 Min`,
  umrandeter Datenblock mit 3 Zeilen: `Wo & wann → km 5–18 · ab 14:35` (mono) /
  `Intensität → leichter Regen` / `Quelle → Radar (DWD)`, Cooldown-Box mit Accent-Border
  (`Cooldown: Du erhältst diese Warnung höchstens einmal in 2 Stunden.`),
  Fußzeile `Stand: heute 14:23 · Quelle: Radar (DWD)`.
- **Telegram:** fette erste Zeile `GR20 · km 5–18 · Regen in 12 Min`, zweite Zeile
  `14:35 · leichter Regen · Radar (DWD)`. KEINE `[Betreff]`-Zeile.
- **SMS:** `GR20 km5-18: R!12` bzw. `TH!8` (GSM-7, `!` = Onset-Marker, Überlauf `+k`).
- Offene Formulierungsfrage für PO: Badge-Text der Vorlage lautet wörtlich
  `Radar-Nowcast · kein Δ, kein Pfeil` — Anteil „kein Δ, kein Pfeil" wirkt wie
  Design-Doc-Annotation; Vorschlag: Badge = `Radar-Nowcast`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/render.py` | MODIFY | Onset-E-Mail auf Design-Tokens/Datenblock (Vorbild Z.185-244); km `int(round())` in Onset-Body/Telegram; Telegram beide Zweige auf `<b>`-HTML statt `**` |
| `src/services/trip_alert.py` | MODIFY | `intensity_label`-Fix: `result.intensity_label` direkt nutzen statt `format_now_text`-Satz (Z.793-797, Ein-Zeilen-Datenflussfix); SMS-Ast in `check_radar_alerts` analog `_send_alert` Z.989-995; `can_*`-Gate Z.766-770 um SMS erweitern |
| `src/outputs/telegram.py` | MODIFY | `send()` rückwärtskompatibel: optionale Parameter `parse_mode=None`, `suppress_subject_line=False` (Default = exakt heutiges Verhalten; 8 Bestands-Caller unberührt) |
| `api/routers/validator.py` | MODIFY | Alert-Preview (#918) um Onset-Zweig erweitern — aktuell existiert KEIN Codepfad, der eine Onset-AlertMessage synthetisch erzeugt (Preview baut nur Deviation via `to_alert_message`) |
| `tests/tdd/test_919_*` etc. | MODIFY | Format-Assertions an neues SOLL anpassen |
| `tests/tdd/` (neu) | CREATE | Zweig-Paritätstest (source=None UND source=<str> parametrisiert); SMS-Dispatch-Test analog test_914_slice4; Fake-Radar-Seam-E2E (rot vor Fix) |

### Scope Assessment
- Files: ~6 · Estimated LoC: +150/−40 (Limit 250 reicht, knapp) · Risk Level: MEDIUM-HIGH

### Technical Approach (Plan-Agent, Sonnet)
1. **Telegram parse_mode = HTML, nicht MarkdownV2** — MarkdownV2 hat 18 escape-pflichtige
   Zeichen (Trip-Namen mit `.`/`-`/`(` → 400-Fehler der Bot-API); HTML braucht nur `<>&`,
   die vorhandene `_esc()` ist wiederverwendbar. Renderer liefert `<b>…</b>`.
   Deviation-Telegram im selben Zug mitziehen (nutzt ebenfalls `**`).
2. **intensity_label:** `NowcastResult.intensity_label` (radar_service.py:59-63) enthält
   bereits das kurze Label („leichter Regen") und wird heute verworfen — kein
   radar_service-Umbau nötig.
3. **Float-Rauschen-Ursprung** liegt in `trip_segments.py:150,156` (kumulative
   Float-Addition) — Fix bewusst als `int(round())` im Renderer, NICHT als Versuch,
   die Float-Quelle zu „reparieren".
4. **SMS im Radar-Pfad** war dokumentierte Slice-Entscheidung (#919 „Known Limitations"),
   Wording „wird nachgezogen".

### E2E-Verifikationsweg (Kernentscheidung)
- **Option A (Format-Iteration):** Preview-Endpoint-Erweiterung um Onset → alle 4
  Kanaltexte ohne Versand; Fidelity-Vergleich gegen Vorlage.
- **Option B (Pflicht-Beweis):** Fake-Radar-Seam über vorhandenes `_get_radar_service()`
  — echte Subklasse (KEIN `Mock()`/`patch()`) liefert garantiert-nasses `NowcastResult`,
  ab da läuft die reale Kette (Renderer→EmailOutput→SMTP→gregor-test@henemm.com IMAP-Beweis,
  TelegramOutput→echter Staging-Bot). Konsistent mit Mock-Verbot (nur Transport/API tabu;
  nicht-triggerbare Wetterquelle via Seam ersetzen ist der einzige praktikable Weg,
  Vorbild test_773_alert_e2e).
- Beide zusammen in die Spec; B ist der Rot-vor-Fix/Grün-nach-Fix-Beweis.

### Dependencies
8 `TelegramOutput.send`-Caller: trip_alert.py ×2 (Onset Z.840, Deviation Z.981),
trip_report_scheduler.py (Briefings), inbound_telegram_reader.py ×5 (Bot-Antworten) —
alle ohne parse_mode; optionale Parameter mit altem Default halten sie unberührt.

### Open Questions
- [ ] Badge-Text Onset-Mail: wörtlich `Radar-Nowcast · kein Δ, kein Pfeil` oder nur
      `Radar-Nowcast`? (Vorlagen-Text wirkt teils wie Annotation → PO bei Spec-Freigabe)
- [ ] Verbleib der Briefing-Kontext-Info („im Briefing nicht angekündigt"/„jetzt akut"):
      Design-Vorlage hat dafür KEINEN Platz vorgesehen — als 4. Datenblock-Zeile
      aufnehmen oder weglassen? (PO bei Spec-Freigabe)
