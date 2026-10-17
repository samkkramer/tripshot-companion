# Building Personal AI Integrations: Repeatable Project Playbook

**Case study:** Northwestern TripShot Companion (October 2026)

**Audience:** A technically curious product owner using Windows/PowerShell with ChatGPT as a technical copilot.
**Purpose:** Document how we built a working integration so future projects can follow a clearer, faster, safer process.

## Executive summary

The goal was simple: ask ChatGPT when Northwestern shuttles will arrive, which stop is appropriate, and which scheduled trip gets someone to a destination on time. Initially there was no verified public Northwestern GTFS URL or supported ChatGPT TripShot plugin. Through a sequence of manual observations, Python prototypes, local tests, and a Secure MCP Tunnel, we connected TripShot data to ChatGPT.

We ultimately implemented: a 50-stop local catalog; Intercampus and Loop live/reported arrival lookup; historical vs live vs scheduled confidence labels; separate Loop directions; full published stop-by-stop schedules; future timetable queries; same-ride journey planning; and a 14-tool MCP interface in v9. A proposed v10 adds on-demand synchronization of Northwestern's four official published timetable pages. "Working" means that a tool invocation returned useful data in ChatGPT; it does not mean the tool has been independently audited for GPS accuracy, availability, or security.

## Who did what

**User / product owner / field tester**

- Specified practical goals and priorities (E2 commute, morning gym, Global Hub arrival, live departures, nearby stops).
- Investigated what was permitted by the institution and contacted Northwestern about feed access.
- Opened the actual TripShot website, inspected Network → Fetch/XHR, and shared screenshots of the request list, endpoint paths, and selected response structure (not cookies or authorization headers).
- Installed Python, ran PowerShell commands, imported JSON, kept the tunnel running, and executed tests.
- Reported exact logs, mistakes, unexpected output, and failure scenarios, including those the assistant did not anticipate.
- Used ChatGPT as the end-user client to test MCP tool discovery, actual queries, dynamic predictions, future schedules, and incorrect stop names.

**Assistant / AI architect / programmer / debugger / documenter**

- Researched vendor/platform capabilities and public university schedules; separated confirmed facts from guesses.
- Designed a minimal read-only data model, route/stop join strategy, JSON parsers, and the MCP layer.
- Authored incremental Python files, patches, test scripts, and PowerShell instructions; iterated based on user feedback.
- Diagnosed errors such as missing Python/time-zone data, nested stop objects, SDK compatibility, Windows path quoting, UTF-16 JSON exports, and malformed tool inputs.
- Helped configure a stdio MCP server and an OpenAI Secure MCP Tunnel; instructed how to load keys without disclosing them.
- Distinguished service timetable data from trip-specific predicted arrivals, data-fetch timestamps, and GPS-confirmed movement.
- Kept output verifiable and reproducible, without assuming access to the user's local files or claiming the tunnel was running when it was not.

**Institution / third-party vendor / runtime**

- Northwestern publishes the official timetable and service rules and governs university permissions.
- TripShot operates the data-backed rider interface; its public browser view exposed JSON from which stop and trip relationships could be understood.
- OpenAI's MCP tooling let a local Python server expose typed tools, and the tunnel bridged a locally running client into ChatGPT.

## How the project evolved

1. **User problem first.** We began with conversational shuttle questions, not a mandate to use a particular technology. The initial fallback was Northwestern's human-readable published timetable.
2. **Discovery and legitimate access.** We looked for GTFS/GTFS-Realtime feeds and a documented TripShot API. Northwestern feed URLs were not verified; the user contacted the relevant university office. We did not assume that TripShot's feed support meant all feeds were public.
3. **Browser network observation.** The user inspected the normal TripShot rider UI in Chrome DevTools. A `whoami` call returned 401 but many public-route calls succeeded. The high-value calls included a stop list (`stop?`), route directory (`route?`), route-group live-data response (`live?day=...`), and individual ride JSON (`/v2/p/ride/{rideId}`). We did not require browser cookies to programmatically fetch the later tested `live?day=` response.
4. **Identify join keys.** The stop catalog provided names, coordinates and `stopId`. Ride records contained nested status objects (`Awaiting`, `Departed`, `Skipped`) with the same stop IDs and arrival timestamps. The first parser incorrectly looked for outer `stopId`; diagnostic files revealed and fixed the nesting issue.
5. **First local prototype.** The assistant made simple Python scripts and mock fixtures; the user installed Python 3.14 and `tzdata`, then ran them in a PowerShell window opened from File Explorer.
6. **Validate on actual data.** The user imported 50 stop records, saved route-group JSON snapshots, and verified that two Intercampus arrival records matched Emerson/Maple and Sherman/Emerson. Snapshot timestamps were explicitly not passed off as current results.
7. **Direct programmatic retrieval.** A one-shot Python GET successfully fetched the public ride-group JSON without authentication headers. The parser was re-run against this fresh response. Service dates, route direction, and trips crossing midnight required additional work.
8. **Multi-route live lookup.** Loop and Intercampus were combined and sorted. Code was expanded to distinguish live-group records from schedule/non-live records and to expose when TripShot said an ETA had last been updated.
9. **MCP tool layer and Windows debugging.** The local stdio MCP server grew to nine tools. MCP Python SDK v2 had changed the server import (`MCPServer` versus earlier `FastMCP`). Local `list_tools`/`call_tool` smoke tests confirmed actual protocol discovery and invocation.
10. **Connect ChatGPT with Secure MCP Tunnel.** The user created a tunnel in OpenAI Platform, installed the Windows AMD64 tunnel client, corrected `Read-Host` input and Windows command quoting, and passed the tunnel `doctor` checks. One API key appeared in a screenshot and needed revocation/rotation: a real security lesson. The user then connected the tunnel in ChatGPT.
11. **Real-world testing exposed defects.** ChatGPT successfully queried stops and new arrivals, but the server raised an uncaught exception when `limit > 20`. A patch enforced bounded defaults and cleaner messages. PowerShell redirection also created UTF-16 JSON, which broke a UTF-8-only analysis script.
12. **Evaluate ETA claims rigorously.** Repeated queries found the same ride ID at multiple stops and saw the prediction at a downstream stop change across observations. Another example showed the ETA-update timestamp advancing while the predicted time remained unchanged. We stopped equating a recent fetch/update timestamp with a newly computed or GPS-verified prediction.
13. **Directions and future schedules.** TripShot returned `NonDirectional` for some Loop rides, so stop sequences and route navigation IDs were compared against the university's published clockwise/counterclockwise circuits. v8 introduced a future-time schedule tool; v9 expanded fixed timetables to every published Loop and Intercampus stop, same-trip board/alight queries, and approximate nearest-stop comparisons.
14. **Tool-schema caching.** A ChatGPT conversation still knew only nine older tools, despite new server code. Refreshing the custom MCP connection and starting a new chat exposed the updated tool list. Successful `get_shuttles_at_time` calls then returned the official future Intercampus departures directly from the MCP integration.
15. **Proposed maintenance layer.** v10 checks the four official HTML timetable tables on demand, computes normalized content differences, and replaces a validated local timetable while preserving the last-known-good version. This still requires first-run testing against Northwestern's live HTML pages on the user's machine.

## Important engineering lessons

- Begin with one narrow, read-only user story and prove it locally before building a complicated agent or hosting infrastructure.
- Prefer official documented API/feed contracts; observing a website's own network requests is useful for understanding data structures, but does not automatically authorize unlimited automated polling or imply vendor support.
- Treat typed identifiers (`stopId`, `rideId`, navigation IDs) as join keys, not display names. Handle aliases and names in either order gracefully.
- Separate published schedules, trip-specific expected arrivals, observed vehicle GPS, and service alerts. They have different freshness/accuracy semantics.
- Return data provenance and warnings in the MCP tool's structured output, not only in ChatGPT prose.
- Distinguish API 401/403 from empty service results, past arrivals, validation failures, and nighttime inactivity. An error is not evidence that no shuttle operates.
- Use UTC-aware timestamps internally and render local times in the appropriate IANA timezone; test midnight/date boundaries explicitly.
- Use representative offline fixtures and real-world samples, including wrong stop names, unexpected limits, partial responses, changed HTML, delays, and outdated ETAs.
- Apply changes as small, versioned patches that preserve the user's local environment. Back up files and verify tests before restarting the tunnel/client.
- Avoid copying keys or tokens into commands, screenshots, repositories, and chat. Use environment variables and secure prompts; rotate leaked credentials promptly.
- Verify with an actual MCP handshake and actual tool call, not just that Python starts without errors. Refresh client-side tool discovery when the schema changes.
- Do not confuse a program running locally through a tunnel with permanent background availability. Only claim services are available while connected and healthy.
- For automatically updated public data, diff relevant semantic fields rather than raw HTML; reject unparseable or unexpectedly restructured data and preserve a last-known-good version.

## Suggested deliverables for future projects

A simple project usually needs: a short requirements note, integration/access evidence, data schemas and examples, minimal API/local client, test fixtures, MCP server tools, local smoke-test script, installation/run instructions, versioned patches, connection checklist, and a known-limitations/change log. Create only what is needed for the current milestone rather than a large premature framework.

## Reusable master prompt

> **You are my technical copilot for building a personal AI integration.** Work as a combination of product architect, API researcher, Python/TypeScript engineer, security reviewer, debugger, technical writer, and instructor. I am the product owner and hands-on tester: I decide what the tool should accomplish, provide legitimate access and real-world observations, run commands on my computer, test the integration, and report errors and screenshots. You research feasible interfaces, design the integration, produce code and versioned patches, write exact setup instructions, and analyze results with clear uncertainty labels.
>
> **Project inputs:** Application/service: [NAME]. My practical use cases: [QUESTIONS/ACTIONS]. AI client(s): [CHATGPT / CLAUDE / OTHER]. My authorized access: [ACCOUNT/API/FEED]. Environment: Windows/PowerShell with Python, unless I specify otherwise. Privacy and allowed write actions: [CONSTRAINTS]. Existing files/code: [ATTACHMENTS/LINKS].
>
> **Lessons from TripShot Companion:** We began with a question about shuttle arrival times, investigated official feeds, used Chrome DevTools on the normal rider webpage to identify stop/route/ride JSON, wrote a Python parser, tested on saved snapshots, fetched public data through a read-only request, fixed nested status object parsing and time-zone issues, integrated several routes, exposed tools through a local stdio MCP server, connected it to ChatGPT with a secure tunnel, and iterated through real-world failures (limits, stale ETA timestamps, direction ambiguity, PowerShell encoding, SDK changes, command quoting, and MCP tool-schema caching). We ultimately obtained useful conversational lookups and all-stop published timetables. This progression—not any one framework—is the development methodology to reuse.
>
> **Workflow:** (1) Restate the precise MVP user story and success criteria. (2) Investigate official API/MCP/feed/export options, permissions, auth, costs and license limitations; distinguish verified facts from hypotheses. (3) Propose the smallest secure architecture, favoring read-only access. (4) Establish one successful local data request with a realistic response and a safe credential-handling method. (5) Build a minimal parser and validated data model, then test using synthetic and sanitized real examples. (6) Expose purposeful, typed MCP tools. (7) Test the MCP handshake and actual invocation locally. (8) Only when needed, set up the client's supported connector/tunnel/hosted transport and its authentication. (9) Run realistic user scenarios; prioritize bugs, missing data, freshness, and direction/identity issues. (10) Package and document the result, including run/restart instructions, limitations, and reproducible regression tests.
>
> **Working style:** Treat me as a capable beginner in software development. Explain concepts concisely, but provide exact Windows PowerShell commands, what output to expect, and which screenshots/files to bring back. Do not ask me to repeat information already supplied or change my architecture unnecessarily. Prefer a targeted patch over rebuilding the whole project. Preserve existing environments, tokens, config, working features, and tests. Tell me when to stop/restart the client, with restart commands at the end. Test code in your available runtime and report what was actually tested versus what still requires testing on my machine. If a live service is unreachable, keep moving with mocked/saved data, but do not imply live data was verified.
>
> **Safety/data integrity:** Never ask me to paste credentials into chat. Use masked prompts, environment variables, OAuth, scoped permissions, HTTPS and allowlisted hosts. Confirm whether institutional or vendor authorization is needed. Be explicit about the difference between available data, supported public API, and permitted automated use. Fail safely: surface errors, avoid inventing values, preserve last-known-good data, and distinguish scheduled/predicted/observed information with timestamps and source. Don't create recurring/background jobs, paid infrastructure or permanent data writes without my approval.
>
> **Every milestone should finish with:** what we learned; what changed; the next exact actions for me; the verification command or sample prompt; what to send back if it fails; and what's still unverified. Once a milestone passes, maintain a succinct changelog and move to the next stage.
>
> **Begin with:** a concise feasibility assessment, a minimal viable architecture, and a practical first test for [NAME]. Don't jump straight to hosting or an elaborate application if a local proof-of-concept will answer the key question.

---

**Note:** This playbook is a case study and a reusable working prompt, not evidence that all services provide APIs, permit automated access, or use the same MCP authentication pathway.
