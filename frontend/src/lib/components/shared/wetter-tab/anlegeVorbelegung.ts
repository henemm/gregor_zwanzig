// Issue #2794 S3a Teil-PR 4a (AC-43, AC-44, AC-45): Vorbelegung der
// Wertebereiche (`corridors`) beim Anlegen — als reine Funktionen, EIN Modul
// fuer beide Kontexte (#1170, Trip/Vergleich-Teilung).
//
// Bisher lief diese Logik in einem unsichtbar gemounteten CorridorEditor
// (Trip: `vorbelegen()` + `onVorbelegungFertig`; Vergleich:
// `isFreshCompareCreate` -> `syncToWizard`). Die Oberflaeche ist entfernt; das
// Ergebnis ist unveraendert dasselbe, gebaut aus denselben Bausteinen
// (`buildRoutePrefillRows`/`buildCorridorSavePayload` bzw.
// `buildComparePrefillRows`/`buildCompareCorridorSavePayload`).
//
// Orchestrierung: je Anlege-Editor genau EIN `$effect`
// (TripNewEditor: `erstelleTripVorbelegungsLauf`, CompareNewEditor:
// `vergleichVorbelegung`). Kein Datenweg, kein Netz, keine user_id — die
// Funktionen rechnen nur aus dem, was der Editor ihnen gibt.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import { toCompareProfile, type ActivityProfile, type Corridor, type SensLevel, type WeatherConfigMetric } from '../../../types.ts';
import {
	buildRoutePrefillRows,
	buildCorridorSavePayload,
	buildComparePrefillRows,
	buildCompareCorridorSavePayload,
	saveGateDecision,
	type CompareMetricDef,
	type IdealRange,
	type ProfileKey,
	type RouteMetricDef
} from './corridorEditorState.ts';
import { materializeActiveMetricKeys } from '../weather-metrics-tab/compareMetricOrder.ts';

// ── Trip ─────────────────────────────────────────────────────────────────────

export interface TripVorbelegungEingabe {
	/** Vom Reiter Wetter gemeldete Metrik-Auswahl (`display_config.metrics`). */
	metrics: WeatherConfigMetric[] | undefined;
	/** Zusatz-Metriken aus dem Katalog (leer, wenn der Abruf scheiterte). */
	extraDefs: RouteMetricDef[];
	/** Bereits im Editor stehende Wertebereiche — sie werden nie ueberschrieben. */
	vorhandeneCorridors: Corridor[] | undefined;
}

/**
 * Vorbelegung der Trip-Wertebereiche beim Anlegen. `null`, wenn schon
 * Wertebereiche stehen, keine Metrik aktiv ist, keine Zeile einen Startwert hat
 * oder die Zeilen ungueltig waeren; sonst genau die Korridore, die der fruehere
 * CorridorEditor (createMode, route) nach oben gemeldet hat.
 */
export function tripVorbelegung(e: TripVorbelegungEingabe): Corridor[] | null {
	if ((e.vorhandeneCorridors ?? []).length > 0) return null;
	if (!e.metrics || e.metrics.length === 0) return null;
	const rows = buildRoutePrefillRows(e.metrics, e.extraDefs);
	if (rows.length === 0) return null;
	if (saveGateDecision(rows) !== 'schedule') return null;
	// Anlegen: keine gespeicherten Alarmstufen, keine unbekannten Korridore.
	return buildCorridorSavePayload(rows, {}, []).corridors;
}

export interface TripVorbelegungsVersuch {
	/** `null` = Zusatz-Katalog noch nicht geladen. */
	extraDefs: RouteMetricDef[] | null;
	metrics: WeatherConfigMetric[] | undefined;
	vorhandeneCorridors: Corridor[] | undefined;
}

/**
 * Einmaliger Lauf der Trip-Vorbelegung. `versuchen` wartet, solange der
 * Zusatz-Katalog fehlt oder keine Metrik gemeldet ist; danach laeuft er GENAU
 * EINMAL: erst die Korridore melden (falls vorhanden), dann `onFertig` — auch
 * wenn nichts vorzubelegen ist (sonst bliebe „Mit Standardwerten speichern"
 * gesperrt). Jeder weitere Versuch ist wirkungslos.
 */
export function erstelleTripVorbelegungsLauf(cb: {
	onCorridors: (c: Corridor[]) => void;
	onFertig: () => void;
}): { versuchen: (v: TripVorbelegungsVersuch) => void; readonly fertig: boolean } {
	let fertig = false;
	return {
		versuchen(v: TripVorbelegungsVersuch): void {
			if (fertig || v.extraDefs === null) return;
			if (!v.metrics || v.metrics.length === 0) return;
			fertig = true;
			const c = tripVorbelegung({ metrics: v.metrics, extraDefs: v.extraDefs, vorhandeneCorridors: v.vorhandeneCorridors });
			if (c) cb.onCorridors(c);
			cb.onFertig();
		},
		get fertig(): boolean {
			return fertig;
		}
	};
}

// ── Vergleich ────────────────────────────────────────────────────────────────

export interface VergleichVorbelegungQuelle {
	corridors?: Corridor[];
	idealRanges?: Record<string, IdealRange>;
	/** `null` = nie eingestellt (Vorgabemenge), `[]` = bewusst leer (#1366 F002). */
	activeMetricKeys?: string[] | null;
	metricAlertLevels?: Record<string, string>;
	isEditMode?: boolean;
	activityProfile?: ActivityProfile | null;
}

export interface VergleichVorbelegung {
	corridors: Corridor[];
	idealRanges: Record<string, IdealRange>;
	activeMetricKeys: string[];
	metricAlertLevels: Record<string, SensLevel>;
}

/**
 * Vorbelegung der Vergleichs-Wertebereiche beim Anlegen aus dem
 * Aktivitaetsprofil (ohne Profil: ALLGEMEIN). `null` im Bearbeiten-Modus, wenn
 * schon Wertebereiche stehen (Nutzereingaben bleiben) oder das Profil im
 * Katalog nichts vorbelegt. Vorhandene `idealRanges`/`activeMetricKeys`/
 * `metricAlertLevels` werden per Read-Modify-Write uebernommen. Die Eingabe wird
 * nicht veraendert.
 */
export function vergleichVorbelegung(wiz: VergleichVorbelegungQuelle, defs: CompareMetricDef[]): VergleichVorbelegung | null {
	if (wiz.isEditMode) return null;
	if ((wiz.corridors ?? []).length > 0) return null;
	const profileKey = wiz.activityProfile ? (toCompareProfile(wiz.activityProfile) as ProfileKey) : 'ALLGEMEIN';
	const rows = buildComparePrefillRows(profileKey, defs);
	if (rows.length === 0) return null;
	return buildCompareCorridorSavePayload(rows, [], {
		idealRanges: { ...(wiz.idealRanges ?? {}) },
		activeMetricKeys: [...materializeActiveMetricKeys(wiz.activeMetricKeys ?? null)],
		metricAlertLevels: { ...((wiz.metricAlertLevels ?? {}) as Record<string, SensLevel | undefined>) }
	}, []);
}
