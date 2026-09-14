---
entity_id: fix_2154_premium_sms_verknuepfungscode
type: module
created: 2026-09-13
updated: 2026-09-13
status: draft
version: "1.0"
tags: [sms, inbound, premium, garmin, security, hijacking, seven-io]
---

<!-- Issue #2154 (Scheibe A -- Sicherheit/Backend), Teil von Epic #2138.
     Loest teilweise feat_1676_s1_premium_sms_rueckkanal.md ab (AC-4/AC-5).
     Scheibe B (Konto-Oberflaeche im Frontend) folgt in eigenem Workflow. -->

# Premium-SMS Verknüpfungscode — Scheibe A: Sicherheit/Backend

## Approval

- [ ] Approved

## Purpose

Der Premium-SMS-Rückkanal ordnet eine eingehende Garmin-Rufnummer heute per
Heuristik einem Nutzer zu: Treffer auf die gespeicherte Rückadresse, sonst
„genau ein Premium-Kandidat" (`internal/handler/premium_sms_connect.go:71-73`).
Bei genau einem Premium-Nutzer schreibt dadurch **jede** fremde Nachricht mit
dem Garmin-Kennzeichen dessen Rückadresse — Hijacking mit Kostenwirkung, ohne
jedes Geheimnis. Ab zwei Premium-Nutzern scheitert jede Erstzuordnung
dauerhaft mit 409. Diese Scheibe ersetzt die Heuristik durch einen
Verknüpfungs-Code, den der Nutzer aus seinem Konto abliest und per inReach
einmalig mitschickt, sowie einen TTL-Abgleich im Eingangspfad, der eine nach
Ablauf der 30-Tage-Frist wiederverwendete Nummer nicht mehr ungeprüft
bestätigt. Kein Frontend für den Code selbst (folgt in Scheibe B) — hier
entsteht nur ein lesender/schreibender Konto-Endpoint.

## Source

- **File:** `internal/model/premium_sms_link.go` (NEU) — Datenform `PremiumSmsLinkCode{CodeHash string, CreatedAt time.Time}`
- **File:** `internal/store/user.go` (MODIFY) — `SaveLinkCode`/`LoadLinkCode`/`DeleteLinkCode` nach Vorbild `SaveResetToken`/`LoadResetToken` (Zeile 104-136), eigene Datei `data/users/<id>/premium_sms_link.json`
- **File:** `internal/handler/premium_sms_link_code.go` (NEU) — Konto-Endpoint `POST /api/auth/premium-sms-link-code` (erzeugen/erneuern) und `GET /api/auth/premium-sms-link-code` (Status), Vorbild `internal/handler/auth.go:260-283` (Passwort-Reset-Token-Erzeugung, bcrypt-Hash)
- **File:** `internal/handler/premium_sms_connect.go` (MODIFY) — R3-Fallback entfernt, TTL-Abgleich, Code-Vergleich, Ratebremse eingebaut
- **File:** `internal/handler/premium_sms_ratelimit.go` (NEU) — globaler Fehlversuchszähler für Code-Vergleiche (D5)
- **File:** `internal/router/router.go`, `cmd/server/main.go` (MODIFY) — Registrierung der neuen Routen, Instanziierung des Ratenzählers
- **File:** `src/services/inbound_sms_reader.py` (MODIFY) — Code aus dem SMS-Text abtrennen und im Payload mitschicken (Zeile 171-175, 232-275); keine ausgehende Antwort ohne Auflösung
- **File:** `api/routers/scheduler.py` (MODIFY) — abgelehnte Lernversuche (4xx) im `status`-Feld sichtbar machen (Zeile 167)

> **Schicht-Hinweis:** Konto-Endpoint (`premium_sms_link_code.go`) ist Go-API
> (authentifiziert, `SessionAuth`, wie `telegram_connect.go:104-139`); der
> Lern-Endpoint (`premium_sms_connect.go`) bleibt Go-API localhost-only. Die
> Text-Zerlegung (D9) ist Python-Core (`src/services/`).

## Estimated Scope

- **LoC:** ~550-650 (Produktivcode + Tests), −50 (abgelöster Fallback-Code)
- **Files:** ~13
- **Effort:** high — `loc_limit_override 500` erforderlich, nur mit PO-Freigabe

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/user.go::SaveResetToken/LoadResetToken` | Vorbild | Datei-je-Nutzer-Persistenz mit Hash statt Klartext (D1) |
| `internal/handler/auth.go:260-283` | Vorbild | Code-Erzeugung (`crypto/rand` + `bcrypt.GenerateFromPassword`), einmalige Klartext-Rückgabe |
| `internal/model/premium_sms.go::PremiumSmsReplyTTL` (30 Tage) | module | dieselbe Konstante für den Eingangs-TTL-Abgleich (D4), kein neuer Zahlenwert |
| `internal/model/tier.go::EffectiveTier` | module | Premium-Kandidatenfilter, unverändert |
| `internal/store/store.go::ListUserIDs/LoadUser/SaveUser` | module | Nutzer-Iteration, Read-Modify-Write mit Merge |
| `internal/middleware.UserIDFromContext` | module | echte `user_id` für den Konto-Endpoint, niemals `"default"` |
| `src/services/inbound_sms_reader.py::GARMIN_MARKER` | module | Trennzeichen `"inreachlink.com"`, unverändert |
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` | abgelöst | AC-4 (Ein-Kandidaten-Fallback) entfällt, s. „Abgelöste Entscheidungen" |
| `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md` | Downstream | `_verarbeite_befehl` erhält weiterhin `user_id`, jetzt aus dem code-gestützten Pfad |

## Implementation Details

### Code-Gestalt (D2)

7 Zeichen aus einem Alphabet ohne verwechselbare Zeichen (kein `I`/`L`/`O`/`0`/`1`,
31 verbleibende Zeichen) → Schlüsselraum ≈ 31⁷ ≈ 2,75·10¹⁰ (≈ 35 Bit). Erzeugung
mit `crypto/rand`, analog `telegram_connect.go:72-76`. Gespeichert wird
ausschließlich der bcrypt-Hash (`internal/model/premium_sms_link.go`); der
Klartext existiert nur im Antwortkörper des Erzeugungs-Aufrufs.

> **Nachtrag (2026-09-14, Issue #2323):** Das Format wurde auf einen festen
> Präfix `XX` (case-insensitive) + 3 Buchstaben (ohne I/L/O) + 3 Ziffern (ohne
> 0/1) umgestellt, z.B. `XXdrt249` — leichter per Satellit abzutippen.
> Schlüsselraum ohne den festen Präfix ≈ 23³·8³ ≈ 6,23 Mio. (kleiner als der
> hier ursprünglich beschriebene, s. Known Limitations zur Ratebremse). Die
> Zahlen in diesem Abschnitt beschreiben den Stand VOR #2323 (historischer
> Beleg der D2-Abwägung); aktuelle Formaldefinition:
> `docs/specs/modules/fix_2323_premium_sms_gate_generisch.md`.

### Neuer Konto-Endpoint (D1, D3, D6)

```
POST /api/auth/premium-sms-link-code   (SessionAuth, echte user_id)
  -> erzeugt/erneuert den Code, gibt ihn EINMAL im Klartext zurueck
     {"code": "XXABC234"} (Format seit #2323, s. Nachtrag oben). Erneuern
     entwertet den alten Code (Replace der Datei, kein Anhaengen).
GET  /api/auth/premium-sms-link-code   (SessionAuth)
  -> {"exists": true|false} -- niemals der Code selbst, niemals der Hash.
```

### Neuer Entscheidungsbaum `PostPremiumSmsLearnHandler` (löst Schritt 1-7 im
Vorbild `feat_1676_s1_premium_sms_rueckkanal.md` ab)

```
1. requireLocalOnly -- unveraendert.
2. Body: "from" (Pflicht, sonst 400), "code" (optional), "dry_run".
3. Premium-Kandidaten sammeln (EffectiveTier == "premium"); storedMatch =
   Kandidat mit PremiumSmsReplyTo == body.From.
4. storedMatch vorhanden UND now - storedMatch.PremiumSmsReplyAt <=
   model.PremiumSmsReplyTTL (D4) -> Ziel = storedMatch; ein mitgeschickter
   Code wird ignoriert, Ratebremse bleibt unberuehrt.
5. Sonst, kein Code im Body -> kein Ziel. (Der len(candidates)==1-Fallback
   entfaellt hier ersatzlos -- der eigentliche Bugfix.)
6. Sonst, Code vorhanden -> Ratebremse pruefen (D5): Budget erschoepft ->
   429, KEIN Hash-Vergleich. Budget frei -> bcrypt.CompareHashAndPassword
   gegen den gespeicherten Hash jedes Premium-Kandidaten mit einem Code:
   genau ein Treffer -> Ziel; kein oder mehrdeutiger Treffer -> Zaehler +1,
   kein Ziel, nie "default".
7. Kein Ziel -> Dry-Run "would_skip" mit Grund; real 409 (bzw. 429).
8. Ziel -> Dry-Run "would_learn" ohne Schreiben; real PremiumSmsReplyTo/-At
   setzen (Read-Modify-Write mit Merge), SaveUser.
```

### Ratebremse (D5)

Globaler In-Memory-Zähler für erfolglose Code-Vergleiche
(`internal/handler/premium_sms_ratelimit.go`), nicht je IP (immer localhost),
nicht je Absendernummer (fälschbar), nicht je Konto (ein Angreifer könnte
sonst gezielt mehrere Konten gleichzeitig aussperren, indem er denselben
falschen Code gegen jedes Konto probiert). Dry-Run-Aufrufe berühren den
Zähler nie — dieselbe strukturelle Trennung wie in
`premium_sms_connect.go:77-96`.

### Text-Zerlegung (D9) — eine Stelle für Payload und Befehlsverarbeitung

`src/services/inbound_sms_reader.py` bekommt eine einzige Funktion, die den
Code (falls vorhanden) vom übrigen Text trennt; sowohl der Payload-Aufbau
(heute Zeile 171-175, künftig `{"from": ..., "code": ..., "dry_run": ...}`)
als auch `_verarbeite_befehl` (Zeile 232-275, `befehl = text.split(...)`)
rufen dieselbe Funktion. Ohne diese Bündelung landet der Code sonst als
erstes Wort im ersten Befehl nach jeder Verknüpfung (größtes Bruchrisiko
dieses Umbaus).

### Keine Antwort an Unbekannte (D7)

Löst der Lernaufruf kein Ziel auf (409/429), unterbleibt jede ausgehende
Premium-SMS — das ergibt sich als *Folge* des bestehenden 409-Zweigs in
`inbound_sms_reader.py:245-251` (`_verarbeite_befehl` wird ohne `user_id`
gar nicht aufgerufen), ist also keine eigene Zusicherung im Code. Der Test
dazu muss am ausgehenden Versand messen (kein Premium-SMS-Send erfolgt),
nicht am Lern-Endpoint.

### Beobachtbarkeit (D8)

`api/routers/scheduler.py:167` zählt bisher nur Netz-/5xx-Fehler in
`last_failed_count`. Ein abgelehnter Lernversuch (409/429, bewusste
Ablehnung) muss zusätzlich in einem eigenen Zähler sichtbar werden, damit
`GET /api/scheduler/status` einen dauerhaft ausgesperrten Nutzer nicht
stillschweigend als „ok" meldet.

### Bestandsdaten-Migration (D6)

Testbare Migrationsfunktion (nicht Hand-Eingriff), die vorhandene
`PremiumSmsReplyTo`/`PremiumSmsReplyAt` auf allen Nutzern verwirft. Grund:
jede Variante mit Bestandserhalt hielte genau die möglicherweise entführte
Nummer als Bestätigungspfad am Leben. Betroffen ist heute genau ein Nutzer;
der muss sich einmal neu verknüpfen (Folge, kein Fehler).

### Affected Files

| Datei | Art |
|---|---|
| `internal/model/premium_sms_link.go` | CREATE |
| `internal/store/user.go` | MODIFY |
| `internal/handler/premium_sms_link_code.go` | CREATE |
| `internal/handler/premium_sms_connect.go` | MODIFY |
| `internal/handler/premium_sms_ratelimit.go` | CREATE |
| `internal/router/router.go`, `cmd/server/main.go` | MODIFY |
| `src/services/inbound_sms_reader.py` | MODIFY |
| `api/routers/scheduler.py` | MODIFY |
| Go- und Python-Tests (s. Test Plan) | CREATE/MODIFY |
| `docs/reference/api_contract.md`, `feat_1676_s1_premium_sms_rueckkanal.md`, `docs/features/architecture.md`, `docs/adr/0049-premium-sms-vierter-kanal.md` | MODIFY (Doku) |

## Expected Behavior

- **Input:** eingehende Garmin-SMS im seven.io-Journal, erkannt am Kennzeichen
  `inreachlink.com` (seit #2323: am `to`-Feld, s. Nachtrag oben); optional
  davor ein Verknüpfungs-Code (Format seit #2323: `XX`+3+3)
- **Output:** bei gültiger Auflösung (frischer gespeicherter Treffer ODER
  passender Code) aktualisierte `premium_sms_reply_to`/`-at` in genau einem
  `user.json`; bei fehlender/ungültiger Auflösung 409 bzw. 429, kein Schreiben,
  keine ausgehende Antwort
- **Side effects:** Ratenzähler für erfolglose Code-Vergleiche; Scheduler-
  Statusfeld für abgelehnte Lernversuche; einmalige Migrationsfunktion beim
  Umstieg verwirft bestehende Rückadressen

## Acceptance Criteria

- **AC-1:** Given genau ein Nutzer mit Tier `premium` existiert und für die
  eingehende Absendernummer liegt kein gespeicherter, frischer Treffer vor /
  When eine als Garmin erkannte Nachricht ohne gültigen Code eintrifft / Then
  wird sie NICHT diesem Nutzer zugeordnet, `user.json` bleibt unverändert, und
  der Lernaufruf antwortet mit einem Fehlerstatus statt 200.
  - Test: Ein-Nutzer-Fixture (Tier `premium`), Lernaufruf ohne `code` im
    Body, `user.json` vor/nach vergleichen (muss identisch sein), HTTP-Status
    prüfen. Reproduziert den Bug aus Nutzersicht (rot vor Fix — heute lernt
    der Ein-Kandidaten-Fallback die fremde Nummer —, grün nach Fix).

- **AC-2:** Given zwei Nutzer mit Tier `premium` haben je einen eigenen,
  gültigen Verknüpfungs-Code erzeugt / When zwei getrennte Garmin-Nachrichten
  von zwei unterschiedlichen Nummern eintreffen, jede mit dem Code genau des
  jeweils zugehörigen Nutzers / Then landet jede Nachricht bei dem Konto,
  dessen Code sie trägt — keine Verwechslung, kein Kandidat wird dem falschen
  Nutzer zugeordnet.
  - Test: Zwei-Nutzer-Fixture mit zwei erzeugten Codes, zwei Lernaufrufe mit
    vertauschbaren Absendernummern, danach beide `user.json` prüfen.

- **AC-3:** Given ein Nutzer hat eine gespeicherte, innerhalb der TTL
  liegende `premium_sms_reply_to` / When erneut eine als Garmin erkannte
  Nachricht von exakt dieser Nummer eintrifft, ohne Code / Then bestätigt der
  Lernaufruf weiterhin ohne Code, aktualisiert höchstens den Zeitstempel
  desselben Nutzers, und ordnet niemals neu einem anderen Kandidaten zu.
  - Test: Nutzer mit frischem `PremiumSmsReplyAt`, Nachricht ohne `code`,
    nur der Zeitstempel darf sich ändern, `PremiumSmsReplyTo` unverändert.

- **AC-4:** Given ein Nutzer hat eine gespeicherte `premium_sms_reply_to`,
  deren `PremiumSmsReplyAt` älter als `model.PremiumSmsReplyTTL` ist / When
  eine Nachricht von exakt dieser Nummer eintrifft, ohne Code / Then wird der
  Treffer als unbekannt behandelt, der Lernaufruf verlangt einen gültigen
  Code, und ohne Code bleibt `user.json` unverändert.
  - Test: Fixture mit `PremiumSmsReplyAt` = jetzt minus 31 Tage, Lernaufruf
    ohne Code, Ablehnung prüfen; mit korrektem Code desselben Nutzers muss
    dieselbe Nachricht anschließend zugeordnet werden.

- **AC-5:** Given ein Nutzer ruft den Konto-Endpoint zum Erzeugen eines
  Verknüpfungs-Codes auf / When die Antwort ausgewertet wird / Then enthält
  sie den Code genau einmal im Klartext, ein erneuter Statusaufruf liefert
  nur „vorhanden: ja", niemals den Code oder dessen Hash, und ein zweiter
  Erzeugungsaufruf entwertet den ersten Code (der alte Code wird danach vom
  Lernaufruf nicht mehr akzeptiert).
  - Test: Erzeugungsaufruf, danach Statusaufruf (Body enthält keinen Code),
    zweiten Erzeugungsaufruf, alten Code gegen den Lernaufruf prüfen (muss
    abgelehnt werden), neuen Code prüfen (muss angenommen werden).

- **AC-6:** Given zwei verschiedene Nutzer rufen je ihren eigenen
  Konto-Endpoint auf / When beide Aufrufe mit ihren jeweiligen
  Session-Kontexten erfolgen / Then erzeugt jeder Aufruf einen Code für die
  eigene, aus dem Auth-Kontext gelesene `user_id` — niemals für `"default"`
  und niemals für den jeweils anderen Nutzer.
  - Test: Zwei Sessions, zwei Aufrufe, danach beide `premium_sms_link.json`
    getrennt prüfen (verschiedene Hashes, keine Überschneidung).

- **AC-7:** Given der globale Fehlversuchszähler für Code-Vergleiche ist
  erschöpft / When ein weiterer Lernaufruf mit einem beliebigen (auch
  korrekten) Code eintrifft / Then antwortet der Aufruf mit 429, ohne dass
  ein Hash-Vergleich stattfindet, und kein `user.json` wird verändert.
  - Test: Zähler durch wiederholte Fehlversuche erschöpfen, danach Aufruf
    mit dem tatsächlich korrekten Code eines Kandidaten senden, 429 und
    unveränderten Nutzerdatensatz prüfen.

- **AC-8:** Given ein Dry-Run-Lauf (`GZ_PREMIUM_SMS_POLL_DRYRUN=1`,
  außerhalb Produktion) prüft einen falschen Code gegen einen Kandidaten /
  When der Dry-Run mehrfach hintereinander läuft / Then bleibt der
  Fehlversuchszähler für Code-Vergleiche unverändert bei null erhöhten
  Versuchen — Dry-Run-Läufe berühren die Ratebremse nie.
  - Test: Mehrere Dry-Run-Aufrufe mit falschem Code, Zählerstand vor/nach
    vergleichen (muss identisch sein).

- **AC-9:** Given eine unbekannte Nummer schickt eine als Garmin erkannte
  Nachricht ohne gültigen Code / When der Lernaufruf sie ablehnt (409) /
  Then wird an diese Nummer KEINE ausgehende Premium-SMS verschickt —
  geprüft am ausgehenden Versandpfad, nicht am Lernaufruf selbst.
  - Test: `poll_and_process()` mit Fixture, die eine unbekannte Nummer ohne
    Code enthält; Versand-Fake/-Double darf keinen Aufruf für diese Nummer
    verzeichnen.

- **AC-10:** Given der Umstieg auf diese Scheibe läuft (Migrationsfunktion
  wird ausgeführt) und mindestens ein Nutzer hat eine bestehende
  `premium_sms_reply_to`/`-at` / When die Migration läuft / Then sind
  `premium_sms_reply_to` und `premium_sms_reply_at` bei allen betroffenen
  Nutzern anschließend leer — kein Nutzer behält eine vor der Migration
  gelernte Rückadresse als gültigen Bestätigungspfad.
  - Test: Fixture mit vorbelegter Rückadresse, Migrationsfunktion ausführen,
    `user.json` danach auf leere Felder prüfen.

- **AC-11:** Given ein Lernaufruf wird wegen fehlendem/ungültigem Code
  abgelehnt (409) / When `GET /api/scheduler/status` danach abgefragt wird /
  Then zeigt der Status-Endpoint einen von reinen Netz-/5xx-Fehlern
  unterscheidbaren Zähler für abgelehnte Lernversuche — ein 409 meldet nicht
  länger unbemerkt `"status": "ok"`.
  - Test: Lernaufruf gezielt ablehnen lassen, `/api/scheduler/status` danach
    auf den neuen Zähler/Status prüfen.

- **AC-12:** Given eine Verknüpfungsnachricht enthält Code UND einen
  Befehlstext danach / When die Nachricht verarbeitet wird / Then wird der
  Code nicht Teil des an `TripCommandProcessor` weitergereichten Befehlstexts
  — der Code taucht nicht als erstes Wort im ausgeführten Befehl auf.
  - Test: Text `"<CODE> heute inreachlink.com/..."` verarbeiten, den an
    `TripCommandProcessor` übergebenen `befehl`-Wert prüfen (darf `<CODE>`
    nicht enthalten).

## Known Limitations

- **Garmins Rotationsrate ist weiterhin unbelegt.** „Garmin vergibt die
  Nummer je Gespräch neu" stützt sich auf eine einzelne Messung vom
  10.08.2026 (`feat_1676_s1…md:326`). Diese Scheibe macht die Rate bewusst
  irrelevant (Code wird immer verlangt, wenn kein frischer Treffer vorliegt),
  beweist sie aber nicht.
- **Kein Frontend für den Code.** Der Konto-Endpoint ist rein programmatisch
  nutzbar; eine Oberfläche zum Anzeigen/Erneuern folgt in Scheibe B.
  > **Nachtrag (2026-09-14):** Scheibe B ergänzt genau diese Oberfläche unter
  > `/account` (Karte „Code erzeugen/erneuern", nur für Tier `premium`),
  > ohne den hier beschriebenen Backend-Vertrag zu ändern — s.
  > `docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md`.
- **Die Ratebremse überlebt keinen Neustart.** Der Zähler liegt im
  Arbeitsspeicher; ein Dienst-Neustart setzt ihn auf null. Bewusst in Kauf
  genommen: die Bremse ist Tiefenstaffelung, nicht die tragende
  Sicherheitsgrenze. Diese trägt der Schlüsselraum von ≈ 2,75·10¹⁰ (7 Zeichen,
  ≈ 35 Bit) in Verbindung damit, dass jeder einzelne Rateversuch dem Angreifer
  eine echte, bezahlte SMS kostet und frühestens beim nächsten Fünf-Minuten-Poll
  überhaupt geprüft wird. Ein dateibasierter, neustartfester Zähler wäre die
  strengere Variante und gehört zu #2153, falls die Annahme je kippt.
  **Nachtrag (#2323):** der Schlüsselraum ist seither kleiner (≈ 6,23 Mio.
  ohne festen Präfix statt ≈ 2,75·10¹⁰) — macht die Ratebremse wichtiger als
  hier ursprünglich angenommen, s. `fix_2323_premium_sms_gate_generisch.md`
  Known Limitations.
- **Staging kann den Schreibpfad nicht beweisen.** Der Poll läuft außerhalb
  der Produktion nur mit `GZ_PREMIUM_SMS_POLL_DRYRUN=1`, dann ohne
  Schreibwirkung — der Nachweis liegt vollständig im Kern (Go- und
  Python-Tests).

## Test Plan

Kern-Schicht (deterministisch, kein Netz, kein echtes inReach):

- `internal/handler/premium_sms_connect_test.go` (MODIFY):
  - `TestLearnRejectsSoleCandidateWithoutCode` (AC-1, Bug-Reproduktion: rot
    vor Fix — heute greift `len(candidates)==1` —, grün nach Fix)
  - `TestLearnMatchesCodeToCorrectAccountAmongTwoUsers` (AC-2)
  - `TestLearnConfirmsFreshStoredMatchWithoutCode` (AC-3)
  - `TestLearnRejectsStaleStoredMatchWithoutCode` (AC-4)
  - `TestLearnExhaustedBudgetSkipsHashComparison` (AC-7: Budget erschöpft →
    429 ohne Hash-Vergleich)
  - `TestLearnDryRunNeverIncrementsRateLimit` (AC-8)
  - `TestSchedulerStatusSurfacesRejectedLearnAttempt` (AC-11, ggf. teilweise
    in `api/routers`-Tests)
- `internal/handler/premium_sms_link_code_test.go` (CREATE):
  - `TestLinkCodeReturnsCodeOnceInPlaintext` (AC-5)
  - `TestLinkCodeStatusNeverExposesCodeOrHash` (AC-5)
  - `TestLinkCodeRegenerateInvalidatesOldCode` (AC-5)
  - `TestLinkCodeUsesRealUserIDNeverDefault` (AC-6, zwei Nutzer)
- `internal/model/premium_sms_migration_test.go` (CREATE):
  - `TestMigrationClearsExistingReplyAddress` (AC-10)
- `tests/unit/test_inbound_sms_reply_learning.py` (MODIFY):
  - `test_unknown_sender_without_code_receives_no_outbound_reply` (AC-9)
  - `test_link_code_is_stripped_before_command_processing` (AC-12)
  - Payload-Test: `code` wird mitgeschickt, wenn im Text vorhanden

Live-E2E: **entfällt für diese Scheibe** — Staging kann den Schreibpfad
strukturell nicht prüfen (`GZ_PREMIUM_SMS_POLL_DRYRUN=1` blockt jedes
Schreiben). `/e2e-verify` prüft nur HTTP-Erreichbarkeit der neuen Routen
(Smoke), nicht das Sicherheitsverhalten selbst.

## Bug-Reproduktion

`TestLearnRejectsSoleCandidateWithoutCode` (Go, Kern-Schicht) reproduziert
den gemeldeten Bug aus Nutzersicht: eine fremde Absendernummer schreibt bei
genau einem Premium-Nutzer heute dessen `PremiumSmsReplyTo` — der Test ist
gegen den heutigen Code rot (Fallback greift), nach Entfernen des
`len(candidates)==1`-Zweigs grün.

## Out of Scope

- **Scheibe B** — Konto-Oberfläche im Frontend (Anzeigen/Erneuern des Codes
  als UI-Element). Umgesetzt in
  `docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md`.
- **#2153** — allgemeine Quoten/Rate-Limits am Profil.
- **#2159** — Localhost-Guard hängt am nginx-Header (separates Ticket).

## Abgelöste Entscheidungen

- `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` AC-4
  (Z. 303-304, Ein-Kandidaten-Fallback) — **abgelöst durch AC-1 dieser Spec.**
  Vermerk in der Zieldatei ergänzen, AC nicht löschen (historischer Beleg).
- `docs/features/architecture.md:203 ff.` („Rückkanal für genau einen
  Premium-Nutzer") — muss auf den Code-gestützten Mehrnutzer-Fall aktualisiert
  werden.
- `docs/adr/0049-premium-sms-vierter-kanal.md` — Verweis auf die alte
  Heuristik ergänzen/korrigieren, ADR-Status bleibt „Angenommen" (kein
  Grundsatzwechsel, nur Sicherheitsnachbesserung).
- `docs/reference/api_contract.md` — geänderte Payload
  `POST /api/internal/premium-sms-learn` (neues optionales Feld `code`), neue
  Endpunkte `GET`/`POST /api/auth/premium-sms-link-code`.

## Risiken

1. Die Rufnummer bleibt kein Wiedererkennungsmerkmal (Garmin vergibt sie neu)
   — durch den TTL-Abgleich (D4) strukturell irrelevant gemacht, nicht widerlegt.
2. Der IP-Rate-Limiter passt nicht auf diesen Pfad (Lernaufruf immer von
   localhost) — deshalb eigener Zähler (D5), nicht Wiederverwendung von
   `internal/middleware/ratelimit.go`.
3. Migrations-Spannung zwischen Bestandserhalt-Regel und Sicherheitsbefund —
   aufgelöst durch AC-10 (bewusstes Verwerfen als Funktion, PO-Freigabe über
   diese Spec).
4. Schema-Hook: Edits an `internal/model/user.go`/`internal/store/store.go`
   lösen `data_schema_backup.py` aus; Read-Modify-Write-Merge bleibt Pflicht
   (`SaveUser` ist Replace).
5. LoC-Grenze: Umfang sprengt 250 LoC je Workflow deutlich —
   `loc_limit_override 500` einplanen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (bestehendes ADR-0049 reicht)
- **Rationale:** ADR-0049 (Premium-SMS als vierter Kanal) legt den Kanal
  selbst fest, nicht die Zuordnungsmechanik. Diese Scheibe ersetzt eine
  fehlerhafte Heuristik durch ein Geheimnis-basiertes Verfahren nach
  bestehendem Muster (Passwort-Reset/E-Mail-Bestätigung/Telegram-Token) —
  kein neuer Architektur-Grundsatz, daher kein neues ADR. Der ADR-Text zur
  Rufnummern-Rotation (Zeile 65-67) bleibt gültig und wird um den Verweis auf
  den TTL-Abgleich im Eingang ergänzt.

## Changelog

- 2026-09-13: Initial spec erstellt — Issue #2154, Scheibe A
- 2026-09-14: Nachtrag — Scheibe B (Konto-Oberfläche für den Code unter
  `/account`) ergänzt, s. `docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md`
- 2026-09-14: Nachtrag — Code-Format auf `XX`+3+3 umgestellt und
  Akzeptanz-Gate auf `to == SERVICE_NUMBER` korrigiert, s.
  `docs/specs/modules/fix_2323_premium_sms_gate_generisch.md`
