<script lang="ts">
	// Issue #249 — Compare-Screen Locations-Sidebar.
	//
	// Spec: docs/specs/modules/issue_249_locations_rail.md
	//
	// Diese Komponente ist rein presentational: sie haelt lokal nur Search- und
	// Chip-Filter-State; Selection-/Gruppen-Toggle-Logik liegt in der Page.

	import type { Location } from '$lib/types.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Pill } from '$lib/components/ui/pill/index.js';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import { filterLocations } from './locationHelpers.js';

	interface Props {
		locations: Location[];
		selectedIds: string[];
		groupedLocations: { groups: Map<string, Location[]>; ungrouped: Location[] };
		openGroups: Set<string>;
		allSelected: boolean;
		onToggleAll: () => void;
		onToggleLocation: (id: string) => void;
		onToggleGroup: (name: string) => void;
		onToggleGroupSelection: (name: string) => void;
		onShowWeather: (id: string) => void;
		onNewLocation: () => void;
	}

	let {
		locations,
		selectedIds,
		groupedLocations,
		openGroups,
		allSelected,
		onToggleAll,
		onToggleLocation,
		onToggleGroup,
		onToggleGroupSelection,
		onShowWeather,
		onNewLocation,
	}: Props = $props();

	let search = $state('');
	let activeGroup = $state<string | null>(null);

	// Gefilterte Locations werden aus groupedLocations + filterLocations() abgeleitet.
	// Damit bleibt die Gruppen-Reihenfolge konsistent zur Page, und wir setzen nur die
	// einzelnen Listen auf gefilterte Subsets.
	let filteredGrouped = $derived.by(() => {
		const filtered = filterLocations(locations, search, activeGroup);
		const filteredIds = new Set(filtered.map((l) => l.id));
		const groups = new Map<string, Location[]>();
		const ungrouped: Location[] = [];
		for (const [name, locs] of groupedLocations.groups) {
			const gl = locs.filter((l) => filteredIds.has(l.id));
			if (gl.length > 0) groups.set(name, gl);
		}
		for (const l of groupedLocations.ungrouped) {
			if (filteredIds.has(l.id)) ungrouped.push(l);
		}
		return { groups, ungrouped };
	});
</script>

<div
	data-testid="compare-rail"
	class="hidden w-60 shrink-0 flex-col space-y-3 border-r pr-4 md:flex"
>
	<input
		data-testid="compare-rail-search"
		type="search"
		placeholder="Orte suchen..."
		bind:value={search}
		class="h-8 w-full rounded-md border border-input bg-transparent px-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
	/>

	{#if groupedLocations.groups.size > 0}
		<div class="flex flex-wrap gap-1">
			{#each [...groupedLocations.groups.keys()].sort() as g}
				<button
					data-testid="compare-rail-chip"
					aria-label={g}
					aria-pressed={activeGroup === g}
					onclick={() => (activeGroup = activeGroup === g ? null : g)}
					class="cursor-pointer"
				>
					<Pill tone={activeGroup === g ? 'accent' : 'default'}>{g}</Pill>
				</button>
			{/each}
		</div>
	{/if}

	<label class="flex items-center gap-2 text-sm">
		<input
			type="checkbox"
			checked={allSelected}
			onchange={onToggleAll}
			class="h-4 w-4 rounded border-input"
		/>
		Alle ({selectedIds.length}/{locations.length})
	</label>

	<div class="space-y-1">
		{#each [...filteredGrouped.groups.entries()].sort((a, b) => a[0].localeCompare(b[0])) as [groupName, groupLocs]}
			{@const isOpen = openGroups.has(groupName)}
			{@const allInGroup = groupLocs.every((l) => selectedIds.includes(l.id))}
			<div>
				<div class="flex items-center gap-1">
					<button
						data-testid="compare-rail-group-header"
						aria-label={groupName}
						class="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
						onclick={() => onToggleGroup(groupName)}
					>
						<span class="inline-block w-3 text-xs">{isOpen ? '▼' : '▶'}</span>
					</button>
					<label class="flex items-center gap-1.5 text-sm font-medium">
						<input
							type="checkbox"
							checked={allInGroup}
							onchange={() => onToggleGroupSelection(groupName)}
							class="h-3.5 w-3.5 rounded border-input"
						/>
						{groupName} ({groupLocs.length})
					</label>
				</div>
				{#if isOpen}
					<div class="ml-4 space-y-0.5">
						{#each groupLocs as loc}
							<div class="flex items-center gap-1.5 text-sm">
								<input
									type="checkbox"
									checked={selectedIds.includes(loc.id)}
									onchange={() => onToggleLocation(loc.id)}
									class="h-3.5 w-3.5 rounded border-input"
								/>
								<span class="flex-1">{loc.name}</span>
								<button
									onclick={() => onShowWeather(loc.id)}
									title="Wetter anzeigen"
									class="opacity-40 hover:opacity-100"
								>
									<CloudSunIcon class="size-3.5" />
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/each}

		{#each filteredGrouped.ungrouped as loc}
			<div class="flex items-center gap-1.5 text-sm">
				<input
					type="checkbox"
					checked={selectedIds.includes(loc.id)}
					onchange={() => onToggleLocation(loc.id)}
					class="h-3.5 w-3.5 rounded border-input"
				/>
				<span class="flex-1">{loc.name}</span>
				<button
					onclick={() => onShowWeather(loc.id)}
					title="Wetter anzeigen"
					class="opacity-40 hover:opacity-100"
				>
					<CloudSunIcon class="size-3.5" />
				</button>
			</div>
		{/each}
	</div>

	<Btn
		variant="outline"
		size="sm"
		class="w-full"
		onclick={onNewLocation}
		data-testid="compare-rail-new-btn"
	>
		+ NEU
	</Btn>
</div>
