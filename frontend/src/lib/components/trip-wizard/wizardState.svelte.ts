// Zentrale Svelte-5-Runes-State-Klasse fuer den Trip-Wizard.
// Quelle: docs/specs/modules/epic_136_trip_wizard.md §3.1, §1.4
//
// Sub-Steps lesen/schreiben ausschliesslich Felder dieser Klasse —
// kein Step-lokaler Trip-State.

import type {
	AlertRule,
	ActivityType,
	ChannelLayouts,
	DisplayConfig,
	ReportConfig,
	Stage,
	Trip,
	Waypoint,
	WeatherConfigMetric
} from '$lib/types';
import { addDays, mapActivityToProfile, newId } from './wizardHelpers.ts';
import { toHHMMSS } from '$lib/utils/time';

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
	// Issue #224: `thresholds` entfaellt — ersetzt durch WizardState.alertRules
	// (AlertRule[]) als Top-Level-State. Spec: docs/specs/modules/issue_224_wizard_alert_rules_editor.md
}

export const defaultBriefingConfig: BriefingConfig = {
	channels: { email: true, signal: false, telegram: false, sms: false },
	reports: {
		morning: { enabled: true, time: '06:00' },
		evening: { enabled: true, time: '18:00' }
	}
};

export type SaveStatus = 'idle' | 'saving' | 'ok' | 'error';

export class WizardState {
	// Issue #430: Wizard von 4 auf 5 Steps erweitert (neuer Layout-Step 4).
	currentStep = $state<1 | 2 | 3 | 4 | 5>(1);
	activity = $state<ActivityType | null>(null);
	name = $state('');
	shortcode = $state('');
	region    = $state('');
	// `null` bedeutet "nicht gewaehlt"; addDays-Aufrufer muessen vorher null-checken.
	startDate = $state<string | null>(null);
	endDate = $state<string | null>(null);
	stages = $state<Stage[]>([]);
	briefings = $state<BriefingConfig>(cloneBriefingConfig(defaultBriefingConfig));
	// Issue #224: Direkter Top-Level-State fuer Alarmregeln (analog `stages`),
	// gebunden an `<AlertRulesEditor bind:rules={...}>` in Step 4.
	alertRules: AlertRule[] = $state([]);
	// Issue #300: Wetter-Metriken aus Step 3 (Wetter-Konfigurator). Werden beim
	// Save als `display_config.metrics` persistiert (toTripPayload).
	weatherMetrics = $state<WeatherConfigMetric[]>([]);
	// Issue #431: Pro-Kanal-Layouts aus Step 4 (Layout-Editor).
	// null = noch nicht gesetzt (Step 4 nicht besucht) → omitempty in toTripPayload.
	channelLayouts = $state<ChannelLayouts | null>(null);
	// Issue #432 (Scope-Erweiterung, schließt #437): Mehrtages-Trend-Toggle
	// im Abend-Briefing. Default true = heutiges Backend-Verhalten
	// (multi_day_trend_reports = ["evening"] in TripReportConfig).
	trendEnabled = $state<boolean>(true);

	saveStatus = $state<SaveStatus>('idle');
	saveError = $state<string | null>(null);

	derivedAggregationProfile = $derived(
		this.activity ? mapActivityToProfile(this.activity) : null
	);

	// --- Step-Validation ----------------------------------------------------
	//
	// AC-2 Issue #300: Step 1 darf weitergeschaltet werden, sobald die zwei
	// Pflichtfelder (name nicht-leer-getrimmt, startDate nicht-leer) gesetzt
	// sind. `activity` ist KEIN Pflichtfeld mehr — sie wird in Step 3 gewaehlt.
	// Optional: shortcode (faellt nicht in die Bedingung).
	//
	// Implementierungsentscheidung (Abweichung vom literalen Spec-Pseudo-Code,
	// dokumentiert im Master-Spec-Changelog 2026-05-10): Getter statt $derived,
	// damit die Bedingung in Svelte-5 reaktiv bleibt UND in Plain-Node-Tests
	// (Identity-Mocks fuer $state/$derived) bei Mutationen aktuell bleibt —
	// $derived(...) wuerde unter Identity-Mocks nur einmal bei
	// Klassen-Konstruktion evaluieren. Lesen eines Getters von $state-Feldern
	// ist Svelte-5-reaktivitaets-kompatibel.
	get canAdvanceStep1(): boolean {
		// AC-2 Issue #300: activity ist kein Pflichtfeld mehr — name + startDate genügen.
		return (
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
	 * Issue #430: Step 4 (NEU) = Layout-Editor. Kein Gate — User darf jederzeit
	 * weiterschalten, der Default ist die globale Liste aus Step 3.
	 *
	 * Getter (nicht $derived) — siehe canAdvanceStep1 fuer Begruendung.
	 */
	get canAdvanceStep4(): boolean {
		return true;
	}

	/**
	 * Issue #430: Step 5 (heute Reports, war Step 4). Trip ohne Kanaele
	 * speicherbar — kein Gate (Sub-Spec #164 §3.1, User-Entscheidung 2026-05-11).
	 */
	get canAdvanceStep5(): boolean {
		return true;
	}

	/**
	 * Switch ueber currentStep — liefert true wenn der aktuelle Step weitergeschaltet
	 * werden darf. Issue #430: erweitert um case 5 (Reports).
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
			case 5:
				return this.canAdvanceStep5;
		}
	}

	// --- Navigation ---------------------------------------------------------

	nextStep(): void {
		if (this.currentStep < 5) {
			this.currentStep = (this.currentStep + 1) as 1 | 2 | 3 | 4 | 5;
		}
	}

	prevStep(): void {
		if (this.currentStep > 1) {
			this.currentStep = (this.currentStep - 1) as 1 | 2 | 3 | 4 | 5;
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
			const created = await api.post<Trip>('/api/trips', trip);
			this.saveStatus = 'ok';
			const { goto } = await import('$app/navigation');
			// Issue #436: Navigation zur Detail-Page des neu erstellten Trips.
			// Logisch aequivalent zu: created?.id ? `/trips/${created.id}` : '/trips'
			// (als if/else expandiert fuer bessere Lesbarkeit + Stack-Traces).
			if (created?.id) {
				await goto(`/trips/${created.id}`);
			} else {
				await goto('/trips');
			}
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

		const reg = this.region.trim();
		if (reg.length > 0) {
			trip.region = reg;
		}

		if (this.activity) {
			trip.activity = this.activity;
			// Issue #207: Aggregation strukturiert typisiert. Issue #230 hat den
			// Mismatch zwischen Frontend-Read (`activity_profile`) und Wire-Format
			// (`profile`) aufgeloest — Interface verwendet jetzt `profile`.
			trip.aggregation = { profile: mapActivityToProfile(this.activity) };
		}

		// Sub-Spec #164 §3.3: Mapping briefings -> report_config
		// Backward-Compat-Block (alte Felder, Scheduler/Alert lesen diese).
		// Issue #224: `alert_thresholds`-Block entfaellt — AlertRules werden
		// direkt aus `this.alertRules` in `trip.alert_rules` geschrieben.
		// Issue #207: ReportConfig statt Record<string, unknown> — strukturierte
		// Typisierung sorgt dafuer, dass Tippfehler in Feldnamen vom Compiler
		// gefangen werden.
		const b = this.briefings;
		const rc: ReportConfig = {
			// Backward-Compat-Block (TripReportConfig.py Z.589-605):
			// Synthetisch abgeleitet: enabled = morning.enabled || evening.enabled
			// (Phase-2-Entscheidung #4, 2026-05-11).
			enabled: b.reports.morning.enabled || b.reports.evening.enabled,
			morning_time: toHHMMSS(b.reports.morning.time),
			evening_time: toHHMMSS(b.reports.evening.time),
			send_email: b.channels.email,
			send_signal: b.channels.signal,
			send_telegram: b.channels.telegram,
			send_sms: b.channels.sms
		};

		// Issue #432 (Scope-Erweiterung, schließt #437): Mehrtages-Trend-Persistenz.
		// Wert kommt aus dem Wizard-Toggle in der Abend-Card; das bestehende
		// Backend-Feld `multi_day_trend_evening` steuert den Trend-Block im
		// Abend-Briefing-Renderer.
		rc.multi_day_trend_evening = this.trendEnabled;

		trip.report_config = rc;

		// Issue #224: AlertRules werden direkt aus dem Top-Level-State geschrieben
		// (Tiefkopie analog `TripEditView.svelte:26–28`). Kein Mapper, kein
		// `alert_thresholds`-Block mehr — `BriefingConfig.thresholds` ist entfernt.
		if (this.alertRules.length > 0) {
			trip.alert_rules = JSON.parse(JSON.stringify(this.alertRules));
		}

		// Issue #300: Wetter-Metriken aus Step 3 als display_config.metrics
		// persistieren — nur wenn welche gewaehlt wurden (omitempty-Symmetrie).
		if (this.weatherMetrics.length > 0) {
			trip.display_config = { metrics: [...this.weatherMetrics] };
		}

		// Issue #431: channel_layouts (Step 4 Layout) additiv unter display_config
		// schreiben — nur wenn nicht null (omitempty-Symmetrie). Bewahrt das aus
		// `weatherMetrics` ggf. bereits gesetzte `metrics`-Feld.
		if (this.channelLayouts !== null) {
			const dc: DisplayConfig = trip.display_config ?? {};
			dc.channel_layouts = this.channelLayouts;
			trip.display_config = dc;
		}

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
		}
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
