<script lang="ts">
	// Issue #249 / #301 — Compare-Screen Locations-Sidebar.
	//
	// Spec: docs/specs/modules/issue_249_locations_rail.md
	//       docs/specs/modules/issue_301_sidebar_groups.md §7
	//
	// Diese Komponente ist rein presentational: sie haelt lokal nur Search- und
	// Chip-Filter-State; Selection-/Gruppen-Toggle-Logik liegt in der Page.
	// Seit #301: Gruppen kommen als Group-Entity (group_id), gerendert via GroupSection;
	// Wrapper ist <aside> mit 320px (E2E sucht page.locator('aside')).

	import type { Location, Group, ActivityProfile } from '$lib/types.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Pill } from '$lib/components/ui/pill/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import GroupSection from './GroupSection.svelte';
	import CreateGroupDialog from './CreateGroupDialog.svelte';
	import { filterLocations } from './locationHelpers.js';
	import { profileSignature } from '$lib/utils/profileSignature.js';

	interface Props {
		locations: Location[];
		groups: Group[];
		selectedIds: string[];
		groupedLocations: { sections: { group: Group; locations: Location[] }[]; ungrouped: Location[] };
		openGroups: Set<string>;
		allSelected: boolean;
		onToggleAll: () => void;
		onToggleLocation: (id: string) => void;
		onToggleGroup: (id: string) => void;
		onToggleGroupSelection: (id: string) => void;
		onShowWeather: (id: string) => void;
		onEditLocation: (loc: Location) => void;
		onNewLocation: () => void;
		onGroupCreated: (group: Group) => void;
	}

	let {
		locations,
		groups,
		selectedIds,
		groupedLocations,
		openGroups,
		allSelected,
		onToggleAll,
		onToggleLocation,
		onToggleGroup,
		onToggleGroupSelection,
		onShowWeather,
		onEditLocation,
		onNewLocation,
		onGroupCreated,
	}: Props = $props();

	let search = $state('');
	let activeGroup = $state<string | null>(null);
	let activeProfile = $state<ActivityProfile | null>(null);
	let createGroupOpen = $state(false);

	// group_id -> group.name fuer die Suche im Gruppennamen (AC-4).
	let groupNameMap = $derived(new Map(groups.map((g) => [g.id, g.name])));

	// Issue #132 — Nur Profile, die tatsaechlich (nicht-'allgemein') in der Liste vorkommen,
	// werden als Chips gerendert. Feste Sortier-Reihenfolge fuer UI-Stabilitaet.
	let profilesInLocations = $derived(
		[
			...new Set(
				locations
					.map((l) => l.activity_profile)
					.filter((p): p is ActivityProfile => Boolean(p) && p !== 'allgemein'),
			),
		].sort((a, b) => {
			const order = ['wintersport', 'wandern', 'summer_trekking'];
			return order.indexOf(a) - order.indexOf(b);
		}),
	);

	// Gefilterte Sektionen werden aus groupedLocations + filterLocations() abgeleitet.
	// Die Gruppen-Reihenfolge bleibt konsistent zur Page; einzelne Listen werden auf
	// gefilterte Subsets gesetzt.
	let filteredGrouped = $derived.by(() => {
		const filtered = filterLocations(locations, search, activeGroup, activeProfile, groupNameMap);
		const filteredIds = new Set(filtered.map((l) => l.id));
		const sections = groupedLocations.sections.map((s) => ({
			group: s.group,
			locations: s.locations.filter((l) => filteredIds.has(l.id)),
		}));
		const ungrouped = groupedLocations.ungrouped.filter((l) => filteredIds.has(l.id));
		return { sections, ungrouped };
	});
</script>

<aside
	data-testid="compare-rail"
	class="shrink-0 flex flex-col space-y-3 pr-4"
	style="width: 320px; border-right: 1px solid color-mix(in srgb, var(--g-ink-faint) 40%, transparent);"
>
	<input
		data-testid="compare-rail-search"
		type="search"
		placeholder="Orte suchen..."
		bind:value={search}
		class="h-8 w-full rounded-md border border-input bg-transparent px-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
	/>

	{#if groups.length > 0}
		<div class="flex flex-wrap gap-1">
			{#each groups as g (g.id)}
				<button
					data-testid="compare-rail-chip"
					aria-label={g.name}
					aria-pressed={activeGroup === g.id}
					onclick={() => (activeGroup = activeGroup === g.id ? null : g.id)}
					class="cursor-pointer"
				>
					<Pill tone={activeGroup === g.id ? 'accent' : 'default'}>{g.name}</Pill>
				</button>
			{/each}
		</div>
	{/if}

	{#if profilesInLocations.length > 0}
		<div class="flex flex-wrap gap-1">
			{#each profilesInLocations as p}
				{@const sig = profileSignature(p)}
				<button
					data-testid="compare-rail-profile-chip"
					aria-label={sig.eyebrow}
					aria-pressed={activeProfile === p}
					onclick={() => (activeProfile = activeProfile === p ? null : p)}
					class="cursor-pointer"
				>
					<Pill tone={activeProfile === p ? 'accent' : 'default'}><span data-slot="dot" data-size="xs" style="background: {sig.accent}; flex-shrink: 0; margin-right: 4px;" title={sig.eyebrow}></span>{sig.eyebrow}</Pill>
				</button>
			{/each}
		</div>
	{/if}

	<Checkbox
		checked={allSelected}
		onchange={onToggleAll}
	>Alle ({selectedIds.length}/{locations.length})</Checkbox>

	<div class="space-y-1">
		{#each filteredGrouped.sections as section (section.group.id)}
			<GroupSection
				group={section.group}
				locations={section.locations}
				open={openGroups.has(section.group.id)}
				{selectedIds}
				onToggle={() => onToggleGroup(section.group.id)}
				onToggleAll={() => onToggleGroupSelection(section.group.id)}
				{onToggleLocation}
				{onEditLocation}
				{onShowWeather}
			/>
		{/each}

		{#if filteredGrouped.ungrouped.length > 0}
			<div class="ungroup-section" data-testid="ungroup-section">
				<p class="text-sm font-medium text-muted-foreground">Ungruppiert ({filteredGrouped.ungrouped.length})</p>
				<ul class="ml-4 space-y-0.5">
					{#each filteredGrouped.ungrouped as loc (loc.id)}
						<li class="flex items-center gap-1.5 text-sm">
							<Checkbox
								checked={selectedIds.includes(loc.id)}
								onchange={() => onToggleLocation(loc.id)}
							/>
							<button
								class="loc-name-btn flex-1 text-left hover:underline"
								onclick={() => onEditLocation(loc)}
								data-testid="loc-name-{loc.id}"
							>{loc.name}</button>
							<button
								onclick={() => onShowWeather(loc.id)}
								title="Wetter anzeigen"
								class="opacity-40 hover:opacity-100"
							>
								<CloudSunIcon class="size-3.5" />
							</button>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>

	<div class="rail-footer flex gap-2">
		<Btn
			variant="outline"
			size="sm"
			class="flex-1"
			onclick={onNewLocation}
			data-testid="compare-rail-new-btn"
		>
			+ Ort
		</Btn>
		<Btn
			variant="outline"
			size="sm"
			class="flex-1"
			onclick={() => (createGroupOpen = true)}
			data-testid="compare-rail-new-group-btn"
		>
			+ Gruppe
		</Btn>
	</div>
</aside>

<CreateGroupDialog bind:open={createGroupOpen} onCreate={onGroupCreated} />
