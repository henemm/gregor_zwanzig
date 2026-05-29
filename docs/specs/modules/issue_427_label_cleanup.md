# Spec: Issue #427 — GitHub Labels & Issues aufräumen

**Status:** Draft  
**Issue:** #427  
**Typ:** Wartung (keine Code-Änderungen)

---

## Ziel

Labels im Repo `henemm/gregor_zwanzig` auf einheitliches `type:`-Präfix-Schema konsolidieren.
Offene Issues erhalten korrekte `type:`-Labels. Redundante Legacy-Labels werden gelöscht.

---

## Acceptance Criteria

**AC-1:** Given das `enhancement`-Label existiert / When es umbenannt wird / Then heißt es `type:feature` und alle 117 Issue-Verknüpfungen bleiben erhalten.

**AC-2:** Given Issues #438–443 haben `feature` aber kein `type:feature` / When die Migration läuft / Then haben sie `type:feature` und kein `feature` mehr.

**AC-3:** Given Issue #426 hat `feature` + `type:feature` / When die Migration läuft / Then hat es nur noch `type:feature` (kein Duplikat).

**AC-4:** Given Label `feature` existiert / When alle Issues migriert sind / Then wird das Label gelöscht.

**AC-5:** Given Label `bug` existiert (50 closed Issues, 0 open) / When die Migration läuft / Then wird das Label gelöscht (closed Issues werden nicht nachträglich umgetaggt).

**AC-6:** Given offene Issues #368, #351, #349 haben kein `type:`-Label / When die Migration läuft / Then haben sie das korrekte `type:`-Label (#368 → `type:feature`, #351/#349 → `type:bug`).

**AC-7:** Given offene Issues #444, #445, #446 haben kein `type:`-Label / When die Migration läuft / Then haben sie `type:rework` (#444, #445) bzw. `type:infra` (#446).

**AC-8:** Given das Label `priority:critical` hat keine Beschreibung / When die Migration läuft / Then hat es die Beschreibung "Kritischer Fehler — blockiert Betrieb".

---

## Implementierungs-Commands

### Schritt 1 — `enhancement` umbenennen (Label-Associations bleiben erhalten)

```bash
gh label edit "enhancement" --name "type:feature" --repo henemm/gregor_zwanzig
```

### Schritt 2 — #438–443: `feature` → `type:feature`

```bash
for num in 438 439 440 441 442 443; do
  gh issue edit $num --add-label "type:feature" --remove-label "feature" --repo henemm/gregor_zwanzig
done
```

### Schritt 3 — #426: doppeltes `feature` entfernen

```bash
gh issue edit 426 --remove-label "feature" --repo henemm/gregor_zwanzig
```

### Schritt 4 — Label `feature` löschen

```bash
gh label delete "feature" --yes --repo henemm/gregor_zwanzig
```

### Schritt 5 — Label `bug` löschen

```bash
gh label delete "bug" --yes --repo henemm/gregor_zwanzig
```

### Schritt 6 — Offene Issues ohne `type:`-Label korrigieren

```bash
# Epics / Features
gh issue edit 368 --add-label "type:feature" --repo henemm/gregor_zwanzig

# Backend-Bugs
gh issue edit 351 --add-label "type:bug" --repo henemm/gregor_zwanzig
gh issue edit 349 --add-label "type:bug" --repo henemm/gregor_zwanzig

# Refactoring-Issues
gh issue edit 444 --add-label "type:rework" --repo henemm/gregor_zwanzig
gh issue edit 445 --add-label "type:rework" --repo henemm/gregor_zwanzig

# Infrastruktur/Hardening
gh issue edit 446 --add-label "type:infra" --repo henemm/gregor_zwanzig
```

### Schritt 7 — `priority:critical` Beschreibung ergänzen

```bash
gh label edit "priority:critical" --description "Kritischer Fehler — blockiert Betrieb" --repo henemm/gregor_zwanzig
```

---

## Nach der Migration: erwarteter Zustand

| Was | Vorher | Nachher |
|-----|--------|---------|
| Labels mit `type:`-Präfix | 5 | 5 (unverändert) |
| Legacy-Labels ohne `type:` | 3 (`bug`, `feature`, `enhancement`) | 0 |
| Offene Issues ohne `type:`-Label | 14 | 0 |
| Doppelt gelabelte Issues | 4 | 0 |

---

## Risiken

- **Reversibel:** Alle Änderungen sind rückgängig machbar (Label neu anlegen, Issues re-taggen).
- **Keine Code-Änderungen:** Kein Deploy, kein Test-Lauf nötig.
- **Keine Daten-Risiken:** Nur GitHub-Metadaten.
