<script lang="ts">
	// CompareNewEditor — Progressive-Tab-Anlege-Editor für /compare/new.
	// Epic #1301 Scheibe F2a. Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
	//
	// Struktureller Spiegel von trip-new/TripNewEditor.svelte (#622): eigene
	// Anlege-Shell je Domäne (ADR-0029), zusammengesetzt aus den GETEILTEN
	// Organismen (Step2Orte, WeatherMetricsTab, CorridorEditor(Mobile),
	// CompareHourlyLayoutControls, AlarmeTab, VersandTab). Reine Freischalt-Logik
	// in compareNewLogic.ts. Lokaler CompareWizardState (Context), EIN POST bei
	// „Briefing aktivieren" via wiz.saveNewPreset() — kein Backend-Change.
	//
	// Der Alt-Editor CompareEditor.svelte bleibt unangetastet als Rollback-Punkt
	// (AC-10, Löschung ist F2b). Testid-Familien 1:1 erhalten (E2E-Verträge).
	// Safari-Factory-Pattern für alle Handler (CLAUDE.md).

	import { getContext, onMount } from 'svelte';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import { Field } from '$lib/components/molecules';
	import {
		ACTIVITY_PROFILE_OPTIONS,
		toCompareProfile,
		type ActivityProfile,
		type Location,
		type Group
	} from '$lib/types';
	import type { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import { PROFILE_METRICS_WITH_SCALES, type ProfileKey } from '$lib/components/compare/compareMetricDefs';
	import { api } from '$lib/api.js';
	import {
		unlockedTabs,
		doneTabs,
		progressCount,
		canActivate,
		type CompareNewTabId,
		type CompareNewProgress
	} from './compareNewLogic.ts';
	import Step2Orte from '$lib/components/compare/steps/Step2Orte.svelte';
	import { groupLocations } from '$lib/components/compare/locationHelpers';
	import WeatherMetricsTab from '$lib/components/shared/WeatherMetricsTab.svelte';
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	import CompareHourlyLayoutControls from '$lib/components/shared/CompareHourlyLayoutControls.svelte';
	import AlarmeTab from '$lib/components/shared/AlarmeTab.svelte';
	import VersandTab from '$lib/components/shared/VersandTab.svelte';
	import Toast from '$lib/components/mobile/Toast.svelte';
	import MBtn from '$lib/components/mobile/MBtn.svelte';
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	import { topAppBarStore } from '$lib/stores/topAppBar.svelte';

	interface Props {
		locations?: Location[];
		groups?: Group[];
	}
	let { locations = [], groups }: Props = $props();

	const wiz = getContext<CompareWizardState>('compare-wizard-state');

	// ── Tab-Definitionen (7 Tabs, Spec-Tabelle) ───────────────────────────────
	const TAB_DEFS: { id: CompareNewTabId; label: string; lockHint: string | null }[] = [
		{ id: 'vergleich', label: 'Vergleich', lockHint: null },
		{ id: 'orte', label: 'Orte', lockHint: 'erst Vergleich benennen' },
		{ id: 'metriken', label: 'Wetter-Metriken', lockHint: 'erst mind. 2 Orte auswählen' },
		{ id: 'idealwerte', label: 'Wertebereiche', lockHint: 'erst Wetter-Metriken öffnen' },
		{ id: 'layout', label: 'Layout', lockHint: 'erst Wertebereiche öffnen' },
		{ id: 'alarme', label: 'Alarme', lockHint: 'erst Layout öffnen' },
		{ id: 'versand', label: 'Versand', lockHint: 'erst Alarme öffnen' }
	];

	// ── Visited-Flags (Tab-Besuch → nächster Tab frei; nie zurückgesetzt) ──────
	let metrikenVisited = $state(false);
	let idealsVisited = $state(false);
	let layoutVisited = $state(false);
	let alarmeVisited = $state(false);
	let versandVisited = $state(false);

	let activeTab = $state<CompareNewTabId>('vergleich');

	// Echte Viewport-Erkennung (Muster #932/#1231 Slice 4): nur die
	// Wertebereiche-/Metriken-Zweige mounten viewport-exklusiv, damit nicht
	// Desktop- UND Mobile-Editor gleichzeitig in `wiz` schreiben.
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	// ── Abgeleitete Freischaltung (reine compareNewLogic) ──────────────────────
	const progress = $derived<CompareNewProgress>({
		name: wiz.name,
		pickedCount: wiz.pickedIds.length,
		metrikenVisited,
		idealsVisited,
		layoutVisited,
		alarmeVisited,
		versandVisited
	});
	const unlocked = $derived(unlockedTabs(progress));
	const done = $derived(doneTabs(progress));
	const doneCount = $derived(progressCount(done));
	const canActivateNow = $derived(canActivate(done));

	const canContinue = $derived(wiz.name.trim().length > 0);
	const orteContinueReady = $derived(wiz.pickedIds.length >= 2);
	const alarmeNotifyCount = $derived(wiz.corridors.filter((c) => c.notify).length);

	// ── Gruppen (App-Group-Entity #301) — lazy beim ERSTEN Orte-Besuch ─────────
	let ceGroups = $state<Group[]>(groups ?? []);
	let ceGroupsLoadStarted = groups !== undefined;
	async function ceLoadGroups(): Promise<void> {
		try {
			ceGroups = await api.get<Group[]>('/api/groups');
		} catch {
			/* Gruppen optional — Bibliothek fällt auf „Weitere" zurück */
		}
	}
	$effect(() => {
		if (activeTab === 'orte' && !ceGroupsLoadStarted) {
			ceGroupsLoadStarted = true;
			void ceLoadGroups();
		}
	});

	const mobileLibraryGroups = $derived.by(() => {
		const { sections, ungrouped } = groupLocations(locations, ceGroups);
		const result: [string, Location[]][] = [];
		for (const s of sections) if (s.locations.length > 0) result.push([s.group.name, s.locations]);
		if (ungrouped.length > 0) result.push(['Weitere', ungrouped]);
		return result;
	});

	// ── Tab-Wechsel + visited-Kaskade ──────────────────────────────────────────
	function switchTab(id: CompareNewTabId) {
		if (!unlocked.has(id)) return;
		activeTab = id;
		if (id === 'metriken') metrikenVisited = true;
		if (id === 'idealwerte') idealsVisited = true;
		if (id === 'layout') layoutVisited = true;
		if (id === 'alarme') alarmeVisited = true;
		if (id === 'versand') versandVisited = true;
	}
	function makeTabHandler(id: CompareNewTabId) {
		return () => switchTab(id);
	}
	function makeContinueHandler(id: CompareNewTabId) {
		return () => switchTab(id);
	}
	function jumpToWertebereiche() {
		switchTab('idealwerte');
	}

	function selectProfile(value: ActivityProfile) {
		wiz.activityProfile = value;
	}
	function profileMetricsLabel(value: ActivityProfile): string {
		const key = toCompareProfile(value) as ProfileKey;
		return PROFILE_METRICS_WITH_SCALES[key].map((m) => m.label).join(' · ');
	}

	// ── „Briefing aktivieren" — genau EIN POST (saveNewPreset), dann Redirect ──
	function handleActivate() {
		if (!canActivateNow) return;
		void wiz.saveNewPreset();
	}

	// ── Mobile-only State ──────────────────────────────────────────────────────
	let mobileLibraryOpen = $state(false);
	let lockToastMsg = $state('');
	let lockToastVisible = $state(false);
	let _lockToastTimer: ReturnType<typeof setTimeout> | null = null;
	function showLockToast(msg: string) {
		lockToastMsg = msg;
		lockToastVisible = true;
		if (_lockToastTimer) clearTimeout(_lockToastTimer);
		_lockToastTimer = setTimeout(() => { lockToastVisible = false; }, 2000);
	}
	function handleMobileTabClick(id: CompareNewTabId) {
		if (!unlocked.has(id)) {
			showLockToast(TAB_DEFS.find((t) => t.id === id)?.lockHint ?? 'Tab gesperrt');
			return;
		}
		switchTab(id);
	}
	function handleMobileNext() {
		const idx = TAB_DEFS.findIndex((t) => t.id === activeTab);
		if (activeTab === 'versand') {
			handleActivate();
		} else if (idx >= 0 && idx < TAB_DEFS.length - 1) {
			switchTab(TAB_DEFS[idx + 1].id);
		}
	}

	// ── Mobile: EINE globale Design-Kopfleiste befüllen (AC-15-Muster) ─────────
	$effect(() => {
		topAppBarStore.set({
			title: TAB_DEFS.find((t) => t.id === activeTab)?.label ?? 'Vergleich',
			eyebrow: wiz.name.trim() || 'Neuer Vergleich',
			leftIcon: 'back',
			backHref: '/compare',
			right: topAppBarActivate
		});
		return () => topAppBarStore.reset();
	});
</script>

<!-- Mobile App-Bar: rechte Aktion „…"/„Aktivieren" (analog CompareEditor). -->
{#snippet topAppBarActivate()}
	<button
		type="button"
		data-testid="top-app-bar-activate"
		disabled={!canActivateNow}
		onclick={handleActivate}
		style="height: 44px; padding: 0 14px; border: none; background: transparent; color: {canActivateNow ? 'var(--g-accent)' : 'var(--g-ink-4)'}; font-weight: 600; font-size: 14px; cursor: {canActivateNow ? 'pointer' : 'default'}; font-family: var(--g-font-sans); flex-shrink: 0;"
	>{canActivateNow ? 'Aktivieren' : '…'}</button>
{/snippet}

<!-- Create-Aktivierungs-Banner als Snippet-Prop für VersandTab (1:1 Muster). -->
{#snippet versandActivationBanner()}
	<div
		data-testid="compare-step5-activation-banner"
		data-ready={versandVisited ? 'true' : 'false'}
		class="rounded-md p-4 text-white text-sm"
		style:background={versandVisited ? 'var(--g-good)' : 'var(--g-ink)'}
	>
		<div class="mono" style:font-size="10px" style:letter-spacing="0.12em" style:text-transform="uppercase" style:color="rgba(255,255,255,0.55)" style:margin-bottom="4px">Bereit zum Aktivieren</div>
		<div style:font-size="15px" style:font-weight="600">„{wiz.name || 'Neuer Vergleich'}" · {wiz.pickedIds?.length ?? 0} Orte</div>
		<div style:font-size="12.5px" style:color="rgba(255,255,255,0.75)" style:margin-top="4px" style:line-height="1.5">
			{#if versandVisited}Versand konfiguriert — klicke „Briefing aktivieren".{:else}Versand einrichten zum Aktivieren.{/if}
		</div>
	</div>
{/snippet}

<div data-testid="compare-editor" style:position="relative" style:min-height="100%" style:background="var(--g-paper)">
<!-- ══════════════════ Desktop ══════════════════ -->
<div class="cm-desktop">
	<TopoBg opacity={0.12}>
		<!-- Breadcrumb + Aktionen -->
		<div style:position="relative" style:padding="14px 40px" style:border-bottom="1px solid var(--g-rule-soft)" style:display="flex" style:justify-content="space-between" style:align-items="center">
			<div class="mono" style:font-size="11px" style:color="var(--g-ink-3)" style:letter-spacing="0.06em">
				<span style:opacity="0.6">Orts-Vergleiche</span>
				<span style:margin="0 8px">/</span>
				<span style:color="var(--g-ink)">Neuer Vergleich</span>
			</div>
			<div style:display="flex" style:gap="8px" style:align-items="center">
				{#if !canActivateNow}
					<span class="mono" style:font-size="10.5px" style:color="var(--g-ink-4)">Versand einrichten zum Aktivieren</span>
				{/if}
				<Btn variant="ghost" size="sm" href="/compare">Abbrechen</Btn>
				<Btn
					data-testid="compare-editor-activate"
					variant={canActivateNow ? 'primary' : 'quiet'}
					size="sm"
					disabled={!canActivateNow}
					onclick={handleActivate}
					style={canActivateNow ? '' : 'opacity:0.4; cursor:not-allowed'}
				>Briefing aktivieren</Btn>
			</div>
		</div>

		<!-- Hero + Fortschrittsbalken (7 Segmente) -->
		<div style:position="relative" style:padding="20px 40px 14px">
			<Eyebrow>Neuer Orts-Vergleich</Eyebrow>
			<h1 style:font-size="32px" style:font-weight="600" style:letter-spacing="-0.02em" style:margin="4px 0 0" style:line-height="1.1" style:color={wiz.name.trim() ? 'var(--g-ink)' : 'var(--g-ink-4)'}>
				{wiz.name.trim() || 'Noch kein Name'}
			</h1>
			<div data-testid="compare-editor-progress" style:display="flex" style:align-items="center" style:gap="10px" style:margin-top="7px">
				<div style:display="flex" style:gap="3px">
					{#each TAB_DEFS as t (t.id)}
						<div data-testid="compare-editor-progress-segment" style:width="24px" style:height="3px" style:border-radius="2px" style:background={done.has(t.id) ? 'var(--g-accent)' : 'var(--g-rule)'} style:transition="background 350ms"></div>
					{/each}
				</div>
				<span class="mono" style:font-size="10.5px" style:color="var(--g-ink-4)" style:letter-spacing="0.04em">
					{doneCount === 0 ? 'Noch nichts eingerichtet' : `${doneCount} / ${TAB_DEFS.length} Abschnitte eingerichtet`}
				</span>
			</div>
		</div>

		<!-- Tab-Bar -->
		<div style:border-bottom="1px solid var(--g-rule)" style:padding="0 40px" style:display="flex" style:gap="0" style:overflow-x="auto">
			{#each TAB_DEFS as t (t.id)}
				{@const on = t.id === activeTab}
				{@const open = unlocked.has(t.id)}
				{@const isDone = done.has(t.id) && !on}
				<button
					data-testid={`compare-editor-tab-${t.id}`}
					data-active={on ? 'true' : 'false'}
					data-locked={open ? 'false' : 'true'}
					data-done={done.has(t.id) ? 'true' : 'false'}
					type="button"
					onclick={makeTabHandler(t.id)}
					title={!open && t.lockHint ? `Gesperrt — ${t.lockHint}` : undefined}
					style:padding="12px 16px" style:cursor={open ? 'pointer' : 'not-allowed'} style:background="none" style:border="none"
					style:border-bottom={on ? '2px solid var(--g-accent)' : '2px solid transparent'} style:margin-bottom="-1px"
					style:font-family="var(--g-font-sans)" style:font-size="13px" style:font-weight={on ? 600 : 500}
					style:color={on ? 'var(--g-ink)' : open ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}
					style:display="flex" style:align-items="center" style:gap="5px" style:white-space="nowrap"
					style:opacity={open ? 1 : 0.34} style:transition="opacity 250ms, color 200ms" style:user-select="none"
				>
					{t.label}
					{#if isDone}
						<span class="mono" style:font-size="10px" style:font-weight="700" style:padding="2px 5px" style:border-radius="3px" style:background="rgba(61,107,58,0.12)" style:color="var(--g-good)">✓</span>
					{/if}
					{#if !open}
						<span class="mono" style:font-size="10px" style:color="var(--g-ink-4)" style:opacity="0.7">⊘</span>
					{/if}
				</button>
			{/each}
		</div>
	</TopoBg>

	<!-- Tab-Panel -->
	{#if activeTab === 'vergleich'}
		<div style:position="relative" style:padding="28px 40px 60px">
			<TopoBg opacity={0.1}>
				<div style:position="relative" style:max-width="640px">
					<Eyebrow style="margin-bottom: 14px">Eckdaten</Eyebrow>
					<Field label="Name des Vergleichs" hint="Erscheint im Mail-Betreff. Kurz & wiedererkennbar.">
						<input data-testid="compare-editor-name" type="text" maxlength="80" placeholder="z.B. Skitouren Hochkönig" bind:value={wiz.name} class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]" />
					</Field>
					<Field label="Region" side="optional · max 60">
						<input data-testid="compare-editor-region" type="text" maxlength="60" placeholder="z.B. Hochkönig · Salzburger Land" bind:value={wiz.region} class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]" />
					</Field>
					<Eyebrow style="margin-bottom: 12px; margin-top: 28px">Aktivitätsprofil</Eyebrow>
					<div style:font-size="13px" style:color="var(--g-ink-3)" style:margin-bottom="14px">
						Bestimmt, welche Wetter-Metriken verglichen werden. Die Wertebereiche legst du in den nächsten Tabs fest.
					</div>
					<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="10px">
						{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
							{@const sel = wiz.activityProfile === opt.value}
							<button data-testid={`compare-editor-profile-${opt.value}`} data-selected={sel ? 'true' : 'false'} type="button" onclick={() => selectProfile(opt.value)}
								style:text-align="left" style:cursor="pointer" style:padding="14px 16px"
								style:background={sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}
								style:border={sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}
								style:border-radius="var(--g-r-3)" style:font-family="var(--g-font-sans)">
								<div style:font-size="14px" style:font-weight="600" style:color={sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'} style:margin-bottom="4px">{opt.label}</div>
								<div class="mono" style:font-size="11px" style:color="var(--g-ink-3)" style:margin-top="4px">{profileMetricsLabel(opt.value)}</div>
							</button>
						{/each}
					</div>
					<div style:margin-top="28px" style:padding-top="20px" style:border-top="1px solid var(--g-rule)" style:display="flex" style:justify-content="flex-end" style:align-items="center" style:gap="12px">
						{#if !canContinue}<span class="mono" style:font-size="11px" style:color="var(--g-ink-4)">⊘ Name fehlt</span>{/if}
						<Btn data-testid="compare-editor-continue-orte" variant={canContinue ? 'accent' : 'quiet'} size="md" disabled={!canContinue} onclick={() => canContinue && switchTab('orte')}>Orte hinzufügen →</Btn>
					</div>
				</div>
			</TopoBg>
		</div>
	{:else if activeTab === 'orte'}
		<Step2Orte {locations} groups={ceGroups} />
		<div class="ce-cta-foot" style:max-width="980px">
			<div class="ce-cta-row">
				{#if !orteContinueReady}<span class="mono ce-cta-hint">⊘ min. 2 Orte auswählen</span>{/if}
				<Btn data-testid="compare-editor-continue-metriken" variant={orteContinueReady ? 'accent' : 'quiet'} size="md" disabled={!orteContinueReady} onclick={() => orteContinueReady && switchTab('metriken')} style={orteContinueReady ? '' : 'opacity:0.45; cursor:not-allowed'}>Wetter-Metriken →</Btn>
			</div>
		</div>
	{:else if activeTab === 'metriken'}
		{#if !isMobileViewport}
			<WeatherMetricsTab context="vergleich" {wiz} />
		{/if}
		<div class="ce-cta-foot" style:max-width="1040px">
			<div class="ce-cta-row">
				<Btn data-testid="compare-editor-continue-idealwerte" variant="accent" size="md" onclick={makeContinueHandler('idealwerte')}>Wertebereiche festlegen →</Btn>
			</div>
		</div>
	{:else if activeTab === 'idealwerte'}
		{#if !isMobileViewport}
			<CorridorEditor context="vergleich" />
		{/if}
		<div class="ce-cta-foot" style:max-width="1040px">
			<div class="ce-cta-row">
				<Btn data-testid="compare-editor-continue-layout" variant="accent" size="md" onclick={makeContinueHandler('layout')}>Layout einrichten →</Btn>
			</div>
		</div>
	{:else if activeTab === 'layout'}
		<div style:padding="28px 40px 20px" style:max-width="760px">
			<Eyebrow style="margin-bottom: 8px">Stundenverlauf</Eyebrow>
			<p class="mono" style:font-size="12px" style:color="var(--g-ink-3)" style:margin-bottom="18px" style:line-height="1.55">
				Lege fest, ob die Vergleichs-Mail einen stündlichen Detailverlauf enthält und welche Metriken darin erscheinen.
			</p>
			<CompareHourlyLayoutControls {wiz} />
		</div>
		<div class="ce-cta-foot" style:max-width="1100px">
			<div class="ce-cta-row">
				<Btn data-testid="compare-editor-continue-alarme" variant="accent" size="md" onclick={makeContinueHandler('alarme')}>Alarme einrichten →</Btn>
			</div>
		</div>
	{:else if activeTab === 'alarme'}
		<AlarmeTab context="vergleich" {wiz} notifyCount={alarmeNotifyCount} onJumpToWertebereiche={jumpToWertebereiche} />
		<div class="ce-cta-foot" style:max-width="1100px">
			<div class="ce-cta-row">
				<Btn data-testid="compare-editor-continue-versand" variant="accent" size="md" onclick={makeContinueHandler('versand')}>Versand einrichten →</Btn>
			</div>
		</div>
	{:else if activeTab === 'versand'}
		<VersandTab context="vergleich" {wiz} activation={versandActivationBanner} />
	{/if}
</div><!-- /.cm-desktop -->

<!-- ══════════════════ Mobile ══════════════════ -->
<div class="cm-mobile" style="position: relative; min-height: 100vh; display: flex; flex-direction: column;">
	{#if lockToastVisible}
		<Toast kind="info" msg={lockToastMsg} />
	{/if}

	<!-- Fortschrittsbalken -->
	<div class="cm-mobile-flex" data-testid="cm-mobile-progress" style="align-items: center; gap: 8px; padding: 8px 16px 0; flex-shrink: 0;">
		<div style="display: flex; gap: 3px; flex: 1;">
			{#each TAB_DEFS as t (t.id)}
				<div style="flex: 1; height: 3px; border-radius: 2px; background: {done.has(t.id) ? 'var(--g-accent)' : (t.id === activeTab ? 'var(--g-accent-soft,#bcd)' : 'var(--g-rule)')}; transition: background 350ms;"></div>
			{/each}
		</div>
		<span class="mono" style="font-size: 10px; color: var(--g-ink-4); flex-shrink: 0;">{doneCount}/{TAB_DEFS.length}</span>
	</div>

	<!-- Scrollbare Tab-Bar -->
	<div class="cm-mobile-flex" data-testid="cm-mobile-tabbar" style="gap: 0; overflow-x: auto; border-bottom: 1px solid var(--g-rule-soft); -webkit-overflow-scrolling: touch; scrollbar-width: none; flex-shrink: 0; mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent); -webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);">
		{#each TAB_DEFS as t (t.id)}
			{@const on = t.id === activeTab}
			{@const open = unlocked.has(t.id)}
			<button type="button" data-testid="cm-mobile-tab-{t.id}" data-active={on ? 'true' : 'false'} data-locked={open ? 'false' : 'true'} onclick={() => handleMobileTabClick(t.id)}
				style="display: inline-flex; align-items: center; gap: 5px; padding: 13px 13px; min-height: 44px; flex-shrink: 0; background: transparent; border: none; border-bottom: {on ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; cursor: {open ? 'pointer' : 'default'}; font-size: 14px; font-weight: {on ? 600 : 500}; color: {on ? 'var(--g-ink)' : open ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; white-space: nowrap; font-family: var(--g-font-sans); opacity: {open ? 1 : 0.35};">
				{t.label}
				{#if !open}<span class="mono" style="font-size: 10px; opacity: 0.8;">⊘</span>{/if}
			</button>
		{/each}
	</div>

	<!-- Tab-Inhalt -->
	<div style="flex: 1; overflow-y: auto; padding: 16px;">
		{#if activeTab === 'vergleich'}
			<div style="margin-bottom: 14px;">
				<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 8px;">Name des Vergleichs</div>
				<input type="text" maxlength="80" placeholder="z.B. Skitouren Hochkönig" bind:value={wiz.name}
					style="width: 100%; box-sizing: border-box; padding: 12px 14px; font-size: 16px; border: 1px solid var(--g-rule); border-radius: var(--g-r-3); background: var(--g-card); font-family: var(--g-font-sans); color: var(--g-ink); outline: none; min-height: 48px;" />
			</div>
			<div style="margin-bottom: 14px;">
				<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 8px;">Region <span style="font-weight:400; text-transform:none;">(optional)</span></div>
				<input type="text" maxlength="60" placeholder="z.B. Hochkönig · Salzburger Land" bind:value={wiz.region}
					style="width: 100%; box-sizing: border-box; padding: 12px 14px; font-size: 16px; border: 1px solid var(--g-rule); border-radius: var(--g-r-3); background: var(--g-card); font-family: var(--g-font-sans); color: var(--g-ink); outline: none; min-height: 48px;" />
			</div>
			<div>
				<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 10px;">Aktivitätsprofil</div>
				<div style="display: flex; flex-direction: column; gap: 8px;">
					{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
						{@const sel = wiz.activityProfile === opt.value}
						{@const metricsList = profileMetricsLabel(opt.value).split(' · ')}
						<button type="button" data-testid={`compare-editor-profile-mobile-${opt.value}`} onclick={() => selectProfile(opt.value)}
							style="display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 12px 14px; background: {sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}; border: {sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}; border-radius: var(--g-r-3); cursor: pointer; text-align: left; font-family: var(--g-font-sans);">
							<div style="flex: 1; min-width: 0; display: flex; flex-direction: column;">
								<div style="font-size: 14px; font-weight: 600; color: {sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'};">{opt.label}</div>
								<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{metricsList.slice(0, 4).join(' · ')}{metricsList.length > 4 ? ' …' : ''}</div>
							</div>
							{#if sel}
								<span style="width: 20px; height: 20px; border-radius: 50%; background: var(--g-accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
									<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.5"><path d="M2 6l3 3 5-6"/></svg>
								</span>
							{/if}
						</button>
					{/each}
				</div>
			</div>
		{:else if activeTab === 'orte'}
			<Step2Orte {locations} groups={ceGroups} dense onOpenLibrary={() => { mobileLibraryOpen = true; }} />
		{:else if activeTab === 'metriken'}
			{#if isMobileViewport}
				<WeatherMetricsTab context="vergleich" {wiz} />
			{/if}
		{:else if activeTab === 'idealwerte'}
			{#if isMobileViewport}
				<CorridorEditorMobile context="vergleich" />
			{/if}
		{:else if activeTab === 'layout'}
			<div class="mono" style="font-size: 12px; color: var(--g-ink-3); margin-bottom: 14px; line-height: 1.55;">
				Stundenverlauf für die Vergleichs-Mail konfigurieren.
			</div>
			<CompareHourlyLayoutControls {wiz} />
		{:else if activeTab === 'alarme'}
			<AlarmeTab context="vergleich" {wiz} notifyCount={alarmeNotifyCount} onJumpToWertebereiche={jumpToWertebereiche} />
		{:else if activeTab === 'versand'}
			<VersandTab context="vergleich" {wiz} activation={versandActivationBanner} />
		{/if}
	</div>

	<!-- Floating-CTA (nicht auf Versand — dort sitzt „Aktivieren" in der App-Bar) -->
	{#if activeTab !== 'versand'}
		<div data-testid="cm-mobile-cta" style="position: sticky; bottom: 0; padding: 12px 16px; background: var(--g-paper); border-top: 1px solid var(--g-rule-soft); flex-shrink: 0;">
			{#if activeTab === 'vergleich'}
				<MBtn block variant={canContinue ? 'primary' : 'quiet'} size="xl" disabled={!canContinue} onclick={handleMobileNext}>{canContinue ? 'Orte hinzufügen →' : 'Name eingeben'}</MBtn>
			{:else if activeTab === 'orte'}
				{@const restOrte = 2 - wiz.pickedIds.length}
				<MBtn block variant={orteContinueReady ? 'primary' : 'quiet'} size="xl" disabled={!orteContinueReady} onclick={handleMobileNext}>{orteContinueReady ? 'Wetter-Metriken →' : `noch ${restOrte} Ort${restOrte !== 1 ? 'e' : ''} nötig`}</MBtn>
			{:else if activeTab === 'metriken'}
				<MBtn block variant="primary" size="xl" onclick={handleMobileNext}>Wertebereiche festlegen →</MBtn>
			{:else if activeTab === 'idealwerte'}
				<MBtn block variant="primary" size="xl" onclick={handleMobileNext}>Layout einrichten →</MBtn>
			{:else if activeTab === 'layout'}
				<MBtn block variant="primary" size="xl" onclick={handleMobileNext}>Alarme einrichten →</MBtn>
			{:else if activeTab === 'alarme'}
				<MBtn block variant="primary" size="xl" onclick={handleMobileNext}>Versand einrichten →</MBtn>
			{/if}
		</div>
	{/if}
</div><!-- /.cm-mobile -->

<!-- Mobile Bibliotheks-Sheet (Orte-Tab) -->
<Sheet open={mobileLibraryOpen} snap="full" title="Ort wählen" onClose={() => { mobileLibraryOpen = false; }}>
	{#each mobileLibraryGroups as [groupName, groupLocs] (groupName)}
		<div style="margin-bottom: 8px;">
			<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; padding: 8px 0 4px; font-weight: 600;">{groupName} · {groupLocs.length}</div>
			{#each groupLocs as loc (loc.id)}
				{@const on = wiz.pickedIds.includes(loc.id)}
				<button type="button" data-testid="compare-step2-mobile-lib-check-{loc.id}"
					onclick={() => { if (on) { wiz.pickedIds = wiz.pickedIds.filter((x) => x !== loc.id); } else { wiz.pickedIds = [...wiz.pickedIds, loc.id]; } }}
					style="display: flex; align-items: center; gap: 14px; width: 100%; padding: 12px 0; min-height: 52px; background: {on ? 'var(--g-accent-tint)' : 'transparent'}; border: none; border-bottom: 1px solid var(--g-rule-soft); cursor: pointer; text-align: left; font-family: var(--g-font-sans);">
					<span style="width: 22px; height: 22px; border-radius: 4px; border: 1.5px solid {on ? 'var(--g-accent)' : 'var(--g-rule)'}; background: {on ? 'var(--g-accent)' : 'transparent'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
						{#if on}<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.5"><path d="M2 6l3 3 5-6"/></svg>{/if}
					</span>
					<div style="flex: 1; min-width: 0;">
						<div style="font-size: 14px; font-weight: {on ? 600 : 500}; color: {on ? 'var(--g-accent-deep)' : 'var(--g-ink)'}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{loc.name}</div>
						{#if loc.region}<div class="mono" style="font-size: 10.5px; color: var(--g-ink-3); margin-top: 1px;">{loc.region}</div>{/if}
					</div>
				</button>
			{/each}
		</div>
	{/each}
</Sheet>
</div>

<style>
	/* CSS-only Responsive Switch (Muster #682/#661). Desktop offscreen statt
	   display:none, damit compare-editor-name auf Mobile für Playwright befüllbar
	   bleibt (ein Element, strict-mode-safe). .cm-mobile display:none für
	   toBeHidden() in Desktop-Tests. */
	.cm-mobile {
		display: none !important;
	}
	@media (max-width: 899px) {
		.cm-desktop {
			position: fixed !important;
			top: -9999px !important;
			left: -9999px !important;
			width: 1px !important;
			height: 1px !important;
			overflow: hidden !important;
		}
		.cm-mobile {
			display: block !important;
		}
		.cm-mobile-flex {
			display: flex !important;
		}
	}

	.ce-cta-foot {
		padding: 0 40px 48px;
	}
	.ce-cta-row {
		padding-top: 20px;
		border-top: 1px solid var(--g-rule);
		display: flex;
		justify-content: flex-end;
		align-items: center;
		gap: 12px;
	}
	.ce-cta-hint {
		font-size: 11px;
		color: var(--g-ink-4);
	}
</style>
