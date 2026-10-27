# Context: fix-2302-s2-dwd-zeitbudget (#2302 Scheibe B)

## Request Summary

`dwd.py` (ICON-D2) und `dwd_eu.py` (ICON-EU) prüfen ihr Zeitbudget nur **zwischen** zwei
HTTP-Abrufen. Ein einzelner Abruf gegen eine Gegenstelle, die die Verbindung annimmt und
dann schweigt, kann die Retry-Kette rechnerisch ~390 s offenhalten. Scheibe B überträgt
darauf den in Scheibe A gebauten geteilten Baustein `src/providers/http.py` und ersetzt
den Test-Wächter, der heute **Abrufe** statt **verstrichener Zeit** zählt (Befund D5).

## Vorarbeit — nicht duplizieren

**Die vollständige Analyse liegt in `docs/context/fix-2302-provider-zeitbudget.md`** und
deckt alle drei Scheiben ab. Hier stehen nur der Schnitt für B, der **Ist-Stand nach
Scheibe A** und die in dieser Sitzung selbst nachgemessenen Fakten.

| Abschnitt dort | Inhalt |
|---|---|
| `:626-691` (D1) | Accessor-Muster, Schnittstelle von `providers/http.py`, **Dual-Fall `dwd.py`** |
| `:705-721` (D5) | Testüberarbeitung: Wanduhr-Test ergänzen, Marker entfernen, Zähl-Test behalten |
| `:722-731` (D6/D7) | Tröpfel-Fall bleibt **ausdrückliche Grenze**, `radar_service.py` unberührt |
| `:733-749` | Schnitt A/B/C, K3-Prüfauftrag für TDD-RED |
| `:751-782` | Risiko + Deckungskarte |

## Ist-Stand nach Scheibe A (selbst gelesen, Stand `c31a09a6`)

`src/providers/http.py` (108 Z.) liefert drei Bausteine — **Fabriken, kein gemeinsames
`Retrying`-Objekt**:

| Funktion | Zeile | Aufgabe |
|---|---|---|
| `make_deadline_before_hook(deadline_attr)` | `:32-56` | `before`-Hook; setzt `kwargs["deadline_at"]` **nur wenn None** (sonst rollende statt fester Frist); löst den Accessor über den **Methodennamen** zur Aufrufzeit auf |
| `stop_at_deadline(retry_state)` | `:59-70` | zeitbasierte Stop-Bedingung, per `\|` mit `stop_after_attempt` kombinierbar; tenacity wertet `stop` **vor** dem Schlafen aus, die Wartepausen zählen also mit |
| `capped_timeout_or_raise(...)` | `:73-108` | Kopf eines Versuchs: `deadline_at is None` → `base_timeout`; Restzeit ≤ 0 → `ProviderRequestError`; sonst `min(base_timeout, Restzeit)` |

**Anwendungsvorbild** `src/providers/meteofrance.py`: Accessor `_fetch_deadline_seconds`
(`:426-433`), Dekorator `:435-442` (`stop_after_attempt(RETRY_ATTEMPTS) | stop_at_deadline`,
`before=make_deadline_before_hook("_fetch_deadline_seconds")`), Kopf-Check `:467-475`,
Durchreichen an `_request_once(..., timeout=request_timeout)`.

## Zielstellen Scheibe B (Zeilennummern selbst verifiziert)

### `src/providers/dwd.py` (579 Z.) — der Dual-Fall

| Was | Zeile |
|---|---|
| `TIMEOUT = 30.0` / `RETRY_ATTEMPTS = 5` | `:59` / `:61` |
| `FETCH_DEADLINE_SECONDS = 180.0` (Grundpfad) | `:69` |
| `THUNDER_FETCH_DEADLINE_SECONDS = 150.0` (Gewitterpfad) | `:119` |
| `@retry(...)` **ohne** Zeitbedingung | `:316-322` |
| `_request(self, url)` — `self._client.get(url)` **ohne `timeout=`** | `:323-330`, Abruf `:326` |
| `_fetch_series(..., deadline_at)` — Budgetprüfung **zwischen** den Stunden | `:332-350`, Prüfung `:341`, Abruf `:348` |
| `_thunder_point(...)` — `while True` über Lauf-Kandidaten, **trägt `deadline_at` gar nicht** | `:352-404`, Abruf `:371` |
| `fetch_thunder_signals_named` bildet `deadline_at` lokal | `:450`, Prüfungen `:468`/`:486`, Aufrufe `:471`/`:489` |
| `fetch_forecast` bildet `deadline_at` lokal | `:541`, Aufrufe `:544-547` |

**Ein** `@retry`-dekoriertes `_request` bedient **beide** Budgets. Ein `before`-Hook kann
nicht zwei Vorgabewerte haben. Auflösung laut Analyse: `_request(self, url,
deadline_at=None)`, beide Aufrufer reichen ihren **bereits vorhandenen** Wert explizit
durch; der Hook bleibt nur Netz für den vergessenen Fall und muss die **weitere** Hülle
(180 s) als Vorgabewert tragen — nie 150 s, sonst verkürzt er den Gewitterpfad heimlich.

### `src/providers/dwd_eu.py` (431 Z.) — der einfache Fall

Strukturell deckungsgleich, aber **nur ein** Budget: `TIMEOUT = 30.0` (`:78`),
`THUNDER_FETCH_DEADLINE_SECONDS = 25.0` (`:134`), `@retry` `:305-311`, `_request`
`:312-319` (Abruf `:315`, ebenfalls ohne `timeout=`), `_thunder_point` `:321-…`
(Abruf `:339`), `fetch_thunder_signals_named` bildet `deadline_at` `:404`, prüft `:408`.
Ein Accessor genügt.

### K3 — der Lauf-Rückfall (während TDD-RED zu prüfen)

`_thunder_point` schleift in **beiden** Dateien über Lauf-Kandidaten (`while True`) und
ruft dabei mehrfach `_request` — ohne jede Frist. Wird `deadline_at` eine Ebene tiefer
durchgereicht, schließt das den Multiplikator mit. Reines Parameter-Durchreichen, keine
neue Logik. **Falls doch nicht trivial: ausdrücklich als offener Rest benennen, nicht
stillschweigend weglassen.**

## D5 — Testüberarbeitung

`tests/tdd/test_dwd_eu_thunder_time_budget.py` (134 Z.) zählt **Abrufe**
(`abrufe < ohne_zeitdruck`, `abrufe <= _ABRUF_SCHWELLE`, `:87-94`). Ein Abruf, der 390 s
hängt, lässt den Test grün — er misst den Wächter, nicht die Wirkung.

- **Ergänzen** (nicht ersetzen): Wanduhr-Test gegen `_HangingServer`; httpx-Kopie aus
  `tests/tdd/test_send_slot_and_fetch_deadline.py:140-188` **übernehmen, nicht nachbauen**
- **Plus Normalfall-Gegenprobe** — sonst wäre „bricht alles sofort ab" ebenfalls grün
- `@pytest.mark.timeout(N)` je Hänger-Test (globaler Default 30 s, `pyproject.toml:69`)
- **`live`-Marker (`:31`) entfernen** — er wird hier in der Bedeutung „vom Commit-Gate
  ausgenommen" benutzt, nicht laut eigener Definition; ohne Entfernen bliebe die neue
  Zusicherung ab Tag eins unsichtbar
- **Zähl-Test behalten:** er prüft eine andere, echte Eigenschaft (Signal-Reihenfolge unter
  Budgetdruck). Nur seine Docstring-Behauptung, das genüge als Zeitgrenzen-Nachweis, wird
  korrigiert.

**Selbst nachgemessen — das Entfernen des Markers ist unbedenklich:** Beide Fixtures
binden auf `127.0.0.1` (`_dwd_eu_fixtures.py:236` `eu_server`, `:296` `hauptquelle_laeuft`),
brauchen **kein** echtes Netz und schreiben **nicht** nach `data/users`. Die CI-Egress-Sperre
erlaubt `127.0.0.1` ausdrücklich (`.github/workflows/ci.yml:59-60`).

## Koordination mit #2226 (Antwort der Parallelsitzung, 12.09.)

Kein Dateikonflikt: #2226 fasst weder `test_dwd_eu_thunder_time_budget.py` noch
`_dwd_eu_fixtures.py` an. Zwei Folgen für uns:

1. **Die Selektions-Wirkung von `live`** (`pyproject.toml:65`) bleibt unberührt — D5 wird
   also **nicht** überflüssig, der Marker muss weiterhin von uns raus.
2. **Die Isolations-Wirkung von `live` kehrt sich um:** Nach #2226 schaltet nur noch
   `real_data_root` die Umleitung der Datenwurzel ab, `live` allein nicht mehr. Zusätzlich
   scheitert der Lauf künftig am Session-Ende, wenn irgendein Test nach `<repo>/data/users`
   schreibt. Für einen Zeitbudget-Test gegen einen hängenden Server erwarten wir keine
   Berührung — der Messbefund oben bestätigt das. **Falls doch:** `@pytest.mark.real_data_root`
   ist unter beiden Ständen die richtige Antwort.

#2226 ist in GREEN, aber noch **nicht** auf `main`. Liefern wir vorher, ist unsere Basis
die alte Semantik.

## Risks & Considerations

- **Die einzige echte Verhaltensverschlechterung:** `min(base_timeout, Restzeit)` kann am
  Ende einer langen Schleife **unter** die heutigen festen 30 s fallen. Ein Abruf, der heute
  in 25 s durchkäme, kann danach mit 5 s Restzeit scheitern. Das ist die **gewollte**
  Wirkung — aber die einzige Stelle, an der heute erfolgreiche (nur langsame) Abrufe neu
  kippen. **Gehört in die Spec, nicht nur in den PR**, sonst meldet der Adversary sie zu
  Recht als Defekt.
- **Kein geteiltes `Retrying`-Objekt:** `DwdDirectProvider._request.retry is
  DwdEuProvider._request.retry` muss `False` bleiben, sonst patchen sich Tests gegenseitig
  kaputt. Adversary-Prüfpunkt.
- **Vorgabewert des Hooks in `dwd.py`** muss 180 s sein, nicht 150 s (siehe oben).
- **Tröpfel-Fall (D6) bleibt ungedeckt** — eine einzelne, beliebig lang hingezogene Antwort.
  Ausdrückliche Grenze in der Spec, eigenes Ticket. **Verschweigen scheidet aus.**
- **Nie beobachtet:** Der Nachweis bleibt Konstruktion gegen `_HangingServer`; es gibt
  keinen Live-Vorfall zu reproduzieren.
- **LoC-Schätzung 180–220** inklusive D5-Test — knapp unter 250. Bei Überschreitung ist
  `workflow.py set-field loc_limit_override 500` der dokumentierte Weg, **nicht** Scope-Schnitt.

# Analysis (Phase 2)

## Type

**Bug** (Label `bug`, `priority:medium`, Epic #2257 Block 2). Kein neues Verhalten —
eine bestehende Zusicherung greift an der falschen Stelle.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/providers/dwd.py` | MODIFY | `_request(url, deadline_at=None)`; Dekorator um `\| stop_at_deadline` + `before`-Hook; Kopf-Check via `capped_timeout_or_raise`; Accessor `_fetch_deadline_seconds` → **180 s**; beide Aufrufer reichen ihr vorhandenes `deadline_at` durch |
| `src/providers/dwd_eu.py` | MODIFY | dasselbe, einfacher Fall; Accessor liefert `THUNDER_FETCH_DEADLINE_SECONDS` (25 s) |
| `tests/tdd/test_provider_request_deadline.py` | MODIFY | Wanduhr-Wächter für dwd + dwd_eu ergänzen; `_HangingServer` wird **geteilt**, nicht kopiert |
| `tests/tdd/test_dwd_eu_thunder_time_budget.py` | MODIFY | `live`-Marker (`:31`) entfernen; Docstring-Behauptung „Laufzeit-Test misst die Maschine" korrigieren; **Zähl-Test bleibt** |

## Scope Assessment

Dateien: 4 · geschätzt +180…220 / −5 LoC · **Risiko MEDIUM** — kritischer Pfad, aber
erprobtes Muster und eine gemessene Regressions-Grundlinie.

## Technical Approach

Der in Scheibe A gebaute Baustein wird angewandt, nicht neu erfunden. Vorbild ist
`meteofrance.py:426-475`, eins zu eins übertragbar auf `dwd_eu.py`. `dwd.py` ist der
**Dual-Fall** (ein `_request`, zwei Budgets) und braucht die in D1 beschriebene Auflösung.

## Vier eigene Messungen dieser Phase (nicht übernommen)

**M1 — Die Marker-Begründung ist veraltet.** `test_dwd_eu_thunder_time_budget.py:28-31`
begründet den `live`-Marker mit „lief im Kern nie grün (CI-Vermessung 2026-08-04, #1196)".
Nachgemessen unter exakten CI-Bedingungen (`--disable-socket --allow-unix-socket
--allow-hosts=127.0.0.1,::1,localhost`): **3 von 3 Läufen grün.** Das Entfernen des Markers
ist damit belegt unbedenklich, nicht bloß plausibel.

**M2 — Die Datenwurzel bleibt unberührt.** Vor/nach einem Lauf der Datei sind `mtime` von
`data` **und** `data/users` identisch (`1789211535`), ebenso der Hash der Verzeichnisliste.
Gemessen wurde die **mtime des Elternverzeichnisses**, weil ein Blick auf die Kinder
Anlegen und Löschen verpasst. Folge: Nach #2226 braucht die Datei **kein**
`@pytest.mark.real_data_root`.

**M3 — Regressions-Grundlinie, vor der ersten Code-Änderung genommen.**
`.../scratchpad/baseline_2302_s2.txt`, sechs Dateien mit `-m ''`: **43 passed, 1 failed.**
Diese Liste muss nach GREEN unverändert laufen. `test_send_slot_and_fetch_deadline.py`
gehört dazu, weil es das Regressionsnetz der A-Migration ist.

**M4 — Der eine Fehlschlag ist vorbestehend und bewacht abgelöstes Verhalten.**
`test_dwd_thunder_signal_fetch.py::test_ac3_dauerhafter_serverfehler_liefert_leeres_ergebnis_statt_ausnahme`
erwartet „wirft NIE", bekommt aber `ThunderSourceUnavailableError`. Ursache datiert:
Commit `5a8b6014` (**#1492 S2a**, Gewitter-Vertretung bei echtem Ausfall) hat diesen Fehler
**bewusst** eingeführt und damit den älteren AC-3-Vertrag abgelöst. Reproduzierbar (2/2),
kein Flake. **Nicht Gegenstand von Scheibe B.**

Zwei Folgen für die Spec:
1. Dieser Test ist **kein** Regressionsnetz für den Gewitterpfad von `dwd.py` — der neue
   Wanduhr-Wächter muss diese Lücke selbst decken.
2. Scheibe B entmarkert **nur** `test_dwd_eu_thunder_time_budget.py`. Ein Entmarkern von
   `test_dwd_thunder_signal_fetch.py` würde die CI-Ampel rot färben — ausdrücklich **nicht**
   Teil dieser Scheibe. Nebenbefund für **#1199** (Triage: kein nutzersichtbares
   Fehlverhalten, das Produktivverhalten ist das neuere und gewollte).

## Dokumentierte Abweichung von D5

D5 verlangt den Wanduhr-Test „in **derselben** Datei" mit einer **Kopie** des
`_HangingServer`. Das war formuliert, **bevor** Scheibe A
`tests/tdd/test_provider_request_deadline.py` schuf: 903 Zeilen, **ungemarkert**, in der
CI-Ampel, mit `_HangingServer` (`:105`) und bereits vier Wanduhr-Wächtern plus
Normalfall-Gegenprobe (`:351`). Die neuen Wächter gehören **dorthin** — das teilt den
Baustein, statt ihn ein zweites Mal zu kopieren, und folgt damit D5s Absicht statt seinem
Wortlaut. Das Entmarkern der Altdatei bleibt trotzdem drin, ist aber jetzt eine
**eigenständige** Zusicherung (macht einen vorhandenen Wächter sichtbar) und hängt nicht
mehr an der Wanduhr-Frage.

## Die dwd-Zusicherung braucht ZWEI unterscheidbare Budgets

Der gefährliche Fehler in `dwd.py` ist nicht „keine Frist", sondern „**stillschweigend die
falsche** Frist": Reicht die Gewitter-Aufrufstelle ihr `deadline_at` nicht durch, setzt der
`before`-Hook den Vorgabewert **180 s** — der Gewitterpfad bekäme heimlich das weitere
Budget. Ein Test, der beide Konstanten auf denselben kleinen Wert patcht, bliebe dabei
**grün und misst nichts**.

**Folge für die ACs:** `FETCH_DEADLINE_SECONDS` und `THUNDER_FETCH_DEADLINE_SECONDS` auf
**deutlich verschiedene** Werte patchen und zusichern, dass der Gewitterpfad die
**Gewitter**-Frist einhält. Als Mutation in die Gegenprobe: „Durchreichen an der
Gewitter-Aufrufstelle entfernen" muss einen Wächter rot machen.

## Schwellen der neuen Wanduhr-Assertions

Die Verhältnisse aus Scheibe A übernehmen, **nicht verschärfen**: `elapsed < 0.9` bei
0,45 s Frist, Normalfall `< 2.0`. Diese Schwellen haben CI-Läufe überstanden; eine knappere
Schwelle wäre eine Zeitbombe, die erst bei fremden PRs rot wird.

## Open Questions

- [ ] **K3 (in TDD-RED zu entscheiden, nicht vorher):** Lässt sich `deadline_at` in
  `_thunder_point` (`dwd.py:352`, `dwd_eu.py:321`) eine Ebene tiefer durchreichen und damit
  der Lauf-Rückfall-Multiplikator schließen? Gelingt es nicht trivial → **als offener Rest
  benennen**, nicht stillschweigend weglassen.

## Existing Specs

- `docs/specs/modules/fix_2302_s1_provider_zeitbudget_baustein.md` — Scheibe A (nicht editieren)
- `docs/specs/modules/fix_1448_s3_telegram_openmeteo.md` — Ursprung des Musters
- ADR-0038 (Alarm-Lauf-Gesamtfrist), ADR-0018 (4xx bleibt sichtbar)
