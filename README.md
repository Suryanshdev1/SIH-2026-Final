# 🔥 AI-Based Fire Detection & Classification

### Team Pyron — SIH'26

An autonomous AI-powered system for detecting, classifying, and assessing the risk of industrial fires and persistent thermal anomalies. This backend pipeline integrates real-time NASA FIRMS data, ESA WorldCover satellite land-cover mapping, OpenStreetMap (OSM) infrastructure data, and Machine Learning to dynamically assign risk levels.

---

## 🚀 Architecture & Pipeline

Our dynamic backend runs on a fully automated scheduled pipeline (`APScheduler`):

**NASA FIRMS API → Data Cleaning → DBSCAN Clustering → Persistence Scoring → ESA WorldCover Integration → OSM Geospatial Context → Industrial Proximity Calculation → ML Feature Generation (30 attributes) → Artificial Neural Network (ANN) Classification → Supabase PostgreSQL → React/Vite Map**

---

## 🎯 Key Features

- **Live Automation:** `APScheduler` automatically triggers the data fetching and processing pipeline every 3 hours.
- **Dual-Track AI Risk Engine:** Classifies events as **Industrial, Agricultural, or Wildfire** and dynamically assigns risk scores based on proximity to major infrastructure and population density.
- **Cloud Database:** Seamlessly stores processed multi-dimensional geo-data in Supabase for real-time querying.
- **FastAPI Backend:** Serves lightweight, scalable endpoints (`/api/thermal-map`, `/api/alerts`) returning GeoJSON objects for map rendering.
- **Interactive Frontend:** React + Vite + Tailwind CSS map dashboard that visualizes live thermal/fire data on an interactive map.

---

## 🛠️ Tech Stack

- **Backend & ML:** Python, FastAPI, TensorFlow/Keras, Scikit-Learn, APScheduler, Pandas, DBSCAN
- **Database:** PostgreSQL (Supabase Connection Pooler)
- **Geospatial & APIs:** NASA FIRMS, ESA WorldCover, OpenStreetMap (OSM)
- **Frontend:** React, Vite, Tailwind CSS
- **IoT Simulation:** Wokwi (ESP32), Localtunnel

---

## 📁 Project Structure (Reference)

```
SIH_Dynamic_Backend/
├── ml_model/              # FastAPI backend, ML pipeline, APScheduler
│   ├── main.py
│   ├── requirements.txt
│   └── ...
├── frontend/               # React + Vite dashboard
│   ├── src/
│   ├── package.json
│   └── ...
├── data/
│   ├── worldcover/         # (ask @Suryansh)
│   └── infrastructure/     # (ask @Suryansh)
├── .env.example
└── README.md
```

> Note: Adjust folder names above (`ml_model`, `frontend`) if your repo uses different names.

---

## 💻 Local Setup Instructions

Follow these steps exactly to run the backend, the live ESP32 hardware simulation, and the frontend on your local machine. You will need **three terminals open at the same time** — one for the backend, one for the Localtunnel bridge, and one for the frontend.

### 1. Clone the Repository

```bash
git clone <your-repo-link>
cd SIH_Dynamic_Backend
```

### 2. Request Missing Large Data Files (Important!)

Due to GitHub file size limits, the heavy geospatial data folders are ignored via `.gitignore`.
Before running the pipeline, you MUST ping @Suryansh to get these folders:

- `data/worldcover/`
- `data/infrastructure/`

Place these folders exactly inside the `data/` directory at the root of the project.

### 3. Setup the Python Environment

This project requires Python 3.11 or 3.12 (TensorFlow compatibility).

**For Windows:**
```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**For macOS/Linux:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment Variables

You need API keys and database credentials to run this project.
Create a new file named `.env` in the root directory and copy the contents from `.env.example`.

Ask @Suryansh for the actual values if you don't have them:

```
# Get this from NASA FIRMS portal
FIRMS_MAP_KEY=your_nasa_api_key_here

# Get this from Supabase Dashboard -> Connect -> IPv4 Pooler
DATABASE_URL=postgresql://[user]:[password]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

> **Note:** Use the Supabase IPv4 Connection Pooler URL (Port 6543) for stable DNS resolution, especially if you are on a restricted ISP like Jio/Airtel.

### 5. Run the Backend (Terminal 1)

Open your **first terminal**, activate the virtual environment if it isn't already active, navigate to the `ml_model` directory, and start the FastAPI server. The `APScheduler` is built directly into the server's startup routine and will automatically trigger the data pipeline in the background.

```bash
cd ml_model
uvicorn main:app --reload
```

- The server will start at `http://127.0.0.1:8000`.
- The background scheduler will automatically begin processing data every 3 hours.

**Keep this terminal running** — closing it will stop the backend and the scheduler.

### 6. Expose Backend via Localtunnel (Terminal 2)

Because the ESP32 hardware simulation runs on the cloud (Wokwi), it cannot directly send data to your `127.0.0.1` local server. We use Localtunnel to create a temporary public URL for your FastAPI backend.

Open a **second, separate terminal** and run:

```bash
npx localtunnel --port 8000
```

- You will get a URL like: `https://rapid-foxes-jump.loca.lt`
- Copy this URL — you will need to paste it into the ESP32 C++ code in the next step.

**Keep this terminal running.**

### 7. Start the ESP32 Hardware Simulation (Wokwi)

We use Wokwi to simulate a live IoT Ground Node sending real-time thermal, humidity, and gas telemetry to our backend.

1. Open the [Wokwi Simulation Link](https://wokwi.com/projects/476346268728822785) in your browser.
2. In the `sketch.ino` (or main C++) file, find the `serverUrl` line defined on line 10.
3. Replace the old URL with your newly generated Localtunnel URL (e.g., `String serverUrl = "https://rapid-foxes-jump.loca.lt/api/thermal-map";`).
4. Replace `https` → `http` (**Very important**).
5. Click the Play (▶) button to start the simulation. You can use the sliders on the DHT22 and other sensors to manipulate live data!

### 8. Run the Frontend (Terminal 3)

Open a **third terminal**. Navigate to the frontend folder from the project root:

```bash
cd frontend
```

Install the frontend dependencies (only needed the first time, or whenever `package.json` changes):

```bash
npm install
```

Start the frontend in development mode:

```bash
npm run dev
```

- The frontend will start at `http://localhost:5173` (Vite's default dev port — check your terminal output in case it differs).
- The frontend dev server uses in-memory caching and SWR (Stale-While-Revalidate) to fetch instantly from `http://127.0.0.1:8000`.
- Click on the Sambalpur ground node on the map to see the live ESP32 telemetry bridging all the way from Wokwi!

**Keep this terminal running** as well — this is a dev server, so no build or preview step is needed; it live-reloads as you edit code.

### ✅ Summary

| Terminal | Directory / Tool | Command | URL |
|---|---|---|---|
| Terminal 1 (Backend) | `ml_model` | `uvicorn main:app --reload` | `http://127.0.0.1:8000` |
| Terminal 2 (Localtunnel bridge) | project root | `npx localtunnel --port 8000` | `https://<random-name>.loca.lt` |
| Terminal 3 (Frontend) | `frontend` | `npm run dev` | `http://localhost:5173` |

Plus the **Wokwi ESP32 simulation** running in your browser, pointed at the Terminal 2 URL.

All three terminals (plus the Wokwi tab) must stay open at the same time for the full app — map, live data, and simulated hardware telemetry — to work.

---

## 🐛 Troubleshooting

- **CORS errors in browser console:** Make sure the FastAPI backend has CORS middleware enabled allowing `http://localhost:5173`.
- **Database connection fails:** Double-check you're using the Supabase **IPv4 Pooler** URL (port `6543`), not the direct connection string.
- **TensorFlow install errors:** Confirm you're using Python 3.11 or 3.12 — other versions are not supported.
- **Frontend shows blank map / no data:** Confirm the backend is running on port `8000` and `VITE_API_BASE_URL` in the frontend `.env` matches it.
- **Missing data folders:** If the pipeline throws file-not-found errors for `worldcover` or `infrastructure`, ping @Suryansh — these are not in the repo due to size limits.
- **ESP32 telemetry not reaching the backend:** Make sure the Localtunnel terminal (Terminal 2) is still running, the URL in `sketch.ino` matches the current Localtunnel URL exactly, and it uses `http`, not `https`. Localtunnel URLs change every time you restart Terminal 2, so update the Wokwi code again if you restart it.
- **Localtunnel asks for a "tunnel password" in the browser:** This is expected the first time you open the tunnel URL directly — the ESP32 request itself will still go through fine.

---

## 📌 Notes

- The APScheduler runs the full pipeline automatically every 3 hours — no manual trigger needed once the backend is up.
- The Localtunnel URL is temporary and changes each time you restart Terminal 2 — remember to update the Wokwi `sketch.ino` whenever that happens.
- Contact **@Suryansh** for: data folders, API keys, and database credentials.

---

**Smart India Hackathon 2026 — Team Pyron**