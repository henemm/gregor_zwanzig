<script lang="ts">
	// Issue #571 — Home Cockpit Hero (Compare-Modus + CompareStatusRow + Stretch-Fix).
	// Spec: docs/specs/modules/issue_571_home_cockpit_hero.md
	//
	// Schlanke horizontale Zeile für aktive Vergleiche in der "Außerdem beobachtet"-Sektion.
	// Als <a>-Element mit Touch-Target ≥ 44px.

	import type { ComparePreset } from '$lib/types.js';
	import { Dot } from '$lib/components/atoms';
	import { deriveNextSend } from '$lib/utils/cockpitHelpers568.js';
	import { formatNextSend } from '$lib/components/compare/subscriptionHelpers.js';

	interface Props {
		preset: ComparePreset;
		dense?: boolean;
	}

	let { preset, dense = false }: Props = $props();

	const now = new Date();
	const nextSend = $derived(deriveNextSend(preset, now));
</script>

<a
	href="/compare/{preset.id}"
	style:display="flex"
	style:align-items="center"
	style:gap="10px"
	style:min-height="44px"
	style:padding="{dense ? '6px 12px' : '8px 16px'}"
	style:background="var(--g-card)"
	style:border="1px solid var(--g-rule-soft)"
	style:border-radius="var(--g-r-2)"
	style:text-decoration="none"
	style:color="var(--g-ink)"
>
	<!-- Aktiv-Dot -->
	<Dot tone="good" />

	<!-- Preset-Name -->
	<span style:font-size="14px" style:font-weight="600" style:flex="1" style:min-width="0" style:white-space="nowrap" style:overflow="hidden" style:text-overflow="ellipsis">
		{preset.name}
	</span>

	<!-- N Orte -->
	<span style:font-size="12px" style:color="var(--g-ink-2)" style:white-space="nowrap">
		{(preset.location_ids ?? []).length} Orte
	</span>

	<!-- Region (falls vorhanden) -->
	{#if (preset.display_config as Record<string,unknown> | undefined)?.region}
		<span style:font-size="12px" style:color="var(--g-ink-2)" style:white-space="nowrap">
			· {(preset.display_config as Record<string,unknown>).region as string}
		</span>
	{/if}

	<!-- Nächster Versand Mono-Text -->
	<span style:font-family="var(--g-font-mono)" style:font-size="11px" style:color="var(--g-ink-3)" style:white-space="nowrap">
		{formatNextSend(nextSend)}
	</span>

	<!-- Kanal-Chips -->
	{#if preset.empfaenger && preset.empfaenger.length > 0}
		{#each preset.empfaenger as emp (emp)}
			<span
				style:font-size="11px"
				style:padding="2px 6px"
				style:background="var(--g-card-alt)"
				style:border="1px solid var(--g-rule-soft)"
				style:border-radius="3px"
				style:white-space="nowrap"
			>{emp}</span>
		{/each}
	{/if}

	<!-- Pfeil -->
	<span style:color="var(--g-ink-3)" style:font-size="14px">→</span>
</a>
