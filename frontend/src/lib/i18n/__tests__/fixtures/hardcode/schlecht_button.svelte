<script lang="ts">
	let zaehler = $state(0);
	function erhoehe() {
		zaehler += 1;
	}
</script>

<button onclick={erhoehe}>Speichern</button>

<style>
	button {
		color: black;
	}
</style>
