# Context: Zentraler Egress-Wächter (Scheibe A von #1337)

## Request Summary
Statt Umgebungs-Isolation weiter dienstweise nachzurüsten (jede Nachrüstung ließ einen Weg
offen), einen **zentralen Egress-Wächter** bauen, durch den in Test/Staging jeder ausgehende
Ruf an einen kostenpflichtigen/nebenwirkungsbehafteten Dienst läuft. Der Wächter erzwingt pro
Dienst genau eine deklarierte Isolationsart (getrennter Test-Zugang ODER kein Zugriff) und
blockt hart, wenn ein Ruf keiner Art zugeordnet ist.

**Scope dieses Workflows (PO-Entscheidung 2026-07-21):** NUR **Scheibe A** — zentraler Guard +
Dienst-Inventar-Deklaration. Scheiben B (SMS), C (Telegram), D (Warn-Dienste), E (resend-Relay
infra#114) hängen sich später an das Fundament. Technischer Ansatz (dünner Wrapper pro Modul vs.
zentraler Interceptor) wird in `/20-analyse` begründet entschieden.

## Related Files

### Ausgehende Egress-Call-Sites (Kartierung)
| File | Dienst | Host-Herkunft | Relevanz |
|------|--------|---------------|----------|
| `src/providers/openmeteo.py:538,682` | open-meteo forecast/air-quality | hart codiert `BASE_HOST`/`AIR_QUALITY_HOST` (:58-60) | Forecast läuft über `get_provider` → Fixture-respektierend |
| `src/services/radar_service.py:332` | open-meteo (Radar-Pfad) | hart codiert inline (:326) | **Umgeht** `get_provider` + `GZ_TEST_FIXTURE_DIR` — geht live |
| `src/providers/geosphere.py:271,381` | GeoSphere INCA/SNOWGRID + om-Clouds-Fallback | hart codiert `BASE_URL` (:48) | fetch-Weg ungeschützt |
| `src/services/official_alerts/geosphere_warn.py:77` | GeoSphere Warn-API | hart codiert (:34) | ungeschützt |
| `src/providers/brightsky.py:72` | BrightSky (Radar DE) | hart codiert (:22) | via radar_service Fixture |
| `src/providers/radar_dpc.py:73,89,112` | Radar-DPC (IT) | hart codiert `BASE_URL` (:35) + presigned S3 | ungeschützt |
| `src/services/official_alerts/meteoalarm.py:218,254,272` | MeteoAlarm EDR | hart codiert `BASE_URL` (:43), Key `GZ_METEOALARM_APIKEY` | ungeschützt |
| `src/services/official_alerts/vigilance.py:90` | Météo-France Vigilance | hart codiert (:35), Key `GZ_METEOFRANCE_APIKEY` | ungeschützt |
| `src/services/official_alerts/meteo_forets.py:79` | Météo-France Feux | hart codiert (:40) | ungeschützt |
| `src/services/official_alerts/massif_closure.py:104` | risque-prevention-incendie | hart codiert (:34) | ungeschützt |
| `src/output/channels/sms.py:41` | seven.io SMS | Config `sms_gateway_url` (:155) | **0 Guards — Scheibe B** |
| `src/output/channels/email.py:536,582,624` | Resend/SMTP + Fallback-Host | Config `smtp_host`/`imap_host` | 4 Guards; Fallback-Host ohne erneuten Guard |
| `src/app/core.py:20` | SMTP (Legacy-Pfad) | env `SMTP_HOST` | Alt-Pfad, ungeschützt |
| `src/output/channels/telegram.py:197…399` | Telegram Bot (senden) | hart codiert `TELEGRAM_API_BASE` (:13) | nur `send()` geguardet — Scheibe C |
| `src/services/inbound_email_reader.py:65` | Stalwart IMAP | Config `imap_host` | Test-Postfach via `for_testing()` |
| `src/services/inbound_telegram_reader.py:128,397` | Telegram getUpdates + localhost Go-Backend | hart codiert | intern/inbound |
| `src/validation/ground_truth.py:71` | Bergfex (Ground-Truth) | hart codiert (:34) | Validation-Tool, im Issue-Inventar NICHT gelistet |
| `src/validation/geosphere_validator.py:74,121` | GeoSphere (Validator) | hart codiert (:47) | dito |
| `src/lib/mq_notify.py:45` | Claude-MQ | env, localhost | intern |

**Kein `requests`/`aiosmtplib`/`urlopen` im Code.** `urllib` nur `urlencode`.

### Bestehende Isolations-Guards (das „14-Türen-Muster")
| File | Guard | liest |
|------|-------|-------|
| `src/app/config.py:151-152` | `GZ_ENV` → `env`-Field (Pydantic, kein expliziter Read) | `GZ_ENV` |
| `src/app/config.py:259` | Routing: `staging` OR test-user → `for_testing()` | `env`, user_id |
| `src/app/config.py:165-188` | `_resend_default_deny` (Validator) → Stalwart-Umlenkung | `resend_allowed`, pytest |
| `src/app/config.py:212-238` | `for_testing()` → Stalwart + `is_test_mode` + Test-Chat-ID | Test-Creds |
| `src/app/config.py:25-52` | `_in_pytest()`, `is_test_user_id()` | `PYTEST_CURRENT_TEST`, Profil |
| `src/providers/base.py:141-147` | `GZ_TEST_FIXTURE_DIR` → FixtureProvider (nur openmeteo) | `GZ_TEST_FIXTURE_DIR` |
| `src/services/preview_service.py:45,158-160` | **2. FixtureProvider-Weg**, hartkodierter Pfad, liest Env NICHT | `demo`-Param |
| `src/output/channels/email.py:337-351` | Init-Hard-Guard staging/is_test_mode + Resend | `env`, `is_test_mode` |
| `src/output/channels/email.py:428-514` | Send-Allowlists (Resend + lokal) | Allowlist-Datei |
| `src/output/channels/telegram.py:134-153,179` | `_guard_test_mode_chat_id()` — **nur in `send()`** | `is_test_mode`, Test-Chat-ID |

## Existing Patterns
- **Zwei `GZ_ENV`-Auswertungen:** Routing (`config.py:259`) + Mail-Hard-Guard (`email.py:337`).
- **Zwei parallele `GZ_TEST_FIXTURE_DIR`/Fixture-Wege:** `base.py` (Env) vs. `preview_service.py`
  (hartkodiert). Beide bauen `FixtureProvider` — Konvergenzkandidat.
- **Guard-Stil bisher:** `OutputConfigError` werfen (harter Abbruch), positiv Allowlist statt
  Blocklist bei Mail-Empfängern.
- **Host-Konstanten:** fast alle Provider-Hosts sind Modul-Konstanten (`BASE_URL`/`*_HOST`) —
  gut für eine zentrale Allowlist auswertbar, aber verstreut.

## Dependencies
- **Upstream:** `Settings` (`config.py`) als einzige Env-Quelle; `httpx.Client`, `smtplib.SMTP`,
  `imaplib.IMAP4_SSL` als Transport-Primitive.
- **Downstream:** Jeder Provider/Channel/Alert-Service ruft sein Transport-Primitiv selbst —
  es gibt **keinen gemeinsamen Egress-Punkt** (das ist die Kernursache).

## Existing Specs / Referenzen
- `docs/analysis/backlog-spirale-2026-07.md` — Regel-Budget/Ratsche (Kontext: neue Pflicht muss
  Prüfdatum tragen oder Regel ersetzen).
- Memory `reference_env_isolation_all_external_services` — Muster, SMS-Leck #1336 (Key gepaust),
  14 Dienste inventarisiert.
- Verwandt: #1329 (open-meteo-Kontingent, C2 Radar-Fixture), infra#114 (Resend-Relay), #1336 (SMS).

## Risks & Considerations
- **Blast Radius maximal:** Ein zentraler Punkt vor allen ausgehenden Calls ist per Definition
  kritischer Pfad. Fehlkonfiguration = alle Dienste betroffen. Muss in Prod ein reiner No-Op sein
  (nur in Test/Staging aktiv).
- **Prod darf nicht blockiert werden:** Der Wächter greift NUR bei `is_test_mode`/`env=staging`.
  In Prod null Verhalten, null Latenz-Risiko idealerweise.
- **Interceptor vs. Wrapper (Analyse-Frage):** Interceptor (httpx-Transport + smtplib/imaplib-Hook)
  gibt härtere Garantie („falsch konfigurierte Tür fliegt auf"), aber tieferer Eingriff und
  smtplib/imaplib sind schwerer global zu hooken als httpx. Wrapper ist weniger invasiv, lässt
  aber Disziplin-Lücken (jedes Modul muss ihn nutzen) — genau das Muster, das #1337 überwinden will.
- **Regel-Budget:** Neuer Laufzeit-Guard braucht Prüfdatum (+90 Tage) ODER ersetzt bestehende
  dienstweise Guards. Der Fang ist konkret belegbar (versehentlicher Prod-Call in Staging).
- **Scheibe A liefert allein noch keinen geschlossenen Dienst** — sie ist Fundament + Inventar.
  Nutzensichtbarkeit entsteht erst, wenn der erste Dienst deklariert und der Tripwire scharf ist.
  ACs müssen deshalb einen **beweisbaren Tripwire-Test** enthalten (undeklarierter Call → Block).
- **Validation-Tools** (Bergfex, geosphere_validator) sind im Issue-Inventar nicht gelistet —
  in Scheibe A als „zu deklarieren" erfassen oder bewusst außen vor lassen (Analyse-Frage).

## Analysis

### Type
Feature (Scheibe A von Epic #1337)

### Technical Approach — Interceptor (Option I), zentraler Monkeypatch
Neues Modul `src/app/egress_guard.py` mit einer Funktion `install_egress_guard(settings)`, die
**nur** bei `is_test_mode or env=="staging"` die drei Transport-Primitive patcht:
- `httpx.HTTPTransport.handle_request` — fängt in httpx 0.28.1 JEDEN synchronen Request, auch
  selbstgebaute `httpx.Client()` (Repo hat keinen custom-transport/AsyncClient/requests).
- `smtplib.SMTP.connect` — Mail (email.py Haupt- + Fallback-Host, core.py-Legacy).
- `imaplib.IMAP4.open` — Stalwart Inbound.
In **Prod wird gar nicht gepatcht** → echter No-Op (null Latenz, null Verhalten). Idempotenz-Flag
gegen Doppel-Patch. Installation an zwei Bootstrap-Stellen: `src/app/cli.py` (Staging-Laufzeit) und
`tests/conftest.py` (pytest, mit Patch-Restore-Fixture gegen Leak in andere Tests).

**Inventar (Andock-Fläche für B–E):** hartcodiertes `INVENTORY: dict[str, IsolationKind]` im Guard-
Modul (host → `TEST_ACCESS` erlaubt | `BLOCKED`). Hartcodiert bewusst — Sicherheits-Manifest, git-
versioniert, code-review-sichtbar, nicht per Env übersteuerbar (sonst Bypass). Dynamische Test-Hosts
(`test_smtp_host`, `imap_host` nach `for_testing()`) werden bei `install()` aus `settings` injiziert.
**Entscheidungsregel:** Host `TEST_ACCESS` → durch; `BLOCKED` → `EgressBlockedError`; **Host in KEINER
Deklaration → `EgressBlockedError` (der Tripwire)**. localhost/127.0.0.1 generisch durchlassen.

### Warum nicht Wrapper (Option W)
W reproduziert die Kernursache von #1337: 15+ Call-Sites müssten diszipliniert einen Helper rufen.
Der bestehende radar_service-Pfad (umgeht bereits `get_provider`+Fixtures) beweist, dass genau diese
Disziplin im Repo real bricht. Eine vergessene Tür ruft den Wrapper nicht → Tripwire strukturell
unmöglich. Auch die „saubere" httpx-Variante (custom BaseTransport + Client-Factory) scheitert, weil
7 Module ihren `httpx.Client()` selbst bauen und die Factory nicht erben.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/app/egress_guard.py` | CREATE | Guard-Kern: `IsolationKind`, `INVENTORY`, `EgressBlockedError`, `install_egress_guard()` + 3 Patches + Idempotenz |
| `tests/tdd/test_egress_guard.py` | CREATE | Tripwire-Beweis: undeklariert→raise, deklariert→durch (Sentinel), Prod→No-Op, selbstgebauter Client→raise; Restore-Fixture |
| `src/app/cli.py` | MODIFY | 1 Aufruf `install_egress_guard(settings)` nach Settings-Konstruktion |
| `tests/conftest.py` | MODIFY | Installations-/Restore-Fixture |

### Scope Assessment
- Files: 2 neu, 2 geändert
- Estimated LoC: ~200–240 (unter 250-Limit, knapp — Import-Guard bewusst nach B–E verschoben)
- Risk Level: HIGH (kritischer Pfad — aber Prod-No-Op begrenzt reales Risiko)

### Deterministischer Tripwire-Test (kein Netz, kein Mock-Theater)
Original-`handle_request` durch Sentinel ersetzen, der `AssertedNetworkTouch` wirft → beweist ohne
ein gesendetes Byte, ob der Guard VOR dem Transport entscheidet:
- (a) `is_test_mode=True`, undeklarierter Host (`api.open-meteo.com`) → `EgressBlockedError`, Sentinel
  nie erreicht. Zusätzlich über selbstgebauten `httpx.Client()` → gleicher Raise.
- (b) deklarierter Test-Host (`mail.henemm.com`, `smtplib.SMTP`) → durch → Sentinel feuert = Beweis
  „durchgelassen" ohne echte Verbindung.
- (c) `env=production` → `httpx.HTTPTransport.handle_request` identisch mit Original-Referenz (kein Patch).

### Reihenfolge/Abhängigkeiten B–E
A trägt das **vollständige bekannte Host-Set** (14 Dienste aus dem Inventar oben) initial ein, sonst
legt der scharfe Tripwire Staging lahm. B–E fügen dann nur je Enum-Eintrag + Deklarations-Test hinzu
bzw. verschärfen `TEST_ACCESS`→`BLOCKED` — **kein Anfassen der Guard-Mechanik**. `IsolationKind` von
Anfang mit beiden Werten → kein Schema-Bruch für B–E.

### Tech-Lead-Entscheidungen zu den 5 offenen Fragen (PO gibt bei Spec-Freigabe frei)
1. Staging-Rollout **hart blockend** mit vollständigem Initial-Inventar (kein Beobachtungsmodus).
2. Validation-Tools (Bergfex, geosphere_validator) **außerhalb A** — laufen nicht im Staging-Report-Prozess.
3. `@pytest.mark.live`-Tests: Guard **nicht** installieren (echte APIs gewollt).
4. Import-Guard (requests/aiosmtplib) **nicht in A** (LoC-Budget) — Restlücke dokumentiert.
5. localhost/127.0.0.1 **generisch durchlassen**.

### Open Questions
- Keine offenen — alle Richtungsfragen als Tech-Lead-Default entschieden (siehe oben), PO-Freigabe an der Spec.
