# Epic 2644 — Verbindliche Konventionen für alle i18n-Pakete

> Stand 2026-10-30. Dieses Dokument schließt **alle** Entwurfsfragen der 32 Pakete (#2645–#2681),
> damit Specs, Developer-Agenten (Haiku/Sonnet) und Adversary ohne Rückfrage arbeiten.
> Weicht ein Paket ab, ist das ein Finding. Grundsatz: ADR-0104. Wortliste: `docs/reference/i18n_glossar.md`.
> Nach Abschluss des Epics wandert der dauerhaft gültige Teil in `docs/reference/` (Paket A1 #2680).

## 1. Sprachen, Auflösung, Persistenz

| Punkt | Festlegung |
|---|---|
| Sprachen | genau `de`, `en`; Typ `Lang`; alles andere → `de` |
| Persistenz | `data/users/<id>/user.json` Feld `language` (top-level, String). Leer/fehlend = `de`. Go schreibt (Read-Modify-Write), Go und Python lesen |
| Go: Reihenfolge | angemeldet: `user.Language` > Cookie `gz_lang` > `Accept-Language` > `de`; öffentlich: Cookie > `Accept-Language` > `de` |
| Python | `resolve_user_lang(user_id) -> Lang` liest `user.json` über dieselbe Pfadlogik wie `src/app/config.py` (`get_data_dir()`); **einziger** Weg; keine Modul-/Prozess-globale Sprache |
| SvelteKit | `hooks.server.ts`: Cookie `gz_lang` > `Accept-Language` > `de` → `event.locals.lang`; `transformPageChunk` liest `event.locals.lang` erst beim Ersetzen von `%lang%` in `app.html`, damit der Layout-Loader (`lang = profil.language ?? locals.lang`, schreibt `locals.lang` zurück) für Angemeldete wirkt; `+layout.svelte` setzt den Store `locale`. Login-Action reicht `gz_lang` aus der Go-Antwort weiter |
| Cookie `gz_lang` | Setzt **Go** bei Login, Register und Profil-Update (Wert = Nutzersprache), und das Frontend-Endpoint `POST /lang` für Besucher. `Path=/`, `Max-Age=31536000`, `SameSite=Lax`, `Secure` auf https, nicht HttpOnly (Frontend-Server liest es, Client braucht es nicht) |
| Umschalter (Besucher) | `frontend/src/routes/lang/+server.ts` (`POST`, Formfeld `lang`, `redirect` zurück auf `Referer` oder `/`) |
| Registrierung | Frontend sendet `language: data.lang`; Go validiert, speichert, setzt Cookie |
| API-Vertrag | **Es gibt kein `/api/me`**: Profil ist `GET /api/auth/profile` → `language` (wirksame Sprache, `de` wenn Feld fehlt); `PUT /api/auth/profile` nimmt `language` (nur `de`/`en`, Kleinschreibung); Fehlerobjekt `{"code": "...", "message": "..."}` (Abschnitt 5) |

## 2. Katalog-Konventionen (alle drei Schichten)

- **Schlüssel:** `bereich.gruppe.element`, nur `[a-z0-9_.]`, 2–4 Segmente. Beispiele: `versand.kanal.telegram.label`, `mail.betreff.briefing`, `fehler.etag_mismatch`.
- **Platzhalter:** `{name}` in snake_case, identisch in `de` und `en` (Paritätstest prüft die Platzhaltermenge je Schlüssel). Keine Satz-Konkatenation, keine positionsabhängigen `%s`.
- **Plural:** zwei Schlüssel `x.one` / `x.other`; Aufruf `tn("x", count, …)`; `{count}` ist implizit verfügbar.
- **Kein HTML** im Katalog; Ausnahme Frontend-Bereich `hilfe`: `<strong>`, `<br>`.
- **Englischer Stil:** Sentence case („Save as defaults", nicht „Save As Defaults"); einfache Sätze; Fachbegriffe laut Glossar; Oxford-freie Aufzählungen; keine Ausrufezeichen. Verboten: *tour*.
- **Deutsch bleibt wörtlich** wie heute (Golden-Tests). Rechtschreibkorrekturen sind kein Teil dieses Epics.
- **Wiederverwendung:** Texte, die auf Trip- und Ortsvergleich-Flächen identisch sind, liegen in `aktionen.*` (Frontend) bzw. `allgemein.*` (Python/Go). Nie zwei Schlüssel für denselben Text.
- **Nie im Katalog:** Protokoll-Token (`sms_code`, `compact_label`, `col_label`, Kürzel), Eigennamen (Kanäle, Provider, Orte, Regionen), Nutzertexte, Log-/Debug-Ausgaben.
- **Fallback:** fehlt `en`, wird `de` ausgegeben und einmal je Prozess geloggt (`i18n fallback: <key>`); der Paritätstest verhindert das im Repo.
- **Parität:** je Schicht ein Test, der für jeden Bereich `set(keys_de) == set(keys_en)` und gleiche Platzhaltermengen erzwingt.
- **Allowlists** der Ratschen sind JSON-Listen von Pfad-Präfixen; sie werden nur gekürzt. Ein Adversary-Punkt je Paket: „Allowlist-Eintrag des Pakets entfernt?"

### Namensräume (Dateien)

| Schicht | Datei je Sprache | Bereiche (eine Datei je Bereich, **alle in S2/P1/G1 leer angelegt**) |
|---|---|---|
| Frontend | `frontend/src/lib/i18n/messages/{de,en}/<bereich>.json` | `start`, `auth`, `nav`, `home`, `listen`, `konto`, `admin`, `wertebereiche`, `versand`, `alarme`, `layout`, `trip`, `vergleich`, `aktionen`, `bausteine`, `fehler`, `hilfe` |
| Python | `src/i18n/messages/{de,en}/<bereich>.json` | `allgemein`, `mail`, `vergleich`, `alarm`, `warnung`, `telegram`, `sms`, `versand`, `inbound`, `api` |
| Go | `internal/i18n/messages/{de,en}/<bereich>.json` | `fehler`, `auth`, `konto`, `fach`, `mail` |

Die Import-/Ladelisten (`messages/de/index.ts`, Python-Loader, Go-`embed`) werden **im Kern-Paket vollständig** angelegt, damit Migrationspakete nur ihre eigene Bereichsdatei anfassen (kein Merge-Konflikt). Da die Umsetzung in **einer** Sitzung nacheinander läuft, darf ein Paket Schlüssel in einer fremden Bereichsdatei **ergänzen** (nie umbenennen oder löschen), wenn der Text fachlich dorthin gehört (z. B. F2 und F3 in `home.json`). Allowlist-Einträge nennen konkrete Dateien oder Verzeichnisse mit `/`, keine losen Präfixe.

## 3. Frontend-Schnittstelle (`frontend/src/lib/i18n`)

```ts
// index.ts
export type Lang = 'de' | 'en';
export type MessageKey = keyof typeof de;              // Vereinigung aller Bereichsdateien (messages/de/index.ts)
export const locale: Writable<Lang>;                    // gesetzt in +layout.svelte aus data.lang
export const t: Readable<(key: MessageKey, params?: Record<string, string | number>) => string>;   // Svelte: {$t('key')}
export const tn: Readable<(key: string, count: number, params?) => string>;                       // Plural: key ohne .one/.other
export function tr(key: MessageKey, params?): string;   // für .ts-Module ohne Store-Kontext (liest get(locale))
export function trFor(lang: Lang | undefined, key: MessageKey, params?): string;  // Server-Actions/Loader (kein geteilter Store auf dem Server); undefined → de
export function trn(key: string, count: number, params?): string;              // Plural für .ts-Module (Gegenstück zu tn)
// format.ts
export function fmtDate(d: Date, lang: Lang, style: 'kurz' | 'lang'): string;   // kurz: 'Fr 30.10.' | 'Fri 30 Oct'; lang: 'Freitag, 30. Oktober 2026' | 'Friday, 30 October 2026'
export function fmtTime(d: Date): string;                                       // '14:30' (24 h, beide)
export function fmtWeekday(d: Date, lang: Lang, kurz?: boolean): string;        // 'Fr' | 'Fri'
export function fmtRelativeMinutes(min: number, lang: Lang): string;            // 'vor 3 Min' | '3 min ago' (tn)
```

- In Svelte-Markup immer `{$t('bereich.x')}`; in `.ts` `tr(...)`. Dynamische Schlüssel nur mit Kommentar `// i18n-dynamic: <präfix>` (Verwender-Test).
- Bestandskatalog (112 Schlüssel: `start` 30, `hilfe` 42, `onboarding` 19, `info` 9, `tip` 8, `telegram_kurzstil` 2, `nav` 1, `standardwerte` 1) wird in S2 **ohne Umbenennung** auf die Bereichsdateien verteilt (`info`/`tip`/`telegram_kurzstil`/`standardwerte` → `bausteine.json`, `onboarding` → `home.json`) und vollständig nach `en` übersetzt.
- Metrik-Namen kommen aus `GET /api/metrics` (`label_de`, `label_en`, `alert_label`, `alert_label_en`); Auswahl über `metricLabel(def, lang)` in `$lib/i18n/metricLabel.ts` (F5). Fallback `label_de`.
- Tests: `node:test` (kein Vitest im Repo): `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test <datei>`; `locale.set('en')` im Test; Prüfung über `tr()`-Werte, nie über Literale.
- `svelte-check` muss grün bleiben (unbekannter Schlüssel = Typfehler).

### Ratsche Frontend (S4)

`frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts`: für jede `*.svelte` (ohne `__tests__/`, `routes/_design*`, `routes/email-preview-dev`) `<script>`/`<style>` entfernen, `{…}`-Ausdrücke entfernen, dann (a) Textknoten mit ≥ 2 Buchstaben `[A-Za-zÄÖÜäöüß]`, (b) statische Attributwerte von `title|aria-label|placeholder|alt|label` melden. Allowlist `frontend/src/lib/i18n/hardcode_allowlist.json` (Pfade relativ zu `frontend/src/`, Verzeichnisse mit `/` am Ende); beide Richtungen rot: Treffer ohne Eintrag **und** Eintrag ohne Treffer; Startstand per `--messen` erzeugen. Ab F11 zusätzlich `*.ts` in `lib/utils`, `lib/stores`, `lib/api.ts` mit Heuristik „String-Literal mit Umlaut/ß oder Signalwort (`nicht`, `bitte`, `fehlgeschlagen`, `gespeichert`)".

## 4. Python-Schnittstelle (`src/i18n`)

```python
Lang = Literal["de", "en"]
def t(key: str, lang: Lang = "de", /, **params: object) -> str
def tn(key: str, count: int, lang: Lang = "de", /, **params: object) -> str
def resolve_user_lang(user_id: str, data_dir: str | Path | None = None) -> Lang
def fmt_date(d: date | datetime, lang: Lang, style: Literal["kurz", "lang"] = "kurz") -> str   # 'Fr 30.10.' | 'Fri 30 Oct'
def fmt_weekday(d: date | datetime, lang: Lang, kurz: bool = True) -> str                     # 'Fr' | 'Fri'
def fmt_time(d: datetime) -> str                                                               # '14:30'
def relative_day(delta_days: int, lang: Lang) -> str                                           # heute/morgen/übermorgen | today/tomorrow/day after tomorrow
```

- Render-Funktionen bekommen `*, lang: Lang = "de"` (keyword-only, Default bewahrt Alt-Aufrufer und Golden-`de`). Orchestrierer (`trip_report_scheduler`, `trip_alert`, `compare_*`, Inbound) rufen `resolve_user_lang(user_id)` **einmal je Nutzer** und reichen `lang` durch.
- Metrik-Register (`src/app/metric_catalog.py`): neue Felder `label_en: str = ""`, `alert_label_en: str = ""`, `friendly_label_en: str = ""`; Methoden `label(lang)`, `alert_label_for(lang)`, `friendly_label_for(lang)` mit Fallback auf die deutschen Felder; `aggregation_label(aggregation, lang)` neben `aggregation_label_de`. **Unverändert:** `col_label`, `compact_label`, `sms_code` (falls vorhanden), `col_key`.
- Token-Wächter: `tests/fixtures/metric_tokens_frozen.json` = `{metric_id: {"col_label":…, "compact_label":…, "sms_code":…}}`, erzeugt in P1 aus dem Ist-Stand; `tests/test_metric_tokens_eingefroren.py` vergleicht byte-genau.
- Mail-Marker: `X-GZ-Lang: de|en` setzt `src/output/channels/email.py` neben den bestehenden `X-GZ-Mail-Type`-Headern; Go-Mails setzen ihn ebenfalls (G4).
- Golden-Tests: je Renderer-Paket vor der Umstellung die heutige deutsche Ausgabe mit **deterministischer** Fixture (feste Zeit `2026-10-29T06:00+02:00`, feste Wetterwerte, Nutzer `golden-de`) nach `tests/golden/<paket>/<fall>.de.(html|txt)` schreiben; Test vergleicht nach der Umstellung byte-genau. `en`-Ausgabe derselben Fixture wird als `*.en.*` eingecheckt (Review-Hilfe, Validator-Fixture).

### Englische Namen der Wettergrößen (Klasse 2 „voll"; P1 trägt sie ein)

| id | `label_de` | `label_en` | `alert_label` → `alert_label_en` |
|---|---|---|---|
| temperature | Temperatur | Temperature | Temp → Temp |
| temperature_cold | Tiefsttemperatur-Alarm | Low temperature alert | Temp → Temp |
| temperature_night | Nacht-Tiefsttemperatur | Night low | — |
| temperature_day_low | Tages-Tiefsttemperatur (Gehzeit) | Daytime low (walking hours) | — |
| temperature_day_high | Tages-Höchsttemperatur (Gehzeit) | Daytime high (walking hours) | — |
| (alle weiteren Register-Einträge, z. B. `sunshine`, gefühlte Tages-Tiefst-/Höchsttemperatur) | laut `label_de` | nach demselben Muster (Glossar), P1 vervollständigt die Tabelle in der Spec | ≤ 12 Zeichen |
| wind_chill | Gefühlte Temperatur | Feels-like temperature | — |
| wind_chill_night | Gefühlte Nacht-Tiefsttemperatur | Feels-like night low | — |
| humidity | Luftfeuchtigkeit | Humidity | Feuchte → Humidity |
| dewpoint | Taupunkt | Dew point | — |
| wind | Wind | Wind | Wind → Wind |
| gust | Böen | Wind gusts | Böen → Gusts |
| wind_direction | Windrichtung | Wind direction | — |
| precipitation | Niederschlag | Precipitation | Niedersch → Precip |
| rain_probability | Regenwahrscheinlichkeit | Rain probability | Regen% → Rain% |
| confidence | Sicherheit | Confidence | — (nicht wählbar, #710) |
| thunder | Gewitter | Thunderstorm | Gewitter → Thunder |
| cape | Gewitterenergie (CAPE) | Thunderstorm energy (CAPE) | CAPE → CAPE |
| snowfall_limit | Schneefallgrenze | Snow line | 0°-Grenze → 0° line |
| precip_type | Niederschlagsart | Precipitation type | — |
| cloud_total | Bewölkung | Cloud cover | — |
| cloud_low | Tiefe Wolken | Low clouds | — |
| cloud_mid | Mittelhohe Wolken | Mid-level clouds | — |
| cloud_high | Hohe Wolken | High clouds | — |
| visibility | Sichtweite | Visibility | Sicht → Visib |
| uv_index | UV-Index | UV index | UV-Index → UV index |
| pressure | Luftdruck | Air pressure | — |
| freezing_level | Nullgradgrenze | Freezing level | Nullgradgrenze → Freezing lvl |
| snow_depth | Schneehöhe | Snow depth | Schneehöhe → Snow depth |
| fresh_snow | Neuschnee | Fresh snow | Neuschnee → Fresh snow |

Auswertungen: `min` Minimum/Minimum · `max` Maximum/Maximum · `avg` Mittel/Average · `sum` Summe/Total. Alle `alert_label_en` ≤ 12 Zeichen (Alarm-Kurzform ~10, ADR-0042).

### Ratsche Python (P11)

`tests/test_i18n_keine_hartkodierten_nutzertexte_python.py`: AST-Lauf über `src/output/**`, `src/services/*{report,alert,notification,command,inbound,preview,comparison}*.py`, `api/routers/**`; meldet String-Konstanten mit Umlaut/ß oder Signalwörtern (`nicht`, `bitte`, `keine`, `fehlgeschlagen`, `Hinweis`) außerhalb von `t(...)`-Argumenten, Docstrings, Kommentaren und Zeilen mit `# i18n-log`. Allowlist `tests/fixtures/i18n_python_allowlist.json`.

## 5. Go-Schnittstelle (`internal/i18n`)

```go
type Lang string
const De Lang = "de"; const En Lang = "en"
type Args map[string]any
func Parse(s string) Lang                               // "en" → En, sonst De
func T(lang Lang, key string, args Args) string         // {name}-Platzhalter; fehlender en-Schlüssel → de + einmaliges Log
func Tn(lang Lang, key string, count int, args Args) string
func FromContext(ctx context.Context) Lang              // Default De
func WithLang(ctx context.Context, lang Lang) context.Context
func FromRequest(r *http.Request, user *model.User) Lang // Reihenfolge Abschnitt 1
// internal/handler/httperr.go
func WriteError(w http.ResponseWriter, r *http.Request, status int, code string, args i18n.Args)   // JSON {"code":code,"message":T(lang,"fehler."+code,args)}
```

- Middleware `middleware.Lang` läuft **nach** Auth, lädt den Nutzer (Store) und legt die Sprache in den Kontext; öffentliche Routen nutzen Cookie/Header.
- **Ist-Stand Go (Messung Spec G1–G5):** nur 57 deutsche Nutzertexte; rund 416 Fehlerstellen antworten heute schon mit englischen Codes im Feld `error` (`{"error":"invalid credentials"}`). `WriteError` schreibt deshalb übergangsweise `error` (= `code`) und `detail` zusätzlich zu `code`/`message`; Alt-Codes mit Leerzeichen werden snake_case; Suchkette `fehler.` → `auth.fehler.` → `konto.fehler.` → `fach.fehler.`.
- Jede Fehlerantwort an den Client geht über `WriteError`; `code` ist stabil (snake_case) und wird in `docs/reference/api_contract.md` gelistet; das Frontend übersetzt bekannte Codes selbst (`fehler.code.<code>`), unbekannte zeigt es mit `message`.
- Mails: Schlüssel je Zeile (`mail.verify.betreff`, `mail.verify.z1` …), **keine** `text/template`-Dateien je Sprache (Paritätstest bleibt einheitlich). Empfängersprache = `user.Lang()`; Admin-Mails an den Betreiber bleiben `de`.
- Logs bleiben deutsch und tragen bei Umlauten den Zeilenkommentar `// i18n-log`.

### Ratsche Go (G5)

`internal/i18n/hardcode_guard_test.go`: `go/parser` über `internal/{handler,mail,notify,store,middleware,resolver}`; meldet String-Literale mit Umlaut/ß oder Signalwörtern in Argumenten von `http.Error`, `json.NewEncoder(...).Encode`, `fmt.Errorf` (nur wenn in Response geschrieben) und Mail-Builder; Ausnahme `// i18n-log`; Allowlist `internal/i18n/hardcode_allowlist.json`.

## 6. Validatoren und E2E

- Alle vier Validatoren lesen `X-GZ-Lang`; Erwartungen (Überschriften, Legendenzeile, Hinweise, Betreff-Muster) kommen aus `src/i18n` (`t(key, lang)`), nie aus Literalen. Übergang (PV): Header fehlt → `de` + Warnung; nach A2: Header fehlt → Exit ≠ 0.
- **Zweiter Staging-Nutzer `en` ohne neue Infrastruktur:** Postfach per **Subadressierung** des bestehenden Staging-Postfachs (`<GZ_IMAP_USER-Lokalteil>+en@<domain>`, Stalwart liefert `user+tag` ins Basispostfach); Validatoren filtern zusätzlich auf den `To`-Header. Nutzer wird über `POST /api/auth/register` auf Staging mit `language: "en"` angelegt (Skript `scripts/staging_e2e_user_en.py`, idempotent). Zugangsdaten als `GZ_E2E_EN_*`-Secrets in der Staging-Umgebung, nicht im Repo.
- **Telegram** hat eine Chat-Zuordnung je Nutzer (ein Chat = ein Nutzer, `address_owner.go`): die englische Live-Prüfung setzt die Sprache des bestehenden Test-Nutzers auf `en`, sendet, prüft, setzt auf `de` zurück (im Skript, mit `finally`). Kein zweiter Chat nötig.
- `.claude/e2e_verified/<sha>.json` erhält `"langs": ["de", "en"]`.
- Playwright `frontend/e2e/sprachwechsel.spec.ts` (F12) läuft im CI-Check `e2e` mit.

## 7. Autonomer Ablauf (eine Sitzung, Pakete nacheinander)

1. **Block-Freigabe (einmalig, PO):** PO antwortet im Epic #2644 mit `freigabe i18n-specs` oder hakt in den Specs `- [x] Approved` ab. Die erste Sitzung setzt daraufhin in allen 32 Specs `- [x] Approved (PO-Freigabe <Datum>)` und `status: approved` in **einem** Commit. Danach gibt es keine PO-Frage mehr, außer ein Hard Gate scheitert.
2. **Nächstes Paket:** erstes offenes Paket der Reihenfolge in `docs/features/epic-i18n-de-en.md` (Abschnitt „Reihenfolge"), dessen Abhängigkeiten geschlossen sind (`gh api repos/henemm/gregor_zwanzig/issues/<n> --jq .state`). `/next-ticket` darf anders entscheiden, wenn ein Hotfix wartet; danach zurück zur Reihenfolge.
3. **Je Paket:** `/01-feature <issue>` (Workflow anlegen, `OPENSPEC_ACTIVE_WORKFLOW` setzen) → `/10-context` → `/20-analyse` (kurz, Konventionen gelten) → `/30-write-spec` erkennt die vorhandene, freigegebene Spec `docs/specs/modules/i18n_<paket>_<issue>.md` und lässt nur den `spec-validator` laufen (kein Neuschreiben, keine Freigabefrage) → `/40-tdd` (RED aus den ACs) → `/50-implement` mit **Developer-Agent im Modell laut Spec-Kopf** (`model: haiku` bzw. `sonnet`; Briefing Abschnitt 8) → `/60-validate` (Adversary Sonnet, Mutations-Gegenprobe Pflicht) → PR, 6 CI-Checks, Merge → `/70-deploy` (Staging-Poll → `/e2e-verify` → Prod → Selftest → Issue-Close) → `/clear`.
4. **Haiku scheitert** (zweimal keine grünen Tests oder Adversary BROKEN mit Ursache „Verständnis"): Paket mit `sonnet` wiederholen, Modell im Spec-Kopf aktualisieren, Kommentar im Issue.
5. **Hard Gate scheitert** (Staging BROKEN, Selftest ≠ 0, CI dauerhaft rot): Rollback laut `operations_playbook.md`, Befund als Kommentar im Paket-Issue **und** im Epic, Sitzung hält an. Das ist die einzige Unterbrechung.
6. **Phasenwechsel:** ein Kommentar im Epic („Phase 1 abgeschlossen, Allowlist leer, Stand `<sha>`").
7. **Kontext:** nach jedem Paket `/clear`; Konventionen und Spec werden je Paket neu gelesen, nicht aus dem Gedächtnis.

## 8. Briefing-Baustein für Developer-Agenten (Haiku)

```
Issue #<n> (<Paket>), OPENSPEC_ACTIVE_WORKFLOW=<name>. Spec: docs/specs/modules/i18n_<paket>_<issue>.md (freigegeben).
Konventionen: docs/features/epic-i18n-de-en-konventionen.md (Abschnitte 2 + <3|4|5>). Glossar: docs/reference/i18n_glossar.md. Verboten: "Tour"/"tour".
Dein Bereich: <Dateiliste aus der Spec>. Dein Katalog-Namensraum: <bereich> → nur messages/{de,en}/<bereich>.json anfassen.
Beispiel-Umstellung (aus dem Kern-Paket): <vorher> → <nachher>.
Pflicht: (1) RED-Tests aus den ACs grün machen, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag "<präfix>" entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an col_label/compact_label/sms_code/Kürzeln.
Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte "verbessern", neue Abhängigkeiten.
```

## 9. Reihenfolge (topologisch, eine Sitzung)

S0 #2645 → S1 #2646 → S2 #2647 → S4 #2649 → S3 #2648 → P1 #2662 → PV #2663 → G1 #2675 → F1 #2650 → F11 #2660 → F2 #2651 → F3 #2652 → F4 #2653 → F6 #2655 → F8 #2657 → F5 #2654 → F7 #2656 → F9 #2658 → F10 #2659 → P2 #2664 → P3 #2665 → P4 #2666 → P5 #2667 → P6 #2668 → P7 #2669 → P8 #2670 → P9a #2671 → P9b #2672 → P10 #2673 → P11 #2674 → G2 #2676 → G3 #2677 → G4 #2678 → G5 #2679 → F12 #2661 → A1 #2680 → A2 #2681.

**Skalenwörter (`src/services/weather_metrics.py`, `format_wind_strength` u. a.)** werden von P2 (`email/helpers.py`) und P4 (`compare_outlook_metric_ids.py`) aufgerufen, gehören aber zu P11. Regel: das **erste** Paket, das eine Skalenfunktion in einer englischen Ausgabe braucht, legt dort den keyword-only Parameter `lang` mit Default `"de"` und die `api.skala.*`-Schlüssel an; spätere Pakete prüfen per Grep und nutzen ihn. Dieselbe Regel gilt für `metric_catalog.format_metric_value` (P2/P3/P5) und `fmt_date_numeric` in `src/i18n/format.py` (P4/F2-Pendant). **`src/app/thunder_scale.py`** (Gewitter-Wortschatz, kein Paket im Issue-Plan): P2 legt `THUNDER_LABEL_EN`, `thunder_label(level, lang)`, `format_hail_note(lang)` an; P3 die englischen Satzbauer als parallele Tabellen im Domänenmodul (kein `src/i18n`-Import dort, Schichtwächter #1365); P5/P7/P9b/P10 nutzen sie.

Ratschen-Pakete (S4, P11-Ratsche, G5) legen ihre Allowlist mit dem **vollen** Startstand an, sobald der jeweilige Kern steht; die Endstände (leer) werden in P11 bzw. G5 nach den Migrationspaketen abgenommen. Deshalb steht P11 nach P2–P10 und G5 nach G2–G4, der Ratschen-Test selbst entsteht aber früh (P11-Teil 1 direkt nach P1, G5-Teil 1 direkt nach G1 — in einem Workflow mit zwei Commits oder als Teil der Kern-PR, Entscheidung in der Spec).
