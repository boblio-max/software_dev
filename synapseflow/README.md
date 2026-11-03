# SynapseFlow: AI-Adaptive Scaffolding Learning Platform

## Problem Statement

Learners consume educational content but struggle to apply knowledge to open-ended problems. No adaptive system provides the right scaffolding at the right moment, fading away as competence grows.

## Solution

AI-driven adaptive scaffolding that teaches through progressive fading support:

1. **Dynamic Scaffolding** — Socratic hints, maximally helpful but minimally revealing
2. **Knowledge Graph Navigation** — Skills unlock based on demonstrated mastery
3. **Adaptive Hint Fading** — Support decreases automatically as competence increases
4. **Collaborative Peer Review** — Practice professional feedback skills

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, Tailwind CSS 3, Monaco |
| Backend | FastAPI (Python 3.11+), SQLAlchemy |
| AI Engine | OpenAI-compatible LLM (configurable) |
| Database | PostgreSQL or SQLite (auto-detects) |
| Real-time | WebSockets |

## Quick Start

Backend:

```bash
cd synapseflow/backend
cp .env.example .env  # optional
pip install -r requirements.txt
python seed.py  # loads starter skills/tasks/users
uvicorn app.main:app --reload
```

Frontend:

```bash
cd synapseflow/frontend
npm install
npm run dev
```

Tests:

```bash
cd synapseflow/backend
python -m pytest -q
cd ../frontend
npm run type-check && npm run build
```

## Architecture Notes

- Learner code is executed in an isolated subprocess with a hard timeout (`app/core/sandbox.py`).
- Skill prerequisites are modeled as a DAG (`app/ai/knowledge_graph.py`).
- Scaffolding hints never contain solution code and are generated from a `CognitiveState` (`app/ai/scaffold_engine.py`).
- Peer matching blends complementary mastery with reviewer quality (`app/ai/pairing.py`).

## Recent Improvements (v1.1)

- Subprocess sandbox with real per-test grading (stdin/expected output).
- FastAPI lifespan startup, SQLite-by-default for zero-config local development.
- Idempotent, environment-driven database seeding.
- Frontend dependency repair and production build verification.
- Expanded backend and API test coverage.

## Demo Credentials (after seeding)

- `student / password123`
- `admin / admin123`