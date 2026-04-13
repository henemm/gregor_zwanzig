<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { Button } from '$lib/components/ui/button/index.js';

	let { data } = $props();
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold">Dashboard</h1>

	<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
		<Card.Root data-testid="stat-trips">
			<Card.Header>
				<Card.Title>Trips</Card.Title>
			</Card.Header>
			<Card.Content>
				<span class="text-3xl font-bold" data-testid="stat-value">{data.tripCount}</span>
			</Card.Content>
			<Card.Footer>
				<a href="/trips" class="text-sm text-muted-foreground hover:underline">Verwalten</a>
			</Card.Footer>
		</Card.Root>

		<Card.Root data-testid="stat-locations">
			<Card.Header>
				<Card.Title>Locations</Card.Title>
			</Card.Header>
			<Card.Content>
				<span class="text-3xl font-bold" data-testid="stat-value">{data.locationCount}</span>
			</Card.Content>
			<Card.Footer>
				<a href="/locations" class="text-sm text-muted-foreground hover:underline">Verwalten</a>
			</Card.Footer>
		</Card.Root>

		<Card.Root data-testid="stat-health">
			<Card.Header>
				<Card.Title>System Status</Card.Title>
			</Card.Header>
			<Card.Content>
				<div class="space-y-1">
					<p>
						API:
						<span
							class="font-medium"
							class:text-green-600={data.health.status === 'ok'}
							class:text-yellow-600={data.health.status === 'degraded'}
						>
							{data.health.status}
						</span>
					</p>
					<p>
						Python Core:
						<span
							class="font-medium"
							class:text-green-600={data.health.python_core === 'ok'}
							class:text-red-600={data.health.python_core === 'unavailable'}
						>
							{data.health.python_core}
						</span>
					</p>
					<p class="text-xs text-muted-foreground">v{data.health.version}</p>
				</div>
			</Card.Content>
		</Card.Root>
	</div>
</div>
