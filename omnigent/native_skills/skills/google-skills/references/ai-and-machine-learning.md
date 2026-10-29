# ai-and-machine-learning

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## agent-platform-alert-configuration
Configures best-practice alerting policies for AI agents using OpenTelemetry (OTel) metrics, generating output as Terraform (.tf) configuration files. Use when analyzing, writing, or deploying alerting policies to monitor agent latency, error rates, token usage, and quality metrics. Don't use for standard infrastructure monitoring unrelated to AI agents, or when the agent is not instrumented with OpenTelemetry (for Reliability, Cost, Safety, Security alerts). NOTE: Reliability, Cost, Safety, and Security alerts use generic OTel metrics and work across runtimes (such as Cloud Run, Vertex AI). Quality alerts rely on Vertex AI Online Monitors and are strictly bound to Vertex AI deployments.

Read: `library/cloud/agent-platform-alert-configuration/INSTRUCTIONS.md`

## agent-platform-deploy
Deploy open models or custom weights from Model Garden to Agent Platform endpoints, check the status of an in-progress deployment operation, or clean up resources by undeploying models and deleting endpoints. Use when asked to actively deploy a model, list the Model Garden CATALOG of available models, check if a specific model is deployable (`gcloud ai model-garden models list-deployment-config`), query deployment cost, troubleshoot deployment errors (like quota limits), or undeploy/clean up endpoints. Also use when copying and deploying a 1P Tuned Model. Don't use for pure listing/discovery questions of the form "is X deployed?", "list my endpoints", or "which regions have models running?" — for those use `agent-platform-endpoint-management`. Don't use for running model evaluations (use `agent-platform-eval-flywheel` skill).

Read: `library/cloud/agent-platform-deploy/INSTRUCTIONS.md`

## agent-platform-endpoint-management
Manages Agent Platform serving endpoints. Use when you need to create, list, describe, update, or delete serving endpoints for model deployment on Agent Platform. Also use when troubleshooting endpoint permission, quota, or resource busy errors. Don't use for deploying models to endpoints or for running model evaluations.

Read: `library/cloud/agent-platform-endpoint-management/INSTRUCTIONS.md`

## agent-platform-eval-flywheel
Measures and improves the quality of AI models and agents on Google Cloud using the Eval Quality Flywheel methodology. Use when generating synthetic user scenarios, evaluating an agent or model, building an eval dataset, picking or writing evaluation metrics, analyzing failures, comparing results before and after a fix, or when guidance is needed on Agent Platform eval methodology — including dataset schema, LLM-as-judge scoring, and common failure causes. For fine-tuning, use agent-platform-tuning. For general production deployment, use agent-platform-deploy.

Read: `library/cloud/agent-platform-eval-flywheel/INSTRUCTIONS.md`

## agent-platform-inference
Connects to and performs inference with Google Cloud Agent Platform GenAI models, including First-Party Gemini models and Third-Party OpenMaaS models (Llama, DeepSeek, Qwen, etc.). Use when asked to perform inference, ask a model a question, run a test prompt, execute chat completions, or generate code for calling Gemini or OpenMaaS models, authenticate with GenAI SDK, OpenAI SDK, or legacy Agent Platform SDK, configure base URLs and global/regional endpoints, or troubleshoot 429 Resource Exhausted (DSQ), 400 User Validation, or 404 Not Found errors. Don't use for deploying models to endpoints or for running model evaluations.

Read: `library/cloud/agent-platform-inference/INSTRUCTIONS.md`

## agent-platform-migrate-from-ai-studio
Guides agents and users through migrating from Gemini API in Google AI Studio to Gemini Enterprise Agent Platform (formerly Vertex AI). Use this skill when moving applications to Google Cloud, to leverage Cloud credits, or to unify inferencing with other Cloud infrastructure (IAM, billing, telemetry).

Read: `library/cloud/agent-platform-migrate-from-ai-studio/INSTRUCTIONS.md`

## agent-platform-model-registry
Agent Platform Model Registry Management. Use when you need to upload, list, describe, update, or delete machine learning models (and their versions) in the Agent Platform Model Registry. Don't use for model training, model deployment to endpoints, or managing non-Agent Platform models.

Read: `library/cloud/agent-platform-model-registry/INSTRUCTIONS.md`

## agent-platform-prompt-management
Manages and orchestrates prompts in Agent Platform. Use when you need to create, list, retrieve, version, or delete managed prompts in Agent Platform. Don't use for model training, model deployment to endpoints, or managing non-Agent Platform prompts.

Read: `library/cloud/agent-platform-prompt-management/INSTRUCTIONS.md`

## agent-platform-rag-engine-management
Manage and query Agent Platform RAG Engine Corpora and retrieve grounded contexts using the Google GenAI SDK. Use when listing RAG corpora or files, inspecting a corpus, retrieving contexts, or generating content grounded in a RAG corpus. Do not use for standard database queries (use SQL/Spanner skills), Google Workspace RAG, or other RAG products like gRAG.

Read: `library/cloud/agent-platform-rag-engine-management/INSTRUCTIONS.md`

## agent-platform-skill-registry
Interact with the Gemini Enterprise Agent Platform Skill Registry to create and search for available skills. Use this skill to enable agents to register functionality or discover new capabilities.

Read: `library/cloud/agent-platform-skill-registry/INSTRUCTIONS.md`

## agent-platform-troubleshooting
Troubleshoots Google Cloud Gemini Enterprise Agent Platform issues (Agent Gateway, Registry, Identity, Policies, Model Armor, Identity-Aware Proxy (IAP)). Use when agent requests fail with 403 (especially unauthorized egress), Agent Runtime queries return 500, or gateway/IAP logs show permission errors. Don't use for general Google Cloud Identity and Access Management (IAM) debugging or networking issues unrelated to the Agent Platform stack.

Read: `library/cloud/agent-platform-troubleshooting/INSTRUCTIONS.md`

## agent-platform-tuning
Agent Platform Model Tuning. Use when you need to fine-tune open models or Gemini models using Agent Platform infrastructure. Don't use for model training outside Agent Platform, model deployment to endpoints (use `agent-platform-deploy`), or managing serving endpoints (use `agent-platform-endpoint-management`).

Read: `library/cloud/agent-platform-tuning/INSTRUCTIONS.md`

## agent-platform-tuning-management
Manages GenAI tuning jobs in Agent Platform. Use this to list, get, or cancel ongoing model tuning jobs. Don't use for fine-tuning models (use `agent-platform-tuning`), deploying models to endpoints (use `agent-platform-deploy`), or managing serving endpoints (use `agent-platform-endpoint-management`).

Read: `library/cloud/agent-platform-tuning-management/INSTRUCTIONS.md`

## api-gateway-mcp-server
Configures Google Cloud API Gateway to act as a remote Model Context Protocol (MCP) server (Public Preview) that exposes REST APIs as agent tools over HTTP (POST /mcp). Use when migrating OpenAPI 2.0 specs to OpenAPI 3.x for MCP, annotating specs with x-google-api-management.mcp and x-google-mcp-tool, securing tools/list with JWTs or API keys, connecting Google ADK (McpToolset) or Apigee API hub and Agent Registry, or troubleshooting MCP JSON-RPC errors (-32601, -32602, -32000). Do not use for Apigee X proxy bundles, outbound LLM model routing, or GKE Gateway API.

Read: `library/cloud/api-gateway-mcp-server/INSTRUCTIONS.md`

## apigee-agent-gateway-governance
Stands up an Apigee API proxy that a Google Cloud Agent Gateway calls as an ext-proc (Service Extension) callout on an agent's LLM traffic, to meter token usage per model, extract caller identity, and apply Model Armor prompt screening or a semantic cache. Use when wiring Apigee in as an AI gateway behind an Agent Gateway, when an agent's model egress needs governing, or when a callout proxy returns no verdict and you need to find out why. The distinguishing question is whether Apigee forwards the traffic or only inspects it: this skill is inspect-only, and builds the proxy itself. Don't use it when Apigee is meant to receive a request and route it onward to a backend — including hosting an MCP server behind Apigee — which needs a proxy with a target instead. Don't use for governing the agent's calls to tools or MCP servers. Don't use for choosing or switching which model a request goes to. Don't use for creating the Agent Gateway itself, nor for Apigee hybrid.

Read: `library/cloud/apigee-agent-gateway-governance/INSTRUCTIONS.md`

## bigquery-ai-ml
Leverages BigQuery's built-in machine learning and GenAI capabilities for advanced data analytics. Use when you need to write SQL queries that perform time-series forecasting, predict values, detect outliers or anomalies, find key drivers, perform semantic search or vector search, classify text, calculate similarity, summarize content, translate language, evaluate models, filter by semantic conditions, measure the causal effect of an intervention, compute correlations between columns, detect change points or structural breaks, extract trend or seasonality components, or leverage generative AI capabilities in BigQuery. Do not use for general BigQuery dataset, table, or job management requests.

Read: `library/cloud/bigquery-ai-ml/INSTRUCTIONS.md`

## developing-genkit-dart
Generates code and provides documentation for the Genkit Dart SDK. Use when the user asks to build AI agents in Dart, use Genkit flows, or integrate LLMs into Dart/Flutter applications.

Read: `library/cloud/developing-genkit-dart/INSTRUCTIONS.md`

## developing-genkit-go
Develop AI-powered applications using Genkit in Go. Use when the user asks to build AI features, agents, flows, or tools in Go using Genkit, or when working with Genkit Go code involving generation, prompts, streaming, tool calling, or model providers.

Read: `library/cloud/developing-genkit-go/INSTRUCTIONS.md`

## developing-genkit-js
Develop AI-powered applications using Genkit in Node.js/TypeScript. Use when the user asks about Genkit, AI agents, flows, or tools in JavaScript/TypeScript, or when encountering Genkit errors, validation issues, type errors, or API problems.

Read: `library/cloud/developing-genkit-js/INSTRUCTIONS.md`

## developing-genkit-python
Develop AI-powered applications using Genkit in Python. Use when the user asks about Genkit, AI agents, flows, or tools in Python, or when encountering Genkit errors, import issues, or API problems.

Read: `library/cloud/developing-genkit-python/INSTRUCTIONS.md`

## gemini-agents-api
Manages custom Agent resources on Gemini Enterprise Agent Platform. Use when the user wants to programmatically create, configure, list, update, or delete stateful, server-managed Agent resources (including mounting files, skills, and tools) before executing conversations.

Read: `library/cloud/gemini-agents-api/INSTRUCTIONS.md`

## gemini-api
Use when the user asks about using Gemini in an enterprise environment or explicitly mentions Vertex AI, Google Cloud, or Agent Platform. Guides the usage of the Gemini API on Agent Platform with the Google Gen AI SDK. Covers SDK usage (Python, JS/TS, Go, Java, C#), capabilities like multimodal inputs, tools, media generation, caching, batch prediction, and Live API.

Read: `library/cloud/gemini-api/INSTRUCTIONS.md`

## gemini-interactions-api
Guides the usage of Gemini Interactions API on Gemini Enterprise Agent Platform. Use when the user wants to use the stateful, server-managed Interactions API for multi-turn conversations, background execution, streaming, structured output, and function calling on the Agent Platform.

Read: `library/cloud/gemini-interactions-api/INSTRUCTIONS.md`

## gemini-live-api
Generates a Gemini LiveAPI client service class in the user's chosen programming language. Use when the user wants to build, scaffold, or integrate a client that connects to the Gemini Enterprise LiveAPI websocket endpoint, handles session setup/resumption, bearer token refresh, and sending/receiving `ClientMessage`/`ServerMessage` protos. Don't use for general (non-live, non-bidirectional) Gemini API usage such as one-shot `generateContent`, embeddings, image/video generation, or fine-tuning — use the `gemini-api` skill for those.

Read: `library/cloud/gemini-live-api/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-mxla-hang
Diagnose GKE Cloud TPU multi-slice training hangs (Megascale `HANG_DETECTED` logs and hang monitored events) using the ML Diagnostics `Megascale XLA (MXLA) Hang Analyzer` (`gcloud alpha mldiagnostics monitored-events`) and 1-minute Cloud Monitoring multi-slice latency metrics (`kubernetes.io/container/multislice/*`). Distinguishes XLA compiler/HLO launch divergence and host data-input stalls from TPU chip, SparseCore, ICI, or network fabric faults. Use when multi-slice TPU training jobs freeze without progressing steps, emit `HANG_DETECTED`, or stall in collective operations. Don't use for gradual step-time throughput drops without hangs (use gke-ai-troubleshooting-tpu-performance-degradation) or pod preemption/eviction restarts (use gke-ai-troubleshooting-jobset-interruption).

Read: `library/cloud/gke-ai-troubleshooting-tpu-mxla-hang/INSTRUCTIONS.md`

## gke-ai-troubleshooting-tpu-performance-degradation
Diagnose GKE Cloud TPU training throughput drops and step-time regressions (15%+ TPU duty-cycle drop) using ML Diagnostics Workload Monitoring (`gcloud alpha mldiagnostics monitored-events` / `hypercomputecluster.googleapis.com/v1alpha`) and 1-minute Cloud Monitoring system metrics (`kubernetes.io/node/accelerator/*`). Distinguishes hardware and network fabric throttling from workload resource bottlenecks (HBM capacity, host memory, or host CPU saturation). Use when TPU training throughput or duty cycle drops without crashing pods, when `PERFORMANCE_DEGRADATION` monitored events fire, or when triaging slow multi-slice training steps. Don't use for complete multi-slice XLA execution stalls with `HANG_DETECTED` logs (use gke-ai-troubleshooting-tpu-mxla-hang) or pod eviction/interruption restarts (use gke-ai-troubleshooting-jobset-interruption).

Read: `library/cloud/gke-ai-troubleshooting-tpu-performance-degradation/INSTRUCTIONS.md`
