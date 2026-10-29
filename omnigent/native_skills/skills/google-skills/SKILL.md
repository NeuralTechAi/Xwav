---
name: google-skills
description: Select official Google product skills for Google Cloud/GCP, Gemini or Vertex AI/Agent Platform, Firebase, GKE/Kubernetes on GCP, BigQuery, Cloud SQL, Spanner, Google Ads/AdMob, Google Analytics, Google Identity and Genkit. Use for Google-specific implementation, operations or troubleshooting; skip generic coding and unrelated providers. Loads one matching topic and skill on demand.
---

# Google skills, on demand

This native entry provides Google's official skill collection through staged discovery.
No installation, authentication or network access is needed to read the bundled guidance.

1. Identify the Google product and concrete task. For unrelated work, stop and use no Google skill.
2. Check the existing skill catalog first. If a user/project/plugin skill already covers the same upstream name or instructions, use that copy and its invocation policy; do not load a second copy from this library. Respect explicit exclusions and manual-only restrictions. If the requested subskill is disabled, do not bypass that restriction through this entry.
3. Read only the matching topic below with `read_skill_file`, using `skill_name: google-skills`. Choose the smallest relevant set from its descriptions; ordinarily one skill. If ambiguous, clarify the product rather than reading every topic.
4. Read the selected `library/.../INSTRUCTIONS.md` using the same tool. Native harnesses may use their file reader from this skill's directory instead. Resolve all relative links and script paths relative to that selected file's parent, not this entry's root. Upstream entry files are named `INSTRUCTIONS.md` here to prevent recursive vendor discovery from advertising duplicate skills; resolve an upstream link ending in `SKILL.md` to the sibling `INSTRUCTIONS.md` when needed. Do not invoke `load_skill` for a library name: these are staged resources, not 177 separate catalog entries.
5. Follow the selected instructions; read supporting references only for the current step. Reuse already loaded guidance. Do not recursively preload all linked documents, list or read the entire library, or download a duplicate copy using upstream installers or skill finders.
6. Reading guidance does not run scripts, install SDKs/MCP servers, enable APIs, sign in, deploy resources or authorize spending. Check actual prerequisites when needed and apply the user's scope and Xwav's existing policies. Explain unavailable credentials/tools precisely. Upstream references to other plugins may require separate setup; these plugin runtimes are not bundled.

## Topic index

- ai and machine learning: `references/ai-and-machine-learning.md` (26 skills)
- application development: `references/application-development.md` (4 skills)
- big data and analytics: `references/big-data-and-analytics.md` (14 skills)
- cloud infrastructure: `references/cloud-infrastructure.md` (2 skills)
- cloud infrastructure and services: `references/cloud-infrastructure-and-services.md` (3 skills)
- cloud observability and monitoring: `references/cloud-observability-and-monitoring.md` (18 skills)
- compute: `references/compute.md` (1 skills)
- containers: `references/containers.md` (25 skills)
- databases: `references/databases.md` (5 skills)
- dev ops: `references/dev-ops.md` (2 skills)
- getting started: `references/getting-started.md` (3 skills)
- google ads: `references/google-ads.md` (14 skills)
- google analytics: `references/google-analytics.md` (2 skills)
- identity: `references/identity.md` (2 skills)
- multi product solutions: `references/multi-product-solutions.md` (12 skills)
- networking: `references/networking.md` (4 skills)
- security: `references/security.md` (18 skills)
- security and compliance: `references/security-and-compliance.md` (3 skills)
- serverless: `references/serverless.md` (3 skills)
- storage: `references/storage.md` (10 skills)
- well architected framework: `references/well-architected-framework.md` (6 skills)

## Provenance

177 upstream skills and their relative supporting resources are bundled with unchanged file contents under `library/`, pinned to Google skills revision `c1578116ec34d574e5df618bb02849ecc717d329`. Apache-2.0; see `LICENSE.upstream`. `catalog.json` records paths and checksums for maintenance, not a prompt to preload it. Google Cloud plugin submodules and repository installers/hooks are excluded.
