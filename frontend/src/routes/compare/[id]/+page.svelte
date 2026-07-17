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
		compareDetailActions,
		isRuntimeExceeded
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { page } from '$app/state';
	import { createSaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { api } from '$lib/api';
	import { ACTIVITY_PROFILE_OPTIONS, type ActivityProfile, type ComparePreset } from '$lib/types';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import MoreHorizontalIcon from '@lucide/svelte/icons/more-horizontal';

	let { data } = $props();

	// Epic #1273 S2, Adversary-Fund (live gegen Staging, nicht durch Code-
	// Lesung auffindbar): `data` aus $props() ist NICHT tief-reaktiv fuer
	// Nested-Mutation — `data.preset = updated` erzeugte zwar eine neue
	// Objekt-Referenz, aber KEIN {@const}/$derived, das `currentPreset.X` liest,
	// hat das reaktiv mitbekommen (bewiesen: Name/Region "funktionierten" nur
	// zufaellig, weil der isEditingX-Toggle denselben Zweig neu mountet und
	// dabei `currentPreset.name` frisch auswertet — die Aktivitaetsprofil-
	// Kacheln haben keinen solchen Toggle und blieben sichtbar auf dem alten
	// Wert stehen, obwohl der PUT serverseitig erfolgreich war). Fix: echter
	// $state-Spiegel, exakt das Muster aus CompareTabs.svelte (`currentPreset
	// = $state<ComparePreset>(preset)` + Resync-$effect auf Prop-Referenz).
	let currentPreset = $state(data.preset);
	$effect(() => {
		currentPreset = data.preset;
	});

	// Epic #1273 S1: SaveStatus-Controller fuer den Hub — eine Instanz pro
	// Compare-Detail-Seite (kein Singleton!), analog tripSaveCtl in
	// routes/trips/[id]/+page.svelte:22. Wird an CompareDetail/CompareTabs
	// durchgereicht und dort manuell (nicht via schedule()) getrieben.
	const hubSaveCtl = createSaveStatus();

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

	let status = $derived(deriveStatusWithScheduleOverride(currentPreset, scheduleOverride));
	// Issue #1250 Scheibe 3 (AC-12): Hub-Hinweis, wenn Auto-Pause wegen
	// ueberschrittenem end_date gegriffen hat.
	let runtimeExceeded = $derived(isRuntimeExceeded(currentPreset));
	// Adversary-Finding F001: geguardetes Profil-Label für die mobile Kontext-
	// Unterzeile (Muster CompareTile.svelte:62) — leer bei unbekanntem/fehlendem profil.
	let profileLabel = $derived(presetProfileLabel(currentPreset.profil));

	// Epic #1273 S2 — Inline-Edit für Name/Region/Aktivitätsprofil im Hub
	// (Feature-Parität zum alten CompareEditor). Muster: TripHeader.svelte:33-54.
	// KRITISCH: Round-Trip-Spread beim PUT ({ ...currentPreset, <feld> }), sonst
	// setzt der Go-Handler (compare_preset.go:259-297) location_ids/empfaenger/
	// schedule/profil auf Zero-Value zurück (BUG-DATALOSS). Und: nach Erfolg
	// currentPreset MIT NEUER OBJEKT-REFERENZ ersetzen, damit der defensive
	// $effect in CompareTabs.svelte:821-826 currentPreset resynct (Cross-Tab-
	// Datenverlust-Schutz, AC-5). NIE ein Feld in-place mutieren.
	let editName = $state(currentPreset.name);
	let nameSaving = $state(false);
	let isEditingName = $state(false);
	let nameSaveError: string | null = $state(null);

	let editRegion = $state((currentPreset.display_config?.region as string) ?? '');
	let regionSaving = $state(false);
	let isEditingRegion = $state(false);
	let regionSaveError: string | null = $state(null);

	let profilSaving = $state(false);
	let profilSaveError: string | null = $state(null);

	function startNameEdit(): void {
		editName = currentPreset.name;
		nameSaveError = null;
		isEditingName = true;
	}
	function cancelNameEdit(): void {
		editName = currentPreset.name;
		nameSaveError = null;
		isEditingName = false;
	}
	async function saveName(): Promise<void> {
		nameSaving = true;
		nameSaveError = null;
		try {
			const updated = await api.put<ComparePreset>(`/api/compare/presets/${currentPreset.id}`, {
				...currentPreset,
				name: editName
			});
			currentPreset = updated;
			isEditingName = false;
		} catch (e: unknown) {
			nameSaveError = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
		} finally {
			nameSaving = false;
		}
	}

	function startRegionEdit(): void {
		editRegion = (currentPreset.display_config?.region as string) ?? '';
		regionSaveError = null;
		isEditingRegion = true;
	}
	function cancelRegionEdit(): void {
		editRegion = (currentPreset.display_config?.region as string) ?? '';
		regionSaveError = null;
		isEditingRegion = false;
	}
	async function saveRegion(): Promise<void> {
		regionSaving = true;
		regionSaveError = null;
		try {
			const updated = await api.put<ComparePreset>(`/api/compare/presets/${currentPreset.id}`, {
				...currentPreset,
				display_config: { ...currentPreset.display_config, region: editRegion }
			});
			currentPreset = updated;
			isEditingRegion = false;
		} catch (e: unknown) {
			regionSaveError = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
		} finally {
			regionSaving = false;
		}
	}

	async function saveProfil(value: ActivityProfile): Promise<void> {
		profilSaving = true;
		profilSaveError = null;
		try {
			const updated = await api.put<ComparePreset>(`/api/compare/presets/${currentPreset.id}`, {
				...currentPreset,
				profil: value
			});
			currentPreset = updated;
		} catch (e: unknown) {
			profilSaveError = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
		} finally {
			profilSaving = false;
		}
	}

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
			const res = await fetch(`/api/compare/presets/${currentPreset.id}/send`, { method: 'POST' });
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
			window.location.href = `/compare/${currentPreset.id}/edit`;
		} else if (id === 'pause' || id === 'resume') {
			// 'resume' kommt aus compareDetailActions() (Hub-Header, #1256 S3 + #1261) —
			// selbe Toggle-Aktion wie 'pause' aus compareActions() (Listen-Kebab).
			void togglePause();
		} else if (id === 'send') {
			void handleTestSend();
		} else if (id === 'preview') {
			window.location.href = '/compare/' + currentPreset.id + '?tab=vorschau';
		} else if (id === 'archive') {
			void archivePreset();
		} else if (id === 'delete' || id === 'trash') {
			// 'trash' kommt aus compareDetailActions() (Hub-Header, #1256 S3 + #1261) —
			// selbe Lösch-Aktion wie 'delete' aus compareActions() (Listen-Kebab).
			void deletePreset();
		}
	}

	async function archivePreset() {
		try {
			const res = await fetch(`/api/compare/presets/${currentPreset.id}/state`, {
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
			const res = await fetch(`/api/compare/presets/${currentPreset.id}`, { method: 'DELETE' });
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
				{#if isEditingName}
					<input type="text" data-testid="compare-hub-name-edit" bind:value={editName} aria-label="Name bearbeiten" style="font-size: 24px; font-weight: 600; padding: 4px 8px; border: 1px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card)" />
					<Btn variant="ghost" size="sm" data-testid="compare-hub-name-save" disabled={nameSaving} onclick={saveName}>{nameSaving ? '…' : 'Umbenennen'}</Btn>
					<Btn variant="ghost" size="sm" onclick={cancelNameEdit}>Abbrechen</Btn>
				{:else}
					<h1 style="font-size: 30px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.1; margin: 0">{currentPreset.name}</h1>
					<button type="button" data-testid="compare-hub-name-edit-toggle" aria-label="Name bearbeiten" onclick={startNameEdit} style="display: inline-flex; padding: 4px; color: var(--g-ink-3); cursor: pointer"><PencilIcon size={15} /></button>
				{/if}
				<span style="flex-shrink: 0"><CompareStatusPill {status}/></span>
				{#if runtimeExceeded}
					<span data-testid="runtime-exceeded-hint" style="font-size: 12px; font-weight: 600; color: var(--g-bad)">Laufzeit überschritten</span>
				{/if}
			</div>
			{#if nameSaveError}<div data-testid="compare-hub-name-save-error" role="alert" style="font-size: 13px; color: var(--g-bad); margin-top: 6px">{nameSaveError}</div>{/if}
			<!-- Issue #1256 S8c (AC-11): profileLabel statt rohem preset.profil,
			     Leerfeld-Absicherung analog Mobile-Unterzeile unten (Soll: JSX:78-80).
			     Epic #1273 S2: Region inline editierbar. -->
			<div style="font-size: 14px; color: var(--g-ink-3); margin: 8px 0 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
				{#if isEditingRegion}
					<input type="text" data-testid="compare-hub-region-edit" bind:value={editRegion} aria-label="Region bearbeiten" maxlength="60" style="font-size: 14px; padding: 3px 8px; border: 1px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card)" />
					<Btn variant="ghost" size="sm" data-testid="compare-hub-region-save" disabled={regionSaving} onclick={saveRegion}>{regionSaving ? '…' : 'Speichern'}</Btn>
					<Btn variant="ghost" size="sm" onclick={cancelRegionEdit}>Abbrechen</Btn>
				{:else}
					<span>{currentPreset.display_config?.region ?? '—'}</span>
					<button type="button" data-testid="compare-hub-region-edit-toggle" aria-label="Region bearbeiten" onclick={startRegionEdit} style="display: inline-flex; padding: 2px; color: var(--g-ink-3); cursor: pointer"><PencilIcon size={13} /></button>
					{#if profileLabel}<span>· {profileLabel}</span>{/if}<span>· {currentPreset.location_ids.length} {currentPreset.location_ids.length === 1 ? 'Ort' : 'Orte'}</span>
				{/if}
			</div>
			{#if regionSaveError}<div data-testid="compare-hub-region-save-error" role="alert" style="font-size: 13px; color: var(--g-bad); margin-bottom: 6px">{regionSaveError}</div>{/if}
			<!-- Epic #1273 S2: Aktivitätsprofil-Kacheln (Muster CompareEditor.svelte:1193-1233),
			     sofortiger Commit pro Klick (kein Zwischenschritt). -->
			<div style="display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 18px">
				{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
					{@const sel = currentPreset.profil === opt.value}
					<button
						type="button"
						data-testid={`compare-hub-profil-option-${opt.value}`}
						data-selected={sel ? 'true' : 'false'}
						disabled={profilSaving}
						onclick={() => saveProfil(opt.value)}
						style:padding="6px 12px"
						style:font-size="13px"
						style:cursor="pointer"
						style:background={sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}
						style:border={sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}
						style:border-radius="var(--g-r-3)"
						style:color={sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'}
					>{opt.label}</button>
				{/each}
			</div>
			{#if profilSaveError}<div data-testid="compare-hub-profil-save-error" role="alert" style="font-size: 13px; color: var(--g-bad); margin-bottom: 8px">{profilSaveError}</div>{/if}
		</div>

		<div style="display: flex; gap: 8px; flex-shrink: 0">
			{#if status === 'draft'}
				<Btn variant="primary" onclick={() => { window.location.href = `?tab=versand`; }}>Setup abschließen</Btn>
			{:else}
				<Btn variant="primary" onclick={handleTestSend} disabled={isSending}>
					{isSending ? 'Wird gesendet…' : 'Test senden'}
				</Btn>
				<!-- Issue #1261 (a): "Bearbeiten" war zuvor nur ueber den toten
				     handleAction('edit')-Zweig erreichbar — kein sichtbarer Einstieg. -->
				<Btn variant="outline" href="/compare/{currentPreset.id}/edit" data-testid="compare-detail-edit-button">Bearbeiten</Btn>
			{/if}
			<CompareKebab {status} actions={compareDetailActions(status)} onSelect={handleAction} />
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
		<span class="flex-1 flex items-center gap-2 min-w-0">
			{#if isEditingName}
				<input type="text" data-testid="compare-hub-name-edit" bind:value={editName} aria-label="Name bearbeiten" class="min-w-0 flex-1 font-semibold px-2 py-1 rounded-md" style="border: 1px solid var(--g-rule); background: var(--g-card)" />
				<Btn variant="ghost" size="sm" data-testid="compare-hub-name-save" disabled={nameSaving} onclick={saveName}>{nameSaving ? '…' : 'OK'}</Btn>
				<Btn variant="ghost" size="sm" onclick={cancelNameEdit}>×</Btn>
			{:else}
				<span class="font-semibold truncate">{currentPreset.name}</span>
				<button type="button" data-testid="compare-hub-name-edit-toggle" aria-label="Name bearbeiten" onclick={startNameEdit} class="flex-shrink-0 flex items-center justify-center min-h-[44px] min-w-[44px]" style="color: var(--g-ink-3)"><PencilIcon size={16} /></button>
			{/if}
			<span class="flex-shrink-0"><CompareStatusPill {status} /></span>
			{#if runtimeExceeded}
				<span data-testid="runtime-exceeded-hint" class="flex-shrink-0" style="font-size: 11px; font-weight: 600; color: var(--g-bad)">Laufzeit überschritten</span>
			{/if}
		</span>
		<a
			href="/compare/{currentPreset.id}/edit"
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
	<div class="text-sm text-[var(--g-ink-3)] flex items-center gap-2 flex-wrap">
		{#if isEditingRegion}
			<input type="text" data-testid="compare-hub-region-edit" bind:value={editRegion} aria-label="Region bearbeiten" maxlength="60" class="min-w-0 flex-1 px-2 py-1 rounded-md text-sm" style="border: 1px solid var(--g-rule); background: var(--g-card)" />
			<Btn variant="ghost" size="sm" data-testid="compare-hub-region-save" disabled={regionSaving} onclick={saveRegion}>{regionSaving ? '…' : 'OK'}</Btn>
			<Btn variant="ghost" size="sm" onclick={cancelRegionEdit}>×</Btn>
		{:else}
			<span>{currentPreset.display_config?.region ?? '—'}</span>
			<button type="button" data-testid="compare-hub-region-edit-toggle" aria-label="Region bearbeiten" onclick={startRegionEdit} class="flex items-center" style="color: var(--g-ink-3)"><PencilIcon size={13} /></button>
			{#if profileLabel}<span>{' · '}{profileLabel}</span>{/if}<span>{' · '}{data.locations.length} {data.locations.length === 1 ? 'Ort' : 'Orte'}</span>
		{/if}
	</div>
	{#if nameSaveError}<div data-testid="compare-hub-name-save-error" role="alert" class="text-sm" style="color: var(--g-bad)">{nameSaveError}</div>{/if}
	{#if regionSaveError}<div data-testid="compare-hub-region-save-error" role="alert" class="text-sm" style="color: var(--g-bad)">{regionSaveError}</div>{/if}
	<!-- Epic #1273 S2: Aktivitätsprofil-Kacheln (Mobile-Parität) -->
	<div class="flex gap-2 flex-wrap">
		{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
			{@const sel = currentPreset.profil === opt.value}
			<button
				type="button"
				data-testid={`compare-hub-profil-option-${opt.value}`}
				data-selected={sel ? 'true' : 'false'}
				disabled={profilSaving}
				onclick={() => saveProfil(opt.value)}
				class="rounded-md"
				style:padding="6px 12px"
				style:font-size="13px"
				style:background={sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}
				style:border={sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}
				style:color={sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'}
			>{opt.label}</button>
		{/each}
	</div>
	{#if profilSaveError}<div data-testid="compare-hub-profil-save-error" role="alert" class="text-sm" style="color: var(--g-bad)">{profilSaveError}</div>{/if}
</div>

<!-- Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): CompareDetail wird
     GENAU EINMAL gemountet (weder im Desktop- noch im Mobile-Block oben) —
     versorgt beide Viewports, vermeidet Doppel-Fetches/doppelte
     hubPutQueue-Instanzen/doppelte testids (S4-F001-/S7-F004-Fehlerklasse).
     CompareTabs schaltet Monitoring-Streifen + Idealwerte-Tab intern via
     isMobileViewport (matchMedia) um. -->
<CompareDetail
	preset={currentPreset}
	locations={data.locations}
	{initialTab}
	onScheduleChange={handleScheduleChange}
	saveController={hubSaveCtl}
	bind:this={compareDetailRef}
/>

<!-- Bottom-Sheet für mobile Aktionen (#493) -->
<MCompareActionSheet
	open={actionSheetOpen}
	onClose={() => (actionSheetOpen = false)}
	{status}
	onAction={handleAction}
	presetName={currentPreset.name}
/>

<style>
	.breadcrumb-link:hover {
		text-decoration: underline;
	}
</style>

