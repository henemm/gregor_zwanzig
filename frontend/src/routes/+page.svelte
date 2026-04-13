<script lang="ts">
	import { api } from '$lib/api.js';
	import type { HealthResponse } from '$lib/types.js';

	let health: HealthResponse | null = $state(null);
	let error: string | null = $state(null);

	async function checkHealth() {
		try {
			health = await api.get<HealthResponse>('/api/health');
			error = null;
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Connection failed';
			health = null;
		}
	}

	$effect(() => {
		checkHealth();
	});
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold">Dashboard</h1>

	<div class="rounded-lg border p-4">
		<h2 class="mb-2 text-sm font-medium text-muted-foreground">System Status</h2>
		{#if health}
			<div class="space-y-1">
				<p>
					API:
					<span class="font-medium" class:text-green-600={health.status === 'ok'} class:text-yellow-600={health.status === 'degraded'}>
						{health.status}
					</span>
				</p>
				<p>
					Python Core:
					<span class="font-medium" class:text-green-600={health.python_core === 'ok'} class:text-red-600={health.python_core === 'unavailable'}>
						{health.python_core}
					</span>
				</p>
				<p class="text-xs text-muted-foreground">v{health.version}</p>
			</div>
		{:else if error}
			<p class="text-sm text-destructive">{error}</p>
		{:else}
			<p class="text-sm text-muted-foreground">Loading...</p>
		{/if}
	</div>
</div>
