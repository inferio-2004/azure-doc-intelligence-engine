
# rasa_pdf_app_starter

## Overview
Monorepo combining a Rasa-based backend for conversational PDF interactions and an Azure-powered document-intelligence server.  
The Rasa backend handles NLU, dialogue flows, and connectors for chat interfaces. The Azure server provides TOC extraction, chart/graph analytics (Azure OpenAI Vision), and spreadsheet parsing (Azure Form Recognizer). Designed for modular deployment and easy integration into BI or chatbot pipelines.

---

## Key Features
- **Rasa conversational backend** for intent classification, entity extraction, and dialogue management.  
- **TOC extraction** from PDFs (server) to produce structured navigation metadata.  
- **Graph analytics** using Azure OpenAI Vision to extract axes, legends, values, and trends from charts.  
- **Spreadsheet parsing** via Azure Form Recognizer/Form Intelligence to convert XLS/XLSX into structured JSON.  
- **Hybrid retrieval options** (if enabled) to augment Rasa responses with document context.  
- **Modular APIs**: independent services for Rasa and Azure document processing.

---

## Tech Stack
- **Conversational**: Rasa (Rasa Open Source), Python  
- **Document intelligence**: Azure OpenAI Vision, Azure Form Recognizer, Python Flask  
- **Storage & caching**: MongoDB / Redis (optional), local filesystem for temp storage  
- **Dev / Ops**: Docker, docker-compose, Git

---

## Project Layout (example)
```
rasa_pdf_app_starter/
│
├── rasa/                      # Rasa project (NLU, stories, actions)
│   ├── data/
│   ├── models/
│   ├── actions/
│   ├── config.yml
│   └── endpoints.yml
│
├── server/                    # Azure document-intelligence services
│   ├── app.py
│   ├── extract_toc.py
│   ├── graph_upload_server.py
│   └── spreadsheet_analysis.py
│
└── README.md
```

---

## Environment Variables
Create a `.env` file (do not commit). Example keys:

```
# Azure
AZURE_ENDPOINT=<your-azure-endpoint>
AZURE_KEY=<your-azure-key>
FORM_RECOGNIZER_ENDPOINT=<form-intel-endpoint>
FORM_RECOGNIZER_KEY=<form-intel-key>

# Rasa
RASA_TOKEN=<rasa-auth-token-if-any>
RASA_PROJECT_NAME=rasa_project
RASA_MODEL_PATH=./rasa/models

# Storage / DB
MONGO_URI=mongodb://localhost:27017/rasa_documents
```

---

## Installation (local)
1. Clone repo:
```bash
git clone <repo-url>
cd rasa_pdf_app_starter
```

2. Python environment (backend & server):
```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate      # Windows
pip install -r server/requirements.txt
pip install -r rasa/requirements.txt
```

3. Configure `.env` from `.env.example`.

---

## Running the Services

### Rasa backend (development)
```bash
# Start Rasa action server (if custom actions exist)
cd rasa
rasa run actions --actions actions
# Start Rasa server
rasa run --model models --enable-api --cors "*"
```

### Azure document server
```bash
cd server
python app.py
```

Alternatively, use Docker Compose if provided:
```bash
docker-compose up --build
```

---

## API Summary

### Rasa
- Rasa REST endpoints (interactive messaging, webhook) — see `endpoints.yml`.

### Server (Flask)
- `POST /extract-toc` → Accepts PDF, returns structured TOC JSON.  
- `POST /analyze-graph` → Upload chart image or PDF page, returns axes/values/trend insights via Azure Vision.  
- `POST /parse-sheet` → Upload spreadsheet, returns structured JSON using Azure Form Recognizer.

---

## Integration Tips
- To enrich Rasa responses with document context, call server endpoints from custom Rasa actions (`actions/custom_actions.py`) and include extracted snippets in the response generation logic.  
- Use MongoDB or another persistent store to cache extracted document indices and avoid reprocessing large files.  
- Implement authentication between Rasa and server (API keys or internal tokens) in `endpoints.yml` and Flask routes.

---

## Security & Operational Notes
- **Never commit** Azure keys or `.env`. Use secret managers for production.  
- Remove large binaries (model files) from the repo; provide download scripts instead.  
- Use containerized deployments for reproducibility. Allocate GPU resources if using model-heavy components.

---

## Contributing
- Follow conventional commits.  
- Add tests for Rasa actions and server endpoints.  
- Document new integrations in `/docs`.

---

## Contact
For questions or demo requests, open an issue on the repo or contact via the project profile.

