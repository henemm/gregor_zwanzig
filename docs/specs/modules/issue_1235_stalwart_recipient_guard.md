---
entity_id: issue_1235_stalwart_recipient_guard
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [email, security, guard, resend, stalwart, issue-1235]
---

# Empfänger-Guard auch auf dem Stalwart-Pfad (Mail-Leck-Fix)

## Approval

- [ ] Approved

## Purpose

Issue #1235 schließt ein aktives Mail-Leck (86 Mails/48h an externe Fake-Adressen, zuletzt
2026-07-12 08:28, Root-Cause von infra via MQ 48151, am Code verifiziert): Der komplette
Empfänger-Guard in `EmailOutput.send()` greift heute ausschließlich, wenn `"resend"` im
SMTP-Host steckt (`src/output/channels/email.py:407`). Staging und praktisch alle Tests
senden aber zwingend über Stalwart (`mail.henemm.com`, #1122-Default-Deny) — dort existiert
KEIN Guard, obwohl Stalwart extern an Resend relayt (infra#114) und Alt-Presets mit
Fake-Empfängern (`test@example.com`, `e@x.invalid`) auf Staging persistieren und vom
Scheduler regulär mitversendet werden. Diese Spec macht den Guard bedingungslos: Resend
verhält sich byte-identisch zu heute, Stalwart bekommt eine eigene, bewusst STRENGERE
Prüfkette (reservierte Test-Domains immer blocken, externe Empfänger komplett blocken,
nur lokale `@henemm.com`-Zustellung — inkl. `gregor-test@`/`gregor-staging@` und
Plus-Adressen — bleibt erlaubt), weil Staging nie echte externe Nutzer anschreiben darf und
die #1219-Allowlist für den Resend-Pfad gedacht ist, nicht für einen Relay-Umweg über
Stalwart.

## Source

- **File:** `src/output/channels/email.py`
- **Identifier:** `EmailOutput.send()` (Guard-Block ab Zeile 407), neue Modul-Funktion
  `_is_local_mail_domain()`, neue Modul-Konstante `LOCAL_MAIL_DOMAINS`

**Schicht:** Python-Core/Domain-Backend (`src/output/channels/`) — kein Frontend, keine
Go-API betroffen. `channels/email.py` ist zugleich Renderer-Mail-Gate-Datei (#811).

## Estimated Scope

- **LoC:** `email.py` ~35-50 LoC (neue Konstante + neue Helper-Funktion mit Docstring +
  Umbau des Guard-Blocks in `send()` von `if resend` auf `if resend / else`); Test-Korpus
  ~120-180 LoC (Invertierung AC-4, neue Testklasse mit 6+ Fällen inkl. Bypass-Härtung,
  ein Live-Test analog #1147-AC-3).
- **Files:** 1 Quelldatei + 2 Testdateien (`test_resend_recipient_allowlist.py` AC-4
  invertiert, neue Datei `test_stalwart_recipient_guard.py`)
- **Effort:** medium (Sicherheits-Fix, hohe Test-Sorgfalt wegen Bypass-Härtung und
  Selbst-Blockade-Risiko auf dem eigenen E2E-Pfad)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_normalized_addrs_for_guard()` (`email.py:64`) | function | liefert bereits case-/plus-/Trennzeichen-normalisierte Kandidaten je Empfänger — wird vom neuen Nicht-Resend-Zweig 1:1 wiederverwendet (kein neuer Parser) |
| `_is_reserved_test_domain()` (`email.py:141`) | function | RFC-2606-Check, bleibt UNVERÄNDERT; wird im neuen Zweig zusätzlich aufgerufen (reservierte Domains blocken auch auf Stalwart) |
| `TEST_MAILBOXES` (`email.py:33`) | constant | unverändert, rein dokumentarisch (s. Kommentar dort); `gregor-test@`/`gregor-staging@henemm.com` werden künftig über `LOCAL_MAIL_DOMAINS`, nicht über diese Konstante, erlaubt |
| `_mask_addr_for_log()` (`email.py:211`) | function | unverändert; Fehlermeldung/Log auf dem neuen Zweig nutzt dieselbe Maskierung wie der Resend-Zweig |
| `OutputConfigError` (`src/output/channels/base.py`) | exception | unverändert; gleicher Fehlertyp wie #1219 auf beiden Zweigen |
| `Settings._resend_default_deny` (`src/app/config.py:163-186`, #1122) | config | UNVERÄNDERT — Grund, warum Stalwart der De-facto-Standardpfad für Staging/Tests ist (macht diesen Fix erst notwendig); nur dokumentiert, nicht angefasst |
| `tests/tdd/test_resend_recipient_allowlist.py::TestAC4StalwartHostGuardInactive` (Zeile 259-280) | test | **wird invertiert** — der bisherige AC-4 („Stalwart-Guard greift NICHT") beschreibt exakt das jetzt geschlossene Leck; neuer Test-Inhalt s. Implementation Details |
| `tests/tdd/test_issue_1147_resend_recipient_invariant.py::TestAC3StalwartTestMailboxUnaffected` (Zeile 557-579+, `@pytest.mark.email`, `GZ_TEST_SMTP_*`-Skip-Guard) | test | Regressions-Anker: echte Stalwart-Zustellung an `gregor-test@henemm.com` MUSS nach dem Fix weiter funktionieren — bleibt unverändert grün, beweist live die Lokal-Erlaubnis |
| `.claude/hooks/renderer_mail_gate.py` (#811) | gate | greift bei `channels/email.py` — Matrix-Test + `briefing_mail_validator.py` mit echter Test-Mail an `gregor-test@henemm.com` vor Commit; die Test-Mail läuft über Stalwart und beweist damit selbst die Lokal-Erlaubnis end-to-end |
| `henemm-infra/scripts/check-gregor20.sh` Abschnitt 3b (Resend-Sent-Log-Wächter) | external | Post-Deploy-Verifikation extern durch infra: 0 Treffer für externe Fake-Empfänger nach diesem Fix (kein blockierender AC dieser Spec, s. Known Limitations) |

## Implementation Details

### 1. Neue Modul-Konstante `LOCAL_MAIL_DOMAINS`

Direkt neben `TEST_MAILBOXES` (`email.py:33`):

```python
# Issue #1235: Domains, die Stalwart LOKAL zustellt (kein Relay an Resend).
# henemm.com ist die einzige von Stalwart bediente Domain -- Empfaenger
# dieser Domain (inkl. gregor-test@/gregor-staging@ und Plus-Adressen)
# sind auf dem Nicht-Resend-Pfad ausdruecklich erlaubt, weil die Zustellung
# lokal bleibt und nicht extern relayt wird (vgl. infra#114).
LOCAL_MAIL_DOMAINS = frozenset({"henemm.com"})
```

### 2. Neue Funktion `_is_local_mail_domain(addr: str) -> bool`

Direkt nach `_is_reserved_test_domain()` (`email.py:141-152`), spiegelbildlich aufgebaut
(gleiche Härtung: Trailing-Dot-Strip, Lowercase, exakter Domain-Vergleich statt
Substring/Suffix — verhindert das #1147-F001..5-Bypass-Muster, z.B. `user@henemm.com.evil.example`
wäre KEIN Treffer):

```python
def _is_local_mail_domain(addr: str) -> bool:
    """Issue #1235: True, wenn die Domain von `addr` (nach Normalisierung:
    Trailing-Dot gestrippt, lowercase) exakt in LOCAL_MAIL_DOMAINS liegt.
    Exakter Vergleich, kein Suffix-/Substring-Match (Bypass-Haertung
    analog _is_reserved_test_domain)."""
    domain = _extract_addr(addr).strip().lower().rpartition("@")[2]
    domain = domain.rstrip(".")
    return domain in LOCAL_MAIL_DOMAINS
```

Plus-Adressierung (`gregor-test+e2e@henemm.com`) braucht hier KEINEN eigenen Umgang: die
Kandidaten kommen bereits durch `_normalized_addrs_for_guard()` (die intern
`_normalize_addr_for_guard()` mit Plus-Kappung aufruft), die Domain bleibt davon unberührt.

### 3. Umbau des Guard-Blocks in `send()` (`email.py:407-454`)

Der bestehende `if "resend" in (self._host or "").lower():`-Block (Zeile 407) bleibt
**unverändert** — Resend-Pfad ist byte-identisch (AC-4 dieser Spec). Neu ist ein
`else:`-Zweig für jeden anderen Host (Stalwart und alles sonstige), der dieselbe
Empfänger-Iteration und `_normalized_addrs_for_guard`-Kandidatenbildung wie der
Resend-Zweig wiederverwendet, aber eine andere Entscheidungsregel anwendet:

```python
else:
    blocked = []
    for r in recipients:
        candidates = [a for a in _normalized_addrs_for_guard(r) if "@" in a]
        if (
            not candidates
            or any(_is_reserved_test_domain(a) for a in candidates)
            or any(not _is_local_mail_domain(a) for a in candidates)
        ):
            blocked.append(r)
    if blocked:
        masked = [_mask_addr_for_log(r) for r in blocked]
        logger.warning(
            "Lokal-Guard blockiert %d Empfaenger ausserhalb von "
            "LOCAL_MAIL_DOMAINS bzw. mit reservierter Test-Domain "
            "(Issue #1235) bei Host %r: %s",
            len(blocked), self._host, masked,
        )
        raise OutputConfigError(
            "email",
            f"{len(blocked)} Empfänger nicht lokal zustellbar "
            f"bei Host {self._host!r} — Versand blockiert (Issue #1235). "
            "Auf dem Nicht-Resend-Pfad sind ausschließlich lokale "
            f"@henemm.com-Empfänger erlaubt. Betroffene Domains: {masked}",
        )
```

**Bewusst KEIN** Aufruf von `_raw_contains_test_mailbox()` in diesem Zweig: dieser Check
existiert, um `gregor-test@`/`gregor-staging@henemm.com` gerade vor Resend-Versand zu
schützen (diese Postfächer gehören zu keinem echten Nutzerprofil). Auf dem lokalen
Stalwart-Pfad ist genau diese Zustellung der gewollte Fall (AC-3) — `_is_local_mail_domain`
lässt sie über `LOCAL_MAIL_DOMAINS` passieren, ohne den Resend-spezifischen Denylist-Check
zu berühren.

**Reihenfolge der Bedingungen ist bewusst:** `_is_reserved_test_domain` wird UNABHÄNGIG
von `_is_local_mail_domain` geprüft (beide Bedingungen sind ODER-verknüpft in derselben
`if`) — ein reserviertes Test-Domain-Präfix blockt immer, selbst wenn es (hypothetisch)
zufällig auch lokal wäre; das ist bei `henemm.com` nicht der Fall, macht die Regel aber
robust gegen künftige `LOCAL_MAIL_DOMAINS`-Erweiterungen.

### 4. Testinvertierung `TestAC4StalwartHostGuardInactive` → `TestAC4StalwartHostGuardBlocksExternal`

`tests/tdd/test_resend_recipient_allowlist.py:259-280`: Der bestehende Test behauptet
„Allowlist-Guard darf bei Stalwart-Host nicht greifen" — das ist exakt die jetzt
geschlossene Lücke. Der Test wird umbenannt und invertiert: GIVEN Stalwart-Host mit
`unbekannt@example.com` (Bestandsfixture) / WHEN `send()` / THEN wirft `send()`
`OutputConfigError` und die Meldung referenziert Issue #1235 (nicht mehr „darf nicht
greifen"). Dokumentiert als bewusste, begründete Verhaltensänderung — kein stilles
Umschreiben (Changelog-Pflicht, s.u.).

### 5. Neue Testklasse(n) — `tests/tdd/test_stalwart_recipient_guard.py`

Namensregel beachtet (nach Verhalten, nicht nach Issue-Nummer). Deterministischer
Kern-Test-Stil analog `test_resend_recipient_allowlist.py::_resend_bypass_settings`
(Fake-`Settings`, `smtp_host="mail.henemm.com"`, Exception VOR SMTP-Connect erwartet):

| Fall | Empfänger | Erwartung |
|---|---|---|
| reservierte Domain | `test@example.com` | `OutputConfigError` (Issue #1235 in Meldung) |
| reservierte Domain (Muster aus Leck) | `e@x.invalid` | `OutputConfigError` |
| externer echter Empfänger | `user@gmail.com` | `OutputConfigError` (auch wenn er in der #1219-Allowlist stünde — Stalwart-Pfad ist strenger, kein Allowlist-Bypass) |
| lokal, Test-Postfach | `gregor-test@henemm.com` | KEIN `OutputConfigError` (Guard lässt durch; SMTP-Fehler wegen Fake-Credentials ist ok/erwartet, entscheidend ist: kein Guard-Raise) |
| lokal, Plus-Adresse | `gregor-test+e2e@henemm.com` | KEIN `OutputConfigError` |
| Bypass: Case | `GREGOR-TEST@HENEMM.COM` | KEIN `OutputConfigError` (Normalisierung greift) |
| Bypass: Trailing-Dot | `gregor-test@henemm.com.` | KEIN `OutputConfigError` (lokal) bzw. für externe Variante `user@example.com.` weiterhin blockiert |
| Bypass: Semikolon-Liste | `"gregor-test@henemm.com; evil@example.com"` | `OutputConfigError` (ein nicht-lokaler/reservierter Kandidat blockt die gesamte Liste — Allow-Logik: ALLE Kandidaten müssen lokal UND unreserviert sein) |
| Bypass: Anzeigename | `'"Gregor Test" <gregor-test@henemm.com>'` | KEIN `OutputConfigError` |

Live-Fall (Regressions-Anker, bereits bestehend, kein neuer Test nötig): `TestAC3StalwartTestMailboxUnaffected` aus `test_issue_1147_resend_recipient_invariant.py:557-579+`
bleibt der Beweis der ECHTEN Zustellung (SMTP+IMAP, `@pytest.mark.email`).

### 6. Kern-Sweep

Da Stalwart der pytest-Standardpfad ist (#1122-Default-Deny), treffen ALLE Tests, die
`EmailOutput.send()` mit einem Nicht-Resend-Host und einem nicht-lokalen Fake-Empfänger
aufrufen, künftig den neuen Guard VOR dem bisherigen Fehlschlagspunkt (SMTP-Connect-Fehler
o.ä.). Vor dem Commit läuft ein gezielter Sweep über `tests/` nach `EmailOutput(` /
`.send(` mit Nicht-`henemm.com`-Empfängern, um Kollateral-Failures zu identifizieren und
ggf. Fixture-Empfänger auf `@henemm.com`-Adressen umzustellen (kein AC-Text-Änderung an
fremden Test-ACs, nur Empfänger-Fixtures).

## Expected Behavior

- **Input:** `EmailOutput.send(to=...)` mit beliebigem `self._host`.
- **Output (Resend-Host):** unverändert — Allowlist-/Reserved-/Raw-Test-Mailbox-Prüfung wie
  vor dieser Spec, byte-identisches Verhalten.
- **Output (Nicht-Resend-Host, z.B. Stalwart):** reservierte Test-Domains blocken immer;
  nicht-lokale (Nicht-`henemm.com`) Empfänger blocken immer, unabhängig von der
  #1219-Allowlist; lokale `@henemm.com`-Empfänger (inkl. `gregor-test@`/`gregor-staging@`
  und Plus-Adressen, case-insensitiv, Trailing-Dot-tolerant) werden zugestellt.
- **Side effects:** ein Block-Fall loggt eine domain-maskierte Warnung (`_mask_addr_for_log`)
  und wirft `OutputConfigError` VOR dem MIME-Bau/SMTP-Dial — kein Netzwerkzugriff bei
  geblocktem Empfänger.

## Acceptance Criteria

- **AC-1:** Given `EmailOutput` mit Nicht-Resend-Host (z.B. `mail.henemm.com`) / When
  `send(to=[...])` mit einer reservierten Test-Domain (`test@example.com` oder
  `e@x.invalid`) aufgerufen wird / Then wirft `send()` `OutputConfigError` mit Bezug auf
  Issue #1235, ohne dass ein SMTP-Connect stattfindet.
  - Test: `test_stalwart_recipient_guard.py` — zwei Fälle (`example.com`, `x.invalid`),
    Fake-`Settings`, Exception vor SMTP-Aufbau geprüft (Bestandsmuster aus
    `test_resend_recipient_allowlist.py`).

- **AC-2:** Given `EmailOutput` mit Nicht-Resend-Host / When `send(to=["user@gmail.com"])`
  (externer, echter Empfänger, NICHT in der #1219-Allowlist relevant) aufgerufen wird /
  Then wirft `send()` `OutputConfigError` — der Stalwart-Pfad kennt keine Allowlist-Ausnahme
  für externe Empfänger, er blockt sie kategorisch (strenger als der Resend-Pfad, s.
  Known Limitations für die Begründung).
  - Test: `test_stalwart_recipient_guard.py` — externer Empfänger ohne jede
    Allowlist-Beteiligung blockt.

- **AC-3:** Given `EmailOutput` mit Nicht-Resend-Host / When `send(to=["gregor-test@henemm.com"])`
  bzw. mit Plus-Adresse (`gregor-test+e2e@henemm.com`) aufgerufen wird / Then greift der
  Guard NICHT (kein `OutputConfigError`), und ein echter Stalwart-Versand an
  `gregor-test@henemm.com` mit IMAP-Abruf gelingt unverändert.
  - Test: `test_stalwart_recipient_guard.py` — Kern-Fälle (kein Raise, Fehlschlag danach
    ist SMTP-bedingt, nicht Guard-bedingt); Live-Beweis via unverändertem
    `test_issue_1147_resend_recipient_invariant.py::TestAC3StalwartTestMailboxUnaffected`
    (`@pytest.mark.email`) PLUS `briefing_mail_validator.py`-Lauf vor Commit (#811-Gate).

- **AC-4:** Given der Resend-Pfad (`if "resend" in (self._host or "").lower():`,
  `email.py:407`) nach diesem Fix / When die vollständige Bestands-Testsuite
  `test_resend_recipient_allowlist.py` (AC-1,2,3,5,6,7) sowie
  `test_issue_1147_resend_recipient_invariant.py` (alle Klassen außer der unter AC-5
  genannten Ausnahme) ausgeführt wird / Then bleibt jedes Ergebnis byte-identisch zum
  Stand vor dieser Spec.
  - Test: kompletter Lauf beider Dateien, keine Anpassung außer der unter AC-5
    dokumentierten Inversion.

- **AC-5:** Given `test_resend_recipient_allowlist.py::TestAC4StalwartHostGuardInactive`
  (Zeile 259-280, alter Titel „Stalwart-Guard greift nicht") / When diese Spec
  implementiert ist / Then ist der Test zu `TestAC4StalwartHostGuardBlocksExternal`
  umbenannt und geprüft, dass `send()` für den bisherigen Test-Empfänger
  (`unbekannt@example.com`, extern, nicht-lokal) jetzt `OutputConfigError` wirft — als
  dokumentierte, begründete Verhaltensänderung (infra#114 widerlegt die alte
  Design-Annahme „Stalwart braucht keinen Guard").
  - Test: der invertierte Test selbst; Changelog-Eintrag in dieser Spec verweist auf die
    Inversion.

- **AC-6:** Given die Bypass-Härtungsmuster aus #1147-F001..5 (Case, Semikolon-Trennung,
  gequoteter Anzeigename, Plus-Adressierung, Trailing-Dot) / When dieselben Muster gegen
  einen Nicht-Resend-Host mit sowohl lokalen als auch nicht-lokalen Kandidaten getestet
  werden / Then verhält sich der neue Guard bypass-resistent: eine gemischte Liste mit
  auch nur einem nicht-lokalen/reservierten Kandidaten blockt vollständig, reine
  lokale Varianten (Case-Variationen, Trailing-Dot, Anzeigename) passieren.
  - Test: `test_stalwart_recipient_guard.py` — mind. 5 Bypass-Fälle (s. Tabelle in
    Implementation Details Abschnitt 5).

- **AC-7:** Given der geänderte `send()`-Guard trifft auf den pytest-Standardpfad
  (Stalwart, #1122-Default-Deny) / When die betroffenen Kern-Testdateien nach dem Fix
  gezielt ausgeführt werden (`tests/tdd/`, alle Dateien mit `EmailOutput(` +
  `.send(`-Aufrufen) / Then treten keine NEUEN Fehlschläge auf, die auf den #1235-Guard
  zurückgehen (bestehende Fixture-Empfänger sind entweder bereits lokal oder werden im
  Rahmen dieser Spec auf `@henemm.com`-Adressen umgestellt).
  - Test: gezielter Sweep-Lauf vor Commit, Diff-Liste eventuell angepasster
    Fixture-Empfänger im Changelog dokumentiert.

## Known Limitations

- **infra#114 (Stalwart-Relay-Hintertür) bleibt offen** bis zum infra-seitigen Fix — diese
  Spec ist die ANWENDUNGSSEITIGE (erste) Verteidigungslinie; infra baut parallel eine
  zweite Verteidigung (Relay-Allowlist am Stalwart selbst). Ohne diesen App-seitigen Fix
  wäre Stalwart weiterhin der einzige ungesicherte Pfad.
- **Design-Entscheidung „strenger als Resend":** externe Empfänger, die in der
  #1219-Allowlist stehen (echte, verifizierte Nutzerprofile), werden auf dem
  Nicht-Resend-Pfad TROTZDEM geblockt. Begründung: Staging/Test-Instanzen sollen NIE echte
  Nutzer anschreiben (bestehendes `with_user_profile`-force_test-Prinzip); ein
  Allowlist-Bypass auf Stalwart würde genau das ermöglichen, sobald infra#114 den Relay
  öffnet. Diese Asymmetrie (Resend = Allowlist-basiert, Stalwart = nur lokal) ist bewusst
  und PO-relevant, falls sie später aufgeweicht werden soll.
- **Staging-Altdaten:** Presets mit `example.com`-Fake-Empfängern
  (`data/users/default/compare_presets.json`) bleiben nach diesem Fix bestehen, werden
  aber ab Deploy laut (Warning-Log) statt still geblockt — Aufräumen der Alt-Daten ist ein
  separater Nebenbefund/Deploy-Schritt, kein Teil dieser Spec.
- **Externe Verifikation nicht Teil der ACs:** `henemm-infra/scripts/check-gregor20.sh`
  Abschnitt 3b (Resend-Sent-Log-Wächter) soll nach dem Deploy 0 Treffer für externe
  Fake-Empfänger zeigen — das ist ein Post-Deploy-Beobachtungspunkt durch infra, kein
  blockierender AC dieser Spec (liegt außerhalb dieses Repos).
- `LOCAL_MAIL_DOMAINS` ist hartkodiert auf `henemm.com` (Tech-Entscheidung, kein
  konfigurierbares Setting) — konsistent mit der bereits hartkodierten `TEST_MAILBOXES`
  (`…@henemm.com`) im selben Modul; eine Umgebung mit einer anderen Stalwart-Domain
  bräuchte eine Spec-Erweiterung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine [no-adr]
- **Rationale:** Der Fix härtet eine bestehende Guard-Architektur (der #1219-Allowlist-Guard-
  Mechanismus bleibt strukturell identisch: Kandidatenbildung → Prüfregel → maskierter
  Log/Raise), erweitert sie lediglich um einen zweiten, host-abhängigen Zweig mit eigener
  Regel. Keine neue Abstraktion, keine neue externe Abhängigkeit, keine Schema-/
  Persistenzänderung, keine API-Vertragsänderung. Die einzige strukturelle Entscheidung
  (Nicht-Resend-Pfad strenger als Resend-Pfad statt Allowlist-Wiederverwendung) ist eine
  Sicherheits-Policy-Entscheidung, keine Architekturentscheidung — sie ist in den Known
  Limitations explizit begründet und für die Adversary-Prüfung vorweggenommen.

## Changelog

- 2026-07-12: Initial spec created (Root-Cause-Report infra MQ 48151, Analyse-Dokument
  `docs/context/fix-1235-stalwart-recipient-guard.md`).
