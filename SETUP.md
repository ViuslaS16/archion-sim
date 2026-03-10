# Archion Sim — Clean Migration & Commit Guide

Because your current codebase was generated organically ("vibe coded") and you want to establish a clean, professional GitHub repository from scratch, you should follow this step-by-step guide. 

This guide walks you through creating a **brand new folder**, setting up the exact directory structure, copy-pasting your code into it logically, and committing it in structured, professional phases.

---

## Phase 1: Initialize New Repository & Folder Structure

Start by creating a completely empty repository on your computer.

```bash
# 1. Create a fresh directory outside of your messy project
mkdir archion-sim-clean
cd archion-sim-clean

# 2. Initialize a blank Git repository
git init

# 3. Recreate the entire folder structure
# Backend
mkdir -p backend/core
mkdir -p backend/sim/data
mkdir -p backend/tests
mkdir -p backend/uploads
mkdir -p backend/reports

# Frontend
mkdir -p frontend/src/app
mkdir -p frontend/src/components
mkdir -p frontend/src/hooks
mkdir -p frontend/src/lib
mkdir -p frontend/src/types
mkdir -p frontend/public

# Misc
mkdir -p images
```

### Commit 1: Project Skeleton & Documentation

**Action:** Copy the following documentation and configuration files from your old project into this new folder:
- `.gitignore` (Make sure to copy the exact contents of your old `.gitignore` so you don't track `node_modules` or `.venv`)
- `README.md`
- `DOCUMENTATION.md`
- `SETUP.md`
- Any placeholder images into the `images/` folder.

```bash
git add .gitignore README.md DOCUMENTATION.md SETUP.md images/
git commit -m "docs: Initialize empty repository with folder skeleton and core documentation"
```

---

## Phase 2: Setup the Backend Foundation

**Action:** Navigate to your **old** project and copy the essential backend routing, schema, and dependency files into the new `backend/` folder.

Files to copy over:
- `backend/main.py`
- `backend/schemas.py`
- `backend/core/__init__.py`
- `backend/sim/__init__.py`
- `backend/tests/__init__.py`

_Wait! Don't commit everything yet. We will configure the backend virtual environment first so it won't be committed._

```bash
# Setup Python Environment
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows

# Install Dependencies (this won't be committed because of .gitignore)
pip install fastapi==0.123.8 uvicorn==0.38.0 python-multipart==0.0.20 pydantic==2.12.5 python-dotenv==1.2.1 shapely==2.1.2 trimesh==4.11.1 numpy==2.4.2 scipy==1.17.0 networkx==3.6.1 pillow==12.1.0 google-genai==1.64.0 reportlab matplotlib

# Create .env (this won't be committed)
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
cd ..
```

### Commit 2: Backend API Shell
```bash
git add backend/
# Make sure .venv and .env are NOT staged (check with 'git status')
git commit -m "feat(backend): Setup FastAPI shell, dependency env, and API schemas"
```

---

## Phase 3: Add Backend Core Logic

**Action:** Copy the heavily unorganized algorithm logic from your old project into the newly structured `backend/core/` and `backend/sim/` directories.

Copy these exact files:
- `backend/core/geometry.py`
- `backend/core/spatial_analyzer.py`
- `backend/sim/engine.py`
- `backend/sim/data/trajectories.json`
- `backend/core/compliance.py`
- `backend/core/validator.py`
- `backend/core/parameter_extractor.py`
- `backend/core/regulations.json`
- `backend/core/analytics.py`
- `backend/core/chart_generator.py`
- `backend/core/navigation.py`
- `backend/core/ai_consultant.py`
- `backend/core/knowledge_base.py`
- `backend/core/report_gen.py`

### Commit 3: Backend Business Logic
```bash
git add backend/core/ backend/sim/
git commit -m "feat(backend): Implement geometry extraction, simulation engine, AI consultant, and reporting logic"
```

---

## Phase 4: Setup the Frontend Foundation

**Action:** Copy all the Next.js and configuration baseline files from your old `frontend/` to the new `frontend/`.

Files to copy:
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.json`
- `frontend/next.config.ts`
- `frontend/eslint.config.mjs`
- `frontend/postcss.config.mjs`
- `frontend/next-env.d.ts`
- `frontend/README.md`
- `frontend/public/` (all SVG icons)
- `frontend/.gitignore`

```bash
# Install NPM modules securely (these won't be committed)
cd frontend
npm ci  # Uses the exact versions from package-lock.json
cd ..
```

### Commit 4: Next.js Configuration
```bash
git add frontend/
git commit -m "chore(frontend): Initialize Next.js configs, Tailwind setup, and dependencies"
```

---

## Phase 5: Add Frontend Components & Pages

**Action:** Copy all source code for the Web UI from your old `frontend/src/` into the new `frontend/src/`.

Files to copy:
- `frontend/src/app/globals.css`
- `frontend/src/app/favicon.ico`
- `frontend/src/types/` (e.g., `simulation.ts`)
- `frontend/src/hooks/` (e.g., `usePlayback.ts`)
- `frontend/src/lib/` (e.g., `theme.ts`)
- `frontend/src/components/Providers.tsx`, `ErrorBoundary.tsx`
- `frontend/src/components/ModelUpload.tsx`
- `frontend/src/components/ModelRenderer.tsx`
- `frontend/src/components/SimViewer.tsx`
- `frontend/src/components/AnalyticsDashboard.tsx`
- `frontend/src/components/ViolationMonitor.tsx`
- `frontend/src/components/Controls.tsx`
- `frontend/src/app/page.tsx`

### Commit 5: Frontend UI & 3D Viewer Integration
```bash
git add frontend/src/
git commit -m "feat(frontend): Implement React Three Fiber 3D simulation viewer, UI dashboards, and main application page"
```

---

## Phase 6: Push to GitHub

Your project is now completely clean, structured efficiently, and has a highly professional git history that isolates documentation, backend shell, backend logic, frontend shell, and frontend logic.

```bash
# Set your branch name
git branch -M main

# Add the repository URL you created on GitHub
git remote add origin https://github.com/YOUR_USERNAME/archion-sim.git

# Push everything!
git push -u origin main
```
