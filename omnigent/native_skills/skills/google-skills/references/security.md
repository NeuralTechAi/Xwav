# security

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## api-gateway-backend-security-and-rate-limiting
Secures and rate limits backend services behind Google Cloud API Gateway across OpenAPI 2.0 and OpenAPI 3.0.x API configurations, including MCP-enabled gateways. Use when configuring API key or JWT authentication, locking down Cloud Run or Cloud Run functions backends with a gateway service account, reading authenticated claims from X-Apigateway-Api-Userinfo, setting per-project request quotas, or diagnosing HTTP 429 and HTTP 500 Service Control Quota errors. Do not use for Apigee, GKE Gateway API, Cloud Load Balancing custom domain setup, or LLM model routing.

Read: `library/cloud/api-gateway-backend-security-and-rate-limiting/INSTRUCTIONS.md`

## assured-workloads-basics
Provisions, inspects, updates, and deletes Google Cloud Assured Workloads V1 compliant folders, CMEK settings, Sovereign Controls by Partners, and service usage restrictions. Use when creating, listing, describing, updating, or deleting an Assured Workloads workload for any compliance regime or data boundary (FedRAMP, DoD IL2/IL4/IL5, ITAR, CJIS, Healthcare, Sovereign Controls by Partners, or Regional Data Boundaries). Don't use for brownfield assessments or custom frameworks (use assuredworkloads-environment-assessor or assuredworkloads-frameworks-*), or non-compliant folders.

Read: `library/cloud/assured-workloads-basics/INSTRUCTIONS.md`

## cloud-armor-crs-rule-upgrader
Upgrades Google Cloud Armor security policies from OWASP CRS 3.0 and 3.3 to OWASP CRS 4.22. Preserves signature opt-in and opt-out lists, translates evaluatePreconfiguredExpr to native evaluatePreconfiguredWaf dictionary parameters, remaps signature IDs to v042200, drops retired signature IDs, and updates structured preconfiguredWafConfig fine-tuning exclusions. Evaluates operational risk (High Breaking Change, Medium Attention Required, Low Clean Upgrade) including Method Enforcement breaking changes (PUT/PATCH/DELETE blocking) and sensitivity coverage expansions. Supports both in-place rule upgrades and smooth preview mode deployments with priority spacing and a 200-rule quota guardrail. Use when a user or agent needs to audit, upgrade, or transition Cloud Armor WAF rules to CRS 4.22. Don't use for non-WAF Cloud Armor rules (IP rate-limiting, geo-blocking, reCAPTCHA) or AWS/Azure WAF migrations.

Read: `library/cloud/cloud-armor-crs-rule-upgrader/INSTRUCTIONS.md`

## detection-engineering-coverage-evaluation
Automates the end-to-end detection engineering workflow in Google SecOps using MCP tools. Use when fetching threat intelligence from blogs, generating Threat Detection Opportunities (TDOs), simulating attacker behavior with synthetic UDM events, evaluating rule coverage, and deploying gap-closing rules. Don't use for standalone YARA-L 2.0 rule authoring/tuning (use secops-detection-engineering), threat hunting, or SOC investigation.

Read: `library/cloud/detection-engineering-coverage-evaluation/INSTRUCTIONS.md`

## gke-platform-security
Plans, configures, and hardens platform-level Google Kubernetes Engine (GKE) cluster security. Covers cluster add-ons (Secret Manager enablement), RBAC hardening (disabling insecure bindings, audit tools), Binary Authorization, Secrets Encryption (--database-encryption-key), Security Posture (--security-posture), enabling Shielded Nodes, GKE Sandbox cluster enablement, GKE IAM roles, and cross-service authentication IAM patterns. Use when securing cluster control planes, hardening GKE RBAC, enabling Shielded Nodes, enabling GKE Sandbox runtime, enabling cluster-wide security add-ons, or managing GKE IAM roles. Don't use for Workload Identity (use gke-workload-identity) or workload-level security (SecretProviderClass, PSS, NetPol, gVisor pod runtimeClassName; use gke-workload-security).

Read: `library/cloud/gke-platform-security/INSTRUCTIONS.md`

## gke-workload-identity
Configures and diagnoses Workload Identity Federation for GKE authentication failures for Pods (403 "iam.serviceAccounts.getAccessToken" / permission denied, "could not find default credentials", or GKE metadata server unreachable) by verifying cluster and node-pool Workload Identity configuration, the Kubernetes ServiceAccount (KSA) to IAM binding (direct principal binding and legacy Google ServiceAccount impersonation), target-resource IAM roles, and gke-metadata-server health. Use when setting up KSA/GSA bindings (`roles/iam.workloadIdentityUser`, `iam.gke.io/gcp-service-account`) or when a Pod cannot authenticate to Google Cloud APIs. Don't use for in-cluster Kubernetes RBAC errors (API-server authorization), general workload crashes (use gke-workload-troubleshooting), or Pod Security Standards and NetworkPolicies (use gke-workload-security).

Read: `library/cloud/gke-workload-identity/INSTRUCTIONS.md`

## gke-workload-security
Audits, configures, and hardens workload-level security controls for Google Kubernetes Engine (GKE) applications and namespaces. Covers running security audits (`audit_cluster.sh`), enforcing Network Policies (default-deny and Dataplane V2 logging), isolating high-risk pods inside GKE Sandbox (`gVisor`), enforcing Pod Security Standards (`restricted` labeling) and pod securityContext, and mounting Secret Manager secrets via CSI (`SecretProviderClass`). Use when auditing workload security posture, isolating namespaces, applying pod security standards, or configuring network policies and secret volume mounts. Don't use for Workload Identity (use gke-workload-identity), cluster-wide control plane security, RBAC hardening, Binary Authorization, Shielded Nodes, or enabling platform-level GKE add-ons (use gke-platform-security instead).

Read: `library/cloud/gke-workload-security/INSTRUCTIONS.md`

## google-cloud-scc-query
Queries and retrieves active security findings, external exposures, toxic combinations, vulnerabilities, threats, and sensitive data risks from Security Command Center on Google Cloud. Use when retrieving details for a security finding by its name, validating finding scope (e.g., verifying findingClass is TOXIC_COMBINATION, VULNERABILITY, EXTERNAL_EXPOSURE, or THREAT), or fetching finding details for triage. Don't use to draft remediations, apply patches, or execute configurations.

Read: `library/cloud/google-cloud-scc-query/INSTRUCTIONS.md`

## google-cloud-scc-remediation
Remediates Google Cloud Security Command Center findings, including IAM permission fixes, cloud resource misconfigurations, vulnerabilities, and Toxic Combinations. Use when asked to fix, remediate, or mitigate a Security Command Center finding or address attack paths. Don't use for general IAM policy querying without a Security Command Center finding. For runtime threat detections, this skill provides containment and investigation guidance rather than automated configuration fixes.

Read: `library/cloud/google-cloud-scc-remediation/INSTRUCTIONS.md`

## iam-helper-for-policy-management
Streamlines the creation, modification, and management of IAM allow policies (v1) and deny policies (v2). Manages access control across Resource Manager resources (Organization, Folder, Project) and individual resources. Use when creating, updating, listing, or deleting IAM allow policies or deny policies. Don't use for access denial troubleshooting (use iam-helper-for-troubleshooting), temporary privileged access (use iam-helper-for-privileged-access-management), configuring VPC Service Controls, or managing network firewall rules.

Read: `library/cloud/iam-helper-for-policy-management/INSTRUCTIONS.md`

## iam-helper-for-policy-simulator
Safely simulates and applies Identity and Access Management (IAM) v1 (Allow) policy changes on Google Cloud. Uses the Policy Simulator to replay historical access logs against proposed policies to prevent breaking active workloads before applying the changes. Use when simulating or applying IAM v1 allow policies across Projects, Folders, or Organizations. Don't use for analyzing IAM v2 deny policies, VPC Service Controls, or performing general policy troubleshooting.

Read: `library/cloud/iam-helper-for-policy-simulator/INSTRUCTIONS.md`

## iam-helper-for-privileged-access-management
Manages the end-to-end lifecycle of on-demand, temporary access using Privileged Access Manager (PAM). Use when a user asks to create, read, update, or delete PAM entitlements, request temporary access, or approve/deny pending PAM grants. Do NOT use for permanent IAM policy bindings, troubleshooting IAM permission errors, or general Google Cloud resource provisioning.

Read: `library/cloud/iam-helper-for-privileged-access-management/INSTRUCTIONS.md`

## iam-helper-for-troubleshooting
Diagnoses, remediates, and manages Identity and Access Management (IAM) access issues on Google Cloud. Supports two distinct operational modes: (1) Requester Flow for developers encountering access denials (capturing error context, self-service PAM JIT activations, elevated developer self-remediation, or logging structured tickets), and (2) Resolver Flow for privileged administrators (authoritative Policy Troubleshooter analysis, deny policy exemptions, least-privilege role discovery, and PAM/IAM provisioning).

Read: `library/cloud/iam-helper-for-troubleshooting/INSTRUCTIONS.md`

## secops-cases
Manage Google Security Operations (SecOps) SOAR cases throughout their lifecycle. Use when listing, creating, inspecting, updating, or closing SOAR cases; adding investigative comments and notes; updating case priority or description; or linking and grouping security alerts within cases. Supports both remote Google SecOps MCP tools and local fallback tools. Don't use for SIEM UDM searches or detection rule authoring.

Read: `library/cloud/secops-cases/INSTRUCTIONS.md`

## secops-detection-engineering
Author, validate, test, and deploy YARA-L 2.0 detection rules and evaluate end-to-end detection coverage gaps in Google SecOps. Use when writing new detection rules, tuning existing rules, validating syntax, testing logic against historical telemetry, or evaluating detection coverage against threat intelligence blogs, CVE disclosures, and Threat Detection Opportunities (TDOs) using synthetic UDM events and long-running coverage analysis. Don't use for alert triage (use secops-triage), deep forensic event reconstruction on infected hosts (use secops-investigate), or case management operations (use secops-cases).

Read: `library/cloud/secops-detection-engineering/INSTRUCTIONS.md`

## secops-hunt
Expert guidance for proactive threat hunting in Google SecOps. Use when proactively hunting for threats, retroactively analyzing indicators of compromise (IoCs), performing prevalence searches across enterprise events, hunting for MITRE ATT&CK techniques, or detecting behavioral and statistical outliers using UDM queries. Don't use for incoming alert triage (use secops-triage), active incident response and timeline deep-dives on a known breach (use secops-investigate), or detection rule authoring (use secops-detection-engineering).

Read: `library/cloud/secops-hunt/INSTRUCTIONS.md`

## secops-investigate
Expert guidance for deep security incident and entity investigations in Google SecOps. Use when investigating cases, analyzing entities (hosts, IPs, domains, hashes, users), extracting and searching UDM events, performing asset and user timeline analysis, and detecting lateral movement across enterprise networks. Don't use for detection rule authoring or YARA-L tuning (use secops-detection-engineering), proactive hypothesis-driven hunting (use secops-hunt), initial alert triage (use secops-triage), or basic case status updates (use secops-cases).

Read: `library/cloud/secops-investigate/INSTRUCTIONS.md`

## secops-triage
Expert guidance for security alert triage in Google SecOps. Use when investigating and triaging security alerts, determining false positives vs. true positives, assessing entity risk, adjusting alert severity or priority, and closing or escalating alerts and cases. Don't use for deep multi-hop incident investigations across host timelines (use secops-investigate), proactive threat hunting or retroactive IoC sweeps (use secops-hunt), or authoring new detection rules (use secops-detection-engineering).

Read: `library/cloud/secops-triage/INSTRUCTIONS.md`
