<script lang="ts">
	// Issue #183 — Dev-Route fuer Email-Preview Header (TDD GREEN).
	// Wird in Issue #189 (Vorschau-Integration) durch die echte Einbindung ersetzt.
	import EmailPreviewHeader from '$lib/components/email-preview/EmailPreviewHeader.svelte';
	import type { Trip, Stage } from '$lib/types';

	const trip: Trip = {
		id: 'dev-trip-zillertal',
		name: 'Zillertal',
		shortcode: 'ZIL',
		stages: []
	};
	const stage: Stage = {
		id: 'dev-stage-1',
		name: 'Tag 1: Karwendelhaus',
		date: '2026-06-15',
		waypoints: [
			{ id: 'w1', name: 'Start', lat: 47.395, lon: 11.467, elevation_m: 900 },
			{ id: 'w2', name: 'Sattel', lat: 47.402, lon: 11.479, elevation_m: 1450 },
			{ id: 'w3', name: 'Gipfel', lat: 47.408, lon: 11.488, elevation_m: 1880 },
			{ id: 'w4', name: 'Hütte', lat: 47.415, lon: 11.495, elevation_m: 1750 }
		]
	};
</script>

<svelte:head><title>Email-Preview Dev — Issue #183</title></svelte:head>

<main class="container mx-auto p-8 max-w-3xl">
	<div class="bg-yellow-100 border border-yellow-400 text-yellow-900 px-3 py-2 rounded text-sm mb-4">
		⚠ DEV-VORSCHAU — interne Entwickler-Seite, kein Echtbetrieb. Wird mit Issue #189 entfernt.
	</div>
	<h1 class="text-2xl font-bold mb-2">Email-Preview Dev — Issue #183</h1>
	<p class="text-sm text-muted-foreground mb-6">
		Isolierte Vorschau des EmailPreviewHeaders mit Mock-Daten.
		Wird in Issue #189 (Vorschau-Integration) durch die echte Einbindung ersetzt.
	</p>

	<h3 class="text-lg font-semibold mb-2">Morgen-Briefing</h3>
	<EmailPreviewHeader {trip} {stage} reportType="morning" reportDate="2026-06-15" />

	<h3 class="text-lg font-semibold mt-8 mb-2">Abend-Briefing</h3>
	<EmailPreviewHeader {trip} {stage} reportType="evening" reportDate="2026-06-15" />
</main>
