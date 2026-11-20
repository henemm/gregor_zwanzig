// naismith.ts — clientseitige Live-Berechnung der Ankunftszeiten je Wegpunkt.
// Issue #296-FE (Grundgerüst), Issue #3196 (Gehzeit nach DAV, Tempo am Trip).
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md
//
// Konstanten + Formel gespiegelt aus internal/model/naismith.go (EINE Quelle:
// FortbewegungRef, DAVHours, ResolveTempo, ComputeStageArrivals, Wrap über
// Mitternacht statt Clamp 23:59 — #1667 S2) und src/core/naismith.py.
// Bewacht durch die gemeinsame Falltabelle tests/fixtures/naismith_dav_paritaet.json,
// damit Editor-Anzeige (vor Save) == persistierter Wert (nach Save) == Pipeline-Zeit.
//
// Distanz: gemeinsame haversineKm aus headerStats.ts (DRY, kein eigener Haversine).

import { haversineKm, stageHasFullTrackDistance } from '../components/email-preview/headerStats.ts';
import type { Fortbewegung, Stage, Tempo } from '../types';

/** Referenzwerte je Fortbewegung: Vorschlags-Grundtempo (km/h) und Raten (Hm/h) bei diesem Tempo. */
export const FORTBEWEGUNG_REF: Record<Fortbewegung, { vorschlagKmh: number; rAuf: number; rAb: number }> = {
	fuss: { vorschlagKmh: 4, rAuf: 300, rAb: 500 },
	rad: { vorschlagKmh: 20, rAuf: 600, rAb: 1000 },
	mtb: { vorschlagKmh: 12, rAuf: 500, rAb: 1000 },
	ski: { vorschlagKmh: 3, rAuf: 300, rAb: 1500 }
};

/** Reihenfolge der Auswahl in der Tempo-Karte. */
export const FORTBEWEGUNGEN: readonly Fortbewegung[] = ['fuss', 'rad', 'mtb', 'ski'];

/** Grenzen eines plausiblen Grundtempos (wie Go Min/MaxGrundtempoKmh; Fix-Loop 2, F001). */
export const MIN_GRUNDTEMPO_KMH = 0.5;
export const MAX_GRUNDTEMPO_KMH = 60;

/** Start-Tempo eines neuen Trips (zu Fuß, Vorschlagswert). */
export const STANDARD_TEMPO: Tempo = { fortbewegung: 'fuss', grundtempo_kmh: 4 };

const DEFAULT_START_TIME = '08:00';
const DAY_MINUTES = 24 * 60; // Wrap-Modul analog naismith.go::formatHHMM (#1667 S2)

/** Grundtempo plus die daraus folgenden Raten (Spiegel Go ActivitySpeeds). */
export interface TempoSpeeds {
	fortbewegung: Fortbewegung;
	grundtempo_kmh: number;
	flatKmh: number;
	ascentMh: number;
	descentMh: number;
}

/** Gültig: bekannte Fortbewegung und 0.5 <= Grundtempo <= 60 km/h (wie Go ValidTempo). */
export function istGueltigesTempo(t: Tempo | null | undefined): t is Tempo {
	if (!t || !(t.fortbewegung in FORTBEWEGUNG_REF)) return false;
	const v = t.grundtempo_kmh;
	return typeof v === 'number' && Number.isFinite(v) && v >= MIN_GRUNDTEMPO_KMH && v <= MAX_GRUNDTEMPO_KMH;
}

/**
 * Leitet das Tempo aus dem Altfeld `activity` ab (Lazy-Migration, Spiegel Go DeriveTempo):
 * fahrrad_15/20/25 → Rad 15/20/25 km/h, alles andere → zu Fuß 4 km/h. Nie MTB oder Ski.
 */
export function deriveTempo(activity?: string | null): Tempo {
	switch (activity) {
		case 'fahrrad_15': return { fortbewegung: 'rad', grundtempo_kmh: 15 };
		case 'fahrrad_20': return { fortbewegung: 'rad', grundtempo_kmh: 20 };
		case 'fahrrad_25': return { fortbewegung: 'rad', grundtempo_kmh: 25 };
		default: return { ...STANDARD_TEMPO };
	}
}

/** Tempo eines Trips: gespeichertes `tempo` vor Ableitung aus `activity`. Ein gespeichertes, aber
 *  ungültiges Tempo zeigt den Wert, mit dem alle Rechner rechnen (zu Fuß 4 km/h, wie tempoSpeeds,
 *  Go TempoSpeeds, Python speeds_for_tempo) — Anzeige = Rechnung (#3196 F-A3-5). */
export function tempoVonTrip(trip: { tempo?: Tempo | null; activity?: string | null } | null | undefined): Tempo {
	if (trip?.tempo) return istGueltigesTempo(trip.tempo) ? trip.tempo : { ...STANDARD_TEMPO };
	return deriveTempo(trip?.activity);
}

/** Raten zu einem Tempo: R = R_ref · v / v_ref. Ungültig → zu Fuß 4 km/h. */
export function tempoSpeeds(tempo: Tempo | null | undefined): TempoSpeeds {
	const t = istGueltigesTempo(tempo) ? tempo : STANDARD_TEMPO;
	const ref = FORTBEWEGUNG_REF[t.fortbewegung];
	const f = t.grundtempo_kmh / ref.vorschlagKmh;
	return {
		fortbewegung: t.fortbewegung,
		grundtempo_kmh: t.grundtempo_kmh,
		flatKmh: t.grundtempo_kmh,
		ascentMh: ref.rAuf * f,
		descentMh: ref.rAb * f
	};
}

/** Einzige Auflösungsstelle des Trip-Tempos (Spiegel Go ResolveTempo, Python tempo_speeds). */
export function tripTempo(trip: { tempo?: Tempo | null; activity?: string | null } | null | undefined): TempoSpeeds {
	return tempoSpeeds(tempoVonTrip(trip));
}

/** Gültiges Etappen-Grundtempo: endliche Zahl in 0.5..60 km/h (Issue #3197, wie Go ValidGrundtempo). */
export function istGueltigesGrundtempo(v: unknown): v is number {
	return typeof v === 'number' && Number.isFinite(v) && v >= MIN_GRUNDTEMPO_KMH && v <= MAX_GRUNDTEMPO_KMH;
}

/** Tempo einer Etappe (Issue #3197, ADR-0108; Spiegel Go ResolveStageTempo, Python stage_speeds):
 *  Fortbewegung immer vom Trip, Grundtempo von der Etappe, falls gültig, sonst vom Trip. */
export function stageTempo(stage: Pick<Stage, 'grundtempo_kmh'> | null | undefined, tripTempo: Tempo): Tempo {
	const v = stage?.grundtempo_kmh;
	if (!istGueltigesGrundtempo(v)) return { ...tripTempo };
	return { fortbewegung: tripTempo.fortbewegung, grundtempo_kmh: v };
}

/** Wechsel der Fortbewegung (AC-6): entfernt `grundtempo_kmh` aus jeder Etappe (Eingabe bleibt
 *  unberührt) und zählt, wie viele Etappen das Feld trugen. */
export function verwirfEtappenTempo(stages: Stage[]): { stages: Stage[]; anzahl: number } {
	let anzahl = 0;
	const neu = stages.map((s) => {
		if (!('grundtempo_kmh' in s)) return s;
		if (s.grundtempo_kmh !== undefined) anzahl += 1;
		return ohneEtappenTempo(s);
	});
	return { stages: neu, anzahl };
}

/** „Trip-Tempo verwenden" (AC-4): dieselbe Etappe ohne `grundtempo_kmh`. */
export function ohneEtappenTempo(stage: Stage): Stage {
	const { grundtempo_kmh: _weg, ...rest } = stage;
	return rest;
}

/** Wechsel der Fortbewegung setzt das Grundtempo auf den Vorschlagswert (AC-4). */
export function wechsleFortbewegung(_tempo: Tempo, neu: Fortbewegung): Tempo {
	return { fortbewegung: neu, grundtempo_kmh: FORTBEWEGUNG_REF[neu].vorschlagKmh };
}

/**
 * Gehzeit nach DAV (DIN 33466), Spiegel Go DAVHours:
 * t_h = km / v, t_v = Hm_auf / R_auf + Hm_ab / R_ab, t = max + min / 2.
 */
export function davHours(
	distKm: number,
	ascentM: number,
	descentM: number,
	sp: Pick<TempoSpeeds, 'flatKmh' | 'ascentMh' | 'descentMh'>
): number {
	const th = distKm / sp.flatKmh;
	const tv = ascentM / sp.ascentMh + descentM / sp.descentMh;
	return Math.max(th, tv) + Math.min(th, tv) / 2;
}

/** Parst "HH:MM" in Minuten ab Mitternacht; unsinnige Zeit → Default. (naismith.go::parseStartMinutes) */
function parseStartMinutes(startTime?: string): number {
	const s = startTime && startTime !== '' ? startTime : DEFAULT_START_TIME;
	const m = /^(\d{1,2}):(\d{1,2})$/.exec(s);
	if (m) {
		const h = Number(m[1]);
		const min = Number(m[2]);
		if (h >= 0 && h <= 23 && min >= 0 && min <= 59) {
			return h * 60 + min;
		}
	}
	const [dh, dm] = DEFAULT_START_TIME.split(':').map(Number);
	return dh * 60 + dm;
}

/**
 * Formatiert Minuten ab Mitternacht als "HH:MM", Wrap über Mitternacht.
 * (naismith.go::formatHHMM)
 *
 * Issue #1667 S2: bis dahin Klemme auf "23:59". Der Grund für die
 * Bereichsgrenze gilt unverändert — die Python-Gegenseite (_parse_hhmm) kann
 * einen Stunden-Teil >23 nicht konsumieren und fällt sonst still auf die
 * divergente Interpolation zurück. Der Wrap ERFÜLLT das (Ausgabe weiterhin nur
 * 00:00–23:59), statt es zu umgehen; die Klemme ließ dagegen mehrere Wegpunkte
 * auf denselben Wert "23:59" fallen und zerstörte damit das Signal, an dem der
 * Tageswechsel erkannt wird.
 *
 * Kein negativsicherer Modulo (((x % m) + m) % m) nötig: totalMin ist
 * konstruktiv >= 0 (Startzeit >= 0 plus kumulierte, nie negative
 * Gehzeit-Minuten). Bitte nicht "sicherheitshalber" umbauen.
 *
 * `export` seit #1667 S2 für den Cross-Language-Paritätstest
 * (naismith_wrap_parity.test.ts), der die drei Kopien gegeneinander prüft.
 */
export function formatHHMM(totalMin: number): string {
	const wrapped = totalMin % DAY_MINUTES;
	const h = Math.floor(wrapped / 60);
	const m = wrapped % 60;
	return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/**
 * Kumulative Ankunftszeiten pro Wegpunkt einer Stage als "HH:MM".
 * startTime "HH:MM" (default "08:00"). Distanz via haversineKm (headerStats).
 * Pausentag (0 Wegpunkte) → []. Erster Wegpunkt = startTime.
 * tempo: Tempo des Trips (tempoVonTrip), default zu Fuß 4 km/h.
 * Gehzeit je Wegpunkt-Paar nach DAV. Spiegelt naismith.go::ComputeStageArrivals.
 */
export function computeArrivalTimes(stage: Stage, startTime?: string, tempo?: Tempo): string[] {
	const wps = stage.waypoints;
	if (!wps || wps.length === 0) return [];

	const sp = tempoSpeeds(tempo ?? STANDARD_TEMPO);
	// #2110: Track-Distanz nur bei vollstaendig vermessener Stage, sonst Haversine.
	const useTrack = stageHasFullTrackDistance(wps);
	let cur = parseStartMinutes(startTime);
	const arrivals: string[] = [formatHHMM(Math.round(cur))];

	for (let i = 1; i < wps.length; i++) {
		const prev = wps[i - 1];
		const wp = wps[i];
		const dist = useTrack
			? (wp.distance_from_start_km as number) - (prev.distance_from_start_km as number)
			: haversineKm(prev, wp);
		const dElev = wp.elevation_m - prev.elevation_m;
		const ascent = Math.max(0, dElev);
		const descent = Math.max(0, -dElev);
		cur += davHours(dist, ascent, descent, sp) * 60.0;
		arrivals.push(formatHHMM(Math.round(cur)));
	}

	return arrivals;
}
