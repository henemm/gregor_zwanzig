# Befunde Runde 7 (#3047)

Status nach den Behebungspaketen: ausgelagert 8 · geklaert 3 · gruen 45 · rot 10.
Quelle: `inventar/*_befunde.md` und `inventar/befund_status.json`, erzeugt mit `inventar/konsolidieren.py`.

| ID | Schwere | Kurztext | Status | Test/Issue |
|---|---|---|---|---|
| B-TM1 | mittel | Kompakt-Mail: amtliche Warnungen stehen nicht an erster Stelle (WV6) | gruen | tests/tdd/test_kompakt_mail_schalter_runde7.py::test_kompakt_amtliche_warnung_vor_jedem_inhaltsblock |
| B-TM2 | niedrig | Wieder eingeschaltete Metrik landet in der Mail an alter Stelle statt „hinten angehängt“ | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::minus_dann_plus_haengt_hinten_an |
| B-TM3 | mittel | Testlücke: Schalter „Amtliche Warnungen“ (W20) beim Trip-Briefing ungeschützt | gruen | tests/tdd/test_einstellung_gleich_mail_runde7_katalog.py::test_trip_w20_amtliche_warnungen_schalter_wirkt_in_der_mail |
| B-TM4 | niedrig | Hinweis (keine Fehlwirkung): Prüfkatalog umgeht zwei render-wirksame Weichen | gruen | tests/tdd/test_einstellung_gleich_mail_runde7_katalog.py::test_trip_ausblick_erscheint_im |
| B-OM-1 | mittel | Klartext ohne Hinweis „Amtliche Warnungen aktuell nicht abrufbar“ | gruen | tests/tdd/test_3047_runde7_orte_mail.py::test_om1_klartext_traegt_hinweis_nicht_abrufbar_wie_html |
| B-OM-2 | mittel | Schalter „Amtliche Warnungen“ aus → HTML zeigt weiter die Zeile „Amtliche Warnungen – – –“ | gruen | tests/tdd/test_3047_runde7_orte_mail.py::test_om2_warnungen_aus_keine_leere_warnzeile |
| B-OM-3 | mittel | K3b: Mail-Kopf zeigt zwei verschiedene Profile (Vorlage UND altes `profil`) | ausgelagert | #2796 (K3b Profil im Mail-Kopf) |
| B-OM-4 | niedrig | Klärung: 3-Tages-Ausblick „Erscheint im Morgen/Abend“ für Orte | geklaert | Spec-Nachtrag Runde 7: Konzept V12 nur Trip; Orte zeigen den Ausblick in jedem Briefing |
| B-OM-5 | niedrig | Stundenverlauf ohne Roh/Einfach (W11) | ausgelagert | #3058 (Roh/Einfach Stundenverlauf) |
| B-OM-6 | niedrig | Katalog-Lücke: fünf Einstellungen stehen nicht im #3047-Prüfkatalog | gruen | tests/tdd/test_einstellung_gleich_mail_runde7_katalog.py::test_orte_tagesfenster_wirkt_in_html_und_klartext |
| B-K1 | mittel | Trip-Telegram ignoriert „Windrichtung Roh“ (#3063 Punkt 2) | gruen | tests/tdd/test_3047_r7_kanaele_trip.py::test_ac22_telegram_windrichtung_roh_zeigt_grad_wie_mail |
| B-K2 | mittel | Trip-Telegram: Kappungshinweis bei EN-Nutzern deutsch | gruen | tests/tdd/test_3047_r7_kanaele_trip.py::test_ac22_telegram_kappungshinweis_in_nutzersprache |
| B-K3 | hoch | Orte-SMS/Premium-SMS: amtliche Warnung eines weiteren Ortes fällt vor Wetterzellen weg | gruen | tests/tdd/test_3047_runde7_orte_kanaele.py::test_ac23_warnung_zweiter_ort_faellt_zuletzt_weg |
| B-K4 | mittel | Trip-SMS kürzt nach fester Priorität, nicht nach Listenende | gruen | tests/tdd/test_3047_r7_kanaele_trip.py::test_ac23_sms_kuerzt_vom_listenende_warnung_bleibt |
| B-K5 | niedrig (Trip) / mittel (Orte) | Telegram-Schnittlinie: Konzepttext und Ausgabe widersprechen sich | gruen | Orte: tests/tdd/test_3047_runde7_orte_kanaele.py::test_ac24_telegram_zeilen_ab_8_in_zweiter_zeile; Trip: Ausgabe bleibt (PO 2026-11-16), Erklaersatz Editor ausgelagert #3031/#3033 |
| B-K6 | niedrig (heute nur per API/Altbestand erreichbar) | Orte: `channel_layouts.<kanal> = []` zeigt die volle Grundauswahl statt nichts | gruen | tests/tdd/test_3047_runde7_orte_kanaele.py::test_k6_leere_kanal_liste_bleibt_leer |
| B-K7 | mittel | Orte-Telegram ohne 3-Tages-Ausblick | gruen | tests/tdd/test_3047_runde7_orte_kanaele.py::test_k7_ausblick_im_orte_telegram_kette |
| B-K8 | niedrig | Testlücke: Roh/Einfach in der Orte-Telegram-Liste von keinem Repo-Test bewacht | gruen | tests/tdd/test_3047_runde7_orte_kanaele.py::test_k8_telegram_roh_einfach_je_zeile |
| B-K9 | niedrig (Hinweis an #3032) | Kürzel-Legende: „steht auch am Ende jedes Briefings“ stimmt für Telegram/SMS nicht | ausgelagert | #3032 (Kuerzel-Legende am Briefing-Ende) |
| E1 | hoch | Grundauswahl „nie eingestellt“: Reiter Wetter zeigt die Vorlage, die Mail etwas anderes | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::anzeige_gleich_ausgabe_a_nie_eingestellt_ohne_metrics |
| E2 | mittel | Mehrtages-Trend „nie eingestellt“: Editor aus, Mail abends an; Kurzstil-Umschalten nimmt den Trend still raus | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::anzeige_gleich_ausgabe_a_trend_nie_eingestellt |
| E3 | hoch | Trip-Altformat in `metrics[]` (Zeichenkette / ohne `enabled`): Editor zeigt „nicht gewählt“, Speichern zerstört den Trip | gruen | internal/handler/weather_config_3047_e3_test.go::TestE3_3047_TripPut_DisplayConfigMetrikOhneID_400_ZweiNutzer; tests/tdd/test_3047_e3_trip_altformat_metrics.py::test_kaputter_eintrag_verwirft_nur_den_eintrag_nicht_den_trip |
| E4 | mittel | Amtliche Warnungen, Altbestand-Mischzustand: Schalter „an“, Briefing ohne Warnungen; Speichern schaltet still ein | gruen | tests/tdd/test_3047_e4_amtliche_warnungen_beides_an.py::test_trip_briefing_enthaelt_warnungen_nach_regel (Mischzustand); Neuanlage 'beides an' rot, in Behebung (p11) |
| E5 | niedrig | Trip-Tagesfenster Altbestand halbes Paar oder Start = Ende: Editor zeigt etwas anderes als gilt | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::anzeige_gleich_ausgabe_b_tagesfenster_halb |
| E6 | mittel | Orte: „Tiefsttemperatur Nacht“ aus Vorlagen steht im Reiter, die Mail verwirft sie still | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::e6_nicht_ausgebbare_groesse_steht_gesperrt_statt_still |
| E7 | mittel | Trip: abgeleitete Größen (Tiefsttemperatur Nacht, Tagestief/-hoch, Windchill-Kinder) in der Mail, im Reiter „nicht im Briefing“ | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::anzeige_gleich_ausgabe_a_folge_mit_temperatur |
| E8 | niedrig | Mail-Inhalt-Altwerte `null`: Editor „an“, Mail ohne Block | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::anzeige_gleich_ausgabe_b_mailinhalt_null |
| TL1 | Testlücke | M4 `zustellungModell.ts:255` Abend-Standard Orte `?? false` → `?? true` ⇒ Editor zeigt Abend-Briefing an, Versand aus | rot | offen: Testluecke ohne Behebungspaket (Nebenbefund-Triage #1199) |
| TL2 | Testlücke | M6 `zustellungModell.ts:212` Stille Stunden `&&` → `\|\|` ⇒ halbe Ruhezeit als aktiv angezeigt | rot | offen: Testluecke ohne Behebungspaket (Nebenbefund-Triage #1199) |
| TL3 | Testlücke | M7 `kanalStilSpeicherung.ts:52` Orte-Kurzstil beim Laden ignoriert ⇒ Schalter „aus“, Telegram bekommt Kurzform | rot | offen: Testluecke ohne Behebungspaket (Nebenbefund-Triage #1199) |
| TL4 | Testlücke | M8 `reportConfigPayload.ts:55` Vorrang Flags/Liste ⇒ siehe E2 | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::liste_vor_flags_a_trend_flags_widersprechen (mit E2) |
| TL5 | Testlücke | M16 `internal/handler/trip.go:484` Feld-Merge `alert_channels.email` ⇒ PUT ohne `email` verliert den Wert | rot | offen: Testluecke ohne Behebungspaket (Nebenbefund-Triage #1199) |
| TL6 | Testlücke | M21 `internal/store/compare_preset.go:116` Lade-Klemme Tagesfenster Orte ⇒ Orte-Editor zeigte halbes Paar | rot | offen: Testluecke ohne Behebungspaket (Nebenbefund-Triage #1199) |
| TL7 | Testlücke | M25 `zustellungModell.ts` Trip `send_email` Standard ⇒ Editor zeigt E-Mail aus, Versand an | rot | offen: Testluecke ohne Behebungspaket (Nebenbefund-Triage #1199) |
| TL8 | Testlücke | M1 `ampelModell.ts:400` `enabled === true` → `!== false` ⇒ (macht den Editor Python-gleich, siehe E3) | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/e3_trip_altformat_metrics.test.ts::Zeichenkette und Objekt ohne enabled gelten als gewaehlt, enabled:false nicht (mit E3) |
| B-V1 | mittel | Ausblick: Zahl der Tageszeilen und Ausblick je Ort ungeprüft (bekannt #3083 H3, gegen den Auftrag echte Lücke) | gruen | tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_trip_ausblick_tageszeile_fehlt_scheitert |
| B-V2 | mittel | Zusatzblöcke Etappen-Kennzahlen und Vortag-Vergleich nie geprüft (bekannt #3083 H2, gegen den Auftrag echte Lücke) | gruen | tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_trip_zusatzbloecke_trotz_aus_scheitern |
| B-V3 | mittel | Orte-Vergleichstabelle: Roh/Einfach je Zeile ungeprüft (neu) | gruen | tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_orte_vergleich_falsche_darstellung_scheitert |
| B-V4 | niedrig–mittel | Orte-Klartext-Stundenverlauf: nur erste Stundenzeile je Ort gelesen (bekannt #3083 H3) | gruen | tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_orte_klartext_spalte_fehlt_ab_zeile_zwei_scheitert |
| B-V5 | mittel | Tagesfenster: Orte-Validator lehnt korrektes Fenster ab, Trip-Validator prüft es nicht (neu) | rot | Orte gruen: tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_orte_tagesfenster_wird_nicht_abgelehnt; Trip-Validator 06-22: rot, in Behebung |
| B-V6 | mittel | Kanal-Parität der Prüfwerkzeuge: kein Soll-Validator für Telegram, SMS, Premium-SMS (neu) | ausgelagert | #3090 (Soll-Validator Telegram/SMS/Premium-SMS) |
| B-V7 | niedrig | Ortsfolge der HTML-Abschnitte hängt am deutschen Wort „ORT“ (latent, Code-Lesung) | gruen | tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_orte_ortsabschnitte_html_vertauscht_scheitert (#3074) |
| B-V8 | niedrig | Testlücke: Sortierung der E-Mail-Kanal-Liste nach `bucket`/`order` ungetestet (neu) | gruen | tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_trip_kanal_liste_array_ungleich_order |
| B-P1 | mittel | Kompakt-Mail zeigt Etappen-Kennzahlen trotz `show_stage_stats = false` | geklaert | PO-Entscheidung #722 (Kompakt ignoriert Baustein-Schalter); tests/tdd/test_kompakt_mail_schalter_runde7.py::test_kompakt_gesperrte_schalter_aendern_die_mail_nicht |
| B-P2 | mittel | Kompakt-Mail zeigt 3-Tages-Ausblick trotz `show_outlook = false` | geklaert | PO-Entscheidung #722; tests/tdd/test_kompakt_mail_schalter_runde7.py::test_kompakt_gesperrte_schalter_aendern_die_mail_nicht |
| B-L1 | mittel | Trip-Telegram-Kurzübersicht ignoriert das Tagesfenster | gruen | tests/tdd/test_3047_runde7_telegram_tagesfenster.py::test_b_l1_fenster_10_19_kurzuebersicht_wie_sms |
| B-L2 | mittel | Orte-Telegram/SMS/Premium-SMS ohne Hinweis „Warnungen nicht abrufbar“ | gruen | tests/tdd/test_3047_runde7_orte_luecken.py::test_bl2_warnungen_nicht_abrufbar_telegram |
| B-L3 | niedrig | Orte-Telegram: Ampel-Grenzen ohne Wirkung, „Einfach“ zeigt Windwort | gruen | tests/tdd/test_3047_runde7_orte_luecken.py::test_bl3_einfach_folgt_ampel_grenzen |
| B-L4 | hoch | Orts-Vergleich „nie eingestellt“ / jede Neuanlage: Telegram und SMS zeigen alten Sechsersatz | gruen | tests/tdd/test_3047_runde7_orte_luecken.py::test_bl4_nie_eingestellt_telegram_folgt_mail |
| B-L5 | niedrig (Testlücke) | Validatoren: weitere ungeprüfte Einstellungen | rot | rot, in Behebung (p4b) |
| B-L6 | niedrig | Trip-Altformat ohne `order`: Validator lehnt die korrekte Mail ab | gruen | tests/tdd/test_einstellung_gleich_mail_validatoren.py::test_r7_trip_altformat_ohne_order_register_prioritaet |
| p8-1 | mittel | Orte-SMS: weitere Orte fielen als '+k Orte' weg, bevor die Zellen aller Orte gekuerzt waren | gruen | tests/tdd/test_3047_runde7_orte_sms_kuerzung.py::test_nie_eingestellt_alle_orte_sichtbar |
| p8-2 | niedrig | Sonnenstunden bauten Settings je Ort neu (Laufzeit) | gruen | tests/tdd/test_3047_runde7_sonnenstunden_settings.py::test_zwanzig_orte_ohne_settings_neubau_je_ort |
| p10-1 | mittel | Orte-Reiter: geloeschter Ort mitten in location_ids ergab Nummernluecke statt Folge der Mail | gruen | frontend/src/lib/components/compare/__tests__/p10_ortsfolge_reiter_gleich_mail.test.ts::geloeschter Ort mitten in location_ids: Reiter zeigt dieselben Orte, Nummern und Folge wie die Mail |
| p10-2 | niedrig | Orte-Reiter: nur geloeschte Orte zeigten eine leere Karte statt 'keine Orte' | gruen | frontend/src/lib/components/compare/__tests__/p10_ortsfolge_reiter_gleich_mail.test.ts::nur geloeschte Orte: Mail wird nicht versendet (orte_geloescht), Reiter zeigt „keine Orte" |
| p5c-1 | hoch | Anlegen aus Vorlage verlor abgeleitete Kind-Groessen (Nachgang p5a) | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/p5c_ableitung_hub_orte_ausgabe.test.ts::anlegen_allgemein_mail_spalten_wie_vor_p5a |
| p5c-2 | mittel | Hub-Uebersicht zaehlte anders als die Mail | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/p5c_ableitung_hub_orte_ausgabe.test.ts::trip_alarmzeile_a_nie_eingestellt |
| p5c-3 | mittel | Orte nie eingestellt: Abwahl entfernte mehr als die abgewaehlte Groesse | gruen | frontend/src/lib/components/shared/wetter-tab/__tests__/p5c_ableitung_hub_orte_ausgabe.test.ts::orte_a_uv_weg_uebrige_zeilen_bleiben |
| p2b-tags | mittel | Orte-Telegram: Warnblock mit rohen HTML-Tags/Entities (parse_mode=None) | gruen | tests/tdd/test_3047_runde7_orte_kanaele.py::test_orte_telegram_warnung_ohne_rohe_tags |
| R7-p11 | mittel | Neuanlage Trip/Orts-Vergleich: amtliche Warnungen 'beides an' (PO 2026-11-16, #1258 AC-4 abgeloest) | rot | rot, in Behebung (p11) |
| R7-p9 | niedrig | Uhrzeitabhaengige Tests (Ergebnis haengt von der Laufzeit-Uhrzeit ab) | rot | rot, in Behebung (p9) |
| R7-3091 | – | Tagesfenster in Ueberblick/Stundentabellen | ausgelagert | #3091 |
| R7-3092 | – | Go-PUT nimmt unbekannte Felder an | ausgelagert | #3092 |
| R7-2801 | – | Eigene Premium-SMS-Liste | ausgelagert | #2801 |
| R7-3065 | – | Ausgelagerte Editor-/Kanal-Zellen (siehe Matrix) | ausgelagert | #3065 |
| R7-3083 | – | Validator-Haertung H1-H3 (B-V1, B-V2, B-V4 in Runde 7 behoben) | gruen | siehe B-V1, B-V2, B-V4 |
