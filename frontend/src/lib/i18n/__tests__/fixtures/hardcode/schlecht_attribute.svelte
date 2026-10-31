<script lang="ts">
	const anzahl = 3;
	const titel = { kurz: 'x' };
</script>

<div>
	<input placeholder="Suche" />
	<button aria-label="Schließen">×</button>
	<img src="/bild.png" alt="" />
	<span title="Orte {anzahl}">{titel.kurz}</span>
</div>

<style>
	div {
		display: flex;
	}
</style>
