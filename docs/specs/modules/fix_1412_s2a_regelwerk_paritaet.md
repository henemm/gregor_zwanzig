---
entity_id: fix_1412_s2a_regelwerk_paritaet
type: feature
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [mail, parity, guard, 1412]
---

# Empfänger-Regelwerk-Parität Python/Go (S2a — Prüfwerkzeug)

## Approval

- [ ] Approved

## Purpose

Python (`src/output/channels/email.py`) und Go (`internal/mail/sender.go`) beurteilen heute denselben Mail-Empfänger mit zwei getrennten, handgepflegten Regelwerken — nachweislich mit unterschiedlichem Ergebnis in mehreren Fällen. S2a baut das Prüfwerkzeug, das diese Abweichungen sichtbar macht und offen hält: einen Läufer je Sprache, der dieselbe Falltabelle gegen beide Seiten prüft, dieselben Sollwerte verlangt und jede heute bekannte Abweichung als benannte, befristete Ausnahme festnagelt. **Diese Scheibe ändert kein Produktivverhalten** — sie schafft nur die Meßlatte, gegen die S2b die Abweichungen einzeln auflöst.

## Source

- **Neu:** `tests/test_mail_recipient_parity.py` (Python-Läufer)
- **Neu:** `internal/mail/recipient_parity_test.go` (Go-Läufer)
- **Neu:** `tests/fixtures/mail_recipient_parity/faelle.json` (geteilte Falltabelle)
- **Gelesen, nicht geändert:** `src/output/channels/email.py` (Guard-Logik), `internal/mail/sender.go` (Guard-Logik)

> **Schicht-Hinweis:** Diese Scheibe berührt ausschließlich Python-Core (`tests/`) und Go-API (`internal/mail/`) — keine Frontend-Dateien.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/channels/email.py::EmailOutput.send` | function | Python-Seite der geprüften Entscheidung (Guard-Zweige :448-534) |
| `internal/mail/sender.go::recipientBlocked` | function | Go-Seite der geprüften Entscheidung (:340-376) |
| `src/app/loader.py::get_data_root` / `_DATA_ROOT` | module | Datenwurzel, aus der beide Seiten die Resend-Allowlist laden |
| `tests/test_egress_inventory_drift.py` | test | Vorbild für Pfadauflösung, Text-Parsing der Go-Seite, Parser-Selbsttest, benannte Existenz-Assertions |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | test | Vorbild für `EXPIRY`-Konstante mit Prüfdatum-Assertion (dortige Zeile 339) |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `tests/fixtures/mail_recipient_parity/faelle.json` | CREATE | Falltabelle (Fälle, Profile, Ausnahmen, Deckel) — geteilte Datenquelle für beide Läufer |
| `tests/test_mail_recipient_parity.py` | CREATE | Python-Läufer: Entscheidungs-Parität, Ausnahmen-Deckel, Konstanten-Parität, Verzweigungs-Ratsche (Python-Seite), Selbstnachweise |
| `internal/mail/recipient_parity_test.go` | CREATE | Go-Läufer: Entscheidungs-Parität, Ausnahmen-Deckel, Verzweigungs-Ratsche (Go-Seite) |

### Estimated Changes
- Files: 3 Code-/Fixture-Dateien + diese Spec
- LoC: ~410 gesamt (Fixture ~55, Python-Test ~135, Go-Test ~135, Spec ~85) — **Override 500 erteilt** (PO-Entscheidung 2026-07-30: zwei vollständige Läufer in zwei Sprachen, keine Produktivzeile geändert)

**Keine Zeile an `src/output/channels/email.py` oder `internal/mail/sender.go`.** Bewusste Entwurfsvorgabe — hält das Renderer-Commit-Gate #811 (`renderer_mail_gate.py:45`) draußen, das sonst einen frischen Validator-Lauf gegen eine echt zugestellte Staging-Mail für ein Werkzeug ohne Produktivänderung verlangen würde.

**Ablauf-Hinweis:** `internal/mail/recipient_parity_test.go` liegt co-located neben `sender.go` — in der TDD-RED-Phase blockt das Gate `.go`-Edits (bekannt aus S1). Der Go-Anteil (Datei anlegen + Nachweis) wandert deshalb in Phase 6 (Implement).

## Implementation Details

### Sechs Sollwerte (zur Freigabe)

Jeder Sollwert ist eine Produktentscheidung, keine Messung. Formuliert aus der Wirkung für den Empfänger:

| Fall | Sollwert | Alltagssprachlich |
|---|---|---|
| **D1** — fremde Adresse über den Stalwart-Versandweg | `block` | Wer nicht zu den bestätigten Empfängern gehört, bekommt über diesen Weg keine Post. |
| **D2** — Empfänger mit Anzeigename und Komma, Adresse selbst bestätigt (`"Nachname, Vorname" <henning@henemm.com>`) | `allow` | Wer eine bestätigte Adresse hat, bekommt Post — auch wenn der Name davor ein Komma enthält. |
| **D3** — bestätigte Adresse auf einer reservierten Test-Unterdomäne | `block` | Adressen unter reservierten Testdomänen bekommen nie echte Post, auch nicht als Unterdomäne. |
| **D4** — bestätigte Adresse mit zwei `@`-Zeichen (`a@b@example.com`) | `block` | Eine Adresse mit zwei Klammeraffen ist keine gültige Adresse und bekommt keine Post. |
| **D5** — bestätigte Plus-Adresse (`name+gz@gmail.com`) | `allow` (PO-Entscheidung 2026-07-30) | Wer eine Adresse mit Pluszeichen hinterlegt und bestätigt hat, soll Post bekommen. |
| **N1** — bestätigte Adresse mit unsichtbarem Randzeichen (Trailing-NBSP) | `allow` (PO-Entscheidung 2026-07-30) | Ein unsichtbares Leerzeichen am Rand einer sonst bestätigten Adresse blockiert die Post nicht. |

D5 und N1 sind bereits dieselbe bestätigte Adresse — heute scheitert sie nur an einem Formfehler der Prüfung, nicht an einer echten Unsicherheit über den Empfänger. Beide Änderungen werden **nicht** in dieser Scheibe umgesetzt (keine Produktivzeile ändert sich), sondern als Ausnahme mit `soll: allow` und `ist: block` (heutiger Zustand) festgehalten — S2b macht die Praxis wahr.

### Startbestand: 6 Ausnahmen

| Fall | Seite | Auflösende Scheibe | Frist |
|---|---|---|---|
| D1 | go | S5 (braucht den Zweck-Begriff aus S4) | 2026-10-28 |
| D2 | go | S2b | 2026-10-28 |
| D3 | python | S2b | 2026-10-28 |
| D4 | go | S2b | 2026-10-28 |
| D5 | beide | S2b | 2026-10-28 |
| N1 | python | S2b | 2026-10-28 |

Jede Ausnahme braucht `{fall, seite, ist, scheibe, frist, grund}` mit Begründung ≥15 Zeichen (Vorbild: `_MIN_BEGRUENDUNG` in `test_repo_path_hardcoding_ratchet.py:351`).

**Welcher Läufer welche Ausnahme sieht — Folge der „ehrlichen Grenze" (s.u.):** Jeder Läufer misst nur **seine eigene** Seite. Der Python-Läufer meldet daher im Ausgangszustand (`ausnahmen: []`) genau **D3, D5, N1**; der Go-Läufer genau **D1, D2, D4, D5**. Erst **beide zusammen** decken alle sechs ab. Ein Läufer allein, der „nur drei von sechs" nennt, ist kein Mangel, sondern die erwartete Bauweise — RED-Nachweis und Gegenprobe müssen deshalb **beide** Läufer zeigen. `seite` steuert dabei, welcher Läufer eine Ausnahme heranzieht (`python` · `go` · `beide`).

### Mechanismus — vier Bausteine

1. **Entscheidungs-Parität (Kern).** Jeder Fall aus der Falltabelle wird gegen beide Läufer gefahren; das gemessene Ergebnis muss dem `soll`-Wert entsprechen, sofern keine Ausnahme greift — sonst muss es dem `ist`-Wert der Ausnahme entsprechen. Erfasst auch Zusammenspiel-Fälle (D2, N2), die keine einzelne Hilfsfunktion zeigt.
2. **Ausnahmen-Deckel.** Beide Läufer lesen `ausnahmen_hoechstzahl` aus derselben Fixture-Datei. Eine zusätzliche, unaufgelöste Divergenz — ein Fall, dessen gemessenes Ergebnis vom Sollwert abweicht, ohne dass eine passende Ausnahme existiert — lässt **beide** Läufer rot werden, nicht nur den, dessen Seite sich geändert hat.
3. **Konstanten-Parität** (nur Python-Läufer, Go-Quelle als Text gelesen — Vorbild `test_egress_inventory_drift.py:11-13`). Vergleicht reservierte Test-Domains/TLDs/Suffixe, `LOCAL_MAIL_DOMAINS` und die zwei Steuerzeichen-Regexe **semantisch**, nicht buchstäblich: Escape-Sequenzen werden auf Codepunkte normalisiert, `re.IGNORECASE` und Go-Inline-`(?i)` werden getrennt als Flag verglichen (die Regexe selbst sind textuell verschieden, `[\r\n\x0b\x0c\x00]` vs. `[\r\n\v\f\x00]`, aber bedeutungsgleich).
4. **Verzweigungs-Ratsche je Seite.** Jede Seite zählt die Entscheidungspunkte in ihrer eigenen Guard-Region und vergleicht gegen eine in der Fixture-Datei hinterlegte eigene Zahl. Die Python-Region wird per AST bestimmt (die `If`-Anweisung im Rumpf von `send()`, deren Bedingung das Literal `resend` enthält) — nicht über Zeilennummern oder Marker-Kommentare, also ohne Zeichenwechsel an der geschützten Datei. Die Zahlen sind zwischen den Sprachen **nicht** vergleichbar (unterschiedliche Zählregeln je Sprache); jede Seite ratscht nur gegen sich selbst.

**Ehrliche Grenze des Mechanismus:** Keiner der vier Bausteine macht bei einer einseitigen Regeländerung beide Suiten rot — Entscheidungs-Parität und Verzweigungs-Ratsche messen je eine Seite. Was beide erwischt, ist ausschließlich der Ausnahmen-Deckel: eine neue, unaufgelöste Divergenz lässt sich nur grün bekommen, indem entweder die andere Seite nachgezogen wird (Ziel erreicht) oder eine neue, begründete Ausnahme eingetragen wird — dann reißt der Deckel beidseitig, sichtbar in einer versionierten Datei. Das eigentliche Erfolgskriterium ist deshalb nicht „beide Suiten werden rot", sondern **„die Änderung landet nicht, und die Meldung nennt die Pflicht"** — eine rote Suite blockiert einen Commit genauso zuverlässig wie zwei.

### Falltabellen-Format

`tests/fixtures/mail_recipient_parity/faelle.json`, JSON (wegen NBSP, eingebetteter Anführungszeichen und Trailing-Dots in den Testadressen — nur `json`/`encoding/json` lesen diese Escapes bitgleich).

- **Fall:** `{"id", "host", "to", "soll"}`. `host` ist literal (fiktive Hosts `smtp.resend-fixture.test`, `mail.henemm.com`), keine Rolle — eine Rollen-Abbildung könnte selbst auseinanderlaufen.
- **Profil-Fixture:** wörtlicher `user.json`-Inhalt je Nutzer unter `"profile"`. Jeder Läufer schreibt den Wert unverändert nach `<tmp>/users/<id>/user.json` — kein Feld-Mapping, keine Default-Regel.
- **Ausnahmen** als eigener Top-Level-Schlüssel: `{"fall", "seite", "ist", "scheibe", "frist", "grund"}` — getrennt von `soll`, damit der Sollwert nie kontaminiert wird.

### Wie jede Seite an ihre Entscheidung kommt

**Python:** `EmailOutput` wird **nicht** über `Settings` konstruiert (`__new__` + die acht Attribute direkt gesetzt) — `_resend_default_deny` (`config.py:195-215`) lenkt unter pytest jeden Resend-Host auf Stalwart um und würde den Läufer still den falschen Zweig messen lassen. Die Datenwurzel wird über `app.loader._DATA_ROOT` gesetzt, nicht über `GZ_DATA_DIR` — `_DATA_ROOT` hat Vorrang (`loader.py:1054`) und `tests/conftest.py:91-97` setzt es bereits autouse; wer nur `GZ_DATA_DIR` setzt, wird überstimmt und liest eine leere Wurzel. `send()` läuft mit einer Sentinel-Ausnahme am Transport, die weder von `smtplib.SMTPException` noch von `OSError` erbt und dadurch beim ersten Versuch ohne Retry durchfällt. Ergebnisvokabular: Sentinel gefangen ⇒ `allow`; `OutputConfigError` mit Guard-Marker im Text ⇒ `block`; alles andere ⇒ lauter Abbruch mit Typnennung — niemals still als `block` gebucht.

**Go:** `recipientBlocked(host, to)` wird direkt gerufen, nicht `Send()` — die nachgelagerten Schritte `resendBlocked`/`dialAndSend` sind Host-Policies außerhalb der Guard-Region und gehören symmetrisch nicht in die Achse. Kein Testflag, kein Seam, kein Build-Tag (wäre eine Aufweichung von #1122). Datenverzeichnis über `t.Setenv("GZ_DATA_DIR", …)`. Ergebnisvokabular: der Aufrufpunkt allein trennt `allow`/`block` — `errors.Is(err, ErrGuardBlocked)` taugt nicht, weil `resendBlocked` denselben Sentinel wrappt.

**Zwei Fallen, benannt, damit der Läufer nicht still falsch misst:**
- `_resend_default_deny` (config.py:195-215) lenkt unter pytest jeden Resend-Host um ⇒ Objekt nicht über `Settings` bauen.
- `_DATA_ROOT` hat Vorrang vor `GZ_DATA_DIR` (`loader.py:1054`, `tests/conftest.py:91-97`) ⇒ Datenwurzel über `_DATA_ROOT` lenken.

**Go-Pfadanker:** `runtime.Caller(0)` liefert unter `-trimpath` einen modulrelativen Pfad und bricht still — **nicht verwenden**. Stattdessen `os.Getwd()`-Aufstieg bis zum Verzeichnis mit `go.mod` (genau eine im Repo), Obergrenze ~6 Ebenen, dann Existenz der Falltabelle prüfen und sonst laut abbrechen.

### Vier Selbstnachweise des Läufers

1. **Fixture-Erreichbarkeit:** ein Fall mit einer Adresse, die es nur in der Fixture-Allowlist gibt (`paritaet-fixture@henemm.com`, `soll: allow` am Resend-Host) — kann nur grün werden, wenn die Fixture-Datenwurzel tatsächlich geladen wurde.
2. **Sentinel-Pflicht (Python-Seite):** `allow` gilt nur bei gefangenem Sentinel; der Gesamtlauf muss mindestens ein `allow` und ein `block` enthalten.
3. **Benannte Existenz-Assertions:** fehlende Falltabellen-Datei und leere Fallliste sind je eine eigene, benannte Assertion (Vorbild `test_egress_inventory_drift.py:56-61`) — kein stilles „0 Fälle geprüft, alles grün".
4. **Parser- und Regionsfund-Nachweis:** ein synthetischer Go-Text mit auskommentierter und echter Zeile beweist, dass die Kommentar-Regel des Konstanten-Parsers greift; eine eigene Assertion beweist, dass die Verzweigungs-Ratsche die AST-Region in `email.py` überhaupt gefunden hat.

## Expected Behavior

- **Input:** Falltabelle mit Fällen, Profilen, Ausnahmen und Deckel; die Guard-Logik in `email.py` und `sender.go` bleibt unverändert.
- **Output:** Zwei grüne Testsuiten (`tests/test_mail_recipient_parity.py`, `go test ./internal/mail/`), solange kein Fall vom Sollwert abweicht, ohne durch eine gültige, unabgelaufene Ausnahme gedeckt zu sein, und solange die Zahl der Ausnahmen den Deckel nicht überschreitet.
- **Side effects:** keine — reiner Prüflauf, kein Netzzugriff, keine echten Mails, keine Änderung an Produktivdateien.

## Acceptance Criteria

- **AC-1:** Given ein Fall aus der Falltabelle, für den Python und Go dieselbe Adresse gleich beurteilen, und dieses Ergebnis dem hinterlegten Sollwert entspricht / When beide Läufer laufen / Then sind beide grün.
  - Test: `tests/test_mail_recipient_parity.py::test_entscheidungsparitaet` und `internal/mail/recipient_parity_test.go::TestEntscheidungsparitaet` laufen mit der ausgelieferten Falltabelle grün durch.

- **AC-2:** Given eine Seite beurteilt einen Fall abweichend von der anderen, ohne dass diese Abweichung als Ausnahme eingetragen ist / When der zugehörige Läufer läuft / Then schlägt er fehl und die Meldung benennt den betroffenen Fall.
  - Test: eine Fixture mit einem zusätzlichen, nicht eingetragenen Divergenz-Fall lässt den Lauf mit dem Fall-Namen in der Fehlermeldung rot werden.

- **AC-3:** Given eine eingetragene Ausnahme behauptet ein bestimmtes Verhalten einer Seite / When diese Seite sich tatsächlich anders verhält als die Ausnahme behauptet — auch weil die Abweichung inzwischen behoben wurde / Then schlägt die Prüfung fehl und die Meldung verlangt das Entfernen der Ausnahme.
  - Test: eine Fixture, in der der `ist`-Wert einer Ausnahme nicht mehr zum gemessenen Verhalten passt, lässt den Lauf rot werden mit dem Hinweis, die Ausnahme sei aufgelöst und zu entfernen.

- **AC-4:** Given eine zusätzliche, unaufgelöste Abweichung, die den Ausnahmen-Deckel überschreitet / When beide Läufer laufen / Then werden **beide** rot, nicht nur der, dessen Seite sich geändert hat.
  - Test: eine Fixture mit einer siebten, nicht gedeckten Divergenz bei unverändertem Deckel (6) lässt sowohl den Python- als auch den Go-Lauf fehlschlagen.

- **AC-5:** Given eine Ausnahme ohne eine Begründung von mindestens 15 sinnvollen Zeichen / When der Läufer die Fixture lädt / Then zählt diese Ausnahme nicht als gültige Ausnahme und die Prüfung schlägt entsprechend fehl.
  - Test: eine Fixture mit einer Ausnahme mit leerem oder zu kurzem `grund`-Feld lässt den betroffenen Fall wie eine nicht eingetragene Abweichung behandeln (AC-2 greift).

- **AC-6:** Given die Frist einer Ausnahme ist abgelaufen / When der Läufer läuft / Then schlägt die Prüfung fehl.
  - Test: eine Fixture mit einer Ausnahme mit einer Frist in der Vergangenheit lässt den zugehörigen Lauf rot werden mit Nennung der abgelaufenen Ausnahme.

- **AC-7:** Given eine fehlende Falltabellen-Datei, eine leere Fallliste, eine nicht auffindbare Guard-Region oder eine Fixture-Datenwurzel, die beim Lauf gar nicht ankommt / When der Läufer startet / Then schlägt jeder dieser vier Zustände mit einer eigenen, benannten Meldung fehl — kein stilles Grün.
  - Test: vier gezielte Szenarien (Datei entfernt, Fallliste geleert, AST-Region-Marker im synthetischen Text entfernt, Fixture-Adresse aus der Allowlist entfernt) lösen je eine unterscheidbare Fehlermeldung aus.

- **AC-8:** Given die geteilten Konstanten (reservierte Test-Domains/TLDs/Suffixe, lokale Domains, die zwei Steuerzeichen-Muster) in Python und Go / When der Konstanten-Vergleich läuft / Then stimmen sie inhaltlich überein, auch wenn sie unterschiedlich geschrieben sind (z. B. verschiedene Escape-Schreibweisen für dasselbe Zeichen, `re.IGNORECASE`-Flag vs. Inline-Modifikator).
  - Test: der mit dem ausgelieferten Stand von `email.py`/`sender.go` gefahrene Konstanten-Vergleich ist grün; ein synthetisch veränderter Konstanten-Wert auf einer Seite lässt ihn rot werden.

- **AC-9:** Given die Zahl der Entscheidungspunkte in der Guard-Region einer Seite wächst gegenüber der hinterlegten Zahl / When der Läufer dieser Seite läuft / Then schlägt er fehl, bis ein Fall ergänzt wurde, der die neue Verzweigung abdeckt.
  - Test: ein synthetisch um eine Bedingung erweiterter Guard-Codeabschnitt lässt die Verzweigungs-Ratsche der betroffenen Seite rot werden; nach Ergänzung eines abdeckenden Falls wird sie wieder grün.

- **AC-10:** Given der ausgelieferte Stand von S2a / When beide Läufer gegen die unveränderte Guard-Logik in `email.py` und `sender.go` laufen / Then verhält sich die Anwendung selbst in keiner Weise anders als vor dieser Lieferung — es wurde keine Produktivzeile geändert.
  - Test: `git diff` zeigt keine Änderung an `src/output/channels/email.py` oder `internal/mail/sender.go`; alle Bestandstests im Mail-Paket bleiben grün.

## Known Limitations

1. **Semantik-Tausch ohne Verzweigungs- oder Konstantenänderung** (z. B. `partition` → `rpartition`, `email.py:65`) bleibt unsichtbar, solange kein abdeckender Fall existiert. D4 deckt genau eine Form ab, verwandte Formen bleiben blind.
2. **Regeln außerhalb der beobachteten Region** — ein neuer Empfänger-Filter etwa in `notification_service.py` oder `internal/handler/auth.go` ist für keinen der vier Bausteine sichtbar.
3. **Gemeinsame Fehler bleiben grün**, solange der `soll`-Wert nicht widerspricht — beide Seiten identisch falsch ergibt paritätisch grün. Punycode/IDN bleibt auf beiden Seiten bewusst ungeprüft (S2a-fremd).
4. **`recipientBlockedForVerification`** (sender.go:472-515) ist nicht in der Achse — anderer Zweck, kein Python-Pendant, gehört zu S4.
5. **`resendBlocked` / `_resend_default_deny` sind Host-Policies**, nicht in der Achse — symmetrischer Ausschluss auf beiden Seiten.
6. **Der Host-Vergleich selbst ist ungeprüft** — beide Seiten prüfen `"resend"` als Teilzeichenkette (email.py:448, sender.go:341). Stellte jemand eine Seite auf exakten Vergleich um, bliebe der Läufer grün.
7. **N2b ist heute nur scheinbar paritätisch** — Go sagt `allow`, weil auf dem Stalwart-Pfad gar kein Guard läuft (D1), nicht weil dieselbe Entscheidung getroffen wurde. Mit der Auflösung von D1 in S5 kippt N2b in eine echte Divergenz.
8. **N3 (Mehrfach-Adresse in einem Profilfeld)** wird als Fall mit `soll: block` plus Ausnahme festgenagelt, nicht aufgelöst — das Auftrennen erweitert die erlaubte Menge und ist eine Produktentscheidung außerhalb dieses Prüfwerkzeugs.

**Regel-Budget:** Diese Scheibe ersetzt keine bestehende Regel ⇒ **Prüfdatum 2026-10-28**. Bauform wie `tests/tdd/test_repo_path_hardcoding_ratchet.py:339` (`EXPIRY`-Konstante, per Assertion gebunden) — der Läufer wird am Prüfdatum nicht von selbst rot, das Prüfdatum ist nur maschinell auffindbar. Jede einzelne Ausnahme trägt zusätzlich ihre eigene Frist (2026-10-28, s.o.).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Prüfwerkzeug ohne Produktivänderung, kein Entscheidungsfeld im Sinne der ADR-Kategorien (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie).

## Changelog

- 2026-07-30: Initial spec created (S2a, aus `docs/context/fix-1412-s2-regelwerk-paritaet.md` Abschnitt „Analysis (S2a)")
