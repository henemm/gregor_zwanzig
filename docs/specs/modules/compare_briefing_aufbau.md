---
entity_id: compare_briefing_aufbau
type: refactor
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: feat-2983-gemeinsamer-berichtsaufbau
tags: [ortsvergleich, vorschau, versand, paritaet, 2983]
---

# Ortsvergleich: gemeinsamer Berichtsaufbau fuer Vorschau und Versand

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich setzt seinen Bericht heute an zwei Stellen zusammen: im Versand
(`send_one_compare_preset`) und in der Vorschau (`ComparePreviewService`). Ein neuer
Baustein `src/services/compare_briefing_aufbau.py` wird die einzige Stelle, die den
Berichtsinhalt (Profil, Wetterlauf, Render-Optionen, Betreff, E-Mail/SMS/Telegram)
aufbaut. Versand = Baustein + Nebenwirkungen + Senden, Vorschau = Baustein. Damit kann
die Vorschau nicht mehr vom Versand abweichen (Folge von #1986, Paar 2).

## Source

- **File:** `src/services/compare_briefing_aufbau.py` (neu)
- **Identifier:** `compare_wetter_laden`, `compare_email_rendern`, `compare_kanaltexte_rendern`, `compare_briefing_bauen`, `compare_zieltag_bestimmen`, `order_locations_by_ids`, `build_compare_preset_subject`

> **Schicht:** ausschliesslich Python-Core (`src/services/`). Kein Frontend, keine Go-API.
>
> **Trip/Ortsvergleich-Teilung:** Der Trip-Teil des Issues #2983 ist als eigenes Issue
> #3128 abgespalten (siehe Out of Scope) und wird danach nach demselben Muster gebaut.
> Das Pendant existiert also bewusst noch nicht; die einseitige Anlage ist durch die
> 250-Zeilen-Grenze je Durchlauf begruendet, jeder Teil ist allein lieferbar.
>
> **Mandantentrennung:** `user_id` kommt aus dem Aufruf, nie `"default"`. Tests mit zwei
> verschiedenen Nutzern.
>
> **Kanaele:** E-Mail, Telegram und SMS werden vom Baustein gebaut. Premium-SMS nutzt
> denselben SMS-Text und wird weiter nur im Versand (NotificationService) zugestellt;
> sein Inhalt aendert sich nicht.

## Estimated Scope

- **LoC:** +~170 / -~150 (hinzugefuegte Produktionszeilen Ziel < 250)
- **Files:** 3 Quelldateien (1 neu, 2 geaendert) plus 4 Testdateien
- **Effort:** medium (Risiko hoch, weil jeder Ortsvergleich-Versand durch den Umbau laeuft)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.comparison_parallel.run_comparison_parallel` | module | Wetterlauf je Ort |
| `services.report_config_resolver` (`resolve_compare_render_options`, `resolve_compare_time_window`) | module | Render-Optionen, Tagesfenster |
| `output.renderers.comparison` (`render_compare_email/telegram/sms`) | module | Kanal-Renderer (unveraendert) |
| `services.compare_alert_channels.effective_compare_telegram_style` | module | Telegram-Stil kurzform/langform |
| `app.ampel` (`profile_for_template`, `template_id_for`) | module | Bewertungsprofil aus der Vorlage |
| `utils.timezone` (`first_resolvable_tz`, `local_dt`) | module | Zieltag = Ortstag |
| `services.scheduler_dispatch_service` | module | Aufrufer (Versand); darf vom Baustein NICHT importiert werden |
| `services.compare_preview_service` | module | Aufrufer (Huelle); darf vom Baustein NICHT importiert werden |
| `services.compare_alert_preview_service` | module | nutzt `ComparePreviewService._load_preset` weiter |
| `tests/tdd/test_profil_ampel_kette.py` | test | zaehlt `template_id_for`-Aufrufe je Funktion (AST) |

## Implementation Details

**Aufteilung des Bausteins.** Die Reihenfolge im Versand ist fachlich festgelegt:
Wetterlauf, dann Kontingent-Abbruch (`manuell_abgelehnt`), dann `no_weather`-Regel,
dann `undelivered`, dann E-Mail rendern, dann innerhalb des try-Blocks (Anker-Pfad,
#1629) SMS und Telegram rendern. Ein einziger Rundum-Aufruf wuerde diese Reihenfolge
und den try-Block veraendern. Deshalb besteht der Baustein aus vier kleinen,
zusammengehoerigen Funktionen in EINEM Modul; der Versand ruft sie an den Stellen, an
denen heute gerendert wird, die Vorschau ruft den Gesamtaufruf:

1. `compare_wetter_laden(preset, locations, zieltag, user_id)`: Profil
   (`profile_for_template(template_id_for(preset))`), Tagesfenster, `run_comparison_parallel`
   mit `COMPARE_FORECAST_HOURS`, `call_source="vergleich"`, Amtliche-Warnungen-Schalter.
   Liefert ein kleines Ergebnisobjekt (Profil, `ComparisonResult`, Render-Optionen,
   Name). Wirft Ausnahmen des Wetterlaufs unveraendert weiter; die Umwandlung in
   `no_weather` (`weather_failure_as_outcome`) bleibt im Versand um genau diesen Aufruf.
2. `compare_email_rendern(kontext, *, lang, undelivered=None)`: `render_compare_email`
   mit allen bisherigen Parametern; `undelivered` ist optionaler Eingang (Vorschau: None).
3. `compare_kanaltexte_rendern(kontext, *, lang)`: SMS-Text und Telegram-Text.
   `effective_compare_telegram_style(preset) == "kurzform"` ergibt den SMS-Text,
   sonst `render_compare_telegram` (genau die Logik, die heute im Versand steht).
4. `compare_briefing_bauen(preset, locations, zieltag, user_id, *, lang, undelivered=None)`:
   Gesamtaufruf = 1 + 2 + 3 + Betreff (`build_compare_preset_subject`); Rueckgabe als
   Woerterbuch/Objekt mit Betreff, `email_html`, `email_text`, `telegram`, `sms`.

Ohne Nebenwirkungen: kein Versand, kein Kontingent, kein Anker, keine Vorfaelle, keine
Persistenz, keine Schreibzugriffe. `undelivered` wird vom Aufrufer ermittelt und
hereingereicht (Lesezugriff auf Vorfaelle bleibt im Versand).

**Zirkelimport.** `order_locations_by_ids` (heute in `compare_preview_service`) und
`build_compare_preset_subject` (heute in `scheduler_dispatch_service`) werden in den
Baustein verschoben. Beide Alt-Module importieren sie von dort und halten sie als
Re-Export unter dem alten Namen (Tests importieren `build_compare_preset_subject` aus
`scheduler_dispatch_service`; ein Patch dieser Namen findet sich in den Tests nicht, es
gibt nur Importe). Der Baustein importiert weder `scheduler_dispatch_service` noch
`compare_preview_service`; die Funktions-lokalen Imports in beide Richtungen entfallen.

**Zieltag (im Code geprueft).** Vorschau (`_resolve_target_date`, Ast `given is None`)
und Versand (`send_one_compare_preset`, Ast `target_date is None`) bestimmen den Tag
fachlich IDENTISCH: `first_resolvable_tz(locations)` und `local_dt(jetzt_utc, zone).date()`,
also der Ortstag des ersten aufloesbaren Orts (#1727 S5b/S5c, ADR-0044). Unterschied nur
im `context_label` des Logs. Daher gemeinsame Ermittlung `compare_zieltag_bestimmen(
locations, jetzt_utc, *, context_label)` im Baustein. Beide Seiten rufen sie fuer den
Fall „kein Tag uebergeben". Der Slot-Tag des Versands (`target_date` mit
`tage_ab_ortstag`, Kontrakt #1661 F003) und das Parsen von ISO-String/`date` der Vorschau
bleiben bei der jeweiligen Seite; der Baustein bekommt den fertigen `date` als Eingang.

**Versand (`send_one_compare_preset`).** Name und Signatur unveraendert (72 Testdateien
patchen ihn). Er ruft `compare_wetter_laden` anstelle von Profil/Engine, behaelt
Kontingent, `no_weather`, `orte_ohne_wetter`, `undelivered`-Ermittlung, Nachhol-Hinweis,
Anker, Versand und alle Rueckgabewerte/Fehlerpfade in der heutigen Reihenfolge und ruft
`compare_email_rendern` bzw. `compare_kanaltexte_rendern` an den heutigen Stellen (E-Mail
ausserhalb, SMS/Telegram innerhalb des try-Blocks).

**Vorschau (`ComparePreviewService.render_all_channels`).** Wird eine duenne Huelle:
Preset und Orte laden (`_load_preset`/`_resolve_locations` bleiben, `_load_preset` nutzt
die Alarm-Vorschau), Zieltag bestimmen, Sprache des Nutzers, `compare_briefing_bauen`
aufrufen, die bisherigen Schluessel (`subject`, `email_html`, `telegram`, `sms`,
`sms_char_count`) zurueckgeben. `_prepare` und `_render_email` entfallen, soweit kein
Test sie direkt aufruft (vor dem Loeschen per Suche pruefen; sonst als Einzeiler
belassen).

**Angeglichene Abweichung.** Die Vorschau zeigt Telegram bisher immer in Langform. Sie
folgt jetzt `effective_compare_telegram_style` wie der Versand (kurzform = SMS-Text).

**Bewusst unveraendert bleibende Unterschiede** (keine Abweichung, sondern Seiten-
Eigenheiten): `undelivered` im Mailtext, Kontingent, `no_weather`, Nachhol-Hinweis,
Anker, Kanal-Fan-out gibt es nur im Versand; die Vorschau liest ein Preset des Nutzers
und wirft `LookupError` bei fremdem Preset.

**Namenszaehler `tests/tdd/test_profil_ampel_kette.py:926-932` (geprueft).** Der Test
zaehlt per AST genau einen `template_id_for`-Aufruf in `send_one_compare_preset` und in
`ComparePreviewService._prepare` (`DIENST_NUR_VORLAGEN_ID`). Der Aufruf zieht in
`compare_wetter_laden` um; beide alten Eintraege wuerden rot (Aufruf nicht mehr
vorhanden, bzw. `_prepare` nicht mehr da). Der Test ist also BETROFFEN und wird im
Umfang minimal angepasst: Eintraege `("compare_briefing_aufbau.py",
"compare_wetter_laden"): 1` ergaenzen und die beiden alten Eintraege streichen. Die
Zusicherung (Profil kommt aus der Vorlage, genau an einer Stelle) bleibt erhalten und
wird sogar schaerfer (eine statt zwei Stellen).

## Expected Behavior

- **Input:** Preset-Dict, geordnete Orte, Zieltag (`date`), `user_id`, Sprache, optional `undelivered`.
- **Output:** Betreff, E-Mail (HTML und Text), SMS-Text, Telegram-Text (je nach Stil Kurz- oder Langform).
- **Side effects:** keine im Baustein. Der Wetterlauf verbraucht Abrufbudget des uebergebenen Nutzers wie bisher (`user_id`, #2234).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Golden-Test Versand (Characterization, VOR dem Umbau gruen, danach unveraendert): GIVEN ein Preset mit festen Orten und deterministischen Wetterdaten (vorhandene Test-Provider/Fixtures nach Muster `tests/tdd/test_compare_preview_*.py`, kein Mock-Theater) und Mail/SMS/Telegram-Sinks WHEN `send_one_compare_preset` laeuft THEN sind Betreff, Mail-HTML, Mail-Text, SMS-Text und Telegram-Text byte-gleich zu den vor dem Umbau festgehaltenen Werten.
- [ ] Golden-Test Telegram-Kurzform und Langform im Versand je einmal (beide Stile).
- [ ] RED: GIVEN Preset mit Telegram-Stil kurzform WHEN `render_all_channels` THEN `telegram` == `sms` (schlaegt vor dem Umbau fehl).
- [ ] Gleichheit Vorschau gegen Versand: GIVEN dasselbe Preset, derselbe Zieltag WHEN Vorschau und Versand laufen THEN identische Kanaltexte (ohne `undelivered`-Block).
- [ ] Mandantentrennung: GIVEN zwei Nutzer mit je eigenem Preset und eigenen Orten WHEN Vorschau und Versand fuer Nutzer A laufen THEN erscheint nichts von Nutzer B, Preset von B ist fuer A nicht aufloesbar (`LookupError`), `user_id` im Wetterlauf ist die echte (nie `"default"`).
- [ ] Reihenfolge Versand: GIVEN alle Orte ohne Wetter WHEN Versand THEN `no_weather` und es wird kein Mail-Render/Versand ausgefuehrt; GIVEN erschoepftes Kontingent im Handversand THEN `kontingent_erschoepft` vor jeder Zustellung.
- [ ] Zieltag: GIVEN Orte mit Zeitzone und fester Uhr WHEN `compare_zieltag_bestimmen` THEN Ortstag des ersten aufloesbaren Orts, Vorschau und Versand ohne uebergebenen Tag liefern denselben Tag.
- [ ] Struktur: Der Baustein ist importierbar, ohne dass `scheduler_dispatch_service` oder `compare_preview_service` geladen wird (Subprozess-Import), die Alt-Importe der Namen bleiben gueltig.
- [ ] Bestehende Paritaetstests `tests/tdd/test_compare_preview_service.py` und `tests/tdd/test_compare_preview_hourly_parity.py` werden Regressionswaechter und laufen gruen; `tests/tdd/test_compare_preview_user_isolation.py`, `tests/unit/test_compare_preview_second_call_uses_cache.py`, `tests/tdd/test_profil_ampel_kette.py` laufen gruen.
- [ ] Mail-Validator `.claude/hooks/email_spec_validator.py` gegen echt zugestellte Staging-Mail: Exit 0 (Deploy-Nachweis, Renderer-Commit-Gate).

## Definition of Done

- [ ] Golden-Tests des Versands (Betreff, Mail HTML/Text, SMS, Telegram) vor dem Umbau gegen den Ist-Stand grün, nach dem Umbau unverändert grün (AC-1, AC-8)
- [ ] AC-2 bis AC-7, AC-9 durch deterministische Kern-Tests ohne Mock-Theater belegt, AC-2 vor der Umsetzung rot nachgewiesen
- [ ] AC-10: `tests/tdd/test_profil_ampel_kette.py` grün
- [ ] AC-11: `email_spec_validator.py` gegen echt zugestellte Staging-Mail Exit 0
- [ ] Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit festen Orten und gleichen Wetterdaten / When der Versand vor und nach dem Umbau laeuft / Then sind Betreff, E-Mail (HTML und Text), SMS und Telegram des Versands byte-gleich zu vorher.
  - Test: Golden-Test mit Sinks und deterministischen Test-Wetterdaten, Soll-Werte vor dem Umbau erfasst, ohne Mock-Theater.
- **AC-2:** Given ein Ortsvergleich mit Telegram-Stil Kurzform / When die Vorschau erzeugt wird / Then zeigt die Telegram-Vorschau denselben Kurztext wie die SMS und wie die zugestellte Telegram-Nachricht.
  - Test: Vorschau und Versand fuer dasselbe Preset vergleichen, Telegram-Text muss gleich dem SMS-Text sein.
- **AC-3:** Given ein Ortsvergleich mit Telegram-Stil Langform / When Vorschau und Versand laufen / Then ist die Telegram-Langform in beiden identisch, inklusive Ausblick und Vertretungshinweis.
  - Test: Textvergleich Vorschau gegen Versand im Langform-Stil.
- **AC-4:** Given zwei verschiedene Nutzer mit je eigenem Ortsvergleich / When Vorschau oder Versand fuer Nutzer A laufen / Then enthalten Ergebnis und Wetterabruf nur Orte und Presets von Nutzer A, ein Preset von Nutzer B ist nicht erreichbar, und es wird nie `"default"` als Nutzer verwendet.
  - Test: Zwei-Nutzer-Test an Vorschau und Versand mit echter `user_id`, fremdes Preset liefert `LookupError`.
- **AC-5:** Given der Quelltext der Dienste / When man nach der Stelle sucht, die Profil, Wetterlauf, Render-Optionen, Betreff und Kanaltexte des Ortsvergleichs zusammensetzt / Then gibt es genau eine (`compare_briefing_aufbau`), und Versand wie Vorschau rufen sie auf, ohne eigene Kopie des Aufbaus.
  - Test: Verhaltenstest: eine Aenderung am Baustein (in einer Test-Ersatzfassung eingesetzt) ist in Vorschau UND Versand sichtbar; Mutations-Gegenprobe des Validators.
- **AC-6:** Given der neue Baustein / When er importiert wird / Then werden weder `scheduler_dispatch_service` noch `compare_preview_service` geladen (kein Zirkelimport), und die alten Namen `order_locations_by_ids` und `build_compare_preset_subject` sind aus den alten Modulen weiter importierbar.
  - Test: Import in frischem Prozess, Pruefung der geladenen Module; Alt-Importe funktionieren.
- **AC-7:** Given der Baustein / When er ausgefuehrt wird / Then erzeugt er keine Nebenwirkung: kein Versand, kein Kontingent-Abbruch, kein Anker, kein Melde-Gedaechtnis, keine Vorfall-Schreibung, keine Datei-Aenderung im Nutzerverzeichnis.
  - Test: Vorschau-Aufruf mit Verzeichnis-Snapshot vorher/nachher und Sinks, die nie aufgerufen werden duerfen.
- **AC-8:** Given ein Ortsvergleich, bei dem alle Orte keine Wetterdaten liefern, oder ein erschoepftes Handversand-Kontingent / When der Versand laeuft / Then bleiben Reihenfolge und Ergebnis wie bisher: `kontingent_erschoepft` bzw. `no_weather` vor jeder Mail, Anker nur nach erfolgreichem Versand, Rueckgabe `(top_ort, empfaenger)` unveraendert.
  - Test: Versand-Tests fuer beide Abbruchpfade; bestehende Tests fuer Anker und Fehlerpfad (#1629) bleiben gruen.
- **AC-9:** Given Vorschau und Versand ohne uebergebenen Zieltag / When der Tag bestimmt wird / Then gilt in beiden der Ortstag des ersten aufloesbaren Orts aus derselben gemeinsamen Ermittlung; ein vom Slot uebergebener Tag bleibt unveraendert wirksam.
  - Test: feste Uhr und Orte in unterschiedlichen Zeitzonen, Tag in Vorschau und Versand identisch; Slot-Tag bleibt unveraendert im Betreff.
- **AC-10:** Given die Namensanzahl-Pruefung `tests/tdd/test_profil_ampel_kette.py` / When sie nach dem Umbau laeuft / Then ist sie gruen und belegt, dass das Bewertungsprofil genau an einer Stelle (im Baustein) aus der Vorlage bestimmt wird.
  - Test: Test laeuft mit angepasster Eintragsliste gruen; weder Versand noch Vorschau loesen das Profil selbst auf.
- **AC-11:** Given ein echt zugestellter Ortsvergleich im Staging-Postfach / When der Mail-Validator `email_spec_validator.py` laeuft / Then endet er mit Exit 0 („E2E bestanden").
  - Test: Validator gegen echte Staging-Mail nach dem Deploy auf Staging.

## Out of Scope

- **Trip-Briefing** (`preview_service._build_report`, `trip_report_scheduler._briefing_bauen_und_senden`): eigenes Issue #3128, folgt nach demselben Muster.
- Aenderung des Inhalts der Mail, SMS oder Premium-SMS: keine; nur Aufbau-Ort und Telegram-Kurzform der Vorschau.
- Alarm-Vorschau (`compare_alert_preview_service`): unveraendert, nutzt nur `_load_preset` weiter.

## Known Limitations

- `render_all_channels` hat seit #1743 keinen produktiven Aufrufer mehr (nur Tests); sie bleibt als Regressionswaechter fuer „Vorschau = Versand" bestehen.
- `resolve_compare_render_options` wird im Versand kuenftig im Baustein aufgeloest (etwas frueher als bisher, vor der `no_weather`-Pruefung); die Funktion ist rein, an der Reihenfolge der Fehlerpfade aendert sich nichts.
- Der Baustein ist in vier Funktionen geteilt (nicht nur eine), weil der Versand zwischen Wetterlauf und Rendern Kontingent und `no_weather` prueft und SMS/Telegram im try-Block des Anker-Pfads rendert.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/compare_briefing_aufbau.py` | CREATE | Baustein (4 Funktionen), `compare_zieltag_bestimmen`, hierher verschoben: `order_locations_by_ids`, `build_compare_preset_subject` |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset` ruft den Baustein; Re-Export `build_compare_preset_subject`; Nebenwirkungen und Reihenfolge unveraendert |
| `src/services/compare_preview_service.py` | MODIFY | `render_all_channels` duenne Huelle; Re-Export `order_locations_by_ids`; `_load_preset` bleibt; `_resolve_target_date` nutzt gemeinsame Ermittlung |
| `tests/tdd/test_profil_ampel_kette.py` | MODIFY | Eintraege fuer den Umzug von `template_id_for` (Zeilen 926-934) |
| `tests/tdd/test_compare_briefing_aufbau.py` | CREATE | Golden-Tests Versand, Kurzform, Mandantentrennung, Seiteneffektfreiheit, Import ohne Zirkel, Zieltag |
| `tests/tdd/test_compare_preview_service.py` | MODIFY | Regressionswaechter „gleicher Baustein", Telegram-Kurzform |
| `tests/tdd/test_compare_preview_hourly_parity.py` | MODIFY (nur falls noetig) | Waechter-Kommentar/Verdrahtung |

### Estimated Changes

- Files: 7 (3 Quellen, 4 Tests)
- LoC: +~170 / -~150 Produktionszeilen (Ziel < 250 hinzugefuegt)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Zusammenfuehrung doppelter Verdrahtung nach dem bestehenden Muster geteilter Bausteine (`resolve_compare_render_options`, `alert_channel_texts`); keine neue Entscheidungsflaeche. Abweichung von der Trip/Ortsvergleich-Teilung nur zeitlich (Trip folgt in #3128).

## Changelog

- 2026-11-17: Initial spec created (Issue #2983, nur Ortsvergleich; Trip als #3128 abgespalten)
