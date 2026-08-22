"""
Weather Snapshot Service — persists aggregated weather data for alert comparison.

ALERT-01: Saves SegmentWeatherSummary to JSON after report send,
loads during alert checks so change detection compares real deltas.

SPEC: docs/specs/modules/weather_snapshot.md v1.0
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from app.loader import get_snapshots_dir
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    PrecipType,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Fields that hold Enum values and their types (aggregated summary)
_ENUM_FIELDS: dict[str, type] = {
    "thunder_level_max": ThunderLevel,
    "precip_type_dominant": PrecipType,
}

# Issue #1468: Felder des Tages-Aggregats, die einen ZEITPUNKT tragen. Sie
# gehen als ISO-Zeichenkette in den Anker und kommen als naives `datetime`
# (UTC, Hausnorm) zurueck. Ohne diese Behandlung schluckt `save_alarm_anchor`
# den Serialisierungsfehler still (`weather_snapshot.py:208`) -- der Anker
# waere dann GAR NICHT geschrieben und jeder Folgelauf haette nichts zu
# vergleichen.
_DATETIME_FIELDS: frozenset[str] = frozenset({
    "thunder_onset_utc",
    "precip_heavy_onset_utc",
})

# Fields that hold Enum values in ForecastDataPoint
_HOURLY_ENUM_FIELDS: dict[str, type] = {
    "thunder_level": ThunderLevel,
    "precip_type": PrecipType,
}

# Issue #1987: erkennt den DATIERTEN Snapshot `{trip_id}_{YYYY-MM-DD}.json` —
# und nur ihn. Trennt die Aufraeumung von den Nachbardateien desselben Trips
# (rollierende Alarm-Anker), s. `_prune_dated_snapshots`.
_DATED_SUFFIX = re.compile(r"_\d{4}-\d{2}-\d{2}\.json$")

# Provider string → Provider enum mapping
_PROVIDER_MAP: dict[str, Provider] = {p.value.lower(): p for p in Provider}
_PROVIDER_MAP.update({p.value: p for p in Provider})


class WeatherSnapshotService:
    """Persist and load aggregated weather snapshots as JSON files."""

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id
        self._snapshots_dir = get_snapshots_dir(user_id)

    def save(
        self,
        trip_id: str,
        segments: List[SegmentWeatherData],
        target_date: date,
        *,
        briefing_backed: bool = True,
    ) -> None:
        """Save aggregated weather snapshot to JSON file.

        Issue #1699: `briefing_backed` haelt die HERKUNFT fest — nur ein
        Snapshot aus einem regulaeren Briefing taugt als Abweichungs-
        Vergleichsbasis (ADR-0009). Default `True`, damit die bestehenden
        Aufrufer (Briefing-Lauf, Compare-Presets) unveraendert bleiben;
        `False` setzt ausschliesslich der reine Abfrage-Pfad
        (`trip_command_processor._fetch_and_save_snapshot`).
        """
        try:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)

            snapshot = {
                "trip_id": trip_id,
                "target_date": target_date.isoformat(),
                "snapshot_at": datetime.now(timezone.utc).isoformat(),
                "provider": segments[0].provider if segments else "unknown",
                "briefing_backed": briefing_backed,
                "segments": [
                    _serialize_segment(seg)
                    for seg in segments
                ],
            }

            filepath = self._snapshots_dir / f"{trip_id}.json"
            filepath.write_text(json.dumps(snapshot, indent=2))
            logger.info(f"Snapshot saved: {trip_id}")
        except Exception as e:
            logger.warning(f"Failed to save snapshot {trip_id}: {e}")

    def save_dated(
        self,
        trip_id: str,
        target_date: date,
        segments: List[SegmentWeatherData],
    ) -> None:
        """Save dated forecast snapshot to {trip_id}_{YYYY-MM-DD}.json."""
        try:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)

            snapshot = {
                "trip_id": trip_id,
                "target_date": target_date.isoformat(),
                "snapshot_at": datetime.now(timezone.utc).isoformat(),
                "provider": segments[0].provider if segments else "unknown",
                "segments": [
                    _serialize_segment(seg)
                    for seg in segments
                ],
            }

            filepath = self._snapshots_dir / f"{trip_id}_{target_date.isoformat()}.json"
            filepath.write_text(json.dumps(snapshot, indent=2))
            logger.info(f"Dated snapshot saved: {filepath.name}")
        except Exception as e:
            logger.warning(f"Failed to save dated snapshot {trip_id} {target_date}: {e}")
            return

        self._prune_dated_snapshots(trip_id)

    def load_dated(
        self,
        trip_id: str,
        target_date: date,
        *,
        segment_fetched_at: bool = False,
    ) -> Optional[List[SegmentWeatherData]]:
        """Load dated forecast snapshot from {trip_id}_{YYYY-MM-DD}.json.

        `segment_fetched_at=True` liefert je Segment seinen EIGENEN
        Erhebungszeitpunkt statt des Schreibzeitpunkts der Datei (Issue #2050
        S6, E-1). Bewusst opt-in und per Vorgabe AUS: derselbe Wert speist
        ueber `trip_alert._check_deviation_alerts()` den nutzersichtbaren
        Referenz-Zeitpunkt im Alarm-Footer (#1916), und `format_reference_at()`
        verzweigt am KALENDERTAG — eine Verschiebung um Minuten ueber
        Mitternacht machte aus "07:00" ein "gestern 23:55 Uhr". Diese Scheibe
        ist rein additiv und darf keine Anzeige verschieben; die
        Protokoll-Ableitung fragt den genaueren Wert deshalb ausdruecklich an."""
        filepath = self._snapshots_dir / f"{trip_id}_{target_date.isoformat()}.json"

        if not filepath.exists():
            logger.debug(f"No dated snapshot for {trip_id} {target_date}")
            return None

        try:
            data = json.loads(filepath.read_text())
            snapshot_at = datetime.fromisoformat(data["snapshot_at"])
            provider = data.get("provider", "unknown")

            result: List[SegmentWeatherData] = []
            for seg_data in data["segments"]:
                segment = _reconstruct_segment(seg_data)
                aggregated = _deserialize_summary(seg_data["aggregated"])
                timeseries = _deserialize_timeseries(seg_data, provider)
                result.append(
                    SegmentWeatherData(
                        segment=segment,
                        timeseries=timeseries,
                        aggregated=aggregated,
                        fetched_at=(
                            _segment_fetched_at(seg_data, snapshot_at)
                            if segment_fetched_at else snapshot_at
                        ),
                        provider=provider,
                    )
                )
            return result
        except (json.JSONDecodeError, ValueError, KeyError, OSError) as e:
            logger.warning(f"Corrupt dated snapshot {trip_id} {target_date}: {e}")
            return None

    def _prune_dated_snapshots(self, trip_id: str) -> None:
        """Delete oldest dated snapshots for trip_id, keeping max 7.

        Issue #1987: Das Glob-Muster `{trip_id}_*.json` erfasst NICHT nur die
        datierten Snapshots, sondern jede Nachbardatei desselben Trips — also
        auch die rollierenden Alarm-Anker. Gemessen: von vier kanalscharfen
        Ankern (`{trip_id}_alarm_anchor_{channel}.json`) ueberlebten nach acht
        Briefing-Laeufen genau EINER; die uebrigen drei fuellten das
        7er-Kontingent und wurden als "aelteste" geloescht. Getroffen haette
        es bevorzugt die Kanaele, die laenger nichts zugestellt bekommen haben
        (aeltester mtime) — exakt jene, deren eigenen Stand dieses Ticket
        erhalten soll. Deshalb greift die Aufraeumung jetzt ausschliesslich
        auf Dateien mit echtem Datums-Suffix.
        """
        dated_files = sorted(
            (
                p for p in self._snapshots_dir.glob(f"{trip_id}_*.json")
                if _DATED_SUFFIX.search(p.name)
            ),
            key=lambda p: (p.stat().st_mtime, p.name),
        )
        for old_file in dated_files[:-7]:
            try:
                old_file.unlink()
                logger.debug(f"Pruned dated snapshot: {old_file.name}")
            except OSError as e:
                logger.warning(f"Failed to prune dated snapshot {old_file}: {e}")

    def _alarm_anchor_path(self, trip_id: str, channel: str) -> Path:
        """Ablageort des rollierenden Alarm-Ankers dieses Kanals (Issue #1987).

        Faellt auf die KANALLOSE Altdatei `{trip_id}_alarm_anchor.json`
        zurueck, solange der Kanal noch keine eigene besitzt (AC-5): der
        Bestand vor dieser Scheibe bleibt damit ohne Migrationsskript als
        Vergleichsbasis lesbar. Die Ableitung sitzt bewusst hier statt in den
        drei Methoden — sonst faelle der Rueckfall in einer von ihnen
        irgendwann auseinander.
        """
        kanalscharf = self._snapshots_dir / f"{trip_id}_alarm_anchor_{channel}.json"
        if kanalscharf.exists():
            return kanalscharf
        return self._snapshots_dir / f"{trip_id}_alarm_anchor.json"

    def save_alarm_anchor(
        self,
        trip_id: str,
        target_date: date,
        segments: List[SegmentWeatherData],
        channel: str,
    ) -> None:
        """Rollierender Alarm-Anker (Issue #1916, ADR-0056) — EIGENER,
        undatierter Speicherort (EIN File je Trip UND Kanal, ueberschrieben
        statt aufgehaeuft), getrennt von `save_dated()`/`load_dated()`: ein
        rollierender Schreibvorgang darf die eingefrorene Briefing-Referenz
        der Radar-Unterdrueckung (#818/#1667) niemals veraendern (AC-11).

        Issue #1987 (S1): `channel` ist PFLICHT und hat bewusst KEINEN
        Vorgabewert — dasselbe Muster wie `tagesgleicher_anker_noetig` aus
        #1661. Ein vergessenes Argument mit stillschweigendem Default
        erzeugte eine Kanal-Verwechslung, die kein Test faengt, solange nur
        EIN Kanal konfiguriert ist. Geschrieben wird ausschliesslich die
        kanalscharfe Datei; die kanallose Altdatei bleibt liegen und
        veraltet (sie dient nur noch als Lese-Rueckfall).
        """
        try:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)

            snapshot = {
                "trip_id": trip_id,
                "target_date": target_date.isoformat(),
                "snapshot_at": datetime.now(timezone.utc).isoformat(),
                "provider": segments[0].provider if segments else "unknown",
                "segments": [
                    _serialize_segment(seg)
                    for seg in segments
                ],
            }

            filepath = self._snapshots_dir / f"{trip_id}_alarm_anchor_{channel}.json"
            filepath.write_text(json.dumps(snapshot, indent=2))
            logger.info(f"Alarm anchor saved: {trip_id} ({channel})")
        except Exception as e:
            logger.warning(f"Failed to save alarm anchor {trip_id} ({channel}): {e}")

    def load_alarm_anchor(
        self, trip_id: str, channel: str,
    ) -> Optional[List[SegmentWeatherData]]:
        """Rollierenden Alarm-Anker DIESES Kanals laden (Issue #1916/#1987)
        — s. `save_alarm_anchor` und `_alarm_anchor_path` (Rueckfall auf die
        kanallose Altdatei, AC-5)."""
        filepath = self._alarm_anchor_path(trip_id, channel)

        if not filepath.exists():
            logger.debug(f"No alarm anchor for {trip_id} ({channel})")
            return None

        try:
            data = json.loads(filepath.read_text())
            snapshot_at = datetime.fromisoformat(data["snapshot_at"])
            provider = data.get("provider", "unknown")

            result: List[SegmentWeatherData] = []
            for seg_data in data["segments"]:
                segment = _reconstruct_segment(seg_data)
                aggregated = _deserialize_summary(seg_data["aggregated"])
                timeseries = _deserialize_timeseries(seg_data, provider)
                result.append(
                    SegmentWeatherData(
                        segment=segment,
                        timeseries=timeseries,
                        aggregated=aggregated,
                        fetched_at=snapshot_at,
                        provider=provider,
                    )
                )
            return result
        except (json.JSONDecodeError, ValueError, KeyError, OSError) as e:
            logger.warning(f"Corrupt alarm anchor {trip_id} ({channel}): {e}")
            return None

    def alarm_anchor_target_date(self, trip_id: str, channel: str) -> Optional[date]:
        """Gespeicherten Tagesbezug des rollierenden Alarm-Ankers DIESES
        Kanals lesen (Issue #1916, AC-10; Issue #1987) — analog
        `load_target_date()` fuer den undatierten Rueckfall. Liest dieselbe
        Datei wie `load_alarm_anchor()` (inkl. Altdatei-Rueckfall), sonst
        koennte die Tagesgrenze einen anderen Anker pruefen als den, der
        tatsaechlich verwendet wird."""
        filepath = self._alarm_anchor_path(trip_id, channel)
        try:
            data = json.loads(filepath.read_text())
            return date.fromisoformat(str(data["target_date"]))
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, OSError) as e:
            logger.debug(
                f"No readable target_date in alarm anchor {trip_id} ({channel}): {e}"
            )
            return None

    def load_target_date(self, trip_id: str) -> Optional[date]:
        """Den beschriebenen Tag des UNDATIERTEN Snapshots lesen (Issue #1661).

        Liest ausschliesslich das `target_date`-Feld aus `{trip_id}.json` —
        derselben Datei, die `load()` liest — und rekonstruiert bewusst KEINE
        Segmente: der Alarm-Pfad braucht hier nur die Tagesfrage.

        Bewusst eine EIGENE Methode statt eines geaenderten Rueckgabewerts von
        `load()` (Spec A1): `load()` hat drei Aufrufer, zwei davon
        (`weather_extractor.py:84,127`) sind reine Anzeigepfade der
        `/heute`-/`/morgen`-Kommandos, die bewusst "was auch immer da ist"
        zeigen sollen. Ein geaenderter Rueckgabetyp haette deren Semantik still
        mitveraendert.

        Returns:
            Den geparsten Tag — oder `None`, wenn die Datei fehlt, das JSON
            korrupt ist, das Feld fehlt oder der Wert unlesbar ist (dasselbe
            fail-soft-Muster wie `load()`/`load_dated()`). Was ein fehlender
            Tag bedeutet, entscheidet der Aufrufer; dort greift das Altersnetz.
        """
        filepath = self._snapshots_dir / f"{trip_id}.json"
        try:
            data = json.loads(filepath.read_text())
            return date.fromisoformat(str(data["target_date"]))
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, OSError) as e:
            logger.debug(f"No readable target_date in snapshot {trip_id}: {e}")
            return None

    def load_briefing_backed(self, trip_id: str) -> bool:
        """Herkunft des UNDATIERTEN Snapshots lesen (Issue #1699).

        Bauart wie `load_target_date()`: liest ausschliesslich das eine Feld
        aus `{trip_id}.json`, rekonstruiert bewusst keine Segmente.

        Returns:
            `False` NUR, wenn in der Datei ausdruecklich `briefing_backed:
            false` steht. Jeder andere Fall — fehlendes Feld (Altbestand vor
            #1699), fehlende Datei, korruptes JSON — ergibt `True`, nie
            `None`/`False`. Das ist der bewusste Unterschied zu
            `load_target_date()`: die strenge Auslegung ("unbekannt =
            verwerfen") wuerde beim ersten Alarmlauf nach dem Deploy JEDEN
            legitim geschriebenen Altanker verwerfen und flaechendeckend
            Alarme unterdruecken — schwerer als der behobene Schaden
            (freigegebene PO-Auslegung, Spec AC-5).
        """
        filepath = self._snapshots_dir / f"{trip_id}.json"
        try:
            data = json.loads(filepath.read_text())
            return data.get("briefing_backed", True) is not False
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError, OSError) as e:
            logger.debug(f"No readable briefing_backed in snapshot {trip_id}: {e}")
            return True

    def load(self, trip_id: str) -> Optional[List[SegmentWeatherData]]:
        """Load aggregated weather snapshot from JSON file."""
        filepath = self._snapshots_dir / f"{trip_id}.json"

        if not filepath.exists():
            logger.debug(f"No snapshot for {trip_id}")
            return None

        try:
            data = json.loads(filepath.read_text())
            snapshot_at = datetime.fromisoformat(data["snapshot_at"])
            provider = data.get("provider", "unknown")

            result: List[SegmentWeatherData] = []
            for seg_data in data["segments"]:
                segment = _reconstruct_segment(seg_data)
                aggregated = _deserialize_summary(seg_data["aggregated"])
                timeseries = _deserialize_timeseries(seg_data, provider)
                result.append(
                    SegmentWeatherData(
                        segment=segment,
                        timeseries=timeseries,
                        aggregated=aggregated,
                        fetched_at=snapshot_at,
                        provider=provider,
                    )
                )
            return result
        except (json.JSONDecodeError, ValueError, KeyError, OSError) as e:
            logger.warning(f"Corrupt snapshot {trip_id}: {e}")
            return None


def _serialize_summary(summary: SegmentWeatherSummary) -> dict:
    """Serialize SegmentWeatherSummary to dict, omitting None values."""
    result = {}
    for field_name, value in vars(summary).items():
        if value is None:
            continue
        if field_name == "aggregation_config":
            if value:
                result[field_name] = value
            continue
        if isinstance(value, Enum):
            result[field_name] = value.name
        elif isinstance(value, datetime):
            result[field_name] = value.isoformat()
        else:
            result[field_name] = value
    return result


def _deserialize_summary(data: dict) -> SegmentWeatherSummary:
    """Deserialize dict to SegmentWeatherSummary, reconstructing Enums.

    Unknown keys (e.g. legacy field names from old snapshots) are silently
    ignored to keep deserialization forward- and backward-compatible.
    """
    import dataclasses
    known_fields = {f.name for f in dataclasses.fields(SegmentWeatherSummary)}
    kwargs = {}
    for key, value in data.items():
        if key not in known_fields:
            continue
        if key in _ENUM_FIELDS and isinstance(value, str):
            kwargs[key] = _ENUM_FIELDS[key](value)
        elif key in _DATETIME_FIELDS and isinstance(value, str):
            try:
                kwargs[key] = datetime.fromisoformat(value)
            except ValueError:
                continue  # unlesbarer Zeitpunkt -> Feld bleibt None
        else:
            kwargs[key] = value
    return SegmentWeatherSummary(**kwargs)


def _segment_fetched_at(seg_data: dict, snapshot_at: datetime) -> datetime:
    """Erhebungszeitpunkt DIESES Segments (Issue #2050 S6, E-1): der
    mitgeschriebene eigene Wert, sonst der Schreibzeitpunkt der Datei --
    Bestandsdateien ohne das additive Feld verhalten sich unveraendert.

    Bewusst NUR ueber `load_dated(segment_fetched_at=True)` erreichbar, also
    allein fuer die Protokoll-Ableitung: dort fragt E-1, auf welchen Abruf
    sich der Briefing-Vergleich beruft. Ueberall sonst -- rollierender
    Alarm-Anker, undatierter Rueckfall, Alarm-Footer (#1916) -- bemisst sich
    der Zeitpunkt weiter am SCHREIBzeitpunkt der Datei (Tagesgrenze #823,
    Ceiling-Fallback #1987)."""
    roh = seg_data.get("fetched_at")
    if not roh:
        return snapshot_at
    try:
        wert = datetime.fromisoformat(roh)
    except (TypeError, ValueError):
        return snapshot_at
    return wert if wert.tzinfo else wert.replace(tzinfo=timezone.utc)


def _serialize_segment(seg: SegmentWeatherData) -> dict:
    """Serialize a single SegmentWeatherData to dict, with optional hourly."""
    entry: dict = {
        "segment_id": seg.segment.segment_id,
        "start_time": seg.segment.start_time.isoformat(),
        "end_time": seg.segment.end_time.isoformat(),
        "start_lat": seg.segment.start_point.lat,
        "start_lon": seg.segment.start_point.lon,
        "start_elevation_m": seg.segment.start_point.elevation_m,
        "start_distance_from_start_km": seg.segment.start_point.distance_from_start_km,
        "end_lat": seg.segment.end_point.lat,
        "end_lon": seg.segment.end_point.lon,
        "end_elevation_m": seg.segment.end_point.elevation_m,
        "end_distance_from_start_km": seg.segment.end_point.distance_from_start_km,
        "distance_km": seg.segment.distance_km,
        # Issue #2036: Herkunft der km-Spanne (gemessen vs. Luftlinie) gehoert
        # MIT in den Anker -- aus einem geladenen Segment entsteht sonst still
        # wieder eine ungemessene Ortsangabe. `False` bleibt weg, damit
        # Bestands-Anker byte-identisch bleiben.
        **({"distance_measured": True} if seg.segment.distance_measured else {}),
        "ascent_m": seg.segment.ascent_m,
        "descent_m": seg.segment.descent_m,
        "duration_hours": seg.segment.duration_hours,
        # Issue #1468 (E2): das Auswertungsfenster gehoert MIT in den Anker.
        # Wird aus einem geladenen Anker-Segment je neu aggregiert, muss
        # dasselbe Fenster gelten wie beim Schreiben -- sonst faellt es still
        # auf den Default zurueck und die Vergleichsbasis waere wieder schief.
        # `None` bleibt weg (Absenz heisst "keine Angabe", nicht "0 Uhr").
        **{
            k: v for k, v in (
                ("day_window_start_hour", seg.segment.day_window_start_hour),
                ("day_window_end_hour", seg.segment.day_window_end_hour),
            ) if v is not None
        },
        "aggregated": _serialize_summary(seg.aggregated),
        # Issue #2050 S6 (E-1): der EIGENE Erhebungszeitpunkt dieses Segments.
        # Bis hierher ging er beim Laden verloren (alle Segmente erbten den
        # Schreibzeitpunkt der Datei) -- damit war der Zeitpunkt, auf den sich
        # ein Briefing-Vergleich beruft, nachtraeglich nicht mehr belegbar.
        # Additiv: fehlt der Schluessel (Bestandsdateien), gilt weiter der
        # Schreibzeitpunkt.
        **(
            {"fetched_at": seg.fetched_at.isoformat()}
            if seg.fetched_at is not None else {}
        ),
    }
    if seg.timeseries is not None:
        hourly = []
        for p in seg.timeseries.data:
            pt: dict = {"ts": p.ts.isoformat()}
            for fname, fval in vars(p).items():
                if fname == "ts" or fval is None:
                    continue
                if isinstance(fval, Enum):
                    pt[fname] = fval.name
                else:
                    pt[fname] = fval
            hourly.append(pt)
        entry["hourly"] = hourly
    return entry


def _deserialize_timeseries(
    seg_data: dict, provider_str: str
) -> Optional[NormalizedTimeseries]:
    """Reconstruct NormalizedTimeseries from segment dict, or None if absent."""
    raw_hourly = seg_data.get("hourly")
    if not raw_hourly:
        return None
    provider_enum = _PROVIDER_MAP.get(provider_str.lower(), Provider.OPENMETEO)
    meta = ForecastMeta(provider=provider_enum, model="snapshot", grid_res_km=0.0)
    points: List[ForecastDataPoint] = []
    for h in raw_hourly:
        kwargs: dict = {}
        for key, val in h.items():
            if key == "ts":
                continue
            if key in _HOURLY_ENUM_FIELDS and isinstance(val, str):
                kwargs[key] = _HOURLY_ENUM_FIELDS[key][val]
            else:
                kwargs[key] = val
        ts_dt = datetime.fromisoformat(h["ts"])
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        points.append(ForecastDataPoint(ts=ts_dt, **kwargs))
    return NormalizedTimeseries(meta=meta, data=points)


def _reconstruct_segment(seg_data: dict) -> TripSegment:
    """Reconstruct minimal TripSegment from snapshot data."""
    start_point = GPXPoint(
        lat=seg_data.get("start_lat", 0.0),
        lon=seg_data.get("start_lon", 0.0),
        elevation_m=seg_data.get("start_elevation_m"),
        distance_from_start_km=seg_data.get("start_distance_from_start_km", 0.0),
    )
    end_point = GPXPoint(
        lat=seg_data.get("end_lat", 0.0),
        lon=seg_data.get("end_lon", 0.0),
        elevation_m=seg_data.get("end_elevation_m"),
        distance_from_start_km=seg_data.get("end_distance_from_start_km", 0.0),
    )
    return TripSegment(
        segment_id=seg_data["segment_id"],
        start_point=start_point,
        end_point=end_point,
        start_time=datetime.fromisoformat(seg_data["start_time"]),
        end_time=datetime.fromisoformat(seg_data["end_time"]),
        duration_hours=seg_data.get("duration_hours", 0.0),
        distance_km=seg_data.get("distance_km", 0.0),
        ascent_m=seg_data.get("ascent_m", 0.0),
        descent_m=seg_data.get("descent_m", 0.0),
        # Issue #1468 (E2): fehlender Schluessel -> None -> Default 4-19.
        # Alt-Anker ohne die Felder laden dadurch unveraendert.
        day_window_start_hour=seg_data.get("day_window_start_hour"),
        day_window_end_hour=seg_data.get("day_window_end_hour"),
        # Issue #2036: fehlender Schluessel -> False (Alt-Anker sind
        # unvermessen und zeigen weiter die Segmentnummer).
        distance_measured=bool(seg_data.get("distance_measured", False)),
    )
