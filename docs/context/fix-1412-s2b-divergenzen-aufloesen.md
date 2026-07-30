# Context: fix-1412-s2b-divergenzen-aufloesen

Issue: [#1412](https://github.com/henemm/gregor_zwanzig/issues/1412) Scheibe **S2b**.
Vorarbeit vollständig: `docs/context/fix-1412-s2-regelwerk-paritaet.md` (beide Regelwerke zeilengenau, alle Divergenzen gemessen) · `docs/specs/modules/fix_1412_s2a_regelwerk_paritaet.md` (Sollwerte PO-freigegeben, Ausnahmen-Startbestand). S2a ist live (`ee922264`).

## Request Summary

Die fünf in S2a festgenagelten Abweichungen zwischen dem Python- und dem Go-Empfängerschutz werden aufgelöst. Jede Korrektur entfernt genau eine Ausnahme aus der Falltabelle und senkt den Deckel um eins; das in S2a gebaute Prüfwerkzeug belegt jede einzeln.

## Was sich ändert — fünf Eingriffe

Alle Angaben gemessen (volle Go-Modul- und Python-Repo-Kopie im Scratchpad, jede Variante gegen die ausgelieferte Falltabelle plus die sieben guard-nahen Python- und neun Go-Testdateien).

### D4 (Go) — Domain am letzten `@` bestimmen
`isReservedTestDomain` (`internal/mail/sender.go:145-166`), Domain-Bestimmung `:147`: `strings.Cut` (erstes `@`) → `strings.LastIndex` (letztes `@`), analog Pythons `rpartition` (`email.py:160`).
**Wirkung ausschließlich auf Adressen mit ≥2 `@`** — bei genau einem `@` sind erstes und letztes identisch, bitgleiches Ergebnis. Kein regulärer Empfänger ändert sein Verdikt.
Aufrufer: `loadResendAllowlist:225`, `recipientBlocked:361`, `recipientBlockedForVerification:509`. Der dritte ist S4-Gebiet, dort ist die Adresse ohnehin auf eine nackte Einzeladresse eingeengt (`:496-506`) — Härtung ohne Risiko.
Ratsche Go: 31 → 32.

### D3 (Python) — reservierte Unterdomänen ausschließen
`_is_reserved_test_domain` (`src/output/channels/email.py:148-166`): Suffix-Liste analog `sender.go:122` ergänzen (`_RESERVED_TEST_DOMAIN_SUFFIXES` neben `:144`), Prüfung vor dem TLD-`endswith` (`:166`).
**Ein Eingriff genügt** — `_load_resend_allowlist:223` ruft dieselbe Funktion; ein zweiter Eingriff an der Allowlist-Befüllung wäre eine Dopplung.
Blast Radius: vier Entscheidungen härten gleichzeitig (Allowlist-Befüllung `:223`, Resend-Guard `:475`, Nicht-Resend-Guard `:515`, Fallback-Guard `:383`). Praktisch ändert sich **nur der Resend-Pfad** — auf dem Stalwart-Pfad war `sub.example.com` schon durch `_is_local_mail_domain` blockiert.
Ratsche Python: 13 → 13 (das `endswith` liegt außerhalb der `send()`-Guard-Region).

### D2 (Go) — Adressfeld parsen, bevor am Komma getrennt wird
`splitRecipientField` (`internal/mail/sender.go:303-327`): `mail.ParseAddressList` auf das ganze Feld **vor** dem Komma-Split (`:304`), **plus `strings.TrimSpace` auf jede geparste Adresse**.

**Gewählt: Variante A (Parsen vor dem Split).** Verworfen: Variante B (`@`-Kandidatenfilter in `recipientBlocked:359-363`, Pythons Muster `email.py:469-471`) — sie stellt zwar exakte Parität her, **weitet aber die erlaubte Menge**: gemessen kippt `real@gmail.com, garbage` von `block` auf `allow`. Ein Müllfragment neben einer bestätigten Adresse würde dann nicht mehr blockieren. A hat **null** Nebenwirkungen: gemessen über 14 Empfängerformen kippt keine Entscheidung außer D2.

**Der `TrimSpace` ist nicht optional.** Ohne ihn kippt **N1** von `allow` auf `block` und reißt eine neue, ungedeckte Divergenz auf (gemessen). Grund: `mail.ParseAddressList("henning@henemm.com ")` liefert die Adresse **mit** NBSP zurück; Gos NBSP-Toleranz sitzt heute allein im `TrimSpace` bei `sender.go:306`, **nicht** in `normalizedAddrForGuard` — dort überschreibt `mail.ParseAddress` (`:280`) den getrimmten Wert wieder. Die unauffälligste Falle der Scheibe.
Ratsche Go: +2 (A), +1 (B).

### N1 (Python) — Randzeichen im Normalisierer strippen
`_normalize_addr_for_guard` (`src/output/channels/email.py:60-68`), Zeile `:64`: `_extract_addr(raw).lower()` → `_extract_addr(raw).strip().lower()`.
**Der Strip muss NACH `_extract_addr` stehen** — gemessen liefert `parseaddr("henning@henemm.com ")` die Adresse **mit** NBSP zurück, ein Strip davor wird wieder eingeholt.
Zeichenklasse: `str.strip()` ohne Argument deckt alle `str.isspace()`-Zeichen ab, NBSP eingeschlossen — keine explizite Liste nötig. Gos `strings.TrimSpace` deckt `unicode.IsSpace` ab; die Mengen sind nahezu, nicht exakt deckungsgleich (Python zusätzlich U+001C–U+001F). Für die Guard-Entscheidung irrelevant — aber niemand darf später „identische Zeichenklasse" behaupten.
Blast Radius: `_normalize_addr_for_guard` wird nur von `_normalized_addrs_for_guard` gerufen (`:107,115,119,121`), also von allen drei Guard-Zweigen. Die drei anderen Domain-Prüfer strippen **bereits** (`:160`, `:174`, `:222`) — die Änderung stellt Python **intern** her, was dort schon Standard ist.
Ratsche Python: 13 → 13.

### D5 (beide) — Empfänger in beiden Formen prüfen, Allowlist unangetastet
Prüf-Ausdruck in `email.py:472-477` und `internal/mail/sender.go:359-364`: der Empfänger wird zusätzlich in seiner **ungekappten, getrimmten** Form gegen die Allowlist geprüft.

**Gewählt: Variante C. Die beiden naheliegenden Varianten sind unzulässig — und untereinander wirkungsgleich.**
Gemessen: „Allowlist-Eintrag kappen" und „beide Formen in die Allowlist aufnehmen" liefern **identische** Ergebnisse, weil der Empfänger **immer** plus-gekappt normalisiert wird (`email.py:67`, `sender.go:285-287`) — ein ungekappter Eintrag ist dadurch unerreichbar.

| Bestätigt: `name+gz@gmail.com` | heute | Kappen / beide Formen | **Variante C** |
|---|---|---|---|
| `name+gz@gmail.com` | block | allow | **allow** |
| `name@gmail.com` | block | **allow** | **block** |
| `name+andere@gmail.com` | block | **allow** | **block** |
| `NAME+GZ@gmail.com` | — | allow | allow |

Beide verworfenen Varianten erlauben also die **Basisadresse und jeden beliebigen anderen Zusatz**, obwohl nur eine bestimmte Plus-Adresse bestätigt wurde — eine globale Erweiterung der erlaubten Menge, die über die PO-Freigabe („wer eine bestätigte Plus-Adresse hat, bekommt Post") deutlich hinausginge. **Tech-Lead-Entscheidung 2026-07-30: Variante C.**

Die heute festgeschriebene Gegenrichtung bleibt erhalten: bestätigt `real@gmail.com` → `real+tag@gmail.com` weiterhin `allow` (`recipient_guard_test.go:252`, `test_issue_1147_resend_recipient_invariant.py` F005e — beide unter C gemessen grün).
Blast Radius: C lässt die gespeicherte Allowlist **unberührt** (die Kapp-Variante hätte `_load_resend_allowlist:222`/`loadResendAllowlist:224` geändert und damit jeden Eintrag jedes Nutzers). Nicht-Resend-Zweig (`email.py:513-517`) und Fallback-Guard (`:385`) bleiben unangetastet — dort zählt nur die Domain.
Ratsche: Python 13 → 14, Go +2. **Einziger der fünf Eingriffe mit Struktureingriff** — deshalb zuletzt.

## Reihenfolge

**D4 → D3 → D2 → N1 → D5.** Begründung:
- D4 ist von allem unabhängig (eigene Funktion, eigene Zeile).
- **D3 und die verworfene D5-Kappvariante hätten textuell kollidiert** (`email.py:222-223` / `sender.go:224-225`, benachbarte Zeilen derselben Schleife). Variante C berührt die Allowlist-Befüllung gar nicht und räumt die Kollision ersatzlos aus.
- **D2-Variante B und D5-C hätten in `sender.go:359-364` kollidiert** — A und C überschneiden sich nicht. Zweites Argument für A.
- **N1 MUSS vor D5-C liegen.** D5-C prüft die ungekappte Form **getrimmt** und löst N1 dadurch **mit auf**. Läge C zuerst, müsste der N1-Eintrag mit derselben Änderung entfallen und der Deckel um **zwei** sinken (6→4), sonst wird der Läufer mit „N1: Divergenz aufgeloest, Ausnahme entfernen (AC-3)" rot. Mit N1 zuerst bleibt die 1:1-Rechnung.

## Prüfwerkzeug — die Rechnung stimmt

Gemessen, jede Korrektur einzeln gegen die volle Falltabelle: jede kippt **genau ihren** Fall, Deckel 6→5→4→3→2→1. **Alle Kontrollfälle** (`schlichte-adresse`, `fixture-erreichbarkeit`, `leerer-empfaenger`, N2a, N2b, N3) bleiben in **jeder** geprüften Variante und jeder Kombination grün. Vollkombinationen sauber: Python `D3+D5+N1` → alle 12 Fälle auf Soll; Go `D2A+D4+D5` → nur die erwarteten „Ausnahme entfernen"-Meldungen.

Zusätzlich zu pflegen (kein Ausnahme-Eintrag, aber Fixture-Feld): `verzweigungen_go` 31 → 34, `verzweigungen_python` 13 → 14. Der Läufer nennt die neue Zahl beim Rotwerden selbst.

## Bestandstests

**Genau einer bricht — und zwar bei allen fünf Korrekturen:**
`tests/test_mail_recipient_parity.py:663-675` `test_ac10_keine_produktivzeile_geaendert` prüft per `git diff --quiet HEAD` und behauptet „diese Scheibe darf KEINE Produktivzeile ändern (Spec-Vorgabe S2a, AC-10)". Seine Aussage war an S2a gebunden. **Er gehört in S2b gelöscht.** Ein Go-Pendant existiert nicht (`recipient_parity_test.go:16` verweist nur darauf).

**Sonst bricht kein einziger Bestandstest**, in keiner Variante, auf keiner Seite — geprüft über die sieben guard-nahen Python-Testdateien und die neun Go-Testdateien. Rot wird ausschließlich der Paritätsläufer, mit der gewollten Meldung.
Im ganzen Repo existiert außerhalb der Falltabelle **genau eine** Adresse auf einer `example.*`-Unterdomäne: `internal/mail/verify_send_test.go:179-180` — und die verlangt bereits `true` (Go-Seite, unverändert).

## Dependencies
**Upstream:** `data/users/<id>/user.json` (`email_verified_at`, `mail_to`, `email`) · `get_data_root()` / `GZ_DATA_DIR`.
**Downstream:** alle Mail-Versandwege über `EmailOutput.send()` · die vier Go-Sendeanlässe (Passwort-Reset `internal/handler/auth.go:282`, Verifikation `:689`, Level-Antrag `:848`, Magic-Link `internal/handler/auth_magic.go:114`) · das Prüfwerkzeug aus S2a.

## Risks & Considerations

- **Erste Scheibe, die Schutzentscheidungen tatsächlich ändert.** Das Sicherheitsnetz aus S2a hängt aber schon: jede Korrektur wird durch genau eine Ausnahme belegt, und zu viel/zu wenig/falsche Seite fällt auf.
- **Renderer-Commit-Gate #811** greift, sobald `src/output/channels/email.py` gestaged wird: `test_issue_811_mode_matrix.py` grün **und** frischer `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail, **nach** dem Stagen (die Nachweise werden gegen den gestagten Stand gehasht) und mit gesetzter Workflow-Kennung in der Umgebung.
- **AC-10-Test muss zuerst fallen**, sonst blockiert er jede der fünf.
- **`normalizedAddrForGuard` (`sender.go:280`) hebt den Trim wieder auf** — jede Go-Änderung, die auf getrimmte Werte baut, muss selbst trimmen.

## Zwei neu gefundene Divergenzen — NICHT Teil dieser Scheibe

Bei der Vermessung fielen zwei Fälle auf, die von keinem der zwölf Fälle abgedeckt sind:
1. `real@gmail.com, garbage` — Go `block`, Python `allow`.
2. `real@gmail.com garbage` (ohne Komma) — Go `allow`, Python `block`. Ursache: Pythons `parseaddr` verklebt das zu `real@gmail.comgarbage` (`email.py:113`).

Beide brauchen einen **Sollwert** — also eine Produktentscheidung — und gehören deshalb nicht still in diese Scheibe. Sie werden am Issue vermerkt und als Fälle nachgezogen, sobald der Sollwert entschieden ist.
