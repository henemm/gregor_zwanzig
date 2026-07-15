# Context: feat-1250-s6-api-konsolidierung

Issue #1250 (Phase 3 von Epic #1230), **Scheibe 6 — API-Konsolidierung**.
Programm-Spec: `docs/specs/modules/issue_1250_briefing_subscription.md` (S6 = §166-174,
AC-20…AC-22 §380-402). ADR: `docs/adr/0023-briefing-subscription-shared-model.md`.
Vorstufen S0–S5 live (HEAD `e1935803`).

## Request Summary

Eine vereinheitlichte API-Familie `/api/briefings*` einführen, über die Trip- und
Compare-Subscriptions `kind`-diskriminiert (`route`/`vergleich`) angesprochen werden;
die bestehenden `/api/trips*`- und `/api/compare/presets*`-Endpoints werden dünne
Kompat-Delegates (C6: Testids/FE bleiben stabil). PUT merged feldweise statt blind zu
ersetzen (AC-22, KL-5 — siebte Wiederholung des Datenverlust-Musters vermeiden).

## Related Files (Ist-Belege aus Kartierung)

| Datei:Zeile | Relevanz |
|---|---|
| `internal/router/router.go:136-159` | 8 Trip-Routen (Spec sagte fälschlich `cmd/server/router.go`) |
| `internal/router/router.go:172-178` | 7 Compare-Preset-Routen |
| `internal/handler/trip.go` | Trip-CRUD; PUT via DTO `tripUpdateRequest` (:147) + RMW-Merge (:199-268) |
| `internal/handler/compare_preset.go` | Preset-CRUD; PUT nil-Preserve pro Feld (:279-410); lädt/speichert immer ganzes Array |
| `internal/handler/config_merge.go:11` | `mergeConfigMap` (#1159) — bereits in beiden Handlern für Config-Maps genutzt |
| `internal/store/trip.go:14,155,190` | `TripsDir` = 1 Datei/Trip `trips/{id}.json`; `LoadTrip`/`SaveTrip` |
| `internal/store/compare_preset.go:12,58,122` | `compare_presets.json` = **Sammel-Array**; `LoadComparePresets`/`SaveComparePresets` |
| `internal/model/trip.go:101-158` | Trip-Modell inkl. S4-Flat-Felder + S5 `kind` (`omitempty`, kein Go-Writer setzt es) |
| `internal/model/compare_preset.go:14-108` | Preset-Modell inkl. Slots + S5 `kind` |
| `internal/model/briefing_subscription.go` | S5-Gerüst (ID/Kind + `raw`-Auffang), **nicht verdrahtet** |
| `internal/store/briefing_subscription.go` | `briefings/{id}.json`-Store (Load/Save), **nicht verdrahtet** |
| `scripts/migrate_1250_briefings.py` | Migration rohe Dicts + `kind` → `briefings/<id>.json`; Skip-wenn-`kind` (Staleness!) |
| `src/app/loader.py:1225-1230` | Python `load_all_trips` liest `trips/*.json` — **Choke-Point für S7** |
| `src/app/loader.py:283` | Python `load_compare_presets` liest `compare_presets.json` — **Choke-Point für S7** |
| `api/routers/scheduler.py` | Python-FastAPI (localhost:8000), von Go-Cron gerufen — S7-Terrain |
| `frontend/src/lib/types.ts:275,477` | FE-Typen Trip/ComparePreset (snake_case), Flat-Felder vorhanden, **kein `kind`** |
| `frontend/e2e/compare-editor-edit.spec.ts:27,104,150` | schärfster Contract-E2E (direkter `page.request` gegen `/api/compare/presets*`) |

## Existing Patterns

- **RMW-Merge ist bereits Bestandspattern.** Trip-PUT lädt→merged feldweise
  (`trip.go:199-268`, Map-Felder über `mergeConfigMap`), Compare-PUT nil-Preserve
  (`compare_preset.go:279-410`). AC-22 zementiert das nur für den neuen Pfad.
- **Responses = model-Structs direkt** (keine separaten DTOs). Struktur-Stabilität
  (AC-20) heißt: dieselben Structs weiter serialisieren.
- **Asymmetrische Persistenz:** Trip = 1 Datei/Trip, Preset = Sammel-Array. Ein
  vereinheitlichter Handler muss beide Store-Formen bedienen.
- **Dateisystem = Integrationspunkt.** Go-API und Python-Core lesen/schreiben
  **dieselben** Dateien. Es gibt keinen DB-Layer dazwischen.
- **`kind` ist additiv & schlafend** (Go + Python): parst/serialisiert verlustfrei,
  wird aber von KEINER App-Logik gesetzt/konsumiert — nur die Migration setzt es.
- **Trip-PUTs sind fast alle partiell** (`{stages}`, `{name}`, `{report_config}`,
  Alarm-Payloads) → Merge kritisch. Compare-PUTs schicken Voll-Objekte (`{...original}`)
  → replace-sicher, aber Server muss alle snake_case-Felder + nested `display_config`
  + top-level `corridors` durchreichen.

## Dependencies

- **Upstream (nutzt S6):** S5-Modell/Store-Gerüst (`briefing_subscription.go`),
  Migrationsskript, die additiven `kind`-Felder auf beiden Modellen.
- **Downstream (hängt an unveränderter API):** alle FE-Aufrufe von `/api/trips*` +
  `/api/compare/presets*` inkl. Sub-Endpoints (`/state`, `/send`, `/stages/weather`,
  `/alert-preview`, `/weather-config`, `/briefing-history`); Python-Lesepfade der
  Alt-Stores (Scheduler/Alert/Send).

## Existing Specs

- `docs/specs/modules/issue_1250_briefing_subscription.md` — Programm-Spec, S6 = §166-174,
  AC-20/21/22. Wird für S6 wiederverwendet (Muster #1231, eine Spec/Scheiben-Workflows).
- `docs/adr/0023-briefing-subscription-shared-model.md` — Entscheidung 4/5: volles
  typisiertes Union-Modell + Lesepfad-Umschaltung „in S6"; Konsequenz nennt
  ADR-Fortschreibung in S6 ausdrücklich.

## Zentrale Design-Entscheidung (für /20-analyse + PO)

**Spannung:** ADR-0023 Entscheidung 5 formuliert „S6 schaltet die Lesepfade um"
(auf `briefings/`). Da Go **und** Python dieselben Alt-Dateien nutzen, Python aber
erst in S7 umzieht, würde ein reiner Go-Umschalt einen **Split-Brain** erzeugen:
Frontend-Edit → `briefings/`, Python-Scheduler liest weiter `trips/`/`compare_presets.json`
→ Edit bis S7 versandwirkungslos. Das verletzt die Programm-Invariante
„jede Scheibe verhaltensneutral".

**Tragfähige Auflösung (Empfehlung, in Analyse zu schärfen):** S6 konsolidiert nur die
**API-/Handler-Ebene** — `/api/briefings*` dispatcht per `kind` über die **bestehenden**
Store-Methoden (`LoadTrip`/`SaveTrip` für route, `LoadComparePresets`/`SaveComparePresets`
für vergleich); Alt-Endpoints werden dünne Delegates. Alt-Stores bleiben **einzige
Wahrheit**. Der echte `briefings/`-Cutover (Go+Python, Lesen+Schreiben, atomar) inkl.
Prod-`--execute` bleibt **S7**. Konsequenz: das volle typisierte Union-Modell (~40 Felder,
`points`-Sum-Type) ist in S6 **nicht** nötig — der Dispatcher nutzt die schon typisierten
`model.Trip`/`model.ComparePreset`. Der S5-Handoff hat „S6 muss Koexistenz/Refresh klären"
genau als diese Arbeit offengelassen — kein ADR-Widerspruch, aber **ADR-0023-Fortschreibung**
nötig (S6/S7-Grenze präzisieren).

## Risks & Considerations

- **R1 — Split-Brain (s.o.):** höchstes Risiko; Auflösung = Persistenz-Cutover NICHT in S6.
- **R2 — ID-Auflösung:** `/api/briefings/{id}` muss `id`→`kind` auflösen (zwei Stores,
  mögliche ID-Kollision, vgl. Migrations-F001). Design: `?kind=`-Param oder
  Lookup-Reihenfolge. FE nutzt `/api/briefings` noch nirgends → freies Feld.
- **R3 — Sub-Endpoint-Fläche:** Trip-Pfad hat viele Sub-Routen (`/send` Proxy,
  `/stages/weather`, `/alert-preview`, `/weather-config`, `/briefing-history`, `/state`);
  Delegate-Umbau darf keine davon brechen (AC-21). Sicherste Variante: Bestands-Handler
  funktional unangetastet lassen, `/api/briefings*` additiv daneben.
- **R4 — AC-22 Merge:** neuer PUT-Pfad muss den Trip-partiell-Fall mergen (nicht nur den
  Compare-Voll-Objekt-Fall) — sonst Datenverlust bei partiellen Trip-PUTs.
- **R5 — Migrations-Staleness:** solange `briefings/` in S6 nicht gelesen wird, ist die
  Staleness moot; sie wird erst bei S7-Cutover scharf (Prod-`--execute` an S7-Deploy).
- **R6 — Renderer-/Mail-Gate:** S6 fasst keine Renderer an (KL-1) → Mail-Gates sollten
  nicht triggern; vor Commit prüfen, ob ein Edit-Pfad ein gate-pflichtiges File berührt.

## Analysis

### Type
Feature (Scheibe eines PO-freigegebenen Programms; Programm-Spec wird wiederverwendet).

### Design-Entscheidung (Gegenprobe Plan/Sonnet bestätigt, Risiko NIEDRIG)

**S6 macht `briefings/<id>.json` NICHT zur Persistenz-Wahrheit.** `/api/briefings*` wird
eine neue, `kind`-diskriminierte CRUD-Oberfläche, die per `kind` über die **bestehenden**
Store-Methoden dispatcht (`LoadTrip`/`SaveTrip` für route, `LoadComparePresets`/
`SaveComparePresets` für vergleich). Die Alt-Endpoints `/api/trips*` und
`/api/compare/presets*` werden dünne Delegates auf denselben geteilten Kern (kind fix aus
der Route). Alt-Stores bleiben **einzige Wahrheit**; niemand liest `briefings/` in S6
(`LoadBriefing` bleibt unverdrahtet bis S7).

**Warum nicht ADR-wörtlich (Go liest `briefings/`):** Go **und** Python nutzen dieselben
Alt-Dateien; Python zieht erst in S7 um und **schreibt** die Alt-Stores auch
(`save_compare_preset_status`/`_pause` scheduler_dispatch_service.py:124-201, `save_trip`
via Inbound-Commands loader.py:1476). Ein Go-only-Umschalt erzeugt **bidirektionalen
Split-Brain** → verletzt „jede Scheibe verhaltensneutral" (Spec:190-192). Verworfene
Alternativen: Go-Dual-Write (Python schreibt weiter nur alt → `briefings/` driftet);
S6+S7 zusammen (sprengt Scheiben-Granularität, ~600-1000 LoC, hoher GR221-Risk).

**Pflicht-Refinement (Falle aus der Gegenprobe):** `kind` muss auf `/api/briefings*`
**explizit** sein, nie per Store-Probing geraten (Trip-ID == Preset-ID real möglich, s.
Migrations-F001). POST setzt `kind` im Body; GET/PUT/DELETE tragen `kind` per Query oder
Pfadsegment. Die kind-freie Aggregat-`GET /api/briefings`-Liste ist ein NEUER Endpoint
(FE opt-in), **kein** Ersatz der zwei Alt-Listen (andere Shape).

**Folge:** volles typisiertes Union-Modell (~40 Felder, `points`-Sum-Type) in S6 **nicht**
nötig — Dispatcher nutzt die schon typisierten `model.Trip`/`model.ComparePreset`.
**ADR-0023-Fortschreibung** (Entscheidung 5 umformulieren: S7 schaltet Lese+Schreibpfade
Go+Python atomar um; S6 liefert nur die kind-diskriminierte API-Oberfläche) — vom ADR
selbst vorgesehen (Konsequenzen §53).

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `internal/handler/briefing_subscription.go` | CREATE | Geteilter Kern: kind-Dispatch für List/GET/POST/PUT/DELETE über Alt-Stores |
| `internal/router/router.go` | MODIFY | +`/api/briefings*`-Routen (kind-explizit) |
| `internal/handler/trip.go` | MODIFY | CRUD-Kern in geteilte Funktion(en) mit kind="route" heben; Handler = dünner Delegate |
| `internal/handler/compare_preset.go` | MODIFY | dito, kind="vergleich" |
| `internal/handler/*_test.go` (Kern) | CREATE | Kontrakt-Test `/api/briefings*` + Delegate-Struktur-Gleichheit + PUT-Merge (AC-20/22) |
| `docs/adr/0023-...md` | MODIFY | Entscheidung 5 fortschreiben (S6/S7-Grenze) |
| `docs/reference/api_contract.md` | MODIFY | `/api/briefings*` dokumentieren (Spec-Dependency) |

### Scope Assessment
- Files: ~7 (davon 1-2 CREATE, Rest MODIFY + Doku)
- Estimated LoC: +200…300 (deckt sich mit Spec ~250, §173) — AC-22-Merge existiert bereits
- Risk Level: **LOW** (kein Persistenz-Umschalt, kein neues Modell, kein Python-Change,
  keine Renderer) — sofern das kind-explizit-Refinement eingehalten wird.

### Dependencies / Reihenfolge
- Baut auf S5 (`kind`-Felder, Store-Gerüst). Blockiert nichts in S6, aber S7 baut darauf auf.
- Python bleibt in S6 unangetastet (S7-Terrain: Loader `loader.py:283,1225` + Writer).

### Open Questions / zu klären in der Spec
- [ ] `kind`-Transport auf `/api/briefings/{id}`: Query (`?kind=`) vs. Pfadsegment
  (`/api/briefings/{kind}/{id}`) — Spec legt eine Variante fest (Empfehlung: Query, minimal-invasiv).
- [ ] Werden die Alt-Handler wirklich zu Delegates umgebaut (Konsolidierung) ODER bleiben
  sie funktional stehen und `/api/briefings*` ruft nur dieselben Store-Methoden? (AC-20
  verlangt „dünner Delegate" — Empfehlung: geteilter Kern, Alt-Handler dünn darauf.)
- [ ] `POST /api/briefings` ohne gültiges `kind` → 400 (Edge Case in Spec).
