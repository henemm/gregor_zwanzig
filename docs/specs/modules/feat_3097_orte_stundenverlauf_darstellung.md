---
entity_id: feat_3097_orte_stundenverlauf_darstellung
type: feature
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: feat-3097-orte-stundenverlauf-darstellung
tags: [orte, stundenverlauf, darstellung, roh-einfach, w11, epic-3058, issue-3097]
---

> **Hinweis (2026-11-17, [ADR-0124](../../adr/0124-was-steht-wo-eine-tabelle.md), Issue #3122):** Diese Spec ist gebaut (`hourly_metric_formats`) und gilt bis zum Bau zu #3122. Die hier vorgesehene Verlagerung nach `channel_layouts.hourly` mit #3060 entfällt in dieser Form: ADR-0124 schneidet das gespeicherte Format mit dem Bau neu. Roh/Einfach bleibt je Stelle getrennt (ADR-0124 Nr. 5, nur bei Metriken mit zwei Formen); der Stundenverlauf selbst folgt dann der E-Mail-Auswahl (Nr. 4). ACs unverändert.

# Orte-Stundenverlauf: Darstellung Roh oder Einfach je Zeile (W11)

## Approval

- [ ] Approved

## Purpose

Im Stundenverlauf der Orts-Vergleich-Mail kann der Nutzer je Metrik waehlen, ob der Wert als Zahl (Roh) oder in Einfach-Form (Ampelpunkt, Symbol, Wort) erscheint, wie es Vergleichstabelle (#3039) und 3-Tages-Ausblick (#2049) schon koennen. Ohne diese Scheibe bleibt PO-Entscheidung W11 fuer den Stundenverlauf offen (Befund B-OM-5, Faelle `O-SV-H-DARST` und `O-SV-K-DARST`).

## Source

- **File:** `src/output/renderers/compare_outlook_metric_ids.py` (neuer Stunden-Einfach-Helfer), `src/output/renderers/email/compare_html.py`, `src/output/renderers/comparison.py`, `src/services/channel_list_resolver.py`
- **Identifier:** `_friendly_hour_text`, `resolve_hourly_metric_formats`, `_render_hour_row`, `_render_hour_table`, Klartext-Stundenschleife in `comparison.py`, Resolver-Zweig `hourly`

> **Schicht-Hinweis:** Python-Core (`src/output/renderers/`, `src/services/`) fuer Rendering und Aufloesung; Frontend (`frontend/src/lib/components/compare/`, `shared/`) fuer den Umschalter und die Persistenz. Go-API unveraendert (Feld wird ueber den bestehenden `display_config`-Weg gespeichert, Merge nach ADR-0077). Kontext: `docs/context/feat-3097-orte-stundenverlauf-darstellung.md`.

> **Querschnitts-Pruefpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Der Stundenverlauf existiert nur im Ortsvergleich (Trip hat kein Pendant). Es entsteht keine neue Compare-Komponente: der Umschalter nutzt die vorhandene `friendlyMap` des geteilten `shared/OutputLayoutEditor.svelte` im bestehenden `CompareHourlyLayoutControls.svelte`.
> - **Mandantentrennung:** Das Feld liegt in `data/users/<user_id>/` (Orts-Vergleich-Konfiguration); `user_id` aus dem Auth-Kontext, zwei Nutzer im Test (AC-9).
> - **Kanaele:** Der Stundenverlauf wird nur in der Orte-Mail (HTML + Klartext) ausgegeben, nicht in Telegram, SMS und Premium-SMS; diese bleiben unberuehrt (#3098 bis #3100 behandeln deren Listen). Kanal-Paritaet nach ADR-0095 bleibt gewahrt, da kein Kanal einen Stundenverlauf hat.

## Scope

Phase 3b von #3047 (Epic #3058). Im Stundenverlauf der Orts-Vergleich-Mail (HTML und Klartext) und in der Editor-Vorschau wirkt die Darstellung Roh/Einfach je Metrik, gespeichert in `display_config.hourly_metric_formats` und vom Resolver als `hourly[].format` geliefert. Der Stundenverlauf-Editor bekommt dazu den Umschalter je Zeile ueber die vorhandene `friendlyMap`. Ohne Einstellung bleibt jede Mail byte-gleich.

## Estimated Scope

- **LoC:** Python +120/-160, Frontend +60/-90, Tests und Doku zusaetzlich
- **Files:** ca. 15
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0121-kanonische-kanal-liste.md` (Nachtrag 2b, neu 3b) | ADR | Resolver-Vertrag `hourly[].format`; Nachtrag 3b legt `hourly_metric_formats` als Quelle fest |
| `docs/adr/0119-*.md` Nr. 4 | ADR | Fehlende Einstellung = Roh |
| `docs/specs/modules/feat_3039_vergleich_kanal_layouts.md` | Spec | Vergleichstabelle (`channel_layouts.email`), Abgrenzung |
| `docs/specs/modules/fix_2049_ausblick_darstellungsform.md` | Spec | Vorbild `outlook_metric_formats`, Tagessummen-Skala fuer Niederschlag |
| `docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md`, `feat_3096_mail_resolver.md` | Spec | Resolver und Mail-Anbindung |
| `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` | Spec | Fallliste und Pruefkatalog |
| `src/output/renderers/compare_outlook_metric_ids.py` | module | `_friendly_outlook_text`, `format_precip_intensity` |
| `src/services/report_config_resolver.py`, `scheduler_dispatch_service.py`, `compare_preview_service.py`, `validator_render_service.py` | module | Drei Verbraucher der Stundenliste (Mail-Versand, Vorschau, Validator-Render) |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | component | `friendlyMap` |
| `.claude/hooks/email_spec_validator.py` | hook | Stundentabellen-Pruefung (geprueft, siehe Implementation Details) |

## Implementation Details

**Speicherort (Tech-Lead-Entscheidung):** `display_config.hourly_metric_formats` als `{metric_id: bool}` (true = Einfach), Schwesterfeld zu `outlook_metric_formats`. Fehlt Feld oder Eintrag, gilt Roh. `channel_layouts.email` (Vergleichstabelle) und `channel_layouts.hourly` (reserviert, erst mit #3060 schreibbar) werden bewusst nicht benutzt: W11 verlangt je Liste eigene Werte, und der Go-Merge ersetzt Unterschluessel (Datenverlustrisiko). Spaetere Migration nach `channel_layouts.hourly` ist verlustfrei moeglich.

**Resolver:** `channel_list_resolver.py` fuellt `hourly[].format` mit `simplified`, `raw` oder `null` (statt bisher immer `None`) aus `hourly_metric_formats`. `validator_render_service.py` (umgeht heute den Resolver) liest das Feld ebenfalls. Alle drei Verbraucher reichen das Format an den Renderer durch, damit Vorschau und Mail identisch sind.

**Einfachformen je Metrik** (neuer Helfer `_friendly_hour_text`, sonst Delegation an `_friendly_outlook_text`):

- Wind und Boeen: Ampelpunkt wie in der Vergleichstabelle
- Wolken (gesamt, tief, mittel, hoch): Symbol
- Windrichtung: Kompassrichtung
- Regenwahrscheinlichkeit und Sonnenschein: Wortskala
- Niederschlag: Stunden-Intensitaetsskala ueber `format_precip_intensity` (trocken, leicht, maessig, stark), nicht die Tagessummen-Skala von `_friendly_outlook_text`
- Gewitter: kein Umschalter (Roh ist bereits Text, #1475)
- Temperatur und weitere Metriken ohne Einfachform: Zahl, kein Umschalter; Metriken mit nur einem `format_mode` ignorieren Einfach (Regel `_friendly_effective`)

**Renderer:** `_render_hour_row` und `_render_hour_table` (HTML) sowie die Klartext-Schleife in `comparison.py` erhalten den Parameter Stundenformate und denselben Einfach-Zweig. Ohne Einstellung bleibt die Ausgabe byte-gleich zu heute, Goldens bleiben unveraendert.

**Frontend:** `CompareHourlyLayoutControls.svelte` ersetzt `friendlyMap={{}}` durch eine echte Map (nur Metriken mit Einfachform), entfernt den Hinweis, es gaebe keinen Umschalter. Persistenz `hourly_metric_formats` analog `outlook_metric_formats` in `compareEditorSave.ts`, `shared/pickEigenfelder.ts`, `lib/types.ts`. Speichern als Read-Modify-Write: bestehende `display_config`-Felder bleiben erhalten.

**Validator-Klaerung (offene Frage aus dem Kontext):** `.claude/hooks/email_spec_validator.py` (`validate_structure`, :941-1012, und `validate_hourly_table`, :1116-1159) prueft von der Stundentabelle ausschliesslich die Kopfzeile (Spaltennamen: Mindestspalten, unbekannt, doppelt, mail-weit gleich) und die erste Spalte (Stunde: vorhanden, innerhalb des Tagesfensters). Zelleninhalte der Wertspalten werden nicht auf "leer" geprueft. Wort-, Symbol- und Ampelzellen sind damit fuer den Validator unkritisch; es ist keine Validator-Aenderung noetig. Die Zusicherung wird stattdessen durch einen Test belegt (AC-11): eine Mail mit Einfach-Zeilen besteht den Validator, und die Zeit-Spalte bleibt auch bei Symbolzellen eindeutig erkennbar. Sollte der Test eine Luecke zeigen, wird der Validator in diesem Workflow nachgezogen.

**Dokumentation:** ADR-0121 Nachtrag 3b (Stundenverlauf-`format` stammt aus `display_config.hourly_metric_formats`, Fehlt = Roh, Migration nach `channel_layouts.hourly` mit #3060); `docs/reference/api_contract.md` erhaelt das Feld `display_config.hourly_metric_formats` mit Changelog-Zeile.

**Umsetzungsabweichungen (2026-11-17, bei der Implementierung entschieden):**

- **Persistenz ohne `pickEigenfelder.ts`:** Das Feld wird nicht in `shared/pickEigenfelder.ts` eingetragen; diese Datei bleibt unveraendert, weil sie Trip-only ist. Die Eigenfelder fuer den Ortsvergleich liegen in `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` (Read-Modify-Write, Schluessel `hourly_metric_formats` in der Eigenfeld-Liste dort).
- **Umschalter ueber `WeatherV2Reihenfolge`:** Die Bedienflaeche im Stundenverlauf-Editor laeuft nicht ueber `shared/OutputLayoutEditor.svelte`, sondern ueber `shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte`, das `CompareHourlyLayoutControls.svelte` mit der `friendlyMap` aus `compare/hourlyFriendlyMap.ts` einbindet. Begruendung: Dieselbe Reihenfolge-Komponente bedient bereits die Uebersichts-Groessen; eine zweite Liste waere eine neue Compare-Komponente mit Pendant (Trip/Ortsvergleich-Teilung).

## Expected Behavior

- **Input:** Orts-Vergleich-Konfiguration mit optionalem `display_config.hourly_metric_formats`, z. B. `{"wind": true, "precip": true}`.
- **Output:** Stundentabelle in HTML und Klartext zeigt fuer diese Metriken die Einfach-Form, fuer alle anderen die Zahl; die Vorschau im Editor zeigt dasselbe.
- **Side effects:** Keine; ohne das Feld bleibt jede Mail byte-gleich.

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich mit Stundenverlauf und der Metrik Wind auf Einfach gestellt / When die Mail erzeugt wird / Then zeigt die Zeile Wind in der HTML-Stundentabelle jeder Stunde den Ampelpunkt statt der Zahl, die Zeilen anderer Metriken bleiben Zahlen
  - Test: Mail fuer einen Orts-Vergleich rendern (Kern-Schicht, kein Mock) und die Wind-Zellen der HTML-Stundentabelle auf Ampelpunkt, die uebrigen Zellen auf Zahl pruefen.

- **AC-2:** Given derselbe Orts-Vergleich mit Wind auf Einfach / When der Klartext-Teil der Mail erzeugt wird / Then enthaelt der Klartext-Stundenverlauf fuer Wind dieselbe Einfach-Darstellung wie die HTML-Tabelle und nicht die Zahl
  - Test: Klartext-Teil der Mail rendern und die Wind-Zeile der Stundenschleife gegen die Einfachform pruefen, Gegenprobe Roh liefert die Zahl.

- **AC-3:** Given ein Orts-Vergleich mit einzelnen Stundenverlauf-Zeilen auf Einfach / When der Nutzer die Vorschau im Editor oeffnet / Then zeigt die Vorschau fuer den Stundenverlauf dieselben Zellen wie die tatsaechlich versendete Mail
  - Test: Vorschau-Ausgabe (`compare_preview_service`) und Versand-Ausgabe (`scheduler_dispatch_service`) mit derselben Konfiguration erzeugen und die Stundentabellen vergleichen.

- **AC-4:** Given ein bestehender Orts-Vergleich ohne `hourly_metric_formats` / When die Mail erzeugt wird / Then zeigt jede Stundenverlauf-Zeile die Zahl wie bisher und die Mail ist byte-gleich zur Ausgabe vor dieser Aenderung
  - Test: Bestehende Goldens (HTML und Klartext) bleiben unveraendert gruen; zusaetzlich fuehrt ein explizites Roh (`false`) zur identischen Ausgabe wie ein fehlender Eintrag.

- **AC-5:** Given ein Orts-Vergleich, in dem die Vergleichstabelle auf Einfach steht (`channel_layouts.email`) / When die Mail erzeugt wird / Then bleibt der Stundenverlauf unveraendert bei Zahlen, und umgekehrt aendert eine Einfach-Einstellung im Stundenverlauf die Vergleichstabelle nicht
  - Test: Zwei Konfigurationen rendern, die sich nur im jeweils anderen Feld unterscheiden, und Stundentabelle bzw. Vergleichstabelle auf Unveraendertheit pruefen (`test_w11_darstellung_je_zeile`, Gegenprobe).

- **AC-6:** Given die Metrik Niederschlag steht im Stundenverlauf auf Einfach / When die Mail erzeugt wird / Then erscheint pro Stunde eine Intensitaets-Angabe nach Stunden-Skala (trocken, leicht, maessig, stark), und ein Stundenwert wird nicht nach der Tagessummen-Skala eingestuft
  - Test: Stundenwerte an den Skalengrenzen (z. B. 0 mm, 0,4 mm, 2 mm, 6 mm pro Stunde) rendern und die Worte pruefen; ein Wert, der als Tagessumme "wenig" waere, zeigt als Stundenwert die hoehere Stufe.

- **AC-7:** Given die Metriken Temperatur und Gewitter im Stundenverlauf / When der Nutzer den Stundenverlauf-Editor oeffnet / Then zeigen diese Zeilen keinen Roh/Einfach-Umschalter, die Mail zeigt sie weiter als Zahl bzw. Text, auch wenn ein Eintrag im Feld steht
  - Test: Frontend-Test (`node --test`) prueft, dass die `friendlyMap` nur Metriken mit Einfachform enthaelt; Renderer-Test mit gesetztem Einfach fuer Temperatur zeigt weiter die Zahl.

- **AC-8:** Given der Nutzer stellt im Stundenverlauf-Editor die Zeile Wind auf Einfach / When er speichert und die Seite neu laedt / Then steht Wind weiter auf Einfach, und alle uebrigen Einstellungen des Orts-Vergleichs (z. B. `outlook_metric_formats`, `hourly_metrics`, Kanal-Layouts) sind unveraendert erhalten
  - Test: Frontend-Persistenztest (`node --test`, analog `compare_outlook_metric_formats_persistenz.test.ts`) und Round-Trip gegen die API: speichern, neu laden, Feld und bestehende `display_config`-Felder vergleichen (Read-Modify-Write).

- **AC-9:** Given zwei verschiedene Nutzer mit je einem Orts-Vergleich, Nutzer A mit Wind auf Einfach / When beide ihre Mail bzw. Vorschau erzeugen / Then zeigt nur Nutzer A den Ampelpunkt, Nutzer B bleibt bei Zahlen, und keiner sieht Daten des anderen
  - Test: Zwei Nutzer mit getrennter `user_id` anlegen, Einstellung nur bei A speichern, beide Ausgaben vergleichen; kein Zugriff ueber den Fallback `"default"`.

- **AC-10:** Given die Fallliste `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` / When `tests/tdd/test_einstellung_gleich_mail_orte.py::test_w11_darstellung_je_zeile` laeuft / Then sind `O-SV-H-DARST` und `O-SV-K-DARST` mit Status `gruen` eingetragen und der Test besteht gegen `hourly_metric_formats`
  - Test: Der auf `hourly_metric_formats` umgestellte Test belegt fuer HTML (H) und Klartext (K), dass die Einstellung "Einfach" in der Mail ankommt; Fallliste steht auf `gruen`.

- **AC-11:** Given eine Mail mit Stundenverlauf-Zeilen in Einfach (Ampelpunkt, Symbol oder Wort) / When der Mail-Validator `email_spec_validator.py` sie prueft / Then gilt keine Wort-, Symbol- oder Ampelzelle als fehlend oder leer, und die Pruefung der Stundentabelle (Spaltenkoepfe, Stunden, Tagesfenster) besteht
  - Test: Staging-nahe Mail bzw. gerenderte Mail mit Einfach-Zeilen durch `validate_structure` und `validate_hourly_table` schicken; Ergebnis ohne Fehler. Der Validator prueft nur Kopfzeile und Zeit-Spalte, daher ist keine Validator-Aenderung vorgesehen.

## Definition of Done

- AC-1 bis AC-11 durch benannte Tests gruen; Golden-Mails (HTML und Klartext) unveraendert gruen, Golden-Dateien unveraendert.
- `O-SV-H-DARST` und `O-SV-K-DARST` in der Fallliste auf `gruen`.
- Mutations-Gegenprobe durch den Adversary (siehe Test Plan): jede Verfaelschung macht mindestens einen Test am Mail- bzw. Speicher-Ergebnis rot.
- ADR-0121 Nachtrag 3b und `api_contract.md` (Feld plus Changelog-Zeile) geschrieben.
- Vor dem ersten Code gegen `origin/main` abgeglichen.
- Alle 6 CI-Checks gruen, Staging-Verifikation mit echt zugestellter Orte-Mail (Einfach-Zeile sichtbar, Validator gruen), Prod-Selftest bestanden.

## Test Plan

### Automated Tests (TDD RED)

Zusicherungen werden am Mail-Ergebnis bzw. am gespeicherten Datensatz geprueft, nicht an Hilfsfunktionen; kein Mock-Theater (kein `Mock()`/`patch()`).

- [ ] Neu `tests/tdd/test_3097_stundenverlauf_darstellung.py`: GIVEN Orts-Vergleich mit `hourly_metric_formats={"wind": true}` WHEN Orte-Mail HTML und Klartext gerendert THEN Wind-Zellen Ampelpunkt/Einfach, uebrige Zahlen (AC-1, AC-2); Roh `false` und fehlender Eintrag gleich (AC-4).
- [ ] Neu im selben Test: Niederschlag Einfach an Skalengrenzen nach Stunden-Skala, Gegenprobe gegen Tagessummen-Skala (AC-6); Temperatur mit gesetztem Einfach bleibt Zahl, Gewitter bleibt Text (AC-7 Renderer-Teil).
- [ ] Neu: Vorschau (`compare_preview_service`) und Versand (`scheduler_dispatch_service`) sowie Validator-Render (`validator_render_service`) mit derselben Konfiguration liefern dieselbe Stundentabelle (AC-3).
- [ ] Neu: Resolver liefert `hourly[].format` `simplified`/`raw`/`null` aus `hourly_metric_formats` (Teil von AC-1/AC-3).
- [ ] Neu: zwei Nutzer, Einstellung nur bei A, beide Aufrufreihenfolgen (AC-9).
- [ ] Neu: Mail mit Einfach-Zeilen besteht `validate_structure` und `validate_hourly_table` aus `.claude/hooks/email_spec_validator.py` (AC-11).
- [ ] Umstellen: `tests/tdd/test_einstellung_gleich_mail_orte.py::test_w11_darstellung_je_zeile` auf `hourly_metric_formats`, Gegenprobe `channel_layouts.email` aendert den Stundenverlauf nicht und umgekehrt (AC-5, AC-10); Fallliste auf `gruen`.
- [ ] Neu Frontend (`node --test`): `compare_hourly_metric_formats_persistenz.test.ts` analog Ausblick: Speichern schreibt `hourly_metric_formats` per Read-Modify-Write, andere `display_config`-Felder bleiben (AC-8); `friendlyMap` enthaelt nur Metriken mit Einfachform (AC-7).
- [ ] Unveraendert gruen (Regression, einzeln benannt): Orte-Golden-Tests, `test_3057_channel_list_resolver.py`, `test_3065_ausblick_stundenverlauf_resolver.py`, `test_3096_mail_resolver.py`, `test_compare_preview_hourly_parity.py`, Ausblick-Persistenztest.
- [ ] Mutations-Gegenprobe durch den Adversary (Kopie extern, String-Ersetzung, nie `git checkout/stash/reset`): Resolver liefert immer `None`; Einfach-Zweig nur im HTML, nicht im Klartext; Niederschlag ueber Tagessummen-Skala; Vorschau reicht Format nicht durch; Speichern ersetzt `display_config` statt Merge; Renderer liest `channel_layouts.email` statt Stundenformate. Jede Verfaelschung muss mindestens einen Test rot machen.
- Live-E2E: Staging-Orte-Mail mit Einfach-Zeile echt zustellen, `email_spec_validator.py` Exit 0; Editor-Umschalter auf Staging speichern und nach Neuladen pruefen.

## Out of Scope

- Roh/Einfach in Telegram, SMS, Premium-SMS: #3098, #3099, #3100.
- Verlagerung nach `channel_layouts.hourly` und neuer Kanal-Editor: #3060.
- Vokabular-Vereinheitlichung: #3101; Migration und Orakel-Loeschung: #3102.
- Einfachform fuer Temperatur, Gewitter und andere Metriken ohne bestehende Einfachform.
- Trip-Mail (hat keinen Stundenverlauf in diesem Sinn).

## Affected Files

| Datei | Aenderung | Beschreibung |
|-------|-----------|--------------|
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | `_friendly_hour_text` (Stunden-Skala Niederschlag, sonst Delegation), `resolve_hourly_metric_formats` |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_render_hour_row`/`_render_hour_table` mit Stundenformaten und Einfach-Zweig |
| `src/output/renderers/comparison.py` | MODIFY | Klartext-Stundenschleife mit demselben Einfach-Zweig |
| `src/services/channel_list_resolver.py` | MODIFY | `hourly[].format` aus `hourly_metric_formats` |
| `src/services/report_config_resolver.py` | MODIFY | Stundenformate in die Render-Optionen |
| `src/services/scheduler_dispatch_service.py`, `src/services/compare_preview_service.py`, `src/services/validator_render_service.py` | MODIFY | Format durchreichen |
| `frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte` | MODIFY | echte `friendlyMap`, Hinweistext entfernt |
| `frontend/src/lib/components/compare/compareEditorSave.ts`, `frontend/src/lib/components/shared/pickEigenfelder.ts`, `frontend/src/lib/types.ts` | MODIFY | Persistenz `hourly_metric_formats` |
| `tests/tdd/test_3097_stundenverlauf_darstellung.py` | CREATE | Kern-Tests AC-1 bis AC-7, AC-9, AC-11 |
| `tests/tdd/test_einstellung_gleich_mail_orte.py`, `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` | MODIFY | W11-Test umstellen, Faelle auf `gruen` |
| `frontend/src/lib/components/compare/__tests__/compare_hourly_metric_formats_persistenz.test.ts` | CREATE | Persistenz und `friendlyMap` (AC-7, AC-8) |
| `docs/adr/0121-kanonische-kanal-liste.md`, `docs/reference/api_contract.md` | MODIFY | Nachtrag 3b, Feld plus Changelog |

## Known Limitations

- Telegram, SMS und Premium-SMS haben keinen Stundenverlauf; Roh/Einfach dort ist Sache von #3098 bis #3100.
- `hourly_metric_formats` ist ein Zwischenspeicherort; die Verlagerung nach `channel_layouts.hourly` folgt mit #3060 und ist dann verlustfrei moeglich.
- Gewitter, Temperatur und weitere Metriken ohne Einfachform bleiben bewusst ohne Umschalter.
- **Klartext zeigt Wortstufe statt Ampelpunkt:** Im Klartext gibt es keinen Farbpunkt; Wind und Boeen erscheinen dort als Wortstufe (wie in der Ausgabe von `_friendly_hour_text`).
- **Validator-Vorschau ohne Stundendaten (Adversary F004, aequivalente Mutante):** Der Stub-Ort im Validator-Render-Pfad (`validator_render_service.py`) enthaelt keine Stundendaten. Die Stundenformate werden dort zwar durchgereicht, die Mutation dieser Durchreichung bleibt aber ohne Wirkung auf das Ergebnis; eine Stundentabelle wird im Validator-Pfad nicht erzeugt. Die Zusicherung "Vorschau = Mail" ist fuer Versand und Editor-Vorschau belegt (AC-3), nicht fuer den Validator-Stub.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0121 (Nachtrag 3b, bestehendes ADR erweitert)
- **Rationale:** Der Resolver-Vertrag aus ADR-0121 Nachtrag 2b Nr. 3 ("Roh/Einfach dort = #3058") wird eingeloest: die Quelle fuer `hourly[].format` ist `display_config.hourly_metric_formats`. Kein neues ADR, da keine bestehende Entscheidung aufgehoben wird.

## Changelog

- 2026-11-17: Umsetzung dokumentiert: zwei Abweichungen (Persistenz ohne `pickEigenfelder.ts`, Umschalter ueber `WeatherV2Reihenfolge`), Known Limitations (Klartext Wortstufe, Validator-Stub ohne Stundendaten). API-Vertrag und ADR-0121 Nachtrag 3b bereits eingetragen.
- 2026-11-17: Initial spec created (Issue #3097, Epic #3058)
