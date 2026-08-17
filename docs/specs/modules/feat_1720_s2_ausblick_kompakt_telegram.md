---
entity_id: feat_1720_s2_ausblick_kompakt_telegram
type: feature
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.0"
workflow: feat-1720-s2-ausblick-kompakt-telegram
tags: [trip, outlook, ausblick, kompakt-mail, telegram, metrik-katalog, feature, epic-1372, issue-1720]
---

# 3-Tages-Vorschau des Trip-Briefings: wählbare Spalten für Kompakt-Mail und Telegram (Issue #1720, Scheibe 2)

## Approval

- [ ] Approved

## Purpose

Scheibe 1 (#1720, PR #1840) hat die 3-Tages-Vorschau der HTML- und
Klartext-Trip-Mail katalog-getrieben gemacht. Kompakt-Mail und Telegram
zeigen weiterhin ihre alten, fest verdrahteten Felder — unabhängig davon,
was der Nutzer im bereits vorhandenen Abschnitt „3-Tages-Vorschau" auswählt.
ADR-0055 kündigt diese Scheibe ausdrücklich an. Dieses Modul schließt die
Lücke: dieselbe, bereits gespeicherte Auswahl (`display_config.outlook_metrics`)
wirkt danach in **allen vier** Trip-Ausgabeorten mit Ausblick (HTML, Klartext,
Kompakt-Mail, Telegram) — SMS/Premium-SMS bleiben unverändert baulich
unerreichbar, Ortsvergleich bleibt unverändert. Es entsteht **keine** neue
Auflösung, **kein** neues Persistenzfeld — nur zwei fehlende Durchreichungen
und zwei Renderer, die zwischen Legacy-Feldern und dem bereits vorliegenden
`row["cells"]` umschalten.

## Source

- **File:** `src/output/renderers/trip_report.py:215-220` (render_email-Aufruf)
  und `:290-309` (render_telegram_bubbles-Aufruf). Neu: EINE Auflösung vor
  beiden Aufrufen (`_outlook_metrics = resolve_trip_outlook_metrics(_dc_uncollapsed, report_type)`),
  wiederverwendet als `outlook_metrics=_outlook_metrics` in **beiden**
  Aufrufen. `render_telegram_bubbles(...)` bekommt den Kwarg dabei zum
  ersten Mal — bislang fehlt er komplett. 🔴 Die Quelle MUSS
  `_dc_uncollapsed` bleiben, NICHT `_dc_telegram` (das kanal-kollabierte
  Telegram-Layout, Zeile 274/293) — der Ausblick hat laut ADR-0055 Punkt 2
  keine Kanal-Ebene; Telegram-eigene `per_channel_layouts` dürfen die global
  gewählte Vorschau-Spalte nicht enger schneiden als die Grundauswahl
  erlaubt (identische Gefahr zu S1s Adversary-Finding F001/AC-17, jetzt auf
  den zweiten Konsumenten übertragen).
- **File:** `src/output/renderers/email/__init__.py:111-132` (`render_email()`,
  `email_format == "compact"`-Zweig). Neu: `outlook_metrics=outlook_metrics,`
  in den `render_compact(...)`-Aufruf (Zeile 112-131) einfügen — der Wert ist
  hier bereits als Funktionsparameter vorhanden (Zeile 51), geht aber vor
  dieser Änderung verloren, weil er im Aufruf fehlt.
- **File:** `src/output/renderers/email/compact.py:130-151` (`render_compact()`-
  Signatur). Neu: `outlook_metrics: Optional[list[dict]] = None,` ergänzen
  (nach `multi_day_trend`, vor `outlook_state`, analog zur Reihenfolge in
  `render_email()`). Import `outlook_columns`, `format_outlook_value` aus
  `output.renderers.compare_outlook_metric_ids`.
- **File:** `src/output/renderers/email/compact.py:258-270` (`if multi_day_trend:`-
  Block). Neu: Katalog-Zweig analog `email/outlook.py:333-341`
  (`render_outlook_plain()`s bereits vorhandenem Muster) — siehe
  Implementation Details Punkt 1. Bedingung erweitert sich um
  `outlook_metrics != []` (Implementation Details Punkt 3); dieselbe
  Erweiterung gilt für den `elif outlook_state ...`-Fallback-Zweig
  (Zeile 271-278).
- **File:** `src/output/renderers/narrow.py:572-613` (`_outlook_lines()`).
  Signatur neu: `def _outlook_lines(multi_day_trend: list[dict], outlook_metrics: Optional[list[dict]] = None) -> list[str]:`.
  Neu: Katalog-Zweig analog Implementation Details Punkt 2.
- **File:** `src/output/renderers/narrow.py:635-655`
  (`render_telegram_bubbles()`-Signatur). Neu:
  `outlook_metrics: Optional[list[dict]] = None,` ergänzen (nach
  `multi_day_trend`, analog `render_email()`).
- **File:** `src/output/renderers/narrow.py:832-839` (Ausblick-Bubble-Block,
  `if multi_day_trend:` / `elif outlook_state ...`). Neu:
  `_outlook_lines(multi_day_trend, outlook_metrics)` statt
  `_outlook_lines(multi_day_trend)`; Bedingung beider Zweige erweitert um
  `outlook_metrics != []` (identisch zu compact.py, Implementation Details
  Punkt 3).
- **File:** `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte:37-60`
  (Props-Interface). Neu: optionale Prop `showEmailOnlyHint?: boolean`
  (Default `true` — bewahrt das heutige Compare-Verhalten ohne
  Compare-seitige Änderung). `:176-183` (Hinweistext-Block): die
  `{#if materializedOutlookKeys.length > 0}`-Bedingung erweitert sich um
  `&& showEmailOnlyHint`.
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1778-1784`
  (Trip-Einbindung von `CompareOutlookLayoutControls`). Neu:
  `showEmailOnlyHint={false}` ergänzen — die Compare-Einbindung
  (`:1398-1405`) bleibt unverändert (Default greift).

> **Schicht-Hinweis:** Python-Core (`src/output/renderers/`) trägt das
> Rendering; Frontend (`frontend/src/lib/components/shared/`) nur den
> Hinweistext. Kein Anteil in `cmd/`, `internal/` oder anderen Go-Paketen
> (`display_config` bleibt `map[string]interface{}`, unverändert seit S1).
> `compare_outlook_metric_ids.py` wird **nicht** verändert — reine
> Wiederverwendung.

## Estimated Scope

- **LoC:** ~95-130 Produktiv (`trip_report.py` ~6: eine Variable statt
  Inline-Aufruf, zweiter Aufrufort ergänzt; `email/__init__.py` ~1;
  `compact.py` ~30-35: Signatur + Katalog-Zweig + Bedingungserweiterung;
  `narrow.py` ~35-45: zwei Signaturen + Katalog-Zweig + Bedingungserweiterung
  + Aufrufstelle; `CompareOutlookLayoutControls.svelte` ~10;
  `WeatherMetricsTab.svelte` ~1). Bleibt unter dem 250er-Limit; kein Override
  beantragt.
- **Files:** 6 Produktionsdateien geändert, 0 neu.
- **Effort:** medium — kein neuer Resolver, kein neues Persistenzfeld, aber
  zwei fest verdrahtete Renderer müssen auf den bereits vorhandenen
  `row["cells"]`-Katalog-Zweig umgestellt werden, und die **einzige**
  Bestandsschutz-Grundlage (ein Charakterisierungstest) muss für beide
  Kanäle **neu entstehen**, weil sie heute nicht existiert (s. „Der Befund,
  der die Testplanung bestimmt").
- **LoC-Limit Test-Budget:** 450 (getrennt vom 250-Produktiv-Limit,
  `config_loader.py:264-297`) — zwei neue Referenz-Fixtures
  (Kompakt-Block, Telegram-Bubble-Text), ein Charakterisierungstest, zwei
  Wirkort-Dispatch-Tests (Kompakt über `EmailOutput`-Recording analog
  `test_trip_outlook_dispatch_mail.py`, Telegram über
  `TelegramOutput`-Recording analog `test_telegram_rate_limit.py:274`).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `output.renderers.compare_outlook_metric_ids.resolve_trip_outlook_metrics/outlook_columns/format_outlook_value` | reused, unverändert | Dieselbe Auflösung/Formatierung wie S1 — kein zweites Vokabular, kein neuer Schnitt gegen die Grundauswahl nötig, er gilt bereits |
| `output.renderers.email.outlook.render_outlook_plain` (Muster, Zeile 333-341) | Vorbild, nicht aufgerufen | Der Katalog-Zweig für `compact.py`s Zeilenformat übernimmt exakt dasselbe Label-Wert-Muster (`f"{c['label']} {cells[i]}"`, `"  "`-Trenner) — keine dritte Formatierungsregel erfinden |
| `output.channels.email.EmailOutput` / `output.channels.telegram.TelegramOutput` | reused, Wirkort-Test | Recording-Subklassen fangen den echten Versandpfad ab, kein Mock-Framework (Muster `test_trip_outlook_dispatch_mail.py:200-212`, `test_telegram_rate_limit.py:274`) |
| `renderer_mail_gate.py` (#811) | Gate | Blockiert den Commit auf `compact.py`, bis der Modus-Matrix-Test und ein frischer `briefing_mail_validator.py`-Lauf vorliegen — `compact.py` ist eine Mail-Inhaltsdatei |
| `pendant_gate.py` (#1481 B) | Gate | Alle geänderten Dateien sind Bestandsdateien, keine Neuanlage — Gate greift nicht |
| `trip_report_scheduler.py:2329` (`build_outlook_row`) | reused, unverändert | Liefert `row["cells"]`/`row["cell_bg"]` bereits für alle vier Ausgabeorte identisch — diese Scheibe liest sie nur, baut sie nicht neu |

## Implementation Details

1. **Kompakt-Zeilenformat bei aktiver Auswahl.** `compact.py`s Katalog-Zweig
   übernimmt exakt das Label-Wert-Muster, das `render_outlook_plain()`
   bereits für den Ortsvergleich-Klartext nutzt (`outlook.py:333-341`) — kein
   drittes Format erfinden:
   ```python
   if outlook_metrics is not None:
       columns = outlook_columns(outlook_metrics)
       for stage in multi_day_trend:
           weekday = stage.get("weekday", "")
           cells = stage.get("cells") or []
           values = "  ".join(
               f"{c['label']} {cells[i] if i < len(cells) else '–'}"
               for i, c in enumerate(columns)
           )
           lines.append(_ascii(f"{weekday:<3} {values}".rstrip()))
   else:
       ... bestehende sieben-Feld-Schleife unverändert ...
   ```
   Begründung gegen feste Feldbreiten: bei 1..N frei gewählten Spalten gibt
   es keine sinnvolle feste Breite je Spalte — das Label trägt die
   Zuordnung, nicht die Spaltenposition. `_ascii()` faltet wie im
   Legacy-Zweig auf reines ASCII (Kompakt-Mail-Vertrag, Docstring
   `compact.py:154-156`).

2. **Telegram-Zeilenformat bei aktiver Auswahl — MIT Labels.** Die heutige
   feste Zeile (`weekday  temp  precip  wind  thunder`) trägt keine Labels,
   weil die Position selbsterklärend ist (immer dieselben fünf Felder in
   derselben Reihenfolge). Bei freier Auswahl entfällt diese Garantie —
   deshalb bekommt jede Zelle ihr Katalog-Label vorangestellt, mit Doppelpunkt
   (kompakter als das Leerzeichen-Format der Kompakt-Mail, weil Telegram-
   Bubbles auf `_TG_PROSE_WIDTH` umbrechen und Label+Wert dort optisch enger
   zusammengehören müssen als in einer Mail-Zeile):
   ```python
   if outlook_metrics is not None:
       columns = outlook_columns(outlook_metrics)
       for stage in multi_day_trend:
           weekday = stage.get("weekday", "")
           cells = stage.get("cells") or []
           values = "  ".join(
               f"{c['label']}: {cells[i] if i < len(cells) else '–'}"
               for i, c in enumerate(columns)
           )
           trend_line = f"{weekday}  {values}"
           lines.extend(_wrap(trend_line, _TG_PROSE_WIDTH))
           note = stage.get("note")
           if note:
               lines.extend(_wrap(f"    ↳ {note}", _TG_PROSE_WIDTH))
   else:
       ... bestehende Fünf-Feld-Logik (Zeile 576-612) unverändert ...
   ```
   Die Notiz-Zeile (`stage.get("note")`) bleibt in BEIDEN Zweigen identisch
   — sie ist keine Katalog-Spalte, sondern ein eigenständiges Feld.

3. **`outlook_metrics == []` lässt den GESAMTEN Block entfallen — inklusive
   des Zustands-Fallbacks.** Anders als HTML/Klartext haben Kompakt-Mail und
   Telegram einen dritten Zweig: den Zustands-Hinweis
   (`elif outlook_state is not None and outlook_state != _OutlookState.FOUND:`,
   `compact.py:271-278`, `narrow.py:836-839`), der bei fehlenden Ausblicksdaten
   (statt fehlender Auswahl) eine Ersatzmeldung zeigt. Eine bewusst geleerte
   Auswahl (`outlook_metrics == []`) muss AUCH diesen Fallback unterdrücken —
   der Nutzer hat den ganzen Abschnitt abgewählt, nicht nur die Spalten. Beide
   Renderer bekommen deshalb eine gemeinsame äußere Bedingung:
   ```python
   if outlook_metrics != []:
       if multi_day_trend:
           ...
       elif outlook_state is not None and outlook_state != _OutlookState.FOUND:
           ...
   ```
   Für `outlook_metrics is None` (Altbestand, Default-Parameter) bleibt das
   Verhalten unverändert — nur der explizite `[]`-Fall schaltet beide Zweige
   ab. Identisch zur Bedingungserweiterung aus S1 (`html.py`/`plain.py`,
   Implementation Details Punkt 2 jener Spec), hier auf den zusätzlichen
   Fallback-Zweig ausgeweitet, den HTML/Klartext gar nicht besitzen.

4. **EINE Auflösung, jetzt für drei statt zwei Konsumenten.** `trip_report.py`
   löst `outlook_metrics` bereits einmal aus `_dc_uncollapsed` auf (S1,
   Implementation Details Punkt 10 jener Spec). Diese Scheibe zieht die
   Auflösung aus dem Inline-Kwarg-Ausdruck in eine lokale Variable und
   verdrahtet sie an BEIDE Aufrufstellen:
   ```python
   _outlook_metrics = resolve_trip_outlook_metrics(_dc_uncollapsed, report_type)
   ...
   email_html, email_plain = render_email(
       ...,
       outlook_metrics=_outlook_metrics,
       ...,
   )
   ...
   telegram_bubbles_result = render_telegram_bubbles(
       ...,
       outlook_metrics=_outlook_metrics,
       ...,
   )
   ```
   Kein zweiter `resolve_trip_outlook_metrics()`-Aufruf für Telegram — sonst
   könnte (wie bei S1s F001) eine spätere Änderung an einer Stelle die andere
   unbemerkt zurücklassen. Die Regel aus ADR-0055 Punkt 4 („eine Auflösung,
   explizit durchgereicht") gilt jetzt für alle drei Renderer-Aufrufstellen
   im Trip-Pfad (HTML, Klartext, Kompakt teilen sich `render_email()`;
   Telegram bekommt dieselbe Variable separat).

5. **Hinweistext wird für den Trip-Kontext entfernt, für Compare bleibt er
   stehen.** `CompareOutlookLayoutControls.svelte` bekommt eine additive,
   optionale Prop `showEmailOnlyHint` (Default `true`). Die
   Compare-Einbindung (`WeatherMetricsTab.svelte:1398-1405`) übergibt sie
   NICHT — der Default hält das Verhalten dort byte-identisch (der Compare-
   Ausblick erscheint weiterhin ausschließlich in `render_compare_email()`,
   nie in Telegram; der Hinweis bleibt richtig). Die Trip-Einbindung
   (`:1778-1784`) übergibt `showEmailOnlyHint={false}` — nach dieser Scheibe
   wirkt die Auswahl in allen vier Trip-Ausgabeorten, der Hinweis wäre dort
   falsch. Kein Ersatztext: die Abwesenheit des Hinweises ist selbsterklärend
   (kein Kanal wird mehr ausgenommen außer den weiterhin baulich
   unerreichbaren SMS/Premium-SMS, die nie Teil der Aussage waren).

6. **Legenden-Frage: nicht zutreffend.** Weder `compact.py` noch `narrow.py`
   besitzen eine eigenständige Abkürzungs-Legende wie `html.py:1360-1366`.
   Die heutigen Kürzel (`R{token}`, `W{token}`, `⚡{token}`) stehen inline in
   der Wertzelle selbst, nicht in einem separaten Legenden-Block — es gibt
   nichts, das an die S1-Regel „Legende nur ohne Auswahl" (S1 Implementation
   Details Punkt 4) gekoppelt werden müsste. Bei aktiver Auswahl tragen die
   Katalog-Labels bereits die Bedeutung (Punkt 1/2 oben), bei Legacy-Zustand
   bleiben die bestehenden Inline-Kürzel unverändert.

## Was sich NICHT ändern darf

- **HTML- und Klartext-Trip-Mail bleiben byte-identisch zu S1.** Diese
  Scheibe rührt `html.py`/`plain.py` nicht an — `test_trip_outlook_parity.py`
  UND die S1-Wirkort-Tests bleiben grün ohne Anpassung.
- **Ortsvergleich bleibt unverändert.** `resolve_outlook_metrics()`,
  `comparison.py`, `compare_html.py`, die Compare-Einbindung von
  `CompareOutlookLayoutControls.svelte` (Default-Prop greift) — alles
  unangetastet.
- **`report_config.show_outlook`-Semantik unverändert.** Weiterhin der
  einzige Ein/Aus-Schalter für den gesamten Ausblick-Block.
- **Kompakt-Mail und Telegram OHNE gesetztes `outlook_metrics` bleiben
  byte-identisch zum heutigen Stand.** Das ist die zentrale Zusicherung
  dieser Scheibe — geprüft am echten Versandpfad gegen eine vor dieser
  Lieferung aufgezeichnete Referenz (AC-1).
- **Persistenzformat `display_config.outlook_metrics` unverändert.** Kein
  neues Feld, kein neues Vokabular — reine Wiederverwendung des in S1
  eingeführten Felds.
- **SMS/Premium-SMS bleiben baulich unerreichbar.** `sms_trip.py` kennt
  `multi_day_trend` weiterhin nicht — außerhalb des Zuschnitts.

## 🔴 Der Befund, der die Testplanung bestimmt

Für Kompakt-Mail- und Telegram-Ausblick existiert **kein** Byte-Golden-Test.
`test_issue_729_render_compact_empty.py`, `test_issue_1001_telegram_bubbles.py`
und `test_channel_metric_matrix.py` decken andere Aspekte ab; keiner
vergleicht den heutigen Ist-Zustand des Ausblick-Blocks byte-genau gegen eine
aufgezeichnete Referenz. `test_trip_outlook_parity.py` ruft ausschließlich
`render_outlook_table()`/`render_outlook_plain()` (den HTML/Klartext-Pfad)
auf — Kompakt/Telegram nie.

**Deshalb MUSS zuerst ein Charakterisierungstest entstehen**, der den
heutigen Legacy-Zustand (`outlook_metrics=None`) aus dem echten Aufrufpfad
(`render_email()` für Kompakt, `render_telegram_bubbles()` für Telegram)
aufzeichnet, BEVOR `compact.py`/`narrow.py` verändert werden — analog zum
Vorgehen von S1 (`tests/fixtures/trip_outlook_reference/`, README dort). Die
Referenz-Fixtures dürfen anschließend NICHT nachgezogen werden, außer für
eine unabhängig begründete, PO-freigegebene Änderung (Muster: S1s
Warnstufen-Palette-Ausnahme #1801).

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen `display_config.outlook_metrics` NICHT
  gesetzt ist (Altbestand, heutiger Normalfall), When Kompakt-Mail und
  Telegram-Bubbles über den echten Versandpfad erzeugt werden (nicht der
  isolierte Renderer-Aufruf), Then sind beide Ausblick-Blöcke byte-identisch
  zu einer VOR dieser Lieferung aufgezeichneten Referenz.
  - Test: `render_email(email_format="compact")` bzw.
    `render_telegram_bubbles()` mit unverändertem `display_config` gegen je
    eine aufgezeichnete Referenz-Datei (`tests/fixtures/trip_outlook_reference/compact_block.txt`,
    `telegram_bubble.txt`), NICHT gegen einen zweiten Aufruf desselben Codes
    im selben Lauf.

- **AC-2:** Gegeben ein Nutzer hat im Abschnitt „3-Tages-Vorschau" eine
  Teilmenge der Größen gewählt und gespeichert (z. B. „Niederschlag" und
  „Böen"), wenn die nächste Trip-Mail versendet wird, dann zeigt der
  Kompakt-Mail-Ausblick ausschließlich diese gewählten Spalten in
  Auswahlreihenfolge mit lesbaren deutschen Labels — nicht die bisherigen
  fünf/sieben festen Felder.
  - Test: echter Trip-Versandpfad (`_send_trip_report_outcome()`,
    `email_format="compact"`), `EmailOutput(settings).send(...)` über eine
    Recording-Subklasse abgefangen (Muster
    `test_trip_outlook_dispatch_mail.py:200-212`), der Kompakt-Textkörper
    auf genau die gewählten Label-Wert-Paare in Reihenfolge geprüft.

- **AC-3:** Given dieselbe gespeicherte Auswahl wie in AC-2, When die
  Telegram-Bubbles über den echten Versandpfad erzeugt werden, Then zeigt
  die Ausblick-Bubble dieselben gewählten Größen in derselben Reihenfolge,
  jede Zelle MIT ihrem Katalog-Label versehen (nicht nur der Wert).
  - Test: `TelegramOutput(settings).send(...)` über eine Recording-Subklasse
    abgefangen (Muster `test_telegram_rate_limit.py:274`), die
    Ausblick-Bubble auf Label:Wert-Paare in Auswahlreihenfolge geprüft.

- **AC-4:** Given ein Trip mit `display_config.outlook_metrics = []`
  (bewusst geleerte Auswahl), When Kompakt-Mail und Telegram erzeugt werden,
  Then entfällt der gesamte Ausblick-Block in BEIDEN Kanälen vollständig —
  weder die Überschrift „Naechste Etappen" (Kompakt) noch die
  Ausblick-Bubble (Telegram), UND auch kein Zustands-Fallback-Hinweis
  (`outlook_state`-Zweig) tritt an ihre Stelle.
  - Test: gerenderte Kompakt-Mail und Telegram-Bubble-Liste auf vollständige
    Abwesenheit jedes Ausblick-Bezugs geprüft, inklusive eines Falls mit
    gesetztem `outlook_state != FOUND` (der Fallback darf trotzdem nicht
    erscheinen).

- **AC-5:** Given ein Trip führt ein Telegram-eigenes Kanal-Layout
  (`display_config.per_channel_layouts["telegram"]`), das eine gewählte
  Ausblick-Größe NICHT enthält, während dieselbe Größe in der Grundauswahl
  aktiv UND für die Vorschau gewählt ist, When Telegram-Bubbles über den
  echten Versandpfad erzeugt werden, Then erscheint sie trotzdem als Spalte
  im Ausblick — ein enges Kanal-Layout darf den kanal-neutralen Ausblick
  nicht enger schneiden als die Grundauswahl erlaubt (identische Regel zu
  S1 AC-17, jetzt auf Telegram übertragen; der Ausblick hat laut ADR-0055
  Punkt 2 keine Kanal-Ebene).
  - Test: `per_channel_layouts["telegram"]` ohne eine der zwei gewählten
    Ausblick-Größen gesetzt, echter Versandpfad, die abgefangene
    Telegram-Bubble enthält beide Spalten mit korrekten Werten (kein
    Versatz zwischen Label und Zelle).

- **AC-6:** Gegeben der Abschnitt „3-Tages-Vorschau" wird im Trip-Kontext
  angezeigt, wenn mindestens eine Größe gewählt ist, dann trägt er NICHT
  mehr den Hinweistext „Erscheint nur in der E-Mail" — die Auswahl wirkt ab
  dieser Lieferung in allen vier Ausgabeorten. Gegeben derselbe Abschnitt
  wird im Ortsvergleich-Kontext angezeigt, dann trägt er den Hinweistext
  weiterhin unverändert (der Compare-Ausblick existiert nach wie vor nur in
  der E-Mail).
  - Test: DOM-Test/Component-Test für beide Kontexte getrennt — Trip-Rendering
    prüft Abwesenheit von `data-testid="compare-layout-outlook-email-only-hint"`,
    Compare-Rendering prüft dessen Anwesenheit (Regressionsschutz für S1
    AC-7, das denselben Testid nutzte).

- **AC-7:** Given ein Trip OHNE gesetztes `outlook_metrics`, When die
  gesamte Trip-Mail (HTML+Klartext+Kompakt) über denselben Versandpfad
  erzeugt wird, Then bleiben der HTML- und Klartext-Ausblick byte-identisch
  zur S1-Referenz (`tests/fixtures/trip_outlook_reference/outlook_table.html`,
  `outlook_legend.html`, `outlook_block.txt`) — diese Scheibe verändert
  `html.py`/`plain.py` nicht.
  - Test: `test_trip_outlook_parity.py` und die S1-Wirkort-Tests
    (`test_trip_outlook_dispatch_mail.py`) laufen unverändert grün, keine
    Golden-Datei-Anpassung in dieser Lieferung.

## Mutations-Gegenproben

1. `outlook_metrics=_outlook_metrics` wird beim `render_compact(...)`-Aufruf
   in `email/__init__.py` wieder weggelassen (die Regression, die diese
   Scheibe überhaupt auslöst) ⇒ **AC-2** muss rot werden — Kompakt-Mail
   zeigt weiterhin die fünf Legacy-Felder trotz aktiver Auswahl.
2. `outlook_metrics=_outlook_metrics` wird beim
   `render_telegram_bubbles(...)`-Aufruf in `trip_report.py` weggelassen ⇒
   **AC-3** muss rot werden.
3. Die äußere Bedingung `if outlook_metrics != []:` (Implementation Details
   Punkt 3) wird in `compact.py`/`narrow.py` weggelassen, nur die innere
   `if multi_day_trend:` bleibt ⇒ **AC-4** muss rot werden — bei `[]`
   erscheint der Zustands-Fallback-Hinweis statt eines vollständigen
   Wegfalls.
4. `resolve_trip_outlook_metrics(_dc_uncollapsed, report_type)` wird durch
   `_dc_uncollapsed.outlook_metrics or []` ersetzt (`None` als leer
   behandelt, keine Nutzung des Resolvers) ⇒ **AC-1** muss rot werden — der
   Ausblick würde für alle Bestandstrips in Kompakt UND Telegram leer.
5. Die Telegram-Auflösung wird durch einen ZWEITEN, unabhängigen
   `resolve_trip_outlook_metrics(_dc_telegram, report_type)`-Aufruf ersetzt
   (kollabierter statt ungekollabierter Stand, analog S1s F001) ⇒ **AC-5**
   muss rot werden — ein enges Telegram-Kanal-Layout schneidet dann eine
   global gewählte Größe fälschlich weg.
6. Das Telegram-Zeilenformat lässt die Labels weg (nur Werte, Trenner
   `"  "`, wie im Legacy-Zweig) ⇒ **AC-3** muss rot werden, weil der Test
   explizit auf `Label: Wert`-Paare prüft, nicht nur auf die Zahlenwerte.
7. `showEmailOnlyHint={false}` wird bei der Trip-Einbindung in
   `WeatherMetricsTab.svelte` weggelassen (Default `true` bleibt wirksam)
   ⇒ **AC-6** muss rot werden — der Hinweis erscheint im Trip-Kontext
   weiterhin, obwohl die Auswahl dort jetzt in allen vier Kanälen wirkt.

## Prüfhinweis für den Adversary

- Leitfrage (Projektregel „Prüfort muss dem Wirkort entsprechen"): Ist die
  Zusicherung an der Stelle geprüft, an der sie **wirkt** — an der
  zugestellten/gerenderten Kompakt-Mail bzw. Telegram-Bubble über den echten
  Aufrufpfad — oder nur dort, wo der Code steht (isolierter
  `_outlook_lines()`- bzw. Compact-Loop-Aufruf)?
- Zweite Pflichtprobe: die Test-Fixtures für AC-2/AC-3 dürfen NICHT
  dieselbe Auswahl-Reihenfolge wie die AC-1-Referenz verwenden — sonst
  könnte ein Test grün bleiben, der Reihenfolge und Auswahlmenge verwechselt
  (analog S1s Drei-Tage-Fixture mit „unterscheidbaren Werten", vgl.
  `tests/helpers/trip_outlook_selection.py:70-72`).
- Dritte: prüfen, ob der Charakterisierungstest (AC-1) wirklich VOR jeder
  Code-Änderung an `compact.py`/`narrow.py` aufgezeichnet wurde (TDD-RED-
  Reihenfolge) — ein nachträglich aus dem bereits geänderten Code erzeugter
  „Ist-Stand" wäre keine Referenz, sondern eine Bestätigung der Änderung.

## Out of Scope

- **HTML- und Klartext-Trip-Mail** — unverändert, bleiben bei S1s Stand.
- **SMS/Premium-SMS** — bleiben baulich unerreichbar
  (`sms_trip.py` kennt `multi_day_trend` nicht).
- **Ortsvergleich** — `resolve_outlook_metrics()`, `comparison.py`,
  `compare_html.py`, die Compare-Einbindung des geteilten Bausteins bleiben
  unangetastet (Default-Prop hält das Verhalten byte-identisch).
- **Kanal-Ebene für die Auswahl** — bleibt bewusst global, keine
  Wiederaufnahme jener bereits in S1/ADR-0055 abgeschlossenen Diskussion.
- **CI-Ampel-Eintrag für neue Tests dieser Lieferung** — reine
  Kern-Schicht-Tests (kein Playwright/E2E in dieser Scheibe, da keine neue
  Bedienfläche entsteht — der Abschnitt existiert bereits seit S1).
- **Migration bestehender Trips.** Kein Datenmodell-Wechsel, keine
  Rückwirkung auf gespeicherte `outlook_metrics`-Werte.

## Known Limitations

- Die Telegram-Zeile bricht bei vielen gewählten Spalten auf mehrere Zeilen
  um (`_wrap(..., _TG_PROSE_WIDTH)`) — identisch zum bestehenden
  Umbruchverhalten, keine neue Breitensteuerung für diese Scheibe.
- Kompakt-Mail und Telegram teilen sich weiterhin KEINE gemeinsame
  Formatierungsfunktion für die Ausblick-Zeile (Label-Wert-Paare mit
  Leerzeichen-Trenner in Kompakt, mit Doppelpunkt in Telegram) — das ist
  eine bewusste, in dieser Spec begründete Divergenz (Implementation Details
  Punkt 1/2), keine übersehene Duplizierung. Eine spätere Vereinheitlichung
  müsste beide Formate angleichen, was hier nicht verlangt ist.
- Die Vorschau (`PreviewService`) ist für Kompakt-Mail und Telegram nicht
  Gegenstand dieser Spec — S1s Vorschau-Parität-Fix (Known Limitations,
  „falscher Report-Typ") betraf `_build_stage_trend()`, das bereits
  kanalübergreifend korrekt läuft; eine gesonderte Kompakt-/Telegram-
  Vorschau-Prüfung ist hier nicht enthalten, weil `PreviewService` beide
  Formate nicht getrennt rendert (Ist-Stand, ungeändert).

## Definition of Done

- [ ] AC-1 bis AC-7 grün
- [ ] Adversary-Verdict VERIFIED, alle sieben Pflicht-Mutationen gefangen
- [ ] `test_trip_outlook_parity.py` und die S1-Wirkort-Tests bleiben grün
      OHNE Anpassung
- [ ] Neue Referenz-Fixtures (`compact_block.txt`, `telegram_bubble.txt`)
      VOR jeder Code-Änderung an `compact.py`/`narrow.py` aufgezeichnet
      (TDD-RED-Reihenfolge, per Commit-Historie nachvollziehbar)
- [ ] Issue #1720 Scheiben-Checkbox für Scheibe 2 gesetzt, Issue geschlossen
      (beide Scheiben ausgeliefert)

## Architektur-Entscheidung (ADR)

Kein neues ADR. ADR-0055 deckt diese Scheibe bereits konzeptionell ab —
Punkt 1 legt die Drei-Werte-Semantik fest, Punkt 4 die Ein-Auflösung-Regel,
und der Abschnitt „Folgen" kündigt Scheibe 2 wörtlich an
(„Kompakt-Mail und Telegram folgen in Scheibe 2 ... Scheibe 2 legt deshalb
zuerst einen Charakterisierungstest des Ist-Zustands an"). Diese Spec liefert
genau das an — keine neue Grundsatzentscheidung, keine Abweichung von einer
dokumentierten Zusicherung, die ein neues ADR mit Status-Fortschreibung
verlangen würde. Die einzige neue, benannte Design-Entscheidung dieser
Scheibe (Telegram-Zeilenformat MIT Labels, Kompakt-Zeilenformat OHNE
Doppelpunkt) ist eine Rendering-Detailfrage innerhalb des bereits durch
ADR-0055 gesetzten Rahmens, keine Entscheidungsfläche im Sinne von
CLAUDE.md („Kanäle, Provider, Datenmodell/Persistenz, Auth,
Editor-Paradigma, Test-/Deploy-Strategie").

## Changelog

- 2026-08-17: Initial spec created
