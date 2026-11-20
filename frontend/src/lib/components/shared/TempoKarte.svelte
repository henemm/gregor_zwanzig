<script lang="ts">
	// Issue #3196 (ADR-0108 Nr. 2): Karte „Fortbewegung + Grundtempo" — oben im Reiter Etappen UND
	// im Anlegen (Anlegen = Bearbeiten, EIN Code). Dünne Seite in SEITEN_SCOPE (Regel (a), ADR-0112):
	// kein <style>, keine rohen Controls; Aufbau und Bedienung liegen im Organismus TempoKarteInhalt.
	// Vertrag: props { tempo, onchange? }; der Aufrufer speichert (Autosave/ETag-Pfad).
	import type { ComponentProps } from 'svelte';
	import TempoKarteInhalt from '$lib/components/organisms/tempo-karte/TempoKarteInhalt.svelte';

	let { tempo, onchange }: ComponentProps<typeof TempoKarteInhalt> = $props();
</script>

<TempoKarteInhalt {tempo} {onchange} />
