<script lang="ts">
	// Pure presentational Stepper fuer Epic #136 Sub-Spec #160.
	// Issue #430: erweitert von 4 auf 5 Steps + Mobile-Progressbar.
	// Quelle: docs/specs/modules/epic_136_step0_shell.md §3
	// Mobile-Compact-Block: docs/specs/modules/issue_430_431_wizard_layout_step.md §2
	// Logik (stepperStateOf, progressBarSegments) liegt in stepperState.ts /
	// stepperCompact.ts — unit-testbar ohne Svelte-Compiler.

	import CheckIcon from '@lucide/svelte/icons/check';
	import { stepperStateOf } from './stepperState.ts';
	import { progressBarSegments } from './stepperCompact.ts';

	interface Props {
		current: 1 | 2 | 3 | 4 | 5;
		labels: string[];
		subLabels?: string[];
	}

	let { current, labels, subLabels = [] }: Props = $props();

	// Issue #430: Segmente fuer Mobile-Progressbar (eine Bar pro Step).
	const segments = $derived(progressBarSegments(current, labels.length));
</script>

<div data-testid="trip-wizard-stepper">
	<!-- Mobile Compact Stepper (Viewport <= 899px) — Issue #430 Progressbar -->
	<div
		data-testid="trip-wizard-stepper-compact"
		class="desktop:hidden"
	>
		<div
			data-testid="trip-wizard-stepper-progress"
			class="progress-bar flex gap-1 mb-1"
		>
			{#each segments as seg, i (i)}
				<div
					data-testid={`progress-segment-${i + 1}`}
					data-segment-state={seg}
					class={`h-1 flex-1 rounded-full transition-colors ${
						seg === 'done'
							? 'bg-[var(--g-success)]'
							: seg === 'active'
								? 'bg-[var(--g-accent)]'
								: 'bg-[var(--g-ink-faint)]/30'
					}`}
				></div>
			{/each}
		</div>
		<span class="text-xs font-mono text-[var(--g-ink-muted)]">
			SCHRITT {current} VON {labels.length} · {labels[current - 1]}
		</span>
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
						<CheckIcon class="size-4 text-[var(--g-success)]" />
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
