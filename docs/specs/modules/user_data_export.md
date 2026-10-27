---
entity_id: user_data_export
type: module
created: 2026-09-09
updated: 2026-09-09
status: draft
version: "1.0"
tags: [go, auth, dsgvo, datenexport, issue-2270]
---

# Datenexport für Nutzer (DSGVO Art. 20)

## Approval

- [ ] Approved

## Purpose

Der angemeldete Nutzer kann seine eigenen Daten als ZIP-Archiv herunterladen (Art. 20 DSGVO) — über einen neuen, geschützten Endpoint `GET /api/auth/export` und einen eigenen Knopf im Konto-Bereich der Account-Seite. Der Export ist die lesende Gegenrichtung zur bestehenden Account-Löschung (`docs/specs/modules/account_deletion.md`).

## Source

- **File:** `internal/store/user.go`
- **Identifier:** `func (s *Store) ExportUser(id string, w io.Writer) error` — die Signatur folgt der Streaming-Entscheidung aus Implementation Details: Nutzdaten werden direkt in einen `io.Writer` (die HTTP-Antwort) geschrieben, nicht gepuffert zurückgegeben.

> **Schicht-Hinweis:** Store-Methode und Handler liegen in der Go-API (`internal/`), nicht im Python-Core. Der Python-Core schreibt zwar einen Teil der exportierten Dateien (`src/services/*.py`), der Export selbst liest nur den gemeinsamen Datenbaum unter `<GZ_DATA_DIR>/users/<id>/` — dieselbe Prämisse, auf der auch `DeleteUser` bereits beruht.

## Estimated Scope

- **LoC:** ~300–470 (Store-Methode 60–90, Handler+Route 30–50, Frontend 40–70, Go-Tests inkl. Vollbild-Fixture 150–220, Frontend-Test 20–40)
- **Files:** 6 (2 neu, 4 geändert)
- **Effort:** medium — kleine Codefläche, aber Sicherheitswirkung (Mandantentrennung, Geheimnis-Filterung) und eine aufwendige Vollbild-Test-Fixture

**Hinweis LoC-Limit:** Das Standard-Limit von 250 LoC/Workflow reißt voraussichtlich an der Test-Fixture (rund zwanzig Datenarten müssen für den Drift-Test angelegt werden), nicht an der Produktionslogik. `workflow.py set-field loc_limit_override 500` ist hier begründet einzuplanen, nicht ein Zeichen für ausufernden Umfang.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/user.go` (`DeleteUser`, `UserDir`, `ValidUserID`) | Go-Store | Vorbild für die symmetrische `ExportUser`-Methode; `UserDir` ist die einzige Pfad-Engstelle, `ValidUserID` schützt vor Traversal auf Nutzerordner-Ebene |
| `internal/middleware/auth.go` (`UserIDFromContext`, `AuthMiddleware`) | Go-Middleware | Einzige erlaubte Quelle der Nutzerkennung; Grundlage für AC-2/AC-3 |
| `internal/router/router.go` | Go-Router | Route `/api/auth/export` kommt neben `r.Delete("/api/auth/account", …)` (Zeile 67) in den geschützten Bereich |
| `internal/model/user.go` (Feldliste `User`) | Go-Model | Grundlage der Positiv-/Negativliste für AC-5 (`user.json`-Filterung) |
| `src/services/throttle_store.py` | Python-Core | Quelle der aktuellen und der drei Altbestand-Dateinamen (AC-9) |
| `frontend/src/routes/account/+page.svelte` (`data-testid="account-section"`) | Frontend | Ort der neuen Export-Karte, muss vor der Gefahrenzone-Karte stehen (AC-12) |
| `frontend/src/lib/api.ts` (`uploadGpx` als Vorbild für Nicht-JSON-Antworten) | Frontend | Der bestehende `request<T>`-Client liefert nur geparstes JSON; für den Download ist ein Sonderweg (`fetch` + `res.blob()`) nötig |
| `docs/specs/modules/account_deletion.md` | Spec | Gegenrichtung — als Aufbau-Vorlage genutzt, **nicht** als Bestandsliste (dort unvollständig) |

## Implementation Details

**Format: ZIP-Archiv, durchgereicht statt gepuffert.** Die Nutzerdaten liegen in gemischten Formaten (`gpx/` ist XML, alle anderen Wurzeln JSON). Ein ZIP hält jede Datei im Originalformat. Die Antwort wird direkt in `http.ResponseWriter` geschrieben statt vollständig im Speicher aufgebaut, weil die reale Datenmenge produktiv ungemessen ist (Produktivordner nicht lesbar) — Durchreichen hält den Speicherbedarf unabhängig von der Nutzergröße konstant.

**Aufteilung:**
- `internal/store/user.go` — neue Methode `ExportUser` direkt neben `DeleteUser`, macht die Symmetrie der beiden Operationen im Code sichtbar.
- `internal/handler/data_export.go` (neu) — dünner Handler: Kennung aus dem Auth-Kontext lesen, bei leerer Kennung 401 und Abbruch, sonst `Content-Disposition`/`Content-Type: application/zip` setzen und die Store-Methode in die Antwort durchreichen.
- `internal/router/router.go` — `r.Get("/api/auth/export", …)` im geschützten Bereich (nicht in der Public-Allowlist aus `internal/middleware/auth.go:50-63`).
- `internal/handler/data_export_test.go` (neu, **nicht** `export_test.go` — diese Datei existiert bereits und gehört zum Go-Idiom „Paket-Interna für Tests zugänglich machen", hat mit Datenexport nichts zu tun).
- `frontend/src/routes/account/+page.svelte` — eigene Karte „Deine Daten" vor der Gefahrenzone-Karte.
- `frontend/src/lib/api.ts` — Sonderweg für Datei-Antworten.

**Leere Kennung — Begründung, warum eine ausdrückliche Prüfung nötig ist:** Ohne diese Prüfung entsteht strukturell ein Fremddaten-Export, weil drei Bestandsstellen ineinandergreifen: `UserIDFromContext` liefert bei fehlendem Kontext den leeren String statt eines Fehlers (`internal/middleware/auth.go:151-154`), `WithUser("")` ist im Store ein No-Op (`internal/store/store.go:21-24`), und die Store-Voreinstellung ist `"default"` (`internal/config/config.go:10`). Ein Handler, der die Kennung nur durchreicht, würde bei fehlendem Auth-Kontext den `default`-Ordner ausliefern — das ist AC-3.

**Pfadsicherheit im Archiv — Begründung, warum AC-11 nicht trivial erfüllt ist:** `ValidUserID`/`pathsafe.go:41` schützen nur die Nutzerordner-Ebene (welches `<id>` als Store-Wurzel dient). Die Dateinamen *innerhalb* des Nutzerordners — Entitäts-Kennungen in `locations/`, `gpx/`, `briefings/` — durchlaufen diese Prüfung nicht automatisch, sobald sie als Archiv-Eintragsname verwendet werden. Die Archiv-Erzeugung muss deshalb selbst sicherstellen, dass jeder Eintragsname relativ und ohne `..`-Segment bleibt, unabhängig davon, was als Entitäts-Kennung gespeichert wurde.

**Die Erlaubnisliste (Export-Inhalt) — mit Vergleichsart:**

Exakte Dateinamen (Gleichheitsvergleich):

| Datei | Beleg |
|---|---|
| `user.json` | **gefiltert** — ohne `password_hash`, ohne `passkey_credentials` |
| `groups.json` | `internal/store/group.go:15` |
| `metric_presets.json` | `internal/store/metric_preset.go:15` |
| `alert_log.json` | `internal/store/log.go:64` |
| `briefing_log.json` | `internal/store/log.go:24` |
| `pending_briefings.json` | `internal/store/pending_briefings.go:30` |
| `briefing_slots.json` | `src/services/briefing_slots.py:6` |
| `briefing_anchor.json` | `src/services/alert_briefing_anchor.py:40` |
| `throttle_state.json` | `src/services/throttle_store.py:29` |
| `alert_throttle.json`, `compare_alert_throttle.json`, `radar_alert_throttle.json` | `throttle_store.py:31-33` — Altbestand, s. AC-9 |

Ordner (Präfixvergleich, Inhalt wandert vollständig mit): `locations/`, `gpx/`, `weather_snapshots/`, `compare_weather_snapshots/`, `briefings/` (alle vier dort liegenden Sorten — Trips, Compare-Presets, Subscriptions, Fingerprints), `alert_state/`.

Begründete Ausnahmeliste (nicht im Export, aber der Drift-Klammer bekannt):

| Eintrag | Grund |
|---|---|
| `sessions.json`, `password_reset.json`, `email_verification.json` | Geheimnisse (exakter Vergleich, bewusst kein Präfixvergleich — ein künftiges `email_verification_v2.json` soll weder still exportiert noch still ausgenommen werden, sondern die Drift-Klammer meldet es) |
| `alert_input/`, `diagnostics/` | Betriebsdaten — technische Protokolle zur Fehlersuche, vom System über sich selbst geführt, nicht vom Nutzer bereitgestellt (s. Known Limitations d) |
| `.throttle_state_*.tmp` | Reste des atomaren Schreibens (`throttle_store.py:154`), können nach einem Absturz liegenbleiben |

## Expected Behavior

- **Input:** `GET /api/auth/export`, authentifiziert über den bestehenden Session-/Auth-Mechanismus; keine Request-Parameter mit Wirkung auf die exportierte Kennung.
- **Output:** Bei gültigem Auth-Kontext HTTP 200, `Content-Type: application/zip`, `Content-Disposition: attachment; filename=...`, Body ist das ZIP-Archiv mit dem gefilterten Nutzerbestand. Bei fehlendem Auth-Kontext HTTP 401, kein Archiv.
- **Side effects:** Keine Schreibwirkung — reiner Lesezugriff auf den bestehenden Nutzerbaum. Kein Log-Eintrag mit Geheimniswerten.

## Acceptance Criteria

- **AC-1:** Given zwei Nutzer A und B mit jeweils eigenen, unterscheidbaren Daten (z. B. Locations, Trips) / When A angemeldet den Export unter `GET /api/auth/export` aufruft / Then enthält das ausgelieferte Archiv ausschließlich Daten von A — kein einziger Wert aus Bs Datenbestand taucht im entpackten Archivinhalt auf.
  - Test: Zwei Store-Nutzer mit eindeutigen Markerwerten in ihren Daten anlegen, als A authentifizierten Request an den Handler stellen, Antwort als ZIP entpacken und den kompletten Inhalt nach Bs Markerwert durchsuchen — kein Treffer.

- **AC-2:** Given A ist angemeldet / When die Anfrage zusätzlich den Parameter `?user_id=B` trägt / Then enthält das Archiv weiterhin ausschließlich A-Daten — der Parameter wird ignoriert.
  - Test: Request mit gesetztem Auth-Kontext A und Query-Parameter `user_id=B` stellen; im entpackten Archiv ist A-Markerwert vorhanden, B-Markerwert fehlt vollständig. Fängt die Verfälschung „Kennung wird aus dem Request-Parameter statt aus dem Auth-Kontext gelesen".

- **AC-3:** Given eine Anfrage ohne gesetzten Anmelde-Kontext (leere `user_id`) und ein vorhandener `default`-Nutzerordner mit eigenem, wiedererkennbarem Markerwert / When der Export-Endpoint aufgerufen wird / Then ist die Antwort HTTP 401, es wird kein Archiv ausgeliefert, und insbesondere taucht der Markerwert des Sammelordners `default` nirgends in der Antwort auf.
  - Test: Der `default`-Ordner muss **über den Store selbst** befüllt werden (`store.New(tmp, "default")` + `SaveUser` und mindestens eine weitere Datenart mit Markerwert) — genau der Ordner, auf den ein leerer Kontext auflösen würde. Sonst ist die Prüfung gegenstandslos: In einem frischen `t.TempDir()` existiert kein `default`-Ordner, und „Marker fehlt" wäre bei jeder beliebigen leeren Antwort erfüllt. Geprüft wird danach **beides**: Statuscode 401 **und** ein leerer bzw. als Fehler geformter Antwortkörper (kein Archiv). Ein bloßes „Marker nicht enthalten" genügt nicht.

- **AC-4:** Given ein Nutzer mit vorhandenen Geheimnis-Dateien `sessions.json`, `password_reset.json`, `email_verification.json` sowie gesetztem `password_hash`/`passkey_credentials` in `user.json` / When der Export aufgerufen wird / Then taucht keiner dieser Geheimniswerte irgendwo im entpackten Archivinhalt auf.
  - Test: Geheimnis-Dateien und `user.json`-Geheimnisfelder mit eindeutigen Markerwerten befüllen, Export aufrufen, den kompletten entpackten Archivinhalt (nicht nur die Dateinamen-Liste) nach jedem Markerwert durchsuchen — kein Treffer.

- **AC-5:** Given ein Nutzer mit vollständig ausgefülltem `user.json` inklusive `password_hash` und `passkey_credentials` / When der Export aufgerufen wird / Then enthält die ausgelieferte `user.json` die Felder `id`, `email`, `created_at`, `mail_to`, `sms_to`, `telegram_chat_id`, `display_name`, `tier` sowie die übrigen Profilfelder — aber weder `password_hash` noch `passkey_credentials`.
  - Test: `user.json` mit gesetzten Geheimnisfeldern anlegen, Export aufrufen, entpackte `user.json` als JSON parsen, geforderte Felder auf Vorhandensein prüfen und `password_hash`/`passkey_credentials` auf Abwesenheit.

- **AC-6:** Given ein Vollbild-Nutzerverzeichnis mit je einem Exemplar jeder in der Analyse belegten Datenart / When der Export aufgerufen wird / Then ist jeder angelegte Eintrag entweder im entpackten Archiv enthalten oder steht auf der begründeten Ausnahmeliste — eine künftige, nicht gelistete neue Datenart macht den Test rot.
  - Test: Fixture über die Produktiv-Schreiber (`ProvisionUserDirs`, `SaveUser`, `SaveLocation`, `SaveTrip`, …) für alle in der Analyse belegten ca. zwanzig Datenarten aufbauen, Export aufrufen, jeden angelegten Eintrag gegen (entpackter Archivinhalt ∪ Ausnahmeliste) abgleichen — ein nicht zugeordneter Rest lässt den Test fehlschlagen.

- **AC-7:** Given das Vollbild-Nutzerverzeichnis und die begründete Ausnahmeliste / When der Drift-Test läuft / Then ist jeder Eintrag der Ausnahmeliste durch einen tatsächlich angelegten Eintrag im Vollbild-Verzeichnis gedeckt — eine Ausnahme ohne Gegenstück lässt den Test fehlschlagen, damit Totholz auffällt, sobald eine Datenart aus dem Bestand verschwindet.
  - Test: Bei **jedem** Lauf iteriert der Test über die Ausnahmeliste und prüft für jeden Eintrag, dass das Vollbild-Fixture einen passenden Pfad angelegt hat; ein unbelegter Ausnahme-Eintrag lässt den Test fehlschlagen. Die Prüfung läuft bei jedem Testlauf und hängt nicht an einer gedachten Änderung — sonst wäre sie eine Aussage über die Testsuite statt über den Export.

- **AC-8:** Given die Erlaubnisliste in der Umsetzung (`internal/store/user.go`) und die Erwartungsliste im Test / When ein Eintrag versuchsweise aus der Erlaubnisliste der Umsetzung entfernt wird (Mutations-Gegenprobe) / Then wird der Drift-Test rot, weil der zugehörige Eintrag im ausgelieferten Archiv fehlt — die beiden Listen sind nicht dieselbe Konstante, der Test bewacht also den Code und nicht nur sich selbst.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie: einen Eintrag aus dem Erlaubnislisten-Slice der Store-Methode entfernen, Export erneut aufrufen, Drift-Test schlägt fehl, weil der Eintrag im entpackten Archiv fehlt, obwohl das Vollbild-Fixture ihn angelegt hat.

- **AC-9:** Given ein Nutzerverzeichnis mit den drei Altbestand-Dateien `alert_throttle.json`, `compare_alert_throttle.json`, `radar_alert_throttle.json` / When der Export aufgerufen wird / Then sind alle drei Dateien im Archiv enthalten, sofern vorhanden.
  - Test: Altbestand-Dateien mit Markerwert anlegen, Export aufrufen, alle drei Markerwerte im entpackten Archiv wiederfinden.

- **AC-10:** Given ein `briefings/`-Ordner mit allen drei dort abgelegten Dateisorten (Trips, Compare-Presets, Subscriptions) / When der Export aufgerufen wird / Then sind alle drei Sorten vollständig im Archiv enthalten — und damit auch die Grundlage, aus der der Briefing-Fingerabdruck berechnet wird.
  - **Präzisierung nach der Freigabe (2026-09-09, Phase 5):** Die freigegebene Fassung sprach von „vier Sorten … Fingerprints". Nachgemessen ist das falsch: `BriefingFingerprint` (`internal/store/briefing_fingerprint.go:27-41`) liest `briefings/<id>.json` und bildet eine Prüfsumme darüber — es existiert **keine** eigene Fingerabdruck-Datei. Der abgedeckte Bestand ändert sich dadurch **nicht** (der Ordner wandert vollständig mit); korrigiert wird allein die Zählung, damit das AC nichts verlangt, was es nicht gibt.
  - Test: Je einen Eintrag jeder Sorte über die zugehörigen Produktiv-Schreiber anlegen, Export aufrufen, alle vier Markerwerte im entpackten `briefings/`-Anteil des Archivs wiederfinden.

- **AC-11:** Given ein Nutzerverzeichnis mit einer Entität, deren gespeicherter Dateiname/Kennung gezielt ein Traversal-Segment enthält (z. B. eine Location- oder GPX-Kennung mit `..` im Namen — `ValidUserID`/`pathsafe.go:41` schützen nur die Nutzerordner-Ebene, nicht diese Entitäts-Dateinamen) / When der Export aufgerufen wird / Then ist trotzdem jeder Eintragsname im ausgelieferten Archiv relativ zum Nutzerordner — kein Eintrag enthält `..` als Pfadsegment oder einen absoluten Pfad.
  - Test: Entität mit manipuliertem Dateinamen/Kennung anlegen, Export aufrufen, alle ZIP-Header-Namen der entpackten Antwort durchlaufen und prüfen, dass kein Name mit `/` beginnt und kein Name `..` als Pfadsegment enthält — zusätzlich als Invariante über alle übrigen (regulären) Einträge.

- **AC-12:** Given ein angemeldeter Nutzer auf der Konto-Seite / When die Seite geladen wird / Then existiert eine eigene, über `data-testid` auffindbare Karte „Deine Daten" mit einem Export-Knopf, die in der Seitenreihenfolge vor der Gefahrenzone-Karte steht, und ein Klick auf den Knopf löst den Download der Archivdatei aus.
  - Test: E2E — Konto-Seite laden, die Export-Karte über ihren `data-testid` lokalisieren (nicht über den Anzeigetext) und ihre DOM-Reihenfolge relativ zur Gefahrenzone-Karte prüfen (Export-Karte kommt zuerst), Klick auf den Export-Knopf auslösen und den ausgelösten Download bzw. die Download-Anfrage verifizieren — reines `toBeVisible()` auf die Karte genügt nicht.

## Known Limitations

- (a) **Abweichung vom Issue-Wortlaut „Export und Löschung decken denselben Bestand ab".** Wörtlich genommen ist diese Zusicherung unerfüllbar: Die Löschung entfernt per `os.RemoveAll` restlos alles im Nutzerordner, der Export lässt Geheimnisse und Betriebsdaten absichtlich weg. Der in dieser Spec geltende Maßstab lautet stattdessen: Der Export deckt den Löschbestand ab **abzüglich der begründeten Ausnahmeliste**, und jeder Eintrag der Ausnahmeliste trägt einen dokumentierten Grund. Diese Abweichung wird hier ausdrücklich benannt, damit sie nicht still passiert.
- (b) **Unvollständiges Archiv bei Fehler mitten im Stream.** Da das Archiv durchgereicht statt gepuffert wird, ist der Erfolgs-Statuscode bereits gesendet, wenn ein Fehler mitten im Packvorgang auftritt — die Übertragung bricht dann ab und liefert ein unvollständiges Archiv. Das ist bewusst dem stillen Teilexport mit vorgetäuschter Vollständigkeit vorgezogen.
- (c) **Kein zeitlich konsistenter Schnitt.** Ohne Sperre auf dem Nutzerverzeichnis ist der Export ein zeitlich unscharfer Schnitt bei gleichzeitigem Schreiben (z. B. läuft parallel ein Briefing-Versand) — für einen Art.-20-Export vertretbar, aber eine bewusste Entscheidung und keine Nebenwirkung.
- (d) **Betriebsdaten-Auslassung als ausdrückliche Annahme.** `diagnostics/` und `alert_input/` bleiben außerhalb des Exports, weil sie technische Protokolle zur Fehlersuche sind, die das System über sich selbst führt, nicht Daten, die der Nutzer bereitgestellt hat. Grenzfall ist `alert_input/`: Es schneidet die Alarm-Eingangsdaten dieses Nutzers mit, ist also nutzerbezogen. Wird das rechtlich anders bewertet, wandern beide Ordner dank der Erlaubnisliste als einzeilige Ergänzung auf die Einschlussliste, ohne Umbauarbeit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Export ist ein rein lesender Zugriff auf eine bestehende Datenablage und ändert keine der in `docs/adr/` erfassten Entscheidungsflächen (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie). Die Wahl von ZIP als Übertragungsformat und Streaming statt Pufferung ist eine hier in „Implementation Details" dokumentierte Umsetzungsentscheidung ohne Grundsatzcharakter — sie etabliert lediglich das erste Vorbild für Binärantworten im Bestand, ohne eine bestehende ADR-Entscheidung zu berühren oder abzulösen.

## Changelog

- 2026-09-09: Initial spec created (Issue #2270, Epic #2138, Scheibe 3 von 4 aus #2146)
