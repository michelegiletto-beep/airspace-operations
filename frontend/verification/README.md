# Frontend engineering verification

Checked on 27 October 2026 with Node.js 22.13.1 and npm 10.9.2 on Windows. This evidence concerns software behaviour, not aviation approval or operational acceptance.

Commands actually executed from `frontend/`:

| Command | Result |
| --- | --- |
| `npm ci --ignore-scripts --fetch-retries=0 --fetch-timeout=20000` | Passed; 108 packages installed from the dedicated lockfile. |
| `npm run build` | Passed; strict TypeScript check and Vite production build. Final measured assets: 296.66 kB JavaScript (88.25 kB gzip), 23.23 kB CSS (5.90 kB gzip). |
| `npm test` | Passed; 27 isolated software tests in seven suites. |
| `node node_modules/vitest/vitest.mjs run --reporter=json --outputFile=verification/tests.json` | Passed; machine-readable results stored in `tests.json`. |
| `npm audit --json --registry=https://registry.npmjs.org` | Passed after upgrading Vitest to 4.1.12; zero known findings reported across installed runtime and development dependencies. Report in `npm-audit.json`. |

Tests cover authenticated requests, concurrency rejections, role-specific authoring, self-approval prevention, decisions against saved revisions, reserved metadata, missing financial values, unknown vertical references, DST timestamp rendering, jurisdiction/date submission, unsupported questions, escaped malicious source passages refused script links, bounded evidence uploads, saved-version attachment writes, independent alert acknowledgement, absent approved incident procedures, truthful timeline empty states, HTML attachment exports and authenticated contract inspection. All artificial records are confined to test files and their isolated test runtime.

An earlier dependency audit identified two moderate findings in the Vitest 4.1.0 test dependencies. Upgrading to 4.1.12 resolved those reported findings. Initial installation hit an npm 10 peer-resolution error; the scoped `.npmrc` selects legacy peer resolution, and a subsequent clean `npm ci` passed. Vite is configured locally to avoid inheriting the unrelated System Lab website's PostCSS configuration.

The interface uses real API services. Provider connectivity, current legal coverage, operational data rights, SORA decision tables, live dispatch and authority acceptance are separately assessed by the backend and product capability register. These frontend tests do not establish live provider acceptance or certified aviation capability.

Browser inspection of the integrated application is recorded separately by the parent delivery workflow. This report does not claim a browser session that was not executed by this frontend task.


