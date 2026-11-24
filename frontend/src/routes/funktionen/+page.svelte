<script lang="ts">
	// Issue #3319 / #3320 — oeffentliche Funktionsuebersicht /funktionen (DE/EN).
	// Spec: docs/specs/modules/oeffentliche_doku_3319.md. Duenne Seite in SEITEN_SCOPE
	// (Regel (a), ADR-0112): Aufbau im Organismus FunktionenUebersicht. Ohne Anmeldung
	// erreichbar (hooks.server.ts, exakte Pfade), keine Nutzerdaten, kein API-Aufruf.
	import { t } from '$lib/i18n';
	import FunktionenUebersicht from '$lib/components/organisms/funktionen/FunktionenUebersicht.svelte';

	let { data }: { data: { oeffentlich: true; lang: 'de' | 'en' } } = $props();
</script>

<svelte:head>
	<title>{$t('funktionen.meta.title')}</title>
	<meta name="description" content={$t('funktionen.meta.description')} />
</svelte:head>

<FunktionenUebersicht oeffentlich={data.oeffentlich} />
