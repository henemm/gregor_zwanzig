---
entity_id: fix_2328_premium_sms_rueckkanal_kollision
type: module
created: 2026-09-15
updated: 2026-09-15
status: draft
version: "1.0"
tags: [sms, inbound, premium, garmin, security, cross-user-leak]
---

<!-- Issue #2328. Folge-Bugfix auf fix_2154_premium_sms_verknuepfungscode.md
     (Scheibe A) -- die dortige Sammelschleife ueber "frische" Treffer wurde
     nie auf Mehrfachtreffer geprueft. -->

# Premium-SMS-Rückkanal: Kollisionserkennung beim „ohne Code"-Zuordnungsweg

## Approval

- [ ] Approved

## Purpose

`resolvePremiumSmsTarget` bestätigt eine eingehende Garmin-Nummer ohne Code,
sobald irgendein Nutzer mit dieser gespeicherten Rückadresse als „frisch"
gilt. Weil Garmin dieselbe Rückadresse aus einem rotierenden Pool erneut
vergeben kann, können zwei Premium-Nutzer zeitgleich `PremiumSmsReplyTo ==
body.From` mit `PremiumSmsStateFresh` haben — die Sammelschleife
(`premium_sms_connect.go:69-83`) überschreibt `storedMatch` dann
kommentarlos mit dem zuletzt geladenen Nutzer. Es gibt keinen Log-Eintrag,
keinen Fehler, keine Möglichkeit für den verdrängten Nutzer, das zu
bemerken: seine Trip-Daten würden für den anderen Nutzer beantwortet, sein
Datensatz mit dessen Nummer überschrieben (Cross-User-Datenleck). Diese
Spec führt eine Freshness-gefilterte Mehrfachtreffer-Prüfung ein, die bei
≥2 frischen Kandidaten nicht sofort ablehnt, sondern zum bestehenden
Code-Pfad durchreicht — damit ein Nutzer mit gültigem Verknüpfungs-Code die
Kollision weiterhin auflösen kann und sich niemand selbst aussperrt.

## Source

- **File:** `internal/handler/premium_sms_connect.go`
- **Identifier:** `func PostPremiumSmsLearnHandler`, `func
  resolvePremiumSmsTarget`

> **Schicht-Hinweis:** Go-API (`internal/handler/`, localhost-only
> Lern-Endpoint `POST /api/internal/premium-sms-learn`, Production-API auf
> Port 8090). Kein Frontend-, kein Python-Core-Anteil — der einzige
> Python-Konsument (`src/services/inbound_sms_reader.py:268-278`) wertet
> nur den HTTP-Statuscode-Bereich aus und bleibt unverändert (s.
> Dependencies). Grep über `internal/` bestätigt: `resolvePremiumSmsTarget`
> hat außerhalb von `premium_sms_connect.go` keine weiteren Aufrufstellen
> (nur Zeile 92/111 innerhalb derselben Datei) — die Signaturänderung
> berührt keine dritte Datei.

## Estimated Scope

- **LoC:** ~20-25 Produktivcode, ~100-130 Tests (2 Code-Dateien) + kurzer
  Dokumentations-Nachtrag
- **Files:** 2 Code-Dateien + 1 Doku-Datei (`docs/reference/api_contract.md`)
- **Effort:** low — bleibt unter dem 250-LoC-Workflow-Limit, kein
  `loc_limit_override` nötig (Doku zählt laut CLAUDE.md ohnehin nicht ins
  LoC-Limit)

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `internal/handler/premium_sms_connect.go` | MODIFY | Sammelschleife liefert alle Kandidaten statt des letzten Treffers; `resolvePremiumSmsTarget` filtert intern auf frische Treffer und unterscheidet 0/1/≥2; neuer Ablehnungsgrund `reasonStoredReplyToAmbiguous`; Entscheidungsbaum-Kommentar (Zeile 13-22) nachgezogen |
| `internal/handler/premium_sms_connect_test.go` | MODIFY | 4 neue Testfälle (Fälle a-d der Testmatrix) + 1 Regressionstest für den unveränderten Ein-Kandidat-Fall |
| `docs/reference/api_contract.md` | MODIFY | neuer `reason`-Wert `stored_reply_to_ambiguous` bei `POST /api/internal/premium-sms-learn` (409-Zeile ~3242 und `would_skip`-Beispiel ~3227-3234) ergänzt — reine Ergänzung, die bereits bestehende Drift der Reason-Strings in diesem Abschnitt (`no_unique_premium_candidate` vs. tatsächlich `link_code_required`/`link_code_invalid`) wird NICHT rückwirkend korrigiert, das ist Altlast aus #2154 und nicht Gegenstand dieser Spec |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/premium_sms.go::DerivePremiumSmsReplyState` / `PremiumSmsStateFresh` / `PremiumSmsReplyTTL` | module | Freshness-Filter der Kandidaten — dieselbe Fristformel wie im Sendepfad und in der Oberfläche, keine zweite Formel hier einführen |
| `internal/store/store.go::ListUserIDs/LoadUser/SaveUser` | module | Nutzer-Iteration und Persistenz, Read-Modify-Write mit Merge (`SaveUser` ist Replace, betroffene Felder gezielt setzen) |
| `internal/store/store.go::LoadLinkCode` | module | bcrypt-gestützter Code-Vergleich im bestehenden Schritt 6, unverändert wiederverwendet |
| `internal/handler/premium_sms_ratelimit.go::PremiumSmsRateLimiter` | module | Budget-Prüfung vor jedem Hash-Vergleich, unverändert — auch im Kollisionsfall zuerst gefragt |
| `internal/model/tier.go::EffectiveTier` | module | Premium-Kandidatenfilter, unverändert |
| `src/services/inbound_sms_reader.py:268-278` | Downstream-Konsument, unverändert | wertet nur den HTTP-Statuscode-Bereich (409) aus, nicht den `reason`-String — keine Python-Änderung nötig |
| `docs/reference/api_contract.md` (Abschnitt `POST /api/internal/premium-sms-learn`) | Dokumentation | Single Source of Truth für DTOs (CLAUDE.md); neuer `reason`-Wert wird ergänzt |
| `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` | Vorgänger-Spec | führte den hier fehlerhaften Freshness-Filter samt Code-Pfad ein; diese Spec korrigiert dessen Mehrfachtreffer-Lücke, löst nichts davon ab |

## Implementation Details

Bereits entschiedener Ansatz (keine Alternativen offen), fünf Schritte:

1. **Sammelschleife liefert alle Kandidaten.** `var storedMatch *model.User`
   (Zeile 70) wird zu `var storedMatches []*model.User`; die Zuweisung
   `storedMatch = user` (Zeile 81) wird zu `storedMatches = append(storedMatches,
   user)` — unabhängig vom Alter, die Freshness-Filterung passiert erst in
   Schritt 2.

2. **`resolvePremiumSmsTarget` ändert Signatur** (betrifft beide
   Aufrufstellen: Dry-Run Zeile 92, real Zeile 111 — Parameter `storedMatch
   *model.User` wird zu `storedMatches []*model.User`) und filtert intern auf
   `DerivePremiumSmsReplyState(...) == PremiumSmsStateFresh`:
   - **0 fresh** → weiter zu Schritt 5 des bestehenden Baums (`code == ""` →
     `reasonLinkCodeRequired`, unverändert).
   - **genau 1 fresh** → heutiges korrektes Verhalten, unverändert sofortiges
     Ziel, Code wird ignoriert.
   - **≥2 fresh** → NICHT sofort ablehnen. Der Kollisionsfall wird an einer
     eigenen Stelle markiert (z.B. lokale Variable `ambiguous := true`) und
     durchläuft trotzdem den bestehenden Code-Pfad (Schritt 6, unveränderter
     bcrypt-Vergleich über alle `candidates`) — ein Nutzer mit gültigem
     Verknüpfungs-Code muss die Kollision weiterhin auflösen können, sonst
     wäre das ein Self-DoS/Lockout, aus dem sich die Kollision nie mehr
     heilt. Erst wenn dieser Pfad danach an `code == ""` scheitert (Zeile
     161), greift statt `reasonLinkCodeRequired` der neue Grund
     `reasonStoredReplyToAmbiguous`. **Wichtig:** Scheitert der Code-Pfad
     stattdessen an einem Code, der zu keinem Kandidaten passt (Zeile
     179-183), bleibt es beim bestehenden `reasonLinkCodeInvalid` — die
     Ambiguitäts-Markierung muss also gezielt nur den `code == ""`-Zweig
     umleiten, nicht den ganzen restlichen Baum.

3. **Dry-Run-Pfad und echter Pfad bleiben identisch.** Beide rufen
   `resolvePremiumSmsTarget` mit denselben Parametern auf (Zeile ~92 mit
   `rl.scratch()`, Zeile ~111 mit der echten Bremse) — keine Sonderbehandlung
   für den Kollisionsfall nötig, da die Logik vollständig in der gemeinsamen
   Funktion sitzt.

4. **HTTP-Transport bleibt unverändert.** Der bestehende
   `http.StatusConflict` (Zeile 121) deckt auch `reasonStoredReplyToAmbiguous`
   ab — der Python-Konsument wertet nur den Statuscode-Bereich aus, keine
   Änderung an `src/services/inbound_sms_reader.py` nötig.

5. **Entscheidungsbaum-Kommentar nachziehen.** Der Kommentarblock in
   `premium_sms_connect.go:13-22` wird als spec-tragend behandelt und muss um
   den Mehrdeutigkeitsfall ergänzt werden: „bei ≥2 frischen Treffern wird
   nicht sofort abgelehnt, sondern der Code-Pfad entscheidet; scheitert dieser
   mangels Code, lautet der Grund `reasonStoredReplyToAmbiguous` statt
   `reasonLinkCodeRequired`".

## Expected Behavior

- **Input:** POST an `/api/internal/premium-sms-learn` mit `from` (Pflicht),
  optional `code`, optional `dry_run` — unverändertes Request-Schema
- **Output:** bei genau einem frischen Treffer oder einem zu genau einem
  Kandidaten passenden Code weiterhin HTTP 200 mit aktualisiertem Ziel-Nutzer;
  bei ≥2 frischen Treffern ohne (passenden) Code neu HTTP 409 mit
  `reason: "stored_reply_to_ambiguous"` statt der bisherigen stillen
  Fehlzuordnung an den zuletzt geladenen Nutzer
- **Side effects:** bei Ablehnung (0 fresh ohne Code, ≥2 fresh ohne
  auflösenden Code) erfolgt kein `SaveUser` bei irgendeinem der beteiligten
  Kandidaten — insbesondere ändert sich bei einer Kollision weder der
  verdrängte noch der fälschlich bevorzugte Nutzerdatensatz

## Acceptance Criteria

- **AC-1:** Given zwei Premium-Nutzer haben jeweils einen frischen
  gespeicherten Treffer auf dieselbe eingehende Absendernummer / When eine
  Garmin-Nachricht von dieser Nummer ohne Code eintrifft / Then lehnt der
  Lernaufruf mit HTTP 409 und Grund `reasonStoredReplyToAmbiguous` ab, und
  bei keinem der beiden Nutzer wird `SaveUser` aufgerufen.
  - Test: Zwei Fixture-Nutzer mit identischer `PremiumSmsReplyTo` und
    frischem `PremiumSmsReplyAt`, Lernaufruf ohne `code`, HTTP-Status und
    `reason` prüfen, beide `user.json` vor/nach byte-identisch vergleichen.
    Reproduziert den Bug aus Nutzersicht (rot vor Fix — heute gewinnt
    kommentarlos der zuletzt geladene Nutzer —, grün nach Fix).

- **AC-2:** Given dieselbe Kollision aus AC-1 besteht und einer der beiden
  Nutzer hat einen gültigen Verknüpfungs-Code erzeugt / When die Garmin-
  Nachricht mit genau diesem Code eintrifft / Then antwortet der Lernaufruf
  mit HTTP 200, aktualisiert `PremiumSmsReplyTo`/`PremiumSmsReplyAt` exakt
  bei dem Nutzer, dessen Code passt, und lässt den anderen Nutzer
  unverändert — die Kollision sperrt niemanden dauerhaft aus.
  - Test: Zwei Fixture-Nutzer wie in AC-1, einer mit erzeugtem
    Verknüpfungs-Code, Lernaufruf mit diesem Code, HTTP-Status und
    `user_id` im Antwortkörper prüfen, `user.json` beider Nutzer danach
    vergleichen (nur der code-tragende Nutzer geändert).

- **AC-3:** Given ein Nutzer hat einen frischen Treffer auf die eingehende
  Nummer und ein zweiter Nutzer hat einen veralteten (`stale`, außerhalb der
  TTL) Treffer auf dieselbe Nummer / When die Nachricht ohne Code eintrifft /
  Then wird sie deterministisch dem frischen Nutzer zugeordnet (HTTP 200),
  ohne dass der Kollisionsfall greift — eine reine Zählung aller Treffer
  (ohne Freshness-Filter) würde hier fälschlich mit 409 ablehnen.
  - Test: Ein Fixture-Nutzer mit frischem, einer mit abgelaufenem
    `PremiumSmsReplyAt` auf dieselbe Nummer, Lernaufruf ohne `code`,
    HTTP 200 und Ziel-`user_id` gleich dem frischen Nutzer prüfen; Regressions-
    wächter gegen eine naive Treffer-Zählung, die diesen Fall fälschlich als
    Kollision behandeln würde.

- **AC-4:** Given dieselbe Kollisionslage wie in AC-1 / When der Lernaufruf
  mit `dry_run: true` und ohne Code ausgeführt wird / Then meldet die
  Antwort `outcome: "would_skip"` mit Grund `reasonStoredReplyToAmbiguous`,
  und bei keinem der beiden Nutzer wird `SaveUser` aufgerufen.
  - Test: Fixture wie AC-1, Lernaufruf mit `dry_run: true`, Antwortkörper auf
    `outcome`/`reason` prüfen, beide `user.json` vor/nach vergleichen (muss
    identisch bleiben).

- **AC-5:** Given genau ein Premium-Nutzer hat einen frischen gespeicherten
  Treffer auf die eingehende Nummer, kein anderer Nutzer trägt dieselbe
  Nummer / When die Nachricht ohne Code eintrifft / Then bleibt das
  Verhalten unverändert gegenüber dem Stand vor diesem Fix: HTTP 200,
  genau dieser Nutzer wird aktualisiert — der neue Mehrfachtreffer-Pfad
  verändert den unkritischen Ein-Kandidaten-Fall nicht.
  - Test: Ein Fixture-Nutzer mit frischem Treffer, Lernaufruf ohne `code`,
    HTTP 200 und aktualisierten `user.json` prüfen (Regressionsschutz gegen
    die bestehende Testabdeckung aus `fix_2154_premium_sms_verknuepfungscode.md`).

## Known Limitations

- **Kollision heilt nur über einen gültigen Verknüpfungs-Code.** Haben beide
  kollidierenden Nutzer keinen Code erzeugt, bleibt die Nummer bis zur
  nächsten TTL-Ablauf-Runde oder bis mindestens ein Nutzer einen Code anlegt
  dauerhaft mit `reasonStoredReplyToAmbiguous` blockiert — bewusst in Kauf
  genommen, die Alternative (stillschweigend einem Nutzer zuordnen) ist genau
  der hier behobene Bug.
- **#2154 AC-1 (`reasonLinkCodeRequired` ohne Code) bleibt für den 0-fresh-Fall
  unverändert gültig** — nur der neu hinzukommende ≥2-fresh-Fall bekommt den
  eigenen Grund `reasonStoredReplyToAmbiguous`.
- **Der neue Grund ist nur im HTTP-Antwortkörper des Lernaufrufs sichtbar,
  nicht operativ beobachtbar.** Der einzige Konsument
  (`src/services/inbound_sms_reader.py:268-278`) wertet laut dem
  entschiedenen Ansatz bewusst nur den Statuscode aus und verwirft den
  `reason`-String; weder `/api/scheduler/status` noch ein Log erfahren, dass
  konkret eine Kollision statt eines fehlenden Codes vorlag. Die im Bug
  beklagte Stille ist damit für den betroffenen Endpoint-Aufruf selbst
  behoben (er lehnt jetzt korrekt und mit unterscheidbarem Grund ab statt
  fälschlich zuzuordnen), nicht aber operativ sichtbar gemacht — eine
  Erweiterung der Beobachtbarkeit ist bewusst nicht Teil dieser Spec.

## Test Plan

Kern-Schicht (deterministisch, kein Netz, echter Store gegen
`t.TempDir()`, kein Mock):

- `internal/handler/premium_sms_connect_test.go` (MODIFY):
  - `TestLearnRejectsAmbiguousFreshCollisionWithoutCode` (AC-1,
    Bug-Reproduktion: rot vor Fix — heute gewinnt kommentarlos der zuletzt
    geladene Nutzer —, grün nach Fix)
  - `TestLearnResolvesAmbiguousCollisionWithValidCode` (AC-2)
  - `TestLearnPrefersFreshMatchOverStaleCollisionWithoutCode` (AC-3,
    Regressionswächter gegen naive Treffer-Zählung ohne Freshness-Filter)
  - `TestLearnDryRunReportsAmbiguousCollisionWithoutSaving` (AC-4)
  - `TestLearnConfirmsFreshStoredMatchWithoutCode` (AC-5 — bereits
    bestehender Test aus `fix_2154_premium_sms_verknuepfungscode.md`; hier
    NICHT neu schreiben, nur gegenlesen, dass er nach der Signaturänderung
    von `resolvePremiumSmsTarget` weiterhin grün bleibt)

Live-E2E: **entfällt für diese Änderung** — der Poll läuft außerhalb der
Produktion nur mit `GZ_PREMIUM_SMS_POLL_DRYRUN=1`, dann ohne Schreibwirkung
(gleiche Einschränkung wie bei `fix_2154_premium_sms_verknuepfungscode.md`).
Der Nachweis liegt vollständig im Kern; `/e2e-verify` prüft nur HTTP-
Erreichbarkeit, nicht das Kollisionsverhalten selbst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reiner Bugfix innerhalb der mit Issue #1676 Scheibe S1 und
  #2154 Scheibe A bereits etablierten Zuordnungsmechanik — es wird keine neue
  Entscheidungsfläche berührt (kein neuer Kanal, kein neuer Provider, kein
  neues Datenmodell, kein neues Auth-Verfahren). Die Freshness-Filterung und
  der Code-Pfad selbst wurden bereits in `fix_2154_premium_sms_verknuepfungscode.md`
  entschieden; diese Spec korrigiert ausschließlich eine dort unentdeckte
  Mehrfachtreffer-Lücke in der Umsetzung.

## Changelog

- 2026-09-15: Initial spec created
