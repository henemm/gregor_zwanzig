<script lang="ts">
	// Issue #3319 / #3320 — oeffentliche Funktions-Unterseite /funktionen/<slug> (DE/EN).
	// Spec: docs/specs/modules/oeffentliche_doku_3319.md. Duenne Seite in SEITEN_SCOPE
	// (Regel (a), ADR-0112): Aufbau im Organismus FunktionenUnterseite; hier nur der
	// eigene Seitentitel und die eigene Meta-Beschreibung (AC-12).
	import { t } from '$lib/i18n';
	import type { FunktionenSlug } from '$lib/funktionen_seiten';
	import FunktionenUnterseite from '$lib/components/organisms/funktionen/FunktionenUnterseite.svelte';
	import { seitenBeschreibung, seitenTitel } from '$lib/components/organisms/funktionen/inhalt';

	let { data }: { data: { oeffentlich: true; lang: 'de' | 'en'; slug: FunktionenSlug } } = $props();
</script>

<svelte:head>
	<title>{$t('funktionen.meta.title_seite', { thema: $t(seitenTitel(data.slug)) })}</title>
	<meta name="description" content={$t(seitenBeschreibung(data.slug))} />
</svelte:head>

<FunktionenUnterseite slug={data.slug} oeffentlich={data.oeffentlich} />
