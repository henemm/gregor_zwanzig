<script lang="ts">
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
</script>

<div data-testid="alert-feed">
	<GCard class="p-6">
		<Eyebrow>Alerts letzte 24h</Eyebrow>
		<p class="text-muted-foreground mt-2 text-sm">Keine Alerts in den letzten 24h</p>
	</GCard>
</div>
