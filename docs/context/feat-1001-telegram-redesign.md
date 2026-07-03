# Context: Telegram-Ausgabe neu bauen (#1001)

## Request Summary
Die Telegram-Briefing-Ausgabe soll nach einer bereits vorliegenden Claude-Design-Vorgabe
("Gregor 20 - Telegram Vorschau.html") komplett neu gebaut werden: echte Spalten-Tabelle pro
Segment, Aufteilung in mehrere einzeln zitierbare Bubbles (Kopf · Kurzübersicht · Segmente ·
Ziel · Ausblick · Aktionen), Inline-Keyboard statt Text-Befehle, keine bunten Emoji/Wertungen.
Ausgangspunkt war #994 (gemeldete Formatierungsfehler), die Analyse ergab aber, dass der
provisorische Code strukturell ersetzt werden soll statt nur gefixt zu werden.

## Design-Quelle (extern, kein lokales Repo-Dokument)
Claude-Design-Projekt „Gregor Zwanzig" (`projectId 019dfcf4-1e69-73f2-b094-c19e157014a2`),
Datei `Gregor 20 - Telegram Vorschau.html`, abgerufen via `DesignSync.get_file`. Enthält
vollständiges React/JSX-Mockup für Morgen- + Abend-Briefing inkl. Kanal-Regeln (laut
Code-Kommentar im Mockup "CLAUDE.md, PO-bestätigt"):
- Telegram = engster Tabellen-Kanal → max. 8 Metrik-Spalten (Zeit + 7, wie `CHANNEL_LIMITS`)
- Bevorzugt Aufteilung in mehrere Bubbles statt einer Nachricht
- Native Telegram-Formatierung (Bold/Italic-Ranges, `<pre>`-Monospace, Inline-Keyboard) —
  keine Markdown-Sternchen
- Keine bunten Wetter-Emoji, keine Wertungen/Ratschläge — nur Daten
- Kürzel durchgängig aus derselben Quelle wie E-Mail-Tabellenkopf (im JSX: `metric-codes.jsx`,
  `buildQuickTokens()`/`buildQuickLegend()` — geteilte Logik mit SMS-Kürzeln)

Mockup-Struktur pro Briefing: Kopf-Bubble (Trip/Etappe/Datum) → Kurzübersicht-Bubble (SMS-Stil
Token-Zeile, alle konfigurierten Metriken, ganztägig) → je Segment eine Bubble mit Mini-Header
(Name, km-Range, Höhen-Range) + Monospace-Tabelle (bis 8 Spalten, `<pre>` via `parse_mode=HTML`)
→ Ziel-Bubble (eigene Tabelle) → Ausblick-Bubble (3-Tage-Trend-Tabelle, Kopfzeilen wie
E-Mail-Outlook-Tabelle) → Aktionen-Bubble (Inline-Keyboard: Trip-Übersicht, Pause, Überspringen,
Spalten ändern, Hilfe).

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/narrow.py` | Kernstück. `render_narrow()` verzweigt für `channel=="telegram"` aktuell auf `_tg_segment_line()` (Prosa) + `_tg_extra_detail_line()` (kaputte Detail-Zeile, Ursprung von #994) statt der bereits vorhandenen `_narrow_table()` (Spalten-Tabelle, aktuell nur für den abgeschalteten Signal-Kanal genutzt). Muss für Telegram komplett neu verzweigt werden: Tabelle statt Prosa, Multi-Bubble-Rückgabe statt ein String. |
| `src/output/renderers/channel_layout.py` | `CHANNEL_LIMITS["telegram"] = {"max_table_cols": 8, "max_chars": 4096}` bereits korrekt gesetzt (Issue #360). `render_for_channel()` liefert bereits `table_columns`/`detail_metrics` für Telegram — wird aktuell für Telegram nur teilweise genutzt (`_tg_extra_detail_line` nutzt `layout.table_columns + layout.detail_metrics` zusammengeworfen statt sie wie im Mockup getrennt zu behandeln: `table_columns` → Segment-Tabelle, alle konfigurierten Metriken → Kurzübersicht). |
| `src/outputs/telegram.py` | `send()` verschickt aktuell IMMER genau EINE Nachricht pro Aufruf (`sendMessage`). Für Multi-Bubble muss der Aufrufer mehrfach `send()` aufrufen (kein Umbau der Methode selbst nötig) — ggf. mit kleinen Pausen/Reihenfolge-Garantie. `parse_mode="HTML"` und `suppress_subject_line` existieren bereits (genutzt in `trip_alert.py`). Kein Multi-Message-Präzedenzfall im Code — das ist neu. |
| `src/services/trip_report_scheduler.py` | Orchestriert den Versand (Zeile ~634-638 für Telegram, single `send()`-Call mit `report.telegram_text`). Muss für Multi-Bubble auf eine Liste von Nachrichten (+ optional Inline-Keyboard nur auf der letzten) umgestellt werden. |
| `src/formatters/trip_report.py` | `format_email()` befüllt `report.telegram_text` über `render_narrow()` (Zeile 184-196) und hängt bei `dc.telegram_kurzform` bereits eine SMS-Kurzform als Textblock an (Zeile 227-238, s.u.). Muss ggf. `telegram_text` zu `telegram_messages: list[str]` erweitern (additiv, Modell-Schema-Rework-Pflicht beachten falls `TripReport`/`models.py` betroffen). |
| `src/app/models.py:570` | **`telegram_kurzform: bool = False`** — bereits existierendes, additives Feld auf `UnifiedWeatherDisplayConfig` (aus #614/615, PO "go" 2026-06-06, LIVE). Frontend-Toggle existiert bereits (`WeatherV2Kanaele.svelte` u.a.). |
| `src/formatters/sms_trip.py` | `SMSTripFormatter.format_sms()` — wird bereits für die Telegram-Kurzform wiederverwendet (`telegram_kurzform=true`-Pfad). `SMS_SYMBOL_BY_METRIC` (Zeile 44-52) ist das bestehende Python-Äquivalent zu `metric-codes.jsx` aus dem Mockup — vermutlich direkt wiederverwendbar für die neue Kurzübersicht-Bubble statt einer Neuimplementierung. |
| `src/output/tokens/builder.py`, `src/output/tokens/dto.py` | `build_token_line()`, `TokenLine`, `HourlyValue`, `NormalizedForecast` — Token-Pipeline hinter der SMS-Kurzform, liefert Min/Max/Peak@Stunde-Werte. Wiederverwendbar für die Kurzübersicht-Bubble. |
| `src/services/trip_command_processor.py` | Umfangreiches bestehendes Inline-Keyboard-Vorbild (`{"inline_keyboard": [[{"text": ..., "callback_data": ...}]]}`, Zeilen 100-724). Direktes Vorbild für die Aktionen-Bubble. Callback-Namen für neue Aktionen ("Spalten ändern" etc.) müssen hier ergänzt und im Reader behandelt werden. |
| `src/services/inbound_telegram_reader.py` | Verarbeitet eingehende Callbacks (`answer_callback_query`, Zeile 266 etc.). Neue Button-Aktionen aus der Aktionen-Bubble brauchen hier neue Handler-Zweige. |
| `src/app/metric_catalog.py` | `MetricDefinition.compact_label`/`col_label` — Python-Quelle der Kürzel für Tabellen-Header, analog zu `METRIC_CODES` im JSX-Mockup. Bereits Single Source of Truth, keine neue Datei nötig (im Gegensatz zur Mockup-Annahme einer separaten `metric-codes.jsx`). |

## Existing Patterns

- **Tabellen-Rendering existiert bereits vollständig** (`_narrow_table()` in `narrow.py`,
  Zeile 115-151) — wird aktuell nur für Signal genutzt (Signal ist seit #610 abgeschaltet,
  aber der Code lebt noch). Für Telegram muss dieselbe Funktion aufgerufen werden statt der
  Prosa-Variante — kein Neubau der Tabellen-Logik nötig, nur Verkabelung + `<pre>`-Wrapping
  beim Versand (`parse_mode="HTML"`, HTML-Escaping der Zellinhalte beachten).
- **Kurzübersicht ist bereits (opt-in) gebaut** (#614/615, `telegram_kurzform`) — reuse von
  `SMSTripFormatter.format_sms()`. Die Design-Vorgabe will das aber (a) als eigene Bubble statt
  angehängtem Textblock, (b) vermutlich standardmäßig aktiv statt opt-in, (c) mit den
  E-Mail-Kürzeln (`metric_catalog.col_label`) statt den SMS-Symbolen (`SMS_SYMBOL_BY_METRIC`) —
  muss in der Analyse-Phase geklärt werden, ob beide Kürzel-Sätze deckungsgleich sind oder
  divergieren.
- **Inline-Keyboard-Pattern etabliert** (`trip_command_processor.py`) — Buttons mit
  `callback_data`, Verarbeitung im `InboundTelegramReader`. Neue Aktionen folgen demselben
  Muster.
- **`suppress_subject_line` + `parse_mode="HTML"`** bereits kombiniert genutzt in
  `trip_alert.py:847-850` — direktes Vorbild für alle neuen Bubble-Sends.

## Dependencies

- **Upstream:** `SegmentWeatherData[]`, `UnifiedWeatherDisplayConfig`/`MetricConfig`
  (bucket/order aus #360), `render_for_channel()` (`channel_layout.py`), `fmt_val()`
  (`email/helpers.py`), `SMSTripFormatter.format_sms()`, `metric_catalog.get_metric()`.
- **Downstream:** `trip_report_scheduler.py` (Briefing-Versand), `trip_alert.py` (sendet
  aktuell EIGENE Telegram-Nachrichten für Alarme — bleibt vermutlich unverändert, da Alarme
  kein Briefing-Multi-Bubble-Format brauchen, aber in der Analyse gegenprüfen), Frontend
  Kanal-Vorschau (`ChannelPreviewBlock.svelte`/`ChannelPreviewCard.svelte`, #496) — zeigt
  aktuell eine Kachel-Vorschau; müsste ggf. die neue Multi-Bubble-Struktur widerspiegeln
  (separates Thema, ggf. eigenes Folge-Ticket statt in #1001 mitzuziehen).

## Existing Specs

- `docs/specs/modules/issue_360_signal_channel_renderer.md` — Ursprungs-Spec für
  `channel_layout.py`/`narrow.py`/`_narrow_table()`. Definierte ursprünglich eine echte Tabelle
  auch für Telegram (Approved, 2026-05-24) — wurde durch #635 für Telegram überschrieben.
- `docs/specs/modules/issue_635_telegram_weather_readable.md` — PO-Entscheidung "Telegram:
  fest & kuratiert, keine Zahlenwand" (07.06.2026), Ursprung der aktuellen Prosa-Zeilen.
  Direkter Ziel-Konflikt mit der neuen Design-Vorgabe (die wieder eine Tabelle will) — muss in
  der neuen Spec explizit als überholt markiert werden.
- `docs/specs/modules/fix_887_report_inkonsistenz.md` — Ursprung der jetzt zu ersetzenden
  `_tg_extra_detail_line()` (09.06.2026 grob, Fix für "Telegram ignoriert Parameter").
- `docs/specs/modules/issue_614_615_telegram_kurzform.md` — bereits **approved und live**
  (06.06.2026), baut exakt die SMS-Stil-Kurzübersicht, nur als angehängter Text statt eigener
  Bubble und opt-in statt Standard. Wichtigste Wiederverwendungs-Chance für #1001.
- `docs/context/fix-994-telegram-vorlage.md` — Root-Cause-Analyse der ursprünglich gemeldeten
  Bugs (doppelte Klammern, kaputte Einheiten in `_tg_extra_detail_line()`), Workflow gestoppt
  zugunsten dieses Feature-Tickets, bleibt als historischer Beleg stehen.

## Analysis

### Type
Feature (Full Process). Drei parallele Explore-Agenten + ein Plan/Sonnet-Strategie-Agent haben
den Kontext vertieft; wichtigste Korrektur gegenüber der ersten Einschätzung: `render_narrow()`
hat in Produktion **genau einen Aufrufer** (`trip_report.py:185`, immer `channel="telegram"`
literal) — die `channel`-Parametrisierung ist totes Überbleibsel aus der Signal-Ära. Der von
einem Recherche-Agenten gemeldete ~80-Dateien-Blast-Radius wurde per Stichprobe widerlegt: der
echte Kern ist eng (7 Dateien), der Rest sind reine `send_telegram`-Boolean-Flag-Treffer ohne
inhaltlichen Bezug zum Nachrichtenformat.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/narrow.py` | MODIFY (Rewrite) | Neue Funktion `render_telegram_bubbles()` → `list[TelegramBubble]`. Prosa-Pfad (`_tg_segment_line`, `_tg_extra_detail_line`, `_tg_day_footer`) entfernt, `_narrow_table()` reaktiviert für Segment-Tabellen. |
| `src/formatters/trip_report.py` (170-253) | MODIFY | Verkabelung auf `telegram_bubbles`; Kurzübersicht nutzt `metric_catalog`-Kürzel statt `SMSTripFormatter`-Reuse. |
| `src/app/models.py:677` | MODIFY | `telegram_text: Optional[str]` → `telegram_bubbles: list[str]` (keine Persistenz-Migration nötig — transientes DTO, kein Bestandsdatenverlust-Risiko). |
| `src/services/trip_report_scheduler.py` (593-640) | MODIFY | Multi-Send-Schleife über Bubbles, Fehlerpolitik: Abbruch + einmaliges Log bei erster fehlgeschlagener Bubble (kein Teil-Retry). |
| `src/services/trip_command_processor.py` + `src/services/inbound_telegram_reader.py` | MODIFY | Aktionen-Bubble: Inline-Keyboard nach etabliertem Muster (Zeilen 100-724), neue Callback-Handler. Namenskonvention bewusst von `#704`-Präfixen (`dd_*`) abgrenzen. |
| `src/services/preview_service.py` + `api/routers/preview.py` (84-111) | MODIFY (additiv) | Neues Feld `bubbles: list[str]` zusätzlich zum bestehenden `body`-String (Rückwärtskompatibilität für Frontend, kein Breaking Change). |
| 12 Testdateien (siehe unten) | MODIFY | Migration auf neue Bubble-API. |

**Explizit NICHT in #1001:** Frontend-Multi-Bubble-Darstellung (`ChannelPreviewBlock.svelte`,
`ChannelPreviewCard.svelte`) — Folge-Ticket, additives `bubbles`-Feld reicht für jetzt.
`internal/handler/preview_proxy.go` ist reines JSON-Passthrough, keine Go-Änderung nötig.

### Scope Assessment
- Files: 7 Kern-Dateien (Backend) + 12 Testdateien
- Estimated LoC: **400-600** über die Kern-Dateien — überschreitet das 250-LoC-Standardlimit
  deutlich. Braucht `workflow.py set-field loc_limit_override` (User-Permission PFLICHT laut
  Memory, vor Nutzung abfragen).
- Risk Level: MEDIUM — kein Persistenz-Risiko (transientes DTO), aber neuer Multi-Message-
  Versand ohne Präzedenzfall im Code (Reihenfolge-Garantie, Teilausfall-Verhalten müssen in
  TDD gegen echten Staging-Bot verifiziert werden, keine Mocks).

### Technical Approach
Siehe Plan-Agent-Bewertung (vollständig im Workflow-Verlauf). Kernentscheidungen:
1. **Breaking Replace statt additivem Duplikat** für `render_narrow()` — einziger
   Produktions-Konsument ist `trip_report.py:185`, alle anderen "Konsumenten" sind Tests, die
   ohnehin migriert werden müssen (ihre Specs werden durch #1001 fachlich abgelöst).
2. **Kurzübersicht nutzt `metric_catalog.compact_label`/`col_label`**, nicht
   `SMS_SYMBOL_BY_METRIC` — Mockup fordert "gleiche Quelle wie E-Mail-Tabellenkopf". Damit wird
   die #614/615-Wiederverwendung von `SMSTripFormatter` NICHT übernommen (bewusste Abweichung,
   in der Spec zu begründen). Das `telegram_kurzform`-Feld bleibt additiv erhalten (Kurzübersicht
   ein/aus), Default-Wert-Entscheidung für neue Trips separat zu treffen.
3. **`TelegramOutput.send()` bleibt unverändert** — Multi-Send ist eine simple Schleife im
   Scheduler, keine der 7 Bot-Antwort-Call-Sites oder Alert-Call-Sites ist betroffen.
4. **Reihenfolge-Empfehlung für Trend (#623/#640):** BEIDE sind DRAFT, nicht implementiert,
   null Produktions-Callsites → NACH #1001 neu spezifizieren (die neue Ausblick-Bubble
   absorbiert ihren fachlichen Kern; `format_trend_tokens()`-Rechenlogik bleibt
   wiederverwendbar, nur die "ein-Block"-Strukturannahme in AC-3 wird obsolet).
5. **#612 (Befehls-Footer) wird durch Aktionen-Bubble abgelöst**, nicht gebrochen — Text-Befehle
   bleiben über den bestehenden Parser funktionsfähig, nur die Einladung dazu wandert zu Buttons.

### Dependencies
Siehe Context-Sektion oben, ergänzt um: Aktionen-Bubble-Callback-Namen müssen bewusst von
#704-Präfixen (`dd_hours_today` etc.) abgegrenzt werden, um künftige Kollisionen zu vermeiden,
falls #704 später doch noch gebaut wird.

### Open Questions — Entschieden (User, 2026-07-03)
- [x] LoC-Limit-Override auf 600 gesetzt (ein zusammenhängender Workflow, kein Split).
- [x] Kurzübersicht-Bubble ist künftig **immer aktiv**, kein Ein/Aus-Schalter mehr —
      `telegram_kurzform`-Feld/Frontend-Toggle wird entfernt bzw. wirkungslos gemacht statt
      als weiterhin nutzbare Option erhalten zu bleiben (Abweichung von der ursprünglichen
      Plan-Agent-Annahme "additiv erhalten").

## Risks & Considerations

- **Zielkonflikt zwischen drei PO-Entscheidungen über Zeit:** #635 (fest/kuratiert, keine
  Tabelle) vs. #614/615 (Kurzform reicht als Textanhang) vs. jetzige Design-Vorgabe (Tabelle +
  Multi-Bubble + Kurzübersicht als eigene Bubble). Die neue Spec muss explizit festhalten, dass
  die aktuelle Vorgabe die früheren ersetzt (nicht stillschweigend widersprüchlich nebeneinander
  stehen lassen).
- **Kürzel-Konsistenz:** Zwei parallele Kürzel-Quellen existieren (`SMS_SYMBOL_BY_METRIC` vs.
  `metric_catalog.compact_label`/`col_label`). Das Mockup will "Kürzel durchgängig aus derselben
  Quelle wie E-Mail-Tabellenkopf" — das spricht für `metric_catalog`, nicht für die SMS-Symbole.
  Falls die neue Kurzübersicht-Bubble NICHT mehr `SMSTripFormatter.format_sms()` wiederverwendet,
  sondern eigene Kürzel nutzt, wird aus der "Wiederverwendung" (#614/615) ein Parallelbau —
  muss in der Analyse-Phase bewusst entschieden werden (Trade-off: Konsistenz mit SMS vs.
  Konsistenz mit E-Mail).
- **Multi-Message-Versand ist ohne Präzedenzfall im Code** — Reihenfolge-Garantie, Teilausfall
  (was, wenn Bubble 3 von 7 fehlschlägt?), Rate-Limits der Telegram-Bot-API bei schnellen
  aufeinanderfolgenden `sendMessage`-Calls müssen in der Analyse geklärt werden.
  Fire-and-forget-Semantik von `TelegramOutput.send()` (kein Retry) bleibt vermutlich pro
  Einzelnachricht bestehen, aber die Gesamt-Fehlerbehandlung (ein Log pro Bubble? Abbruch nach
  erstem Fehler?) ist offen.
- **HTML-Escaping in `<pre>`-Blöcken:** Zellwerte könnten `<`/`>`/`&` enthalten (aktuell
  unwahrscheinlich bei reinen Zahlen/Einheiten, aber defensiv zu prüfen) — `parse_mode="HTML"`
  erfordert korrektes Escaping, sonst bricht die Telegram-API die Nachricht ab oder rendert
  falsch.
- **KEINE MOCKED TESTS (Projektregel):** TDD-Tests müssen echte `render_narrow()`-Ausgaben und
  echten Telegram-Versand (Staging-Bot, `gregor-test`-Äquivalent für Telegram: Chat
  `8346977700`, siehe Memory `reference_staging_telegram_bot`) prüfen — kein Mock der
  Bot-API. Der in dieser Session bereits gebaute Wegwerf-Prototyp
  (`/tmp/.../telegram_table_prototype.py`) hat den `<pre>`+`parse_mode=HTML`-Ansatz bereits
  empirisch bestätigt (Nachricht kam als echte Monospace-Tabelle an, iPhone brach bei zu
  breiter Tabelle um → Spaltenzahl/-breite muss in der Spec bewusst eng gehalten werden).
- **Scope-Abgrenzung Frontend-Kanalvorschau (#496):** Die Kachel-Vorschau im Trip-Editor zeigt
  aktuell keine Multi-Bubble-Struktur. Ob das in #1001 mitgezogen wird oder als Folge-Ticket
  läuft, ist eine offene Entscheidung für die Spec-Phase — tendenziell Folge-Ticket, um Scope-
  Explosion zu vermeiden.
