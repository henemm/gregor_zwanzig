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
