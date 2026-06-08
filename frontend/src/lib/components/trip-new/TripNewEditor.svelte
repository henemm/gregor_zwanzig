<script lang="ts">
	// Issue #622 — Progressive Tab Editor für /trips/new (Desktop, Slice 1).
	// Spec: docs/specs/modules/issue_622_trip_new_progressive_editor.md
	// Design: docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2.jsx
	// Factory-Pattern für alle Event-Handler (Safari-Closure-Schutz, CLAUDE.md).

	import { goto } from '$app/navigation';
	import { api } from '$lib/api.js';
	import { Eyebrow, Btn, Input, TopoBg } from '$lib/components/atoms';
	import WeatherMetricsTab from '$lib/components/trip-detail/WeatherMetricsTab.svelte';
	import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';
	import EditStagesPanelNew from '$lib/components/edit/EditStagesPanelNew.svelte';
	import { AlertRulesEditor } from '$lib/components/organisms';
	import type { Trip, ReportConfig, AlertRule, WeatherConfigMetric, Stage, Waypoint } from '$lib/types';
	import {
		type TabId,
		type CreateTripState,
		unlockedTabs,
		doneTabs,
		stageDate,
		progressCount,
		canSave,
		buildCreateTripPayload,
	} from './tripNewLogic.ts';

	// ── Tab-Definitionen (1:1 TN_TAB_DEFS) ──────────────────────────────────
	const TAB_DEFS: { id: TabId; label: string; lockHint: string | null; optional: boolean }[] = [
		{ id: 'route',     label: 'Route',            lockHint: null,                             optional: false },
		{ id: 'etappen',   label: 'Etappen & GPX',    lockHint: 'erst Tour-Name + Startdatum',    optional: false },
		{ id: 'wegpunkte', label: 'Wegpunkte prüfen', lockHint: 'erst alle GPX hochladen',        optional: true  },
		{ id: 'metriken',  label: 'Wetter-Metriken',  lockHint: 'erst alle GPX hochladen',        optional: false },
		{ id: 'zeitplan',  label: 'Briefing-Zeitplan',lockHint: 'erst Wetter-Metriken öffnen',    optional: false },
		{ id: 'alerts',    label: 'Alerts',            lockHint: 'erst Zeitplan öffnen',           optional: false },
	];

	// ── Lokaler Anlege-State ──────────────────────────────────────────────────
	let name = $state('');
	let region = $state('');
	let startDate = $state('');

	interface StageLocal { id: number; name: string; gpx: { file: string; km: number; asc: number } | null; waypoints: Waypoint[] }
	let stages = $state<StageLocal[]>([
		{ id: 1, name: '', gpx: null, waypoints: [] },
		{ id: 2, name: '', gpx: null, waypoints: [] },
	]);

	let weatherMetrics = $state<WeatherConfigMetric[]>([]);
	let channels = $state({ email: true, telegram: true, sms: false });
	let reportConfig = $state<ReportConfig | undefined>(undefined);
	let alertRules = $state<AlertRule[]>([]);

	// Visited-Flags (Tab-Besuch setzt done)
	let wtVisited = $state(false);
	let ztVisited = $state(false);

	let activeTab = $state<TabId>('route');

	// Stub-Trip für WeatherMetricsTab (createMode — kein PUT)
	const stubTrip = $derived<Trip>({
		id: '__new__',
		name: name || 'Neue Tour',
		stages: [],
		display_config: { channels, metrics: weatherMetrics } as unknown as Trip['display_config'],
	});

	// Saving state
	let saving = $state(false);
	let saveError: string | null = $state(null);

	// ── Abgeleitete Zustandsgrößen ────────────────────────────────────────────
	const etDone = $derived(stages.length > 0 && stages.every(s => s.gpx !== null));
	const unlocked = $derived(unlockedTabs(name, startDate, etDone, wtVisited, ztVisited));
	const done = $derived(doneTabs(name, startDate, etDone, wtVisited, ztVisited));
	const ready = $derived(canSave(done));
	const gpxCount = $derived(stages.filter(s => s.gpx !== null).length);
	const progressN = $derived(progressCount(done));

	// Flash-State für gesperrte Tabs
	let flashTab = $state<TabId | null>(null);

	// ── Tab-Wechsel (Factory-Pattern) ─────────────────────────────────────────
	function makeTabHandler(id: TabId) {
		return function doSwitch() {
			if (unlocked.has(id)) {
				switchTab(id);
			} else {
				flashTab = id;
				setTimeout(() => { flashTab = null; }, 500);
			}
		};
	}

	function switchTab(id: TabId) {
		const prev = activeTab;
		// Issue #658 — beim Verlassen des Wegpunkte-Tabs Editor-Edits zurückschreiben.
		if (prev === 'wegpunkte' && id !== 'wegpunkte') syncEditorBack();
		activeTab = id;
		// Issue #658 F001-Fix: Rebuild nur bei echtem Tab-EINTRITT (prev !== 'wegpunkte'),
		// damit ein erneuter Klick auf den bereits aktiven Tab keine ungespeicherten
		// Wegpunkt-Edits verwirft.
		if (id === 'wegpunkte' && prev !== 'wegpunkte') editorStages = buildEditorStages();
		if (id === 'metriken') wtVisited = true;
		if (id === 'zeitplan') ztVisited = true;
	}

	// ── Stage-Brücke: lokaler Create-State ⇄ EditStagesPanelNew (Issue #658) ──
	// EditStagesPanelNew arbeitet auf Stage[] (string-IDs, waypoints[]) und mutiert
	// das Array per bind:stages in place. Wir spiegeln den kanonischen lokalen State
	// (StageLocal, numerische IDs) beim Öffnen des Tabs in `editorStages` und
	// schreiben Wegpunkt-Edits per Index zurück — kein PUT (kein tripId), Persistenz
	// erst beim finalen POST. String-ID = `s<numerische id>` (stabile Brücke).
	let editorStages = $state<Stage[]>([]);

	function buildEditorStages(): Stage[] {
		return stages.map((s, idx) => ({
			id: `s${s.id}`,
			name: s.name || `Etappe ${idx + 1}`,
			date: stageDateISO(startDate, idx),
			waypoints: s.waypoints ?? [],
		}));
	}

	function stageDateISO(start: string, offset: number): string {
		if (!start) return '';
		const parts = start.split('-').map(Number);
		const dt = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
		dt.setUTCDate(dt.getUTCDate() + offset);
		return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`;
	}

	// Editor-Mutationen (Wegpunkt-Edits) per Index in den kanonischen State zurück.
	function syncEditorBack(): void {
		if (editorStages.length === 0) return;
		stages = stages.map((s, idx) => {
			const es = editorStages[idx];
			return es ? { ...s, waypoints: es.waypoints } : s;
		});
	}

	// ── Route-Tab-Handlers ────────────────────────────────────────────────────
	function makeNameHandler() { return (e: Event) => { name = (e.target as HTMLInputElement).value; }; }
	function makeRegionHandler() { return (e: Event) => { region = (e.target as HTMLInputElement).value.slice(0, 50); }; }
	function makeDateHandler() { return (e: Event) => { startDate = (e.target as HTMLInputElement).value; }; }
	function makeContinueToEtappenHandler() { return () => switchTab('etappen'); }

	// ── Etappen-Tab-Handlers ──────────────────────────────────────────────────
	function makeStageNameHandler(id: number) {
		return (e: Event) => {
			stages = stages.map(s => s.id === id ? { ...s, name: (e.target as HTMLInputElement).value } : s);
		};
	}

	function makeGpxUploadHandler(idx: number, stageId: number) {
		return async (e: Event) => {
			const file = (e.target as HTMLInputElement).files?.[0];
			if (!file) return;
			const iso = startDate ? (() => {
				const parts = startDate.split('-').map(Number);
				const dt = new Date(Date.UTC(parts[0], parts[1]-1, parts[2]));
				dt.setUTCDate(dt.getUTCDate() + idx);
				return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth()+1).padStart(2,'0')}-${String(dt.getUTCDate()).padStart(2,'0')}`;
			})() : '';
			try {
				const fd = new FormData();
				fd.append('file', file);
				const resp = await fetch(`/api/gpx/parse?stage_date=${iso}&start_hour=7`, { method: 'POST', body: fd });
				if (resp.ok) {
					const data = await resp.json();
					const km = data.distance_km ?? data.km ?? '–';
					const asc = data.ascent_m ?? data.asc ?? '–';
					// Issue #658 — aus GPX berechnete Wegpunkte je Etappe in den lokalen State.
					const waypoints: Waypoint[] = (data.waypoints ?? []) as Waypoint[];
					stages = stages.map(s => s.id === stageId ? { ...s, gpx: { file: file.name, km, asc }, waypoints } : s);
				}
			} catch {
				// Upload fehlgeschlagen — GPX-Slot bleibt leer
			}
		};
	}

	function makeGpxRemoveHandler(stageId: number) {
		return () => { stages = stages.map(s => s.id === stageId ? { ...s, gpx: null } : s); };
	}

	function makeRemoveStageHandler(stageId: number) {
		return () => { stages = stages.filter(s => s.id !== stageId); };
	}

	function makeAddStageHandler() {
		return () => {
			const nextId = (stages.length ? Math.max(...stages.map(s => s.id)) : 0) + 1;
			stages = [...stages, { id: nextId, name: '', gpx: null, waypoints: [] }];
		};
	}

	function makeEtappenContinueHandler(target: TabId) {
		return () => switchTab(target);
	}

	// ── Kanal-Änderung aus WeatherMetricsTab ──────────────────────────────────
	function handleChannelsChange(c: { email: boolean; telegram: boolean; sms: boolean }) {
		channels = { ...c };
	}

	// ── Speichern ─────────────────────────────────────────────────────────────
	function makeSaveHandler() {
		return async function doSave() {
			if (!ready) return;
			saveError = null;
			saving = true;
			// Issue #658 — etwaige offene Editor-Edits vor dem POST in den State holen.
			if (activeTab === 'wegpunkte') syncEditorBack();
			try {
				const state: CreateTripState = {
					name,
					region: region || undefined,
					startDate,
					stages: stages.map(s => ({ id: s.id, name: s.name, waypoints: s.waypoints })),
					weatherMetrics,
					channels,
					reportConfig,
					alertRules: alertRules.length > 0 ? alertRules : undefined,
				};
				const payload = buildCreateTripPayload(state);
				const created = await api.post<Trip>('/api/trips', payload);
				await goto(`/trips/${created.id}`);
			} catch (e: unknown) {
				const err = e as { detail?: string; error?: string };
				saveError = err.detail ?? err.error ?? 'Fehler beim Speichern';
			} finally {
				saving = false;
			}
		};
	}

	function makeCancelHandler() {
		return () => goto('/trips');
	}

	const onSave = makeSaveHandler();
	const onCancel = makeCancelHandler();
</script>

<div data-testid="trip-new-editor" style="display: flex; min-height: 100%; background: var(--g-paper);">
	<main style="flex: 1; position: relative; overflow-y: auto; overflow-x: hidden;">
		<TopoBg opacity={0.12} />

		<!-- Breadcrumb + Aktionen -->
		<div style="position: relative; padding: 14px 40px; border-bottom: 1px solid var(--g-rule-soft); display: flex; justify-content: space-between; align-items: center;">
			<div class="mono" style="font-size: 11px; color: var(--g-ink-3); letter-spacing: 0.06em;">
				<span style="opacity: 0.6;">Trips</span>
				<span style="margin: 0 8px;">/</span>
				<span style="color: var(--g-ink);">Neue Tour</span>
			</div>
			<div style="display: flex; gap: 8px; align-items: center;">
				{#if !ready}
					<span class="mono" style="font-size: 10.5px; color: var(--g-ink-4);">Zeitplan einrichten zum Speichern</span>
				{/if}
				<button type="button" onclick={onCancel}
					style="padding: 6px 12px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
					Abbrechen
				</button>
				<button type="button" onclick={onSave} disabled={!ready || saving}
					data-testid="trip-new-save-btn"
					style="padding: 6px 12px; border-radius: var(--g-r-2); border: none; background: var(--g-ink); color: var(--g-paper); font-size: 13px; font-weight: 500; cursor: {ready && !saving ? 'pointer' : 'not-allowed'}; opacity: {ready && !saving ? 1 : 0.4};">
					{saving ? 'Speichere…' : 'Tour speichern'}
				</button>
			</div>
		</div>

		<!-- Hero -->
		<div style="position: relative; padding: 20px 40px 14px;">
			<Eyebrow>Neue Tour anlegen</Eyebrow>
			<h1 style="font-size: 32px; font-weight: 600; letter-spacing: -0.02em; margin: 4px 0 0; line-height: 1.1; color: {name.trim() ? 'var(--g-ink)' : 'var(--g-ink-4)'};">
				{name.trim() || 'Noch kein Name'}
			</h1>
			<!-- Fortschrittsbalken (TN_Progress) -->
			<div style="display: flex; align-items: center; gap: 10px; margin-top: 7px;">
				<div style="display: flex; gap: 3px;">
					{#each ['route', 'etappen', 'metriken', 'zeitplan'] as step}
						<div style="width: 24px; height: 3px; border-radius: 2px; background: {done.has(step as TabId) ? 'var(--g-accent)' : 'var(--g-rule)'}; transition: background 350ms;"></div>
					{/each}
				</div>
				<span class="mono" style="font-size: 10.5px; color: var(--g-ink-4); letter-spacing: 0.04em;">
					{progressN === 0 ? 'Noch nichts eingerichtet' : `${progressN} / 4 Abschnitte eingerichtet`}
				</span>
			</div>
		</div>

		<!-- Tab-Bar (TN_TabBar) -->
		<div style="border-bottom: 1px solid var(--g-rule); padding: 0 40px; display: flex; gap: 0; overflow-x: auto;">
			{#each TAB_DEFS as t}
				{@const isActive = t.id === activeTab}
				{@const isOpen = unlocked.has(t.id)}
				{@const isDone = done.has(t.id) && !isActive}
				<div
					role="tab"
					tabindex={isOpen ? 0 : -1}
					aria-selected={isActive}
					onclick={makeTabHandler(t.id)}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') makeTabHandler(t.id)(); }}
					title={!isOpen && t.lockHint ? `Gesperrt — ${t.lockHint}` : undefined}
					style="padding: 12px 16px; cursor: {isOpen ? 'pointer' : 'not-allowed'}; font-size: 13px; font-weight: {isActive ? 600 : 500}; color: {isActive ? 'var(--g-ink)' : isOpen ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; border-bottom: {isActive ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; display: flex; align-items: center; gap: 5px; white-space: nowrap; opacity: {isOpen ? 1 : 0.34}; transition: opacity 250ms, color 200ms; transform: {flashTab === t.id ? 'translateX(2px)' : 'none'}; user-select: none;">
					{t.label}
					{#if t.optional && isOpen}
						<span class="mono" style="font-size: 9px; font-weight: 600; letter-spacing: 0.06em; padding: 1px 5px; border-radius: 3px; background: rgba(196,90,42,0.10); color: var(--g-accent-deep); text-transform: uppercase;">optional</span>
					{/if}
					{#if isDone}
						<span style="font-size: 10px; font-weight: 700; padding: 2px 5px; border-radius: 3px; background: rgba(61,107,58,0.12); color: var(--g-good); font-family: var(--g-font-mono);">✓</span>
					{/if}
					{#if !isOpen}
						<span style="font-size: 10px; color: var(--g-ink-4); font-family: var(--g-font-mono); opacity: 0.7;">⊘</span>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Fehler-Banner -->
		{#if saveError}
			<div style="padding: 10px 40px; background: rgba(180,30,30,0.08); border-bottom: 1px solid rgba(180,30,30,0.2);">
				<span class="mono" style="font-size: 11px; color: var(--g-bad);">⚠ {saveError}</span>
			</div>
		{/if}

		<!-- Tab-Inhalt -->
		{#if activeTab === 'route'}
			<!-- Route-Tab (TN_RouteTab) -->
			<div style="position: relative; padding: 28px 40px 60px;">
				<TopoBg opacity={0.10} />
				<div style="position: relative; max-width: 640px;">
					<Eyebrow style="margin-bottom: 14px;">Tour-Grunddaten</Eyebrow>

					<div style="margin-bottom: 18px;">
						<label style="display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--g-ink-3); margin-bottom: 6px;">
							Tour-Name <span style="color: var(--g-bad);">*</span>
						</label>
						<input type="text" value={name} oninput={makeNameHandler()}
							placeholder="z.B. Karnischer Höhenweg 2026"
							data-testid="trip-new-name-input"
							autofocus
							style="width: 100%; box-sizing: border-box; padding: 9px 12px; font-size: 14px; font-family: var(--g-font-sans); border: 1.5px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card); color: var(--g-ink); outline: none;" />
					</div>

					<div style="margin-bottom: 18px;">
						<label style="display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--g-ink-3); margin-bottom: 6px;">
							Region
							<span class="mono" style="font-size: 10px; color: var(--g-ink-4); text-transform: none; letter-spacing: normal; font-weight: 400; margin-left: 6px;">optional · max 50</span>
						</label>
						<input type="text" value={region} oninput={makeRegionHandler()}
							placeholder="z.B. Karnische Alpen"
							maxlength="50"
							style="width: 100%; box-sizing: border-box; padding: 9px 12px; font-size: 14px; font-family: var(--g-font-sans); border: 1.5px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card); color: var(--g-ink); outline: none;" />
					</div>

					<div style="margin-bottom: 18px;">
						<label style="display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--g-ink-3); margin-bottom: 6px;">
							Startdatum <span style="color: var(--g-bad);">*</span>
						</label>
						<input type="date" value={startDate} onchange={makeDateHandler()}
							data-testid="trip-new-date-input"
							style="width: 100%; box-sizing: border-box; padding: 9px 12px; font-size: 14px; font-family: var(--g-font-mono); border: 1.5px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card); color: var(--g-ink); outline: none; appearance: none; -webkit-appearance: none;" />
						{#if startDate}
							<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 6px;">
								Etappe 1 startet am {stageDate(startDate, 0)?.replace(/\.$/, '')} — jede folgende Etappe +1 Tag.
							</div>
						{/if}
					</div>

					<div style="margin-top: 12px; padding: 12px 16px; border-radius: var(--g-r-2); background: var(--g-accent-tint); border: 1px solid var(--g-accent-rule);">
						<div class="mono" style="font-size: 11px; color: var(--g-accent-deep); line-height: 1.6;">
							GPX-Dateien lädst du im nächsten Schritt hoch — eine Datei pro Etappe.
						</div>
					</div>

					<div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--g-rule); display: flex; justify-content: flex-end; align-items: center; gap: 12px;">
						{#if !name.trim()}
							<span class="mono" style="font-size: 11px; color: var(--g-ink-4);">⊘ Tour-Name fehlt</span>
						{:else if !startDate}
							<span class="mono" style="font-size: 11px; color: var(--g-ink-4);">⊘ Startdatum fehlt</span>
						{/if}
						<button type="button"
							disabled={!name.trim() || !startDate}
							onclick={makeContinueToEtappenHandler()}
							data-testid="trip-new-continue-etappen"
							style="padding: 8px 16px; border-radius: var(--g-r-2); border: none; background: {name.trim() && startDate ? 'var(--g-accent)' : 'var(--g-ink-4)'}; color: #fff; font-size: 13px; font-weight: 600; cursor: {name.trim() && startDate ? 'pointer' : 'not-allowed'}; opacity: {name.trim() && startDate ? 1 : 0.45};">
							Etappen anlegen →
						</button>
					</div>
				</div>
			</div>

		{:else if activeTab === 'etappen'}
			<!-- Etappen-Tab (TN_EtappenTab) -->
			<div style="position: relative; padding: 28px 40px 60px;">
				<TopoBg opacity={0.10} />
				<div style="position: relative; max-width: 900px;">
					<div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px;">
						<div>
							<Eyebrow style="margin-bottom: 2px;">Etappen</Eyebrow>
							<h2 style="font-size: 20px; font-weight: 600; letter-spacing: -0.01em; margin: 0;">
								Namen vergeben &amp; GPX-Datei je Etappe hochladen
							</h2>
						</div>
						<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 3px;">
							<span class="mono" style="font-size: 11px; color: {etDone && stages.length > 0 ? 'var(--g-good)' : 'var(--g-ink-4)'};">
								{gpxCount} / {stages.length} GPX geladen
							</span>
							{#if startDate}
								<span class="mono" style="font-size: 10px; color: var(--g-ink-4);">
									Start: {stageDate(startDate, 0)?.replace(/\.$/, '')}
								</span>
							{/if}
						</div>
					</div>

					<!-- Spaltenheader -->
					<div style="display: grid; grid-template-columns: 36px 1fr 60px minmax(170px, 200px) 28px; gap: 10px; padding: 0 14px 5px;">
						{#each ['', 'Etappenname', 'Datum', 'GPX-Datei', ''] as h}
							<span class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.06em; text-transform: uppercase;">{h}</span>
						{/each}
					</div>

					<div style="display: flex; flex-direction: column; gap: 3px; margin-bottom: 14px;">
						{#each stages as s, idx}
							{@const dateStr = stageDate(startDate, idx)}
							{@const hasGpx = s.gpx !== null}
							<div style="display: grid; grid-template-columns: 36px 1fr 60px minmax(170px, 200px) 28px; gap: 10px; align-items: center; padding: 8px 14px; background: var(--g-card); border: 1px solid {hasGpx ? 'rgba(61,107,58,0.2)' : 'var(--g-rule)'}; border-radius: var(--g-r-2); transition: border-color 200ms;">
								<!-- T-Badge -->
								<span class="mono" style="font-size: 10px; font-weight: 700; text-align: center; color: var(--g-accent-deep); background: var(--g-accent-tint); padding: 2px 4px; border-radius: 999px;">
									T{String(idx + 1).padStart(2, '0')}
								</span>

								<!-- Inline-Name -->
								<input type="text" value={s.name} oninput={makeStageNameHandler(s.id)}
									placeholder="Etappe {idx + 1} benennen …"
									style="width: 100%; box-sizing: border-box; background: transparent; border: 1.5px solid transparent; border-radius: var(--g-r-1); padding: 4px 2px; font-size: 13.5px; font-weight: {s.name ? 500 : 400}; font-family: var(--g-font-sans); color: {s.name ? 'var(--g-ink)' : 'var(--g-ink-4)'}; outline: none;" />

								<!-- Auto-Datum -->
								<span class="mono" style="font-size: 11px; color: {dateStr ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; white-space: nowrap;">
									{dateStr || '–'}
								</span>

								<!-- GPX-Slot -->
								{#if s.gpx}
									<div style="display: flex; align-items: center; gap: 7px; padding: 5px 10px; border-radius: var(--g-r-2); background: rgba(61,107,58,0.08); border: 1px solid rgba(61,107,58,0.22);">
										<span style="width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0; background: var(--g-good); display: flex; align-items: center; justify-content: center;">
											<svg width="9" height="9" viewBox="0 0 10 10" fill="none"><polyline points="1.5,5.5 4,8 8.5,2" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
										</span>
										<div style="flex: 1; min-width: 0;">
											<div class="mono" style="font-size: 10px; font-weight: 600; color: var(--g-ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{s.gpx.file}</div>
											<div class="mono" style="font-size: 9.5px; color: var(--g-ink-3);">{s.gpx.km} km · ↑{s.gpx.asc} m</div>
										</div>
										<button type="button" onclick={makeGpxRemoveHandler(s.id)} title="GPX entfernen"
											style="background: transparent; border: none; cursor: pointer; color: var(--g-ink-4); font-size: 13px; padding: 1px 3px; line-height: 1; flex-shrink: 0;">×</button>
									</div>
								{:else}
									<label style="padding: 6px 11px; border-radius: var(--g-r-2); border: 1.5px dashed var(--g-rule); background: transparent; cursor: pointer; display: flex; align-items: center; gap: 6px;">
										<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
											<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
										</svg>
										<span class="mono" style="font-size: 10.5px; font-weight: 600; letter-spacing: 0.02em; color: var(--g-ink-4); white-space: nowrap;">GPX hochladen</span>
										<input type="file" accept=".gpx" style="display: none;" onchange={makeGpxUploadHandler(idx, s.id)} />
									</label>
								{/if}

								<!-- Entfernen -->
								<button type="button" onclick={makeRemoveStageHandler(s.id)}
									style="background: transparent; border: none; cursor: pointer; color: var(--g-ink-4); font-size: 15px; padding: 2px 4px; line-height: 1; text-align: center;">×</button>
							</div>
						{/each}
					</div>

					<div style="display: flex; gap: 8px; margin-bottom: 24px;">
						<button type="button" onclick={makeAddStageHandler()}
							style="padding: 6px 12px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 12px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
							+ Etappe hinzufügen
						</button>
					</div>

					<!-- Hinweis GPX fehlen -->
					{#if !etDone && stages.length > 0}
						<div style="padding: 10px 15px; border-radius: var(--g-r-2); background: var(--g-paper); border: 1px solid var(--g-rule); margin-bottom: 20px;">
							<span class="mono" style="font-size: 11px; color: var(--g-ink-3);">
								⊘ {stages.length - gpxCount} Etappe{stages.length - gpxCount !== 1 ? 'n' : ''} ohne GPX-Datei —
								nach dem Upload werden Wegpunkte automatisch berechnet.
							</span>
						</div>
					{/if}

					<!-- Hinweis alle GPX geladen -->
					{#if etDone && stages.length > 0}
						<div style="padding: 10px 15px; border-radius: var(--g-r-2); background: rgba(61,107,58,0.07); border: 1px solid rgba(61,107,58,0.2); margin-bottom: 20px;">
							<span class="mono" style="font-size: 11px; color: var(--g-good);">
								✓ Alle GPX geladen — Wegpunkte werden berechnet.
								Jetzt weiter zu „Wegpunkte prüfen" (optional) oder direkt zu „Wetter-Metriken".
							</span>
						</div>
					{/if}

					<div style="padding-top: 20px; border-top: 1px solid var(--g-rule); display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
						{#if etDone}
							<button type="button" onclick={makeEtappenContinueHandler('metriken')}
								style="padding: 8px 16px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
								Wetter direkt →
							</button>
						{/if}
						<button type="button"
							disabled={!etDone}
							onclick={makeEtappenContinueHandler('wegpunkte')}
							style="padding: 8px 16px; border-radius: var(--g-r-2); border: none; background: {etDone ? 'var(--g-accent)' : 'var(--g-ink-4)'}; color: #fff; font-size: 13px; font-weight: 600; cursor: {etDone ? 'pointer' : 'not-allowed'}; opacity: {etDone ? 1 : 0.45};">
							Wegpunkte prüfen →
						</button>
					</div>
				</div>
			</div>

		{:else if activeTab === 'wegpunkte'}
			<!-- Wegpunkte-Tab (Issue #658) — Info-Banner + eingebetteter Editor + Footer -->
			<div style="position: relative;">
				<!-- Info-Banner (1:1 TN_WegpunkteTab) -->
				<div style="padding: 14px 40px; background: var(--g-card); border-bottom: 1px solid var(--g-rule-soft); display: flex; justify-content: space-between; align-items: center; gap: 24px;">
					<div style="flex: 1;">
						<div style="font-size: 13.5px; font-weight: 600; margin-bottom: 3px;">
							Wegpunkte aus GPX berechnet — optional prüfen
						</div>
						<div class="mono" style="font-size: 11px; color: var(--g-ink-3); line-height: 1.55;">
							Wegpunkte sind Wetterscheiden — Punkte, an denen sich Höhe, Exposition oder Geländekammer ändert.
							Du kannst sie umbenennen, verschieben oder ergänzen. Diesen Schritt kannst du auch überspringen.
						</div>
					</div>
					<div style="display: flex; gap: 8px; flex-shrink: 0;">
						<button type="button" onclick={makeEtappenContinueHandler('metriken')}
							style="padding: 6px 12px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
							Überspringen →
						</button>
						<button type="button" onclick={makeEtappenContinueHandler('metriken')}
							style="padding: 6px 12px; border-radius: var(--g-r-2); border: none; background: var(--g-accent); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;">
							Wegpunkte übernehmen →
						</button>
					</div>
				</div>

				<!-- Eingebetteter Wegpunkt-Editor: kein tripId → kein PUT, kein Save-Bar -->
				<EditStagesPanelNew bind:stages={editorStages} showSave={false} />

				<!-- Footer (1:1 TN_WegpunkteTab) -->
				<div style="padding: 20px 40px; border-top: 1px solid var(--g-rule); background: var(--g-card); display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
					<button type="button" onclick={makeEtappenContinueHandler('metriken')}
						style="padding: 8px 16px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
						Überspringen
					</button>
					<button type="button" onclick={makeEtappenContinueHandler('metriken')}
						style="padding: 8px 16px; border-radius: var(--g-r-2); border: none; background: var(--g-accent); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;">
						Wegpunkte übernehmen →
					</button>
				</div>
			</div>

		{:else if activeTab === 'metriken'}
			<!-- Wetter-Tab: reuse WeatherMetricsTab im createMode -->
			<WeatherMetricsTab trip={stubTrip} createMode={true} onChannelsChange={handleChannelsChange} />

		{:else if activeTab === 'zeitplan'}
			<!-- Zeitplan-Tab: reuse EditReportConfigSection im create-Modus -->
			<div style="padding: 32px 40px 60px; max-width: 720px;">
				<EditReportConfigSection bind:reportConfig mode="create" weatherChannels={channels} />
			</div>

		{:else if activeTab === 'alerts'}
			<!-- Alerts-Tab: reuse AlertRulesEditor mit bind:rules -->
			<div style="padding: 32px 40px 60px;">
				<AlertRulesEditor bind:rules={alertRules} />
			</div>
		{/if}
	</main>
</div>
