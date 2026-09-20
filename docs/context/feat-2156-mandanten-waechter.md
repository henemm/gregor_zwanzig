# Context: feat-2156-mandanten-waechter

Issue: #2156 (Epic #2138, Stufe „Hoch") — „Wächter gegen Handler ohne `WithUser` — ADR-0003
wird nur durch Review-Disziplin getragen". Phase 1, Stand 2026-09-20, alles gegen den
Arbeitsstand `3c14e6e7` gemessen.

## Request Summary

Die Mandantentrennung (ADR-0003) wird heute an der entscheidenden Stelle nicht maschinell
geprüft: Es gibt keinen Wächter, der meldet, wenn ein Handler Nutzerdaten anfasst, ohne die
Nutzerkennung aus dem Auth-Kontext zu binden. Diese Arbeit schließt die Lücke strukturell —
Go-Seite (`internal/handler`) und Python-Pendant (`api/routers`), samt Eintrag in
`docs/reference/gates_und_ratschen.md` mit Prüfdatum (Regel-Budget).

## Ticket-Befund nachgemessen (Stand hält)

| Behauptung im Ticket | Messung | Ergebnis |
|---|---|---|
| `ssgScan` prüft nur die Zuweisungsform | `internal/handler/store_scope_guard_test.go:1-21,246` — Fund ist ausschließlich `ast.AssignStmt` mit `=` auf einen äußeren Parameter innerhalb einer Closure (Race-Klasse #1396) | ✅ bestätigt: ein Handler, der `WithUser` NIE aufruft, ist grün |
| `user_scoped_test.go` deckt 4 von >100 Handlern ab | genau 4 `func Test…` (`:28,:68,:101,:135`), 96 Handler-Funktionen im Paket | ✅ bestätigt |
| `gates_und_ratschen.md` führt keine Mandantentrennungs-Ratsche | einziger Treffer `:163` ist ein Nebensatz über Test-Splits | ✅ bestätigt |
| kein Commit auf den Wächter-Dateien seit dem Befund (06.09.) | `git log --since=2026-09-05 --` leer | ✅ Befund nicht überholt |

## 🔴 Was das Ticket NICHT sagt — der Store ist seit #2151 fail-closed

Der entscheidende Befund dieser Phase, er verschiebt Risiko und Zuschnitt:

- `internal/store/store.go:26-33` — der Basis-Store trägt seit **#2151 Scheibe B** eine
  **leere** Kennung (kein Config-Default `"default"` mehr, `internal/config/config.go:31`,
  bestätigt in `docs/reference/operations_playbook.md:158`).
- `internal/store/pathsafe.go:66-71` — `requireUser()` verweigert jeden Dateizugriff mit
  `ErrInvalidUserID`, wenn die Kennung ungültig/leer ist. 27 Store-Methoden rufen es auf.
  ⚠️ **Durch Phase 2 überholt: es sind 25** — die Zahl trägt die Mindestzahl-Assertion, siehe unten.

**Folge:** Ein heute vergessenes `WithUser` führt zu einem **Laufzeitfehler**, nicht zu einem
stillen Fremdzugriff. Der Wächter ist damit **Härtung/Regressionsschutz**, kein akuter
Datenleck-Fix. Restgefahr, die er bewacht: (a) eine künftige Store-Methode ohne
`requireUser()`, (b) ein Betrieb mit gesetzter `GZ_USER_ID` (dann trägt der Basis-Store eine
echte Kennung und ein vergessenes `WithUser` liest still dieses Konto), (c) Rückbau von
#2151 B. Ob `GZ_USER_ID` im Produktivbetrieb gesetzt ist, war aus dieser Sitzung **nicht
messbar** (`/var/lib/gregor` für `hem` nicht lesbar) — `NOT_MEASURABLE`, blockiert nichts:
der Wert des Wächters hängt nicht davon ab.

## 🔴 Zwei Store-Familien — die Regel aus dem Ticket passt nur auf eine

Eine naive Umsetzung der Ticket-Formulierung („jede Funktion, die `*store.Store` nimmt und
eine Store-Methode aufruft") meldet **32 Funktionen**, von denen **keine einzige** eine echte
Lücke ist.

| Familie | Methoden (Auswahl) | Braucht `WithUser`? |
|---|---|---|
| **Implizit-Scope** — Pfad aus `s.UserID`, intern über `requireUser()` abgesichert | `LoadTrips/LoadTrip/SaveTrip/DeleteTrip`, `LoadLocations/…`, `Load/Save/DeleteComparePreset(s)`, `Load/SaveMetricPresets`, `LoadGroups/SaveGroup/DeleteGroup`, `Load/SaveBriefing`, `BriefingFingerprint`, `LoadBriefingLog/LoadAlertLog`, `BriefingCountByTrip`, `AlertCountByEntity` | **ja** — hier wirkt der Wächter |
| **Explizit-ID** — Kennung als Parameter (`internal/store/user.go`, `sessions.go`) | `LoadUser/SaveUser/DeleteUser/UserExists/ExportUser`, `Save/LoadLinkCode`, `Add/Remove/ClearSessions`, `Save/Load/DeleteVerificationToken`, `ResolveAddressOwner`, `FindUserByOAuthSub`, `FindUserByTelegramChatID`, `IsAddressTakenByOtherAccount`, `ProvisionUserDirs`, `CountAddressCollisions` | **nein** — `WithUser` hat keine Wirkung |

Die 32 Treffer liegen **alle** in der Explizit-ID-Familie: Registrierung, Login, Magic-Link,
OAuth, Passkey, Telegram-/Premium-SMS-Verknüpfung, Datenexport. Mehrere davon sind
**strukturell nie** über `WithUser` lösbar (Adress-/Sub-/ChatID-Lookup findet erst die
Identität) oder bewusst kontoübergreifend hinter `requireLocalOnly`
(`premium_sms_connect.go:54` iteriert absichtlich alle Konten).

⚠️ **Durch Phase 2 entschieden (Positivliste, gemessen trennscharf) — keine offene Frage mehr.**

**Designfrage für die Spec (nicht in `/50-implement` entscheiden):** Positivliste der
Implizit-Scope-Methoden als Auslöser (startet bei 0 Treffern, keine 32 Ausnahme-Marker am
ersten Tag) **vs.** breite Regel plus Ausnahmeliste (Wartungslast, Regel-Budget-Erosion).
Vorzeichnung aus der Recherche: Positivliste, mit `requireUser()`-Nutzung in
`internal/store/` als Quelle der Wahrheit und einem Gegentest, der Liste und Code
auseinanderlaufen lässt (sonst ist die Liste selbst die stille Lücke).

## Korrekte Bindung im Bestand

Kein Wrapper und keine Middleware liefert einen vorgebundenen Store — jeder Handler bindet
selbst pro Anfrage, meist in eine **neue** Variable
(`us := s.WithUser(middleware.UserIDFromContext(r.Context()))`, z.B. `archive_stats.go:18`).
Eine Textsuche nach `s.WithUser(` würde das übersehen; der AST-Weg (wie `ssgScan`) nicht.
Handler reichen `s` außerdem an Helfer mit eigenem `*store.Store`-Parameter weiter
(`resolveMagicLinkAccount`, `resolvePremiumSmsTarget`) — eine Funktion isoliert zu beurteilen
erzeugt dort Fehlalarme.
⚠️ **Durch Phase 2 entkräftet:** alle **13** solchen Helfer nutzen ausschließlich die
Explizit-ID-Familie; **0** rufen eine Implizit-Scope-Methode. Die per-Funktion-Regel ist
fehlalarmfrei.

## Python-Seite (`api/routers/`)

- Von 28 gefundenen Endpunkten tragen alle nutzerbezogenen `user_id: str = Query(...)` —
  **außer** `api/routers/scheduler.py:97` (`/radar-alert-checks`) und `:107`
  (`/compare-radar-alert-checks`), die `user_id: str` ohne `Query(...)` deklarieren.
  Wirkung ist in FastAPI dieselbe (einfacher Typ ⇒ Pflicht-Query), die **Form** weicht ab.
  ⇒ Der Wächter muss die **Wirkung** prüfen (Pflichtparameter, kein Default), nicht die
  Schreibweise — sonst meldet er zwei Fehlalarme oder erzwingt kosmetische Änderungen.
- Zentrale Validierung: `get_data_dir(user_id)` in `src/app/loader.py:1169` (wirft bei
  ungültiger Kennung, #1364).
- Bestehend: `tests/test_user_id_default_guard.py` — AST-Wächter gegen `user_id="default"`
  in `api/` und `src/`, Ratsche `_SRC_BESTAND` ist **leer**, keine Marker-Syntax. Gemessener
  Lauf am 20.09.: **8 Tests grün**. Er prüft Defaults, **nicht** die Existenz eines
  Pflichtparameters — das ist die offene Flanke für #2156.
- `tests/test_scheduler_router_requires_user_id.py` prüft Verhalten (422 ohne `user_id`) für
  drei Endpunkte, ohne Ratsche.

## Bauprinzip bestehender Wächter (Vorbilder)

- **Go:** `internal/handler/store_scope_guard_test.go` — `go/parser`+`go/ast`, Marker
  `gz-closure-param-write:` mit ≥15 sinnvollen Zeichen Begründung, Selbstschutz
  `ssgMindestDateien = 50` gegen „Pfad verloren ⇒ still grün", Fixtures als
  String-Konstanten (sonst scannt der Test sich selbst). Läuft im CI-Check `go-test`.
- **Python:** `tests/test_user_id_default_guard.py`, `tests/test_output_timezone_guard.py`
  (Marker + `KNOWN_VIOLATIONS`), `tests/tdd/test_thunder_scale_local_copy_guard.py`
  (3-stufige Duldung). Marker-Konvention `# gz-<thema>: <≥15 Zeichen>`. Läuft im CI-Check
  `test`.
- **Doku:** Abschnitt in `docs/reference/gates_und_ratschen.md` + Zeile in der Tabelle
  „Regel-Budget: Prüfdaten im Überblick" (Prüfdatum +90 Tage ⇒ **2026-12-20**; Vorbildzeile:
  „`user_id="default"`-Wächter … | 2026-12-18 | —").

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/handler/store_scope_guard_test.go` | bestehender Go-Wächter — erweitern oder Vorbild für einen zweiten |
| `internal/handler/user_scoped_test.go` | 4 Zwei-Nutzer-Verhaltenstests (alice/bob) als Muster |
| `internal/store/pathsafe.go`, `internal/store/store.go` | `requireUser()`, `WithUser`, Fail-closed-Verhalten |
| `internal/store/user.go`, `internal/store/sessions.go` | Explizit-ID-Familie (Abgrenzung) |
| `api/routers/scheduler.py` | die zwei abweichenden Signaturen |
| `tests/test_user_id_default_guard.py` | Python-Wächter-Vorbild + Ratschen-Mechanik |
| `docs/reference/gates_und_ratschen.md` | Eintrag + Regel-Budget-Tabelle |
| `docs/adr/0003-multi-tenant-isolation.md` | die zu bewachende Zusicherung |

## Existing Specs

- `docs/specs/modules/fix_1396_s2_store_scope_guard.md` — Vorlage (Aufbau, AC-Schnitt,
  LoC-Override auf 500 wegen Scan-Kern)
- `docs/specs/modules/fix_2151_default_fallbacks_scheibe_a/b/c.md` — Python-/Go-Ratschen
- `docs/specs/modules/user_scoped_store.md`, `docs/specs/modules/thunder_scale_guard.md`

## Risks & Considerations

1. **Fehlalarm-Risiko** (Hauptrisiko): breite Regel ⇒ 32 Treffer am ersten Tag ⇒ `main` rot
   ⇒ Drive-to-green verdrängt alles andere. Zuschnitt muss das in der Spec lösen.
2. **Vakuum-Grün** (schärfste Falle): Eine Positivliste, die niemand pflegt, macht den Wächter
   still wirkungslos. Konkreter Ausfallmodus: **eine neue Store-Methode, die `requireUser()`
   ruft, aber nicht in der Liste steht, ist für den Wächter für immer unsichtbar.** Die Liste
   muss daher zur Testzeit **abgeleitet** und gegen die gemessene Menge der
   `requireUser()`-Aufrufstellen in `internal/store/*.go` (heute 27) geprüft werden —
   Abweichung ⇒ rot. Das ist eine eigene AC, nicht ein Nebensatz; sie hält den Wächter nach
   dem Ticket-Schluss am Leben (Lehre #2151 C).
3. **Regel-Budget**: neue Pflichtprüfung braucht entweder eine Ablösung oder Prüfdatum
   2026-12-20. **Zu entscheiden in Phase 2 (mit Empfehlung, nicht als offene Frage):**
   erweitern vs. zweiter Wächter. Sachlage: `ssgScan` läuft je `FuncDecl`/`FuncLit` und sucht
   *Zuweisungen an äußere Parameter*; die neue Regel braucht eine andere Traversierung
   (*ging einem Aufruf aus der Implizit-Scope-Menge irgendein `WithUser` voraus?*) und einen
   anderen Befund-Typ. Gleiche Datei und gleiche AST-Technik heißt nicht gleiche Prüfung —
   der Regel-Budget-Druck darf nicht in ein schlechteres Design zwingen.
4. **Mutations-Gegenprobe**: Der Wächter muss dort messen, wo die Zusicherung wirkt —
   ein Testfixture, dem `WithUser` fehlt, muss rot werden.
5. **LoC**: bestehender Wächter ~700 Zeilen; Go-Teil + Python-Teil + Doku sprengen das
   250er-Limit ⇒ `loc_limit_override 500` einplanen, RED trotzdem über **alle** ACs.
6. **Nebenbefund** (nicht Teil dieser Arbeit): `scheduler.py:97/107` Signaturform —
   Sammel-Issue #1199, sofern nicht ohnehin vom Wächter miterledigt.

---

# Analysis (Phase 2, 2026-09-20)

## Type

**Feature** (Härtung/Regressionsschutz). Kein akuter Defekt: Beide Flächen sind heute
sauber — der Wächter friert den erreichten Zustand ein.

## Messungen dieser Phase (alle gegen `3c14e6e7`, je zweifach belegt)

| Messung | Ergebnis | Bedeutung für den Zuschnitt |
|---|---|---|
| Store-Methoden, die `requireUser()` rufen | **25**, **alle** aus der Implizit-Scope-Familie; `user.go`/`sessions.go` rufen es **0×** | Die Ableitung „Auslöserliste = Methoden mit `requireUser()`" ist **trennscharf** (Explizit-ID kommt nicht herein), aber **nicht vollständig** — siehe Abschnitt zur Lückenhaftigkeit. Positivlisten-Frage aus Phase 1 **entschieden**. |
| Go-Handler-Funktionen mit Implizit-Scope-Aufruf | **37**, davon **37 mit** `WithUser` im selben Körper | **Tag-1-Treffer = 0** — kein Ausnahme-Marker am ersten Tag, kein rotes `main`. |
| dito, aufrufstellen-genau und reihenfolgebewusst (2. Messweg) | **92 Aufrufstellen, 92 gebunden** | Unabhängige Bestätigung; liefert zugleich die richtige Prüfmechanik (s.u.). |
| Hilfsfunktionen mit `*store.Store`-Parameter | **13** (auth/oauth/magic/premium-sms), **keine** ruft eine Implizit-Scope-Methode | Die **per-Funktion**-Regel ist fehlalarmfrei; interprozeduraler Fluss ist heute nicht nötig. |
| Python-Endpunkte in `api/routers/` | **36**, davon **22 mit** `user_id` | — |
| `user_id`-Pflichtigkeit per **Wirkungs**prüfung | **22 Pflicht, 0 Befunde** | Auch die Python-Regel startet bei null. |
| dito per **Form**prüfung (`Query(...)` als Text) | **5 Fehlalarme**, 2 wirkungsgleiche Fälle übersehen | Belegt die Phase-1-Forderung: Wirkung prüfen, nicht Schreibweise. |
| `get_data_dir(user_id)` gegen leere Kennung | **wirft** (`^[a-zA-Z0-9_-]+$`, `loader.py:1154/1181`, #1364) | Python ist zur **Laufzeit bereits fail-closed** — s. „Verworfene Alternative". |

### Zwei Korrekturen an Zwischenmeldungen (beide am Quelltext geprüft)

- `applyComparePresetPatch`, `validateLocation`, `validateTrip` sind **keine** Store-Nutzer:
  sie nehmen keinen `*store.Store` entgegen (`compare_preset.go:292`, `location.go:45`,
  `trip.go:111`); die Store-Methoden stehen dort nur in **Kommentaren**. Eine Textsuche zählt
  sie mit (39 statt 37) — **der AST nicht**.
- Zwei Python-Endpunkte schienen `user_id` ohne Parameter zu nutzen
  (`compare.py:12`, `validator.py:541`) — das Wort steht nur im **Docstring**.

⇒ Verallgemeinerung, die in die Spec gehört: **Jede Textsuche erzeugt hier Geistertreffer aus
Kommentaren und Docstrings.** Auch die *Ableitung* der Auslöserliste muss über den AST laufen,
sonst zieht schon der Kommentar in `internal/store/store.go:25` einen Phantom-Eintrag nach.

## Technischer Ansatz

### Go — Provenance-Lauf je Funktion (neuer, eigenständiger Wächter)

Ein Vorwärtslauf über den Funktionskörper führt eine Menge „scoped" Bezeichner:
Eine `:=`/`=`-Bindung, deren rechte Seite ein `CallExpr` mit Selektor `.WithUser(...)` auf
einem Store-Ausdruck ist, markiert ihr Ziel als scoped. Ein `CallExpr` mit Selektor aus der
Auslösermenge auf einem zu diesem Zeitpunkt **nicht** scoped markierten Bezeichner ist ein Fund.

- **Reihenfolge ist Teil der Zusicherung:** „`WithUser` steht irgendwo im Körper" genügt
  nicht — ein `s.LoadTrips()` **vor** der Bindung muss rot werden.
- **Kein Namens-Whitelisting** (`s.WithUser(` als Text): der Bestand nutzt sowohl
  Schattierung `s := s.WithUser(...)` als auch `us := s.WithUser(...)`.
- **Bewusste, zu dokumentierende Grenzen:** kein interprozeduraler Fluss (heute 0 Fälle),
  keine Zweig-Analyse (Bindung im einen, Nutzung im anderen Zweig).

### Python — AST-Wächter auf die Signatur-Wirkung

- **Auslöser:** Endpunkt-Funktion in `api/routers/` (Dekorator `@router.get/post/...`), die
  einen `user_id`-Parameter deklariert → **22 Endpunkte**.
- **Regel:** `user_id` muss Pflichtparameter sein — entweder ohne Default oder mit
  `Query(...)`, wobei das **erste Positional-Argument `Ellipsis`** sein muss (beliebige
  weitere kwargs wie `description=` sind unschädlich).
- Das deckt `scheduler.py:97/107` (`user_id: str` ohne `Query`) korrekt als **erfüllt** ab,
  statt kosmetische Änderungen zu erzwingen.

**Verworfene Alternative (mit Begründung):** Auslöser „Endpunkt ruft einen Loader" ist
**Vakuum-Grün** — nur **1 von 36** Endpunkten ruft `get_data_dir`/`load_*` direkt, der Rest
geht über Service-Funktionen. Ebenfalls verworfen: ein zusätzlicher Laufzeit-Guard im Loader —
`get_data_dir()` lehnt ungültige und leere Kennungen **seit #1364 bereits ab**; das wäre eine
Doppelung ohne Zugewinn.

### Selbstschutz der Ableitung (eigene AC, kein Nebensatz)

Die Auslösermenge wird zur Testzeit per `go/ast` aus `internal/store/*.go` (ohne `_test.go`)
abgeleitet: `FuncDecl` mit Receiver `*Store`, deren Körper strukturell `s.requireUser()`
aufruft. Dreifacher Schutz gegen stilles Leerlaufen (Lehre #2151 C):

1. **Mindestzahl-Assertion** — heute 25 Methoden; Unterschreiten ⇒ rot (Vorbild `ssgMindestDateien`).
2. **Fest kodierte Stichprobe** — `LoadTrip`, `SaveTrip`, `LoadLocations`, `LoadComparePresets`
   u.a. **müssen** in der Ableitung enthalten sein; bricht der Parser-Pfad, schlägt das laut fehl
   statt still leer zu werden.
3. **Mindestzahl gescannter Handler-Dateien** — Schutz gegen „Pfad verloren ⇒ still grün".

### 🔴 Die Ableitung allein ist LÜCKENHAFT — nachgemessen, nicht hypothetisch

`requireUser()` als alleinige Quelle verfehlt nutzergebundene Methoden, die Pfad bzw.
Schlüssel direkt aus `s.UserID` bauen. Gemessen (exportierte `*Store`-Methoden mit `s.UserID`
und **ohne** `requireUser()`):

| Methode | Nutzt `s.UserID` für | Aus `internal/handler/` gerufen? |
|---|---|---|
| `LockBriefing` (`briefing_lock.go:30`) | Sperrschlüssel aus UserID + NUL + id | **JA — 16×** (trip.go, compare_preset.go, briefing_subscription.go, weather_config.go) |
| `LocationsDir` (`location.go:14`) | Verzeichnispfad | nein (nur store-intern) |
| `PresetsFile` (`metric_preset.go:14`) | Dateipfad | nein (nur store-intern) |

*(`briefingsDir`, `groupsFile`, `saveGroups` sind unexportiert, aus `internal/handler/` nicht
erreichbar.)*

**Heute kein Defekt:** Alle 16 `LockBriefing`-Aufrufe folgen nachweislich auf eine
`WithUser`-Bindung. **Aber:** Eine nur aus `requireUser()` abgeleitete Auslösermenge enthält
`LockBriefing` **nicht** — ein künftiger Handler, der vor der Bindung sperrt, wäre für den
Wächter unsichtbar. Folge wäre eine kontoübergreifend geteilte Sperre, also falsche
Sperrgranularität.

**⇒ Zwingend für die Spec (eigene AC):** Auslösermenge =
**`requireUser()`-Ableitung ∪ benannte Ergänzungen**; `LockBriefing` ist heute die einzige
nötige Ergänzung. Abgesichert durch eine **Vollständigkeits-Gegenprobe**: Der Wächter
ermittelt alle **exportierten** `*Store`-Methoden, die `s.UserID` verwenden, und verlangt,
dass jede entweder in der Auslösermenge steht **oder** in einer begründeten, im Test
kodierten Ausnahmeliste (heute `LocationsDir`, `PresetsFile` — store-intern). Taucht eine
neue auf, wird der Wächter rot, statt still unvollständig zu bleiben.

**Verbleibende prinzipbedingte Grenze:** Eine künftige Store-Methode, die nutzergebundene
Pfade baut, ohne `requireUser()` **und** ohne `s.UserID` (etwa über einen Helfer), bleibt
unsichtbar — Scope-*Design*-Fehler, andere Regel, Folge-Ticket optional.

## Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `internal/handler/store_scope_call_guard_test.go` | **CREATE** | Go-Wächter: Provenance-Lauf + AST-Ableitung (inkl. `LockBriefing`-Ergänzung) + Vollständigkeits-Gegenprobe + Selbstschutz + Fixtures als String-Konstanten |
| `tests/test_router_user_id_required.py` | **CREATE** | Python-Wächter: Pflichtparameter-Wirkung je Endpunkt mit `user_id` |
| `docs/reference/gates_und_ratschen.md` | **MODIFY** | Abschnitt + Zeile in „Regel-Budget: Prüfdaten im Überblick", Prüfdatum **2026-12-20** |

`store_scope_guard_test.go` wird **nicht** angefasst (Begründung unten). Kein Produktivcode.

## Scope Assessment

- Dateien: 2 CREATE, 1 MODIFY (Doku zählt nicht aufs LoC-Limit)
- Geschätzte LoC: Go ~200–250, Python ~70–90 ⇒ **> 250**
- ⇒ **`workflow.py set-field loc_limit_override 500` einplanen**; RED trotzdem über **alle** ACs
- Risiko: **NIEDRIG**

**Risiko-Begründung:** Es entsteht ausschließlich Testcode und Doku — kein Produktivpfad, kein
Staging-Verhalten, kein Deploy-Risiko. Beide Regeln starten gemessen bei **0 Treffern**, das
`main`-Rot-Risiko ist damit ausgeschlossen. Das verbleibende Risiko ist ein *unwirksamer*
Wächter — dagegen stehen der dreifache Selbstschutz und die Mutations-Gegenprobe.

## Entscheidungen (technisch, in Phase 2 getroffen — keine PO-Fragen)

1. **Zweiter eigenständiger Wächter statt `ssgScan` erweitern.** `ssgScan` bewacht
   Schreibzugriffe auf äußere Closure-Parameter (Race-Klasse #1396) — anderer Befundtyp,
   andere Traversierung, andere Fixtures. Gleiche AST-Technik heißt nicht gleiche Prüfung.
   Das Repo lebt „ein Wächter, ein Befundtyp" bereits (`test_user_id_default_guard.py`,
   `test_output_timezone_guard.py`). Regel-Budget wird über das Prüfdatum 2026-12-20 bedient,
   nicht über eine erzwungene Verschmelzung.
2. **Dateinamen nach Verhalten**, nicht nach Issue-Nummer.
3. **Eine Lieferung statt drei Scheiben.** Beide Teile sind reine Test-/Doku-Artefakte ohne
   Produktivcode; ein Scheibenschnitt erzeugte drei PRs, drei Staging-Runden und drei
   Prüfdatum-Einträge für **eine** Regel. Das LoC-Limit wird per Override bedient — dafür ist
   es da. (Gegenposition der Strategie-Bewertung: getrennt liefern, damit ein Scheitern des
   Go-Teils den Python-Teil nicht blockiert. Verworfen, weil der Go-Teil gemessen unkritisch
   ist: klares Bindungsmuster, 0 Treffer, 13 Hilfsfunktionen sauber abgegrenzt.)
4. **Mutations-Gegenprobe je Regel** (Pflicht): ein Fixture-Handler ohne `WithUser` und eines
   mit `WithUser` **nach** dem Store-Aufruf müssen den Go-Wächter rot machen; ein Fixture-
   Endpunkt mit `user_id: str = "default"` bzw. `Query("x")` den Python-Wächter. Zusätzlich
   die **Rückdreh-Gegenprobe** auf die Ableitung: Auslösermenge künstlich leeren ⇒ der
   Selbstschutz muss rot werden (sonst ist der Wächter vakuum-grün).

## Dependencies

- `internal/store/pathsafe.go:66` (`requireUser`) ist die **Quelle der Wahrheit** der Ableitung —
  ändert sich dort die Absicherung, ändert sich die Auslösermenge automatisch mit.
- CI: Go-Teil läuft im Check `go-test`, Python-Teil im Check `test`.
- #2151 Scheibe B (fail-closed Store) und #1364 (`get_data_dir`-Validierung) sind die
  Laufzeit-Absicherungen, die dieser Wächter statisch flankiert.

## Open Questions

Keine. Beide Designfragen aus Phase 1 (Positivliste vs. breite Regel; erweitern vs. zweiter
Wächter) sind durch die Messungen oben entschieden und unter „Entscheidungen" begründet.

## Nebenbefund (nicht Teil dieser Arbeit)

`api/routers/scheduler.py:97/107` deklarieren `user_id: str` ohne `Query(...)` — wirkungsgleich
Pflicht, nur uneinheitlich geschrieben. Vom Wächter korrekt als erfüllt gewertet. Kosmetik ⇒
Sammel-Issue **#1199**, kein eigenes Ticket.
