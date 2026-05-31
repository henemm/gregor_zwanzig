<script lang="ts">
	// Issue #491 — Compare-Preset Detail-Seite.
	// Issue #493 — Mobile-Responsive: TopBar + 2×2-Grid + MCompareActionSheet.
	import { Eyebrow, Btn, Card, KV, Dot } from '$lib/components/atoms';
	import CompareDetail from '$lib/components/compare/CompareDetail.svelte';
	import CompareStatusPill from '$lib/components/compare/CompareStatusPill.svelte';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	import { MCompareActionSheet } from '$lib/components/mobile';
	import {
		deriveStatusFromPreset,
		STATUS_MAP,
		presetScheduleLabel,
		formatLastSent
	} from '$lib/components/compare/subscriptionHelpers.js';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import MoreHorizontalIcon from '@lucide/svelte/icons/more-horizontal';

	let { data } = $props();
	let status = $derived(deriveStatusFromPreset(data.preset));
	let statusInfo = $derived(STATUS_MAP[status]);

	let actionSheetOpen = $state(false);

	function handleAction(id: string) {
		if (id === 'edit' || id === 'setup') {
			window.location.href = `/compare/${data.preset.id}/edit`;
		}
	}
</script>

<!-- Desktop-Layout (#491) -->
<div class="hidden desktop:block p-8 max-w-5xl mx-auto">
	<Eyebrow>WORKSPACE · ORTS-VERGLEICHE / DETAIL</Eyebrow>
	<div class="flex items-start justify-between mt-1 mb-6">
		<div>
			<h1 class="text-3xl font-semibold tracking-tight">
				{data.preset.name}
			</h1>
			<span
				class="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full"
				style="background: {statusInfo.dot}1a; color: {statusInfo.dot}; border: 1px solid {statusInfo.dot}40"
			>
				{statusInfo.label}
			</span>
			<p class="text-sm text-[var(--g-ink-3)] mt-1">
				{data.preset.display_config?.region ?? '—'} · {data.preset.profil} · {data.preset.location_ids.length} {data.preset.location_ids.length === 1 ? 'Ort' : 'Orte'}
			</p>
		</div>
		<Btn variant="primary" href="/compare/{data.preset.id}/edit">Bearbeiten</Btn>
	</div>

	<CompareDetail preset={data.preset} locations={data.locations} />
</div>

<!-- Mobile-Layout (#493) -->
<div class="desktop:hidden flex flex-col gap-4 p-4">
	<!-- TopBar -->
	<div class="flex items-center gap-2 min-h-[44px]">
		<a
			href="/compare"
			class="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-md"
			aria-label="Zurück zur Übersicht"
		>
			<ArrowLeftIcon size={20} />
		</a>
		<span class="flex-1 font-semibold truncate">{data.preset.name}</span>
		<a
			href="/compare/{data.preset.id}/edit"
			class="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-md"
			aria-label="Bearbeiten"
		>
			<PencilIcon size={18} />
		</a>
		<button
			type="button"
			class="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-md"
			aria-label="Weitere Aktionen"
			onclick={() => (actionSheetOpen = true)}
		>
			<MoreHorizontalIcon size={20} />
		</button>
	</div>

	<!-- Status -->
	<CompareStatusPill {status} />

	<!-- Monitoring 2×2-Grid -->
	<div class="grid grid-cols-2 gap-3">
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Status</div>
			<div class="text-sm mt-1">{statusInfo.label}</div>
		</Card>
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Nächster</div>
			<div class="text-sm mt-1">{presetScheduleLabel(data.preset)}</div>
		</Card>
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Zuletzt</div>
			<div class="text-sm mt-1">{formatLastSent(data.preset.letzter_versand)}</div>
		</Card>
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Kanäle</div>
			<div class="text-sm mt-1 truncate">{(data.preset.empfaenger ?? []).length} Kanäle</div>
		</Card>
	</div>

	<!-- Standort-Liste -->
	{#if data.locations && data.locations.length > 0}
		{#each data.locations as loc, i (loc.id)}
			<CompareLocationRow {loc} index={i + 1} dense={true} />
		{/each}
	{:else}
		<p class="text-sm text-[var(--g-ink-3)]">Noch keine Orte ausgewählt.</p>
	{/if}
</div>

<!-- Bottom-Sheet für mobile Aktionen (#493) -->
<MCompareActionSheet
	open={actionSheetOpen}
	onClose={() => (actionSheetOpen = false)}
	{status}
	onAction={handleAction}
	presetName={data.preset.name}
/>
