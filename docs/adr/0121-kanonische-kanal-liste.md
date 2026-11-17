# ADR-0121: Kanonische Kanal-Liste — ein Datenformat und ein reiner Resolver für Trip und Orte (verfeinert ADR-0119 und ADR-0049)

- **Status:** Akzeptiert
- **Datum:** 2026-11-16
- **Bezug:** GitHub-Issue #3057 (Phase 2 von Epic #3047 „Einstellung = Mail“), Spec `docs/specs/modules/feat_3057_kanal_liste_resolver.md`, Kontext `docs/context/feat-3057-kanal-liste-resolver.md`, Konzept `docs/context/einstellungen_neu.md` §5 Punkt 6 und 8. **Verfeinert:** [ADR-0119](0119-vergleich-channel-layouts.md) (Datenform, Standard ohne Angabe) und [ADR-0049](0049-premium-sms-vierter-kanal.md) (Premium-SMS-Inhalt). Schreibt fort: ADR-0050 (Grundauswahl als Maximum, leer bleibt leer), ADR-0077 (Go speichert `display_config` ungeprüft), ADR-0095 (Kanal-Parität), ADR-0097 (Trip und Orte teilen Code), ADR-0101 (Read-Modify-Write-Migration).

## Kontext

Die Frage „welche Metriken stehen in welcher Folge und Darstellung in Kanal X“ wird heute zweimal und mit unterschiedlichem Vokabular beantwortet. Trip: `display_config.metrics` plus `channel_layouts` plus `channel_layouts_per_report`, Format als `format_mode` (`raw|simplified|None`). Orte: `active_metrics`, `channel_active_metrics` und seit ADR-0119 `channel_layouts` mit `use_friendly_format`. Dazu kommen mehrere Standardfolgen in Python und TypeScript und eine Premium-SMS ohne eigene Liste. Editor und Renderer rechnen daher je Fläche selbst; Abweichungen („Einstellung ≠ Mail“) sind die Folge (Epic #3047).

Phase 2 soll EINE Auflösung schaffen, ohne die zugestellte Mail zu ändern und ohne Bestandsdaten anzufassen. Die Umstellung der Renderer ist Phase 3 (#3058), der Lese-Endpoint für den Editor ist #3066, Ausblick und Stundenverlauf sind #3065.

## Entscheidung

1. **Datenform = Superset von `display_config.channel_layouts` (Variante A).** Schlüssel `email | telegram | sms | premium_sms`. `outlook` und `hourly` sind als Schlüssel **reserviert** (Umsetzung #3065), in Phase 2 weder gelesen noch geschrieben. Eine Zeile ist `{metric_id, enabled, order, format}`; fehlt `order`, gilt der Listenindex. `format` ∈ `raw | simplified | null`; `null` heißt „Standard der Fläche“: Trip Katalog-Standard (`loader._resolve_format_mode`), Orte Roh (ADR-0119 Nr. 4). Beide Standards bleiben in Phase 2 unverändert, eine Vereinheitlichung wäre eine Änderung der zugestellten Mail und gehört nach #3058.
2. **Lese-Adapter, gleichwertig.** Der Resolver liest das Format einer Zeile aus `format`, `use_friendly_format` (ADR-0119, von der Editor-Karte #3042 geschrieben, `true` = simplified, `false` = raw) oder `format_mode` (Trip-`MetricConfig`) und bildet alles auf `raw|simplified|null` ab. Bei mehreren Angaben gilt `format`, dann `format_mode`, dann `use_friendly_format`. Verworfen: ein neuer Schlüssel `kanal_listen` (drittes Vokabular, verbotene Übergangsschicht, Teilung Trip/Orte) und „nur lesen, nichts persistieren“ (löst die zwei parallelen Kanalfelder nicht auf).
3. **Resolver rein lesend, ohne I/O.** `resolve_channel_lists(display_config, surface, report_type)` liefert ein unveränderliches View-Model mit je Kanal einer geordneten Liste von Zeilen. Er bündelt die bestehenden Primitive (Trip: Kaskade `per_report > channel > global` geschnitten mit der Grundauswahl; Orte: `channel_layouts` vor `channel_active_metrics` vor Grundauswahl) und schreibt keine Regel neu (ADR-0097). ADR-0050 bleibt unberührt: Grundauswahl ist das Maximum, Kanal-Listen dürfen nur abwählen.
4. **Leere Liste bleibt leer.** Eine ausdrücklich leere Kanal-Liste (`[]`) bleibt leer (ADR-0050). Das Anhängen neuer Grundauswahl-Metriken beim Lesen (ADR-0119 Nr. 6, Konzept §5 Pkt. 6a) bleibt in Phase 2 in der heutigen Reichweite der Primitive; **verfeinert** ist nur die Abgrenzung, dass der Resolver diese Regel nicht auf `[]` ausdehnt, auch nicht für den Trip.
5. **Premium-SMS.** Der Schlüssel `premium_sms` ist lesbar. Fehlt er, liefert der Resolver die SMS-Liste (heutiges Verhalten, ADR-0049 und ADR-0119 Nr. 5: Premium-SMS sendet den SMS-Text). Eine eigene, kürzere Liste (Konzept Pkt. 8) wird damit vorbereitet, aber in Phase 2 von keinem Renderer ausgewertet; der Versand ändert sich nicht.
6. **Amtliche Warnungen werden nicht gespeichert.** Ihre Position setzt der Resolver fest (E-Mail und Telegram vorn, SMS und Premium-SMS hinten); sie sind keine Zeile der Liste und nicht abwählbar.
7. **Migration lazy.** Ausschließlich der Lese-Adapter; es gibt kein Schreib-Skript und der Resolver schreibt nie. Bestandsdaten bleiben byte-gleich. Die Eager-Migration (Read-Modify-Write mit Merge, Pre-Snapshot-Hook `data_schema_backup.py`, ADR-0101) ist der Contract-Schritt von Phase 3 (#3058), wenn die Altpfade wegfallen. Neue Schlüssel (`premium_sms`, später `outlook`, `hourly`) werden erst mit dem Editor (#3060) geschrieben, weil Go `mergeConfigMap` Unterschlüssel komplett ersetzt (ADR-0077) und daher nur ein voller Stand sicher ist.
8. **Einbindung als Adapter.** `get_metrics_for_channel` und `resolve_compare_render_options` lesen aus dem Resolver, Signaturen und Rückgabetypen bleiben. Renderer und übrige Aufrufer sind unberührt. Der Alarmpfad (`notification_service`) läuft über `get_metrics_for_channel` automatisch mit (ADR-0095). Beweis der Gleichheit: Differenztest neu = alt mit dem Altpfad als Test-Orakel; das Orakel wird in Phase 3 mit den Altpfaden gelöscht.

## Verworfene Alternativen

- **Neuer Schlüssel `kanal_listen` neben `channel_layouts`:** drittes Vokabular, hätte nach Phase 3 eine Übergangsschicht ohne Contract-Schritt hinterlassen (Retro #3047).
- **Format ohne Angabe sofort vereinheitlichen (Orte → Katalog-Standard oder Trip → Roh):** ändert die Mail bestehender Nutzer, gehört nach #3058 mit eigener Freigabe.
- **Sofortige Eager-Migration:** würde vor Wegfall der Altpfade Daten in zwei Formen halten und das Zurückrollen erschweren.

## Konsequenzen

- **Positiv:** Eine Auflösung für alle vier Kanäle und beide Flächen; #3042 braucht keine Änderung, sein Format ist verlustfrei lesbar; die Mail bleibt in jedem Kanal unverändert; Nachprüfungs-Punkt 6 (Mutation `morning_enabled=False`) wird abgedeckt.
- **Negativ / Preis:** Bis Phase 3 bestehen Altpfade und Resolver nebeneinander (Differenztest als Klammer). Die zwei Format-Standards (Trip Katalog, Orte Roh) bleiben als `null` sichtbar, bis #3058 sie vereinheitlicht oder bewusst beibehält.

## Nachtrag 2b (2026-11-16, Issue #3065): Ausblick und Stundenverlauf

Der Resolver liefert zusätzlich die in Punkt 1 reservierten Flächen-Listen `outlook` (Trip und Orte) und `hourly` (nur Orte) im selben Zeilenformat. Spec: `docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md`.

1. **Vokabular.** In `outlook` und `hourly` ist `metric_id` die Katalog-ID (`temperature`), so wie sie der Ausblick schon liefert und der Editor später speichert. Die Orte-Kanäle bleiben bei der Renderer-Kennung (`temp_max`). Diese Zwei-Vokabular-Lage ist bewusst; es gibt keine Rückübersetzungstabelle `dp_field` nach Katalog-ID. Vereinheitlichung gehört zu #3058.
2. **Quellen.** Werte nur aus den bestehenden Altfunktionen: Trip-Ausblick `resolve_trip_outlook_metrics` auf dem ungekollabierten Modell (kein Schnitt mit `channel_layouts.email`), Orte-Ausblick `resolve_compare_outlook_metrics`, beide über `_erbe_grundauswahl` (ADR-0059). Stundenverlauf über die ID-Stufe `resolve_hourly_metric_ids`, aus der `resolve_hourly_metrics` verhaltensgleich `dp_field` bildet. Trip-`hourly` ist immer `None` (keine eigene Trip-Stundenliste).
3. **Format.** Ausblick: wahr = `simplified`, ausdrücklich falsch = `raw`, kein Eintrag oder nicht ausblick-fähig = `null` (Flächen-Standard Roh), über `resolve_*_outlook_formats`. Stundenverlauf: `format` immer `null` (Roh/Einfach dort = #3058).
4. **None-Vertrag.** `None` = Renderer-Vorgabemenge (Altbestand ohne Grundauswahl), `()` = Block entfällt (bewusst leer), sonst Zeilen in Anzeigefolge mit `order` ab 0 und `enabled=True`.
5. **Abschaltflags bewusst draußen.** `hourly_enabled` und `outlook_enabled` stehen auf Preset-Ebene, nicht in `display_config`, und sind nicht Teil des View-Models; der Aufrufer schaltet wie bisher ab.
6. **Kein Adapter-Umbau.** In dieser Scheibe liest niemand `outlook`/`hourly`; die Mail bleibt in jedem Kanal unverändert.

## Nachtrag 3a (2026-11-17, Issue #3096): E-Mail liest aus dem Resolver

Ergänzt Nachtrag 2b Nr. 4 und setzt Nr. 8 (Adapter) für die E-Mail um. Spec: `docs/specs/modules/feat_3096_mail_resolver.md`.

1. **Orte-`hourly` ist nie `None`.** Die Vorgabe „nie eingestellt“ (neun Spalten) löst `compare_hourly_metric_ids` genau einmal auf und liefert sie als konkrete Liste; der Renderer führt keine eigene Vorgabeliste und keinen `None`-Sonderpfad mehr. `None` bleibt nur für Trip-`hourly` und kanalweise als „kein Filter“.
2. **Trip-Mail.** Spalten und Folge (HTML und Klartext) kommen aus `resolve_channel_lists(dc, "trip", report_type).email`, einmal auf dem ungekollabierten Modell; der Adapter `email_col_order` bildet auf `col_key` ab und filtert `selectable`. `resolve_metric_col_order` entfällt.
3. **Format-Standard ohne Angabe** bleibt verschieden (Trip Katalog, Orte Roh). Morgen- und Abendbericht sowie die Orte-Mail sind für den Nutzer unverändert.
4. **Update- und Alarm-Mail folgen der E-Mail-Auswahl** (PO-Entscheidung 2026-11-17, #3096). Der Trip-Briefing-Renderer (`TripReportFormatter.format_email`) schneidet die Datenzeilen jetzt für jeden `report_type` (auch `update` und `alert`) auf die E-Mail-Auswahl zu; bisher galt dort die Grundauswahl. Trips ohne eigene E-Mail-Auswahl sind unverändert. Die zugestellten Alarm-Mails laufen über den eigenen Alarm-Renderer (`output/renderers/alert/`, #921) und sind von dieser Umstellung nicht berührt.

## Nachtrag 3b (2026-11-17, Issue #3097): Roh/Einfach im Orte-Stundenverlauf

Löst Nachtrag 2b Nr. 3 für den Stundenverlauf ein („Roh/Einfach dort = #3058"). Spec: `docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md`.

1. **Quelle.** `hourly[].format` stammt aus `display_config.hourly_metric_formats` (`{kennung: bool}`): wahr = `simplified`, ausdrücklich falsch = `raw`, kein Eintrag = `null` (Roh, ADR-0119 Nr. 4). Schwesterfeld zu `outlook_metric_formats`; ohne das Feld bleibt jede Mail byte-gleich.
2. **Eigener Schalter je Liste (W11).** `channel_layouts.email` (Vergleichstabelle) wirkt nicht auf den Stundenverlauf und umgekehrt. `channel_layouts.hourly` bleibt reserviert (Nr. 7, erst mit #3060 schreibbar; der Go-Merge ersetzt Unterschlüssel). Die spätere Verlagerung dorthin ist verlustfrei möglich.
3. **Einfachformen.** Wind und Böen im HTML als Ampelpunkt (wie die Vergleichstabelle), im Klartext als Wortstufe; Wolken Symbol, Regenwahrscheinlichkeit und Sonnenschein Wortskala; Niederschlag nach der Stunden-Skala (`format_precip_intensity`), nicht der Tagessummen-Skala des Ausblicks. Temperatur, Gewitter und weitere Größen ohne Einfachform ignorieren einen gesetzten Eintrag und bekommen im Editor keinen Umschalter.
4. **Verbraucher.** Versand, Editor-Vorschau und Validator-Vorschau reichen dieselben Stundenformate an HTML- und Klartext-Renderer durch (Vorschau = Mail).

## Nachtrag 3c (2026-11-17, Issue #3098): Telegram liest aus dem Resolver

Setzt Nr. 8 (Adapter) für Telegram um, analog Nachtrag 3a für die E-Mail. Spec: `docs/specs/modules/feat_3098_telegram_resolver.md`.

1. **Trip-Telegram.** Menge, Folge und Roh/Einfach je Zeile kommen aus `resolve_channel_lists(dc, "trip", report_type).telegram`, einmal auf dem ungekollabierten Modell. Ein Adapter übersetzt die Zeilen in die Darstellungsform des Renderers. Die Telegram-Kanal-Ebene wird danach nicht erneut kaskadiert.
2. **Format `null` = Katalog-Standard.** Ein Roh der Grundauswahl wird für eine Telegram-Zeile ohne eigenes Format nicht geerbt (Nr. 1 gilt unverändert).
3. **Orte-Telegram** liest bereits aus dem Resolver und bleibt unverändert; es bekommt nur Nachweis-Fälle. Der Format-Standard ohne Angabe bleibt Roh (ADR-0119 Nr. 4).
4. **Keine Ausgabeänderung.** Die zugestellte Telegram-Nachricht bleibt in allen Bestandsfällen gleich (ADR-0095). Keine Entscheidung wird geändert, daher kein neues ADR.
