// State-Klasse fuer den Compare-Wizard (Orts-Vergleich).
// Issue #440. Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
//
// Factory-Pattern: Instanziierung im +page.svelte mount (Safari-Reaktivitaets-Fix).
// Lazy imports von goto/api damit Unit-Tests die Klasse ohne Browser-APIs testen.

import type { ActivityProfile, ChannelLayouts } from '$lib/types';
import type { IdealRange } from './compareMetricDefs';

export type SaveStatus = 'idle' | 'saving' | 'ok' | 'error';

export class CompareWizardState {
	currentStep = $state<1 | 2 | 3 | 4 | 5>(1);
	name = $state('');
	region = $state(''); // mapped: display_config.region
	activityProfile = $state<ActivityProfile | null>(null);
	pickedIds = $state<string[]>([]);
	isEditMode = $state(false);
	subscriptionId = $state<string | null>(null);
	subscriptionEnabled = $state(true);
	// round-trip Sicherheit fuer bestehende display_config-Felder
	existingDisplayConfig = $state<Record<string, unknown>>({});
	// Issue #441: Idealwerte pro Metrik (Step 3); leer = nicht in display_config.
	idealRanges = $state<Record<string, IdealRange>>({});
	// Issue #442: Pro-Kanal-Layouts. null = Step 4 nicht besucht / nichts konfiguriert.
	channelLayouts = $state<ChannelLayouts | null>(null);
	// Issue #443 — Step 5 Versand-Felder
	sendEmail = $state(true);
	sendSignal = $state(false);
	sendTelegram = $state(false);
	timeWindowStart = $state(9);
	timeWindowEnd = $state(16);
	forecastHours = $state(48);
	schedule = $state<'daily_morning' | 'daily_evening' | 'weekly'>('daily_morning');
	weekday = $state(0);
	includeHourly = $state(false);
	topN = $state(3);
	saveStatus = $state<SaveStatus>('idle');
	saveError = $state<string | null>(null);

	// --- Validation ---------------------------------------------------------

	get canAdvanceStep1(): boolean {
		return this.name.trim().length > 0;
	}

	get canAdvanceStep2(): boolean {
		return this.pickedIds.length >= 2;
	}

	get canAdvanceStep5(): boolean {
		return this.sendEmail || this.sendSignal || this.sendTelegram;
	}

	get canAdvanceCurrent(): boolean {
		switch (this.currentStep) {
			case 1:
				return this.canAdvanceStep1;
			case 2:
				return this.canAdvanceStep2;
			case 5:
				return this.canAdvanceStep5;
			default:
				return true;
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

	/**
	 * Tab-Verhalten im Edit-Modus: alle 5 Steps frei navigierbar.
	 * Im Create-Modus blockiert (sequenzielle Bedienung).
	 */
	goToStep(n: number): void {
		if (!this.isEditMode) return;
		if (n >= 1 && n <= 5) {
			this.currentStep = n as 1 | 2 | 3 | 4 | 5;
		}
	}

	// --- API-Aktionen --------------------------------------------------------

	/**
	 * Edit-Modus Header-Aktion: enabled-Flag sofort flippen.
	 * Sendet PUT /api/subscriptions/{id} mit Voll-Payload (Backend macht Full-Replace).
	 */
	async toggleEnabled(): Promise<void> {
		if (!this.subscriptionId) return;
		const newEnabled = !this.subscriptionEnabled;
		try {
			const { api } = await import('$lib/api');
			await api.put(`/api/subscriptions/${this.subscriptionId}`, {
				enabled: newEnabled,
				name: this.name,
				activity_profile: this.activityProfile ?? undefined,
				locations: this.pickedIds,
				display_config: {
					...this.existingDisplayConfig,
					...(this.region ? { region: this.region } : {}),
					...(Object.keys(this.idealRanges).length > 0
						? { ideal_ranges: this.idealRanges }
						: {}),
					...(this.channelLayouts !== null
						? { channel_layouts: this.channelLayouts }
						: {})
				},
				forecast_hours: this.forecastHours,
				time_window_start: this.timeWindowStart,
				time_window_end: this.timeWindowEnd,
				schedule: this.schedule,
				weekday: this.weekday,
				include_hourly: this.includeHourly,
				top_n: this.topN,
				send_email: this.sendEmail,
				send_signal: this.sendSignal,
				send_telegram: this.sendTelegram
			});
			this.subscriptionEnabled = newEnabled;
		} catch {
			// Fehler still — kein saveError hier (Sofort-Aktion ohne sichtbares Feedback)
		}
	}

	/**
	 * Speichern: Create -> POST, Edit -> PUT. Anschliessend Redirect nach /compare.
	 *
	 * F001: Backend (internal/handler/subscription.go validateSubscription)
	 * verlangt sub.ID != "". Beim Create generieren wir clientseitig eine UUID,
	 * sonst antwortet das Backend mit HTTP 400 "id required".
	 */
	async save(): Promise<void> {
		this.saveStatus = 'saving';
		this.saveError = null;
		const payload: Record<string, unknown> = {
			name: this.name,
			activity_profile: this.activityProfile ?? undefined,
			locations: this.pickedIds,
			display_config: {
				...this.existingDisplayConfig,
				...(this.region ? { region: this.region } : {}),
				...(Object.keys(this.idealRanges).length > 0
					? { ideal_ranges: this.idealRanges }
					: {}),
				...(this.channelLayouts !== null
					? { channel_layouts: this.channelLayouts }
					: {})
			},
			enabled: this.subscriptionEnabled,
			forecast_hours: this.forecastHours,
			time_window_start: this.timeWindowStart,
			time_window_end: this.timeWindowEnd,
			schedule: this.schedule,
			weekday: this.weekday,
			include_hourly: this.includeHourly,
			top_n: this.topN,
			send_email: this.sendEmail,
			send_signal: this.sendSignal,
			send_telegram: this.sendTelegram
		};
		if (!this.isEditMode) {
			payload.id = crypto.randomUUID();
		}
		try {
			const { api } = await import('$lib/api');
			const { goto } = await import('$app/navigation');
			if (this.isEditMode && this.subscriptionId) {
				await api.put(`/api/subscriptions/${this.subscriptionId}`, payload);
			} else {
				await api.post('/api/subscriptions', payload);
			}
			this.saveStatus = 'ok';
			await goto('/compare');
		} catch (e: unknown) {
			this.saveStatus = 'error';
			this.saveError = extractErrorMessage(e);
		}
	}
}

function extractErrorMessage(e: unknown): string {
	if (e && typeof e === 'object') {
		const obj = e as Record<string, unknown>;
		if (typeof obj.detail === 'string' && obj.detail) return obj.detail;
		if (typeof obj.error === 'string' && obj.error) return obj.error;
		if (typeof obj.message === 'string' && obj.message) return obj.message;
	}
	return 'Fehler beim Speichern';
}
