# Bereich orte_mail – Befunde (#3047 Runde 7)

Kette: rohes Preset-JSON → echter Loader → `send_one_compare_preset(..., mail_sink(plain_body))` → HTML + Klartext derselben Mail.
Zwei Probe-Arten (alle unter `/tmp/claude-0/-home-user-gregor-zwanzig/8fd24bbd-2477-52fc-adc3-e2681826a5f8/scratchpad/inventar/orte_mail/`):

- `test_probe_befunde.py`, `test_probe_dump.py`: Wetter-Naht wie im Bestand (`wetter_naht`, echte Subklasse der Engine).
- `test_probe_echt.py`: ECHTE `ComparisonEngine` mit Offline-Fixture-Provider; einzige Naht der Netzabruf amtlicher Warnungen (`comparison_engine.fetch_location_official_alerts`, zeichnet Aufrufe auf). Nur so sind Tagesfenster, Warn-Schalter und Zieltag (Abend) prüfbar – die Bestands-Naht ersetzt genau die Engine, die diese Einstellungen auswertet.

Befehl (aus dem Worktree): `uv run pytest -c pyproject.toml --rootdir . -p tests.conftest <Probe-Datei> -q`
Ergebnis heute: alle Probe-Fälle grün außer den Befund-Tests `test_befund_om1_*`, `test_befund_om3_*`, `test_amtliche_warnungen_schalter_und_erste_zeile[*-False]` (rot = Befund bestätigt). Bestand (`test_einstellung_gleich_mail_orte.py`, `test_compare_einstellung_auslieferung_kette.py`): grün, 5 xfail (#3065 p7 ×3, W11 Stundenverlauf ×2).

---

## B-OM-1 · mittel · Klartext ohne Hinweis „Amtliche Warnungen aktuell nicht abrufbar“

- **Soll:** HTML und Klartext derselben Mail tragen denselben Inhalt (Spec §1 „HTML und Klartext stammen aus derselben Mail“, ADR-0095 Kanal-Parität; Trip/Orte gleich). Der Trip-Klartext zeigt den Hinweis (`src/output/renderers/email/plain.py:86-87`).
- **Ist:** Ist ein Warndienst nicht erreichbar (`official_alerts_unavailable`), zeigt nur der HTML-Teil den Kasten (`src/output/renderers/email/compare_html.py:1872-1879`). `render_comparison_text` (`src/output/renderers/comparison.py:179-460`) kennt das Flag nicht. Wer den Klartext liest, liest „keine Warnung“ als „alles ruhig“ – genau davor warnt der Hinweis. DE und EN gleich.
- **Repro:** `test_probe_befunde.py::test_befund_om1_klartext_ohne_hinweis_warnungen_nicht_abrufbar`
- **Fix:** in `render_comparison_text` nach dem Kopf `if any_official_alerts_unavailable(locations): lines.append(render_official_alerts_unavailable_plain(lang=lang))` (geteilter Baustein `email/unavailable_hint.py`, kein neuer Text).
- **Einordnung:** innerhalb Spec/Konzept.

## B-OM-2 · mittel · Schalter „Amtliche Warnungen“ aus → HTML zeigt weiter die Zeile „Amtliche Warnungen – – –“

- **Soll:** Konzept §5 Reiter Wetter Punkt 7: Karte „Amtliche Warnungen (im Briefing und als Alarm …), ein Schalter“ (W20 + A1). Aus heißt: nicht im Briefing. WV6 (feste erste Zeile) gilt für den eingeschalteten Zustand.
- **Ist:** Abruf unterbleibt korrekt (0 Aufrufe der Netz-Naht), Klartext ohne Zeile – aber `_visible_metrics` (`compare_html.py:870-882`) setzt die Warnzeile IMMER als erste Zeile; bei abgeschaltetem Abruf stehen dort Striche. Das liest sich wie „keine amtliche Warnung“, obwohl nie gefragt wurde (ADR-0018-Muster: Ausfall nicht kaschieren). HTML und Klartext derselben Mail laufen auseinander.
- **Repro:** `test_probe_echt.py::test_amtliche_warnungen_schalter_und_erste_zeile[de-False]` / `[en-False]`
- **Fix:** `official_alerts_enabled` (über `resolve_compare_render_options`) bis `render_compare_html` reichen; bei `False` die `warn`-Zeile weglassen (auch `rowless_count`/Kopfzähler prüfen). Alternativ Zelltext „abgeschaltet“ statt „–“ – das wäre neuer Nutzertext (Katalog DE/EN).
- **Einordnung:** innerhalb Konzept; die Wahl „weglassen“ vs. „abgeschaltet anzeigen“ ist eine kleine Produktentscheidung (Empfehlung: weglassen, wie Klartext).

## B-OM-3 · mittel · K3b: Mail-Kopf zeigt zwei verschiedene Profile (Vorlage UND altes `profil`)

- **Soll:** Konzept §3.2 K3b und §5 („Ohne Oberfläche“), ADR-0108 Punkt 3: Der Name der Vorlage ersetzt das bisherige `profil`, auch im Mail-Kopf und beim Versand.
- **Ist:** Kopfzelle „Profil“ zeigt die Vorlage (`compare_html.py:1867`, `vorlage_label_schluessel`), aber die Eyebrow „ORTS-VERGLEICH · WANDERN“ (`compare_html.py:1461`, `sig.eyebrow`) und der Abo-Fuß „3 Orte · Profil WANDERN“ (`compare_html.py:1688`) kommen aus dem alten `profil` (`scheduler_dispatch_service.py:932-933`). Beispiel `preset_name=alpen-trekking`, `profil=wandern`: „ORTS-VERGLEICH · WANDERN … Profil Alpen-Trekking … Profil WANDERN“. Mit `profil=ALLGEMEIN` (Bestand) steht „WETTER-BRIEFING“ neben „Allgemein“. Der Klartext-Kopf nennt weder Vorlage noch Profil. Auch die Engine-Bewertung (`profile=`) hängt weiter am alten `profil`.
- **Repro:** `test_probe_befunde.py::test_befund_om3_k3b_kopf_und_fuss_zeigen_vorlage[preset_name|ampel]`; Sichtung `out/vorlage.de.html`.
- **Fix:** Eyebrow und Fuß aus derselben Vorlage-Auflösung (`resolve_ampel(preset)["template"]`) wie die Kopfzelle; Klartext-Kopf um die Zeile „Vorlage: …“ ergänzen (Katalog DE/EN).
- **Einordnung:** innerhalb Konzept; Scope liegt bei Scheibe S4 #2796 (offen, ADR-0108 noch „Vorgeschlagen“). Vorschlag: dort als Akzeptanzpunkt aufnehmen statt eigenes Issue.

## B-OM-4 · niedrig · Klärung: 3-Tages-Ausblick „Erscheint im Morgen/Abend“ für Orte

- **Soll (uneindeutig):** Konzept §5 Punkt 8, Unterpunkt 3-Tages-Ausblick: „Erscheint im: Morgen-Briefing · Abend-Briefing … Vorbelegung: nur abends“ – ohne Kontextangabe, in der für Trip und Orte geteilten Karte. §3.2 V12 (Quelle dieses Schalters) ist aber Kontext „Trip“.
- **Ist:** Orte haben kein Feld; der Ausblick steht in Morgen- und Abend-Briefing (`report_config_resolver.py:257ff`, Go `internal/model/compare_preset.go` ohne Feld). Kein Fehlverhalten, aber Editor-Karte und Code-Teilungsregel (EIN Code für beide Kontexte) lassen offen, ob der Schalter bei Orten erscheinen soll.
- **Repro:** —(Feldsuche), `test_probe_echt.py::test_morgen_abend` zeigt Ausblick in beiden.
- **Fix:** keiner bis Klärung; dann ggf. Feld `outlook_reports` analog Trip.
- **Einordnung:** Zielkonflikt Konzept-Wortlaut §5.8 vs. V12 → PO-Frage.

## B-OM-5 · niedrig · Stundenverlauf ohne Roh/Einfach (W11)

- **Soll:** Konzept §3.2 W11: Umschalter Roh/Einfach „in jeder Liste: …, Vergleichstabelle, Stundenverlauf und 3-Tages-Ausblick. Gilt für Trip und Orte gleich.“
- **Ist:** kein Feld (Python, Go, Frontend), Renderer immer Roh. Bestand führt es als `offen_feature` (`fallliste_orte.json` O-SV-H/K-DARST, xfail strict in `test_einstellung_gleich_mail_orte.py::test_w11_darstellung_je_zeile`) mit Verweis nur „#3047 Phase 3“ – kein eigenes Issue.
- **Fix:** Feld `hourly_metric_formats` (analog `outlook_metric_formats`) + `_visible_hour_metrics`/Klartext-Stundenzeile; Editor-Segment.
- **Einordnung:** Feature innerhalb Konzept; Vorschlag: eigenes Issue anlegen, damit der Verweis nicht nur auf eine Phase zeigt.

## B-OM-6 · niedrig · Katalog-Lücke: fünf Einstellungen stehen nicht im #3047-Prüfkatalog

Alle 18 Mutationen werden von irgendeinem Test gefangen (breite Suite, 206 Compare-Testdateien, `orte_mail/suite.txt`). Fünf davon aber NICHT vom Prüfkatalog (`test_einstellung_gleich_mail_orte.py` + `test_compare_einstellung_auslieferung_kette.py`), sondern nur von älteren Einzeltests, die nicht über die fertige Mail prüfen bzw. nur die Durchreichung an die Engine:

- M1 Tagesfenster ignoriert → nur `test_compare_dispatch_fixed_window.py`, `test_compare_alert_day_window.py`.
- M2 Warn-Schalter ignoriert → nur `test_issue_1040_alerts_toggle.py` (Durchreichung `official_alerts_enabled=False` an die Engine, nicht die Mail).
- M12/M13 Kopfdatum = Erstellungstag statt Zieltag → nur `test_vergleichsmail_kopfzeile_wochentag_deutsch.py`, Golden `test_metric_format_slice5_comparison.py`, `test_compare_html_email.py::test_ac5_*`; kein Abend-Briefing-Fall (Zieltag ≠ Erstellungstag) über die Kette.
- M15 Warnzeile Klartext immer deutsch → nur `tests/test_amtliche_warnungen_zweisprachig.py`; auch meine Probe fängt das nicht (prüft nur das Warnsymbol).
- Zusätzlich M5 (K3b-Kopfzelle) und M6 (HTML-Hinweis „nicht abrufbar“) fängt im Katalog nur der byte-genaue Golden, kein gezielter Fall.

Ursache: die Orte-Ketten-Tests ersetzen `ComparisonEngine` vollständig (`tests/helpers/einstellung_gleich_mail_orte.py::wetter_naht`, `tests/tdd/_compare_kette_fixtures.py::engine_naht`) – genau dort wirken Tagesfenster, Warn-Schalter und Zieltag – und die Naht setzt `created_at == target_date`.
- **Fix:** `test_probe_echt.py` (echte Engine + Offline-Fixture-Provider, Naht nur am Warndienst) als Muster in den Katalog übernehmen; Fallliste um Tagesfenster (inkl. über Mitternacht), Warn-Schalter an/aus, Abend-Briefing (Zieltag morgen), EN-Warnwortlaut, K3b-Kopf ergänzen.
- **Einordnung:** innerhalb Spec (Ziel: jede Hub-Einstellung über den echten Weg bis zur Mail).

## Nebenbeobachtungen (kein eigener Befund)

- Vergleichstabelle: Regenwahrscheinlichkeit hat keine Einfach-Form (bleibt Zahl, #3039 AC-8), im Ausblick schon. W11 sagt „je Zeile und Liste“; ob der Editor den Umschalter für diese Zeile anbietet, gehört zum Bereich Editor.
- EN-Reste „ORT“, „Risk“-Legende: ausgelagert #3074.
- Altbestand ohne `active_metrics`: Übersicht ~25 Zeilen mit vielen „-“, Stundenverlauf 9, Ausblick 7 Spalten – eingefroren (Golden), O4 im Editor-Paket.

---

## Mutations-Gegenprobe (18 eigene Mutationen, String-Ersetzung mit Sicherung in `orte_mail/backup/`, danach zurückkopiert; `git status` danach leer)

Skript: `orte_mail/mutationen.py` (Kern: die zwei Bestandsdateien + beide Probe-Dateien; `BREIT=1`: 206 Compare-Testdateien für Überlebende). Rohdaten: `orte_mail/mutationen_ergebnis.json`, `orte_mail/mutationen_breit.json`.

| Nr | Datei | Ersetzung (kurz) | Gefangen Katalog (Bestand) | Gefangen breite Suite | Gefangen eigene Probe |
|---|---|---|---|---|---|
| 1 | `src/services/report_config_resolver.py` | `resolve_compare_time_window`: `preset.get("day_window_*")` → `None, None` | nein | ja – `test_compare_dispatch_fixed_window.py::…day_window`, `test_compare_alert_day_window.py::test_f001_*` | ja – `test_probe_echt.py::test_tagesfenster*` |
| 2 | `src/services/scheduler_dispatch_service.py` | `official_alerts_enabled=preset.get(...)` → `True` | nein | ja – `test_issue_1040_alerts_toggle.py::…passes_false_to_engine` | ja – `test_zwei_nutzer_tagesfenster_und_warnschalter` |
| 3 | `email/compare_html.py` | `warn_row + ordered` → `ordered + warn_row` | ja – `test_wv6_amtliche_warnung_zuerst_html`, Golden | ja | ja |
| 4 | `comparison.py` | Klartext-Warnzeile `lines.append(⚠️ …)` → `pass` | ja – `test_wv6_amtliche_warnung_zuerst_klartext` | ja | ja |
| 5 | `email/compare_html.py` | Kopfzelle `profil_label = t(vorlage…)` → `sig.eyebrow` | ja – nur Golden `test_ac11_altbestand_golden` | ja | nicht messbar (Befund-Test B-OM-3 ist schon rot) |
| 6 | `email/compare_html.py` | Hinweis „nicht abrufbar“ `if any_…` → `if False` | ja – nur Golden | ja | nein |
| 7 | `report_config_resolver.py` | `hourly_enabled = preset.get(...)` → `True` | ja – `test_ac6_stundenverlauf_aus_und_leer[hourly_enabled_aus]`, `test_vergleichs_mail_traegt_kennung_…` | ja | nein |
| 8 | `report_config_resolver.py` | `outlook_enabled = preset.get(...)` → `True` | ja – `test_ac7_ausblick_aus_und_leer[outlook_enabled_aus]` | ja | nein |
| 9 | `compare_outlook_metric_ids.py` | `resolve_compare_outlook_formats` → `return None` | ja – `test_ac8_ausblick_roh_einfach`, `test_ausblick_paarweise[O-AB-P02]` | ja | ja |
| 10 | `comparison.py` | Klartext `friendly=bool(metric_formats…)` → `False` | ja – `test_vergleichstabelle_paarweise[O-VT-P13/P14]` | ja | ja |
| 11 | `email/compare_html.py` | HTML `einfach_fn` nie | ja – `test_vergleichstabelle_paarweise[O-VT-P12/P16]` | ja | ja |
| 12 | `comparison.py` | Klartext `target_date = result.created_at.date()` | nein | ja – `test_vergleichsmail_kopfzeile_wochentag_deutsch.py`, `test_metric_format_slice5_comparison.py` (Golden) | ja – `test_morgen_abend[True]` |
| 13 | `email/compare_html.py` | HTML-Kopf Datum aus `created_at` | nein | ja – `test_compare_html_email.py::…test_ac5_html_behaelt_datum_und_wochentag` | ja – `test_morgen_abend[True]` |
| 14 | `email/compare_html.py` | `location_render_order` → alphabetisch | ja – 71 Tests, u. a. `test_reihenfolge_der_kanal_liste_bestimmt_zellen_und_kappung` | ja | ja |
| 15 | `comparison.py` | Klartext-Warnzeile `lang="de"` fest | nein | ja – `tests/test_amtliche_warnungen_zweisprachig.py` (2 Tests) | nein |
| 16 | `report_config_resolver.py` | Ausblick nicht gegen Grundauswahl geschnitten (`global_metrics` → `None`) | ja – 19 Tests, u. a. `test_3061_*` | ja | nein |
| 17 | `comparison.py` | Klartext-Ausblick `metrics=outlook_metrics` → `None` | ja – 15 Tests, u. a. `test_ac10_grundauswahl_ausblick` | ja | ja |
| 18 | `scheduler_dispatch_service.py` | `order_locations_by_ids` → Cache-Reihenfolge | ja – 71 Tests | ja | ja |

Summe: 18 Mutationen, 18 von irgendeinem Test gefangen; 13 vom #3047-Katalog; 5 (M1, M2, M12, M13, M15) nur außerhalb des Katalogs → B-OM-6. Mutationen in `compare_hourly_metric_ids.py` und `channel_list_resolver.py` bewusst nicht gesetzt (Dateien in PR #3087).
