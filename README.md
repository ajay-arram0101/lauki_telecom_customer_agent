# Lauki Telecom Customer Support Agent

An AI-powered customer support agent for **Lauki Phones** (a fictional telecom provider), built with LangGraph and deployed on AWS Bedrock AgentCore with short-term and long-term memory capabilities.

## Live Demo

**[Try the Agent →](http://quaki-fe-125975759762-quaki-support.s3-website.us-east-2.amazonaws.com/)**

##  Project Overview

This project demonstrates an end-to-end AI customer support solution that:

- **Answers telecom FAQs** — Plans, billing, SIM activation, roaming, 5G, porting, and more
- **Remembers context** — Uses Bedrock AgentCore's STM (Short-Term Memory) and LTM (Long-Term Memory) for personalized, context-aware conversations
- **Low latency responses** — Optimized for 2-7 second response times using OpenAI's `gpt-4o-mini`
- **Semantic search** — Finds the most relevant FAQ answer using embedding-based similarity matching

### Why This Matters

Traditional rule-based chatbots fail when customers ask questions in unexpected ways. This agent uses semantic understanding to match customer queries to the right answers, even when phrasing differs from the original FAQ. The memory layer enables multi-turn conversations where the agent remembers previous interactions.

##  Dataset

The agent is powered by `lauki_qna.csv` — a curated FAQ dataset containing **76 question-answer pairs** covering typical telecom customer inquiries:

| Category | Topics Covered |
|----------|---------------|
| **Plans & Pricing** | Prepaid, postpaid, family, enterprise, data-only plans |
| **SIM & Activation** | New SIM activation, eSIM, SIM replacement, KYC |
| **Billing** | Payment methods, billing cycles, itemized usage |
| **Data & Usage** | Balance checks, throttling, data sharing, upgrades |
| **Roaming** | International packs, activation, regional coverage |
| **Network** | 5G availability, VoLTE, WiFi Calling, network bands |
| **Porting** | Number transfer from other carriers |
| **Support** | Network issue reporting, address changes, corporate discounts |

Each FAQ entry includes detailed, technically accurate answers simulating real telecom support documentation.

##  Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   S3 Frontend   │────▶│  Lambda + API GW │────▶│  Bedrock AgentCore  │
│   (Static UI)   │     │    (Proxy)       │     │    Runtime          │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────────┐
                                                 │   LangGraph Agent   │
                                                 │   + FAQ Search Tool │
                                                 │   + STM/LTM Memory  │
                                                 └─────────────────────┘
```

##  Tech Stack

- **Agent Framework**: LangGraph
- **LLM**: OpenAI `gpt-4o-mini`
- **Embeddings**: `text-embedding-3-small`
- **Runtime**: AWS Bedrock AgentCore
- **Memory**: AgentCore STM + LTM
- **Frontend**: HTML/CSS/JS hosted on S3
- **Infrastructure**: Lambda, API Gateway, ECR, CodeBuild

##  Project Structure

```
├── 02_agentcore_memory.py   # Main agent code (deployed)
├── lauki_qna.csv            # FAQ dataset
├── Dockerfile               # Container configuration
├── buildspec.yml            # CodeBuild spec
├── pyproject.toml           # Python dependencies
└── serverless-ui/           # Frontend and Lambda handlers
    ├── frontend/            # Static web UI
    └── lambda/              # API proxy handlers
```

##  Getting Started

1. Clone the repository
2. Copy `.sample_env` to `.env` and add your API keys
3. Install dependencies: `uv sync`
4. Run locally: `python 02_agentcore_memory.py`


