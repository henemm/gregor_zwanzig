# ADR-0014: Telegram-Ausgabe — Multi-Bubble-Tabellenformat ersetzt Prosa

- **Status:** Akzeptiert
- **Datum:** 2026-07-03
- **Bezug:** GitHub-Issue #1001, `docs/specs/modules/feat_1001_telegram_redesign.md`,
  ADR-0004 (Signal entfernt), ADR-0012 (Telegram `parse_mode="HTML"`)

## Kontext

Das Telegram-Ausgabeformat hat sich über drei aufeinanderfolgende PO-Entscheidungen in
widersprüchliche Richtungen entwickelt: Issue #360 spezifizierte ursprünglich eine echte
Spalten-Tabelle für Telegram (analog zu Signal). Issue #635 entschied kurz danach
("fest & kuratiert, keine Zahlenwand") auf reine Prosa-Zeilen um — die Tabellen-Logik
(`_narrow_table()`) blieb im Code, wurde aber für Telegram nicht mehr aufgerufen.
Issue #614/615 ergänzte eine optionale SMS-Stil-Kurzform als angehängten Textblock.
Bug #994 deckte strukturelle Formatierungsfehler in der Prosa-Variante auf
(`_tg_extra_detail_line()`: doppelte Klammern, kaputte Einheiten). Eine neue, bereits
vorliegende externe Design-Vorgabe (Claude-Design-Projekt "Gregor Zwanzig") fordert nun
wieder eine tabellarische Darstellung, zusätzlich aufgeteilt in mehrere einzeln
zitierbare Nachrichten ("Bubbles") mit Inline-Keyboard statt Text-Befehls-Hinweis.

`render_narrow()` hat in Produktion genau einen Aufrufer (`trip_report.py:185`, immer
`channel="telegram"` literal) — die ursprüngliche Mehrkanal-Parametrisierung ist totes
Überbleibsel aus der (inzwischen entfernten) Signal-Ära.

## Entscheidung

1. **Breaking Replace statt additivem Duplikat:** `render_narrow()` wird für Telegram
   vollständig durch eine neue Funktion `render_telegram_bubbles()` ersetzt, die eine
   Liste von Nachrichten (`list[TelegramBubble]`) statt eines einzelnen Strings liefert.
   Kein Parallel-Code, da es nur einen Produktions-Konsumenten gibt.
2. **Multi-Message-Versand:** Ein Telegram-Briefing wird künftig als Sequenz separater
   Bot-API-`sendMessage`-Aufrufe verschickt (Kopf, Kurzübersicht, je Segment, Ziel,
   optional Ausblick, Aktionen) statt einer einzigen Nachricht.
3. **Echte Monospace-Tabellen statt Prosa:** Segment-/Ziel-/Ausblick-Bubbles nutzen die
   bereits vorhandene `_narrow_table()`-Logik, gesendet via `<pre>` + `parse_mode="HTML"`
   (Fortführung von ADR-0012, jetzt auch für Briefings statt nur Alerts).
4. **Kurzübersicht immer aktiv:** Die Tages-Kurzübersicht ist kein optionales Feature
   mehr (`telegram_kurzform`-Schalter entfällt funktional), sondern fester Bestandteil
   jedes Briefings, und nutzt `metric_catalog.compact_label`/`col_label` als
   Kürzel-Quelle (dieselbe wie der E-Mail-Tabellenkopf) statt der SMS-Symbole.
5. **Aktionen per Inline-Keyboard statt Text-Footer:** Der bisherige
   "Befehle: report morning, ..."-Hinweis wird durch eine Aktionen-Bubble mit Buttons
   ersetzt. Text-Befehle bleiben über den bestehenden Parser weiter funktionsfähig.
6. **Explizite Supersession:** Diese Entscheidung ersetzt fachlich #635 (Prosa-
   Entscheidung), den Text-Anhang-Teil von #614/615, #887 (Ursprung der jetzt
   entfernten `_tg_extra_detail_line()`) und #612-AC4 (Text-Befehls-Footer). Bug #994
   wird durch die Entfernung des betroffenen Codes miterledigt, nicht separat gefixt.

## Verworfene Alternativen

- **Nur Bugfix von #994** (kaputte Klammern in `_tg_extra_detail_line()` reparieren,
  Struktur unverändert lassen) — verworfen: die externe Design-Vorgabe fordert ein
  grundlegend anderes Format; ein reiner Bugfix hätte die bereits vorhandene, aber
  seit #635 brachliegende Tabellen-Logik weiter ungenutzt gelassen.
- **Additive Parallel-Funktion** (`render_narrow()` unangetastet lassen, neue Funktion
  daneben einführen) — verworfen: `render_narrow()` hat nur einen Produktions-
  Konsumenten; Parallel-Code hätte reine Wartungslast ohne fachlichen Nutzen erzeugt,
  alle "weiteren Konsumenten" sind Tests, die ohnehin migriert werden müssen.
- **Kurzübersicht weiterhin opt-in** (`telegram_kurzform`-Feld als aktiv nutzbare
  Option belassen) — verworfen per User-Entscheidung 2026-07-03: Die Kurzübersicht ist
  im neuen Format ein Kernbestandteil des Briefings, kein optionales Add-on.
- **Kürzel aus `SMS_SYMBOL_BY_METRIC` wiederverwenden** (Fortführung der #614/615-
  Wiederverwendungs-Idee) — verworfen: Die Design-Vorgabe fordert explizit dieselbe
  Kürzel-Quelle wie der E-Mail-Tabellenkopf (`metric_catalog`), nicht die SMS-Symbole;
  beide Kürzel-Sätze divergieren teilweise.

## Konsequenzen

- **Positiv:** Telegram bekommt echte tabellarische Lesbarkeit zurück (wie ursprünglich
  in #360 vorgesehen), Aktionen sind per Button discoverable statt Text-Memorierung, die
  Kurzübersicht ist für jeden Trip konsistent vorhanden statt konfigurationsabhängig.
- **Negativ / Preis:** Mehr Bot-API-Aufrufe pro Briefing (bis zu ~10 statt 1) — erhöhtes
  Rate-Limit-Risiko bei vielen parallelen Trips, noch nicht lastgetestet. Ohne
  Teil-Retry-Mechanik bekommt ein Nutzer bei einem Bubble-Fehlschlag ein unvollständiges
  Briefing (bewusst in Kauf genommen: Konsistenz der Sequenz hat Vorrang vor
  Vollständigkeits-um-jeden-Preis).
- **Folgepflichten:** Issue #623/#640 (mehrtägiger Trend als eigenständiger Baustein)
  müssen NACH #1001 neu spezifiziert werden, nicht parallel dazu. Die
  Frontend-Kanalvorschau (`ChannelPreviewBlock.svelte`/`ChannelPreviewCard.svelte`)
  benötigt ein Folge-Ticket, um die Multi-Bubble-Struktur widerzuspiegeln — bis dahin
  bleibt sie auf dem additiven `body`-Feld. Neue Callback-Namen (`act_*`) müssen bei
  künftigen Telegram-Interaktions-Features (z.B. #704) konsistent von bestehenden
  Präfixen (`dd_`, `tl_`) abgegrenzt bleiben.
