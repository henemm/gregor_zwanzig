<script lang="ts">
	// Issue #489 — CompareIdealRow-Molecule (Svelte 5).
	//
	// Idealwert-Konfigurationszeile fuer Compare-Detail-Seite: Metrik-Label
	// links, Idealwert mittig, Gewicht-Pill rechts.
	//
	// Pill-Tone-Mapping:
	//   weight=hoch    -> tone=accent
	//   weight=mittel  -> tone=default
	//   weight=niedrig -> tone=ghost
	//
	// Spec: docs/specs/modules/issue_489_compare_row_molecules.md (AC-2)

	import { Pill } from '$lib/components/atoms';

	interface Props {
		item: { metric: string; range: string; weight: 'hoch' | 'mittel' | 'niedrig' };
		dense?: boolean;
		last?: boolean;
	}

	let { item, dense = false, last = false }: Props = $props();

	const tone = $derived(
		item.weight === 'hoch' ? 'accent' : item.weight === 'mittel' ? 'default' : 'ghost'
	);
</script>

<div
	style:display="flex"
	style:align-items="center"
	style:gap="12px"
	style:padding={dense ? '8px 16px' : '12px 16px'}
	style:border-bottom={last ? 'none' : '1px solid var(--g-rule-soft)'}
>
	<span
		style:font-family="var(--g-font-mono)"
		style:color="var(--g-ink-3)"
		style:font-size="12px"
		style:flex-shrink="0"
	>{item.metric}</span>
	<span
		style:font-family="var(--g-font-mono)"
		style:color="var(--g-ink)"
		style:font-size="13px"
		style:flex="1"
		style:min-width="0"
	>{item.range}</span>
	<Pill {tone}>{item.weight}</Pill>
</div>
