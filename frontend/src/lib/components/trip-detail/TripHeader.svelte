<script lang="ts">
	// Spec: docs/specs/modules/epic_135_step2_trip_detail_actions.md (§6)
	// Bündelt Breadcrumb + StatusBadge + Aktions-Buttons + Confirm-Dialog.
	// Alle on:click-Handler sind benannte Funktionen (Safari-Kompatibilität).
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import TripStatusBadge from './TripStatusBadge.svelte';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
		onStatusChange?: (updated: Trip) => void;
		now?: Date;
	}

	let { trip, onStatusChange, now = new Date() }: Props = $props();

	const status = $derived(deriveTripStatus(trip, now));

	let archiveDialogOpen = $state(false);
	// F002: PATCH-Fehler nicht still schlucken — sichtbares Error-Label.
	let errorMsg = $state<string | null>(null);
	// F003: Doppel-Klick-Schutz — Buttons während laufendem PATCH disablen.
	let isLoading = $state(false);

	async function sendStateUpdate(
		paused?: boolean,
		archived?: boolean
	): Promise<void> {
		const body: Record<string, boolean> = {};
		if (paused !== undefined) body.paused = paused;
		if (archived !== undefined) body.archived = archived;

		isLoading = true;
		try {
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) {
				throw new Error(`PATCH /state failed: ${res.status}`);
			}
			const updated: Trip = await res.json();
			// Erfolg: vorigen Fehler ausblenden.
			errorMsg = null;
			onStatusChange?.(updated);
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : String(e);
		} finally {
			isLoading = false;
		}
	}

	function handlePauseClick(): void {
		// Toggle: aktuell pausiert → resume, sonst pause.
		const nextPaused = status !== 'paused';
		void sendStateUpdate(nextPaused, undefined);
	}

	function handleArchiveClick(): void {
		archiveDialogOpen = true;
	}

	function handleArchiveCancel(): void {
		archiveDialogOpen = false;
	}

	function handleArchiveConfirm(): void {
		const nextArchived = status !== 'archived';
		archiveDialogOpen = false;
		void sendStateUpdate(undefined, nextArchived);
	}

	function handleDialogOpenChange(open: boolean): void {
		archiveDialogOpen = open;
	}
</script>

<header class="trip-header">
	<nav data-testid="trip-detail-breadcrumb" aria-label="Breadcrumb" class="breadcrumb">
		<a href="/trips" data-testid="trip-detail-breadcrumb-link-trips">Trips</a>
		<span aria-hidden="true"> / </span>
		<span data-testid="trip-detail-breadcrumb-current">
			{trip.shortcode ?? trip.name}
		</span>
	</nav>

	<div class="title-row">
		<h2 class="title">{trip.name}</h2>
		<TripStatusBadge {trip} {now} />
	</div>

	<div class="actions">
		{#if status !== 'archived'}
			<Button
				variant="outline"
				size="sm"
				data-testid="trip-detail-action-pause"
				onclick={handlePauseClick}
				disabled={isLoading}
			>
				{status === 'paused' ? 'Fortsetzen' : 'Pausieren'}
			</Button>
		{/if}
		<Button
			variant="outline"
			size="sm"
			data-testid="trip-detail-action-archive"
			onclick={handleArchiveClick}
			disabled={isLoading}
		>
			{status === 'archived' ? 'Reaktivieren' : 'Archivieren'}
		</Button>
	</div>
	{#if errorMsg}
		<p class="text-sm text-red-600" data-testid="trip-detail-action-error">{errorMsg}</p>
	{/if}
</header>

<Dialog.Root open={archiveDialogOpen} onOpenChange={handleDialogOpenChange}>
	<Dialog.Content data-testid="trip-detail-archive-confirm-dialog">
		<Dialog.Header>
			<Dialog.Title>
				{status === 'archived' ? 'Trip reaktivieren?' : 'Trip archivieren?'}
			</Dialog.Title>
			<Dialog.Description>
				{status === 'archived'
					? 'Der Trip wird aus dem Archiv zurückgeholt und ist wieder aktiv.'
					: 'Der Trip wird ins Archiv verschoben — er kann später reaktiviert werden.'}
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Button
				variant="outline"
				data-testid="trip-detail-archive-confirm-cancel"
				onclick={handleArchiveCancel}
			>
				Abbrechen
			</Button>
			<Button
				variant="default"
				data-testid="trip-detail-archive-confirm-yes"
				onclick={handleArchiveConfirm}
				disabled={isLoading}
			>
				Bestätigen
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<style>
	.trip-header {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
	.breadcrumb {
		font-size: 0.875rem;
		color: var(--g-muted, #666);
	}
	.breadcrumb a {
		color: inherit;
		text-decoration: underline;
	}
	.title-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.title {
		font-size: 1.5rem;
		font-weight: 700;
		margin: 0;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
</style>
