<script lang="ts">
	// Compare-Editor — Gerüst + Lock-Engine + Tab „Vergleich" (Issue #678, Epic #677).
	// Edit-Modus + Dirty/Save-Flow (Issue #679, Epic #677).
	// Spec: docs/specs/modules/issue_679_compare_editor_edit.md
	// Design-Quelle: claude-code-handoff/current/jsx/screen-compare-editor.jsx Z. 640-700.

	import { getContext } from 'svelte';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import { Field, ConfirmDialog } from '$lib/components/molecules';
	import { ACTIVITY_PROFILE_OPTIONS, type ActivityProfile, type Location, type ComparePreset } from '$lib/types';
	import type { CompareWizardState } from './compareWizardState.svelte';
	import {
		TAB_ORDER,
		unlockedTabs,
		doneTabs,
		type CompareTabId
	} from './compareEditorLogic';
	import Step2Orte from './steps/Step2Orte.svelte';
	import Step3Idealwerte from './steps/Step3Idealwerte.svelte';
	import Step4Layout from './steps/Step4Layout.svelte';
	import Step5Versand from './steps/Step5Versand.svelte';

	interface Props {
		mode?: 'create' | 'edit';
		locations?: Location[];
		preset?: ComparePreset;
	}
	let { mode = 'create', locations = [], preset }: Props = $props();

	const wiz = getContext<CompareWizardState>('compare-wizard-state');

	const TAB_DEFS: { id: CompareTabId; label: string; lockHint: string | null }[] = [
		{ id: 'vergleich', label: 'Vergleich', lockHint: null },
		{ id: 'orte', label: 'Orte', lockHint: 'erst Vergleich benennen' },
		{ id: 'idealwerte', label: 'Idealwerte', lockHint: 'erst mind. 2 Orte auswählen' },
		{ id: 'layout', label: 'Layout', lockHint: 'erst Idealwerte öffnen' },
		{ id: 'versand', label: 'Versand', lockHint: 'erst Layout öffnen' }
	];

	const isEdit = $derived(mode === 'edit');

	// Lokale visited-Flags (Tab 3/4/5 als „besucht" markieren → schaltet nächsten frei).
	let idealsVisited = $state(false);
	let layoutVisited = $state(false);
	let versandVisited = $state(false);

	let activeTab = $state<CompareTabId>('vergleich');

	// Dirty-Tracking (AC-2): Snapshot der editierbaren Felder beim Mount erfassen.
	// $derived statt manueller markDirty-Wrapper — deckt alle Tabs ab und markiert
	// NICHT bei reiner Tab-Navigation (AC-Semantik: Feldänderung → Pill).
	const initial = {
		name: wiz.name,
		region: wiz.region,
		profile: wiz.activityProfile,
		picked: [...wiz.pickedIds].join(','),
		ideals: JSON.stringify(wiz.idealRanges),
		layouts: JSON.stringify(wiz.channelLayouts)
	};
	const dirty = $derived(
		isEdit &&
			(wiz.name !== initial.name ||
				wiz.region !== initial.region ||
				wiz.activityProfile !== initial.profile ||
				[...wiz.pickedIds].join(',') !== initial.picked ||
				JSON.stringify(wiz.idealRanges) !== initial.ideals ||
				JSON.stringify(wiz.channelLayouts) !== initial.layouts)
	);

	// Status-Dot (AC-6): aus dem preset-Prop lesen (nicht wiz.schedule — type-gemangelt).
	const paused = $derived(preset?.schedule === 'manual');

	// ConfirmDialog für Verwerfen (AC-4).
	let discardOpen = $state(false);

	const unlocked = $derived(
		unlockedTabs({
			name: wiz.name,
			pickedCount: wiz.pickedIds.length,
			idealsVisited,
			layoutVisited
		})
	);
	const done = $derived(
		doneTabs({
			name: wiz.name,
			pickedCount: wiz.pickedIds.length,
			idealsVisited,
			layoutVisited,
			versandVisited
		})
	);
	const doneCount = $derived(TAB_ORDER.filter((t) => done.has(t)).length);

	function switchTab(id: CompareTabId) {
		if (!isEdit && !unlocked.has(id)) return;
		activeTab = id;
		if (id === 'idealwerte') idealsVisited = true;
		if (id === 'layout') layoutVisited = true;
		if (id === 'versand') versandVisited = true;
	}

	function selectProfile(value: ActivityProfile) {
		wiz.activityProfile = value;
	}

	function handleDiscard() {
		discardOpen = true;
	}

	function handleSave() {
		if (preset) void wiz.saveComparePreset(preset);
	}

	// Issue #681: "Briefing aktivieren" im Create-Modus (AC-4).
	// wiz.save() handhabt Create (POST) und Edit (PUT) — saveComparePreset(preset) nur für Edit.
	function handleActivate() {
		if (!versandVisited) return;
		void wiz.save();
	}

	const canContinue = $derived(wiz.name.trim().length > 0);
</script>

<div
	data-testid="compare-editor"
	style:position="relative"
	style:min-height="100%"
	style:background="var(--g-paper)"
>
	<TopoBg opacity={0.12}>
		<!-- Breadcrumb + Aktionen (JSX Z. 649-676) -->
		<div
			style:position="relative"
			style:padding="14px 40px"
			style:border-bottom="1px solid var(--g-rule-soft)"
			style:display="flex"
			style:justify-content="space-between"
			style:align-items="center"
		>
			<div
				class="mono"
				style:font-size="11px"
				style:color="var(--g-ink-3)"
				style:letter-spacing="0.06em"
			>
				<span style:opacity="0.6">Orts-Vergleiche</span>
				<span style:margin="0 8px">/</span>
				<span style:color="var(--g-ink)"
					>{isEdit ? (wiz.name.trim() || 'Vergleich') : 'Neuer Vergleich'}</span
				>
			</div>

			{#if isEdit}
				<!-- Aktionsleiste im Edit-Modus (JSX Z. 657-664) -->
				<div style:display="flex" style:gap="8px" style:align-items="center">
					{#if dirty}
						<span
							data-testid="compare-editor-dirty-pill"
							class="mono"
							style:font-size="11px"
							style:font-weight="600"
							style:padding="3px 8px"
							style:border-radius="4px"
							style:background="rgba(200,140,0,0.12)"
							style:color="var(--g-warn, #b87800)"
							style:letter-spacing="0.04em"
						>Ungespeichert</span>
					{/if}
					<!-- Status-Dot (AC-6): 7×7px, Farbe laut JSX Z. 660 -->
					<span
						data-testid="compare-editor-status-dot"
						data-status={paused ? 'paused' : 'active'}
						style:width="7px"
						style:height="7px"
						style:border-radius="50%"
						style:display="inline-block"
						style:background={paused ? 'var(--g-ink-4)' : 'var(--g-good)'}
					></span>
					<span
						class="mono"
						style:font-size="11px"
						style:color="var(--g-ink-3)"
						style:letter-spacing="0.04em"
					>{paused ? 'pausiert' : 'aktiv'}</span>
					<Btn
						variant="ghost"
						size="sm"
						data-testid="compare-editor-discard"
						onclick={handleDiscard}
					>Verwerfen</Btn>
					<Btn
						variant="primary"
						size="sm"
						data-testid="compare-editor-save"
						onclick={handleSave}
					>Speichern</Btn>
				</div>
			{:else}
				<!-- Create-Modus: Briefing aktivieren (AC-4, Issue #681, JSX Z. 666-674) -->
				<div style:display="flex" style:gap="8px" style:align-items="center">
					{#if !versandVisited}
						<span
							class="mono"
							style:font-size="10.5px"
							style:color="var(--g-ink-4)"
						>Versand einrichten zum Aktivieren</span>
					{/if}
					<Btn variant="ghost" size="sm" href="/compare">Abbrechen</Btn>
					<Btn
						data-testid="compare-editor-activate"
						variant={versandVisited ? 'primary' : 'quiet'}
						size="sm"
						disabled={!versandVisited}
						onclick={handleActivate}
						style={versandVisited ? '' : 'opacity:0.4; cursor:not-allowed'}
					>Briefing aktivieren</Btn>
				</div>
			{/if}
		</div>

		<!-- Hero -->
		<div style:position="relative" style:padding="20px 40px 14px">
			<Eyebrow>{isEdit ? 'Orts-Vergleich bearbeiten' : 'Neuer Orts-Vergleich'}</Eyebrow>
			<h1
				style:font-size="32px"
				style:font-weight="600"
				style:letter-spacing="-0.02em"
				style:margin="4px 0 0"
				style:line-height="1.1"
				style:color={wiz.name.trim() ? 'var(--g-ink)' : 'var(--g-ink-4)'}
			>
				{wiz.name.trim() || 'Noch kein Name'}
			</h1>

			<!-- Fortschrittsbalken: KEIN Render im Edit-Modus (AC-1) -->
			{#if !isEdit}
				<div
					data-testid="compare-editor-progress"
					style:display="flex"
					style:align-items="center"
					style:gap="10px"
					style:margin-top="7px"
				>
					<div style:display="flex" style:gap="3px">
						{#each TAB_ORDER as t (t)}
							<div
								data-testid="compare-editor-progress-segment"
								style:width="24px"
								style:height="3px"
								style:border-radius="2px"
								style:background={done.has(t) ? 'var(--g-accent)' : 'var(--g-rule)'}
								style:transition="background 350ms"
							></div>
						{/each}
					</div>
					<span
						class="mono"
						style:font-size="10.5px"
						style:color="var(--g-ink-4)"
						style:letter-spacing="0.04em"
					>
						{doneCount === 0
							? 'Noch nichts eingerichtet'
							: `${doneCount} / ${TAB_ORDER.length} Abschnitte eingerichtet`}
					</span>
				</div>
			{/if}
		</div>

		<!-- Tab-Bar -->
		<div
			style:border-bottom="1px solid var(--g-rule)"
			style:padding="0 40px"
			style:display="flex"
			style:gap="0"
			style:overflow-x="auto"
		>
			{#each TAB_DEFS as t (t.id)}
				{@const on = t.id === activeTab}
				{@const open = isEdit || unlocked.has(t.id)}
				{@const isDone = !isEdit && done.has(t.id) && !on}
				<button
					data-testid={`compare-editor-tab-${t.id}`}
					data-active={on ? 'true' : 'false'}
					data-locked={open ? 'false' : 'true'}
					data-done={done.has(t.id) ? 'true' : 'false'}
					type="button"
					onclick={() => switchTab(t.id)}
					title={!open && t.lockHint ? `Gesperrt — ${t.lockHint}` : undefined}
					style:padding="12px 16px"
					style:cursor={open ? 'pointer' : 'not-allowed'}
					style:background="none"
					style:border="none"
					style:border-bottom={on ? '2px solid var(--g-accent)' : '2px solid transparent'}
					style:margin-bottom="-1px"
					style:font-family="var(--g-font-sans)"
					style:font-size="13px"
					style:font-weight={on ? 600 : 500}
					style:color={on ? 'var(--g-ink)' : open ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}
					style:display="flex"
					style:align-items="center"
					style:gap="5px"
					style:white-space="nowrap"
					style:opacity={open ? 1 : 0.34}
					style:transition="opacity 250ms, color 200ms"
					style:user-select="none"
				>
					{t.label}
					{#if isDone}
						<span
							class="mono"
							style:font-size="10px"
							style:font-weight="700"
							style:padding="2px 5px"
							style:border-radius="3px"
							style:background="rgba(61,107,58,0.12)"
							style:color="var(--g-good)">✓</span
						>
					{/if}
					{#if !open}
						<span
							class="mono"
							style:font-size="10px"
							style:color="var(--g-ink-4)"
							style:opacity="0.7">⊘</span
						>
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

					<Field
						label="Name des Vergleichs"
						hint="Erscheint im Mail-Betreff. Kurz & wiedererkennbar."
					>
						<input
							data-testid="compare-editor-name"
							type="text"
							maxlength="80"
							placeholder="z.B. Skitouren Hochkönig"
							bind:value={wiz.name}
							class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]"
						/>
					</Field>

					<Field label="Region" side="optional · max 60">
						<input
							data-testid="compare-editor-region"
							type="text"
							maxlength="60"
							placeholder="z.B. Hochkönig · Salzburger Land"
							bind:value={wiz.region}
							class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]"
						/>
					</Field>

					<Eyebrow style="margin-bottom: 12px; margin-top: 28px">Aktivitätsprofil</Eyebrow>
					<div style:font-size="13px" style:color="var(--g-ink-3)" style:margin-bottom="14px">
						Bestimmt, welche Wetter-Metriken verglichen werden. Die Idealwerte legst du im
						nächsten Tab fest.
					</div>
					<div
						style:display="grid"
						style:grid-template-columns="1fr 1fr"
						style:gap="10px"
					>
						{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
							{@const sel = wiz.activityProfile === opt.value}
							<button
								data-testid={`compare-editor-profile-${opt.value}`}
								data-selected={sel ? 'true' : 'false'}
								type="button"
								onclick={() => selectProfile(opt.value)}
								style:text-align="left"
								style:cursor="pointer"
								style:padding="14px 16px"
								style:background={sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}
								style:border={sel
									? '1.5px solid var(--g-accent)'
									: '1px solid var(--g-rule)'}
								style:border-radius="var(--g-r-3)"
								style:font-family="var(--g-font-sans)"
							>
								<div
									style:font-size="14px"
									style:font-weight="600"
									style:color={sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'}
								>
									{opt.label}
								</div>
							</button>
						{/each}
					</div>

					<div
						style:margin-top="28px"
						style:padding-top="20px"
						style:border-top="1px solid var(--g-rule)"
						style:display="flex"
						style:justify-content="flex-end"
						style:align-items="center"
						style:gap="12px"
					>
						{#if !canContinue}
							<span class="mono" style:font-size="11px" style:color="var(--g-ink-4)">
								⊘ Name fehlt
							</span>
						{/if}
						{#if canContinue && !isEdit}
							<Btn
								data-testid="compare-editor-continue-orte"
								variant="accent"
								size="md"
								onclick={() => switchTab('orte')}
							>
								Orte hinzufügen →
							</Btn>
						{/if}
					</div>
				</div>
			</TopoBg>
		</div>
	{:else if activeTab === 'orte'}
		<Step2Orte {locations} />
	{:else if activeTab === 'idealwerte'}
		<Step3Idealwerte />
	{:else if activeTab === 'layout'}
		<Step4Layout />
	{:else if activeTab === 'versand'}
		<Step5Versand {versandVisited} />
	{/if}

	<!-- DOM-Anker für AC-5 isAttached()-Test (display:none, kein sichtbarer Inhalt).
	     Die sichtbare Banner-Version rendert Step5Versand. -->
	{#if !isEdit}
		<div
			data-testid="compare-step5-activation-banner"
			data-ready={versandVisited ? 'true' : 'false'}
			style:display="none"
			aria-hidden="true"
		></div>
	{/if}
</div>

<!-- ConfirmDialog: Änderungen verwerfen (AC-4) -->
<ConfirmDialog
	open={discardOpen}
	title="Änderungen verwerfen?"
	description="Alle Änderungen an diesem Vergleich werden verworfen."
	confirmLabel="Verwerfen"
	confirmVariant="destructive"
	cancelLabel="Weiter bearbeiten"
	onConfirm={async () => {
		discardOpen = false;
		const { goto } = await import('$app/navigation');
		void goto('/compare/' + (preset?.id ?? ''));
	}}
	onCancel={() => {
		discardOpen = false;
	}}
	onOpenChange={(o) => {
		if (!o) discardOpen = false;
	}}
/>
