# Browser capture protocol, 0.2.0-rc.1

Capture the running application served by the actual API, after building the frontend. Use a real provisioned organisation account with the role recorded in capture evidence. Do not insert fictional aircraft, permissions, missions, maintenance, telemetry, incidents or financial results to make a screen appear populated.

An empty operational workspace is a valid capture. Actual ingested public regulatory records and genuine bounded research workflow receipts may be shown with their original provenance. An operator's explicitly entered proposed operation may be shown only as a proposal; it must not be described as a flight, customer service, permission or measured business result.

## Planned views

| Capture | App location | Evidence to retain |
| --- | --- | --- |
| Mission Control | `#operations` | Actual queue/empty state, separate readiness decisions, real map context and current role. |
| Airspace & Sites | `#airspace` | Source attribution, explicit operational-feed limits, operator geometry or honest empty geometry state. |
| Scheduling | `#scheduling` | UTC date, actual resources or empty resources, saved solver runs only. |
| Fleet & Personnel | `#fleet` | Aircraft or honest empty state; maintenance lifecycle and role restrictions where visible. |
| European Coordination | `#crossborder` | Individual country segments and actual catalogue status; no default permission. |
| Agent Workflows | `#agents` | Actual bounded scope, controller identity, tool receipts, blocker/review state and in-house core relationship. |

Use an approximately 1260-pixel desktop viewport and also inspect a narrow viewport for responsive defects. Capture actual pages through the supported computer-use browser surface. A complete page and a carefully chosen visible viewport may both be retained; image crops must preserve important state limitations and provenance. Do not retouch the product output, replace rendered data or add approval marks.

For each published image, record the page URL/hash, frontend release version, capture time, viewport, data context, role and image checksum. Exclude credentials, tokens and private account details. Verify each visible action against its backend capability; unavailable capabilities must remain disabled or absent. Save the capture evidence and actual image paths in the publication manifest maintained by the release owner.

Inspect keyboard focus, readable contrast, empty states, map attribution, reduced motion, lateral overflow and stale/missing-data messages before using screenshots in the project page. Captures demonstrate observed software behaviour only. They do not establish live operational validation, legal permission or certification.

For the owned animation runtime, inspect the rendered companion canvas `data-companion-runtime` and `data-companion-engine` attributes. An active WebGL path reports `active` and `webgl-mesh-2.5d`; fallback remains visibly usable. Verify that only `/vendor/systemlab-companion/assets/originals/mascotte_01_indaco.png` and/or `mascotte_06_coral_compact.png` are requested by exposed companion appearances. Pause globally and exercise a system reduced-motion preference; the adapter must send `motion: off`. Record observed browser behaviour separately from mocked component checks. The visual renderer has no operational authority.
