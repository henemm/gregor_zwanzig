# Kontext feat-3222: Windrichtung bewerten (Gegenwind / unerwünschte Sektoren)

Modus: NEU (Erweiterung der Profil-Ampel um eine zirkuläre Metrik). Stand: Analyse Phase 10/20, kein Code.
Hinweis: `wind_direction_deg` = Richtung, AUS der der Wind kommt (0=N, 90=O; `src/app/models.py:113`).

## A. Ampel-Modell (Ist)

- Datenform je Metrik: `{enabled, lower{red,orange,yellow}, upper{yellow,orange,red}, alarm_ab}` plus `thunder{mittel,hoch}`
  und `template`; Ablage `display_config.ampel` (Trip: `UnifiedWeatherDisplayConfig`, Ortsvergleich: `ComparePreset.display_config`
  Dict). Go reicht `Ampel map[string]interface{}` durch (`internal/model/metric_preset.go:63`, Trip/Compare analog), prüft nur
  Form in `validateAmpel`/`ampelMetrikGueltig` (`internal/handler/ampel.go:50-121`): unbekannte Schlüssel in `lower`/`upper`
  sind nicht geprüft, aber `ampelSeite` erwartet Zahlen; **ein neues Feld neben `lower`/`upper` (z. B. `sektoren`) wird von Go
  heute weder abgelehnt noch validiert** (Map-Durchreichung) -> trotzdem Validierung ergänzen (Python+Go gleiche Regeln, Spec #2792 §1).
- Vorlagen: `src/app/ampel_templates.py` (`_ZEILEN`, Tupel `(id, im_briefing, unten, oben, alarm_ab)`); alle 7 Vorlagen haben
  `("wind_direction", …, X, X, NIE)` (Z. 33/55/77/99/121/143/165; `radtour` Z. 121 mit `im_briefing=True`, `wintersport`/`skitouren`
  Z. 33ff-Block ohne). Fest verdrahtetes „X" = offen.
- Auflösung: `app/ampel.py` `resolve_ampel` (Z. 192) = Vorlage + Abo-Abweichung (`_verschmelzen` Z. 175 kopiert NUR
  `lower/upper/enabled/alarm_ab` -> **neue Felder gehen hier verloren, wenn nicht ergänzt**). Fallback-Kette Abo -> `ampel.template` ->
  `preset_name`/`profil` -> „allgemein" (Z. 143-152).
- Bewertung: `output/metric_format.py:154` `severity_from_thresholds` = ausschließlich skalar: `Wert >= oben-Grenze` bzw. `Wert < unten-Grenze`,
  schärfere Seite gewinnt. **Für zirkuläre/nicht-skalare Größen gibt es heute keinen Pfad.** Einzige Nicht-Skalar-Ausnahme: Gewitter
  (`thunder_color`, `app/ampel.py:285`, eigener Block `ampel.thunder`, seite `"stufe"` in `ampel_alarm.py:122`).
- Leser-Begrenzung: `AMPEL_LESER` (`app/ampel.py:217`) = 9 Metriken; `schwellen_aus_ampel` (Z. 238) liefert für alles andere `{}`,
  `hat_ampel()` (Z. 223) steuert Färbung in `narrow.py:623`, `compare_html.py:477` (`hat_ampel`), `helpers.py:741/758` (`severity_for`).
  `wind_direction` ist NICHT in `AMPEL_LESER` -> wird nie gefärbt (Befund des Issues bestätigt).
- Specs/ADR: `docs/specs/modules/feat_2792_s1_profil_ampel.md`, `feat_2793_s2_alarm_stufenwechsel.md`, ADR-0106 (Profil-Ampel ist die einzige Bewertung;
  neue Bewertungslogik außerhalb der Ampel wäre ADR-Verstoß), ADR-0108 (Vorlage/Tempo getrennt).
- Frontend-Spiegel: `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` (`MetrikEigenschaften.allowed_sides`, Katalog-Ausgabe
  `src/app/metric_catalog.py:1347` / `api/routers/config.py:178`), Parität Abweichungszahl über `tests/fixtures/ampel_deviation_cases.json`
  (`deviation_count`, `app/ampel.py:261`; muss neue Felder mitzählen).

## B. Reiter Wetter (Frontend)

- Gemeinsame Hülle `frontend/src/lib/components/shared/WetterTab.svelte` (12 Zeilen) -> `organisms/wetter-tab/WetterTabInhalt.svelte`.
  Metrik-Zeile = `organisms/wetter-tab/MetrikZeile.svelte` (212 Z.): `AmpelLeiste.svelte` (Leiste+Grenzzahlen), `GrenzenEditor.svelte`
  (Dialog „Grenzen ändern"), `AlarmAbKopf.svelte` („Alarm ab"). Zeilenvariante je `eig.allowed_sides` (`level` = Gewitter, sonst oben/unten/beide).
  Zustand/Speicherung: `shared/wetter-tab/ampelModell.ts`, `ampelSchreiben.ts`, `wetterTabSpeicherung.ts`,
  `wertebereicheVergleichSpeicherung.ts`. Trip UND Ortsvergleich nutzen dieselben Dateien (`context="route"|"vergleich"`); neue
  Komponente mit Pendant wäre Verstoß (#1170) -> Richtungs-Baustein EINMAL bauen.
- Passender Baustein (ADR-0112: Oberflächen nur aus Design-System-Bausteinen, atoms/molecules/organisms): neue Molekül-Komponente
  `molecules/RichtungsWahl.svelte` (8 Sektoren als Chip-/Toggle-Kreis oder `ChipLeiste.svelte`-Reihe, jeder Sektor ein Toggle aus
  `atoms/Btn`/`Switch`), eingebettet in `GrenzenEditor` (Sektoren) bzw. als Variante `allowed_sides="sektor"` in `MetrikZeile`; Alarm-ab bleibt
  `AlarmAbKopf`. Kein Roh-HTML-Chip an anderer Stelle (Bausteine-Wächter, `tests/test_adr_0112_bausteine_regel_doku.py`, `tests/test_alarm_bausteine_nutzersprache.py`).
- Mockup-Pflicht: JA. ADR-0112 Z. 34: Elementliste `docs/context/einstellungen_neu/elementliste.json` + Prüf-Agent `mockup-bildpruefer`;
  „fertig" = Elementliste lückenlos. Windrichtung kommt dort heute nur als Chip „+ Windrichtung" vor (`wetter.nicht_im_briefing.hinzufuegen`,
  Zeilen 164/1027 Trip, 1592/2298 Orte). Neue Elemente (Sektor-Wahl, „ab {n} km/h", Hinweis „Gegenwind automatisch") brauchen Mockup-Bild +
  Elementlisten-Einträge in Trip UND Orte (Normal- und Lücken-Zustand) + i18n-Schlüssel DE/EN (`i18n_konventionen.md`).

## C. Bewegungsrichtung im Trip

- Keine Peilung/Bearing im Code: `grep bearing|heading` findet in `src/` nur Render-Texte; `utils/geo.py` hat nur `haversine_km` (Z. 19),
  `point_to_segment_m` (Z. 32), `degrees_to_compass` (Z. 60); `weather_metrics.py:273` dupliziert `degrees_to_compass`. **Neu: `bearing_deg(lat1,lon1,lat2,lon2)`** in `utils/geo.py`.
- Geometrie je Segment: `TripSegment` (`app/models.py:428`) hat `start_point`/`end_point` als `GPXPoint(lat, lon, elevation_m, distance_from_start_km)`
  (Z. 381), dazu `start_time/end_time` (UTC), `distance_km`. Segment-Peilung = Luftlinie start->end; grob bei Schleifen/Serpentinen/Segmenten ~2 h (Rad:
  länger). Feiner: GPX-Track (`GPXTrack.points`, Z. 399) nutzen und Peilung je Stunde zwischen den zum Stundenfenster gehörenden
  Track-Punkten (über `distance_from_start_km` + Tempo interpolieren, `core/naismith.py`). Empfehlung: MVP Segment-Peilung, Stunden-Feinheit später.
- Tempo/Fortbewegung (#3196): `Trip.tempo = {"fortbewegung": "fuss|rad|mtb|ski", "grundtempo_kmh"}` (`app/trip.py:206-208`, Go `internal/model/trip.go:133-136`),
  Altdaten aus `activity` abgeleitet (`core/naismith.py:48-69`). Schalter für „Rückenwind/Gegenwind relevant" ist also `tempo.fortbewegung in (rad, mtb)`;
  Vorlage `radtour` (`ampel_templates.py:113`) ist davon getrennt (ADR-0108: Vorlage ≠ Tempo) -> Aktivierung pro Ampel-Eintrag, nicht über Fortbewegung koppeln.
- Wetterwert: nur Segment-Aggregat `SegmentWeatherSummary.wind_direction_avg_deg` (`models.py:508`, int, Mittel; kein zirkuläres Mittel garantiert!)
  und stündlich `wind_direction_deg` (`models.py:113`). Für Gegenwind besser stündlich (Windstärke+Richtung je Stunde) als Segment-Mittel; Mittelung
  von Winkeln muss vektoriell erfolgen (Prüfen: Aggregator in `weather_extractor.py`/`segment_weather.py`).
- Ortsvergleich: Orte sind Punkte (`SavedLocation` lat/lon, `app/user.py:49-60`), KEINE Bewegungsrichtung -> nur absolute Sektoren möglich
  (Konsistenz mit Anforderung 2). Gegenwind dort nicht definiert.

## D. Renderer & Tokens

- Katalog: `metric_catalog.py:420-433` `wind_direction` (`col_key wind_dir`, `col_label WDir`, `compact_label WD`, `sms_code WD`), Ausgabe `WD:` (Doppelpunkt
  zum Symbol, Z. 882; `sms_format.md` §3.2a Z. 267-269, 828). Wert = dominanter 8-Sektor N/NO/O/SO/S/SW/W/NW, Tageswert ohne Stunde, Lücke `WD:?`/`WD:-`.
- E-Mail: Spalte WDir bzw. mit Wind verschmolzen (`email/helpers.py:66` `should_merge_wind_dir`, Compare `compare_html.py:1115`);
  Telegram: Roh `WD 250°`, Einfach `WD W` (`telegram_format.md:59`); Premium-SMS/SMS: `WD:NW` bzw. Kurzform `NW` im Ad-hoc-Verlauf
  (`sms_format.md:616`, #2207); Kanal-Layout `channel_layout.py:67,145`; Kompakt `compact_summary.py:555`.
- Färbung: Zellfarbe nur wenn `hat_ampel(metric_id)` (`narrow.py:623`, `compare_html.py:477`) und `severity_for` (`helpers.py:741/758`,
  `compare_html.py:117-154`). Für die Richtung bräuchte es eine neue Funktion `richtung_stufe(ampel, wert_deg, wind_kmh, fahrt_peilung)` und Einhängen
  an denselben drei Stellen (Briefing-Zelle, Compare-Zelle, Kachel/`schlimmster_index`).
- Protokoll-Token-Regeln: `sms_code`/`compact_label` nie übersetzen, neue Nutzertexte nur Katalog (CLAUDE.md, ADR-0104). Himmelsrichtungs-Kürzel
  (N/NO/O/SO/S/SW/W/NW) sind deutsche Tokens (EN nutzt E statt O? -> Prüfen in `degrees_to_compass`/Katalog; **nicht ändern**).
- Ausdruck von Gegenwind ohne Tokenbruch: (a) `WD:` unverändert lassen und die Stärke-Warnfarbe/`@h`-Stundenmarke wie bei Ampel-Tokens nutzen
  (`narrow.py:623`: `@h` nur bei gelb+); (b) Zusatzzeichen im bestehenden Wert, z. B. `WD:NW-` (Gegen) / `WD:NW+` (Rücken) wäre neues Token-Muster
  und braucht Format-Spec-Änderung; (c) nur Kanal-Parität über Farbe in E-Mail + Wortlabel in Telegram („Gegenwind"/„Rückenwind", Katalogtext), in
  SMS/Premium nur `WD:{Sektor}` plus Alarmtext. Empfehlung: SMS bleibt `WD:SW`; die Bewertung steckt in Alarm-/Warntext und Hervorhebungsmarke `@h`
  (ADR-0095: gleicher Inhalt, nicht gleiche Form; Spec muss dies als Ausdrucksform festlegen).

## E. Alarme

- Alarm-Kern: `services/ampel_alarm.py`. `AMPEL_FELDER` (Z. 59-75) listet 9 alarmfähige Felder mit `field` (Aggregat-Attribut), Seite
  `oben|unten|stufe`; `alarmfaehige_felder` (Z. 92) lässt nur Felder zu, deren `alarm_ab != never` und die aktiv sind; Ereignis: Farbe alt/neu aus
  `_farbe` (Z. 114) -> `_art` (Verschärfung/Entwarnung/Sprung, Z. 130). Daten: `SegmentWeatherSummary`-Felder.
- Richtungsbedingung einbaubar: JA, als zusätzliche Seite `seite="richtung"` mit eigenem `AmpelFeld`; `_farbe` bräuchte beim Richtungsfeld
  Wind+Richtung+Peilung gemeinsam (zwei Aggregate!). Sauberer: abgeleitetes Aggregat-Feld `gegenwind_kmh` bzw. `wind_unerwuenscht_kmh` (Komponente der
  Windstärke gegen die Fahrtrichtung bzw. Wind aus markiertem Sektor, sonst 0) in `SegmentWeatherSummary` und dann normale skalare Schwellen
  (`yellow/orange/red` in km/h) -> **kein Eingriff in `severity_from_thresholds`, `_art`, Sprung-Logik, Dedup**. Entspricht Anforderung 3 (Stärke
  zählt, ohne Stärke keine Farbe) automatisch.
- Aktivierung: `_aktiv` (Z. 78) braucht `AlertMetric`-Zuordnung oder `aktivierung=None` (dann `display_config.is_metric_enabled`); `alert_preset._PRESET_TABLE`
  liefert Sprung-Schwelle (`_sprung`, Z. 40) -> neuer Eintrag nötig oder `sprung=None` (wie Sicht/Gewitter, Z. 72/74).
- Alle Kanäle: Alarmversand läuft über geteilte Kanal-Auflösung (#1533/#1701); ein weiteres Ampelfeld erbt das. Radar/Warnungen unberührt.

## F. Wind-Exposition (F7)

- `services/wind_exposition.py`: erkennt Grate/Pässe aus Höhenprofil (`detect_exposed_sections`/`detect_exposed_from_segments`),
  `ExposedSection(start_km,end_km,max_elevation_m,exposition_type)`; Verbraucher `risk_engine.py:102-104,201ff` (Regel 9: Windrisiko eskalieren) und
  `trip_report_scheduler.py:1746-1751`. Arbeitet auf Höhe/km, nicht auf Richtung; speist das Risiko-System (`risk_engine`), nicht die Profil-Ampel.
- Kollision: keine technische (andere Eingabe, anderer Ausgabeweg). Nutzbar: die km-Fenster/Geometrie-Auflösung (`distance_from_start_km`) und
  die Grenzfall-Logik für Segmentzuordnung. Nicht mitnutzen: Eskalationsregel (würde Stärke-Schwelle verändern). Fachlich Doppelzählung möglich
  (Gegenwind auf Grat) -> Priorität: höchste Stufe gewinnt, nicht addieren.

## Risiken / Seiteneffekte

1. `_verschmelzen`/`deviation_count`/Go-Validierung/TS-Spiegel müssen gleichzeitig um das neue Feld erweitert werden (Parität-Ratsche, Fixture).
2. Bestandsdaten: Read-Modify-Write mit Merge (#102), neues Feld ist additiv (`omitempty`), Vorlagen-Default = aus -> Bestand unverändert.
3. Windrichtung MEHRDEUTIG: „aus" vs. „nach"; Gegenwind = Wind kommt aus Fahrtrichtung. Test mit Beispielen N/S/O/W und Wrap-around 359°/1°.
4. Segment-Mittel von Richtung nicht vektoriell -> Fehlbewertung bei wechselnden Winden; Stundenbasis oder vektorielles Mittel nötig.
5. Peilung über Luftlinie bei Rundkurs-Segmenten = 0 Länge/instabil -> bei < ~300 m Distanz keine Richtung (Neutral, keine Färbung).
6. Premium-SMS-Länge (160): kein zusätzlicher Token im MVP, Zeichenbudget unberührt.
7. Mail-Validatoren/Renderer-Gate (`docs/reference/mail_validators.md`): Änderung am Mail-Inhalt -> Modus-Matrix + Briefing-Validator gegen Staging-Mail.
8. Spec muss `## Acceptance Criteria` (`**AC-n:** Given/When/Then`, deutsch) tragen.

## G. Empfehlung: Zuschnitt in Scheiben (je <= 250 LoC Code, Tests/Doku zählen nicht)

Kernidee: Richtungsbewertung wird zu einer SKALAREN Größe „Windkomponente" reduziert (Stärke * Richtungsfaktor); danach läuft alles über den
bestehenden Ampel-/Alarm-/Renderer-Pfad (ADR-0106 bleibt gültig, Paritäts- und Alarmlogik unberührt).

- **S1 Fachkern (Python, ~150 LoC):** `bearing_deg`, `ist_gegenwind`-Komponente, 8-Sektor-Zuordnung, vektorielles Winkelmittel (`utils/geo.py` + neues
  `services/windrichtung.py`); Modell: `ampel.metrics.wind_direction.{modus: "gegenwind"|"sektoren"|"aus", sektoren: [..], min_kmh}`; `validate_ampel`,
  `_verschmelzen`, `deviation_count`, Go `ampelMetrikGueltig`, Vorlage `radtour` (Modus gegenwind, Gelb/Orange/Rot als Gegenwind-km/h, z. B. 10/20/30).
- **S2 Aggregat + Färbung E-Mail (Python, ~200 LoC):** abgeleitetes Feld `wind_unerwuenscht_kmh` je Segment/Ort (Trip: Peilung aus Segment; Orte: Sektoren);
  `AMPEL_LESER` um `wind_direction` erweitern, `severity`-Pfad für die Zelle WDir (Briefing + Compare) und `schlimmster_index`; Tests Mail-Matrix + Validator.
- **S3 Alarm + Kanalparität (Python, ~150 LoC):** `AmpelFeld("wind_direction", "wind_unerwuenscht_kmh", "oben", …)`, `_PRESET_TABLE`-Eintrag,
  Telegram-Wortlabel („Gegenwind"/„Rückenwind"), SMS/Premium: `WD:` + `@h`-Marke bei gelb+ (`narrow.py`-Regel), Alarmtext in allen Kanälen; Formatdoku-Eintrag.
- **S4 Frontend Reiter Wetter (~220 LoC):** `molecules/RichtungsWahl.svelte`, Variante in `MetrikZeile`/`GrenzenEditor`, `ampelModell.ts`-Spiegel,
  i18n DE/EN, Mockup + Elementliste (Trip + Orte), Bausteine-Wächter grün. Trip: Modus „Gegenwind automatisch"; Orte: Sektor-Wahl + Mindeststärke; Trip-Sektoren optional (selber Baustein).
- Reihenfolge S1 -> S2 -> S3 -> S4; S1+S2 allein liefern bereits E-Mail-Wirkung für `radtour` (per Vorlage), S4 macht es konfigurierbar. Mockup (S4) vorab
  per PO-Freigabe klären, damit Spec nicht blockiert.

### Technikentscheidungen (Tech Lead, nicht an PO)

- Skalarreduktion statt Sonderlogik in `severity_from_thresholds` (Begründung: ADR-0106 und Alarm-Dedup/Sprung bleiben unverändert).
- Segment-Peilung per Luftlinie start->end im MVP; Stundenfeinheit nur wenn Segment > 3 h oder Peilung variiert stark (spätere Scheibe).
- Gegenwind-Aktivierung pro Ampel-Eintrag, nicht automatisch aus `fortbewegung` (ADR-0108: Vorlage getrennt von Tempo); Vorlage `radtour` setzt Default.
- Grat-Exposition (F7) bleibt separat, höchste Stufe gewinnt.
- SMS bleibt `WD:{Sektor}` (kein neues Protokoll-Token im MVP), Bewertung über `@h` + Alarmtext.

### Echte Produktentscheidungen für den PO (max. 4)

1. **Rückenwind/Seitenwind mitzeigen?** Empfehlung: nur Gegenwind bewerten (rot/gelb), Rückenwind/Seitenwind neutral anzeigen; Seitenwind
   (Windkante beim Rad) später, weil ein zweiter Grenzwertsatz Mehraufwand und Mockup-Fläche braucht.
2. **Gegenwind-Schwellen Rad (Default):** Empfehlung gelb 10 / orange 20 / rot 30 km/h Gegenwindkomponente, Alarm ab Orange (analog `radtour` wind 20/30/45).
3. **Sektor-Wahl im Trip anbieten?** Empfehlung: ja, aber nachrangig (S4, hinter „Gegenwind automatisch"), selber Baustein wie Ortsvergleich; Wirkung dort ebenfalls nur mit Mindeststärke (Default 15 km/h).
4. **Darstellung in SMS/Premium-SMS:** Empfehlung: nur Sektorkürzel `WD:SW` plus `@h`-Marke bei Warnung und Alarmtext „Gegenwind"; kein neues Zeichenmuster (Platz 160 Zeichen, Protokoll-Stabilität).
