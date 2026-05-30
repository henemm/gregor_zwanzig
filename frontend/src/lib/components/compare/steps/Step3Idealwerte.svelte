<script lang="ts">
	// Issue #441 — Step 3: Idealwerte (Min/Max pro Metrik je Aktivitätsprofil).
	// Spec: docs/specs/modules/issue_441_compare_wizard_step3_idealwerte.md §3
	//
	// Konsumiert CompareWizardState via getContext. Profilauswahl in Step 1
	// bestimmt die angezeigte Metrik-Liste. Defaults aus IDEAL_DEFAULTS werden
	// per $effect beim ersten Rendern gesetzt — nur für Keys die noch nicht
	// belegt sind (Edit-Modus-Schutz, AC-5).
	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import type { CompareWizardState } from '../compareWizardState.svelte';
	import {
		PROFILE_METRICS_WITH_SCALES,
		IDEAL_DEFAULTS,
		type ProfileKey
	} from '../compareMetricDefs';
	import { toCompareProfile } from '$lib/types';

	const state = getContext<CompareWizardState>('compare-wizard-state');

	// Profil-Mapping: ActivityProfile → ProfileKey, Fallback ALLGEMEIN.
	const profileKey = $derived<ProfileKey>(
		state.activityProfile
			? (toCompareProfile(state.activityProfile) as ProfileKey)
			: 'ALLGEMEIN'
	);

	const metrics = $derived(
		PROFILE_METRICS_WITH_SCALES[profileKey] ?? PROFILE_METRICS_WITH_SCALES.ALLGEMEIN
	);

	// Defaults aus IDEAL_DEFAULTS in state.idealRanges schreiben — nur wenn Key
	// noch nicht belegt ist (sonst würden Edit-Modus-Werte überschrieben).
	$effect(() => {
		const defaults = IDEAL_DEFAULTS[profileKey] ?? {};
		let next = state.idealRanges;
		let changed = false;
		for (const [key, range] of Object.entries(defaults)) {
			if (!(key in next)) {
				if (!changed) {
					next = { ...next };
					changed = true;
				}
				next[key] = range;
			}
		}
		if (changed) state.idealRanges = next;
	});

	function setMin(key: string, raw: number) {
		const val = Number.isNaN(raw) ? null : raw;
		const prev = state.idealRanges[key] ?? {};
		state.idealRanges = { ...state.idealRanges, [key]: { ...prev, min: val } };
	}

	function setMax(key: string, raw: number) {
		const val = Number.isNaN(raw) ? null : raw;
		const prev = state.idealRanges[key] ?? {};
		state.idealRanges = { ...state.idealRanges, [key]: { ...prev, max: val } };
	}

	function setEnumMax(key: string, val: string) {
		state.idealRanges = { ...state.idealRanges, [key]: { max: val } };
	}
</script>

<div data-testid="compare-wizard-step-3" class="space-y-4">
	<header class="space-y-1">
		<Eyebrow>IDEALWERTE</Eyebrow>
		<p class="text-sm text-[var(--g-ink-muted)]">
			Pro Aktivitätsprofil werden passende Metriken gezeigt.
		</p>
	</header>

	{#each metrics as metric (metric.key)}
		<div
			data-testid={`compare-step3-metric-${metric.key}`}
			class="grid grid-cols-[10rem_1fr_1fr_auto] gap-3 items-start py-2 border-b border-[var(--g-ink-faint)]/30"
		>
			<span class="text-sm font-mono text-[var(--g-ink)] pt-1">{metric.label}</span>

			{#if metric.kind === 'range'}
				<div class="space-y-1">
					<input
						data-testid={`compare-step3-min-${metric.key}`}
						type="number"
						min={metric.rangeMin}
						max={metric.rangeMax}
						step={metric.step}
						value={state.idealRanges[metric.key]?.min ?? ''}
						oninput={(e) => setMin(metric.key, (e.currentTarget as HTMLInputElement).valueAsNumber)}
						class="w-full border rounded px-2 py-1 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
					/>
					<span
						data-testid={`compare-step3-scale-min-${metric.key}`}
						class="block text-xs font-mono text-[var(--g-ink-muted)]"
					>
						{metric.rangeMin}
					</span>
				</div>
				<div class="space-y-1">
					<input
						data-testid={`compare-step3-max-${metric.key}`}
						type="number"
						min={metric.rangeMin}
						max={metric.rangeMax}
						step={metric.step}
						value={state.idealRanges[metric.key]?.max ?? ''}
						oninput={(e) => setMax(metric.key, (e.currentTarget as HTMLInputElement).valueAsNumber)}
						class="w-full border rounded px-2 py-1 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
					/>
					<span
						data-testid={`compare-step3-scale-max-${metric.key}`}
						class="block text-xs font-mono text-[var(--g-ink-muted)] text-right"
					>
						{metric.rangeMax}
					</span>
				</div>
			{:else if metric.kind === 'enum'}
				<div></div>
				<div class="space-y-1">
					<select
						data-testid={`compare-step3-max-${metric.key}`}
						value={(state.idealRanges[metric.key]?.max as string) ?? ''}
						onchange={(e) =>
							setEnumMax(metric.key, (e.currentTarget as HTMLSelectElement).value)}
						class="w-full border rounded px-2 py-1 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
					>
						{#each metric.enumValues ?? [] as val (val)}
							<option value={val}>{val}</option>
						{/each}
					</select>
				</div>
			{/if}

			<span class="text-xs font-mono text-[var(--g-ink-muted)] pt-2">{metric.unit}</span>
		</div>
	{/each}
</div>
