# containers

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## gke-ai-troubleshooting-jobset-interruption
Diagnoses GKE JobSet interruptions, restarts, and preemptions for AI/ML training workloads autonomously. Use when troubleshooting JobSet restart loops, spot VM preemptions, node readiness failures, host VM issues, or coordinator worker crashes. Don't use for general GKE cluster creation, basic workload deployment, or non-JobSet application issues.

Read: `library/cloud/gke-ai-troubleshooting-jobset-interruption/INSTRUCTIONS.md`

## gke-ai-troubleshooting-node-unresponsive-timeout
Diagnose and mitigate GKE TPU or GPU nodes stuck in NotReady / NodeStatusUnknown ("Kubelet stopped posting node status") due to host kernel panics, hardware lockups, or disabled node auto-repair. Use when nodes stop heartbeating beyond the node auto-repair threshold and pods remain stuck in Terminating. Don't use for healthy nodes, pod-only application crashes, or routine GKE upgrades.

Read: `library/cloud/gke-ai-troubleshooting-node-unresponsive-timeout/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-dynamic-slices-monitoring
Monitors, troubleshoots, and manages GKE TPU Dynamic Slices custom resources. Use when checking TPU slice lifecycle states, troubleshooting slice provisioning failures, validating single-slice or multi-slice (JobSet) workload manifests, or safely patching stuck finalizers and disabling the slice controller. Don't use for generic GKE cluster node pool creation or standard non-TPU workload management (use gke-basics or gke-cluster-creation instead).

Read: `library/cloud/gke-ai-troubleshooting-tpu-dynamic-slices-monitoring/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-partition-overlap
Diagnose and resolve GKE TPU slice creation failures (SliceCreationFailed) caused by partition overlap conflicts where requested TPU partitions or their nodes are already used by another slice or JobSet. Use when diagnosing GKE TPU slice creation failures with SliceCreationFailed partition or node conflicts. Don't use for general slice lifecycle states or slice provisioning failures without node overlap (use gke-ai-troubleshooting-tpu-dynamic-slices-monitoring), quota exhaustion, or unresponsive TPU nodes.

Read: `library/cloud/gke-ai-troubleshooting-tpu-partition-overlap/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-reservation-stockout
Diagnose and resolve cluster-wide GKE TPU node pool creation or scale-up failures caused by Compute Engine reservation stockouts (GCE_STOCKOUT, ZONE_RESOURCE_POOL_EXHAUSTED) when existing unhealthy or NotReady TPU node pools in the cluster have node auto-repair disabled and hold reserved TPU capacity. Use when TPU node pool creation or scale-up fails with GCE_STOCKOUT, ZONE_RESOURCE_POOL_EXHAUSTED, or ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS despite having a specific Compute Engine TPU reservation. Don't use for general pod scheduling without a TPU reservation or workload-level container crashes.

Read: `library/cloud/gke-ai-troubleshooting-tpu-reservation-stockout/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-slice-mig-stuck-updating
Diagnose and resolve GKE TPU Dynamic Slice creation and JobSet scheduling failures blocked by underlying Compute Engine managed instance groups (MIGs) stuck in an updating or unstable state (isStable=False). Use when TPU slice creation fails with a SliceCreationFailed status reason, when JobSets remain stuck in pending, or when MIG status reflects isStable=False or versionTarget.isReached=False during TPU slice formation. Don't use for SliceCreationFailed causes unrelated to MIG stability (use gke-ai-troubleshooting-tpu-dynamic-slices-monitoring) or general pod scheduling failures unrelated to TPU slices.

Read: `library/cloud/gke-ai-troubleshooting-tpu-slice-mig-stuck-updating/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-vm-repair-stuck
Diagnose GKE TPU VM instances stuck in Compute Engine repair (REPAIRING state) after host errors, maintenance events, or faulty host reports in single-host, multi-host, dynamic slicing, and TPU All Capacity mode node pools. Use when TPU instances in a slice node pool remain in REPAIRING, host error events appear in audit logs, or TPU slices are unschedulable due to a VM in repair. Don't use for nodes reporting Ready: Unknown when no VM is in REPAIRING (use gke-ai-troubleshooting-node-unresponsive-timeout), other NotReady nodes when no VM is in REPAIRING (use gke-node-notready), Pending Pods when all nodes are Ready (use gke-workload-troubleshooting), JobSet preemption events (use gke-ai-troubleshooting-jobset-interruption), or Slice custom resource lifecycle failures (use gke-ai-troubleshooting-tpu-dynamic-slices-monitoring).

Read: `library/cloud/gke-ai-troubleshooting-tpu-vm-repair-stuck/INSTRUCTIONS.md`

## gke-app-onboarding
Manages GKE application onboarding, covering containerization, deployment manifests, and migration. Use when onboarding or deploying an application to GKE for the first time, or containerizing an app for GKE. Don't use for general GKE cluster administration or upgrades (use gke-basics or gke-upgrades instead).

Read: `library/cloud/gke-app-onboarding/INSTRUCTIONS.md`

## gke-basics
Manages core GKE cluster provisioning, credentials, Autopilot vs Standard selection, and workload deployment. Use when creating GKE clusters, fetching kubectl credentials, or deciding between Autopilot and Standard modes. Don't use for Workload Identity (use gke-workload-identity), GKE networking (use gke-networking), security hardening (use gke-platform-security or gke-workload-security), or cluster upgrades (use gke-upgrades).

Read: `library/cloud/gke-basics/INSTRUCTIONS.md`

## gke-batch-hpc
Runs batch and HPC workloads on GKE, utilizing job queues and parallel processing. Use when running GKE batch jobs, configuring GKE HPC, or setting up GKE job queues. Don't use for standard web application deployments (use gke-app-onboarding instead).

Read: `library/cloud/gke-batch-hpc/INSTRUCTIONS.md`

## gke-cluster-autoscaler
Trigger on mention of GKE cluster autoscaler, node autoscaling, node pool auto-creation / node auto-provisioning. Provides guidance on enabling and optimizing cluster autoscaler, best practices, and troubleshooting issues such as nodes not scaling up or down, zonal stockouts, or capacity buffers. Do not use for ComputeClass-specific YAML generation or priority configuration (defer to gke-compute-classes skill).

Read: `library/cloud/gke-cluster-autoscaler/INSTRUCTIONS.md`

## gke-cluster-creation
Plans and executes GKE cluster creation, provisioning, and production readiness audits using pre-defined templates (Autopilot, Standard Regional, GPU/AI Inference, AI Hypercompute). Use when creating GKE clusters, provisioning GKE environments, selecting cluster modes, or auditing GKE clusters. Don't use for application onboarding or deployment configuration (use gke-app-onboarding instead).

Read: `library/cloud/gke-cluster-creation/INSTRUCTIONS.md`

## gke-compute-classes
Configures, optimizes, and troubleshoots GKE ComputeClasses. Use when configuring Spot VMs with on-demand fallback, targeting specific accelerators (GPUs/TPUs) or machine families, restricting ComputeClass access, or debugging pending pods related to node pool auto-creation. Do not use for cluster-level Node Auto Provisioning configuration or general GKE cluster creation.

Read: `library/cloud/gke-compute-classes/INSTRUCTIONS.md`

## gke-custom-golden-image-discovery
Discovers golden base images for creating GKE custom node images based on technical specifications or context clues. Use when finding the golden base image for custom GKE node creation, mapping cluster configuration parameters (GKE version, OS, architecture, accelerators, gVisor, cgroups) to image names, or querying GKE base image maps. Don't use for general GKE cluster creation (use gke-cluster-creation) or standard node pool management (use gke-basics).

Read: `library/cloud/gke-custom-golden-image-discovery/INSTRUCTIONS.md`

## gke-golden-path
Provides GKE golden path configuration defaults, production readiness checklists, and cluster default patterns. Use when designing GKE clusters, verifying GKE production readiness, or checking configurations against GKE defaults. Don't use for setting up workload autoscaling specifically (use gke-workload-scaling instead).

Read: `library/cloud/gke-golden-path/INSTRUCTIONS.md`

## gke-inference
Deploys and optimizes AI/ML inference workloads on GKE, using GPUs, TPUs, and model servers. Use when deploying GKE inference servers, configuring GKE GPU resources for inference, or deploying LLMs on GKE. Don't use for migrating existing AI workloads to GKE (use google-cloud-solution-guided-gke-ai-migration), GKE RAG with Cloud SQL/AlloyDB (use google-cloud-solution-rag-enterprise-search-gke-sqldb), or batch/HPC (use gke-batch-hpc).

Read: `library/cloud/gke-inference/INSTRUCTIONS.md`

## gke-manifest-generation
Generates and updates secure, production-ready Kubernetes YAML manifests optimized for GKE Autopilot and GKE Standard clusters. Use when creating or modifying GKE deployment manifests, configuring container security contexts, setting CPU/memory resource limits, defining readiness/liveness/startup probes, mounting secrets and volumes, configuring GKE Gateway API routes, targeting Spot VMs, or deploying AI model inference workloads (vLLM, TGI, Gemma). Don't use for live cluster operations, pod troubleshooting (use gke-workload-troubleshooting), or cluster infrastructure provisioning (use gke-cluster-creation).

Read: `library/cloud/gke-manifest-generation/INSTRUCTIONS.md`

## gke-multitenancy
Plans and configures multi-tenancy on GKE. Covers namespace isolation, RBAC planning for teams, resource quotas, LimitRanges, network isolation, and cost allocation. Use when designing GKE multi-tenancy, configuring GKE namespaces, setting up resource quotas, or isolating GKE teams. Don't use for single-tenant cluster configuration or general deployment instructions (use gke-basics or gke-app-onboarding instead).

Read: `library/cloud/gke-multitenancy/INSTRUCTIONS.md`

## gke-node-notready
Diagnoses GKE nodes reporting NotReady or Unknown status by inspecting node conditions, events, kubelet/containerd logs, and node metrics, then proposing safe remediations. Use when nodes show NotReady, when the kubelet stops posting node status, or when workloads are evicted or stuck Pending due to node health. Don't use for pod-level application failures (use gke-workload-troubleshooting), autoscaler scale-up/scale-down decisions (use gke-cluster-autoscaler), or non-GKE compute.

Read: `library/cloud/gke-node-notready/INSTRUCTIONS.md`

## gke-productionize
Orchestrates comprehensive production readiness reviews and assessments for GKE clusters and workloads across scalability, security, reliability, observability, backup/DR, and cost optimization. Use when asked to productionize, prepare, assess, audit, or review a GKE cluster or workload before going live to production. Don't use for deep-dive single-domain implementation (use specific domain skills like gke-workload-scaling, gke-platform-security, gke-workload-security, gke-service-networking, gke-reliability instead).

Read: `library/cloud/gke-productionize/INSTRUCTIONS.md`

## gke-reliability
Improves GKE workload reliability, using PDBs, health probes, and topology spread constraints. Use when configuring GKE workload reliability, setting up PDBs, or configuring GKE health probes (liveness, readiness, startup). Don't use for generating K8s YAML manifests (use gke-manifest-generation) or disaster recovery and cluster backups (use gke-backup-dr).

Read: `library/cloud/gke-reliability/INSTRUCTIONS.md`

## gke-upgrades
Plans, executes, and validates Google Kubernetes Engine (GKE) cluster upgrades and maintenance operations for both Standard and Autopilot clusters. Produces upgrade plans, pre/post-upgrade checklists, maintenance runbooks with gcloud commands, release channel strategy, and troubleshooting guides. Handles node pool upgrade strategies (surge, blue-green), version compatibility, PDB management, and workload-specific concerns (stateful, GPU, operators). Use this skill whenever the user mentions GKE upgrades, Kubernetes version bumps, node pool maintenance, GKE patching, cluster version management, release channel selection, maintenance windows, surge upgrades, stuck upgrades, or any GKE lifecycle management task — even casual mentions like "we need to upgrade our clusters" or "plan our next GKE maintenance" or "our upgrade is stuck." Don't use for GKE cluster creation, application onboarding, general networking/routing setup, or security policy configurations (use gke-basics or relevant GKE skills instead).

Read: `library/cloud/gke-upgrades/INSTRUCTIONS.md`

## gke-workload-scaling
Manages scaling for GKE workloads using HPA and VPA. Use when configuring Horizontal Pod Autoscaler (HPA), configuring Vertical Pod Autoscaler (VPA), or applying best practices for GKE workload autoscaling. Do not use for cluster-level autoscaling (Cluster Autoscaler), static cluster sizing, or configuring node-level machine styles directly.

Read: `library/cloud/gke-workload-scaling/INSTRUCTIONS.md`

## gke-workload-scaling-troubleshooting
Diagnoses GKE HorizontalPodAutoscaler (HPA) failures — metrics showing as <unknown>, FailedGetResourceMetric / FailedGetScale / FailedComputeMetricsReplicas events, missing Pod resource requests, custom/external metrics-pipeline breakage (FailedGetExternalMetric / FailedGetCustomMetric, unavailable metrics adapter, control-plane firewall blocking the adapter), HPA that won't scale up or down (tolerance / stabilization window / unavailable rate metrics), scale-to/from-zero problems, and slow HPA reaction on large clusters. Use when an HPA isn't scaling a workload as expected or reports metric errors. Don't use for configuring or authoring new HPA/VPA objects or scaling best practices (see the gke-workload-scaling skill), or for Cluster Autoscaler / node-pool sizing.

Read: `library/cloud/gke-workload-scaling-troubleshooting/INSTRUCTIONS.md`

## gke-workload-troubleshooting
Diagnoses GKE workload failures (CrashLoopBackOff, OOMKilled, ImagePullBackOff, Pending, etc.) via logs and events. Use when pods fail to start or crash repeatedly. Don't use for GKE cluster infrastructure provisioning, node pool creation, or non-Kubernetes Google Cloud services.

Read: `library/cloud/gke-workload-troubleshooting/INSTRUCTIONS.md`
