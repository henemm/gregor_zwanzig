<script lang="ts">
	// Issues #477 + #486 — TestReportDialog-Molecule.
	//
	// Kapselt den Status-Rückmeldungs-Dialog für ausgelöste Test-Briefings.
	// Befreit /trips/+page.svelte von ui/dialog.
	//
	// Spec: docs/specs/modules/trips_atomic_kebab.md (Schritt 4)

	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Btn } from '$lib/components/atoms';

	interface Props {
		open: boolean;
		hour: 7 | 18 | null;
		running?: boolean;
		result?: string | null;
		error?: string | null;
		onClose: () => void;
	}

	let {
		open,
		hour,
		running = false,
		result = null,
		error = null,
		onClose
	}: Props = $props();
</script>

<Dialog.Root
	{open}
	onOpenChange={(o) => { if (!o) onClose(); }}
>
	<Dialog.Content class="max-w-sm">
		<Dialog.Header>
			<Dialog.Title>
				Test-Report — {hour === 7 ? 'Morgen' : 'Abend'}
			</Dialog.Title>
		</Dialog.Header>
		<div class="py-4 text-sm">
			{#if running}
				<p class="text-muted-foreground">Report wird ausgelöst…</p>
			{:else if result}
				<p class="text-green-700 dark:text-green-400">{result}</p>
			{:else if error}
				<p class="text-destructive">{error}</p>
			{/if}
		</div>
		<Dialog.Footer>
			<Btn variant="primary" onclick={onClose}>Schließen</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
