<script lang="ts">
	// Pure presentational Stepper fuer Epic #136 Sub-Spec #160.
	// Issue #430: erweitert von 4 auf 5 Steps + Mobile-Progressbar.
	// Issue #584: Design-Fidelity 1:1 nach screen-trip-wizard.jsx
	//   - done-Dot: "✓" Text + g-paper bg + g-ink-3 border (kein Lucide-Icon)
	//   - active/upcoming: Mono-Font für Zahlen
	//   - Verbindungslinien: flex: 1, volle Breite (JSX: flex: 1, height: 1px)
	// Logik (stepperStateOf, progressBarSegments) liegt in stepperState.ts /
	// stepperCompact.ts — unit-testbar ohne Svelte-Compiler.

	import { stepperStateOf } from './stepperState.ts';
	import { progressBarSegments } from './stepperCompact.ts';

	interface Props {
		current: 1 | 2 | 3 | 4 | 5;
		labels: string[];
		subLabels?: string[];
		// Issue #440: Optional callback fuer Edit-Modus (Tab-Verhalten,
		// alle Steps frei klickbar). Wenn nicht gesetzt, sind die Punkte
		// nicht klickbar (Create-Modus, Default).
		onStepClick?: (step: number) => void;
		// F003 (Issue #440): TestID-Prefix fuer Wiederverwendung im
		// CompareWizard. Default bleibt 'trip-wizard' (Backward-Compat fuer
		// bestehende E2E-Tests + Stepper-Tests).
		testidPrefix?: string;
	}

	let {
		current,
		labels,
		subLabels = [],
		onStepClick,
		testidPrefix = 'trip-wizard'
	}: Props = $props();

	// Issue #430: Segmente fuer Mobile-Progressbar (eine Bar pro Step).
	const segments = $derived(progressBarSegments(current, labels.length));
</script>

<div data-testid={`${testidPrefix}-stepper`}>
	<!-- Mobile Compact Stepper (Viewport <= 899px) — Issue #430 Progressbar -->
	<div
		data-testid={`${testidPrefix}-stepper-compact`}
		class="desktop:hidden"
	>
		<div
			data-testid={`${testidPrefix}-stepper-progress`}
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

	<!-- Desktop Full Stepper (Viewport >= 900px) — Issue #584: 1:1 nach JSX -->
	<div
		data-testid={`${testidPrefix}-stepper-full`}
		class="mobile:hidden"
		style="display: flex; align-items: flex-start; gap: 0; padding: 8px 0;"
	>
		{#each labels as label, i (i)}
			{@const state = stepperStateOf(i, current)}
			{@const dotCfg = state === 'done'
				? { bg: 'var(--g-paper)', border: '1.5px solid var(--g-ink-3)', color: 'var(--g-ink-2)' }
				: state === 'active'
					? { bg: 'var(--g-paper)', border: '2px solid var(--g-accent)', color: 'var(--g-accent)' }
					: { bg: 'var(--g-paper)', border: '1.5px solid var(--g-rule)', color: 'var(--g-ink-4)' }}
			<div
				data-testid={`${testidPrefix}-step-${i + 1}`}
				data-state={state}
				onclick={onStepClick ? () => onStepClick(i + 1) : undefined}
				style="display: flex; flex-direction: column; align-items: center; gap: 6px;
				       cursor: {state !== 'pending' && onStepClick ? 'pointer' : 'default'};
				       flex-shrink: 0; width: 112px; text-align: center;"
			>
				<!-- Dot: done=✓ text, active/upcoming=Mono-Zahl -->
				<div style="width: 40px; height: 40px; border-radius: 50%;
				            display: flex; align-items: center; justify-content: center;
				            background: {dotCfg.bg}; border: {dotCfg.border}; color: {dotCfg.color};
				            font-size: {state === 'done' ? 15 : 14}px; font-weight: 600;
				            font-family: {state === 'done' ? 'var(--g-font-sans)' : 'var(--g-font-mono)'};">
					{state === 'done' ? '✓' : i + 1}
				</div>
				<div style="font-size: 13px; font-weight: 600; margin-top: 2px;
				            color: {state === 'active' ? 'var(--g-ink)' : state === 'done' ? 'var(--g-ink-2)' : 'var(--g-ink-4)'};">
					{label}
				</div>
				{#if subLabels[i]}
					<div class="mono" style="font-size: 10px; letter-spacing: 0.04em;
					            color: {state === 'active' ? 'var(--g-ink-3)' : 'var(--g-ink-4)'};">
						{subLabels[i]}
					</div>
				{/if}
			</div>
			{#if i < labels.length - 1}
				<!-- Connector: flex:1, height:1px — volle Breite (JSX: flex: 1) -->
				<div style="flex: 1; height: 1px; margin-top: 21px;
				            background: {state === 'done' ? 'var(--g-ink-3)' : 'var(--g-rule)'};
				            opacity: {state === 'done' ? 0.5 : 1};
				            min-width: 24px;"></div>
			{/if}
		{/each}
	</div>
</div>
