# Adversary Dialog — rework-3020-pruefungen-und-waisen
Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md
Datum: 2026-11-25 21:37

## Checkliste
- [x] **Input:** Katalog `fallliste_*.json`, vorhandene Tests, neue Prüfungen.
- [x] **Output:** Wächter meldet jeden Verweis auf nicht existierenden Test rot; die 26 Fälle verweisen auf echte Tests oder tragen `ausnahme` mit Begründung; jedes lebende Verhalten hat eine Prüfung dort, wo es wirkt.
- [x] **Side effects:** keine Produktionsänderung; nicht angefasst werden `frontend/src/lib/components/molecules/EinstellTabelle.svelte` und deren Test sowie `.claude/hooks`.
- [x] **AC-1:** Given ein Katalogfall mit erfundenem Testnamen ohne Dateiangabe / When der Wächter läuft, obwohl irgendeine Vitest-Datei eine reine Platzhalter-Vorlage wie `${key}` als Titel hat / Then meldet der Wächter diesen Fall als Fehler (rot).
- [x] **AC-2:** Given eine Titelvorlage mit festem Textanteil und eine reine Platzhalter-Vorlage / When Katalogfälle auf passende Titel verweisen / Then trifft die Vorlage mit festem Anteil, die reine Platzhalter-Vorlage nie.
- [x] **AC-3:** Given die 26 bisher falsch-grünen Fälle `D-*-frontend` / When der Katalog-Test mit dem verschärften Wächter läuft / Then verweist jeder Fall auf einen existierenden, passenden Test mit Dateiangabe oder trägt `ausnahme` mit Verweismuster; kein Fall steht grün ohne echten Test.
- [x] **AC-4:** Given ein Trip mit mehr als sieben Metriken in der Karte / When die Telegram-Spalte dargestellt wird / Then zeigt sie ab der achten Metrik nur den Tageswert (ADR-0124 Nr. 3), und der Katalogfall zur Schnittlinie verweist auf diesen Test mit Status `gruen`.
- [x] **AC-5:** Given zwei verschiedene Nutzer mit je einem Trip, in dessen `report_config` `skip_next` gesetzt ist / When Nutzer A den Trip über den Go-Speicherpfad ohne `skip_next` in der Nutzlast speichert / Then bleibt `skip_next` bei A erhalten, und Trip und Daten von Nutzer B bleiben unverändert.
- [x] **AC-6:** Given ein geladener Trip mit `skip_next` / When das Frontend die Speichernutzlast aus Karte und Zustellung baut / Then enthält die Nutzlast `skip_next` nie.
- [x] **AC-7:** Given der Zustellung-Reiter eines Trips / When gespeichert und beim Verlassen geflusht wird / Then trägt der PUT If-Match, das normale Speichern hat kein keepalive, der Flush hat `keepalive:true`, und der Antwort-Stempel wird für den nächsten Schreibvorgang übernommen.
- [x] **AC-8:** Given ein Alt-Trip ohne Feld `show_night_block` / When die Karte geöffnet wird / Then zeigt der Nachtblock-Schalter „an“.
- [x] **AC-9:** Given derselbe Alt-Trip / When der Nutzer speichert, ohne den Schalter zu berühren / Then wird `show_night_block` nicht gesendet, und der Go-Store schreibt das Feld auch nicht neu, mit zwei Nutzern (Alt-Trip von B bleibt ebenfalls ohne Feld).
- [x] **AC-10:** Given der Nutzer hat den Nachtblock-Schalter geändert / When er die Änderung verwirft / Then ist der Sende-Merker zurückgesetzt und der nächste Speichervorgang sendet das Feld nicht.
- [x] **AC-11:** Given ein noch nicht gespeicherter neuer Trip / When die Karte im Anlegen-Modus den Nachtblock-Schalter zeigt und der Nutzer ihn umschaltet / Then wird der Wert mit dem Anlegen gemeldet und es gibt keinen Teilfeld-PUT. Das Verhalten des Alt-Editors („kein Schalter beim Anlegen“) ist durch #3305 (Tabelle beim Trip-Anlegen, PO-freigegeben, live) abgelöst.
- [x] **AC-12:** Given zwei Nutzer mit je einem Trip mit `display_config.metrics.morning_enabled`, `evening_enabled`, `format_mode` / When Nutzer A speichert, ohne diese Felder zu ändern oder mitzusenden / Then sind die drei Felder bei A unverändert, bei B ebenso.
- [x] **AC-13:** Given ein Trip bzw. Ortsvergleich im Zustellung-Reiter / When ein Premium-SMS-Handler vorhanden bzw. nicht vorhanden ist / Then ist das Premium-SMS-Kästchen schaltbar bzw. gesperrt, im Vergleich ist der Block sichtbar und schaltbar.
- [x] **AC-14:** Given ein neu angelegter Trip bzw. Ortsvergleich / When der Zustellung-Reiter seine Standardwerte zeigt / Then entsprechen sie der ausgelieferten Standard-Nutzlast (Defaults = Auslieferung).
- [x] **AC-15:** Given ein Trip mit `show_stability=true`/`show_outlook=false` und umgekehrt / When die Karte den Haken Großwetterlage zeigt / Then folgt der Haken `show_stability` und nie `show_outlook`.
- [x] **AC-16:** Given ein Katalogfall, dessen Verweisziel (Testdatei oder Titel) nicht existiert, und zugleich die übrigen Katalogfälle mit gültigem Verweis / When der Wächter läuft / Then wird genau der Fall mit dem fehlenden Test rot, die anderen bleiben grün.
- [x] **AC-17:** Given ein Trip, bei dem der Nutzer in der Karte den Ausblick ein- bzw. ausschaltet und eine Warnungsstufe ändert / When die Karte den Trip speichert / Then trägt die Speichernutzlast `placements.outlook_reports` und `metric_alert_levels` mit genau diesen Werten, kein Altfeld (`show_outlook`, `multi_day_trend_reports`) steht darin, und nicht geänderte Felder bleiben aus der Nutzlast.


## Findings

Finding:
  ID: F001
  Status: BEHOBEN (Runde 3)
  Severity: MEDIUM
  Category: spec_violation
  Code reference: docs/artifacts/rework-3020-pruefungen-und-waisen/zuordnung-geloeschter-faelle.md:52
  Description: Die geloeschte Datei shared/__tests__/wetter_metriken_versand_panel_speicherung.test.ts steht in Gruppe A ("nur gelöschter Quelltext"). Im Altstand c8329fea4^1 prueft sie im Block "context vergleich" das Zusammenspiel zweier Schreiber (Wetter-Metriken und Versand) mit einem Controller ueber versandVergleichSpeicherung.ts, weatherMetricsCompareSave.ts und compareHubPersistenz.ts; alle drei existieren heute (Abbruch, Zuruecksetzen binnen 700 ms, Re-Hydration, 500er-Fehler).
  Spec requirement: Gruppe A = prueft nur gelöschten Quelltext; lebendes Verhalten gehoert in Gruppe C (AC-16, Zuordnungsliste).
  Conflict: Die Begruendung trifft fuer den Vergleichs-Block nicht zu; die Rennlage zweier Speicherstroeme im lebenden Code ist ungeprueft und nicht in C gefuehrt.
  Remediation: Datei nach C umsortieren und an den heutigen Modulen belegen, oder benennen, welcher bestehende Test sie deckt.

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:D-trip_tabellen-nur_ein_bericht_semantik-frontend
  Description: Die vier n3-Faelle verweisen mit seite go auf denselben Go-Test TestRework3020_SpeichernOhneAenderungErhaeltMetrikFlags_ZweiNutzer. Er belegt nur den Erhalt von morning_enabled/evening_enabled, nicht Semantik, Kennzeichnung oder Editorstand. seite go ist ueberfluessig, weil der Zweig _test.go:: im Wächter zuerst greift (tests/tdd/test_einstellung_gleich_mail_fallliste.py:285).
  Spec requirement: AC-3 — ausnahme mit Verweismuster und existierendem passendem Test.
  Conflict: Nur der vierte Fall (Flags bewahrt) ist belegt; drei Faelle sind ausnahme "entfaellt bewusst" mit thematisch benachbartem Test. Der verweis-Text ist ehrlich; die Prod-Messung ist hier nicht nachpruefbar. Keine Umgehung des Wächters, aber ein Testverweis als Pflichtfeld.
  Remediation: Fuer entfallene Faelle keinen Testverweis erzwingen oder klaren Status fuer "entfallen" einfuehren.

Finding:
  ID: F003
  Status: BEHOBEN (Runde 3)
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts:36
  Description: Eigene Mutationen M9 (zustellungModell.ts Rueckfall COOLDOWN_STANDARD gleich 0) und M11 (STILLE_VON_STANDARD 22:00 gleich 21:00) lassen alle AC-14-Tests gruen. Der Test gibt Cooldown und Stille aus demselben alarm-Objekt an Stand und POST und vergleicht sie nicht; pruefeBriefingFelder deckt nur Briefing-Zeiten und Kanaele.
  Spec requirement: AC-14 — Standardwerte des Zustellung-Reiters entsprechen der ausgelieferten Standard-Nutzlast.
  Conflict: Abweichende Alarm-Standardwerte (Cooldown, Stillezeit) zwischen Anzeige und Auslieferung wuerden nicht rot.
  Remediation: alert_cooldown_minutes und alert_quiet_from/to aus dem POST gegen den angezeigten Stand pruefen, mit Eintritt ohne diese Felder.

Finding:
  ID: F004
  Status: BEHOBEN (Runde 3)
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:158
  Description: Mutation M13 (Zweig premium_sms_reply_state stale deaktiviert) bleibt in den rework_3020-Tests gruen; AC-13 prueft nur Handler vorhanden oder nicht. Der stale-Zweig ist sicherheitsrelevant.
  Spec requirement: AC-13 (nur vorhanden/nicht vorhanden gefordert).
  Conflict: Keine Spec-Verletzung; Hinweis, dass der Zweig durch diese Dateien nicht bewacht ist.
  Remediation: Pruefen, ob ein bestehender Test den stale-Zweig fuehrt.

## Confirmations

Confirmation:
  AC: AC-1
  Code reference: tests/tdd/test_einstellung_gleich_mail_fallliste.py:201
  Evidence: Erfundener Titel ohne Datei, '${x}', '.+' und ' ' liefern per Skript je einen Fehler (ROT); nur der echte Titel bleibt gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: tests/tdd/test_einstellung_gleich_mail_fallliste.py:181
  Evidence: _hat_festen_anteil/_template_muster: reine Platzhalter-Vorlage gibt None und trifft nie; Vorlage mit festem Anteil trifft (anzeige_gleich_ausgabe_a_bewusst_leer).
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: tests/tdd/test_einstellung_gleich_mail_fallliste.py:283
  Evidence: Alle 26 Faelle verweisen auf existierende Titel mit Datei oder tragen ausnahme mit Verweis; ausnahme-Faelle laufen durch dieselbe Pruefung (STATUS_MIT_TEST); 32 pytest passed.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:E-3020-TRIP-TG-NUR-TAGESWERT
  Evidence: Neuer Fall status gruen verweist auf was_steht_wo_karte.test.ts::Trip: nur Tageswert (Titel existiert, Wächter gruen).
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: internal/store/trip_display_config_felderhalt_test.go:1
  Evidence: Mutation delete skip_next nach ReportConfig-Merge in internal/handler/trip.go wird rot (SkipNextBleibtBeimSpeichernOhneFeld_ZweiNutzer).
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/__tests__/rework_3020_trip_nutzlast_ohne_skip_next.test.ts:1
  Evidence: 27 node-Tests gruen; Mutationsnachweis des Implementierers F1a/F1b rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/api.ts:145
  Evidence: Eigene Mutationen: If-Match-Header entfernt (M5) und If-Match nur bei Konflikt (M6) werden beide rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/components/shared/wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts:1
  Evidence: Tests gruen; Mutation M4 (show_stability aus Nutzlast) faellt in AC-15 und AC-9/10 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: internal/store/trip_display_config_felderhalt_test.go:1
  Evidence: Go-Store-Test mit zwei Nutzern gruen; Mutation M3b/M1b (Felder nach Merge entfernt) rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: frontend/src/lib/components/shared/wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts:1
  Evidence: Tests gruen; M4 zeigt rot im AC-9/AC-10-Test.
  Status: CONFIRMED

Confirmation:
  AC: AC-11
  Code reference: frontend/src/lib/components/organisms/__tests__/rework_3020_karte_schalter.test.ts:1
  Evidence: Test auf das #3305-Verhalten (Schalter im Anlegen, Wert wird gemeldet) umgestellt, gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-12
  Code reference: internal/store/trip_display_config_felderhalt_test.go:33
  Evidence: Mutation M1b (metrics nach Merge geloescht) rot im AC-12-Test; zwei Nutzer, B als Byte-Vergleich.
  Status: CONFIRMED

Confirmation:
  AC: AC-13
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:141
  Evidence: Mutation M12 (Premium-Gate aus) wird in route und vergleich rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-14
  Code reference: frontend/src/lib/components/shared/zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts:36
  Evidence: Tests gruen, Zeiten/Kanaele/Alarmkanaele verglichen; Luecke bei Cooldown/Stille siehe F003.
  Status: CONFIRMED

Confirmation:
  AC: AC-15
  Code reference: frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts:238
  Evidence: M4 (show_stability aus der Liste) rot in AC-15 und Nachtblock-Test.
  Status: CONFIRMED

Confirmation:
  AC: AC-16
  Code reference: tests/tdd/test_einstellung_gleich_mail_fallliste.py:201
  Evidence: Jeder falsche Verweis wird einzeln gemeldet (genau ein Fehler je Fall); Selbsttests in test_einstellung_gleich_mail_waechter_3020.py gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-17
  Code reference: frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts:124
  Evidence: M7 (metric_alert_levels leer) und M8 (Ausblick-Filter invertiert) rot; Go M3b/M3c rot.
  Status: CONFIRMED


## Dialog

### Runde 1
**Adversary:** Wächter per Skript mit Katalogfaellen angegriffen (erfundener Titel, nur ${x}, ${x} mit Datei, Titel aus falscher Datei, erfundener Titel mit Datei, leer, ".+", Leerzeichen, Go-Name falsch, Go-Datei falsch): alle ROT, nur der echte Verweis gruen. Gelesen: tests/tdd/test_einstellung_gleich_mail_fallliste.py, tests/fixtures/einstellung_gleich_mail/fallliste_editor.json, frontend/src/lib/components/organisms/__tests__/rework_3020_karte_schalter.test.ts, frontend/src/lib/components/shared/wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts, docs/artifacts/rework-3020-pruefungen-und-waisen/test-green-output.txt. ausnahme-Faelle laufen durch dieselbe Verweispruefung. Stichprobe gruen-Verweise (Trip nie_eingestellt, gespeichert_folge, hinweis_grundauswahl_leer, bewusst_leer, ohne_ausblick, Vorlage-Reihenfolge): Titel existieren und passen; "gesperrt mit Grundtext je reason" ist fuer ohne_ausblick nur sinngemaess. Elf ausnahme-Faelle: Altfeld-Zustaende, ADR-0124 Nr. 3/4 laesst keine Kanal-Liste zu; Reihenfolge und Grundauswahl sind durch die gruenen Python-Faelle gedeckt, daher gerechtfertigt. Zuordnungsliste docs/artifacts/rework-3020-pruefungen-und-waisen/zuordnung-geloeschter-faelle.md: alle 60 Dateien und 17 E-Faelle vorhanden (30 A, 10 B, 20 C). Stichprobe von 30 Gruppe-A-Dateien gegen heute existierende Importe des Altstands: wetter_metriken_versand_panel_speicherung.test.ts importiert drei lebende Module (F001).
**Implementierer:** nicht beteiligt (isolierter Kontext); Mutationsnachweis mutationsnachweis-red.md gelesen.

### Runde 2
**Adversary:** 16 eigene Mutationen per String-Ersetzung mit Sicherung und sha256-Pruefung, jeweils wiederhergestellt: Go M1 (format_mode top-level) GRUEN und M3 (morning_enabled top-level) GRUEN, beide verworfen, weil die Felder in metrics-Eintraegen liegen; M1b metrics loeschen ROT, M2 skip_next loeschen ROT, M3b placements loeschen ROT, M3c Merge ignoriert metric_alert_levels ROT. Frontend M4 show_stability aus Nutzlast ROT, M5 If-Match-Header weg ROT, M6 If-Match nur bei Konflikt ROT, M7 metric_alert_levels leer ROT, M8 Ausblick-Filter invertiert ROT, M9 Cooldown-Rueckfall 0 GRUEN (F003), M10 keepalive-Zweig tripSpeicherung (anderer Reiter) GRUEN, M11 Stille-Standard GRUEN (F003), M12 Premium-Gate aus ROT, M13 stale-Zweig GRUEN (F004). Index unveraendert (6 gestagte Dateien). Tests: pytest 32 passed, node 27 passed, go test ./internal/store/ ok (docs/artifacts/rework-3020-pruefungen-und-waisen/adversary-test-output.txt). Keine Produktionsdatei veraendert.
**Implementierer:** nicht beteiligt.

### Runde 3
**Adversary:** Fix-Loop geprueft. Wiederholte Mutationen jetzt alle ROT (je mit Sicherung und sha256-Pruefung wiederhergestellt): Cooldown-Rueckfall 0 (AC-14 route und vergleich), Stille 22:00 gleich 21:00 (AC-14), stale-Zweig deaktiviert (AC-13 route und vergleich), Queue-Serialisierung entfernt (neuer Test rework_3020_vergleich_parallele_schreiber) und ETag-Stempel entfernt (derselbe Test). F001, F003 und F004 sind behoben. Tests: pytest 32 passed, node 33 passed, go test ./internal/store/ ok. F002 (LOW) bleibt als Hinweis.
**Implementierer:** Luecken geschlossen (Test ergaenzt, Zuordnung 29 A / 10 B / 21 C).

## Herkunft der Vorbedingungen

Kein Feld mit Test-Zuweisung gefunden — nichts zu pruefen.

## Verdict
VERDICT: VERIFIED (F001, F003, F004 behoben und per Mutation belegt; F002 LOW offen als Hinweis)

## Geprüfte Dateien

- sha256:25de1d9f13d1525d84260bc924d03bdff7bfd7f96d73e16926714e84f8b0791b  docs/artifacts/rework-3020-pruefungen-und-waisen/zuordnung-geloeschter-faelle.md
- sha256:937125fd6df27a1b31402bccfa0d490b9b2468a304a9aebca08806c61f776541  frontend/src/lib/api.ts
- sha256:dfc82126b8dd60cfb4d6bcdfb72f32b45cd2bec76dbf4a0c283ab7aa2bdd3f6b  frontend/src/lib/components/organisms/__tests__/rework_3020_karte_schalter.test.ts
- sha256:33f48610c5e556679ada131cb976dcd0bd7143efd819b5029bae3563391613ee  frontend/src/lib/components/shared/__tests__/rework_3020_trip_nutzlast_ohne_skip_next.test.ts
- sha256:1f43d911b3fb959972a8c4b04a85ee00f0252322be20817f97873405aea225ea  frontend/src/lib/components/shared/wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts
- sha256:9c101e7d3689ece3b1bc17f76d8063cc9c733ed42a19410be0e58428412f4d86  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- sha256:edd5db97a25dc83cdfaddea7c23ab70089dab71281309c43bab85dc815b0f8a9  frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts
- sha256:b4854d836cee7ff318e781d562e7a2d20bf8d61c50f0aff9fbf2688be8e7b808  frontend/src/lib/components/shared/zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts
- sha256:fb48b2fd1f94737bef499ec45ff5ad2a95afcf014d8800039bee3779761deade  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- sha256:5eb10cd109ab84011353715b9f89bc3727904360dfc4e76629671fa2d8f76bcb  internal/store/trip_display_config_felderhalt_test.go
- sha256:13aa81ea2954e23a15fa031af686b80864704fd9b84b6420380adc3912688f6a  tests/tdd/test_einstellung_gleich_mail_fallliste.py

## Prüfbasis

- base: a0a801a0bfe3d7eb0c1f679cfa0b0ab7435eed8d
- blob:b69bbff5a63b9ff6f92fdc9c2068577f756c3079  docs/artifacts/rework-3020-pruefungen-und-waisen/zuordnung-geloeschter-faelle.md
- blob:b9af2f1376a14fba16f4df85aee056b8fb0e9de4  frontend/src/lib/api.ts
- blob:eae78c20f43b1e6d6406a5f5a4f2165f4ce430e5  frontend/src/lib/components/organisms/__tests__/rework_3020_karte_schalter.test.ts
- blob:c5ea3ee34d0c91f4c1eaad0eb68e6cecc979b67d  frontend/src/lib/components/shared/__tests__/rework_3020_trip_nutzlast_ohne_skip_next.test.ts
- blob:4bf781e9d983ec10c700d8a0ba5a93398e7b96e9  frontend/src/lib/components/shared/wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts
- blob:7d464da5c48fe67ec61d87fdae15f5e0293b01ec  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- blob:7c5f71bf34f746a7c235c7de0d5c0da5d211b61c  frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts
- blob:4aa04f3bbf7b47f509be565cdcbde18da9899aea  frontend/src/lib/components/shared/zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts
- blob:2f0d89b599e14d015cddef9deb408815a2589db1  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- blob:789763c86bcf18197801f40977b069122ed5deb3  internal/store/trip_display_config_felderhalt_test.go
- blob:72b7307b306d4c02500480875e0b6433cb919804  tests/tdd/test_einstellung_gleich_mail_fallliste.py
