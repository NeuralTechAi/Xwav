# cloud-observability-and-monitoring

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## cloud-logging-configuration-basics
Configure single-project Cloud Logging on Google Cloud: regional log buckets, log sinks, log views, restricting or hiding sensitive logs in the default view (_Default) filter, IAM permissions for views (Logs View Accessor, IAM conditions), logs-based metrics, log exclusions, and sampling. Don't use for cross-project logging or multi-project setups.

Read: `library/cloud/cloud-logging-configuration-basics/INSTRUCTIONS.md`

## cloud-logging-cross-project-configuration
Configure and troubleshoot Google Cloud cross-project centralized logging and read-time aggregation. Use when: - Setting up log routing from multiple projects/folders/organizations to a central log bucket. - Creating cross-project log sinks and configuring central log buckets. - Troubleshooting cross-project routing. Don't use for single-project basic configurations.

Read: `library/cloud/cloud-logging-cross-project-configuration/INSTRUCTIONS.md`

## cloud-logging-finops
Audits Cloud Logging costs for a Google Cloud project: the charges for log entries written to log buckets, the services, log streams and severities that drive them, and the log sinks that route them. Reconciles Cloud Billing export costs with Cloud Monitoring volume metrics, and generates a FinOps report with charts and copy-paste exclusion filters. Use when auditing Cloud Logging spend, finding logging waste, identifying top logging contributors, generating log cost reduction reports, or creating log sink exclusion filters. Don't use for querying log entries (use cloud-logging-query-generation), configuring Cloud Monitoring alerts, or querying metrics/traces.

Read: `library/cloud/cloud-logging-finops/INSTRUCTIONS.md`

## cloud-logging-query-generation
Generates Logging Query Language (LQL) queries for Cloud Logging on Google Cloud from natural language. Use this skill when you need to query log data or when you are debugging issues. You can filter log data by Google Cloud service. Don't use this skill to query other databases, such as SQL or Cloud Spanner.

Read: `library/cloud/cloud-logging-query-generation/INSTRUCTIONS.md`

## cloud-monitoring-chart-generation
Generates Cloud Monitoring Server-Driven UI (SDUI) Widget and XyChart Protocol Buffer textprotos on Google Cloud from resolved PromQL or ListTimeSeries queries. Use when: - Generating valid google.monitoring.dashboard.v1.Widget textprotos, containing PrometheusQuery or TimeSeriesFilter datasets, for use with the Cloud Monitoring Dashboards API, gcloud CLI, or declarative dashboard definitions. - Synthesizing Server-Driven UI (SDUI) widget titles, axis labels, and plot types for Prometheus or ListTimeSeries queries. Don't use for: - Metric discovery or PromQL query generation. For those tasks, use the cloud-monitoring-metric-selection or cloud-monitoring-promql-query skills.

Read: `library/cloud/cloud-monitoring-chart-generation/INSTRUCTIONS.md`

## cloud-monitoring-list-time-series-request
Generates valid Cloud Monitoring ListTimeSeries requests and aggregation specifications from metric descriptors and resource parameters. Use when asked to create, generate, format, or build ListTimeSeries requests, JSON payloads, filter expressions, or aligner/reducer aggregations for Cloud Monitoring metrics and charts. Don't use for metric discovery or metric selection.

Read: `library/cloud/cloud-monitoring-list-time-series-request/INSTRUCTIONS.md`

## cloud-monitoring-metric-selection
Retrieve, query, and identify relevant Cloud Monitoring metric descriptors on Google Cloud for a service or resource (such as Compute Engine, Spanner, BigQuery, Cloud Run, Cloud SQL, Pub/Sub, Cloud Storage, etc.). Use when asked to find, list, search, or discover GCP metric types, names, kind/value schemas, or descriptors.

Read: `library/cloud/cloud-monitoring-metric-selection/INSTRUCTIONS.md`

## cloud-monitoring-notification-channels-configuration
Generates Terraform HCL configurations for Cloud Monitoring notification channels (`google_monitoring_notification_channel`) and adds notification channels to alerting policies (`google_monitoring_alert_policy`) in Google Cloud projects. Use when creating or configuring email, SMS, Slack, PagerDuty, Pub/Sub, or webhook notification channels, verifying Pub/Sub topic compatibility (including cross-project topics, message storage policies, and in-transit enforcement) and publishing permissions for the Cloud Monitoring Service Agent, or adding notification channels to existing alert policies. Don't use for authoring or editing alerting policy conditions, selecting metric descriptors, or writing PromQL or Monitoring Filter queries.

Read: `library/cloud/cloud-monitoring-notification-channels-configuration/INSTRUCTIONS.md`

## cloud-monitoring-promql-query
Generates valid PromQL queries from Cloud Monitoring metric descriptors and resource parameters. Use when asked to create, generate, write, or format PromQL queries, PromQL strings, or PromQL aggregations for Cloud Monitoring metrics and resources. Don't use for raw metric discovery or metric selection.

Read: `library/cloud/cloud-monitoring-promql-query/INSTRUCTIONS.md`

## cloud-trace-querying
Query Cloud Trace spans, filter by latency thresholds or error status, correlate distributed traces with Cloud Logging, and diagnose latency bottlenecks across Google Cloud services. Use when investigating slow requests, analyzing trace hierarchies, or resolving latency regressions. Do NOT use for querying non-GCP telemetry or database query optimization outside Cloud Trace.

Read: `library/cloud/cloud-trace-querying/INSTRUCTIONS.md`

## gke-ai-troubleshooting-handle-disruption-gpu-tpu
Diagnoses, predicts, and mitigates node disruptions during Compute Engine host maintenance and hardware or software maintenance events for GPU and TPU workloads on GKE. Use when diagnosing node disruptions, predicting host maintenance events on GPU/TPU nodepools, inspecting node interruption PromQL metrics, auditing node taints, or configuring workload protection strategies (graceful termination, opportunistic maintenance, PodDisruptionBudgets). Don't use for general GKE cluster creation, network policy configuration, or non-disruption workload deployment.

Read: `library/cloud/gke-ai-troubleshooting-handle-disruption-gpu-tpu/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-metrics-monitoring
Monitors and troubleshoots GKE TPU workloads, nodes, and node pools using GKE system metrics and PromQL. Use when monitoring TensorCore duty cycle, TPU memory, node readiness, multi-host TPU node pool availability, host maintenance or preemption interruptions, and calculating MTTR or MTBI metrics for GKE TPUs. Don't use for general non-TPU GKE workload monitoring or non-metric TPU debugging.

Read: `library/cloud/gke-ai-troubleshooting-tpu-metrics-monitoring/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-vbar-oom
Diagnoses and prevents vbar_control_agent segfaults, out-of-memory (OOM) errors, and TPU device initialization failures on TPU v6e nodes in GKE caused by race conditions during TPU device resets or high-frequency metrics polling. Use when troubleshooting vbar_control_agent crashes, memory cgroup OOMs in serial console logs, tpu-device-plugin metrics checksum corruption errors, or custom TPU metrics collection conflicts on GKE TPU v6e nodes. Don't use for general non-TPU container OOM troubleshooting or standard GKE node lifecycle operations.

Read: `library/cloud/gke-ai-troubleshooting-tpu-vbar-oom/INSTRUCTIONS.md`

## gke-cost-analysis
Answer natural language questions and perform analysis on GKE cluster and workload costs using BigQuery billing exports, cost allocation data, and live cluster monitoring metrics. Use when querying GKE costs across projects, namespaces, or workloads, analyzing billing reports in BigQuery (`bq`), checking cluster cost budgets (`gcloud billing`), or diagnosing cost drivers like pod requests vs. actual utilization (`kubectl top`). Don't use for applying cost optimization changes, creating rightsizing manifests (VPA/MPA), or selecting ComputeClasses (use gke-cost-optimization instead).

Read: `library/cloud/gke-cost-analysis/INSTRUCTIONS.md`

## gke-cost-optimization
Optimizes GKE costs, rightsizes workloads, and configures Spot VMs, CUDs, cost allocation, and resource quotas. Use when optimizing GKE cluster or workload costs, configuring GKE cost allocation or quotas, rightsizing CPU/memory requests, or selecting Spot VMs and machine types. Don't use for general compute class provisioning or GPU Selection (use gke-compute-classes instead).

Read: `library/cloud/gke-cost-optimization/INSTRUCTIONS.md`

## gke-observability
Configures GKE observability, including Cloud Logging, Cloud Monitoring, and managed Prometheus. Use when configuring GKE monitoring, setting up GKE logging, or configuring Prometheus metrics collection, and to troubleshoot Managed Service for Prometheus (GMP) issues such as missing metrics, unhealthy scrape targets, PodMonitoring misconfiguration, rule/alert evaluation failures, and monitoring permission errors. Don't use to configure local application logging frameworks or external APMs outside GKE.

Read: `library/cloud/gke-observability/INSTRUCTIONS.md`

## google-cloud-slo-alert-configuration
Configures Cloud Monitoring PromQL-based Service Level Objective (SLO) alerting policies on Google Cloud for resources registered in App Hub or individually specified. Generates Terraform output. Use when the user asks to configure an SLO or Service Level Objective. Don't use for standard alerting policies.

Read: `library/cloud/google-cloud-slo-alert-configuration/INSTRUCTIONS.md`

## workload-manager-basics
Use this skill to manage Google Cloud Workload Manager evaluations, rules, scanned resources, and validation results by using public client libraries and the REST API. Use when you need to inspect workload best-practice rules, create and run evaluations for Google Cloud general best practices, SAP, SQL Server, or custom organizational rules, review violations, export results to BigQuery, or automate Workload Manager through client libraries because no service-specific public CLI or MCP server is available. Don't use for general Google Compute Engine instance management, VPC configuration, or standard IAM auditing.

Read: `library/cloud/workload-manager-basics/INSTRUCTIONS.md`
