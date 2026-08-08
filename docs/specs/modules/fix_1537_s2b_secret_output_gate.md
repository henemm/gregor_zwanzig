---
entity_id: fix_1537_s2b_secret_output_gate
type: feature
created: 2026-08-07
updated: 2026-08-07
status: draft
version: "1.0"
tags: [gate, security, post-tool-use, secrets]
---

# Spec: Ausgabe-Wächter „Secret-Output-Sperre" (Stufe B)

- **Issue:** #1537 Scheibe 2, Stufe B
- **Workflow:** `fix-1537-s2-laufzeit-lecks`
- **created:** 2026-08-07
- **Kontext & Messungen:** `docs/context/fix-1537-s2-laufzeit-lecks.md`
- **Status:** Entwurf — wartet auf PO-Freigabe der Acceptance Criteria

## Approval

- [x] Approved — Product Owner, 2026-08-07 („go", Freigabe der 12 Acceptance Criteria auf Deutsch)

## Zweck in einem Satz

Ein `PostToolUse`-Wächter durchsucht das **Ergebnis** jedes Werkzeugaufrufs nach dem
ausgeschriebenen Wert eines Geheimnisses aus der lokalen `.env` und ersetzt jeden Treffer
durch `***<SCHLÜSSELNAME>***`, bevor Claude das Ergebnis sieht — im Normalfall (kein Fund)
bleibt das Ergebnis unangetastet und es erscheint keinerlei Ausgabe.

## Warum

Scheibe 1 (`secret_in_repo_gate.py`) schützt nur einen einzigen Austrittsweg: vorgemerkte
Dateien beim `git commit`. Zwei Wege bleiben offen. **Stufe A** (Werte, die zur Laufzeit von
einer Datei in eine andere wandern) ist ein eigener Workflow. **Stufe B** — dieser hier —
schließt den zweiten Weg: einen Geheimniswert, der in der **Ausgabe** eines Werkzeugs
zurückkommt, obwohl er im Aufruf selbst nie stand. `PreToolUse` prüft vor der Ausführung und
sieht diesen Wert nicht; der bestehende Egress-Wächter des Plugins (`secret_egress_guard.py`,
#1380) deckt nur ausgehende *Eingaben* ab.

Anlassfall: `tests/tdd/test_issue_1014_live_optin.py:89` vergleicht `os.environ`-Abbilder und
druckt bei Fehlschlag den **Wert** von `GZ_TELEGRAM_TEST_BOT_TOKEN` in die Testausgabe (#1535).
Genau diese Klasse — ein Geheimnis, das über ein Werkzeug-Ergebnis (hier: `Bash`-`stdout`)
sichtbar wird — fängt Stufe B ab. Der eigentliche Fix bleibt im Test (Zusicherung auf
Schlüsselnamen statt Wert umstellen, siehe „Nicht in dieser Scheibe") — dieser Wächter ist das
Netz, nicht der Ersatz.

## Zuschnitt

**Umfang: alle Werkzeuge, kein Ausschluss.** Der bestehende Egress-Wächter überspringt `Read`
und `Grep`, weil er ausgehende *Eingaben* prüft (dort ist ein gelesener Dateiname kein
Geheimnis). Für *Ausgaben* gilt das Gegenteil: `Read` ist gerade der wahrscheinlichste
Austrittsweg — jede Datei, die ein Geheimnis im Klartext enthält (versehentlich committet, aus
einer `.env` kopiert, in einem Log), tritt beim Vorlesen aus. Der Wächter filtert deshalb nicht
nach `tool_name`.

**Ersatzform: `***<SCHLÜSSELNAME>***`**, z.B. `***GZ_SMTP_PASS***`. Nie der nackte Wert, aber
auch nie ein anonymes `***` — ein Ersatz ohne Schlüsselnamen macht die Ausgabe unverständlich
(„wieso ist da plötzlich `***`?"), der Schlüsselname selbst ist nicht das Geheimnis, und die
Form bleibt konsistent zur Meldungsform aus Scheibe 1 (dort: „Schlüssel: GZ_SMTP_PASS", nie der
Wert).

**Durchgehend fail-open — die Umkehrung von Scheibe 1.** Dort ist fail-closed richtig: ein
Irrtum beim Commit-Gate kostet einen blockierten Commit, das ist unbequem, aber ungefährlich.
Hier ist die Lage umgekehrt: der Wächter läuft nach **jedem** Werkzeugaufruf in **jeder**
laufenden Sitzung — ein Irrtum (Plugin fehlt, `.env` unlesbar, unerwartete Nutzlast-Gestalt,
eine nicht vorhergesehene Ausnahme) darf niemals ein Werkzeug-Ergebnis zerstören oder eine
Sitzung blockieren. Jede eigene Störung führt zu: Ergebnis unverändert, Exit 0.

**Stumm im Normalfall.** Kein Fund heißt keinerlei Ausgabe und ein unverändertes Ergebnis. Nur
ein echter Treffer erzeugt überhaupt eine Wirkung.

**Geheimnis-Erkennung wird wiederverwendet, nicht neu gebaut.** Es gibt im Projekt bereits zwei
verschiedene Begriffe von „Geheimnis" (Scheibe 1: enge Suffix-Allowlist mit vier Endungen;
Plugin-Egress-Wächter: breite Regex-Denylist mit Platzhalter-Filter). Ein dritter, eigener
Begriff wäre der Fehler. Dieser Wächter lädt `collect_secrets`, `_is_secret_key`,
`_is_secret_value` aus `core/hooks/secret_egress_guard.py` des Plugins `agent-os-openspec`
per `importlib` — analog zum bestehenden Muster in `.claude/hooks/hook_utils.py` (dort für
`hook_utils.py` des Plugins). Der Import passiert in **zwei getrennten `try`-Blöcken** (Vorbild
`secret_in_repo_gate.py:96-123`), damit eine ältere Plugin-Fassung ohne diese Funktionen den
Wächter nur fail-open werden lässt, statt ihn komplett lahmzulegen.

**Der Mechanismus trägt — gemessen 2026-08-07, der frühere Rückfall entfällt.** Neun Läufe einer
eigenständigen Sitzung (Claude Code 2.1.224) im Scratchpad, mit einem Zufallsmarker, den die
Kindsitzung nur aus dem Werkzeug-Ergebnis kennen konnte. Ergebnis:

| Gesendeter Ersatzwert | Wirkung |
|---|---|
| dict mit **allen fünf** Originalschlüsseln | **ersetzt** |
| dict mit allen fünf **plus** eigenem Zusatzschlüssel | **ersetzt** |
| String | still verworfen |
| dict mit nur `stdout` | still verworfen |
| dict mit nur `stdout` + `stderr` | still verworfen |

🔴 **Das Verwerfen ist vollständig lautlos.** Kein Fehler, kein Hinweis, Hook-Exit 0, Sitzung
läuft normal weiter — auch unter `--debug hooks` erscheint keine Diagnosezeile. Ein falsch
geformter Ersatzwert ist damit **von einem funktionierenden Wächter nicht unterscheidbar**.

**Bauvorgabe, zwingend:** das empfangene `tool_response` **kopieren** und darin nur Werte
ersetzen. Niemals ein frisches Objekt bauen, niemals einen String zurückgeben. Fehlende
Schlüssel führen zur Ablehnung, zusätzliche nicht.

**Zusatznutzen, gemessen:** Bei wirksamer Ersetzung enthält auch das auf Platte gespeicherte
Sitzungsprotokoll (`~/.claude/projects/…/*.jsonl`) den Ersatzwert an beiden Stellen; der
Zufallsanteil des Originals war per Suche in keinem Protokoll auffindbar. Die Maskierung wirkt
also nicht nur auf den Modellkontext, sondern auch auf die dauerhafte Ablage.

## Acceptance Criteria

- **AC-1:** Kein Fund bleibt vollständig unsichtbar.
  Given ein Werkzeug-Ergebnis enthält keinen Wert aus der lokalen `.env`, der als Geheimnis gilt
  When der Wächter nach dem Werkzeugaufruf läuft
  Then bleibt das Ergebnis, das Claude sieht, unverändert, und es erscheint keinerlei zusätzliche
  Ausgabe (kein stderr, kein stdout-Zusatz).
  - Test: Wegwerf-Sitzung mit synthetischer `.env`, ein `Bash`-Aufruf ohne Geheimnis im Ergebnis
    → Prozess-Exit 0, leere zusätzliche Ausgabe.

- **AC-2:** Ein Geheimnis in einer erfolgreichen Bash-Ausgabe erscheint danach nicht mehr im
  Klartext.
  Given eine `.env` mit einem Geheimnis (Schlüssel-Endung passend, Wert lang genug)
  When ein `Bash`-Aufruf erfolgreich durchläuft und der Wert im `stdout` des Ergebnisses steht
  Then ist der ausgeschriebene Wert im Ergebnis, das Claude sieht, nicht mehr im Klartext
  lesbar — an seiner Stelle steht `***<SCHLÜSSELNAME>***`.
  - Test: synthetisches Bash-Erfolgsergebnis (dict mit `stdout`) mit eingebettetem Geheimnis als
    stdin-Payload an den Wächter, geprüft wird die vom Wächter erzeugte Ersatz-Ausgabe.

- **AC-3:** ~~Ein Geheimnis in einer fehlgeschlagenen Bash-Ausgabe erscheint danach nicht mehr im
  Klartext~~ — ENTFÄLLT, belegt unmöglich (2026-08-07).

  Diese Zusicherung ist mit dem Hook-Vertrag **nicht erfüllbar**. Zwei unabhängige Belege:

  1. **Gemessen:** Bei `Exit ≠ 0` wird der `PostToolUse`-Hook **überhaupt nicht aufgerufen**.
     Kontrollläufe mit Zufallsmarker: Exit 0 → eine Protokollzeile im Hook, Exit 1 → **null**
     Zeilen, und die Sitzung sah den Marker wörtlich. Nicht „Ersatz verworfen" — nie aufgerufen.
  2. **Dokumentiert:** „PostToolUse | After a tool call **succeeds**" gegenüber
     „PostToolUseFailure | After a tool call **fails**". Und `PostToolUseFailure` unterstützt
     laut Decision-Control-Tabelle **kein** `updatedToolOutput` — nur `decision: "block"` und
     `additionalContext`. Ein fehlgeschlagenes Ergebnis kann also gemeldet, aber nicht ersetzt
     werden.

  Der zugehörige Test bleibt als Absicherung des String-Zweigs im Wächter erhalten (andere
  Werkzeuge können String-Ergebnisse liefern), verweist aber im Docstring auf diese Grenze. Er
  belegt eine **Fähigkeit**, keine **Wirkung** — und wird deshalb nicht als erfüllte AC gezählt.

  🔴 **Tragweite, offen benannt:** Der Anlassfall #1535 ist ein *fehlschlagender* Test; pytest
  endet dann mit Exit ≠ 0. **Stufe B verhindert den Vorfall nicht, für den sie gebaut wurde.**
  Sie schützt weiterhin: gelesene Dateiinhalte, erfolgreiche Befehlsausgaben, geschriebene
  Dateien und Textänderungen. Der eigentliche Fix für #1535 bleibt im Test selbst — das stand
  schon immer so im Issue, ist jetzt aber keine Empfehlung mehr, sondern die einzige Möglichkeit.

- **AC-4:** Ein Geheimnis in einem gelesenen Dateiinhalt erscheint danach nicht mehr im Klartext.
  Given dieselbe `.env`
  When das `Read`-Werkzeug eine Datei liest, deren Inhalt (verschachtelt unter `file.content`)
  den Wert enthält
  Then ist der Wert im Ergebnis, das Claude sieht, nicht mehr im Klartext lesbar.
  - Test: synthetisches `Read`-Ergebnis mit der gemessenen verschachtelten Form
    `{"file": {"content": "…GEHEIMNIS…"}}` — ohne diesen Test bliebe der wahrscheinlichste
    Austrittsweg ungeprüft.

- **AC-5:** Ein Geheimnis in einem geschriebenen Dateiinhalt erscheint danach nicht mehr im
  Klartext.
  Given dieselbe `.env`
  When das `Write`-Werkzeug eine Datei anlegt, deren Ergebnis (`content` auf oberster Ebene) den
  Wert enthält
  Then ist der Wert im Ergebnis nicht mehr im Klartext lesbar.
  - Test: synthetisches `Write`-Ergebnis mit `content`-Feld auf oberster Ebene.

- **AC-6:** Ein Geheimnis in einer Textänderung erscheint danach nicht mehr im Klartext.
  Given dieselbe `.env`
  When das `Edit`-Werkzeug einen Text ändert und der Wert in `oldString`, `newString` oder
  `originalFile` steht
  Then ist der Wert in keinem dieser drei Felder mehr im Klartext lesbar.
  - Test: synthetisches `Edit`-Ergebnis, Geheimnis einmal in `oldString`, einmal in `newString`,
    einmal in `originalFile` — je einzeln geprüft, damit keines der drei Felder unbemerkt
    durchrutscht.

- **AC-7:** Kurze oder nicht passende Werte lösen keine Maskierung aus.
  Given eine `.env` enthält einen Wert, der entweder zu kurz ist oder dessen Schlüssel nicht zu
  den gesuchten Mustern passt, oder einen bekannten Platzhalterwert (z.B. `changeme`)
  When dieser Wert in einem Werkzeug-Ergebnis vorkommt
  Then bleibt das Ergebnis unverändert — keine Maskierung, keine Ausgabe.
  - Test: Ergebnis mit kurzem Wert und mit einem der vom Plugin-Filter erfassten
    Platzhalterwerte, jeweils Exit 0 und unverändertes Ergebnis. Verhindert, dass der Wächter
    harmlose Werte (Projektnamen, Beispielwerte) fälschlich maskiert.

- **AC-8:** Eine eigene Störung des Wächters führt nie zu einem veränderten oder blockierten
  Ergebnis.
  Given der Wächter selbst kann nicht arbeiten (Plugin-Modul nicht ladbar, `.env` unlesbar, die
  Nutzlast hat eine nicht vorhergesehene Gestalt, oder eine sonstige Ausnahme tritt auf)
  When ein Werkzeugaufruf durchläuft, dessen Ergebnis ein Geheimnis enthält
  Then bleibt das Ergebnis unverändert (Exit 0) — der Wächter blockiert nie und verfälscht das
  Ergebnis nie durch einen eigenen Fehler.
  - Test: Wächter-Aufruf mit fehlendem/nicht ladbarem Plugin (Umgebung ohne Plugin-Registrierung)
    → Ergebnis unverändert. Zusätzlich: kaputtes JSON auf stdin, `tool_response` als unerwarteter
    Typ (z.B. `null`/Zahl) → Ergebnis unverändert, kein Absturz.

- **AC-9:** Eine Fund-Meldung nennt nie den Wert selbst.
  Given der Wächter maskiert einen Fund oder greift auf den Rückfall (stderr-Meldung) zurück
  When die Meldung erzeugt wird
  Then enthält sie ausschließlich Werkzeugname und Schlüsselname — der Wert selbst taucht in
  keiner Ausgabe (stdout, stderr, Ersatz-Ergebnis) auf.
  - Test: Fund-Fall auslösen, Prozess-Gesamtausgabe (stdout + stderr) auf Abwesenheit des rohen
    Werts prüfen, Anwesenheit des Schlüsselnamens prüfen — wichtigste Einzelzusicherung, analog
    zu `test_block_message_never_contains_the_secret_value` aus Scheibe 1.

- **AC-10:** Die Maskierung gilt unabhängig vom Werkzeugnamen.
  Given ein Geheimnis steht im Ergebnis eines Werkzeugs, das weder `Bash`, `Read`, `Write` noch
  `Edit` heißt (z.B. ein MCP-Werkzeug oder ein zukünftig hinzukommendes Werkzeug)
  When dieses Ergebnis den Wert enthält
  Then wird ebenso maskiert wie bei den vier benannten Werkzeugen — es gibt keine Positivliste,
  die ein Werkzeug ausnimmt.
  - Test: synthetisches Ergebnis mit einem frei erfundenen `tool_name` (z.B. `"AnyMcpTool"`) und
    einem generischen Textfeld, das das Geheimnis enthält — Maskierung greift trotzdem.

- **AC-11:** Alles außer dem Geheimnis bleibt unversehrt.
  Given ein Werkzeug-Ergebnis enthält ein Geheimnis **und** übrigen Inhalt (weiterer Text vor und
  nach dem Wert, sowie weitere Felder im Ergebnis)
  When der Wächter maskiert
  Then ist ausschließlich der Geheimniswert ersetzt — jeder andere Text und jedes andere Feld
  kommt unverändert bei Claude an.
  - Test: Ergebnis mit Text vor und nach dem Wert sowie mit weiteren Feldern (`stderr`,
    `interrupted`) — geprüft wird die Anwesenheit **beider** Textteile und aller übrigen Felder.
    Ohne diese AC bestünde eine Umsetzung, die das gesamte Ergebnis durch einen Platzhalter
    ersetzt, die ACs 2–6 vollständig — der Wert wäre weg, aber auch jede nutzbare Ausgabe.

- **AC-12:** Mehrfaches Vorkommen wird vollständig maskiert.
  Given derselbe Geheimniswert steht **mehrfach** in einem Werkzeug-Ergebnis, und zusätzlich
  stehen **zwei verschiedene** Geheimnisse darin
  When der Wächter maskiert
  Then ist kein einziges Vorkommen mehr im Klartext lesbar — weder ein weiteres Vorkommen
  desselben Werts noch das zweite Geheimnis.
  - Test: Ergebnis mit demselben Wert an drei Stellen und einem zweiten Geheimnis an einer
    vierten. Verhindert eine Umsetzung, die nur den ersten Treffer ersetzt.

- **AC-13:** Der Ersatz hat die Gestalt, die die Plattform tatsächlich annimmt.
  Given der Wächter hat ein Geheimnis gefunden und erzeugt einen Ersatz für ein
  Werkzeug-Ergebnis, das als Objekt vorlag
  When der Ersatz an die Plattform übergeben wird
  Then trägt er **jeden** Schlüssel des ursprünglichen Ergebnisses — kein Schlüssel fehlt, und
  der Ersatz ist kein blosser Text.
  - Test: Ergebnis mit den fünf gemessenen Bash-Schlüsseln (`stdout`, `stderr`, `interrupted`,
    `isImage`, `noOutputExpected`) hineingeben; die Schlüsselmenge des Ersatzes muss die
    ursprüngliche vollständig enthalten, und der Ersatz darf kein String sein.
  - **Warum diese eine AC den Mechanismus nennt:** Gemessen wurde, dass die Plattform einen
    String oder ein unvollständiges Objekt **stillschweigend verwirft** — ohne Fehler, ohne
    Hinweis, mit Exit 0. Ein Wächter mit falscher Gestalt sieht in jedem anderen Test wie ein
    funktionierender aus. Ohne AC-13 wären die ACs 2–6 und 10–12 alle mit einem Wächter grün, der
    nachweislich nichts bewirkt.

## Bekannte Grenzen

- **`PostToolUse` kann nicht blockieren.** Laut Hook-Vertrag hat das Werkzeug zu diesem
  Zeitpunkt bereits ausgeführt; eine Sperre (wie bei Scheibe 1) ist hier technisch nicht
  möglich. Der Wächter kann nur das Ergebnis **vor der Anzeige an Claude** verändern.
- **Ein falsch geformter Ersatzwert ist lautlos wirkungslos** (siehe Messung im Zuschnitt).
  Deshalb genügt es NICHT, in einem Test die Ausgabe des Wächters zu prüfen — ein Wächter, der
  einen String ausgibt, bestünde eine solche Prüfung und täte nichts. **AC-13 bewacht genau
  das.** Diese Zusicherung nennt bewusst den Mechanismus: sie bildet den gemessenen Vertrag der
  Plattform ab, ohne den jede Wirkungszusicherung unbeweisbar bliebe.
- **Kein `.env`-Cache**, wie bei Scheibe 1 — sonst greift der Wächter nach einer Rotation ins
  Leere.
- **Wirkt erst ab der nächsten Sitzung.** `.claude/settings.json` wird beim Sitzungsstart
  eingelesen; eine Änderung während der laufenden Sitzung wird erst beim nächsten Start
  wirksam.
- **`.claude/settings.json` ist orchestrator-geschützt.** Die Verdrahtung braucht eine
  ausdrücklich **getippte** Freigabe des Product Owners (`override`, TTL 1 Stunde) — sie kann
  nicht ohne PO-Eingriff erfolgen.
- **Ein Geheimnis als Schlüsselname auf der obersten Ebene erreicht Claude im Klartext**
  (F001, behoben-mit-Rest 2026-08-08). Schlüssel **unterhalb** der obersten Ebene werden
  maskiert. Auf der obersten Ebene von `tool_response` wird **bewusst nicht** umbenannt: Fehlt
  dort ein Originalschlüssel, verwirft die Plattform den **gesamten** Ersatz — dann bliebe auch
  jeder Wert unmaskiert. Die Wahl lautet also „laute Teillücke statt stiller Totalausfall".
  Der Wächter meldet diesen Fall auf stderr, mit **maskiertem** Schlüsselnamen.
  ⚠️ Sonderfall der Meldungsregel: Wenn der Schlüssel *selbst* das Geheimnis ist, wäre „nenne
  den Schlüsselnamen, nie den Wert" widersprüchlich — deshalb wird auch der Name maskiert
  dargestellt (`token_***GZ_…***_ende`).
- **Verschachtelungstiefe: nirgends mehr Rekursion, Obergrenze 9997** (F002/F003/F005, behoben
  2026-08-08). Traversierung **und** Tiefenkopie laufen iterativ über einen Stapel; die feste
  Grenze von 25 Ebenen samt ihrer stderr-Meldung ist ersatzlos gefallen, `copy.deepcopy` ist
  durch `_tiefe_kopie` ersetzt.
  **Warum das mehr war als eine Randnotiz:** Die frühere Formulierung an dieser Stelle
  („greift fail-open — Ergebnis unverändert, Exit 0, stumm") klang neutral, bedeutete aber
  wörtlich, dass der Geheimniswert **im Klartext sichtbar bleibt**. `copy.deepcopy` warf ab
  Tiefe 498 einen `RecursionError`, den der Notfall-Handler auffing — **bevor** irgendeine
  Ausgabe entstand. Von außen war das nicht von „geprüft, nichts gefunden" zu unterscheiden,
  während die Plattform das Ergebnis unverändert weiterreichte. Ein stiller Totalausfall ist
  der schwerste Fehler, den ein Wächter dieser Art haben kann.
  **Neue Grenze, gemessen** (2026-08-08, Python 3.12, `recursionlimit` 1000): `json.loads`
  **und** `json.dumps` schaffen Tiefe **9997**, ab 9998 werfen beide einen `RecursionError` —
  rund das Zwanzigfache der alten Schranke. Jenseits davon kann nichts mehr *unbemerkt*
  schiefgehen, und zwar aus drei Gründen: (1) Einlesen und Ausgeben haben **dieselbe** Grenze,
  (2) die Maskierung erhöht die Tiefe nicht — was durch `json.loads` kam, geht auch durch
  `json.dumps` — und (3) scheitert das Einlesen doch, **meldet** der Wächter das jetzt auf
  stderr, statt zu schweigen.
- **Fail-open heißt nicht mehr lautlos** (F005, 2026-08-08). Bricht die Prüfung mit einer
  Ausnahme ab, bleibt es bei Exit 0 und unverändertem Ergebnis — aber es entsteht eine
  stderr-Zeile, dass **nicht zu Ende geprüft** wurde. Präzisierung zu AC-1, kein Widerspruch:
  AC-1 regelt „geprüft, kein Fund", nicht „konnte nicht prüfen". Die Meldung nennt
  ausschließlich den Ausnahme-**Typ** (`type(e).__name__`), nie deren Text — eine
  Fehlermeldung kann Bruchstücke der Nutzlast tragen, und eine kaputte Nutzlast ist der
  wahrscheinlichste Ort dafür.
  **Ausgenommen bleibt der Fall „Plugin fehlt":** Das ist ein Dauerzustand, kein Zwischenfall —
  der Wächter weiß von Anfang an, dass er nicht arbeiten kann, und eine Zeile nach *jedem*
  Werkzeugaufruf wäre Lärm. Gemeldet wird, wer **unerwartet mitten in der Arbeit** scheitert.
- ⚠️ **Ein Geheimnis im WERKZEUGNAMEN erscheint im Klartext in den Meldungen des Wächters**
  (F008, Adversary-Runde 6, **bewusst nicht behoben**). Der Name aus `tool_name` wird
  ungeprüft in jede Meldung gedruckt — er kommt aus der Nutzlast, nicht aus dem Ergebnis, und
  läuft deshalb an der Maskierung vorbei. Trägt er einen Geheimniswert, steht dieser
  ausgeschrieben da, **direkt neben dem Satz „Wert bewusst nicht angezeigt"**. Reproduziert auf
  beiden Pfaden — Erfolgsfall und Notfall-Handler:
  `[secret_output_gate] Zugangsdaten im Ergebnis von mcp__dienst_<WERT> maskiert: … (Wert
  bewusst nicht angezeigt).` Das verletzt AC-9, die schärfste Zusicherung dieses Bauteils.
  **Warum trotzdem so ausgeliefert:** praktisch nicht auslösbar. `tool_name` ist bei den
  eingebauten Werkzeugen ein fester Plattform-String (`Bash`, `Read`, `Edit`, …) und bei
  MCP-Werkzeugen ein statischer Server-Bezeichner; keiner davon trägt jemals einen `.env`-Wert.
  **Die Behebung ist bekannt und scheitert nicht an der Technik**, sondern ist aus
  Aufwandsgründen vertagt: ein Modul-Feld `_PAARE` (`None` = Erkennung noch nicht geladen) plus
  eine Funktion `_werkzeug_sicher()`, die alle Druckstellen benutzen — sie maskiert den Namen,
  sobald die Erkennung geladen ist, und **hält ihn zurück**, solange sie es nicht ist. Letzteres
  ist nötig, weil auf dem Notfallpfad gerade das Laden der Erkennung die Fehlerquelle sein kann;
  ein Maskieren „einmal beim Setzen von `_WERKZEUG`" liefe dort ins Leere. Der Nutzen dieser
  Form: eine künftige fünfte Druckstelle kann die Maskierung nicht vergessen. Folge-Ticket:
  **#1617** (enthält Lösungsskizze, Reproduktion beider Pfade und den Grund, warum der
  naheliegende Ansatz nicht trägt).
- **Die Schlüssel-REIHENFOLGE ist ein erhaltener Nebeneffekt, keine belegte Anforderung**
  (F009). Gemessen (neun Läufe) ist ausschließlich die Schlüssel-**Menge**: fehlt dem Ersatz
  ein Schlüssel des Originals, verwirft die Plattform den gesamten Ersatz stillschweigend. Ob
  die Reihenfolge zählt, wurde **nie gemessen**. `_tiefe_kopie` erhält sie (sie kostet nichts
  und ist die naheliegendere Gestalt), und `test_replacement_keeps_the_original_key_order`
  bewacht sie — aber der Docstring der Funktion führt sie weiterhin als
  „Plattform-Anforderung", was so nicht belegt ist. Diese Zeile hier ist die maßgebliche
  Fassung; der Docstring konnte nicht nachgezogen werden (geschützte Datei, keine Freigabe).
- **Keine Sperre gegen Werte, die nicht über ein Claude-Code-Werkzeugergebnis laufen** (z.B.
  ein Prozess, der direkt in eine vom Nutzer geöffnete Datei schreibt, ohne dass ein
  `PostToolUse`-Hook dazwischen sitzt). Das ist außerhalb der Reichweite jedes Hooks dieser
  Art.

## Nicht in dieser Scheibe

- **Stufe A** (Werte, die zur Laufzeit von der `.env` in eine andere Datei wandern, ohne im
  Werkzeugaufruf selbst zu stehen) — eigener, nachfolgender Workflow.
- **Ein Melder für fehlgeschlagene Aufrufe** (`PostToolUseFailure`): Er könnte einen Fund
  **erkennen und melden** — ersetzen kann er nichts (siehe AC-3). Wert hätte das trotzdem: Man
  erführe, dass gerade ein Geheimnis ausgetreten ist, und könnte erneuern. Als eigene Scheibe
  dem PO vorzulegen, nicht hier mitzunehmen.
- **F008/F009** (Nebenbefunde an Scheibe 1: `cd`-Erkennung ignoriert Heredoc-Inhalte;
  Testlücke bei kaputten Anführungszeichen) — eigener Workflow.
- **Die Erneuerung der drei noch kompromittierten Zugangsdaten** (`GZ_SMTP_PASS`,
  `GZ_TEST_SMTP_PASS`, `GZ_TEST_IMAP_PASS`) — läuft außerhalb dieses Workflows (PO: Resend,
  `infra`: Stalwart-Postfach), ist kein Code.
- **Der eigentliche Fix zu #1535** (Test druckt Bot-Zugang bei Fehlschlag) bleibt im Test
  selbst — Zusicherung auf Schlüsselnamen statt Wert umstellen. Dieser Wächter ist das Netz,
  nicht der Ersatz dafür.
- **Eine Plugin-Änderung** an `secret_egress_guard.py` selbst — das Plugin ist auf allen sechs
  Claude-Instanzen dieses Servers aktiv; ein projektspezifischer Fix gehört nicht dorthin.

## Regel-Budget

Dieser Wächter schließt einen Weg, über den in #1535 nachweislich ein aktiver Zugang
ausgetreten ist (aktiv ausgenutzte Sicherheitslücke, analog Scheibe 1) — er schaltet sich
deshalb **nicht** automatisch nach einem Prüfdatum ab. Wirksamkeits-Prüfung
(Regel-Budget-Ledger): **2026-11-05**.

## Umfang

| Datei | Art | Zeilen (geschätzt) |
|---|---|---|
| `.claude/hooks/secret_output_gate.py` | ANLEGEN | ~150–200 |
| `tests/unit/test_secret_output_gate.py` | ANLEGEN | ~150 |
| `.claude/settings.json` | ÄNDERN | ~8 |

**`.claude/hooks/` und `.claude/settings.json` sind geschützt** — das Anlegen des Wächters und
die Verdrahtung brauchen die getippte PO-Freigabe (`override`, TTL 1 Stunde), gebunden an den
aktiven Workflow `fix-1537-s2-laufzeit-lecks`.

Risiko **HOCH** (Analyse A4): der Wächter läuft nach jedem Werkzeugaufruf in jeder Sitzung.
Ein Fehler verfälscht nicht ein Feature, sondern potenziell jedes Werkzeug-Ergebnis. AC-1
(stumm im Normalfall) und AC-8 (fail-open) sind deshalb nicht verhandelbar.

Vor der eigentlichen Umsetzung steht ein Wegwerf-Experiment (Marker-String statt echtem
Geheimnis, eigenes Scratchpad-Projekt), das klärt, ob `updatedToolOutput` in dieser
Claude-Code-Fassung überhaupt trägt — ohne diesen Nachweis wäre die Implementierung auf einer
Vermutung gebaut.

## Implementation Details

- **Erkennung wiederverwenden:** `collect_secrets`, `_is_secret_key`, `_is_secret_value` aus
  `core/hooks/secret_egress_guard.py` des Plugins `agent-os-openspec` per `importlib` laden —
  derselbe Ladeweg wie in `.claude/hooks/hook_utils.py` (dort für `hook_utils.py` des Plugins),
  nur mit anderem Zieldateipfad. Zwei getrennte `try`-Blöcke (Vorbild
  `secret_in_repo_gate.py:96-123`): fehlt das Modul komplett → fail-open mit Meldung; fehlt nur
  eine der privaten Funktionen (ältere Plugin-Fassung) → ebenfalls fail-open, nicht abstürzen.
- **Verdrahtung:** neue `PostToolUse`-Gruppe in `.claude/settings.json`, geschützte Form
  `if [ -f "${CLAUDE_PROJECT_DIR}/.claude/hooks/secret_output_gate.py" ]; then python3
  "${CLAUDE_PROJECT_DIR}/.claude/hooks/secret_output_gate.py"; fi` (Vorbild: jede bestehende
  Gruppe, kein `&&`/`|| exit 0`). Da Stufe B **alle** Werkzeuge treffen soll (Zuschnitt), ist
  in der Implementierung zu bestätigen, mit welcher `matcher`-Angabe eine `PostToolUse`-Gruppe
  tatsächlich jedes Werkzeug abdeckt (die einzige bestehende Gruppe im Projekt,
  `auto_restart_server.py`, ist bewusst auf `Bash` eingeschränkt und damit kein direktes
  Vorbild für „alle Werkzeuge"). **Geklärt 2026-08-07:** Laut Matcher-Tabelle treffen `"*"`,
  `""` und das Weglassen des Feldes gleichermaßen alle Werkzeuge. Gewählt wird `"matcher": "*"`
  — explizit, weil `test_issue_384_hook_fail_open.py:181` je Gruppe ausschließlich die Schlüssel
  `matcher` und `hooks` zulässt und eine ausgeschriebene Angabe im Bestand lesbarer ist.
- **Fehlgeschlagene Werkzeugaufrufe sind nicht erreichbar** (siehe AC-3). Eine Verdrahtung auf
  `PostToolUseFailure` würde den Wächter zwar aufrufen, könnte das Ergebnis aber nicht ersetzen.
- **Ausgabeform:** `{"hookSpecificOutput": {"hookEventName": "PostToolUse",
  "updatedToolOutput": <maskiertes Ergebnis>}}` — Struktur (String vs. Beibehaltung der
  ursprünglichen dict-Form) wird im Vorab-Experiment geklärt, bevor der Wächter final gebaut
  wird.
- **Zeitbudget klein** (Vorbild Plugin-Egress-Wächter: 5 s), damit kein Werkzeugaufruf spürbar
  gebremst wird.
- **Kein Werkzeugname-Filter** — Umsetzung des Zuschnitts „alle Werkzeuge, kein Ausschluss".

## Test Plan

Kern-Schicht, deterministisch, Vorbild `tests/unit/test_secret_in_repo_gate.py`: der Wächter
läuft als **echter Subprozess** mit stdin-JSON (`tool_name`, `tool_input`, `tool_response`),
gegen eine **synthetische** `.env` in `tmp_path` (nie die echte Projekt-`.env`) — kein Mock,
kein `patch()`. Prüflingspfad per `GZ_SECRET_GATE_PATH`-Umgebungsvariable austauschbar (analog
`GZ_SECRET_GATE_PATH` aus Scheibe 1), damit die spätere Mutations-Gegenprobe auf einer Kopie im
Scratchpad läuft und `.claude/**` unangetastet bleibt. Eine Plugin-Sonde am Modulkopf
überspringt die Suite sauber (`pytest.skip`), falls das Plugin nicht installiert ist, statt
strukturell rot zu werden.

Geplante Tests (mindestens einer je AC, mehrere ACs brauchen eine Gegenprobe):

1. `test_gate_silent_when_no_secret_found` (AC-1)
2. `test_gate_masks_secret_in_bash_success_stdout` (AC-2)
3. `test_gate_masks_secret_in_bash_failure_string_result` (AC-3)
4. `test_gate_masks_secret_in_read_nested_file_content` (AC-4)
5. `test_gate_masks_secret_in_write_content` (AC-5)
6. `test_gate_masks_secret_in_edit_old_string` (AC-6)
7. `test_gate_masks_secret_in_edit_new_string` (AC-6)
8. `test_gate_masks_secret_in_edit_original_file` (AC-6)
9. `test_gate_ignores_short_values` (AC-7)
10. `test_gate_ignores_known_placeholder_values` (AC-7)
11. `test_gate_fail_open_when_plugin_missing` (AC-8)
12. `test_gate_fail_open_on_malformed_stdin_json` (AC-8)
13. `test_gate_fail_open_on_unexpected_tool_response_type` (AC-8)
14. `test_masking_message_never_contains_the_secret_value` (AC-9)
15. `test_gate_masks_regardless_of_tool_name` (AC-10)
16. `test_gate_preserves_surrounding_text_and_other_fields` (AC-11)
17. `test_gate_masks_every_occurrence_and_multiple_secrets` (AC-12)
18. `test_replacement_keeps_every_original_key_and_is_not_a_string` (AC-13)

Geplant: **18 Verhaltenstests** in `tests/unit/test_secret_output_gate.py`.

**Pflicht-Mutationen für die Gegenprobe** (der Adversary muss belegen, dass jede davon
mindestens einen Test rot macht — bleibt eine grün, ist das ein Befund):

| Mutation | erwartet rot |
|---|---|
| Maskierung ganz entfernen (Ergebnis unverändert durchreichen) | 2–6, 10–12 |
| nur das erste Vorkommen ersetzen | 17 |
| gesamtes Ergebnis durch Platzhalter ersetzen statt nur den Wert | 16 |
| nur `stdout` betrachten (verschachtelte und String-Formen ignorieren) | 3, 4, 5, 6 |
| Schlüsselname durch den **Wert** in der Ersatzform tauschen | 14 |
| fail-open → fail-closed (Störung blockiert) | 11, 12, 13 |
| Ausgabe auch ohne Fund erzeugen | 1 |
| Ersatz als **String** statt als Objekt zurückgeben | 18 |
| beim Ersatz einen Originalschlüssel weglassen | 18 |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Wächter setzt eine bereits bestehende, im Plugin dokumentierte
  Geheimnis-Definition mechanisch auf einen bisher ungeschützten Weg (Werkzeug-Ausgaben) an —
  er trifft keine neue Architekturentscheidung und führt keinen neuen Geheimnis-Begriff ein
  (siehe „Zuschnitt").

## Changelog

- 2026-08-07: Initial spec created
- 2026-08-08: F003 behoben — Tiefengrenze (`_MAX_TIEFE = 25`) samt ihrer stderr-Meldung
  ersatzlos entfernt, Traversierung iterativ. AC-1 (stumm im Normalfall) gilt damit auch für
  tief verschachtelte harmlose Ergebnisse; der blinde Fleck aus F002 entfällt ganz.
- 2026-08-08: F005/F006/F007 behoben. `copy.deepcopy` durch die iterative `_tiefe_kopie`
  ersetzt (Obergrenze 497 → **9997**, Schlüsselreihenfolge erhalten); der Notfall-Handler
  meldet einen Abbruch jetzt auf stderr (nur Ausnahme-Typ), statt lautlos ein ungeprüftes
  Ergebnis durchzulassen; zwei Testlücken geschlossen (Geheimnis als reiner Listeneintrag,
  echter Auslöser für den äußeren Notfall-Pfad). 23 → 27 Tests.
- 2026-08-08: Adversary-Runde 6. **F008 bewusst nicht behoben** und als bekannte Grenze
  dokumentiert (Geheimnis im Werkzeugnamen erscheint im Klartext in den Meldungen; praktisch
  nicht auslösbar, Behebung bekannt und vertagt). **F009** geklärt: die Schlüsselreihenfolge
  ist ein erhaltener Nebeneffekt ohne belegte Plattform-Anforderung — gemessen ist nur die
  Schlüsselmenge; neuer Test `test_replacement_keeps_the_original_key_order` hält sie fest.
  28 → 29 Tests. Der Wächter selbst bleibt unverändert (`4fc65709…`).
