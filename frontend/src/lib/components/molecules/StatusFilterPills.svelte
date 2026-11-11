<script lang="ts">
	// Issue #2278 (AC-2/AC-14) — EINE Filter-Pillen-Leiste fuer Trip- und Vergleichs-Liste.
	import { Pill } from '$lib/components/atoms';
	import { t, type MessageKey } from '$lib/i18n';

	export type StatusFilterValue = 'all' | 'aktiv' | 'geplant' | 'pausiert' | 'fertig';

	interface Props {
		active: StatusFilterValue;
		counts: Record<StatusFilterValue, number>;
		onSelect: (value: StatusFilterValue) => void;
	}

	let { active, counts, onSelect }: Props = $props();

	// #2919: Anzeige aus dem Katalog; Filterwerte bleiben Logikwerte (ADR-0104).
	const PILLEN: Array<{ key: MessageKey; value: StatusFilterValue }> = [
		{ key: 'listen.filter.alle', value: 'all' },
		{ key: 'trip.status.active', value: 'aktiv' },
		{ key: 'trip.status.planned', value: 'geplant' },
		{ key: 'trip.status.paused', value: 'pausiert' },
		{ key: 'trip.status.finished', value: 'fertig' }
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
				{$t(f.key)} ({counts[f.value] ?? 0})
			</Pill>
		</button>
	{/each}
</div>
