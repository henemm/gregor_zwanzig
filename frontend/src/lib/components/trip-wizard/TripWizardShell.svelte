<script lang="ts">
	// Wizard-Shell fuer Epic #136 Sub-Spec #160.
	// Quelle: docs/specs/modules/epic_136_step0_shell.md §5
	//
	// Verantwortlich fuer:
	//   - Header (h1 + Eyebrow "Schritt N von 4")
	//   - Stepper-Render
	//   - Dynamischer Step-Slot via {#if state.currentStep === N}
	//   - Save-Status-Region (role="status", aria-live="polite")
	//   - Footer mit Btn-Atomen (Zurueck/Abbrechen/Weiter/Speichern)
	//
	// Konsumiert WizardState via getContext('trip-wizard-state').
	// Die Instanziierung erfolgt im +page.svelte Mount-Punkt (Factory-Pattern).

	import { getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import type { WizardState } from './wizardState.svelte';
	import Stepper from './Stepper.svelte';
	import Step1Profile from './steps/Step1Profile.svelte';
	import Step2Stages from './steps/Step2Stages.svelte';
	import Step3Weather from './steps/Step3Weather.svelte';
	import Step4Layout from './steps/Step4Layout.svelte';
	// Issue #432 (PR 4/Epic #428): Step4Reports.svelte wurde nach Step5Reports.svelte
	// umbenannt; bei currentStep === 5 gemountet.
	import Step5Reports from './steps/Step5Reports.svelte';

	const state = getContext<WizardState>('trip-wizard-state');

	// Issue #430: Wizard-spezifische Step-Texte fuer 5 Steps (Layout zwischen Wetter und Reports).
	const stepLabels = ['Route', 'Etappen', 'Wetter', 'Layout', 'Reports'];
	const stepSubLabels = [
		'Name & GPX hochladen',
		'Etappen prüfen',
		'Metriken konfigurieren',
		'Reihenfolge pro Kanal',
		'Briefings einrichten'
	];

	// Issue #391 / #430: sprechende H1-Titel + step-spezifische Footer-Hinweise.
	const stepTitles: Record<number, string> = {
		1: 'Route — wie kennt das System deinen Weg?',
		2: 'Etappen — stimmt die Tagesaufteilung?',
		3: 'Wetter — welche Daten gehen ins Briefing?',
		4: 'Layout — wie sieht das Briefing aus?',
		5: 'Reports — wann und wohin?'
	};

	const stepHints: Record<number, string | null> = {
		1: 'GPX-Upload empfohlen — manuelle Eingabe geht auch.',
		2: null,
		3: null,
		4: null,
		5: 'Unterwegs läuft alles autark. Kein Eingreifen nötig.'
	};

	const saveLabel = $derived(
		state.saveStatus === 'saving'
			? 'Speichern...'
			: state.saveStatus === 'ok'
				? 'Gespeichert'
				: 'Tour speichern'
	);

	// Factory-Handler (CLAUDE.md NiceGUI/Safari-Pattern auf Svelte-Klassen erweitert):
	// expliziter benannter Handler statt anonymer Closure.
	function handleBack() {
		state.prevStep();
	}

	function handleCancel() {
		void goto('/');
	}

	function handleNext() {
		state.nextStep();
	}

	function handleSave() {
		void state.save();
	}
</script>

<div data-testid="trip-wizard-shell" style="display: flex; min-height: 100%; background: var(--g-paper);">
	<main style="flex: 1; position: relative;">
		<TopoBg opacity={0.16} />

		<div style="position: relative; padding: 32px 80px 60px; max-width: 1180px; margin: 0 auto;">
			<header style="margin-bottom: 28px;">
				<Eyebrow style="margin-bottom: 8px;">Schritt {state.currentStep} von 5 · Neue Tour</Eyebrow>
				<div style="font-size: 30px; font-weight: 600; letter-spacing: -0.02em; color: var(--g-ink);">
					{stepTitles[state.currentStep]}
				</div>
			</header>

			<Stepper current={state.currentStep} labels={stepLabels} subLabels={stepSubLabels} />

			<div style="margin-top: 40px;">
				{#if state.currentStep === 1}
					<Step1Profile />
				{:else if state.currentStep === 2}
					<Step2Stages />
				{:else if state.currentStep === 3}
					<Step3Weather />
				{:else if state.currentStep === 4}
					<Step4Layout />
				{:else if state.currentStep === 5}
					<Step5Reports />
				{/if}
			</div>

			{#if state.currentStep === 5}
				<div style="margin-top: 36px; text-align: center; font-size: 13px; color: var(--g-ink-3); font-style: italic;">
					Unterwegs läuft alles autark. Kein Eingreifen nötig.
				</div>
			{/if}

			{#if state.saveStatus !== 'idle'}
				<div
					data-testid="trip-wizard-save-status"
					role="status"
					aria-live="polite"
					class="mt-4 min-h-[1.5rem] text-sm"
				>
					{#if state.saveStatus === 'saving'}
						<span>Speichern...</span>
					{:else if state.saveStatus === 'error'}
						<span class="text-[var(--g-danger)]">{state.saveError}</span>
					{:else if state.saveStatus === 'ok'}
						<span class="text-[var(--g-success)]">Gespeichert</span>
					{/if}
				</div>
			{/if}

			<!-- Footer: 3-Spalten-Grid (JSX: 1fr auto 1fr) -->
			<div
				style="margin-top: 36px; padding-top: 20px; border-top: 1px solid var(--g-rule);
				       display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 12px;"
			>
				<!-- Linke Spalte: Zurück -->
				<div>
					{#if state.currentStep > 1}
						<Btn
							data-testid="trip-wizard-back"
							variant="ghost"
							size="md"
							onclick={handleBack}
						>
							← Zurück
						</Btn>
					{/if}
				</div>
				<!-- Mittlere Spalte: Step-spezifischer Extra-Slot -->
				<div>
					{#if state.currentStep === 2}
						<Btn variant="ghost" size="md">+ Pausentag einfügen</Btn>
					{/if}
				</div>
				<!-- Rechte Spalte: Abbrechen + Weiter/Speichern -->
				<div style="display: flex; justify-content: flex-end; gap: 10px;">
					<Btn
						data-testid="trip-wizard-cancel"
						variant="quiet"
						size="md"
						onclick={handleCancel}
					>
						Abbrechen
					</Btn>
					{#if state.currentStep < 5}
						<Btn
							data-testid="trip-wizard-next"
							variant="accent"
							size="md"
							onclick={handleNext}
							disabled={!state.canAdvanceCurrent}
						>
							Weiter →
						</Btn>
					{:else}
						<Btn
							data-testid="trip-wizard-save"
							variant="accent"
							size="md"
							onclick={handleSave}
							disabled={state.saveStatus === 'saving'}
						>
							{saveLabel}
						</Btn>
					{/if}
				</div>
			</div>
		</div>
	</main>
</div>
