---
entity_id: fix_1412_s2b_divergenzen_aufloesen
type: bugfix
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [mail, parity, guard, 1412]
---

# Empfänger-Regelwerk-Parität Python/Go (S2b — fünf Divergenzen auflösen)

## Approval

- [ ] Approved

## Purpose

S2a hat ein Prüfwerkzeug gebaut, das zeigt: Python und Go beurteilen denselben Mail-Empfänger heute in fünf Fällen unterschiedlich, obwohl derselbe Sollwert für beide Seiten gilt. S2b löst genau diese fünf Abweichungen auf — je Korrektur entfällt eine der sechs in S2a festgenagelten Ausnahmen, sodass am Ende nur noch **D1** übrig bleibt (die erst S5 auflösen kann, weil sie den Zweck-Begriff aus S4 braucht). Diese Scheibe ändert erstmals seit S2a wieder tatsächliches Schutzverhalten am Mail-Versand.

## Source

| File | Identifier |
|---|---|
| `src/output/channels/email.py` | `_is_reserved_test_domain` (D3), `_normalize_addr_for_guard` (N1), `EmailOutput.send` Guard-Region (D5) |
| `internal/mail/sender.go` | `isReservedTestDomain` (D4), `splitRecipientField` (D2), `recipientBlocked` (D5) |
| `tests/fixtures/mail_recipient_parity/faelle.json` | Falltabelle: Ausnahmen, Deckel, Ratschen-Zahlen, neue Fälle |
| `tests/test_mail_recipient_parity.py` | `test_ac10_keine_produktivzeile_geaendert` (entfällt) |

> **Schicht-Hinweis:** Python-Core (`src/output/channels/email.py`) und Go-API (`internal/mail/sender.go`) — kein Frontend.

## Estimated Scope

- **LoC:** ~140 (email.py ~15, sender.go ~30, faelle.json ~55 geändert, Test-Datei ~15 entfernt)
- **Files:** 4 Code-/Fixture-Dateien + diese Spec
- **Effort:** medium (Guard-Logik in zwei Sprachen, Renderer-Commit-Gate #811 greift)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/channels/email.py::EmailOutput.send` (Guard-Region ~448-534) | function | Python-Seite der zu korrigierenden Entscheidung (D3, N1, D5) |
| `internal/mail/sender.go::recipientBlocked` (~340-376) | function | Go-Seite der zu korrigierenden Entscheidung (D2, D4, D5) |
| `internal/mail/sender.go::normalizedAddrForGuard` (:278-291, insb. :280) | function | Hebt `TrimSpace` wieder auf — Falle für D2 |
| `tests/test_mail_recipient_parity.py` / `internal/mail/recipient_parity_test.go` | test | S2a-Prüfwerkzeug, Nachweis für jede der fünf Korrekturen |
| `tests/fixtures/mail_recipient_parity/faelle.json` | fixture | geteilte Falltabelle, Ausnahmen, Deckel, Ratschen-Zahlen |
| `.claude/hooks/renderer_mail_gate.py` (Issue #811) | gate | Commit-Gate, greift weil `email.py` gestaged wird |
| `.claude/hooks/briefing_mail_validator.py` / `email_spec_validator.py` | validator | Frischer Nachweis gegen echt zugestellte Staging-Mail (Pflicht für Gate #811) |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/channels/email.py` | MODIFY | D3 (reservierte Unterdomänen ausschließen), N1 (Randzeichen nach `_extract_addr` strippen), D5 Python-Teil (ungekappte, getrimmte Form zusätzlich gegen Allowlist prüfen) |
| `internal/mail/sender.go` | MODIFY | D4 (Domain am letzten `@` statt am ersten bestimmen), D2 (Adressfeld vor dem Komma-Split parsen, plus `TrimSpace` auf jede geparste Adresse), D5 Go-Teil (ungekappte, getrimmte Form zusätzlich gegen Allowlist prüfen) |
| `tests/fixtures/mail_recipient_parity/faelle.json` | MODIFY | Fünf Ausnahmen entfernen (D2, D3, D4, D5, N1 — D1 bleibt), Deckel 6→1, `verzweigungen_go` 31→34, `verzweigungen_python` 13→14, drei neue Fälle für das Plus-Adresse-Verhalten (Basisadresse blockiert, Fremdzusatz blockiert, bestehende Gegenrichtung bleibt erreichbar) |
| `tests/test_mail_recipient_parity.py` | MODIFY | `test_ac10_keine_produktivzeile_geaendert` entfernen — seine Aussage war an S2a gebunden und blockiert sonst jede der fünf Korrekturen; nicht mehr benötigten `import subprocess` mitentfernen |

**Kein Go-Pendant zu entfernen:** `internal/mail/recipient_parity_test.go` enthält keinen AC-10-Test (`recipient_parity_test.go:16` verweist nur auf den Python-Test).

## Implementation Details

### Variantenwahl D5 — Variante C (Tech-Lead-Entscheidung 2026-07-30)

Bestätigte Plus-Adressen (`name+gz@gmail.com`) werden heute auf beiden Seiten geblockt, weil die Allowlist-Normalisierung das Pluszeichen kappt und der Vergleich dadurch scheitert. Zwei naheliegende Reparaturen — „Allowlist-Eintrag kappen" und „beide Formen in die Allowlist aufnehmen" — sind **gemessen wirkungsgleich** und erlauben beide zusätzlich die **Basisadresse und jeden beliebigen anderen Zusatz**, obwohl nur eine bestimmte Plus-Adresse bestätigt wurde:

| Bestätigt: `name+gz@gmail.com` | heute | Kappen / beide Formen | **Variante C (gewählt)** |
|---|---|---|---|
| `name+gz@gmail.com` | block | allow | **allow** |
| `name@gmail.com` | block | **allow** | **block** |
| `name+andere@gmail.com` | block | **allow** | **block** |
| `NAME+GZ@gmail.com` | — | allow | allow |

**Gewählt: Variante C** — der Empfänger wird zusätzlich in seiner ungekappten, getrimmten Form gegen die unveränderte Allowlist geprüft (statt die Allowlist selbst zu verändern). Blast Radius: die gespeicherte Allowlist bleibt unberührt, die Kapp-Variante hätte `_load_resend_allowlist`/`loadResendAllowlist` verändert und damit jeden Eintrag jedes Nutzers global erweitert. Nicht-Resend-Zweig und Fallback-Guard sind unangetastet — dort zählt nur die Domain. Die heute bereits funktionierende Gegenrichtung (bestätigt `real@gmail.com` → `real+tag@gmail.com` weiterhin erreichbar) ändert sich durch C nicht, weil die plus-gekappte Form dafür schon ausreicht.

### D2 — der `TrimSpace` ist nicht optional

`splitRecipientField` parst künftig `mail.ParseAddressList` auf das ganze Feld **vor** dem Komma-Split, **plus `strings.TrimSpace` auf jede geparste Adresse**. Ohne diesen Trim kippt **N1** von `allow` auf `block` und reißt eine neue, ungedeckte Divergenz auf: `mail.ParseAddressList("henning@henemm.com ")` liefert die Adresse mit NBSP zurück, und `normalizedAddrForGuard` (`sender.go:280`) überschreibt einen zuvor getrimmten Wert wieder mit dem ungetrimmten geparsten Ergebnis. Jede Go-Änderung, die auf getrimmte Werte baut, muss deshalb selbst trimmen.

### N1 — Strip muss NACH `_extract_addr` stehen

`_normalize_addr_for_guard` (`email.py:64`): `_extract_addr(raw).lower()` → `_extract_addr(raw).strip().lower()`. Ein Strip **vor** `_extract_addr` würde eingeholt — `parseaddr("henning@henemm.com ")` liefert die Adresse mit NBSP zurück.

### Reihenfolge: D4 → D3 → D2 → N1 → D5

- D4 ist von allem unabhängig (eigene Funktion, eigene Zeile) — zuerst.
- D2 (Variante A, Parsen vor Split) statt der verworfenen Variante B, weil B die erlaubte Menge weitet (`real@gmail.com, garbage` würde von `block` auf `allow` kippen) — A hat gemessen keine Nebenwirkung außer D2 selbst.
- **N1 MUSS vor D5 liegen.** D5 (Variante C) prüft die ungekappte Form **getrimmt** und löst N1 dadurch mit auf. Läge D5 zuerst, müsste der N1-Fall mit derselben Änderung entfallen und der Deckel um zwei statt eins sinken — sonst wird der Läufer mit „N1: Divergenz aufgeloest, Ausnahme entfernen (AC-3)" rot, obwohl keine N1-eigene Korrektur vorgenommen wurde. Mit N1 zuerst bleibt die 1:1-Rechnung (jede Korrektur löst genau eine Ausnahme).

### Ratschen-Zahlen mitpflegen

`tests/fixtures/mail_recipient_parity/faelle.json`: `verzweigungen_go` 31 → 34, `verzweigungen_python` 13 → 14. Beide Zahlen wachsen, weil D2/D4/D5 (Go) bzw. D5 (Python) neue Entscheidungspunkte in der jeweiligen Guard-Region einführen — der Läufer nennt die neue Zahl beim Rotwerden selbst (`test_verzweigungsratsche_python_region_gefunden_und_zahl_stimmt`, Go-Pendant).

### AC-10-Test entfällt

`tests/test_mail_recipient_parity.py:663-675` behauptet per `git diff --quiet HEAD`, diese Scheibe dürfe keine Produktivzeile ändern — eine Aussage, die nur für S2a galt. Er wird gelöscht (nicht deaktiviert), sonst blockiert er strukturell jede der fünf Korrekturen. Ein Go-Pendant existiert nicht.

### Renderer-Commit-Gate #811

`src/output/channels/email.py` wird gestaged → das Gate verlangt vor dem Commit **beide** Nachweise frisch: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün, **und** ein erfolgreicher `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail — **nach** dem Stagen (Nachweise werden gegen den gestagten Stand gehasht) und mit gesetzter Workflow-Kennung in der Umgebung.

## Expected Behavior

- **Input:** unveränderte Falltabelle bis auf die fünf gelösten Ausnahmen, den gesenkten Deckel, die aktualisierten Ratschen-Zahlen und drei neue Fälle; Guard-Logik in `email.py`/`sender.go` mit den fünf beschriebenen Korrekturen.
- **Output:** beide Läufer aus S2a (`tests/test_mail_recipient_parity.py`, `internal/mail/recipient_parity_test.go`) grün, bei einem Deckel von 1 statt 6.
- **Side effects:** tatsächliche Verhaltensänderung am Mail-Versand für fünf konkrete Empfängerformen (s. AC-1 bis AC-5) — keine Änderung für alle anderen Empfänger.

## Acceptance Criteria

- **AC-1 (D4):** Given eine bestätigte Adresse mit zwei „@"-Zeichen (z. B. `a@b@example.com`) / When ein Versand über den Go-Sendeweg an diese Adresse geprüft wird / Then bleibt sie blockiert — wie auf dem Python-Sendeweg schon heute.
  - Test: Fall `D4` in `tests/fixtures/mail_recipient_parity/faelle.json` erfüllt `soll=block` ohne Ausnahme; Gegenprobe (Korrektur zurückgenommen) lässt genau diesen Fall im Go-Läufer namentlich rot werden.

- **AC-2 (D3):** Given eine bestätigte Adresse auf einer Unterdomäne einer reservierten Testdomäne (z. B. `x@sub.example.com`) / When ein Versand über den Python-Sendeweg an diese Adresse geprüft wird / Then wird sie blockiert — wie auf dem Go-Sendeweg schon heute.
  - Test: Fall `D3` erfüllt `soll=block` ohne Ausnahme; Gegenprobe lässt genau diesen Fall im Python-Läufer namentlich rot werden.

- **AC-3 (D2):** Given eine bestätigte Adresse mit einem Anzeigenamen, der ein Komma enthält (z. B. `"Nachname, Vorname" <adresse>`) / When ein Versand über den Go-Sendeweg an diese Adresse geprüft wird / Then kommt die Post an — wie auf dem Python-Sendeweg schon heute.
  - Test: Fall `D2` erfüllt `soll=allow` ohne Ausnahme; Gegenprobe lässt genau diesen Fall im Go-Läufer namentlich rot werden.

- **AC-4 (N1):** Given eine bestätigte Adresse mit einem unsichtbaren Leerzeichen am Rand (Trailing-NBSP) / When ein Versand über den Python-Sendeweg an diese Adresse geprüft wird / Then kommt die Post an — wie auf dem Go-Sendeweg schon heute.
  - Test: Fall `N1` erfüllt `soll=allow` ohne Ausnahme; Gegenprobe lässt genau diesen Fall im Python-Läufer namentlich rot werden.

- **AC-5 (D5):** Given ein Nutzer hat eine Adresse mit Pluszeichen bestätigt (z. B. `name+gz@gmail.com`) / When er selbst diese genaue Adresse als Empfänger nutzt, auf beiden Sendewegen geprüft / Then kommt die Post an.
  - Test: Fall `D5` erfüllt `soll=allow` ohne Ausnahme auf beiden Seiten; Gegenprobe lässt genau diesen Fall in beiden Läufern namentlich rot werden.

- **AC-6 (wichtigster Einzelpunkt — Variante C vollständig):** Given ein Nutzer hat eine bestimmte Plus-Adresse bestätigt (z. B. `name+gz@gmail.com`) / When jemand stattdessen die Basisadresse (`name@gmail.com`) oder einen anderen Zusatz derselben Basisadresse (`name+andere@gmail.com`) als Empfänger nutzt / Then bleibt der Versand dorthin blockiert — nur die exakt bestätigte Plus-Adresse erreicht den Nutzer, keine Nachbaradresse.
  - Test: zwei neue Fälle in der Falltabelle (`plus-adresse-basis-bleibt-blockiert`, `plus-adresse-fremdzusatz-bleibt-blockiert`) erfüllen `soll=block` ohne Ausnahme, auf beiden Sendewegen.

- **AC-7 (Gegenrichtung bleibt erhalten):** Given ein Nutzer hat seine Basisadresse bestätigt (z. B. `real@gmail.com`) / When er eine Plus-Variante davon als Empfänger nutzt (`real+tag@gmail.com`) / Then kommt die Post weiterhin an — unverändert gegenüber dem Stand vor dieser Scheibe.
  - Test: neuer Fall `plus-adresse-gegenrichtung-erreichbar` erfüllt `soll=allow` ohne Ausnahme, auf beiden Sendewegen; die bestehenden Regressionstests `recipient_guard_test.go:252` und `test_issue_1147_resend_recipient_invariant.py` (Fall F005e) bleiben unverändert grün.

- **AC-8 (nur D1 bleibt übrig):** Given alle fünf Korrekturen dieser Scheibe sind umgesetzt / When das Prüfwerkzeug aus S2a läuft / Then enthält die Falltabelle genau eine gültige, unabgelaufene Ausnahme (D1, weiterhin blockiert bis S5) und `ausnahmen_hoechstzahl` steht auf 1.
  - Test: `test_ausnahmen_deckel_im_ausgelieferten_stand_nicht_ueberschritten` (Python) und sein Go-Pendant sind grün gegen die aktualisierte Falltabelle mit Deckel 1; die Falltabelle enthält keinen Ausnahme-Eintrag mehr für D2, D3, D4, D5 oder N1.

- **AC-9 (kein heutiger Empfänger bleibt hängen):** Given ein Empfänger, der schon vor dieser Scheibe Post bekam (schlichte bestätigte Adresse, Fixture-Erreichbarkeits-Adresse, lokale Zustellung, Mehrfach-Adressen-Kontrollfälle) / When die fünf Korrekturen umgesetzt sind / Then bekommt dieser Empfänger weiterhin genauso Post wie zuvor.
  - Test: alle bestehenden Kontrollfälle der Falltabelle (`schlichte-adresse`, `fixture-erreichbarkeit`, `leerer-empfaenger`, `N2a`, `N2b`, `N3`) bleiben in beiden Läufern unverändert grün; die bestehenden Bestandstests der sieben guard-nahen Python- und neun Go-Testdateien bleiben grün (einzige Ausnahme: der zu entfernende AC-10-Test).

## Known Limitations

1. **D1 bleibt bestehen** — der Stalwart-Pfad blockt fremde Adressen bei Go nicht, weil `recipientBlocked` nur greift, wenn `host` „resend" enthält. Auflösung braucht den Zweck-Begriff aus S4 und ist S5 zugeordnet.
2. **Zwei neu gefundene Divergenzen bleiben unbearbeitet:** `real@gmail.com, garbage` (Go `block`, Python `allow`) und `real@gmail.com garbage` ohne Komma (Go `allow`, Python `block`, weil Pythons `parseaddr` das zu `real@gmail.com'garbage` verklebt). Beide brauchen erst einen Sollwert vom PO und werden am Issue vermerkt, nicht still in diese Scheibe gezogen.
3. **`NAME+GZ@gmail.com` (Großschreibung)** ist von D5 unberührt — sie wird bereits vor dieser Scheibe wie zuvor behandelt (case-insensitive Normalisierung besteht unverändert fort).
4. Die aus S2a geerbten Grenzen des Prüfwerkzeugs gelten unverändert (semantikgleicher Code ohne Verzweigungsänderung bleibt unsichtbar, Regeln außerhalb der beobachteten Region, gemeinsame Fehler bleiben grün) — siehe `docs/specs/modules/fix_1412_s2a_regelwerk_paritaet.md`, Abschnitt „Known Limitations".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Zielgerichtete Korrektur einer gemessenen Implementierungsabweichung gegen bereits in S2a PO-freigegebene Sollwerte, kein neues Architekturmuster. Die einzige echte Entscheidung (Variante C bei D5) ist im Text dokumentiert und bewusst so gewählt, dass die gespeicherte Allowlist-Struktur unverändert bleibt.

## Changelog

- 2026-07-30: Initial spec created (S2b, aus `docs/context/fix-1412-s2b-divergenzen-aufloesen.md`)
