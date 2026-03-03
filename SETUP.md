# Archion Sim — Setup Guide

Complete commands to clone, set up, and run the project from scratch.

---

## 1. Clone the Repository

```bash
git clone https://github.com/ViuslaS16/archion-sim.git
cd archion-sim
```

---

## 2. Folder Structure

```
archion-sim/
├── backend/
│   ├── core/
│   │   ├── ai_consultant.py
│   │   ├── analytics.py
│   │   ├── chart_generator.py
│   │   ├── compliance.py
│   │   ├── geometry.py
│   │   ├── knowledge_base.py
│   │   ├── navigation.py
│   │   ├── parameter_extractor.py
│   │   ├── regulations.json
│   │   ├── report_gen.py
│   │   ├── spatial_analyzer.py
│   │   └── validator.py
│   ├── sim/
│   │   ├── engine.py
│   │   └── data/
│   ├── tests/
│   ├── main.py
│   └── schemas.py
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   ├── public/
│   ├── package.json
│   └── tsconfig.json
├── images/
├── .gitignore
├── AI_RECOMMENDATION_ENGINE.md
├── DOCUMENTATION.md
└── SETUP.md
```

---

## 3. Backend Setup (Python / FastAPI)

### 3.1 Prerequisites
- Python 3.10 or higher
- pip3

### 3.2 Create required directories

```bash
mkdir -p backend/uploads
mkdir -p backend/reports
mkdir -p backend/sim/data
```

### 3.3 Install Python dependencies

```bash
pip3 install fastapi==0.123.8
pip3 install uvicorn==0.38.0
pip3 install python-multipart==0.0.20
pip3 install pydantic==2.12.5
pip3 install python-dotenv==1.2.1
pip3 install shapely==2.1.2
pip3 install trimesh==4.11.1
pip3 install numpy==2.4.2
pip3 install scipy==1.17.0
pip3 install networkx==3.6.1
pip3 install pillow==12.1.0
pip3 install google-genai==1.64.0
```

Or install everything in one command:

```bash
pip3 install fastapi==0.123.8 uvicorn==0.38.0 python-multipart==0.0.20 pydantic==2.12.5 python-dotenv==1.2.1 shapely==2.1.2 trimesh==4.11.1 numpy==2.4.2 scipy==1.17.0 networkx==3.6.1 pillow==12.1.0 google-genai==1.64.0
```

### 3.4 Create the environment file

```bash
touch backend/.env
```

Add the following to `backend/.env`:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

> Get a free API key from: https://aistudio.google.com/apikey

### 3.5 Start the backend server

```bash
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be running at: **http://localhost:8000**

---

## 4. Frontend Setup (Next.js / React)

### 4.1 Prerequisites
- Node.js 18 or higher
- npm (comes with Node.js)

### 4.2 Install Node.js dependencies

```bash
cd frontend
npm install
```

### 4.3 Start the frontend dev server

```bash
npm run dev
```

The frontend will be running at: **http://localhost:3000**

---

## 5. Run Both Servers (Quick Start)

Open two terminal windows:

**Terminal 1 — Backend:**
```bash
cd archion-sim/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd archion-sim/frontend
npm run dev
```

Then open **http://localhost:3000** in your browser.

---

## 6. Verify Everything is Working

Check backend health:
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{"status": "ok", "service": "archion-sim-backend"}
```

---

## 7. Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend Framework | Next.js 16 + React 19 |
| 3D Rendering | React Three Fiber + Three.js |
| Animations | Framer Motion + GSAP |
| UI Components | Tailwind CSS + Lucide React |
| Charts | Recharts |
| Backend Framework | FastAPI + Uvicorn |
| 3D Model Processing | Trimesh |
| Geometry / Spatial | Shapely + NumPy + SciPy |
| AI Recommendations | Google Gemini 2.5 Flash |
| Graph / Pathfinding | NetworkX |
