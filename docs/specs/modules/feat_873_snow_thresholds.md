# Spec: #873 — Schneehöhe/Schneefallgrenze als SMS-Display-Filter

## Ziel

Nutzer können in den Wetter-Metriken → Schwellwerte einstellen, ab welchem Wert der
Schneehöhe-Token (SN) bzw. der Schneefallgrenze-Token (SFL) in SMS/Telegram-Kurzform erscheinen soll.

## Kontext

SN und SFL werden in `_wintersport()` als einfache Tageswerte gerendert — ohne
Threshold-Filterung. Das bestehende Threshold-System (Issue #624) funktioniert nur
für `R`, `PR`, `W`, `G`, `TH:` (via `_mk_metric()`). Diese Spec erweitert es um SN
und SFL mit einer Sonderregel für SFL (inverse Logik).

## Acceptance Criteria

**AC-1:** Given der Nutzer hat für Schneehöhe einen Schwellwert S konfiguriert und der
Tages-Schneehöhenwert ist **unter** S, When SMS/Telegram-Kurzform generiert wird,
Then erscheint **kein SN-Token** in der Ausgabe.

**AC-2:** Given der Nutzer hat für Schneehöhe einen Schwellwert S konfiguriert und der
Tages-Schneehöhenwert ist **≥ S**, When SMS/Telegram-Kurzform generiert wird,
Then erscheint **SN-Token** wie bisher (z.B. `SN15`).

**AC-3:** Given der Nutzer hat für Schneefallgrenze einen Schwellwert S konfiguriert und
die Schneefallgrenze liegt **über** S (höhere Schneefallgrenze = weniger relevant),
When SMS generiert wird, Then erscheint **kein SFL-Token** in der Ausgabe.

**AC-4:** Given der Nutzer hat für Schneefallgrenze einen Schwellwert S konfiguriert und
die Schneefallgrenze liegt **≤ S** (niedrige Schneefallgrenze = relevant),
When SMS generiert wird, Then erscheint **SFL-Token** wie bisher (z.B. `SFL1200`).

**AC-5:** Given **kein** Schwellwert für SN oder SFL konfiguriert ist,
When SMS generiert wird, Then erscheinen SN- und SFL-Tokens unverändert
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
"snow_depth": "SN",
"snowfall_limit": "SFL",
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
        if sym == "SFL":
            if val > spec.threshold:   # inverse: hohe SFL = irrelevant
                continue
        else:
            if val < spec.threshold:   # normal: SN < Schwelle = irrelevant
                continue
    out.append(Token(sym, render_int(val), "wintersport", PRIORITY[sym]))
```

Nur SN und SN24+ werden mit dem normalen `val < threshold` gefiltert. SFL verwendet
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

- SN24+ bekommt keinen eigenen Frontend-Row (ist kein eigenständiger metric_id im Katalog)
- AV, WC: kein Threshold (Lawinenstufe und Windchill haben anderen Charakter)
- Kein Regress bei bestehenden Threshold-Metriken (R, PR, W, G, TH:)
