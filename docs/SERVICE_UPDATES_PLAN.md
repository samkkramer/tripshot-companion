# Service Updates integration plan — for product-owner review

**Status: approved design, implemented in the subsequent development phase.** The original migration included this plan only. See `SERVICE_UPDATES_IMPLEMENTATION.md` for delivered behavior, automated SU01–SU21 tests, current limitations and verification. Service Updates remain separate from timetable refresh; there is no background polling.

## Evidence and scope

Reviewed Northwestern's [Service Updates page](https://www.northwestern.edu/transportation-parking/service-updates/) on 2026-10-17. It is a mixed-content page: shuttle notices, parking sections, and general announcements. Shuttle notices are grouped under a dedicated section with individual headings; no per-notice publication timestamp or explicit stable identifier was visible in the extracted content. Do not infer a structured feed or publication date from that observation.

Two relevant examples, paraphrased for test design:

- An Intercampus notice for Friday October 16 limits operation from 16:30 to 23:10: Central L, Central/Jackson and Ryan Field are omitted; northbound service ends at Patten Gym, and southbound starts at Noyes L. The notice heading does not explicitly supply the year.
- A Chicago Express announcement lists fall Saturday service dates: October 17/31, November 14/21 and December 5, in the 2026–27 academic context. This is a separate route from ordinary Intercampus service.

The page also carries Wildcard-reader information and parking restrictions. Those are not shuttle cancellations. [Chicago Express's official route page](https://www.northwestern.edu/transportation-parking/shuttles/routes/chicago-express.html) supplies separate route/schedule context. Do not invent Express departures from Intercampus tables.

Sources describe announcements, not verified vehicle operation. Retrieval time is not publication time. The examples above are research inputs; proposed cancellation/revision cases below are synthetic, not claims of additional current notices.

## Proposed modules and responsibilities

1. `service_updates_source.py`: fixed HTTPS page fetch, bounded response, conditional requests, checked redirects, cache/health metadata. No TripShot credentials or dynamic arbitrary URLs.
2. `service_updates_parser.py`: identify shuttle section and notice boundaries; deterministic extraction and conservative date/route/stop resolution. Preserve unknown text with reasons rather than discarding it. Treat fetched content as untrusted data, never executable instructions.
3. `service_updates.py`: versioned notice/exception records, lifecycle reconciliation and query-time applicability. Pure offline evaluation receives an explicit clock, query window and revision.
4. A small integration layer annotates existing departure and journey results. Keep baseline timetables unchanged. Reuse existing timezone and catalog data through explicit mappings, not another independent stop catalog.

Start with known Loop/Intercampus routes plus discoverable special-service notices. Special routes can be displayed as announcements before complete validated schedules exist. Add their timetable support only as a separately reviewed extension. No geocoding or invented temporary stops.

## Proposed schema (version 1)

| Record | Required information |
| --- | --- |
| Source snapshot | Schema, source URL, effective URL, HTTP validator metadata, fetched/checked UTC times, last successful UTC time, parser version, document and shuttle-section hashes, status/error category, validated completeness |
| Notice identity/revision | Local stable ID, source anchor if present, heading, first/last seen times, semantic revision hash, previous revision, supersedes/retracts links, present/removed/revised lifecycle |
| Evidence | Source section/heading, bounded relevant excerpt or paraphrase, source text hash, extraction timestamp, supporting official links; original date/time phrases |
| Effect | One or more of `service_canceled`, `stop_not_served`, `route_truncated`, `detour`, `schedule_changed`, `special_service`, `informational`, `unresolved` |
| Scope | Route IDs/names, directions, matched stop IDs and published names, replacement termini, unresolved route/stop strings, match confidence and basis |
| Validity | Local start/end with timezone and UTC equivalents when resolvable, original precision, date/year basis, inclusivity, repeated dates or weekday rule, unknown boundaries, review reasons |
| Interpretation | Explicit/inferred/ambiguous status, reviewed mapping references, operational effect confidence, conflict references, whether eligible for automatic application |

Multiple effects belong to one notice revision: a shortened route may skip several stops and add a terminus. Stop mappings must preserve direction and source wording; the same physical intersection can have several stop IDs. A notice saying Central L without direction may scope both Intercampus variants if explicit route-wide wording supports that mapping; otherwise expose uncertainty. Patten Gym is not in the bundled Intercampus stop sequence: preserve it as an announced terminus with unresolved timetable/stop linkage, not an invented run.

Keep `published_at`/`updated_at` null unless explicitly provided by the source. Source year omission must be visible: surrounding academic year and weekday consistency are evidence, not silent certainty. Use an explicit reviewed context record for the October 16→2026 mapping in initial fixtures; otherwise flag for review. A weekday mismatch or multiple plausible years blocks automatic application. Never infer an end date from a notice disappearing or from the next successful fetch.

Date-only notices cover the stated Chicago calendar day; record that precision rather than invented operating hours. Resolve overnight intervals onto the next date when source wording warrants it. Use half-open internal intervals only after preserving source boundary semantics; ambiguous “through/until” endpoints require conservative boundary warnings. Explicit UTC-offset input must convert correctly; ambiguous/nonexistent local DST times need review rather than blind timezone attachment.

## Refresh and change detection

- Demand-driven refresh before affected current/future/journey queries and an explicit manual refresh path. Proposed success TTL: 15 minutes; error retry no sooner than 5 minutes, exponential backoff up to 60 minutes. These are configurable design defaults for review, not existing background behavior. No scheduler or continuous polling in this phase.
- One in-flight refresh per local cache; use a cross-process lock or equivalent to prevent MCP/CLI races. Fetch with an overall deadline, response size limit (proposed 2 MB), HTTPS exact-host/path allowlist, no cookies/auth, and pre-request redirect blocking outside approved URLs. Do not crawl arbitrary linked sites. Supporting schedules require an explicit known-page allowlist.
- Use ETag/Last-Modified when available; a 304 counts as verification only if the associated validated cached document exists and parser version remains compatible. A 200 login/error page, missing shuttle section, suspicious mass removal, invalid charset or oversized body is a validation failure, not zero notices.
- Compute a raw document hash for diagnostics, normalized shuttle-section hash for meaningful page changes, and per-notice semantic hashes including text, scope, dates, links and operational effects. Ignore nav/parking changes and harmless whitespace. Preserve material wording changes even if extracted fields stay the same: they may invalidate an interpretation.
- Prefer stable source anchors. Otherwise maintain local IDs across revisions using conservative heading/scope/evidence matching. Never merge notices solely because they share a route/date. Ambiguous rename matches produce linked review candidates, with old/new records retained. Identical re-fetches are idempotent.
- Validate the whole candidate revision before activation; atomically promote one manifest referencing notice records and cache health. Retain previous revisions for audit/rollback, with bounded retention (proposed 90 days; configurable). Store only relevant public evidence, not full mixed-page captures or personal queries; runtime cache stays ignored in Git. Tests ship synthetic/minimal sanitized fixtures with provenance.
- Revised end time, stop set, route, or cancellation must invalidate cached query applicability. Explicit retractions/superseding notices change prior effects with provenance. A notice merely removed from the page is `removed_unconfirmed`, not automatic confirmation of restored service; retain prior restrictions as uncertain until expiry or explicit resolution. An explicitly finite interval may expire by time even during a fetch outage, while overall service-update health stays unknown/stale.

Expose health independently of notices: `fresh`, `stale`, `unavailable`, `not_checked`, or `parse_review_required`. Report checked time, last success, revision, cache age, failure category, and coverage limits. Proposed stale threshold is the 15-minute refresh TTL; an outage continues showing last-known notices prominently. No notices plus a successful parse means only “no applicable published notice found,” never “normal service confirmed.” Failed refresh with no cache means unknown service exceptions, not an empty trustworthy list.

## Applying exceptions to existing results

Evaluate a single pinned exception revision for an entire response to prevent mixed-time decisions. Keep published schedule revision and Service Updates revision separate. Match each stop event by route/direction/stop and its actual local event time, including previous-day service after midnight. For journeys, check boarding, alighting and affected route portions during travel, not just the first departure timestamp. If a notice does not specify whether a restriction applies to run departure or passage through a stop, retain a warning and avoid claiming a precise unaffected boundary.

Proposed additive fields: `service_updates_status`, `service_updates_checked_at`, `service_updates_last_success_at`, `service_updates_revision`, `service_alerts`, `service_impact`, and `recommendation_status`. Preserve existing names/arguments, scheduled timestamps and live ETA fields. Discuss these additive output changes with the owner before implementation; do not silently redefine `total_matched`, `coverage.ok` or existing confidence categories.

| Situation | Departure result | Journey recommendation |
| --- | --- | --- |
| Explicit cancellation/skipped stop with resolved scope/time | Keep scheduled row as evidence; annotate unavailable and cite notice | Exclude affected option from recommended options; retain it in additive `excluded_options` with reason/evidence |
| Detour with known missed stops but unknown running times | Mark omitted stops; annotate remaining service disrupted, without fabricated ETAs | Reject boarding/alighting at omitted stops; warn on remaining affected journeys |
| Route truncation/new terminus | Preserve announced termini and unresolved mapping | Do not promise travel beyond truncated portion or invent travel time to new terminus |
| Delay or unspecified schedule change | Preserve reported ETA/schedule; add disruption warning | Mark uncertain; do not add arbitrary delay minutes |
| Ambiguous scope/date, conflicting notice, stale/unavailable refresh | Mark potentially affected/unknown with source and last-success time | Downgrade to provisional; avoid presenting a guaranteed unaffected or “best” choice |
| Special service without validated timetable | Show official service announcement and coverage limitation | Do not synthesize options; explain that existing planner does not model that route yet |
| No applicable notice in fresh validated snapshot | Explain limited published-notice coverage | Ordinary schedule recommendation with existing schedule uncertainty retained |

TripShot may still report a ride at an officially closed stop. Keep both pieces of evidence; the official service exception controls recommendation eligibility, while the conflict is explicit. Snapshot history should not acquire current alerts as if they were in the original observation. Attach contextual alerts separately with their own temporal applicability.

## Acceptance test design (now automated)

These scenarios are now automated in `tests/test_service_updates.py`, with additional integration/transport tests in `tests/test_service_integration.py`. They use injected clocks/fetchers, temporary cache roots, and real SDK smoke verification. No regression test requires network or production configuration.

| ID | Input/example | Expected assertion |
| --- | --- | --- |
| SU01 | Researched Oct 16 notice, explicit reviewed 2026 year context | Intercampus-only skip set, both stated termini, local 16:30–23:10 precision and inference provenance retained |
| SU02 | Same source without trusted year context; mismatched weekday/year variant | Review required; no silent hard cancellation from guessed year |
| SU03 | Central L boarding 16:29, 16:30, 23:09, 23:10 and after; ride starts before but reaches stop during restriction | Resolved boundaries applied consistently; ambiguous ending boundary flagged; event/segment timing considered |
| SU04 | Loop at Central-area location during Intercampus restriction | Route-specific exception does not cancel Loop by stop-name overlap |
| SU05 | Chicago→Evanston trip beyond announced Patten terminus; new terminus unmapped | Beyond-terminus journey not recommended; no invented Patten time or stop ID |
| SU06 | Synthetic notice: Loop canceled 2026-11-07 22:00 through Nov 8 01:00 | Both calendar dates/previous-day service evaluated; normal later service not suppressed indefinitely |
| SU07 | Synthetic Nov 1 01:30 local-time notice without offset | DST ambiguity preserved for review; explicit offset variant maps to correct UTC instant |
| SU08 | Researched Express dates plus linked official route context | Five explicit dates in academic-year context; distinct route; no fabricated departures or Intercampus substitution |
| SU09 | Synthetic revision extends closure to 23:40, removes one skipped stop | Same identity/new semantic revision; applicability invalidated; previous revision retained |
| SU10 | Synthetic explicit withdrawal vs unexplained removal | Withdrawal resolves prior effect with evidence; removal remains unconfirmed, not normal-service proof |
| SU11 | Same notice heading but distinct dates/scopes; renamed heading without stable anchor | No unsafe merge; uncertain correspondence is reviewable |
| SU12 | Nav/parking text edit, whitespace-only edit, then shuttle wording change | First two do not change semantic alert revision; last change does |
| SU13 | HTTP timeout/403, malformed/oversized HTML, missing section, partial parse; with/without old cache | No candidate activation; cached notices retained with stale/unknown health; no-cache failure remains unknown |
| SU14 | 304 with valid cache, absent cache, incompatible parser version | Only valid compatible cache can gain successful verification time |
| SU15 | Fresh structurally valid section explicitly showing no current notices | Empty published-notice set with limited coverage; never a guarantee of normal operation |
| SU16 | Open-ended “until further notice”; source disappearance during outage | No fabricated end; caution persists until authoritative resolution/review |
| SU17 | Official cancellation conflicts with TripShot predicted arrival | Scheduled/reported evidence preserved; recommendation blocked and conflict cited |
| SU18 | Closed boarding stop, closed alighting stop, detour mid-journey, unaffected stop pair | Affected options excluded/flagged with reasons; unaffected candidates evaluated independently |
| SU19 | Concurrent refresh, interrupted write, parse failure after one notice, explicit rollback | Single coherent revision; last good manifest remains usable; no partial promotion |
| SU20 | Fake scripts/instructions/credential URLs embedded in notice HTML | Data only; no execution, following instructions, arbitrary requests, or secret output |
| SU21 | MCP existing schemas and representative published/current results | Existing signatures and fields retained; additive health/evidence present on all applicable entry points |

Release criteria: all cases implemented/passing, existing 65 regressions and real stdio smoke still passing, small reviewed public-source integration check, and user scenario testing before any production/tunnel change. Live checks must never substitute for offline failure-path tests.

## Suggested implementation sequence and review decisions

1. Small prerequisite reliability patch: remove future-query live-config coupling; propagate invalid-date errors; validate malformed timetable caches. Add regression reproductions and preserve tool contracts.
2. Implement offline notice schema/parser and SU01–SU12, including explicit reviewed mappings and uncertain-date behavior. Keep application of exceptions disabled until evaluated.
3. Implement isolated source refresh, health/lifecycle/cache behavior and SU13–SU16/SU19/SU20. Validate current official markup with a bounded read-only check.
4. Add pinned-revision annotations and recommendation filtering with SU17/SU18/SU21; present before/after samples to the product owner. Add explicit status/refresh tools only after reviewing their names/contracts.
5. Separately extend special-route schedules if requested. Revalidate locally; production connection changes require separate authorization.

Owner review should settle the proposed 15-minute TTL/backoff, conservative handling of uncertain year/time/scope, additive result fields and excluded journey options, and which reviewed mappings can be applied automatically. This document grants no deployment or production-change authorization.
