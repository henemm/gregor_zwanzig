---
entity_id: i18n_g5_ratsche_go_2679
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2679, go, docs, model-haiku]
---

# i18n G5: Ratsche Go — Test blockt neue hartkodierte Nutzertexte in der Go-API

**Issue:** #2679 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2 (Allowlists) und 5 (Ratsche Go)

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer künftig in einem Go-Handler, einer Middleware, im Resolver oder in einer Mail einen deutschen Nutzertext direkt in den Code schreibt, bekommt einen roten Test mit Datei und Zeile, statt dass der Text still an der englischen Sprachfassung vorbeigeht. Der Test (`go/parser`) startet sofort nach G1 mit einer Allowlist, die alle heutigen Fundstellen enthält, und wird von den Paketen G2 bis G4 Eintrag für Eintrag leergeräumt. Protokolltext, Logzeilen und Betreiber-Mails sind ausgenommen.

## Source

- **File:** `internal/i18n/hardcode_guard_test.go` (neu), `internal/i18n/hardcode_allowlist.json` (neu), `docs/reference/gates_und_ratschen.md`
- **Identifier:** `TestKeineHartkodiertenNutzertexte`, `TestAllowlistHatKeineVeralteten`, `TestWaechterErkenntNeueTexte`, `scanSource`

> **Schicht-Hinweis:** Reiner Go-Test im Paket `internal/i18n`, plus eine Doku-Zeile. Kein Produktionscode, kein Python, kein Frontend. Name und Ort der Testdatei sind in den Konventionen (Abschnitt 5) festgelegt; sie ist ein Ratschentest (`// doc-compliance-test`), kein Verhaltenstest.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht betroffen; der Wächter prüft alle Dateien gleich, es gibt kein Trip- oder Compare-Pendant.
> - **Mandantentrennung:** nicht betroffen; der Test liest nur Quelltext, keine Nutzerdaten.
> - **Kanäle:** nicht betroffen; geprüft wird Go-Code für HTTP-Antworten und Konto-Mails. Briefing- und Alarm-Inhalte der Kanäle E-Mail, Telegram, SMS und Premium-SMS entstehen in Python (Ratsche P11, #2674).

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `internal/i18n/hardcode_guard_test.go` | CREATE | Wächter: `scanSource`, drei Testfunktionen, Ausgabe des Startstands über `GZ_I18N_GUARD_PRINT=1` |
| `internal/i18n/hardcode_allowlist.json` | CREATE | JSON-Liste von Pfad-Präfixen relativ zur Repo-Wurzel; Startstand = alle heutigen Fundstellen; Endstand `[]` |
| `docs/reference/gates_und_ratschen.md` | MODIFY | eine Zeile in der Tabelle „Regel-Budget: Prüfdaten im Überblick" (Prüfdatum 2027-01-28) |

## Estimated Scope

- **LoC:** ca. 130 Zeilen Testcode, ca. 15 Zeilen JSON, 1 Doku-Zeile. Unter dem Limit von 250.
- **Files:** 3
- **Effort:** low bis medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2675 (G1) | Paket | legt `internal/i18n` an (Voraussetzung); G5 Teil 1 startet direkt nach dem Merge von G1 |
| #2676 (G2), #2677 (G3), #2678 (G4) | Pakete | entfernen ihre Allowlist-Einträge; G5 Teil 2 nach G4 |
| `go/parser`, `go/ast`, `go/token` | Standardbibliothek | Quelltext-Analyse, keine neue Abhängigkeit |
| `docs/reference/gates_und_ratschen.md` | Doku | Regel-Budget-Tabelle |
| ADR-0104 | ADR | Ratschen je Schicht, Allowlists nur schrumpfend |

## Implementation Details

**Ablauf: zwei Teile, ein Issue.** *Teil 1* ist ein eigener Workflow (eigener Branch und PR) unmittelbar nach dem Merge von G1: Test, Allowlist mit **vollem** Startstand und Doku-Zeile in zwei Commits (Test+Allowlist, dann Doku). *Teil 2* ist eine Abnahme nach G4: Allowlist ist `[]`, der Doku-Eintrag nennt „Endstand leer", Issue #2679 wird geschlossen. G2 bis G4 entfernen ihre Einträge selbst; der Veraltet-Test erzwingt das.

**Gescannt wird** (rekursiv, ohne `_test.go` und ohne Verzeichnisse `testdata`): `internal/handler`, `internal/mail`, `internal/notify`, `internal/store`, `internal/middleware`, `internal/resolver`. Die Wurzel wird relativ zur Testdatei aufgelöst (`runtime.Caller(0)`, zwei Ebenen nach oben), nie über das Arbeitsverzeichnis.

**Was als Befund zählt.** Jedes String-Literal (`*ast.BasicLit` mit `token.STRING`, auch Raw-Strings), nachdem es mit `strconv.Unquote` aufgelöst wurde, das mindestens einen dieser Treffer enthält:

1. einen Umlaut oder `ß` (`[äöüÄÖÜß]`),
2. eine HTML-Entity `&auml;`, `&ouml;`, `&uuml;`, `&Auml;`, `&Ouml;`, `&Uuml;`, `&szlig;`,
3. ein deutsches Signalwort ohne Umlaut, groß-/kleinschreibungsunabhängig und als ganzes Wort (`(?i)\b(nicht|fehlt|bitte|hallo|ignoriere|bestaetig\w*|zurueck\w*|abgelaufen|fehlgeschlagen)\b`). Dieser dritte Treffer fängt die Mail-Texte in ae/ue-Umschrift („Bitte bestaetige …"), die der Umlaut-Test allein übersieht.

**Was nicht zählt (Ausnahmen).**
- Literale, die (auch tief verschachtelt) Argument eines Aufrufs von `log.*`, `slog.*`, `fmt.Errorf` oder `errors.New` sind. Das ist die statisch entscheidbare Form der Konventions-Regel „`fmt.Errorf` nur wenn in Response geschrieben": Fehlertexte, die ein Handler an den Client durchreicht, müssen über `WriteError`/Katalog laufen.
- Literale in Struct-Tags (`ast.Field.Tag`) und Importpfade.
- Literale in einer Zeile mit dem Kommentar `// i18n-log`, in der Zeile direkt darunter oder in einer Funktion, deren Doc-Kommentar `// i18n-log` enthält (so wird die deutsche Betreiber-Mail `BuildTierChangeRequestMail` als Ganzes ausgenommen).
- Kommentare und Docstrings (sind keine Literale).

**Struktur des Tests (Grundgerüst).**

```go
// doc-compliance-test: Ratsche, kein Verhaltenstest.
type finding struct{ File string; Line int; Text string }
func scanSource(filename string, src []byte) ([]finding, error) // parser.ParseComments, ast.Inspect mit Vorfahren-Stack
func scanRepo(t *testing.T) []finding                           // WalkDir ueber die sechs Verzeichnisse
func loadAllowlist(t *testing.T) []string                       // hardcode_allowlist.json: JSON-Array von Pfad-Praefixen
```

- `TestKeineHartkodiertenNutzertexte`: jeder Befund, dessen Dateipfad (relativ, mit `/`) mit **keinem** Allowlist-Präfix beginnt, lässt den Test scheitern; die Meldung listet `datei:zeile: "text"`.
- `TestAllowlistHatKeineVeralteten`: jeder Allowlist-Eintrag muss mindestens einen Befund abdecken, sonst scheitert der Test mit „Eintrag veraltet, bitte entfernen: <präfix>". Das macht aus der Allowlist eine echte Ratsche (nur schrumpfend).
- `TestWaechterErkenntNeueTexte`: Selbsttest ohne Dateisystem. `scanSource` wird mit kleinen Quelltext-Schnipseln aufgerufen: `http.Error(w, "Nicht gefunden", 404)` ergibt einen Befund mit Zeile; `log.Printf("Datei nicht gefunden")` keinen; derselbe Aufruf mit `// i18n-log` keinen; `"Bitte bestaetige deine Adresse"` einen; `"Hallo,&nbsp;f&uuml;r dich"` einen; ein Literal in einer Funktion mit `// i18n-log` im Doc-Kommentar keinen; ein Struct-Tag mit `json:"fehlt"` keinen; `errors.New("Datei fehlt")` keinen.
- Startstand ermitteln: Läuft der Test mit gesetzter Umgebungsvariable `GZ_I18N_GUARD_PRINT=1`, loggt er (`t.Logf`) die sortierte, eindeutige Dateiliste der Befunde als JSON-Array. Diese Ausgabe wird einmalig in `hardcode_allowlist.json` übernommen; der Test schreibt nie selbst in das Repo.

**Erwarteter Startstand** (maßgeblich ist der tatsächliche Lauf; Grundlage ist `grep` auf Umlaute und Signalwörter am 2026-10-30): `internal/handler/briefing_send.go`, `trip.go`, `quota.go`, `etag.go`, `schreibsperre.go`, `location_resolve.go`, `account_delete_code.go`, `auth_oauth.go`; `internal/resolver/` (vier Dateien); `internal/mail/` (`verify.go`, `reset.go`, `magic.go`, `tier_change.go`). Aufteilung nach Paketen: G3 entfernt `briefing_send.go`, `trip.go`, `quota.go`, `etag.go`, `schreibsperre.go`, `location_resolve.go` und `internal/resolver/`; G4 entfernt `internal/mail/`, `account_delete_code.go`, `auth_oauth.go`. G2 entfernt keinen Eintrag.

**Doku-Zeile** in `docs/reference/gates_und_ratschen.md`, Tabelle „Regel-Budget: Prüfdaten im Überblick": `| i18n-Ratsche Go (`internal/i18n/hardcode_guard_test.go`, Allowlist `internal/i18n/hardcode_allowlist.json`, #2679) | 2027-01-28 | Startstand = alle Fundstellen vom Tag der Einführung; Endstand leer nach G2 bis G4 (Epic #2644) |`.

**Allowlist-Eintrag, der entfernt wird:** keiner in diesem Paket (es legt die Liste an); der Endstand `[]` ist Gegenstand von Teil 2.

## Expected Behavior

- **Input:** Quelltext der sechs gescannten Verzeichnisse und `hardcode_allowlist.json`.
- **Output:** grüner Test, solange jede Fundstelle durch die Allowlist, `// i18n-log` oder eine Ausnahme-Regel gedeckt ist und jeder Allowlist-Eintrag noch eine Fundstelle hat; sonst roter Test mit Datei:Zeile bzw. Eintragsname.
- **Side effects:** keine; der Test liest nur.

## Acceptance Criteria

- **AC-1:** Given ein Entwickler schreibt neu `http.Error(w, "Nicht gefunden", 404)` in einen Handler / When `go test ./internal/i18n/...` läuft / Then ist der Test rot und nennt Datei und Zeile der Stelle.
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — `TestWaechterErkenntNeueTexte` ruft `scanSource` mit genau diesem Quelltext auf und erwartet einen Befund mit der richtigen Zeile; zusätzlich Mutationsprobe: Unterbinden der Literalprüfung lässt den Selbsttest rot werden.

- **AC-2:** Given `log.Printf("Datei nicht gefunden")`, dieselbe Zeile mit `// i18n-log`, `errors.New("Datei fehlt")` und eine Betreiber-Funktion mit `// i18n-log` im Doc-Kommentar / When der Wächter sie prüft / Then bleibt der Test grün, weil Logs, Fehlerwerte und markierte Betreiber-Texte keine Nutzertexte sind.
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — `TestWaechterErkenntNeueTexte`, Fälle ohne erwarteten Befund.

- **AC-3:** Given ein Mail-Text in ae/ue-Umschrift („Bitte bestaetige deine Adresse") und ein HTML-Text mit Entity („f&uuml;r") / When der Wächter sie prüft / Then meldet er beide, während Struct-Tags und Importpfade nie gemeldet werden.
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — Schnipsel-Fälle in `TestWaechterErkenntNeueTexte`.

- **AC-4:** Given die Allowlist mit dem Startstand / When `go test ./internal/i18n/...` direkt nach der Einführung läuft / Then ist der Test grün, und ein zusätzlich eingetragener Präfix ohne Fundstelle (oder ein Eintrag, dessen Datei inzwischen umgestellt wurde) macht ihn rot mit der Meldung „Eintrag veraltet".
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — `TestKeineHartkodiertenNutzertexte` und `TestAllowlistHatKeineVeralteten` gegen das echte Repo; der Veraltet-Fall wird in einem Hilfsaufruf mit künstlicher Allowlist geprüft.

- **AC-5:** Given die Pakete G2, G3 und G4 sind gemergt / When Teil 2 abgenommen wird / Then enthält `hardcode_allowlist.json` nur `[]`, der Wächter ist grün, und die Doku-Zeile nennt den leeren Endstand.
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — unveränderter Lauf mit leerer Allowlist; Abnahme-Schritt im Workflow von Teil 2.

- **AC-6:** Given die Verzeichnisse `internal/handler`, `internal/mail`, `internal/notify`, `internal/store`, `internal/middleware`, `internal/resolver` / When der Wächter läuft / Then liest er Quelltext relativ zur Testdatei (auch bei Aufruf aus einem anderen Arbeitsverzeichnis) und ignoriert `_test.go`-Dateien und `testdata`-Ordner.
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — Lauf mit `go test ./...` aus der Repo-Wurzel und mit `-C internal/i18n`; Befundliste enthält keine `_test.go`-Pfade.

## Known Limitations

- **Annahme (`fmt.Errorf`):** Die Konventionen nehmen `fmt.Errorf` nur dann auf, wenn der Fehler in die Antwort geschrieben wird. Das ist statisch nicht entscheidbar; der Wächter nimmt `fmt.Errorf` und `errors.New` daher komplett aus und prüft stattdessen jedes andere Literal im Verzeichnis (strenger als die Sink-Liste der Konventionen: `http.Error`, `json`-Antworten, Mail-Bauer, Konstanten und Struct-Felder sind alle erfasst).
- **Annahme (Allowlist-Format):** JSON-Array von Pfad-Präfixen (Dateien oder Verzeichnisse mit abschließendem `/`), wie in den Konventionen („Allowlists sind JSON-Listen von Pfad-Präfixen").
- Der Wächter ist eine Heuristik: ein deutscher Satz ohne Umlaut und ohne Signalwort (z. B. „Ort mit dieser ID existiert bereits") wird nicht gefunden. Die Pakete G2 bis G4 stellen ihn trotzdem um, weil ihre Dateilisten aus der Messung aller Fehlerstellen stammen, nicht aus dem Wächter.
- `internal/scheduler` ist nicht Teil der Konventionen-Liste und wird nicht gescannt; seine deutschen Texte sind Betreiber-Meldungen.
- Maschinen-Endpunkte mit englischen Klartexten (`/api/internal/`, `/api/webhooks/`) werden vom Wächter nicht gemeldet und bleiben unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Je Schicht blockt eine Ratsche mit schrumpfender Allowlist neue hartkodierte Nutzertexte, damit die Zweisprachigkeit nicht wieder zerfällt.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
