# storage

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## gke-backup-dr
Configures Backup for GKE: the BackupRestore cluster addon, BackupPlan and RestorePlan resources, restore workflows, and CMEK-encrypted backups. Use for backup policies, disaster recovery, or GKE cluster restores. Don't use for database backups.

Read: `library/cloud/gke-backup-dr/INSTRUCTIONS.md`

## gke-storage
Manages GKE storage, including PVCs, PersistentVolumes, and Filestore. Use when configuring GKE storage or creating PVCs. For GCS FUSE mounts, use google-cloud-storage-fuse. For diagnosing storage failures (volume attach/mount errors, disk performance/node storage pressure, or Cloud Storage FUSE OOM), use gke-storage-troubleshooting. Don't use for database administration or replication strategies outside volume provisioning context.

Read: `library/cloud/gke-storage/INSTRUCTIONS.md`

## gke-storage-troubleshooting
Diagnoses GKE persistent-storage failures — volume attach/mount errors (Regional PD on optimized VMs, fsGroup mount timeouts), disk-performance and node storage-pressure issues, slow-disk Pod-creation failures, volume-expansion problems, Local SSD / Hyperdisk Storage Pool creation errors, and Cloud Storage FUSE OOM. Use when Pods are stuck in ContainerCreating, volumes fail to attach or mount, or nodes report storage pressure. Don't use for routine storage provisioning or StorageClass/PVC authoring (see the gke-storage skill).

Read: `library/cloud/gke-storage-troubleshooting/INSTRUCTIONS.md`

## google-cloud-filestore-auditing
Audits Filestore instances on Google Cloud across projects for disaster recovery readiness (missing or stale backups), security access governance (overly permissive NFS export rules, 0.0.0.0/0 exposure, missing ROOT_SQUASH), and reliability compliance (Physical Zone Isolation PZI and Physical Zone Separation PZS). Use when assessing storage health posture, auditing NFS export permissions, identifying unprotected file shares, or validating zone failure domains. Don't use for Cloud Storage buckets, Persistent Disk, or NetApp Volumes.

Read: `library/cloud/google-cloud-filestore-auditing/INSTRUCTIONS.md`

## google-cloud-filestore-autoscale
Inspects Filestore capacity and utilization on Google Cloud, evaluates storage scaling rules, and performs capacity autoscaling (scale UP for low free space or scale DOWN for cost optimization). Use when monitoring Filestore instance headroom, resizing instance shares, configuring automated growth/shrink thresholds (custom thresholds apply globally across projects in session memory), or preventing out-of-space outages. Don't use for Cloud Storage (GCS) buckets, Persistent Disk block storage, or NetApp Volumes.

Read: `library/cloud/google-cloud-filestore-autoscale/INSTRUCTIONS.md`

## google-cloud-filestore-log-troubleshooting
Diagnoses and resolves Filestore client mount failures on Google Cloud, permission errors (EACCES), and network timeouts (ETIMEDOUT). Use when an NFS mount hangs or fails from a Compute Engine VM, GKE pod, Cloud Run service, or Vertex AI workload, when `mount.nfs` reports "Connection timed out" or "access denied by server", when checking whether VPC ingress firewall rules or `nfsExportOptions` allow a client IP, or when a previously working Filestore share suddenly stops mounting after an administrative change. Don't use for Cloud Storage (GCS) buckets, Persistent Disk, or Cloud NetApp Volumes, and don't use for Filestore capacity scaling or backup and export-policy auditing.

Read: `library/cloud/google-cloud-filestore-log-troubleshooting/INSTRUCTIONS.md`

## google-cloud-filestore-nfs-browser
Inspects, searches, and reads files and POSIX metadata on Filestore (NFS) instances on Google Cloud without local NFS client packages or root privileges. Use when browsing Filestore shares, searching files, reading remote logs, or inspecting file attributes; don't use for Cloud Storage buckets, Cloud NetApp Volumes, Persistent Disks, or modifying/deleting files.

Read: `library/cloud/google-cloud-filestore-nfs-browser/INSTRUCTIONS.md`

## google-cloud-storage-basics
Stores, retrieves, and manages data as objects in Cloud Storage on Google Cloud (also known colloquially as GCS) buckets. Use when you need to interact with Cloud Storage — set up a Storage MCP server (remote or local Toolbox), create or configure buckets, upload, download, stream, or transfer data, organize objects with folders, generate signed URLs, control access (IAM, ACLs, public access prevention), set storage classes (Standard, Nearline, Coldline, Archive), manage lifecycle and cost, protect data (versioning, CMEK, retention, Bucket Lock, holds, soft delete), host static websites, trigger Pub/Sub notifications, mount buckets (gcsfuse), or optimize performance. Covers gcloud storage / gsutil, JSON/XML APIs, client libraries, Terraform, and Cloud Storage MCP servers. Don't use for generic MCP setup that doesn't mention Cloud Storage, other MCP servers, block storage (Persistent Disk), BigQuery, or databases (Cloud SQL, Spanner, Bigtable, Firestore).

Read: `library/cloud/google-cloud-storage-basics/INSTRUCTIONS.md`

## google-cloud-storage-bucket-architect
Creates Cloud Storage on Google Cloud (also known colloquially as GCS) buckets. Analyzes the workload (sensitive data, media hosting, ingestion, web hosting, archiving, backup, logging, analytics, AI/ML, or general-purpose), validates project-level security settings, and designs a secure-by-default, cost-effective configuration (location, storage class, uniform bucket-level access, public access prevention, soft delete, lifecycle) before creating it. Use whenever a user wants to create, make, set up, provision, or spin up a bucket, or needs object storage for an app, service, pipeline, or dataset — even a "simple" or "default" bucket, or when bucket creation is one step in a larger workflow. Outputs or executes the creation via gcloud, the JSON/REST API, Terraform, or SDK client libraries (C++, Java, Python, Go). Don't use for anything other than creating new buckets — for uploads, downloads, access changes, or reconfiguring existing buckets, use google-cloud-storage-basics.

Read: `library/cloud/google-cloud-storage-bucket-architect/INSTRUCTIONS.md`

## google-cloud-storage-fuse
Mounts Cloud Storage buckets on Google Cloud as a POSIX file system with Cloud Storage FUSE (gcsfuse). Use when interacting with gcsfuse or Cloud Storage FUSE mounts: decide whether FUSE, native gs:// reads, or Filestore/Managed Lustre fits a workload, deploy tuned mounts on GKE, Compute Engine, or Cloud Run, enable and size file, stat, and list caches, tune mount flags (--implicit-dirs) or config files, apply workload profiles, keep ML checkpointing safe (rename atomicity, hierarchical namespace/HNS, close-time finalization, concurrent writers), or diagnose slow training, low throughput, or bill spikes with gcsfuse metrics. Covers mount semantics, gcsfuse CLI and configs, GKE gcsfuse CSI driver (Workload Identity principal:// bindings, profile StorageClasses, sidecar sizing), and Cloud Run volume mounts. Don't use for bucket administration without a mount (google-cloud-storage-basics) or POSIX shared file systems (Filestore, Managed Lustre; use gke-storage).

Read: `library/cloud/google-cloud-storage-fuse/INSTRUCTIONS.md`
