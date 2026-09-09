# Context: feat-2270-datenexport

Issue #2270 — Datenexport nach DSGVO Art. 20: `GET /api/auth/export` plus Knopf im Konto.
Scheibe 3 von 4 aus #2146, Teil von Epic #2138. Label `priority:critical`.

## Request Summary

Der angemeldete Nutzer soll seine eigenen Daten als Download bekommen (Art. 20 DSGVO) — ein
neuer Go-Endpoint `GET /api/auth/export` und ein Knopf im bestehenden Konto-Bereich der
Account-Seite.

## 🔴 Kernbefund: Die Datei-Liste im Issue ist unvollständig

Das Issue nennt neun Wurzeln unter `data/users/<id>/`. Nachgemessen sind es **mindestens
sechzehn** — vier weitere aus dem Go-Store, sechs aus dem Python-Core. Wer den Export aus der
Issue-Liste baut, erbt die Lücke.

| Wurzel | Quelle | Im Issue? | Art |
|---|---|---|---|
| `user.json` | `internal/store/user.go:52` | ja | Nutzdaten **+ Geheimnisse** (s.u.) |
| `locations/` | `internal/store/location.go:14` | ja | Nutzdaten |
| `gpx/` | `internal/store/user.go:93`, `api/routers/gpx.py:4` | ja | Nutzdaten (XML, **nicht** JSON) |
| `weather_snapshots/` | `internal/store/user.go:93` | ja | Nutzdaten |
| `groups.json` | `internal/store/group.go:15` | ja | Nutzdaten |
| `metric_presets.json` | `internal/store/metric_preset.go:15` | ja | Nutzdaten |
| `alert_log.json` | `internal/store/log.go:64` | ja | Nutzdaten |
| `briefing_log.json` | `internal/store/log.go:24` | ja | Nutzdaten |
| `briefings/` | `internal/store/briefing_subscription.go:19` | ja | Nutzdaten — **drei** Dateisorten in EINEM Ordner: Trips (`trip.go:180`), Compare-Presets (`compare_preset.go:144`), Subscriptions (`briefing_subscription.go:32`) |

**Korrektur (in Phase 5 aufgefallen):** Frühere Fassungen dieses Dokuments zählten
„Fingerprints" als vierte Sorte. Das ist falsch. `BriefingFingerprint`
(`internal/store/briefing_fingerprint.go:27-41`) **liest** `briefings/<id>.json` und berechnet
eine Prüfsumme darüber — es entsteht keine eigene Datei. Für den Export bedeutet das: nichts
Zusätzliches einzusammeln; der Ordner wandert ohnehin vollständig mit.
| `sessions.json` | `internal/store/sessions.go:48` | **nein** | 🔴 Geheimnis |
| `password_reset.json` | `internal/store/user.go:113` | **nein** | 🔴 Geheimnis |
| `email_verification.json` | `internal/store/user.go:163` | **nein** | 🔴 Geheimnis |
| `pending_briefings.json` | `internal/store/pending_briefings.go:30`, `src/services/trip_report_scheduler.py:776` | **nein** | Nutzdaten |
| `alert_state/` | `src/services/alert_state.py:6` | **nein** | Nutzdaten |
| `compare_weather_snapshots/` | `src/services/compare_weather_snapshot.py:4` | **nein** | Nutzdaten |
| `briefing_slots.json` | `src/services/briefing_slots.py:6` | **nein** | Nutzdaten |
| Briefing-Anker-Datei | `src/services/alert_briefing_anchor.py:107` | **nein** | Nutzdaten |
| Throttle-Zustand | `src/services/throttle_store.py:65` | **nein** | Nutzdaten |
| `alert_input/` | `src/services/alert_input_capture.py:74` | **nein** | Betriebsdaten (Mitschnitt zur Fehlersuche) |
| `diagnostics/` | `src/services/track_resolution_health.py:10`, `alert_briefing_anchor.py:88,132` | **nein** | Betriebsdaten (`.jsonl`) |

**Die Prämisse „eine Datenwurzel" hält für den Nutzerbaum:** Go liest `GZ_DATA_DIR`
(`internal/config/config.go:9,55` — Prefix `GZ` + Feld `DATA_DIR`), Python liest dieselbe
Variable (`src/app/loader.py:1170`). Beide Prozesse schreiben in **denselben** Baum
`<GZ_DATA_DIR>/users/<id>/`. `DeleteUser` (`internal/store/user.go:200-206`, `os.RemoveAll`)
erwischt deshalb auch die Python-Ordner — innerhalb des Nutzerordners ist die Löschung
vollständig, nur die *Aufzählung* im Issue ist es nicht.

### 🔴 Aber: es gibt Ablagen AUSSERHALB des Nutzerordners

Das Issue behauptet, es gebe „**keine** globale Nutzerdatei". Für den Go-Nutzer-Store stimmt
das. Daneben existieren jedoch **globale** Ablagen direkt unter `<GZ_DATA_DIR>/`:

| Ablage | Quelle |
|---|---|
| `debug/alert_input/<zweig>/` | `src/services/alert_input_capture.py:112,131` (Zweig b — **global**, nicht nutzer-scoped) |
| `diagnostics/forecast_budget.json` | `src/services/forecast_budget.py:49`, `internal/scheduler/forecast_budget_health.go:125` |
| `diagnostics/enrichment_calls.jsonl` | `internal/scheduler/enrichment_health.go:139` |
| `diagnostics/warn_service_calls.jsonl`, `diagnostics/meteoalarm_budget.json` | `internal/scheduler/warn_service_health.go:270,306` |
| Vorhersage-Mitschnitt | `src/services/forecast_capture.py:127` |

**Nachgemessen in Phase 2 — keine Lücke.** Keine dieser Ablagen führt eine Nutzerkennung:

| Ablage | Geschriebene Felder | Kennung? |
|---|---|---|
| `debug/alert_input/` | `capture_id`, `captured_at`, `branch`, `source_key`, `payload` — `source_key` ist der **Dienstname** (`warn_egress.py:480`), keine Nutzerkennung | nein |
| `diagnostics/forecast_budget.json` | `date`, `calls`, `cache_hits`, `cache_misses` | nein |
| `diagnostics/forecast_capture_*.jsonl` | u.a. `lat`, `lon`, `segment_id`, `provider` (`forecast_capture.py:206-222`) | nein¹ |
| `diagnostics/enrichment_calls.jsonl` | `ts`, `path`, `outcome`, `detail` | nein |
| `diagnostics/warn_service_calls.jsonl` | `ts`, `service`, `host`, `status` bzw. `zone_code`, `drift` | nein |
| `diagnostics/meteoalarm_budget.json` | `date`, `calls`, `observed_reset_ts` | nein |

¹ `forecast_capture` schreibt Koordinaten und eine Segment-Kennung, **ohne** Zuordnung zu einem
Nutzer. Ohne Verknüpfungsmerkmal kein Personenbezug — vertretbar, aber der einzige Eintrag mit
Vorbehalt.

**Folge:** Die Kontolöschung hat keine erkannte Lücke, und der Export muss außerhalb des
Nutzerordners nichts einsammeln. Kein Folgeticket nötig.

**Nebenbefund OTP:** `internal/handler/auth_magic.go:43` hält aktive Anmelde-Codes in einer
`sync.Map` im Prozessspeicher, geschlüsselt nach E-Mail — nicht auf Platte. Nach einer
Kontolöschung bleibt ein bereits versandter Code bis zum Ablauf im Speicher gültig. Für den
Export ohne Belang (nichts zu exportieren), für die Löschung eine Randnotiz.

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/router/router.go:67` | `r.Delete("/api/auth/account", …)` — hier kommt die neue Route daneben |
| `internal/router/router.go:37` | `authmw.AuthMiddleware(...)` global; sie legt die `user_id` in den Context |
| `internal/handler/auth.go:202-228` | `DeleteAccountHandler` — die Vorlage: `middleware.UserIDFromContext(r.Context())`, kein Request-Parameter |
| `internal/store/user.go:44` | `UserDir(id)` — die eine Pfad-Engstelle; `ValidUserID` schützt vor Traversal |
| `internal/model/user.go:10-39` | Die Feldliste für die Positiv-/Negativliste aus AC-2 |
| `internal/middleware/auth.go:222` | `ContextWithUserID` — Test-Einstieg für authentifizierte Requests |
| `frontend/src/routes/account/+page.svelte:798` | `data-testid="account-section"` — der Konto-Bereich, in den der Knopf gehört |
| `frontend/src/routes/account/+page.svelte:368-381` | `deleteAccount()` / `confirmDeleteAccount()` — Muster für Konto-Aktionen |
| `frontend/src/lib/api.ts:181-187` | Der API-Client (`get`/`post`/`del`) — kann **kein** Blob, s. Risiken |

## Existing Patterns

- **Auth-Kontext:** Jeder nutzerbezogene Handler holt die Kennung über
  `middleware.UserIDFromContext(r.Context())`. Kein Request-Parameter, kein `"default"`.
- **Test-Muster Mandantentrennung:** `internal/handler/store_scope_race_test.go:46-50`
  (alice/bob parallel), `internal/handler/entity_traversal_test.go:91-105` (echter Fremdnutzer
  „bob" als Kontrollobjekt), `internal/handler/cockpit_test.go:49-52` (`withUserCtx`-Helper).
  `store.New(t.TempDir(), …)` ist das übliche Test-Store-Setup.
- **Pfadsicherheit:** `internal/store/pathsafe.go:41` — Store-Methoden joinen nur `id+".json"`,
  nie einen fremden Pfad.

## Existing Specs

- `docs/specs/modules/account_deletion.md` — die Gegenrichtung (DELETE `/api/auth/account`).
  **Achtung:** Diese Spec hat **keine** formalen Acceptance Criteria und zählt den Bestand nur
  beispielhaft auf („locations, trips, gpx, snapshots, user.json"). Sie taugt als Aufbau-Vorlage,
  **nicht** als Bestandsliste — genau diese Aufzählung ist inzwischen unvollständig.
- `docs/specs/modules/account_page.md`, `…/account_page_extend.md` — die Konto-Seite
- `docs/specs/modules/user_auth_endpoints.md` — Go User-Store + Auth-Endpoints
- Vorlage `docs/specs/_template.md`: Frontmatter (`entity_id`, `type`, `created`, `updated`,
  `status`, `version`, `tags`), Abschnitte Approval → Purpose → Source → Estimated Scope →
  Dependencies → Implementation Details → Expected Behavior → **Acceptance Criteria** → Known
  Limitations → ADR → Changelog. AC-Form: `**AC-1:** Given … / When … / Then …` plus Test-Zeile.

### 🔴 Namensfalle: `internal/handler/export_test.go` ist NICHT für dieses Feature

Die Datei existiert bereits und enthält ausschließlich `ResetOTPStoreForTest`. Sie folgt dem
Go-Idiom „`export_test.go` = Paket-Interna für Tests zugänglich machen" und hat mit
Datenexport nichts zu tun. Export-Tests gehören in eine **neue**, nach Verhalten benannte
Datei. Ein Analyse-Agent ist bereits auf diese Doppelbedeutung hereingefallen.

## Risks & Considerations

1. **🔴 Geheimnisse liegen im selben Ordner wie die Nutzdaten.** `sessions.json`,
   `password_reset.json`, `email_verification.json` und in `user.json` die Felder
   `password_hash` + `passkey_credentials`. Ein „pack den Ordner ein"-Export leckt sie
   sämtlich. AC-2 verlangt die Prüfung gegen den **ausgelieferten Inhalt**, nicht gegen die
   Absicht im Code.
2. **Erlaubnisliste vs. Sperrliste — beide versagen still, in entgegengesetzte Richtungen.**
   Erlaubnisliste: eine künftige Store-Wurzel fehlt unbemerkt im Export (Art.-20-Lücke).
   Sperrliste: eine künftige Geheimnis-Datei landet unbemerkt im Export (Leck). Die Wahl ist
   nur mit einer **Drift-Sicherung** vertretbar; die Sicherung trägt die Zusicherung, nicht die
   Wahl. Entscheidung gehört in Phase 2 — keine PO-Frage, das ist eine technische Entscheidung.
3. **Format ist offen.** `gpx/` enthält XML, `diagnostics/` `.jsonl`, der Rest JSON. Ein
   einzelnes JSON-Dokument müsste Fremdformate einbetten; ZIP wäre der natürliche Behälter.
   **Im Bestand gibt es kein Vorbild:** `Content-Disposition`, `archive/zip` und
   `octet-stream` kommen in `internal/`, `cmd/`, `api/`, `src/` **nirgends** vor. Das Muster
   wird hier erstmalig etabliert.
4. **Der Frontend-API-Client kann keine Binärantwort.** `frontend/src/lib/api.ts:181-187`
   liefert ausschließlich geparstes JSON (`request<T>`). Ein Download braucht entweder einen
   eigenen Weg (`fetch` + `res.blob()` + `URL.createObjectURL`, analog zum Upload-Sonderweg
   `uploadGpx` in `api.ts:200-223`) oder einen schlichten Link auf die Route.
5. **Kein `data/`-Ordner im Worktree.** Tests müssen den Nutzerbaum vollständig selbst anlegen —
   am besten über die **Produktiv-Schreiber** (`ProvisionUserDirs`, `SaveUser`, `SaveLocation`,
   `SaveTrip`, …), damit die Erwartung nicht handgetippt ist und mitwächst.
6. **LoC-Limit.** Handler + Packformat + Frontend-Knopf + Zwei-Nutzer-Tests sprengen die 250
   Zeilen voraussichtlich; `loc_limit_override 500` einplanen statt mitten drin zu stolpern.
7. **OpenAPI:** `openapi.yaml` liegt im Repo-Wurzelverzeichnis (nicht `api/openapi.yaml`) und
   führt **keine** `/api/auth/*`-Route. Eine Pflicht zur Ergänzung besteht dort also nicht;
   `docs/reference/api_contract.md` ist die maßgebliche Stelle für DTOs.
8. **Export-Testdateien enthalten echte Nutzerdaten** → Session-Scratchpad, `install -m 600`,
   nicht weltlesbar nach `/tmp` (Security #199, AC-4 im Issue).

---

# Analysis (Phase 2)

## Type

**Feature** (Label `enhancement`, `priority:critical`). Kein Bug — die Funktion fehlt schlicht.

## 🔴 Der schärfste Befund: der Rückfall auf `default` ist im Code angelegt

Das Issue verbietet den Rückfall auf `"default"`. Nachgemessen ist er **nicht** nur eine
theoretische Nachlässigkeit, sondern die Wirkung des Bestands, wenn der Handler nichts dagegen
tut — drei Stellen greifen ineinander:

| Stelle | Verhalten |
|---|---|
| `internal/middleware/auth.go:151-154` | `UserIDFromContext` macht eine Typ-Zusicherung mit verworfenem Fehler → bei fehlendem Kontext ist das Ergebnis der **leere** String, kein Fehler |
| `internal/store/store.go:21-24` | `WithUser("")` gibt den Store **unverändert** zurück (bewusster No-Op) |
| `internal/config/config.go:10` | Der Store trägt dann seine Voreinstellung: `UserID` = **`"default"`** |

Ein Export-Handler, der die Kennung nur durchreicht, liefert bei fehlendem Auth-Kontext also
den **fremden `default`-Ordner** aus. Das ist genau das Leck, das AC-1 verbietet. **Folge:** Die
leere Kennung braucht eine ausdrückliche Prüfung mit Abweisung (401) — und einen eigenen Test,
denn ein Test, der immer `ContextWithUserID(ctx, "alice")` setzt, betritt diesen Pfad nie.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `internal/store/user.go` | MODIFY | Neue Methode `ExportUser` direkt neben `DeleteUser` — die Symmetrie aus AC-3 wird dadurch im Code sichtbar |
| `internal/handler/data_export.go` | CREATE | Handler: Kennung aus dem Auth-Kontext, Leer-Prüfung → 401, Kopfzeilen, Archiv durchreichen |
| `internal/router/router.go` | MODIFY | `r.Get("/api/auth/export", …)` in den geschützten Bereich (nicht in die Public-Allowlist, `internal/middleware/auth.go:50-63`) |
| `internal/handler/data_export_test.go` | CREATE | Zwei-Nutzer-Trennung, Geheimnis-Abwesenheit, leerer Kontext, Vollbild-Drift-Test |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Eigene Karte „Deine Daten" **vor** der Gefahrenzone-Karte (Struktur der Seite: eigenständige Karten je Thema) |
| `frontend/src/lib/api.ts` | MODIFY | Sonderweg für Datei-Antworten — der Client kann heute nur JSON |

**Nicht** `internal/handler/export_test.go` (Go-Idiom, s.o.). **Kein** Backup-Hook betroffen:
`data_schema_backup.py:25-31` listet `internal/model/`, `internal/store/store.go`,
`src/app/models.py`, `src/app/trip.py`, `src/app/loader.py` — `internal/store/user.go` ist
nicht dabei.

## Technical Approach

**Format: ZIP-Archiv, durchgereicht statt gepuffert.** Die Nutzerdaten liegen in gemischten
Formaten (GPX ist XML, `diagnostics/` ist `.jsonl`); ein ZIP hält sie im Original und ist die
unverbogene Lesart von „strukturiert, gängig, maschinenlesbar". Da die reale Datenmenge
ungemessen bleibt (Produktivordner nicht lesbar), ist Durchreichen ins Antwortobjekt die
einzige Variante mit gleichbleibendem Speicherbedarf. **Bewusst hinzunehmen:** Bei einem Fehler
mitten im Archiv ist der Erfolgs-Statuscode bereits gesendet — dann bricht die Übertragung ab
und liefert ein unvollständiges Archiv. Das ist ehrlicher als ein stiller Teilexport und gehört
als Kommentar an die Stelle, nicht als übersehene Lücke.

**Auswahl: Erlaubnisliste im Code, abgesichert durch eine Verzeichnis-Klammer im Test.** Ein
durchgelassenes Geheimnis ist der teurere Fehler als eine vergessene Datenart. Die Wahl allein
sichert aber nichts — die Zusicherung trägt der Drift-Test:

1. Der Test baut ein **Vollbild**-Nutzerverzeichnis mit je einem Exemplar jeder belegten
   Datenart (inklusive der drei Geheimnis-Dateien).
2. Er ruft den Export **auf**, entpackt das Ergebnis und verlangt: jeder angelegte Eintrag ist
   entweder im **ausgelieferten Archiv** enthalten oder steht auf einer begründeten
   Ausnahmeliste (Geheimnisse + Betriebsdaten).
3. Kein Geheimniswert taucht irgendwo im Archivinhalt auf — gesucht wird im **entpackten
   Inhalt** nach dem Wert, nicht in der Struktur.
4. Die Ausnahmeliste muss vollständig verbraucht sein — ein Eintrag, den es nicht mehr gibt,
   macht den Test rot (kein Totholz, keine stille Verengung).

Damit werden **beide** Drift-Richtungen rot: eine neue Datenart ohne Eintrag fällt durch (1),
ein neues Geheimnis muss jemand bewusst eintragen (2).

**🔴 Bedingung, sonst ist der Test Selbstbespiegelung:** Erlaubnisliste der Implementierung und
Erwartungsliste des Tests dürfen **nicht dieselbe Konstante** sein. Teilen sie sich eine
Variable, spiegelt der Test nur die Annahme des Codes und bewacht nichts.

### Die Erlaubnisliste — konkret, mit Vergleichsart

**Exakte Dateinamen** (Vergleich auf Gleichheit, kein Präfix):

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
| `alert_throttle.json`, `compare_alert_throttle.json`, `radar_alert_throttle.json` | `throttle_store.py:31-33` — **Altbestand**, s.u. |

**Ordner** (Vergleich auf Präfix, Inhalt wandert vollständig mit):
`locations/`, `gpx/`, `weather_snapshots/`, `compare_weather_snapshots/`, `briefings/`
(alle vier Sorten), `alert_state/`

**Begründete Ausnahmeliste** (nicht im Export, aber der Drift-Klammer bekannt):

| Eintrag | Grund |
|---|---|
| `sessions.json`, `password_reset.json`, `email_verification.json` | Geheimnisse (exakter Vergleich) |
| `alert_input/`, `diagnostics/` | Betriebsdaten, s.u. |
| `.throttle_state_*.tmp` | Reste des atomaren Schreibens (`throttle_store.py:154`), können nach einem Absturz liegenbleiben |

**Warum exakter Vergleich bei den Geheimnissen die richtige Wahl ist:** Ein künftiges
`email_verification_v2.json` fiele bei Präfix-Vergleich still unter die Ausnahme. Bei exaktem
Vergleich ist es weder exportiert noch ausgenommen — und die Drift-Klammer meldet es. Der
Fehler fällt nach vorne, nicht ins Leere.

**🔴 Altbestand:** `throttle_store.py:31-33` nennt drei Vorgänger-Dateien. Bei Nutzern aus
älteren Ständen können sie noch im Ordner liegen. Eine Erlaubnisliste, die nur den heutigen
Namen kennt, verliert sie stillschweigend — sie gehören mit auf die Liste.

## Scope Assessment

| Teil | ca. LoC |
|---|---|
| Store-Methode `ExportUser` | 60–90 |
| Handler + Route | 30–50 |
| Frontend (Karte + Datei-Sonderweg) | 40–70 |
| Go-Tests inkl. Vollbild-Fixture | 150–220 |
| Frontend-Test | 20–40 |

- Dateien: 6 (2 neu, 4 geändert)
- Risiko: **MITTEL** — kleine Fläche, aber Sicherheitswirkung
- **Das LoC-Limit von 250 reißt an den Tests**, nicht an der Produktionslogik. Die Vollbild-
  Fixture mit rund zwanzig Datenarten ist der Grund. `loc_limit_override 500` ist hier
  begründet und kein Zeichen für ausufernden Umfang.

## Weitere Risiken

- **Pfadnamen im Archiv:** Einträge in `locations/`, `gpx/`, `briefings/` tragen
  Entitäts-Kennungen. Die Archiv-Einträge müssen strikt relativ zum Nutzerordner bleiben, sonst
  bricht ein manipulierter Dateiname aus dem Archivpfad aus.
- **Gleichzeitiges Schreiben:** Ohne Sperre ist der Export ein zeitlich unscharfer Schnitt
  (eine Datei von 10:00, die nächste von 10:01). Für Art. 20 vertretbar — aber als bewusste
  Entscheidung zu vermerken.

## Mutationen, die ein naiver Test NICHT fängt

1. **Geheimnis-Filter entfernt** — ein Test, der nur prüft „Archiv enthält `user.json`", bleibt
   grün. Fängt nur die Suche nach dem Geheimniswert im entpackten Inhalt.
2. **Kennung aus dem Anfrageparameter statt aus dem Auth-Kontext** — ein Test mit nur einem
   Nutzer sieht keinen Unterschied. Fängt nur: Alice ist angemeldet, die Anfrage trägt
   zusätzlich `?user_id=bob`, und Bobs Daten dürfen nicht auftauchen.
3. **Leerer Kontext fällt auf `default` zurück** — s.o.; fängt nur ein Test ohne gesetzten
   Nutzerkontext, der 401 und kein Archiv verlangt.

## Reihenfolge

1. Store-Methode (Drift-Test zuerst rot)
2. Handler mit Leer-Prüfung + Route
3. Go-Tests: Zwei-Nutzer-Trennung mit Parameter-Manipulation, Geheimnis-Abwesenheit, leerer Kontext
4. Frontend: Karte + Datei-Sonderweg
5. Frontend-Test

## Entschiedene Fragen (waren offen nach Phase 1)

- Format → **ZIP**, durchgereicht
- Erlaubnis- oder Sperrliste → **Erlaubnisliste + Drift-Klammer im Test**
- Globale Ablagen → **gemessen, keine Nutzerkennung**, kein Folgeticket
- `briefings/` → **alle vier** dort liegenden Sorten, der Ordner wandert vollständig mit

### Betriebsdaten: bewusste Annahme, keine stille Auslassung

`diagnostics/` und `alert_input/` bleiben draußen — **als ausdrückliche Annahme, nicht als
Selbstverständlichkeit.** Begründung: technische Protokolle zur Fehlersuche, vom System über
sich selbst geführt, nicht vom Nutzer bereitgestellt. Der Grenzfall ist `alert_input/`: es
schneidet die Alarm-Eingangsdaten **dieses** Nutzers mit, ist also nutzerbezogen. Wird das
rechtlich anders bewertet, wandern beide auf die Einschlussliste — dank der Drift-Klammer ist
das eine Zeile, keine Umbauarbeit. Die Annahme steht hier, damit sie sichtbar bleibt.

### 🔴 AC-3 muss umformuliert werden

Das Issue verlangt: „Export und Löschung decken denselben Bestand ab." So wörtlich genommen ist
das **nicht erfüllbar** — die Löschung entfernt per `os.RemoveAll` restlos alles, der Export
lässt Geheimnisse und Betriebsdaten absichtlich weg. Die beiden Mengen sind konstruktionsbedingt
verschieden. Die Spec muss den Maßstab deshalb so fassen:

> Der Export deckt den Löschbestand ab **abzüglich der begründeten Ausnahmeliste** — und jeder
> Eintrag der Ausnahmeliste trägt einen Grund.

Andernfalls trägt die Spec ein Kriterium, das keine Umsetzung erfüllen kann: in Phase 6 wird es
dann entweder weggeredet oder blockiert. Beides ist schlecht.

## Offene Fragen aus Phase 1 (erledigt)

- Erlaubnisliste oder Sperrliste — und welche Drift-Sicherung macht die Wahl prüfbar?
- Ein JSON-Dokument oder ZIP? (folgt aus dem Umgang mit `gpx/` und `diagnostics/`)
- Gehören Betriebsdaten wie `diagnostics/` und `alert_input/` (Mitschnitte zur Fehlersuche)
  überhaupt in einen Art.-20-Export, oder sind sie technische Protokolle?
- Deckt der Export `briefings/` mit allen **vier** dort liegenden Sorten ab?
- Stehen in den **globalen** Ablagen (`debug/alert_input/`, `diagnostics/*.jsonl`)
  Nutzerkennungen? Wenn ja → eigenes Ticket für die Löschung, nicht diese Scheibe.
