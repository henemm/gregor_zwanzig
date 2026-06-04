<script lang="ts">
	// Issue #517 — CompareTabs: 6-Tab-Orchestrator für /compare/[id] Detail-Seite.
	//
	// Tabs: Übersicht · Orte · Idealwerte · Layout · Versand · Vorschau
	//
	// URL-Sync via history.replaceState (?tab=VALUE), kein Hash wie TripTabs.
	// Mobile (<900px): scrollbare Pill-Tabs analog TripTabs.svelte.
	//
	// Spec: docs/specs/modules/issue_517_compare_hub.md

	import { Segmented, Dot, Pill, Btn, Eyebrow, Card, Switch } from '$lib/components/atoms';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	import CompareIdealRow from '$lib/components/molecules/CompareIdealRow.svelte';
	import CompareLayoutRow from '$lib/components/molecules/CompareLayoutRow.svelte';
	import DetailRow from '$lib/components/molecules/DetailRow.svelte';
	import {
		deriveStatusFromPreset,
		presetScheduleLabel,
		formatLastSent,
		STATUS_MAP
	} from '$lib/components/compare/subscriptionHelpers.js';
	import type { ComparePreset, Location } from '$lib/types.js';
	import { api } from '$lib/api.js';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
		initialTab?: string;
	}

	let { preset, locations, initialTab = 'uebersicht' }: Props = $props();

	const TABS = [
		{ value: 'uebersicht', label: 'Übersicht' },
		{ value: 'orte', label: 'Orte' },
		{ value: 'idealwerte', label: 'Idealwerte' },
		{ value: 'layout', label: 'Layout' },
		{ value: 'versand', label: 'Versand' },
		{ value: 'vorschau', label: 'Vorschau' }
	] as const;

	const segmentedOptions = $derived(
		TABS.map((tab) => ({
			value: tab.value,
			label: tab.label,
			testid: `compare-detail-tab-${tab.value}`
		}))
	);

	const VALID_VALUES: readonly string[] = TABS.map((t) => t.value);
	function resolve(value: string): string {
		return VALID_VALUES.includes(value) ? value : 'uebersicht';
	}

	let activeTab = $state<string>('uebersicht');
	$effect(() => {
		activeTab = resolve(initialTab);
	});

	function handleValueChange(value: string): void {
		activeTab = value;
		if (typeof window !== 'undefined') {
			const url = new URL(window.location.href);
			url.searchParams.set('tab', value);
			history.replaceState(history.state, '', url.toString());
		}
	}

	// Tab-Daten ──────────────────────────────────────────────────────────────────

	const status = $derived(deriveStatusFromPreset(preset));
	const statusInfo = $derived(STATUS_MAP[status]);

	// Orts-Auflösung: location_ids → locations[] (mit elevation_m für CompareLocationRow).
	const resolvedLocations = $derived(
		preset.location_ids.map((id, idx) => ({
			rank: idx + 1,
			loc: locations.find((l) => l.id === id)
		}))
	);

	const idealRanges = $derived(
		preset.display_config?.ideal_ranges as
			| Record<string, { min: number; max: number; unit?: string }>
			| undefined
	);

	const CHANNEL_COLS: Record<string, number> = {
		email: 99,
		telegram: 8,
		sms: 0
	};
	const channels = ['email', 'telegram', 'sms'];

	// ── Vorschau-Tab (Issue #514) ────────────────────────────────────────────────
	let previewChannel = $state<'email' | 'sms'>('email');
	let previewHtml = $state('');
	let previewLoading = $state(false);
	let previewError = $state<string | null>(null);
	let sendQueued = $state(false);
	let sendLoading = $state(false);
	let sendError = $state<string | null>(null);

	const PREVIEW_CHANNELS = [
		{ value: 'email', label: 'Email' },
		{ value: 'sms', label: 'SMS' }
	];

	$effect(() => {
		if (activeTab !== 'vorschau') return;
		previewHtml = '';
		previewError = null;
		previewLoading = true;
		api
			.post<{ html: string }>('/api/_validator/compare-email-preview', {
				profile: preset.profil,
				time_window: [preset.hour_from, preset.hour_to],
				target_date: new Date().toISOString().slice(0, 10),
				winner_tags: []
			})
			.then((r) => {
				previewHtml = r.html;
			})
			.catch((e: unknown) => {
				previewError =
					e && typeof e === 'object' && 'error' in e
						? String((e as { error: unknown }).error)
						: e instanceof Error
							? e.message
							: 'Vorschau konnte nicht geladen werden';
			})
			.finally(() => {
				previewLoading = false;
			});
	});

	async function handleSend() {
		if (sendLoading) return;
		sendLoading = true;
		sendError = null;
		sendQueued = false;
		try {
			await api.post(`/api/compare/presets/${preset.id}/send`, {});
			sendQueued = true;
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			sendError = body?.detail ?? body?.error ?? 'Versand fehlgeschlagen';
		} finally {
			sendLoading = false;
		}
	}

	// Issue #527/#558 — Pause/Aktivieren mit Schedule-Gedächtnis
	let previousSchedule = $state<string>((preset.schedule && preset.schedule !== 'manual') ? preset.schedule : 'daily');
	let localSchedule = $state<string>(preset.schedule ?? 'manual');

	async function handleToggleActive() {
		const isPausing = localSchedule !== 'manual';
		if (isPausing) previousSchedule = localSchedule;
		const next = isPausing ? 'manual' : previousSchedule;
		try {
			await api.put(`/api/compare/presets/${preset.id}`, { ...preset, schedule: next });
			localSchedule = next;
		} catch {
			// State bleibt unverändert bei Fehler
		}
	}
</script>

<div class="compare-tabs" data-testid="compare-detail-tab-list">
	<Segmented options={segmentedOptions} selected={activeTab} onselect={handleValueChange} />

	{#if activeTab === 'uebersicht'}
		<div class="tab-panel" data-testid="compare-detail-panel-uebersicht">
			<!-- Monitoring-Card (weiß statt off-white Streifen) -->
			<Card padding={16} class="monitoring-card">
				<div class="monitoring-row">
					<div class="monitoring-item">
						<Dot tone={status === 'active' ? 'good' : 'neutral'} />
						<span class="monitoring-label-inline">{statusInfo.label}</span>
					</div>
					<div class="monitoring-item-col">
						<span class="monitoring-label">Nächster Versand</span>
						<span class="monitoring-value">{presetScheduleLabel(preset)}</span>
					</div>
					<div class="monitoring-item-col">
						<span class="monitoring-label">Zuletzt</span>
						<span class="monitoring-value">{formatLastSent(preset.letzter_versand)}</span>
					</div>
					<div class="monitoring-item-col">
						<span class="monitoring-label">Kanäle</span>
						<span class="monitoring-value">{preset.empfaenger.length}</span>
					</div>
				</div>
			</Card>

			<!-- 2×2 SummaryCard-Grid -->
			<div class="summary-grid">
				<Card padding={20}>
					<Eyebrow>Orte</Eyebrow>
					<p class="summary-value">{preset.location_ids.length} Kandidaten</p>
					<p class="summary-sub">{resolvedLocations[0]?.loc?.name ?? '—'}</p>
					<Btn variant="ghost" size="sm" onclick={() => handleValueChange('orte')}>Bearbeiten →</Btn>
				</Card>

				<Card padding={20}>
					<Eyebrow>Idealwerte</Eyebrow>
					<p class="summary-value">{preset.profil}</p>
					<p class="summary-sub">{Object.keys(idealRanges ?? {}).length} Metriken konfiguriert</p>
					<Btn variant="ghost" size="sm" onclick={() => handleValueChange('idealwerte')}>Bearbeiten →</Btn>
				</Card>

				<Card padding={20}>
					<Eyebrow>Layout</Eyebrow>
					<p class="summary-value">{channels.join(' · ')}</p>
					<p class="summary-sub">Spalten pro Kanal</p>
					<Btn variant="ghost" size="sm" onclick={() => handleValueChange('layout')}>Bearbeiten →</Btn>
				</Card>

				<Card padding={20}>
					<Eyebrow>Versand</Eyebrow>
					<p class="summary-value">{presetScheduleLabel(preset)}</p>
					<p class="summary-sub">{preset.hour_from}–{preset.hour_to} Uhr</p>
					<Btn variant="ghost" size="sm" onclick={() => handleValueChange('versand')}>Bearbeiten →</Btn>
				</Card>
			</div>

			<!-- Hinweis-Box -->
			<Card accent={true} padding={20} class="hint-box">
				<p class="hint-text">Gelesen wird das Briefing unterwegs im Postfach. Tab Vorschau dient nur zum Prüfen der Konfiguration.</p>
				<Btn variant="ghost" size="sm" onclick={() => handleValueChange('vorschau')}>Vorschau prüfen →</Btn>
			</Card>
		</div>
	{/if}

	{#if activeTab === 'orte'}
		<div class="tab-panel" data-testid="compare-detail-panel-orte">
			{#if resolvedLocations.length === 0}
				<p class="empty-state">Noch keine Orte ausgewählt.</p>
			{:else}
				{#each resolvedLocations as { rank, loc }}
					{#if loc}
						<CompareLocationRow {loc} index={rank} />
					{/if}
				{/each}
			{/if}
			<div class="footer-link">
				<Btn variant="ghost" size="sm">Ort hinzufügen</Btn>
			</div>
		</div>
	{/if}

	{#if activeTab === 'idealwerte'}
		<div class="tab-panel" data-testid="compare-detail-panel-idealwerte">
			{#if idealRanges && Object.keys(idealRanges).length > 0}
				{#each Object.entries(idealRanges) as [metric, r]}
					<CompareIdealRow
						item={{
							metric,
							range: `${r.min}–${r.max}${r.unit ? ' ' + r.unit : ''}`,
							weight: 'mittel'
						}}
					/>
				{/each}
			{:else}
				<p class="empty-state">Keine Idealwerte konfiguriert.</p>
			{/if}
			<div class="footer-link">
				<Btn variant="ghost" size="sm">Metrik hinzufügen</Btn>
			</div>
		</div>
	{/if}

	{#if activeTab === 'layout'}
		<div class="tab-panel" data-testid="compare-detail-panel-layout">
			{#each channels as ch}
				<CompareLayoutRow channel={ch} cols={CHANNEL_COLS[ch]} />
			{/each}
		</div>
	{/if}

	{#if activeTab === 'versand'}
		<div class="tab-panel" data-testid="compare-detail-panel-versand">
			<div class="versand-grid">
				<!-- Linke Spalte -->
				<div class="versand-left">
					<!-- Rhythmus & Vorausschau -->
					<Card padding={20}>
						<Eyebrow>Rhythmus & Vorausschau</Eyebrow>
						<DetailRow label="Zeitplan" value={presetScheduleLabel(preset)} />
						<DetailRow label="Zeitfenster" value="{preset.hour_from}–{preset.hour_to} Uhr" />
						<DetailRow label="Nächster Versand" value={presetScheduleLabel(preset)} divider="none" />
					</Card>

					<!-- Kanäle -->
					<Card padding={20} class="channel-card">
						<Eyebrow>Kanäle</Eyebrow>
						<div class="channel-row">
							<Dot tone={preset.empfaenger.length > 0 ? 'good' : 'neutral'} />
							<span class="channel-name">Email</span>
							<span class="channel-status">{preset.empfaenger.length > 0 ? 'verifiziert' : 'nicht verbunden'}</span>
							<Switch checked={preset.empfaenger.length > 0} disabled={true} size="sm" aria-label="Email-Kanal" />
						</div>
						<div class="channel-row">
							<Dot tone="neutral" />
							<span class="channel-name">Telegram</span>
							<span class="channel-status">nicht verbunden</span>
							<Switch checked={false} disabled={true} size="sm" aria-label="Telegram-Kanal" />
						</div>
						<div class="channel-row">
							<Dot tone="neutral" />
							<span class="channel-name">SMS</span>
							<span class="channel-status">nicht verbunden</span>
							<Switch checked={false} disabled={true} size="sm" aria-label="SMS-Kanal" />
						</div>
					</Card>
				</div>

				<!-- Rechte Spalte -->
				<div class="versand-right">
					<Card padding={20}>
						<Eyebrow>Aktivierung</Eyebrow>
						{#if localSchedule !== 'manual' && preset.name && preset.location_ids.length > 0}
							<div class="activation-status">
								<Dot tone="good" />
								<span class="activation-label">Aktiv</span>
							</div>
							<p class="activation-desc">Läuft automatisch</p>
							<Btn variant="quiet" size="sm" onclick={handleToggleActive}>Pausieren</Btn>
						{:else if !preset.name || preset.location_ids.length === 0}
							<div class="activation-status">
								<Dot tone="neutral" />
								<span class="activation-label">Entwurf</span>
							</div>
							<p class="activation-desc">Noch nicht aktiv</p>
							<Btn variant="primary" size="sm" onclick={handleToggleActive}>Aktivieren</Btn>
						{:else}
							<div class="activation-status">
								<Dot tone="neutral" />
								<span class="activation-label">Pausiert</span>
							</div>
							<Btn variant="primary" size="sm" onclick={handleToggleActive}>Aktivieren</Btn>
						{/if}
					</Card>

					<!-- Test-Briefing senden -->
					{#if sendQueued}
						<p class="send-success" data-testid="compare-send-success-versand">
							Briefing wurde zur Zustellung vorgemerkt.
						</p>
					{:else}
						<Btn
							variant="quiet"
							size="sm"
							disabled={sendLoading}
							onclick={handleSend}
							data-testid="compare-send-btn-versand"
						>
							{sendLoading ? 'Wird gesendet…' : 'Test-Briefing jetzt senden'}
						</Btn>
					{/if}
					{#if sendError !== null}
						<p class="send-error">{sendError}</p>
					{/if}
				</div>
			</div>
		</div>
	{/if}

	{#if activeTab === 'vorschau'}
		<div class="tab-panel" data-testid="compare-detail-panel-vorschau">
			<!-- Header: Eyebrow + Titel + Untertitel | Kanal-Umschalter + Disclaimer -->
			<div class="preview-header">
				<div class="preview-header-text">
					<Eyebrow>Vorschau · Verifikation</Eyebrow>
					<h2 class="preview-title">So sieht dein nächstes Briefing aus</h2>
					<p class="preview-subtitle">
						Pixel-Vorschau zum Gegencheck deiner Konfiguration.
						Gelesen wird das echte Briefing im jeweiligen Kanal.
					</p>
				</div>
				<div class="preview-header-right">
					<Segmented
						options={PREVIEW_CHANNELS}
						selected={previewChannel}
						onselect={(v) => (previewChannel = v as 'email' | 'sms')}
					/>
					<span class="preview-disclaimer">Beispielwerte · kein Live-Wetter</span>
				</div>
			</div>

			<!-- Preview-Fläche: warmes Grau, zentriert -->
			<div class="preview-stage">
				{#if previewLoading}
					<p class="preview-loading" data-testid="compare-preview-loading">
						Vorschau wird geladen…
					</p>
				{:else if previewError !== null}
					<p class="preview-error" data-testid="compare-preview-error">{previewError}</p>
				{:else if previewHtml !== '' && previewChannel === 'email'}
					<div style="width: 680px; max-width: 100%;">
						<iframe
							data-testid="compare-preview-iframe"
							srcdoc={previewHtml}
							sandbox="allow-same-origin"
							title="E-Mail-Vorschau"
						></iframe>
					</div>
				{/if}
				{#if previewChannel === 'sms'}
					<p class="preview-sms-hint" data-testid="compare-preview-sms-hint">
						SMS-Vorschau ist noch nicht verfügbar.
					</p>
				{/if}
			</div>

			<!-- Test-Briefing senden -->
			<div class="preview-send">
				{#if sendQueued}
					<p class="send-success" data-testid="compare-send-success">
						Briefing wurde zur Zustellung vorgemerkt.
					</p>
				{:else}
					<Btn
						variant="quiet"
						disabled={sendLoading}
						onclick={handleSend}
						data-testid="compare-send-btn"
					>
						{sendLoading ? 'Wird gesendet…' : 'Test-Briefing jetzt senden'}
					</Btn>
				{/if}
				{#if sendError !== null}
					<p class="send-error" data-testid="compare-send-error">{sendError}</p>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.compare-tabs :global([data-slot='segmented']) {
		display: flex;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.compare-tabs :global([data-slot='segmented-item']) {
		position: relative;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		border-bottom: 2px solid transparent;
		background: transparent;
		color: var(--g-ink);
		cursor: pointer;
	}
	.compare-tabs :global([data-slot='segmented-item'][data-active='true']) {
		background: transparent;
		color: var(--g-ink);
	}
	.compare-tabs :global([data-slot='segmented-item'][data-state='active']) {
		border-bottom-color: var(--g-accent);
	}

	.tab-panel {
		padding: 1.5rem 0;
	}

	.monitoring-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.monitoring-item-col {
		display: flex;
		flex-direction: column;
	}
	.monitoring-label {
		font-size: 0.75rem;
		color: var(--g-ink-3);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-family: var(--g-font-mono);
	}
	.monitoring-label-inline {
		font-weight: 500;
	}
	.monitoring-value {
		font-size: 0.875rem;
	}

	.empty-state {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		padding: 1rem 0;
	}

	.footer-link {
		margin-top: 1rem;
	}
	.footer-link a {
		color: var(--g-accent);
		font-size: 0.875rem;
		text-decoration: none;
	}
	.footer-link a:hover {
		text-decoration: underline;
	}

	.placeholder {
		font-size: 0.875rem;
		color: var(--g-ink);
		margin: 0 0 0.5rem 0;
	}
	.hint {
		font-size: 0.8125rem;
		color: var(--g-ink-3);
		margin: 0 0 1rem 0;
	}

	@media (max-width: 899px) {
		/* Scrollbares Tab-Band */
		.compare-tabs :global([data-slot='segmented']) {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x mandatory;
		}
		.compare-tabs :global([data-slot='segmented'])::-webkit-scrollbar {
			display: none;
		}

		/* Pill-Trigger: einzeilig, nicht schrumpfbar */
		.compare-tabs :global([data-slot='segmented-item']) {
			white-space: nowrap;
			flex-shrink: 0;
			scroll-snap-align: start;
			border-bottom: none;
			border-radius: var(--g-radius-pill, 99rem);
			padding: 0.375rem 0.875rem;
		}

		/* Aktiver Pill: gefüllt mit Akzentfarbe */
		.compare-tabs :global([data-slot='segmented-item'][data-state='active']) {
			background: var(--g-accent);
			color: var(--g-paper, #f6f4ee);
			border-bottom-color: transparent;
		}
	}

	/* ── Vorschau-Tab (Issue #514) — Design nach HubPreview ─────────────────── */
	.preview-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 24px;
		margin-bottom: 20px;
		flex-wrap: wrap;
	}
	.preview-header-text {
		max-width: 680px;
	}
	.preview-title {
		font-size: 1.5rem;
		font-weight: 600;
		letter-spacing: -0.02em;
		margin: 6px 0 6px;
		color: var(--g-ink);
	}
	.preview-subtitle {
		font-size: 0.84375rem;
		color: var(--g-ink-3);
		line-height: 1.5;
		margin: 0;
	}
	.preview-header-right {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 6px;
		flex-shrink: 0;
	}
	.preview-disclaimer {
		font-family: var(--g-font-mono);
		font-size: 0.625rem;
		color: var(--g-ink-4);
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}
	.preview-stage {
		display: flex;
		justify-content: center;
		padding: 24px;
		background: #e9e6dc;
		border-radius: var(--g-r-3, 0.75rem);
		border: 1px solid var(--g-rule, #d8d3c7);
		margin-bottom: 1rem;
		min-height: 120px;
		flex-direction: column;
		align-items: center;
	}
	.preview-stage iframe {
		width: 100%;
		min-height: 500px;
		border: 0;
		display: block;
	}
	.preview-loading {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		margin: 0;
	}
	.preview-error {
		font-size: 0.875rem;
		color: var(--g-danger, #dc2626);
		margin: 0;
	}
	.preview-sms-hint {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		margin: 0.5rem 0 0;
		font-style: italic;
	}
	.preview-send {
		margin-top: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: flex-start;
	}
	.send-success {
		font-size: 0.875rem;
		color: var(--g-success, #16a34a);
		margin: 0;
	}
	.send-error {
		font-size: 0.875rem;
		color: var(--g-danger, #dc2626);
		margin: 0;
	}

	@media (max-width: 899px) {
		.preview-header {
			flex-direction: column;
			align-items: flex-start;
		}
		.preview-header-right {
			align-items: flex-start;
		}
		.preview-stage {
			padding: 12px;
		}
	}

	/* ── Issue #526 — Übersicht-Tab ─────────────────────────────────────────── */
	.monitoring-card {
		margin-bottom: 1.5rem;
	}
	.monitoring-row {
		display: flex;
		gap: 2rem;
		flex-wrap: wrap;
		align-items: center;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.summary-value {
		font-size: 1rem;
		font-weight: 600;
		margin: 0.5rem 0 0.25rem;
		color: var(--g-ink);
	}
	.summary-sub {
		font-size: 0.8125rem;
		color: var(--g-ink-3);
		margin: 0 0 0.75rem;
	}

	.hint-box {
		margin-top: 0.5rem;
	}
	.hint-text {
		font-size: 0.875rem;
		color: var(--g-ink-2);
		line-height: 1.5;
		margin: 0 0 0.75rem;
	}

	/* ── Issue #527 — Versand-Tab ────────────────────────────────────────────── */
	.versand-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
		align-items: start;
	}
	.versand-left {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.versand-right {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.channel-card {
		margin-top: 0;
	}
	.channel-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 0;
		border-bottom: 1px dashed var(--g-rule-soft);
	}
	.channel-row:last-child {
		border-bottom: none;
	}
	.channel-name {
		flex: 1;
		font-size: 0.875rem;
		font-weight: 500;
	}
	.channel-status {
		font-size: 0.75rem;
		color: var(--g-ink-3);
		font-family: var(--g-font-mono);
	}

	.activation-status {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.activation-label {
		font-weight: 600;
		font-size: 0.9375rem;
	}
	.activation-desc {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		margin: 0 0 0.75rem;
	}

	@media (max-width: 899px) {
		.summary-grid {
			grid-template-columns: 1fr;
		}
		.versand-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
