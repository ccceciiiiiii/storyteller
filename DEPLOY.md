# Deploying Storyteller

Use **PostgreSQL** in production (SQLite is for local only). The app reads `DATABASE_URL` and creates tables on first request.

---

## Option A: Railway

1. **Push your code to GitHub** (if you haven’t already).

2. **Create a project on [Railway](https://railway.app)**  
   New Project → **Deploy from GitHub repo** → select your repo (and branch).

3. **Add PostgreSQL**  
   In the project: **+ New** → **Database** → **PostgreSQL**.  
   Railway creates a DB and exposes `DATABASE_URL` to the app.

4. **Configure the service**  
   Click your **web service** (not the DB):
   - **Variables**: Ensure `DATABASE_URL` is present (Railway often links it from the PostgreSQL service).
   - **Settings** → **Build**:
     - **Build Command**: `pip install -r requirements-prod.txt`
     - Or leave default and add to **Settings** → **Custom start command**:  
       `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - If Railway uses the **Procfile**, it will run:  
     `uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}`  
     No need to change anything if the Procfile is detected.

5. **Deploy**  
   Railway builds and runs the app. Open the generated URL (e.g. `https://your-app.up.railway.app`).

6. **Optional – OpenAI judge**  
   In the web service **Variables**, add:
   - `JUDGE_PROVIDER` = `openai`
   - `OPENAI_API_KEY` = your key (mark secret if available).

---

## Option B: Render

1. **Push your code to GitHub.**

2. **Create a Web Service on [Render](https://render.com)**  
   Dashboard → **New +** → **Web Service** → connect your repo.

3. **Add PostgreSQL**  
   **New +** → **PostgreSQL**. Create a DB (e.g. free plan), then copy the **Internal Database URL** (or External if you need off-Render access).

4. **Configure the Web Service**
   - **Build Command**: `pip install -r requirements-prod.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Environment**:
     - Add variable `DATABASE_URL` = the PostgreSQL URL from step 3.  
     - (Optional) `JUDGE_PROVIDER` = `openai`, `OPENAI_API_KEY` = your key.

5. **Deploy**  
   Render builds and deploys. Your app will be at e.g. `https://storyteller-xxxx.onrender.com`.

### Using the Blueprint (optional)

If your repo has `render.yaml` at the root:

- **New +** → **Blueprint** → connect repo.  
- Render will create the web service and PostgreSQL from the blueprint.  
- If the DB link doesn’t set `DATABASE_URL`, add it manually in the web service’s **Environment** with the new PostgreSQL URL.

---

## After deployment

- **App URL**: Open the service URL in a browser to use the frontend.
- **API base**: `https://your-app-url/api` (e.g. `POST /api/agents`, `POST /api/stories`, etc.).
- **CORS**: The app allows all origins, so agents or other frontends can call the API from any domain.

If something fails, check the platform’s logs; the app will create DB tables on first request, so the first load might be slightly slower.
