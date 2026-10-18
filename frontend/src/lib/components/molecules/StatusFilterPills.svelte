<script lang="ts">
	// Issue #2278 (AC-2/AC-14) — EINE Filter-Pillen-Leiste fuer Trip- und Vergleichs-Liste.
	import { Pill } from '$lib/components/atoms';

	export type StatusFilterValue = 'all' | 'aktiv' | 'geplant' | 'pausiert' | 'fertig';

	interface Props {
		active: StatusFilterValue;
		counts: Record<StatusFilterValue, number>;
		onSelect: (value: StatusFilterValue) => void;
	}

	let { active, counts, onSelect }: Props = $props();

	const PILLEN: Array<{ label: string; value: StatusFilterValue }> = [
		{ label: 'Alle', value: 'all' },
		{ label: 'Aktiv', value: 'aktiv' },
		{ label: 'Geplant', value: 'geplant' },
		{ label: 'Pausiert', value: 'pausiert' },
		{ label: 'Fertig', value: 'fertig' }
	];
</script>

<div class="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
	{#each PILLEN as f (f.value)}
		<button
			type="button"
			class="shrink-0 cursor-pointer inline-flex items-center min-h-[44px]"
			data-testid="status-filter-pill-{f.value}"
			aria-pressed={active === f.value}
			onclick={() => onSelect(f.value)}
		>
			<Pill tone={active === f.value ? 'accent' : 'default'}>
				{f.label} ({counts[f.value] ?? 0})
			</Pill>
		</button>
	{/each}
</div>
