## Adversary Report F14a — Subscription Metriken-Auswahl

**Geprüft:** 2026-04-04
**Prüfer:** Validation Agent (adversary mode)
**Scope:** Model + Loader + UI + Dialog

---

### Punkt 1-2: Neue Subscription ohne Metrics-Dialog → display_config: null

**Verdict:** PASS
**Beweis:** Code-Inspektion `src/app/user.py` Z. 137 + Python-Verifikation
**Details:** `CompareSubscription` hat `display_config: Optional["UnifiedWeatherDisplayConfig"] = None`. Der "Save"-Handler in `show_subscription_dialog()` (Z. 410-424 in `subscriptions.py`) erstellt `CompareSubscription` ohne `display_config`-Argument → Default `None` greift korrekt. Verifiziert via:
```
new_sub.display_config is None  → True
```

---

### Punkt 3: Reports nutzen Standard-Metriken (keine Verhaltensänderung)

**Verdict:** PASS (F14a-Scope)
**Beweis:** Spec explizit: "F14a only stores the config — the renderer (compare.py) does NOT yet respect it (F14b scope)"
**Details:** Kein bestehender Code liest `subscription.display_config` aus. Bestehende Report-Logik unverändert.

---

### Punkt 4-5: "Wetter-Metriken" klicken → Dialog zeigt Defaults

**Verdict:** PASS (nach Server-Neustart — INFRASTRUKTUR-PROBLEM ENTDECKT)
**Beweis:** Screenshot `02-metrics-dialog.png` + Screenshot `03-metrics-dialog-bottom.png`
**Details:** Dialog öffnet korrekt mit Subscription-Name in Header ("Wetter-Metriken: Zillertal täglich"), Subtitle "Subscription-Vergleich", alle Metriken-Kategorien (Temperatur, Wind, Niederschlag, Atmosphäre, Winter) sichtbar. Defaults korrekt vorausgewählt (Temp, Feels, Wind, Gust, Rain, Thunder, SnowL, Cloud, Sun). Abbrechen- und Speichern-Buttons vorhanden.

**ABER: KRITISCHES INFRASTRUKTUR-PROBLEM**
Beim ersten Screenshot-Versuch war der "Wetter-Metriken"-Button NICHT sichtbar. Ursache: Der laufende Server-Prozess (PID 306262, gestartet 11:06) verwendete ALTEN Code, weil `gregor_zwanzig.service` nach der Implementierung (Dateien modifiziert 11:54-11:56) NICHT neu gestartet wurde. Der Service crashte wegen Port-Konflikt in einer Restart-Schleife und konnte den alten Prozess nicht ersetzen. Erst nach manuellem `kill 306262` lud der Service den neuen Code.

---

### Punkt 7-8: Hiking-Metriken aktivieren, Schnee deaktivieren → gespeichert

**Verdict:** PASS (Mechanismus verifiziert, kein Full-E2E-Click-Test)
**Beweis:** Code-Inspektion `weather_config.py` Z. 677-706 + Loader Round-Trip Test
**Details:** `make_subscription_save_handler()` liest Widget-Werte, erstellt `MetricConfig`-Liste, setzt `target.display_config = UnifiedWeatherDisplayConfig(...)`, ruft `save_compare_subscription(target, uid)` auf. Round-Trip-Test bestätigt JSON-Persistenz (24 Metriken, `trip_id`, `updated_at` korrekt gespeichert und geladen).

---

### Punkt 9: Notification + Dialog schließt

**Verdict:** PASS
**Beweis:** Code-Inspektion `weather_config.py` Z. 701-706
**Details:** `ui.notify(f"{sum(...)} Metriken gespeichert", type="positive")` gefolgt von `dlg.close()`. Minimum-1-Metrik-Validation vorhanden (Z. 694-696).

---

### Punkt 10-11: Legacy JSON ohne display_config → None

**Verdict:** PASS
**Beweis:** Produktions-JSON + Python-Verifikation
**Details:** `data/users/default/compare_subscriptions.json` enthält keinen `display_config`-Key und ebenfalls keine `send_email`/`send_signal`-Keys. Loader liest korrekt:
```
subs[0].display_config → None
subs[0].send_email → True (default)
subs[0].send_signal → False (default)
```

---

### Punkt 13-14: Toggle preserviert display_config

**Verdict:** PASS
**Beweis:** Code-Inspektion `subscriptions.py` Z. 179 + Python-Verifikation
**Details:** `make_toggle_handler()` übergibt explizit `display_config=subscription.display_config` beim Rekonstruieren. Automatischer Test:
```
display_config preserved after toggle: True
metrics count: 24
```

---

### Punkt 15: Metric Config nicht verloren

**Verdict:** FAIL — KRITISCHER BUG
**Beweis:** `subscriptions.py` Z. 410-424 + Python-Verifikation

**Problem:** `show_subscription_dialog()` (Edit-Dialog für Subscription-Name, Locations, Schedule etc.) erstellt beim Speichern ein neues `CompareSubscription` OHNE `display_config`:

```python
new_sub = CompareSubscription(
    id=sub_id,
    name=name_input.value,
    ...
    send_email=send_email_cb.value,
    send_signal=send_signal_cb.value,
    # display_config fehlt → None
)
```

**Auswirkung:** User öffnet Wetter-Metriken-Dialog → konfiguriert Metriken → speichert. Danach öffnet User den Edit-Dialog (Bleistift-Icon) → ändert z.B. den Schedule → speichert. display_config wird auf `None` zurückgesetzt, alle Metrik-Konfigurationen sind verloren.

**Bestätigt durch:**
```
display_config after edit save: None
BUG CONFIRMED: display_config was LOST
```

**Fix:** In `show_subscription_dialog()` → `do_save()`, in `CompareSubscription(...)` hinzufügen:
```python
display_config=sub.display_config if not is_new else None,
```

---

## Defekte

### BUG-001: Edit-Dialog löscht display_config (KRITISCH)

**Datei:** `/home/hem/gregor_zwanzig/src/web/pages/subscriptions.py`, Funktion `show_subscription_dialog()` → `make_save_handler()` → `do_save()`
**Zeile:** ~410-424
**Schwere:** HOCH — User verliert Metrik-Konfiguration bei jeder Subscription-Bearbeitung
**Reproduktion:**
1. Subscription hat display_config (Wetter-Metriken gesetzt)
2. Edit-Dialog öffnen (Bleistift-Icon)
3. Irgendwas ändern und speichern
4. display_config ist weg

**Fix:**
```python
new_sub = CompareSubscription(
    ...
    send_signal=send_signal_cb.value,
    display_config=sub.display_config if not is_new else None,
)
```

### INFRASTRUKTUR-HINWEIS: Service-Restart nach Deployment

**Problem:** Nach Implementierung wurde der Service nicht neu gestartet. Der alte Prozess hielt Port 8080, der neue Service-Start schlug fehl. Seite zeigte Code-Stand von vor der Implementierung.
**Fix:** Nach Code-Änderungen immer: `systemctl restart gregor_zwanzig.service` und prüfen ob Service tatsächlich läuft.

---

## Gesamtverdikt

**BROKEN**

Alle 14 Punkte außer Punkt 15 sind korrekt implementiert. Punkt 15 (Metric Config nicht verloren) schlägt fehl wegen eines klar identifizierten Bugs: Der allgemeine Edit-Dialog setzt `display_config` auf `None` zurück, weil das Feld nicht aus der bestehenden Subscription übernommen wird. Dieser Bug macht das Kern-Feature F14a praktisch unzuverlässig — jede Bearbeitung der Subscription-Grunddaten löscht die Metrik-Konfiguration.

---

## Test Plan

### Automatisierte Tests (bestehend)
- [x] 9/9 Tests in `tests/tdd/test_subscription_metrics.py` grün
- [ ] FEHLT: Test für display_config-Erhalt nach Edit-Dialog-Save

### Manuelle Tests
- [x] Screenshot: Wetter-Metriken-Button sichtbar auf Subscriptions-Seite (`01-subscriptions-page.png`)
- [x] Screenshot: Metriken-Dialog öffnet korrekt mit Defaults (`02-metrics-dialog.png`)
- [x] Screenshot: Winter-Kategorie sichtbar im Dialog (`03-metrics-dialog-bottom.png`)
- [ ] FEHLT: Klick-Test: Metriken konfigurieren → Speichern → Edit-Dialog → Speichern → display_config prüfen

### Edge-Case-Tests (zu ergänzen)
- [ ] Fehlender Test: Metric Config nach Edit-Dialog-Save erhalten?
- [ ] Fehlender Test: Metric Config nach Subscription-Delete + Re-Create?
- [ ] Fehlender Test: Leere Aggregationsliste beim Speichern?
