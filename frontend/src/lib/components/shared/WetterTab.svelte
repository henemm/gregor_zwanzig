<script lang="ts">
	// Issue #2913 Teil 2 (AC-17, K-1): Reiter „Wetter“ als dünne Seite für Trip (`route`) und
	// Orts-Briefing (`vergleich`) — Hub und Anlege-Kette, EIN Code (Trip/Ortsvergleich-Teilung, #1170).
	// Steht in SEITEN_SCOPE (Regel (a), ADR-0112): kein <style>, keine rohen Controls, Komponenten nur
	// aus atoms/molecules/organisms. Zustand, Laden und Speichern liegen im Organismus WetterTabInhalt.
	import type { ComponentProps } from 'svelte';
	import WetterTabInhalt from '$lib/components/organisms/wetter-tab/WetterTabInhalt.svelte';

	let { context, ...rest }: ComponentProps<typeof WetterTabInhalt> = $props();
</script>

<WetterTabInhalt {context} {...rest} />
