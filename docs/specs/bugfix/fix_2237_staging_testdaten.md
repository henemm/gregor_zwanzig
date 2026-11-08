---
entity_id: fix_2237_staging_testdaten
type: bugfix
created: 2026-11-03
updated: 2026-11-08
status: implemented
version: "1.0"
workflow: fix-2237-staging-testdaten
tags: [staging, sweep, testdaten, mandantentrennung, infra]
---

# Staging-Testdaten bereinigen und Ansammlung dauerhaft verhindern (#2237)

OPENSPEC_ACTIVE_WORKFLOW=fix-2237-staging-testdaten

## Approval

- [ ] Approved

## Purpose

Das nächtliche Sweep-Skript der Staging-Umgebung meldet täglich "OK", räumt aber einen toten Datenbaum auf, nicht den, den der Staging-Dienst benutzt. Dadurch sammeln sich Testdaten an (122 Nutzerordner, 663 Sperrdateien, 130 Snapshot-Dateien). Diese Spec korrigiert den Sweep, schließt zwei Code-Lücken (Preset-Löschen hinterlässt Snapshots, Löschen hinterlässt `.lock`-Dateien) und definiert die einmalige Daten-Bereinigung.

## Source

- **File:** `/home/hem/henemm-infra/scripts/gregor-staging-sweep.sh` (Repo `henemm-infra`)
- **Identifier:** Variable `R=` (Z.25), `find`-Löschblock (Z.51-62)
- **Weitere Quellen:** `internal/store/compare_preset.go` (`DeleteComparePreset`, Z.299), `internal/store/trip.go` (`DeleteTrip`, Z.331), `internal/store/location.go` (`DeleteLocation`, Z.114), `internal/store/briefing_lock.go` (`briefingLockPath`, Z.68), `src/services/compare_weather_snapshot.py` (`CompareWeatherSnapshotService`)

> **Schicht-Hinweis:** Go-API (`internal/store/`) für Löschpfade, Python-Core (`src/services/`) für den Snapshot-Dienst, Infra-Repo `henemm-infra` für den Sweep. Kein Frontend betroffen. Kein Trip/Compare-Pendant-Problem: Trip- und Preset-Löschen liegen beide im selben Store und werden gleichartig erweitert.

## Messbasis (Stand 2026-11-03, aus `docs/context/fix-2237-staging-testdaten.md`)

Echter Staging-Baum: `/var/lib/gregor-staging/users` (`GZ_DATA_DIR` des Dienstes, nur per `sudo -n -u claude-gregor` lesbar). Sweep-Pfad dagegen: `/home/hem/gregor_zwanzig_staging/data` mit nur 3 Nutzern.

| Messwert | Wert |
|---|---|
| Nutzerordner | 122 |
| Briefing-JSONs / davon älter als 12 h | 84 / 82 |
| Location-JSONs | 83 |
| `.lock`-Dateien | 663 (hunderte in `default/briefings`) |
| `compare_weather_snapshots/`-Dateien | 130 |
| `telegram_chat_id` doppelt | 2 Nutzer teilen `-5369694790` |
| `mail_to=gregor-test@henemm.com` / `gregor-staging@henemm.com` | 5 / 2 Konten |

Hinweis zur Entstehung der Spec: Der Spec-Schreiber hatte kein Shell-Werkzeug. Alle Zahlen oben stammen aus der Analyse-Datei; die in Entscheidung 4/5 geforderten Neumessungen (Konten-Namensmuster, Ladetest `e2e-cockpit-test`) sind deshalb als verbindliche **erste Schritte der Implementierung** festgelegt (siehe unten), nicht als bereits gemessen behauptet.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `/var/lib/gregor-staging` | Datenbaum | echter Staging-Datenpfad (`GZ_DATA_DIR`), neues Sweep-Ziel |
| `validator-issue110` | Fixture-Nutzer | Gate-Fixture des Prod-Deploys, nie löschen |
| `e2e-loc-innsbruck/stubai/zillertal` | Seed-Orte | nie löschen |
| ADR-0031 / ADR-0083 | Entscheidung | dateibasierte Persistenz; Go und Python teilen sich Schreibzugriff über `<id>.json.lock` |
| ADR-0101 | Entscheidung | Read-Modify-Write mit Merge bei Konten-Änderung |
| Issue #2173 | geschlossen (laut Epic-Stand; Code-Ursache für B1-23/C3-65) | Doppelbelegung von chat_id/mail_to ist nur noch Datenrest |
| `henemm-infra` Cron 04:30 (`sudo -u claude-gregor bash -s`) | Betrieb | Aufrufer des Sweeps |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `/home/hem/henemm-infra/scripts/gregor-staging-sweep.sh` | MODIFY | `R` = `/var/lib/gregor-staging`; Plausibilitätsprüfung; `--dry-run`; nimmt `.json.bak-*` und verwaiste `.json.lock` mit |
| `/home/hem/henemm-infra/tests/test_gregor_staging_sweep.sh` | CREATE | Shell-Test gegen temporären Baum |
| `internal/store/compare_preset.go` | MODIFY | `DeleteComparePreset` entfernt zusätzlich Snapshots dieses Nutzers zum Preset und die `.lock`-Datei |
| `internal/store/trip.go` | MODIFY | `DeleteTrip` entfernt `<id>.json.lock` mit |
| `internal/store/compare_preset_cleanup_test.go` | CREATE | Go-Tests mit echtem Dateisystem (`t.TempDir`), Zwei-Nutzer-Test |
| `src/services/compare_weather_snapshot.py` | MODIFY | `delete(preset_id)` für alle Snapshots eines Presets des eigenen Nutzers |
| `tests/unit/test_compare_weather_snapshot_delete.py` | CREATE | Zwei-Nutzer-Test des Python-Dienstes |
| Staging-Daten (einmalig, per Skript, Backup vorab) | DATA | Preset verlegen, Test-Konten, Locks, Snapshots, Alt-Briefings |

## Estimated Scope

- Files: 8 (2 Repos), davon 3 Test-Dateien
- LoC: +~150 / -~10
- Effort: medium, Risiko MEDIUM (Sweep löscht erstmals im echten Baum)

## Implementation Details

### 1. Sweep (Repo `henemm-infra`)

- `R=/var/lib/gregor-staging`; Überschreiben nur über die Umgebungsvariable `GZ_SWEEP_DATA_DIR` (damit der Shell-Test einen temporären Baum nutzen kann), Standard bleibt der echte Pfad.
- Plausibilitätsprüfung vor jeder Aktion: `$R/users` existiert und enthält mindestens `GZ_SWEEP_MIN_USERS` (Standard 20) Nutzerordner. Sonst Meldung auf stderr, Exit != 0, **keine** "OK"-Zeile, **kein** Heartbeat (Readiness-Regel). Der Test-Schwellwert 20 liegt weit unter 122 und weit über dem alten Fehlpfad mit 3.
- `--dry-run`: führt die Plausibilitätsprüfung aus, listet alle Löschkandidaten per `find ... -print`, löscht nichts, legt kein Backup an, gibt keine "OK"-Zeile aus, die als Lauf zählt (Ausgabe `DRY-RUN: N Kandidaten`).
- Backup-first bleibt unverändert (tar des `users`-Baums, Retention 7).
- Zusätzliche Löschkandidaten (>12 h, gleiche Schutzliste): `briefings/*.json.bak-*` und `locations/*.json.bak-*`; **verwaiste** `briefings/*.json.lock` (keine zugehörige `.json` im selben Ordner). Eine `.lock` mit vorhandener `.json` wird nie angefasst.
- Schutzliste (nie löschen): Pfade unter `*/validator-issue110/*`; Orte `e2e-loc-innsbruck.json`, `e2e-loc-stubai.json`, `e2e-loc-zillertal.json`; `user.json` und alle Konten-Dateien (der Sweep berührt nur `locations/`, `briefings/`, `trips/`, `compare_weather_snapshots/` nicht, siehe Punkt 2).
- `compare_weather_snapshots/*.json` älter als 12 h werden vom Sweep mitgenommen (Auffangnetz für Snapshots, deren Preset ohne den neuen Löschpfad verschwand), ausgenommen unter `validator-issue110`.
- Infra-Teil gehört in das Repo `henemm-infra` (Issue dort; die Spec legt es nicht an). Commit-Verweis auf #2237.

### 2. Code (Repo gregor_zwanzig)

ADR-konforme Variante: **Go räumt die Dateien des eigenen Nutzers direkt ab**, ohne Aufruf in den Python-Core. Begründung: ADR-0031/ADR-0083 erlauben beiden Prozessen Schreibzugriff unter `data/users/<user_id>/` mit gemeinsamer Sperre; ein Go-nach-Python-Aufruf für eine reine Dateilöschung wäre ein zusätzlicher Netzwerkpfad ohne Nutzen und ein neuer Fehlerfall im Löschen. Die Mandantentrennung entsteht aus `s.UserID`: der Pfad ist `users/<s.UserID>/compare_weather_snapshots/<presetID>__*.json`, nie nutzerübergreifend.

- `DeleteComparePreset(id)`: nach erfolgreichem Entfernen von `briefings/<id>.json` (und nur dann, d.h. nicht im `kind != "vergleich"`-Frühausstieg) werden
  - alle Dateien `compare_weather_snapshots/<id>__*.json` dieses Nutzers entfernt (Muster exakt `<id>__`-Präfix; die ID ist durch `ValidEntityID` bereits segmentgeprüft, so dass `cp-1` nicht `cp-10__x` trifft), idempotent (nicht vorhanden = kein Fehler).
- Sperrdatei `briefings/<id>.json.lock`: wird **nicht** im Store-Delete entfernt (das verkürzte die Haltedauer der Sperre, ADR-0083, und ließe zwei Prozesse parallel sperren). Stattdessen neue Store-Methode `RemoveBriefingLockFile(id)`; `DeleteTripHandler` und `DeleteComparePresetHandler` rufen sie in **einer** defer-Closure **nach** `unlockB()` auf und nur, wenn das Store-Delete erfolgreich war. Die Methode entfernt die Datei nur als Waise: sie hält dabei den Prozess-Mutex des Schlüssels, bricht ab, wenn `briefings/<id>.json` existiert (deckt den `kind == "vergleich"`-Ausstieg des Trip-Pfads ab, AC-8), öffnet ohne `O_CREATE` und entfernt nur, wenn `flock(LOCK_EX|LOCK_NB)` sofort gelingt (sonst hält der Python-Kern sie, der Sweep räumt später ab). Fehler werden nur geloggt.
- `DeleteTrip(id)`: unverändert (keine eigene Lock-Entfernung mehr).
- Python `CompareWeatherSnapshotService.delete(preset_id) -> tuple[int, int]`: entfernt alle `"{preset_id}__*.json"` im Ordner des Nutzers dieser Instanz (Nutzer ist im Konstruktor fixiert), gibt `(removed, failed)` zurück (Hausnorm `run_briefing_dispatch()`): `failed` zählt je Datei einen `OSError` (bereits verschwundene Datei zählt nicht), ein Listing-Fehler zählt als 1, fehlender Ordner = `(0, 0)`, Fehler werden geloggt wie bei `save`. Er ist die Python-seitige Entsprechung für Löschpfade im Kern und bekommt den Zwei-Nutzer-Test.
- Prüfbefund `cp-21e198c1b74020dd`: im Produkt-/Testcode nirgends hart verdrahtet. Treffer nur in zwei Kommentaren (`tests/unit/test_compare_mail_validator_column_order.py:40`, `tests/unit/test_provider_registry_threadsicher.py:4`). Verlegen bricht also keinen Code.

### 3. Einmal-Bereinigung der Daten (Backup vorab, Skript im Infra-Repo, als `claude-gregor`)

Reihenfolge: (a) Backup des gesamten Baums, (b) Auflistung ohne Änderung, (c) Änderung.

1. **Validator-Preset verlegen:** `default/briefings/cp-21e198c1b74020dd.json` und die zwei `.bak-*` per `mv` nach `validator-issue110/briefings/`. Ist dort bereits eine Datei gleichen Namens, wird nicht überschrieben (Abbruch mit Meldung). Danach schützt die Schutzliste das Preset; kein Racing mit Sessions, die `default` benutzen (C3-76).
2. **C4-06:** Die vier Dateien `default/briefings/{277aa63f,38e358d0,56231a2b,67017042}.json` (Trip `E2E-1613-WC-Test`) werden einmalig sofort entfernt (der korrigierte Sweep hätte sie nach 12 h entfernt).
3. **C1-34 `e2e-cockpit-test.json`:** Erster Schritt der Umsetzung ist ein Ladetest: die Datei wird mit dem Go-Store (`LoadTrip`/`LoadComparePreset` auf einer Kopie in einem `t.TempDir`-Nutzerbaum) gelesen. Regel: lädt sie nicht oder ist leer/Müll, wird sie samt `e2e-mutation-check.json` entfernt; lädt sie, ist C1-34 als "nicht reproduzierbar, Datei ist gültiges Testobjekt der E2E-Specs (`frontend/e2e/*cockpit*`-Verweise)" im Issue dokumentiert und fällt dem 12-h-Sweep anheim. Das Ergebnis wird im Changelog dieser Spec nachgetragen.
4. **Verwaiste Locks, Alt-Briefings, Orphan-Snapshots:** erledigt der erste scharfe Sweep-Lauf nach bestandenem Trockenlauf (Abnahme: Kandidatenliste enthält keinen geschützten Pfad).
5. **Konten (B1-23, C3-65, B1-50, B1-54):**
   - B1-23/C3-65: Code-Ursache war Issue #2173 (laut Epic-Stand geschlossen, vor dem Schließen des Workflows mit `gh issue view 2173 --json state,title` zu bestätigen). Es bleibt nur Datenbereinigung.
   - **Test-Konto-Muster (verbindlich, vor Löschen zu messen):** Ein Konto gilt nur dann als Test-Konto, wenn seine Nutzer-ID mit `e2e` oder `E2E` (ohne Bindestrich, gemessen am echten Baum 2026-11-03: z. B. `e2e2017a…`, `e2eag5…`, `e2e1352a…`) beginnt UND es nicht auf der Schutzliste steht (zusätzlich geschützt: `mobile-audit`, `default`, `validator-issue110`, `tg-live-e2e`, die ebenfalls geteilte Kontaktdaten tragen). Der erste Umsetzungsschritt listet im echten Baum per `sudo -n -u claude-gregor` alle Ordner mit diesem Muster samt `mail_to` und `telegram_chat_id` (nur lesen) und hängt die Liste an Issue #2237. Konten, die das Muster nicht treffen, werden nicht gelöscht.
   - **Nie löschen:** `gregor_zwanzig_staging`, `admin`, `default`, `validator-issue110`, `tg-live-e2e`.
   - Doppelte `telegram_chat_id` (`-5369694790`): trägt eines der beiden Konten das Test-Muster, wird dieses Konto gelöscht; sonst wird das Feld beim Test-ähnlichen Konto per Read-Modify-Write mit Merge geleert. Ohne Test-Muster bei beiden Konten: keine Änderung, Befund im Issue vermerkt.
   - Geteiltes `mail_to` (`gregor-test@henemm.com` 5 Konten, `gregor-staging@henemm.com` 2 Konten): Test-Muster-Konten werden gelöscht; bei Konten ohne Muster nur das Feld `mail_to` per Merge leeren, ausgenommen `gregor_zwanzig_staging`.
   - B1-50: `gregor_zwanzig_staging` bekommt `mail_to=gregor-staging@henemm.com` per Merge, sobald nach der Bereinigung kein anderes Konto diese Adresse mehr trägt (Messung davor und danach). `telegram_chat_id` wird nur gesetzt, wenn der Wert danach in keinem anderen Konto vorkommt; sonst bleibt das Feld leer.
   - B1-54: Test-Presets (Dateien in `gregor_zwanzig_staging/briefings/` mit Test-Namensmuster oder älter als 12 h) werden gelöscht, reguläre Presets des Kontos bleiben.

## Test Plan

### Automated Tests (TDD RED)

Test-Politik laut CLAUDE.md: echtes Dateisystem, kein Mock-Theater, keine Dateiinhalt-Checks als Verhaltensnachweis.

- [ ] Go `TestDeleteComparePreset_RaeumtSnapshotsAuf`: GIVEN Nutzer A mit Preset `cp-a`, Snapshots `cp-a__loc1.json`, `cp-a__loc2.json` und einem fremden Snapshot `cp-ab__loc1.json` WHEN `DeleteComparePreset("cp-a")` THEN Preset und beide Snapshots sind weg, `cp-ab__loc1.json` bleibt.
- [ ] Go `TestDeleteComparePreset_ZweiNutzer`: GIVEN Nutzer A und B, beide mit Preset-ID `cp-x` und Snapshots `cp-x__loc1.json` WHEN der Store für A `cp-x` löscht THEN Preset und Snapshot von B existieren unverändert (Inhalt gleich).
- [ ] Go `TestDeleteComparePreset_KindGuardLaesstSnapshotsStehen`: GIVEN Datei `cp-t.json` mit `kind:"route"` und Snapshot `cp-t__loc.json` WHEN `DeleteComparePreset("cp-t")` THEN nichts wird entfernt.
- [ ] Go `TestDeleteComparePreset_Idempotent`: zweites Löschen derselben ID ist fehlerfrei.
- [ ] Go `TestRemoveBriefingLockFile_*` (Store, echtes Dateisystem): verwaiste Sperrdatei wird entfernt, die gleichnamige von Nutzer B bleibt; bei vorhandener `.json` bleibt sie; bei von außen gehaltenem flock bleibt sie; bei gehaltenem Prozess-Mutex wartet das Entfernen bis zur Freigabe; ungültige ID (`../evil`) und leerer Nutzer entfernen nichts; fehlt sie, wird keine angelegt.
- [ ] Go Handler `TestDeleteComparePresetHandler_404LaesstSperrdateiStehen`: kein erfolgreiches Löschen (404) ⇒ Sperrdatei bleibt.
- [ ] Go Handler `TestDeleteTripHandler_RaeumtEigeneSperrdateiAb_ZweiNutzer` / `TestDeleteComparePresetHandler_RaeumtEigeneSperrdateiAb_ZweiNutzer`: echtes `DELETE` als A entfernt `.json` und `.lock` von A; `.json` und `.lock` von B mit gleicher ID bleiben byte-identisch.
- [ ] Go Handler `TestDeleteTripHandler_VergleichBleibtSamtSperrdatei`: Ortsvergleich-Preset über `DELETE /api/trips/{id}` ⇒ `.json` und `.lock` bleiben (AC-8).
- [ ] Go `TestSchreibsperre_HaltedauerJeStelle_BisZurAntwortBelegt` (Bestand) bleibt grün: Sperre ist bei der Antwort noch belegt.
- [ ] Python `test_delete_entfernt_nur_eigene_preset_snapshots`: GIVEN `CompareWeatherSnapshotService("user-a")` und `("user-b")` mit gleicher Preset-ID und je zwei Snapshots (echte `save`-Aufrufe in einem temporären `GZ_DATA_DIR`) WHEN `delete(preset_id)` für A THEN Rückgabe `(2, 0)`, A hat keinen Snapshot, B hat beide, `load` für B liefert weiter je einen Punkt.
- [ ] Python `test_delete_ohne_ordner_liefert_null`: Rückgabe `(0, 0)`.
- [ ] Python `test_delete_meldet_nicht_loeschbaren_eintrag_als_fehler`: Verzeichnis `cp-1__kaputt.json` (echter `IsADirectoryError`) ⇒ Rückgabe `(1, 1)`.
- [ ] Python `test_delete_meldet_nicht_lesbaren_ordner_als_fehler`: Ordner ohne Leserecht (echtes `PermissionError`) ⇒ Rückgabe `(0, 1)`.
- [ ] Shell `test_gregor_staging_sweep.sh` gegen temporären Baum (`GZ_SWEEP_DATA_DIR`, `GZ_SWEEP_MIN_USERS=2`, Backup-Verzeichnis ebenfalls temporär): (1) Fixture-Nutzer `validator-issue110` mit alten Dateien bleibt vollständig; (2) alte Briefings, `.bak-*`, verwaiste `.lock` und alte Snapshots eines anderen Nutzers sind weg; (3) frische Dateien (<12 h) bleiben; (4) `.lock` mit zugehöriger `.json` bleibt; (5) Seed-Orte und `user.json` bleiben; (6) falscher Pfad oder zu wenige Nutzerordner ⇒ Exit != 0 und keine "OK"-Zeile in der Ausgabe; (7) `--dry-run` löscht nichts und listet Kandidaten.
- [ ] Abnahme am echten Baum: Trockenlauf gegen `/var/lib/gregor-staging` zeigt keinen Pfad unter `validator-issue110` und keinen Seed-Ort; erst danach scharfer Lauf mit Backup.

## Acceptance Criteria

- **AC-1:** Given der Staging-Datenbaum `/var/lib/gregor-staging` mit mehr als 20 Nutzerordnern / When das Sweep-Skript läuft / Then bearbeitet es genau diesen Baum (sichtbar daran, dass abgestandene Testdateien dort verschwinden und das Backup `nightly-sweep-*.tar.gz` alle Nutzerordner enthält).
  - Test: Shell-Test gegen temporären Baum mit mehreren Nutzern; nach dem Lauf fehlen die alten Dateien, das Backup enthält alle Nutzerordner.
- **AC-2:** Given ein Sweep-Pfad, der nicht existiert oder weniger Nutzerordner als die Mindestzahl enthält / When das Sweep-Skript läuft / Then endet es mit Exit-Code ungleich 0, gibt keine "OK"-Zeile aus und feuert keinen Heartbeat.
  - Test: Shell-Test mit leerem Verzeichnis und mit nicht vorhandenem Pfad; Exit-Code und Ausgabe werden geprüft.
- **AC-3:** Given Daten des Fixture-Nutzers `validator-issue110`, der Seed-Orte und aller `user.json`, auch wenn sie älter als 12 Stunden sind / When der Sweep scharf läuft / Then bleiben alle diese Dateien unverändert erhalten.
  - Test: Shell-Test mit alten Fixture-Dateien; Dateiliste und Inhalte vorher/nachher gleich.
- **AC-4:** Given abgestandene `.json.bak-*`-Dateien, verwaiste `.json.lock`-Dateien und alte Compare-Snapshots sowie eine `.lock` mit vorhandener `.json` / When der Sweep scharf läuft / Then sind die abgestandenen und verwaisten Dateien entfernt und die `.lock` mit zugehöriger `.json` bleibt.
  - Test: Shell-Test; Dateibaum nach dem Lauf wird gegen die erwartete Liste verglichen.
- **AC-5:** Given der Aufruf des Sweeps mit `--dry-run` / When er läuft / Then listet er die Löschkandidaten, löscht nichts und legt kein Backup an.
  - Test: Shell-Test; Baum und Backup-Verzeichnis sind nach dem Lauf unverändert, Ausgabe nennt die Kandidaten.
- **AC-6:** Given Nutzer A hat ein Ortsvergleich-Preset mit gespeicherten Snapshots und einer Sperrdatei / When Nutzer A das Preset löscht / Then sind Preset, alle seine Snapshots und die Sperrdatei vom Datenträger verschwunden, Snapshots anderer Presets von A bleiben.
  - Test: Go-Test mit echtem Dateisystem in `t.TempDir`, inklusive Preset `cp-ab`, das vom Löschen von `cp-a` nicht berührt werden darf.
- **AC-7:** Given Nutzer A und Nutzer B besitzen je ein Preset mit derselben ID und Snapshots / When Nutzer A sein Preset löscht / Then bleiben Preset, Snapshots und Sperrdatei von Nutzer B unverändert.
  - Test: Zwei-Nutzer-Test im Go-Store und im Python-Dienst (`CompareWeatherSnapshotService.delete`), Prüfung am Dateibaum und per `load` für B.
- **AC-8:** Given ein Trip (Briefing) mit Sperrdatei / When der Trip gelöscht wird / Then ist auch die Sperrdatei weg; wird stattdessen ein Ortsvergleich-Preset über den Trip-Löschpfad angefragt, bleiben Datei und Sperrdatei bestehen.
  - Test: Go-Test mit echtem Dateisystem; zusätzlich Zwei-Nutzer-Variante mit gleicher Trip-ID.
- **AC-9:** Given das Preset `cp-21e198c1b74020dd` mit seinen zwei Sicherungsdateien lag unter `default/briefings` / When die Daten-Bereinigung gelaufen ist / Then liegen alle drei Dateien unter `validator-issue110/briefings`, unter `default/briefings` liegt keine davon mehr, und ein anschließender Trockenlauf des Sweeps listet sie nicht als Kandidaten.
  - Test: Dateibaum-Messung per `sudo -n -u claude-gregor` vor und nach dem Schritt; Trockenlauf-Ausgabe.
- **AC-10:** Given die vier Dateien `E2E-1613-WC-Test` unter `default/briefings` / When die Daten-Bereinigung gelaufen ist / Then existiert keine Datei mit diesem Trip-Namen mehr im Baum.
  - Test: Suche nach dem Namen im echten Baum liefert keinen Treffer.
- **AC-11:** Given die Konten im echten Baum / When die Konten-Bereinigung gelaufen ist / Then ist keine `telegram_chat_id` und keine `mail_to`-Adresse mehr von zwei Konten gleichzeitig belegt, die Konten `gregor_zwanzig_staging`, `admin`, `default`, `validator-issue110` und `tg-live-e2e` existieren weiterhin, und `gregor_zwanzig_staging` (nur sofern im echten Baum vorhanden; Messung 2026-11-03: existiert dort nicht, B1-50/B1-54 entfallen) hat `mail_to=gregor-staging@henemm.com`.
  - Test: Auswertung aller `user.json` per `sudo -n -u claude-gregor` (Zählen von Duplikaten, Existenz der Schutz-Konten); es werden nur Konten gelöscht, die das Muster `e2e`/`E2E` tragen, und die vorab im Issue dokumentierte Liste entspricht der gelöschten Menge.
- **AC-12:** Given die Datei `default/briefings/e2e-cockpit-test.json` / When der Ladetest mit dem Go-Store ausgeführt wurde / Then ist sie entweder entfernt (nicht ladbar) oder im Issue als gültiges, vom 12-h-Sweep abgeräumtes Testobjekt dokumentiert; das Ergebnis steht im Changelog dieser Spec.
  - Test: Ladeversuch auf einer Kopie im temporären Nutzerbaum; Ergebnis wird protokolliert.

## Known Limitations

- Sperrdateien (`.lock`) von Briefings, deren `.json` noch existiert, bleiben absichtlich bestehen (sie sind Betriebsmittel, ADR-0083); der Sweep entfernt nur verwaiste.
- Snapshots von Presets, die über einen Weg außerhalb von `DeleteComparePreset` verschwinden (z.B. Konto-Löschung auf Dateiebene), räumt nur der Sweep nach 12 h ab.
- Produktionsdaten sind nicht betroffen; alle Datenschritte gelten ausschließlich für Staging.
- Die Konten-Bereinigung löscht nichts außerhalb des Musters `e2e`/`E2E`; weitere Altkonten bleiben bewusst bestehen.
- Risiken: Der Sweep löscht erstmals im echten Baum. Gegenmaßnahmen: Backup-first, Trockenlauf-Abnahme vor scharfem Lauf, Schutzliste, Plausibilitätsprüfung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0031, ADR-0083 und ADR-0101 gelten unverändert)
- **Rationale:** Go räumt Dateien im eigenen Nutzerordner ab; das ist von ADR-0031/ADR-0083 abgedeckt und weicht keiner Entscheidung ab. Der Sweep-Pfad ist Betrieb, keine Architekturentscheidung.

## Changelog

- 2026-11-03: Initial spec created (Workflow fix-2237-staging-testdaten)
- 2026-11-03 (Umsetzung): AC-12 Ladetest mit Go-Store: `e2e-cockpit-test.json` lädt (kind=route, 3 Etappen) = gültiges Testobjekt, nicht reproduzierbar, fällt dem 12-h-Sweep anheim; `e2e-mutation-check.json` lädt (Name "x", 0 Etappen), wird ebenfalls vom Sweep abgeräumt.
- 2026-11-03 (Umsetzung): Konto `gregor_zwanzig_staging` existiert im echten Baum nicht; B1-50/B1-54 entfallen, AC-11 entsprechend präzisiert. Backup `cleanup-2237-<heute>` ohne `*.json.lock` (für `claude-gregor` unlesbar). Gelöscht wurden 6 e2e-Konten mit doppelter mail_to/telegram_chat_id (Liste im Issue #2237). Infra-Teil: henemm/henemm-infra#377.
- 2026-11-03 (Validierungs-Fix): Sperrdatei-Entfernung aus `DeleteTrip`/`DeleteComparePreset` herausgenommen (verkürzte die Haltedauer, `TestSchreibsperre_HaltedauerJeStelle_BisZurAntwortBelegt` rot) und als `Store.RemoveBriefingLockFile` nach dem Freigeben der Sperre in die beiden Delete-Handler verlegt (betrifft zusätzlich `internal/handler/trip.go`, `internal/handler/compare_preset.go`, `internal/store/briefing_lock.go`, neu `internal/handler/delete_lock_cleanup_test.go`, Registereintrag in `internal/store/user_scope_guard_test.go`; `internal/store/trip.go` ist damit gegenüber dem Stand vor #2237 unverändert). Python `delete()` liefert jetzt `(removed, failed)` statt `int` (Wächter `partial_success_blind`).
- 2026-11-08 (Abnahme Betrieb): Nacht-Sweep meldet seit 5.11. jede Nacht `OK` mit 123 Nutzerordnern; `nightly-sweep-20261108-043001.tar.gz` enthält alle 123 Ordner = Live-Baum (AC-1). Keine doppelte `mail_to`/`telegram_chat_id`, Schutz-Konten vorhanden (AC-11), kein `E2E-1613-WC-Test` mehr im Baum (AC-10). AC-9: Preset samt zwei `.bak-*` liegt unter `validator-issue110` und überstand vier scharfe Läufe; der geforderte Trockenlauf war aus der Claude-Sitzung nicht ausführbar (Sitzungssperre gegen `sudo … bash`), die scharfen Läufe belegen dieselbe Aussage. Befund: Am 6.11. und 7.11. legten Sitzungen das Preset erneut unter `default` an (Ursache: veraltete Sitzungs-Notiz verortete es dort, korrigiert); der Sweep räumte es jeweils nach 12 h ab, die Kopie unter `validator-issue110` blieb unberührt.
