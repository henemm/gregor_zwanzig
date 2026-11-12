# Context: feature-2794-s3a-teil4b (S3a Teil-PR 4b)

## Request Summary
Letzter Schritt von S3a (#2794, Epic #2791): Übersicht, Listen-Sprünge, Menü-Wortlaut, Hilfe-/Onboarding-Texte, Glossar und ein Wächter gegen alte Reiternamen auf die neuen Reiter Übersicht · Etappen/Orte · Wetter · Zustellung nachziehen; danach Fresh-Eyes-Abgleich gegen Mockup Fassung 3 und Soll/Ist-Bild an den PO. ACs: AC-32, AC-33, AC-35, AC-48, AC-49, AC-50, AC-34 (Querschnitt).

Spec (bereits freigegeben, gemeinsam mit 4a): `docs/specs/modules/feat_2794_s3a_teil4_entfernen.md` (Abschnitte „Schritt 4b“, „Schritt 4b: Reihenfolge“). Analyse von Teil 4 (gilt weiter): `docs/context/feature-2794-s3a-teil4.md`. 4a ist live (59ec6f5d8, PR #2945, Prod-Selftest Exit 0).

## Related Files (Ist-Stand auf origin/main 59ec6f5d8)
| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts` | Z.133 `tripWetterAlarmAktiv()` kennt `alarm_ab` noch nicht (nur alert_preset, metric_alert_levels, alert_rules, alert_on_changes); Z.253-260 `wertebereicheKarte()` mit Eyebrow `aktionen.reiter.wertebereiche` (U3) |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | Z.150 `ReportLine` mit `trip.uebersicht.bei_delta` („bei Δ“) → U4 Text über „Alarm ab“; Kommentare/Texte „Wetter-Metriken“ Z.10/24/116 |
| `frontend/src/lib/components/alerts-tab/alarmAbAnzeige.ts` | Quelle für den „Alarm ab“-Text (U4) |
| `frontend/src/lib/types.ts` Z.368-382 | Profil-Ampel mit `alarm_ab?: AmpelAlarmAb` (fehlt = Vorlage „allgemein“) |
| `frontend/src/lib/components/shared/subscriptionActions.ts` Z.18-19, 40-41, 74-78 | Menü-Aktionen `alarms`/`weather` (Schlüssel `aktionen.alarms`/`aktionen.weather`) |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` Z.13-14 | DE „Alarme“ / „Wetter-Metriken“ → „Wetter“ (AC-48) |
| Weitere Verwender `aktionen.weather/alarms` | `WeatherConfigDialog.svelte`, `trip-detail/__tests__/trip_hub_sprache.test.ts`, `f9KatalogAnker.ts`, `shared/__tests__/s3a2794_reiter_definition.test.ts` (Schlüssel bleiben) |
| `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `routes/+page.svelte` | Listen- und Startseiten-Sprünge (Ziel-Reiter prüfen) |
| `shared/infoboxKeys.ts`, `lib/utils/cockpitHelpers568.ts`, `routes/hilfe/+page.svelte` | Info-Abschnitte, Startklar-Checkliste, Hilfe |
| `docs/reference/i18n_glossar.md` | Z.24 Zeile „Wertebereiche … Reiter-Name“ entfällt; Wetter etc. ab Z.185-195 schon da |
| `.claude/hooks/pendant_gate.py` | AC-35, läuft zu Beginn von 4b |
| `frontend/src/lib/i18n/__tests__/keine_alten_reiternamen.test.ts` | NEU (AC-49), existiert noch nicht |
| Golden `tests/golden/f3_home_listen/cockpit_planung` u. a. | Neuschrieb per `GZ_GOLDEN_SCHREIBEN` |

## Existing Patterns
- Texte nur über Katalog DE/EN (ADR-0104), Wächter `keine_hartkodierten_nutzertexte.test.ts`, Katalog-Parität, „Schlüssel ohne Verwender“.
- Reiter-Definition und Umleitungen alter `?tab=`-Werte stammen aus Teil-PR 2 (`s3a2794_reiter_definition.test.ts`).
- E2E-Staging-Konfiguration: für 4a fehlte eine eigene; benutzt wurde eine Kopie von `playwright.2794-s3a3.staging.config.ts` (seriell, `workers: 1`, gemeinsames Staging-Konto). Für 4b eine eigene Konfiguration anlegen.
- Registrier-Sperre Staging: 5 Registrierungen/IP/Stunde (#117) — Zwei-Nutzer-Läufe sparsam planen.

## Dependencies
- Upstream: Profil-Ampel `alarm_ab` (S1a, #2792), `alarmAbAnzeige.ts`, Reiterleiste/Umleitungen (Teil 2), Reiter Wetter (Teil 3).
- Downstream: Übersicht Trip und Orts-Briefing, Listen-Menüs, Startseite, Hilfe, Golden-Prüfstände, Wächter-Allowlists.

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_teil4_entfernen.md` — maßgeblich (4b-Teil)
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` — Gesamt-Spec
- `docs/specs/modules/feat_2794_s3a_teil2_leiste.md`, `feat_2794_s3a_teil3_wetter.md`

## Risks & Considerations
- **Überschneidung mit #2913 (Neustart „Einstellungen neu“, PO-Entscheidung 2026-11-10, parallele Sitzung aktiv in `fix-2913-metrikliste-mockup`):** #2913 stellt fest, dass Reiter Wetter/Zustellung noch alte Seiten zeigen, und baut sie aus Design-System-Bausteinen neu (ADR-0112, Elementliste aus dem Mockup, Bildprüfer-Agent). AC-35/AC-50 (Fresh-Eyes gegen Mockup Fassung 3, Soll/Ist-Bild) überschneiden sich damit. In der Analyse klären: Mockup-Abgleich in 4b auf das beschränken, was 4b ändert (Übersicht, Listen, Texte), und die Abweichungen der Reiter-Seiten #2913 zuordnen statt sie in 4b nachzubauen; Soll/Ist-Bild benennt das ausdrücklich (Memory: jede Abweichung einem Plan zuordnen).
- **Dateikollision mit #2913-Sitzung:** Katalogdateien und `molecules/index.ts` sind gemeinsame Flächen; vor dem PR auf `origin/main` rebasen.
- **U4-Logik:** `tripWetterAlarmAktiv()` spiegelt eine Backend-Regel (`src/services/trip_alert.py`); `alarm_ab` darf die Aussage nur so ändern, wie das Backend tatsächlich alarmiert (prüfen, ob Backend `alarm_ab` schon auswertet).
- **Wächter AC-49:** „Alarme“ als Funktionsname und „Layout je Kanal“ als Abschnitt müssen über eine begründete Positivliste erlaubt bleiben, sonst Fehlalarme.
- **Golden-Neuschrieb:** Diffs inhaltlich prüfen, unerwartete Unterschiede sind Befund.
- Nur Frontend/Texte/Doku; keine Daten-, Go-, Python- oder Mail-Änderung.

## Analysis

### Type
Feature (Abschluss S3a, Teil-PR 4b; Spec `feat_2794_s3a_teil4_entfernen.md` bereits mit 4a freigegeben)

### Befunde (2026-11-12, Stand origin/main 59ec6f5d8)
1. **Sprungziele stimmen schon:** Trip-Liste, Orts-Liste und Startseite springen bereits auf `?tab=wetter` bzw. `?tab=zustellung` (`routes/trips/+page.svelte:109-110`, `routes/compare/+page.svelte:125-126`, `routes/+page.svelte:293-477`). AC-33/AC-48 sind reine Wortlaut-Arbeit plus Live-Klicktest.
2. **Backend wertet `alarm_ab` aus:** `src/services/trip_alert.py:215 ampel_alarmquelle_aktiv()` (nur wenn `display_config.ampel` gesetzt; aufgelöste Ampel inkl. Vorlagen-Vorgabe, `alarmfaehige_felder` != never und Metrik aktiv). Das Frontend-`tripWetterAlarmAktiv()` (`hubUebersichtModell.ts:133`) kennt das noch nicht → Übersicht kann „aus“ zeigen, obwohl der Alarm läuft.
3. **U4-Text:** Mockup Fassung 3 arbeitet die Übersicht nicht aus („Unverändert“, Z.594). Maßgeblich ist darum der Reiter Wetter: dort steht der Zähler „{ausloesend} von {alarmfaehig} Metriken lösen einen Alarm aus“ (`shared/wetter-tab/ampelModell.ts:386 alarmZaehler`, Katalog `wetter.alarm_ab.zaehler`). Für die Alarm-Zeile der Trip-Übersicht wird derselbe Zähler auf derselben aufgelösten Ampel genutzt (Vorlagen via `ladeVorlagenAmpeln`/`vorlagenAusTemplates`, `verschmelzen`, Eigenschaften aus Katalog), kein zweites Rechenmodell. Fehlt die Vorlage (Ladefehler), Anzeige „—“, nie geraten.
4. **Pendant-Lage (AC-35):** In `compare/`, `compare-new/`, `trip-detail/`, `trip-new/` keine Compare-Komponente mit Trip-Pendant für die sieben Funktionen. Einseitig benannte Dateien (`AlarmeScheduleTab`, `ActiveMetricRow`, `WeatherV2Kanaele` in `trip-detail/`) werden nur von `shared/`-Komponenten (AlarmeTab, ZustellungTab, VersandTab, WeatherMetricsTab) für beide Kontexte genutzt; `compare/*PropsAus.ts` sind Prop-Bündel. Prüfung zu Beginn der Umsetzung: `tests/tdd/test_pendant_gate_bekannte_paare.py` grün.
5. **Textbestand (Explore):** Reiternamen DE/EN: Übersicht/Overview, Etappen & Wegpunkte/Stages & waypoints, Orte/Locations, Wetter/Weather, Zustellung/Delivery. Jeder Schlüssel, der einen alten Reiter nennt, hat noch einen Verwender (keine Leichen):

| Schlüssel | Problem | Verwender |
|---|---|---|
| `aktionen.weather` | „Wetter-Metriken“ → „Wetter“ / „Weather“ (AC-48) | subscriptionActions, HubOverview:121, WeatherConfigDialog:153 |
| `aktionen.alarms` | bleibt „Alarme“ (Funktionsname, Ziel Zustellung) | subscriptionActions |
| `aktionen.reiter.wertebereiche` | Eyebrow U3 → `aktionen.reiter.wetter`; alter Schlüssel nur noch für Umleitung prüfen, sonst löschen | hubUebersichtModell:256 |
| `aktionen.uebersicht.uhrzeiten_festlegen` | „unter Wetter-Metriken im Abschnitt Versand“ → Reiter Zustellung | hubUebersichtModell:169 |
| `alarme.metriken.keine_gewaehlt`, `alarme.tabelle.leer`, `alarme.vorschau.keine_metriken`, `alarme.vorschau.reiter_wetter_metriken` | „Tab Wetter-Metriken“ → Reiter Wetter | AlarmeTab, alerts-tab/* |
| `alarme.kanaele.kein_empfaenger` | DE „Reiter Versand“ → Zustellung (EN schon „Delivery“) | AlertMetricChannelsBlock |
| `alarme.alarm_ab.umbau_hinweis` | „mit dem neuen Reiter Wetter“ → Hinweis veraltet, umformulieren („im Reiter Wetter“) | AlertMetricLevelTable |
| `home.aktion.metriken`, `home.aktion.metriken_ziel` | „Wetter-Metriken ändern“ → Wetter | routes/+page.svelte |
| `trip.uebersicht.metriken_bearbeiten`, `trip.uebersicht.bei_delta` | „Wetter-Metriken bearbeiten“ → Wetter; „bei Δ“ → Alarm-ab-Zähler (U4) | HubOverview |
| `vergleich.neu.wetter_metriken`, `vergleich.neu.profil_hinweis` | Wetter-Metriken/Wertebereiche als nächste Tabs → Wetter | CompareNewEditor |
| `wertebereiche.vergleich.titel` | Titel „Wetter-Metriken“ im Übergangsbaustein der Zustellung → neutraler Abschnittstitel | WeatherMetricsTab |
| `bausteine.checkliste.layout`, `bausteine.checkliste.wertebereiche` | Startklar-Checkliste nennt alte Reiter → Zustellung/Wetter | cockpitHelpers568:73,120 |
| `bausteine.checkliste.versand` | Eyebrow „Versand“ der Übersicht: Abschnitt der Zustellung (Anker `#versand`) → Positivliste, falls als Abschnitt gemeint | HubUebersicht:154,177 |
| `trip.anlegen.alle_gpx` | Wortlaut beim Umsetzen prüfen | TripNewEditor |

Funktions-/Fachbegriffe ohne Reiterbezug (Positivliste-Kandidaten für AC-49): Versand-Historie, nächster Versand, `hilfe.alarme.*`, `alarme.alarm_ab.*`, `info.*` (Bausteinbezug, Fachbegriff „Wetter-Metriken“ ohne Reiter), „Layout · volle Tabelle“ (`versand.briefing.sub.*`, Layout je Kanal), `trip.about.eyebrow`.
Bestehende Tests: `i18n/__tests__/katalog_schluessel_haben_verwender.test.ts`, `paritaet_de_en.test.ts`; mitzuziehen: `f5/f7/f9/f10KatalogAnker.ts`, `deutsch_unveraendert.test.ts`, `s3a2794_reiter_definition.test.ts`, `trip_hub_sprache`/`vergleich_hub_sprache`, `alarme_kanaele_hinweise_de_en`, `kanal_block_hinweise_render`, `bausteine_waechter*`, `elementliste_aktuell`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `shared/hub-uebersicht/hubUebersichtModell.ts` | MODIFY | U3 Eyebrow `aktionen.reiter.wetter`; `tripWetterAlarmAktiv()` + Ampel-Alarmquelle (Spiegel `ampel_alarmquelle_aktiv`); Uhrzeiten-Hinweis |
| `trip-detail/HubOverview.svelte` | MODIFY | U4 Alarm-Zeile mit `alarmZaehler` statt „bei Δ“; Vorlagen laden; Texte Wetter |
| `shared/hub-uebersicht/HubUebersicht.svelte` | MODIFY | Eyebrow/Versand-Abschnitt prüfen |
| `lib/utils/cockpitHelpers568.ts`, `shared/infoboxKeys.ts`, `routes/+page.svelte`, `routes/hilfe/+page.svelte`, `compare-new/CompareNewEditor.svelte`, `WeatherConfigDialog.svelte` | MODIFY | Texte/Schlüssel auf neue Reiter |
| `i18n/messages/{de,en}/{aktionen,alarme,home,trip,vergleich,wertebereiche,bausteine,hilfe}.json` | MODIFY | Wortlaut, verwaiste Schlüssel löschen |
| `i18n/__tests__/keine_alten_reiternamen.test.ts` | CREATE | Wächter AC-49 mit begründeter Positivliste und Negativ-Fixture |
| Übersichts-Modell-Test (`hub-uebersicht/__tests__`) | MODIFY/CREATE | AC-32: U3-Ziel/Eyebrow, Alarm aktiv mit/ohne `alarm_ab` |
| Katalog-Anker und Text-Tests (Liste oben) | MODIFY | nachziehen, nicht aufweichen |
| `docs/reference/i18n_glossar.md` | MODIFY | Zeile „Wertebereiche“ (Reiter-Name) entfällt |
| `frontend/e2e/s3a2794-teil4b-*.spec.ts`, eigene Staging-Playwright-Konfiguration | CREATE | Übersicht, Sprünge, EN, Screenshots |
| Golden `tests/golden/f3_home_listen/*` | MODIFY | Neuschrieb, Diff prüfen |

### Scope Assessment
- Files: ca. 25 (davon ca. 10 Tests/Anker)
- Estimated LoC: +250/-80 (ohne Golden)
- Risk Level: LOW–MEDIUM (nur Frontend-Texte und Anzeige; einzige Logik: Alarm-aktiv-Spiegel, muss exakt der Backend-Regel folgen)

### Technical Approach
Reihenfolge laut Spec „Schritt 4b: Reihenfolge“. Ergänzende Tech-Lead-Entscheidungen:
- **U4:** Alarm-Zeile zeigt den Zähler des Reiters Wetter (gleicher Katalogtext-Kern, gleiche Funktion `alarmZaehler` auf der aufgelösten Ampel); `active` = bisherige Quellen ODER Ampel-Alarmquelle (nur wenn `display_config.ampel` vorhanden, wie Backend). Gilt nur für den Trip (Orts-Briefing hat keine Alarm-Zeile in der Übersicht).
- **Menü:** „Wetter“/„Weather“ für `aktionen.weather`; „Alarme“/„Alerts“ bleibt, Ziel Zustellung (Spec-Vorschlag, mit Freigabe bestätigt).
- **„Versand“** ist Abschnitt der Zustellung (Anker `#versand`), kein Reiter mehr: als Abschnitts-/Funktionsname erlaubt, aber nie „Reiter/Tab Versand“. Der Wächter prüft daher Muster „Reiter|Tab|tab|im …-Tab“ + alter Name sowie die Reiter-Schlüssel selbst, plus Positivliste je Schlüssel mit Begründung.
- **Mockup-Abgleich (AC-35/AC-50):** auf das beschränken, was 4b ändert (Übersicht, Listen, Texte, Reiterleiste). Abweichungen der Reiter Wetter/Zustellung und des Seitenkopfs werden im Soll/Ist-Bild ausdrücklich #2913 (Neustart „Einstellungen neu“, laufende Scheiben a–e und Nachtrag Seitenkopf) zugeordnet, nicht in 4b nachgebaut.
- Vor dem PR auf `origin/main` aktualisieren (Katalogdateien sind gemeinsame Fläche mit der #2913-Sitzung).

### Dependencies
Upstream: S1a Profil-Ampel `alarm_ab`, `ampelModell.ts` (Reiter Wetter), Reiter-Umleitungen (Teil 2). Downstream: Übersicht, Listen-Menüs, Startseite, Hilfe, Golden, Wächter-Allowlists. Parallel: #2913.

### Open Questions
- Keine Produktfrage offen (Menü-Wortlaut mit Spec freigegeben; U4-Darstellung folgt dem Reiter Wetter).
