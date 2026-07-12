<script lang="ts">
	// Issue #491 — Compare-Preset Detail-Seite.
	// Issue #493 — Mobile-Responsive: TopBar + 2×2-Grid + MCompareActionSheet.
	import { Btn, Card, KV, Dot } from '$lib/components/atoms';
	import CompareDetail from '$lib/components/compare/CompareDetail.svelte';
	import CompareStatusPill from '$lib/components/compare/CompareStatusPill.svelte';
	import CompareKebab from '$lib/components/compare/CompareKebab.svelte';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	import { MCompareActionSheet } from '$lib/components/mobile';
	import {
		deriveStatusFromPreset,
		STATUS_MAP,
		presetScheduleLabel,
		presetProfileLabel,
		formatLastSent,
		computePauseToggle,
		channelCountLabel
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { page } from '$app/state';
	import { invalidateAll } from '$app/navigation';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import MoreHorizontalIcon from '@lucide/svelte/icons/more-horizontal';

	let { data } = $props();
	let status = $derived(deriveStatusFromPreset(data.preset));
	let statusInfo = $derived(STATUS_MAP[status]);
	// Adversary-Finding F001: geguardetes Profil-Label für die mobile Kontext-
	// Unterzeile (Muster CompareTile.svelte:62) — leer bei unbekanntem/fehlendem profil.
	let profileLabel = $derived(presetProfileLabel(data.preset.profil));

	// Issue #517 — ?tab=-Query-Parameter lesen und an CompareDetail/CompareTabs weitergeben.
	const initialTab = $derived(page.url.searchParams.get('tab') ?? 'uebersicht');

	let actionSheetOpen = $state(false);

	// Issue #528 — Status-abhängige Header-Primäraktion.
	let isSending = $state(false);
	let sendMsg = $state<string | null>(null);

	async function handleTestSend() {
		isSending = true;
		sendMsg = null;
		try {
			const res = await fetch(`/api/compare/presets/${data.preset.id}/send`, { method: 'POST' });
			sendMsg = res.ok ? 'Test-Briefing gesendet' : 'Fehler beim Senden';
		} catch {
			sendMsg = 'Netzwerkfehler';
		} finally {
			isSending = false;
		}
	}

	let isPausing = $state(false);
	let pauseError = $state<string | null>(null);

	async function togglePause() {
		isPausing = true;
		pauseError = null;
		const next = computePauseToggle(data.preset);
		try {
			const res = await fetch(`/api/compare/presets/${data.preset.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ ...data.preset, ...next })
			});
			if (!res.ok) throw new Error(`PUT failed: ${res.status}`);
			await invalidateAll();
		} catch {
			pauseError = 'Status-Änderung fehlgeschlagen. Bitte versuche es erneut.';
		} finally {
			isPausing = false;
		}
	}

	function handleAction(id: string) {
		if (id === 'edit' || id === 'setup') {
			window.location.href = `/compare/${data.preset.id}/edit`;
		} else if (id === 'pause') {
			void togglePause();
		} else if (id === 'send') {
			void handleTestSend();
		} else if (id === 'preview') {
			window.location.href = '/compare/' + data.preset.id + '?tab=vorschau';
		} else if (id === 'archive') {
			void archivePreset();
		} else if (id === 'delete') {
			void deletePreset();
		}
	}

	async function archivePreset() {
		try {
			const res = await fetch(`/api/compare/presets/${data.preset.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived: true })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			window.location.href = '/compare';
		} catch {
			sendMsg = 'Archivieren fehlgeschlagen.';
		}
	}

	async function deletePreset() {
		try {
			const res = await fetch(`/api/compare/presets/${data.preset.id}`, { method: 'DELETE' });
			if (!res.ok) throw new Error(`DELETE failed: ${res.status}`);
			window.location.href = '/compare';
		} catch {
			sendMsg = 'Löschen fehlgeschlagen.';
		}
	}
</script>

<!-- Desktop-Layout (#491, #582) — full-width Header nach JSX-Vorlage -->
<div class="hidden desktop:block" style="position: relative; padding: 22px 40px 0; border-bottom: 1px solid var(--g-rule)">
	<!-- Breadcrumb (Issue #582 + Bug #589) -->
	<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px">
		<a href="/" style="font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-4); text-decoration: none" class="breadcrumb-link">WORKSPACE</a>
		<span style="color: var(--g-ink-4); font-size: 11px"> · </span>
		<a href="/compare" style="font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-3); text-decoration: none" class="breadcrumb-link">ORTS-VERGLEICHE</a>
		<span style="color: var(--g-ink-4); font-size: 11px">/</span>
		<span style="font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-4)">Hub</span>
	</div>

	<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 24px">
		<div style="min-width: 0; flex: 1">
			<div style="display: flex; align-items: center; gap: 12px">
				<h1 style="font-size: 30px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.1; margin: 0">{data.preset.name}</h1>
				<span style="flex-shrink: 0"><CompareStatusPill {status}/></span>
			</div>
			<div style="font-size: 14px; color: var(--g-ink-3); margin: 8px 0 18px">
				{data.preset.display_config?.region ?? '—'} · {data.preset.profil} · {data.preset.location_ids.length} {data.preset.location_ids.length === 1 ? 'Ort' : 'Orte'}
			</div>
		</div>

		<div style="display: flex; gap: 8px; flex-shrink: 0">
			{#if status === 'draft'}
				<Btn variant="primary" onclick={() => { window.location.href = `?tab=versand`; }}>Setup abschließen</Btn>
			{:else}
				<Btn variant="primary" onclick={handleTestSend} disabled={isSending}>
					{isSending ? 'Wird gesendet…' : 'Test senden'}
				</Btn>
			{/if}
			<CompareKebab {status} onSelect={handleAction} />
		</div>
	</div>

	{#if sendMsg}
		<div style="font-size: 14px; color: var(--g-ink-3); margin-bottom: 8px">{sendMsg}</div>
	{/if}
	{#if pauseError}
		<div style="font-size: 14px; color: var(--g-bad); margin-bottom: 8px">{pauseError}</div>
	{/if}

	<CompareDetail preset={data.preset} locations={data.locations} {initialTab} />
</div>

<!-- Mobile-Layout (#493) -->
<div class="desktop:hidden flex flex-col gap-4 p-4">
	<!-- TopBar -->
	<div class="flex items-center gap-2 min-h-[44px]">
		<a
			href="/compare"
			class="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-md"
			aria-label="Zurück zur Übersicht"
		>
			<ArrowLeftIcon size={20} />
		</a>
		<span class="flex-1 flex items-center gap-3 min-w-0">
			<span class="font-semibold truncate">{data.preset.name}</span>
			<span class="flex-shrink-0"><CompareStatusPill {status} /></span>
		</span>
		<a
			href="/compare/{data.preset.id}/edit"
			class="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-md"
			aria-label="Bearbeiten"
		>
			<PencilIcon size={18} />
		</a>
		<button
			type="button"
			class="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-md"
			aria-label="Weitere Aktionen"
			onclick={() => (actionSheetOpen = true)}
		>
			<MoreHorizontalIcon size={20} />
		</button>
	</div>

	<!-- Kontext-Unterzeile (Fix 4, Design-Fidelity 2026-07) -->
	<!-- Adversary-Finding F001: profileLabel geguardet (Muster CompareTile.svelte:174) —
	     kein führender/doppelter " · " bei leerem/unbekanntem profil. -->
	<div class="text-sm text-[var(--g-ink-3)]">
		{#if data.preset.display_config?.region}{data.preset.display_config.region} · {/if}{#if profileLabel}{profileLabel} · {/if}{data.locations.length} {data.locations.length === 1 ? 'Ort' : 'Orte'}
	</div>

	<!-- Monitoring 2×2-Grid -->
	<div class="grid grid-cols-2 gap-3">
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Status</div>
			<div class="text-sm mt-1">{statusInfo.label}</div>
		</Card>
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Nächster</div>
			<div class="text-sm mt-1">{presetScheduleLabel(data.preset)}</div>
		</Card>
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Zuletzt</div>
			<div class="text-sm mt-1">{formatLastSent(data.preset.letzter_versand)}</div>
		</Card>
		<Card padding={14}>
			<div class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Kanäle</div>
			<div class="text-sm mt-1 truncate">{channelCountLabel((data.preset.empfaenger ?? []).length)}</div>
		</Card>
	</div>

	<!-- Standort-Liste -->
	{#if data.locations && data.locations.length > 0}
		{#each data.locations as loc, i (loc.id)}
			<CompareLocationRow {loc} index={i + 1} dense={true} />
		{/each}
	{:else}
		<p class="text-sm text-[var(--g-ink-3)]">Noch keine Orte ausgewählt.</p>
	{/if}
</div>

<!-- Bottom-Sheet für mobile Aktionen (#493) -->
<MCompareActionSheet
	open={actionSheetOpen}
	onClose={() => (actionSheetOpen = false)}
	{status}
	onAction={handleAction}
	presetName={data.preset.name}
/>

<style>
	.breadcrumb-link:hover {
		text-decoration: underline;
	}
</style>

