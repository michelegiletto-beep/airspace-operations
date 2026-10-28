# Interface design and implementation, 0.2.0-rc.1

The interface is an authenticated operations application. A navy navigation rail groups operational work, assurance and coordination. A light workspace uses compact typography, aligned tables, a shared panel pattern and a limited blue accent. State text accompanies colour; no state depends on colour alone. The user role, organisation reference and release status remain visible.

## Operational flows

| Workspace | Actual application behaviour | Boundary visible to the user |
| --- | --- | --- |
| Mission Control | Loads saved missions, aircraft, personnel, permissions, routes, sites and alerts. An intended-operation form persists a draft, its explicit UTC offsets and selected real resources. | User-entered proposals and actual flight execution are separate. Empty queues contain no illustrative flights. |
| Airspace & Sites | Displays supplied WGS 84 geometries over Natural Earth context. Supports site/route drawing, exact coordinate entry, saved geometry and source-linked screening. | General geography is not an aviation data service. Unknown vertical references, unconnected traffic and missing operational zones remain explicit. |
| Scheduling | Draws saved assignments on an aircraft timeline and shows actual solver runs. Builds proposals from saved scheduling baselines or an explicit complete operator input; exposes reviewer assignment, reservation, cancellation, pilot acknowledgement and dispatch review. | Solver result, independent verification, internal reservation, pilot acknowledgement, dispatch release and actual execution are separate. The server rechecks current records and permissions. |
| Fleet & Personnel | Manages configuration records, measured utilisation, source-defined maintenance programmes, work orders, independent reviewers, actual personnel and proposed mission teams. | No universal maintenance interval, duty limit, measured counter or release authority is supplied as an operational default. |
| European Coordination | Records country reviews and genuine instruments, assesses individual country segments and handovers, and manages explicit bilateral aircraft-sharing terms. | Catalogue registration is not legal validation. A sharing agreement does not transfer an authorisation or create an aircraft command. |
| Agent Workflows | Creates a scope with an explicit controller mode, relevant date, context versions and bounded resource budget. Starts a durable job and shows actual receipts, prepared artifacts, blockers and review checkpoints. | The native deterministic path is separately named. Model failure does not trigger an undisclosed fallback. The workflow cannot approve itself or communicate externally. |

The existing source-grounded Regulatory Library, controlled Authorisations, Safety Evidence, Incidents, Deployment Planning and Administration remain integrated with the same API and record system. Additional structured fields are available for advanced operator inputs; their schema and missing evidence remain inspectable.

## In-house technology relationship

The Agent Workflows view identifies the server-reported `systemlab_agentic` general-purpose coordination package and its version. The application supplies aviation-specific typed capabilities, source and context access, deterministic tools and approval boundaries. The interface links the existing System Lab Multiagentic Systems programme. It does not imply that the proprietary trading implementation has been copied, open-sourced or certified for aviation.

## Owned artwork and map provenance

Indigo is copied byte-for-byte from `public/assets/agent-indigo.webp` in the established System Lab workspace. Coral is copied from `public/assets/reasoning-companion.webp`. The user explicitly authorised use of the owned characters. The original artwork remains proprietary, with separate rights and SHA-256 provenance in `frontend/public/mascots/`. The existing distributed presentation renderer, motion core and catalogue are now reused byte-for-byte with the two original PNG skins under `frontend/public/vendor/systemlab-companion/`. This is actual reuse of the in-house animation runtime, with reserved rights preserved; it does not copy a trading engine, broker adapter, model, private configuration or training implementation. A fresh Apache-2.0 React adapter mounts and disposes the renderer, passes only presentation state, and exposes only Indigo and Coral. An optimised image and newly authored CSS provide fallback when the module, source image or WebGL path is unavailable. No new logo, regenerated mascot or ornamental network graphic was introduced.

The map is a 52-feature subset of the actual Natural Earth 1:50m Admin 0 Countries dataset, retrieved on 28 October 2026. Geometry coordinates are preserved; metadata is reduced and Europe-related features selected. The public-domain terms, upstream and subset checksums and exact transformation are in `frontend/public/map/provenance.json`. The SVG projection is exclusively for display. Safety distances use backend geodesic calculations; this map introduces no operational-distance calculation.

## Accessibility and resilience

- Native labels, buttons, form validation and explicit units support keyboard use. A corrected `:is(...):focus-visible` selector preserves a visible keyboard ring without drawing rings around every unfocused control.
- The map supports keyboard panning and zoom, exact coordinate forms and a separate saved-record list. A map is not the sole way to inspect an operation.
- A global companion-motion preference and live `prefers-reduced-motion` changes force the owned renderer to `motion: off` and disable fallback CSS movement. Text states stay visible with animation stopped. The renderer's upstream reduced-motion setting alone is not relied upon, because that mode still permits limited movement.
- Mission and workflow drafts use actor- and organisation-scoped browser session storage. Generic controlled-record drafts retain their prior scoped revision handling.
- Source and API failures produce visible messages; unavailable data is not replaced by sample activity. Concurrency errors retain the server explanation.
- Role restrictions disable or omit controls when the current role cannot perform the action. The backend remains authoritative, including independent review, exact versions and resource reservations.

The country-instrument form distinguishes operator-documented `host_declaration_submission` and `luc_host_notification` from host-issued confirmation. The first two require an actual recipient country and provision timestamp, originate from the registration country, and refer to documented provision/delivery evidence. They do not imply a host-authority response. The operational-authorisation route retains its distinct host-confirmation instrument. The preserved Article 13 source reference and currentness limitations are documented in `fleet-and-cross-border.md`.

## Verification limits

Frontend unit and interaction tests use isolated fixtures and test fetch responses. They verify presentation and request contracts; they are not live provider integration tests. Browser captures are made from the running authenticated application and have their own evidence. Software checks, screenshots and usability review confer no aviation certification or operational acceptance. Full accessibility conformance and every deployment-specific failure mode have not been independently certified.
