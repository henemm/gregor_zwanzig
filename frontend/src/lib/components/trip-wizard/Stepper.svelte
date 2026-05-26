<script lang="ts">
	// Pure presentational 4-Step-Stepper fuer Epic #136 Sub-Spec #160.
	// Quelle: docs/specs/modules/epic_136_step0_shell.md §3
	// Mobile-Compact-Block: bug_271_wizard_mobile_stepper.md §2
	// Logik (stepperStateOf) liegt in stepperState.ts — unit-testbar ohne
	// Svelte-Compiler.

	import { Dot } from '$lib/components/ui/dot';
	import { stepperStateOf } from './stepperState.ts';

	interface Props {
		current: 1 | 2 | 3 | 4;
		labels: string[];
		subLabels?: string[];
	}

	let { current, labels, subLabels = [] }: Props = $props();
</script>

<div data-testid="trip-wizard-stepper">
	<!-- Mobile Compact Stepper (Viewport <= 899px) -->
	<div
		data-testid="trip-wizard-stepper-compact"
		class="desktop:hidden flex items-center gap-2 text-sm"
	>
		<span class="font-mono font-semibold text-[var(--g-ink)]">{current} / {labels.length}</span>
		<span class="text-[var(--g-ink-muted)]">·</span>
		<span class="text-[var(--g-ink)]">{labels[current - 1]}</span>
	</div>

	<!-- Desktop Full Stepper (Viewport >= 900px) -->
	<div
		data-testid="trip-wizard-stepper-full"
		class="mobile:hidden flex items-start gap-2"
	>
		{#each labels as label, i (i)}
			{@const state = stepperStateOf(i, current)}
			<div
				data-testid={`trip-wizard-step-${i + 1}`}
				data-state={state}
				class="flex flex-col items-center text-center min-w-0 flex-1"
			>
				{#if state === 'done'}
					<span
						class="w-8 h-8 rounded-full bg-[var(--g-success)]/15 flex items-center justify-center"
					>
						<Dot tone="success" size="md" />
					</span>
				{:else if state === 'active'}
					<span
						class="w-8 h-8 rounded-full border-2 border-[var(--g-accent)] bg-[var(--g-accent)]/10 flex items-center justify-center text-[var(--g-accent-deep)] font-medium"
					>
						{i + 1}
					</span>
				{:else}
					<span
						class="w-8 h-8 rounded-full border border-[var(--g-ink-faint)] flex items-center justify-center text-[var(--g-ink-muted)]"
					>
						{i + 1}
					</span>
				{/if}
				<span class="text-sm mt-1 leading-tight">{label}</span>
				{#if subLabels[i]}
					<span class="text-xs text-[var(--g-ink-muted)] leading-tight">{subLabels[i]}</span>
				{/if}
			</div>
			{#if i < labels.length - 1}
				<div
					class={state === 'done'
						? 'flex-none mt-4 w-6 h-0.5 bg-[var(--g-accent)]'
						: 'flex-none mt-4 w-6 h-0.5 bg-[var(--g-ink-faint)]/30'}
				></div>
			{/if}
		{/each}
	</div>
</div>
