<script lang="ts">
	// Issue #578 — MetricOffShelf-Organism.
	// Kanonische Quelle: organisms.jsx::MetricOffShelf
	//
	// Aufklappbarer "Nicht im Briefing"-Block. Gruppiert nach Metric-Kategorie.

	import { Card, Eyebrow, Btn } from '$lib/components/atoms';

	interface MetricItem {
		id: string;
		label: string;
		unit?: string;
		short?: string;
		category?: string;
		group?: string;
	}

	interface Props {
		items?: string[];
		onAdd?: (id: string, bucket: string) => void;
		compact?: boolean;
		catalog?: MetricItem[];
		defaultOpen?: boolean;
		class?: string;
	}

	let {
		items = [],
		onAdd,
		compact = false,
		catalog = [],
		defaultOpen = false,
		class: className = ''
	}: Props = $props();

	let open = $state(defaultOpen);

	// Group by category
	const grouped = $derived(() => {
		const result: Record<string, MetricItem[]> = {};
		catalog.filter(m => items.includes(m.id)).forEach(m => {
			const cat = m.category || m.group || 'sonstige';
			if (!result[cat]) result[cat] = [];
			result[cat].push(m);
		});
		return result;
	});

	const orderedCats = $derived(Object.keys(grouped()));
</script>

<Card padding={0} class={className}>
	<button
		onclick={() => (open = !open)}
		style:width="100%"
		style:padding={compact ? '12px 16px' : '14px 18px'}
		style:display="flex"
		style:justify-content="space-between"
		style:align-items="center"
		style:background="transparent"
		style:border="none"
		style:cursor="pointer"
		style:text-align="left"
	>
		<div>
			<Eyebrow>Nicht im Briefing</Eyebrow>
			<div style:font-size={compact ? '14px' : '15px'} style:font-weight="600" style:margin-top="2px">
				{items.length} weitere Metriken
				<span style:color="var(--g-ink-4)" style:font-size="12px" style:font-weight="400"> · aktuell aus</span>
			</div>
		</div>
		<span style:font-family="var(--g-font-mono)" style:font-size="11px" style:color="var(--g-ink-3)">
			{open ? '▴ einklappen' : '▾ ausklappen'}
		</span>
	</button>

	{#if open}
		<div style:padding="0 18px 16px" style:border-top="1px solid var(--g-rule-soft)">
			{#each orderedCats as cat (cat)}
				<div style:margin-top="14px">
					<div
						style:font-family="var(--g-font-mono)"
						style:font-size="10px"
						style:letter-spacing="0.1em"
						style:text-transform="uppercase"
						style:color="var(--g-ink-3)"
						style:font-weight="600"
						style:margin-bottom="6px"
					>{cat}</div>
					<div style:display="grid" style:grid-template-columns="repeat(auto-fill, minmax(240px, 1fr))" style:gap="6px">
						{#each grouped()[cat] as m (m.id)}
							<div
								style:display="flex"
								style:align-items="center"
								style:gap="6px"
								style:padding="6px 9px"
								style:border="1px solid var(--g-rule-soft)"
								style:border-radius="var(--g-r-2)"
								style:background="var(--g-card-alt)"
							>
								<div style:flex="1" style:min-width="0">
									<div style:font-size="12px" style:font-weight="500" style:color="var(--g-ink-2)">{m.label}</div>
									<div style:font-family="var(--g-font-mono)" style:font-size="9.5px" style:color="var(--g-ink-4)">
										{m.unit ?? '—'} · {m.short ?? ''}
									</div>
								</div>
								<Btn variant="ghost" size="xs" onclick={() => onAdd && onAdd(m.id, 'primary')}>+ Spalte</Btn>
								<Btn variant="quiet" size="xs" onclick={() => onAdd && onAdd(m.id, 'secondary')}>+ Detail</Btn>
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</Card>
