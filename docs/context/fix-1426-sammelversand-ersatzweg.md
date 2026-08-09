# Context: fix-1426-sammelversand-ersatzweg

## Request Summary
Sammelversand an mehrere Empfänger (erreichbar über Ortsvergleich-Presets) hat zwei
zusammenhängende Defekte in `EmailOutput`: (A) die beiden Ersatz-Postausgänge brechen
beim ersten abgelehnten Empfänger komplett ab, statt wie der Primärweg jeden Empfänger
einzeln zu behandeln; (B) lehnt der Mailserver *alle* Empfänger ab, meldet `send()`
trotzdem Erfolg, weil jede Ablehnung nur geloggt wird und kein Erfolgs-Check existiert.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/channels/email.py` | Kernstück. `_dial_and_send()` (:456) ist seit #1412 S3a der EINE Transport-Ort für Primär- und beide Ersatzwege. Docstring dort verweist bereits explizit auf #1426 als offen. `send()` (:596-975) orchestriert Retry/Ersatzweg-Auswahl. |
| `tests/test_mail_recipient_parity.py` | Bestehender Struktur-Test (`_finde_guard_if`) sucht die Empfänger-Guard-`If`-Anweisung als **oberste Ebene** von `send()` — kein `ast.walk`. Bei Umbau von `send()` prüfen, ob dieser Test noch die richtige Region trifft (siehe Memory-Falle unten). |
| `tests/tdd/test_telegram_test_mode_guard.py:278-303` | Vorbild-Testmuster laut Issue: Sink am Transportrand, der je Empfänger gezielt ablehnt. |
| `src/services/notification_service.py` | Aufrufer von `EmailOutput(...).send(...)` — u. a. Zeile 736/762 (Compare-Mehrempfänger-Pfad), 469, 835, 974, 1198, 1311, 1466/1502 (überwiegend Einzelempfänger). |
| `src/services/scheduler_dispatch_service.py:333` | Ortsvergleich-Preset liefert Feld `empfaenger` (Fallback `mail_to` bei leer, `:338`) — Einstiegspunkt für Mehrempfänger-Versand. |
| `src/services/radar_alert_service.py:96` | Weiterer direkter `EmailOutput(...).send(...)`-Aufrufer, ebenfalls betroffen falls Mehrempfänger. |

## Existing Patterns

- **`isolate_per_recipient`-Parameter** (`_dial_and_send`, :465) steuert bereits die
  Asymmetrie: Primärweg (`True`, aufgerufen `:836`) fasst jeden `sendmail()`-Call in
  `try/except smtplib.SMTPException` (:501-522) und loggt nur; beide Ersatzwege
  (`False`, aufgerufen `:586` und `:900`) tun das nicht — ein `SMTPException` bei
  einem Empfänger reißt die restliche Schleife (:523-524) mit.
- Primärweg-Loop endet ohne Rückgabewert/Erfolgs-Tracking; `send()` interpretiert
  jedes normale Return von `_dial_and_send()` als vollen Erfolg (`:843`).
- `smtplib.SMTPServerDisconnected` wird VOR dem generischen `SMTPException`-Zweig
  behandelt (:503-518) — bei einer Erweiterung um Erfolgs-Tracking darf dieser
  Vorrang nicht verändert werden (Transportabbruch ≠ Empfänger-Ablehnung).
- Guard-Reihenfolge in `send()` (Herkunftssperre #1476, Allowlist #1219) bleibt
  unverändert vor der Dial-Schleife — dieser Fix betrifft nur, was *nach* dem Dial
  passiert.

## Dependencies

- **Upstream (was `_dial_and_send`/`send` nutzt):** `smtplib.SMTP`, `_phase_timeout_or_raise()`
  (#1448 S1 Zeitbudget), `_fallback_recipients_blocked()` (#1412 S1 Guard vor Ersatzweg).
- **Downstream (was von `send()`/`EmailOutput` abhängt):** `notification_service.py`
  (Trip- und Compare-Versand), `radar_alert_service.py` (Alarme). Ein geänderter
  Fehlerfall (`OutputError` bei Totalablehnung) muss von diesen Aufrufern bereits
  behandelbar sein — sie fangen `OutputError` schon heute für andere Fehlerarten ab.

## Existing Specs
- `docs/specs/bugfix/email_retry_mechanism_spec.md` v1.0 — Retry-Mechanismus (Referenz in `send()`-Docstring)
- `docs/context/fix-1412-s3-transport-kapselung.md` — Analyse zu `_dial_and_send`, Abschnitt „Antwort auf Frage 1" (Ursprung der #1426-Erfassung)

## Risks & Considerations

- **Renderer-Commit-Gate (#811):** `src/output/channels/email.py` steht auf der
  geschützten Liste (`.claude/hooks/renderer_mail_gate.py:45`). Commit blockiert,
  bis im aktiven Workflow beide frisch vorliegen: `tests/tdd/test_issue_811_mode_matrix.py`
  grün UND ein erfolgreicher `briefing_mail_validator.py`-Lauf.
- **Struktur-Test-Falle (#1412-Memory):** `test_mail_recipient_parity.py::_finde_guard_if`
  sucht die Guard-`If` nur auf der obersten Ebene von `send()`. Falls die Änderung
  Logik in eine Hilfsmethode auslagert, könnte dieser Test „Region verloren" melden,
  ohne dass die Guard-Prüfung selbst kaputt ist — vor Eingriff an `send()` gegenprüfen,
  Fixture-Wert (`verzweigungen_python`) nicht blind nachziehen.
- **Kombinierter Fix zwingend:** Issue betont ausdrücklich, A und B nur getrennt zu
  fixen würde B auf die Ersatzwege ausbreiten (Einfassung ohne Erfolgs-Check).
- **Kern-Schicht genügt:** Laut Issue kein Staging-Nachweis nötig — der Ersatzweg ist
  im Betrieb praktisch nicht gezielt provozierbar, ein Sink-Test am Transportrand
  (Vorbild `test_telegram_test_mode_guard.py`) ist der tragfähige Nachweis.
- **`radar_alert_service.py:96`** ist ein weiterer direkter Aufrufer — prüfen, ob er
  ebenfalls Mehrempfänger-Listen übergibt (bisher nicht verifiziert, nur Blast-Radius-Hinweis).

## Bug Report (Intake-Phase Verifizierung)

### Reproduktionspfad aus Nutzersicht

**Szenario A — Ersatzweg bricht beim ersten abgelehnten Empfänger ab (Defekt A):**

1. **Ausgangslage:** Ortsvergleich-Preset mit zwei oder mehr Empfängern (die Mehrempfänger-Unterstützung wird bereits vom Compare-Versand erwartet, s.u.)
2. **Versandreihenfolge:** 
   - `notification_service.py:835` → `EmailOutput(...).send(..., to=recipients, compare_hourly_enabled=..., mail_type="compare")`
   - `email.py:597-843` Primärweg mit `isolate_per_recipient=True` (Zeile 836)
   - Der Primärweg wird mit `smtplib.SMTP` verbunden (z.B. Resend)
3. **Fehlerfall Primärweg-Rejection:**
   - Primärserver lehnt den ersten oder einen mittleren Empfänger ab (z.B. `SMTPRecipientsRefused` auf ein lokales Testpostfach `gregor-test@henemm.com` mit 452-Quota-Limit)
   - Die `try/except`-Einfassung (Zeile 501-522) fängt das auf, loggt nur (:520-522), Schleife läuft weiter
   - Die übrigen Empfänger werden versendet
4. **Fehlerfall Ersatzweg (isolate_per_recipient=False, Zeile 586):**
   - Primärweg schlägt mit `OSError`/Timeout/Netz komplett fehl (nicht Empfänger-Einzelablehnung)
   - `_handle_transient_dial_failure()` wird aufgerufen (Zeile 814 oder :882), versucht Ersatzweg (Zeile 578)
   - Ersatzweg wird mit `isolate_per_recipient=False` aufgerufen (Zeile 586)
   - **Defekt:** Zeile 524 hat KEINEN try/except für das zweite und folgende `sendmail()`-Aufrufe
   - Erster Empfänger wird versendet, zweiter Empfänger wird ABGELEHNT → **`SMTPException` wird nicht gefangen**, Schleife bricht ab
   - Alle Empfänger 3+ bekommen nichts, **obwohl sie vielleicht akzeptabel wären** (z.B. andere Provider, andere Quota)

**Szenario B — Totalablehnung meldet Erfolg (Defekt B):**

1. **Ausgangslage:** Ortsvergleich mit zwei Empfängern, beide von derselben Quota-Grenze betroffen
2. **Versandablauf Primärweg:**
   - Server antwortet auf BEIDE `sendmail()`-Aufrufe mit `SMTPRecipientsRefused` (z.B. 452 "Quota exceeded")
   - Beide Fehler werden in der `try/except` (Zeile 501-522) abgefangen und nur geloggt
   - Schleife endet normal, `_dial_and_send()` kehrt nach Zeile 524 zurück (kein return-Statement, implizites `None`)
3. **Erfolgs-Check in send():**
   - Nach der `_dial_and_send()`-Rückkehr (Zeile 838) prüft der Code NICHT, ob überhaupt ein Empfänger erreicht wurde
   - Zeile 843: einfach `return` — gibt dem Aufrufer (notification_service.py:835) den Eindruck, die Mail wurde versendet
   - **Defekt:** Beide Empfänger wurden abgelehnt, aber `notification_service.py` sieht keinen Fehler, `mail_type="compare"` wird im Nutzer-Notifikations-State als Erfolg gebucht

### Betroffene Code-Stellen

| Datei | Zeilen | Defekt | Beschreibung |
|-------|--------|--------|-------------|
| `src/output/channels/email.py` | 500–524 | A | `if isolate_per_recipient:` → try/except nur bei `True`; bei `False` (Ersatzweg) kein Schutz |
| `src/output/channels/email.py` | 523–524 | A | Ersatzweg-Zeile ohne try/except: `server.sendmail(from_addr, [recipient], msg.as_string())` |
| `src/output/channels/email.py` | 836 | — | Primärweg-Aufruf mit `isolate_per_recipient=True` (korrekt) |
| `src/output/channels/email.py` | 586 | — | Ersatzweg-Aufruf mit `isolate_per_recipient=False` (hier sitzt Defekt A) |
| `src/output/channels/email.py` | 838–843 | B | Nach `_dial_and_send()` kein Erfolgs-Check; einfach `return` ohne zu prüfen, ob ein Empfänger erreicht wurde |
| `src/services/notification_service.py` | 835–842 | — | Compare-Report-Versand mit `to=recipients` (mehrere möglich); ruft `EmailOutput(...).send()` ohne try/except auf (propagiert Fehler korrekt, aber Defekt B sorgt dafür, dass kein Fehler kommt) |

### Reproduktionsmechanismus (Sink-Test-Vorbild)

Nach Vorbild von `tests/tdd/test_telegram_test_mode_guard.py:278-303`:
- Mock-Sink auf dem Primärweg: antwortet normal auf Empfänger 1, wirft `smtplib.SMTPRecipientsRefused` auf Empfänger 2+
- Ersatzweg ausgewogen verfügbar (kein Netzfehler)
- **Defekt A:** Ersatzweg-Loop bricht nach Empfänger 1 ab → Empfänger 2 wird nicht versendet
- **Defekt B:** Primärweg-Loop mit zwei Empfängern, BEIDE Ablehnung → `send()` kehrt mit Code 0 (Erfolg) zurück

### Offene Fragen zur Spec

1. **Erfolgs-Semantik:** Was ist ein „erfolgreicher Versand" bei Mehrempfänger? Mindestens einer? Alle? Oder wird erwartet, dass der Aufrufer (notification_service.py) selbst `recipients` aufteilt und pro Empfänger einzeln aufruft?
   - Aktueller Stand: `send()` dokumentiert kein Verhalten für Mehrempfänger-Totalablehnung (Defekt B)
   
2. **Ersatzweg-Fehlsammelstrategie:** Soll der Ersatzweg wie der Primärweg `isolate_per_recipient=True` nutzen und damit komplett asymmetrisch werden, oder bleibt die Asymmetrie bewusst?
   - Laut Docstring (Zeile 474-478): die Asymmetrie ist bewusst konserviert als „heute noch so", wird aber als #1426 behoben — keine Aussage zur Zielform

3. **Renderer-Commit-Gate #811:** `email.py` steht auf geschützter Liste. Tests `tests/tdd/test_issue_811_mode_matrix.py` und Validator `briefing_mail_validator.py` prüfen Mail-Inhalte, nicht Versand-Logik. Müssen bei dieser Änderung neue Tests hinzukommen (Mehrempfänger-Ablehnung), oder Bestands-Tests aktualisiert?
   - Derzeit kein Bestandstest für Mehrempfänger-Fehlerfall bekannt

### Zusammenfassung (< 300 Worte)

**Root Cause:** Zwei zusammenhängende Implementierungsfehler im Sammelversand (`email.py:456-843`):
- **(A) Ersatzweg-Abbruch:** Parameter `isolate_per_recipient` ist nur beim Primärweg `True` (mit try/except pro Empfänger), bei Ersatzwegen `False` (ohne Einfassung). Ein abgelehnter Empfänger (z.B. Quota 452 auf Ersatzserver) reißt die restliche Schleife mit.
- **(B) Totalablehnung still:** Nach `_dial_and_send()` (Zeile 838) prüft `send()` nicht, ob überhaupt ein Empfänger erreicht wurde. Lehnt der Server alle Empfänger ab, kehrt `send()` normal zurück → `notification_service.py:835` sieht keinen Fehler.

**Reproduktionspfad:** Ortsvergleich-Versand mit mehreren Empfängern via `notification_service.py:835` (`to=recipients`). Primärweg schlägt mit Netzfehler fehl oder ein Empfänger wird auf Primärweg abgelehnt, Ersatzweg wird versucht. Defekt A: Ersatzweg bricht ab. Defekt B: Primärweg lehnt alle ab, send() kehrt erfolgreich zurück.

**Betroffene Dateien:** `src/output/channels/email.py` (Versand-Logik), `src/services/notification_service.py` (Compare-Aufrufer).

**Offene Punkte:** (1) Sollte Erfolg = mindestens ein Empfänger erreicht oder alle? (2) Soll Ersatzweg auch `isolate_per_recipient=True` nutzen (symmetrisch)? (3) Welche neuen Testfälle für Mehrempfänger-Fehler nötig?

## Strategische Bewertung

### 1. Technischer Ansatz

**Erfolgs-Semantik (Antwort auf offene Frage 1):** *Mindestens ein* Empfänger
erreicht = Erfolg. Das ist konsistent mit dem bestehenden
`isolate_per_recipient`-Zweck ("ein abgelehnter Empfänger reißt die übrigen
nicht mit") und mit dem Fail-soft-Muster, das der Compare-Versand bereits für
Telegram/SMS fährt (`notification_service.py`, AC-5 dort: "Telegram-/SMS-Fehler
werden geloggt, reissen aber die anderen Kanaele nicht mit"). Nur *Total*-
Ablehnung (0 von N zugestellt) ist ein Fehler.

**Asymmetrie auflösen (Antwort auf offene Frage 2):** `isolate_per_recipient`
als Parameter entfällt ersatzlos — beide Ersatzwege bekommen dieselbe
try/except-Einfassung wie heute nur der Primärweg (Zeile 500–522). Eine
Variante, die den Parameter behält und beide Aufrufer auf `True` umstellt,
wäre funktional identisch, ließe aber einen toten Parameter mit falscher
Suggestion ("hier gibt es noch eine Wahl") zurück — schlechter für die
nächste Person, die den Code liest.

**Erfolgs-Check-Ort:** *In* `_dial_and_send()`, nicht im Aufrufer. Es gibt
drei Aufrufstellen (:828 Primärweg, :578 und :892 beide Ersatzwege) — den
Zähl-und-Prüf-Code an einer Stelle zu halten vermeidet dreifache Duplikation.
Konkret: eine lokale Liste `fehler: list[tuple[str, Exception]]` sammelt
abgelehnte Empfänger in der bestehenden Schleife; nach der Schleife, wenn
`len(fehler) == len(recipients)` (und `len(recipients) > 1` — der
Ein-Empfänger-Fast-Path in Zeile 494–496 bleibt unverändert, dort propagiert
eine Ablehnung schon heute korrekt als Exception), wird
`raise OutputError("email", f"Alle {len(recipients)} Empfänger abgelehnt: …")`
geworfen. Die drei Aufrufer brauchen dafür KEINE Änderung: der Primärweg-Call
(:828) liegt in `send()`s eigenem try-Block, aber `OutputError` matcht keinen
der nachfolgenden `except`-Zweige (alle smtplib-/OSError-spezifisch) und
propagiert damit unverändert aus `send()` — exakt das gewünschte Verhalten
(Totalablehnung ist ein permanenter Fehler, kein Retry-Kandidat). Die beiden
Ersatzweg-Calls stehen bereits in einem `except Exception as fb_err: raise
OutputError(..., f"fallback also failed: {fb_err}")`-Wrapper — eine dort
geworfene `OutputError` läuft automatisch durch diesen Pfad und liefert die
richtige, bereits vorhandene Fehlermeldungsform.

**`SMTPServerDisconnected`-Vorrang bleibt unangetastet:** Der Fix ändert
nichts an Reihenfolge oder Verhalten dieses Zweigs (Zeile 503–518) — er wird
weiterhin VOR dem generischen `SMTPException`-Zweig geprüft und weiterhin
sofort durchgereicht (kein Sammeln, kein Weitermachen), weil ein toter Socket
kein Empfänger-Problem ist. Nur der bisher `else`-Zweig (Zeile 523–524, heute
ungeschützt) bekommt dieselbe dreiteilige Struktur wie der `if`-Zweig.

**Nettoeffekt am Code:** die `if isolate_per_recipient: … else: …`-Verzweigung
in der Schleife entfällt zugunsten EINES Pfads; Signatur und alle drei
Aufrufer verlieren das `isolate_per_recipient=`-Argument; nach der Schleife
kommt der Fehler-Check.

### 2. Risiko-Bewertung

- **`test_mail_recipient_parity.py::_finde_guard_if` (Struktur-Test-Falle):**
  KEIN Risiko bei diesem Zuschnitt. Der Guard-`If` mit dem Literal `"resend"`
  liegt in `send()` bei Zeile 669 — weit VOR der Retry-Schleife (819ff.) und
  strukturell unberührt von Änderungen in `_dial_and_send()`. Solange die
  Änderung sich auf `_dial_and_send()`/`_handle_transient_dial_failure()` und
  die drei Call-Sites beschränkt (kein Umbau von `send()`s Kontrollfluss vor
  der Schleife), bleibt sowohl die Region-Findung als auch die
  Verzweigungszahl (`verzweigungen_python`-Fixture) unverändert.
- **Gate #811 (Renderer-Commit-Gate):** `email.py` steht auf der geschützten
  Liste — normaler Ablauf, kein Sonderrisiko: `tests/tdd/test_issue_811_mode_matrix.py`
  grün und ein frischer `briefing_mail_validator.py`-Lauf müssen vor dem
  Commit vorliegen. Da dieser Fix reine Versand-*Logik* ändert (nicht
  Mail-*Inhalt*/Rendering), sollte der Mode-Matrix-Test unberührt bleiben —
  trotzdem Pflichtlauf vor Commit, nicht überspringbar.
- **Ein Bestandstest zementiert aktuell genau Defekt A als Sollverhalten:**
  `tests/tdd/test_mail_transport_dial_behaviour.py::test_ac3_ersatzweg_bricht_beim_ersten_abgelehnten_empfaenger_ab`
  (Zeile 243–268, parametrisiert über beide Ersatzwege) erwartet explizit
  `pytest.raises(OutputError)` nach genau zwei von drei Zustellversuchen und
  kommentiert "nach dem abgelehnten Empfaenger darf kein weiterer folgen".
  Dieser Test ist NICHT in `.github/ci_tdd_excludes.txt` gelistet, läuft
  also heute grün in CI und wird durch den Fix zwangsläufig rot — er MUSS im
  selben PR umgeschrieben werden (Vorbild: die direkt benachbarte
  `test_ac2_primaerweg_stellt_trotz_einer_ablehnung_an_die_uebrigen_zu`,
  Zeile 197–228, die dieselbe Erwartung für den Primärweg schon heute
  korrekt formuliert — Ersatzweg-Pendant analog bauen, inkl. neuem Test für
  Totalablehnung = Defekt B). Das ist der zentrale TDD-Umbaupunkt dieser
  Schebe, kein Nebenbefund.
- **Aufrufer (`notification_service.py:835`, Compare-Pfad):** kein
  Nachzug nötig. Der Aufruf steht bereits ohne try/except (Docstring
  Zeile 813–818: "Der E-Mail-Pfad propagiert Fehler unveraendert … damit ein
  SMTP-Ausfall weiterhin als Fehler des Preset-Versands sichtbar bleibt") —
  eine neu geworfene `OutputError` bei Totalablehnung fällt in denselben,
  bereits vorgesehenen Pfad wie jeder andere SMTP-Fehler heute.
- **`radar_alert_service.py:96`:** verifiziert — sendet praktisch immer an
  genau einen Empfänger (`mail_settings.mail_to` oder `to`-Override, beides
  einzelne Strings), trifft also den Ein-Empfänger-Fast-Path (Zeile 494–496),
  der von diesem Fix unverändert bleibt. Kein Nachzugsbedarf.
- **Verhaltensänderung für bestehende Fallback-Aufrufer, die heute (fälschlich)
  einen Fehler sehen:** Fälle, in denen der Ersatzweg heute wegen Defekt A
  einen `OutputError` wirft, obwohl tatsächlich ≥1 Empfänger zustellbar wäre,
  werden nach dem Fix zu Erfolg (mit Log-Zeile pro abgelehntem Empfänger)  —
  das ist die beabsichtigte Korrektur, aber jede Monitoring-/Alerting-Logik,
  die sich auf die heutige Fehlerrate verlässt, sieht danach weniger
  `OutputError`s aus diesem Pfad. Kein bekannter Konsument tut das; nur zur
  Vollständigkeit genannt.

### 3. Scope-Schätzung

| Datei | Art | ~LoC |
|---|---|---|
| `src/output/channels/email.py` | `_dial_and_send()`-Schleife vereinheitlichen + Erfolgs-Check, Signatur + Docstring, 3 Call-Sites (Parameter entfernen) | ~40–60 (netto eher −10 bis +30, da die `if/else`-Verzweigung entfällt) |
| `tests/tdd/test_mail_transport_dial_behaviour.py` | AC-3 umschreiben (Ersatzweg liefert trotz Ablehnung zu), neuer AC für Totalablehnung (Defekt B, beide Wege) | ~60–90 (neue/umgeschriebene Testfunktionen + ggf. neue Helper-Fixtures für "alle Empfänger abgelehnt") |
| `docs/context/…`/Spec | Spec-Dokument für die Scheibe (Pflicht laut Workflow) | separat, zählt nicht gegen das 250-LoC-Limit |

Gesamt: **klar innerhalb des 250-LoC-Budgets**, realistisch 100–150 LoC
Code+Test zusammen. Kein Bedarf für `loc_limit_override`.

### 4. Abhängigkeiten und Reihenfolge

1. Spec schreiben (AC-N-Format), insbesondere die Erfolgs-Semantik
   ("mindestens ein Empfänger") explizit als AC festhalten — das ist die
   einzige echte Design-Entscheidung, der Rest ist mechanisch.
2. TDD RED: `test_ac3_…` umschreiben (rot, weil Ersatzweg heute noch abbricht)
   + neuer Test für Defekt B (Primärweg UND Ersatzweg total abgelehnt → `send()`
   wirft) — beide VOR der Implementierung rot bekommen.
3. Implementierung in `_dial_and_send()` + 3 Call-Sites (GREEN).
4. Gate #811 (Mode-Matrix-Test + `briefing_mail_validator.py`) — unabhängig
   von 1–3, muss vor Commit grün sein, keine Reihenfolgeabhängigkeit zu den
   übrigen Schritten außer "vor Commit".
5. Kein Staging-Nachweis nötig (Issue-Aussage: Ersatzweg im Betrieb praktisch
   nicht gezielt provozierbar) — Kern-Schicht-Sink-Test genügt als Nachweis.

### 5. Empfehlung

**Ersatzwege auf dieselbe Try/Except-Einfassung wie der Primärweg heben
(Parameter `isolate_per_recipient` ersatzlos entfernen), Erfolgs-Check
zentral in `_dial_and_send()` nach der Schleife (`raise OutputError` nur bei
0 von N zugestellt), Erfolgs-Semantik = mindestens ein Empfänger.** Das löst
A und B mit einer einzigen, in sich konsistenten Änderung an einer Stelle,
statt den Check dreimal an den Aufrufstellen zu duplizieren. Größtes
praktisches Risiko ist nicht der Code selbst, sondern der vorhandene Test
`test_ac3_ersatzweg_bricht_beim_ersten_abgelehnten_empfaenger_ab`, der die
heutige Fehlfunktion als Sollverhalten festschreibt — der muss im selben PR
umgedreht werden, sonst bleibt CI nach dem Fix zuverlässig rot.
