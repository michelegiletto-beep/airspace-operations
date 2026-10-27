# Operations interface

This React and TypeScript client requires the authenticated System Lab Airspace Operations API. It does not contain a demo dataset or a standalone simulation mode.

Use Node.js 22.12 or later. Install with `npm ci`, run `npm test`, then `npm run build`. Start development with `npm run dev`; Vite proxies `/api` to `http://127.0.0.1:8787`. The backend serves `dist/` in the packaged installation.

Sessions and unsaved record drafts are scoped to the browser session. Sign out clears application session storage. The backend remains the source of record and enforces organisation access, workflow transitions and optimistic concurrency. No frontend check substitutes for server permissions.

Source and record data are rendered as text. Regulatory research requires a jurisdiction and relevant date. Empty values stay missing. Missing providers do not produce simulated live information. The interface does not control aircraft or issue regulatory or U-space permissions.

Official compatibility references checked on 27 October 2026: [Vite guide](https://vite.dev/guide/) and [React build guidance](https://react.dev/learn/build-a-react-app-from-scratch). Dependencies are pinned in `package-lock.json`.
