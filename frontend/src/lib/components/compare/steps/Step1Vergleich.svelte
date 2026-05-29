<script lang="ts">
	// Issue #440 — Step 1: Name, Region, Aktivitaetsprofil.
	// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md §6
	import { getContext } from 'svelte';
	import { Field } from '$lib/components/molecules';
	import type { CompareWizardState } from '../compareWizardState.svelte';
	import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types';

	const state = getContext<CompareWizardState>('compare-wizard-state');

	// F005 (Spec §6): Compare-Wizard-spezifische Labels. Trip-Wizard nutzt
	// weiterhin die generischen ACTIVITY_PROFILE_OPTIONS.label-Werte.
	const COMPARE_PROFILE_LABELS: Record<string, string> = {
		wandern: 'Alpine Touring'
	};

	function profileLabel(value: string, fallback: string): string {
		return COMPARE_PROFILE_LABELS[value] ?? fallback;
	}
</script>

<div data-testid="compare-wizard-step-1" class="space-y-6">
	<Field label="Name" hint="Pflichtfeld">
		<input
			data-testid="compare-step1-name"
			type="text"
			class="w-full border rounded px-3 py-2 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
			placeholder="z.B. Skirunde Tirol"
			bind:value={state.name}
		/>
	</Field>

	<Field label="Region" hint="Optional — hilft bei der Orientierung">
		<input
			data-testid="compare-step1-region"
			type="text"
			class="w-full border rounded px-3 py-2 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
			placeholder="z.B. Korsika, Allgäu, Zillertal"
			bind:value={state.region}
		/>
	</Field>

	<div class="space-y-2">
		<p class="text-xs font-mono uppercase tracking-wide text-[var(--g-ink-muted)]">
			Aktivitätsprofil
		</p>
		<!--
			Testids fuer Aktivitaetsprofil-Tiles (Spec §6 / Issue #440):
			  compare-step1-tile-wintersport
			  compare-step1-tile-wandern
			  compare-step1-tile-summer_trekking
			  compare-step1-tile-allgemein
		-->
		<div class="grid grid-cols-2 gap-3">
			{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
				<button
					data-testid={`compare-step1-tile-${opt.value}`}
					type="button"
					onclick={() => {
						state.activityProfile = opt.value;
					}}
					class={`p-4 rounded border text-left transition-colors ${
						state.activityProfile === opt.value
							? 'border-[var(--g-accent)] bg-[var(--g-accent)]/10 text-[var(--g-accent-deep)]'
							: 'border-[var(--g-ink-faint)] hover:border-[var(--g-ink-muted)]'
					}`}
				>
					<span class="text-sm font-medium">{profileLabel(opt.value, opt.label)}</span>
				</button>
			{/each}
		</div>
	</div>
</div>
