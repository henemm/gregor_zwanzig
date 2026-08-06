---
entity_id: feat_1492_s2a_thunder_vertretung
status: draft
type: module
created: 2026-08-06
updated: 2026-08-06
version: "1.1"
tags: [gewitter, provider, fallback, vertretung, dwd, meteofrance, s2a]
---

# Gewitter-Vertretung: Ausfall einer Direktquelle wird von der benachbarten Quelle aufgefangen

## Approval

- [x] Approved — PO-Freigabe 2026-08-06 („approved")

## Purpose

Fällt eine Gewitter-Direktquelle (`de_direct`, `fr_direct`) tatsächlich aus
(Netzwerkfehler, Zeitüberschreitung), bleibt die Gewitteraussage heute
lautlos leer — ohne Vertretung, ohne Herkunftsvermerk. Diese Scheibe führt
eine **Fehlerunterscheidung** ein (echter Dienstausfall vs. geografisch
unzuständig vs. korrekt leere Antwort), eine **benannte Vertretungstabelle**
je Region und die **Herkunftsangabe** in den bereits vorhandenen
`ForecastMeta`-Feldern. Zweite von zwei Scheiben aus Issue #1492
(`docs/context/feat-1492-gewitter-fallback-kette.md`, Abschnitt „Scheibe 2 —
PO-Entscheidungen 2026-08-06", Zuschnitt 2a). Sichtbarkeit im Briefing
(E-Mail-/Telegram-Fußzeile, Klartext) ist **nicht** Teil dieser Scheibe —
das ist 2b, siehe Known Limitations.

**Nachgebessert 2026-08-06 (team-lead-Review, PO-Entscheidungen):** Nur
`de_direct` (`dwd.py`) und `fr_direct` (`meteofrance.py`) bekommen die neue
Fehlerunterscheidung — `eu_direct` (`dwd_eu.py`) hat laut Vertretungstabelle
selbst keine Vertretung und muss ihren Ausfall daher niemandem melden,
bleibt also **unverändert**. LoC-Grenze auf 500 angehoben (statt 250) —
Testumfang wird dadurch NICHT gekürzt.

## Source

- **File:** `src/providers/thunder_enrichment.py` (Orchestrierung),
  `src/providers/thunder_routing.py` (neue Vertretungstabelle),
  `src/providers/base.py` (neuer Ausnahmetyp), `src/providers/dwd.py`,
  `src/providers/meteofrance.py` (Fehlerunterscheidung an der jeweiligen
  Abrufstelle). `src/providers/dwd_eu.py` wird **nicht** verändert — s.
  Purpose.
- **Identifier:** `providers.thunder_enrichment._fetch_lightning_density`
  (umgebaut), `providers.thunder_routing.thunder_vertretung_for` (neu),
  `providers.base.ThunderSourceUnavailableError` (neu),
  `DwdDirectProvider.fetch_thunder_signals_named` (Zeile 379),
  `MeteoFranceDirectProvider.fetch_thunder_signals_multi` (Zeile 542).
  `DwdEuDirectProvider.fetch_thunder_signals_named` (dwd_eu.py:334) wird
  ausschließlich als bestehender, unveränderter Aufrufweg KONSUMIERT (als
  Vertretungsziel), nicht geändert.

**Schicht:** Python-Core (`src/providers/`). Keine Go-API, kein Frontend.

## Estimated Scope

- **LoC:** Produktivcode ~90–105 (base.py ~12, thunder_routing.py ~15,
  thunder_enrichment.py ~40, dwd.py ~12, meteofrance.py ~18 — `dwd_eu.py`
  entfällt gegenüber der Vorfassung). Tests grob geschätzt ~230–260 (eine
  Fake-Provider-Fixtures-Datei für die Enrichment-/Vertretungs-Ebene, ZWEI
  Provider-Testdateien für die Fehlerunterscheidung: `dwd.py` und
  `meteofrance.py` — `dwd_eu.py` braucht keine neue Testdatei, da
  unverändert). **Zusammen ~320–365 LoC.** PO hat für dieses Paket 500 LoC
  freigegeben (`loc_limit_override`) — der Testumfang wird dadurch NICHT
  gekürzt, alle acht ursprünglich vorgesehenen Prüfszenarien plus das neu
  hinzugekommene AC-9 (Hagel-Rohsignal, s. u.) bleiben vollständig erhalten.
- **Files:** 5 geändert (`base.py`, `thunder_routing.py`,
  `thunder_enrichment.py`, `dwd.py`, `meteofrance.py`) + 2 neue
  Testdateien + 2 Doku-Korrekturen (zählen nicht gegen LoC)
- **Effort:** medium (kritischer Datenpfad, alle Kanäle; kein neues
  Architektur-Muster, aber zwei strukturell unterschiedliche
  Provider-Dateien)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.thunder_routing.thunder_provider_for` / `_REGIONS` | intern | Primärauswahl — bleibt **unangetastet** (AC-8-Schutz aus `feat_1457_s2c_icon_eu_luekenfueller.md`) |
| `providers.base.ThunderSignalProvider` | intern (Protokoll) | Nach außen unverändert: „wirft NIE" bleibt gültig für `enrich_thunder()` als Ganzes |
| `providers.base.ProviderRequestError` | intern | Vorbild für einen zusätzlichen, spezifischen Ausnahmetyp in `base.py` |
| `app.models.ForecastMeta.{fallback_model,fallback_reason,fallback_metrics}` | Datenmodell | Bereits vorhanden (#1115/ADR-0018), heute für Gewitter nie gesetzt — diese Scheibe befüllt sie, führt kein neues Feld ein |
| ADR-0018 „Modell-Fallback ohne Kaschieren" | Architektur | Diese Scheibe dehnt die Nicht-Kaschieren-Invariante auf die Gewitter-Domäne aus — eigenes ADR-0047 |
| ADR-0025 „Eine Gewitter-Quelle für alle Kanäle" | Architektur | Betrifft die **Ausgabe** (`dp.thunder_level`), nicht die Anzahl der Bezugsquellen — Abgrenzung im ADR-0047 |
| `providers.dwd.DwdDirectProvider._thunder_point` (Zeile 330) | intern | Bekommt die Zähllogik „versucht/fehlgeschlagen" |
| `providers.meteofrance.MeteoFranceDirectProvider.fetch_thunder_signals_multi` (Zeile 542) | intern | Analoge Zähllogik, andere Schleifenform (Gruppen × Offsets, Zwischenspeicher-Treffer zählen NICHT als Versuch) |
| `providers.dwd_eu.DwdEuDirectProvider.fetch_thunder_signals_named` (dwd_eu.py:334) | intern | Unverändertes Vertretungsziel — liefert `lpi`, KEIN `grau_gsp` (KL-3 aus S2c, relevant für AC-9) |
| `providers.openmeteo.OpenMeteoProvider._derive_thunder_fields` (S1) | intern (Abgrenzung) | Speist `ForecastDataPoint.hail_flag` (bool, #1475) ausschließlich aus `wmo_code` — von dieser Scheibe **nicht** berührt, s. Known Limitations 8 |

## Implementation Details

**1. Neuer Ausnahmetyp (`base.py`, neben `ProviderRequestError`):**

```
class ThunderSourceUnavailableError(Exception):
    """Optionales Signal fuer ThunderSignalProvider-Implementierungen:
    wird geworfen, wenn ALLE tatsaechlich versuchten Abrufe eines Aufrufs
    an einer Verbindungs-/Zeitueberschreitung scheiterten -- NICHT bei
    einer erfolgreichen, aber leeren/ausserhalb-des-Gitters-Antwort und
    NICHT bei nur TEILWEISE gescheiterten Punkten. Kein Provider MUSS ihn
    werfen; ohne ihn gilt weiterhin das alte Fail-soft-Verhalten (leeres
    Ergebnis). Der Vertrag von ThunderSignalProvider ("wirft NIE") bleibt
    fuer den AEUSSEREN Aufrufer (enrich_thunder) unveraendert -- dieser Typ
    wird ausschliesslich INNERHALB von thunder_enrichment abgefangen."""
    def __init__(self, provider: str, attempted: int) -> None:
        self.provider = provider
        self.attempted = attempted
        super().__init__(f"[{provider}] Gewitterquelle nicht erreichbar "
                          f"({attempted} Punkt(e) versucht, alle gescheitert)")
```

**2. Vertretungstabelle (`thunder_routing.py`, NEUE Funktion neben,
nicht in `_REGIONS`/`thunder_provider_for` — die Primärauswahl bleibt
first-match-wins und unangetastet):**

```
_VERTRETUNG: Dict[str, Optional[str]] = {
    "de_direct": "eu_direct",
    "fr_direct": "eu_direct",
    "eu_direct": None,
}

def thunder_vertretung_for(quelle: str) -> Optional[str]:
    """Benannte Ersatzquelle bei echtem Ausfall von `quelle`, oder None."""
    return _VERTRETUNG.get(quelle)
```

**3. Provider-Ebene — NUR `dwd.py` (`de_direct`) und `meteofrance.py`
(`fr_direct`) bekommen die Zähllogik. `dwd_eu.py` bleibt unverändert, weil
`eu_direct` selbst keine Vertretung hat (`_VERTRETUNG["eu_direct"] is
None`) — sein Ausfall hat niemanden, der ihn auffangen könnte, also lohnt
sich die Unterscheidung dort nicht. `zustand` existiert in `dwd.py` bereits
als lokales Dict je Aufruf von `fetch_thunder_signals_named`:**

```
zustand: Dict[str, object] = {"index": 0, "bestaetigt": False,
                               "versucht": 0, "fehlgeschlagen": 0}
# in _thunder_point, direkt vor self._request(...):
zustand["versucht"] = int(zustand["versucht"]) + 1
# in der bestehenden generischen except-Klausel UND wenn der 404-Lauf-
# Rueckfall erschoepft ist (weiterer_kandidat=False):
zustand["fehlgeschlagen"] = int(zustand["fehlgeschlagen"]) + 1
# NACH dem bestehenden try/except-Block der Methode, vor `return ergebnis`:
versucht = int(zustand["versucht"])
fehlgeschlagen = int(zustand["fehlgeschlagen"])
if versucht > 0 and fehlgeschlagen == versucht:
    raise ThunderSourceUnavailableError(self.name, versucht)
```

Ein erfolgreicher Request, dessen Wert wegen Gitterrand/Füllwert zu `None`
wird (`_read_point_value`), erhöht `versucht`, aber NICHT `fehlgeschlagen`
— genau das trennt „außerhalb des Modellgebiets" (kein Ausfall) von einem
echten Verbindungsfehler. Ein einzelner fehlgeschlagener Zeitpunkt unter
vielen erfolgreichen erhöht `fehlgeschlagen`, aber `fehlgeschlagen <
versucht` bleibt — kein Ausfall (Teilfehlschlag). `meteofrance.py`
bekommt dieselbe Zählung an der strukturell anderen Stelle (Gruppen ×
Offsets, `fetch_thunder_signals_multi`, Zeile 542); ein
Zwischenspeicher-Treffer (`speicher.get(...)` liefert nicht `None`) zählt
NICHT als Versuch — er ist keine frische Abfrage. Der budgetbedingte
Frühausstieg (`restzeit <= 0: return ergebnis`) prüft NICHT auf
Ausfall — ein erschöpftes Zeitbudget ist kein Dienstausfall (s. auch Known
Limitations 1 — die Vertretung bekommt bewusst KEINE Restzeit-Weitergabe).

**4. Vertretungsaufruf (`thunder_enrichment.py`, `_fetch_lightning_density`
umgebaut): der bestehende Dispatch-Block (benannt/sammeln/einzelwert,
heute Zeilen 211–229) wird in einen kleinen Helfer
`_hole_eintraege(quelle_name, location, von, bis) -> list[tuple[str, dict]]`
extrahiert — unverändert im Verhalten, nur parametrisiert auf
`quelle_name` statt auf die feste `quelle`-Variable. `_fetch_lightning_density`
ruft ihn zuerst für die Primärquelle auf; bei
`ThunderSourceUnavailableError` wird `thunder_vertretung_for(quelle)`
nachgeschlagen und — falls vorhanden und `!= bereits_befragt` — derselbe
Helfer erneut mit der Ersatzquelle aufgerufen. `_hole_eintraege` ruft dabei
ganz normal `get_provider(ersatz)` und den bestehenden, unveränderten
Dispatch auf — für `eu_direct` als Ersatz ist das exakt derselbe Weg wie
heute, wenn `eu_direct` PRIMÄR zuständig ist:**

```
aktive_quelle = quelle
try:
    eintraege = _hole_eintraege(quelle, location, von, bis)
except ThunderSourceUnavailableError:
    ersatz = thunder_vertretung_for(quelle)
    if ersatz is None or ersatz == bereits_befragt:
        return
    aktive_quelle = ersatz
    eintraege = _hole_eintraege(ersatz, location, von, bis)
    # Scheitert die Ersatzquelle IHRERSEITS (heute strukturell nicht der
    # Fall, da dwd_eu.py unveraendert bleibt und daher nie
    # ThunderSourceUnavailableError wirft -- sie liefert bei echtem
    # Ausfall weiterhin ein leeres Ergebnis OHNE zu werfen): dieser Zweig
    # bleibt trotzdem als Sicherheitsnetz stehen, falls eine kuenftige
    # Ersatzquelle die Ausnahme doch wirft -- die propagiert dann
    # unveraendert zum bestehenden aeusseren Fang in enrich_thunder()
    # (Zeile 157-160), Verhalten bleibt fail-soft (Spec AC-5).
```

Weil `_hole_eintraege` bei jedem Aufruf FRISCH ermittelt, ob die
angefragte Quelle `fetch_thunder_signals_named`/`_multi`/die
Einzelwert-Methode anbietet, schreibt eine Vertretung automatisch in DIE
FELDER, die die Ersatzquelle selbst benennt (`_SIGNAL_ZU_FELD`) — bei
`fr_direct → eu_direct` also `lightning_potential_lpi_jkg`, NICHT das
`lightning_density_per_km2_3h`-Feld von `fr_direct`. Der Skalenwechsel ist
damit strukturell sauber (keine Vermischung), ohne Sonderfall-Code. Aus
demselben Grund bleibt `hail_potential_grau_gsp` bei `de_direct →
eu_direct` automatisch `None` — `eu_direct` benennt kein Hagelsignal (s.
AC-9).

**5. Herkunft festhalten (nach erfolgreichem `gefuellt > 0`):**

```
if aktive_quelle != quelle:
    reihe.meta.fallback_metrics.extend(
        sorted({feld for feld, werte in eintraege if werte})
    )
    if reihe.meta.fallback_model is None:  # Merge-Schutz, s. Known Limitations 3
        reihe.meta.fallback_model = aktive_quelle
        reihe.meta.fallback_reason = "thunder_source_unavailable"
    logger.warning(
        "Gewittersignale von Ersatzquelle '%s' statt '%s' "
        "(nicht erreichbar): %d Zeitpunkte gefuellt",
        aktive_quelle, quelle, gefuellt,
    )
```

KEINE Änderung an `thunder_level_from_signals`, an `_REGIONS`, an der
Fusion (`_fuse_thunder_levels`) oder an irgendeinem Renderer/Kanal.

## Expected Behavior

- **Input:** Eine Vorhersage für einen Ort, dessen zuständige
  Gewitter-Direktquelle (`de_direct` oder `fr_direct`) bei JEDEM
  versuchten Abruf mit einem Verbindungsfehler/Timeout scheitert.
- **Output:** Statt leerer Signalfelder trägt die Reihe die Werte der
  benannten Ersatzquelle (`eu_direct`), `reihe.meta.fallback_model` /
  `fallback_reason` (falls noch unbesetzt) sowie `fallback_metrics`
  nennen die Ersatzquelle bzw. die befüllten Felder, ein `logger.warning`
  protokolliert den Wechsel.
- **Side effects:** Bei ausgelöster Vertretung EIN zusätzlicher HTTP-Abruf
  an die Ersatzquelle, mit ihrem eigenen, VOLLEN Zeitbudget (keine
  Restzeit-Weitergabe, PO-Entscheidung — s. Known Limitations 1). Kein
  zusätzlicher Abruf im Normalfall (Primärquelle erreichbar).

## Acceptance Criteria

- **AC-1 (Vertretung springt bei echtem Dienstfehler ein):** Given ein
  Ort mit Primärquelle `de_direct`, die bei jedem der angefragten Punkte
  einen Verbindungsfehler wirft (Fake-Provider, erfüllt das echte
  `ThunderSignalProvider`-Protokoll, wirft `ThunderSourceUnavailableError`
  aus `fetch_thunder_signals_named`) / When `_fetch_lightning_density`
  läuft / Then trägt `lightning_potential_lpi_jkg` den Wert, den ein
  zweiter Fake für `eu_direct` mit einem eindeutigen Sentinelwert (z. B.
  `42.0`) liefert — NICHT `None`.
  - Test: Ausgangswert (`None`, weil Primärquelle wirft), Ableitungsquelle
    (Vertretungstabelle `de_direct → eu_direct`) und Sollwert (`42.0` vom
    Ersatz-Fake) sind drei unterscheidbare Größen — eine Implementierung,
    die die Ausnahme nur schluckt (heutiges Verhalten), bleibt bei `None`
    und macht den Test rot.

- **AC-2 (Vertretung springt NICHT ein bei leerer, aber gültiger
  Antwort):** Given dieselbe Primärquelle liefert ein leeres, aber
  gültiges Ergebnis (`{}`/alle Werte `None`, OHNE zu werfen — „kein
  Gewitter in Sicht") / When `_fetch_lightning_density` läuft / Then
  bleibt das Feld `None` UND der Ersatz-Fake für `eu_direct` wird **nicht
  aufgerufen** (`call_count == 0`).
  - Test: Der Ersatz-Fake trägt einen eindeutigen Sentinelwert (z. B.
    `99.0`), der bei fälschlicher Vertretung sichtbar würde. Ausgangswert
    (`None`, korrekt leer), Ableitungsquelle (Ersatz-Fake mit `99.0`) und
    Sollwert (weiterhin `None`, `call_count == 0`) sind drei
    unterscheidbare Größen — eine Implementierung, die jede leere Antwort
    wie einen Fehler behandelt, würde den Sentinel `99.0` durchreichen
    oder den Aufruf zählen und damit rot werden.

- **AC-3 (Vertretung springt NICHT ein außerhalb des tatsächlichen
  Modellgebiets):** Given `de_direct` antwortet für JEDEN angefragten
  Punkt erfolgreich (kein Verbindungsfehler), aber der gelesene Wert ist
  wegen Gitterrand-Füllwert `None` (Muster `_read_point_value`) / When
  `DwdDirectProvider.fetch_thunder_signals_named` läuft / Then wirft die
  Methode **keine** `ThunderSourceUnavailableError` (`versucht > 0`,
  `fehlgeschlagen == 0`).
  - Test: Gegen einen lokalen HTTP-Fake, der für jeden Request 200 mit
    einem gültigen GRIB2-Füllwert-Rechteck liefert (kein 4xx/5xx, keine
    `ConnectError`). Ausgangswert (Erfolg auf Transportebene),
    Ableitungsquelle (`_read_point_value` filtert den Füllwert zu `None`)
    und Sollwert (kein Wurf) sind drei unterscheidbare Größen — eine
    Implementierung, die jedes `None`-Ergebnis als Fehlschlag zählt, wird
    rot (sie würfe hier fälschlich).

- **AC-4 (Herkunft wird vermerkt):** Given AC-1s Vertretungsfall / When
  die Vertretung erfolgreich Werte liefert / Then trägt
  `reihe.meta.fallback_model == "eu_direct"`,
  `reihe.meta.fallback_reason == "thunder_source_unavailable"`, und
  `"lightning_potential_lpi_jkg" in reihe.meta.fallback_metrics`.
  - Test: Vor dem Aufruf sind alle drei Felder leer (`None`/`[]`) — nach
    dem Aufruf tragen sie die genannten Werte. Gegenprobe: Bleiben sie
    leer trotz erfolgreicher Vertretung (AC-1 grün, AC-4 rot), ist die
    Herkunftsangabe nicht verdrahtet.

- **AC-5 (Grundvorhersage kippt nicht, auch wenn Primär- UND
  Vertretungsquelle scheitern):** Given `de_direct` UND `eu_direct`
  scheitern beide an jedem Punkt (zwei Fakes, beide werfen
  `ThunderSourceUnavailableError`) / When `enrich_thunder()` (die äußere,
  produktiv aufgerufene Funktion, nicht `_fetch_lightning_density`
  direkt) läuft / Then wirft `enrich_thunder()` selbst **nichts**, die
  Zeitreihe bleibt vollständig mit `None`-Signalfeldern, und
  `dp.t2m_c`/`dp.wind10m_kmh` (Grunddaten, im Test vorab mit
  Nicht-`None`-Werten belegt) sind unverändert.
  - Test: Reproduziert exakt den in `base.py` zugesicherten Vertrag über
    den PRODUKTIV verdrahteten Aufrufer (`enrich_thunder`), nicht über den
    internen Helfer — sonst wäre nicht bewiesen, dass der äußere Fang
    (Zeile 157–160) tatsächlich greift. Gegenprobe: Entfernte man den
    äußeren `try/except` oder ließe die neue Ausnahme ihn umgehen, würde
    dieser Test mit einer unbehandelten Exception abbrechen statt grün zu
    laufen. Hinweis: In der HEUTIGEN Produktion wirft `eu_direct` selbst
    nie (dwd_eu.py bleibt unverändert, s. Purpose) — dieser Test ist damit
    auch eine Absicherung gegen eine künftige Erweiterung, nicht nur ein
    Abbild des Ist-Zustands.

- **AC-6 (Teilfehlschlag ist KEIN Dienstausfall):** Given `de_direct`
  liefert für 23 von 24 angefragten Zeitpunkten einen gültigen Wert und
  scheitert nur an EINEM Zeitpunkt mit Verbindungsfehler / When
  `fetch_thunder_signals_named` läuft / Then wirft die Methode **keine**
  `ThunderSourceUnavailableError` (`fehlgeschlagen=1 < versucht=24`), die
  23 gültigen Werte werden ganz normal übernommen, keine Vertretung wird
  ausgelöst.
  - Test: Ein lokaler HTTP-Fake, der bei genau einem Zeitstempel eine
    `ConnectError` wirft, sonst gültig antwortet. Ausgangswert (23/24
    Erfolge), Ableitungsquelle (Zähllogik `fehlgeschlagen == versucht`)
    und Sollwert (kein Wurf, 23 Werte gefüllt) sind drei unterscheidbare
    Größen — eine Implementierung, die schon EINEN Fehlschlag als Ausfall
    wertet, würfe hier fälschlich und macht den Test rot.

- **AC-7 (Messgrößenwechsel `fr_direct → eu_direct` schreibt ins RICHTIGE
  Feld, keine Vermischung):** Given `fr_direct` scheitert an jedem Punkt
  (Fake wirft `ThunderSourceUnavailableError` aus
  `fetch_thunder_signals_multi`) / When die (reale, unveränderte)
  Vertretung `eu_direct` einen gültigen `lpi`-Wert liefert / Then bleibt
  `dp.lightning_density_per_km2_3h` (das Feld von `fr_direct`) `None`,
  während `dp.lightning_potential_lpi_jkg` (das Feld von `eu_direct`) den
  gelieferten Wert trägt.
  - Test: Beide Felder werden nach dem Aufruf explizit geprüft — eine
    Implementierung, die den Ersatzwert fälschlich in
    `lightning_density_per_km2_3h` schriebe (Feld der Primärquelle statt
    der Ersatzquelle), macht diesen Test rot, weil `None` erwartet, aber
    ein Wert vorgefunden würde.

- **AC-8 (Primärauswahl-Reihenfolge bleibt unverletzt):** Given die neue
  Vertretungstabelle `_VERTRETUNG` existiert / When `thunder_provider_for`
  für einen französischen und einen deutschen/alpinen Testort abgefragt
  wird (dieselben Koordinaten wie in
  `feat_1457_s2c_icon_eu_luekenfueller.md` AC-8) / Then liefert die
  Funktion weiterhin `"fr_direct"` bzw. `"de_direct"` — unverändert
  gegenüber dem Stand vor dieser Scheibe.
  - Test: Regressions-Check gegen den bereits bestehenden AC-8-Test aus
    S2c (nicht dupliziert, nur re-importiert/erneut ausgeführt) PLUS eine
    Prüfung, dass `_REGIONS` als Tupel objektidentisch mit dem Stand vor
    dieser Scheibe bleibt (`_REGIONS == (unveränderter Referenzwert)`).
    Gegenprobe: Würde `_VERTRETUNG` versehentlich in `_REGIONS` verschmolzen
    oder `_REGIONS` umsortiert, wird dieser Test rot.

- **AC-9 (Hagel-Rohsignal bleibt „keine Aussage", wird nie zur stillen
  Entwarnung):** Given `de_direct` scheitert und wird durch `eu_direct`
  vertreten (AC-1-Szenario) / When die Vertretung erfolgreich
  Blitzpotenzial liefert / Then bleibt `dp.hail_potential_grau_gsp` an
  JEDEM betroffenen Datenpunkt `None` — nicht `0.0`, nicht irgendein aus
  dem Blitzpotenzial abgeleiteter Platzhalter.
  - Test: Nach erfolgreicher Vertretung wird `hail_potential_grau_gsp`
    explizit auf `None` geprüft, an denselben Datenpunkten, an denen
    `lightning_potential_lpi_jkg` bereits einen Wert trägt (AC-1). Diese
    Zusicherung folgt strukturell aus demselben Mechanismus wie AC-7 (die
    Vertretung schreibt nur Felder, die `eu_direct` selbst benennt —
    `grau_gsp` gehört nicht dazu, KL-3 aus
    `feat_1457_s2c_icon_eu_luekenfueller.md`); der Test macht sie nur
    explizit und schützt gegen eine künftige Änderung, die versehentlich
    einen Platzhalterwert einführt. **Abgrenzung (s. Known Limitations
    8):** Das eigentliche, nutzersichtbare Hagel-Kennzeichen
    (`ForecastDataPoint.hail_flag`, bool, #1475) ist von dieser Scheibe
    NICHT betroffen — es wird ausschließlich aus `wmo_code` abgeleitet,
    unabhängig von jeder Gewitter-Direktquelle.

## Known Limitations

1. **Zeitbudget-Verdopplung bei ausgelöster Vertretung — PO-Entscheidung:
   keine Sonderlogik.** `de_direct` (`THUNDER_FETCH_DEADLINE_SECONDS=90s`)
   + `eu_direct` (25s) ergeben im Worst Case bis zu 115s zusätzliche
   Wartezeit für die Gewitter-Anreicherung, `fr_direct` (45s) + `eu_direct`
   (25s) bis zu 70s. Jede Quelle bekommt bewusst ihre **volle eigene
   Frist**, keine Restzeit-Weitergabe zwischen Primär- und Ersatzquelle.
   Begründung (PO, 2026-08-06): Briefings entstehen asynchron, niemand
   wartet synchron darauf — die Laufdauer einzelner Anreicherungsschritte
   ist unkritisch, solange die Grundvorhersage (AC-5) nicht kippt. Das
   eigentliche Problem in diesem Bereich (sequenzielle Orts-/
   Etappenverarbeitung, 15-Minuten-Alarmtakt, übersprungene Ticks bei
   Gesamtlaufzeit-Überschreitung) ist unter **#1539** erfasst und liegt
   außerhalb dieser Scheibe.
2. **Health-Signal fehlt bewusst.** ADR-0018 „Folgepflichten" verlangt für
   jeden neuen degradierbaren Pfad zusätzlich ein mit der Ausfalldauer
   wachsendes Signal (`provider_error_streak_since`-Muster,
   `/api/scheduler/status`). Für Gewitter existiert das nicht und wird in
   dieser Scheibe **nicht** nachgerüstet — die Vertretung selbst hält
   Briefings am Laufen, ohne dass ein andauernder Ausfall einer
   Direktquelle extern eskaliert würde. **Vorschlag:** eigenes
   Folge-Issue („Health-Signal für Gewitter-Direktquellen"), nicht Teil
   von 2a/2b. Diese Vertagung ist eine bewusste Entscheidung, die der PO
   bei der Freigabe sieht — kein Versehen.
3. **`fallback_model`/`fallback_reason` sind Singularfelder — Kollision
   mit dem bestehenden WEATHER-05b-Mechanismus möglich, mit Konsequenz für
   2b.** Erleidet DIESELBE Zeitreihe zusätzlich einen
   Modell-/Metrik-Fallback der Grundvorhersage (Issue #1115/#1302), setzt
   dieser dieselben Felder. Diese Scheibe schreibt
   `fallback_model`/`fallback_reason` deshalb NUR, wenn sie noch unbesetzt
   sind (Merge-Schutz, s. Implementation Details Punkt 5) — im seltenen
   Kollisionsfall gewinnt, wer zuerst schreibt, und nur EIN Mechanismus
   ist über das Singularfeld sichtbar. Die Liste `fallback_metrics` ist
   davon nicht betroffen (immer append-fähig) und bleibt in jedem Fall
   vollständig — für 2a genügt das, weil es hier ausschließlich um
   Nachvollziehbarkeit IM SYSTEM geht (kein Renderer liest diese Felder in
   2a). **Übergabe an 2b:** Die geplante Briefing-Sichtbarkeit (E-Mail-/
   Telegram-Fußzeile) darf sich NICHT allein auf `reihe.meta.fallback_model`
   stützen, weil dieses Feld im Kollisionsfall bereits vom
   Grundvorhersage-Fallback belegt sein kann, obwohl eine Gewitter-
   Vertretung stattgefunden hat. 2b muss stattdessen (auch)
   `fallback_metrics` auswerten, um eine Gewitter-Vertretung zuverlässig
   zu erkennen.
4. **`thunder_provider_for()` liefert für reale Koordinaten strukturell
   nie `None`.** Die Catch-all-Zeile `EU_REST` (`_REGIONS`, S2c) deckt
   die gesamte Welt ab — nachgemessen (team-lead, 2026-08-06): Korsika →
   `fr_direct`, Zugspitze → `de_direct`, Island/Sydney/Nordpol →
   `eu_direct`. „Außerhalb des Zuständigkeitsgebiets" (AC-3) meint deshalb
   NICHT die Routing-Tabelle, sondern das tatsächliche Modellgitter der
   jeweiligen Quelle (Füllwert-Fall, geprüft innerhalb von
   `_thunder_point`) — eine Klarstellung, keine neue Lücke.
5. **Der `if quelle is None: return`-Zweig in `_fetch_lightning_density`
   ist toter Code.** Da `thunder_provider_for()` nie `None` liefert (s.
   Punkt 4), ist dieser Zweig strukturell unerreichbar; das dort zitierte
   „Spec AC-6" (aus #1457 S2a) ist damit wirkungslos. **Wird in dieser
   Scheibe NICHT repariert** — team-lead bucht das als eigenständigen
   Nebenbefund separat.
6. **`eu_direct` hat keine eigene Vertretung** (`_VERTRETUNG["eu_direct"]
   == None`). Scheitert `eu_direct` selbst (als Primärquelle ODER als
   bereits eingesprungene Ersatzquelle), bleibt es beim bisherigen
   Fail-soft-Verhalten — keine Verschlechterung gegenüber heute, aber
   auch keine Verbesserung für dieses eine Gebiet. `dwd_eu.py` bleibt
   deshalb vollständig unverändert (s. Purpose/Source).
7. **Doku-Korrekturen sind Teil des Umfangs, aber kein Code:**
   `docs/reference/api_contract.md:241` und
   `docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md` Known
   Limitations Punkt 4 (NICHT `feat_1457_s2b`, dort geprüft — kein
   Treffer, team-lead hat das bestätigt) behaupten beide, die Herkunft
   eines Gewitterwerts sei allein über die Position
   (`thunder_provider_for()`) rekonstruierbar — das stimmt mit Vertretung
   nicht mehr. Beide Stellen bekommen einen ergänzenden Satz, der auf die
   neue Vertretungstabelle und die `ForecastMeta`-Felder verweist.
8. **`ForecastDataPoint.hail_flag` (bool, #1475) ist von dieser Scheibe
   NICHT betroffen.** Er wird ausschließlich aus `wmo_code`/`weather_code`
   abgeleitet (`openmeteo.OpenMeteoProvider._derive_thunder_fields`,
   Scheibe 1) — unabhängig von jeder `ThunderSignalProvider`-Quelle. Die
   Vertretung dieser Scheibe wirkt ausschließlich auf
   `hail_potential_grau_gsp` (`Optional[float]`, reine Rohdaten, laut
   `api_contract.md` aktuell an KEINEM Renderer angeschlossen) — für
   dieses Feld gibt es keinen „False"-äquivalenten Zustand, das Risiko
   einer falschen Entwarnung besteht heute nicht, weil kein Ausgabeort es
   liest. AC-9 sichert trotzdem zu, dass die Vertretung hier niemals
   einen Platzhalterwert einführt, falls ein künftiger Renderer daran
   anschließt.
- **Nicht in dieser Scheibe (folgt als 2b):** Sichtbarkeit im Briefing
  (E-Mail-/Telegram-Fußzeile, Klartext-Formulierung „Gewitterdaten von
  Ersatzquelle …"). 2a hält die Herkunft nur intern fest.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0047
- **Rationale:** Diese Scheibe führt eine neue, dauerhafte
  Architekturentscheidung ein — Ausweichen zwischen Gewitter-Direktquellen
  bei echtem Ausfall, inklusive eines Messgrößenwechsels (Blitzdichte →
  Blitzpotenzial bei `fr_direct → eu_direct`). Das ist kein additiver
  Lückenschluss wie Scheibe 1, sondern dehnt ADR-0018 auf eine zweite
  Domäne aus und braucht eine explizite Abgrenzung zu ADR-0025. Details:
  `docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md`.

## Changelog

- 2026-08-06 (Nachbesserung nach team-lead-Review, PO-Entscheidungen):
  `dwd_eu.py` aus dem Produktivumfang entfernt (eu_direct hat keine eigene
  Vertretung, muss ihren Ausfall niemandem melden) — Estimated Scope
  entsprechend gesenkt (~320–365 statt ~360–420 LoC), LoC-Grenze vom PO auf
  500 angehoben, Testumfang dadurch NICHT gekürzt. Neues AC-9 (Hagel-
  Rohsignal bleibt „keine Aussage") plus Known Limitations 5 (toter
  `quelle is None`-Zweig), 8 (Abgrenzung zu `hail_flag`/#1475) ergänzt.
  Known Limitation zum Zeitbudget präzisiert: PO-Entscheidung „keine
  Sonderlogik", Verweis auf #1539 statt offener Prüfauftrag. Known
  Limitation zur `fallback_model`-Kollision um expliziten
  Übergabe-Hinweis an Scheibe 2b ergänzt. KL-4-Fundort von `feat_1457_s2b`
  auf `feat_1457_s2c` korrigiert (bereits in Vorfassung richtig, jetzt von
  team-lead gegengeprüft).
- 2026-08-06: Initial spec created (Issue #1492 Scheibe 2a, Analyse
  `docs/context/feat-1492-gewitter-fallback-kette.md` Abschnitt „Scheibe 2
  — PO-Entscheidungen 2026-08-06", E1–E3, Zuschnitt 2a/2b).
