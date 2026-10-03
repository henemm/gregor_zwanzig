---
entity_id: mengen_quoten_je_tier
type: feature
created: 2026-10-02
updated: 2026-10-02
status: draft
workflow: feat-2482-quoten-je-tier
version: "1.0"
tags: [tiers, quotas, trips, compare, locations, epic-2138]
---

# Mengen-Quoten je Tier (S5 — Trips, Ortsvergleiche, Orte)

## Approval

- [ ] Approved

## Purpose

Begrenzt, wie viele Trips, Ortsvergleiche und Orte ein Nutzer je Tarif (Free, Standard, Premium)
neu anlegen kann. Zweck ist der Schutz des gemeinsamen Systems: jeder aktive Trip und jeder aktive
Ortsvergleich erzeugt Scheduler-Last und Wetter-Abrufe, ein einzelnes Konto soll sie nicht
unbegrenzt vermehren können (Epic #2138 Multi-User, Sammel-Issue #2153, Issue #2482). Wer die
Grenze erreicht hat, bekommt beim Neuanlegen eine verständliche deutsche Meldung; vorhandene
Daten bleiben vollständig erhalten und bearbeitbar.

## PO-Entscheidung: Grenzwerte (VORSCHLAG — PO gibt mit den ACs frei)

Die Werte sind ein begründeter Vorschlag, keine Messung: die Produktiv-Bestände sind für den
Entwicklungsbenutzer nicht lesbar. Wer über der Grenze liegt, verliert nichts (siehe AC-5). Die
Werte stehen an genau einer Stelle (Tabelle in `internal/model/tier.go`) und sind jederzeit ohne
Datenänderung anpassbar.

| Tarif | Trips (aktiv) | Ortsvergleiche (aktiv) | Orte (gesamt) |
|---|---|---|---|
| Free | 3 | 2 | 10 |
| Standard | 15 | 10 | 50 |
| Premium | 50 | 30 | 200 |
| Admin / Ausnahme-Liste | unbegrenzt | unbegrenzt | unbegrenzt |

Begründung der Größenordnung: Ein Weitwanderer plant selten mehr als einige Trips gleichzeitig
(Free 3 deckt "ein Trip aktiv, ein bis zwei in Planung"); Orte werden von Ortsvergleichen und Trips
gemeinsam genutzt und wachsen schneller als Trips (daher das Vielfache). Premium ist großzügig,
aber endlich, damit auch dort keine unbegrenzte Scheduler-Last entsteht.

## Source

- **File:** `internal/model/tier.go` (Tabelle), `internal/handler/quota.go` (neu, geteilter Helfer)
- **Identifier:** `QuotaFor(tier string) Quota`, Helfer `checkQuota`/`withQuota` (Namen im Ermessen des Entwicklers, EIN geteilter Helfer)

> **Schicht-Hinweis:** Reine Go-/Frontend-Änderung. Python (`src/`, `api/`) wird nicht angefasst
> und spiegelt die Tabelle nicht (eine Quelle der Wahrheit, vgl. Code-Teilungs-Regel).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `model.EffectiveTier` (`internal/model/tier.go:35`) | function | Normalisiert Tier, leer/unbekannt wird fail-closed `free` |
| `Store.LoadUser` (`internal/store/user.go:53`) | function | Tier des aktuellen Nutzers (Muster `sms_verify.go:211-225`) |
| `Store.LoadTrips` / `LoadComparePresets` / `LoadLocations` | function | Zählquellen (nur Lesen) |
| `internal/store/briefing_lock.go` | pattern | Vorbild für den Per-User-Quoten-Lock (Paket-Map mit Refcount) |
| `config.ParseAdminUserIDs` (`internal/router/router.go:42`) | function | Admin-Menge (`GZ_ADMIN_USER_IDS`), wird an die Create-Handler durchgereicht |
| `GZ_QUOTA_EXEMPT_USER_IDS` | env | NEU, Default leer; Testkonten ohne Admin-Rechte von der Quote ausnehmen |
| `internal/handler/briefing_subscription.go:131` | caller | `POST /api/briefings` delegiert an Trip-/Preset-Create und erbt die Prüfung |
| `internal/handler/auth.go` (`toProfileResponse`) | module | Liefert die Grenzen im Profil aus |
| `frontend/src/lib/api.ts:137-141` | module | Wirft `{error, detail, status}`; Anlege-UIs zeigen `detail ?? error` |
| `frontend/src/routes/account/+page.svelte:1083-1112` | module | Vorbild "x von N" aus S4 |
| `frontend/e2e/ci-stack.sh:67` | script | CI-Stack: `GZ_ADMIN_USER_IDS=admin` ergänzen |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/tier.go` | MODIFY | Quoten-Tabelle `QuotaFor(tier)`, Eingabe `EffectiveTier` |
| `internal/store/quota_lock.go` | CREATE | Per-User-Lock (Muster `briefing_lock.go`), Zählen+Speichern atomar |
| `internal/handler/quota.go` | CREATE | EIN geteilter Quoten-Helfer inkl. 409-Antwort, Admin-/Ausnahme-Prüfung |
| `internal/handler/trip.go` | MODIFY | `CreateTripHandler`: Quote nur bei echter Neuanlage (ID existiert für diesen Nutzer nicht) |
| `internal/handler/compare_preset.go` | MODIFY | `CreateComparePresetHandler`: Quote prüfen |
| `internal/handler/location.go` | MODIFY | `CreateLocationHandler`: Quote prüfen |
| `internal/handler/trip.go:495` `UpdateTripStateHandler`, `internal/handler/compare_preset.go:481` `UpdateComparePresetStateHandler` (`PATCH .../state`) | MODIFY | Nur beim Wiederherstellen aus dem Archiv: derselbe Helfer (AC-9) |
| `internal/router/router.go` | MODIFY | Admin-Menge und Ausnahme-Liste an die Handler durchreichen |
| `internal/config/config.go` | MODIFY | `GZ_QUOTA_EXEMPT_USER_IDS` einlesen (Default leer) |
| `internal/handler/auth.go` | MODIFY | Grenzen im Profil ausliefern (Admin/Ausnahme: unbegrenzt) |
| `frontend/src/lib/types.ts` | MODIFY | Profil-Typ um Grenzen erweitern |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Anzeige "x von N" für Trips, Ortsvergleiche, Orte |
| `frontend/e2e/ci-stack.sh` | MODIFY | `GZ_ADMIN_USER_IDS=admin` (Seed-Konto ist das Betreiber-Konto) |
| `internal/handler/*quota*_test.go` | CREATE | Go-Handler-Tests (siehe Test Plan) |
| `docs/specs/modules/epic_user_tiers_overview.md` | MODIFY (Doku) | Mengengrenzen in die Tier-Tabelle |

### Estimated Changes

- Files: ~14 (davon 3 Test-/Doku-Dateien)
- LoC: ca. +150 Produktion, +250 Tests (Detail-Zählung via `workflow.py status`)

## Implementation Details

**Tabelle und Auflösung.** `QuotaFor(model.EffectiveTier(user.Tier))` liefert drei Grenzen
(Trips, Ortsvergleiche, Orte). Ein leeres oder unbekanntes Tier ergibt `free` (fail-closed),
genau wie bei den bestehenden Kanal-Gates. Admin (`GZ_ADMIN_USER_IDS`) und Ausnahme-Liste
(`GZ_QUOTA_EXEMPT_USER_IDS`) werden vor der Tabelle abgefangen: "unbegrenzt".

**Geteilter Helfer.** Die drei Create-Handler rufen denselben Helfer auf (Resource-Name, Zähl-
Funktion, Speicher-Funktion). Keine drei Kopien. Der Helfer ermittelt Nutzer-ID aus dem
Auth-Kontext (nie `"default"`-Fallback), lädt das Tier, nimmt den Per-User-Quoten-Lock, zählt,
prüft `current >= limit` und ruft bei Erfolg die Speicher-Funktion noch innerhalb des Locks auf.

**Race-Schutz.** Zwei parallele Neuanlagen eines Nutzers bei `limit - 1` würden ohne Lock beide
zählen und beide speichern. Deshalb ein Per-User-Lock (Muster `briefing_lock.go`), der Zählen und
Speichern umschließt. Lock-Reihenfolge fest: Quoten-Lock zuerst, danach `LockBriefing`; nie
umgekehrt (Deadlock-Vermeidung). Der Lock ist je Nutzer, Neuanlagen verschiedener Nutzer
blockieren sich nicht.

**Antwort bei Überschreitung.** HTTP 409 mit
`{"error":"quota_exceeded","detail":"<deutscher Text>","resource":"trips|compare_presets|locations","limit":N,"current":M}`.
422 ist für Validierung belegt, 403 kollidiert mit Rollen-/Tier-Gates. Beispieltext für Trips:
"Du hast bereits 3 von 3 Trips in deinem Tarif. Archiviere oder lösche einen Trip, um einen neuen
anzulegen." Analog für Ortsvergleiche und Orte. Es heißt durchgängig "Trip". Weil alle
Anlege-UIs `detail ?? error` anzeigen (TripNewEditor, Compare-Wizard, Orte-Liste, Ort-Modal,
GPX-Upload), erscheint der deutsche Text ohne Frontend-Umbau.

**Zählung (Empfehlung, begründet).** Trips und Ortsvergleiche: nur nicht archivierte. Grund: Last
im Scheduler entsteht nur durch aktive; würden Archivierte mitzählen, würde das Archiv die
Neuanlage dauerhaft sperren und der Hinweis "archiviere einen Trip" wäre unwahr. Orte: alle (es
gibt kein Archiv). Restrisiko: "anlegen + archivieren" kann unbegrenzt Datensätze erzeugen. Das
trifft Speicherplatz, nicht Scheduler-Last, und ist bewusst akzeptiert; ein Gesamtdeckel wäre eine
spätere, eigene Entscheidung.

**Nur Neuanlage.** Geprüft wird ausschließlich bei Neuanlage. PUT, PATCH (außer Wiederherstellen),
DELETE und Archivieren sind nie blockiert. Der Trip-POST auf eine bereits vorhandene ID desselben
Nutzers bleibt, wie heute, ein Upsert ohne Quotenprüfung (kein Verhaltenswechsel; die E2E-Setups
nutzen DELETE+POST). Ortsvergleiche und Orte: jede Anlage ist neu (ein Ort mit bestehender ID
bleibt 409 `conflict` wie heute, dieser Fehler hat Vorrang vor der Quote).

**Wiederherstellen aus dem Archiv (Entscheidung).** Wiederherstellen erzeugt einen aktiven Trip
bzw. Ortsvergleich und wird deshalb wie eine Neuanlage gegen die Grenze geprüft (409
`quota_exceeded`). Begründung: sonst wäre die Quote trivial umgehbar (anlegen, archivieren,
neuen anlegen, alten wiederherstellen) und die Zählregel "nur Aktive" hätte keine Wirkung. Das
widerspricht nicht dem Grundsatz "Bestand bleibt unangetastet": der Datensatz bleibt im Archiv
erhalten, nur das Aktivieren über die Grenze hinaus wird verweigert. Archivieren und Löschen
schaffen jederzeit Platz.

**Admin und Testkonten.** Admin (`GZ_ADMIN_USER_IDS`) ist unbegrenzt, damit das Betreiber-Konto
nie ausgesperrt wird. Zusätzlich gibt es die Env `GZ_QUOTA_EXEMPT_USER_IDS` (kommagetrennte
Nutzer-IDs, Default leer, Produktion bleibt leer). Sie nimmt Konten von der Quote aus, ohne ihnen
Admin-Rechte (Admin-UI, Tarifvergabe) zu geben.

**Testnutzer (verifizierter Befund — sonst bricht die CI-Ampel).**

- CI-Stack: `frontend/e2e/ci-stack.sh:67` startet Go mit `GZ_USER_ID=admin`; das Seed-Konto
  `admin` (`cmd/server/main.go:135`, `seedAdminUser`) hat kein Tier und wäre fail-closed `free`
  (3 Trips). `GZ_ADMIN_USER_IDS` ist dort nicht gesetzt. Rund 61 E2E-Specs legen Trips per POST
  in eine frische Datenwurzel an; mit Quote 3 würde der Check `e2e` rot. Abhilfe: `GZ_ADMIN_USER_IDS=admin`
  im CI-Stack (das Seed-Konto ist das Betreiber-Konto, Admin ist hier fachlich korrekt).
- Staging: der E2E-Login läuft als `GZ_AUTH_USER=default` (`/home/hem/gregor_zwanzig_staging/.env`),
  `GZ_ADMIN_USER_IDS=gz-staging-admin`. Tier und Bestand von `default` sind für den
  Entwicklungsbenutzer nicht lesbar, vermutlich sind dort viele Trips angesammelt; die Quote
  könnte `/e2e-verify` blockieren. Abhilfe: `default` in `GZ_QUOTA_EXEMPT_USER_IDS` auf Staging
  eintragen (statt `default` zum Admin zu machen, was die Admin-UI für das Testkonto öffnen
  würde). Wegwerf-Nutzer `gregor-test+...` bleiben quotenpflichtig, damit die Quote auf Staging
  selbst messbar ist.
- Python-`tests/tdd/*`: geprüft (2026-10-02). Die Tests, die Trips/Orte per HTTP anlegen
  (z. B. `test_674_aktivitaetstyp_fahrrad.py`, `test_stage_reorder.py`,
  `test_issue_1069_tier_channel_gating.py`), sind `staging`/`live`-markiert und laufen nicht im
  Commit-Gate/CI-`test`-Job, sondern gegen Staging — dort mit dem Konto `default`, das über
  `GZ_QUOTA_EXEMPT_USER_IDS` ausgenommen ist. Kein zusätzlicher Handlungsbedarf.

**Profil und Anzeige.** `GET /api/auth/profile` liefert je Ressource die Grenze (Admin/Ausnahme:
"unbegrenzt", z. B. `null`). `/account` zeigt "x von N" für Trips, Ortsvergleiche und Orte im
Stil der S4-Anzeige; die Zählwerte stammen aus den bereits in `+page.server.ts:21` geladenen
Listen (Trips und Ortsvergleiche nur aktive, dieselbe Regel wie im Server). Bei unbegrenzt
entfällt die Grenze ("x").

**Empfängerkanäle — begründete Herausnahme aus dem Scope.** Das Issue nennt "Empfängerkanäle".
Es gibt dafür keine zählbare Mengengröße: das Profil hat genau eine Adresse je Kanal (`MailTo`,
`SmsTo`, `TelegramChatID`, `PremiumSmsReplyTo`); `ComparePreset.Empfaenger` ist inert (#1452) und
wird nicht versendet. Welche Kanäle ein Tarif nutzen darf, ist bereits per Tier geregelt
(`SmsAllowed`/`PremiumSmsAllowed`), die Versandmenge pro Tag per S4 (`sms_daily_limit`). Eine
zusätzliche Mengenquote hätte keinen Gegenstand. Es wird bewusst kein Folge-Issue angelegt; sollte
später eine Mehr-Empfänger-Funktion entstehen, bekommt sie ihre Quote in deren eigener Spec.

**Gruppen und Metrik-Presets — außerhalb des Scopes.** Sie stehen nicht im Issue-Auftrag und
erzeugen keine Scheduler-Last oder Wetter-Abrufe; sie sind reine Konfigurationsobjekte. Keine
Quote in dieser Scheibe.

**ADR-Abwägung.** ADR-0015 ordnet Persistenz, Mandantentrennung und Rate-Limiting Go zu.
ADR-0075/0076 betreffen nur das geteilte Wetter-Kontingent (Python), nicht Mengen von
Go-Store-Entitäten. Eine Mengenquote auf Trips, Ortsvergleiche und Orte ist Persistenz-Bestand
in Go; die Prüfung dort ist konsistent mit ADR-0015, ein neues ADR ist nicht nötig. Python
spiegelt die Tabelle nicht. Keine Persistenz-/Schema-Änderung: es wird nur gelesen und gezählt,
kein Migrationsbedarf.

## Expected Behavior

- **Input:** Authentifizierter Nutzer legt einen Trip, einen Ortsvergleich oder einen Ort neu an
  (bzw. stellt einen archivierten Trip/Ortsvergleich wieder her).
- **Output:** Liegt die aktuelle Anzahl unter der Grenze des Tarifs: Anlage wie bisher. Sonst
  409 `quota_exceeded` mit deutschem Text, nichts wird gespeichert.
- **Side effects:** Keine Schreibzugriffe außer der Anlage selbst; kein Löschen, kein Sperren.

## Acceptance Criteria

- **AC-1:** Given ein Free-Nutzer hat 2 aktive Trips / When er einen 3. Trip anlegt und danach einen 4. / Then gelingt die dritte Anlage und die vierte wird mit der Meldung "Du hast bereits 3 von 3 Trips in deinem Tarif ..." abgelehnt (409 `quota_exceeded`, `limit` 3, `current` 3), und der Trip-Bestand bleibt bei 3.
- **AC-2:** Given ein Free-Nutzer hat 2 aktive Ortsvergleiche bzw. 10 Orte / When er einen weiteren Ortsvergleich bzw. Ort anlegt / Then wird die Anlage mit einer deutschen Meldung zu Ortsvergleichen bzw. Orten abgelehnt (409 `quota_exceeded`, `resource` `compare_presets` bzw. `locations`), und es wird nichts gespeichert.
- **AC-3:** Given die Grenzwerte aus der Tabelle (Free 3/2/10, Standard 15/10/50, Premium 50/30/200) / When je ein Nutzer pro Tarif genau bis zur Grenze anlegt und dann eine weitere Anlage versucht / Then ist die Anlage bis zur Grenze erfolgreich und die nächste wird abgelehnt, und ein Nutzer ohne Tarif oder mit unbekanntem Tarif wird wie Free behandelt.
- **AC-4:** Given ein Nutzer hat die Grenze erreicht / When er einen Trip archiviert oder löscht und danach einen neuen Trip anlegt / Then gelingt die Neuanlage, weil archivierte Trips und Ortsvergleiche nicht zur Grenze zählen (Orte zählen alle, Löschen schafft Platz).
- **AC-5:** Given ein Nutzer liegt mit seinem Bestand über der Grenze seines Tarifs (z. B. nach einer Tarif-Herabstufung) / When er einen vorhandenen Trip, Ortsvergleich oder Ort bearbeitet (PUT/PATCH), archiviert oder löscht / Then funktioniert das ohne Fehler und kein Datensatz geht verloren; nur die Neuanlage ist blockiert.
- **AC-6:** Given ein Nutzer sendet einen Trip mit der ID eines bereits vorhandenen eigenen Trips erneut per Anlegen (Upsert) / When er sich an der Grenze oder darüber befindet / Then wird der Trip wie bisher überschrieben und nicht als Neuanlage gezählt oder blockiert.
- **AC-7:** Given Nutzer A hat die Grenze erreicht und Nutzer B im selben System nicht / When B einen Trip, Ortsvergleich oder Ort anlegt / Then gelingt das bei B, A bleibt blockiert, und die Zählung geschieht strikt je Nutzer (Test mit zwei verschiedenen Nutzern, auch umgekehrt).
- **AC-8:** Given ein Nutzer steht bei der Grenze minus 1 / When zwei Neuanlagen gleichzeitig eintreffen / Then gelingt genau eine, die andere wird mit 409 abgelehnt, und die Grenze wird nie überschritten (Per-User-Lock, Zählen und Speichern gemeinsam geschützt).
- **AC-9:** Given ein Nutzer hat die Grenze für aktive Trips erreicht und besitzt einen archivierten Trip / When er diesen Trip wiederherstellt / Then wird das Wiederherstellen mit derselben Meldung abgelehnt (409 `quota_exceeded`) und der Trip bleibt unverändert im Archiv; nach dem Archivieren oder Löschen eines aktiven Trips gelingt das Wiederherstellen (gleiches gilt für Ortsvergleiche).
- **AC-10:** Given ein Admin (`GZ_ADMIN_USER_IDS`) oder ein Konto aus der Ausnahme-Liste (`GZ_QUOTA_EXEMPT_USER_IDS`) / When es mehr Trips, Ortsvergleiche oder Orte anlegt, als die Free-Grenze erlaubt / Then wird nie abgelehnt; ein normales Konto mit gleichem Tarif wird weiterhin abgelehnt, und die Ausnahme-Liste verleiht keine Admin-Rechte.
- **AC-11:** Given ein Briefing wird über den gemeinsamen Weg `POST /api/briefings` angelegt / When der Nutzer die Trip- oder Ortsvergleichs-Grenze erreicht hat / Then wird die Anlage ebenfalls mit 409 `quota_exceeded` abgelehnt und es entsteht weder ein Trip noch ein Ortsvergleich.
- **AC-12:** Given ein Nutzer öffnet das Anlegen eines Trips, eines Ortsvergleichs oder eines Ortes in der Oberfläche und die Grenze ist erreicht / When er speichert / Then sieht er die deutsche Meldung mit "x von N" und dem Hinweis, was er tun kann, ohne dass die Seite abstürzt oder Eingaben verloren gehen.
- **AC-13:** Given ein Nutzer öffnet die Seite /account / When die Seite lädt / Then sieht er für Trips, Ortsvergleiche und Orte jeweils "x von N" seines Tarifs (Admin und Ausnahme-Konten ohne Obergrenze), analog zur Anzeige der SMS-Tagesnutzung.
- **AC-14:** Given der CI-Stack und das Staging-Testkonto / When die E2E-Läufe ihre Trips per POST anlegen / Then bleibt der CI-Check `e2e` grün (CI-Seed-Konto `admin` ist Admin) und `/e2e-verify` läuft auf Staging durch (Konto `default` steht in der Ausnahme-Liste), während Wegwerf-Nutzer `gregor-test+...` auf Staging der Free-Grenze unterliegen.
- **AC-15:** Given der deutsche Fehlertext und alle neuen Anzeigetexte / When sie in Backend und Oberfläche ausgegeben werden / Then verwenden sie ausschließlich die Begriffe "Trip" und "Trips" (kein anderer Begriff für diese Objekte).

## Known Limitations

- **Anlegen + Archivieren** erzeugt unbegrenzt Datensätze (Speicher, keine Scheduler-Last).
  Ein Gesamtdeckel ist eine spätere Entscheidung.
- **Grenzwerte sind unbelegt** (Produktiv-Bestände nicht lesbar). Bestand über der Grenze bleibt
  voll erhalten; die Werte sind zentral änderbar.
- **Wiederherstellen ist die einzige Nicht-Anlage-Operation mit Prüfung** (AC-9); alle anderen
  Änderungen bleiben frei.
- **Race-Schutz gilt pro Prozess** (In-Memory-Lock wie `briefing_lock.go`); es läuft ein einziger
  Go-Prozess je Umgebung.
- **Empfängerkanäle, Gruppen, Metrik-Presets** sind bewusst ohne Quote (Begründung oben).

## Test Plan

### Automated Tests (TDD RED)

Go-Handler-Tests in `internal/handler/*quota*_test.go` (Muster `addUserToContext`
`user_scoped_test.go:23`, `newTestStore`/`seedTrip` aus `trip_write_test.go`, Tier-Fixture per
`s.SaveUser`):

- GIVEN Free-Nutzer mit 2 Trips WHEN 3. und 4. Trip per POST THEN 3. ok, 4. 409 mit `limit` 3 / `current` 3 (AC-1)
- GIVEN Free-Nutzer an der Grenze für Ortsvergleiche und Orte WHEN weitere Anlage THEN 409 mit passendem `resource` (AC-2)
- GIVEN leeres, fehlendes oder unbekanntes Tier WHEN Anlage über Grenze THEN wie Free blockiert; je Tarif exakte Grenze N ok / N+1 409 (AC-3)
- GIVEN Nutzer an der Grenze WHEN Trip archiviert bzw. gelöscht THEN Neuanlage ok (AC-4)
- GIVEN Bestand über der Grenze WHEN PUT/PATCH/DELETE/Archivieren THEN alles ok, Bestand unverändert (AC-5)
- GIVEN Nutzer an der Grenze WHEN POST auf bestehende Trip-ID THEN Upsert ok (AC-6)
- GIVEN alice an der Grenze, bob nicht WHEN bob und alice anlegen THEN bob ok, alice 409, beide Richtungen (AC-7)
- GIVEN Nutzer bei Grenze minus 1 WHEN parallele Goroutinen anlegen THEN genau eine ok, Endbestand = Grenze (AC-8)
- GIVEN archivierter Trip und volle aktive Zahl WHEN Wiederherstellen THEN 409, danach nach Platzschaffen ok (AC-9)
- GIVEN Admin und Ausnahme-Konto WHEN weit über Free-Grenze THEN nie 409; Ausnahme ohne Admin-Rechte (AC-10)
- GIVEN `POST /api/briefings` an der Grenze WHEN Anlage THEN 409 und kein Datensatz (AC-11)

Frontend und Live:

- Frontend-Test: Anzeige "x von N" auf `/account`, unbegrenzt ohne Grenze (AC-13)
- Staging/Live mit Wegwerf-Nutzer `gregor-test+...` (Free): 4. Trip anlegen, Fehlermeldung ist in der Oberfläche sichtbar (AC-12); `/e2e-verify` läuft mit Ausnahme-Konto durch (AC-14)
- Begriffs-Test auf den Fehlertext: enthält "Trip", keinen abweichenden Begriff (AC-15)

## Changelog

- 2026-10-02: Initial spec created (S5, Issue #2482, Sammel-Issue #2153, Epic #2138)
