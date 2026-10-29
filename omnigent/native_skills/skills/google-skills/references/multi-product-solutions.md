# multi-product-solutions

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## google-cloud-solution-agentic-ai-bidirectional-streaming
Guides agents to interactively discover customer requirements for live, bidirectional multi-agent AI systems that process continuous streams of multimodal data for real-time technical guidance and safety monitoring. Generates a custom Google Cloud solution that uses opinionated best practices and architecture guidance. Use when users need agentic assistance to design and create a multi-product solution in the cloud for live bidirectional multimodal streaming workloads. Don't use for simple text-based chat applications or workloads without real-time streaming requirements.

Read: `library/cloud/google-cloud-solution-agentic-ai-bidirectional-streaming/INSTRUCTIONS.md`

## google-cloud-solution-agentic-ai-borderless-data-lakehouse
Discovers requirements and designs a borderless open data lakehouse using Lakehouse for Apache Iceberg and BigQuery data agents. Use when architecting multi-cloud storage infrastructure (Cloud Storage, AWS S3, Azure Blob), establishing ingestion and AI serving subsystems, configuring Cross-Cloud Interconnect, or deploying Gemini Enterprise Agent Platform and BigQuery data agents. Don't use for single-cloud data warehouses, or when the focus is on Knowledge Catalog metadata governance and Spark-driven IDE analytics workflows (use google-cloud-solution-agentic-analytics-spark-knowledge-catalog instead).

Read: `library/cloud/google-cloud-solution-agentic-ai-borderless-data-lakehouse/INSTRUCTIONS.md`

## google-cloud-solution-agentic-ai-data-science-workflow
Designs a tailored multi-product agentic data science architecture on Google Cloud that incorporates opinionated best practices. Use when architecting multi-product solutions for agent-based data analytics or ML workloads. Don't use for simple queries, non-agentic pipelines, general cloud reviews, or writing agent code.

Read: `library/cloud/google-cloud-solution-agentic-ai-data-science-workflow/INSTRUCTIONS.md`

## google-cloud-solution-agentic-analytics-spark-knowledge-catalog
Discovers requirements and designs an end-to-end governed agentic analytics solution using Knowledge Catalog and Managed Service for Apache Spark (Lightning Engine). Use when designing data science and analytics workflows across structured and unstructured distributed data (including in S3, Azure Blob, AlloyDB, and Iceberg), establishing metadata governance with Knowledge Catalog aspect types, or grounding agentic IDEs (VS Code, Antigravity) by using the Google Cloud Data Agent Kit. Don't use for provisioning borderless data lakehouse infrastructure (use google-cloud-solution-agentic-ai-borderless-data-lakehouse instead).

Read: `library/cloud/google-cloud-solution-agentic-analytics-spark-knowledge-catalog/INSTRUCTIONS.md`

## google-cloud-solution-architecture
Interactively discovers requirements and designs holistic, multi-product system architectures, solution blueprints, and deployment recommendations for complex workloads on Google Cloud. Use when designing end-to-end cloud solutions, selecting and integrating Google Cloud services, generating architecture diagrams, or conducting requirements discovery for new cloud workloads or migrations. Don't use for single-product tasks (use product-specific skills), initial onboarding or authentication (use google-cloud-recipe-*), Well-Architected Framework reviews or audits (use google-cloud-waf-*), or workloads covered by specialized solution skills.

Read: `library/cloud/google-cloud-solution-architecture/INSTRUCTIONS.md`

## google-cloud-solution-build-deploy-agents
Designs, builds, and deploys AI agents or multi-agent systems on Google Cloud. Provides an interactive workflow to gather requirements, recommend a tailored architecture, and generate deployment instructions. Use when designing or implementing agentic systems on Google Cloud. Don't use for general Google Cloud solution architecture (use google-cloud-solution-architecture instead) or for narrow tasks targeting a single product without agent context.

Read: `library/cloud/google-cloud-solution-build-deploy-agents/INSTRUCTIONS.md`

## google-cloud-solution-guided-gke-ai-migration
Guides the migration of existing AI workloads (Cloud Run, Gemini API, Gemini Enterprise Agent Platform) to self-hosted GKE inference using gcloud and kubectl. Use when the user has an existing AI inference workload (on Cloud Run, the Gemini API, Gemini Enterprise Agent Platform, or a custom VM) and wants to move it to self-hosted inference on GKE, or asks follow-up questions during such a migration (hardware sizing, model staging, manifest generation, validation, traffic cutover). DO NOT use for brand new GKE inference deployments with no existing workload to migrate (use gke-inference instead). DO NOT use if the user intends to automate the migration via the Gemini Cloud Assist MCP server.

Read: `library/cloud/google-cloud-solution-guided-gke-ai-migration/INSTRUCTIONS.md`

## google-cloud-solution-hybrid-search-alloydb
Discovers requirements and generates architectural, design, and deployment guidance for dynamic hybrid search systems by combining semantic search and keyword search. Optimized for AlloyDB hybrid search use cases in Google Cloud. Use when users need vector search combined with structured SQL filtering, faceted attributes, semantic reranking, in-database AI validation, or serverless hosting across transactional relational databases, analytical data warehouses, or managed database engines. DON'T use this skill for simple keyword-only search, or when a standalone non-relational vector database is required.

Read: `library/cloud/google-cloud-solution-hybrid-search-alloydb/INSTRUCTIONS.md`

## google-cloud-solution-multi-agent-security
Designs, deploys, and secures Google Cloud Agent Gateway solutions. Use when the user needs to configure multi-agent security, ingress (CLIENT_TO_AGENT), or egress (AGENT_TO_ANYWHERE) patterns involving Model Armor, IAP, and Agent Registry. Don't use for general Cloud Load Balancing or basic VPC setup not related to Agent Gateways.

Read: `library/cloud/google-cloud-solution-multi-agent-security/INSTRUCTIONS.md`

## google-cloud-solution-n-tier-serverless-web-app
Assists in designing and implementing secure n-tier serverless web applications and microservices on Google Cloud. Use when users need architecture designs, security checklists, Terraform code, or deployment guidance for multi-tier serverless apps, regional data residency / European sovereignty compliance, zero-trust private VPC networking, or Private Service Connect. Don't use for VM, GKE, or non-Google Cloud architectures.

Read: `library/cloud/google-cloud-solution-n-tier-serverless-web-app/INSTRUCTIONS.md`

## google-cloud-solution-rag-enterprise-search-gke-sqldb
Discovers requirements, and generates architectural, design, and deployment guidance for a retrieval-augmented generation (RAG)-capable enterprise search system in Google Cloud. Use when users need a vector-enabled SQL database as the store and index for the embedding vectors, an open model and open-source inferencing framework, and Kubernetes containers to host all the application components. DON'T use this skill for fully-managed RAG, or SaaS search services, or when a non-SQL vector database is required.

Read: `library/cloud/google-cloud-solution-rag-enterprise-search-gke-sqldb/INSTRUCTIONS.md`

## finding-google-skills
Google platform decision and setup guidance, loaded on demand from Google's skill catalog. Use when a developer is choosing or setting up part of their stack, such as where to run a service, a database, storage, messaging, authentication, analytics, ads, or AI model serving, and a Google product is a reasonable candidate - whether or not a vendor is named - or when a request names a Google product or API. Brings in the matching Google skill so the answer can weigh Google options, their trade-offs, and when they are not the right fit. Skip when the stack is already settled on another provider and no Google product is named, or the task involves no platform choice.

Read: `library/developers/finding-google-skills/INSTRUCTIONS.md`
