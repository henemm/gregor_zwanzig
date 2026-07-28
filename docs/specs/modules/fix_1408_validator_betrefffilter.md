---
entity_id: fix_1408_validator_betrefffilter
type: bugfix
created: 2026-07-28
updated: 2026-07-28
status: draft
workflow: fix-1408-validator-betrefffilter
version: "1.0"
tags: [compare, mail-validator, gate, imap, staleness-guard, e2e-verify]
---

# Fix #1408: Der Ortsvergleichs-Mail-Prüfer sucht die richtige Mail namentlich, statt blind die jüngste zu nehmen

## Approval

- [x] Approved — PO Henning, 2026-07-28 („Go"): die sechs Acceptance Criteria,
  die standardmässig **aktive** Altersschranke, die Begründungspflicht beim
  Abschalten (`--ignore-mail-age "<Grund>"`), der harte Abbruch bei fehlender
  Server-Zeit statt Ausweichen auf den `Date`-Header, sowie die Aussparung der
  Radar- und Official-Alert-Validatoren (Folgearbeit an #1408). Angehobene
  Umfangsgrenze ausdrücklich mitfreigegeben.

## Purpose

Der Pflicht-Prüfer für die Ortsvergleichs-Mail (`.claude/hooks/email_spec_validator.py`)
nimmt heute immer die **jüngste** Mail mit `X-GZ-Mail-Type: compare` aus dem
geteilten Test-Postfach. Weil parallele Sitzungen dort ebenfalls hineinschreiben,
kann der Prüfer eine fremde Mail bewerten — im schlimmsten Fall **still**
(Exit 0 auf eine Mail, die nicht aus dem geprüften Stand stammt, und die dann
als Nachweis ins Renderer-Commit-Gate #811 und in die Staging-Attestation
eingeht). Diese Lieferung gibt dem Prüfer einen optionalen Betreffs-Filter
(analog `briefing_mail_validator.py`, #780) und eine standardmäßig aktive
Altersschranke über die serverseitig vergebene IMAP-`INTERNALDATE`, damit er
gezielt die eigene, frische Mail wählt und bei Zweifel hörbar abbricht statt
stillschweigend die nächstbeste zu nehmen — sowohl beim Betreff als auch bei
einer fehlenden vertrauenswürdigen Server-Zeit.

## Source

- **File:** `.claude/hooks/email_spec_validator.py`
- **Identifier:** `_select_compare_uid()` (Zeilen 111-124), `_fetch_latest_message()`
  (Zeilen 127-194), `_no_compare_mail_error()` (Zeilen 102-108),
  `run_validation()`/`main()` (Zeilen 650-734), `_write_validation_log()`
  (Zeilen 37-94)

> **Schicht-Hinweis:** Kein Produktcode einer der drei Laufzeit-Schichten
> (Frontend/Go-API/Python-Core). `.claude/hooks/email_spec_validator.py` ist
> ein Pflicht-Gate-Skript, das der Renderer-Commit-Gate (#811,
> `.claude/hooks/renderer_mail_gate.py`) für den Compare-Mailpfad als
> Nachweisquelle verlangt. Betroffen ist ausschließlich dieses Skript sowie
> seine Testabdeckung — keine Datei unter `src/`, `internal/`, `frontend/`.

## Ausgangslage (gemessen, s. `docs/context/fix-1408-validator-betrefffilter.md`)

| Baustein | Heute | Lücke |
|---|---|---|
| `_select_compare_uid(candidates)` | Reine Auswahlfunktion, wählt die **neueste** Mail mit `X-GZ-Mail-Type: compare` aus einer vorsortierten Kandidatenliste | Kein Betreffs-Filter — kann nicht zwischen der eigenen und einer parallelen Compare-Mail unterscheiden |
| `_fetch_latest_message(imap=None)` | Scannt das Postfach newest-first, stoppt beim ersten `compare`-Treffer (kein Scan-Fenster, F001). Die Auswahllogik ist hier **inline wiederholt** (Zeilen 174-181), nicht über `_select_compare_uid` — dieselbe Trefferbedingung existiert damit doppelt und kann auseinanderlaufen | Dieselbe Marker-Lücke wie oben, zusätzlich doppelt gepflegte Prüfung |
| Zeitprüfung | **Keine.** `INTERNALDATE` wird nirgends im Fetch-Pfad angefordert (geprüft: kein Treffer für `INTERNALDATE` im gesamten Repo außer im Kontext-Dokument selbst) | Eine beliebig alte Mail — z. B. aus einer abgebrochenen Vorsitzung — wird anstandslos als Nachweis akzeptiert; und falls der Server keine belastbare Zeit liefert, gibt es keinen Mechanismus, der das bemerkt |
| `run_validation()`/`main()` | Kennen keinen Filter-Parameter | Aufrufer können der Auswahl keine Hinweise mitgeben |
| `_write_validation_log()` | Schreibt `validator`, `validated_at`, `workflow_id`, `passed`, `error_count`, `errors`, `min_locations_checked` ins YAML | Kein Feld, das eine bewusst abgeschaltete Altersschranke samt Begründung sichtbar macht |

**Vorbild `briefing_mail_validator.py` (seit #780):** `_message_matches()`
als reines Prädikat, `--subject-contains`-Argument mit `default=None`,
„beide Filter `None` → True" für Rückwärtskompatibilität, `ValueError` bei
keinem Treffer, der **nennt, wonach gesucht wurde**
(`briefing_mail_validator.py:546-563, 609-612`). Dieselbe Struktur wird hier
übernommen, nicht neu erfunden.

**Vorbild für die Abschalt-Begründung:** `qa_gate.py --no-visual "<Grund>"`
— ein Schalter, der eine Begründungs-Zeichenkette als Pflichtwert verlangt,
statt eines bloßen Boolean-Flags oder eines überladenen Zahlenwerts. Diese
Lieferung überträgt dasselbe Muster auf `--ignore-mail-age`.

## Estimated Scope

- **LoC:** ~360-450 (Rechenweg unten) — **liegt deutlich über dem
  250-Zeilen-Deckel**. PO hat die Größenordnung bereits vorab akzeptiert
  („~290-390 ist in Ordnung, ich hole die Freigabe ein") — diese Spec
  rechnet AC-6 und den `--ignore-mail-age`-Schalter ein und schreibt die
  dadurch gestiegene Zahl ehrlich fort, keine Schönrechnung.
- **Files:** 1 Produktivdatei, 1 Testdatei (bestehend, erweitert)
- **Effort:** medium

### Rechenweg

**Produktivcode — `.claude/hooks/email_spec_validator.py`:**

| Änderung | Netto-Zeilen |
|---|---|
| `_decode_subject()` (neu) — RFC-2047-Dekodierung, 1:1 das Vorbild aus `briefing_mail_validator.py:528-543` | ~12 |
| `_message_matches(headers, subject_contains=None)` (neu) — löst die bisher **doppelt** gepflegte Marker-Prüfung aus `_select_compare_uid` und dem Inline-Scan in `_fetch_latest_message` ab; danach gibt es genau EINE Trefferbedingung, keine zwei (s. Implementation Details 1) | ~12 |
| `_select_compare_uid(candidates, subject_contains=None)` — Signatur erweitert, Prüfung auf `_message_matches()` umgestellt | ~5 (netto ggü. Ersatz) |
| `_no_compare_mail_error(subject_contains=None, max_age_minutes=None)` — Meldungstext nennt jetzt zusätzlich Betreffs-Fragment und Altersgrenze | ~15 |
| `_age_minutes(internaldate_resp)` (neu) — parst `INTERNALDATE` über `imaplib.Internaldate2tuple()` (stdlib); liefert die Antwort KEINE auswertbare `INTERNALDATE`, erhebt die Funktion `ValueError` statt `None`/Fallback zurückzugeben (AC-6) | ~22 |
| `_fetch_latest_message(imap=None, subject_contains=None, max_age_minutes=60, ignore_mail_age_reason=None)` — Fetch-Kommando auf `(BODY.PEEK[HEADER] INTERNALDATE)` erweitert; nach gefundenem Treffer: Alters-Check via `_age_minutes()` (überspringt ihn nur bei gesetztem `ignore_mail_age_reason`), zweiter Fehlerpfad bei Überschreitung, `_age_minutes()`-`ValueError` propagiert unverändert (kein Auffangen, kein Fallback) | ~45-55 |
| `_write_validation_log()` — neue Felder `max_age_minutes` und `ignore_mail_age_reason` (Text oder `null`) im YAML, sichtbar auch bei erfolgreichem Lauf | ~8 |
| `run_validation()` — Parameter `subject_contains`, `max_age_minutes`, `ignore_mail_age_reason`, Durchreichung | ~10 |
| `main()` — drei neue `argparse`-Argumente (`--subject-contains`, `--max-age-minutes`, `--ignore-mail-age GRUND`); Validierung, dass `--ignore-mail-age` einen nicht-leeren Grund trägt (fail-fast, analog `qa_gate.py --no-visual`) | ~18 |
| Kommentarblock (Prüfdatum-Marker für die neue Ablehnungsursache, Design-Begründung der Tech-Lead-Entscheidungen inkl. `--ignore-mail-age`-Vorbild) | ~22-27 |

**Produktivcode-Summe:** ~155-195 Netto-Zeilen.

**Tests — `tests/tdd/test_compare_validator_mail_selection.py` (bestehend, MODIFY):**

| Test | Inhalt | Netto-Zeilen |
|---|---|---|
| AC-1: benannte Mail trotz jüngerer fremder Mail mit demselben Marker | Neue Testfunktion gegen `_select_compare_uid(candidates, subject_contains=...)` — nutzt die bestehende `_header_bytes(mail_type, subject=...)`-Fixture unverändert | ~25 |
| AC-2: fehlende benannte Mail → hörbarer Abbruch mit Marker+Betreff in der Meldung | Neue Testfunktion, analog `test_ac3_no_compare_mail_raises_clear_error` dieser Datei, mit `subject_contains` gesetzt | ~25 |
| AC-3: Mail älter als Altersgrenze wird trotz korrektem Inhalt abgelehnt | Neue Testfunktion gegen `_fetch_latest_message(imap=fake, max_age_minutes=...)` — erweitert `_RecordingIMAPFake` um ein optionales `internaldate`-Feld je Mail-Eintrag (Default „frisch", bestehende 11 Tests bleiben unverändert grün) | ~45-60 |
| AC-4: Aufruf ohne neue Argumente verhält sich wie bisher (Regression) | Neue Testfunktion, ruft `_fetch_latest_message(imap=fake)` ohne neue Argumente auf einer frischen Fake-Mail auf, erwartet identisches Ergebnis zu `test_ac4_full_fetch_uses_body_peek_not_rfc822` | ~25 |
| AC-5: `--ignore-mail-age "<Grund>"` macht die Abschaltung samt Begründung im Log sichtbar | Neue Testfunktion gegen `run_validation(ignore_mail_age_reason="...", ...)`/`_write_validation_log()` — prüft, dass das YAML-Feld `ignore_mail_age_reason` den übergebenen Text (nicht nur `true`/`false`) trägt; zweiter Teil derselben oder einer begleitenden Testfunktion belegt, dass ein leerer/fehlender Grund bei `main()`/Argument-Validierung abgelehnt wird | ~35-40 |
| AC-6 (neu): fehlende `INTERNALDATE` in der Fetch-Antwort → hörbarer Abbruch, kein Rückgriff auf `Date`-Header | Neue Testfunktion gegen eine Variante der erweiterten `_RecordingIMAPFake`, deren Fetch-Antwort für die gewählte uid KEINEN `INTERNALDATE`-Bestandteil enthält; die Fake-Mail trägt zusätzlich einen validen `Date`-Header, um zu beweisen, dass er NICHT als Ersatz herangezogen wird | ~35-45 |
| `_RecordingIMAPFake`-Erweiterung (INTERNALDATE-Antwortformat inkl. „fehlt"-Variante, `header_fetch_count()`-kompatibel) | Erweiterung bestehender Klasse, kein neuer Fixture-Apparat | ~25-35 |

**Test-Summe:** ~215-265 Netto-Zeilen.

**Gesamt:** ~370-460 Netto-Zeilen (Kopf-Spanne oben auf ~360-450 gerundet).
Gestiegen gegenüber der Vorversion dieser Spec (~290-390): AC-6 mit eigenem
Fehlerpfad und eigener Testfunktion sowie der begründungspflichtige
`--ignore-mail-age`-Schalter (statt eines einzeiligen Sentinel-Werts) kosten
zusammen ~70-80 Netto-Zeilen mehr, überwiegend in den Tests.

### Empfehlung zur Deckel-Einhaltung

PO hat die Größenordnung bereits vorab akzeptiert und holt die Freigabe für
den erhöhten Deckel ein. Kein inhaltlicher Schnitt vorgeschlagen: AC-6 und
der begründungspflichtige Schalter sind beide Teil der Entscheidung, die
Issue #1408 laut PO beheben soll (stiller Rückfall auf eine schwächere
Zeitquelle bzw. eine ohne Begründung abschaltbare Schranke wären dieselbe
Art von Lücke, nur verschoben). Empfehlung unverändert:
`workflow.py set-field loc_limit_override 500` vor der Implementierung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/briefing_mail_validator.py` (`_message_matches`, `_decode_subject`, `--subject-contains`) | REFERENZ (Vorbild) | Struktur- und Namensvorbild für den Betreffs-Filter, seit #780 produktiv |
| `qa_gate.py` (`--no-visual "<Grund>"`) | REFERENZ (Vorbild, vom Koordinator benannt) | Namens- und Verhaltensvorbild für `--ignore-mail-age "<Grund>"`: ein Schalter, der eine Begründung als Pflichtwert verlangt statt eines bloßen Flags/Sentinels. Datei liegt außerhalb dieses Repos (Plugin), daher keine Zeilenangabe verifizierbar |
| `tests/tdd/test_compare_validator_mail_selection.py` | MODIFY | Trägt bereits die Fixture-Helfer (`_header_bytes()`, `_RecordingIMAPFake`), die für alle 6 ACs erweitert bzw. wiederverwendet werden |
| `.claude/hooks/renderer_mail_gate.py` | PROZESS (unverändert) | Macht einen bestandenen `email_spec_validator.py`-Lauf zur Commit-Pflicht für `compare_html.py` — Abnehmer des Nachweises, den diese Lieferung robuster macht |
| `.claude/hooks/staging_gate.py` | PROZESS (unverändert) | Nutzt denselben Validator-Nachweis für die Staging-Attestation |
| `CLAUDE.md:153`, `.claude/commands/e2e-verify.md:98`, `.claude/standards/email_formatting.md:191` | AUFRUFER (unverändert) | Rufen den Validator ohne Argumente auf — müssen nach dieser Lieferung identisch funktionieren (AC-4) |
| Python-Stdlib `imaplib.Internaldate2tuple()` | NUTZUNG (neu) | Einzige im Projekt bereits verfügbare, korrekte Umrechnung der IMAP-`INTERNALDATE`-Server-Antwort in ein Zeit-Tupel — kein selbstgebautes Parsing nötig |

## Implementation Details

**1. Betreffs-Filter, EIN gemeinsames Prädikat statt zwei Kopien
(`--subject-contains`, optional, Vorbild `briefing_mail_validator.py`):**
`_message_matches(headers, subject_contains=None)` wird neu eingeführt und
ersetzt die heute doppelt gepflegte Marker-Prüfung — sowohl
`_select_compare_uid()` als auch der Inline-Scan in `_fetch_latest_message()`
rufen dieselbe Funktion auf, statt die Bedingung `X-GZ-Mail-Type == "compare"`
(und künftig zusätzlich den Betreffs-Filter) an zwei Stellen zu pflegen.
**Nach dieser Änderung gibt es in der Auswahl genau EINE Trefferbedingung,
keine zwei** — das ist ausdrücklich Teil dieser Lieferung, nicht nur ein
Nebeneffekt: die bestehende Doppelpflege (Kontext-Dokument, Zeilen 174-181)
ist bereits einmal auseinandergelaufen (Grund, warum `_select_compare_uid`
als isolierte, getestete Funktion existiert, aber im echten Fetch-Pfad nie
aufgerufen wurde) und wird mit dieser Vereinheitlichung strukturell
unmöglich gemacht. Ist `subject_contains` gesetzt, muss zusätzlich das über
`_decode_subject()` dekodierte Subject den Substring enthalten. Ist es
`None`, verhält sich die Prüfung exakt wie heute (nur Marker). Das neue
`argparse`-Argument in `main()` trägt `default=None` — die drei dokumentierten
Aufrufer bleiben unverändert lauffähig (AC-4).

**2. Altersschranke, standardmäßig aktiv (`--max-age-minutes`, Default 60):**
`_fetch_latest_message()` fordert das Fetch-Kommando neu als
`(BODY.PEEK[HEADER] INTERNALDATE)` an (bisher nur `(BODY.PEEK[HEADER])`) —
der Zusatz kostet keinen weiteren IMAP-Roundtrip, da er in dieselbe
Fetch-Antwort eingebettet wird, vergrößert aber jede einzelne Antwort
geringfügig. Nachdem der newest-first-Scan die erste (also jüngste) Mail
gefunden hat, die `_message_matches()` erfüllt, wird ihr Alter aus der
mitgelieferten `INTERNALDATE` berechnet (`_age_minutes()`). Liegt das Alter
über `max_age_minutes`, wird **sofort** abgebrochen — ein weiteres
Zurückscannen nach einer älteren, namentlich passenden Mail ergibt keinen
Sinn, weil jede weiter zurückliegende Mail per Definition noch älter ist als
die bereits zu alte, gerade gefundene.

**3. Bewusstes Abschalten mit Pflicht-Begründung (`--ignore-mail-age "<Grund>"`,
ersetzt den ursprünglich vorgesehenen `max_age_minutes=0`-Sentinel):**
Eine `0`, die „unbegrenzt" statt „nichts erlaubt" bedeutet, ist genau die Art
stiller Umkehr, die im entscheidenden Moment falsch gelesen wird. Statt
eines überladenen Zahlenwerts bekommt der Validator einen eigenen,
selbsterklärenden Schalter nach dem Vorbild `qa_gate.py --no-visual "<Grund>"`:
`--ignore-mail-age GRUND` verlangt eine nicht-leere Zeichenkette. Fehlt der
Grund oder ist er leer, bricht `main()` sofort mit einem klaren Fehler ab
(fail-fast) — der Schalter lässt sich nicht versehentlich setzen. Ist er
gesetzt, überspringt `_fetch_latest_message()` die Altersprüfung für den
gefundenen Treffer vollständig (inkl. der `_age_minutes()`-Berufung, s.
Punkt 4 — bewusstes Abschalten der Zeitprüfung deckt zwangsläufig auch die
Prüfung auf fehlende `INTERNALDATE` mit ab, das ist Teil derselben bewussten
Entscheidung). Der Grund-Text wird bis in `_write_validation_log()`
durchgereicht (s. Punkt 6) — der abgeschaltete Schutz ist damit nicht nur
sichtbar, sondern **begründet**.

**4. `INTERNALDATE` statt `Date`-Header — fehlende Server-Zeit ist ein Fehler,
kein Fallback (AC-6):** Im vorhandenen Fetch-Pfad wird `INTERNALDATE` heute
**nicht** angefordert — bestätigt durch Volltextsuche über das gesamte
Repository (einziger Treffer: das Kontextdokument selbst). Die Umsetzung
nutzt `imaplib.Internaldate2tuple()`, den dafür vorgesehenen Stdlib-Helfer,
statt eigenes Parsing der IMAP-Zeitzeichenkette zu bauen. Liefert die
Fetch-Antwort für die gewählte Mail keinen auswertbaren `INTERNALDATE`-Anteil
(Server liefert das Item nicht, oder `Internaldate2tuple()` kann die Antwort
nicht parsen), erhebt `_age_minutes()` `ValueError` — **nicht** `None`,
**nicht** einen Rückfall auf den `Date`-Header der Mail. Dieser Fehler
propagiert unverändert durch `_fetch_latest_message()` bis zum Aufrufer; er
wird nirgends abgefangen und stillschweigend kompensiert. Das gilt auch dann,
wenn die Mail selbst einen validen `Date`-Header trägt — der Prüfer weicht
bewusst nicht auf die absenderseitige Zeitangabe aus, weil sie vom Absender
manipulierbar ist (der ganze Zweck der `INTERNALDATE`-Wahl, s. Purpose). Ist
`--ignore-mail-age` gesetzt, entfällt dieser Check vollständig (Punkt 3).

**5. Fehlermeldungen — hörbarer Abbruch statt stiller Rückfall:**
Drei getrennte Fehlerpfade, alle `ValueError`:
- **Kein Treffer für Marker+Betreff:** `_no_compare_mail_error(subject_contains, max_age_minutes)`
  — nennt Marker, Betreffs-Fragment (falls gesetzt) und aktive Altersgrenze
  (falls aktiv).
- **Treffer gefunden, aber zu alt:** nennt die gefundene Mail (Subject), ihr
  Alter in Minuten, die konfigurierte Grenze und den Hinweis, dass
  `--ignore-mail-age "<Grund>"` die bewusste Abschaltung ist.
- **Treffer gefunden, aber keine auswertbare `INTERNALDATE`:** nennt die
  gefundene Mail und den fehlenden Server-Zeitstempel als Grund — ohne
  Rückgriff auf den `Date`-Header (AC-6).

**6. Log-Sichtbarkeit (`_write_validation_log()`):** Heute schreibt die
Funktion (Zeilen 78-86) `validator`, `validated_at`, `workflow_id`, `passed`,
`error_count`, `errors`, `min_locations_checked`. Neu: zwei Felder werden
**immer** geschrieben — auch bei erfolgreichem Lauf (`passed: true`) —
`max_age_minutes` (der konfigurierte Wert) und `ignore_mail_age_reason`
(der übergebene Grund-Text oder `null`, wenn die Schranke aktiv war). Damit
kann eine bewusst abgeschaltete Schranke weder unbemerkt noch unbegründet
zur Gewohnheit werden. `run_validation()` und `main()` reichen beide Werte
bis zum Log-Aufruf durch.

## Expected Behavior

- **Input:** Ein Aufruf von `email_spec_validator.py` — optional mit
  `--subject-contains <Fragment>`, `--max-age-minutes <N>` und/oder
  `--ignore-mail-age "<Grund>"` — gegen das geteilte Test-Postfach, das
  mehrere Mails unterschiedlichen Typs, Alters und Subjects enthalten kann
  (parallele Sitzungen).
- **Output:** Ohne neue Argumente: identisches Verhalten wie heute, solange
  die gewählte Mail innerhalb der Standard-Altersgrenze (60 Minuten) liegt
  UND der Server eine auswertbare `INTERNALDATE` liefert. Mit
  `--subject-contains`: die namentlich passende Mail wird gewählt, auch wenn
  eine jüngere fremde Mail mit demselben Marker daneben liegt. Fehlt die
  passende Mail, ist die einzig passende zu alt, oder liefert der Server
  keine auswertbare Server-Zeit: `ValueError` mit den jeweils relevanten
  Angaben in der Meldung, kein stiller Fallback. Mit `--ignore-mail-age
  "<Grund>"`: Alters- und `INTERNALDATE`-Prüfung entfallen bewusst, der Grund
  landet im Log. Das Validator-Log trägt in jedem Lauf die Felder
  `max_age_minutes` und `ignore_mail_age_reason`.
- **Side effects:** Keine — der Prüfer bleibt ein reines Analyse-Skript ohne
  Schreibzugriff auf Mail-Inhalte, Renderer oder Persistenz; IMAP-Fetches
  bleiben ausschließlich `BODY.PEEK`-basiert (kein `\Seen`-Flag, unverändert
  seit #1124).

## Acceptance Criteria

- **AC-1:** Given zwei Mails im Postfach tragen denselben Compare-Marker,
  aber nur die ältere trägt das gesuchte Betreffs-Fragment / When der Prüfer
  mit `--subject-contains` nach der benannten Mail sucht / Then wählt er die
  benannte (ältere) Mail, obwohl eine jüngere fremde Mail mit demselben
  Marker daneben liegt.
  - Test: `tests/tdd/test_compare_validator_mail_selection.py` (MODIFY) —
    neue Testfunktion gegen `_select_compare_uid(candidates, subject_contains=...)`
    mit zwei `compare`-Kandidaten unterschiedlichen Subjects, erwartet die
    UID der älteren, namentlich passenden Mail.

- **AC-2:** Given die gesuchte, namentlich markierte Mail existiert nicht im
  Postfach (kein Kandidat erfüllt Marker UND Betreffs-Fragment gleichzeitig)
  / When der Prüfer danach sucht / Then bricht er hörbar mit `ValueError` ab,
  dessen Meldung sowohl den erwarteten Marker als auch das gesuchte
  Betreffs-Fragment nennt — statt still die nächstbeste Mail zu nehmen.
  - Test: `tests/tdd/test_compare_validator_mail_selection.py` (MODIFY) —
    neue Testfunktion analog `test_ac3_no_compare_mail_raises_clear_error`,
    mit `subject_contains` gesetzt und keinem passenden Kandidaten; prüft
    beide Fragmente in der Fehlermeldung.

- **AC-3:** Given die einzige namentlich passende Mail ist älter als die
  konfigurierte Altersgrenze / When der Prüfer sie über `_fetch_latest_message()`
  auswählt / Then lehnt er sie als Nachweis ab, auch wenn ihr Inhalt
  fehlerfrei wäre — der Abbruch nennt Alter und Grenze.
  - Test: `tests/tdd/test_compare_validator_mail_selection.py` (MODIFY) —
    neue Testfunktion gegen die erweiterte `_RecordingIMAPFake` mit einer
    `INTERNALDATE` deutlich vor dem `max_age_minutes`-Fenster, erwartet
    `ValueError` statt einer erfolgreich zurückgegebenen Message.

- **AC-4:** Given ein Aufruf ohne die neuen Argumente (wie die drei
  dokumentierten Aufrufer `CLAUDE.md:153`, `.claude/commands/e2e-verify.md:98`,
  `.claude/standards/email_formatting.md:191`) und eine ausreichend frische
  Mail im Postfach / When der Prüfer läuft / Then verhält er sich exakt wie
  vor dieser Lieferung — die drei dokumentierten Aufrufe brechen nicht.
  - Test: `tests/tdd/test_compare_validator_mail_selection.py` (MODIFY) —
    neue Testfunktion, ruft `_fetch_latest_message(imap=fake)` ohne
    `subject_contains`/`ignore_mail_age_reason` und mit Default-`max_age_minutes`
    auf einer frischen Fake-Mail auf, erwartet identisches Ergebnis zu
    `test_ac4_full_fetch_uses_body_peek_not_rfc822`.

- **AC-5:** Given die Altersgrenze wurde für einen bewusst geprüften Altfall
  ausdrücklich über `--ignore-mail-age "<Grund>"` ausgeschaltet / When der
  Validierungslauf abgeschlossen ist / Then vermerkt das strukturierte
  Validator-Log sowohl, dass die Schranke deaktiviert war, als auch die
  angegebene Begründung im Klartext — ein abgeschalteter Schutz bleibt weder
  unbemerkt noch unbegründet. Ein leerer oder fehlender Grund wird beim
  Setzen des Schalters abgelehnt.
  - Test: `tests/tdd/test_compare_validator_mail_selection.py` (MODIFY) —
    neue Testfunktion gegen `run_validation(ignore_mail_age_reason="...", ...)`/
    `_write_validation_log()` direkt, prüft, dass das YAML-Feld
    `ignore_mail_age_reason` den übergebenen Text trägt (nicht nur
    `true`/`false`); zusätzliche Assertion (gleiche oder begleitende
    Testfunktion), dass ein leerer String beim Argument-Parsing abgelehnt
    wird.

- **AC-6:** Given der Server liefert für die gewählte Mail keine belastbare
  `INTERNALDATE` (die Fetch-Antwort enthält keinen auswertbaren
  Server-Zeitstempel) / When der Prüfer ihr Alter bestimmen will / Then
  verweigert er die Arbeit hörbar und nennt den Grund — er weicht **nicht**
  auf die absenderseitige `Date`-Header-Zeitangabe aus, selbst wenn diese in
  derselben Mail vorhanden und lesbar wäre.
  - Test: `tests/tdd/test_compare_validator_mail_selection.py` (MODIFY) —
    neue Testfunktion gegen eine Variante der erweiterten `_RecordingIMAPFake`,
    deren Fetch-Antwort für die gewählte uid keinen `INTERNALDATE`-Bestandteil
    enthält (nur `BODY[HEADER]`); die Fake-Mail trägt zusätzlich einen
    validen `Date`-Header, um zu beweisen, dass er nicht stillschweigend als
    Ersatzquelle herangezogen wird. Erwartet: `ValueError`, dessen Meldung
    den fehlenden Server-Zeitstempel benennt.

## Known Limitations

- **`radar_alert_mail_validator.py` und `official_alert_mail_validator.py`
  sind NICHT Teil dieser Lieferung.** Beide haben dieselbe Lücke (kein
  Betreffs-Filter, keine Zeitschranke,
  `radar_alert_mail_validator.py:175-208` und
  `official_alert_mail_validator.py:257-299`), aber ihre Mail-Typen werden
  nicht von parallelen Compare-Tests erzeugt — das Kollisionsrisiko ist dort
  ungleich kleiner. Folgearbeit an #1408, damit es nicht verfällt.
- **Die Altersschranke ist eine neue Ablehnungsursache und trägt ein
  Prüfdatum (Regel-Budget, `created` + 90 Tage: 2026-07-28 → 2026-10-26).**
  Bewährt sich der Standardwert von 60 Minuten nicht (zu eng: legitime, aber
  langsame Staging-Läufe scheitern; zu weit: fängt die eigentliche
  #1408-Ursache nicht mehr zuverlässig), ist eine Anpassung oder ein Rückbau
  fällig.
- **`INTERNALDATE` kostet einen zusätzlichen Fetch-Bestandteil, keinen
  zusätzlichen Roundtrip** — er wird in dieselbe kombinierte
  `BODY.PEEK[HEADER] INTERNALDATE`-Fetch-Anfrage eingebettet wie der ohnehin
  nötige Header-Fetch. Bei sehr tiefen Scans (F001-Fall, Compare-Mail liegt
  unter vielen frischeren Fremd-Mails) vergrößert sich dadurch jede der
  potenziell vielen Einzelantworten geringfügig.
- **Das genaue Antwortformat kombinierter `INTERNALDATE`-Fetches muss in der
  Testphase gegen das ECHTE Postfach verifiziert werden — nicht gegen einen
  selbstgebauten Nachbau.** Diese Spec legt `imaplib.Internaldate2tuple()`
  als Parsing-Mechanismus fest (korrekter Stdlib-Weg für IMAP-`INTERNALDATE`-
  Antwortzeilen). Die Kern-Schicht-Tests gegen `_RecordingIMAPFake` (Zwei-
  Schichten-Testpolitik, CLAUDE.md) prüfen die LOGIK unter einer angenommenen
  Antwortstruktur — sie können nicht beweisen, dass diese Struktur der
  tatsächlichen Stalwart-Antwort entspricht, weil ein handgebauter Fake nur
  die eigene Annahme zurückspiegelt. Diese Annahme muss zusätzlich in der
  Live-E2E-Schicht (echtes Test-Postfach, `GZ_IMAP_*`-Credentials) bestätigt
  werden, bevor `_age_minutes()` als bewiesen gilt — das ist Teil der
  TDD-Implementierungsphase, nicht dieser Spec.
- **`--ignore-mail-age` verlangt eine nicht-leere Begründung, deren
  inhaltliche Sinnhaftigkeit nicht maschinell geprüft wird** — analog
  `qa_gate.py --no-visual`. Ein technisch gültiger, aber inhaltsleerer Grund
  (z. B. ein einzelnes Zeichen) ist damit nicht ausgeschlossen; die Pflicht
  wirkt als Reibungspunkt gegen versehentliches Setzen, nicht als
  inhaltliche Qualitätsprüfung.

## ADR-Bezug

- **ADR-Nr.:** keine
- **Rationale:** Diese Lieferung ändert die Mail-Auswahl- und
  Ablehnungslogik eines bestehenden Pflicht-Gate-Skripts, führt aber keinen
  neuen Mechanismus und keine neue Grundsatzentscheidung ein — sie überträgt
  zwei bereits produktive Muster (`briefing_mail_validator.py`-Betreffsfilter
  #780, `qa_gate.py`-Begründungspflicht) auf den zweiten Validator. Weder
  Kanäle noch Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma noch
  die Test-/Deploy-Strategie sind betroffen; der Renderer-Commit-Gate #811
  und die Zwei-Schichten-Testpolitik bleiben unverändert in Kraft.

## Changelog

- 2026-07-28d (bei der Staging-Verifikation gefunden, Umfang bewusst
  erweitert): **F005 — die Protokolle fraßen einander.**
  `_write_validation_log()` baute den Dateinamen nur mit Sekundenauflösung und
  legte per `os.rename` ab; zwei Läufe in derselben Sekunde überschrieben sich
  lautlos. Real passiert: ein bestandener Nachweis wurde von einem
  gescheiterten gefressen, worauf die Staging-Attestation zu Recht auf
  AMBIGUOUS stehen blieb. Das wiegt schwer, weil das Protokoll der Nachweis
  ist, den `renderer_mail_gate.py` liest.
  - Fix: neuer geteilter Helfer `.claude/hooks/_validator_log.py`
    (Mikrosekunden im Namen, `os.link` in einer Zähler-Schleife statt
    `os.rename` — atomar, damit auch parallele Prozesse nicht dieselbe Datei
    belegen; parallele Sitzungen sind hier der Normalfall).
  - **Ausweitung auf alle vier Mail-Validatoren** (`email_spec`, `briefing`,
    `radar_alert`, `official_alert`) statt nur auf den Compare-Prüfer:
    identischer Fehler, identischer Fix. Der Briefing-Prüfer ist sogar stärker
    betroffen — auch er ist Pflicht-Nachweis für #811, und dort wird
    „senden → validieren" paarweise mehrfach hintereinander ausgeführt.
    Geteilt ist ausdrücklich nur die **Ablage**, nicht die Erzeugung des
    Inhalts (zwei der vier bauen ihr YAML von Hand — das zusammenzuführen wäre
    eine Verhaltensänderung ohne Bezug zu F005).
  - **Nachbesserung nach Adversary Runde 4 (BROKEN):** Der erste Fix hängte
    den Kollisions-Zähler **hinter** die Endung (`..._email_validation_1.yaml`)
    und fiel damit aus dem `glob("*_<kind>_validation.yaml")` der Abnehmer —
    die ausgewichene Datei war für das Gate unsichtbar. Also dasselbe Symptom,
    nur über Unsichtbarkeit statt Überschreiben. Der Zähler steht jetzt im
    **Präfix**; die Endung ist der Vertrag mit dem Gate und bleibt unangetastet.
  - **Die eigentliche Lücke war der Test:** Neun grüne Tests bestätigten
    Eindeutigkeit, Inhalt und sogar die Endung als Zeichenkette — und
    übersahen, dass das Gate die Datei nicht findet. Eine Endung als String zu
    prüfen sieht wie eine Vertragsprüfung aus, bestätigt aber nur das eigene
    Namensschema. Erst der Aufruf der **echten** Prüffunktionen des Gates
    (`_validator_log_ok`, `_compare_validator_log_ok`,
    `_radar_validator_log_ok`, `_official_validator_log_ok`) prüft den
    Vertrag; der Test enthält zusätzlich die Gegenprobe, dass die alte
    Namensform abgelehnt wird.
  - Adversary nach **fünf Runden** VERIFIED, mit eigener Reproduktion statt
    Übernahme der Entwickler-Tests.
- 2026-07-28c (Adversary-Fix-Schleife, keine AC-Änderung): Vier Umgehungswege
  gefunden und geschlossen — **alle derselben Klasse: ein Wert, der
  unauffällig „keine Prüfung" bedeutet.**
  - **F001** (HIGH, Adversary): `--max-age-minutes` war nach oben unbegrenzt;
    ein absurd hoher Wert hebelte die Frischeprüfung aus, ohne Begründung und
    ohne Spur im Log — dieselbe stille Umkehr, die beim `0`-Sentinel bewusst
    vermieden wurde. Fix: Obergrenze **1440 Minuten**, **und** jede Abweichung
    vom Standardwert 60 wird protokolliert (`max_age_minutes`,
    `max_age_minutes_default`, `max_age_minutes_overridden`). Nur eines von
    beiden hätte die Umgehung von „unendlich" auf „1439" verschoben.
  - **F002** (MEDIUM, Adversary): Die Begründungspflicht sass nur in `main()`,
    ein direkter Funktionsaufruf mit leerem Grund kam durch. Fix: Prüfung dort,
    wo die Entscheidung fällt.
  - **F003** (Entwickler-Selbstfund): `--subject-contains ""` schaltete den
    Filter still ab — ein leeres Fragment passt auf jede Mail. Trifft den Kern
    dieser Lieferung am direktesten: wer den Filter setzt, glaubt seine eigene
    Mail benannt zu haben und prüft die fremde. Fix: leeres/Leerraum-Fragment
    wird abgelehnt, an **beiden** Einstiegen.
  - **F004** (MEDIUM, Adversary Runde 2): `max_age_minutes=float('nan')`
    umging Obergrenze und Altersvergleich zugleich (`nan > x` ist immer falsch)
    **und** liess `_write_validation_log()` lautlos gar kein Log schreiben —
    der schlechteste Ausgang, weil das Log der Nachweis ist, den das
    Commit-Gate liest. Fix: `math.isfinite`-Prüfung; zusätzlich wurde das
    `except Exception: pass` im Log-Schreiber durch eine stderr-Warnung
    ersetzt (Exit-Code unverändert, nur die Lautlosigkeit ist weg).

  Alle vier Prüfungen sitzen jetzt in **einer** Funktion
  (`_check_selection_arguments()`), mit der Regel als Kommentar darüber — wer
  dort künftig ein Argument ergänzt, sieht sie, bevor er sie bricht.
  Tatsächlicher Umfang: +381/-21 am Validator, +580/-12 in der Testdatei —
  über der Schätzung (~360-450), PO-Freigabe für die angehobene Grenze lag vor.
- 2026-07-28b (Koordinator-Review, keine neue AC-Nummerierungslücke):
  AC-6 ergänzt (fehlende `INTERNALDATE` = hörbarer Abbruch, kein
  `Date`-Header-Fallback); `max_age_minutes=0`-Sentinel durch begründungspflichtigen
  Schalter `--ignore-mail-age "<Grund>"` ersetzt (Vorbild `qa_gate.py
  --no-visual`), AC-5 entsprechend nachgezogen; `_message_matches()` als
  gemeinsames Prädikat explizit in Implementation Details verankert. Umfang
  von ~290-390 auf ~360-450 Netto-Zeilen korrigiert (AC-6 plus Schalter
  kosten zusammen ~70-80 Zeilen mehr, überwiegend in den Tests) — nicht
  schöngerechnet.
- 2026-07-28: Initial spec created (Fix #1408).
