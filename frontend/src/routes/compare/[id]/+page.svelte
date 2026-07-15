<script lang="ts">
	// Issue #491 — Compare-Preset Detail-Seite.
	// Issue #493 — Mobile-Responsive: TopBar + MCompareActionSheet.
	// Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): der mobile Bespoke-
	// Block (2×2-5-Karten-Grid + flache Standort-Liste) entfaellt — CompareDetail
	// wird jetzt GENAU EINMAL gemountet und versorgt Desktop UND Mobile; die
	// Viewport-Umschaltung (4-Stat-2×2 statt 5-Stat-Leiste, CorridorEditorMobile
	// im Idealwerte-Tab) passiert INNERHALB von CompareTabs (matchMedia).
	import { Btn } from '$lib/components/atoms';
	import CompareDetail from '$lib/components/compare/CompareDetail.svelte';
	import CompareStatusPill from '$lib/components/compare/CompareStatusPill.svelte';
	import CompareKebab from '$lib/components/compare/CompareKebab.svelte';
	import { MCompareActionSheet } from '$lib/components/mobile';
	import {
		deriveStatusWithScheduleOverride,
		presetProfileLabel,
		compareLifecycleActions,
		isRuntimeExceeded
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { page } from '$app/state';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import MoreHorizontalIcon from '@lucide/svelte/icons/more-horizontal';

	let { data } = $props();

	// Staging-Fund SF-2 (CRITICAL, AC-37): der Hub (CompareTabs) haelt fuer die
	// Aktivierungs-Karte einen eigenen `localSchedule`-Zustand und PUT-Pfad
	// (ohne invalidateAll() — das wuerde die dortige eingefrorene-Prop-Baseline
	// mit frisch geladenen `data` kollidieren lassen). Diese Header-Status-Pille
	// las bislang AUSSCHLIESSLICH `data.preset`, das nur der Kebab-Pfad
	// (togglePause -> invalidateAll()) aktualisiert — nach einem Pausieren/
	// Aktivieren aus der Karte blieb die Pille auf dem alten Status stehen.
	// `scheduleOverride` wird vom CompareTabs-Callback gesetzt und verwirft
	// sich selbst, sobald `data` durch einen echten Reload (invalidateAll)
	// neu ankommt — die dann gelieferten Server-Daten sind wieder autoritativ.
	let scheduleOverride = $state<string | null>(null);
	$effect(() => {
		void data;
		scheduleOverride = null;
	});
	function handleScheduleChange(schedule: string): void {
		scheduleOverride = schedule;
	}

	let status = $derived(deriveStatusWithScheduleOverride(data.preset, scheduleOverride));
	// Issue #1250 Scheibe 3 (AC-12): Hub-Hinweis, wenn Auto-Pause wegen
	// ueberschrittenem end_date gegriffen hat.
	let runtimeExceeded = $derived(isRuntimeExceeded(data.preset));
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

	// Staging-Fund F004 (CRITICAL): kein eigenstaendiger fetch-Pfad mit vollem
	// Objekt-Spread aus `data.preset` mehr (Datenverlust-Risiko in BEIDE
	// Richtungen gegenueber Hub-internen Edits, s. Adversary-Proben
	// probe_kebab_vs_hub_stale_data.mjs / probe_kebab_vs_hub_reverse.mjs) —
	// delegiert stattdessen an denselben `handleToggleActive`-Pfad, den auch
	// die Aktivierungs-Karte im Versand-Tab nutzt (hubPutQueue + currentPreset-
	// Baseline). Kein invalidateAll() mehr noetig: die Pille zieht ueber
	// `onScheduleChange`/`scheduleOverride` mit (s. SF-2-Kommentar oben).
	let compareDetailRef: ReturnType<typeof CompareDetail> | undefined = $state();

	async function togglePause() {
		isPausing = true;
		pauseError = null;
		// Adversary Runde 6 (LOW): Ref-Fallback analog CompareDetail.svelte:24 —
		// ein (noch) undefined `compareDetailRef` faellt jetzt auf denselben
		// Fehlerpfad zurueck statt still (ohne pauseError) zu enden.
		const ok = (await compareDetailRef?.toggleActiveFromParent()) ?? false;
		if (!ok) pauseError = 'Status-Änderung fehlgeschlagen. Bitte versuche es erneut.';
		isPausing = false;
	}

	function handleAction(id: string) {
		if (id === 'edit' || id === 'setup') {
			window.location.href = `/compare/${data.preset.id}/edit`;
		} else if (id === 'pause' || id === 'resume') {
			// 'resume' kommt aus compareLifecycleActions() (Hub-Header, #1256 S3) —
			// selbe Toggle-Aktion wie 'pause' aus compareActions() (Listen-Kebab).
			void togglePause();
		} else if (id === 'send') {
			void handleTestSend();
		} else if (id === 'preview') {
			window.location.href = '/compare/' + data.preset.id + '?tab=vorschau';
		} else if (id === 'archive') {
			void archivePreset();
		} else if (id === 'delete' || id === 'trash') {
			// 'trash' kommt aus compareLifecycleActions() (Hub-Header, #1256 S3) —
			// selbe Lösch-Aktion wie 'delete' aus compareActions() (Listen-Kebab).
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
	<!-- Breadcrumb (Issue #582 + Bug #589). Issue #1256 S8c (AC-10): App-weiter
	     Extra-Krümel entfernt — Soll ist genau 2 Krümel (Soll: JSX:66-70). -->
	<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px">
		<a href="/compare" style="font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-3); text-decoration: none" class="breadcrumb-link">ORTS-VERGLEICHE</a>
		<span style="color: var(--g-ink-4); font-size: 11px">/</span>
		<span style="font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-4)">Hub</span>
	</div>

	<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 24px">
		<div style="min-width: 0; flex: 1">
			<div style="display: flex; align-items: center; gap: 12px">
				<h1 style="font-size: 30px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.1; margin: 0">{data.preset.name}</h1>
				<span style="flex-shrink: 0"><CompareStatusPill {status}/></span>
				{#if runtimeExceeded}
					<span data-testid="runtime-exceeded-hint" style="font-size: 12px; font-weight: 600; color: var(--g-bad)">Laufzeit überschritten</span>
				{/if}
			</div>
			<!-- Issue #1256 S8c (AC-11): profileLabel statt rohem preset.profil,
			     Leerfeld-Absicherung analog Mobile-Unterzeile unten (Soll: JSX:78-80). -->
			<div style="font-size: 14px; color: var(--g-ink-3); margin: 8px 0 18px">
				{data.preset.display_config?.region ?? '—'}{#if profileLabel}{' · '}{profileLabel}{/if}{' · '}{data.preset.location_ids.length} {data.preset.location_ids.length === 1 ? 'Ort' : 'Orte'}
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
			<CompareKebab {status} actions={compareLifecycleActions(status)} onSelect={handleAction} />
		</div>
	</div>

	{#if sendMsg}
		<div style="font-size: 14px; color: var(--g-ink-3); margin-bottom: 8px">{sendMsg}</div>
	{/if}
	{#if pauseError}
		<div style="font-size: 14px; color: var(--g-bad); margin-bottom: 8px">{pauseError}</div>
	{/if}
</div>

<!-- Mobile-TopBar (#493) — bleibt bespoke Seiten-Chrome, s. Modulkommentar oben -->
<div class="desktop:hidden flex flex-col gap-4 p-4">
	<!-- Issue #1256 S8c (AC-12): mobile Eyebrow-Zeile über dem Preset-Namen
	     (Soll: screen-compare-detail-mobile.jsx:51, Styling analog TopAppBar.svelte:56-61). -->
	<span class="mono block" style="font-size: 9px; color: var(--g-ink-muted); letter-spacing: 0.12em; text-transform: uppercase; line-height: 1;">Orts-Vergleich · Hub</span>
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
			{#if runtimeExceeded}
				<span data-testid="runtime-exceeded-hint" class="flex-shrink-0" style="font-size: 11px; font-weight: 600; color: var(--g-bad)">Laufzeit überschritten</span>
			{/if}
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
	     kein führender/doppelter " · " bei leerem/unbekanntem profil.
	     Staging-Befund: {' · '} statt " · " im Markup — Svelte trimmt sonst das
	     Leerzeichen vor {/if} weg ("Wandern ·0 Orte" statt "Wandern · 0 Orte"). -->
	<div class="text-sm text-[var(--g-ink-3)]">
		{#if data.preset.display_config?.region}{data.preset.display_config.region}{' · '}{/if}{#if profileLabel}{profileLabel}{' · '}{/if}{data.locations.length} {data.locations.length === 1 ? 'Ort' : 'Orte'}
	</div>
</div>

<!-- Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): CompareDetail wird
     GENAU EINMAL gemountet (weder im Desktop- noch im Mobile-Block oben) —
     versorgt beide Viewports, vermeidet Doppel-Fetches/doppelte
     hubPutQueue-Instanzen/doppelte testids (S4-F001-/S7-F004-Fehlerklasse).
     CompareTabs schaltet Monitoring-Streifen + Idealwerte-Tab intern via
     isMobileViewport (matchMedia) um. -->
<CompareDetail
	preset={data.preset}
	locations={data.locations}
	{initialTab}
	onScheduleChange={handleScheduleChange}
	bind:this={compareDetailRef}
/>

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

