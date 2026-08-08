---
entity_id: feat_1558_frontend_browser_gate
type: module
created: 2026-08-07
updated: 2026-08-07
status: draft
version: "1.0"
tags: [gate, frontend, staging, browser]
---

# Spec: Frontend-Änderungen erzwingen einen echten Browserlauf

- **Issue:** #1558 (Scheibe 1)
- **Workflow:** `feat-1558-frontend-browser-gate`
- **Kontext & Messungen:** `docs/context/feat-1558-frontend-browser-gate.md`
- **Status:** Entwurf — wartet auf PO-Freigabe der Acceptance Criteria

## Approval

- [x] Approved — PO-Freigabe („go") 2026-08-08, ACs unverändert wie oben

## Zweck in einem Satz

Berührt der auszuliefernde Änderungssatz das Frontend, lädt das Gate die Kernseiten selbst in
einem echten Browser und verweigert das Staging-Verdict, wenn dabei Konsolenfehler auftreten
oder der Lauf nicht zustande kommt.

## Warum

Bei #1552 war die Seite *Trip anlegen* auf Staging vollständig unbedienbar — eine Endlosschleife
im `$effect`, ausgelöst beim bloßen Laden. Der Stand dabei: 5837 grüne Tests, Adversary VERIFIED
mit 11 Mutationen, alle CI-Checks grün. Alles grün, Seite tot.

Kein Testsatz konnte das fangen: Die Frontend-Tests prüfen Quelltext statt Verhalten (kein jsdom),
und serverseitiges Rendern führt `$effect` nie aus. Eine Reaktivitäts-Endlosschleife ist für beide
Schichten strukturell unsichtbar — keine Lücke im Testsatz, sondern in der Test-*Art*. Gefunden
wurde es nur, weil die Staging-Prüfung damals ausdrücklich über den echten Klickpfad beauftragt
war: eine Einzelentscheidung, kein Mechanismus.

## Die tragende Entwurfsentscheidung: das Gate führt aus, es liest nicht

Ein Gate, das einen abgelegten Nachweis nur **liest**, prüft hier nichts — Nachweis-Erzeuger und
Gate-Aufrufer sind dieselbe Instanz. Der Beleg läuft im Betrieb:
`pre_issue_close_design_gate.py:64–72` globt `design-diff-*.json` und akzeptiert jede Datei mit
`passed: true`, ohne zu prüfen, ob die referenzierten Bilder existieren. Drei Zeilen JSON von Hand
bestehen dieses Gate. Ebenso prüft `write_verdict()` die Findings-Datei heute nur auf
JSON-Validität (`staging_gate.py:278–282`), nie darauf, ob die genannten `evidence`-Pfade existieren.

Deshalb: **Die Prüf-Logik läuft im Gate-Code, nicht im Agenten-Code.** Der Browserlauf passiert im
selben Aufruf, der das Verdict schreibt. Damit entfällt auch das Anti-Stale-Problem — es gibt
keinen zwischengelagerten Nachweis, der veralten könnte.

**Der Preis, ausdrücklich:** Staging-Erreichbarkeit wird Voraussetzung für jeden Frontend-Deploy.
Der Aufrufer entscheidet weiterhin, *ob* er `--write-verdict` startet; das ist unvermeidbar. Aber
wenn er es startet, kann er das Ergebnis nicht mehr durch Behauptung erkaufen.

## Zuschnitt

**Auslöser:** `scope in ("frontend-only", "full-stack")` — der Wert, den `write_verdict()` bei
`staging_gate.py:296` **bereits berechnet hat**. Das Gate zieht ausdrücklich **keinen eigenen
git-Diff**. Begründung: das Telegram-Vorbild diffft fest `HEAD~1..HEAD` (`staging_gate.py:237`)
und übersieht dadurch alles, was weiter zurückliegt als der letzte Commit. Ohne zweite Diff-Logik
kann dieser Fehler strukturell nicht entstehen.

**Einbauort:** in `write_verdict()` **nach** der Scope-Berechnung (Z. 296) — nicht bei Z. 275, wo
das Telegram-Gate sitzt und `scope` noch nicht existiert.

**Geprüfte Kernseiten** (fester Satz, nicht aus dem Diff abgeleitet):
`/` · `/trips` · `/trips/new` · `/compare` · `/compare/new` · `/locations`

Eine Zuordnung „geänderte Komponente → betroffene Route" wäre bei 235 `lib`-Komponenten gegen
27 Routen ohne Dependency-Graph eine Rate-Funktion mit hoher Fehlerquote — genau die Fehlerklasse,
gegen die das Gate antritt. `design_fidelity_diff.py:21–70` löst dasselbe Problem bereits mit einer
festen Karte.

**Bewusst nicht in dieser Scheibe:**
- Trip-Detailseite `/trips/[id]` — braucht einen garantiert vorhandenen Trip auf Staging; die
  Abhängigkeit von fremden Daten macht das Gate flatterig. Nachziehen, sobald ein fest geseedeter
  Test-Trip dort verlässlich existiert.
- Klickpfade. Geprüft wird **Laden**, nicht Bedienen. Genau das hätte #1552 gefangen.
- Der CI-Playwright-Smoke (eigenes Folge-Issue): braucht Build, Preview-Server und Chromium im
  Runner sowie einen eigenen Login-Mechanismus — kein Copy-Paste aus dieser Scheibe.

## Wiederverwendung statt Neubau

| Baustein | Herkunft |
|---|---|
| Credentials beider Ebenen laden | `design_fidelity_diff.py:145–164` (`load_validator_env()`), erweitert um die Staging-Quelle (s.u.) |
| „Sind wir wirklich angemeldet auf der Zielseite?" | `design_fidelity_diff.py:167–194` (`unauthenticated_reason()`) — prüft Redirect auf `/login` **und** sichtbares Passwortfeld |
| Modul-Import ohne Package | `staging_gate.py:45–53` (`importlib.util.spec_from_file_location`) |
| Struktur des Gate-Moduls | `e2e_telegram_live.py` |

## Schnittstelle — in der RED-Phase festgelegt

Drei Festlegungen entstanden beim Testschreiben, weil die ACs sonst nur mit Mock-Theater
prüfbar gewesen wären. Die Implementierung muss ihnen folgen:

| Festlegung | Warum |
|---|---|
| `staging_gate.FRONTEND_GATE_PATH` als **Modul-Attribut** (nicht inline im Funktionsrumpf wie beim Telegram-Vorbild, `staging_gate.py:224`) | Nur so kann AC-8a auf eine **echt kaputte Datei** zeigen und einen realen Importfehler auslösen. Inline ginge es nur mit einem gemockten Importfehler — verbotenes Mock-Theater. |
| `check_pages()` als eigene Ebene neben `gate()` | `gate()` prüft „Zugangsdaten fehlen" und blockiert; `check_pages()` lädt nur und sammelt Konsolenfehler. Ohne die Trennung bräche AC-2 schon vor dem Laden ab und wäre ohne Staging nicht prüfbar. |
| `gate()` bewertet **ausschließlich das übergebene `env`-Mapping** und lädt keine Zugangsdaten nach | `os.environ.setdefault` in `load_validator_env()` würde die Testbedingung „Zugangsdaten fehlen" wieder aufheben. Das Nachladen gehört in `_frontend_browser_gate()`. |

Feldname im Attestations-Payload für AC-7: **`frontend_pages_checked`**.

## Zugangsdaten: DREI Quellen, nicht zwei (Nachtrag 2026-08-08)

Die erste Fassung nahm die Anwendungs-Anmeldedaten aus der `.env` des
Arbeitsordners. Damit blockierte das ausgelieferte Gate **jede**
Frontend-Auslieferung: alle sechs Kernseiten meldeten „zurückgeleitet auf die
Anmeldemaske". **Die Staging-Instanz hat eigene Anmeldedaten** — gleicher
Benutzername, anderes Passwort. Gemessen gegen `POST /api/auth/login`:

| Quelle | Antwort |
|---|---|
| `.env` im Arbeitsordner | **401** `invalid credentials` |
| `/home/hem/gregor_zwanzig_staging/.env` | **200**, `gz_session`-Cookie |

| Ebene | Variablen | Quelle |
|---|---|---|
| vorgeschaltete nginx-Schranke | `GZ_VALIDATOR_*` | `.claude/validator.env` |
| Anmeldung der Anwendung, Ziel Staging | `GZ_AUTH_*` | `STAGING_ENV_PATH`, Vorgabe `/home/hem/gregor_zwanzig_staging/.env`, überschreibbar per `GZ_STAGING_ENV_PATH` |
| Anmeldung der Anwendung, sonst | `GZ_AUTH_*` | lokale `.env` |

**Rangfolge:** bereits gesetzte Umgebungsvariable > Staging-`.env` (nur bei
Staging-Ziel) > `.claude/validator.env`/lokale `.env`. Umgesetzt über die
Reihenfolge — `os.environ.setdefault` macht den ersten Schreiber maßgeblich.
Dieselbe Quelle nennen die bestehenden Playwright-Staging-Specs
(`frontend/e2e/issue-1093-compare-layout-crash.spec.ts:21-22`).

## Vier unterscheidbare Anmelde-Ausgänge (Nachtrag 2026-08-08)

Der erste Staging-Nachweis für „falsches Passwort wird erkannt" war grün **aus
dem falschen Grund**: Er meldete Fehlschlag, weil die Anmeldung *generell*
kaputt war, nicht wegen des falschen Passworts. Damit sich dieser Fehlschluss
nicht wiederholt, sind die Ausgänge benannt und unterscheidbar:

| Meldung | Bedeutung | Ort |
|---|---|---|
| „Zugangsdaten fehlen" | Variablen nicht gesetzt | `gate()` |
| „Anmeldung nicht durchführbar" | technisch (Zeitüberschreitung, Feld weg) | `_login()` |
| „Anmeldung abgelehnt" | die Anwendung weist die Daten zurück, mit HTTP-Status und Route | `_login()` |
| „keine angemeldete Kernseite" | Zielseite steht auf `/login` bzw. zeigt ein Passwortfeld | `_visit()` |

**Gemessen, nicht angenommen:** Die Ablehnung kommt im Browser als `POST 401`
auf die Route **`/login`** (SvelteKit-Form-Action) — *nicht* auf
`/api/auth/login`. Ein auf diesen Endpunkt fest verdrahteter Wächter blieb im
Versuch still. Erkannt wird deshalb allgemein: während der Anmeldung ist jede
fehlgeschlagene POST-Antwort die abgelehnte Anmeldung.

## Acceptance Criteria

**AC-1: Frontend-Änderung ohne bestandenen Browserlauf bekommt kein Verdict**
Given der auszuliefernde Änderungssatz hat den Scope `frontend-only`
When `staging_gate.py --write-verdict "VERIFIED: …"` aufgerufen wird und der Browserlauf nicht
bestanden wird
Then wird **keine** Attestations-Datei geschrieben und der Aufruf endet mit Exit-Code 1.
- Test: `write_verdict()` mit Scope `frontend-only` und einem Browser-Gate, das Nicht-Bestehen
  meldet; danach gemessen, dass `.claude/e2e_verified/<sha>.json` **nicht** existiert.

**AC-2: Ein Konsolenfehler beim Laden verweigert das Verdict**
Given eine der geprüften Kernseiten wirft beim Laden einen JavaScript-Fehler oder eine
Konsolenmeldung der Stufe `error`
When der Browserlauf des Gates diese Seite lädt
Then meldet das Gate Nicht-Bestehen, die Meldung nennt Seite und Fehlertext, und es entsteht
kein Verdict.
- Test: Seite mit provoziertem `pageerror` gegen eine lokal ausgelieferte Testseite; gemessen,
  dass das Gate Exit ≠ 0 liefert und der Fehlertext in der Meldung steht.

**AC-3: Backend- und Doku-Änderungen bleiben unberührt**
Given der Änderungssatz hat den Scope `backend` oder `docs-only`
When `--write-verdict` aufgerufen wird
Then startet **kein** Browserlauf, und das Verdict wird geschrieben wie bisher.
- Test: `write_verdict()` mit beiden Scopes läuft in einer Umgebung, in der ein Browserlauf
  **zwangsläufig scheitern würde** (Zugangsdaten entfernt); gemessen, dass die Attestation
  trotzdem entsteht. Damit ist belegt, dass kein Browserlauf stattfand — ohne einen Aufruf-Zähler
  zu befragen, der nur eine Implementierungs-Annahme bewacht.

**AC-4: `full-stack` zählt wie `frontend-only`**
Given der Änderungssatz berührt Frontend **und** Backend, Scope ist also `full-stack`
When `--write-verdict` aufgerufen wird
Then greift das Gate genauso wie bei `frontend-only`.
- Test: derselbe Aufbau wie AC-1, nur mit Scope `full-stack`; gemessen, dass kein Verdict entsteht.

**AC-5: Eine Frontend-Änderung mehrere Commits zurück wird trotzdem erkannt**
Given seit dem letzten Gate-Lauf liegen mehrere Commits vor, die Frontend-Änderung liegt zwei
Commits zurück, und der jüngste Commit ändert nur Dokumentation
When `--write-verdict` aufgerufen wird
Then greift das Gate trotzdem, weil es den bereits ermittelten Scope verwendet statt eines
eigenen `HEAD~1`-Vergleichs.
- Test: Wegwerf-Repo mit dieser Commit-Folge; gemessen, dass das Gate anspringt. **Dieser Test
  ist der Wächter gegen den Erbfehler des Telegram-Vorbilds** — ohne ihn wäre die Zusicherung
  „kein zweiter Diff" nur eine Behauptung.

**AC-6: Nicht angemeldet erreichte Seite gilt als Nicht-Bestehen**
Given die Anmeldung an der Staging-Anwendung schlägt fehl, sodass die Kernseiten auf die
Anmeldemaske zurückleiten
When der Browserlauf läuft
Then meldet das Gate Nicht-Bestehen — eine fehlerfreie Anmeldemaske gilt **nicht** als bestandene
Kernseite.
- Test: Lauf mit ungültigem Anwendungs-Passwort; gemessen, dass Exit ≠ 0 und die Meldung den
  Anmeldegrund nennt. Deckt die Falle aus #1307 ab, bei der ein Gate mit einem Foto der
  Anmeldemaske bestand.

**AC-7: Sauberer Frontend-Änderungssatz läuft durch und hinterlässt eine Spur**
Given alle Kernseiten laden ohne Konsolenfehler
When `--write-verdict "VERIFIED: …"` aufgerufen wird
Then wird die Attestation geschrieben und enthält, welche Seiten geprüft wurden.
- Test: Lauf gegen Staging; gemessen, dass die Attestation entsteht und die geprüften Seiten
  benennt.

**AC-8: Fehlendes Nachweismittel blockiert, ein defektes Gate lässt durch**
Given das Gate-Modul selbst lässt sich nicht laden (Import-/Syntaxfehler)
When `--write-verdict` bei Frontend-Scope aufgerufen wird
Then läuft der Aufruf mit einer Warnung durch — ein kaputtes Gate darf nie die Ursache sein, dass
niemand mehr ausliefern kann.
Und Given Playwright fehlt, Staging ist nicht erreichbar oder die Zugangsdaten fehlen
Then blockiert das Gate. Das ist „Nachweis nicht erbringbar", nicht „Gate kaputt" — als
Freifahrtschein wäre es genau das Sicherheits-Theater, das dieses Ticket abschafft.
- Test: beide Fälle getrennt; gemessen, dass der erste Exit 0 mit Warnung liefert und der zweite
  Exit ≠ 0 ohne Attestation.

## Festlegungen zu den offenen Punkten

| Frage | Festlegung | Begründung |
|---|---|---|
| Warnungen auch? | Nein — nur Stufe `error` und `pageerror` | Warnungen aus Drittbibliotheken würden das Gate in Rauschen ersticken. #1552 war ein `error`. |
| Auch bei `AMBIGUOUS`? | Ja | Ein AMBIGUOUS-Verdict wird abgelegt und kann später als Vorgänger dienen; die Lücke wäre sonst trivial zu nutzen. |
| Trip-Detailseite? | Nicht in dieser Scheibe | Braucht garantiert vorhandene Fremddaten auf Staging. |

## Estimated Scope

- **LoC:** ~190–220 (Limit 250)
- **Files:** 4 — 2 neu, 2 geändert
- **Effort:** medium

| Datei | Typ |
|---|---|
| `.claude/hooks/e2e_frontend_browser_gate.py` | CREATE |
| `.claude/hooks/staging_gate.py` | MODIFY |
| `tests/tdd/test_frontend_browser_gate.py` | CREATE |
| `tests/tdd/test_staging_gate_verdict_merge.py` | MODIFY (Seam neutralisieren, analog Z. 70–73) |

## Risiken

- **Der Eingriff sitzt im gemeinsamen Auslieferungspfad**, den jede Sitzung durchläuft. Greift die
  Scope-Prüfung falsch, blockiert das auch Backend-Deploys — AC-3 bewacht genau das.
- **Staging wird zum Nadelöhr** für Frontend-Deploys. Bewusst in Kauf genommen; ein Notausgang für
  echte Ausfälle existiert bereits (`GZ_SKIP_E2E_GATE=1`, `staging_gate.py:383–385`) — laut und
  geloggt. Ein zweiter, stiller wird nicht gebaut.
- **Laufzeit:** gemessen 1,0 s je Seitenaufruf inkl. Browser-Start und Basic-Auth. Sechs Seiten
  plus einmal Anmelden bleiben im Sekundenbereich, in einem Schritt, der einmal je Auslieferung läuft.
- **Nicht geprüft:** ob der Hook-Kontext dieselben Netzwerkrechte hat wie eine interaktive Sitzung.
  Fällt das durch, greift AC-8 zweiter Teil (blockieren) — dann wäre nachzubessern.
  *Erledigt 2026-08-08:* gemessen, der Zugriff steht (sechs Kernseiten in 6,1 s).
- **Die Tests bewachen die QUELLE der Anmeldedaten, nicht ihre GÜLTIGKEIT.**
  `test_app_credentials_for_staging_come_from_the_staging_env` belegt, dass
  `GZ_AUTH_*` bei Staging-Ziel aus `STAGING_ENV_PATH` stammt — nicht, dass das
  dort hinterlegte Passwort noch stimmt. Wird es auf Staging gedreht, ohne die
  Datei nachzuziehen, bleibt die Kern-Suite grün und das Gate blockiert
  trotzdem jede Frontend-Auslieferung. Sichtbar wird das erst im Staging-Lauf,
  und zwar an der Meldung „Anmeldung abgelehnt" (nicht an „zurückgeleitet auf
  die Anmeldemaske"). Ohne echtes Staging ist diese Lücke nicht ehrlich
  schließbar; ein Kern-Test dafür wäre der Nachbau der eigenen Annahme.

## Regel-Budget

Neues Gate ⇒ **Prüfdatum 2026-11-05**. Fang-Beleg bei Einführung liegt vor: #1552 — Kernseite
unbedienbar trotz vollständig grüner Ampel und bestandener Adversary-Prüfung. Ob
`ui_screenshot_gate.py` dadurch ganz oder teilweise entbehrlich wird, ist am Prüfdatum mitzubewerten.
