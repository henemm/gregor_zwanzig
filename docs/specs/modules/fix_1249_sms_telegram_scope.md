---
entity_id: fix_1249_sms_telegram_scope
type: module
created: 2026-07-13
updated: 2026-07-13
status: draft
version: "1.0"
tags: [official-alerts, sms, telegram, scope, design-fidelity]
---

# #1249 — SMS/Telegram amtliche Warnung: korrekter Ort je Warnung bei unterschiedlichem Umfang

## Approval

- [x] Approved (PO-go 2026-07-13)

## Purpose

Behebt, dass SMS und Telegram bei mehreren amtlichen Warnungen mit **unterschiedlichem** betroffenem Umfang (Orte/Streckenabschnitte) nur den Ort der führenden (schwersten) Warnung nennen, als gälte er für alle. Der Empfänger unterwegs — genau der Moment, in dem er die Mail nicht nachschlagen kann — liest z. B. „nur Toulon" und darunter Gefahren, von denen ein Teil Toulon gar nicht betrifft. Dieselbe Fehlerklasse wurde in der E-Mail bereits mit #1238/#1239 behoben; diese Spec zieht SMS und Telegram nach, ohne die dort gebauten Bausteine zu duplizieren.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` (MODIFY)
- **Identifier:** `render_official_alert_sms` (~:1383), `render_official_alert_telegram` (~:1320)

Schicht: **Python-Core / Domain-Backend** (`src/output/renderers/alert/`) — kein Frontend, kein Go.

## Estimated Scope

- **LoC:** ~80–150 (zwei Renderer-Funktionen erweitert, keine neue Datenstruktur, keine neuen Helfer — reine Wiederverwendung bestehender Bausteine + Anpassung ~5 Bestandstests + 1 neue Testdatei)
- **Files:** 1 Quell-Datei (MODIFY) + bis zu 5 Bestandstests (MODIFY, Non-Regression-Anpassung) + 1 neue Testdatei (CREATE, nach Verhalten benannt)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_uniform_scope(notices)` (official_alerts.py:951) | reuse | Identitätsbasierte Prüfung (über `scope_ids`, nicht Anzeige-Namen), ob ALLE Warnungen denselben betroffenen Umfang haben — bereits die geteilte Grundlage für Quelle-Box/Headline/Betreff in der Mail (#1238/#1239), wird hier zusätzlich von SMS und Telegram konsumiert |
| `_display_label(alert)` (official_alerts.py:462) | reuse | Reicher Quell-Label statt generischem Typ-Wort, entfernt doppelte numerische Stufe — speist bereits Betreff/Titel/embedded Block der Mail, wird hier zusätzlich von Telegram-Warnungszeilen konsumiert |
| `_hazard_display(alert)` (official_alerts.py:446) | reuse (unverändert) | Liefert `(Anzeige, SMS-Kürzel)` — das SMS-Kürzel (`[1]`) bleibt exakt wie bisher, Träger des Zeichenbudgets; nur die Telegram-Nutzung der Anzeige-Komponente (`[0]`) wird durch `_display_label` ersetzt |
| `_sms_truncate(head, tokens, limit, suffix)` (official_alerts.py:1363) | **Runde 3 überholt** — s. Changelog | Ursprünglich als „reuse (unverändert)" eingeplant; Adversary F004 (CRITICAL) fand, dass die Funktion kein Minimum garantierte (leere SMS bzw. Schnitt mitten im Ortsnamen möglich). Zu `_sms_pack`/`_sms_pack_with_fallback` erweitert (AC-4/AC-15/AC-16) — einziger Aufrufer bleibt `render_official_alert_sms` |
| `OfficialAlertNotice.scope_ids` / `.scope_label` / `.sms_scope` (official_alerts.py:110) | reuse (unverändert) | Pro-Notice-Umfang, bereits von beiden Buildern (`build_official_alert_notices` Trip, `build_compare_official_alert_notices` Compare) gesetzt |
| `notification_service.py` Trip-/Compare-Standalone (Zeilen ~517, ~548, ~652, ~672) | consume (unverändert) | Ruft `render_official_alert_sms`/`render_official_alert_telegram` mit derselben Notice-Liste auf, die auch die Mail speist — kein Aufrufer-Änderungsbedarf |

## Implementation Details

### S1 — SMS uniform-Zweig: Ortszusatz nur wenn er für alle gilt

Heute hängt der uniform-Zweig von `render_official_alert_sms` einen gemeinsamen `suffix = f", {leading.sms_scope}"` ans Ende — unabhängig davon, ob dieser Umfang für alle Warnungen gilt. Der bestehende `uniform`-Schalter in dieser Funktion prüft nur die **Eskalationsstufe** (`alert.level`), nicht den **Umfang** — beide Dimensionen sind unabhängig und müssen getrennt geprüft werden (per `_uniform_scope(notices)`). Nur wenn zusätzlich `_uniform_scope(notices)` wahr ist, bleibt der gemeinsame Ortszusatz am Ende unverändert (Format bit-identisch zum Ist-Stand). Ist der Umfang uneinheitlich, trägt jedes Token seinen eigenen Ort — nach demselben Muster, das der mixed-level-Zweig heute bereits für Tokens verwendet (`... {n.sms_scope}` pro Token).

### S2 — SMS-Zeichenbudget: schwächere Warnungen fallen als Ganzes weg

Ursprünglich als reine Nutzungsfrage der bestehenden `_sms_truncate` geplant (kein Umbau): Tokens werden vollständig (inkl. angehängtem Ort) oder gar nicht übernommen; passt nicht alles ins Limit, markiert `+N` die weggelassenen, schwächeren Warnungen. **Runde 3 (F004, s. Changelog):** die Annahme „die schwerste Warnung bleibt durch die bestehende Logik garantiert samt Ort erhalten" hielt im Ernstfall nicht — bei einem sehr langen Ortsnamen konnte `kept=[]` werden (leere SMS) oder der Ein-Warnung-Fall in einen Schnitt mitten im Ortsnamen fallen. `_sms_pack_with_fallback` ergänzt die abgestufte Rückfallebene aus AC-4/AC-15/AC-16 (Ort weglassen, dann nur Kürzel), bevor überhaupt in den Bereich von `body[:limit]` gelaufen wird.

### S3 — Telegram-Kopfzeile: Umfang nur nennen, wenn er für alle gilt

Heute nennt `head = f"{prefix} · {leading.scope_label} · ..."` den Umfang der führenden Warnung bedingungslos. Analog zur E-Mail-Einleitungszeile (#1238/#1239) gilt künftig: `_uniform_scope(notices)` entscheidet, ob der Umfang in der Kopfzeile erscheint. Bei einheitlichem Umfang bleibt die Kopfzeile unverändert (inkl. `scope_label`). Bei uneinheitlichem Umfang entfällt die Umfangsangabe aus der Kopfzeile ersatzlos (kein Platzhalter, kein „diverse Orte").

### S4 — Telegram-Warnungszeilen: eigener Umfang bei Uneinheitlichkeit

Die Warnungszeilen tragen heute gar keinen Umfang — der Empfänger kann eine Gefahr keinem Ort zuordnen, sobald mehrere Orte betroffen sind. Bei uneinheitlichem Umfang (`_uniform_scope(notices)` falsch) ergänzt jede Zeile ihren eigenen `scope_label`. Bei einheitlichem Umfang bleiben die Zeilen wie bisher schlank (der Umfang steht bereits einmalig in der Kopfzeile, S3) — Format in diesem Fall bit-identisch zum Ist-Stand.

### S5 — Telegram-Gefahrenbezeichnung: Gleichlauf mit der Mail

Die Warnungszeilen nutzen heute `_hazard_display(n.alert)[0]` (generisches Typ-Wort, z. B. „Zugang gesperrt"), während dieselbe Warnung in der Mail bereits `_display_label` zeigt („Zugang eingeschränkt — Monts Toulonnais", #1238). Telegram wechselt auf `_display_label(n.alert)`, damit beide Kanäle dieselbe Gefahrenbezeichnung zeigen. Das SMS-Kürzel (`_hazard_display(alert)[1]`) bleibt davon unberührt — es ist Träger des Zeichenbudgets, nicht des Anzeigetexts, und wird durch diese Spec nicht verändert.

## Expected Behavior

- **Input:** Dieselbe `list[OfficialAlertNotice]` (Trip- oder Compare-Standalone), die auch die Mail speist — inkl. `scope_ids`/`scope_label`/`sms_scope` je Notice.
- **Output:** SMS und Telegram nennen bei unterschiedlichem Umfang für jede genannte Warnung ihren eigenen Ort/Abschnitt statt eines einzigen, für alle geltenden Ortszusatzes; bei einheitlichem Umfang bleibt die Ausgabe unverändert. Telegram zeigt zusätzlich die reichere Gefahrenbezeichnung (Gleichlauf mit der Mail).
- **Side effects:** keine — reine Präsentationsänderung an bestehenden Renderern, kein neuer Versand-Trigger, keine geänderte Aufrufer-Signatur, kein State-Effekt.

## Betroffene Tests

Bestand (werden bei Bedarf an das neue Verhalten angepasst, nicht als Regression liegengelassen):
`tests/golden/test_sms_golden.py`, `tests/tdd/test_official_alert_template_render.py`, `tests/tdd/test_official_alert_subject_label_fidelity.py`, `tests/tdd/test_compare_official_alert.py`, `tests/tdd/test_issue_1088_official_alert_triggers.py`.

Neu (nach Verhalten benannt, NICHT nach Issue-Nummer — Gate `test_naming_gate.py`): z. B. `test_official_alert_channel_scope.py` (S1/S3/S4: Umfang je Warnung in SMS und Telegram bei uneinheitlichem Scope; S2: Zeichenbudget-Verhalten; S5: Telegram-Gefahrenbezeichnung).

## Acceptance Criteria

- **AC-1:** Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem Umfang (z. B. zwei verschiedene Orte) / When die SMS gerendert wird / Then nennt jede in der SMS enthaltene Warnung ihren eigenen Ort statt eines einzigen, gemeinsamen Ortszusatzes am Ende.
  - Test: Assert, dass in der gerenderten SMS-Zeichenkette pro enthaltener Warnung deren jeweiliger Ort erscheint, nicht nur der Ort der schwersten Warnung.

- **AC-2:** Given mehrere amtliche Warnungen, die alle denselben betroffenen Umfang haben / When die SMS gerendert wird / Then bleibt ihr Text bit-identisch zum Stand vor diesem Fix (gemeinsamer Ortszusatz am Ende).
  - Test: Non-Regression-Assert auf bestehenden Golden-Fällen aus `tests/golden/test_sms_golden.py` mit einheitlichem Umfang.

- **AC-3:** Given eine SMS mit mehreren Warnungen und je eigenem Ortszusatz / When die SMS gerendert wird / Then überschreitet sie das konfigurierte Zeichenlimit (Default 140, GSM-7/ASCII) niemals.
  - Test: Längen-Assert (`len(result) <= limit`) für ein Szenario mit mehreren langen Ortsnamen und unterschiedlichem Umfang.

- **AC-4** (präzisiert 2026-07-13 Runde 3, s. Changelog): Given mehr Warnungen mit unterschiedlichem Umfang, als vollständig samt Ort ins Zeichenlimit passen / When die SMS gerendert wird / Then fallen die schwächeren Warnungen als vollständige Einträge weg (mit „+N"-Hinweis), während die schwerste Warnung **in dieser Rückfallreihenfolge** erhalten bleibt: (1) Kürzel + Zeit + Ort, falls das ins Budget passt; (2) sonst Kürzel + Zeit, **ohne** Ort; (3) sonst nur das Gefahren-Kürzel. In **keinem** Fall wird die SMS inhaltsleer, und in keinem Fall wird mitten in einem Wort (Ortsname oder anderswo) abgeschnitten.
  - Test: Assert, dass bei einem Überlauf-Szenario der Text der schwersten Warnung (in der jeweils höchsten noch passenden Rückfallstufe) vollständig im Ergebnis steht und ein „+N"-Marker die Anzahl der weggelassenen Warnungen korrekt beziffert; kein abgeschnittenes Wort am Ende. Zusätzlich: ein Szenario mit einem einzelnen, das gesamte Zeichenlimit überschreitenden Ortsnamen ergibt weiterhin eine gültige, nicht-leere SMS mit Gefahr und Stufe (AC-15/AC-16).

- **AC-5:** Given amtliche Warnungen unterschiedlicher Gefahrentypen / When die SMS gerendert wird / Then bleiben die verwendeten Zwei-Buchstaben-Kürzel je Gefahrentyp identisch zum Stand vor diesem Fix.
  - Test: Non-Regression-Assert, dass die bekannten Kürzel (z. B. für Hitze, Gewitter, Zugangssperre, Waldbrand) unverändert im SMS-Text erscheinen.

- **AC-6:** Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem Umfang / When die Telegram-Kopfzeile gerendert wird / Then nennt die Kopfzeile keinen Umfang mehr, der fälschlich für alle Warnungen gälte.
  - Test: Assert, dass die gerenderte Telegram-Kopfzeile bei uneinheitlichem Umfang keinen einzelnen Ortsnamen mehr enthält, der nicht für alle folgenden Warnungszeilen zutrifft.

- **AC-7:** Given mehrere amtliche Warnungen, die alle denselben betroffenen Umfang haben / When die Telegram-Kopfzeile gerendert wird / Then bleibt sie bit-identisch zum Stand vor diesem Fix und nennt weiterhin den gemeinsamen Umfang.
  - Test: Non-Regression-Assert auf bestehenden Telegram-Fällen mit einheitlichem Umfang in `tests/tdd/test_official_alert_template_render.py`.

- **AC-8:** Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem Umfang / When die Telegram-Warnungszeilen gerendert werden / Then trägt jede Zeile den Umfang genau der Warnung, die sie beschreibt.
  - Test: Assert, dass jede gerenderte Warnungszeile ihren eigenen Ort/Abschnitt enthält und dieser sich zwischen den Zeilen unterscheidet, wenn die zugrunde liegenden Umfänge unterschiedlich sind.

- **AC-9** (präzisiert 2026-07-13, s. Changelog): Given mehrere amtliche Warnungen, die alle denselben betroffenen Umfang haben / When die Telegram-Warnungszeilen gerendert werden / Then bleibt ihre **Umfangs-Behandlung** bit-identisch zum Stand vor diesem Fix: keine Zeile trägt einen eigenen Umfangs-Zusatz, der Umfang steht einmalig in der Kopfzeile (AC-7). Die **Gefahren-Bezeichnung** ist von dieser Bit-Identität ausdrücklich ausgenommen — sie ändert sich durch AC-10 (S5) gewollt auch bei einheitlichem Umfang (z. B. „Hitze" → „Extreme Hitze").
  - Test: Assert bei einheitlichem Umfang, dass jede Zeile exakt `{Stufen-Emoji} {_display_label} · {Gültigkeit}` lautet (Trennzeichen „·“, s. AC-13/F002), also keinen zusätzlichen Ortstext trägt. Die Test-Fixture verwendet bewusst eine Gefahr mit reichem Quell-Label („Extreme Hitze"), damit AC-9 und AC-10 im selben Fall zugleich geprüft werden und der Test dem Konflikt nicht ausweicht.

- **AC-10:** Given eine amtliche Warnung mit einem reicheren Quell-Label (z. B. eine Zugangssperre mit Massiv-Namen) / When eine Telegram-Warnungszeile gerendert wird / Then zeigt sie dieselbe Gefahrenbezeichnung wie die entsprechende E-Mail-Warnung, statt eines generischen Typ-Worts.
  - Test: Assert, dass der Text der Telegram-Zeile mit dem `_display_label`-Ergebnis derselben Warnung übereinstimmt, nicht mit dem `_hazard_display`-Anzeigewort.

- **AC-11:** Given eine Trip-Standalone-Alarmmeldung mit unterschiedlichem betroffenem Umfang über mehrere Streckenabschnitte UND eine Ortsvergleich-Standalone-Alarmmeldung mit unterschiedlichem betroffenem Umfang über mehrere verglichene Orte / When SMS und Telegram für beide Fälle gerendert werden / Then zeigen beide Pfade korrekt den jeweils eigenen Umfang je Warnung (Segmente im Trip-Fall, Orte im Compare-Fall), da beide Pfade denselben Renderer nutzen.
  - Test: Assert für Trip- und Compare-Notice-Listen getrennt, dass beide denselben korrigierten Renderer-Pfad durchlaufen und in beiden Fällen kein „falscher Ort für alle"-Text mehr auftritt (z. B. in `tests/tdd/test_compare_official_alert.py` und `tests/tdd/test_issue_1088_official_alert_triggers.py`).

- **AC-12** (Runde 2, F001, ergänzt 2026-07-13 — s. Changelog): Given eine amtliche Warnung ohne bekannten Gültigkeitszeitraum / When eine Telegram-Warnungszeile gerendert wird / Then entfällt die Zeitangabe (samt Trennzeichen) ersatzlos, statt „unbekannt" zu zeigen — dieselbe PO-Beanstandung aus #1238, hier für Telegram nachgezogen (Gleichlauf mit der Mail, #1238 AC-7).
  - Test: Assert, dass die Zeile einer Warnung ohne `valid_from`/`valid_to` kein „unbekannt" enthält; Non-Regression, dass eine Warnung mit bekannter Zeit sie unverändert zeigt.

- **AC-13** (Runde 2, F002, ergänzt 2026-07-13 — s. Changelog): Given eine amtliche Warnung mit einem reichen Quell-Label, das selbst einen Gedankenstrich trägt, UND bekannter Gültigkeit / When eine Telegram-Warnungszeile gerendert wird / Then trennt die Zeile Label und Zeitangabe mit einem Zeichen, das nicht mit dem Gedankenstrich im Label kollidiert (Trennzeichen „·", konsistent mit dem Umfangs-Trenner aus S4).
  - Test: Assert, dass die gerenderte Zeile höchstens den einen Gedankenstrich enthält, der bereits im Label selbst steht.

- **AC-14** (Runde 2, F003, ergänzt 2026-07-13 — s. Changelog): Given eine amtliche Warnung ohne bekannten Gültigkeitszeitraum / When die SMS gerendert wird / Then enthält das zugehörige Token kein Zeit-Platzhalterzeichen („?") mehr, sondern lässt die Zeitangabe ersatzlos weg.
  - Test: Assert, dass die gerenderte SMS kein „?" enthält; Non-Regression, dass Warnungen mit bekannter Zeit ihre Zeitangabe unverändert zeigen.

- **AC-15** (Runde 3, F004 CRITICAL, ergänzt 2026-07-13 — s. Changelog): Given eine amtliche Warnung, deren (nutzereingegebener, im Modell nicht längenbegrenzter) Ortsname so lang ist, dass Kopf + Kürzel + Zeit + Ort das Zeichenlimit sprengt / When die SMS gerendert wird / Then bleibt sie **nicht leer** und enthält weiterhin mindestens Gefahren-Kürzel und Zeitangabe der schwersten Warnung (Ort entfällt in diesem Fall) — statt einer inhaltsleeren SMS wie „GZ AMT:  +1".
  - Test: Assert am gerenderten SMS-Output über den echten Compare-Builder mit einem überlangen Ortsnamen, dass das Ergebnis nicht leer ist, das Limit hält, Gefahr und Zeit enthält und kein Fragment des zu langen Ortsnamens trägt. Non-Regression: normale Ortsnamen (kein Overflow) bleiben unverändert.

- **AC-16** (Runde 3, F004 CRITICAL, Extremfall, ergänzt 2026-07-13 — s. Changelog): Given ein einziger Ortsname, der länger ist als das **gesamte** Zeichenlimit / When die SMS gerendert wird / Then bleibt sie gültig (nicht leer, hält das Limit, kein Wort-Fragment) und nennt weiterhin Gefahr und Stufe.
  - Test: Assert am gerenderten SMS-Output mit einem 250 Zeichen langen Ortsnamen (bei Limit 140), dass das Ergebnis gültig bleibt und kein Fragment des Ortsnamens enthält.

## Known Limitations

- **Bündelung nicht Teil dieser Spec:** Die Bündelung gleichartiger Warnungen nach Gefahren-Typ + Stufe (`_bundle_by_hazard_level`, #1239 E7) findet bereits vor der Übergabe an diese Renderer statt (in den Buildern) und wird hier nicht verändert.
- **ASCII-Konvertierung bleibt vor der Kürzung:** Die bestehende Reihenfolge in `render_official_alert_sms` (erst `_ascii()`, dann `_sms_pack`/`_sms_pack_with_fallback`, Runde 3 Umbenennung von `_sms_truncate`) bleibt unverändert — sie stellt sicher, dass die Längen-Buchhaltung mit der finalen Zeichenkette übereinstimmt.
- **Einzelfall trivial uniform:** Enthält eine Nachricht nur eine einzige Warnung, ist `_uniform_scope` trivial wahr — Verhalten entspricht dann automatisch dem heutigen Stand.
- **Rückfallebene nur für die schwerste Warnung (Runde 3):** Fällt das Budget knapp aus, greift die Rückfallebene (Ort weglassen, dann nur Kürzel) ausschließlich für die schwerste Warnung. Schwächere Warnungen folgen weiterhin der bestehenden Logik aus AC-4 (ganze Tokens fallen weg, „+N"-Marker) — sie bekommen keine eigene abgestufte Rückfallebene, weil sie ohnehin als Ganzes wegfallen dürfen, wenn kein Platz bleibt.
- **Letztes Sicherheitsnetz nur bei unrealistischem `sms_prefix`:** Die Wortgrenzen-Kürzung (`_word_boundary_truncate`) greift nur, wenn selbst Kopf + blankes Gefahren-Kürzel das Limit sprengt — in der Praxis nur bei einem absurd langen, nutzerdefinierten `sms_prefix` (Trip-/Vergleichsname) denkbar, nicht bei realistischen Ortsnamen.

## Ersetzt/Überschreibt

Diese Spec löst die in `docs/specs/modules/fix_1237_1238_1239_mail_darstellung.md` (Abschnitt „Known Limitations") dokumentierte Einschränkung „Telegram/SMS nicht Teil dieser Spec" ein: die dort für die E-Mail gebauten Bausteine `_uniform_scope`/`_display_label` werden hier für die verbleibenden zwei Kanäle wiederverwendet, nicht neu gebaut. Die alte Spec-Datei wird nicht editiert (Transparenz-Prinzip); dieser Abschnitt dokumentiert die Nachlieferung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0011, bestehend — gemeinsamer kontext-agnostischer Renderer für amtliche Warnungen, bleibt gültig)
- **Rationale:** Reine Präsentations-/Korrektheits-Fixes an zwei bereits mit ADR-0011 etablierten Renderern. Keine neue Architektur, kein neuer Konsument, keine neue Datenstruktur — vollständige Wiederverwendung der in #1238/#1239 geschaffenen Bausteine.

## Changelog

- 2026-07-13: Initial spec created (Issue #1249, Kontext `docs/context/fix-1249-sms-telegram-scope.md`, PO-Entscheidung zum SMS-Zeichenbudget wörtlich übernommen).
- 2026-07-13: **AC-9 präzisiert** (im TDD-RED aufgefallen, nicht stillschweigend geändert). Die ursprüngliche Formulierung „bleiben sie schlank … und bit-identisch zum Stand vor diesem Fix" widersprach AC-10/S5: der Wechsel der Telegram-Zeilen auf `_display_label` ändert die Gefahren-Bezeichnung (z. B. „Hitze" → „Extreme Hitze") **auch dann, wenn der Umfang einheitlich ist** — beide ACs konnten nur gleichzeitig erfüllt werden, indem die Test-Fixture Gefahren wählt, deren Quell-Label zufällig dem Typ-Wort entspricht (Gewitter/Sturm). Damit hätte der Test nicht mehr geprüft, was er verspricht. AC-9 sagt jetzt genau das aus, was AC-9 schützen soll: die **Umfangs-Behandlung** (kein wiederholter Umfang je Zeile bei einheitlichem Umfang) ist bit-identisch; die Gefahren-Bezeichnung ist ausgenommen und liegt allein bei AC-10. Die Test-Fixture wurde entsprechend auf eine Gefahr mit reichem Label („Extreme Hitze") umgestellt, damit der echte Konfliktfall geprüft wird. Sachlicher Umfang des Fixes unverändert; keine neue Verhaltenszusage.
- 2026-07-13 (Runde 2): **AC-12/AC-13/AC-14 ergänzt** (F001/F002/F003), nach Review der Runde-1-Beispielausgaben. Dieselbe PO-Beanstandung aus #1238 („Warum ‚Gültig: unbekannt‘?") lebte in Telegram fort (`_format_validity` liefert dort weiterhin „unbekannt", `_tag_time` in der SMS weiterhin „?"), obwohl die Mail sie mit #1238 AC-7 bereits ersatzlos entfernt. Zusätzlich kollidierte ein neu eingeführter Zeilen-Trenner „—" zwischen Label und Zeitangabe mit dem Gedankenstrich, den ein reiches `_display_label` selbst tragen kann („Zugang eingeschränkt — Monts Toulonnais — Sa 11.07. …"). Fix: (a) Telegram-Zeile lässt die Zeitangabe samt Trennzeichen ganz weg, wenn `valid_from`/`valid_to` fehlen (F001, Gleichlauf mit der Mail); (b) Trennzeichen zwischen Label und Zeitangabe ist „·" statt „—", konsistent mit dem bereits genutzten Umfangs-Trenner (F002); (c) `_tag_time` liefert „" statt „?" bei fehlender Zeit, das SMS-Zeit-Token entfällt dann ganz (F003). AC-2 (mixed-level, SMS) und AC-9 (Telegram-Zeilen, uniform scope) mussten dadurch inhaltlich angepasst werden: die betroffenen literalen Erwartungs-Strings verlieren das „?" bzw. wechseln „—" zu „·" — die jeweils geprüfte Kern-Zusage (Umfangs-Bit-Identität) bleibt unverändert, nur der orthogonale Zeit-/Trennzeichen-Fehler ist behoben. Kein Scope-Creep über #1249 hinaus — beide Fehlerklassen entstammen der ursprünglichen #1216-Implementierung und werden hier im Zuge der ohnehin geänderten Zeilen mitbehoben.
- 2026-07-13 (Runde 3): **AC-4 präzisiert, AC-15/AC-16 ergänzt** (F004, CRITICAL — Adversary-Verdict BROKEN). `_sms_truncate` (Vorgänger von `_sms_pack`) garantierte entgegen dem Wortlaut von AC-4 und der PO-Entscheidung („muss immer mindestens die schwerste Warnung samt Ort enthalten") **kein Minimum**: Ortsnamen sind nutzereingegeben und im Modell nicht längenbegrenzt. Sprengte Kopf + erstes Token + Ort das Limit, wurden **alle** Tokens verworfen (`kept=[]`, SMS wie „GZ AMT:  +2" — ohne jeden Inhalt), und im Ein-Warnung-Fall griff `body[:limit]` — ein Schnitt mitten im Ortsnamen, obwohl „nie mitten im Token" eine dokumentierte Invariante der Funktion war. Der Defekt bestand bereits auf `origin/main` (nicht durch #1249 eingebaut), wird aber hier behoben: eine im Ernstfall nicht haltende Zusage ist schlimmer als keine, und eine leere Unwetterwarnung ist der schlechteste denkbare Ausgang. Fix: `_sms_pack_with_fallback` (neu) probiert für die schwerste Warnung drei Stufen durch — (1) Kürzel+Zeit+Ort wie bisher, (2) Kürzel+Zeit ohne Ort, (3) nur das Kürzel — und garantiert mit `_word_boundary_truncate` als letztem Sicherheitsnetz, dass NIE ein leeres Ergebnis und NIE ein Schnitt mitten im Wort entsteht. `_sms_truncate` wurde zu `_sms_pack` (liefert zusätzlich die Anzahl behaltener Tokens, damit der Aufrufer einen Fehlschlag der ersten Stufe erkennen kann) umbenannt; einziger Aufrufer bleibt `render_official_alert_sms`, kein anderer Kanal betroffen. AC-4 wurde um die Rückfallreihenfolge präzisiert (war zuvor ohne Einschränkung formuliert, hätte im Grenzfall also weiterhin etwas versprochen, das nicht hielt); AC-15/AC-16 sichern den Normalfall-Overflow bzw. den Extremfall (Ortsname länger als das gesamte Limit) explizit ab. Bestehende Non-Regression-Tests (AC-2, AC-4, `tests/golden/test_sms_golden.py`) bleiben unverändert grün, da die Rückfallebene nur greift, wenn Stufe 1 tatsächlich nicht passt.
