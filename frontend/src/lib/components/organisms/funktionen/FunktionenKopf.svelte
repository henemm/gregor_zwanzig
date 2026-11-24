<script lang="ts">
	// Issue #3319 (AC-6/AC-11) — Seitenkopf der Funktionsseiten: Logo und
	// Sprachumschalter als Banner AUSSERHALB von <main> (die Markenschrift ist als
	// Logo von der Kontrastpflicht ausgenommen; der Inhalt in <main> erfuellt WCAG-AA).
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import SprachUmschalter from '$lib/components/ui/SprachUmschalter.svelte';
</script>

<header class="kopf">
	<Wordmark size="md" />
	<SprachUmschalter />
</header>

<style>
	.kopf {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-3);
	}
</style>
