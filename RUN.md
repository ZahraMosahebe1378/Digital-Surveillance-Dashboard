# How to Run Phase 1

## Important (Windows)

PowerShell on your machine blocks scripts (`Activate.ps1`, `npm.ps1`).

**Do NOT use in PowerShell:**
```powershell
npm install
npm run dev
.\.venv\Scripts\activate
uvicorn app:app --reload
```

**Use the `.bat` files instead:**

| Step | File |
|------|------|
| Backend | `F:\RSV\project\start-backend.bat` |
| Frontend | `F:\RSV\project\start-frontend.bat` |

---

## Step 1: Backend (terminal 1)

```powershell
F:\RSV\project\start-backend.bat
```

Or manually:
```powershell
cd F:\RSV\project\backend
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Open: http://127.0.0.1:8000/docs

---

## Step 2: Frontend (terminal 2)

```powershell
F:\RSV\project\start-frontend.bat
```

Open either:
- http://127.0.0.1:5173
- http://localhost:5173

If one fails, try the other. After restarting frontend, both should work.

---

## Optional: fix PowerShell permanently

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

After this, `npm install` may work directly in PowerShell.
