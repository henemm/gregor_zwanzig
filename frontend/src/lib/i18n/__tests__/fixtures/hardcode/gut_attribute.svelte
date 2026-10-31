<script lang="ts">
	// Fixture fuer den Scanner (#2649): Stand-in fuer den Katalog-Store.
	import { readable } from 'svelte/store';
	const t = readable((key: string) => key);
</script>

<div class="karte breit" data-hinweis="Kein beschriftendes Attribut">
	<input placeholder={$t('aktionen.suche')} />
	<button aria-label={$t('aktionen.schliessen')} title="×">×</button>
	<img src="/bild.png" alt={$t('aktionen.bild')} />
</div>
