// Issue #1223 — Cockpit-Etappen-Kacheln: Wetter-Risiko-Farben.
// Spec: docs/specs/modules/fix_1223_cockpit_stage_risk_colors.md
//
// Reines TS-Helfermodul: Pill-Mapping + lazy Client-Fetch des
// Stage-Wetter-Endpoints. Wird von TripStageRow.svelte und
// HubOverview.svelte konsumiert.

import type { StagesWeatherResponse } from '../types';

export type StageRisk = 'green' | 'yellow' | 'red' | null;

export interface RiskPill {
	tone: 'good' | 'warn' | 'bad' | 'neutral';
	label: string;
}

// Mapping (PO-bestätigt): red→bad/'Risiko', yellow→warn/'Achten', green→good/'OK',
// null|undefined → neutral/'—' (KEIN Falsch-Grün).
export function riskToPill(risk: StageRisk | undefined): RiskPill {
	if (risk === 'red') return { tone: 'bad', label: 'Risiko' };
	if (risk === 'yellow') return { tone: 'warn', label: 'Achten' };
	if (risk === 'green') return { tone: 'good', label: 'OK' };
	return { tone: 'neutral', label: '—' };
}

// Lazy Client-Fetch des Risiko-Endpoints. Gibt Map stageId→risk zurück.
// Fail-soft: bei !ok oder Exception → leeres Objekt {} (kein Throw).
export async function fetchStageRisk(
	tripId: string,
	fetchFn: typeof fetch = fetch
): Promise<Record<string, StageRisk>> {
	try {
		const res = await fetchFn(`/api/trips/${tripId}/stages/weather`);
		if (!res.ok) return {};
		const data = (await res.json()) as StagesWeatherResponse;
		const map: Record<string, StageRisk> = {};
		for (const stageId of Object.keys(data.results ?? {})) {
			map[stageId] = data.results[stageId]?.risk ?? null;
		}
		return map;
	} catch {
		return {};
	}
}
