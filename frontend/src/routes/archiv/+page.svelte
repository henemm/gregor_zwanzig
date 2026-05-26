<script lang="ts">
	import { EmptyState } from '$lib/components/ui/empty-state/index.js';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
</script>

<div class="space-y-4">
	<div>
		<Eyebrow>ARCHIV · VERGANGENE TRIPS</Eyebrow>
		<h1 class="text-3xl font-semibold tracking-tight mt-1">Archiv</h1>
	</div>

	<EmptyState title="Noch keine abgeschlossenen Trips im Archiv." />
</div>
