---
entity_id: feat_1373_s2b_metrik_speicherformat
type: module
created: 2026-07-26
updated: 2026-07-26
status: draft
workflow: feat-1373-s2b-metrik-speicherformat
version: "1.0"
tags: [compare, metric-catalog, persistence, migration]
---

# S2 Scheibe B: Speicherformat der Metrik-Auswahl auf Größe+Auswertung umstellen

## Approval

- [ ] Approved

## Purpose

Die Metrik-Auswahl eines Orts-Vergleichs (`display_config.active_metrics`)
wird heute als Liste von Zeichenketten gespeichert (`["temp_max_c",
"temp_min_c"]`). Diese Lieferung stellt das Speicherformat auf eine Liste aus
Größe und Auswertung um (`[{"metric_id": "temperature", "aggregation":
"max"}, …]`) — Grundlagenarbeit für S4 (wählbare Auswertung, #1357). Gelesen
wird künftig beides (Alt- und Neuformat, dauerhaft, nicht nur bis zur
Migration), geschrieben wird ab dieser Lieferung nur noch das Neuformat.
Bestandsdaten werden per Migrationsskript umgestellt (verlustfrei,
wiederholbar, mit Sicherung, je Host). An der Bedienoberfläche ändert sich
nichts — dieselbe Auswahl muss vor und nach der Umstellung dieselbe Mail
ergeben.

Etappe S2 von Epic #1372 (Kind von Dach-Epic #1374), Ticket #1373, Scheibe B
(Folgelieferung zu Scheibe A, `feat_1373_s2_ein_katalog.md`, geliefert und
live: `373d3970`).

## Source

- **File:** `src/output/renderers/compare_metric_ids.py`
- **Identifier:** `resolve_enabled_metrics()` (Z.101-132) — der zentrale
  Auflöser, den `report_config_resolver.resolve_compare_render_options()`
  als einzigen Aufrufer nutzt
- **File:** `src/services/compare_alert.py`
- **Identifier:** `_display_config_from_active_metrics()` (Z.233-271) —
  zweiter, unabhängiger Leser für den Δ-Alarm-Pfad (#1191)
- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts`
- **Identifier:** `buildComparePresetSavePayload()` (Z.97-103, Edit),
  `buildNewComparePresetPayload()` (Z.277, Neuanlage)

## Estimated Scope

- **LoC:** Produktivcode **~80-120** Zeilen (Auflöser + Alarm-Normalisierung
  + drei Frontend-Stellen + Umkehr-Index im Katalog), Migrationsskript
  **~140-160** Zeilen, Tests **~350-440** Zeilen. Gesamt **~600-700**
  Zeilen. Der 250-Zeilen-Deckel hält damit **nicht** — ein Override auf
  **900** ist beantragt (wie bereits in Scheibe A begründet: Persistenz-
  Umstellung mit Migrationsskript und Testvorbild ist nicht sinnvoll unter
  250 Zeilen abzuschneiden, ohne die Sicherungs- oder Testabdeckung zu
  kürzen — genau das würde das Datenverlust-Risiko #102 erhöhen).
- **Files:** 6 MODIFY + 3 CREATE (s. Implementation Details), davon 2
  Backend-Python, 3 Frontend-TypeScript, 1 neues Migrationsskript, 2 neue
  Testdateien, 1-2 bestehende Frontend-Testdateien erweitert.
- **Effort:** high (Bestandsdaten-Migration, mehrere unabhängige
  Leser/Schreiber, Datenverlust-Klasse #102 als dominierendes Risiko).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/compare_metric_catalog.py` | READ-ONLY (Scheibe A, geliefert) | Liefert `metric_id`/`aggregation` je der 26 Katalog-Einträge — Grundlage für den neuen Umkehr-Index |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | `resolve_enabled_metrics()` muss künftig beide Formate pro Element auflösen |
| `src/services/compare_alert.py` | MODIFY | `_display_config_from_active_metrics()` muss Neuformat-Einträge vor der bestehenden `_SUMMARY_KEY_TO_CATALOG_ID`-Übersetzung auf die alte Zeichenkette normalisieren |
| `src/services/report_config_resolver.py` | CHECK | Einziger Aufrufer von `resolve_enabled_metrics()` — keine Änderung erwartet, muss aber unverändert grün bleiben |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | Zwei Schreibstellen (Edit, Neuanlage) übersetzen künftig ins Neuformat; Asymmetrie `[]` vs. weglassenden Key bleibt erhalten |
| `frontend/src/lib/components/compare/compareEditorLoad.ts` | MODIFY | `rehydrateActiveMetrics()` liest künftig beide Formate und liefert weiterhin `string[]` |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts` | MODIFY/CREATE | Übersetzung Auswahl-Eintrag ↔ `{metric_id, aggregation}` aus der bereits geladenen Katalogantwort (Scheibe A) |
| `scripts/migrate_1373_compare_active_metrics_format.py` | CREATE | Bestandsumstellung, Vorbild `migrate_1361_drop_compare_hour_from_to.py` |
| `tests/unit/test_compare_active_metrics_dual_format.py` | CREATE | Kern-Tests: beide Formate, Mischliste, Reihenfolge, `[]` vs. `null` |
| `tests/test_compare_active_metrics_format_migration.py` | CREATE | Migrations-Tests, Vorbild `tests/test_compare_hour_from_to_migration.py` |

**Ausdrücklich NICHT betroffen** (geprüft, keine Änderung nötig):
`corridorEditorState.ts` (ist nur Aufrufer der einen Übersetzungsstelle,
keine eigene), `compareMetricOrder.ts`, `CompareTabs.svelte`,
`weatherMetricsCompareSave.ts`, `compareWizardState.svelte.ts`,
`cockpitHelpers568.ts`, jeglicher Go-Code (`display_config` ist dort
untypisiert, reicht den JSON-Blob blind durch), `api/routers/compare.py`.

## Implementation Details

```
1. UMKEHR-INDEX IM KATALOG (compare_metric_catalog.py)

   Ein Index auf Modulebene ueber COMPARE_METRIC_CATALOG:
   {(metric_id, aggregation): key}, plus Funktion
   key_for(metric_id, aggregation) -> str | None. Keine fuenfte
   Uebersetzungstabelle -- ein reiner Index ueber die in Scheibe A bereits
   ergaenzten Herkunftsfelder. Zusaetzlicher Assert:
   len(pairs) == len(set(pairs)) -- meldet ein kuenftiges doppeltes
   Groesse-Auswertung-Paar beim Modul-Import, statt es still kollidieren
   zu lassen (heute paarweise eindeutig, nachgemessen).

2. AUFLOESUNG PRO ELEMENT (compare_metric_ids.py)

   resolve_enabled_metrics() bekommt eine Hilfsfunktion _to_key(item):
   Zeichenkette bleibt Zeichenkette; Objekt mit metric_id/aggregation wird
   ueber key_for() aufgeloest; alles andere (unbekanntes Paar, falscher
   Typ) wird wie heute mit logger.warning verworfen. Die Aufloesung laeuft
   PRO ELEMENT, nicht pro Liste -- eine Mischliste (Alt- und Neuformat im
   selben Array) wird also ohne Absturz verarbeitet. Danach unveraendert
   die bestehende Verarbeitung: Dedup ueber dict.fromkeys (reihenfolge-
   erhaltend), leer/None/falscher Typ -> None (= kein Filter). Der
   Dedup-Schluessel bleibt die Renderer-Kennung -- er aendert sich nicht,
   Reihenfolge (#1335/#1359) bleibt erhalten.

3. ALARM-PFAD NORMALISIEREN, NICHT UMBAUEN (compare_alert.py)

   _display_config_from_active_metrics() bekommt vor dem bestehenden
   Zugriff auf _SUMMARY_KEY_TO_CATALOG_ID einen Normalisierungsschritt:
   jedes Element, das ein Neuformat-Objekt ist, wird zuerst ueber
   key_for(metric_id, aggregation) auf die alte Zeichenkette zurueck-
   uebersetzt. _SUMMARY_KEY_TO_CATALOG_ID selbst bleibt unveraendert --
   sie fuehrt in einen anderen Namensraum (Alarm-Engine-IDs wie
   "temperature_cold"), den der neue Katalog-Index nicht ersetzen kann.

4. FRONTEND: VIER STELLEN

   Korrigiert 2026-07-26 nach RED-Befund: es sind vier, nicht drei. Die
   vierte (buildHubPutPayload) ist ein echter Datenverlust-Pfad, siehe
   AC-12.

   - compareEditorLoad.ts::rehydrateActiveMetrics(): liest Alt- UND
     Neuformat, liefert weiterhin string[] (Renderer-Keys) an den
     geteilten State.
   - compareHubWizardBridge.ts::buildHubPutPayload() Z.115: der
     Bestandsrueckfall
       activeMetricKeys: edit.activeMetricKeys ?? (displayConfig.active_metrics as string[])
     reicht den ROHEN gespeicherten Wert weiter, wenn der Nutzer einen
     anderen Reiter bearbeitet (edit.activeMetricKeys ist dann undefined).
     Nach der Migration sind das Objekte, die als string[] deklariert
     weitergegeben und von der Schreibfunktion erneut uebersetzt wuerden
     -- Ergebnis: beschaedigte oder verlorene Auswahl beim Speichern eines
     voellig anderen Reiters. Der Rueckfall MUSS ueber dieselbe
     Lesenormalisierung wie rehydrateActiveMetrics() laufen.
   - compareEditorSave.ts::buildComparePresetSavePayload() (Edit) und
     buildNewComparePresetPayload() (Neuanlage): uebersetzen
     activeMetricKeys (string[]) beim Schreiben ueber die bereits aus
     GET /api/compare/metrics geladene Katalogantwort (Scheibe A liefert
     metric_id/aggregation je Eintrag) ins Neuformat. Die Asymmetrie
     bleibt erhalten: Edit schreibt [] explizit, Neuanlage laesst den Key
     bei leerer Auswahl weg (#1191/F001).
   - compareMetricSelection.ts: kleine Uebersetzungsfunktion
     Auswahl-Key -> {metric_id, aggregation} anhand der geladenen
     Katalogantwort -- keine neue Tabelle, keine neue Anfrage.
   corridorEditorState.ts bleibt unangetastet: es ist Aufrufer der Save-
   Funktion, keine eigene Uebersetzungsstelle.

5. MIGRATIONSSKRIPT (scripts/migrate_1373_compare_active_metrics_format.py)

   Vorbild migrate_1361_drop_compare_hour_from_to.py (gleiches
   briefings/-Layout wie das Zielverzeichnis dieser Migration, saubere
   Fehlerpfade): --root (Pflicht), --backup-dir, --execute; Dry-Run ist
   Default; tar.gz-Sicherung vor jedem Schreiblauf; Plan->Apply;
   Idempotenz ueber eine _needs_migration()-Pruefung; Read-Modify-Write
   (ganze Datei laden, nur active_metrics aendern, alle anderen Felder
   unveraendert zurueckschreiben); Filter kind != "vergleich" ->
   uebersprungen; alle Nutzerverzeichnisse unter --root erfasst.
```

## Expected Behavior

- **Input:** Ein Nutzer wählt im Ortsvergleich-Editor weiterhin einzelne
  Metrik-Zeilen aus (unverändert an der Oberfläche). Beim Speichern eines
  bestehenden oder neu angelegten Vergleichs wird diese Auswahl künftig als
  Liste aus Größe+Auswertung geschrieben.
- **Output:** Editor, Cockpit-Fortschrittsanzeige, E-Mail (HTML/Klartext),
  Telegram und SMS zeigen für dieselbe Auswahl exakt dieselben Zeilen in
  derselben Reihenfolge mit denselben Werten wie vor der Umstellung — egal
  ob die zugrundeliegende Datei noch im Alt- oder bereits im Neuformat
  vorliegt.
- **Side effects:** Nach erfolgreichem Migrationslauf liegen alle
  Bestandsvergleiche im Neuformat vor; Touren (`kind=route`) sind davon
  nicht betroffen. Ein künftiges doppeltes Größe-Auswertung-Paar im
  Vergleichs-Katalog lässt einen Test beim nächsten Lauf sichtbar
  fehlschlagen, statt zwei Zeilen unbemerkt auf denselben Auswahl-Eintrag
  kollidieren zu lassen.

## Acceptance Criteria

- **AC-1:** Given ein Vergleich, in dem Höchst- und Tiefsttemperatur
  ausgewählt sind / When der Nutzer die Vergleichsmail auslöst / Then
  enthält sie beide Temperaturzeilen mit denselben Werten wie vor der
  Umstellung — keine der beiden verschmilzt mit der anderen.
  - Test: Kern-Test des Auflösers mit einer Auswahl, die dieselbe Größe in
    zwei Auswertungen enthält (Höchst- und Tiefsttemperatur) — beide
    Zeilen müssen getrennt erhalten bleiben.

- **AC-2:** Given ein Nutzer wählt mehrere Wettergrößen in einer bestimmten
  Reihenfolge aus und speichert / When er die Auswahl später erneut öffnet
  oder eine Mail auslöst / Then erscheinen die Größen in genau der
  Reihenfolge, in der er sie ausgewählt hat.
  - Test: Kern-Test mit einer mehrelementigen Auswahl in fester Reihenfolge
    — die aufgelöste Liste hat dieselbe Reihenfolge wie die Eingabe.

- **AC-3:** Given ein Nutzer hat bewusst alle Wettergrößen abgewählt und
  gespeichert / When er die Auswahl danach erneut öffnet, eine Mail
  ausgelöst wird oder die Bestandsumstellung über den Vergleich läuft /
  Then bleibt im Editor weiterhin keine Größe angehakt, und der Versand
  verhält sich genau wie vor der Umstellung — die bewusst leere Auswahl
  wird weder in „nie konfiguriert" umgedeutet noch mit allen Größen
  aufgefüllt.
  - Test: Kern-Test mit explizit leerer Auswahl (`[]`) — der Auflöser gibt
    exakt dasselbe zurück wie vor dieser Lieferung (heute: `None`, also
    kein Filter — dieses Verhalten wird NICHT geändert, siehe
    `compare_metric_ids.py:114-115`); Migrations-Test: eine leere Auswahl
    bleibt leer und wird nicht entfernt; Frontend-Test: leere Auswahl
    bleibt vom fehlenden Feld unterscheidbar (#1191).

- **AC-4:** Given ein Vergleich wurde vor dieser Umstellung angelegt und
  seine Metrik-Auswahl liegt weiterhin im alten Speicherformat vor / When
  der Nutzer ihn im Editor öffnet oder eine Mail für ihn ausgelöst wird /
  Then zeigt der Editor dieselbe Auswahl und die Mail dieselben Zeilen wie
  vor der Umstellung — unabhängig davon, ob er die Auswahl später erneut
  speichert.
  - Test: Kern-Test des Auflösers ausschließlich mit Altformat-Einträgen
    (Zeichenketten) — Ergebnis identisch zum heutigen Verhalten.

- **AC-5:** Given eine gespeicherte Auswahl enthält sowohl Einträge im
  alten als auch im neuen Format (etwa weil ein Browser-Tab während der
  Umstellung offen geblieben ist) / When eine Mail für diesen Vergleich
  ausgelöst wird / Then erscheinen alle gültigen Größen als Zeilen in der
  Mail, und der Versand bricht nicht ab.
  - Test: Kern-Test des Auflösers mit einer gemischten Liste (Zeichenkette
    und Objekt im selben Array) — kein Fehler, alle gültigen Elemente
    aufgelöst.

- **AC-6:** Given ein bestehender Vergleich hat Höchst-, Tiefst- und
  gefühlte Tiefsttemperatur ausgewählt, im alten Speicherformat / When das
  Migrationsskript im Ausführungsmodus über den Datenbestand läuft / Then
  liegen danach alle drei Größen im neuen Format vor, keine ist
  verschwunden oder mit einer anderen verschmolzen, und eine Tour (kein
  Vergleich) im selben Datenbestand bleibt unverändert.
  - Test: Migrations-Test mit echtem Dateisystem-Root (`tmp_path`), echtem
    Subprozessaufruf des Skripts — vor/nach-Vergleich der drei Größen plus
    einer unveränderten Tour-Datei.

- **AC-7:** Given das Migrationsskript wurde bereits einmal im
  Ausführungsmodus gegen einen Datenbestand gelaufen / When es ein
  zweites Mal läuft / Then ändert es nichts mehr, meldet einen leeren
  Plan, und alle anderen Felder des Vergleichs (z. B. Orte, Empfänger,
  Alarmschwellen) sind unverändert erhalten; vor dem ersten
  Ausführungslauf existiert eine Sicherung des vorherigen Zustands.
  - Test: Migrations-Test — zweiter Lauf über bereits migrierte Daten
    ergibt leeren Plan/Exit 0; Sicherungsdatei enthält nachweislich den
    Vorzustand; ein zusätzliches, dem Skript unbekanntes Feld im
    Vergleich bleibt nach der Migration erhalten.

- **AC-8:** Given ein Vergleich mit mindestens drei Orten und einer
  festen Metrik-Auswahl / When dieselbe Mail vor und nach der Umstellung
  erzeugt und an ein Test-Postfach zugestellt wird / Then stimmen beide
  Mails Zahl für Zahl überein — gleiche Zeilen, gleiche Werte, gleiche
  Reihenfolge.
  - Test: echte, zugestellte Staging-Mail über das Test-Postfach, Auswahl
    unverändert vor/nach; `email_spec_validator.py` Exit 0 auf beiden
    Mails.

- **AC-9:** Given ein Nutzer bearbeitet die Metrik-Auswahl eines
  bestehenden Vergleichs oder legt einen neuen Vergleich mit einer
  Metrik-Auswahl an / When er speichert / Then wird die Auswahl ab dieser
  Lieferung ausschließlich im neuen Speicherformat abgelegt — sowohl beim
  Bearbeiten als auch bei der Neuanlage.
  - Test: Frontend-Kern-Test beider Schreibstellen (Edit-Payload und
    Neuanlage-Payload) — der gebaute Payload enthält für jede gewählte
    Größe ein Objekt mit `metric_id`/`aggregation`, keine Zeichenkette
    mehr.

- **AC-10:** Given im Vergleichs-Katalog würde künftig eine zweite Zeile
  dieselbe Größe-Auswertung-Kombination tragen wie eine bereits
  bestehende Zeile / When die Test-Suite läuft / Then schlägt ein Test
  sichtbar fehl, statt dass beide Zeilen unbemerkt auf denselben
  Auswahl-Eintrag kollidieren.
  - Test: der Eindeutigkeits-Wächter wird künstlich mit einer Katalog-
    Kopie geprüft, die ein Paar dupliziert (Wirkungsnachweis) — der Test
    muss dann tatsächlich anschlagen.

- **AC-11:** Given ein Vergleich, für den Abweichungs-Alarme eingerichtet
  sind und dessen Metrik-Auswahl umgestellt wurde / When der Alarm-Pfad
  für diesen Vergleich läuft / Then überwacht er genau dieselben Größen
  wie vor der Umstellung — keine Größe fällt aus der Überwachung heraus.
  - Test: Kern-Test des Alarm-Lesers mit derselben Auswahl einmal im alten
    und einmal im neuen Format — beide ergeben identisch überwachte Größen.
  - Nachgezogen 2026-07-26: die Spec nannte diesen zweiten, unabhängigen
    Leser (`compare_alert.py::_display_config_from_active_metrics`) als
    Änderungsstelle, aber kein AC prüfte ihn. Ohne AC wäre ein stiller
    Verlust der Alarm-Größen möglich gewesen, ohne dass ein Test rot wird.

- **AC-12:** Given ein Vergleich, dessen Metrik-Auswahl bereits umgestellt
  ist / When der Nutzer einen völlig anderen Reiter bearbeitet (etwa
  Versandzeiten oder Empfänger) und speichert / Then ist seine
  Metrik-Auswahl danach unverändert vorhanden — sie wird nicht beschädigt,
  nicht geleert und nicht doppelt umgewandelt.
  - Test: Frontend-Kern-Test des Speicher-Payloads ohne Metrik-Bearbeitung
    (Bestandsrückfall-Pfad) über ein bereits umgestelltes Preset — die
    Auswahl im gebauten Payload entspricht exakt der gespeicherten.
  - Nachgezogen 2026-07-26 aus dem RED-Befund: `buildHubPutPayload()`
    (`compareHubWizardBridge.ts:115`) reicht bei unverändertem
    Metrik-Reiter den rohen gespeicherten Wert weiter. Das ist ein echter
    Datenverlust-Pfad der Klasse #102, nicht nur ein Typfehler.

## Nicht in dieser Lieferung

- Kein Rückbau von `_SUMMARY_KEY_TO_CATALOG_ID` in `compare_alert.py` —
  anderer Namensraum (Alarm-Engine-IDs), andere Zuständigkeit (S3/S4).
- Keine Oberflächenänderung am Ortsvergleich-Editor — dieselbe Bedienung,
  nur ein anderes Speicherformat im Hintergrund.
- Keine wählbare Auswertung (min/max/avg als Nutzerwahl) — das ist S4
  (#1357). „Temperatur max"/„Temperatur min" bleiben zwei feste,
  vorgegebene Einträge.
- Kein Umbau von `CV2_METRICS`/`HOUR_METRICS` in `compare_html.py` — S3/S5.
- Keine Go-Änderung — `display_config` bleibt in Go untypisiert, der
  JSON-Blob wird weiterhin blind durchgereicht.
- `corridorEditorState.ts` bleibt unangetastet — es ist reiner Aufrufer der
  einen Übersetzungsstelle in `compareEditorSave.ts`, keine eigene
  Schreibstelle.

## Betriebsablauf

Reihenfolge ist zwingend: **erst Deploy, dann Migration je Host.**
`deploy-gregor-prod.sh` bringt Go, Python und Frontend im selben Lauf auf
denselben Commit — es gibt keinen Zwischenzustand „schreibt neu, liest
alt". Zu sequenzieren ist nur die Migration selbst:

```bash
uv run python3 scripts/migrate_1373_compare_active_metrics_format.py --root data/users
uv run python3 scripts/migrate_1373_compare_active_metrics_format.py --root data/users --execute
```

Immer zuerst den Trockenlauf (Dry-Run, Default) lesen, dann `--execute`.
Läuft pro Host (zuerst Staging, danach Produktion), als User
`claude-gregor`. Manueller Ops-Schritt, kein Teil von
`deploy-gregor-prod.sh` — Vorbild und Detailform: Abschnitt
„Null-Listenfelder in Trip-/Compare-Preset-Dateien heilen (#1244)" in
`docs/reference/operations_playbook.md:195-251`. Tolerantes Lesen bleibt
dauerhaft im Code (nicht „bis migriert"), weil eine stehengebliebene
Browser-Sitzung jederzeit wieder Altformat schreiben kann (s. Restrisiko
R1).

## Bekannte Restrisiken

- **R1 — Mischlisten durch stehengebliebene Browser-Sitzungen.** Nach
  Deploy und Migration liefert der Server das Neuformat; ein im Browser
  noch geladener alter Code prüft nur `Array.isArray(...)` und reicht
  Neuformat-Objekte unverändert als `activeMetricKeys` durch — jede
  UI-Prüfung wie `.includes("temp_max_c")` schlägt dann fehl, die
  gespeicherte Auswahl zeigt sich als „nichts ausgewählt". Klickt der
  Nutzer danach eine Metrik an, entsteht eine Mischliste. Das ist nicht
  verhinderbar (der Browser lädt den neuen Code erst beim nächsten
  vollständigen Reload), aber durch die pro-Element-Auflösung (AC-5)
  abgefedert: keine verlorene Zeile, kein Absturz. Heilt sich beim
  nächsten Laden mit neuem Code selbst.
- **R2 — Rollback nach Migrationsstart ist nicht gefahrlos.** Die heutige
  `resolve_enabled_metrics()` prüft Mitgliedschaft eines Elements in einem
  Dict (`m not in FRONTEND_TO_RENDERER_METRIC_ID`). Kommt ein Element als
  Neuformat-Objekt herein und wurde der Code-Commit dieser Lieferung
  zurückgerollt, wirft Python `TypeError: unhashable type: 'dict'` — der
  komplette Vergleichs-Mailversand für dieses Preset bricht ab, nicht nur
  eine Metrik fällt weg. Betriebswissen für künftige Deploys: nach
  Migrationsstart ist ein Zurückrollen des Codes nicht mehr gefahrlos.

## Verifikationsanker

Gemessen am Produktionsbestand (2026-07-26): **3 Produktions-Vergleiche**
mit sowohl `temp_max_c` als auch `temp_min_c` in der Auswahl, **1
Produktions-Vergleich** mit `wind_chill_min_c`. Die Migration darf keinen
dieser vier Fälle verlieren oder zusammenfallen lassen — genau das ist die
Verschmelzungsfalle aus AC-1/AC-6, weil `temp_max_c` und `temp_min_c` auf
dieselbe `metric_id` (`temperature`) abbilden und sich nur in der
`aggregation` unterscheiden.

## Known Limitations

- `hourly_metrics` (Stundenverlauf-Auswahl, `compare_hourly_metric_ids.py`)
  ist ein eigenständiges Vokabular und wird von dieser Spec nicht
  verändert.
- Die Feststellung aus Scheibe A zu `resolve_enabled_metrics()` und der
  Sonderbehandlung von `[]` vs. `None` im Render-Pfad der Übersichtstabelle
  bleibt Zuständigkeit von #1366 (S3) — diese Lieferung ändert daran
  nichts, macht das bestehende Verhalten für beide Speicherformate nur
  gleichermaßen erreichbar.
- `_SUMMARY_KEY_TO_CATALOG_ID` in `compare_alert.py` bleibt als eigene,
  bewusst andersartige Übersetzungstabelle stehen (anderer Namensraum,
  Alarm-Engine-IDs) — kein Zusammenlegen mit dem neuen Katalog-Index.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ändert das Speicherformat eines bestehenden Feldes
  (`display_config.active_metrics`), setzt dabei aber ein bereits
  etabliertes Muster fort (toleranter Leser, strenger Schreiber;
  Read-Modify-Write-Migration mit Sicherung — Vorbilder `migrate_1262_*`,
  `migrate_1361_*`). Keine neue Entscheidungsfläche (kein neuer Kanal, kein
  neuer Provider, kein neues Auth-Modell) — daher kein eigenes ADR nötig.

## Changelog

- 2026-07-26: Initial spec created (S2 Scheibe B von Epic #1372, Ticket
  #1373), auf Basis der Analyse in
  `docs/context/feat-1373-s2b-metrik-speicherformat.md`. Gegenüber der
  ursprünglichen Skizze in `feat_1373_s2_ein_katalog.md` (Abschnitt
  „Scheibe B") vier Korrekturen übernommen: `compare_alert.py` braucht nur
  Normalisierung, keinen Rückbau; `corridorEditorState.ts` bleibt
  unangetastet (ist Aufrufer, keine eigene Schreibstelle); nur drei
  zwingende Frontend-Änderungsstellen statt vier; Migrations-Vorbild ist
  `migrate_1361_*`, nicht `migrate_1191_*`/`migrate_1360_*`. Zwei neue
  Restrisiken (R1 Mischlisten durch Alt-Sitzungen, R2 Rollback-Absturz)
  dokumentiert. Zehn AC in Nutzersprache formuliert, jede an einen der
  neun härtesten Prüffälle aus der Analyse gebunden.
