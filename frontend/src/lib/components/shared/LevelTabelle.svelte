<script lang="ts">
	// Issue #3319 (AC-2/AC-6): Level-Tabelle fuer Startseite (kurz) und Funktionsseite (voll).
	// Duenne Seite in SEITEN_SCOPE (Regel (a), ADR-0112): Aufbau im Organismus LevelTabelleInhalt.
	import type { ComponentProps } from 'svelte';
	import LevelTabelleInhalt from '$lib/components/organisms/funktionen/LevelTabelleInhalt.svelte';

	let { umfang }: ComponentProps<typeof LevelTabelleInhalt> = $props();
</script>

<LevelTabelleInhalt {umfang} />
