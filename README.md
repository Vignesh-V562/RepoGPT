# RepoGPT 🤖 - Heavy-Duty Codebase Intelligence

[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/AI-Gemini%202.0%20Flash-blue?style=flat-square&logo=google-gemini)](https://deepmind.google/technologies/gemini/)
[![Groq](https://img.shields.io/badge/AI-Groq%20Llama%203.3-orange?style=flat-square&logo=groq)](https://groq.com/)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?style=flat-square&logo=supabase)](https://supabase.com/)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind%204-06B6D4?style=flat-square&logo=tailwindcss)](https://tailwindcss.com/)

**RepoGPT** is a production-grade RAG (Retrieval-Augmented Generation) and Multi-Agent Research application designed for deep codebase analysis. It enables users to ingest entire GitHub repositories, generate hierarchical summaries, and perform complex technical research using a specialized swarm of AI agents.

---

## 🚀 Key Features

- **🔍 Smart Repository Ingestion**: Clones and parses repositories using **Tree-sitter AST-based chunking** for high-precision code context.
- **🧠 Intelligent RAG Pipeline**: A dual-stage retrieval system utilizing file-level summaries and granular code blocks. Now features **Intent Detection** for instant replies to general questions.
- **🤖 Multi-Agent Research Swarm**: A sophisticated planning-executor architecture with:
  - **Planner Agent**: Decomposes queries into actionable roadmaps.
  - **Research Agent**: Utilizes Tavily, ArXiv, and GitHub Search tools.
  - **Writer/Editor Agents**: Drafts professional technical blueprints.
  - **Critique Agent**: Validates output quality via feedback loops.
- **⚡ Multi-Model Intelligence**: Seamlessly switches between **Gemini 2.0 Flash** for massive context and **Groq (Llama 3.3/3.1)** for lightning-fast analysis.
- **📡 Live Status Updates**: Real-time execution tracking in Architect mode—see exactly what the agents are doing (e.g., "🔍 Researching...", "✍️ Writing...").
- **🎨 Modern UI/UX**: Sleek Next.js 16 dashboard with Tailwind 4 and Framer Motion.

---

## 🏗️ System Architecture

### Multi-Agent Interaction Flow
```mermaid
graph TD
    User([User Prompt]) --> Planner[Planner Agent]
    Planner -->|Detailed Roadmap| Steps[Research/Draft/Review]
    Steps --> Executor[Research Agent]
    Executor -->|Tool Interactions| Tools[GitHub/Tavily/ArXiv/Wiki]
    Tools --> Executor
    Executor --> Writer[Writer Agent]
    Writer --> Editor[Editor Agent]
    Editor --> Critic[Critique Agent]
    Critic -->|Feedback Loop| Executor
    Critic -->|Final Verified Result| Result([Professional Report])
    
    style User fill:#f9f,stroke:#333,stroke-width:2px
    style Result fill:#00ff0022,stroke:#333,stroke-width:2px
```

### Hierarchical RAG Pipeline
```mermaid
graph LR
    Repo[GitHub Repo] --> Ingest[Ingestion Service]
    Ingest --> AST[AST-based Chunking]
    Ingest --> Sum[LLM Summarization]
    AST --> VectorDB[(Supabase Vector)]
    Sum --> VectorDB
    Query[User Query] --> Stage1[Stage 1: File Retrieval]
    Stage1 --> Stage2[Stage 2: Code Retrieval]
    Stage2 --> Rerank[Cross-Encoder Reranking]
    Rerank --> Gen[Gemini 2.0 Flash]
```

---

## 🛠️ Tech Stack

### Frontend
- **Framework**: Next.js 16 (App Router)
- **Styling**: Tailwind CSS 4 (+ PostCSS)
- **Animations**: Framer Motion
- **Icons**: Lucide React
- **Syntax Highlighting**: React Syntax Highlighter

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **AI Engine**: Google GenAI (Gemini 2.0 Flash) & Groq (Llama 3.3)
- **Orchestration**: Custom Multi-Agent Framework
- **Tools**: Tavily, ArXiv, Wikipedia, GitHub API
- **NLP**: Hybrid search (Vector + Keyword) + Cross-Encoder Reranking
- **Database**: Supabase (PostgreSQL + pgvector)
- **Parsing**: Tree-sitter (AST-aware chunking)

---

## ⚙️ Getting Started

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- Supabase Account (with Vector enabled)
- Google AI (Gemini) API Key

### 2. Backend Setup
```bash
cd server
# Install dependencies
pip install -r requirements.txt

# Configure Environment
cp .env.example .env
# Edit .env with your credentials:
# GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, TAVILY_API_KEY

# Start Server
uvicorn main:app --reload
```

### 3. Frontend Setup
```bash
cd client
# Install dependencies
npm install

# Configure Environment
cp .env.example .env.local
# Edit .env.local with Supabase credentials

# Start Development Server
npm run dev
```

---

## 📂 Project Structure

```bash
RepoGPT/
├── client/           # Next.js Frontend (React + Tailwind 4)
│   ├── src/          # Components, Hooks, and App Logic
│   └── public/       # Static Assets
├── server/           # FastAPI Backend (Python)
│   ├── app/          # Core RAG & Ingestion Services
│   ├── src/          # Multi-agent Architecture (Research, Planning)
│   ├── prompts/      # Agent System Instructions
│   └── database/     # Schema and Migrations
└── README.md         # Global Documentation
```

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

<p align="center">
  Built with ❤️ for the Next Generation of Developers
</p>
