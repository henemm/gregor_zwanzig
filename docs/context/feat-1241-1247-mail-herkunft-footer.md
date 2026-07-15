# Context: Mail-Herkunft-Footer (#1241) + Date-Header (#1247)

## Request Summary
Jede versendete Gregor-Mail bekommt (A) eine dezente Herkunfts-Fußzeile
„Mail-Art · Renderer · Commit-Stand" aus **einem geteilten Baustein** (keine Kopie
pro Renderer) und (B) einen RFC-5322-`Date`-Header im MIME-Envelope.

## Related Files

### Versand-Kern (beide Issues)
| Datei | Relevanz |
|------|-----------|
| `src/output/channels/email.py:237` `build_mime_message` | Nutzt `MIMEMultipart`/`MIMEText`. Setzt heute From/To/Subject/Reply-To/X-GZ-*. **KEIN `Date`-Header** → #1247. HTML-Zweig `:262-273`, Plain-Zweig `:287-298`. Einfügepunkt Date: nach `msg["To"]` in **beiden** Zweigen. |

### Mail-Renderer (Footer #1241 — heute je Renderer inline, KEIN geteilter Baustein)
| Mail-Art | Renderer:Funktion | Heutiger Footer |
|---|---|---|
| Trip-Briefing full (HTML) | `email/html.py:751` `render_html` | `_render_footer` `html.py:383`, eingehängt `:1559`; Brand-Zeile + `date · provider · model` (`:400-411`) |
| Trip-Briefing full (Plain) | `email/plain.py:72` `render_plain` | inline `plain.py:282-291` (`---`, `Generated:`, `Data:`) |
| Trip-Briefing compact | `email/compact.py:83` `render_compact` | inline `compact.py:193-197`; **ASCII-garantiert** |
| Ortsvergleichs-Briefing | `email/compare_html.py:776` `render_compare_html` | `_render_app_footer` `:748` + `_render_abo_footer` `:725` |
| Abweichungs-Alarm | `alert/render.py:372` `render_email` (+ Legacy `:551`) | `Stand: heute …` `render.py:386/426` |
| Radar-Onset-Alarm | `alert/render.py:190/136` (via `render_email`) | `Stand: heute …` `render.py:156/211` |
| Amtliche Warnung standalone | `alert/official_alerts.py:1048` `render_official_alert_html` (Plain `:213`) | `Stand: heute … · abgerufen bei …` `:1094-1098` |
| Amtliche Warnung embedded | `alert/official_alerts.py:1138` `_render_warn_block_embedded` / `:1291` | nur Quelle-Box, kein Herkunfts-Footer |

Orchestrator Trip-Mail: `email/__init__.py:32` `render_email` (compact vs. full+plain).

### Validatoren & Gate (dürfen nicht kippen)
| Datei | Relevanz |
|------|-----------|
| `.claude/hooks/briefing_mail_validator.py` | COMPACT-**ASCII-Check** `:449-450` (hartes Risiko), Byte-Limit 2048 `:454-456`, `HH:00`-Zeilenanfang-Heuristik `:458`. Kein Zeilen-/Ende-Check. |
| `.claude/hooks/email_spec_validator.py` | Nur HTML-Tabellen; Score/Winner-Regex `:214-217` (weiches Risiko bei Renderer-Namen). |
| `.claude/hooks/official_alert_mail_validator.py` | CSS-Klassen + Textbausteine; `Gültig:`-Regex `:187`, `Stand: heute` `:202`. Kein Ende-Check. |
| `.claude/hooks/renderer_mail_gate.py` | #811-Gate. Trigger-Pfade `:42-48`: `renderers/email/*.py`, `channels/email.py`, `renderers/alert/*.py`. **`channels/email.py` (B) triggert Briefing-Kategorie** → Matrix-Hash + frischer `briefing_mail_validator` + Golden-Email-Tests nötig. Alert-Renderer → radar/official-Validator zusätzlich. |

## Existing Patterns
- **SSoT-Helper-Muster**: `email/helpers.py:338` `format_units_legend` ist geteilte Quelle für die Legende → Vorbild für einen neuen `build_origin_footer(...)` in `email/helpers.py`.
- **profile_signature.py** (`:95`): geteilter Baustein, aber für Profil-**Branding** (accent/icon/eyebrow), NICHT für Herkunft. Als Muster tauglich, inhaltlich falscher Ort.
- **Date-Format**: RFC 2822 via `email.utils.formatdate(localtime=True)`.

## Dependencies
- Upstream: X-GZ-Mail-Type-Werte kommen von den Callern (`notification_service.py`, `scheduler_dispatch_service.py`, `radar_alert_service.py`). Werte: `trip-briefing`(+`X-GZ-Format` full/compact), `compare`, `official-alert`, `radar-alert`, `deviation-alert` → **Footer-Klartext-Labels aus dieser fixen Menge ableiten** (Konsistenz Header↔Footer).
- Downstream: alle drei Mail-Validatoren + Golden-Email-Tests + Gate #811.

## Existing Specs
- `docs/reference/mail_validators.md` — Validator-Schwellen/Anti-Stale.
- CLAUDE.md „Mail-Validatoren & Renderer-Gate" — Dispatch-Regeln.

## Risks & Considerations
1. **COMPACT-ASCII-Falle (hart):** Trennzeichen `·` (U+00B7) bricht `briefing_mail_validator._check_compact` → Compact-Mail scheitert. Footer im Compact-Pfad braucht ASCII-Trenner (`|` / ` - `).
2. **Byte-Limit Compact 2048:** zusätzliche Footer-Zeile kann knappe Compact-Mails über die Grenze drücken.
3. **Commit-Stand existiert nicht:** keinerlei Laufzeit-Git/Version-Mechanismus in `src/`. Muss neu gebaut werden (z.B. `git rev-parse --short HEAD` gecached, oder Deploy-Stamp-File) — Analyse-Entscheidung.
4. **Hook-Entscheidung (zentrale Analyse-Frage):** geteilter Helper pro Renderer (sauber, Design-Tokens, Issue-konform „ein Baustein") **vs.** MIME-Ebene in `build_mime_message` (wirklich jede Mail an einer Stelle, aber roh/stillos). Issue #1241 fordert explizit den geteilten Baustein → Helper, pro Renderer aufgerufen; „jede Mail" = die aufgezählten Arten abdecken.
5. **Gate #811 zieht mehrere Kategorien:** Änderungen an `channels/email.py` + email-Renderern (Briefing) UND `alert/*` (radar/official) → alle betroffenen Validator-Läufe frisch grün nötig.
6. **Embedded Warn-Block** hat heute keinen Herkunfts-Footer — klären, ob embedded eine eigene Zeile bekommt oder die Wirts-Mail sie trägt.
7. **Test-Mails**: kein eigener Renderer; laufen über dieselben Render-Pfade (`preview_service.py`/`notification_service.py`) → Footer erbt automatisch, aber Label „Test" ggf. gewünscht.

## Analysis

### Type
Feature (#1241) + kleiner Bug (#1247), gebündelt.

### Entscheidungen (aus strategischer Bewertung)
1. **Einhängepunkt:** geteilter Helper `build_origin_footer(...) -> OriginFooter(.line1/.line2)` in `email/helpers.py` (Vorbild `format_units_legend`/`ProfileSignature`), plus zwei dünne Renderfunktionen `render_origin_footer_html` (Design-Tokens) und `render_origin_footer_text` (` · `-join). Pro Renderer aufgerufen. **NICHT** MIME-Ebene (Issue-Vorgabe + HTML würde brechen).
2. **ASCII-Compact — schon gelöst:** `compact.py:44-48` `_ascii()` faltet `·`→`-` über den gesamten Body am Ende (`compact.py:83` `return _ascii(body)`). Footer VOR diesem Call einfügen → Compact-Validator bleibt grün, keine Sonderbehandlung. Footer kurz halten (Byte-Limit 2048).
3. **Commit-Stand:** `git rev-parse --short HEAD` per subprocess, **einmal beim Modul-Import gecached**, `try/except`→`"unknown"`. Prod läuft aus echtem Git-Checkout (`deploy-gregor-prod.sh:114` `git reset --hard origin/main`), `.git` immer da. NICHT `.claude/last_prod_deploy.json` (falsche Schicht-Grenze), NICHT ENV-Var.
4. **Label-Ableitung:** zentrales Dict `(mail_type, mail_format) -> Klartext` in `helpers.py`.
5. **Kontext-Lücke official-alert:** `mail_type="official-alert"` wird aus Trip- (`notification_service.py:530`) UND Compare-Kontext (`:641`) mit identischem Header gesendet. „Ortsvergleich · Amtliche Warnung" braucht deshalb einen **zusätzlichen `context_label`-Parameter**, durchgereicht: `notification_service.py` (2 Aufrufer) → `render_warn_block(context_label=...)` (`official_alerts.py:1148`) → `render_official_alert_html(...)` (`:1048`) → Helper.
6. **Embedded Warn-Block:** keine eigene Footer-Zeile (Wirts-Mail trägt Herkunft). **Test-Mails:** kein „Test"-Label (Scope-Erweiterung, ausgeklammert).

### Affected Files
| File | Change | LoC grob |
|------|--------|----------|
| `src/output/renderers/email/helpers.py` | MODIFY (Helper + Mapping + `_deployed_commit()` + HTML/Text-Render) | +70..100 |
| `src/output/renderers/email/html.py` | MODIFY (`_render_footer` `:383`) | +5..10 |
| `src/output/renderers/email/plain.py` | MODIFY (`:282`) | +3..6 |
| `src/output/renderers/email/compact.py` | MODIFY (`:193`) | +3..6 |
| `src/output/renderers/email/compare_html.py` | MODIFY (`_render_app_footer` `:748`) | +5..10 |
| `src/output/renderers/alert/render.py` | MODIFY (radar/deviation, html+plain) | +8..15 |
| `src/output/renderers/alert/official_alerts.py` | MODIFY (+ `context_label`-Plumbing) | +15..25 |
| `src/services/notification_service.py` | MODIFY (`:530`,`:641` context threaden) | +2..4 |
| `src/output/channels/email.py` | MODIFY (`Date`-Header #1247, beide Zweige) | +2..3 |
| Tests (Golden-Email, #811-Matrix, Helper-Units) | MODIFY/CREATE | +40..80 |

### Scope Assessment
- Dateien: 9 MODIFY + Tests
- LoC: ~155–260 Code, mit Tests **über 250** → **LoC-Limit gefährdet** (Entscheidung Override vs. Slice offen)
- Risiko: MEDIUM (zentraler SSoT, Gate #811 zieht Briefing+Radar+Official, `context_label`-Kette)

### Reihenfolge
1. #1247 Date-Header isoliert (Gate klein halten) → 2. Helper+Mapping+Commit mit Unit-Tests → 3. 4 einfache Renderer (compact zuletzt) → 4. `alert/render.py` → 5. `official_alerts.py`+`notification_service.py`-Plumbing. Nach jeder Gruppe Validator frisch + `record-matrix` (Anti-Stale).

### Open Questions (PO)
- [ ] Scope: alles in einem Workflow (LoC-Override) ODER in zwei Etappen slicen?
- [ ] Label-Wording (wird mit ACs in Phase 3 freigegeben).
