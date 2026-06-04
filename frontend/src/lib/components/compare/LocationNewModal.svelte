<script lang="ts">
	// Issue #588 — LocationNewModal: 1:1-Uebersetzung von screen-location-new.jsx
	//
	// Vollflächiges Modal-Overlay (position:fixed). Kein Shadcn Dialog-Wrapper.
	// Drei Sektionen: Smart-Import, Benennung, Meteorologische Brille.
	//
	// Spec: docs/specs/modules/issue_588_location_new.md

	import type { ActivityProfile } from '$lib/types.js';
	import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Eyebrow, Pill, KV, TopoBg, Btn, Card } from '$lib/components/atoms';

	interface Props {
		onsave: () => void;
		oncancel: () => void;
	}

	let { onsave, oncancel }: Props = $props();

	interface ResolveResult {
		lat: number;
		lon: number;
		elevation_m?: number;
		timezone: string;
		suggested_name?: string;
		region?: string;
		source_type: string;
	}

	let importInput = $state('');
	let resolvedPreview: ResolveResult | null = $state(null);
	let resolving = $state(false);
	let nameInput = $state('');
	let groupInput = $state('');
	let activeProfile: ActivityProfile = $state('wandern');
	let saving = $state(false);
	let saveError: string | null = $state(null);

	async function resolveLocation() {
		if (!importInput.trim() || resolving) return;
		resolving = true;
		try {
			const result = await api.post<ResolveResult>('/api/locations/resolve', { input: importInput });
			resolvedPreview = result;
			if (result.suggested_name && !nameInput.trim()) nameInput = result.suggested_name;
		} catch {
			resolvedPreview = null;
		} finally {
			resolving = false;
		}
	}

	async function saveLocation() {
		if (!nameInput.trim() || saving) return;
		saving = true;
		saveError = null;
		try {
			const id = nameInput.trim().toLowerCase().replace(/[^a-z0-9äöüß]+/g, '-').replace(/^-|-$/g, '');
			await api.post('/api/locations', {
				id,
				name: nameInput.trim(),
				lat: resolvedPreview?.lat ?? 0,
				lon: resolvedPreview?.lon ?? 0,
				elevation_m: resolvedPreview?.elevation_m,
				group_id: groupInput.trim() || undefined,
				activity_profile: activeProfile,
			});
			onsave();
		} catch (e: unknown) {
			saveError = (e as { detail?: string; error?: string })?.detail ?? 'Fehler beim Speichern';
		} finally {
			saving = false;
		}
	}
</script>

<!-- Snippet: nummeriertes Sektions-Label (top-level für alle 3 Sektionen) -->
{#snippet LocSectionTag(n: number, label: string)}
	<div style="display:flex; align-items:center; gap:10px;">
		<span style="width:22px; height:22px; background:var(--g-ink); color:var(--g-paper); border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-family:var(--g-font-mono); font-size:11px; font-weight:600;">{n}</span>
		<span style="font-size:13px; font-weight:600; color:var(--g-ink); letter-spacing:-0.005em;">{label}</span>
	</div>
{/snippet}

<!-- Snippet: Format-Chip (innerhalb Sektion 1) -->
{#snippet LocFormatChip(kind: string, label: string, example: string)}
	<div title={example} style="padding:6px 10px; border:1px solid var(--g-rule); border-radius:var(--g-r-2); font-size:11px; color:var(--g-ink-3); background:var(--g-card-alt); display:inline-flex; align-items:center; gap:6px;">
		<span style="font-family:var(--g-font-mono); font-weight:600; color:var(--g-ink-2);">{label}</span>
		<span style="color:var(--g-ink-4);">·</span>
		<span style="font-family:var(--g-font-mono); color:var(--g-ink-4);">{example}</span>
	</div>
{/snippet}

<!-- Vollflächiges Overlay -->
<div style="position:fixed; inset:0; z-index:50;">
	<!-- Dunkle Overlay-Schicht -->
	<div style="position:absolute; inset:0; background:rgba(26,26,24,0.45);"></div>

	<!-- Modal-Card -->
	<div style="position:absolute; top:60px; left:50%; transform:translateX(-50%); width:720px; background:var(--g-card); border:1px solid var(--g-rule); border-radius:var(--g-r-4); box-shadow:var(--g-shadow-3); overflow:hidden;">

		<!-- Header -->
		<div style="padding:20px 28px 16px; border-bottom:1px solid var(--g-rule-soft); display:flex; justify-content:space-between; align-items:flex-start;">
			<div>
				<Eyebrow>Modul 1 · Location anlegen</Eyebrow>
				<div style="font-size:22px; font-weight:600; margin-top:4px; letter-spacing:-0.01em;">Neuer Ort</div>
				<p style="font-size:13px; color:var(--g-ink-3); margin-top:4px;">
					Importiere aus Komoot, Google Maps, oder gib Koordinaten direkt ein.
				</p>
			</div>
			<button
				style="background:transparent; border:none; font-size:20px; color:var(--g-ink-4); cursor:pointer; padding:4px;"
				onclick={oncancel}
				aria-label="Schließen"
			>×</button>
		</div>

		<!-- Sektion 1: Verortung · Smart-Import -->
		<div style="padding:20px 28px 8px;">
			{@render LocSectionTag(1, 'Verortung · Smart-Import')}

			<div style="margin-top:12px;">
				<!-- Smart-Import-Eingabe-Row -->
				<div style="display:flex; align-items:center; gap:10px; padding:12px 14px; background:var(--g-card-alt); border:1.5px solid var(--g-accent); border-radius:var(--g-r-3);">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--g-accent)" stroke-width="2">
						<path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/>
						<path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/>
					</svg>
					<input
						class="mono"
						style="font-size:13px; flex:1; border:none; outline:none; background:transparent; color:var(--g-ink);"
						placeholder="Komoot-Link, Google-Maps-URL oder Koordinaten…"
						bind:value={importInput}
						onchange={resolveLocation}
						onkeydown={(e: KeyboardEvent) => e.key === 'Enter' && resolveLocation()}
					/>
					{#if resolvedPreview}
						<Pill tone="good">erkannt · {resolvedPreview.source_type}</Pill>
					{/if}
				</div>

				<!-- Format-Chips -->
				<div style="display:flex; gap:8px; margin-top:10px; flex-wrap:wrap;">
					{@render LocFormatChip('komoot',    'Komoot-URL',      'komoot.com/highlight/…')}
					{@render LocFormatChip('gmaps',     'Google Maps',     'goo.gl/maps/… · maps.app.goo.gl/…')}
					{@render LocFormatChip('dms',       'DMS-Koordinaten', '47°04\'44.0"N 11°41\'08.2"E')}
					{@render LocFormatChip('dec',       'Dezimal',         '47.0789, 11.6856')}
					{@render LocFormatChip('utm',       'UTM',             '33T 296000 5215000')}
					{@render LocFormatChip('paste-gpx', 'GPX-Wegpunkt',    '.gpx · einzelner Trkpt')}
				</div>
			</div>
		</div>

		<!-- Auflösungs-Vorschau (2-Spalten-Grid) -->
		<div style="padding:8px 28px 16px; display:grid; grid-template-columns:1fr 280px; gap:16px; align-items:stretch;">
			<Card padding={0} background="var(--g-card-alt)">
				<div style="padding:12px 16px 8px; border-bottom:1px solid var(--g-rule-soft);">
					<Eyebrow>Erkannt · Vorschau</Eyebrow>
				</div>
				<div style="padding:10px 16px 14px;">
					{#if resolvedPreview}
						<KV label="Quelle"       value={resolvedPreview.source_type} mono={false} />
						<KV label="Koordinaten"  value="{resolvedPreview.lat.toFixed(5)}°N · {resolvedPreview.lon.toFixed(5)}°E" />
						<KV label="Höhe (DEM)"   value={resolvedPreview.elevation_m != null ? `${resolvedPreview.elevation_m} m ü.M.` : '—'} />
						<KV label="Zeitzone"     value={resolvedPreview.timezone} />
						<KV label="Land/Region"  value={resolvedPreview.region ?? '—'} mono={false} />
					{:else}
						<KV label="Quelle"       value="—" />
						<KV label="Koordinaten"  value="—" />
						<KV label="Höhe (DEM)"   value="—" />
						<KV label="Zeitzone"     value="—" />
						<KV label="Land/Region"  value="—" mono={false} />
					{/if}
				</div>
			</Card>

			<!-- Mini-Map -->
			<div style="position:relative; border-radius:var(--g-r-3); overflow:hidden; border:1px solid var(--g-rule); background:linear-gradient(135deg, var(--g-paper-deep), var(--g-card-alt)); display:flex; align-items:center; justify-content:center;">
				<TopoBg opacity={0.5} lines={28} />
				<div style="position:absolute; inset:0; background:linear-gradient(180deg, transparent 60%, rgba(20,30,20,0.15));"></div>
				<div style="position:relative; width:28px; height:28px; border-radius:50%; background:var(--g-accent); border:3px solid var(--g-card); box-shadow:var(--g-shadow-3);"></div>
			</div>
		</div>

		<!-- Sektion 2: Benennung -->
		<div style="padding:12px 28px;">
			{@render LocSectionTag(2, 'Benennung')}
			<div style="margin-top:10px; display:grid; grid-template-columns:2fr 1fr; gap:12px;">
				<div style="display:flex; flex-direction:column; gap:4px;">
					<span style="font-size:10px; color:var(--g-ink-4); font-family:var(--g-font-mono); letter-spacing:0.08em; text-transform:uppercase;">Eindeutiger Name (für deine Übersicht)</span>
					<input
						style="padding:10px 12px; border:1.5px solid var(--g-accent); background:var(--g-card); border-radius:var(--g-r-2); font-size:14px; color:var(--g-ink); font-weight:500; outline:none; font-family:var(--g-font-sans);"
						bind:value={nameInput}
						placeholder="z.B. Hintertuxer Gletscher"
					/>
				</div>
				<div style="display:flex; flex-direction:column; gap:4px;">
					<span style="font-size:10px; color:var(--g-ink-4); font-family:var(--g-font-mono); letter-spacing:0.08em; text-transform:uppercase;">Gruppe (optional)</span>
					<div style="padding:10px 12px; border:1.5px solid var(--g-rule); background:var(--g-card); border-radius:var(--g-r-2); font-size:14px; color:var(--g-ink); font-weight:500; display:flex; justify-content:space-between; align-items:center;">
						<input
							style="border:none; outline:none; background:transparent; font-size:14px; color:var(--g-ink); font-weight:500; flex:1; font-family:var(--g-font-sans);"
							bind:value={groupInput}
						/>
						<span style="font-size:10px; color:var(--g-ink-4); font-family:var(--g-font-mono);">Tippen für neue Gruppe</span>
					</div>
				</div>
			</div>
		</div>

		<!-- Sektion 3: Meteorologische Brille -->
		<div style="padding:12px 28px;">
			{@render LocSectionTag(3, 'Meteorologische Brille (Aktivitätsprofil)')}
			<p style="font-size:12px; color:var(--g-ink-3); margin-top:4px; margin-bottom:10px;">
				Welche Metriken sind für genau diese Koordinaten standardmäßig relevant?
			</p>
			<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px;">
				{#each ACTIVITY_PROFILE_OPTIONS as profile}
					{@const isActive = activeProfile === profile.value}
					<div
						onclick={() => { activeProfile = profile.value; }}
						style="padding:12px 14px; border:1.5px solid {isActive ? 'var(--g-accent)' : 'var(--g-rule-soft)'}; background:{isActive ? 'var(--g-accent-tint)' : 'var(--g-card-alt)'}; border-radius:var(--g-r-3); cursor:pointer;"
					>
						<div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
							<Pill tone="accent">{profile.label.split(' ')[0]}</Pill>
							<span style="font-size:13px; font-weight:600; color:var(--g-ink);">{profile.label}</span>
						</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- Footer -->
		<div style="background:var(--g-card-alt); border-top:1px solid var(--g-rule-soft); padding:16px 28px 18px; display:flex; justify-content:space-between; align-items:center;">
			<span class="mono" style="font-size:11px; color:var(--g-ink-4);">☐ Nach Speichern als Compare-Kandidat vormerken</span>
			<div style="display:flex; gap:8px; align-items:center;">
				{#if saveError}
					<span style="font-size:12px; color:var(--g-bad);">{saveError}</span>
				{/if}
				<Btn variant="ghost" onclick={oncancel}>Abbrechen</Btn>
				<Btn variant="primary" onclick={saveLocation} disabled={!nameInput.trim() || saving}>
					{saving ? 'Speichern…' : 'Ort speichern'}
				</Btn>
			</div>
		</div>

	</div>
</div>
