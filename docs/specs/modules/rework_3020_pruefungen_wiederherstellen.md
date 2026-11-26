---
entity_id: rework_3020_pruefungen_wiederherstellen
type: refactor
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.2"
workflow: rework-3020-pruefungen-und-waisen
tags: [tests, katalog, einstellung-gleich-mail, rework-3020, R1, R1b]
---

# Rework #3020 R1/R1b: Katalog-Wächter schärfen und entfallene Prüfungen am heutigen Code wiederherstellen

## Approval

- [ ] Approved

## Purpose

Mit PR #3357 sind 60 Testdateien (337 Fälle) und 17 Katalogfälle entfallen. Dabei ging Prüfschutz für Verhalten verloren, das heute noch lebt (z. B. Schutz von `skip_next`, If-Match/keepalive im Zustellung-Reiter). Außerdem meldet der Katalog-Wächter 26 Fälle grün, obwohl ihr Test nicht mehr existiert. Diese Spec macht zuerst den Wächter ehrlich (R1b) und stellt danach die Prüfungen für lebendes Verhalten am heutigen Code wieder her (R1), jeweils dort, wo die Zusicherung wirkt.

## Source

- **File:** `tests/tdd/test_einstellung_gleich_mail_fallliste.py` (Wächter, R1b); Go-Store-Tests `internal/store/` und Frontend-Tests unter `frontend/src/lib/components/**/__tests__/` (R1)
- **Identifier:** `_template_muster`, `_vitest_titel_gefunden`, `_pruefe_vitest_verweis` (Z. 181-216); Katalog `tests/fixtures/einstellung_gleich_mail/fallliste_{editor,orte,trip}.json`

Schicht: Server-Verhalten (`skip_next`, `display_config`-Felderhalt, Alt-Trip ohne `show_night_block`) liegt im Go-Store (`internal/store/trip.go`) und wird dort mit echtem Go-Test geprüft. Reine Frontend-Logik (Nutzlast, Karte, Zustellung-Reiter) mit `node --test`. Keine Produktionsänderung vorgesehen.

Querschnitt: Trip/Ortsvergleich-Teilung: neue Frontend-Prüfungen laufen für `context="route"` und `"vergleich"`, wo der geteilte Code beides bedient. Mandantentrennung: jeder Go-Test des Schreibpfads läuft mit zwei verschiedenen Nutzern. Kanäle: Premium-SMS (R1) und Telegram (nur Tageswert beim Trip ab der 8. Metrik) sind benannt, SMS und E-Mail über die Katalogfälle.

## Scope

- **In Scope:** #3020 R1b. Der Katalog-Wächter zählt nur echte Testverweise, und die 26 falsch-grünen `D-*-frontend`-Fälle bekommen einen ehrlichen Verweis oder Status. Dazu #3020 R1: Prüfungen für das lebende Verhalten der Gruppe C (20 Dateien) werden am heutigen Code neu geschrieben oder per wörtlichem Verweis belegt. Gruppen A und B sowie die 17 gestrichenen Katalogfälle stehen in der Zuordnungsliste.
- **Nicht im Scope:** Löschen der Waisen-Dateien (#3366, R2 von #3020), Browser-Specs (#3374, #3375), Produktionscode-Änderungen, `.claude/hooks`, `EinstellTabelle.svelte`.

## Estimated Scope

- **LoC:** ca. 700 bis 1000; in Scheiben (R1b, dann R1) wegen LoC-Limit des Commit-Gates
- **Files:** 16 = 1 Wächter-Datei (`tests/tdd/test_einstellung_gleich_mail_fallliste.py`), 1 Selbstnachweis des Wächters (neu, Python), 3 Katalogdateien (editor, orte, trip), 3 neue Go-Testdateien (`internal/store/trip_skip_next_erhalt_test.go`, `trip_night_block_altstandard_test.go`, `trip_display_config_felderhalt_test.go`), 7 neue Frontend-Testdateien (`node --test`), 1 Zuordnungsartefakt (Markdown, ohne Test)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3020-pruefungen-und-waisen.md` | Doku | Messliste Gruppe C, Mechanismus des Falsch-Grüns, Nachtrag Prod-Messung |
| `docs/artifacts/feat-3297-trip-pfad-ohne-altfelder/geloeschte-tests.md` | Artefakt | Vorlage der Zuordnungsliste |
| `internal/store/trip.go`, `internal/store/trip_flat_fields_test.go` | Go | Schreibpfad und Testmuster für Server-Zusicherungen |
| `tripSpeicherung.ts`, `pickEigenfelder.ts`, `wasStehtWoSpeicherung.ts`, `zustellungSpeicherung.ts`, `zustellungModell.ts` | Frontend | lebender Schreibpfad / Zustellung-Reiter |
| `organisms/WasStehtWoKarte.svelte`, `mailInhaltKonstanten.ts` | Frontend | Karte |
| ADR-0124 (Nr. 3, Nr. 5) | ADR | Telegram „nur Tageswert“ beim Trip, SMS ohne Wahl |
| #3065 (geschlossen) | Issue | Übergangshilfe „Nur ein Bericht“ |
| #3366, #3374, #3375 | Issues | R2, Browser-Specs, Browser-Fall Telegram; eigene Durchläufe |

## Abgrenzung: die 60 gelöschten Testdateien

Von den 60 Testdateien, die #3357 gelöscht hat, wird jede einer von drei Gruppen zugeordnet. Die Liste je Datei steht in `docs/context/rework-3020-pruefungen-und-waisen.md` (Abschnitt Analysis R1, Gruppen A bis C).

- **Gruppe A (ca. 33 Dateien):** Sie prüften nur den Aufbau, die Verdrahtung oder die Darstellung der gelöschten Alt-Komponenten. Der geprüfte Code existiert nicht mehr. Es gibt nichts wiederherzustellen; jede Datei steht mit der Begründung „nur gelöschter Quelltext“ in der Zuordnungsliste (AC-16).
- **Gruppe B (ca. 11 Dateien):** Sie prüften Altfeld-Logik (`channel_layouts`, `outlook_*`, `hourly_*`). Diese Felder sind seit #3276/#3297/#3298/#3351 bewusst entfallen (ADR-0124 Nr. 6). Jede Datei steht mit diesem Verweis in der Zuordnungsliste. Die Kindmetrik-Ableitung lebt weiter und ist durch `kindmetriken_ableitung_und_mitnahme.test.ts` und `bug_2454_wirkort_verdrahtung.test.ts` belegt.
- **Gruppe C (20 Dateien):** Sie prüften Verhalten, das im lebenden Code weiterbesteht. Diese Dateien behandelt die Tabelle unten, jede bekommt einen neuen Test oder einen wörtlichen Verweis auf einen bestehenden Ersatztest.

Die Zuordnung ist eine Entscheidung des Tech Leads und beruht auf der Import-Analyse im Kontext. Ergibt sich bei der Umsetzung, dass eine Datei aus A oder B doch lebenden Code geprüft hat, wechselt sie nach C.

## Implementation Details

**Reihenfolge: R1b zuerst, damit der Wächter R1 schon bewacht.**

R1b, Wächter:
- Ursache: Die Titelvorlage `${key}` (`frontend/src/lib/i18n/__tests__/standardwerte_hilfe_textkatalog.test.ts:88`) wird in `_template_muster` zu `.+` und trifft jeden Titel.
- Regel neu: Ein Verweis gilt nur bei echtem Treffer, nämlich einem wörtlichen Titel oder einer Vorlage mit mindestens einem festen Textanteil. Eine reine Platzhalter-Vorlage zählt nie.
- Selbstnachweis: ein erfundener Testname wird rot; eine Vorlage mit festem Anteil trifft weiter.
- Die 26 falsch-grünen Fälle `D-*-frontend` in `fallliste_editor.json` (22× `frontend_seite_*`, 4× `n3_*`) werden einzeln auf einen existierenden, passenden Test mit Dateiangabe (`datei.test.ts::Titel`, wörtlicher Titel) umverwiesen oder bekommen einen ehrlichen Status. Erlaubt laut `ERLAUBTE_STATUS`: `gruen`, `rot_erwartet`, `ausnahme`, `offen_feature`; `ausnahme` und `offen_feature` verlangen ein Verweismuster `#N`/`ADR-N`.
- Telegram-Schnittlinie: nicht entfallen. ADR-0124 Nr. 3: beim Trip zeigt die Telegram-Spalte ab der achten Metrik „nur Tageswert“. Das ist in der Karte gebaut und belegt durch `was_steht_wo_karte.test.ts::Trip: „nur Tageswert“, „passt nicht mehr“, Zeile mit max_length und Hinweissatz für Trip`. Die Katalogfälle zur Schnittlinie verweisen darauf und stehen auf `gruen`. Entfallen ist nur die alte `LTCutLine`. Der Browser-Fall ist mit #3375 erledigt: `kanal-grenzen-und-hinweise.staging.spec.ts` (#3375 AC-1/AC-2, Gegenfall AC-3).
- SMS Roh/Einfach: entfallen, ADR-0124 Nr. 5 (SMS ohne Wahl); Status `ausnahme`, Verweis ADR-0124.
- Nur-ein-Bericht (die vier `n3_*`-Fälle): Beleg ist der Dateikopf von `nurEinBericht.ts` („kennzeichnet bis Phase 2 (#3065)“); #3065 ist geschlossen. Prod-Messung 25.11.2026 (Kontext-Dokument, Nachtrag): 21 Dateien, 0 Metriken nur in einem Bericht, 0 Nutzer betroffen. Status `ausnahme`, Verweis #3065. Das ist eine Entscheidung des Tech Leads auf Grundlage von #3065 und der Messung.

R1, Prüfungen für lebendes Verhalten, am heutigen Code neu geschrieben (alte Dateien werden nicht zurückgeholt). Zuordnung aller 20 Dateien der Messliste Gruppe C. Jede Datei hat genau eine Zeile; Verweise stehen als `datei.test.ts::wörtlicher Titel` (Titel per Grep ermittelt):

| Gelöschte Datei | Entscheidung | Wo |
|---|---|---|
| `trip_python_skip_next_ohne_412` | neuer Test | AC-5 (Go-Store, zwei Nutzer), AC-6 (Nutzlast) |
| `trip_versand_reiter_ohne_dauer_keepalive` | neuer Test | AC-7 (Zustellung-Reiter); Teilersatz für den Trip-Speichertakt: `trip_speicherung_reicht_keepalive_durch.test.ts::Gegenprobe: regulärer Flush (Feld verlassen) → PUT OHNE keepalive, MIT dem bekannten If-Match` |
| `trip_night_block_schalter_verdrahtung` | neuer Test | AC-8 bis AC-10; AC-11 Verweis auf #3305 |
| `feld_erhalt_ohne_ausnahme` | neuer Test | AC-12 (Go-Store, zwei Nutzer) |
| `editor_speichern_ohne_aenderung` | neuer Test | AC-12 (Speichern ohne Änderung im Server) |
| `editor_aenderung_gleich_erwartung` | Verweis | `ac26_einstellung_gleich_ausgabe.test.ts::minus_dann_plus_haengt_hinten_an` |
| `editor_anzeige_gleich_erwartung` | Verweis | `p5c_ableitung_hub_orte_ausgabe.test.ts::vorlage_uebernehmen_mail_wie_vor_p5a_und_anzeige_gleich_mail` |
| `editor_standard_gleich_mail` | Verweis | `ac26_einstellung_gleich_ausgabe.test.ts::trip_nie_eingestellt_zeigt_register_standard` und `ac26_einstellung_gleich_ausgabe.test.ts::orte_nie_eingestellt_zeigt_alle_zeilen_und_gesperrtes` |
| `premium_sms_context_gating_render` | neuer Test | AC-13 |
| `compare_versand_zeigt_schaltbare_premium_sms` | neuer Test | AC-13 (Kontext `vergleich`) |
| `versand_tab_defaults_gleich_auslieferung` | neuer Test | AC-14 |
| `mail_inhalt_haken_grosswetterlage_3237` | neuer Test | AC-15 |
| `vorlage_anwenden_uebernimmt_ampel` | Verweis | `fix_3193_vorlage_abweichung_minimal.test.ts::trip_uebernehmen_wandern_aboampel_mit_abgeleiteten_kindern` |
| `wetter_metriken_vorlage_anwenden_sendet_ampel` | Verweis | `fix_3193_vorlage_abweichung_minimal.test.ts::trip_uebernehmen_wandern_aboampel_mit_abgeleiteten_kindern` und `fix_3193_vorlage_abweichung_minimal.test.ts::vergleich_uebernehmen_wandern_aboampel_temperature_night_neutral` |
| `wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte` | neuer Test | AC-17: Der Trip speichert heute den Ausblick-Schalter (`display_config.placements.outlook_reports`, ADR-0124 Nr. 6; das Altfeld `show_outlook` ist seit #3297/#3298 entfallen) und Warnungswerte (`display_config.metric_alert_levels`); `rework_3036_bloecke_schalter` prüft das nicht, die Nutzlast ist heute nur teilweise belegt (`wertebereiche_nutzlast_verliert_keine_daten.test.ts::metric_alert_levels kommt aus dem aktuellen Zustand, nicht aus dem Preset`) |
| `telegram_kanalgrenze_je_kontext` | Verweis | `was_steht_wo_karte.test.ts::Trip: „nur Tageswert“, „passt nicht mehr“, Zeile mit max_length und Hinweissatz für Trip` (ADR-0124 Nr. 3 gilt für den Trip) |
| `telegram_schnittlinie_wahr` | Verweis | derselbe Test wie oben; `LTCutLine` entfallen |
| `sms_reiter_roh_einfach_nur_fuer_sms_format_capable` | begründeter Status | `ausnahme`, ADR-0124 Nr. 5 |
| `nur_ein_bericht_kennzeichnung` | begründeter Status | `ausnahme`, #3065 und Prod-Messung |
| `thunderThresholdCatalogGuard` | Verweis | `thunderThresholdLevels.test.ts::leerer Katalog -> leere Liste, kein Wurf` und `thunderThresholdLevels.test.ts::undefined (Katalog noch nicht geladen) -> leere Liste, kein Wurf` (`deriveThunderThresholdLevels` lebt in `compareMetricCatalogLoader.ts`; #3366/R2 darf diesen Test nicht mit löschen) |

Regeln für neue Prüfungen: kein Mock-Theater; Zusicherungen im Server mit echtem Go-Test, im Frontend mit `node --test` gegen echte Module. Mutations-Gegenprobe im Adversary-Schritt.

Zuordnungsliste als Artefakt für Menschen: `docs/artifacts/rework-3020-pruefungen-und-waisen/zuordnung-geloeschter-faelle.md` mit „gelöschter Fall → neuer Test oder Begründung“ für die 20 Dateien und die 17 gestrichenen Katalogfälle (15 Editor `E-*`, `O-VT-H-NEU-IN-LISTEN`, `trip-ac10--neu_in_bearbeitetem_layout--html`). Kein Test darauf.

Zeigt ein wiederhergestellter Test einen echten Produktfehler, wird er gemeldet und als eigenes Issue angelegt, nicht hier behoben.

## Expected Behavior

- **Input:** Katalog `fallliste_*.json`, vorhandene Tests, neue Prüfungen.
- **Output:** Wächter meldet jeden Verweis auf nicht existierenden Test rot; die 26 Fälle verweisen auf echte Tests oder tragen `ausnahme` mit Begründung; jedes lebende Verhalten hat eine Prüfung dort, wo es wirkt.
- **Side effects:** keine Produktionsänderung; nicht angefasst werden `frontend/src/lib/components/molecules/EinstellTabelle.svelte` und deren Test sowie `.claude/hooks`.

## Acceptance Criteria

- **AC-1:** Given ein Katalogfall mit erfundenem Testnamen ohne Dateiangabe / When der Wächter läuft, obwohl irgendeine Vitest-Datei eine reine Platzhalter-Vorlage wie `${key}` als Titel hat / Then meldet der Wächter diesen Fall als Fehler (rot).
  - Test: Python-Test legt den Katalogfall an und verlangt den Fehler von `pruefe_testverweise`; Mutation (Platzhalter wieder als `.+`) macht den Test rot.

- **AC-2:** Given eine Titelvorlage mit festem Textanteil und eine reine Platzhalter-Vorlage / When Katalogfälle auf passende Titel verweisen / Then trifft die Vorlage mit festem Anteil, die reine Platzhalter-Vorlage nie.
  - Test: Python-Test gegen `_vitest_titel_gefunden` mit beiden Vorlagen.

- **AC-3:** Given die 26 bisher falsch-grünen Fälle `D-*-frontend` / When der Katalog-Test mit dem verschärften Wächter läuft / Then verweist jeder Fall auf einen existierenden, passenden Test mit Dateiangabe oder trägt `ausnahme` mit Verweismuster; kein Fall steht grün ohne echten Test.
  - Test: `pruefe_testverweise` über `fallliste_editor.json` ist grün; derselbe Lauf gegen den Katalog vor der Korrektur wäre rot (Beweis, dass der Wächter die Fälle erkennt).

- **AC-4:** Given ein Trip mit mehr als sieben Metriken in der Karte / When die Telegram-Spalte dargestellt wird / Then zeigt sie ab der achten Metrik nur den Tageswert (ADR-0124 Nr. 3), und der Katalogfall zur Schnittlinie verweist auf diesen Test mit Status `gruen`.
  - Test: `node --test` `organisms/__tests__/was_steht_wo_karte.test.ts` (Titel „Trip: „nur Tageswert“, …“); der Wächter prüft, dass der Verweis den Test findet.

- **AC-5:** Given zwei verschiedene Nutzer mit je einem Trip, in dessen `report_config` `skip_next` gesetzt ist / When Nutzer A den Trip über den Go-Speicherpfad ohne `skip_next` in der Nutzlast speichert / Then bleibt `skip_next` bei A erhalten, und Trip und Daten von Nutzer B bleiben unverändert.
  - Test: Go-Test `internal/store/trip_skip_next_erhalt_test.go` (echter Store, zwei `user_id`, neben `trip_flat_fields_test.go`).

- **AC-6:** Given ein geladener Trip mit `skip_next` / When das Frontend die Speichernutzlast aus Karte und Zustellung baut / Then enthält die Nutzlast `skip_next` nie.
  - Test: `node --test` gegen echtes `pickEigenfelder`/`tripSpeicherung` (ergänzend zu AC-5).

- **AC-7:** Given der Zustellung-Reiter eines Trips / When gespeichert und beim Verlassen geflusht wird / Then trägt der PUT If-Match, das normale Speichern hat kein keepalive, der Flush hat `keepalive:true`, und der Antwort-Stempel wird für den nächsten Schreibvorgang übernommen.
  - Test: `node --test` gegen `zustellungSpeicherung.ts` mit aufgezeichneten Anfrage-Köpfen.

- **AC-8:** Given ein Alt-Trip ohne Feld `show_night_block` / When die Karte geöffnet wird / Then zeigt der Nachtblock-Schalter „an“.
  - Test: `node --test` gegen Kartenmodell (`wasStehtWoSpeicherung.ts`), eigener Test.

- **AC-9:** Given derselbe Alt-Trip / When der Nutzer speichert, ohne den Schalter zu berühren / Then wird `show_night_block` nicht gesendet, und der Go-Store schreibt das Feld auch nicht neu, mit zwei Nutzern (Alt-Trip von B bleibt ebenfalls ohne Feld).
  - Test: `node --test` (Nutzlast ohne Feld) und Go-Test `internal/store/trip_night_block_altstandard_test.go` (zwei Nutzer).

- **AC-10:** Given der Nutzer hat den Nachtblock-Schalter geändert / When er die Änderung verwirft / Then ist der Sende-Merker zurückgesetzt und der nächste Speichervorgang sendet das Feld nicht.
  - Test: `node --test` gegen `wasStehtWoSpeicherung.ts`, eigener Test.

- **AC-11:** Given ein noch nicht gespeicherter neuer Trip / When die Karte im Anlegen-Modus den Nachtblock-Schalter zeigt und der Nutzer ihn umschaltet / Then wird der Wert mit dem Anlegen gemeldet und es gibt keinen Teilfeld-PUT. Das Verhalten des Alt-Editors („kein Schalter beim Anlegen“) ist durch #3305 (Tabelle beim Trip-Anlegen, PO-freigegeben, live) abgelöst.
  - Test: Verweis `was_steht_wo_karte_anlegen_3305.test.ts::Schalter (Nacht-Block): gemeldet mit felder und felderStart, kein Teilfeld-PUT`; der in RED geschriebene Gegentest `rework_3020_nachtblock_schalter` wird auf diesen Stand gebracht bzw. der Fall dort entfernt.

- **AC-12:** Given zwei Nutzer mit je einem Trip mit `display_config.metrics.morning_enabled`, `evening_enabled`, `format_mode` / When Nutzer A speichert, ohne diese Felder zu ändern oder mitzusenden / Then sind die drei Felder bei A unverändert, bei B ebenso.
  - Test: Go-Test `internal/store/trip_display_config_felderhalt_test.go` (echter Store, zwei `user_id`).

- **AC-13:** Given ein Trip bzw. Ortsvergleich im Zustellung-Reiter / When ein Premium-SMS-Handler vorhanden bzw. nicht vorhanden ist / Then ist das Premium-SMS-Kästchen schaltbar bzw. gesperrt, im Vergleich ist der Block sichtbar und schaltbar.
  - Test: `node --test` gegen `zustellungModell.ts` für `context="route"` und `"vergleich"`.

- **AC-14:** Given ein neu angelegter Trip bzw. Ortsvergleich / When der Zustellung-Reiter seine Standardwerte zeigt / Then entsprechen sie der ausgelieferten Standard-Nutzlast (Defaults = Auslieferung).
  - Test: `node --test`, der Reiter-Standardwerte und ausgelieferte Standard-Nutzlast aus derselben Quelle vergleicht, für beide Kontexte.

- **AC-15:** Given ein Trip mit `show_stability=true`/`show_outlook=false` und umgekehrt / When die Karte den Haken Großwetterlage zeigt / Then folgt der Haken `show_stability` und nie `show_outlook`.
  - Test: `node --test` gegen `mailInhaltKonstanten.ts` und Kartenmodell, beide Kombinationen.

- **AC-16:** Given ein Katalogfall, dessen Verweisziel (Testdatei oder Titel) nicht existiert, und zugleich die übrigen Katalogfälle mit gültigem Verweis / When der Wächter läuft / Then wird genau der Fall mit dem fehlenden Test rot, die anderen bleiben grün.
  - Test: Python-Test erzeugt beide Fallarten im Speicher und prüft die Fehlerliste von `pruefe_testverweise` (nur Wächter-Verhalten).

- **AC-17:** Given ein Trip, bei dem der Nutzer in der Karte den Ausblick ein- bzw. ausschaltet und eine Warnungsstufe ändert / When die Karte den Trip speichert / Then trägt die Speichernutzlast `placements.outlook_reports` und `metric_alert_levels` mit genau diesen Werten, kein Altfeld (`show_outlook`, `multi_day_trend_reports`) steht darin, und nicht geänderte Felder bleiben aus der Nutzlast.
  - Test: `node --test` gegen echtes `wasStehtWoSpeicherung`/`tripSpeicherung` (Trip-Pfad); dazu wird `internal/store/trip_metric_alert_levels_test.go` um einen Fall mit zwei Nutzern erweitert: Nutzer A speichert `metric_alert_levels` und `placements.outlook_reports`, Nutzer B mit gleicher Trip-ID bleibt unverändert, und ein Teil-Update von A erhält die übrigen `display_config`-Felder (Merge).

## Known Limitations

- Die Zahl „33 von 57 mit Beleglücke“ aus der S1-Testtabelle ist nicht nachprüfbar; maßgeblich ist die Messliste im Kontext-Dokument.
- Der Wächter erkennt nur Titel in Vitest-Dateien; Tests mit rein dynamischem Titel ohne festen Anteil müssen mit Dateiangabe und wörtlichem Titel verwiesen werden.
- Die Zuordnungsliste ist ein Dokument für Menschen und wird nicht maschinell geprüft.
- Zeigt eine neue Prüfung einen Produktfehler, wird er nur gemeldet und als eigenes Issue geführt.
- `thunderThresholdLevels.test.ts` steht in der R2-Liste als „Namensbezug“; er bleibt, weil `compareMetricCatalogLoader.ts` lebt.

## Out of Scope

- **R2 (Waisen löschen) und #3366:** eigener Durchlauf.
- **#3374:** tote Browser-Specs, eigener Durchlauf.
- **#3375:** Browser-Fall zu Telegram „nur Tageswert“ (erledigt mit #3375: `kanal-grenzen-und-hinweise.staging.spec.ts`; Marken über 14 Auflösungen: `kuerzel-marken-sichtbar.staging.spec.ts`).
- `frontend/src/lib/components/molecules/EinstellTabelle.svelte` und deren Test (andere Sitzung); Dateien unter `.claude/hooks`.
- Wiederaufbau entfallener Alt-Funktionen (`LTCutLine`, SMS Roh/Einfach, Nur-ein-Bericht).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Wächter-Selbstnachweis (AC-1, AC-2, AC-16): erfundener Verweis rot, Vorlage mit festem Anteil trifft.
- [ ] Katalog nach Umverweisung grün; vor der Korrektur rot (AC-3, AC-4).
- [ ] Go-Tests mit zwei Nutzern: `skip_next` (AC-5), Alt-Trip ohne `show_night_block` (AC-9), `display_config`-Felderhalt (AC-12).
- [ ] `node --test`: Nutzlast ohne `skip_next` (AC-6), If-Match/keepalive (AC-7), einzelne Nachtblock-Tests (AC-8 bis AC-11), Premium-SMS (AC-13), Defaults = Auslieferung (AC-14), Haken Großwetterlage (AC-15), Ausblick und Warnungswerte (AC-17), Telegram „nur Tageswert“ (AC-4, bestehend).
- [ ] Mutations-Gegenprobe je AC im Adversary-Schritt (String-Ersetzung mit externer Sicherungskopie).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; stützt sich auf ADR-0124 (Nr. 3, Nr. 5)
- **Rationale:** Es wird keine Architekturentscheidung geändert. Die Statuszuordnung entfallener Fälle (`ausnahme` mit ADR-0124 bzw. #3065) ist eine Entscheidung des Tech Leads auf Grundlage von ADR-0124, #3065 und der Prod-Messung vom 25.11.2026.

## Definition of Done

- Alle ACs haben einen Test, der vorher rot und danach grün war. Ausnahme sind reine Verweiszeilen; deren Ersatztest muss existieren, und der Wächter prüft ihn.
- Der Katalog-Wächter wird bei einem erfundenen Verweis rot, Selbstnachweis inklusive.
- Die Go-Tests für den Schreibpfad laufen mit zwei Nutzern.
- Die Zuordnungsliste `docs/artifacts/rework-3020-pruefungen-und-waisen/zuordnung-geloeschter-faelle.md` deckt alle 60 Dateien und 17 Katalogfälle ab.
- Die Adversary-Prüfung ist VERIFIED, CI 6/6 grün und der Stand live ausgeliefert.
- #3020 bleibt offen, bis #3366 (R2) erledigt ist.

## Changelog

- 2026-11-25: Initial spec created (R1 und R1b; R2, #3366, #3374 ausgenommen)
- 2026-11-25: Überarbeitet nach Validierung: Telegram als lebend (grün), Server-Zusicherungen als Go-Tests mit zwei Nutzern, AC-7 aufgeteilt, Zuordnungstabelle für 20 Dateien
- 2026-11-25: Zweite Überarbeitung: Verweise mit wörtlichem Titel, fix_3193 als Ersatz für Vorlage-Ampel, AC-17 für Ausblick/Warnungswerte, AC-4 nur Trip, Dateizahl 16
