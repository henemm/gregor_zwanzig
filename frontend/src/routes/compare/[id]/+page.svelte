<script lang="ts">
	// Issue #491 — Compare-Preset Detail-Seite.
	import { Eyebrow, Btn } from '$lib/components/atoms';
	import CompareDetail from '$lib/components/compare/CompareDetail.svelte';
	import { deriveStatusFromPreset, STATUS_MAP } from '$lib/components/compare/subscriptionHelpers.js';

	let { data } = $props();
	let status = $derived(deriveStatusFromPreset(data.preset));
	let statusInfo = $derived(STATUS_MAP[status]);
</script>

<div class="p-8 max-w-5xl mx-auto">
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
