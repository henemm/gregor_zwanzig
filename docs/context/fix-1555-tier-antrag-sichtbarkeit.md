# Context: Sichtbarkeit offener Tier-Freischalt-Anträge (#1555, Teil 1)

## Request Summary

Ein Antrag auf Level-Wechsel (`POST /api/auth/tier-change-request`) kann beliebig
lange unbearbeitet liegen bleiben, ohne dass der **Betreiber** je wieder darauf
gestoßen wird. Im konkreten Fall lag ein Premium-Antrag vom 2026-07-07 vier
Wochen unbemerkt — mit der Folge, dass das Konto im Free-Tier (2 Alarme/Tag)
feststeckte und während einer laufenden Tour keine NowCast-Alarme zugestellt
bekam.

## Abgrenzung zum parallel laufenden Workflow

**#1555 wird von zwei Sessions bearbeitet.** Der zweite Teil des Issues
(NowCast-Vorrang im geteilten Tagesbudget) läuft seit 2026-08-07 07:48 als
eigener Workflow `fix-1555-nowcast-alert-priority` (Worktree
`silly-growing-patterson`, Spec freigegeben, RED fertig, in Implementierung).
Dieser Workflow hier fasst **ausschließlich** die Antrags-Sichtbarkeit an und
lässt `src/services/alert_daily_limit.py`, `user_tier.py`, `trip_alert.py`,
`compare_alert.py` unberührt.

| Teilthema | Workflow |
|---|---|
| NowCast-Vorrang im Tagesbudget (Python-Core) | `fix-1555-nowcast-alert-priority` — **nicht hier** |
| Sichtbarkeit offener Tier-Anträge (Go + ggf. Frontend) | dieser Workflow |

## 🔴 Wichtigste Korrektur gegenüber der Issue-Formulierung

Das Issue sagt, es werde „nirgends sichtbar, dass ein Antrag noch offen ist".
Für die **Nutzer**-Seite stimmt das nicht — gemessen, nicht vermutet:

`frontend/src/routes/account/+page.svelte:629-632` zeigt bereits
„Level-Wechsel zu \<Level\> beantragt — wird vom Betreiber geprüft", abgeleitet
aus `pendingTier` (`requested_tier` ≠ `tier`). Diese Anzeige kam mit #1071 und
funktioniert.

**Die Lücke liegt allein auf der Betreiber-Seite:** beim Antrag geht **genau
eine** Mail an den PO raus (`internal/handler/auth.go:825-857`, Builder
`internal/mail/tier_change.go:9-44`). Danach passiert nichts mehr — keine
Erinnerung, keine Liste offener Anträge, kein Status-Endpoint-Feld, keine
Frist. Geht diese eine Mail unter, ist der Antrag für immer unsichtbar.

Konsequenz für die Spec: **keine Nutzer-Anzeige nachbauen, die es schon gibt.**

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:779-859` | `RequestTierChangeHandler` — speichert `requested_tier`+`requested_at`, feuert die einmalige PO-Mail |
| `internal/handler/auth.go:487-492` | `toProfileResponse()` — normalisiert fehlendes `tier` still auf `"free"` |
| `internal/mail/tier_change.go:9-44` | `BuildTierChangeRequestMail` — Betreff, Text, Hinweis „tier-Feld manuell setzen" |
| `internal/model/user.go:22-27` | Felder `Tier`, `RequestedTier`, `RequestedAt *time.Time` |
| `internal/store/user.go:48-79` | `LoadUser`/`SaveUser` — JSON pro Nutzer unter `data/users/<id>/user.json` |
| `internal/router/router.go:68` | Route-Registrierung `/api/auth/tier-change-request` |
| `internal/handler/scheduler_status.go:11-15` | Status-Endpoint — heute ohne jeden Tier-Bezug |
| `internal/scheduler/scheduler.go:611-680` | `Status()` — liefert `jobs`, `briefing_health`, `warn_service_health`, `forecast_budget` |
| `internal/scheduler/scheduler.go:145-153` | Cron-Registrierung, Muster für einen etwaigen neuen Job |
| `frontend/src/routes/account/+page.svelte:626-660` | Bestehende Nutzer-Anzeige + Antragsformular — **Referenz, nicht Baustelle** |
| `internal/handler/auth_tier_change_test.go` | Bestehende Testabdeckung des Antragswegs |

## Existing Patterns

- **Freischaltung ist bewusst manuell.** Es existiert **kein** Code-Pfad, der
  `tier` setzt — breit gegrept, kein Endpoint, kein CLI, kein Script. Der PO
  bearbeitet `user.json` von Hand. Das ist Absicht (die Mail sagt es
  ausdrücklich), begrenzt aber jede Lösung: ein „Erledigt"-Zustand kann nur
  daran erkannt werden, dass `tier` == `requested_tier` wurde bzw.
  `requested_tier` verschwand.
- **Observability-Muster im Haus:** `/api/scheduler/status` sammelt
  Gesundheits-Blöcke (`briefing_health`, `warn_service_health`,
  `forecast_budget`) — das etablierte Andockmuster für „etwas stimmt nicht,
  seit wann". Bislang ohne Nutzer-Bezug.
- **Heartbeat-Konvention (global):** Pings nur bei fachlichem Erfolg
  (Readiness statt Liveness). Für einen neuen Cronjob relevant.
- **Mail-Versand:** SMTP mit Fallback, asynchron in Goroutine, 20s Timeout,
  Fehler nur geloggt — Antrag schlägt nie wegen Mail-Problemen fehl
  (`auth.go:846-857`). Genau diese Nachsicht macht den stillen Verlust möglich.

## Dependencies

- **Upstream:** `store.LoadUser`/`SaveUser`, `model.User`, Config `PoEmail`,
  SMTP-Konfiguration, ggf. Scheduler-Registrierung.
- **Downstream:** Wer `tier` liest, ist von dieser Änderung **nicht** betroffen
  (`src/services/user_tier.py` → `daily_alert_limit()`, `sms_allowed()`;
  `internal/model/tier.go` → `SmsAllowed()`). Diese Konsumenten gehören zum
  Nachbar-Workflow bzw. bleiben ganz unberührt.

## Existing Specs

| Dokument | Aussage | Verlässlichkeit |
|---|---|---|
| `docs/specs/modules/epic_user_tiers_overview.md` | Epic #1067, Slices #1068–#1071; Free 2/Standard 4/Premium unbegrenzt; Antragsweg als Slice #1071 | Status `draft`, aber **vollständig live** seit 2026-07-07 — Status irreführend |
| `docs/specs/modules/alert_daily_limit.md` | #1070 Tageslimit-Mechanik | live; **Zuständigkeit des Nachbar-Workflows** |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | `reason`-Werte inkl. `nowcast`; `daily_limit` als Nicht-Zustellungsgrund in S1 **unprotokolliert** | live seit 2026-08-02 |
| `docs/reference/api_contract.md` | DTO-Vertrag — bei neuem Feld in Profile/Status-Antwort zu pflegen | hoch |

Kein ADR zu Tiers, Antragsprozess oder Betreiber-Observability gefunden.

## Risks & Considerations

- **Doppelarbeit mit der Parallel-Session.** Strikt Go/Frontend bleiben; die
  Python-Alarmpfade sind fremdes Revier.
- **Datenschema `user.json`:** Falls ein Feld ergänzt wird — Read-Modify-Write
  mit Merge, niemals Replace (BUG-DATALOSS-GR221/#102). `internal/model/user.go`
  löst den Pre-Snapshot-Hook aus.
- **Mandantentrennung:** Eine Übersicht offener Anträge ist per Definition
  nutzerübergreifend und darf deshalb **nicht** über die normalen,
  user-scoped Endpoints laufen. Wer sie sehen darf, ist eine offene
  Designfrage — ohne Antwort droht ein Cross-User-Leck.
- **Kein Freischalt-Endpoint vorhanden.** Ob dieser Workflow einen bauen soll
  oder nur sichtbar macht, ist die zentrale offene Frage für `/20-analyse`.
  Ein Freischalt-Endpoint wäre eine Auth-relevante Erweiterung mit deutlich
  größerem Blast Radius.
- **Regel-Budget:** Ein neuer Cronjob braucht laut globaler Konvention einen
  BetterStack-Heartbeat; eine neue Erinnerungsmail darf nicht zur
  Dauerbeschallung werden.
- **Verifikation:** Eine Erinnerungsmail ist auf Staging nur über das
  Test-Postfach `gregor-test@henemm.com` (`GZ_TEST_IMAP_*`) nachweisbar —
  nicht über die Prod-Adresse des PO.

---

# Analysis

## Type

**Bug** (nutzersichtbares Fehlverhalten mit Sicherheitsfolge), behoben durch
eine kleine Feature-Ergänzung.

## Gemessene Produktivdaten — die Größenordnung des Problems

- **3 echte Nutzerkonten** (`henning`, `steffi`, `default`) plus ein
  Validator-Testkonto. Kein Mehrbenutzer-Betrieb im großen Stil.
- **Aktuell 0 offene Anträge.** Nur `henning` hat überhaupt ein `tier`-Feld
  (`premium` — die Sofortmaßnahme aus dem Issue); `steffi` und `default` haben
  gar keins und laufen still auf dem `free`-Fallback.
- Anträge sind also **sehr selten** (ein bekannter Fall seit Livegang von
  #1071 am 2026-07-07). Jede Lösung, die ein Rollenmodell oder eine
  Verwaltungsoberfläche voraussetzt, wäre für diese Größenordnung deutlich
  überdimensioniert.

## 🔴 Zusätzlicher Befund: Die Benachrichtigung geht an ein anderes Postfach

`GZ_PO_EMAIL` ist in der Produktions-`.env` auf **`henning.emmrich@gmail.com`**
gesetzt (`internal/config/config.go:39,52`, Präfix `GZ` bestätigt — die
Variable greift also wirklich). Die einzige Benachrichtigung über einen
Antrag landet damit **nicht** in einem `henemm.com`-Postfach.

Das ist ein plausibler Teil der Ursache, warum die Mail vier Wochen unbemerkt
blieb — und es ist eine offene Frage an den PO, kein technischer Mangel:
Wenn dieses Gmail-Postfach selten gelesen wird, ist „mehr Mails dorthin
schicken" wirkungslos, und die Adresse zu korrigieren wäre ein Ein-Zeilen-Fix
ohne jede Code-Änderung.

## 🔴 Der Status-Endpoint ist öffentlich — und hat dafür ein fertiges Muster

`/api/scheduler/status` ist in `internal/middleware/auth.go:34` **von der
Auth-Middleware ausgenommen**, also ohne Login erreichbar. Das Haus hat dafür
bereits eine erprobte Leitplanke: `internal/scheduler/briefing_health.go:61-67`
aggregiert über **alle** Nutzer, gibt aber ausdrücklich nur Zahlen, eine Dauer
und einen Zeitstempel heraus — keine `user_id`, kein Trip, kein Name (#252).
Bewacht wird das durch einen eigenen Test, der den Response-Body auf
Nutzer-Identifikatoren prüft.

Damit ist die im Kontext notierte Cross-User-Sorge für diesen Weg gelöst:
Ein Block `{open_count, oldest_age_days}` verrät nicht, **wer** etwas
beantragt hat.

## Affected Files (Empfehlung B + Alarmweg)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/tier_request_health.go` | CREATE | `TierRequestHealth()` — zählt offene Anträge über alle Nutzer, liefert nur Zahlen; 1:1 nach dem Muster von `briefing_health.go` |
| `internal/scheduler/tier_request_health_test.go` | CREATE | Wirkungs- **und** Datenschutz-Test (Vorbild: `briefing_health_test.go`) |
| `internal/scheduler/scheduler.go:676-678` | MODIFY | Neuen Schlüssel in die `Status()`-Map einhängen |
| `docs/reference/api_contract.md:1074ff` | MODIFY | Antwortformat des Status-Endpoints nachziehen |
| *(Fremd-Repo)* `henemm-infra/scripts/check-gregor20.sh` | MODIFY | Auswertung des neuen Blocks → nur so entsteht ein echter Alarm |

## Scope Assessment

- Files: 4 im Repo (+1 im Fremd-Repo `henemm-infra`)
- Estimated LoC: ~+90/-0 im Repo (Code ~40, Tests ~50); Doku zählt nicht
- Risk Level: **LOW** — reine additive Lesefunktion, kein Schreibpfad, kein
  neues Berechtigungskonzept, kein Eingriff in Alarm- oder Versandwege

## Technical Approach

**Empfehlung: Option B (Status-Block) plus Auswertung im bestehenden Monitor.**

Der Strategie-Agent empfiehlt B allein und schlägt vor, BetterStack direkt auf
das Feld zu setzen. **Diese Ergänzung übernehme ich so nicht**: BetterStack-
Uptime-Checks sind auf Erreichbarkeit und Antwortinhalt ausgelegt, nicht auf
numerische Schwellen in einem JSON-Feld. Der im Haus **nachweislich** dafür
gebaute Weg ist `check-gregor20.sh` — das Script liest `/api/scheduler/status`
bereits aus (Zeile 119) und wertet die Antwort in Python mit `issues`- und
`soft`-Kategorien aus. Dort gehört die Schwellenprüfung hin.

Das ist zugleich die wichtigste Einschränkung dieser Lösung: **Option B allein
wirkt nicht.** Ein Zahlenfeld, in das niemand schaut, ersetzt eine Mail, die
niemand liest, nicht — es verlagert das Nicht-Hinschauen nur. Erst die
Auswertung im Monitor macht daraus einen Alarm. Da diese im Fremd-Repo
`henemm-infra` liegt, braucht es dort ein Issue bzw. eine MQ-Nachricht; dieser
Workflow kann sie nicht selbst liefern.

**Warum nicht die Alternativen** (Bewertung des Strategie-Agenten, von mir
geteilt):

- **Erinnerungsmail (A):** versucht ein Versagen des Mail-Kanals mit mehr Mails
  desselben Kanals zu heilen. Braucht Cronjob samt Heartbeat-Pflicht und
  Drossel-Logik (~120–180 LoC) und riskiert Alarm-Müdigkeit. Sinnvoll erst,
  wenn die Postfach-Frage oben geklärt ist.
- **Betreiber-Ansicht (C)** und **bedienbare Freischaltung (D):** beide setzen
  eine Admin-Rolle voraus, die im Datenmodell schlicht nicht existiert. D
  schafft zusätzlich einen mächtigen neuen Schreibpfad auf fremde Konten
  (Privilegieneskalations-Risiko). Für drei Nutzer und ~einen Antrag im Monat
  steht das in keinem Verhältnis. **D löst das gemeldete Problem ohnehin
  nicht:** ein bequem genehmigbarer Antrag bleibt genauso liegen, wenn man
  nichts von ihm weiß. Das ist ein eigenständiges Komfort-Feature mit eigener
  Spec.

## Wie die Wirkung nachgewiesen wird

Nicht „die Funktion existiert", sondern: zwei Nutzer mit gesetztem
`requested_tier` (einer mit altem `requested_at`) anlegen → `Status()` aufrufen
→ `open_count == 2` und plausibles `oldest_age_days`. Der Test muss scheitern
können — insbesondere gegen die Mutation „`requested_tier == ""` wird nicht
herausgefiltert" und „ein bereits freigeschalteter Antrag (`tier ==
requested_tier`) zählt weiter mit". Dazu der Datenschutz-Test nach Vorbild
`TestBriefingHealthResponseContainsNoUserIdentifiers`.

## PO-Entscheidungen (2026-08-07, verbindlich)

- [x] **`GZ_PO_EMAIL` wird auf `henning@henemm.com` geändert.** Bisher
      `henning.emmrich@gmail.com`. Produktions-`.env`, greift erst nach
      Neustart von `gregor-api`. Eigener Lieferpunkt dieses Workflows.
- [x] **Überfälligkeitsfrist: 7 Tage.** Ein Antrag, der älter als 7 Tage ist
      und noch nicht freigeschaltet wurde, gilt als überfällig.
- [x] **Monitor-Teil:** MQ-Nachricht an die `infra`-Instanz **plus** Issue in
      `henemm-infra` (Nachricht macht aufmerksam, Issue hält den Auftrag fest).
      `infra` ist eine Claude-Code-Instanz, kein Mensch — ein Issue allein
      erreicht sie nicht. Erfolgt am Ende der Kette, blockiert die Spec nicht.

## Lieferumfang dieses Workflows

1. `TierRequestHealth()` + Einbindung in `Status()` (Go, dieses Repo)
2. Tests: Wirkung + Datenschutz
3. `docs/reference/api_contract.md` nachziehen
4. `GZ_PO_EMAIL` in der Produktions-`.env` korrigieren + `gregor-api` neu starten
5. MQ-Nachricht + Issue an/in `henemm-infra` für die Schwellenprüfung (7 Tage)
