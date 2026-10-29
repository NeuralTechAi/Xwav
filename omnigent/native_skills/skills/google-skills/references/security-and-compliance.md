# security-and-compliance

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## assuredworkloads-environment-assessor
Discover Google Cloud resource telemetry and effective Org Policies, evaluate brownfield workloads against sovereign data boundary and compliance standards (EU Data Boundary with Support, FedRAMP Moderate/High, DoD IL4/IL5, ITAR, CJIS, US/EU Regional Data Boundaries), and recommend the optimal Assured Workloads Framework. Use when asked to: "assess my environment for compliance", "which Assured Workloads framework should I use?", "check if my folder is ready for EU sovereignty", "evaluate compliance posture for folders/123 or projects/xyz", or "discover compliance gaps before deployment". Do NOT use for live mutating policy deployments, generating deep audit reports via Cloud Audit Manager, generating remediation scripts, or authoring custom Assured Workloads frameworks.

Read: `library/cloud/assuredworkloads-environment-assessor/INSTRUCTIONS.md`

## assuredworkloads-frameworks-author
Authors custom cloud controls and customized frameworks for Assured Workloads when built-in resources cannot satisfy core requirements. Use when creating or synthesizing custom data boundary resources. Don't use for browsing or mapping existing built-in frameworks (use assuredworkloads-frameworks-navigator instead).

Read: `library/cloud/assuredworkloads-frameworks-author/INSTRUCTIONS.md`

## assuredworkloads-frameworks-navigator
Acts as a Data Boundary Compliance Analyst that maps user compliance queries against Data Boundary Frameworks and cloud controls, validates matched resources, and recommends appropriate Frameworks or cloud controls. Use when mapping direct natural language workload requirements to Assured Workloads / Data Boundary Frameworks and cloud controls, browsing built-in Data Boundary frameworks, or identifying major requirement gaps. Don't use for non-Data-Boundary Compliance Manager posture assessments or direct Terraform deployment execution without framework selection.

Read: `library/cloud/assuredworkloads-frameworks-navigator/INSTRUCTIONS.md`
