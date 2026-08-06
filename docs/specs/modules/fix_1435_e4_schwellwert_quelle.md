---
entity_id: fix_1435_e4_schwellwert_quelle
type: bugfix
created: 2026-08-06
updated: 2026-08-06
status: draft
version: "1.0"
tags: [metric-catalog, alerts, cross-stack, codegen, drift-prevention]
workflow: fix-1435-e4-schwellwert-quelle
---

# Fix #1435 Etappe E4 — Schwellwert-Tabelle wird eine einzige Quelle

## Approval

- [ ] Approved

## Purpose

Die Schwellwert-Tabelle „ab welchem Wert löst eine Wettergröße Alarm aus" (je
Wettergröße und Empfindlichkeitsstufe entspannt/standard/sensibel) existiert
heute zweimal handgepflegt — als Python-Liste im Backend (wirksam für den
Alarmversand) und als abgetippte Kopie im Frontend (nur für die Anzeige der
Zahl im Alarme-Reiter). Beide sind bei der Nullgradgrenze auseinandergedriftet:
der Alarme-Reiter zeigt bei Standard „Δ ≥ 200 m", tatsächlich löst das Backend
erst bei „Δ ≥ 400 m" aus. E4 macht Python zur einzigen Quelle; ein
Erzeuger-Skript schreibt eine eingecheckte JSON-Datei, das Frontend leitet
seine Anzeigewerte ausschließlich daraus ab, eine Frische-Ratsche fängt jede
künftige Drift.

## Source

> **Schicht-Hinweis:** betrifft zwei Schichten — Python-Core (Quelle +
> neues Erzeuger-Skript) und Frontend (SvelteKit, Alarme-Reiter, geteilt
> zwischen Trip- und Ortsvergleichs-Editor). Keine Go-Seite betroffen.

- **File:** `src/services/alert_preset.py`
- **Identifier:** `_PRESET_TABLE` (Zeile 39-57)
- **File:** `frontend/src/lib/components/alerts-tab/alertMetricTable.ts`
- **Identifier:** `METRIC_PRESETS` (Zeile 42-95), `THRESHOLD_CROSSING_METRICS`
  (Zeile 219-221), `levelToThreshold()` (Zeile 244-255)
- **File (neu):** `scripts/generate_alert_preset_table.py`
- **File (neu, generiert):** `frontend/src/lib/generated/alertPresetThresholds.generated.json`

## Estimated Scope

- **LoC:** ~170 berührt (Erzeuger-Skript ~85, `alertMetricTable.ts`-Diff
  ~-58/+22, `alert_preset.py`-Docstring ~5, Testcode ~90+25). Bleibt unter
  dem 250-Zeilen-Deckel, kein Override nötig. Die generierte JSON-Datei
  selbst zählt laut CLAUDE.md nicht auf den Deckel.
- **Files:** 6 — 2 Produktivdateien geändert (`alert_preset.py`,
  `alertMetricTable.ts`), 1 neu (`scripts/generate_alert_preset_table.py`),
  1 generierte JSON-Datei neu (eingecheckt), 1 neue Testdatei
  (`tests/tdd/test_alert_preset_table_parity.py`), 1 bestehende Testdatei
  neu angelegt (`alerts-tab/__tests__/alertPresetThresholdDisplay.test.ts`).
- **Effort:** medium — die Zahlen selbst ändern sich nur bei der
  Nullgradgrenze (ADR-0019 legt 600/400/200 bereits fest, keine neue
  PO-Entscheidung nötig), der Aufwand steckt im bereits aus E5 bekannten
  Baustein (generiertes Artefakt, ADR-0045) und im Nachweis, dass die
  Ratsche wirklich etwas fängt — auch dann, wenn das Frontend die Ableitung
  umgeht statt sie zu nutzen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_preset.py::_PRESET_TABLE` | READ (unverändert) | bleibt alleinige Quelle; das Erzeuger-Skript liest sie |
| `scripts/generate_alert_preset_table.py` | NEU | erzeugt `alertPresetThresholds.generated.json` aus `_PRESET_TABLE`, bietet `write()`/`check()` analog zum Vorbild aus E5 |
| `frontend/src/lib/generated/alertPresetThresholds.generated.json` | NEU (generiert, eingecheckt) | Vite-JSON-Import-Ziel (`resolveJsonModule` bereits aktiv) |
| `alertMetricTable.ts::METRIC_PRESETS` | MODIFY | wird aus dem JSON-Import abgeleitet (`Partial<Record<AlertMetric, number>>` je Stufe) statt als Literal gepflegt |
| `alertMetricTable.ts::THRESHOLD_CROSSING_METRICS` | MODIFY | wird aus dem `kind`-Feld der generierten Datei abgeleitet — löst die zweite, bisher unbewachte Handkopie mit auf |
| `alertMetricTable.ts::levelToThreshold()` | UNVERÄNDERT (Signatur) | liest weiterhin `METRIC_PRESETS`; behandelt `undefined` bereits korrekt (Zeile 249) |
| `AlertMetricLevelRow.svelte`, `AlarmeTab.svelte` | UNVERÄNDERT | rendern die Schwellwert-Spalte weiterhin über `levelToThreshold()` — geteilter Pfad für Trip **und** Ortsvergleich, keine Editor-spezifische Anpassung nötig |
| `tests/tdd/test_alert_preset_table_parity.py` | NEU | Frische-Ratsche Python-Quelle ⇔ generierte Datei |
| `frontend/.../alerts-tab/__tests__/alertPresetThresholdDisplay.test.ts` | CREATE | Wirkungstest gegen die tatsächlich zurückgegebene Zeichenkette (nicht nur Dateivergleich). **Neue Datei statt Erweiterung von `alertMetricTable.test.ts`:** co-located Tests (`*.test.ts` neben der Komponente) blockiert der `edit_gate` in der RED-Phase, ein Verzeichnis `__tests__/` ist erlaubt — im Projekt etabliert (`components/shared/__tests__/`). |
| `frontend/package.json` | MODIFY | `test`-Script um `--experimental-test-module-mocks` ergänzt — ohne dieses Flag existiert `mock.module()` nicht, das der AC-9-Nachweis für `THRESHOLD_CROSSING_METRICS` braucht. Kein Verhaltenseffekt auf bestehende Tests (voller Frontend-Lauf unverändert grün). |
| `docs/adr/0045-generiertes-eingebettetes-artefakt-fuer-cross-stack-abbildung.md` | REFERENCE | liefert das Muster (aus E5), unverändert übernommen — kein neues ADR nötig |
| `docs/adr/0019-nullgradgrenze-eine-alert-metrik.md` | REFERENCE | legt die Nullgradgrenzen-Zahlen 600/400/200 bereits verbindlich fest (Punkt 4) — E4 setzt eine bestehende Entscheidung durch, entscheidet nichts neu |

## Implementation Details

### 1. Erzeuger-Skript

`scripts/generate_alert_preset_table.py` importiert `_PRESET_TABLE` aus
`src/services/alert_preset.py` und schreibt eine deterministische
JSON-Serialisierung (sortierte Schlüssel, `indent=2`, abschließender
Zeilenumbruch) nach
`frontend/src/lib/generated/alertPresetThresholds.generated.json`, Form:

```json
{
  "freezing_level": {"kind": "delta", "entspannt": 600, "standard": 400, "sensibel": 200},
  "visibility": {"kind": "threshold_crossing", "entspannt": 500, "standard": 1000, "sensibel": 3000}
}
```

Das `kind`-Feld wird mitgenommen, damit das Frontend `THRESHOLD_CROSSING_METRICS`
— heute eine zweite, unbewachte Handkopie in derselben Datei — ebenfalls
ableiten kann statt sie separat zu pflegen. Zwei Modi analog zum Vorbild aus
E5 (`scripts/generate_alert_metric_mapping.py`): `write()` (Datei schreiben)
und `check()` (nur vergleichen, gibt bei Abweichung eine Liste konkreter
Meldungen mit Größe + erwartetem/gefundenem Wert zurück statt still zu
bleiben) — Grundlage der Frische-Ratsche.

**Nur eine physische Datei** (anders als bei E5): keine Go-Seite, also keine
`go:embed`-Verzeichnis-Restriktion, die eine zweite Kopie erzwingen würde.

### 2. Frontend: Ableitung statt Literal

`alertMetricTable.ts` importiert die generierte Datei und leitet
`METRIC_PRESETS` sowie `THRESHOLD_CROSSING_METRICS` daraus ab:

```ts
import rawPresets from '$lib/generated/alertPresetThresholds.generated.json';

type GeneratedPresetEntry = { kind: 'delta' | 'threshold_crossing'; entspannt: number; standard: number; sensibel: number };
const _RAW = rawPresets as Record<string, GeneratedPresetEntry>;

export const METRIC_PRESETS: Record<PresetName, Partial<Record<AlertMetric, number>> | null> = {
	deaktiviert: null,
	entspannt: Object.fromEntries(Object.entries(_RAW).map(([m, v]) => [m, v.entspannt])),
	standard: Object.fromEntries(Object.entries(_RAW).map(([m, v]) => [m, v.standard])),
	sensibel: Object.fromEntries(Object.entries(_RAW).map(([m, v]) => [m, v.sensibel])),
};

export const THRESHOLD_CROSSING_METRICS: ReadonlySet<AlertMetric> = new Set(
	Object.entries(_RAW).filter(([, v]) => v.kind === 'threshold_crossing').map(([m]) => m as AlertMetric),
);
```

**Typbruch beachten:** `Record<AlertMetric, number>` verlangt alle 14
Schlüssel, die Backend-Tabelle liefert 12 (kein `snow_line`, kein
`humidity` — beide sind seit ADR-0019/#889 tot bzw. abgeschafft). Der Typ
wird deshalb auf `Partial<Record<AlertMetric, number>>` geändert;
`levelToThreshold()` behandelt einen fehlenden Schlüssel bereits korrekt
(gibt `null` zurück, Zeile 249) — keine Signaturänderung nötig.

`METRIC_DEFAULTS` (drittes, unabhängiges Zahlen-Set mit anderem Zweck —
Fallback ohne Preset im toten Alt-Editor) bleibt unangetastet, siehe Known
Limitations.

### 3. Frische-Ratsche

`tests/tdd/test_alert_preset_table_parity.py` (Kernschicht, kein Netz) ruft
`scripts/generate_alert_preset_table.check()` direkt auf: frisch aus
`_PRESET_TABLE` berechnete Abbildung gegen die eingecheckte generierte Datei,
Abweichung je Größe konkret benannt (analog zu
`test_alert_metric_mapping_parity.py` aus E5). Anders als bei E5 gibt es
hier **keine** TS-seitigen benannten Ausnahmen zu prüfen — `METRIC_PRESETS`
und `THRESHOLD_CROSSING_METRICS` werden vollständig und ohne Filter aus der
generierten Datei abgeleitet.

Diese Prüfung allein fängt aber **nicht**, wenn das Frontend die Ableitung
gar nicht nutzt (z. B. versehentlich wieder auf ein festes Literal
zurückgebaut wird) — die generierte Datei selbst bliebe dabei korrekt. Dafür
ist zusätzlich ein Wirkungstest in `__tests__/alertPresetThresholdDisplay.test.ts` Pflicht, der
die tatsächlich von `levelToThreshold()` zurückgegebene Zeichenkette prüft
(`levelToThreshold('freezing_level', 'standard') === 'Δ ≥ 400 m'`), nicht
nur Dateien gegeneinander vergleicht.

## Expected Behavior

- **Input:** Ein Entwickler ändert einen Schwellwert in `_PRESET_TABLE`
  (`src/services/alert_preset.py`) und führt
  `scripts/generate_alert_preset_table.py` aus.
- **Output:** Die generierte JSON-Datei wird aktualisiert und eingecheckt;
  beim nächsten Vite-Build übernimmt das Frontend den neuen Wert ohne
  Codeänderung an `alertMetricTable.ts`. Vergisst der Entwickler den
  Skriptlauf, meldet die Frische-Ratsche die Abweichung konkret.
- **Side effects:** Die Nullgradgrenzen-Anzeige ändert sich sichtbar (von
  „Δ ≥ 200 m" auf „Δ ≥ 400 m" bei Standard, entsprechend bei den anderen
  Stufen) — das ist der beabsichtigte Fix von Fund 1, keine neue
  PO-Entscheidung (ADR-0019 legt die Zahl bereits fest). Alle zwölf
  übrigen Backend-Größen bleiben zahlenmäßig unverändert. Das
  Alarmverhalten selbst (welche Regel bei welchem Wert tatsächlich feuert)
  ändert sich nicht — `alert_preset.py` bleibt bis auf eine
  Docstring-Ergänzung unverändert, `expand_preset()`/
  `expand_per_metric_levels()` sind nicht betroffen.

## Acceptance Criteria

- **AC-1:** Given die Nullgradgrenze ist im Backend mit den Schwellen
  600/400/200 Metern hinterlegt (ADR-0019) / When ein Nutzer im
  Trip-Editor den Alarme-Reiter öffnet und bei der Zeile „Nullgradgrenze"
  die Stufe „Standard" gewählt ist / Then zeigt die Schwellwert-Spalte
  „Δ ≥ 400 m" — nicht mehr das bisherige, falsche „Δ ≥ 200 m".
  - Test: `__tests__/alertPresetThresholdDisplay.test.ts` prüft
    `levelToThreshold('freezing_level', 'standard') === 'Δ ≥ 400 m'`.

- **AC-2:** Given dieselbe Zeile „Nullgradgrenze" / When die Stufen
  „Entspannt" bzw. „Sensibel" gewählt sind / Then zeigt die
  Schwellwert-Spalte „Δ ≥ 600 m" bzw. „Δ ≥ 200 m" — alle drei Stufen
  stimmen mit dem tatsächlich wirksamen Backend-Wert überein.
  - Test: `__tests__/alertPresetThresholdDisplay.test.ts`, je ein Fall pro Stufe.

- **AC-3:** Given ein Nutzer hat die Nullgradgrenze sowohl in einem Trip
  als auch in einem Orts-Vergleich als Alarm eingestellt / When er den
  Alarme-Reiter beider Editoren nacheinander öffnet, Stufe Standard /
  Then steht an beiden Stellen derselbe Text „Δ ≥ 400 m" — die Anzeige
  unterscheidet sich nicht danach, aus welchem Editor man sie ansieht.
  - Test: Staging-Verifikation — Screenshot des Alarme-Reiters im
    Ortsvergleichs-Editor mit der Zeile „Nullgradgrenze" auf Standard.

- **AC-4 (Verhaltensneutralität):** Given die zwölf übrigen
  Backend-Größen (Windböen, Regenmenge, Gewitter, Temperatur-Minimum/
  -Maximum/-Wechsel, Windwechsel, Regenmengen-Wechsel, Neuschnee,
  Gewitterpotenzial, Sichtweite) / When ihre Schwellwerte nach der
  Zusammenführung im Alarme-Reiter angezeigt werden / Then bleiben alle
  Zahlen exakt wie vorher — z. B. Windböen weiterhin „Δ ≥ 20 km/h" bei
  Standard, Regenmenge „Δ ≥ 10 mm" — kein einziger Wert weicht ab.
  - Test: `tests/tdd/test_alert_preset_table_parity.py` vergleicht alle
    zwölf Größen × drei Stufen automatisiert gegen `_PRESET_TABLE`.

- **AC-5:** Given ein bestehender Trip mit eingestellten Alarmen / When
  er nach der Umstellung gespeichert wird / Then entstehen exakt
  dieselben Alarmregeln wie vorher — gleiche Größen, gleiche Schwellen,
  gleiche Anzahl. Es ändert sich allein, was der Nutzer liest, nicht
  wann ein Alarm ausgelöst wird.
  - Test: bestehende Backend-Tests für `expand_preset()`/
    `expand_per_metric_levels()`, unverändert grün (`alert_preset.py`
    selbst bleibt bis auf die Docstring-Ergänzung unangetastet).

- **AC-6:** Given die Sichtweite ist die einzige Größe, die bei
  Unterschreiten eines Wertes warnt statt bei einer Änderung / When ihre
  Zeile im Alarme-Reiter auf Stufe Standard angezeigt wird / Then steht
  dort weiterhin „< 1000 m" und nicht „Δ ≥ 1000 m" — die Unterscheidung
  zwischen beiden Warnarten geht bei der Zusammenführung nicht verloren.
  - Test: `__tests__/alertPresetThresholdDisplay.test.ts` (muss nach der
    Umstellung auf Ableitung weiterhin grün bleiben).

- **AC-7 (Mutations-Gegenprobe, PFLICHT — Drift wird benannt):** Given
  die generierte Datei wird lokal (nicht committet) von Hand verfälscht
  (z. B. Windböen-Standard 20→21) ODER die Backend-Tabelle wird geändert,
  ohne das Erzeuger-Skript erneut laufen zu lassen / When die
  Frische-Ratsche läuft / Then schlägt sie fehl und benennt die betroffene
  Größe mit erwartetem und gefundenem Wert — kein stilles Grün.
  - Test: `tests/tdd/test_alert_preset_table_parity.py`, protokollierter
    Nachweis (Mutation setzen → Test rot mit benanntem Wert → Mutation
    zurücknehmen → Test wieder grün), Protokollpflicht analog
    `fix_1435_e5_alert_mapping_unify.md` Abschnitt
    „Wirksamkeitsnachweis der Ratsche".

- **AC-8 (fehlende Größe wird nicht übersehen):** Given eine ganze Zeile
  (z. B. Sichtweite) wird aus der Backend-Tabelle `_PRESET_TABLE`
  gelöscht, ohne die generierte Datei neu zu erzeugen / When die
  Frische-Ratsche läuft / Then meldet sie die fehlende Größe ausdrücklich
  als „fehlt", statt stillschweigend grün zu bleiben — die Prüfung
  iteriert über die Schlüssel BEIDER Seiten, nicht nur einer.
  - Test: derselbe Wächter-Test, zusätzlicher Fall „Zeile komplett aus
    der Quelle entfernt".

- **AC-9 (die entscheidende Mutation — Ableitung wird wirklich genutzt):**
  Given die Ableitung in `alertMetricTable.ts` wird versuchsweise durch
  ein festes Literal ersetzt, während die generierte Datei unverändert
  korrekt bleibt / When die Frontend-Tests laufen / Then wird mindestens
  ein Test rot, weil er die tatsächlich von `levelToThreshold()`
  zurückgegebene Zeichenkette prüft — nicht nur, ob die generierte Datei
  zur Backend-Tabelle passt (das würde bei diesem Fehler weiterhin grün
  bleiben, da nur der Frontend-Konsument die Ableitung ignoriert).
  - Test: `__tests__/alertPresetThresholdDisplay.test.ts`, Wirkungstest gegen die exportierte
    Funktion (kein Dateiinhalt-Check).

## Known Limitations

- **`thunder_level` zeigt bei allen drei Stufen „Δ ≥ 1"**, obwohl seit
  #1460 die Niveau-Grenzen (`ORDINAL_LEVEL_BOUNDS`) entscheiden, nicht die
  Sprunggröße. Zweiter Anzeigefehler derselben Art wie Fund 1 (Anzeige
  widerspricht Wirkung), aber andere Fragestellung — braucht eine eigene
  Wortlaut-Entscheidung und eigene Scheibe. Wird durch E4 nicht behoben.
- **`METRIC_DEFAULTS` + `AlertMetricTable.svelte`/`AlertMetricRow.svelte`**
  (toter Alt-Editor, nirgends importiert außer einem Kommentar-Verweis)
  bleiben unverändert. Eine Löschung wäre Aufräumen, kein
  Zusammenführungsziel — es gibt kein Backend-Gegenstück, das man
  konsolidieren könnte.
- **Go-seitiges `AlertableMetrics`** bleibt ein separates, unverändertes
  Vokabular — offene Restlücke aus E5, durch E4 nicht angefasst.
- **Die Geisterzeile Luftfeuchtigkeit im Trip-Editor** (Fund 2: ein Trip
  mit alt-persistiertem `humidity`-Schlüssel zeigt im Trip-Pfad eine
  Zeile, die nie einen Alarm auslöst, weil der Trip-Pfad — anders als der
  Ortsvergleichs-Pfad — nicht gegen den Katalog filtert) wird **nicht**
  in dieser Scheibe behoben (PO-Entscheid 2026-08-06, eigenes Ticket:
  anderer Fehlertyp — fehlende Filterung, nicht die Zahlentabelle — und
  es fehlt noch die Messung, wie viele Trips überhaupt betroffen sind).
  **Nebenwirkung dieser Scheibe, kein Fix:** Da `_PRESET_TABLE` seit
  #889/ADR-0010 keinen `humidity`-Eintrag mehr führt, zeigt eine solche
  Geisterzeile nach E4 einen Gedankenstrich „—" statt der bisherigen,
  irreführenden festen Zahl „Δ ≥ 15 %" — die Zeile selbst bleibt
  unverändert sichtbar, nur ihr (ohnehin falscher) Zahlenwert verschwindet.
  Das ist eine zulässige Nebenwirkung der Quellzusammenführung, kein
  eigenständiges Kriterium dieser Spec.

## Wirksamkeitsnachweis der Ratsche

Analog zur Erfahrung aus E3a/E5 gilt die Frische-Ratsche aus AC-7/AC-8 erst
als geliefert, wenn folgender Nachweis erbracht und im PR/Commit
protokolliert ist:

1. Ein Schwellwert (z. B. Windböen-Standard) wird in einer lokalen, nicht
   committeten Kopie der generierten Datei verfälscht, ohne die
   Python-Quelle zu ändern.
2. Die Frische-Ratsche wird gegen diesen Zustand ausgeführt; Ausgabe
   protokollieren — muss (a) fehlschlagen, (b) die betroffene Größe mit
   erwartetem und gefundenem Wert benennen.
3. Zweiter Durchlauf: die Backend-Tabelle wird lokal geändert (z. B. eine
   Zeile entfernt), ohne das Erzeuger-Skript laufen zu lassen — derselbe
   Nachweis (a)/(b) inkl. „fehlt"-Meldung.
4. Dritter Durchlauf: die Ableitung in `alertMetricTable.ts` wird lokal
   durch ein festes Literal ersetzt, die generierte Datei bleibt korrekt —
   der Frontend-Wirkungstest (AC-9) muss rot werden, die Frische-Ratsche
   (Python ⇔ Datei) darf dabei grün bleiben (sie prüft eine andere Naht).
5. Alle drei Verfälschungen werden danach zurückgenommen; regulärer Code
   läuft wieder vollständig grün.

Ohne diesen protokollierten Nachweis gilt die Ratsche als nicht abgenommen,
unabhängig davon, ob sie „grün" ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0045 (aus E5) deckt das Muster
  (generiertes, eingecheckt zwischenges Artefakt statt Laufzeit-Kopplung
  oder Handkopie), ADR-0019 legt die Nullgradgrenzen-Zahlen bereits fest.
- **Rationale:** E4 ist strukturell derselbe Fall wie E5 (Cross-Stack-
  Duplikat, eine Seite soll Quelle werden), nur ohne Go-Seite und damit
  einfacher (eine statt zwei generierte Dateien). Ein zweites ADR für
  dasselbe Muster würde Regel 3 aus ADR-0015 nicht neu begründen, sondern
  nur wiederholen — ADR-0045 selbst benennt dieses Muster bereits als
  Vorbild für strukturell ähnliche Fälle. Die Nullgradgrenzen-Zahlen
  600/400/200 sind keine neue Entscheidung: ADR-0019 Punkt 4 legt sie für
  die konsolidierte Metrik ausdrücklich fest: „die bisher tatsächlich
  wirksamen `snow_line`-Werte" — E4 setzt diese Entscheidung durch,
  entscheidet nichts neu.

## Changelog

- 2026-08-06: Initial spec created. Umfang, Randbedingungen und
  PO-Entscheidung aus `docs/context/fix-1435-e4-schwellwert-quelle.md`
  übernommen. Fundstellen (Python, TS) gegen den aktuellen Code-Stand neu
  verifiziert (Zeilennummern in `alertMetricTable.ts` und `alert_preset.py`
  aktualisiert). Vorbild-Muster (Erzeuger-Skript, Frische-Ratsche,
  Wirksamkeitsnachweis-Protokoll) aus `fix_1435_e5_alert_mapping_unify.md`
  übernommen und auf den Ein-Datei-Fall (keine Go-Seite) zugeschnitten.
