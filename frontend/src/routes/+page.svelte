<script lang="ts">
	// Issue 568 — Startseite-Redesign (Cockpit + Planungs-/Leerzustand).
	// Spec: docs/specs/modules/issue_568_home_redesign.md
	//
	// - Zustand A (aktiver Trip): Trip-Status-Karte + Schnellaktionen-Reihe
	//   + rechte Spalte (Briefing-Timeline + Alarme). Keine Sparkline, kein
	//   Pillstreifen, keine Etappen-Prosa mehr.
	// - Zustand B (kein aktiver Trip): ehrlicher Hinweis + bis zu zwei
	//   SetupResumeCards (Trip + Vergleich) + Schnell-anlegen-Buttons.
	// - Vergleiche-Sektion + Archiv bleiben unverändert.

	import type { Trip, ComparePreset, CockpitStatus } from '$lib/types.js';
	import { Card, Pill, Dot, Eyebrow, Btn, SectionH } from '$lib/components/atoms';
	import {
		BriefingTimelineRow,
		QuickAction,
		SetupResumeCard,
		CompareStatusRow
	} from '$lib/components/molecules';
	import { deriveStatusFromPreset } from '$lib/components/compare/subscriptionHelpers.js';
	import { tripStatus, activeOrNextTrip, todayStageIndex } from '$lib/utils/tripStatus.js';
	import { plannedBriefings, archivedTrips } from './_home/cockpitHelpers.js';
	import {
		dayProgress,
		setupStepTrip,
		setupStepCompare,
		nextPlannedTrip,
		firstIncompleteCompare,
		liveTrip
	} from '$lib/utils/cockpitHelpers568.js';
	import TripKachel from './_home/TripKachel.svelte';
	import CompareKachel from './_home/CompareKachel.svelte';
	import EmptyKachel from './_home/EmptyKachel.svelte';

	let { data } = $props();

	const now = new Date();
	const trips = $derived((data.trips ?? []) as Trip[]);
	const presets = $derived((data.presets ?? []) as ComparePreset[]);
	const activePresets = $derived(
		presets.filter((p) => deriveStatusFromPreset(p) === 'active')
	);
	const cockpitStatus = $derived((data.cockpitStatus ?? null) as CockpitStatus | null);
	const isEmpty = $derived(trips.length === 0 && presets.length === 0);

	const todayPretty = now.toLocaleDateString('de-DE', {
		weekday: 'short',
		day: '2-digit',
		month: 'long',
		year: 'numeric'
	});

	// --- Hero-Modus: trip > compare > planning --------------------------------
	// Aktiver Trip: heute im Reise-Zeitraum (liveTrip)
	const activeLiveTrip = $derived(liveTrip(trips, now));

	// Hero-Modus
	const mode = $derived(
		activeLiveTrip ? 'trip' : (activePresets.length > 0 ? 'compare' : 'planning')
	);

	// Compare-Hero (erster aktiver Vergleich)
	const compareHero = $derived(mode === 'compare' ? activePresets[0] : null);

	// "Außerdem beobachtet"-Reihe
	// - trip-Modus: ALLE aktiven Vergleiche
	// - compare-Modus: aktive Vergleiche MINUS compareHero
	const alsoWatched = $derived(
		mode === 'trip' ? activePresets :
		mode === 'compare' ? activePresets.slice(1) : []
	);

	// --- Hero-Tour (aktiv oder nächste) -------------------------------------
	const hero = $derived(mode === 'trip' ? activeLiveTrip : null);
	const heroIsActive = $derived(mode === 'trip');
	const heroStages = $derived(hero?.stages ?? []);
	const todayIdx = $derived(hero ? todayStageIndex(hero, now) : -1);
	const heroStageIdx = $derived(todayIdx >= 0 ? todayIdx : 0);
	const dayX = $derived(heroIsActive ? heroStageIdx + 1 : 1);
	const dayY = $derived(heroStages.length);
	const progressPct = $derived(dayProgress(dayX, dayY));

	// --- Planungs-Kandidaten ------------------------------------------------
	const nextPlanned = $derived(nextPlannedTrip(trips, now));
	const firstIncomplete = $derived(firstIncompleteCompare(presets));
	const setupStepsTrip = $derived(nextPlanned ? setupStepTrip(nextPlanned) : []);
	const setupStepsCompare = $derived(firstIncomplete ? setupStepCompare(firstIncomplete) : []);

	// Tab-Map (Trip-Wizard-Schritt → Detail-Tab-Query).
	const TRIP_TAB_MAP = ['stages', 'stages', 'weather', 'briefings', 'briefings'];

	function buildTripCtaHref(): string {
		if (!nextPlanned) return '/trips/new';
		const firstOpen = setupStepsTrip.findIndex((s) => !s.done);
		if (firstOpen < 0) return `/trips/${nextPlanned.id}?tab=overview`;
		if (firstOpen === 0) return '/trips/new';
		return `/trips/${nextPlanned.id}?tab=${TRIP_TAB_MAP[firstOpen]}`;
	}

	function buildCompareCtaHref(): string {
		if (!firstIncomplete) return '/compare';
		const firstOpen = setupStepsCompare.findIndex((s) => !s.done);
		const step = firstOpen < 0 ? 1 : firstOpen + 1;
		return `/compare/${firstIncomplete.id}/edit`;
	}

	const tripCtaHref = $derived(buildTripCtaHref());
	const compareCtaHref = $derived(buildCompareCtaHref());

	// --- Rechte Spalte / Archiv ---------------------------------------------
	const briefings = $derived(
		hero ? plannedBriefings(hero.report_config, cockpitStatus?.briefings, hero.id) : []
	);
	const heroAlerts = $derived(
		(cockpitStatus?.alerts ?? []).filter((a) => a.trip_id === hero?.id)
	);
	const archive = $derived(archivedTrips(trips, now, 4));
	const otherTrips = $derived(trips.filter((t) => t.id !== hero?.id));

	// Aktive Kanäle aus report_config — für die Kanal-Gesundheits-Dots.
	const heroChannels = $derived.by(() => {
		const rc = hero?.report_config;
		if (!rc) return [] as string[];
		const out: string[] = [];
		if (rc.morning_enabled || rc.evening_enabled) {
			if (rc.send_email !== false) out.push('Email');
			if (rc.send_signal) out.push('Signal');
			if (rc.send_telegram) out.push('Telegram');
			if (rc.send_sms) out.push('SMS');
		}
		return out;
	});
</script>

<div class="page-root" style:position="relative" style:max-width="1320px">
	<!-- Topbar -->
	<header
		style:display="flex"
		style:align-items="center"
		style:justify-content="space-between"
		style:padding="20px 0"
		style:border-bottom="1px solid var(--g-rule-soft)"
		style:margin-bottom="32px"
	>
		<div>
			<Eyebrow>Übersicht · {todayPretty}</Eyebrow>
			<div
				style:font-size="22px"
				style:font-weight="600"
				style:margin-top="2px"
				style:letter-spacing="-0.005em"
			>Deine Touren & Vergleiche</div>
			<div
				style:font-size="0.9375rem"
				style:color="var(--g-ink-muted)"
				style:margin-top="4px"
				style:line-height="1.5"
			>Was du jetzt vorbereitest, läuft unterwegs autark. Briefings gehen per Email oder Signal, du musst am Berg nichts tun.</div>
		</div>
		<div style:display="flex" style:gap="10px" style:align-items="center">
			<Btn href="/compare" variant="ghost" size="sm">Neuer Vergleich</Btn>
			<Btn href="/trips/new" variant="primary" size="sm">+ Neuer Trip</Btn>
		</div>
	</header>

	{#if isEmpty}
		<EmptyKachel />
	{:else}
		<!-- Zustand A: Cockpit für aktiven Trip ------------------------------ -->
		{#if hero && heroIsActive}
			<div class="cockpit-hero">
				<!-- Trip-Status-Karte (ersetzt Hero) -->
				<Card padding={0} accent={true}>
					<div style:padding="24px 28px">
						<div
							style:display="flex"
							style:align-items="center"
							style:gap="10px"
							style:margin-bottom="10px"
						>
							<Pill tone="accent">
								<Dot tone="bad" size={6} /> Live · Tag {dayX} von {dayY}
							</Pill>
						</div>

						<!-- Fortschrittsbalken -->
						<div
							style:height="4px"
							style:background="var(--g-rule-soft)"
							style:border-radius="2px"
							style:overflow="hidden"
							style:margin-bottom="16px"
						>
							<div
								style:height="100%"
								style:background="var(--g-accent)"
								style:border-radius="2px"
								style:width="{progressPct}%"
								style:transition="width 300ms ease"
							></div>
						</div>

						<a
							href="/trips/{hero.id}?tab=overview"
							style:display="block"
							style:font-size="28px"
							style:font-weight="600"
							style:letter-spacing="-0.02em"
							style:line-height="1.1"
							style:margin-bottom="6px"
							style:color="var(--g-ink)"
							style:text-decoration="none"
						>{hero.name}</a>
						{#if hero.region}
							<div
								style:font-size="14px"
								style:color="var(--g-ink-2)"
								style:margin-bottom="12px"
							>{hero.region}</div>
						{/if}

						<!-- Kanal-Gesundheit -->
						{#if heroChannels.length > 0}
							<div
								style:display="flex"
								style:flex-wrap="wrap"
								style:gap="10px"
								style:margin-top="14px"
								style:margin-bottom="14px"
							>
								{#each heroChannels as ch (ch)}
									<span
										style:display="inline-flex"
										style:align-items="center"
										style:gap="6px"
										style:font-size="13px"
										style:color="var(--g-ink-2)"
									>
										<Dot tone="good" />
										<span>{ch}</span>
									</span>
								{/each}
							</div>
						{/if}

						<a
							href="/trips/{hero.id}?tab=overview"
							style:font-size="13px"
							style:color="var(--g-ink-2)"
							style:text-decoration="none"
							style:font-family="var(--g-font-mono)"
						>Trip öffnen →</a>
					</div>
				</Card>

				<!-- Rechte Spalte -->
				<div style:display="flex" style:flex-direction="column" style:gap="16px">
					<Card>
						<div style:padding="20px">
							<SectionH eyebrow="Heute" title="Was geht raus · {hero?.name ?? ''}" />
							{#if briefings.length > 0}
								<div style:display="flex" style:flex-direction="column" style:gap="8px">
									{#each briefings as r, i (i)}
										<BriefingTimelineRow report={r} />
									{/each}
								</div>
							{:else}
								<div style:font-size="13px" style:color="var(--g-ink-2)">
									Keine Briefings für diesen Trip geplant.
								</div>
							{/if}
						</div>
					</Card>

					<Card>
						<div style:padding="20px">
							<SectionH
								eyebrow="Alarme · letzte 24 h"
								title={heroAlerts.length > 0
									? `${heroAlerts.length} Alarm${heroAlerts.length > 1 ? 'e' : ''}`
									: 'Keine Alarme'}
							/>
							{#if heroAlerts.length > 0}
								<div style:display="flex" style:flex-direction="column" style:gap="6px">
									{#each heroAlerts as alert (alert.sent_at)}
										<div
											style:display="flex"
											style:align-items="center"
											style:gap="8px"
											style:padding="8px 10px"
											style:background="var(--g-card-alt)"
											style:border="1px solid var(--g-rule-soft)"
											style:border-radius="var(--g-r-2)"
											style:font-size="13px"
										>
											<Dot
												tone={alert.severity === 'HIGH'
													? 'bad'
													: alert.severity === 'MODERATE'
														? 'warn'
														: 'neutral'}
											/>
											<span style:color="var(--g-ink-2)"
												>{new Date(alert.sent_at).toLocaleTimeString('de-DE', {
													hour: '2-digit',
													minute: '2-digit'
												})}</span
											>
											<span style:color="var(--g-ink-2)"
												>{alert.changes_count} Änderung{alert.changes_count !== 1
													? 'en'
													: ''}</span
											>
										</div>
									{/each}
								</div>
							{:else}
								<div
									style:font-size="13px"
									style:color="var(--g-ink-2)"
									style:line-height="1.5"
								>Keine Alarme in den letzten 24 Stunden. Schwellen verwaltest du im Trip.</div>
							{/if}
						</div>
					</Card>
				</div>
			</div>

			<!-- Schnellaktionen-Reihe (4 QuickActions) -->
			<section style:margin="0 0 32px">
				<Eyebrow>Schnellaktionen</Eyebrow>
				<div class="quick-grid" style:margin-top="10px">
					<QuickAction
						glyph="route"
						label="Pausentag einplanen"
						sub="Etappen & Wegpunkte"
						href="/trips/{hero.id}?tab=stages"
					/>
					<QuickAction
						glyph="metrics"
						label="Wetter-Metriken ändern"
						sub="Wetter-Layout"
						href="/trips/{hero.id}?tab=weather"
					/>
					<QuickAction
						glyph="clock"
						label="Briefing-Zeitplan"
						sub="Versand & Zeiten"
						href="/trips/{hero.id}?tab=briefings"
					/>
					<QuickAction
						glyph="eye"
						label="Vorschau prüfen"
						sub="So wirkt das Briefing"
						href="/trips/{hero.id}?tab=preview"
					/>
				</div>
			</section>
		{/if}

		<!-- Zustand C: Compare-Hero (kein aktiver Trip, aber aktive Vergleiche) -->
		{#if mode === 'compare' && compareHero}
			<div class="cockpit-hero" style:margin-bottom="24px">
				<!-- Linke Spalte: Hero-Karte -->
				<Card>
					<div style:padding="20px">
						<div style:display="flex" style:align-items="center" style:gap="8px" style:margin-bottom="12px">
							<Pill tone="ok">Aktiv</Pill>
							<span style:font-size="14px" style:color="var(--g-ink-2)">{compareHero.location_ids.length} Orte</span>
						</div>
						<div style:font-size="20px" style:font-weight="700" style:margin-bottom="8px">{compareHero.name}</div>
						<!-- Region falls vorhanden -->
						{#if (compareHero.display_config as Record<string,unknown> | undefined)?.region}
							<div style:font-size="13px" style:color="var(--g-ink-2)" style:margin-bottom="8px">
								{(compareHero.display_config as Record<string,unknown>).region as string}
							</div>
						{/if}
						<!-- Zeitplan-Zeile -->
						<div style:font-family="var(--g-font-mono)" style:font-size="12px" style:color="var(--g-ink-3)" style:margin-bottom="16px">
							{compareHero.schedule === 'daily' ? 'täglich' : compareHero.schedule === 'weekly' ? 'wöchentlich' : 'manuell'}
							{#if compareHero.schedule !== 'manual'} · {String(compareHero.hour_from).padStart(2,'0')}:00{/if}
						</div>
						<!-- Kanal-Footer -->
						<div style:display="flex" style:gap="6px" style:flex-wrap="wrap">
							{#each compareHero.empfaenger as emp}
								<span style:font-size="11px" style:padding="2px 8px" style:background="var(--g-card-alt)" style:border="1px solid var(--g-rule-soft)" style:border-radius="4px">{emp}</span>
							{/each}
						</div>
					</div>
				</Card>
				<!-- Rechte Spalte: Was geht raus + Alerts -->
				<div style:display="flex" style:flex-direction="column" style:gap="16px">
					<Card>
						<div style:padding="20px">
							<SectionH eyebrow="Versand" title="Was geht raus · {compareHero.name}" />
							<div style:font-size="13px" style:color="var(--g-ink-2)" style:margin-top="8px">
								Versand läuft automatisch gemäß Zeitplan.
							</div>
						</div>
					</Card>
					<Card>
						<div style:padding="20px">
							<SectionH eyebrow="Alarme · letzte 24 h" title="Keine Alarme" />
							<div style:font-size="13px" style:color="var(--g-ink-2)" style:margin-top="8px">
								Keine Alerts für diesen Vergleich aktiv.
							</div>
						</div>
					</Card>
				</div>
			</div>
			<!-- QuickActions für Compare -->
			<section style:margin="0 0 32px">
				<Eyebrow>Schnellaktionen</Eyebrow>
				<div class="quick-grid" style:margin-top="10px">
					<QuickAction glyph="route" label="Orte bearbeiten" sub="Verglichene Orte" href="/compare/{compareHero.id}/edit" />
					<QuickAction glyph="metrics" label="Ideal-Werte ändern" sub="Ideal-Profil" href="/compare/{compareHero.id}/edit#idealwerte" />
					<QuickAction glyph="clock" label="Briefing-Zeitplan" sub="Zeitplan & Kanäle" href="/compare/{compareHero.id}/edit#schedule" />
					<QuickAction glyph="eye" label="Vorschau prüfen" sub="So wirkt das Briefing" href="/compare/{compareHero.id}?tab=preview" />
				</div>
			</section>
		{/if}

		<!-- Zustand B: Planungs-/Leerzustand (kein aktiver Trip) ------------- -->
		{#if mode === 'planning'}
			<div
				style:margin="0 0 24px"
				style:padding="16px 20px"
				style:background="var(--g-card)"
				style:border="1px solid var(--g-rule-soft)"
				style:border-radius="var(--g-r-3)"
			>
				<div style:font-size="15px" style:color="var(--g-ink-2)" style:line-height="1.5">
					Aktuell läuft kein Trip — Briefings kommen automatisch in die Kanäle, sobald die nächste Reise startet.
				</div>
			</div>

			{#if nextPlanned || firstIncomplete}
				<div class="setup-grid" style:margin-bottom="32px">
					{#if nextPlanned}
						<SetupResumeCard
							eyebrow="Nächster Trip"
							title={nextPlanned.name}
							steps={setupStepsTrip}
							ctaLabel="Setup fortsetzen"
							ctaHref={tripCtaHref}
							secondary={{ label: 'Öffnen', href: `/trips/${nextPlanned.id}?tab=overview` }}
							tone="accent"
						/>
					{/if}
					{#if firstIncomplete}
						<SetupResumeCard
							eyebrow="Orts-Vergleich"
							title={firstIncomplete.name}
							steps={setupStepsCompare}
							ctaLabel="Setup fortsetzen"
							ctaHref={compareCtaHref}
							secondary={{ label: 'Öffnen', href: `/compare/${firstIncomplete.id}` }}
							tone="default"
						/>
					{/if}
				</div>
			{/if}

			<div
				style:display="flex"
				style:gap="12px"
				style:flex-wrap="wrap"
				style:margin-bottom="32px"
			>
				<Btn href="/trips/new" variant="accent">+ Neuer Trip</Btn>
				<Btn href="/compare" variant="outline">+ Neuer Orts-Vergleich</Btn>
			</div>
		{/if}

		<!-- Außerdem beobachtet (immer sichtbar wenn alsoWatched nicht leer) -->
		{#if alsoWatched.length > 0}
			<section style:margin-bottom="32px">
				<Eyebrow>Außerdem beobachtet</Eyebrow>
				<div style:display="flex" style:flex-direction="column" style:gap="8px" style:margin-top="10px">
					{#each alsoWatched as preset (preset.id)}
						<CompareStatusRow {preset} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- Weitere Trips -->
		{#if otherTrips.length > 0}
			<section style:margin-bottom="32px">
				<div class="kachel-grid">
					{#each otherTrips as trip (trip.id)}
						<TripKachel {trip} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- Archiv -->
		{#if archive.length > 0}
			<div style:margin-bottom="40px">
				<Card>
					<div style:padding="20px">
						<SectionH eyebrow="Archiv" title="Frühere Trips" right={archiveLink} />
						<div class="archive-grid">
							{#each archive as t (t.id)}
								<a
									href="/trips/{t.id}"
									style:padding="14px 16px"
									style:border="1px solid var(--g-rule-soft)"
									style:border-radius="var(--g-r-2)"
									style:background="var(--g-card-alt)"
									style:text-decoration="none"
									style:color="var(--g-ink)"
									style:display="block"
								>
									<div
										style:font-family="var(--g-font-mono)"
										style:font-size="10px"
										style:color="var(--g-ink-3)"
										style:text-transform="uppercase"
										style:letter-spacing="0.1em"
										style:margin-bottom="4px"
									>{t.dates}</div>
									<div
										style:font-size="14px"
										style:font-weight="600"
										style:line-height="1.3"
										style:margin-bottom="6px"
									>{t.name}</div>
									<div
										style:font-family="var(--g-font-mono)"
										style:font-size="11px"
										style:color="var(--g-ink-3)"
									>{t.stages} {t.stages === 1 ? 'Etappe' : 'Etappen'}</div>
								</a>
							{/each}
						</div>
					</div>
				</Card>
			</div>
		{/if}
	{/if}
</div>

{#snippet archiveLink()}
	<Btn href="/trips" variant="quiet" size="sm">Alle anzeigen</Btn>
{/snippet}


<style>
	.cockpit-hero {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: 24px;
		margin-bottom: 24px;
		align-items: start;
	}
	.quick-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
	}
	.setup-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}
	.archive-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
	}
	.kachel-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
	}
	@media (max-width: 899px) {
		.cockpit-hero {
			grid-template-columns: 1fr;
		}
		.quick-grid {
			grid-template-columns: repeat(2, 1fr);
		}
		.setup-grid {
			grid-template-columns: 1fr;
		}
		.archive-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	.page-root {
		padding: 0 0 80px;
	}
	@media (max-width: 640px) {
		.page-root {
			/* F002: Inhalt darf nicht hinter der fixen Mobile-Bottom-Nav verschwinden (64px + Safe Area) */
			padding-bottom: 120px;
		}
		.quick-grid {
			grid-template-columns: 1fr;
		}
	}
	@media (min-width: 640px) {
		.kachel-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (min-width: 1024px) {
		.kachel-grid {
			grid-template-columns: repeat(3, 1fr);
		}
	}
</style>
