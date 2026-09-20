# ADR-0003: Konsequente Mandantentrennung, kein `"default"`-Fallback

- **Status:** Akzeptiert
- **Datum:** 2026-04-12 (mit dem Go/SvelteKit-Backend etabliert, siehe ADR-0001)
- **Bezug:** `CLAUDE.md` → „Multi-User-Produkt", `docs/features/architecture.md`

## Kontext

Gregor Zwanzig ist **mandantenfähig**: Jeder Nutzer hat eigene Trips, Orte, Orts-Vergleiche,
Empfänger und Settings. Persistenz liegt pro Nutzer unter `data/users/<user_id>/`. In einem
mandantenfähigen System ist die größte Gefahr ein **Cross-User-Datenleck** — dass ein Endpoint
versehentlich fremde Daten lädt, schreibt oder versendet.

## Entscheidung

Jeder nutzerbezogene Endpoint **muss** die echte `user_id` aus dem Auth-Kontext durchreichen:

- **Go-Backend:** `s.WithUser(middleware.UserIDFromContext(r.Context()))`
- **Python-Scheduler/-Router:** expliziter `user_id`-Parameter

Ein Rückfall auf `"default"` in einem **authentifizierten** Pfad ist **verboten** — er gilt als
Cross-User-Datenleck. Jeder neue Endpoint, der Daten lädt/schreibt/versendet, muss
mandantengetrennt arbeiten und mit **zwei verschiedenen Nutzern** getestet werden.

Produkt-Konsequenz: Es gibt **kein** systemseitiges „an mich". „Senden" heißt immer „an die von
**diesem** Nutzer konfigurierten Empfänger". Single-User-Annahmen (z. B. „Test an mich vs. an die
Empfänger") sind gegenstandslos.

## Verworfene Alternativen

- **`"default"`-User als Fallback** bei fehlender/unklarer Identität — verworfen: maskiert
  Auth-Fehler und führt unweigerlich zu Datenvermischung über Nutzergrenzen hinweg.
- **Single-User-Annahme im Code** mit späterem „Nachrüsten" der Mandantenfähigkeit — verworfen:
  Mandantentrennung lässt sich nicht zuverlässig nachträglich aufpfropfen.

## Konsequenzen

- **Positiv:** Strukturell sichere Datenisolation; klare, einheitliche Aufruf-Konvention.
- **Negativ / Preis:** Jeder Endpoint muss den User-Kontext explizit durchreichen — mehr Disziplin
  bei jeder neuen Route; Tests müssen grundsätzlich mit zwei Nutzern laufen.
- **Folgepflichten:** Code-Review und Tests prüfen bei **jedem** neuen nutzerbezogenen Endpoint die
  Zwei-Nutzer-Isolation. Ein `"default"`-Fallback in authentifiziertem Pfad ist ein Blocker.

## Durchsetzung (seit 2026-09-20, #2156)

Diese Entscheidung hängt nicht mehr allein an Review-Disziplin. Zwei Wächter setzen sie zur
Testzeit durch — sie laufen in der CI-Ampel (`go-test` bzw. `test`) und machen einen Verstoß rot:

| Sprachraum | Wächter | Befund |
|---|---|---|
| Go | `internal/handler/store_scope_call_guard_test.go` | Aufruf einer nutzergebundenen `*Store`-Methode **vor** der `WithUser`-Bindung; unklassifizierte oder fehlerhaft markierte Store-Methode |
| Python | `tests/test_router_user_id_required.py` | Endpunkt in `api/routers/` mit `user_id`-Parameter, der einen Default trägt statt Pflichtparameter zu sein |

Die überwachte Methodenmenge ist **nicht im Testcode kodiert**, sondern wird zur Testzeit per
`go/ast` aus `internal/store/*.go` abgeleitet — sie kann also nicht veralten. Ausnahmen sind
nur als begründeter Marker am Quelltext zulässig (`gz-store-scope-exempt` /
`gz-store-scope-required` / `gz-store-scope-call` / `gz-user-id-optional`), damit jede Abweichung
dort steht und begründet ist, wo sie wirkt.

Marker sind allerdings **Selbstauskunft, kein Beweis**: ein falsch begründeter
`gz-store-scope-exempt` an einer tatsächlich nutzergebundenen Methode bleibt für den Wächter
unsichtbar. Die oben genannte Review-Pflicht bleibt damit bestehen — die Wächter verengen sie,
sie ersetzen sie nicht.

Marker-Syntax, die vier Wege sich damit rot zu machen, und das Regel-Budget-Prüfdatum
(**2026-12-20**): `docs/reference/gates_und_ratschen.md`, Abschnitt „Store-Scope-Call-Guard".
Detailmechanik und alle acht Acceptance Criteria: `docs/specs/modules/store_scope_call_guard.md`.

Ergänzend erzwingt seit #2151 ein eigener Wächter, dass `"default"` nicht als `user_id`-Literal
in `api/` auftaucht — siehe dieselbe Referenz.
