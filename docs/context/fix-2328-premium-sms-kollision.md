# Kontext: Fix #2328 — Premium-SMS-Rückkanal Kollisions-Ambiguität

## Bug Report

- **Location:** `internal/handler/premium_sms_connect.go`
- **Problem:** Beim „ohne Code"-Zuordnungsweg überschreibt die Kandidaten-Sammelschleife (Zeile 69-83) `storedMatch` bei jedem Treffer auf `PremiumSmsReplyTo == body.From` kommentarlos. `resolvePremiumSmsTarget` (Zeile 147-157) übernimmt diesen einen Wert ungeprüft, sobald er „frisch" ist. Haben zwei Premium-Nutzer zufällig dieselbe gespeicherte Rückadresse (Garmin vergibt diese aus einem rotierenden Pool, nicht exklusiv pro Gerät), gewinnt kommentarlos der zuletzt in `ListUserIDs()`/`LoadUser()` geladene Account — kein Log, kein Fehler.
- **Expected:** Mehrdeutigkeit wird erkannt und sauber abgelehnt statt zufällig aufgelöst — analog zum Code-Weg, der bei `len(matches) != 1` bereits ablehnt.
- **Root Cause:** `internal/handler/premium_sms_connect.go:69-83` (Sammlung ohne Mehrfachtreffer-Erkennung) + `:147-157` (`resolvePremiumSmsTarget` nimmt `storedMatch` ungeprüft).
- **Impact:** Cross-User-Datenleck — Nutzer A's Tourdaten würden für Nutzer B beantwortet, A's Datensatz mit B's Nummer überschrieben (`SaveUser`).
- **Effort:** Klein (isoliert, ~20-25 LoC Produktivcode + ~100-130 LoC Tests, keine Python-Seite betroffen).

## Analysis

### Type
Bug

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/handler/premium_sms_connect.go` | MODIFY | `storedMatch *model.User` → `storedMatches []*model.User` in der Sammelschleife (Zeile 69-83); `resolvePremiumSmsTarget` filtert intern auf `PremiumSmsStateFresh` und unterscheidet 0/1/≥2 Treffer; neue Ablehnungs-Konstante `reasonStoredReplyToAmbiguous`; Entscheidungsbaum-Kommentar (Zeile 13-22) nachziehen |
| `internal/handler/premium_sms_connect_test.go` | MODIFY | 4 neue Testfälle (siehe Testmatrix unten) |

### Scope Assessment
- Files: 2
- Estimated LoC: +120/-5 (grob; ~20-25 Produktivcode, ~100-130 Tests)
- Risk Level: LOW — Änderung ist isoliert (kein anderer Ort im Repo hat dasselbe Reverse-Lookup-Muster), bestehende Ein-Kandidat-Tests bleiben unverändert grün

### Technical Approach

**Freshness-gefilterte Mehrfachtreffer-Prüfung statt reiner Treffer-Zählung.** Wichtige Präzisierung gegenüber dem naiven Ausgangsvorschlag im Bug-Report: nicht jeder Mehrfachtreffer auf dieselbe Nummer ist eine echte Kollision — durch die Nummern-Rotation ist es normal, dass ein alter (`stale`) Datensatz eines Nutzers dieselbe Nummer trägt wie ein frisch gelernter (`fresh`) eines anderen. Eine reine Treffer-Zählung ohne Freshness-Filter würde legitime Lernvorgänge blockieren, sobald eine Nummer recycelt wird.

1. Sammelschleife liefert `storedMatches []*model.User` (alle Kandidaten mit `PremiumSmsReplyTo == body.From`, unabhängig vom Alter) — `append` statt Überschreiben.
2. `resolvePremiumSmsTarget` filtert intern auf `DerivePremiumSmsReplyState(...) == PremiumSmsStateFresh` (bleibt die einzige Stelle dieser Formel, kein Drift-Risiko):
   - **0 fresh** → normaler Fall, weiter zu Schritt 5 (`code == ""` → `reasonLinkCodeRequired`).
   - **1 fresh** → heutiges korrektes Verhalten, unverändert.
   - **≥2 fresh** → **nicht sofort ablehnen**, sondern zum Code-Pfad (Schritt 6, bcrypt-Vergleich) durchreichen. Ein Nutzer mit gültigem Verknüpfungs-Code muss trotzdem funktionieren — sonst wäre der Fix ein Self-DoS, der Kollisionen nie mehr auflösen lässt. Scheitert der Code-Pfad danach an `code == ""`, greift der **neue** Reason `reasonStoredReplyToAmbiguous` statt des bestehenden `reasonLinkCodeRequired`, damit das im Bug beklagte Schweigen tatsächlich behoben ist (unterscheidbar von „kein Code angegeben").
3. Dry-Run-Pfad (`:92`, `rl.scratch()`) und echter Pfad (`:111`) durchlaufen identischen Code — keine Sonderbehandlung nötig, AC-7/AC-8-Reihenfolge bleibt strukturell unberührt.
4. HTTP-Transport: bestehender `http.StatusConflict` (Zeile 121) genügt — Python (`inbound_sms_reader.py:268-278`) wertet nur den Statuscode-Bereich aus, nicht den `reason`-String (per Grep bestätigt). Keine Python-Änderung nötig.

**Testmatrix** (realer Store, keine Mocks, Muster wie bestehende Tests):
- (a) Zwei frische Kollisionsnutzer, kein Code → Ablehnung mit `reasonStoredReplyToAmbiguous`, kein `SaveUser` bei beiden.
- (b) Dieselbe Kollision, gültiger Code eines der beiden Nutzer → 200, korrekter Nutzer aktualisiert, anderer unverändert (Beweis gegen Lockout/Self-DoS).
- (c) Ein frischer + ein stale-Treffer auf derselben Nummer, kein Code → 200 für den frischen Nutzer, deterministisch (Regressionswächter gegen die naive Zähl-Variante ohne Freshness-Filter).
- (d) Dry-Run-Variante von Fall (a) → `would_skip`.

### Dependencies
Keine. Grep über `PremiumSmsReplyTo`-Reverse-Lookup im gesamten Go- und Python-Baum zeigt: das Muster „welcher Nutzer hat diese Nummer zuletzt gespeichert" existiert nur in `premium_sms_connect.go`. `internal/store/premium_sms_migration.go:34` und der Sendepfad (`src/output/channels/premium_sms.py`) lesen jeweils nur das Feld eines bereits feststehenden Nutzers — nicht betroffen.

### Open Questions
Keine offenen Fragen — Ansatz ist eindeutig, Risiko niedrig, keine PO-Entscheidung nötig.
