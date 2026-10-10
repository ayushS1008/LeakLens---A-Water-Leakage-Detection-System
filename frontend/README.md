# LeakLens frontend

React dashboard for uploading water readings, exploring daily charts, reviewing
suspected episodes, tracking maintenance and follow-up, managing household profiles,
and viewing opted-in notifications. See the root README for evaluation and limits.

## Development

Start the FastAPI backend on port 8000 from the project root. Then, in this directory:

```bash
npm ci
npm run dev
```

Open the URL printed by Vite. Its development proxy sends `/api` requests to the
backend. Both the dashboard and backend must run for uploads and saved records.

## Checks and single-server preview

```bash
npm run lint
npm run build
```

The build creates `dist/`, which the FastAPI server serves at port 8000. Build output
and dependencies are excluded from Git. Hash navigation keeps all pages available
when served by either Vite or FastAPI. AWS keys are never part of frontend code;
storage and SES configuration belong to the backend. See `../deploy/AWS_LOCAL.md`
for the verified laptop-to-AWS connection.
