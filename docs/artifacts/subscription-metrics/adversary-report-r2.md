## Adversary Report F14a — Subscription Metriken-Auswahl (Runde 2)

**Geprüft:** 2026-04-04
**Prüfer:** Validation Agent (adversary mode)
**Scope:** Bug-Fix-Verifikation + Neue Edge-Cases + Regressions-Check

---

## 1. Bug-Fix-Verifikation: BUG-001 (display_config im Edit-Dialog verloren)

**Verdict: PARTIAL FIX — Teilweise korrekt, teilweise unvollständig**

Der Fix in `/home/hem/gregor_zwanzig/src/web/pages/subscriptions.py` Z. 424:

```python
display_config=sub.display_config if not is_new else None,
```

Die Python-Short-Circuit-Evaluation ist korrekt: bei `is_new=True` wird `sub.display_config` nie ausgewertet (sub ist dann None), kein Crash.

Der Fix schützt **Szenario A** (Haupt-Use-Case des R1-Bugs):

1. Seite laden → subscription_list() liest display_config von Disk → sub.display_config = X
2. Edit-Dialog öffnen → sub mit display_config=X übergeben
3. Edit speichern → display_config=sub.display_config = X BEWAHRT

Der Fix **schützt nicht Szenario B** (normaler User-Flow, neuer Bug):

1. Seite laden → sub.display_config = None (noch kein Metriken-Dialog)
2. "Wetter-Metriken" klicken → konfigurieren → speichern (Disk aktualisiert)
3. `subscription_list.refresh()` wird NICHT aufgerufen — Karten-Sub-Objekte sind veraltet
4. Edit-Dialog (Bleistift) klicken → sub.display_config = None (veraltetes Objekt!)
5. Edit speichern → display_config = None → Metrik-Konfiguration verloren

**Ursache:** `show_subscription_weather_config_dialog()` in `weather_config.py` hat keinen Zugang zu `refresh_fn`. Das save-handler-Ende ruft nur `dlg.close()` — kein Page-Refresh. Die Subscription-Karte bleibt mit dem alten `sub`-Objekt im Speicher.

---

## 2. Spec-Punkte 1-15 — Vollständige Prüfung

### Punkte 1-14

**Verdict: PASS (unverändert gegenüber R1)**

Alle 9 Tests in `tests/tdd/test_subscription_metrics.py` grün (0 Fehler):

```
tests/tdd/test_subscription_metrics.py .........  [9/9 PASSED]
```

Details wie R1-Report. Kein Regressionstest neu fehlgeschlagen.

### Punkt 15: Metric Config nicht verloren

**Verdict: PARTIAL FIX**

- Szenario A (display_config war beim Seitenaufruf bereits gespeichert): FIX KORREKT
- Szenario B (display_config in derselben Session erstmals konfiguriert): WEITERHIN BROKEN

---

## 3. Edge Cases

### Edge Case 1: Save-Handler bei is_new=True

**Verdict: PASS**
`sub.display_config` wird bei `is_new=True` nie ausgewertet (Python Short-Circuit). Kein Crash.

### Edge Case 2: Metriken-Dialog — Nichts ändern, Speichern klicken

**Verdict: PASS**
Der Handler liest Widget-Werte und erstellt MetricConfig für alle sichtbaren Metriken. Da Defaults korrekt vorausgewählt sind (aus `build_default_display_config`), entsteht eine gültige Konfiguration. Das Minimum-1-Guard (Z. 694-696) greift, falls alle deaktiviert wären.

### Edge Case 3: Alle Metriken deaktivieren

**Verdict: PASS**
Z. 694-696 in `weather_config.py`:
```python
if sum(1 for m in metrics if m.enabled) == 0:
    ui.notify("Mindestens 1 Metrik!", type="warning")
    return
```
Dialog bleibt offen, keine Speicherung. Korrekt.

### Edge Case 4: Leere Aggregationsliste

**Verdict: PASS (keine Crash-Gefahr, aber semantisch fragwürdig)**
`MetricConfig(aggregations=[])` ist technisch valide und wird korrekt serialisiert/deserialisiert. Eine Metrik mit 0 Aggregationen hat in F14b keine Auswirkung (F14b ist ohnehin noch nicht implementiert). Kein Crash.

### Edge Case 5: Subscription-ID Kollision

**Verdict: WARNING (pre-existing, F14a-unabhängig)**
`re.sub(r'[^a-z0-9]', '-', name.lower())` entfernt Umlaute teilweise:
- "Zillertal täglich" → "zillertal-t-glich"
- "Zillertal Täglich" → "zillertal-t-glich" (identisch)

Zwei Subscriptions mit ähnlichen Namen erzeugen dieselbe ID → stiller Overwrite. Dieser Bug existiert vor F14a und ist F14a-unabhängig.

### Edge Case 6: Race Condition Metriken-Dialog + gleichzeitiger Edit-Dialog

**Verdict: PASS (nicht möglich in NiceGUI-Modals)**
NiceGUI Dialoge blockieren die Interaktion nicht per se, aber das UI würde beide Dialoge gleichzeitig zeigen. In der Praxis unwahrscheinlich. Wenn beide gespeichert werden, gilt Last-Write-Wins auf Disk (kein atomares Locking). Pre-existing, nicht F14a-spezifisch.

---

## 4. Screenshots (visuell geprüft)

**04-r2-subscriptions.png:** Subscription-Karte "Zillertal täglich" mit "WETTER-METRIKEN"-Button (gear-Icon + Text). Button sichtbar und korrekt positioniert (vor Edit-Icon).

**05-r2-metrics-dialog.png:** Dialog "Wetter-Metriken: Zillertal täglich", Subtitle "Subscription-Vergleich". Kategorien Temperatur, Wind, Niederschlag sichtbar. Defaults korrekt vorausgewählt (Temp, Feels, Wind, Gust, Rain). Aggregations-Dropdowns zeigen korrekte Werte.

---

## 5. Regressions-Check

```
tests/tdd/test_subscription_metrics.py    .........  [9 PASSED]
tests/tdd/test_channel_switch_subscription.py  ......  PASSED
tests/tdd/test_generic_locations.py            ......  PASSED
tests/test_loader.py                          ........  PASSED
```

Alle F14a-relevanten Tests grün. Keine Regressionen.

Die Fehler in `tests/tdd/test_weather_config_api_ui.py` (10 ERRORS) sind pre-existing Infrastructure-Fehler (`/opt/gregor_zwanziger` nicht gefunden) — unverändert gegenüber R1, F14a-unabhängig.

---

## 6. Neue Defekte

### BUG-002: Szenario B — display_config-Verlust nach Erstkonfiguration in derselben Session

**Datei:** `/home/hem/gregor_zwanzig/src/web/pages/weather_config.py`
**Funktion:** `show_subscription_weather_config_dialog()` → `make_subscription_save_handler()` → `do_save()`
**Schwere:** MITTEL — Tritt bei normalem First-Use auf, aber nur in derselben Seitenladung. Nach Seitenneuladen ist Szenario A aktiv (Fix greift).
**Reproduktion:**
1. Subscriptions-Seite laden (display_config noch nicht gesetzt)
2. "Wetter-Metriken" klicken → Metriken konfigurieren → Speichern
3. (Seite NICHT neu laden)
4. Edit-Icon klicken → irgendetwas ändern → Speichern
5. display_config ist zurückgesetzt auf None

**Ursache:** `show_subscription_weather_config_dialog()` hat keine Referenz auf `subscription_list.refresh` und ruft nach dem Speichern kein Page-Refresh auf. Die In-Memory-Subscription-Objekte in den Karten-Closures sind veraltet.

**Fix-Option:**
`show_subscription_weather_config_dialog()` einen optionalen `refresh_fn`-Parameter geben, den der Metrics-Save-Handler aufruft. Alternativ: Im Edit-Dialog (`make_save_handler`) immer frisch von Disk laden statt das gecaptured `sub`-Objekt zu verwenden.

Die robustere Lösung wäre: In `do_save()` der Edit-Dialog-Handler die bestehende `display_config` von Disk laden:

```python
# Statt: display_config=sub.display_config if not is_new else None
# Besser:
if not is_new:
    current_subs = load_compare_subscriptions()
    current = next((s for s in current_subs if s.id == sub_id), None)
    display_config = current.display_config if current else None
else:
    display_config = None
```

---

## Gesamtverdikt

**PARTIAL FIX / BROKEN (Szenario B)**

Der R1-Bug (BUG-001) ist für das beschriebene Szenario A korrekt gefixt — wenn die Seite neu geladen wird bevor der Edit-Dialog geöffnet wird, bleibt display_config erhalten.

Szenario B (normaler First-Use-Flow ohne Seitenneuladung) ist weiterhin broken. Ein neu gefundener Bug (BUG-002) beschreibt diesen Fall.

**Empfehlung:** Fix für BUG-002 implementieren, dann R3-Validierung.

---

## Test Plan

### Automatisierte Tests
- [x] 9/9 Tests in `tests/tdd/test_subscription_metrics.py` grün
- [ ] FEHLT: Test für Szenario B (display_config-Verlust nach Erstkonfiguration)

### Manuelle Tests
- [x] Screenshot 04-r2-subscriptions.png: Button sichtbar
- [x] Screenshot 05-r2-metrics-dialog.png: Dialog korrekt
- [ ] Manueller Test Szenario B: Neue Sub, Metriken setzen, Edit ohne Reload → prüfen

### Edge-Case-Tests
- [x] is_new=True: kein Crash (Python Short-Circuit)
- [x] Alle deaktivieren: Guard greift
- [x] Leere Aggregationen: kein Crash
- [ ] Szenario B Reproduktion: Page-Session ohne Reload
