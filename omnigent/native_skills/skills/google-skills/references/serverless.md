# serverless

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## cloud-run-alert-configuration
Configures best-practice, high-signal alerting policies for Cloud Run resources on Google Cloud (services, jobs, and worker pools) based on seasoned SRE practices. Use when analyzing, recommending, writing, or deploying Terraform PromQL alerting policies to monitor Cloud Run error rates (4xx/5xx), request latency, container instance saturation (warning/critical), container CPU/memory utilization and allocation, billable instance time, job execution status, and worker pool queue backlog. Don't use for GKE workloads (use gke-alert-configuration) or Compute Engine VMs.

Read: `library/cloud/cloud-run-alert-configuration/INSTRUCTIONS.md`

## cloud-run-basics
Manages Cloud Run services, jobs, and worker pools. Use when you need to deploy applications responding to HTTP requests (services), run event-triggered or scheduled tasks (jobs), or handle always-on pull-based background processing (worker pools).

Read: `library/cloud/cloud-run-basics/INSTRUCTIONS.md`

## firebase-basics
Provides foundational Firebase CLI setup, CLI installation, version checks (`firebase-tools@latest --version`), CLI login (including --no-localhost), project creation, project selection (`firebase use`), and app config file downloads (`google-services.json`, `GoogleService-Info.plist`). Use ONLY for CLI login, project creation/switching, or downloading app config files. Don't use for Firebase Hosting deploy, Firestore, Auth, App Hosting, Data Connect, Crashlytics, or Remote Config.

Read: `library/cloud/firebase-basics/INSTRUCTIONS.md`
