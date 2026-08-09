# Context: fix-1348-warn-kompensation

## Request Summary

PO-Korrektur vom 2026-07-30 zu Issue #1348 umsetzen: Der Briefing-Hinweis
"amtliche Warnungen aktuell nicht abrufbar" soll für einen Ort nur noch
erscheinen, wenn **keine** für diesen Ort zuständige Warn-Quelle erfolgreich
geantwortet hat. Kompensation durch eine andere erfolgreiche, ebenfalls
zuständige Quelle zählt. Die aktuelle Formel in
`src/services/official_alerts/base.py:146` (`unavailable = covering > 0 and
failed >= 1`) ist die davor gültige, jetzt abgelöste STRENGE Regel vom
2026-07-23 und erzeugt Fehlalarme (Beleg: PO-Meldung Trip "KHW 403",
30.07., GeoSphere lieferte 54× erfolgreich, nur MeteoAlarm war gesperrt,
Hinweis erschien trotzdem für AT-Etappen).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/official_alerts/base.py` | Kernlogik: `get_official_alerts_with_status()` (Zeile 90-176), Formel in Zeile 146 muss geändert werden; Docstring Zeile 98-116 referenziert die alte STRENGE Regel |
| `tests/tdd/test_official_alerts_unavailable_hint.py` | `TestUnavailableSignal` (Zeile 105-239) — `test_mischfall_streng_one_fail_one_empty_is_unavailable` (Zeile 165-194) fixiert exakt das alte Verhalten und muss auf die neue Kompensationsregel umgestellt werden; Moduldocstring (Zeile 20-22) referenziert ebenfalls die alte Regel |
| `src/services/trip_report_scheduler.py` | Aufrufer 1 (Zeile 802-818): setzt `sw.official_alerts_unavailable` je Segment für Trip-E-Mail/SMS — **kein Codeänderung nötig**, profitiert automatisch von der Formel-Korrektur in `base.py` |
| `src/services/comparison_engine.py` | Aufrufer 2 (Zeile 322-341): setzt `official_alerts_unavailable` je Ort für Compare — **kein Codeänderung nötig**, gleicher Grund |
| `docs/specs/modules/warn_unavailable_hint.md` | Ursprungs-Spec (status: draft, nie approved) dokumentiert die jetzt abgelöste STRENGE Formel als Implementierungsdetail — braucht Update oder Verweis auf neue Spec |

## Existing Patterns

- **Ein zentraler Signalgeber, viele Konsumenten:** `get_official_alerts_with_status()` ist die einzige Stelle, die `covering`/`failed` zählt; Trip-Scheduler und Compare-Engine rufen sie beide auf und reichen das Boolean nur weiter. Die Korrektur an einer Stelle wirkt für beide Kanäle — passt zur Projektvorgabe "möglichst viel Code zwischen Trip und Ortsvergleich teilen".
- **Fail-soft ohne Exception:** echte Quellen (`GeoSphereWarnSource` etc.) werfen nie, sondern liefern bei Egress-Block/429 intern `[]` über `warn_egress.observe_fetch_failure()`. Das bestehende Testmuster unterscheidet daher "wirft" (`_AllCoveringFailSource`) von "fail-soft leer, aber real ausgefallen" (echte `GeoSphereWarnSource` + Egress-Block).
- **Kein Mock-Theater:** Testquellen sind echte Objekte, die das `OfficialAlertSource`-Protocol strukturell erfüllen (`covers`/`fetch`/`name`), keine `Mock()`/`patch()`.

## Dependencies

- **Upstream:** `services.official_alerts.warn_egress` (Fail-Signal je Quelle), `services.official_alerts._REGISTERED_SOURCES` (Registry aller 5 amtlichen Quellen: MeteoAlarm, GeoSphere-Warn, Vigilance, Météo-Forêts, Massif-Closure)
- **Downstream:** `trip_report_scheduler.py` → `SegmentWeatherData.official_alerts_unavailable` → E-Mail-Renderer (full/compact) + SMS-Renderer; `comparison_engine.py` → `LocationResult.official_alerts_unavailable` → Compare-HTML-Renderer. Keiner dieser Renderer muss geändert werden — sie konsumieren nur das Boolean.

## Existing Specs

- `docs/specs/modules/warn_unavailable_hint.md` (draft, nicht approved) — dokumentiert die ursprüngliche STRENGE Formel vom 2026-07-23 als Bestandteil der Implementierung. Braucht in `/30-write-spec` eine Korrektur der Formel-Beschreibung (nicht zwingend eine neue Datei, da `warn_unavailable_hint` bereits das richtige Modul referenziert).
- `docs/specs/modules/feat_1349_compare_unavailable.md`, `feat_1349_sms_unavailable.md`, `feat_1349_telegram_unavailable.md` — Folge-Specs für die Anzeige des Flags in weiteren Kanälen; unverändert betroffen, da sie nur das Boolean konsumieren.

## Risks & Considerations

- **Sicherheitsrelevant:** eine zu lockere Formel darf keine echte Lücke verschlucken. `failed >= covering` (ALLE zuständigen Quellen ausgefallen) statt `failed >= 1` ist die korrekte Übersetzung der PO-Korrektur — bei nur einer zuständigen Quelle bleibt das Verhalten unverändert streng (`covering=1, failed=1` -> weiterhin `unavailable=True`).
- **PO-Aussage zu Südtirol ist zwischenzeitlich überholt (wichtig fuer die Spec!):** Die PO-Korrektur vom 2026-07-30 nennt als Beispiel "Fuer die Suedtirol-Etappen ist MeteoAlarm die einzige Quelle, dort bleibt der Hinweis korrekt". Das stimmte am 2026-07-30, ist aber seit **2026-07-31** (`23118c36`, #1427 S2) nicht mehr aktuell: `DpcSource` deckt seither denselben IT-Bbox-Bereich (lat 36.0-47.5, lon 6.5-19.0) zusätzlich ab — Südtirol liegt darin. Seit **2026-08-01** (`9c20f482`, #1445 S1+S3) laeuft AT+IT zudem ueber `MeteoAlarmFeedSource(country)` statt der alten `MeteoAlarmSource` (EDR-Index, jetzt ruhend/unregistriert). Registrierte Quellen heute (`services/official_alerts/__init__.py:36-42`): `VigilanceSource, MeteoForetsSource, MassifClosureSource, GeoSphereWarnSource, MeteoAlarmFeedSource("IT"), MeteoAlarmFeedSource("AT"), DpcSource`. **Fuer einen Suedtirol-Punkt decken heute ZWEI Quellen ab** (`MeteoAlarmFeedSource("IT")` + `DpcSource`), nicht mehr eine. Ob der Hinweis dort bei einem MeteoAlarm-Ausfall weiterhin erscheinen soll, haengt jetzt vom DpcSource-Status ab, nicht mehr automatisch von "es gibt nur eine Quelle". **Offene Frage fuer die Spec:** AC so formulieren, dass sie die reale Quellenlage von heute prueft, nicht das veraltete Einzelquellen-Beispiel des PO-Kommentars.
- **Regressionsgefahr:** `test_mischfall_streng_one_fail_one_empty_is_unavailable` erwartet aktuell `unavailable is True` für den Kompensationsfall — dieser Test MUSS mit umgedreht werden (neuer Name + neue Assertion), sonst bleibt die alte Regel grün eingefroren.
- **Realpfad-Nachweis explizit vom PO gefordert:** "ein Test, der genau die heutige Prod-Lage abbildet ... vor dem Fix rot." Die im PO-Kommentar genannten Quellen (`GeoSphere` + `MeteoAlarm`) muessen fuer den echten Regressionstest durch die AKTUELL registrierten Klassen ersetzt werden: `GeoSphereWarnSource` + `MeteoAlarmFeedSource("AT")` fuer den AT-Kompensationsfall; fuer den IT-Fall entweder zwei echte IT-Quellen (`MeteoAlarmFeedSource("IT")` + `DpcSource`) mit EINER ausgefallenen (weiterhin `unavailable=False`, kompensiert) ODER — falls die Spec bewusst den strengeren Alt-Fall erhalten will — eine isolierte Registry mit nur einer IT-Quelle.
- **Docstrings synchron halten:** sowohl `base.py:98-116` als auch der Moduldocstring von `test_official_alerts_unavailable_hint.py` referenzieren wörtlich die "STRENGE" 2026-07-23-Regel — beide müssen auf die 2026-07-30-Korrektur aktualisiert werden, sonst widerspricht die Doku dem Code (bekanntes Muster aus früheren Findings in diesem Projekt).

## Analysis

### Type
Bug (Korrektur: aktuelles Verhalten entspricht nicht mehr der gültigen PO-Entscheidung vom 2026-07-30)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/base.py` | MODIFY | Zeile 146: `unavailable = covering > 0 and failed >= 1` → `unavailable = covering > 0 and failed >= covering`; Docstring Zeile 98-116 auf Kompensationsregel umschreiben |
| `tests/tdd/test_official_alerts_unavailable_hint.py` | MODIFY | Mischfall-Test umdrehen (neue Assertion + neuer Name), Moduldocstring-Referenz korrigieren, neuen Realpfad-Test mit aktuell registrierten Quellen (`GeoSphereWarnSource`, `MeteoAlarmFeedSource`, `DpcSource`) ergänzen |
| `docs/specs/modules/warn_unavailable_hint.md` | MODIFY | Formel-Beschreibung in "Implementation Details" auf Kompensationsregel korrigieren (war nie approved, kann direkt korrigiert werden) |

Keine Änderung nötig an: `trip_report_scheduler.py`, `comparison_engine.py` (konsumieren nur das Boolean), allen Renderern (E-Mail/SMS/Compare).

### Scope Assessment
- Files: 3 (1 Produktivdatei, 1 Testdatei, 1 Spec-Korrektur)
- Estimated LoC: ~10 (base.py) + ~40-60 (Testdatei: 1 Test umgeschrieben, 1 neuer Realpfad-Test) + Spec-Text
- Risk Level: LOW — zentrale, gut isolierte Funktion; alle Aufrufer bereits über Tests abgesichert; keine Renderer-Änderung

### Technical Approach
1. Formel in `base.py:146` ändern: `covering > 0 and failed >= covering` (statt `failed >= 1`). Bei genau einer zuständigen Quelle bleibt das Verhalten identisch streng — nur bei ≥2 zuständigen Quellen wirkt jetzt Kompensation.
2. Docstrings (Code + Test) von "STRENG, eine Quelle genügt" auf "nur wenn ALLE zuständigen Quellen ausgefallen sind" umstellen, Referenz auf PO-Entscheid 2026-07-30 statt 2026-07-23.
3. Bestehenden Mischfall-Test umdrehen: gleiches Setup (`_AllCoveringFailSource` + `_SuccessEmptySource`), aber `unavailable is False` erwarten (kompensiert).
4. Neuen Realpfad-Test mit den HEUTE registrierten Quellklassen ergänzen, der die tatsächliche Prod-Quellenlage abbildet (nicht die veraltete "MeteoAlarm einzige IT-Quelle"-Annahme) — echter Nachweis ohne Mock-Theater, analog zum bestehenden `test_real_failsoft_empty_from_blocked_source_is_unavailable`-Muster.
5. Spec-Datei `warn_unavailable_hint.md` Formel-Abschnitt korrigieren.

### Dependencies
- `services.official_alerts.__init__` — Registry-Liste, für den Realpfad-Test relevant (welche Quellen sind heute aktiv)
- `services.official_alerts.warn_egress` — Fail-Signal-Mechanik bleibt unverändert
- Keine neuen externen Abhängigkeiten

### Open Questions
- [x] Soll die Spec das PO-Beispiel "Südtirol = nur eine Quelle" wörtlich reproduzieren, oder die reale heutige Zwei-Quellen-Lage als Grundlage nehmen? **PO-Entscheid (2026-08-09): reale heutige Lage.** Der Realpfad-Test nutzt `MeteoAlarmFeedSource("IT")` + `DpcSource` für Südtirol-Punkte; fällt nur eine der beiden aus, greift jetzt auch dort die Kompensation (kein Hinweis mehr). Der strenge Alt-Fall (nur eine zuständige Quelle) bleibt trotzdem über `test_all_covering_fail_is_unavailable` / `test_real_failsoft_empty_from_blocked_source_is_unavailable` (Innsbruck, nur GeoSphere in isolierter Registry) abgedeckt.
