<script lang="ts">
	// Issue #301 Lieferung A — klappbare Gruppen-Sektion in der Compare-Sidebar.
	//
	// Spec: docs/specs/modules/issue_301_sidebar_groups.md §5
	//
	// Rein presentational: Header (Chevron + Checkbox mit indeterminate +
	// Profil-Dot via profileSignature + Name + Count), darunter die Ortsliste
	// mit Checkbox, klickbarem Ortsnamen (oeffnet Edit-Dialog) und Wetter-Button.

	import type { Location, Group } from '$lib/types.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import { profileSignature } from '$lib/utils/profileSignature.js';

	interface Props {
		group: Group;
		locations: Location[];
		open?: boolean;
		selectedIds: string[];
		onToggle: () => void;
		onToggleAll: () => void;
		onToggleLocation: (id: string) => void;
		onEditLocation: (loc: Location) => void;
		onShowWeather: (id: string) => void;
	}

	let {
		group,
		locations,
		open = true,
		selectedIds,
		onToggle,
		onToggleAll,
		onToggleLocation,
		onEditLocation,
		onShowWeather,
	}: Props = $props();

	let allSelected = $derived(
		locations.length > 0 && locations.every((l) => selectedIds.includes(l.id)),
	);
	let someSelected = $derived(locations.some((l) => selectedIds.includes(l.id)));
	let sig = $derived(profileSignature(group.default_profile));
</script>

<div class="group-section" data-testid="group-section-{group.id}">
	<div data-testid="compare-rail-group-header" class="flex items-center gap-1">
		<button
			aria-label={group.name}
			aria-expanded={open}
			class="flex items-center text-muted-foreground hover:text-foreground"
			onclick={onToggle}
		>
			<ChevronRightIcon
				class="size-3.5 transition-transform"
				style={open ? 'transform: rotate(90deg);' : ''}
			/>
		</button>
		<Checkbox
			checked={allSelected}
			indeterminate={someSelected && !allSelected}
			onchange={onToggleAll}
		>
			<span class="flex items-center gap-1.5">
				<span
					data-slot="dot"
					data-size="xs"
					style="background: {sig.accent}; flex-shrink: 0;"
					title={sig.eyebrow}
				></span>
				<span class="group-name">{group.name}</span>
				<span class="text-muted-foreground" data-testid="group-count-{group.id}">({locations.length})</span>
			</span>
		</Checkbox>
	</div>

	{#if open}
		<ul class="ml-4 space-y-0.5">
			{#each locations as loc (loc.id)}
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
					{#if loc.activity_profile && loc.activity_profile !== 'allgemein'}
						<span
							data-slot="dot"
							data-size="xs"
							style="background: {profileSignature(loc.activity_profile).accent}; flex-shrink: 0;"
							title={profileSignature(loc.activity_profile).eyebrow}
						></span>
					{/if}
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
	{/if}
</div>
