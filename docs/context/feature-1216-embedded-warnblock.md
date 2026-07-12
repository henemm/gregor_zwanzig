# Context + Analysis: feature-1216-embedded-warnblock (#1216 eingebettete Warn-Sektion)

## Request Summary
Ein geteilter **WarnBlock**-Baustein für amtliche Warnungen mit zwei Varianten
(`standalone` / `embedded`) nach Design-Vorlage `docs/design-requests/issue_1216_warn_im_briefing/Gregor 20 - Warnung im Briefing.html`.
Genutzt in drei HTML-Mail-Flächen, PO-Entscheidung: **alles in EINEM Full-Process-Workflow**.

## Design-Entscheidungen (aus der Vorlage, alle „gewählt")
1. **Platzierung:** Warn-Block **ganz oben im Body**, direkt nach dem Header, **vor** der Tageslage. Keine Warnung → Block entfällt ersatzlos.
2. **Optik:** gleiche Bildsprache wie Alarm-Mail, **kompakt**: Severity-Dot, Eyebrow „Amtliche Warnung", Count-Zeile („2 aktiv · höchste Stufe ORANGE" / „Stufe GELB (1/3)"), Quelle-Link; pro Warnung: Meter (bei gemischten Stufen), Stufen-Wort+Position (ORANGE 2/3), Typ, Zeitraum, Route/Umfang-Chips. **Weg:** große H1 + Verdict-Chip (nur `standalone`).
3. **Ortsvergleich:** Aggregat-Banner oben (zählt **Orte**: „6 von 7", „Marseille") **+ Warn-Zeile in der Matrix**. **Kein** dritter Pro-Ort-Detailblock.
4. **Konsistenz:** alle drei Flächen rendern **denselben Baustein**, einziger Unterschied `variant`.

## Ist-Zustand: DREI divergente Strukturen (Kern-Lücke)
| Fläche | Datei:Zeile | Heutiger Renderer | Datenform |
|---|---|---|---|
| Trip-Briefing (embedded) | Aufbau `email/html.py:1416-1427`, Einbau `:1531` (nach Tageslage/Changes) | `render_official_alerts_html` (`alert/official_alerts.py:68-124`) — flaches Div, `border-left:4px`, **kein** Dot/Eyebrow/Count/Meter/Chips/Quelle | `(label, [alert])`-Tupel + `segment_refs` |
| Ortsvergleich (embedded) | Lead `email/compare_html.py:313-354`, Einreihung `:723-729`; Matrix-Row `:90`,`:238-244`; Pro-Ort `:443-445` | `_render_warn_lead` (Satz+Tags, **hartkodierte** Tint-Hex), `_render_warn_cell` (Matrix-Chips), `render_official_alerts_html` (Pro-Ort) | `loc.official_alerts` Aggregat (heat/wildfire/access) |
| Standalone-Alarm | `services/notification_service.py:484` (Trip), `:577` (Compare) | `render_official_alert_html` (`alert/official_alerts.py:366-423`) — nutzt DTO, hat Leiter/Meter/Chips/Quelle (dem `.wb` am nächsten) | `OfficialAlertNotice`-DTO |

**Geteiltes DTO** `OfficialAlertNotice` (`official_alerts.py:56-65`: `alert, scope_label, sms_scope, affected_chips, free_chips`) existiert **nur** für Standalone. Trip/Compare-embedded nutzen `(label,[alert])`-Tupel → müssen auf ein gemeinsames Notice-Modell gehoben werden.

## Related Files
| Datei | Änderung |
|------|----------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY (Kern) — geteilter `render_warn_block(notices, *, variant, source_label, ...)`; `_ladder_html`/`_meter_html`/`_chip_html`/`_LEVEL_*` bleiben Basis; `render_official_alert_html`→`variant=standalone`; `render_official_alerts_html`→ ersetzt durch `variant=embedded` |
| `src/output/renderers/email/html.py` | MODIFY — Trip: Notices bauen, WarnBlock (embedded) **nach Header/vor Tageslage** (`:1525`↔`:1531` umstellen) |
| `src/output/renderers/email/compare_html.py` | MODIFY — Aggregat-Banner = WarnBlock(embedded, Orts-Scope); Matrix-Warn-Zeile behalten; Pro-Ort-Streifen (`:443-445`) **entfernen** (Design: kein dritter Block) |
| `src/services/notification_service.py` | MODIFY — `source_label` nicht mehr hart „GeoSphere Austria"; neues source→Name/URL-Mapping durchreichen |
| `src/output/renderers/email/design_tokens.py` | ggf. MODIFY — Severity-Farb-Tokens (s. Frage A) |
| `tests/golden/email/*` | REGEN — Goldens (u.a. `corsica-vigilance`) via `regenerate.py` neu + Review |
| `tests/tdd/test_*official_alert*`, `test_compare_official_alert*` | MODIFY/CREATE — WarnBlock-Struktur-Tests |

## Analysis

### Type
Feature (neuer geteilter Renderer-Baustein + Konsolidierung dreier Flächen)

### Technischer Ansatz
1. **Ein Renderer** `render_warn_block(notices: list[OfficialAlertNotice], *, variant: "standalone"|"embedded", source_label, source_url, stand_at, tz)` in `official_alerts.py`, der die `.wb`-Struktur emittiert (Dot, Eyebrow, Count, Quelle-Link, pro Warnung Meter/Wort+Pos/Typ/Zeit/Chips). `standalone` ergänzt H1-Headline + Verdict + Leiter (uniform).
2. **Notice-Bau für embedded:** Trip (`html.py`) und Compare (`compare_html.py`) bauen `OfficialAlertNotice`s (Trip: Segment-Chips via `format_segment_reference`; Compare: Orts-Scope „6 von 7 Orten"/Ortsname). Ggf. Notice-Feld für „scope-Zählung" ergänzen.
3. **source→Name/URL-Mapping** neu (analog `radar_service.py:136-147`): `geosphere_warn`→„GeoSphere Austria", `meteofrance_vigilance`→„Météo-France", DWD→„DWD"; Link aus `alert.url`.
4. **Trip-Platzierung** nach oben (vor Tageslage).
5. **Compare:** Pro-Ort-Streifen raus, Banner+Matrix-Zeile bleiben.
6. **Goldens** regenerieren + reviewen.

### Scope Assessment
- Files: ~7-9 (Renderer-Kern + 3 Flächen + tokens + Goldens + Tests)
- Estimated LoC: +250/-150 (Netto moderat, aber Renderer-Umbau) → **LoC-Override nötig** (PO-Freigabe einholen)
- Risk: **HIGH** — Kern-Mail-Pfad über Trip+Compare+Alarm; die live Alarm-Mail wird auf den Baustein umgestellt (Regressionsrisiko), Golden-Mail-Regen, renderer_mail_gate + echte Test-Mails.

### Dependencies & Reihenfolge
1. Severity-Token/Farb-Entscheidung → 2. Renderer-Kern (`render_warn_block`) + Standalone-Umstellung (Goldens/Tests grün halten) → 3. Trip embedded + Platzierung → 4. Compare Banner+Matrix, Pro-Ort raus → 5. source-Mapping → 6. Goldens regen + Tests.

### PO-Entscheidungen (2026-07-11) — locked
- **Frage A/B — Severity-Farben: ALTE Code-Tokens behalten** (PO-go). Der WarnBlock nutzt `G_ALERT_L2 #9a6f00 / L3 #c8482a / L4 #6d28d9` (Level 4 bleibt violett), NICHT die Design-`.wb`-Hex. Folge: **Struktur-Treue** zur Design-Vorlage (Dot/Eyebrow/Count/Meter/Chips/Quelle/Platzierung), Farben aus dem Bestand. Die live Alarm-Mail ändert die Farbe **nicht** → Standalone-Umbau ist rein strukturell/risikoärmer.
- **Frage D — Compare Pro-Ort-Streifen BEHALTEN** (PO-go). Alle drei Compare-Warn-Darstellungen bleiben: neuer Aggregat-Banner (WarnBlock embedded) + Matrix-Warn-Zeile + Pro-Ort-Streifen (`compare_html.py:443-445`, unverändert). Der Umbau ist additiv.

### Offene Punkte (Spec/Impl)
- **Frage C — Standalone-Fidelity-Tests:** `test_952/957_alert_mail_*fidelity` müssen beim Umbau grün bleiben (Farben unverändert hilft); Vorher/Nachher-Struktur-Vergleich.
- **Frage E — LoC-Override** (Renderer-Umbau > 250) — PO-Freigabe im GREEN-Schritt einholen.

### Fidelity-Hinweis
Design-Treue ist **strukturell** (Layout, Grammatik, Platzierung), NICHT farbgetreu zur Vorlage (PO wählte Bestandsfarben). Pixel-Diff-Gate daher gegen eine **an die Bestandsfarben angepasste** Referenz, nicht gegen die rohe Design-HTML.

### Gates (kritisch)
- Alle drei Dateien sind **Mail-Inhalt** → `renderer_mail_gate` (#811). `official_alerts.py` = Radar-Datei → radar_alert_mail_validator (no-op-passed, Log ins HAUPTREPO-_log); `email/html.py`/`compare_html.py` = **Briefing**-Dateien → **Matrix-Test `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py` gegen echte Staging-Mail + Golden-Email-Tests grün** vor Commit. Siehe [[reference_renderer_mailgate_precommit_send_validate]], [[reference_three_briefing_renderers_and_testmail_send]].
- E2E: echte Trip-Briefing- + Compare-Mail auf Staging mit aktiver amtlicher Warnung (bzw. Fixture-Fake-Alert-Seam), IMAP-Verifikation + Pixel/Struktur-Fidelity gegen die Design-Vorlage.
