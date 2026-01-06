# RepoGPT 🤖 - Heavy-Duty Codebase Intelligence

[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/AI-Gemini%202.0%20Flash-blue?style=flat-square&logo=google-gemini)](https://deepmind.google/technologies/gemini/)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?style=flat-square&logo=supabase)](https://supabase.com/)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind%204-06B6D4?style=flat-square&logo=tailwindcss)](https://tailwindcss.com/)

**RepoGPT** is a production-grade RAG (Retrieval-Augmented Generation) and Multi-Agent Research application designed for deep codebase analysis. It enables users to ingest entire GitHub repositories, generate hierarchical summaries, and perform complex technical research using a specialized swarm of AI agents.

---

## 🚀 Key Features

- **🔍 Smart Repository Ingestion**: Clones and parses repositories using **Tree-sitter AST-based chunking** for high-precision code context.
- **🧠 Hierarchical RAG Pipeline**: A dual-stage retrieval system that utilizes file-level summaries and granular code blocks for superior accuracy.
- **🤖 Multi-Agent Research Swarm**: A sophisticated planning-executor architecture featuring:
  - **Planner Agent**: Decomposes complex queries into actionable research steps.
  - **Research Agent**: Utilizes tools like Tavily, ArXiv, and GitHub Search.
  - **Writer & Editor Agents**: Drafts and refines comprehensive technical reports.
  - **Critique Agent**: Validates output quality and ensures technical depth.
- **⚡ Optimized for Gemini 2.0**: Grounded in Google's latest Gemini 2.0 Flash for lightning-fast reasoning and massive context windows.
- **🎨 Modern UI/UX**: A sleek, responsive dashboard built with **Next.js 16**, **Tailwind CSS 4**, and **Framer Motion**.

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
- **AI Engine**: Google GenAI (Gemini 2.0 Flash)
- **Orchestration**: Custom Multi-Agent Framework
- **Tools**: Tavily, ArXiv, Wikipedia API, GitPython
- **Database**: Supabase (PostgreSQL + pgvector)
- **Parsing**: Tree-sitter (for AST-aware chunking)

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
