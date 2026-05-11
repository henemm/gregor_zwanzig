// Zentrale Svelte-5-Runes-State-Klasse fuer den Trip-Wizard.
// Quelle: docs/specs/modules/epic_136_trip_wizard.md §3.1, §1.4
//
// Sub-Steps lesen/schreiben ausschliesslich Felder dieser Klasse —
// kein Step-lokaler Trip-State.

import type { ActivityType, Stage, Trip, Waypoint } from '$lib/types';
import { addDays, mapActivityToProfile, newId } from './wizardHelpers.ts';

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

	// --- Step-Validation ----------------------------------------------------
	//
	// Sub-Spec #161 §6: Step 1 darf erst weitergeschaltet werden, wenn die drei
	// Pflichtfelder (activity, name nicht-leer-getrimmt, startDate nicht-leer)
	// gesetzt sind. Optional: shortcode (faellt nicht in die Bedingung).
	//
	// Implementierungsentscheidung (Abweichung vom literalen Spec-Pseudo-Code,
	// dokumentiert im Master-Spec-Changelog 2026-05-10): Getter statt $derived,
	// damit die Bedingung in Svelte-5 reaktiv bleibt UND in Plain-Node-Tests
	// (Identity-Mocks fuer $state/$derived) bei Mutationen aktuell bleibt —
	// $derived(...) wuerde unter Identity-Mocks nur einmal bei
	// Klassen-Konstruktion evaluieren. Lesen eines Getters von $state-Feldern
	// ist Svelte-5-reaktivitaets-kompatibel.
	get canAdvanceStep1(): boolean {
		return (
			this.activity !== null &&
			this.name.trim().length > 0 &&
			typeof this.startDate === 'string' &&
			this.startDate.length > 0
		);
	}

	/**
	 * Sub-Spec #162 §3: Step 2 darf erst weitergeschaltet werden, wenn mindestens
	 * eine Etappe existiert. Pausentage (waypoints.length === 0) zaehlen NICHT,
	 * weil ein reiner Pause-Trip keinen Sinn ergibt — Acceptance-Criterion verlangt
	 * mindestens eine echte Etappe. Aktuelle Implementierung: stages.length > 0.
	 *
	 * Getter (nicht $derived) — Plain-Node-Test-Kompatibilitaet, siehe canAdvanceStep1.
	 */
	get canAdvanceStep2(): boolean {
		return this.stages.length > 0;
	}

	/**
	 * Sub-Spec #163 §3.4: Step 3 darf immer weitergeschaltet werden — keine
	 * Mindest-Bestaetigung erzwingen (User-Entscheidung 2026-05-10). Begruendung:
	 * `stripSuggested` in `toTripPayload` entfernt das `suggested`-Flag sowieso —
	 * unbestaetigte Waypoints werden beim Save automatisch ohne Flag persistiert,
	 * d.h. faktisch akzeptiert. Explizites Verwerfen ist die einzige Aktion mit
	 * fachlicher Konsequenz.
	 *
	 * Getter (nicht $derived) — siehe canAdvanceStep1 fuer Begruendung.
	 */
	get canAdvanceStep3(): boolean {
		return true;
	}

	/**
	 * Sub-Spec #164 §3.1: Trip ohne Kanaele speicherbar — kein Validierungs-Gate
	 * (User-Entscheidung 2026-05-11). Begruendung: ad-hoc-Trips koennen nachtraeglich
	 * konfiguriert werden. Konsistenz mit canAdvanceStep3-Pattern (#163).
	 *
	 * Getter (nicht $derived) — siehe canAdvanceStep1 fuer Begruendung.
	 */
	get canAdvanceStep4(): boolean {
		return true;
	}

	/**
	 * Switch ueber currentStep — liefert true wenn der aktuelle Step weitergeschaltet
	 * werden darf. Step 4 delegiert auf `canAdvanceStep4` (Sub-Spec #164 §3.2).
	 */
	get canAdvanceCurrent(): boolean {
		switch (this.currentStep) {
			case 1:
				return this.canAdvanceStep1;
			case 2:
				return this.canAdvanceStep2;
			case 3:
				return this.canAdvanceStep3;
			case 4:
				return this.canAdvanceStep4;
		}
	}

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
		// Backend liefert keine id zurueck (POST /api/gpx/parse) — wir vergeben
		// sie hier konsistent. Falls Caller bereits eine id hat, respektieren.
		const stageWithId: Stage = stage.id ? stage : { ...stage, id: newId() };
		// Sub-Spec #163 §3.1: Waypoints aus GPX-Upload als automatische Vorschlaege
		// markieren. Zentralisiert (Variante A, User-Entscheidung 2026-05-10) statt
		// Mount-Hook in Step 3 — funktioniert auch fuer zukuenftige Pfade
		// (z.B. #165 Vorlagen). Explizit gesetzte Werte (true|false) bleiben.
		const withSuggested: Stage = {
			...stageWithId,
			waypoints: stageWithId.waypoints.map((wp) =>
				wp.suggested !== undefined ? wp : { ...wp, suggested: true }
			)
		};
		this.stages = [...this.stages, withSuggested];
	}

	/**
	 * Sub-Spec #163 §3.2: Entfernt das `suggested`-Flag aus einem Wegpunkt.
	 * Der Wegpunkt gilt danach als bestaetigt. Falsche stageId/waypointId:
	 * No-op (kein Crash, State unveraendert).
	 *
	 * Wichtig: Property wird via Destructuring vollstaendig entfernt — NICHT auf
	 * `false` gesetzt — sonst zaehlt `Object.prototype.hasOwnProperty('suggested')`
	 * weiterhin als true (siehe AC#14a).
	 */
	confirmWaypoint(stageId: string, waypointId: string): void {
		this.stages = this.stages.map((stage) => {
			if (stage.id !== stageId) return stage;
			return {
				...stage,
				waypoints: stage.waypoints.map((wp) => {
					if (wp.id !== waypointId) return wp;
					const { suggested: _ignored, ...rest } = wp;
					return rest;
				})
			};
		});
	}

	/**
	 * Sub-Spec #163 §3.3: Entfernt einen Wegpunkt vollstaendig aus
	 * `stage.waypoints`. Falsche stageId/waypointId: No-op.
	 */
	rejectWaypoint(stageId: string, waypointId: string): void {
		this.stages = this.stages.map((stage) => {
			if (stage.id !== stageId) return stage;
			return {
				...stage,
				waypoints: stage.waypoints.filter((wp) => wp.id !== waypointId)
			};
		});
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

	/**
	 * Sub-Spec #162 §7: Pausentag an Position `afterIndex + 1` einfuegen.
	 * `afterIndex = -1` fuegt am Anfang ein. Ruft anschliessend
	 * `recomputeStageDates()` auf, damit Folge-Datierung lueckenlos bleibt.
	 */
	addPauseStageAt(afterIndex: number): void {
		const pause: Stage = {
			id: newId(),
			name: 'Pause',
			date: '',
			waypoints: []
		};
		const insertAt = Math.max(0, Math.min(this.stages.length, afterIndex + 1));
		const next = this.stages.slice();
		next.splice(insertAt, 0, pause);
		this.stages = next;
		this.recomputeStageDates();
	}

	/**
	 * Sub-Spec #162 §5: Etappe per ID entfernen, anschliessend Daten neu rechnen.
	 */
	deleteStage(id: string): void {
		this.stages = this.stages.filter((s) => s.id !== id);
		this.recomputeStageDates();
	}

	reorderStages(fromIndex: number, toIndex: number): void {
		if (fromIndex === toIndex) return;
		if (fromIndex < 0 || fromIndex >= this.stages.length) return;
		if (toIndex < 0 || toIndex >= this.stages.length) return;
		const next = this.stages.slice();
		const [moved] = next.splice(fromIndex, 1);
		next.splice(toIndex, 0, moved);
		this.stages = next;
		this.recomputeStageDates();
	}

	/**
	 * Sub-Spec #162 §8 — Auto-Datierung:
	 * Setzt `stages[i].date = startDate + i Tage` ausser bei `dateOverridden=true`.
	 * No-op wenn `startDate` null/leer ist (Spec verbietet Mutation in dem Fall).
	 *
	 * Erstellt eine neue Stages-Array-Referenz, damit Svelte-5-Reaktivitaet greift.
	 */
	recomputeStageDates(): void {
		if (typeof this.startDate !== 'string' || this.startDate.length === 0) {
			return;
		}
		const start = this.startDate;
		this.stages = this.stages.map((stage, i) => {
			if (stage.dateOverridden === true) {
				return stage;
			}
			return { ...stage, date: addDays(start, i) };
		});
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
		const cleanedStages: Stage[] = this.stages.map((stage) =>
			stripDateOverridden({
				...stage,
				waypoints: stage.waypoints.map((wp) => stripSuggested(wp))
			})
		);

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

		// Sub-Spec #164 §3.3: Mapping briefings -> report_config
		// Zwei Bloecke: Backward-Compat (alte Felder, Scheduler/Alert lesen diese)
		// und neue alert_thresholds (konsumiert ab Epic #139).
		const b = this.briefings;
		const rc: Record<string, unknown> = {
			// Backward-Compat-Block (TripReportConfig.py Z.589-605):
			// Synthetisch abgeleitet: enabled = morning.enabled || evening.enabled
			// (Phase-2-Entscheidung #4, 2026-05-11).
			enabled: b.reports.morning.enabled || b.reports.evening.enabled,
			morning_time: b.reports.morning.time, // 'HH:MM'; Python liest time.fromisoformat
			evening_time: b.reports.evening.time,
			send_email: b.channels.email,
			send_signal: b.channels.signal,
			send_telegram: b.channels.telegram,
			send_sms: b.channels.sms
		};

		// Neuer Block: alert_thresholds (Phase-2-Entscheidung #1, 2026-05-11).
		// Nur schreiben wenn mindestens ein Feld gesetzt ist (nicht alle null).
		const t = b.thresholds;
		if (
			t.gust_kmh !== null ||
			t.precip_mm !== null ||
			t.thunder_level !== null ||
			t.snow_line_m !== null
		) {
			rc.alert_thresholds = {
				gust_kmh: t.gust_kmh,
				precip_mm: t.precip_mm,
				thunder_level: t.thunder_level,
				snow_line_m: t.snow_line_m
			};
		}

		trip.report_config = rc;

		return trip;
	}
}

function stripSuggested(wp: Waypoint): Waypoint {
	const { suggested: _ignored, ...rest } = wp;
	return rest;
}

/**
 * Strippt das transiente `dateOverridden`-Flag aus einer Stage.
 * Wird beim Save (`toTripPayload`) angewendet — analog `stripSuggested` bei Waypoints.
 * Sub-Spec #162 §2.
 */
function stripDateOverridden(stage: Stage): Stage {
	const { dateOverridden: _ignored, ...rest } = stage;
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
