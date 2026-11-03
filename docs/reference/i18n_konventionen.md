# i18n-Konventionen — Zweisprachigkeit de/en

> Ist-Stand nach Epic #2644 (Abschluss 2026-11-02). Grundsatz: `docs/adr/0104-zweisprachigkeit-de-en.md`.
> Wortliste (bindend): `docs/reference/i18n_glossar.md`. Kanal-Parität: `docs/adr/0095-kanal-paritaet-jeder-kanal-jede-frage.md`.
> Die Epic-Konventionen `docs/features/epic-i18n-de-en-konventionen.md` bleiben als Entwurfsdokument
> erhalten; diese Referenz gilt. Abweichungen zwischen Konvention und Code gilt der **Code** (hier
> sind die Signaturen aus dem Code übernommen).

## 1. Sprachen, Auflösung, Persistenz

| Punkt | Festlegung (Code-Beleg) |
|---|---|
| Sprachen | genau `de` und `en`; alles andere wird als `de` gewertet (`src/i18n/lang.py`, `internal/model/user.go` `IsValidLanguage`) |
| Persistenz | `data/users/<user_id>/user.json`, Feld `language` (top-level). Leer oder fehlend = `de`. Go schreibt per Read-Modify-Write (ADR-0101), Go und Python lesen |
| Go-Auflösung (`internal/i18n/request.go`, `FromRequest`) | gespeicherte Nutzersprache > Cookie `gz_lang` > `Accept-Language` > `de`. Ungültige Werte werden übersprungen, nicht als `de` gewertet. Öffentliche Routen haben keinen Nutzer und folgen derselben Kette ohne Nutzerwert |
| Go-Middleware | `middleware.Lang` (`internal/middleware/lang.go`), in `internal/router/router.go` direkt nach `AuthMiddleware` eingehängt; legt die Sprache per `i18n.WithLang` in den Request-Kontext |
| Python | `resolve_user_lang(user_id, data_dir=None) -> Lang` in `src/i18n/lang.py`. Liest `user.json` unter `get_data_root()` (`src/app/loader.py`), Kennung über `is_valid_user_id`. Fehler jeder Art ergeben `de`. Reihenfolge im Feld: Top-Level `language` > `preferences.language` > `de` (`language_from_user_dict`). **Kein** Prozess- oder Modulzustand: jeder Aufruf liest die Datei neu |
| SvelteKit | `frontend/src/hooks.server.ts`: Cookie `gz_lang` > `Accept-Language` > `de` über `resolveLang` → `event.locals.lang`. `app.html` trägt `lang="%lang%"`, `transformPageChunk` ersetzt es erst beim Rendern, damit der Layout-Loader die Profilsprache der Angemeldeten noch berücksichtigen kann. Der Store `locale` (`frontend/src/lib/i18n/locale.ts`) wird im Layout gesetzt |
| Cookie `gz_lang` | Go setzt es bei Anmeldung, Registrierung und Profil-Update, aber nur bei gespeicherter Sprache (`internal/middleware/lang.go`, `SetLangCookie`): `Path=/`, `Max-Age=31536000`, `SameSite=Lax`, `Secure` bei https, nicht HttpOnly. Besucher-Umschalter: `POST /lang` (`frontend/src/routes/lang/+server.ts`, Formfeld `lang`) |
| API-Vertrag | Profil: `GET /api/auth/profile` und `PUT /api/auth/profile` (Feld `language`), Registrierung: `POST /api/auth/register`. **Einen Endpunkt `/api/me` gibt es nicht.** Details: `docs/reference/api_contract.md`, Abschnitt „Nutzerprofil und Sprache" |

Regeln: Sprache nur aus dem Konto (bzw. Cookie/Header für Besucher), nie aus globalem Zustand,
nie über den Nutzer `"default"`. Jeder datenbewegende Pfad wird mit **zwei** Nutzern getestet. Der
Konto-Wert wird bei Nachrichten aus dem Nutzer der jeweiligen Nachricht gelesen, nicht aus dem
Auftraggeber eines Batches.

## 2. Katalog-Konventionen

- **Schlüssel:** `bereich.gruppe.element`, nur `[a-z0-9_.]`, 2 bis 4 Segmente. Beispiele: `versand.kanal.telegram.label`, `mail.betreff.briefing`, `fehler.etag_mismatch`.
- **Platzhalter:** `{name}` in snake_case, in `de` und `en` dieselbe Menge. Keine Satzkonkatenation, keine positionsabhängigen `%s`.
- **Plural:** zwei Schlüssel `x.one` und `x.other`; Aufruf `tn("x", count, …)` bzw. `tn`/`trn` im Frontend. `{count}` ist implizit verfügbar.
- **Kein HTML** im Katalog. Ausnahme: Frontend-Bereich `hilfe` mit `<strong>` und `<br>`.
- **Englischer Stil:** Sentence case, einfache Sätze, Fachbegriffe laut Glossar, keine Ausrufezeichen. Das verbotene Produktwort aus dem Glossar-Kopf wird nie verwendet.
- **Deutsch bleibt wörtlich.** Golden-Tests vergleichen die deutsche Ausgabe byte-genau. Rechtschreibkorrekturen sind kein Teil der Kataloge.
- **Wiederverwendung:** Texte, die auf Trip- und Ortsvergleich-Flächen gleich sind, liegen im geteilten Bereich (`aktionen.*` im Frontend, `allgemein.*` in Python). Nie zwei Schlüssel für denselben Text.
- **Nie im Katalog:** Protokoll-Token (`sms_code`, `compact_label`, `col_label`, Kürzel), Eigennamen (Kanäle, Provider, Orte, Regionen), Log- und Debug-Ausgaben.
- **Fallback:** fehlt der Schlüssel in `en`, wird `de` ausgegeben und einmal je Prozess gemeldet. Go loggt `i18n fallback: <key>` (`internal/i18n/catalog.go`), das Frontend warnt per `console.warn` mit demselben Wortlaut (`frontend/src/lib/i18n/translate.ts`). Die Paritätstests verhindern den Fall im Repo.
- **Parität:** je Schicht ein Test, der Schlüsselmengen und Platzhaltermengen je Bereich vergleicht. Frontend: `frontend/src/lib/i18n/__tests__/paritaet_de_en.test.ts`. Python: `tests/test_i18n_inbound_katalog_paritaet.py`, `tests/test_i18n_api_katalog_paritaet.py`, `tests/unit/test_i18n_katalog_paritaet.py`. Go: `internal/i18n/katalog_paritaet_test.go`.

### Namensräume (Dateien)

| Schicht | Datei je Sprache | Bereiche (eine Datei je Bereich) |
|---|---|---|
| Frontend | `frontend/src/lib/i18n/messages/{de,en}/<bereich>.json` | `start`, `auth`, `nav`, `home`, `listen`, `konto`, `admin`, `wertebereiche`, `versand`, `alarme`, `layout`, `trip`, `vergleich`, `aktionen`, `bausteine`, `fehler`, `hilfe` |
| Python | `src/i18n/messages/{de,en}/<bereich>.json` | `allgemein`, `mail`, `vergleich`, `alarm`, `warnung`, `telegram`, `sms`, `versand`, `inbound`, `api` |
| Go | `internal/i18n/messages/{de,en}/<bereich>.json` | `fehler`, `auth`, `konto`, `fach`, `mail` |

Die Ladelisten (`frontend/src/lib/i18n/messages/de/index.ts`, Python-Loader, Go-`embed`) sind vollständig
angelegt. Ein Paket ergänzt Schlüssel in einer fremden Bereichsdatei nur, wenn der Text dorthin gehört;
Schlüssel werden nie umbenannt oder gelöscht.

## 3. Schnittstellen je Schicht (Ist-Stand)

### Frontend — `frontend/src/lib/i18n`

- `index.ts`: `t` (Store, Svelte-Markup `{$t('key')}`), `tn` (Store, Plural), `tr(key, params?)` und `trn(key, count, params?)` (`.ts`-Module, lesen `get(locale)`), `trFor(lang, key, params?)` und `trnFor(lang, key, count, params?)` (Server-Actions und Loader, `undefined` ergibt `de`), `MessageKey`, Re-Export von `locale` und `Lang`.
- `locale.ts`: `export type Lang = 'de' | 'en'` und `locale` (Writable, Startwert `de`).
- `format.ts`: `fmtDate(d, lang, 'kurz' | 'lang')`, `fmtDateNumeric(d, lang)`, `fmtTime(d)`, `fmtWeekday(d, lang, kurz?)`, `fmtRelativeMinutes(min, lang)`.
- `metricLabel.ts`: `metricLabel(def, lang)`, `metricAlertLabel(def, lang)`, `metricAggregationLabel(aggregation, fallback, lang)`.
- `resolveLang.ts`: `resolveLang(quelle)` und `parseAcceptLanguage(header)`. `fehlerCode.ts`: `fehlerTextFuerCode(code)` für bekannte Fehlercodes.
- Svelte: `{$t('bereich.x')}`. In `.ts`: `tr(...)`, auf dem Server `trFor(locals.lang, ...)`. Dynamische Schlüssel nur mit dem Kommentar `// i18n-dynamic: <präfix>`.
- Tests: `node:test`. Prüfung über die Übersetzungswerte, nicht über Literale. `svelte-check` meldet unbekannte Schlüssel als Typfehler.

### Python — `src/i18n`

- `__init__.py`: `t(key, lang="de", /, **params) -> str` und `tn(key, count, lang="de", /, **params) -> str`. Fallback: `en` fehlt, dann `de`, dann der Schlüssel selbst.
- `catalog.py`: `get_catalog()`, `Catalog.nachschlagen(key, lang)`, `Catalog.melde_einmal(art, key)`, `parity_errors(root)`.
- `lang.py`: `Lang = Literal["de", "en"]`, `resolve_user_lang(user_id, data_dir=None) -> Lang`, `language_from_user_dict(data) -> Lang`.
- `format.py`: `fmt_date(d, lang, style="kurz")`, `fmt_date_numeric(d, lang)`, `fmt_weekday(d, lang, kurz=True)`, `fmt_time(d)`, `relative_day(delta_days, lang)`.
- Render-Funktionen nehmen `lang` als Schlüsselwort mit Default `"de"`. Orchestrierer rufen `resolve_user_lang(user_id)` einmal je Nutzer und reichen `lang` durch.
- Metrik-Register (`src/app/metric_catalog.py`): Felder `label_en`, `alert_label_en`, `friendly_label_en`; Methoden `label(lang)`, `alert_label_for(lang)`, `friendly_label_for(lang)`; Funktion `aggregation_label(aggregation, lang="de")`. Fallback ist immer die deutsche Form. Die englischen Namen stehen in der Registertabelle dort, nicht hier.
- Token-Wächter: `tests/fixtures/metric_tokens_frozen.json` und `tests/test_metric_tokens_eingefroren.py` frieren `col_label`, `compact_label` und `sms_code` byte-genau ein.

### Go — `internal/i18n`

```go
type Lang string        // const De Lang = "de"; const En Lang = "en"
type Args map[string]any
func Parse(s string) Lang                                  // "en" -> En, sonst De
func T(lang Lang, key string, args Args) string            // {name}-Platzhalter; Fallback de + Log
func Tn(lang Lang, key string, count int, args Args) string
func FromContext(ctx context.Context) Lang                 // ohne Eintrag De
func WithLang(ctx context.Context, lang Lang) context.Context
func FromRequest(r *http.Request, user *model.User) Lang   // Reihenfolge Abschnitt 1
const CookieName = "gz_lang"
// internal/handler/httperr.go
func WriteError(w http.ResponseWriter, r *http.Request, status int, code string, args i18n.Args)
```

- `T` und `Tn` sind Paketfunktionen und zugleich Methoden von `Catalog`. `ErrorBody` (`internal/i18n/errorbody.go`) baut das Fehlerobjekt.
- Fehlerobjekt der Go-API: `{"code", "message", "error", "detail"}`. `code` ist stabil (snake_case), `message` ist der Text in der Anfragesprache, `error` (= `code`) und `detail` sind Übergangsfelder für bestehende Clients. Suchkette: `fehler.<code>` → `auth.fehler.<code>` → `konto.fehler.<code>` → `fach.fehler.<code>`, unbekannte Codes ergeben `fehler.unbekannt`. Liste der Codes: `docs/reference/api_contract.md`.
- Python-Core (FastAPI): Fehlerobjekt `{"detail", "code"}` (`api/fehler.py`), `detail` bleibt Zeichenkette, `code` kommt hinzu.
- Mails: je Zeile ein Schlüssel (`mail.verify.betreff` usw.). Keine `text/template`-Datei je Sprache. Empfängersprache ist die Kontosprache. Admin-Mails an den Betreiber bleiben `de`.
- Logs bleiben deutsch und tragen bei Umlauten den Marker `// i18n-log` (Go) bzw. `# i18n-log` (Python).

## 4. Die drei Ratschen

Alle drei verbieten neue hartkodierte Nutzertexte außerhalb des Katalogs. Die Allowlists dürfen nur schrumpfen. Die Mechanik steht in `docs/reference/gates_und_ratschen.md`, Abschnitt „i18n-Ratschen".

| Schicht | Testdatei | Scanfläche | Allowlist | Marker | Endstand 2026-11-02 |
|---|---|---|---|---|---|
| Frontend (S4) | `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | `frontend/src/**/*.svelte` (ohne `__tests__/`, `routes/_design*`, `routes/email-preview-dev`) plus `*.ts` in `lib/utils`, `lib/stores`, `lib/api.ts` | `frontend/src/lib/i18n/hardcode_allowlist.json` | `/* i18n-neutral: <Begründung> */` im Markup-Ausdruck für sprachneutrale Literale (F13); `// i18n-dynamic:` für Schlüssel (Verwender-Test) | leer (`[]`), gehalten durch `hardcode_allowlist_leer.test.ts` |
| Python (P11) | `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` | `src/output/**`, `api/routers/**`, passende `src/services/*.py` | `tests/fixtures/i18n_python_allowlist.json` (Baseline je Datei) | `# i18n-log` | **nicht leer**: 15 Dateien, 47 Funde; `test_allowlist_ist_leer` ist `xfail(strict=True)` (#2751) |
| Go (G5) | `internal/i18n/hardcode_guard_test.go` | `internal/{handler,mail,notify,store,middleware,resolver}` | `internal/i18n/hardcode_allowlist.json` | `// i18n-log` (Zeile oder Funktions-Doc) | leer (`[]`) |

Prüfdaten stehen im Regel-Budget von `gates_und_ratschen.md` (Frontend, Go, Python: 2027-01-28). Am Prüfdatum
gilt: kein nachweisbarer Fang, dann Rückbau.

## 5. Validatoren und E2E

- **Mail-Marker:** `build_mime_message()` setzt in jeder Mail `X-GZ-Lang: de|en` (`src/output/channels/email.py`). Die Sprache des Inhalts steht im Kopf, `en` nur bei englischem Inhalt.
- **Validatoren:** die vier Mail-Validatoren lesen den Kopf über `.claude/hooks/_mail_lang.py` (`mail_lang(msg)`) und bilden ihre Erwartungen aus dem Python-Katalog in dieser Sprache. Details und Schwellen: `docs/reference/mail_validators.md`, Abschnitt „Sprache".
- **Übergangsregel (bis A2 #2681):** Kopf fehlt, dann Prüfung als `de` mit Warnung, Exit unverändert. Nach A2 ist ein fehlender Kopf ein Fehler (`HEADER_PFLICHT`).
- **Zweiter Staging-Nutzer `en`:** vorgesehen als Subadressierung des bestehenden Staging-Postfachs und Registrierung mit `language: "en"`. Im Repo ist davon bisher nur die Playwright-Strecke `frontend/e2e/sprachwechsel.spec.ts` belegt. Das geplante Skript für diesen Nutzer (`staging_e2e_user_en.py`) ist **nicht** im Repo.
- **Nachweis:** `.claude/e2e_verified/<sha>.json` mit `"langs": ["de", "en"]` ist vorgesehen. Im Repo ist das Feld bisher nicht verankert.
- **Telegram:** die Antwortsprache richtet sich nach dem Konto (und nach `telegram_style == "kurzform"` des Ziels, siehe `docs/reference/telegram_format.md`).

## 6. Checkliste: neuer Nutzertext

1. Begriff im Glossar `docs/reference/i18n_glossar.md` nachschlagen; fehlt er, dort zuerst ergänzen.
2. Schlüssel nach Abschnitt 2 wählen und in `de` **und** `en` im passenden Bereich anlegen. Platzhalter identisch.
3. Im Code nur `t(...)`, `tn(...)`, `tr(...)`, `$t`, `T(...)` verwenden. Kein Literal mit Umlaut oder Signalwort außerhalb des Katalogs. Logzeilen mit `# i18n-log` bzw. `// i18n-log` markieren.
4. Keine Protokoll-Token übersetzen (`sms_code`, `compact_label`, `col_label`, Kürzel).
5. Paritätstest und die betroffene Ratsche laufen lassen. Bei einem Mail-Text: Validator und beide Sprachen in den Umfang nehmen.
6. Deutsche Golden-Ausgabe muss byte-gleich bleiben.
