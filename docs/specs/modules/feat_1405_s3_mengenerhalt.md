---
entity_id: feat_1405_s3_mengenerhalt
type: module
created: 2026-10-27
updated: 2026-10-27
status: draft
version: "1.0"
tags: [mengenerhalt, issue-1405, ortsvergleich, trip, renderer, sms, telegram, premium-sms, stille-aufloesung]
---

<!-- Issue #1405 Scheibe S3 (letzte offene Scheibe, Epic #2505): Mengenerhalt über die gerenderte Ausgabe.
     Kontext + Analyse (verbindlich): docs/context/feat-1405-s3-mengenerhalt.md
     Vorgänger-Spec (Abgrenzung "S3 ändert keinen Produktivcode" ist HIERMIT überholt):
       docs/specs/modules/waechter_1405_stille_aufloesung.md
     Formvorbild: docs/specs/modules/fix_1405_s4b_erfolg_heisst_wirkung.md
     Wire-Vertrag SMS (SSOT, wird VOR dem Code geändert): docs/reference/sms_format.md -->

# Mengenerhalt über die gerenderte Ausgabe — Scheibe S3

## Approval

- [ ] Approved

## Purpose

Das Ticket #1405 verspricht: **gewählte Größen hinein → gerenderte Ausgabe → jede erscheint oder ist
ausdrücklich als nicht verfügbar markiert; ein unbekannter Schlüssel ergibt eine sichtbare Meldung, keine
Leerstelle.** Die Wächter S1/S2/S4 erzwingen bisher nur „Verworfenes landet im Log“ — nicht, dass der
Empfänger es **sieht**. Diese Scheibe schließt die Lücke an der Stelle, an der sie wirkt: in der
Mail, im Telegram-Text, in der SMS und in der Premium-SMS.

Für den Empfänger heißt das: Wählt jemand im Ortsvergleich zehn Wettergrößen und eine davon kann nicht
dargestellt werden, verschwindet sie heute **spurlos** (kein Wert, kein Strich, keine Zahl) — man hält die
Nachricht für vollständig. Danach steht dort ein kurzer Hinweis, **wie viele** gewählte Größen nicht gezeigt
werden konnten. Wie viele Größen es sind, ist eine Zahl — keine Empfehlung, keine Bewertung (nur Daten).

**Alle vier Kanäle sind gleichrangig** (E-Mail · Telegram · SMS · Premium-SMS): gleicher Inhalt, kanalgerechte
Form. Der Empfänger weiß unterwegs nicht, welcher Weg gerade trägt; jeder Kanal muss die Frage „fehlt etwas
von dem, was ich gewählt habe?“ beantworten können.

### Befunde (am Code belegt)

| # | Stelle | Verhalten heute | Fläche / Kanal | Danach |
|---|--------|-----------------|----------------|--------|
| L1 | `src/output/renderers/email/compare_html.py:816` (`_visible_metrics`, Filter `if k in by_key`) | gewählte Größe ohne Zeilendefinition verschwindet ohne Markierung | Ortsvergleich E-Mail HTML | Hinweiszeile mit Zahl |
| L2 | `src/output/renderers/comparison.py:143` (`_ordered_rows`, Filter `if m in by_id`) | dito | Ortsvergleich Klartext | Hinweiszeile mit Zahl |
| L3 | `src/output/renderers/compare_metric_ids.py:150-195` (`resolve_enabled_metrics`) | unmappbare Auswahl nur per `logger.warning` (`:186-191`), im Output unsichtbar | Ortsvergleich, **alle** Kanäle | Zahl wird bis in jeden Renderer durchgereicht |
| L4 | `src/output/renderers/comparison.py:611-648` (`_sms_metric_cell` → `None`) und `:944-948` (Zellenaufbau in `_sms_location_part`) | fehlender Wert: Zelle entfällt „ohne Platz oder Zähler“ (Docstring `:629-631`) | Ortsvergleich SMS, Premium-SMS, Telegram-Kurzform | Zähler `?N` am Ortsteil, nur wenn etwas fehlt |
| L5 | Trip: `src/output/renderers/email/html.py:912-935` (`_allowed_col_keys_for_horizon`) | siehe Abschnitt „Befund L5“ — **nicht** durchgängig still | Trip E-Mail | Charakterisierung + eine offene Beobachtung |

**Bereits sauber (nicht anfassen, nur mit Test bewachen):** Trip-SMS (Null-Form `-` / Lückenform `?`, `sms_format.md`
§4), Trip-Telegram (`–`), Trip-E-Mail-Zellen (`–`), Ortsvergleich-Telegram (`… +N gewählte Wettergrößen ohne Wert an
diesem Ort`, `comparison.py:847-860`, aufgerufen `:763-764`).

### Verifizierte Fakten (Code-Lektüre dieser Spec-Phase)

**Premium-SMS im Ortsvergleich — kein eigener Renderer, sondern der `sms_text`-Pfad.**
- `scheduler_dispatch_service.py:718-720` baut genau **einen** Text `_sms_text = render_compare_sms(result,
  enabled_metrics=opts.enabled_metrics_by_channel["sms"])`.
- `send_compare_report(... sms_text=_sms_text ...)` (`scheduler_dispatch_service.py:738`) sendet diesen Text im Zweig
  `if "premium_sms" in effective_channels:` unverändert an Premium-SMS (`notification_service.py:1560-1570`,
  `self._premium_sms_output().send(subject="", body=sms_text)` bzw. `premium_sms_sink(sms_text)`).
- Premium-SMS hat im Ortsvergleich **keine eigene Metrik-Auswahl** (`report_config_resolver.py:339-341`, Kommentar
  „ADR-0049: … Premium-SMS hat keine eigene Auswahl, sie sendet den SMS-Text“; Schlüssel nur `email`/`telegram`/`sms`).
- Folge: Jede Änderung an `render_compare_sms` wirkt **automatisch** auch auf Premium-SMS **und** auf die Telegram-Kurzform
  (`scheduler_dispatch_service.py:721-722`: `_telegram_text = _sms_text`). Ein Test am SMS-Text genügt für den Text; für die
  **Zustellung** ist zusätzlich zu prüfen, dass `sms_sink` und `premium_sms_sink` denselben Text bekommen
  (Wirkort-Prinzip). CLAUDE.md-Aussage „seit #2275 verdrahtet“ stimmt mit dem Code überein.
- `CHANNEL_LIMITS["premium_sms"]` (`channel_layout.py:55`) und `["sms"]` (`:49`) sind beide 153; der Ortsvergleich nutzt
  den Schlüssel `sms` (`comparison.py:~990`). Kein Budgetunterschied.

**Aufrufer der Ortsvergleich-Renderer (für L3 maßgeblich, keine flächendeckende Signaturänderung nötig):**
- Versand: `scheduler_dispatch_service.py:655` (E-Mail), `:719` (SMS), `:726` (Telegram).
- Vorschau: `compare_preview_service.py:68` (Telegram), `:73` (SMS), `:152` (E-Mail).
- Auflösung: `report_config_resolver.py:304` (`resolve_enabled_metrics(display_config.get("active_metrics"))`) und `:337-341`
  (`resolve_channel_enabled_metrics`, ruft intern erneut `resolve_enabled_metrics`, `compare_metric_ids.py:232`).
- Es gibt **keinen weiteren** Aufrufer von `resolve_enabled_metrics` im Produktivcode (`grep` über `src/` und `api/`).
  Damit ist `CompareRenderOptions` (`report_config_resolver.py:~205-222`) der eine Träger, an dem das Verworfene zu den
  Renderern gelangen kann.

**Zwei Arten von „fehlt“ — nicht verwechseln (PO-Entscheid #710/#1585):**
`_resolvable` (`compare_metric_ids.py:172-177`) wirft zwei verschiedene Dinge in einen Topf: (a) Schlüssel **ohne
Renderer-Zuordnung** (ein Defekt — der Nutzer hat etwas gewählt, das das System nicht darstellen kann) und (b) Schlüssel,
die **zentral nicht wählbar** sind (`selectable=False`, z. B. `confidence_pct`, `_non_selectable_keys()` `:130-139`) —
die dürfen **nie** erscheinen, auch nicht als Zähler. Nur (a) wird gemeldet; (b) bleibt still und wird weiterhin nur geloggt.
Ebenso ist eine **vom Kanal bewusst abgewählte** Größe (Kanal schneidet die Grundauswahl, `resolve_channel_enabled_metrics`
`:253-256`) **keine** Lücke.

### Befund L5 (Trip) — am Code geklärt, mit ausdrücklich offenem Rest

`_allowed_col_keys_for_horizon` (`html.py:912-935`) liefert die erlaubten Spaltenschlüssel je Etappen-Horizont und wird an
**einer** Stelle benutzt (`html.py:1160`, danach an `_render_html_table` weitergereicht, `html.py:673-675` filtert
`cols`). Belegt:
1. Eine **enabled** Metrik, deren `horizons[<horizont>]` auf `False` steht, fällt weg. Das ist eine **ausdrückliche
   Nutzerentscheidung** (Tab „Wertebereiche“, Horizont-Schalter), keine stille Auflösung — kein Defekt, aber es braucht
   einen Test, der es bewacht (AC-23).
2. Eine Metrik-ID, die der Katalog nicht kennt, fällt über `except KeyError: continue` (`html.py:929-930`) **still** weg. Ob
   ein gespeicherter Trip eine solche ID überhaupt tragen kann (Migrationsrest), ist **nicht** geklärt → **offen** (siehe
   „Offene Punkte“).
3. `return keys or None` (`html.py:932`): sind **alle** enabled Metriken für den Horizont abgewählt, ist `keys` leer, und
   `None` bedeutet „kein Filter“ — es erscheinen dann **alle** Spalten, nicht keine. Das ist die Umkehrung des Mengenerhalts
   (Überschuss statt Verlust). **Entscheidung (Tech Lead, gestützt auf die bestehende Beschlusslage „leer heißt leer“,
   #1366/#1394):** Abgewählt heißt abgewählt — es erscheinen **keine** Spalten, nicht alle. Der Fall wird im selben Ticket
   behoben (AC-24); `None` bleibt ausschließlich für „Horizont unbekannt“ bzw. „Trip ohne gespeicherte Metrik-Konfiguration“.
4. Zellen: `_extract_hourly_rows` (`trip_report.py:506-523`) baut je Datenpunkt `_dp_to_row(dp, dc)`; ein fehlender Wert
   erscheint laut Kontextanalyse als `–` in der Zelle (nicht als verschwundene Spalte). Das Zeilenbau-Innere (`_dp_to_row`)
   wurde in dieser Spec-Phase **nicht** zeilenweise gelesen — die Aussage wird in `/40` durch AC-20 bewiesen, nicht vorausgesetzt.

## Source

- **Files (Python-Core, produktiv):**
  `src/output/renderers/compare_metric_ids.py` (L3: Verworfenes zurückgeben),
  `src/output/renderers/channel_layout.py` (EIN gemeinsamer Hinweis-Baustein neben `telegram_metric_notice`),
  `src/output/renderers/comparison.py` (L2 Klartext, L3/L4 Telegram + SMS),
  `src/output/renderers/email/compare_html.py` (L1 + L3 HTML),
  `src/services/report_config_resolver.py` (`CompareRenderOptions`: Träger der Zahl),
  `src/services/scheduler_dispatch_service.py`, `src/services/compare_preview_service.py` (Zahl an die Renderer reichen)
- **Files (Doku, vorab):** `docs/reference/sms_format.md` (Wire-Vertrag + Changelog-Zeile v2.36),
  `docs/specs/modules/waechter_1405_stille_aufloesung.md` (Known-Limitations-Abgrenzung korrigieren)
- **Files (Tests):** `tests/test_selection_conservation_rendered.py` (NEU), Fixtures
  `tests/fixtures/compare_kette/` (vorhanden, ggf. eine Datei ergänzen), Helfer `tests/helpers/trip_outlook_selection.py`
- **Identifier:** `resolve_enabled_metrics`, `resolve_channel_enabled_metrics`, `CompareRenderOptions`,
  `_visible_metrics`, `_ordered_rows`, `_sms_metric_cell`, `_sms_location_part`, `render_compare_sms`,
  `render_compare_telegram`, `render_comparison_text`, `render_compare_email`, `telegram_metric_notice`,
  `_telegram_no_data_notice`, `_allowed_col_keys_for_horizon`
- **Nicht im Umfang:** die 22 Funde des Auflösungs-Wächters (`test_resolution_loss_guard.py`) bleiben bei ihren
  Scheiben; keine Änderung am Premium-SMS-Transport; keine neue Metrik-Auswahl für Premium-SMS (ADR-0049);
  `confidence_pct` bleibt nicht wählbar und nirgends sichtbar (#710).

> **Schicht-Hinweis:** ausschließlich **Python-Core** (`src/…`). Kein Go, kein Frontend: die Auswahl wird weiterhin im
> Editor gespeichert, geändert wird nur, wie der Python-Renderer mit nicht Darstellbarem umgeht.
>
> **Trip/Ortsvergleich-Teilung:** Der Hinweis-Baustein liegt **einmal** in `channel_layout.py` (dort wohnt bereits
> `telegram_metric_notice` für beide Flächen, Parameter `context`). Es gibt keinen zweiten Satz Formulierungen je Fläche.
> Eine Trip-Entsprechung zu L1–L4 ist nicht nötig, weil die Trip-Kanäle fehlende Werte bereits zellweise zeigen
> (`–`, `-`/`?`); das ist in AC-20 bis AC-22 mit Test belegt, nicht angenommen.
>
> **Mandantentrennung:** kein neuer Endpoint, keine Persistenz. Die Zahl entsteht je Preset beim Auflösen
> (`resolve_compare_render_options`) und lebt nur in `CompareRenderOptions` dieses einen Aufrufs — kein Modul-Zustand
> (AC-25). Ein Zwei-Nutzer-Endpoint-Test entfällt deshalb mit Begründung; der Nachweis „kein Übertrag zwischen zwei
> Presets/Nutzern“ steht in AC-25.
>
> **Kanäle:** alle vier benannt (AC-1 bis AC-17); Premium-SMS über denselben `sms_text`-Pfad, ausdrücklich mit
> Zustellnachweis (AC-13).

## Estimated Scope

- **Files:** 7 (Quellcode: `compare_metric_ids.py`, `comparison.py`, `email/compare_html.py`, `email/html.py`, `channel_layout.py`, `scheduler_dispatch_service.py`/`compare_preview_service.py`; dazu Test-Datei und `sms_format.md`)
- **LoC produktiv:** ca. +125 / −20 (Resolver-Rückgabe ~25, Träger + Durchreichen ~25, Baustein ~15, HTML ~20, Klartext ~15,
  Telegram ~5, SMS ~25). **Tests:** ca. +300 (zählen nicht). **Doku:** `sms_format.md` + Changelog (zählt nicht).
  Gesamtschätzung inkl. Test-Matrix wie im Kontext: **+250 / −20** → `workflow.py set-field loc_limit_override 500` vorab
  einplanen; vorher `workflow.py status` fragen (LoC-Limit zählt nur produktive Spec-Dateien).
- **Effort:** mittel-hoch. **Risiko:** MITTEL — berührt das 153-Zeichen-Budget und den Wire-Vertrag der SMS (SSOT).
- **Kollisionsprüfung vor Start:** `git log HEAD..origin/main -- src/output/renderers/comparison.py
  src/output/renderers/email/compare_html.py src/services/report_config_resolver.py` (#1412 / #2345 P4 laufen parallel).

## Dependencies

| Entity | Typ | Zweck |
|--------|-----|-------|
| `telegram_metric_notice` (`channel_layout.py:90-109`), `_telegram_no_data_notice` (`comparison.py:847-860`) | Muster / Wortlaut | Formulierung „… +N gewählte Wettergrößen ohne Wert an diesem Ort“ ist die Vorlage |
| `_non_selectable_keys` (`compare_metric_ids.py:130-139`) | Abgrenzung | Nicht-Wählbares (`confidence`) bleibt unsichtbar |
| `docs/reference/sms_format.md` | SSOT | Wire-Vertrag des Zählers, **zuerst** ändern |
| Mail-Validatoren | Gate | `email_spec_validator.py` (Ortsvergleich-Mail), `briefing_mail_validator.py` (Trip-Briefing) |
| ADR-0049 | Entscheidung | Premium-SMS hat keine eigene Auswahl, sendet den SMS-Text |

## Implementation Details

**Reihenfolge (zwingend):** (0) Wire-Vertrag in `sms_format.md` → (1) RED-Matrix → (2) Resolver/Träger → (3) Baustein →
(4) Renderer je Fläche → (5) Vorschau/Versand durchreichen.

**0. Wire-Vertrag SMS (vorab, `sms_format.md`, neue Version 2.36).** Im Ortsvergleich-Ortsteil der SMS steht **nur dann**,
wenn mindestens eine gewählte Größe an diesem Ort keinen darstellbaren Wert hat, ein Zähler `?N` (N = Anzahl ≥ 1) —
unmittelbar nach den Wertzellen und **vor** dem optionalen `!`-Warn-Block: `Name T12 W20 ?2 !TH:M@14`.
Begründung für `?`: dasselbe Zeichen bedeutet im Trip-Briefing „unbekannt / keine Daten“ (§4); `+N` bleibt eindeutig der
**Platzmangel**-Zähler (verdrängte, vorhandene Werte). Beide Zähler sind getrennt und addieren sich mit den sichtbaren
Zellen zur Anzahl der gewählten Größen (Invariante, AC-12). `?` und Ziffern sind GSM-7-Basiszeichen. Ohne fehlenden
Wert bleibt der Ortsteil **Zeichen für Zeichen** wie heute (kein Mehrverbrauch im Normalfall, AC-9). Der Zähler ist —
wie der Warn-Marker — ein **fester Bestandteil** jeder Budgetprüfung (`_assemble` in `_sms_location_part`) und wird nie
vor Wertzellen verdrängt; die Wertzellen weichen ihm (Budget 153, `CHANNEL_LIMITS["sms"]`). Das Gleichgewicht
„Orts-Überlauf `+k Orte`“ bleibt unverändert. *(Tech-Lead-Entscheidung zur Zeichenwahl `?N`; Alternative `-N` verworfen,
weil `-` in der Trip-SMS die Null-Form „geprüft, nichts“ trägt — das wäre das Gegenteil von „fehlt“.)*

**1. Resolver (L3) — Verworfenes durchreichen, ohne Signaturen flächendeckend zu ändern.**
Neue Funktion in `compare_metric_ids.py` (Arbeitsname `resolve_enabled_metrics_report`) liefert
`(resolved: list[str] | None, unresolved: tuple[str, ...])`, wobei `unresolved` **nur** die Schlüssel der Art (a)
enthält (ohne Renderer-Zuordnung), **nicht** die zentral nicht wählbaren (b). `resolve_enabled_metrics(...)` bleibt mit
unveränderter Signatur und Rückgabe bestehen und ruft die neue Funktion (Rückgabe `[0]`) — die Log-Zeile (`logger.warning`)
bleibt erhalten. `resolve_channel_enabled_metrics` ist **nicht** zu ändern: ein Kanal-Eintrag mit unmappbarem Schlüssel wird
über die neue Funktion in `resolve_compare_render_options` zusätzlich ausgewertet.
Träger: `CompareRenderOptions` bekommt ein Feld `unresolved_by_channel: dict[str, int]` (Kanäle `email`, `telegram`, `sms`;
Wert = Anzahl unmappbarer Einträge der Grundauswahl **plus** der Kanal-eigenen Auswahl, dedupliziert nach Schlüssel).
`resolve_compare_render_options` setzt es; Altbestand ohne Feld → leeres Wörterbuch → 0 (kein Rückfall auf irgendeinen
Standardwert im Produkt, `dict.get(ch, 0)` an der **einen** Lesestelle).

**2. Baustein (ein Wortlaut).** In `channel_layout.py` neben `telegram_metric_notice`: eine Funktion
`selection_gap_notice(count, *, scope)`; leer bei `count <= 0`.
`scope="ort"` → `… +N gewählte Wettergrößen ohne Wert an diesem Ort` (**genau** der bestehende Telegram-Wortlaut,
`_telegram_no_data_notice` wird zum dünnen Aufrufer oder entfällt);
`scope="vergleich"` → `… +N gewählte Wettergrößen ohne Wert in diesem Vergleich` (tabellenweit, E-Mail HTML + Klartext).
Die SMS bleibt beim Kürzel `?N` (Wire-Vertrag, Punkt 0) — kein Fließtext im 153-Zeichen-Budget.

**3. Renderer je Fläche.**
- **L1 E-Mail HTML:** `_visible_metrics` (`compare_html.py:~800-816`) meldet zusätzlich die Zahl der gewählten Größen ohne
  Zeilendefinition; `_render_overview_table` setzt unter die Tabelle eine Hinweiszeile (Baustein, `scope="vergleich"`) mit
  Zahl `L1 + L3`. Kein Hinweis bei Zahl 0.
- **L2 Klartext:** `_ordered_rows` (`comparison.py:143`) analog; Hinweiszeile unter der Übersicht.
- **Telegram (L3):** `no_data_count` (`comparison.py:~755`) wird um die Zahl aus `unresolved_by_channel["telegram"]` erhöht
  (gleiche Zeile, gleicher Wortlaut). Die Invariante des Telegram-Pfads („sichtbare + Platzmangel + ohne Wert == gewählt“)
  gilt danach **inklusive** der Unmappbaren.
- **SMS / Premium-SMS / Telegram-Kurzform (L3 + L4):** `_sms_location_part` zählt `cells is None` (Wert fehlt, Zeile/Kürzel
  unbekannt) **plus** `unresolved_by_channel["sms"]` zu `?N`; `render_compare_sms` bekommt dafür einen neuen
  Schlüsselwortparameter (`unresolved_count: int = 0`) — kein Positionsargument, bestehende Aufrufer bleiben gültig.
- **Aufrufseiten:** `scheduler_dispatch_service.py:655/719/726` und `compare_preview_service.py:68/73/152` reichen
  `opts.unresolved_by_channel.get(<kanal>, 0)` durch. Das sind **sechs** Zeilen, keine Signaturwelle (Lehre #1402).

**4. Trip.** L5 Punkt 3 wird repariert (`html.py:932`: nur bei fehlender Metrik-Konfiguration `None`, sonst die — ggf.
leere — Menge; +~5 LoC). Die Tests (AC-20 bis AC-24) beweisen den Ist-Stand der übrigen Stellen; zeigt ein Test einen Defekt (z. B. AC-20 rot), ist das ein Fund und wird **im selben Ticket** behoben (PO-Regel),
nicht als Ausnahme geparkt.

**Verboten (Gaming):** Schwellen oder Erwartungen anpassen, damit etwas grün wird; den Zähler nur im Log erhöhen;
`getattr(opts, …, 0)`-Stillrückfall im Produkt; Hinweis in den Text schreiben, aber nicht bei Zahl 0 unterdrücken;
`confidence_pct` oder andere nicht wählbare Größen melden; einen zweiten Hinweis-Wortlaut pro Fläche.

## Expected Behavior

- **Input:** ein Ortsvergleich- oder Trip-Bericht mit N gewählten Wettergrößen, davon beliebig viele ohne Wert an
  einem Ort, ohne Zeilendefinition oder mit nicht auflösbarem Schlüssel.
- **Output:** in jedem der vier Kanäle ist jede gewählte Größe sichtbar **oder** ihre Anzahl ist genannt. Nichts
  verschwindet spurlos. Ohne Lücke ist die Ausgabe byte-gleich zu heute.
- **Side effects:** keine; keine zusätzlichen Nachrichten, kein neuer Endpoint, keine Persistenz.

## Acceptance Criteria

Prüfort-Regel: Alle Tests gehen durch den **echten Render-Eingang** (`render_compare_email`/`render_comparison_text`/
`render_compare_telegram`/`render_compare_sms`, Trip über `render_trip_mail()` aus `tests/helpers/trip_outlook_selection.py`)
und für die Zustellung durch `send_one_compare_preset` mit den Außengrenzen-Senken (`mail_sink`/`sms_sink`/`telegram_sink`/
`premium_sms_sink`). Die Auswahl wird als gespeicherte `display_config` (`active_metrics` mit einer unmappbaren Kennung und
einer Größe ohne Zeilendefinition) eingespeist, nicht als fertige Renderer-Liste — sonst fällt L3 durch das Raster.

### A. Ortsvergleich — E-Mail (HTML und Klartext)

- **AC-1:** Given ein Ortsvergleich mit mehreren gewählten Wettergrößen, von denen eine keine Zeilendefinition in der Übersicht hat / When die Ortsvergleich-Mail (HTML) gerendert wird / Then steht unter der Übersichtstabelle eine Hinweiszeile „… +1 gewählte Wettergrößen ohne Wert in diesem Vergleich“, und jede der übrigen gewählten Größen hat ihre Zeile in der gewählten Reihenfolge.
  - Test: `_make_comparison_result` mit drei Orten, `active_metrics` mit einer Größe ohne CV2-Zeile; HTML enthält Hinweis mit Zahl 1 und alle anderen Zeilen.
- **AC-2:** Given eine gespeicherte Auswahl, die einen Schlüssel ohne Renderer-Zuordnung enthält / When die Ortsvergleich-Mail (HTML) gerendert wird / Then ist dieser Schlüssel in der Zahl der Hinweiszeile mitgezählt (Zahl = nicht darstellbare Größen insgesamt) statt nur im Log zu stehen.
  - Test: Auswahl mit einem erfundenen Schlüssel; Zahl im Hinweis um 1 höher als ohne ihn.
- **AC-3:** Given ein Ortsvergleich, in dem jede gewählte Größe darstellbar ist / When die Mail (HTML) gerendert wird / Then erscheint **kein** Hinweis, und die Zeilen sind unverändert gegenüber dem Stand vor dieser Scheibe.
  - Test: Normalfall aus `tests/fixtures/compare_kette/basis.json`; kein „ohne Wert in diesem Vergleich“; Zeilenfolge gleich der Auswahlreihenfolge.
- **AC-4:** Given dieselbe Auswahl wie in AC-1/AC-2 / When die Klartext-Fassung derselben Mail gerendert wird / Then steht dort dieselbe Hinweiszeile mit derselben Zahl (gleicher Wortlaut aus demselben Baustein wie im HTML).
  - Test: HTML-Zahl == Klartext-Zahl; Wortlaut identisch (ein Baustein).
- **AC-5:** Given ein Ortsvergleich ohne Lücke / When die Klartext-Fassung gerendert wird / Then erscheint kein Hinweis und die Ausgabe ist unverändert.
  - Test: Normalfall, Vergleich gegen die bisherige Ausgabe (Zeichenfolge aus `basis.json`-Lauf).

### B. Ortsvergleich — Telegram (ausführlich und Kurzform)

- **AC-6:** Given eine Auswahl mit einem unmappbaren Schlüssel und einer Größe, die an einem Ort keinen Wert hat / When die Telegram-Nachricht gerendert wird / Then zeigt jeder Ortsblock „… +N gewählte Wettergrößen ohne Wert an diesem Ort“, und N enthält die Größe ohne Wert **und** den unmappbaren Schlüssel.
  - Test: Zwei Orte, nur einer mit fehlendem Wert; Zahl am betroffenen Ort = fehlende + unmappbare, am anderen = nur unmappbare.
- **AC-7:** Given ein Ortsvergleich ohne Lücke / When die Telegram-Nachricht gerendert wird / Then erscheint kein „ohne Wert“-Hinweis, und der „+N weitere … (Telegram-Limit)“-Hinweis für Platzmangel bleibt davon getrennt und unverändert.
  - Test: Normalfall; Platzmangel-Fall mit mehr als 7 Größen aus `kanal_ueberlauf.json` zeigt weiterhin nur den Platzmangel-Hinweis.
- **AC-8:** Given beliebiger Ortsvergleich im Telegram-Kanal / When die Nachricht gerendert wird / Then gilt je Ort: Anzahl sichtbarer Zellen + Platzmangel-Zahl + „ohne Wert“-Zahl = Anzahl der gewählten Größen (Mengenerhalt).
  - Test: parametrisiert über Normalfall, Platzmangel, fehlender Wert, unmappbarer Schlüssel; Summe wird aus dem **gerenderten Text** gezählt, nicht aus Zwischenwerten.
- **AC-9:** Given der Telegram-Stil „Kurzform“ ist gewählt / When der Ortsvergleich versendet wird / Then trägt die Telegram-Nachricht denselben Text wie die SMS (`_telegram_text = _sms_text`) und damit denselben Zähler `?N`.
  - Test: `send_one_compare_preset` mit `telegram_style="kurzform"`; `telegram_sink`-Text == `sms_sink`-Text.

### C. Ortsvergleich — SMS und Premium-SMS

- **AC-10:** Given ein Ortsvergleich, bei dem an einem Ort eine gewählte Größe keinen Wert hat / When die SMS gerendert wird / Then steht im Ortsteil dieses Ortes nach den Wertzellen ein Zähler `?1` (Format `Name T12 W20 ?1`); Orte ohne Lücke tragen keinen Zähler.
  - Test: zwei Orte, einer mit fehlendem Wert; `?1` genau einmal, beim betroffenen Ort.
- **AC-11:** Given ein Ortsvergleich ohne jede Lücke / When die SMS gerendert wird / Then ist der Text Zeichen für Zeichen identisch zum Stand vor dieser Scheibe (kein Mehrverbrauch im Normalfall) und enthält weder `?` als Zähler noch ein zusätzliches Leerzeichen.
  - Test: Erwartungstext aus dem unveränderten Lauf gegen `basis.json`; Gleichheit `==`, nicht nur Länge.
- **AC-12:** Given eine Auswahl mit sichtbaren, verdrängten (Platzmangel, `+N`) und fehlenden (`?N`) Größen / When die SMS gerendert wird / Then ergibt je Ort sichtbare Zellen + `+N` + `?N` die Anzahl der gewählten Größen, und `+N` (vorhandene, verdrängte Werte) und `?N` (fehlende Werte) sind getrennt lesbar.
  - Test: Fixture `kanal_ueberlauf.json` plus fehlender Wert; Summe aus dem SMS-Text gezählt.
- **AC-13:** Given die SMS wird für Premium-SMS und normale SMS versendet / When der Ortsvergleich zugestellt wird / Then bekommt der Premium-SMS-Weg **denselben** Text wie der SMS-Weg, einschließlich `?N`, und kein Kanal erhält eine ältere oder zählerlose Fassung.
  - Test: `send_one_compare_preset` mit Kanälen `sms` und `premium_sms`; `sms_sink`- und `premium_sms_sink`-Text identisch und enthalten `?1`.
- **AC-14:** Given eine SMS mit Zähler `?N` / When ihre Länge und Zeichen geprüft werden / Then gilt `len(text) <= 153`, alle Zeichen sind GSM-7, und der Zähler wird bei Platzmangel nicht vor Wertzellen verdrängt (die Wertzellen weichen, der Zähler bleibt wie der `!`-Warn-Marker).
  - Test: Grenzfall mit vielen Orten und langen Ortsnamen; `len <= 153` und GSM-7-Prüfung über den vorhandenen Test-Helfer; Zähler steht noch im Text.
- **AC-15:** Given eine gespeicherte Auswahl mit einem unmappbaren Schlüssel / When die SMS gerendert wird / Then erhöht dieser Schlüssel den Zähler `?N` an **jedem** Ort um 1 (er fehlt überall), wie der Telegram-Text es zählt.
  - Test: zwei Orte, Auswahl mit erfundenem Schlüssel; beide Ortsteile tragen `?1`.

### D. Ortsvergleich — Abgrenzungen

- **AC-16:** Given eine Auswahl, die eine zentral nicht wählbare Größe (z. B. `confidence_pct`) enthält / When der Bericht in **irgendeinem** der vier Kanäle gerendert wird / Then erscheint diese Größe weder als Zeile noch als Teil einer Zahl oder eines Hinweises; sie wird weiterhin nur geloggt.
  - Test: Auswahl mit nicht wählbarer Größe; weder E-Mail (HTML/Klartext), Telegram noch SMS zeigen sie, und es erscheint kein Hinweis (Zahl bleibt 0).
- **AC-17:** Given ein Kanal wählt eine Größe der Grundauswahl bewusst ab (`channel_active_metrics`) / When dieser Kanal gerendert wird / Then ist die abgewählte Größe keine Lücke: kein Hinweis, keine Zahl.
  - Test: Fixture `kanal_auswahl.json`; Kanal mit Abwahl trägt keinen Hinweis, die anderen Kanäle zeigen die Größe weiter.
- **AC-18:** Given die Vorschau und der Versand desselben Ortsvergleichs / When beide gerendert werden / Then tragen sie in jedem Kanal denselben Hinweis bzw. Zähler (Vorschau lügt nicht).
  - Test: `compare_preview_service` gegen `send_one_compare_preset` mit denselben Eingaben; Texte gleich.
- **AC-19:** Given der Hinweis-Wortlaut / When er in HTML, Klartext und Telegram verglichen wird / Then stammt er aus **einem** Baustein (`selection_gap_notice`); der Telegram-Wortlaut „… +N gewählte Wettergrößen ohne Wert an diesem Ort“ ist unverändert.
  - Test: Wortlaut-Vergleich der drei Ausgaben mit dem Baustein; Mutation (Baustein-Wortlaut ändern) macht alle drei rot.

### E. Trip — Charakterisierung (E-Mail, Telegram, SMS)

- **AC-20:** Given ein Trip, dessen Auswahl eine Größe enthält, zu der an einem Zeitpunkt kein Wert vorliegt / When die Trip-Mail (HTML) gerendert wird / Then hat die Größe weiterhin ihre Spalte, und die Zelle zeigt `–` statt zu verschwinden.
  - Test: `render_trip_mail()` mit einem Datenpunkt ohne Wert; Spalte vorhanden, Zelle `–`.
- **AC-21:** Given derselbe Trip / When die Telegram-Nachricht gerendert wird / Then steht für die Größe ohne Wert `–`; die Größe verschwindet nicht.
  - Test: Telegram-Render des Trips; Platzhalter vorhanden.
- **AC-22:** Given derselbe Trip / When die SMS (und damit Premium-SMS und Telegram-Kurzform, gleicher Text) gerendert wird / Then trägt das Token der Größe die Null-Form `-` bzw. die Lückenform `?` laut `sms_format.md` §4; das Token fehlt nicht.
  - Test: Trip-SMS mit Datenlücke; Token mit `?` vorhanden; Token mit echter Null mit `-`.
- **AC-23:** Given ein Trip, in dem eine Größe für den Horizont „morgen“ abgewählt, für „heute“ aber gewählt ist / When die Mail für beide Horizonte gerendert wird / Then erscheint die Größe nur im Horizont, in dem sie gewählt ist, und fehlt im anderen — als bewusste Nutzerentscheidung, nicht als Verlust.
  - Test: `horizons={"today": True, "tomorrow": False}`; Spalte nur beim Horizont „heute“.
- **AC-24:** Given ein Trip, in dem **alle** aktivierten Größen für den Horizont abgewählt sind / When die Mail gerendert wird / Then enthält die Tabelle dieses Horizonts **keine** Wertespalten (abgewählt heißt abgewählt, nicht „alle“); ein Trip ohne gespeicherte Metrik-Konfiguration zeigt weiterhin die Standardspalten.
  - Test: der Test benennt den Ist-Stand ausdrücklich; wird er entschieden, ändert nur die Entscheidung den Test, nie ein Zufall.

### F. Mandantentrennung, Anti-Gaming, Doku, Gate

- **AC-25:** Given zwei Ortsvergleiche (zwei Nutzer bzw. zwei Presets), von denen einer eine unmappbare Kennung gewählt hat / When sie nacheinander aufgelöst und gerendert werden / Then trägt nur der Bericht des ersten den Hinweis; der zweite bleibt ohne Hinweis (kein Übertrag, kein Modul-Zustand, kein `"default"`-Rückfall).
  - Test: zwei `resolve_compare_render_options`-Aufrufe in beiden Reihenfolgen; `unresolved_by_channel` getrennt.
- **AC-26:** Given der Wire-Vertrag / When die Scheibe fertig ist / Then beschreibt `docs/reference/sms_format.md` den Zähler `?N` (Position, Bedeutung, Abgrenzung zu `+N`, Normalfall unverändert) mit neuer Changelog-Zeile v2.36, **vor** dem Code geändert, und `waechter_1405_stille_aufloesung.md` nennt S3 nicht mehr als „ändert keinen Produktivcode“.
  - Test: Doku-Vertragstest (`# doc-compliance-test`), nur Doku-Dateien gelesen, kein Produkt-Quelltext.
- **AC-27:** Given die neuen Tests / When der Adversary gezielt verfälscht (a) Filter `if k in by_key` in `_visible_metrics` wieder ohne Zählung, (b) `if m in by_id` in `_ordered_rows` ohne Zählung, (c) `unresolved` nicht an `CompareRenderOptions` durchreichen, (d) den Zähler in `_sms_location_part` entfernen, (e) Zähler im SMS-Normalfall immer anhängen, (f) nicht wählbare Größen mitzählen, (g) Zähler aus dem Budget herausrechnen (Länge über 153), (h) Aufrufseite Versand oder Vorschau ohne Zahl lassen / Then wird je Verfälschung mindestens ein **Verhaltenstest** rot, der am gerenderten Text misst; welche Tests rot wurden, wird gemeldet. Bleibt eine Verfälschung grün, ist das ein Finding.
  - Test: Mutation per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`).
- **AC-28:** Given die Änderung an Mail-Inhalts-Dateien / When der Commit vorbereitet wird / Then sind das Renderer-Commit-Gate (Modus-Matrix-Test) und die Validatoren frisch grün: `email_spec_validator.py` für die Ortsvergleich-Mail (Marker `compare`), und — falls die Trip-Charakterisierung Trip-Dateien berührt — `briefing_mail_validator.py`; geprüft gegen eine echt zugestellte Staging-Mail, nicht gegen eine Attrappe.
  - Test: Staging-Verifikation (Ortsvergleich mit bewusst unmappbarer Kennung); Exit 0 beider Validatoren, Hinweiszeile in der zugestellten Mail sichtbar.

## Tests

- **Datei:** `tests/test_selection_conservation_rendered.py` (Kern-Schicht: deterministisch, ohne Netz, kein Mock-Theater;
  Fakes nur an den Außengrenzen — Senken `mail_sink`/`sms_sink`/`telegram_sink`/`premium_sms_sink`).
- **Aufbau:** Matrix **Fläche × Kanal**, ein Test pro AC aus Nutzersicht („was steht beim Empfänger“):
  - Ortsvergleich × {E-Mail HTML, Klartext, Telegram rich, Telegram Kurzform, SMS, Premium-SMS} → AC-1 bis AC-19
  - Trip × {E-Mail HTML, Telegram, SMS (inkl. Premium-SMS-Text)} → AC-20 bis AC-24
  - Quer: AC-25 bis AC-28
- **Eingaben:** Builder `_make_comparison_result` (aus `tests/tdd/test_compare_render_options_resolver.py` — als Helfer in
  die Testdatei übernehmen oder aus `tests/helpers/compare_briefings.py` ziehen, `ls` des Zielordners vorher),
  Fixtures `tests/fixtures/compare_kette/` (`basis.json`, `kanal_auswahl.json`, `kanal_ueberlauf.json`; für die Lücken-Fälle
  eine neue kleine `selection_luecke.json`), Trip über `tests/helpers/trip_outlook_selection.py` (`render_trip_mail()`).
  Das Prüfobjekt wird **relativ zur Testdatei** aufgelöst (Pfadregel #1409).
- **Rot-vor-Grün:** AC-1, -2, -4, -6, -10, -13, -15 sind heute rot (Fund). AC-3, -5, -7, -11, -16, -17, -20 bis -23 sind heute
  grün und bewachen den Bestand (Rückdreh-Gegenprobe in der Mutation AC-27).
- **Zwei Nutzer:** kein Endpoint berührt, deshalb kein Zwei-Nutzer-Endpoint-Test; der Mandanten-Nachweis ist AC-25
  (kein gemeinsamer Zustand zwischen zwei Auflösungen).
- **Verifikationspflicht:** Mail-Inhalt ändert sich → Renderer-Commit-Gate + `email_spec_validator.py` (Ortsvergleich)
  bzw. `briefing_mail_validator.py` (Trip-Briefing); nur bei Exit 0 darf „E2E bestanden“ gelten. Aufruf nur mit
  benannter Testdatei (`uv run pytest tests/test_selection_conservation_rendered.py`).

## Known Limitations

- Der SMS-Zähler `?N` nennt die **Anzahl**, nicht **welche** Größen fehlen — im 153-Zeichen-Budget ist kein Platz für
  Namen. Die Namen stehen in der E-Mail-Fassung (dort als Zahl; die Zeilenbeschriftung der fehlenden Größen ist nicht
  vorhanden, weil eben keine Zeilendefinition existiert).
- Die Hinweiszeile in E-Mail und Klartext ist tabellenweit (eine Zahl je Vergleich), nicht je Ort; ein Ort ohne Wert für
  eine **darstellbare** Größe zeigt in der Mail weiterhin den Platzhalter `–` in der Zelle (bestehendes Verhalten).
- `partial`-Monitoring u. Ä. bleibt unberührt; die Scheibe ändert keinen Versandweg und keinen Status.
- Der „Wächter“-Aspekt (AST-Prüfung, dass jede künftige Verwerfung einen Hinweis trägt) bleibt bei S1/S2; S3 beweist die
  Wirkung für die heute bekannten Stellen L1–L4 und die Trip-Kanäle, nicht für künftig neu hinzukommende.

## Offene Punkte (ausdrücklich nicht geraten)

1. **L5-Rest (entschieden, Tech Lead):** „alle abgewählt“ ⇒ keine Spalten (AC-24, Reparatur in `html.py:932`). Offen
   bleibt nur, ob ein gespeicherter Trip eine dem Katalog unbekannte Metrik-ID tragen kann (`except KeyError`,
   `html.py:929-930`): Der Zweig bekommt in jedem Fall ein `logger.warning`; ein Test, der eine solche ID einspeist, klärt
   in `/40`, ob sie erreichbar ist.
2. **`_dp_to_row`-Innenleben (Trip):** nicht zeilenweise gelesen; AC-20 bis AC-22 beweisen es erst in `/40`.
3. **Zeichenwahl `?N`:** Tech-Lead-Entscheidung (siehe Implementation Details 0); liegt der Wire-Vertrag in `sms_format.md`
   fest, ist er die einzige Quelle.
4. **Test-Helfer-Ablage:** `_make_comparison_result` existiert in mehreren Testdateien (`test_compare_render_options_resolver.py:43`,
   `test_issue_1107_compare_sections.py:96`, `test_issue_1150_compare_validator_hourly.py:63`); vor Neuanlage `ls` des
   Zielordners, nicht vierte Kopie anlegen.

## Risiken

- **153-Zeichen-Budget:** Der Zähler ist fester Bestandteil jeder Budgetprüfung; im Grenzfall (viele Orte, lange Namen) verlieren
  Wertzellen einen Platz. Das ist gewollt (Ehrlichkeit vor Dichte), aber im Wire-Vertrag zu benennen und mit AC-14 zu bewachen.
- **Dateikollision:** `comparison.py` und `compare_html.py` werden von #1412/#2345-P4 berührt; vor Start `git log HEAD..origin/main -- <datei>`.
- **Renderer-Commit-Gate:** blockiert den Commit bis Modus-Matrix-Test und Validator frisch grün sind (AC-28).
- **Telegram-Wortlaut „an diesem Ort“ für Unmappbare:** streng genommen fehlt die Größe überall, nicht nur „an diesem Ort“;
  bewusst nicht anders formuliert, um den bestehenden Wortlaut zu erhalten (PO-Vorgabe: Muster übertragen, nichts neu erfinden).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. ADR-0049 (Premium-SMS sendet den SMS-Text, keine eigene Auswahl) bleibt unverändert und trägt AC-13.
- **Rationale:** Reparatur innerhalb der Entscheidung „Verworfenes ist sichtbar“ (#1405); keine Entscheidungsfläche (Kanäle,
  Provider, Datenmodell, Auth, Editor, Deploy) verändert. Der SMS-Wire-Vertrag wird über seine SSOT (`sms_format.md`,
  Changelog v2.36) geändert, nicht über ein ADR.

## Changelog

- 2026-10-27: v1.0 — erste Fassung (spec-writer), Grundlage `docs/context/feat-1405-s3-mengenerhalt.md`; Fragen L5 und Premium-SMS
  per Code-Lektüre geklärt (Premium-SMS = `sms_text`-Pfad; L5 teilweise offen).
