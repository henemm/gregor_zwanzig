# Amtliche Warnung: Deutschland an den MeteoAlarm-Feed anbinden (MeteoAlarmFeedSource DE)

[triage:po] — Rang 10 aus dem Gewitter-Gesamtkonzept (#1419, Abschnitt 11), Entscheidung E6. Bisher kein eigenes Ticket; die Roadmap-Tabelle markierte diesen Rang fälschlich als erledigt (richtiggestellt 2026-08-10).

**Tech-Lead-Entscheid 2026-09-09: Dies ist der eine Weg für Deutschland.** #1440 (DWD-CAP direkt) ist zugunsten dieses Tickets geschlossen; Begründung dort.

## Befund

`grep -rn 'MeteoAlarmFeedSource("DE"' src/` (2026-08-10): 0 Treffer. Nur IT und AT sind registriert (`src/services/official_alerts/__init__.py:40-41`).

## Ziel

Der Weg läuft bereits produktiv für IT/AT (#1445 S1/S3) und ist kontingentfrei — Deutschland ist eine Länder-Ergänzung: `register_official_alert_source(MeteoAlarmFeedSource("DE"))`, in korrekter Reihenfolge zu bestehenden Quellen (siehe Kommentar-Reihenfolge in `__init__.py`).

## Offene Punkte (aus Gesamtkonzept 6/E6 und aus #1440 übernommen)

1. **Punkt→Zone-Auflösung für DE.** Anders als AT (ZAMG liefert `gemeindenr` ohnehin) und IT (DPC-Zonen eingecheckt) gibt es für DE keinen vorhandenen Datenbestand. Kandidat: DWD-Warncell-Geometrien (Open Data) → EMMA-ID-Zuordnung, Ray-Cast über `geo_ray_cast.py` (Muster FR-Departements). Vor dem Bau: prüfen, welche Geocode-Kennung der DE-Feed in `area[].geocode` führt (EMMA_ID oder WARNCELLID) — davon hängt die Mapping-Tabelle ab.
2. **Feed-Größe 13,5 MB je Abruf ohne gzip.** `Accept-Encoding: gzip` senden und messen; Cache-TTL wie AT/IT. Kontingent ist keins (Feed-Host), Bandbreite und Parse-Zeit schon.
3. **Drei-Zustände-Regel** wie in S3: „nicht zuständig" ≠ „nicht abrufbar" ≠ „keine Warnung" — Pflicht-Prüfpunkt des Adversary.
4. Äquivalenz-/Realitätstest gegen einen aufgezeichneten DE-Feed (Fixture), Kontrollpunkte z. B. Bayerische Alpen (Grenznähe zu AT/Tirol).

## Bezug

#1419 (Epic, Rang 10/E6), #1445 (Vorbild-Muster IT/AT, erledigt), #1440 (geschlossen, aufgegangen hier), #2258 (Epic Warnungen).

## Kommentare
### 2026-08-19T15:40:15Z
**Einordnung 2026-08-19 (PO-Fokus „Karnischer Höhenweg"): dieses Ticket ist für den KHW NICHT relevant — bewusst kein `session:khw`-Label, Priorität bleibt `medium`.**

Der Karnische Höhenweg verläuft auf der Grenze Österreich/Italien. Beide Anrainerländer sind bei den amtlichen Warnungen bereits mit **je zwei unabhängigen Quellen** verdrahtet (`src/services/official_alerts/__init__.py:36-42`):

| Land | Quellen |
|---|---|
| Österreich | `GeoSphereWarnSource` (`geosphere_warn.py:152-169`) + `MeteoAlarmFeedSource("AT")` (`meteoalarm_feed.py:274-352`) |
| Italien | `DpcSource` (`dpc.py:221-264`, Zonenpolygone) + `MeteoAlarmFeedSource("IT")` (`meteoalarm_feed.py:288-319`) |

Live seit 2026-07-15 (#1086, Commit `8c254038`), Cross-Source-Deduplizierung inklusive.

Dieses Ticket bindet **Deutschland** an — fachlich weiterhin sinnvoll für DE-Trips, aber es schließt keine Lücke auf dem KHW. Wer nach „was hilft dem KHW" sucht: #1581, #1759, #1982 (S8), #1983 (S6).

