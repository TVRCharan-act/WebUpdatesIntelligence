# Health and Performance Logging

The app writes runtime health and performance events to:

```text
logs/app-health.jsonl
```

Each line is one JSON object. The file is created when the Docker app runs.

Captured events include:

- Backend startup and shutdown
- Backend HTTP request latency, path, status code, and failures
- Frontend page views
- Frontend API request latency and failures
- Celery worker readiness and shutdown
- Celery beat readiness
- Celery task start, finish, failure, duration, and result preview

Start the app:

```powershell
docker compose up --build
```

Use the dashboard normally, then stop Docker Compose with `Ctrl+C`.

Review the latest events:

```powershell
Get-Content logs\app-health.jsonl -Tail 100
```

Find errors:

```powershell
Select-String logs\app-health.jsonl -Pattern '"status":"error"'
```

Find slow actions:

```powershell
Get-Content logs\app-health.jsonl |
  ConvertFrom-Json |
  Where-Object { $_.duration_ms -gt 1000 } |
  Select-Object timestamp,event_type,service,action,status,duration_ms
```

The log path can be changed with:

```powershell
$env:APP_HEALTH_LOG_PATH = "logs/custom-health.jsonl"
docker compose up --build
```
