<script lang="ts">
	// Pure presentational 4-Step-Stepper fuer Epic #136 Sub-Spec #160.
	// Quelle: docs/specs/modules/epic_136_step0_shell.md §3
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

<div data-testid="trip-wizard-stepper" class="flex items-start gap-2">
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
					class="w-8 h-8 rounded-full border-2 border-[var(--g-accent)] bg-[var(--g-accent)]/10 flex items-center justify-center text-[var(--g-accent)] font-medium"
				>
					{i + 1}
				</span>
			{:else}
				<span
					class="w-8 h-8 rounded-full border border-[var(--g-ink-faint)] flex items-center justify-center text-[var(--g-ink-faint)]"
				>
					{i + 1}
				</span>
			{/if}
			<span class="text-sm mt-1 leading-tight">{label}</span>
			{#if subLabels[i]}
				<span class="text-xs text-[var(--g-ink-faint)] leading-tight">{subLabels[i]}</span>
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
