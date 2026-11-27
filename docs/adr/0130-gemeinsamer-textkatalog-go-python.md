# ADR-0130: Gemeinsamer Textkatalog Go/Python (Bereich `geteilt`)

- **Status:** Akzeptiert (Spec freigegeben vom PO 2026-11-27)
- **Datum:** 2026-11-27
- **Bezug:** Issue #3444 (ersetzt #2993), Spec `docs/specs/modules/feat_3444_gemeinsamer_katalog.md`, Kontext `docs/context/feat-3444-gemeinsamer-katalog.md`. Schreibt fort: [ADR-0104](0104-zweisprachigkeit-de-en.md) (Zweisprachigkeit, je Schicht ein Katalog). Bezug: [ADR-0095](0095-kanal-paritaet-jeder-kanal-jede-frage.md) (Kanal-Parität). Löst keines davon ab.

## Kontext

ADR-0104 legt je Schicht einen eigenen Katalog fest (Go `internal/i18n/messages`, Python `src/i18n/messages`, Frontend). Einige Texte geben Go-API und Python-Core wortgleich aus, etwa die Fehlermeldung `kind_required` der Versand-Endpunkte: Go meldet sie vor Python selbst, Python meldet sie bei direktem Aufruf. Der Text stand deshalb zweimal (`fehler.kind_required` in Go, `versand.ergebnis.kind_required` in Python); gleich gehalten hat beide nur eine Test-Fixture. Jede Wortlaut-Änderung musste an zwei Stellen erfolgen, Drift war nur durch Tests verhindert, nicht ausgeschlossen.

## Entscheidung

1. **Ein gemeinsamer Bereich `geteilt`.** Texte, die beide Schichten wortgleich ausgeben, liegen in `src/i18n/messages/{de,en}/geteilt.json`, Schlüssel `geteilt.<gruppe>.<element>`. Sie werden **nur dort** gepflegt. Ausnahme von „je Schicht ein Katalog“ (ADR-0104) nur für diesen Bereich.
2. **Python** lädt `geteilt` wie jeden anderen Bereich (`BEREICHE` in `src/i18n/catalog.py`).
3. **Go** bettet genau diese zwei Dateien über `src/i18n/embed.go` ein (`//go:embed messages/de/geteilt.json messages/en/geteilt.json`, keine Python-Bereiche) und lädt sie zusätzlich zum eigenen Katalog (`NewCatalogFrom`). `geteilt.fehler.` gehört zur Suchkette `errorPrefixes`. Ein Wächter (`CheckNoSharedAreaInternal`, beim Start und im Test) verbietet eine `geteilt.json` unter `internal/i18n/messages`.
4. **Umzug löscht den alten Schlüssel.** Der Konventionssatz „Schlüssel werden nie umbenannt oder gelöscht“ gilt beim Umzug nach `geteilt` nicht: der alte Schlüssel wird im selben Commit entfernt (Go-`duplicateCodes` erzwingt das für Fehlercodes). Der Wortlaut bleibt byte-gleich.
5. **Erste Scheibe:** `kind_required` → `geteilt.fehler.kind_required`; `fehler.kind_required` (Go) und `versand.ergebnis.kind_required` (Python) entfallen. Die Fixture `tests/fixtures/send_detail_parity/faelle.json` bleibt als Verhaltenswächter der HTTP-Ausgabe beider Schichten.

## Verworfene Alternativen

- **Quelle unter `internal/`, Python liest mit** — der Prod-Dienst des Python-Core hat Leserechte auf `src/`, nicht verlässlich auf `internal/`.
- **Generator, der eine Datei in die andere kopiert** — zweite physische Datei, Generator-Lauf vergessen ergibt wieder Drift.
- **Weiter zwei Schlüssel mit Gleichlauf-Test** — Drift nur erkannt, nicht ausgeschlossen; jede Änderung doppelt.

## Konsequenzen

- **Positiv:** Ein Text, eine Datei je Sprache; Drift zwischen Go und Python ist für den Bereich ausgeschlossen.
- **Negativ / Preis:** `src/i18n` ist zugleich ein Go-Paket (Python ignoriert die `.go`-Datei). Der Go-Build braucht den vollen Checkout (`src/` vorhanden); ein Build aus abgeschnittenem Baum bricht ab.
- **Deploy-Kopplung:** Staging und Prod bauen Go und starten Python aus demselben Checkout bzw. Commit; beide Schichten sehen damit stets dieselbe `geteilt.json`.
- **Folgepflichten:** Radar-Intensität (`alarm.radar.intensitaet.*`) und MCP-Fehler ziehen in eigenen Issues nach `geteilt` um. Der Frontend-Katalog (`fehler.code.*`) bleibt ausgenommen.
