# Sentinel Actalyst on AWS

The production topology is React static assets behind CloudFront/S3 (or an
equivalent static host), a FastAPI ECS/Fargate service behind an ALB, and a
separate ECS/Fargate task definition for monitor work. SES is the active email
delivery mechanism. EventBridge Scheduler
starts the scheduler task on a one-minute cadence; that task selects only
enabled monitors whose `schedule_minutes` is due and launches normal monitor
jobs. ECS task roles use the AWS credential provider chain—no access keys are
stored in application configuration.

## Required configuration

Set these values in the API and worker task definitions (use Secrets Manager or
SSM Parameter Store for secrets):

```env
ZENROWS_API_KEY=...
GOOGLE_API_KEY=...
GOOGLE_GEMINI_MODEL=gemini-3.5-flash
AWS_REGION=us-east-1
ENVIRONMENT=prod
S3_BUCKET=your-sentinel-bucket
S3_PREFIX=sentinel-actalyst
ECS_CLUSTER=...
ECS_TASK_DEFINITION=...
ECS_NETWORK_CONFIGURATION={"awsvpcConfiguration":{"subnets":[...],"securityGroups":[...],"assignPublicIp":"DISABLED"}}
TASK_EXECUTION_BACKEND=ecs
SES_FROM_EMAIL=alerts@example.com
SES_CONFIGURATION_SET=optional-configuration-set
AUTH_SECRET=<long-random-secret>
```

The ECS task role needs scoped `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`
and `s3:ListBucket` access for `${S3_PREFIX}/${ENVIRONMENT}/v1/*`, SES
`ses:SendEmail`/`ses:SendRawEmail` for the verified sender, and CloudWatch Logs
write access. The API task role additionally needs `ecs:RunTask` only for the
worker task definition plus `iam:PassRole` only for that worker role.

## Local development with AWS IAM Identity Center (SSO)

Use SSO locally rather than adding AWS access keys to `.env`. Install AWS CLI
v2, then configure the profile once. The wizard asks for the IAM Identity
Center start URL, the region hosting IAM Identity Center, the account, and the
role supplied by your AWS administrator:

```powershell
.\scripts\aws-sso-login.ps1 -Configure -Profile actalyst-dev
```

Subsequent sessions only need a login:

```powershell
.\scripts\aws-sso-login.ps1 -Profile actalyst-dev
```

For Docker Desktop on Windows, set these non-secret values in `.env`:

```env
AWS_PROFILE=actalyst-dev
AWS_CONFIG_DIR=C:/Users/your-windows-user/.aws
AWS_SSO_CACHE_DIR=C:/Users/your-windows-user/.aws/sso/cache
TASK_EXECUTION_BACKEND=local
```

Start the local UI and API with the optional SSO override:

```powershell
docker compose -f docker-compose.yml -f docker-compose.sso.yml up -d --build
```

The override mounts the host `.aws` directory into the backend container as
read-only, but mounts the `sso/cache` subdirectory as writable so the AWS SDK
can refresh its short-lived token. It is for local Docker development only.
With `TASK_EXECUTION_BACKEND=local`, manual baseline and monitor runs execute
in a background thread. The Compose stack also starts a local scheduler that
checks for due monitors every 15 seconds, so customer monitoring behaves like
the production EventBridge cadence. Jobs do not survive a container restart.
ECS/Fargate must continue to use task roles, not an SSO profile or mounted
credentials.

## S3 layout

Every key begins with `${S3_PREFIX}/${ENVIRONMENT}/v1`. Customer data is below
`accounts/{url-encoded-owner}/`, including company, source, run, job, seen,
discovered URL, insight, recipient, and notification-setting records. Exact
seen records are keyed by a SHA-256 URL fingerprint. `operations/*-index`
contains small derived owner indexes for admin lookups; it is not a second
mutable source of truth. Individual JSON records carry `schema_version` and
UTC timestamps.

## Deployment

1. Build the backend image and publish it to ECR. Use the same image for the
   API task definition and the worker definition; set the worker command to
   `python -m backend.app.workers.task_runner`.
2. Build the frontend image using `frontend/Dockerfile`, or publish its `dist/`
   folder to a private S3/CloudFront static site. This is a Vite production
   build served as static files, never the Vite development server.
3. Create the S3 bucket with versioning and encryption enabled, then apply the
   least-privilege task roles.
4. Deploy the API ECS service behind HTTPS/ALB and configure its CORS origins
   to the production React origin.
5. Verify the SES sender identity and, if necessary, request production access
   to leave the SES sandbox.
6. Create the EventBridge schedule target using the worker task definition with
   no `SENTINEL_JOB_ID`; it performs the due-monitor dispatch tick.

`infra/fargate-s3-ses.yaml` supplies a parameterized starting point for the S3
bucket, scoped task role, and scheduler role. Networking, ECR images, task
definitions, and the frontend host remain account/environment-specific inputs.

## Data migration

Do not delete the legacy database or JSON files. First take a PostgreSQL backup
and copy `mysignal/data`. Run the migration from an administrative environment
with the target S3 configuration set:

```powershell
python scripts/migrate_to_s3.py --legacy-json-dir mysignal/data --postgres-dsn "postgresql://..." --report migration-report.json
```

The migration is safe to rerun: account/company/source/recipient and seen URL
writes are de-duplicated. It hashes legacy account passwords before storage and
writes migrated/skipped/duplicate/failed counts to the report. Install
`psycopg` only in this one-off administrative environment if PostgreSQL import
is needed; it is not part of the service image. Compare the report with the
legacy backup before switching traffic.
