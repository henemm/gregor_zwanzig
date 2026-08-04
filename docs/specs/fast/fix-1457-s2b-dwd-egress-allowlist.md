# Mini-Spec: DWD-Dienst auf die Test-/Staging-Erlaubnisliste setzen

## Was ändert sich

- `src/app/egress_guard.py`: `INVENTORY`-Tabelle bekommt einen neuen Eintrag
  `"opendata.dwd.de": IsolationKind.TEST_ACCESS` (gleiches Muster wie die
  bereits erlaubten Wetterdienste `api.open-meteo.com`,
  `dataset.api.hub.geosphere.at`, `api.brightsky.dev`).

## Warum

Der DWD-Gewitterabruf (#1457 S2b) und der bereits bestehende DWD-Basis-
Vorhersage-Fallback (Epic #1127) rufen `opendata.dwd.de` auf. Auf Staging
blockiert der Egress-Wächter (#1337) jeden nicht deklarierten Host —
`opendata.dwd.de` fehlte bisher in der Liste. Bisher unauffällig, weil der
DWD-Fallback nur im Totalausfall-Fall lief; S2b ruft DWD aber regulär auf und
deckt die Lücke auf. Betrifft **nur** Test/Staging — in Produktion ist der
Wächter ein No-Op (siehe Moduldocstring).

## Was sich nicht ändern darf

- Keine anderen `INVENTORY`-Einträge werden verändert.
- Der Wächter selbst (Patch-Mechanismus, Blockier-Logik) wird nicht angefasst.

## Acceptance Criteria

- **AC-1:** Given der Test-/Staging-Egress-Wächter ist installiert / When ein
  ausgehender HTTP-Aufruf an `opendata.dwd.de` erfolgt / Then wird er
  durchgelassen (kein `EgressBlockedError`), weil `opendata.dwd.de` als
  `IsolationKind.TEST_ACCESS` im `INVENTORY` deklariert ist.

## Manuelle Test-Schritte

1. Auf Staging: `curl "http://localhost:8001/forecast?lat=46.65&lon=12.60&hours=24"`
   → JSON enthält für spätere Stunden `lightning_potential_lpi_jkg` und
   `hail_potential_grau_gsp` mit numerischem Wert (nicht mehr komplett
   abwesend).
2. Log der Staging-Python-API zeigt keine `EgressBlockedError`/„egress
   blocked for host: opendata.dwd.de" mehr.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Test, der `INVENTORY["opendata.dwd.de"] == IsolationKind.TEST_ACCESS`
  prüft (Regressionsschutz gegen versehentliches Entfernen).
