// State-Klasse fuer den Compare-Wizard (Orts-Vergleich).
// Issue #440. Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
//
// Factory-Pattern: Instanziierung im +page.svelte mount (Safari-Reaktivitaets-Fix).
// Lazy imports von goto/api damit Unit-Tests die Klasse ohne Browser-APIs testen.

import type { ActivityProfile } from '$lib/types';

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
	saveStatus = $state<SaveStatus>('idle');
	saveError = $state<string | null>(null);

	// --- Validation ---------------------------------------------------------

	get canAdvanceStep1(): boolean {
		return this.name.trim().length > 0;
	}

	get canAdvanceStep2(): boolean {
		return this.pickedIds.length >= 2;
	}

	get canAdvanceCurrent(): boolean {
		switch (this.currentStep) {
			case 1:
				return this.canAdvanceStep1;
			case 2:
				return this.canAdvanceStep2;
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
					...(this.region ? { region: this.region } : {})
				},
				forecast_hours: 48,
				time_window_start: 9,
				time_window_end: 16,
				schedule: 'daily_morning',
				weekday: 0,
				include_hourly: false,
				top_n: 3,
				send_email: true,
				send_signal: false,
				send_telegram: false
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
				...(this.region ? { region: this.region } : {})
			},
			enabled: this.subscriptionEnabled,
			forecast_hours: 48,
			time_window_start: 9,
			time_window_end: 16,
			schedule: 'daily_morning',
			weekday: 0,
			include_hourly: false,
			top_n: 3,
			send_email: true,
			send_signal: false,
			send_telegram: false
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
