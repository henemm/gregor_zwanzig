<script lang="ts">
	// Issue #490 — /compare Übersicht mit Kachel-Grid (Block B, Epic #485).
	// Issue #493 — Mobile-Responsive: Stack unter 900 px (Block E).
	// Issue #582 — Design-Fidelity: JSX 1:1 (Block A).
	// Issue #1256 Scheibe 8d (AC-1..AC-5): kompakter mobiler Kopf über die
	// geteilte Design-Kopfleiste (TopAppBar) statt reflowtem Desktop-Kopf;
	// Suchfeld mobil ersatzlos entfernt (Handoff-5-P3), Stats mobil size="sm",
	// kompaktes Content-Padding (12px 16px 24px, ohne main-px-4-Doppelung).
	import type { ComparePreset } from '$lib/types.js';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api.js';
	import { Eyebrow, Btn, Card, Stat, PageHeader } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import SendConfirmDialog from '$lib/components/molecules/SendConfirmDialog.svelte';
	import StatusFilterPills from '$lib/components/molecules/StatusFilterPills.svelte';
	import ListTable from '$lib/components/organisms/ListTable.svelte';
	import SubscriptionCard from '$lib/components/organisms/SubscriptionCard.svelte';
	import SubscriptionActionSheet from '$lib/components/mobile/SubscriptionActionSheet.svelte';
	import {
		deriveStatusFromPreset,
		presetLocationsLabel,
		presetProfileLabel,
		presetChannels,
		presetTileScheduleLabel,
		relativeLastSent,
		compareFilterStatus,
		type CompareStatus
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { subscriptionActions, subscriptionLifecycle } from '$lib/components/shared/subscriptionActions.js';
	import { setPaused, deleteSubscription, sendSubscription } from '$lib/components/shared/subscriptionExec.js';
	import { t, tr, locale, type MessageKey } from '$lib/i18n/index.js';

	let { data } = $props();
	let presets: ComparePreset[] = $state(data.presets ?? []);

	// Issue #1277 — Desktop-Übersicht über das geteilte ListTable-Organism.
	// Aktions-Logik aus dem gelöschten Kachel-Grid hierher übernommen
	// (togglePause · confirmSend · confirmDelete).
	let deleteTarget: ComparePreset | null = $state(null);
	let sendTarget: ComparePreset | null = $state(null);
	let sendInfo: string | null = $state(null);
	let error: string | null = $state(null);

	// Mobiles Aktionsblatt (Issue #2278 AC-2/AC-14: geteilter Baustein wie beim Trip)
	let actionPreset: ComparePreset | null = $state(null);

	// #2652 (i18n F3): Statuswoerter aus dem Katalog (listen.status.*, wie die Trip-Liste).
	const STATUS_KEY: Record<CompareStatus, MessageKey> = {
		active: 'listen.status.aktiv',
		paused: 'listen.status.pausiert',
		draft: 'listen.status.draft'
	};
	function compareDot(status: CompareStatus): string {
		if (status === 'active') return 'var(--g-good)';
		if (status === 'paused') return 'var(--g-ink-3)';
		return 'var(--g-ink-4)';
	}

	const compareColumns = $derived([
		{
			key: 'name',
			header: $t('listen.spalte.name'),
			width: '1.5fr',
			render: (row: unknown) => {
				const p = row as ComparePreset;
				const status = deriveStatusFromPreset(p);
				return {
					nameCell: {
						name: p.name || $t('listen.vergleiche.ohne_namen'),
						statusLabel: $t(STATUS_KEY[status]),
						dotColor: compareDot(status),
						statusTestid: 'compare-status-pill'
					}
				};
			}
		},
		{
			key: 'orte',
			header: $t('listen.spalte.orte'),
			width: '0.7fr',
			mono: true,
			render: (row: unknown) => presetLocationsLabel(row as ComparePreset)
		},
		{
			key: 'profil',
			header: $t('listen.spalte.profil'),
			width: '0.9fr',
			render: (row: unknown) => presetProfileLabel((row as ComparePreset).profil) || '—'
		},
		{
			key: 'kanaele',
			header: $t('listen.spalte.kanaele'),
			width: '1fr',
			render: (row: unknown) => ({ pills: presetChannels(row as ComparePreset) })
		},
		{
			key: 'zeitplan',
			header: $t('listen.spalte.zeitplan'),
			width: '1.2fr',
			render: (row: unknown) => {
				const p = row as ComparePreset;
				if (deriveStatusFromPreset(p) === 'draft') {
					return { lines: [$t('bausteine.abo.setup_unvollstaendig'), ''] };
				}
				const rel = relativeLastSent(p.letzter_versand);
				return { lines: [presetTileScheduleLabel(p), rel ? $t('bausteine.abo.zuletzt', { zeit: rel }) : ''] };
			}
		}
	]);

	function compareRowPrimary(row: unknown) {
		const p = row as ComparePreset;
		return deriveStatusFromPreset(p) === 'active'
			? { label: tr('listen.aktion.briefing_senden'), onClick: () => (sendTarget = p) }
			: null;
	}

	// EIN Dispatch fuer Desktop-Zeilenmenue und mobiles Blatt (AC-2, AC-8, AC-16).
	// Epic #1273 S3: setup/edit landen auf dem Hub, nicht mehr auf /edit.
	function onCompareAction(key: string, row: unknown) {
		const p = row as ComparePreset;
		if (key === 'pause') void togglePause(p, true);
		else if (key === 'resume') void togglePause(p, false);
		else if (key === 'send') sendTarget = p;
		else if (key === 'alarms') goto('/compare/' + p.id + '?tab=alarme');
		else if (key === 'weather') goto('/compare/' + p.id + '?tab=wetter-metriken');
		else if (key === 'edit') goto('/compare/' + p.id);
		else if (key === 'continue-setup') goto('/compare/' + p.id);
		else if (key === 'delete') deleteTarget = p;
	}

	// Issue #1259 — Read-Modify-Write (frischer Stand vor dem PUT) steckt im Adapter.
	async function togglePause(preset: ComparePreset, paused: boolean) {
		error = null;
		try {
			await setPaused('vergleich', preset.id, paused);
			const res = await fetch(`/api/compare/presets/${preset.id}`);
			if (res.ok) {
				const updated = await res.json();
				presets = presets.map((p) => (p.id === preset.id ? updated : p));
			}
		} catch {
			error = tr('listen.meldung.status_fehlgeschlagen');
		}
	}

	// Issue #627 — Einzel-Sofortversand (nach Bestaetigung im Sende-Dialog).
	async function confirmSend() {
		if (!sendTarget) return;
		const target = sendTarget;
		sendTarget = null;
		error = null;
		sendInfo = null;
		// Issue #2124: geteilter Laufzustand (compare:<id>) + Klassifikation.
		const o = await sendSubscription('vergleich', target.id);
		if (o.kind === 'ok') sendInfo = tr('listen.meldung.versendet');
		else error = o.message;
	}

	async function confirmDelete() {
		if (!deleteTarget) return;
		error = null;
		const target = deleteTarget;
		try {
			await deleteSubscription('vergleich', target.id);
			presets = presets.filter((p) => p.id !== target.id);
		} catch {
			error = tr('listen.meldung.loeschen_fehlgeschlagen');
		}
		deleteTarget = null;
	}

	let counts = $derived({
		active: presets.filter((p) => deriveStatusFromPreset(p) === 'active').length,
		paused: presets.filter((p) => deriveStatusFromPreset(p) === 'paused').length,
		draft: presets.filter((p) => deriveStatusFromPreset(p) === 'draft').length
	});

	// Issue #582 — Suche immer sichtbar (nach JSX-Vorlage); Issue #1256 S8d
	// AC-3: nur noch Desktop, mobil ersatzlos entfernt (Handoff-5-P3).
	let searchQuery = $state('');
	const filteredPresets = $derived(
		searchQuery
			? presets.filter((p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()))
			: presets
	);

	// Issue #2278 loest die Link-only-Entscheidung (#1256 S8 AC-21) ab: mobil dieselbe Karte,
	// dasselbe Aktionsblatt und dieselben Filter-Pillen wie beim Trip (Paritaet, Epic #2345 DoD-3).
	let mobileFilter = $state<'all' | 'aktiv' | 'geplant' | 'pausiert' | 'fertig'>('all');
	const mobilePresets = $derived(
		presets.filter((p) => mobileFilter === 'all' || compareFilterStatus(p) === mobileFilter)
	);
	const pillCounts = $derived({
		all: presets.length,
		aktiv: presets.filter((p) => compareFilterStatus(p) === 'aktiv').length,
		geplant: 0, // Ortsvergleiche haben kein Startdatum
		pausiert: presets.filter((p) => compareFilterStatus(p) === 'pausiert').length,
		fertig: presets.filter((p) => compareFilterStatus(p) === 'fertig').length
	});

	// Mobile-Shell S2: Titel, Eyebrow und „Neuer Vergleich" stehen mobil im
	// <PageHeader> der Seite (Rechts-Slot) — derselbe Baustein wie die
	// Uebersicht, kein Kopfleisten-Store mehr (AP-011).
</script>

{#snippet neuerVergleichMobil()}
	<Btn href="/compare/new" variant="ghost" size="sm" data-testid="compare-list-new-mobile">{$t('onboarding.willkommen.neuer_vergleich')}</Btn>
{/snippet}

<div style="background: var(--g-paper)">
	<main style="flex: 1; overflow: auto">
		<!-- Desktop-Kopf (Issue #582, ≥900px unverändert) -->
		<div class="hidden desktop:block" style="padding: 32px 40px 60px">
			<div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 28px">
				<div>
					<Eyebrow>{$t('listen.vergleiche.eyebrow')}</Eyebrow>
					<h1 style="font-size: 32px; font-weight: 600; letter-spacing: -0.025em; margin-top: 4px">{$t('listen.vergleiche.titel')}</h1>
					<div style="font-size: 14px; color: var(--g-ink-3); margin-top: 6px; max-width: 620px">
						{$t('listen.vergleiche.intro')}
					</div>
				</div>
				<Btn variant="primary" href="/compare/new">{$t('onboarding.willkommen.neuer_vergleich')}</Btn>
			</div>

			<!-- Suche — Desktop-only (Issue #582; Issue #1256 S8d AC-3 entfernt sie mobil) -->
			<div class="hidden desktop:block" style="position: relative; max-width: 380px; margin-bottom: 20px">
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" stroke-width="2"
					style="position: absolute; top: 11px; left: 12px">
					<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>
				</svg>
				<input
					type="text"
					bind:value={searchQuery}
					placeholder={$t('listen.suche.platzhalter')}
					style="width: 100%; padding: 9px 14px 9px 34px; border: 1px solid var(--g-rule); border-radius: var(--g-r-pill); background: var(--g-card); font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink); outline: none; box-sizing: border-box"
				/>
			</div>

			<!-- Stats-Zeile — Stat-Molecule (Issue #582) -->
			<div style="display: flex; gap: 24px; margin-bottom: 22px; padding-bottom: 16px; border-bottom: 1px solid var(--g-rule-soft)">
				<Stat label={$t('listen.stat.aktiv')} value={counts.active} layout="inline" tone="accent" mono/>
				<Stat label={$t('listen.stat.pausiert')} value={counts.paused} layout="inline" mono/>
				<Stat label={$t('listen.stat.drafts')} value={counts.draft} layout="inline" mono/>
			</div>

			<!-- Desktop-Übersicht über das geteilte ListTable-Organism (Issue #1277) -->
			{#if error}
				<p class="text-sm text-destructive" style="margin-bottom: 12px">{error}</p>
			{/if}
			{#if sendInfo}
				<p class="text-sm" style="color: var(--g-accent); margin-bottom: 12px">{sendInfo}</p>
			{/if}
			<ListTable
				columns={compareColumns}
				rows={filteredPresets}
				getRowId={(row) => (row as ComparePreset).id}
				onRowClick={(row) => goto(`/compare/${(row as ComparePreset).id}`)}
				rowActions={(row) =>
					// i18n F9: Aktionsnamen entstehen per tr() — `$locale` macht den Aufruf im Render reaktiv.
					(void $locale, subscriptionActions('vergleich', subscriptionLifecycle('vergleich', row as ComparePreset), 'list')).map((a) => ({
						key: a.id,
						label: a.label,
						danger: a.danger
					}))}
				rowPrimary={compareRowPrimary}
				onAction={onCompareAction}
				emptyText={searchQuery
					? $t('listen.leer.vergleich_suche', { suche: searchQuery })
					: $t('listen.leer.vergleich')}
				rowTestid={(row) => `compare-tile-${(row as ComparePreset).id}`}
				menuTestid={() => 'compare-row-kebab'}
			/>

			<!-- Footer-Zähler (Issue #582) -->
			<div style="margin-top: 16px; font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono); letter-spacing: 0.06em">
				{$t('listen.zaehler.vergleiche', { gefiltert: filteredPresets.length, gesamt: presets.length })}
			</div>
		</div>

		<!-- Mobiler Kopf (Issue #493; Issue #1256 S8d AC-2/AC-4/AC-5). -mx-4
		     hebt das main-px-4 (S8-Falle Doppel-Padding) auf, bevor die eigene
		     12/16/24-Polsterung greift — Netto-Abstand bleibt 16px. -->
		<div class="desktop:hidden -mx-4" style="padding: 12px 16px 24px">
			<PageHeader eyebrow={$t('listen.workspace_anzahl', { anzahl: presets.length })} title={$t('listen.vergleiche.titel')} right={neuerVergleichMobil} compact />
			<div style="font-size: 13px; color: var(--g-ink-3); line-height: 1.5; margin: 14px 0">
				{$t('listen.vergleiche.intro_mobil')}
			</div>

			<!-- Stats (Stat-Molecule, inline, kompakt — JSX-M Z.42-44) -->
			<div style="display: flex; gap: 20px; padding: 4px 2px 16px; border-bottom: 1px solid var(--g-rule-soft); margin-bottom: 16px">
				<Stat label={$t('listen.stat.aktiv')} value={counts.active} layout="inline" size="sm" tone="accent" mono/>
				<Stat label={$t('listen.stat.pausiert')} value={counts.paused} layout="inline" size="sm" mono/>
				<Stat label={$t('listen.stat.drafts')} value={counts.draft} layout="inline" size="sm" mono/>
			</div>

			<!-- Mobiler Kachel-Stack (#493): vertikal, unter 900 px -->
			<div style="display: flex; flex-direction: column; gap: 10px">
				{#if presets.length === 0}
					<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">
						{$t('listen.leer.vergleich')}
					</Card>
				{:else}
					<StatusFilterPills active={mobileFilter} counts={pillCounts} onSelect={(v) => { mobileFilter = v; }} />
					{#each mobilePresets as preset (preset.id)}
						<SubscriptionCard
							kind="vergleich"
							sub={preset}
							dense
							onclick={() => goto('/compare/' + preset.id)}
							onAction={() => { actionPreset = preset; }}
						/>
					{/each}
				{/if}
			</div>
		</div>
	</main>
</div>

<!-- Lösch-/Versand-Bestätigung (aus dem gelöschten Kachel-Grid übernommen) -->
<ConfirmDialog
	open={deleteTarget !== null}
	title={$t('listen.dialog.vergleich_loeschen')}
	description={$t('listen.dialog.unwiderruflich', { name: deleteTarget?.name ?? '' })}
	confirmLabel={$t('listen.aktion.loeschen')}
	confirmVariant="destructive"
	onConfirm={confirmDelete}
	onCancel={() => (deleteTarget = null)}
	onOpenChange={(open) => { if (!open) deleteTarget = null; }}
/>

<SendConfirmDialog
	open={sendTarget !== null}
	kind="vergleich"
	profile={data.profile}
	subscription={sendTarget}
	onConfirm={confirmSend}
	onCancel={() => (sendTarget = null)}
/>

<SubscriptionActionSheet
	open={actionPreset !== null}
	onClose={() => (actionPreset = null)}
	kind="vergleich"
	status={actionPreset ? subscriptionLifecycle('vergleich', actionPreset) : 'active'}
	name={actionPreset?.name}
	onAction={(id) => { if (actionPreset) onCompareAction(id, actionPreset); }}
/>
