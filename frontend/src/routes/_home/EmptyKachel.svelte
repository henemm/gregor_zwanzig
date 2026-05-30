<script lang="ts">
	import { EmptyState } from '$lib/components/ui/empty-state/index.js';
	import { Btn } from '$lib/components/atoms';
</script>

<EmptyState title="Willkommen bei Gregor 20" description="Leg deinen ersten Trip an oder starte einen Orts-Vergleich.">
	<div style="display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: center;">
		<Btn variant="accent" href="/trips/new">+ Neuer Trip</Btn>
		<Btn variant="outline" href="/compare">+ Neuer Vergleich</Btn>
	</div>
</EmptyState>
