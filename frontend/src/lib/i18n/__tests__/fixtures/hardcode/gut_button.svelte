<script lang="ts">
	// Fixture fuer den Scanner (#2649): Stand-in fuer den Katalog-Store, damit
	// die Datei ohne echte Katalogschluessel typpruefbar bleibt. Der Scanner
	// liest nur das Markup.
	import { readable } from 'svelte/store';
	const t = readable((key: string) => key);
	const offen = true;
</script>

<!-- Ein Kommentar mit Text zaehlt nicht -->
<button>{$t('aktionen.speichern')}</button>
{#if offen}
	<span>&nbsp;×&nbsp;→ ⓘ • ✓</span>
{:else}
	<span>{$t('aktionen.abbrechen')}</span>
{/if}
