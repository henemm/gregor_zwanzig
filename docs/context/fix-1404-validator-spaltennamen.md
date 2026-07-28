# Context: fix-1404-validator-spaltennamen

Issue #1404 · erhoben 2026-07-28 · Vorbedingung für #1401 Scheibe A2b

## Request Summary

Der Pflicht-Validator für die Ortsvergleichs-Mail (`.claude/hooks/email_spec_validator.py`)
kennt die Spaltenüberschriften der Mail wörtlich. Sobald #1401 A2b die Beschriftungen
auf das zentrale Namensregister umstellt, lehnt der unveränderte Validator die dann
korrekte Mail ab (harter Bruch) — und ein zweiter Teil seiner Prüfung fällt schon
heute lautlos aus (stiller Bruch, Gate-Erosion).

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/email_spec_validator.py:221-223` | `_HOUR_COLUMNS_V2` — Allowlist der 10 Stundentabellen-Spalten, wörtlich |
| `.claude/hooks/email_spec_validator.py:240-246` | `_OVERVIEW_METRIC_CHECKS` — 5 Schlüssel, deutsche Labels der Übersichtstabelle |
| `.claude/hooks/email_spec_validator.py:394-400` | Verwendung `_HOUR_COLUMNS_V2` → unbekannte Spalte = Fehler → Exit 1 |
| `.claude/hooks/email_spec_validator.py:462-464, 494-496` | Verwendung `_OVERVIEW_METRIC_CHECKS` → unbekannter Schlüssel = **stilles `continue`** |
| `.claude/hooks/renderer_mail_gate.py:69-78, 458-463` | Macht den Validator zur Commit-Pflicht für `compare_html.py` **und** die drei geteilten Renderer-Helfer |
| `.claude/commands/e2e-verify.md:95-101` | Pflichtschritt 3b: „STOP wenn Validator nicht Exit 0" |
| `src/output/renderers/email/compare_html.py:233-309, 513-528` | Quelle der Beschriftungen; `_visible_metrics(None)` zeigt **alle 26** Zeilen |
| `src/app/metric_catalog.py:25-390` | Zentrales Namensregister, führt `col_label` bereits für alle A2b-Zielwerte |
| `docs/specs/modules/fix_1401_a2_mailtabellen.md` | Zielstrings für A2b (Abschnitte „Ziel-Beschriftung …", Known Limitations) |

Testdateien, die den Validator gegen echten Renderer-Output prüfen (heute grün,
18/18, gemessen):

- `tests/tdd/test_issue_1046_email_validator_table_contract.py:152-158, 229-238, 308-319`
- `tests/tdd/test_issue_1110_compare_mail_v2.py:600-612`
- `tests/unit/test_compare_mail_validator_column_order.py`

## Gemessene Ausgangslage

**Harter Bruch (`_HOUR_COLUMNS_V2`):** 6 der 9 Wertspalten hießen nach A2b anders.
`validate_structure()` meldet jede nicht gelistete Spalte als Fehler, `main()` endet
mit Exit 1. Als Pflichtteil des Renderer-Commit-Gates blockiert das jeden Commit an
`compare_html.py` **und** an `helpers.py`/`design_tokens.py`/`profile_signature.py` —
also auch Arbeiten, die nur den Trip-Pfad betreffen.

**Stiller Bruch (`_OVERVIEW_METRIC_CHECKS`):** unbekannter Schlüssel → `continue`,
ohne Fehler, ohne Log. Der Befund ist **größer als im Ticket beschrieben**: das Register
kennt 5 Labels, die Übersichtstabelle kann 26 Zeilen zeigen. **Schon heute** laufen
21 von 26 möglichen Zeilen ungeprüft durch — unabhängig von #1401.

**Reihenfolge-Falle:** Ein hartes Umstellen der Literale vor A2b bricht 18 heute grüne
Kern-Tests **beim Merge von #1404 selbst**, nicht erst bei einem A2b-Commit. Das
Blockade-Fenster ist nicht kurz: A2b liegt laut eigener Spec bei ~360-560 Zeilen und
braucht selbst noch einen Schnitt oder eine angehobene Grenze.

**Nebenbefund:** `src/output/renderers/comparison.py` (Klartext-Zwilling, Ziel von
A2b) matcht **kein** `_MAIL_PATTERNS` — Änderungen dort allein lösen das
Renderer-Gate gar nicht aus. Unabhängig von #1404, gehört in die Gate-Sammelstelle.

## Existing Patterns

- `_OVERVIEW_WARN_LABEL` ist bereits eine explizite „diese Zeile braucht keinen
  Format-Check"-Ausnahme — das Muster für eine bewusste Nicht-Prüfung existiert
  also schon und muss nicht erfunden werden.
- Drift dieses Validators nach Renderer-Umbauten ist wiederkehrend: #1106, #1046,
  #1110, #1150, #1381, jetzt #1404.

## Dependencies

- **Upstream:** `src/app/metric_catalog.py` (`col_label`) — mögliche Ableitungsquelle
- **Downstream:** `renderer_mail_gate.py` (Commit-Gate), `/e2e-verify` Schritt 3b,
  die vier oben genannten Testdateien

## Existing Specs

- `docs/specs/modules/fix_1401_a2_mailtabellen.md` — liefert die Zielstrings
- `docs/reference/mail_validators.md` — beschreibt Dispatch und Pflichtcharakter

## Risks & Considerations

- **Selbstblockade:** Validator vor der Mail umstellen sperrt die eigene Werkbank.
- **Specification Gaming:** Würde der Validator die Zeilen-/`metric_id`-Menge aus
  `compare_html.py` beziehen, prüfte er dieselbe Quelle, die er absichern soll —
  Präzedenzfall #1110/#1108, im Ticket selbst benannt.
- **Gold-Standard-Anspruch:** Das Ticket verlangt, dass der angepasste Validator die
  alte Struktur **ablehnt**. Eine dauerhafte Union aus alten und neuen Namen
  widerspricht dem; ein Übergang mit dokumentiertem Rückbau nicht.
- **Härtung ist nicht gratis:** „unbekannter Schlüssel = lauter Befund" bricht sofort,
  solange nur 5 von 26 Labels hinterlegt sind — die restlichen 21 brauchen erst
  einen Eintrag oder eine bewusste Ausnahme.

## Analysis

### Type

Bug (Label `bug`, `area:compare`). Zwei Fehlerbilder in einer Datei: ein harter,
noch nicht eingetretener Bruch und ein stiller, bereits produktiver Ausfall.

### Reihenfolge — geprüft und entschieden

„#1404 nach A2b liefern" ist **keine Alternative, sondern strukturell ausgeschlossen**:
`renderer_mail_gate.py:69-71, 458-463` verlangt für jeden Commit an `compare_html.py`
einen frischen, bestandenen Validator-Lauf, und `docs/reference/mail_validators.md`
hält fest: kein globaler/ENV-Bypass. A2b könnte seinen eigenen Commit also gar nicht
abschließen, solange der Validator die neue Mail ablehnt.

„Hart umstellen, kurz vor A2b" scheidet ebenfalls aus: gemessen 73 grüne Assertions in
7 Testdateien würden **beim Merge von #1404 selbst** rot, für unbestimmte Dauer (A2b
ist selbst noch schnittpflichtig). „Vorübergehend rot" ist im Projekt keine zulässige
Zwischenstufe.

Drei weitere Wege wurden geprüft und verworfen: reiner Struktur-Check ohne Namensliste
(gibt den Gold-Standard-Anspruch dauerhaft auf), Ableitung der Erlaubt-Menge aus
`compare_html.py` (Specification Gaming, Präzedenzfall #1110/#1108), Validator-Änderung
innerhalb des A2b-Workflows (Projektkonvention verbietet es — der Grund für dieses
eigene Ticket).

**Ergebnis:** Die Übergangs-Union (alt ∪ neu, strikt additiv, mit dokumentiertem
Rückbau und Prüfdatum) ist der einzige Weg, der A2b nicht blockiert, die Kern-Tests
jederzeit grün hält und keine der verbotenen Abkürzungen nimmt.

### Neuer Befund: die Verschärfung würde A2b selbst blockieren

Das Ticket nennt „unbekannter Schlüssel = lauter Befund" den eigentlichen
Härtungsgewinn. Die Bewertung zeigt: scharfgeschaltet **jetzt** macht sie A2b zum
harten Blocker, weil A2b **alle 26** Übersichts-Beschriftungen ändert. Ein
vorbeugendes Eintragen der A2b-Ziel-Labels hilft nur begrenzt, weil deren
Kollisions-Zusatz auswahlabhängig ist („Temp" **oder** „Temp max"/„Temp min", je
nachdem was gleichzeitig sichtbar ist) — der Validator müsste dieselbe Fragilität
nachbauen, die #1381 gerade erst behoben hat. Zudem listet die A2-Spec Umbenennungen
nur für die 5 heute geprüften Schlüssel, nicht für die 21 neu hinzukommenden.

**Weiterer gemessener Fallstrick:** Die Warn-Zeile („Amtliche Warnungen") läuft heute
selbst durch den stillen `continue`-Pfad (`email_spec_validator.py:462-464, 494-496`;
die Schleife beginnt bei `rows[1:]`, schließt die Warn-Zeile also ein). Ein
Scharfschalten ohne ausdrückliche Ausnahme für sie würde bei **jeder** Vergleichsmail
sofort einen neuen Fehler erzeugen.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `.claude/hooks/email_spec_validator.py` | MODIFY | `_HOUR_COLUMNS_V2` als Übergangs-Union; `_OVERVIEW_METRIC_CHECKS` von 5 auf 24 heutige Labels; ausdrückliche „keine Prüfung nötig"-Menge (Warn-Zeile + 2 kategoriale) |
| Testdatei (neu) | CREATE | Vorwärts-Nachweis: Validator akzeptiert die A2b-Zielstruktur; Rückwärts-Nachweis: eine erfundene Spalte wird weiterhin abgelehnt |
| Testdatei(en) bestehend | MODIFY | Abdeckungsfälle für die 19 neu geprüften Übersichtszeilen |

### Scope Assessment

- Dateien: 1 Produktivdatei + 1-2 Testdateien
- Geschätzt: Teil 1 ~45-75 Zeilen, Teil 2a ~80-140 Zeilen → **~125-215 Zeilen**, unter
  dem Deckel. Mit der Verschärfung (Teil 2b) käme man auf ~225-365 und darüber.
- Risiko: MITTEL — die Änderung ist strikt additiv (Rückweg = einfaches Zurücknehmen),
  aber sie fasst ein Pflicht-Gate an.

### Technical Approach (Empfehlung)

Zwei Teile jetzt, einer später:

1. **`_HOUR_COLUMNS_V2` als Übergangs-Union** — 10 alte + 6 tatsächlich neue Spalten
   (Zeit/Temp/Wind/UV heißen in beiden Fassungen gleich). Ausdrücklich als temporär
   markiert, mit Prüfdatum (Vorbild: `nebenbefund_gate.py:21`) und Rückbau-Auftrag
   nach A2b.
2. **`_OVERVIEW_METRIC_CHECKS` von 5 auf 24 heutige Labels erweitern** — schließt die
   Lücke, die schon heute 21 von 26 Zeilen ungeprüft lässt. Nutzt ausschließlich
   heutige Beschriftungen, hat also keine A2b-Kopplung. Dazu eine ausdrückliche
   „hier ist keine Prüfung nötig"-Menge für die Warn-Zeile und die zwei kategorialen
   Zeilen (Gewitter, Niederschlagsart), nach dem im Code bereits vorhandenen Vorbild
   `_OVERVIEW_WARN_LABEL`.
3. **Verschiebung:** „unbekannter Schlüssel = lauter Befund" wandert in ein
   Folge-Ticket, das zusammen mit dem Rückbau nach A2b läuft. Begründung oben.

### Open Questions

- [ ] PO-Freigabe der ACs (Pflicht in `/30-write-spec`), insbesondere der Verzicht auf
      die sofortige Verschärfung — das Ticket hatte sie als Hauptgewinn benannt.
- [ ] Wertebereiche der 19 neuen Zeilen sind physikalisch plausibel geschätzt, nicht
      gegen historische Wetterdaten belegt. Für einen Plausibilitäts-Check ist das
      vertretbar, gehört aber in die Spec als bekannte Grenze.
