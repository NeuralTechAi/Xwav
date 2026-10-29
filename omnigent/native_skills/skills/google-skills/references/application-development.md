# application-development

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## application-integration-authoring
Builds, versions, publishes, tests, and executes Google Cloud Application Integration workflows through the REST API and Python discovery client, and promotes versions across environments. Use when listing integrations, downloading or uploading integration versions as JSON, configuring API triggers or config variables, publishing drafts, invoking integrations, or automating CI/CD promotion. Do not use for initial region provisioning and IAM setup (use application-integration-basics) or diagnosing failed runs and logs (use application-integration-troubleshooting).

Read: `library/cloud/application-integration-authoring/INSTRUCTIONS.md`

## application-integration-basics
Explains Google Cloud Application Integration concepts, region provisioning, IAM roles, run-as service accounts, interface choices (REST, Python discovery client, Terraform, ADK), and platform limits. Use when setting up Application Integration in a Google Cloud project, enabling required APIs, provisioning a region, configuring IAM or run-as service accounts, choosing between Application Integration and custom code, or checking quotas and timeouts. Do not use for building, publishing, or invoking integrations (use application-integration-authoring) or diagnosing failed or stuck runs and logs (use application-integration-troubleshooting).

Read: `library/cloud/application-integration-basics/INSTRUCTIONS.md`

## application-integration-troubleshooting
Diagnoses failed, stuck, or silent Google Cloud Application Integration runs and Integration Connectors tasks using the REST API, Cloud Logging, and Cloud Monitoring. Use when an integration fails, returns HTTP 200 without doing the expected work, hangs in a suspended or retry state, or hits IAM, run-as service account, connector health, or quota errors. Do not use for initial region provisioning (use application-integration-basics) or building and deploying versions (use application-integration-authoring).

Read: `library/cloud/application-integration-troubleshooting/INSTRUCTIONS.md`

## migrate-to-rust
Clones, analyzes, plans, and migrates legacy codebases (C++, Fortran, Java, Python, C, Shell) from a GitHub URL or local directory to a modern, high-performance, deterministic, 100% Safe Rust architecture, tracking live telemetry across every task bucket, test failure/fix cycle, and Profile-Guided Optimization (PGO) stage, and producing a first-person AI storytelling report and interactive HTML infographic. Use when migrating a GitHub repository or local codebase to Rust, porting legacy C++, Fortran, Python, or Java workloads to memory-safe Rust, designing Struct-of-Arrays (SoA) or SIMD Rust architectures, or optimizing Rust ports with LLVM PGO. Don't use for unrelated non-Rust refactoring or single-line syntax questions.

Read: `library/developers/migrate-to-rust/INSTRUCTIONS.md`
