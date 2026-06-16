# Ontario Data Preprocessing — Phase 1

React frontend + FastAPI backend for fuzzy Ontario location matching and weekly aggregation.

## Project structure
```
project/
├── frontend/   # React (Vite)
├── backend/    # FastAPI
└── docs/
```

## Backend setup
```powershell
cd F:\RSV\project\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

API docs: http://127.0.0.1:8000/docs

## Frontend setup
Install Node.js first: https://nodejs.org/

```powershell
cd F:\RSV\project\frontend
npm install
npm run dev
```

Open: http://127.0.0.1:5173

## Test with your wastewater file
```powershell
cd F:\RSV\project\backend
.\.venv\Scripts\activate
python test_wastewater.py
```

Input file:
`F:\RSV\wastewater_aggregate(in).csv`

## API example
```powershell
curl -X POST "http://127.0.0.1:8000/preprocess" ^
  -F "file=@F:\RSV\wastewater_aggregate(in).csv" ^
  -F "data_type=wastewater" ^
  -F "download=true" ^
  -o weekly_wastewater.csv
```
