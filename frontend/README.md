# Airspace Operations interface · 0.2.0-rc.1

This React and TypeScript client requires the authenticated System Lab Airspace Operations API. It does not contain a demo dataset or a standalone simulation mode.

Use Node.js 22.12 or later. Install with `npm ci`, run `npm test`, then `npm run build`. Start development with `npm run dev`; Vite proxies `/api` to `http://127.0.0.1:8787`. The backend serves `dist/` in the packaged installation.

Sessions and unsaved record drafts are scoped to the browser session. Sign out clears application session storage. The backend remains the source of record and enforces organisation access, workflow transitions and optimistic concurrency. No frontend check substitutes for server permissions.

Source and record data are rendered as text. Regulatory research requires a jurisdiction and relevant date. Empty values stay missing. Missing providers do not produce simulated live information. The interface does not control aircraft or issue regulatory or U-space permissions.

Official compatibility references checked on 27 October 2026: [Vite guide](https://vite.dev/guide/) and [React build guidance](https://react.dev/learn/build-a-react-app-from-scratch). Dependencies are pinned in `package-lock.json`.

The operational workspaces include Mission Control, Airspace & Sites, Scheduling, Fleet & Personnel, European Coordination and Agent Workflows. They use persisted API records and bounded workflows. Unconnected airspace and traffic layers remain explicitly unavailable. Country registration is separate from a reviewed country pack. A proposed mission does not record flight execution.

Agent Workflows consumes the server capability catalogue and displays actual controller and tool receipts. It identifies the in-house general-purpose `systemlab_agentic` coordination core and the application-specific aviation adapter. Local model modes and the native deterministic mode are distinct, explicitly selected paths. Model unavailability remains a visible blocker.

The existing Indigo and Coral companion artwork is used with the owner's permission. Its reserved proprietary rights are documented in `public/mascots/RIGHTS.md` and `provenance.json`; these images are excluded from the Apache-2.0 code licence. The actual in-house WebGL presentation renderer is reused byte-for-byte from the existing distributed package under `public/vendor/systemlab-companion/`, with two original PNG skins and a separate reserved-rights notice. A newly authored React adapter passes only presentation state, loads only Indigo or Coral, and retains the optimised image/CSS fallback. Application pause and reduced-motion preferences force renderer motion off. The images are companions, not a new System Lab logo. `LICENSES/systemlab-companion.txt` and the vendor `NOTICE.md`/`provenance.json` preserve the distinction between the reserved assets/runtime and newly authored Apache-2.0 integration code.

The map uses a documented public-domain Natural Earth country subset for general geographical context. It is not an authoritative aviation map, operational geozone feed or terrain dataset. The exact source, retrieval time, transformation and checksums are in `public/map/provenance.json`. All displayed operational geometry comes from saved operator inputs.

The versioned UI design and browser capture protocol are in `../docs/UI_DESIGN_0.2.md` and `../docs/UI_CAPTURE_PLAN_0.2.md`. Frontend verification logs are retained under `verification/0.2.0-rc.1/`. Isolated software-test fixtures never populate the operational application.
