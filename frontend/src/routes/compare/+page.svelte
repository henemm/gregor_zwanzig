<script lang="ts">
	// Issue #439 — Orts-Vergleich Übersichtsseite.
	//
	// Spec: docs/specs/modules/issue_439_compare_uebersicht.md §1
	// Ersetzt den früheren interaktiven Vergleichsrechner durch eine tabellarische
	// Übersicht aller gespeicherten Orts-Vergleiche (Subscriptions). Teil von Epic #438.

	import type { Subscription } from '$lib/types.js';
	import { Eyebrow, Btn } from '$lib/components/atoms';
	import CompareList from '$lib/components/compare/CompareList.svelte';
	import { deriveStatus } from '$lib/components/compare/subscriptionHelpers.js';

	let { data } = $props();
	let subscriptions: Subscription[] = $state(data.subscriptions ?? []);

	let activeCount = $derived(subscriptions.filter((s) => deriveStatus(s) === 'active').length);
	let pausedCount = $derived(subscriptions.filter((s) => deriveStatus(s) === 'paused').length);
	let draftCount  = $derived(subscriptions.filter((s) => deriveStatus(s) === 'draft').length);
</script>

<div class="space-y-4">
	<div class="flex items-start justify-between gap-4">
		<div>
			<Eyebrow>WORKSPACE · ORTS-VERGLEICHE</Eyebrow>
			<h1 class="text-3xl font-semibold tracking-tight mt-1">Orts-Vergleiche</h1>
			<p class="text-sm text-muted-foreground mt-1">Alle Orts-Vergleiche auf einen Blick — Status, Kanäle und Aktionen.</p>
		</div>
		<Btn variant="accent" href="/compare/new">+ Neuer Vergleich</Btn>
	</div>

	{#if subscriptions.length > 0}
		<div class="hidden desktop:flex items-center gap-6 pb-3 border-b border-muted">
			<div class="flex items-center gap-2">
				<span style="font-size:22px;font-weight:700;color:var(--g-accent);line-height:1">{activeCount}</span>
				<span style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--g-ink-muted)">Aktiv</span>
			</div>
			<div class="flex items-center gap-2">
				<span style="font-size:22px;font-weight:700;line-height:1">{pausedCount}</span>
				<span style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--g-ink-muted)">Pausiert</span>
			</div>
			<div class="flex items-center gap-2">
				<span style="font-size:22px;font-weight:700;line-height:1">{draftCount}</span>
				<span style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--g-ink-muted)">Drafts</span>
			</div>
		</div>
	{/if}

	<CompareList bind:subscriptions />
</div>
