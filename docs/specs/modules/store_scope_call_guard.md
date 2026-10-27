---
entity_id: store_scope_call_guard
type: module
created: 2026-09-20
updated: 2026-09-20
status: draft
version: "2.0"
tags: [go-api, python-core, multi-user, tenant-isolation, ratchet, regression-guard, issue-2156, marker-convention]
---

<!-- Issue #2156 (Epic #2138) — Wächter gegen Handler, die eine
     nutzergebundene Store-Methode ohne vorherige `WithUser`-Bindung
     aufrufen. ADR-0003 wird heute nur durch Review-Disziplin getragen,
     nicht maschinell geprüft. v2.0: PO-Entscheid — Ausnahmen stehen als
     begründete Marker im Quelltext statt als stille Positivliste im
     Testcode. -->

# Store-Scope-Call-Guard — Wächter gegen Handler ohne `WithUser` (#2156)

## Approval

- [ ] Approved

## Purpose

ADR-0003 (Mandantentrennung) verlangt, dass jeder nutzerbezogene Zugriff
die echte Nutzerkennung aus dem Auth-Kontext bindet — Go über
`s.WithUser(middleware.UserIDFromContext(r.Context()))`, Python über den
`user_id`-Parameter. Heute prüft das ausschließlich Review-Disziplin: Es
gibt keinen Test, der meldet, wenn ein Handler eine nutzergebundene
Store-Methode aufruft, ohne den Store zuvor per `WithUser` gebunden zu
haben, oder wenn ein FastAPI-Endpunkt einen `user_id`-Parameter mit
Default führt. Diese Lieferung baut zwei neue, eigenständige Wächter —
einen Go-Test in `internal/handler/`, einen Python-Test in `tests/` —
die genau das strukturell erzwingen, plus den zugehörigen Doku-Eintrag
mit Prüfdatum.

**Härtung, kein akuter Datenleck-Fix.** Der Store ist seit #2151 Scheibe B
fail-closed: `internal/store/store.go` trägt seit dem Basis-Store keine
Default-Kennung mehr, und `requireUser()`
(`internal/store/pathsafe.go:60-70`) verweigert jeden nutzerbezogenen
Dateizugriff mit `ErrInvalidUserID`, solange die Kennung ungültig/leer
ist. Ein heute vergessenes `WithUser` führt also zu einem
**Laufzeitfehler**, nicht zu einem stillen Fremdzugriff. Der Wächter
bewacht die verbleibende Restgefahr: (a) eine künftige Store-Methode ohne
`requireUser()`-Absicherung, (b) ein Betrieb mit gesetzter `GZ_USER_ID`
(dann trägt der Basis-Store eine echte Kennung, und ein vergessenes
`WithUser` liest still dieses Konto statt abzustürzen), (c) ein Rückbau
von #2151 Scheibe B. Ob `GZ_USER_ID` im Produktivbetrieb gesetzt ist, war
in der Analyse-Phase nicht messbar (`/var/lib/gregor` für `hem` nicht
lesbar) — `NOT_MEASURABLE`, blockiert nichts: Der Wert des Wächters hängt
nicht von dieser Antwort ab.

**v2.0 — Marker statt stiller Positivliste (PO-Entscheid).** v1 dieser
Spec zog die Grenze zwischen nutzergebundenen und explizit-parametrisierten
Store-Methoden über eine im Testcode kodierte Positivliste. Der PO hat
das bei der Freigabe-Rückfrage abgelehnt: „bitte Ausnahmen im Code
markieren" — deckungsgleich mit der Ticket-Forderung, Ausnahmen „nur mit
begründetem Marker" zuzulassen. Diese Fassung ersetzt die Positivliste
durch zwei Marker direkt am Store-Quelltext
(`gz-store-scope-exempt`/`gz-store-scope-required`); jede Abweichung vom
Regelfall steht künftig sichtbar und begründungspflichtig dort, wo sie
wirkt, statt verborgen im Testcode.

## Source

- **File (Go, Test):** `internal/handler/store_scope_call_guard_test.go` (NEU)
- **Identifier (Go):** Modul-Ebene, kein Produktivcode-Symbol — ein
  reihenfolgebewusster Provenance-Lauf per `go/ast` über jede
  `ast.FuncDecl`/`ast.FuncLit` in `internal/handler/*.go`, kombiniert mit
  einer zur Testzeit aus `internal/store/*.go` **und** den Markern
  `gz-store-scope-exempt`/`gz-store-scope-required` abgeleiteten
  Klassifikation.
- **File (Go, Store — nur Marker-Kommentare):** `internal/store/user.go`,
  `internal/store/sessions.go`, `internal/store/address_owner.go`,
  `internal/store/store.go`, `internal/store/briefing_lock.go` (MODIFY —
  je Kommentarzeilen, kein ausführbarer Code)
- **File (Python):** `tests/test_router_user_id_required.py` (NEU)
- **Identifier (Python):** Modul-Ebene — ein `ast`-Wächter über
  `api/routers/*.py`, Auslöser ist jede Endpunkt-Funktion mit
  `@router.get/post/put/delete/...`-Dekorator und `user_id`-Parameter,
  Ausnahme über Marker `gz-user-id-optional`.
- **File (Doku):** `docs/reference/gates_und_ratschen.md` (MODIFY) — neuer
  Abschnitt inklusive Marker-Syntax-Tabelle + Zeile in der Tabelle
  „Regel-Budget: Prüfdaten im Überblick".

> **Schicht-Hinweis (Korrektur gegenüber v1):** Der Go- und Python-
> Wächter selbst sind reine Test-Infrastruktur (`internal/handler/`,
> `tests/`). **Anders als in v1 behauptet wird aber Produktivcode
> berührt:** `internal/store/*.go` bekommt 24 Marker-Kommentarzeilen.
> Kein ausführbarer Code und kein Laufzeitverhalten ändert sich dadurch —
> aber „kein Produktivcode" (v1) stimmt nicht mehr.

## Marker-Konvention (Kern des Zuschnitts, v2.0)

v1 dieser Spec zog die Grenze zwischen den zwei Store-Methodenfamilien
(„Implizit-Scope" vs. „Explizit-ID") über eine **im Testcode kodierte
Positivliste**. Der PO hat das bei der Freigabe-Rückfrage abgelehnt
(„bitte Ausnahmen im Code markieren") — deckungsgleich mit der
Ticket-Forderung, Ausnahmen „nur mit begründetem Marker" zuzulassen.
**v2.0 kodiert deshalb keine Methodennamen mehr im Testcode.** Jede
Abweichung vom Regelfall — sowohl eine Ausnahme als auch eine Ergänzung —
steht als begründeter Marker direkt am Quelltext der betroffenen Methode.
Wer `internal/store/*.go` liest, sieht dort, warum eine Methode keine
`WithUser`-Bindung braucht.

### Zwei Marker an Store-Methoden (`internal/store/*.go`)

Konvention wie im Bestand (`gz-closure-param-write:` in
`store_scope_guard_test.go`, `# gz-<thema>:` in den Python-Wächtern):
Markername, Doppelpunkt, **mindestens 15 Zeichen** sinnvolle Begründung.

| Marker | Bedeutung | Anbringung |
|---|---|---|
| `// gz-store-scope-exempt: <Begründung>` | Methode braucht **keine** `WithUser`-Bindung (nimmt die Kennung als Parameter, oder ist selbst der Bindungsmechanismus) | Kommentarzeile direkt über der Methodendeklaration |
| `// gz-store-scope-required: <Begründung>` | Methode ist nutzergebunden, obwohl sie `requireUser()` **nicht** ruft (baut Pfad/Schlüssel direkt aus `s.UserID`) | Kommentarzeile direkt über der Methodendeklaration |

### Auslösermenge und Ausnahmemenge — beide aus dem Quelltext abgeleitet

- **Auslösermenge** = per `go/ast` abgeleitete Methoden mit
  `s.requireUser()` im Körper **∪** Methoden mit Marker
  `gz-store-scope-required`. `LockBriefing` ist damit **nicht mehr** eine
  im Test kodierte Ergänzung (v1), sondern trägt den Marker im
  Quelltext — das ist der Kern der PO-Entscheidung.
- **Ausnahmemenge** = Methoden mit Marker `gz-store-scope-exempt`.
- Der Wächter verdrahtet **keinen** Methodennamen fest. Einzige fest
  kodierte Namen bleiben die Stichprobe des Selbstschutzes (AC-5) — das
  ist eine Mindest-Assertion, keine Ausnahmeliste.

### Klassifikations-Pflicht (ersetzt die Vollständigkeits-Gegenprobe aus v1)

Jede **exportierte** `*Store`-Methode, die **aus `internal/handler/`
aufgerufen wird**, muss in **genau einer** Klasse liegen: abgeleiteter
Auslöser, `gz-store-scope-required`, oder `gz-store-scope-exempt`. Sonst
rot. Konkret rot machen:

- **unklassifiziert** — aufgerufen, aber weder abgeleitet noch markiert
- **doppelt markiert** — beide Marker an derselben Methode
- **widersprüchlicher Marker** — `gz-store-scope-exempt` an einer
  Methode, die `requireUser()` ruft
- **verwaister Marker** — Marker an einem Namen, den es nicht (mehr) gibt
- **zu kurze Begründung** — weniger als 15 Zeichen nach dem Doppelpunkt

Nicht aus `internal/handler/` erreichbare Methoden **dürfen** einen
Marker tragen, **müssen** aber nicht; ein widersprüchlicher oder
verwaister Marker ist auch dort rot.

### Marker am Aufrufort im Handler (`internal/handler/*.go`)

Für den Fall, dass ein Handler eine Auslöser-Methode bewusst ohne Bindung
ruft (Ticket-Beispiel: `requireLocalOnly`-Endpunkte, kontoübergreifende
Sonderfälle): `// gz-store-scope-call: <Begründung>` (≥15 Zeichen)
unmittelbar über der Aufrufzeile unterdrückt **genau diesen** Fund.
**Heute null solche Marker** — die Mechanik existiert für künftige
Fälle. Ein `gz-store-scope-call`-Marker an einer Aufrufstelle, die
ohnehin korrekt gebunden ist, ist ein **verwaister Marker** und macht den
Wächter **rot** (sonst verrotten Marker zur stillen Ausnahme — genau das,
was der PO gerade abgelehnt hat).

### Python-Seite analog

`# gz-user-id-optional: <Begründung>` (≥15 Zeichen) über einer
Endpunkt-Funktion erlaubt dort ausnahmsweise ein optionales `user_id`.
**Heute null solche Marker.** Ein verwaister Marker (Endpunkt erfüllt die
Regel ohnehin) macht den Wächter rot.

### Gemessene Zahlen (heute, gegen `3c14e6e7`)

| Größe | Wert |
|---|---|
| exportierte `*Store`-Methoden gesamt | **58** |
| davon mit `requireUser()` (abgeleitete Auslöser) | **25** |
| davon aus `internal/handler/` aufgerufen und **nicht** abgeleiteter Auslöser | **23** (darunter `WithUser` selbst) |
| ⇒ zu setzende `gz-store-scope-exempt`-Marker | **23** |
| ⇒ zu setzende `gz-store-scope-required`-Marker | **1** (`LockBriefing`) |
| ⇒ Marker-Kommentarzeilen in `internal/store/*.go` gesamt | **24** |
| `gz-store-scope-call`-Marker heute | **0** |
| `gz-user-id-optional`-Marker heute | **0** |
| Go-Handler-Funktionen mit Auslöser-Aufruf | **37**, alle 37 mit `WithUser` |
| Aufrufstellen / davon gebunden | **92 / 92** |
| Hilfsfunktionen mit `*store.Store`-Parameter | **13**, keine ruft einen Auslöser |
| Python-Endpunkte in `api/routers/` / davon mit `user_id` | **36 / 22**, alle 22 Pflicht, **0 Befunde** |

Die 23 zu markierenden Methoden (`gz-store-scope-exempt`):

- `sessions.go`: `AddSession`, `ClearSessions`, `RemoveSession`
- `user.go`: `DeleteResetToken`, `DeleteUser`, `DeleteVerificationToken`,
  `ExportUser`, `FindUserByOAuthSub`, `FindUserByTelegramChatID`,
  `ListUserIDs`, `LoadLinkCode`, `LoadResetToken`, `LoadUser`,
  `LoadVerificationToken`, `ProvisionUserDirs`, `SaveLinkCode`,
  `SaveResetToken`, `SaveUser`, `SaveVerificationToken`, `UserExists`
- `address_owner.go`: `IsAddressTakenByOtherAccount`, `ResolveAddressOwner`
- `store.go`: `WithUser` (Begründung: *ist* der Bindungsmechanismus)

Und die eine `gz-store-scope-required`-Methode: `LockBriefing`
(`briefing_lock.go`) — baut den Sperrschlüssel direkt aus `s.UserID + NUL
+ id`, ohne `requireUser()` zu rufen; 16 Aufrufstellen aus
`internal/handler/`.

**Beide Regeln starten weiterhin bei 0 Befunden — aber nur, wenn alle 24
Marker in derselben Lieferung gesetzt werden.** Das ist eine eigene AC
(AC-8), kein Nebensatz: ohne die Marker wäre `main` am ersten Tag rot.

## Estimated Scope

- **LoC:** Go-Wächter ~250–300, Python-Wächter ~70–90, 24
  Marker-Kommentarzeilen in `internal/store/*.go` ⇒ zusammen **~350–420**
  (`docs/`-Änderungen zählen nicht aufs Limit). `loc_limit_override 500`
  ist gesetzt und reicht.
- **Files:** 8 (2 CREATE, 6 MODIFY — 5 Store-Dateien mit reinen
  Kommentarzeilen, 1 Doku-Datei)
- **Effort:** medium

**Risiko: NIEDRIG**, aber mit einer wichtigen Korrektur gegenüber v1:
**Produktivdateien werden berührt.** `internal/store/user.go`,
`sessions.go`, `address_owner.go`, `store.go`, `briefing_lock.go`
bekommen je Marker-Kommentarzeilen — **kein ausführbarer Code, kein
geändertes Laufzeitverhalten**, aber eben nicht mehr „kein Produktivcode"
wie in v1 behauptet.

**Deploy-Pfad — Korrektur gegenüber v1.** Die Ausnahme für reine
Doku-/Tooling-Änderungen (nur `.md`/`docs/`/`.claude/`/`.gitignore`, kein
Code in `src/`/`api/`/`internal/`/`frontend/`/`cmd/`) greift **nicht**,
weil `internal/store/*.go` verändert wird. Staging-Validierung
(Schritt 3) und Prod-Deploy (Schritt 4) sind damit wieder Pflicht, obwohl
sich das Verhalten nicht ändert — mindestens ein HTTP-Smoke-Test
(`/`, `/api/health`) gehört dazu.

Beide Regeln starten weiterhin bei **0 Treffern**: siehe die gemessenen
Zahlen oben. Das `main`-Rot-Risiko ist damit ausgeschlossen, **sofern
alle 24 Marker in derselben Lieferung gesetzt werden** (AC-8). Das
verbleibende Risiko ist ein *unwirksamer* Wächter — dagegen stehen der
dreifache Selbstschutz (AC-5), die Klassifikations-Pflicht (AC-3), die
Marker-Hygiene (AC-4) und die Mutations-/Rückdreh-Gegenproben (AC-7).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/pathsafe.go:66` (`requireUser`) | Quelle der Wahrheit | liefert zur Testzeit die Basis-Auslösermenge der Go-Ableitung; ändert sich dort die Absicherung, ändert sich die Auslösermenge automatisch mit |
| `internal/store/briefing_lock.go:30` (`LockBriefing`) | markierte Ergänzung | trägt `// gz-store-scope-required: ...`; nutzt `s.UserID` direkt für den Sperrschlüssel, ohne `requireUser()` zu rufen — ohne den Marker wäre ein künftiger Handler, der vor der Bindung sperrt, für den Wächter unsichtbar |
| `internal/store/user.go`, `internal/store/sessions.go`, `internal/store/address_owner.go`, `internal/store/store.go` | markierte Ausnahmen | 23 Methoden tragen `// gz-store-scope-exempt: ...` — Kennung kommt als Parameter, oder die Methode ist selbst der Bindungsmechanismus (`WithUser`) |
| `internal/handler/store_scope_guard_test.go` | Abgrenzung, kein Ziel dieser Arbeit | eigenständiger, bestehender Wächter gegen einen anderen Befundtyp (Schreibzugriffe auf geteilte Closure-Parameter, Race-Klasse #1396); liefert die Marker-Bauform (`gz-closure-param-write:`) als Vorbild — wird von dieser Lieferung nicht angefasst |
| `internal/handler/user_scoped_test.go` | Bauform-Vorbild | 4 Zwei-Nutzer-Verhaltenstests (alice/bob) als Muster für Fixture-Zuschnitt |
| `src/app/loader.py:1169` (`get_data_dir`) | Laufzeit-Absicherung (Python, flankiert) | wirft bei ungültiger/leerer Kennung (#1364) — Python ist bereits fail-closed, dieser Wächter prüft zusätzlich die *Signatur* |
| `tests/test_user_id_default_guard.py` | Bauform-Vorbild (Python) | AST-Wächter-Vorbild gegen `user_id="default"` und Marker-Konvention `# gz-<thema>:` |
| #2151 Scheibe B (fail-closed Store) | Laufzeit-Absicherung (Go, flankiert) | Basis-Store trägt seit dieser Scheibe keine Default-Kennung mehr; dieser Wächter sichert dieselbe Zusicherung statisch ab |
| CI-Check `go-test` | Zielsystem | führt den Go-Wächter aus |
| CI-Check `test` | Zielsystem | führt den Python-Wächter aus |

## Implementation Details

### Go — reihenfolgebewusster Provenance-Lauf

Ein Vorwärtslauf über jeden Funktionskörper in `internal/handler/*.go`
führt eine Menge „scoped" Bezeichner: Eine `:=`- oder `=`-Bindung, deren
rechte Seite ein `CallExpr` mit Selektor `.WithUser(...)` auf einem
Store-Ausdruck ist, markiert ihr Ziel als scoped (`s := s.WithUser(...)`
**und** `us := s.WithUser(...)` zählen gleichermaßen — kein
Namens-Whitelisting). Ein `CallExpr` mit Selektor aus der Auslösermenge
(siehe „Marker-Konvention" oben) auf einem zu diesem Zeitpunkt **nicht**
scoped markierten Bezeichner ist ein Fund. Die Reihenfolge ist Teil der
Zusicherung: „`WithUser` steht irgendwo im Körper" genügt nicht — ein
`s.LoadTrips()` **vor** der Bindung muss rot werden (AC-1).

**Auslösermenge und Klassifikation:** siehe „Marker-Konvention" oben —
`requireUser()`-Ableitung ∪ `gz-store-scope-required`-markierte
Methoden; Ausnahmemenge = `gz-store-scope-exempt`-markierte Methoden;
Klassifikations-Pflicht (AC-3) und Marker-Hygiene (AC-4) sind eigene
Prüfungen, die zusätzlich zum Provenance-Lauf über den AST von
`internal/store/*.go` laufen. Kein Textsuche-Weg für die Ableitung —
Kommentare/Docstrings erzeugen Geistertreffer (gemessen: ein
`requireUser()`-Kommentar in `internal/store/store.go` hätte einen
Phantom-Eintrag nachgezogen).

**Dreifacher Selbstschutz (AC-5):**
1. Mindestzahl-Assertion: die `requireUser()`-Ableitung muss **>= 25**
   Methoden liefern, sonst rot (Vorbild `ssgMindestDateien` in
   `store_scope_guard_test.go`).
2. Fest kodierte Stichprobe: `LoadTrip`, `SaveTrip`, `LoadLocations`,
   `LoadComparePresets` müssen in der Ableitung enthalten sein.
3. Mindestzahl gescannter Handler-Dateien.

**Bewusste Grenzen:** kein interprozeduraler Fluss (heute 0 Fälle — alle
13 Hilfsfunktionen mit `*store.Store`-Parameter nutzen ausschließlich
`gz-store-scope-exempt`-markierte Methoden), keine Zweig-Analyse
(Bindung im einen, Nutzung im anderen Zweig). Details unter „Known
Limitations".

**Fixtures als String-Konstanten.** Der Wächter scannt alle `*.go` in
`internal/handler/`, `_test.go` eingeschlossen. Lägen die Fixtures dort
als echte Go-Dateien, meldete der Wächter sich selbst rot — sie gehören
deshalb als String-Konstanten in die Testdatei (Vorbild:
`internal/handler/store_scope_guard_test.go`).

### Python — AST-Wächter auf die Signatur-Wirkung

Auslöser: Endpunkt-Funktion in `api/routers/` mit Dekorator
`@router.get/post/put/delete/...` und einem `user_id`-Parameter (22
Stück). Regel: `user_id` muss Pflichtparameter sein — entweder **ohne
Default** oder mit `Query(...)`, dessen **erstes Positional-Argument
`Ellipsis`** ist (weitere kwargs wie `description=` sind unschädlich),
**oder** die Endpunkt-Funktion trägt den Marker
`# gz-user-id-optional: <Begründung>` (siehe „Marker-Konvention"). Damit
gelten `api/routers/scheduler.py:97` und `:107` (`user_id: str` ohne
`Query`) korrekt als **erfüllt** — eine reine Formprüfung (`Query(...)`
als Text) erzeugte in der Analyse **5 Fehlalarme** und übersah **2**
wirkungsgleiche Fälle.

### Mutations- und Rückdreh-Gegenproben (AC-7, Pflicht)

- Go: ein Fixture-Handler **ohne** `WithUser` und einer mit `WithUser`
  **nach** dem Store-Aufruf müssen den Wächter rot machen.
- Python: ein Fixture-Endpunkt mit `user_id: str = "default"` bzw.
  `Query("x")` muss den Wächter rot machen.
- **Neu (Marker-Hygiene):** ein entfernter `gz-store-scope-exempt`/
  `gz-store-scope-required`-Marker macht die Klassifikations-Pflicht
  rot; eine auf unter 15 Zeichen gekürzte Begründung macht die
  Marker-Hygiene rot.
- Rückdreh: wird die Auslösermenge künstlich geleert (in einer
  Testvariante, nicht am Produktivcode), muss der **Selbstschutz**
  (Mindestzahl-Assertion) rot werden — sonst ist der Wächter
  vakuum-grün (Lehre #2151 C).

Alle Fixtures liegen als String-Konstanten im jeweiligen Test (sonst
scannt der Test sich selbst — Vorbild `store_scope_guard_test.go`).

## Expected Behavior

- **Input (Go):** der Inhalt aller `*.go`-Dateien unter
  `internal/handler/` sowie `internal/store/*.go` (ohne `_test.go`,
  inklusive der 24 Marker-Kommentarzeilen) zur Ableitung von
  Auslösermenge, Ausnahmemenge und Klassifikation, zur Testzeit über
  `go test` gelesen.
- **Input (Python):** der Inhalt aller `*.py`-Dateien unter
  `api/routers/`.
- **Output:** beide Wächter grün, solange keine neue Handler-/
  Endpunkt-Stelle gegen die Regel verstößt und kein Marker fehlerhaft,
  doppelt, widersprüchlich oder verwaist ist. Rot mit Datei- und
  Zeilenangabe bei jedem neuen Fund.
- **Side effects:** kein ausführbarer Produktivcode ändert sich.
  `internal/store/user.go`, `sessions.go`, `address_owner.go`,
  `store.go`, `briefing_lock.go` bekommen je Kommentarzeilen — kein
  Laufzeitverhalten ändert sich dadurch.

## Acceptance Criteria

- **AC-1:** Given ein Handler in `internal/handler/`, der eine
  Implizit-Scope-Store-Methode auf einem Store-Bezeichner aufruft, der zu
  diesem Zeitpunkt nicht per `WithUser(...)` gebunden ist / When der
  Go-Wächter läuft / Then meldet er diesen Aufruf als Fund. Die
  Reihenfolge ist Teil der Zusicherung: Ein `s.LoadTrips()` **vor** der
  Bindung wird gemeldet, „`WithUser` steht irgendwo im Körper" genügt
  nicht. Sowohl `s := s.WithUser(...)` als auch `us := s.WithUser(...)`
  zählen als gültige Bindung (kein Namens-Whitelisting).
  - Test: Fixture-Handler mit vertauschter Reihenfolge (Store-Aufruf vor
    Bindung) erzeugt genau einen Fund; eine Variante mit `us :=` statt
    `s :=` als Bindungsname wird korrekt als gebunden erkannt.

- **AC-2:** Given die Auslösermenge des Wächters / When sie zur Testzeit
  als Vereinigung aus (a) der per `go/ast` aus `internal/store/*.go`
  (ohne `_test.go`) abgeleiteten Menge „`FuncDecl` mit Receiver `*Store`,
  deren Körper strukturell `s.requireUser()` aufruft" und (b) allen
  Methoden mit Marker `gz-store-scope-required` gebildet wird / Then
  enthält sie `LockBriefing`, weil diese Methode den Marker im Quelltext
  trägt — nicht weil ihr Name im Testcode steht. Die Ableitung läuft
  strukturell über den AST, nicht über Textsuche; kein Methodenname ist
  im Wächter fest kodiert.
  - Test: Ableitung gegen den echten `internal/store/`-Baum läuft, prüft
    dass `LockBriefing` über den `gz-store-scope-required`-Marker in der
    resultierenden Auslösermenge steht; eine Fixture-Datei mit
    `requireUser()` nur in einem Kommentar liefert dafür keinen Treffer;
    eine Fixture mit dem Marker, aber ohne `requireUser()`-Aufruf, landet
    trotzdem in der Auslösermenge (Marker-Pfad, nicht AST-Pfad).

- **AC-3:** Given alle **exportierten** `*Store`-Methoden, die aus
  `internal/handler/` aufgerufen werden / When der Wächter läuft / Then
  muss jede in **genau einer** Klasse liegen: abgeleiteter Auslöser
  (AC-2), `gz-store-scope-required` oder `gz-store-scope-exempt`. Eine
  aufgerufene Methode, die in keiner Klasse liegt (unklassifiziert),
  macht den Wächter rot.
  - Test: Fixture-Store-Methode, die aus einem Fixture-Handler aufgerufen
    wird, aber weder `requireUser()` ruft noch einen der beiden Marker
    trägt, erzeugt einen Fund der Klassifikations-Pflicht.

- **AC-4:** Given eine Store-Methode mit Marker-Annotation / When der
  Wächter läuft / Then wird er rot bei (a) doppelter Markierung (beide
  Marker an derselben Methode), (b) widersprüchlichem Marker
  (`gz-store-scope-exempt` an einer Methode, die `requireUser()` ruft),
  (c) verwaistem Marker (Marker an einem Methodennamen, Aufrufort oder
  Endpunkt, den es nicht gibt oder der die Regel ohnehin erfüllt) und
  (d) einer Begründung unter 15 Zeichen nach dem Doppelpunkt.
  - Test: vier separate Fixtures — doppelt markierte Methode,
    `exempt`-Marker an einer `requireUser()`-Methode, ein Marker auf
    einen nicht existierenden Namen sowie ein Marker mit einstelliger
    Begründung — erzeugen je einen eigenen Fund.

- **AC-5:** Given der dreifache Selbstschutz der Go-Ableitung / When er
  läuft / Then (a) schlägt die Mindestzahl-Assertion fehl, wenn die
  `requireUser()`-Ableitung weniger als **25** Methoden liefert, (b)
  schlägt eine fest kodierte Stichprobenprüfung fehl, wenn `LoadTrip`,
  `SaveTrip`, `LoadLocations` oder `LoadComparePresets` in der Ableitung
  fehlen, (c) schlägt eine Mindestzahl-Assertion für gescannte
  Handler-Dateien fehl, wenn weniger Dateien besucht wurden als
  erwartet.
  - Test: drei separate Testfälle — (a) Ableitung künstlich auf eine
    leere oder verkürzte Liste gesetzt löst die Mindestzahl-Assertion
    aus, (b) Ableitung ohne eine der vier Stichprobenmethoden löst die
    Stichprobenprüfung aus, (c) eine auf einen Unterordner verkürzte
    Dateiliste löst die Mindestzahl-Dateien-Assertion aus.

- **AC-6:** Given ein Endpunkt in `api/routers/` mit Dekorator
  `@router.get/post/put/delete/...`, der einen `user_id`-Parameter
  deklariert / When der Python-Wächter läuft / Then gilt die
  Wirkungsregel: `user_id` ist erfüllt, wenn er **ohne Default**
  deklariert ist, mit `Query(...)` mit `Ellipsis` als erstem
  Positional-Argument, **oder** wenn die Endpunkt-Funktion den Marker
  `# gz-user-id-optional: <Begründung>` (≥15 Zeichen) trägt. Ein Marker
  an einem Endpunkt, der die Regel ohnehin erfüllt, gilt als verwaist
  und macht den Wächter rot. Die reale Form `user_id: str` ohne
  `Query(...)` (`scheduler.py:97`, `:107`) gilt weiterhin korrekt als
  erfüllt.
  - Test: je eine Fixture für „ohne Default", „`Query(...)`", „`user_id:
    str` ohne `Query`" (alle drei grün) sowie für „Default-String" und
    „`Query(\"x\")`" (beide rot), zusätzlich eine Fixture mit
    `gz-user-id-optional`-Marker an einem ansonsten regelkonformen
    Endpunkt (rot wegen Verwaisung).

- **AC-7:** Given je ein Fixture-Handler ohne `WithUser` bzw. mit
  `WithUser` nach dem Store-Aufruf (Go) und ein Fixture-Endpunkt mit
  `user_id: str = "default"` bzw. `Query("x")` (Python) / When die
  jeweiligen Wächter darüberlaufen / Then werden alle vier rot gemeldet
  (Mutations-Gegenprobe). **Neu:** Entfernt man in einer Testvariante den
  `gz-store-scope-exempt`- oder `gz-store-scope-required`-Marker von
  einer Fixture-Methode, wird die Klassifikations-Pflicht (AC-3) rot;
  kürzt man eine Marker-Begründung auf unter 15 Zeichen, wird die
  Marker-Hygiene (AC-4) rot. Rückdreh: Wird die Auslösermenge künstlich
  geleert, wird der Selbstschutz (AC-5a) rot, nicht grün.
  - Test: sechs Mutations-Fixtures — die vier ursprünglichen plus
    Marker-Entfernung und Marker-Kürzung — erzeugen je einen erwarteten
    Fund; zusätzlich ein Testfall, der die Auslösermenge auf eine leere
    Liste setzt und prüft, dass daraufhin die Mindestzahl-Assertion
    (nicht ein Nulldurchlauf) fehlschlägt.

- **AC-8:** Given alle 24 Marker-Kommentarzeilen in
  `internal/store/*.go` (23× `gz-store-scope-exempt`, 1×
  `gz-store-scope-required` an `LockBriefing`) sowie der neue Abschnitt
  in `docs/reference/gates_und_ratschen.md` mit Marker-Syntax-Tabelle
  und einer neuen Zeile in „Regel-Budget: Prüfdaten im Überblick" mit
  Prüfdatum **2026-12-20** / When beide Wächter im selben Stand laufen
  und das Dokument durchsucht wird / Then melden beide Wächter **0
  Befunde** (kein rotes `main` am ersten Tag) und die Prüfdatum-Zeile
  lässt sich im Dokument auffinden.
  - Test: beide Wächter laufen grün gegen den echten Baum inklusive
    aller 24 gesetzten Marker (echter Verhaltensnachweis); `grep -n
    "2026-12-20" docs/reference/gates_und_ratschen.md` findet die neue
    Tabellenzeile (**Ausnahme von der Dateiinhalt-Check-Regel**,
    `# doc-compliance-test`: geprüft wird reine Metadaten-Präsenz, kein
    Laufzeitverhalten — dafür ist ein Verhaltensnachweis weder möglich
    noch sinnvoll).

## Known Limitations

- **Kein interprozeduraler Fluss.** Ruft ein Handler eine Hilfsfunktion
  mit eigenem `*store.Store`-Parameter, prüft der Wächter deren Körper
  nicht gesondert. Heute **0 Fälle**: alle 13 Hilfsfunktionen mit
  `*store.Store`-Parameter (auth/oauth/magic/premium-sms) nutzen
  ausschließlich `gz-store-scope-exempt`-markierte Methoden.
- **Keine Zweig-Analyse.** Eine Bindung im `if`-Zweig und eine Nutzung im
  `else`-Zweig (oder umgekehrt) wird nicht als „ungebunden zum
  Nutzungszeitpunkt" unterschieden — der Provenance-Lauf ist linear über
  den Funktionskörper, keine Kontrollfluss-Analyse.
- **Eine künftige Store-Methode, die nutzergebundene Pfade baut, ohne
  `requireUser()` und ohne `s.UserID`** (etwa über einen Helfer, der die
  Kennung indirekt weiterreicht), bleibt für beide Ableitungswege
  unsichtbar. Das ist ein Scope-*Design*-Fehler, keine Lücke dieses
  Wächters — eine andere Regel müsste ihn fangen; Folge-Ticket bei
  Bedarf.
- **Nicht messbar aus dieser Sitzung:** ob `GZ_USER_ID` im
  Produktivbetrieb gesetzt ist (`/var/lib/gregor` für `hem` nicht
  lesbar) — `NOT_MEASURABLE`, blockiert nichts, da der Wert des
  Wächters nicht von dieser Antwort abhängt.
- **Der Wächter belegt Vollständigkeit der Form, nicht Korrektheit des
  Verhaltens.** Er stellt sicher, dass jede nutzergebundene Methode nur
  nach einer `WithUser`-Bindung aufgerufen wird — nicht, dass die
  gebundene Kennung tatsächlich die des anfragenden Nutzers ist (das
  prüfen `user_scoped_test.go` und die Auth-Middleware selbst).
- **Marker sind Selbstauskunft, kein Beweis (neu in v2.0).** Ein
  *falsch* begründeter `gz-store-scope-exempt` an einer Methode, die
  tatsächlich nutzergebunden ist, bleibt für den Wächter unentdeckt — er
  prüft nur, dass ein Marker mit ausreichend langer Begründung vorhanden
  ist, nicht dessen inhaltliche Richtigkeit. Dagegen hilft nur Review.
  Die Marker machen die Ausnahme **sichtbar und begründungspflichtig**,
  sie beweisen sie nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (`docs/adr/0003-multi-tenant-isolation.md`)
- **Rationale:** Kein neues ADR nötig — diese Arbeit wechselt keine
  Entscheidungsfläche, sie setzt eine bestehende Entscheidung
  (Mandantentrennung per `WithUser`/`user_id`) erstmals maschinell durch,
  statt sie neu zu treffen. Die zu bewachende Zusicherung bleibt
  ADR-0003. **v2.0-Ergänzung:** Die Marker-Konvention
  (`gz-store-scope-exempt`/`-required`/`-call`, `gz-user-id-optional`)
  ist selbst keine Architektur-Entscheidung, sondern eine Prüfmechanik —
  Ausnahmen von ADR-0003 stehen künftig begründet im Quelltext statt in
  einer stillen Positivliste im Testcode.

## Changelog

- 2026-09-20: Initial spec created (Issue #2156, Epic #2138) — auf Basis
  von `docs/context/feat-2156-mandanten-waechter.md` (Phase 1 + Phase 2,
  Stand `3c14e6e7`). Zahl der `requireUser()`-Store-Methoden auf den in
  Phase 2 zweifach gemessenen Wert **25** korrigiert (Kontext-Dokument
  nannte an einer Stelle noch die veraltete Zahl 27).
- 2026-09-20: v2.0 — Ausnahmen als begründete Marker im Quelltext statt
  stiller Positivliste (PO-Entscheid); Klassifikations-Pflicht und
  Marker-Hygiene als eigene ACs; Produktivdateien werden mit
  Kommentarzeilen berührt ⇒ Staging/Prod-Deploy nötig.
