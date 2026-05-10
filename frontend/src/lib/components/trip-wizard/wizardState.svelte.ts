// Zentrale Svelte-5-Runes-State-Klasse fuer den Trip-Wizard.
// Quelle: docs/specs/modules/epic_136_trip_wizard.md §3.1, §1.4
//
// Sub-Steps lesen/schreiben ausschliesslich Felder dieser Klasse —
// kein Step-lokaler Trip-State.

import type { ActivityType, Stage, Trip, Waypoint } from '$lib/types';
import { mapActivityToProfile, newId } from './wizardHelpers.ts';

// `goto` und `api` werden in `save()` lazy importiert, damit Unit-Tests die
// Klasse instanziieren und Felder/Methoden pruefen koennen, ohne dass der
// SvelteKit-Alias `$app/navigation` und der Browser-fetch-basierte
// `$lib/api`-Client beim Modul-Import aufgeloest werden muessen.

export interface BriefingConfig {
	channels: { email: boolean; signal: boolean; telegram: boolean; sms: boolean };
	reports: {
		morning: { enabled: boolean; time: string }; // 'HH:MM' z.B. '06:00'
		evening: { enabled: boolean; time: string }; // 'HH:MM' z.B. '18:00'
	};
	// Master-Spec §3.1: Schwellwerte sind nullable — `null` bedeutet
	// "kein User-Override". Step 4 (Sub-Issue #164) zeigt Placeholder-Werte
	// in der UI; das Backend setzt projekt-eigene Defaults, wenn die Werte
	// nicht persistiert sind.
	thresholds: {
		gust_kmh: number | null;
		precip_mm: number | null;
		thunder_level: 'NONE' | 'MED' | 'HIGH' | null;
		snow_line_m: number | null;
	};
}

export const defaultBriefingConfig: BriefingConfig = {
	channels: { email: true, signal: false, telegram: false, sms: false },
	reports: {
		morning: { enabled: true, time: '06:00' },
		evening: { enabled: true, time: '18:00' }
	},
	thresholds: {
		gust_kmh: null,
		precip_mm: null,
		thunder_level: null,
		snow_line_m: null
	}
};

export type SaveStatus = 'idle' | 'saving' | 'ok' | 'error';

export class WizardState {
	currentStep = $state<1 | 2 | 3 | 4>(1);
	activity = $state<ActivityType | null>(null);
	name = $state('');
	shortcode = $state('');
	// `null` bedeutet "nicht gewaehlt"; addDays-Aufrufer muessen vorher null-checken.
	startDate = $state<string | null>(null);
	endDate = $state<string | null>(null);
	stages = $state<Stage[]>([]);
	briefings = $state<BriefingConfig>(cloneBriefingConfig(defaultBriefingConfig));

	saveStatus = $state<SaveStatus>('idle');
	saveError = $state<string | null>(null);

	derivedAggregationProfile = $derived(
		this.activity ? mapActivityToProfile(this.activity) : null
	);

	// --- Navigation ---------------------------------------------------------

	nextStep(): void {
		if (this.currentStep < 4) {
			this.currentStep = (this.currentStep + 1) as 1 | 2 | 3 | 4;
		}
	}

	prevStep(): void {
		if (this.currentStep > 1) {
			this.currentStep = (this.currentStep - 1) as 1 | 2 | 3 | 4;
		}
	}

	// --- Stages -------------------------------------------------------------

	addStage(stage: Stage): void {
		this.stages = [...this.stages, stage];
	}

	addPauseStage(): void {
		// Pausentag: leeres waypoints-Array, leeres Datum (Step 2 setzt es ggf. nach).
		const pause: Stage = {
			id: newId(),
			name: 'Pause',
			date: '',
			waypoints: []
		};
		this.stages = [...this.stages, pause];
	}

	reorderStages(fromIndex: number, toIndex: number): void {
		if (fromIndex === toIndex) return;
		if (fromIndex < 0 || fromIndex >= this.stages.length) return;
		if (toIndex < 0 || toIndex >= this.stages.length) return;
		const next = this.stages.slice();
		const [moved] = next.splice(fromIndex, 1);
		next.splice(toIndex, 0, moved);
		this.stages = next;
	}

	// --- Save-Pipeline (§1.4) ----------------------------------------------

	async save(): Promise<void> {
		this.saveStatus = 'saving';
		this.saveError = null;
		const trip = this.toTripPayload();
		try {
			const { api } = await import('$lib/api');
			await api.post<Trip>('/api/trips', trip);
			this.saveStatus = 'ok';
			const { goto } = await import('$app/navigation');
			await goto(`/trips/${trip.id}`);
		} catch (e: unknown) {
			this.saveStatus = 'error';
			this.saveError = extractErrorMessage(e);
		}
	}

	/**
	 * Baut einen persistierbaren Trip aus dem aktuellen Wizard-State.
	 * - strippt das transiente `suggested`-Flag aus jedem Wegpunkt
	 * - leitet `aggregation.profile` aus `activity` ab (sofern gesetzt)
	 * - leerer Shortcode wird zu undefined (omitempty-Symmetrie)
	 * - generiert eine neue Trip-ID via newId()
	 */
	toTripPayload(): Trip {
		const cleanedStages: Stage[] = this.stages.map((stage) => ({
			...stage,
			waypoints: stage.waypoints.map((wp) => stripSuggested(wp))
		}));

		const trip: Trip = {
			id: newId(),
			name: this.name,
			stages: cleanedStages
		};

		const sc = this.shortcode.trim();
		if (sc.length > 0) {
			trip.shortcode = sc;
		}

		if (this.activity) {
			trip.activity = this.activity;
			trip.aggregation = { profile: mapActivityToProfile(this.activity) };
		}

		return trip;
	}
}

function stripSuggested(wp: Waypoint): Waypoint {
	const { suggested: _ignored, ...rest } = wp;
	return rest;
}

function cloneBriefingConfig(src: BriefingConfig): BriefingConfig {
	return {
		channels: { ...src.channels },
		reports: {
			morning: { ...src.reports.morning },
			evening: { ...src.reports.evening }
		},
		thresholds: { ...src.thresholds }
	};
}

function extractErrorMessage(e: unknown): string {
	if (e && typeof e === 'object') {
		const obj = e as Record<string, unknown>;
		const detail = obj.detail;
		if (typeof detail === 'string' && detail.length > 0) return detail;
		const error = obj.error;
		if (typeof error === 'string' && error.length > 0) return error;
		const message = obj.message;
		if (typeof message === 'string' && message.length > 0) return message;
	}
	return 'Fehler beim Speichern';
}
