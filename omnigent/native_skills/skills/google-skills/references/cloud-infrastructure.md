# cloud-infrastructure

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## application-design-center-design-deploy
Processes GCP infrastructure design and deployment workflows within Application Design Center (ADC). Use when: - Designing GCP infrastructure with Terraform. - Validating local HCL. - Performing best-practice plan scans. - Importing templates to Application Design Center (ADC). - Deploying templates. - Troubleshooting deployment failures. Boundaries: - Only use for GCP-specific cloud infrastructure. - Only use for Terraform coding within the ADC context.

Read: `library/cloud/application-design-center-design-deploy/INSTRUCTIONS.md`

## gke-alert-configuration
Configures alerting policies in Terraform for Google Kubernetes Engine (GKE) clusters, workloads, and services using PromQL and Google Cloud Managed Service for Prometheus. Use when writing, analyzing, validating, or deploying Terraform alerting policies to monitor GKE service latency, traffic, error rates using Multi-Window Multi-Burn-Rate SLO alerts, memory saturation, and cluster health such as CrashLoopBackOff and Node NotReady conditions. Don't use for non-GKE compute runtimes such as standalone Compute Engine VMs or standalone Cloud Run services without GKE.

Read: `library/cloud/gke-alert-configuration/INSTRUCTIONS.md`
