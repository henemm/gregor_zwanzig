---
entity_id: fix_1555_tier_antrag_sichtbarkeit
type: bugfix
created: 2026-08-07
updated: 2026-08-07
status: draft
workflow: fix-1555-tier-antrag-sichtbarkeit
---

# Sichtbarkeit offener Tier-Freischalt-Anträge

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-07, alle 9 ACs auf Deutsch vorgelegt

## Purpose

Ein Nutzer-Antrag auf Level-Wechsel (`POST /api/auth/tier-change-request`) löst
heute **genau eine** Mail an den Betreiber aus und danach nie wieder etwas —
es gibt keinen Code-Pfad, der ihn erneut sichtbar macht. Geht diese eine Mail
unter, bleibt der Antrag für immer unbemerkt. Real geschehen: ein Antrag lag
vier Wochen unbemerkt, wodurch ein Nutzer im Free-Tier (2 Alarme/Tag)
feststeckte und während einer laufenden Bergtour keine akuten Wetter-Alarme
bekam. Diese Spec macht offene Anträge im bestehenden, bereits beobachteten
Status-Endpoint dauerhaft sichtbar — ohne dabei preiszugeben, *wer* einen
Antrag gestellt hat (der Endpoint ist ohne Login erreichbar).

**Nicht Gegenstand:** Die Nutzer-seitige Anzeige „Level-Wechsel beantragt —
wird vom Betreiber geprüft" existiert bereits seit #1071
(`frontend/src/routes/account/+page.svelte:629-632`) und wird nicht
angefasst. Der zweite Teil von Issue #1555 (NowCast-Vorrang im geteilten
Tagesbudget, Python-Core) läuft als eigener Workflow
`fix-1555-nowcast-alert-priority` und ist hier ebenfalls nicht Gegenstand.

## Source

- **File:** `internal/scheduler/tier_request_health.go` (neu)
- **Identifier:** `func (s *Scheduler) TierRequestHealth() map[string]any`

## Estimated Scope

- **LoC:** ~105 (Code ~55 inkl. `EffectiveTier`-Umzug, Tests ~50)
- **Files:** 7 im Repo (siehe Scope-Tabelle) + 1 Fremd-Repo-Auftrag (nicht Teil dieser Lieferung)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/scheduler/scheduler.go` (`Status()`) | Go-Funktion | Hängt `tier_request_health` als neuen Schlüssel in die bestehende Status-Map ein — 1:1 nach dem Muster von `briefing_health`/`warn_service_health`/`forecast_budget` |
| `internal/store/user.go` (`ListUserIDs`, `LoadUser`) | Go-Funktion | Liest alle registrierten Nutzer und deren `user.json` |
| `internal/model/user.go` (`User.Tier`, `User.RequestedTier`, `User.RequestedAt`) | Datenmodell | Quelle der Offen/Erledigt-Auswertung |
| `internal/model/tier.go` (`EffectiveTier`, **neu zu exportieren**) | Go-Funktion | Normalisiert ein leeres/ungültiges `tier` auf `"free"` — dieselbe Regel muss die neue Auswertung anwenden, sonst driften Anzeige und Antragslogik auseinander. Liegt heute als **unexported** `effectiveTier` in `internal/handler/auth.go:767` und ist aus `package scheduler` **nicht erreichbar** — siehe Implementation Details |
| `internal/mail/tier_change.go` (`BuildTierChangeRequestMail`) | Go-Funktion | Bedienungsanleitung an den PO — wird um den Hinweis „auch `requested_tier` entfernen" ergänzt |
| `internal/middleware/auth.go:34` | Middleware | Bestätigt: `/api/scheduler/status` ist von der Auth-Ausnahme erfasst, also öffentlich — bindet die Datenschutz-Anforderung |
| *(Fremd-Repo)* `henemm-infra/scripts/check-gregor20.sh:119` | Monitor-Script | Liest `/api/scheduler/status` bereits aus; muss die 7-Tage-Schwelle auswerten, damit ein echter Alarm entsteht — **nicht Teil dieser Lieferung**, siehe Known Limitations |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/tier_request_health.go` | CREATE | `TierRequestHealth()` — aggregiert offene Anträge über alle Nutzer, liefert nur Zahlen (kein `user_id`/Name/E-Mail); 1:1 nach dem Muster von `briefing_health.go:67-149` |
| `internal/scheduler/tier_request_health_test.go` | CREATE | Wirkungs-, Rand- und Datenschutz-Tests (Vorbild `briefing_health_test.go`) |
| `internal/scheduler/scheduler.go:672-680` | MODIFY | Neuen Schlüssel `"tier_request_health": s.TierRequestHealth()` in die `Status()`-Map einhängen |
| `internal/model/tier.go` | MODIFY | `effectiveTier` aus `handler` hierher als exportiertes `EffectiveTier()` heben (~6 LoC) — Voraussetzung dafür, dass der Scheduler dieselbe Normalisierung nutzt statt einer Kopie |
| `internal/handler/auth.go:765-772,806` | MODIFY | Lokale `effectiveTier`-Definition entfernen, Aufrufstelle auf `model.EffectiveTier` umstellen — Verhalten unverändert |
| `internal/mail/tier_change.go:22,34` | MODIFY | Hinweistext um „auch `requested_tier` entfernen" ergänzen (Plain- und HTML-Teil) |
| `internal/mail/tier_change_test.go` | CREATE | Prüft, dass der Freigabe-Hinweis beide Felder (`tier` UND `requested_tier`) nennt |
| `docs/reference/api_contract.md` (Abschnitt „12) Scheduler Status Endpoint", ab Zeile 1074) | MODIFY | Neues Antwortfeld `tier_request_health` dokumentieren |

**Außerhalb des Repos, aber Teil des Lieferumfangs (kein Git-Diff):**

| Ziel | Change Type | Description |
|------|-------------|-------------|
| Produktions-`.env` auf dem Server (nicht versioniert) | MODIFY | `GZ_PO_EMAIL` von `henning.emmrich@gmail.com` auf `henning@henemm.com`; danach `gregor-api` neu starten, damit die Config-Änderung greift (`internal/config/config.go:39`) |
| `henemm-infra` (Fremd-Repo) | MQ-Nachricht + Issue | Auftrag an die `infra`-Instanz: `check-gregor20.sh` um die 7-Tage-Schwellenprüfung auf `tier_request_health` erweitern — **erst dadurch entsteht ein echter Alarm**, siehe Known Limitations |

### Estimated Changes

- Files: 6 im Repo (4 Code/Test, 2 Doku/Test-Mailtext)
- LoC: +90/-4 im Repo (Doku zählt nicht gegen das LoC-Limit)

## Implementation Details

**Offen-Definition (nach Nachtrag, robust gegen abweichend gewährte Level):**
Ein Antrag gilt als **erledigt**, wenn `RequestedTier == ""` **ODER**
`effectiveTier(Tier) == RequestedTier`. Nur wenn `RequestedTier != ""` **und**
sich von `effectiveTier(Tier)` unterscheidet, zählt der Antrag als **offen**.
Das deckt beide in der Praxis beobachteten Freigabe-Handhabungen ab (PO setzt
`tier` und lässt `requested_tier` stehen → über `tier == requested_tier`
erkannt; PO setzt `tier` und löscht `requested_tier` → über die leere Prüfung
erkannt) und vermeidet, dass eine reine „`requested_tier` nicht leer"-Prüfung
einen längst erledigten Antrag für immer als offen zählt.

**Voraussetzung: `effectiveTier` muss erst erreichbar werden.** Die
Normalisierung liegt heute als **unexported** `effectiveTier` in
`internal/handler/auth.go:767` (package `handler`) und ist aus
`package scheduler` nicht aufrufbar. Sie wird deshalb nach
`internal/model/tier.go` als exportiertes `model.EffectiveTier(tier string) string`
gehoben — dort steht mit `SmsAllowed()` bereits die verwandte Tier-Logik. Die
einzige bestehende Aufrufstelle (`auth.go:806`) wird umgestellt; Verhalten
bleibt identisch. **Die Logik darf nicht im Scheduler kopiert werden** — eine
zweite Kopie driftet unweigerlich von der Anzeige weg und ist genau der
Fehlertyp, den diese Spec verhindern soll.

`TierRequestHealth()` folgt dem Aufbau von `BriefingHealth()`
(`internal/scheduler/briefing_health.go:67-149`):

1. `s.store.ListUserIDs()` liefert alle Nutzer mit `user.json`.
2. Pro Nutzer `s.store.LoadUser(id)`; liefert `LoadUser` einen Fehler oder
   `nil` (fehlende/kaputte `user.json`), wird dieser Nutzer übersprungen —
   **fail-soft**, ein einzelner defekter Datensatz darf die Gesamtauswertung
   nicht kippen (Vorbild `briefing_health.go:85`).
3. Ist der Antrag laut obiger Definition offen: `openCount++`; ist
   `RequestedAt` gesetzt, fließt sein Alter in die Ältester-Antrag-Berechnung
   ein (`if !haveOldest || requestedAt.Before(oldest)`).
4. Rückgabe ausschließlich als Zahlen/Dauer — kein `user_id`, kein
   `display_name`, keine E-Mail:

```
map[string]any{
  "open_count":            int,
  "oldest_open_age_hours": float64,  // 0.0 wenn open_count == 0
}
```

Die 7-Tage-Überfälligkeitsschwelle wird **nicht** in diesem Endpoint
kodiert — analog zum bestehenden Muster (`briefing_health` liefert rohe
Stunden, keine Ampel-Bewertung). Die Schwellenprüfung gehört laut
PO-Entscheidung in den externen Monitor (`check-gregor20.sh`, Fremd-Repo,
separater Lieferpunkt).

`scheduler.go`'s `Status()` bekommt einen zusätzlichen Map-Eintrag
`"tier_request_health": s.TierRequestHealth()`, analog zu den drei
bestehenden Health-Blöcken in derselben Zeile.

Der Mailtext in `internal/mail/tier_change.go` (Zeilen 22 Plain, 34 HTML)
wird von „Zum Freigeben das tier-Feld in der user.json dieses Nutzers manuell
setzen." auf einen Wortlaut erweitert, der ausdrücklich beide Felder nennt
(`tier` setzen **und** `requested_tier` entfernen).

## Expected Behavior

- **Input:** GET `/api/scheduler/status` (kein Auth-Header nötig, Endpoint ist öffentlich)
- **Output:** bestehende Status-Antwort plus neuer Schlüssel `tier_request_health: {open_count, oldest_open_age_hours}`
- **Side effects:** keine — reine Lesefunktion, kein Schreibpfad, kein neuer Cronjob, keine neue Mail

## Acceptance Criteria

- **AC-1:** Given es liegen keine offenen Level-Wechsel-Anträge vor / When `/api/scheduler/status` aufgerufen wird / Then meldet `tier_request_health.open_count == 0` und `oldest_open_age_hours == 0.0`, nicht Fehler oder ein fehlendes Feld.
  - Test: Zwei Nutzer ohne `requested_tier` anlegen, echten HTTP-Roundtrip gegen `Status()` fahren, Nullwerte prüfen.

- **AC-2:** Given **zwei** Nutzer haben offene Anträge — einer vor 8 Tagen, einer vor 2 Stunden / When der Status-Endpoint aufgerufen wird / Then zeigt `oldest_open_age_hours` das Alter des **älteren** Antrags (über 168 Stunden), nicht das des jüngeren, und `open_count == 2`.
  - Test: Zwei Nutzer anlegen, `RequestedAt` auf `time.Now().Add(-8*24*time.Hour)` bzw. `-2*time.Hour`; `open_count == 2` und `oldest_open_age_hours > 168` prüfen.
  - **Zwingend zwei Anträge:** Mit nur einem offenen Antrag sind „ältester" und „jüngster" derselbe Wert — der Test könnte die Verwechslung dann gar nicht sehen und würde nichts bewachen. Die Mutation `Before` → `After` in der Ältester-Auswahl MUSS diesen Test rot machen.

- **AC-3:** Given ein Nutzer hat gar keinen Antrag gestellt (`requested_tier` leer) / When der Status-Endpoint aufgerufen wird / Then zählt dieser Nutzer nicht mit in `open_count`.
  - Test: Nutzer ohne `requested_tier`-Feld anlegen, `open_count == 0` erwarten. Mutations-Gegenprobe: eine Implementierung, die auf „`Tier` leer" statt „`RequestedTier` leer" prüft, muss hier scheitern.

- **AC-4:** Given ein Nutzer mit `tier="standard"` und `requested_tier="premium"` wurde vom PO durch Löschen von `requested_tier` als erledigt markiert / When der Status-Endpoint aufgerufen wird / Then zählt dieser Nutzer NICHT mehr als offen.
  - Test: `user.json` mit `tier="standard"`, `requested_tier=""` (Feld entfernt) anlegen, `open_count == 0` erwarten.

- **AC-5:** Given ein Nutzer mit `tier="free"` und `requested_tier="premium"` (Antrag unbearbeitet) / When der Status-Endpoint aufgerufen wird / Then zählt dieser Nutzer als offen.
  - Test: `user.json` mit `tier="free"`, `requested_tier="premium"` anlegen, `open_count == 1` erwarten. AC-4 und AC-5 zusammen fangen eine Implementierung, die nur auf „`requested_tier` nicht leer" statt auf den Vergleich mit `tier` prüft.

- **AC-6:** Given ein Nutzer wurde bereits exakt mit dem beantragten Level freigeschaltet (`tier == requested_tier`, Feld nicht gelöscht) / When der Status-Endpoint aufgerufen wird / Then zählt dieser Nutzer nicht mehr als offen.
  - Test: `user.json` mit `tier="premium"`, `requested_tier="premium"` anlegen, `open_count == 0` erwarten. Mutations-Gegenprobe: eine Implementierung, die nur auf „`requested_tier` nicht leer" statt auf Ungleichheit zu `tier` prüft, muss hier scheitern.

- **AC-7:** Given einer von mehreren Nutzern hat eine defekte/nicht parsebare `user.json` / When der Status-Endpoint aufgerufen wird / Then liefert er trotzdem HTTP 200 mit korrekten Zahlen für die übrigen Nutzer, statt Fehler oder Absturz.
  - Test: Einen Nutzer mit ungültigem JSON in `user.json` anlegen, einen zweiten mit gültigem offenem Antrag; `open_count == 1` (nur der gültige zählt) und HTTP 200 erwarten.

- **AC-8:** Given ein offener Antrag existiert / When die rohe Antwort von `/api/scheduler/status` auf Textebene durchsucht wird / Then enthält sie an keiner Stelle die `user_id`, den `display_name` oder die E-Mail-Adresse des Antragstellers.
  - Test: Nach Vorbild `TestBriefingHealthResponseContainsNoUserIdentifiers` — Nutzer-ID mit erkennbarem Testpräfix vergeben, `rawBody` auf Enthaltensein dieser ID prüfen (`strings.Contains`), muss `false` sein.

- **AC-9:** Given der Betreiber liest die Freigabe-Mail zu einem Antrag / When er den Hinweistext zum Freigeben liest / Then nennt der Text ausdrücklich beide notwendigen Schritte — `tier` setzen UND `requested_tier` entfernen — in Plain- und HTML-Teil.
  - Test: `BuildTierChangeRequestMail(...)` aufrufen, `PlainBody` und `HTMLBody` auf das Vorkommen von `"requested_tier"` (oder einer gleichwertigen deutschen Formulierung, die das Entfernen explizit macht) prüfen; der bisherige Text ohne diesen Hinweis muss den Test scheitern lassen.

## Known Limitations

- **Der Status-Block allein wirkt nicht.** Ein Zahlenfeld, in das niemand
  schaut, ersetzt keine Mail, die niemand liest — es verlagert das
  Nicht-Hinschauen nur. Erst wenn `check-gregor20.sh` (Fremd-Repo
  `henemm-infra`) die 7-Tage-Schwelle auf `tier_request_health` auswertet,
  entsteht ein echter Alarm. Diese Änderung ist **nicht** Teil dieser
  Lieferung, sondern eine MQ-Nachricht + ein Issue an die `infra`-Instanz.
- **Abweichend gewährte Level bleiben als offen sichtbar.** Gewährt der PO ein
  anderes Level als beantragt (z.B. „standard" statt beantragtem „premium")
  und lässt `requested_tier` dabei stehen, zeigt der Endpoint diesen Antrag
  weiterhin als offen — bewusst, weil sich „bewusst abweichend gewährt" vom
  Code aus nicht von „noch nicht bearbeitet" unterscheiden lässt. Die
  Gegenmaßnahme ist der ergänzte Mailtext (AC-9): Der Hinweis, `requested_tier`
  in jedem Fall zu entfernen, macht den Fall bei korrekter Befolgung
  irrelevant.
- **Keine Erinnerungsmail.** Diese Lösung fügt keinen neuen Cronjob und keine
  neue Benachrichtigung hinzu — bewusst gegen Alarm-Müdigkeit und die
  Regel-Budget-Pflicht (neuer Cronjob bräuchte einen BetterStack-Heartbeat).
- **Keine Freischalt-Funktion.** Der Endpoint macht offene Anträge nur
  sichtbar; die Freigabe bleibt manuelle Handarbeit an `user.json` — es gibt
  weiterhin keinen Code-Pfad, der `tier` setzt. Das ist Absicht (siehe
  Analyse-Dokument, Option D verworfen: Privilegieneskalations-Risiko für
  drei Nutzerkonten unverhältnismäßig).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Lesefunktion nach einem bereits etablierten,
  dreifach vorhandenen Muster (`briefing_health`, `warn_service_health`,
  `forecast_budget` in `internal/scheduler/scheduler.go:672-680`). Kein neuer
  Architektur-Layer, kein neues Persistenzformat, kein Schreibpfad, keine
  Änderung an Auth/Mandantentrennung (der Endpoint war bereits vor dieser
  Änderung öffentlich, die Datenschutz-Leitplanke aus #252 wird nur erneut
  angewandt, nicht neu erfunden). Ein ADR wäre hier over-engineered — es
  handelt sich um dieselbe Entscheidungsklasse, die schon durch die
  bestehenden Health-Blöcke abgedeckt ist.

## Changelog

- 2026-08-07: Initial spec created
