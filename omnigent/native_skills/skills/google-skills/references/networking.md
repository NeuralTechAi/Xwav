# networking

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## cloud-network-insights
Guides and automates setup, onboarding, and synthetic monitoring operations for Cloud Network Insights in Google Cloud and Broadcom AppNeta. Use when enabling Cloud Network Insights, deploying or troubleshooting Monitoring Points across cloud and on-premises environments, configuring Network or Web monitoring policies and AppNeta alarm rules, configuring alert policies, querying path alarms and performance metrics, or verifying synthetic path reachability. Don't use for generic network observability, VPC Flow Logs, Cloud NAT, or VPC firewall debugging.

Read: `library/cloud/cloud-network-insights/INSTRUCTIONS.md`

## gke-networking
Plans, configures, and manages core GKE cluster networking. Covers private clusters, VPC-native configurations, DNS, node egress, Dataplane V2, and IP planning. Use when designing GKE networking layouts, configuring private clusters, setting up Dataplane V2, planning GKE IP ranges, or managing VPC- native cluster modes. Don't use for application ingress, load balancing, or service networking (use gke-service-networking instead).

Read: `library/cloud/gke-networking/INSTRUCTIONS.md`

## gke-service-networking
Configures GKE edge networking, traffic routing, load balancing, and private service endpoints. Use when configuring Gateway API manifests, standard Ingress, Cloud Armor WAF security policies, Container-Native Load Balancing (NEGs), Private Service Connect (PSC), or Google-managed SSL certificates on GKE, and to troubleshoot Ingress and load-balancer 502/5xx errors, backend health-check failures, connection draining, and TLS/SSL policy enforcement. Don't use for core cluster IP planning, Dataplane V2 network policies, or node NAT egress (use gke-networking instead).

Read: `library/cloud/gke-service-networking/INSTRUCTIONS.md`

## google-cloud-global-frontend-configuration
Guides agents through a 6-step discovery process to design and deploy Google Cloud global external Application Load Balancers with Cloud CDN, Cloud Armor, and Service Extensions, mapping workload requirements to best-practice configurations. Use when: - Designing, configuring, or deploying a Google Cloud global external Application Load Balancer, Cloud CDN, Cloud Armor WAF, or Service Extensions. - Discovering existing Google Cloud resources (Cloud Storage, MIGs, GKE, Cloud Run) to use as backends. - Generating production-grade Terraform HCL or gcloud CLI scripts for global external Application Load Balancers. - Actuating deployments via Infrastructure Manager or bash scripts, including IAM pre-checks. - Detecting, analyzing, or reconciling configuration drift on deployed global external Application Load Balancers. Don't use for: - Non-Google Cloud load balancing or security configurations. - Purely regional or internal load balancing setups (unless part of a hybrid/failover global design).

Read: `library/cloud/google-cloud-global-frontend-configuration/INSTRUCTIONS.md`
