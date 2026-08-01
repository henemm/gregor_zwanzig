# Spec: #873 — Schneehöhe/Schneefallgrenze als SMS-Display-Filter

## Ziel

Nutzer können in den Wetter-Metriken → Schwellwerte einstellen, ab welchem Wert der
Schneehöhe-Token (SD) bzw. der Schneefallgrenze-Token (SL) in SMS/Telegram-Kurzform erscheinen soll.

> **Kürzel-Umstellung 2026-08-01 (#1435 Etappe E3b).** Diese Spec wurde mit den
> damaligen Kürzeln `SN` (Schneehöhe), `SN24+` (Neuschnee) und `SFL`
> (Schneefallgrenze) geschrieben. Sie heissen jetzt `SD`, `NS24+` und `SL`
> (Wetter-Register, `metric_catalog.sms_code`); `SN` bezeichnet ausschliesslich
> die amtliche Schneewarnung. **Die Filter-Logik dieser Spec ist unverändert** —
> nur die Kürzel wurden ersetzt. Spec:
> `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md`.

## Kontext

SD und SL werden in `_wintersport()` als einfache Tageswerte gerendert — ohne
Threshold-Filterung. Das bestehende Threshold-System (Issue #624) funktioniert nur
für `R`, `PR`, `W`, `G`, `TH:` (via `_mk_metric()`). Diese Spec erweitert es um SD
und SL mit einer Sonderregel für SL (inverse Logik).

## Acceptance Criteria

**AC-1:** Given der Nutzer hat für Schneehöhe einen Schwellwert S konfiguriert und der
Tages-Schneehöhenwert ist **unter** S, When SMS/Telegram-Kurzform generiert wird,
Then erscheint **kein SD-Token** in der Ausgabe.

**AC-2:** Given der Nutzer hat für Schneehöhe einen Schwellwert S konfiguriert und der
Tages-Schneehöhenwert ist **≥ S**, When SMS/Telegram-Kurzform generiert wird,
Then erscheint **SD-Token** wie bisher (z.B. `SD15`).

**AC-3:** Given der Nutzer hat für Schneefallgrenze einen Schwellwert S konfiguriert und
die Schneefallgrenze liegt **über** S (höhere Schneefallgrenze = weniger relevant),
When SMS generiert wird, Then erscheint **kein SL-Token** in der Ausgabe.

**AC-4:** Given der Nutzer hat für Schneefallgrenze einen Schwellwert S konfiguriert und
die Schneefallgrenze liegt **≤ S** (niedrige Schneefallgrenze = relevant),
When SMS generiert wird, Then erscheint **SL-Token** wie bisher (z.B. `SL1200`).

**AC-5:** Given **kein** Schwellwert für SD oder SL konfiguriert ist,
When SMS generiert wird, Then erscheinen SD- und SL-Tokens unverändert
(kein Verhalten-Regress gegenüber Ist-Zustand).

**AC-6:** Given der Nutzer öffnet Wetter-Metriken → Abschnitt 04 — Schwellwerte,
When Schneehöhe als Metrik aktiv ist,
Then ist eine Zeile **Schneehöhe** mit 3 Stufen (Sensibel=5 cm / Standard=10 cm / Robust=20 cm)
sichtbar und speicherbar.

**AC-7:** Given der Nutzer öffnet Wetter-Metriken → Abschnitt 04 — Schwellwerte,
When Schneefallgrenze als Metrik aktiv ist,
Then ist eine Zeile **Schneefallgrenze** mit 3 Stufen (Sensibel=2000 m / Standard=1500 m / Robust=1000 m)
sichtbar und speicherbar.

## Technische Umsetzung

### 1. `src/formatters/sms_trip.py`

`SMS_SYMBOL_BY_METRIC` um zwei Einträge ergänzen:
```python
"snow_depth": get_sms_code("snow_depth"),        # -> "SD"
"snowfall_limit": get_sms_code("snowfall_limit"),  # -> "SL"
```

→ Damit werden per `MetricConfig.sms_threshold` gespeicherte Werte automatisch
als `MetricSpec.threshold` in den Builder durchgereicht (bestehender Mechanismus
in `trip_report.py` Z. 196–200 und `preview_service.py` Z. 200–203).

### 2. `src/output/tokens/builder.py`

`_wintersport()` erhält eine Threshold-Prüfung pro Symbol:

```python
for sym, val in pairs:
    if not _visible(by_sym.get(sym), rt) or val is None:
        continue
    spec = by_sym.get(sym)
    if spec and spec.threshold is not None:
        if sym == "SL":
            if val > spec.threshold:   # inverse: hohe Schneefallgrenze = irrelevant
                continue
        else:
            if val < spec.threshold:   # normal: SD < Schwelle = irrelevant
                continue
    out.append(Token(sym, render_int(val), "wintersport", PRIORITY[sym]))
```

Nur SD und NS24+ werden mit dem normalen `val < threshold` gefiltert. SL verwendet
die inverse Logik. AV und WC bleiben unverändert (kein threshold-Feld).

### 3. `frontend/.../WeatherMetricsTab.svelte`

a) `SMS_THRESHOLD_METRIC_IDS` ergänzen:
```js
const SMS_THRESHOLD_METRIC_IDS = ['precipitation', 'rain_probability', 'wind', 'gust', 'thunder', 'snow_depth', 'snowfall_limit'];
```

b) Im Threshold-Block nach dem Thunder-Row zwei neue `ThresholdMetricRow`-Einträge:
- Schneehöhe: levels `[{Sensibel, 5}, {Standard, 10}, {Robust, 20}]`
- Schneefallgrenze: levels `[{Sensibel, 2000}, {Standard, 1500}, {Robust, 1000}]`

## Nicht in dieser Spec

- NS24+ bekommt keinen eigenen Frontend-Row (ist kein eigenständiger metric_id im Katalog)
- AV, WC: kein Threshold (Lawinenstufe und Windchill haben anderen Charakter)
- Kein Regress bei bestehenden Threshold-Metriken (R, PR, W, G, TH:)
