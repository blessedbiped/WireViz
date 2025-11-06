# WireViz Constitution — Framework

This document defines the governance, roles, processes, and core principles that guide WireViz. It is a lightweight, practical constitution intended to keep project decisions transparent, scalable, and aligned with the original project goals: to provide a simple, extensible, and reliable toolkit for generating visual representations of wiring and connection data (CLI + library), driven by human-readable input formats and producing high-quality diagrams.

## 1. Purpose & Mission
- Purpose: make it easy to convert structured wiring / connection descriptions into clear, maintainable visual diagrams.
- Mission: provide a stable, well-tested library and CLI that is:
  - simple to use from YAML/other input files,
  - extensible (plug-in points, clear APIs),
  - reproducible (deterministic outputs where feasible),
  - usable in CI and tooling pipelines.

## 2. Scope
Included:
- Parsers and standard input formats (YAML, JSON).
- Core rendering via Graphviz and image output (PNG/SVG/etc).
- CLI tooling for generation, preview, and batch runs.
- Library API for programmatic integration.
Excluded (non-goals):
- Reimplementing full CAD/Electrical simulation features.
- Proprietary/closed storage backends.

## 3. Roles
- Project Team: active maintainers with write access who review and merge PRs.
- Committers: contributors whose sustained contributions earn commit rights.
- Contributors: anyone submitting issues, PRs, docs, tests, translations.
- Release Manager: rotates among maintainers per release or as agreed.

Role assignment:
- New maintainers are nominated by existing maintainers and accepted by consensus or majority.

## 4. Decision Making
- Default: consensus with a "lazy consensus" window (48–72 hours) for non-urgent changes.
- If consensus cannot be reached, a simple majority of active maintainers decides.
- Major or breaking changes require a documented upgrade path and a deprecation period.

## 5. Contribution Process
- Work from issues or open a proposal issue for larger changes.
- Use topic branches and open a pull request with tests and documentation.
- PR checklist:
  - Describe the change and motivation.
  - Include tests where applicable.
  - Document public API changes.
  - Confirm linting/CI passes.
- Code reviews: at least one approving review from a maintainer for non-trivial changes; two for breaking or large refactors.

## 6. Quality & CI
- Tests must cover behavior for parsers, core transformations, and rendering integration where practical.
- CI must run linting, unit tests, and smoke integration tests (graph generation).
- Releases follow semantic versioning where feasible.

## 7. Security & Responsible Disclosure
- Security issues should be reported privately to the maintainers as described in the SECURITY.md (or via the repository contact) and handled promptly.
- No public disclosure until a fix or mitigation is available, unless agreed otherwise.

## 8. Code of Conduct
- Contributors are expected to behave respectfully and professionally.
- The project follows the standards set out in the repository's Code of Conduct; violations should be reported to the maintainers.

## 9. Licensing & Trademarks
- The project respects the repository LICENSE file. Contributors must ensure contributed code is compatible with the chosen license.
- Trademarks and the project name usage are governed by repository policy (see LICENSE or trademark documentation if present).

## 10. Dispute Resolution
- Maintain an open discussion. If disagreements persist:
  - Escalate to maintainers for mediation.
  - If needed, invite neutral community members to arbitrate.
  - Document the outcome and reasoning in the issue/PR.

## 11. Amendment
- This constitution can be amended by a PR that:
  - Documents the proposed changes and rationale.
  - Is reviewed and approved by a majority of active maintainers.
  - Changes take effect when merged.

## 12. Transparency & Records
- Major decisions (API changes, governance changes, release policies) should be recorded in the repo (issues, PRs, or governance docs) so history is auditable.

---

This framework is intentionally concise. Specifics (release cadence, maintainer list, security contacts, code of conduct link) should be added to this document as the project matures.
