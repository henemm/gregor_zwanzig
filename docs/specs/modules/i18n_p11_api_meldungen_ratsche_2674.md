---
entity_id: i18n_p11_api_meldungen_ratsche_2674
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2674, python, model-haiku]
---

# i18n P11: Python-API-Meldungen zweisprachig und Ratsche Python

**Issue:** #2674 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 4 (Ratsche Python), 5 (Fehlerobjekt)

## Approval

- [ ] Approved

## Purpose

Wenn die Vorschau scheitert oder eine Validierung eine Eingabe ablehnt, sieht der Nutzer die Meldung in der Sprache seines Kontos (`language=en` liest `Trip 42 not found for user alice`, `de` liest unverändert `Trip 42 nicht gefunden für User alice`), und jede Fehlerantwort trägt zusätzlich einen stabilen `code`, den das Frontend über `fehler.code.<code>` (Paket F11) übersetzen kann. Außerdem entsteht die Ratsche für Python: ein Test, der neue hartkodierte Nutzertexte in Renderern, Diensten und Routern blockt, damit die Zweisprachigkeit nicht wieder verwässert. Die Lieferung hat zwei Teile in einem Workflow: Teil 1 (nur Ratsche und Doku) direkt nach P1, Teil 2 (API-Meldungen, Allowlist leer) nach P2 bis P10.

## Source

- **File:** `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` (neu), `api/fehler.py` (neu), `src/services/fehler_code.py` (neu), `api/routers/validator.py`, `api/routers/preview.py`, `api/routers/gpx.py`, `api/routers/scheduler.py`, `api/routers/debug.py`, `src/services/preview_service.py`, `src/services/compare_preview_service.py`, `src/services/compare_alert_preview_service.py`, `src/services/weather_metrics.py`
- **Identifier:** `ApiFehler`, `api_fehler`, `api_fehler_aus`, `meldung_aus`, `register_fehler_handler`, `fehler_mit_code`; `detector_thresholds` (validator.py Z. 187-208), `alert_preview` (Z. 339-376), `briefing_alert_preview` (Z. 380-408), `_reject_unknown_segment_id` (Z. 424), `_validate_change_metrics` (Z. 444), `_synthesize_segment_times` (Z. 473-499), `metrics_for_channel` (Z. 507-528), `preview_sms` (preview.py Z. 34-60), `PreviewService._load_trip` (Z. 55-88), `_resolve_target_date` (Z. 90-129), `_build_report` (Z. 131 ff.), `render_sms_preview` (Z. 367), `ComparePreviewService._load_preset` (Z. 171-191), `_resolve_locations` (Z. 193-211), `_resolve_target_date` (Z. 229-245), `render_compare_alert_preview` (Z. 35-65), `_ordered` (Z. 68-74), `format_wind_strength` (Z. 123), `format_precip_intensity` (Z. 144), `format_precip_daily_sum` (Z. 162), `format_rain_probability_scale` (Z. 183), `format_sunshine_scale` (Z. 205)

> **Schicht-Hinweis:** Reiner Python-Core (`api/`, `src/services/`, `tests/`). Der Go-Proxy reicht die Antwort des Kerns unverändert an das Frontend durch; das Go-Fehlerobjekt `{"code","message"}` (G1) ist ein eigener Vertrag und bleibt unberührt. `src/services/weather_pattern.py` wurde geprüft und bleibt **unverändert**: die Stabilitäts-Bezeichner `STABIL`/`WECHSELHAFT`/`FRAGIL` sind Werte des `Literal` in `src/app/models.py` (Z. 1411) und damit Protokoll-Bezeichner; ihre Anzeigetexte gehören zu P2/P3.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Vorschau-Pfade (Trip: `preview_service`, Vergleich: `compare_preview_service`, `compare_alert_preview_service`) laufen über **dieselbe** Fehlerinfrastruktur (`api/fehler.py`, `fehler_mit_code`) und denselben Katalogbereich `api`; keine kind-spezifische Kopie. Unterschiedliche Texte haben unterschiedliche Codes mit Präfix `vorschau_` (Trip) bzw. `vergleich_` (Ortsvergleich).
> - **Mandantentrennung:** Die Sprache wird aus der `user_id` des Aufrufs aufgelöst (`resolve_user_lang`), die der Go-Proxy aus der Sitzung einsetzt (Bug #199); fehlt sie (`/api/_validator/compare-email-preview`, Debug-Router), gilt Deutsch. **Niemals** Fallback auf `"default"`. Ein Preset oder Trip eines anderen Nutzers liefert denselben 404 wie ein nicht existierendes Objekt, ohne fremde Inhalte (AC-2).
> - **Kanäle:** Keine Briefing- oder Alarm-Inhalte der vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) werden verändert; die Vorschau-Endpunkte liefern Fehlertexte an das Frontend. Die Skalenwörter in `weather_metrics.py` erscheinen im Briefing (E-Mail-Modus „simplified", Ortsvergleich-Ausblick) und folgen dort der Sprache, sobald P2/P4 `lang` durchreichen; in diesem Paket entsteht nur die Fähigkeit (`lang`-Parameter, Katalog).

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` | CREATE | Ratsche (AST-Lauf), Selbsttest der Ratsche, Wächter gegen tote Allowlist-Einträge; ab Teil 2 zusätzlich `test_allowlist_ist_leer` (`# doc-compliance-test`) |
| `tests/fixtures/i18n_python_allowlist.json` | CREATE | Allowlist: sortierte JSON-Liste von Dateipfaden relativ zum Repo; Startstand = alle Dateien mit Fund; Endstand `[]` |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Abschnitt „i18n-Ratschen" (Zeile für die Python-Ratsche) und Zeile im Regel-Budget (Prüfdatum 2027-01-28) |
| `api/fehler.py` | CREATE | `ApiFehler`, `api_fehler`, `api_fehler_aus`, `meldung_aus`, `register_fehler_handler` |
| `src/services/fehler_code.py` | CREATE | `fehler_mit_code(exc_type, code, **params)`: Ausnahme mit `.code`/`.params`, Meldung deutsch |
| `api/main.py` | MODIFY | `register_fehler_handler(app)` direkt nach `app = FastAPI(...)` (Z. 103) |
| `api/routers/validator.py` | MODIFY | neun `HTTPException(detail=<deutscher Text>)` (Z. 194-197, 346-349, 359-365, 406-408, 426-429, 454-457, 490-493, 520-523, 558-561) auf `api_fehler`/`api_fehler_aus` |
| `api/routers/preview.py` | MODIFY | Z. 42 und Z. 53-60 auf `api_fehler`/`api_fehler_aus` |
| `api/routers/gpx.py` | MODIFY | Z. 46-47 auf `api_fehler_aus`; Token `invalid_user_id`/`no_file_content` bleiben (Code-Tokens, kein Nutzertext) |
| `api/routers/scheduler.py` | MODIFY | Z. 77 (`Unlesbarer Zeitpunkt`) Betreiber-Meldung: Kommentar `# i18n-log`, Text bleibt deutsch |
| `api/routers/debug.py` | MODIFY | Z. 131 (`Mail-Versand fehlgeschlagen`) Debug-Router, nur Betreiber: Kommentar `# i18n-log` |
| `src/services/preview_service.py` | MODIFY | acht Meldungen (Z. 77, 85, 103, 112, 128, 181-185, 196, 367) auf `fehler_mit_code` |
| `src/services/compare_preview_service.py` | MODIFY | fünf Meldungen (Z. 189-191, 199-202, 207-210, 245) auf `fehler_mit_code` |
| `src/services/compare_alert_preview_service.py` | MODIFY | drei Meldungen (Z. 52, 72, 219) auf `fehler_mit_code`; Log-Zeile Z. 211-214 mit `# i18n-log` |
| `src/services/gpx_processing.py` | MODIFY | einzige Meldung Z. 65 (`Nur .gpx Dateien erlaubt`) auf `fehler_mit_code` |
| `src/services/weather_metrics.py` | MODIFY | die fünf Skalenfunktionen bekommen keyword-only `lang: Lang = "de"` und lesen die Wörter aus dem Katalog |
| `src/i18n/messages/de/api.json` | MODIFY | Bereichsdatei `api` (von P1 leer angelegt): deutsche Texte, wörtlich wie heute |
| `src/i18n/messages/en/api.json` | MODIFY | Bereichsdatei `api`: englische Texte laut Glossar |
| `tests/tdd/test_api_fehler_nutzersprache.py` | CREATE | Fehlerantworten je Kontosprache mit `code`, Zwei-Nutzer-Test (AC-1 bis AC-3, AC-8) |
| `tests/tdd/test_skalenwoerter_sprache.py` | CREATE | Skalenwörter `de` unverändert, `en` laut Katalog (AC-4) |
| `tests/test_i18n_api_katalog_paritaet.py` | CREATE | Schlüssel- und Platzhalterparität des Bereichs `api` (AC-7, `# doc-compliance-test`) |
| `tests/tdd/test_compare_missing_locations.py` | MODIFY (nur falls rot) | prüft `verweist auf gelöschte Orte` in `detail` und `str(exc.value)`; bleibt grün, weil die Meldung deutsch bleibt |

## Estimated Scope

- **LoC:** ca. 260 Code ohne Tests und ohne Katalogdaten (Ratsche ca. 110 als eigene Lieferung Teil 1; `api/fehler.py` ca. 55, `fehler_code.py` ca. 20, Router ca. 50, Dienste ca. 45, `weather_metrics.py` ca. 35). Mit Teil 1 über dem Workflow-Limit von 250 LoC: `workflow.py set-field loc_limit_override 500` einplanen (Teil 1 allein bleibt darunter).
- **Files:** 20 Code-/Katalog-/Doku-Dateien, 5 Testdateien.
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2662 P1 (`src/i18n`: `t`, `resolve_user_lang`; Bereichsdateien `api.json` leer angelegt) | Paket | Katalog-Zugriff und Sprachauflösung; Teil 1 startet direkt danach |
| #2664 P2 bis #2673 P10 | Pakete | Teil 2 (Allowlist-Endstand `[]`) erst, wenn alle Pakete ihre Allowlist-Einträge entfernt haben; Phasenwechsel-Kommentar im Epic |
| #2664 P2 / #2666 P4 | Pakete | Aufrufer der Skalenfunktionen: `src/output/renderers/email/helpers.py` (Z. 842-858) und `compare_outlook_metric_ids.py` (Z. 453-469). P11 prüft zuerst per Grep, ob die fünf Funktionen bereits ein `lang`-Argument tragen; wenn ja, entfällt der `weather_metrics.py`-Teil und es bleibt der Katalog-/Ratschen-Abgleich |
| #2660 F11 | Paket | Frontend löst `code` über `fehler.code.<code>` auf; die Codes dieser Spec sind der Vertrag |
| #2680 A1 | Paket | trägt `detail`+`code` in die Doku ein und prüft die drei Ratschen-Zeilen |
| `app.loader.get_data_dir`, `lib/go_internal` | Module | Pfadlogik der Sprachauflösung (in `resolve_user_lang`) |
| ADR-0104 Nr. 8 | ADR | Ratschen mit schrumpfender Allowlist |

## Implementation Details

### Teil 1 — Ratsche (direkt nach P1, eigener PR, keine Laufzeitänderung)

Datei `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` (Pfade relativ zur Testdatei auflösen: `REPO = Path(__file__).resolve().parents[1]`).

- **Scanfläche** (Konventionen Abschnitt 4): `src/output/**/*.py`, `api/routers/**/*.py` und alle `src/services/*.py`, deren Dateiname eines der Wörter `report`, `alert`, `notification`, `command`, `inbound`, `preview`, `comparison` enthält. **Annahme (Erweiterung um zwei Dateien):** zusätzlich die Konstante `EXTRA_DATEIEN = ("src/services/weather_metrics.py", "src/services/trip_selection.py")`, weil beide Nutzertexte tragen, aber in kein Namensmuster fallen.
- **Funde:** jede String-Konstante (`ast.Constant` mit `str`, auch Teile von f-Strings), die einen Buchstaben aus `äöüÄÖÜß` enthält oder eines der Wörter `nicht`, `bitte`, `keine`, `fehlgeschlagen`, `Hinweis` (als ganzes Wort, Groß-/Kleinschreibung egal). **Ausgenommen:** Docstrings (erstes `Expr`-String eines Moduls/einer Klasse/Funktion), Argumente von Aufrufen `t(...)` und `tn(...)`, Konstanten in Zeilen mit dem Kommentar `# i18n-log` (auch bei mehrzeiligen Aufrufen: der Kommentar steht in der Zeile des Literals). Kommentare sind im AST nicht enthalten.
- **Funktionen:**

```python
def _scan_dateien() -> list[Path]                       # Scanfläche + EXTRA_DATEIEN, sortiert
def _finde_nutzertexte(pfad: Path) -> list[tuple[int, str]]   # (Zeile, Textauszug <= 60 Zeichen)
def _allowlist() -> list[str]                           # JSON-Liste von Repo-Pfaden
```

- **Tests:** `test_keine_neuen_hartkodierten_nutzertexte` (jede Datei ausserhalb der Allowlist ohne Fund; Fehlermeldung `Datei:Zeile: "Auszug"` plus Hinweis „Text in den Katalog `src/i18n/messages/{de,en}/<bereich>.json`, oder Log-Zeile mit `# i18n-log` markieren"); `test_allowlist_hat_keine_toten_eintraege` (jeder Eintrag zeigt auf eine existierende Datei, die noch mindestens einen Fund hat — sonst muss der Eintrag raus: die Allowlist schrumpft, sie wächst nie); `test_ratsche_erkennt_bekannte_faelle` (Selbsttest mit `tmp_path`-Dateien: Literal mit Umlaut wird gefunden; `t("x.y")`, Docstring und `# i18n-log`-Zeile werden nicht gefunden).
- **Startstand:** `python tests/test_i18n_keine_hartkodierten_nutzertexte_python.py --startstand` (Aufruf-Block `if __name__ == "__main__"`) schreibt `tests/fixtures/i18n_python_allowlist.json` mit allen heute betroffenen Dateien (sortierte Pfadliste). Nur dieser Befehl erzeugt die Datei; danach wird sie von Hand nur gekürzt.
- **Doku:** `docs/reference/gates_und_ratschen.md` bekommt (falls noch nicht vorhanden) den Abschnitt `## i18n-Ratschen (Epic #2644, ab 2026-10-30)` mit einer Tabelle (Sprachraum | Wächter-Datei | Scanfläche | Allowlist | Marker) und der Zeile für Python; im Abschnitt „Regel-Budget: Prüfdaten im Überblick" eine Zeile „i18n-Ratsche Python (#2674) | 2027-01-28 | —". Die Zeilen für Frontend (S4) und Go (G5) trägt das jeweilige Paket bzw. A1 (#2680) nach.
- **Lieferung:** PR-A mit `Refs #2674` (kein Issue-Close), reguläre CI. Der Test ist mit voller Allowlist grün.

### Teil 2 — API-Meldungen und Endstand (nach P2 bis P10)

**Fehlerinfrastruktur.** Antwortform bleibt rückwärtskompatibel: `detail` ist weiter ein **String**, neu kommt `code` daneben.

```python
# api/fehler.py
class ApiFehler(HTTPException):          # trägt zusätzlich .code
    code: str
def api_fehler(status: int, code: str, nutzer: str | None, **params: object) -> ApiFehler
    # lang = resolve_user_lang(nutzer) if nutzer else "de"; detail = t(f"api.fehler.{code}", lang, **params)
def api_fehler_aus(exc: Exception, status: int, nutzer: str | None) -> ApiFehler
    # exc hat .code/.params (fehler_mit_code) -> api_fehler(status, exc.code, nutzer, **exc.params)
    # sonst: ApiFehler(status, detail=str(exc), code="unbekannt")  # Text unverändert
def meldung_aus(exc: Exception, nutzer: str | None) -> str      # lokalisierter Text oder str(exc)
def register_fehler_handler(app: FastAPI) -> None
    # @app.exception_handler(ApiFehler) -> JSONResponse(status, {"detail": exc.detail, "code": exc.code})

# src/services/fehler_code.py
def fehler_mit_code(exc_type: type[Exception], code: str, **params: object) -> Exception
    # Meldung = t(f"api.fehler.{code}", "de", **params)  -> str(exc) bleibt byte-gleich zu heute
    # (Log, Altaufrufer, bestehende Tests); setzt exc.code und exc.params
```

Dienste werfen weiter dieselben Ausnahmetypen (`FileNotFoundError`, `LookupError`, `ValueError`, `RuntimeError`); die Router entscheiden den Status wie bisher und lokalisieren über `api_fehler_aus`. Die Dienste kennen keine Nutzersprache.

**Beispiel-Umstellung 1 (Router)** `api/routers/validator.py:194-197`:

```python
# vorher
raise HTTPException(
    status_code=404,
    detail=f"Trip {trip} nicht gefunden für User {user_id}",
)
# nachher
raise api_fehler(404, "trip_nicht_gefunden", user_id, trip_id=trip, user_id=user_id)
```

**Beispiel-Umstellung 2 (Dienst + Router)** `src/services/preview_service.py:76-78` und `api/routers/preview.py:53-60`:

```python
# vorher (Dienst)
raise FileNotFoundError(f"Trip '{trip_id}' nicht gefunden für user '{user_id}'")
# nachher (Dienst)
raise fehler_mit_code(FileNotFoundError, "vorschau_trip_nicht_gefunden", trip_id=trip_id, user_id=user_id)
# vorher (Router)
except FileNotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
# nachher (Router)
except (FileNotFoundError, LookupError) as e:
    raise api_fehler_aus(e, 404, user_id)
```

**Codes und Katalog** (Namensraum `api.fehler.<code>`; Platzhalter snake_case in `de` und `en` gleich; `de` ist der heutige Text wörtlich):

| Code (Status) | `de` | `en` |
|---|---|---|
| `trip_nicht_gefunden` (404) | `Trip {trip_id} nicht gefunden für User {user_id}` | `Trip {trip_id} not found for user {user_id}` |
| `vorschau_trip_nicht_gefunden` (404) | `Trip '{trip_id}' nicht gefunden für user '{user_id}'` | `Trip '{trip_id}' not found for user '{user_id}'` |
| `vorschau_ohne_wegpunkte` (404) | `Trip '{trip_id}' hat keine Etappe mit genug waypoints für eine Vorschau` | `Trip '{trip_id}' has no stage with enough waypoints for a preview` |
| `vorschau_etappe_fehlt` (404) | `Keine Stage am {datum} im Trip '{trip_id}'` | `No stage on {datum} in trip '{trip_id}'` |
| `vorschau_zu_wenige_wegpunkte` (404) | `Stage am {datum} im Trip '{trip_id}' hat zu wenige waypoints für eine Vorschau` | `Stage on {datum} in trip '{trip_id}' has too few waypoints for a preview` |
| `vorschau_ohne_etappen` (422) | `Trip '{trip_id}' hat keine Stages` | `Trip '{trip_id}' has no stages` |
| `vorschau_wetter_fehlt` (503) | `Wetterdaten nicht verfügbar für Trip '{trip_id}' am {datum}` | `Weather data not available for trip '{trip_id}' on {datum}` |
| `vorschau_datum_ungueltig` (422) | `Ungültiges Datum '{datum}', ISO erwartet` | `Invalid date '{datum}', ISO format expected` |
| `report_typ_ungueltig` (422) | `Ungültiger report_type '{report_type}'` | `Invalid report_type '{report_type}'` |
| `typ_ungueltig` (422) | `Ungültiger type '{type}'` | `Invalid type '{type}'` |
| `body_genau_einer` (422) | `Body muss genau einen von 'onset', 'changes', 'official' oder 'nowcast_frames' enthalten` | `Body must contain exactly one of 'onset', 'changes', 'official' or 'nowcast_frames'` |
| `segment_unbekannt` (422) | `Unbekannte segment_id '{segment_id}' im Trip` | `Unknown segment_id '{segment_id}' in the trip` |
| `metrik_unbekannt` (422) | `Unbekannte Metrik '{metric}' in changes` | `Unknown metric '{metric}' in changes` |
| `alarm_body_ungueltig` (422) | `Ungültiger Alarm-Körper: {grund}` | `Invalid alert body: {grund}` |
| `vergleich_nicht_gefunden` (404) | `Orts-Vergleich '{preset_id}' nicht gefunden für Nutzer '{user_id}'` | `Location comparison '{preset_id}' not found for user '{user_id}'` |
| `vergleich_ohne_orte` (422) | `Orts-Vergleich '{preset_id}' hat keine Orte konfiguriert — es gibt nichts zu vergleichen.` | `Location comparison '{preset_id}' has no locations configured - there is nothing to compare.` |
| `vergleich_orte_geloescht` (422) | `Ortsvergleich '{preset_id}' verweist auf gelöschte Orte. Ersetze die Orte im Ortsvergleich. (Orte {location_ids} nicht aufloesbar)` | `Location comparison '{preset_id}' points to deleted locations. Replace the locations in the comparison. (Locations {location_ids} not resolvable)` |
| `vergleich_datum_ungueltig` (422) | `Ungültiges Datum '{datum}' (erwartet ISO JJJJ-MM-TT)` | `Invalid date '{datum}' (expected ISO YYYY-MM-DD)` |
| `vergleich_body_genau_einer` (422) | `Body muss genau einen von 'changes', 'onsets' oder 'official' enthalten` | `Body must contain exactly one of 'changes', 'onsets' or 'official'` |
| `vergleich_orte_fremd` (422) | `Orte {orte} gehoeren nicht zu diesem Orts-Vergleich` | `Locations {orte} do not belong to this location comparison` |
| `vergleich_keine_warnung` (422) | `Keine amtliche Warnung fuer die Orte dieses Vergleichs` | `No official warning for the locations of this comparison` |
| `gpx_nur_gpx` (400) | `Nur .gpx Dateien erlaubt, nicht '{filename}'` | `Only .gpx files are allowed, not '{filename}'` |

Der Code `unbekannt` hat keinen Katalogtext: Ausnahmen ohne `.code` behalten ihren Text (`str(exc)`). Das Wort `waypoints` bleibt in beiden Sprachen im Text von `vorschau_ohne_wegpunkte` und `vorschau_zu_wenige_wegpunkte`, weil das Frontend (#421) die Wegpunkt-Fälle bis zur Umstellung durch F11 am Wort erkennt. Unverändert bleiben: `detail="kind_required"`, `invalid_user_id`, `no_file_content` (Code-Tokens, kein Nutzertext), die Pydantic-Fehlerliste `e.errors(...)` (Z. 397, maschinenlesbar), `webhook.py`-Antworten und die `{"error": …}`-Codes in `internal.py`/`compare.py` (Go-zu-Core-Protokoll, nicht nutzersichtbar).

**Skalenwörter** (`api.skala.*`, Bereich laut Issue `api`):

| Schlüssel | `de` | `en` |
|---|---|---|
| `api.skala.wind.schwach` / `.maessig` / `.stark` / `.sehr_stark` | schwach / mäßig / stark / sehr stark | weak / moderate / strong / very strong |
| `api.skala.niederschlag.trocken` / `.leicht` / `.maessig` / `.stark` | trocken / leicht / mäßig / stark | dry / light / moderate / heavy |
| `api.skala.regen.unwahrscheinlich` / `.moeglich` / `.wahrscheinlich` / `.sehr_wahrscheinlich` | unwahrscheinlich / möglich / wahrscheinlich / sehr wahrscheinlich | unlikely / possible / likely / very likely |
| `api.skala.sonne.truebe` / `.wechselhaft` / `.freundlich` / `.sonnig` | trübe / wechselhaft / freundlich / sonnig | overcast / changeable / fair / sunny |

Signaturen: `format_wind_strength(kmh, *, lang: Lang = "de")` und analog für die vier anderen Funktionen; die Schwellen bleiben unverändert, der Platzhalter `–` für `None` ist kein Nutzertext und bleibt Literal. Die Funktion `weather_pattern.compute_stability` bleibt unverändert.

**Endstand der Ratsche.** `tests/fixtures/i18n_python_allowlist.json` wird auf `[]` gekürzt (bis auf Log-/Debug-Ausnahmen, die per `# i18n-log` an der Zeile markiert sind und die Allowlist nicht brauchen); `test_allowlist_ist_leer` kommt in die Testdatei. Vor dem Kürzen: per `--startstand`-Aufruf mit Ausgabe auf stdout (ohne Überschreiben) prüfen, welche Dateien noch Funde haben; verbleibende Funde sind entweder Log-Zeilen (Kommentar ergänzen) oder ein Befund für das Paket, das sie hätte migrieren müssen (Rückmeldung im Epic, nicht hier migrieren).

**Mutations-Gegenproben (Adversary).** (a) deutsches Literal `"Fehler beim Rendern"` in `src/output/renderers/email/html.py` einfügen → `test_keine_neuen_hartkodierten_nutzertexte` rot mit `Datei:Zeile`; (b) `resolve_user_lang` im Handler fest auf `"de"` setzen → AC-1/AC-2 rot; (c) Allowlist-Eintrag einer sauberen Datei ergänzen → `test_allowlist_hat_keine_toten_eintraege` rot.

## Expected Behavior

- **Input:** Aufruf eines Vorschau- oder Validator-Endpunkts mit `user_id` (vom Go-Proxy aus der Sitzung), der scheitert; bzw. ein Testlauf über die Quelldateien.
- **Output:** HTTP-Fehlerantwort `{"detail": "<Text in Kontosprache>", "code": "<stabiler_code>"}`; `detail` bleibt ein String. Ratsche: grün oder rot mit `Datei:Zeile`.
- **Side effects:** keine. Die Sprache wird nur gelesen. Bestehende Aufrufer, die `detail` als String lesen, funktionieren unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit `language=en`, dessen Trip keine Etappe mit genug Wegpunkten hat / When er die SMS-Vorschau aufruft (`GET /api/preview/{trip_id}/sms`) / Then antwortet der Kern mit Status 404, `detail` ist der englische Text `Trip '…' has no stage with enough waypoints for a preview` und `code` ist `vorschau_ohne_wegpunkte`; ein Nutzer mit `de` bekommt denselben Status, den heutigen deutschen Text byte-gleich und denselben `code`.
  - Test: tests/tdd/test_api_fehler_nutzersprache.py — echter FastAPI-Aufruf (TestClient auf `api.main:app`) mit zwei Nutzern `de`/`en` und gleichem Fehlerfall; deutsche Erwartung stammt aus dem Golden-Text der Ist-Fassung.

- **AC-2:** Given Nutzer A (`en`) fragt die Vergleichs-Alarm-Vorschau für einen Ortsvergleich an, der Nutzer B gehört, und für einen eigenen Ortsvergleich ohne Orte / When beide Aufrufe (`POST /api/briefings/{id}/alert-preview?kind=vergleich`) scheitern / Then liefert der fremde Ortsvergleich 404 mit `code` `vergleich_nicht_gefunden` in Englisch ohne Inhalte von B, der eigene ohne Orte 422 mit `vergleich_ohne_orte` in Englisch, und derselbe Aufruf von B (`de`) liefert den deutschen Text.
  - Test: tests/tdd/test_api_fehler_nutzersprache.py — Zwei-Nutzer-Test über den echten Router; Gegenprobe: die Antwort an A enthält weder Namen noch IDs aus B's Daten.

- **AC-3:** Given ein Nutzer mit `language=en` / When er eine Alarm-Vorschau mit unbekannter `segment_id`, unbekannter Metrik oder mit zwei Body-Arten gleichzeitig abschickt / Then lehnt der Validator-Router mit 422 ab, `detail` ist englisch (`Unknown segment_id '…' in the trip`, `Unknown metric '…' in changes`, `Body must contain exactly one of …`), `code` ist `segment_unbekannt`, `metrik_unbekannt` bzw. `body_genau_einer`, und die Pydantic-Fehlerliste bei fehlerhaftem Body bleibt unverändert.
  - Test: tests/tdd/test_api_fehler_nutzersprache.py — drei Fehlerfälle über `/api/trips/{id}/alert-preview`, je `de` und `en`; Positivkontrolle: ein gültiger Body liefert weiter 200.

- **AC-4:** Given die Skalenfunktionen für Wind, Niederschlag, Regenwahrscheinlichkeit und Sonnenstunden / When sie ohne `lang` und mit `lang="en"` aufgerufen werden / Then liefert der Aufruf ohne `lang` für alle Schwellenwerte exakt die heutigen deutschen Wörter (`mäßig`, `sehr stark`, `trübe`), mit `lang="en"` die englischen (`moderate`, `very strong`, `overcast`), und `None` liefert in beiden Sprachen `–`.
  - Test: tests/tdd/test_skalenwoerter_sprache.py — Grenzwerte (9.9/10/24.9/25/39.9/40 km/h usw.) für alle fünf Funktionen in beiden Sprachen; die deutschen Erwartungen sind die Wörter der Ist-Fassung.

- **AC-5:** Given die Python-Ratsche mit voller Startstand-Allowlist (Teil 1) / When ein neues deutsches Literal in `src/output/renderers/email/html.py` eingefügt wird, die Datei aber nicht auf der Allowlist steht oder eine bereits saubere Datei auf die Allowlist gesetzt wird / Then wird der Test rot, mit `Datei:Zeile` des Fundes bzw. mit dem Hinweis auf den toten Allowlist-Eintrag; Docstrings, `t(...)`-Argumente und Zeilen mit `# i18n-log` lösen nie aus.
  - Test: tests/test_i18n_keine_hartkodierten_nutzertexte_python.py — Selbsttest mit echten Dateien in `tmp_path` (Fund, kein Fund, Allowlist-Verhalten); `# doc-compliance-test` für den Scan über den Quellbaum.

- **AC-6:** Given alle Pakete P2 bis P10 sind abgeschlossen / When der Ratschentest im Endstand läuft / Then ist `tests/fixtures/i18n_python_allowlist.json` leer (`[]`) und `test_allowlist_ist_leer` ist grün; bleibende deutsche Log-/Debug-Texte tragen den Zeilenkommentar `# i18n-log`.
  - Test: tests/test_i18n_keine_hartkodierten_nutzertexte_python.py — `test_allowlist_ist_leer` und `test_keine_neuen_hartkodierten_nutzertexte` über den ganzen Quellbaum (`# doc-compliance-test`).

- **AC-7:** Given der Katalogbereich `api` / When der Paritätstest läuft / Then haben `api.json` in `de` und `en` identische Schlüssel- und Platzhaltermengen, und jeder Code der Codes-Tabelle sowie jedes Skalenwort hat in beiden Sprachen einen Eintrag.
  - Test: tests/test_i18n_api_katalog_paritaet.py — `# doc-compliance-test` (Paritätstest, kein Verhaltensnachweis); Verhaltensanteil: Mutation „en-Schlüssel entfernen" färbt den Test rot.

- **AC-8:** Given ein bestehender Aufrufer, der `detail` als String liest (Go-Proxy, Frontend) / When ein Vorschau-Fehler auftritt / Then enthält die Antwort `detail` weiter als String, zusätzlich das Feld `code`, und Fehlerfälle ohne Code (`unbekannt`) behalten ihren bisherigen Text unverändert.
  - Test: tests/tdd/test_api_fehler_nutzersprache.py — Antwortform per `response.json()`: `isinstance(detail, str)`, `code` vorhanden; ungeregelter `ValueError` aus einer Quelle ohne `.code` liefert `code == "unbekannt"` und unveränderten Text.

## Known Limitations

- **Annahme 1 (zwei Lieferungen):** Teil 1 und Teil 2 sind ein Workflow mit zwei PRs (Konventionen Abschnitt 9 überlässt die Entscheidung der Spec). Teil 1 trägt `Refs #2674`; das Issue wird erst mit Teil 2 geschlossen.
- **Annahme 2 (Scanfläche):** `weather_metrics.py` und `trip_selection.py` werden der Scanfläche der Konventionen als `EXTRA_DATEIEN` hinzugefügt, weil sie Nutzertexte tragen und in kein Namensmuster fallen. `trip_selection.py` migriert P10 (#2673).
- **Annahme 3 (Dienst-Meldung deutsch):** `fehler_mit_code` baut die Meldung in Deutsch, damit `str(exc)` für Logs und bestehende Tests byte-gleich bleibt; nur der Router lokalisiert.
- **Annahme 4 (Katalogbereich):** Die Skalenwörter liegen laut Issue im Bereich `api` (`api.skala.*`), obwohl `allgemein` fachlich passender wäre; `allgemein.json` gehört dem Kern-Paket P1.
- Das Frontend zeigt bis zur Umstellung durch F11 weiter `detail`; die `code`-Auflösung über `fehler.code.<code>` ist Sache von F11.
- Pydantic-Validierungsdetails (`e.errors(...)`), `webhook.py`-Antworten, `{"error": …}`-Codes des Go-zu-Core-Protokolls und die Debug-/Scheduler-Betreibermeldungen bleiben unübersetzt.
- Der Eintrag von `detail`+`code` in die Referenzdoku erfolgt in A1 (#2680).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Meldungen folgen der Sprache des Nutzers aus `user.json`, der stabile `code` entkoppelt die Übersetzung vom Text, und die Ratsche mit schrumpfender Allowlist (ADR-0104 Nr. 8) hält den Endstand dauerhaft sauber.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
