from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from io import BytesIO
from typing import Annotated, Literal
import hashlib
import json
import joblib
import pandas as pd

from fastapi import APIRouter, BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.detector import analyse_readings
from backend.storage import make_store, StorageUnavailable, RevisionConflict
from backend.workflow import build_ticket, change_ticket, compare_repair, record_finding, utc_now
from backend.households import validate_identity, train_household, public_profile, explain_analysis
from backend.notifications import preferences, make_notification, deliver_email

root = Path(__file__).resolve().parents[1]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_path = root / "models" / "isolation_forest.joblib"
    config_path = root / "models" / "detection_config.json"
    app.state.model = joblib.load(model_path)
    app.state.config = json.loads(config_path.read_text())
    if list(app.state.model.feature_names_in_) != app.state.config["feature_columns"]:
        raise RuntimeError("Model and configuration features differ.")
    app.state.model_fingerprint = hashlib.sha256(model_path.read_bytes() + config_path.read_bytes()).hexdigest()
    app.state.store = make_store(root)
    app.state.household_models = {}
    print("LeakLens model loaded. Storage:", app.state.store.name)
    yield
    app.state.model = None


app = FastAPI(title="LeakLens API", description="Water-consumption anomaly detection and maintenance prototype.", version="0.4.0", lifespan=lifespan)
router = APIRouter()


@app.exception_handler(StorageUnavailable)
async def storage_error(_request, error):
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.exception_handler(RevisionConflict)
async def revision_error(_request, error):
    return JSONResponse(status_code=409, content={"detail": str(error)})


@router.get("/health")
def health():
    return {"status": "ok", "model_loaded": app.state.model is not None, "storage": app.state.store.name, "aws_enabled": app.state.store.name == "Amazon S3 + DynamoDB"}


@router.get("/model-info")
def model_info():
    config = app.state.config
    return {"model": "Isolation Forest", "anomaly_threshold": config["anomaly_threshold"], "interval_minutes": config["interval_minutes"], "timezone": config["timezone"], "features": config["feature_columns"], "training_rows": config["training_rows"], "scope": "Prototype trained on household hh-01 readings."}


def builtin_profile():
    return {'household_id': 'hh-01', 'name': 'Household hh-01', 'timezone': app.state.config['timezone'], 'built_in': True,
            'config': app.state.config, 'model_fingerprint': app.state.model_fingerprint,
            'training_rows': app.state.config['training_rows'], 'calibration_rows': app.state.config['validation_rows'],
            'baseline_start': '2020-12-15T09:00:00+00:00', 'baseline_end': '2021-05-26T19:45:00+00:00',
            'model_status': 'Built-in household model. Four selected synthetic test scenarios were detected; real leaks are unlabelled.', 'revision': 0}


def household_profile(household_id):
    if household_id == 'hh-01':
        return builtin_profile()
    profile = app.state.store.get_record('household', household_id)
    if profile is None:
        raise HTTPException(status_code=404, detail='Household not found. Add its profile and baseline readings first.')
    return profile


def detector_for(profile):
    if profile['built_in']:
        return app.state.model, app.state.config
    key = profile['model_key']
    cache = app.state.household_models
    if key not in cache:
        if len(cache) >= 4:
            cache.pop(next(iter(cache)))
        # Only artifacts generated internally by train_household are accepted.
        artifact = app.state.store.get_model(key)
        fingerprint = hashlib.sha256(artifact + json.dumps(profile['config'], sort_keys=True).encode()).hexdigest()
        if fingerprint != profile['model_fingerprint']:
            raise StorageUnavailable('The household model does not match its saved configuration.')
        cache[key] = joblib.load(BytesIO(artifact))
    return cache[key], profile['config']


def read_upload(file):
    if not (file.filename or '').lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail='Upload a CSV file.')
    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail='Maximum file size is 10 MB.')
    try:
        return contents, pd.read_csv(BytesIO(contents), nrows=25001, dtype={'household_id': str})
    except (ValueError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def process_upload(file, household_id=None):
    contents, frame = read_upload(file)
    ids = frame['household_id'].dropna().astype(str).unique() if 'household_id' in frame else []
    chosen = household_id or (str(ids[0]) if len(ids) == 1 else 'hh-01')
    try:
        validate_identity(frame, chosen)
        profile = household_profile(chosen)
        model, config = detector_for(profile)
        result = analyse_readings(frame, model, config)
    except (ValueError, UnicodeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    result['household_id'] = chosen
    result['model_fingerprint'] = profile['model_fingerprint']
    # Preserve the existing built-in identity so old tickets still match.
    result['analysis_id'] = 'analysis-' + hashlib.sha256(contents + result['model_fingerprint'].encode()).hexdigest()[:32]
    explain_analysis(result, config, profile)
    app.state.store.save_analysis(result)
    return result


@router.get('/households')
def list_households():
    profiles = [builtin_profile()] + sorted(app.state.store.list_records('household'), key=lambda row: row['name'].lower())
    return {'households': [public_profile(profile) for profile in profiles]}


@router.post('/households')
def create_household(file: Annotated[UploadFile, File()], household_id: Annotated[str, Form(min_length=1, max_length=40)], name: Annotated[str, Form(min_length=1, max_length=80)], timezone: Annotated[str, Form(max_length=80)] = 'UTC'):
    if household_id == 'hh-01' or app.state.store.get_record('household', household_id):
        raise HTTPException(status_code=409, detail='This household ID already exists. Select it or choose a different ID.')
    _, frame = read_upload(file)
    try:
        if not name.strip():
            raise ValueError('Enter a household name.')
        profile, artifact = train_household(frame, household_id, name, timezone, app.state.config['feature_columns'])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    app.state.store.save_model(profile['model_key'], artifact)
    created, saved = app.state.store.create_record('household', household_id, profile)
    if not created:
        raise HTTPException(status_code=409, detail='Another request created this household. Refresh the profile list.')
    return public_profile(saved)


@router.post('/analyse')
def analyse_csv(file: Annotated[UploadFile, File()], background_tasks: BackgroundTasks, include_readings: bool = False, household_id: str | None = None):
    result = process_upload(file, household_id)
    event = make_notification(app.state.store, result)
    if event and event['email_status'] == 'pending':
        background_tasks.add_task(deliver_email, app.state.store, event['notification_id'])
    result = {**result, 'new_notification_id': event['notification_id'] if event else None}
    if not include_readings:
        result = {key: value for key, value in result.items() if key != 'readings'}
    return result


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    analysis = app.state.store.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Saved analysis not found. Upload the CSV again.")
    profile = household_profile(analysis['household_id'])
    if analysis.get('model_fingerprint') == profile['model_fingerprint']:
        explain_analysis(analysis, profile['config'], profile)
    return analysis


class TicketCreate(BaseModel):
    analysis_id: str = Field(min_length=1, max_length=80)
    incident_id: str = Field(min_length=1, max_length=80)
    description: str = Field(default="Investigate persistent unusual water use.", max_length=500)


class TicketUpdate(BaseModel):
    status: Literal["investigating", "repaired"]
    revision: int = Field(ge=0)
    repaired_at: datetime | None = None
    note: str = Field(default="", max_length=500)


def require_ticket(ticket_id):
    ticket = app.state.store.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@router.get("/tickets")
def list_tickets():
    tickets = app.state.store.list_tickets()
    sources = {}
    for ticket in tickets:
        if not ticket.get('explanation'):
            key = ticket['analysis_id']
            if key not in sources:
                try:
                    sources[key] = get_analysis(key)
                except HTTPException:
                    sources[key] = None
            source = sources[key]
            if source:
                incident = next((row for row in source['incidents'] if row['incident_id'] == ticket['incident_id']), {})
                ticket['explanation'] = incident.get('explanation')
    return {"tickets": tickets, "storage": app.state.store.name}


@router.post("/tickets")
def create_ticket(request: TicketCreate):
    analysis = app.state.store.get_analysis(request.analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found. Upload the CSV first.")
    incident = next((item for item in analysis["incidents"] if item["incident_id"] == request.incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Alert episode not found in this analysis.")
    return app.state.store.create_ticket(build_ticket(analysis, incident, request.description))


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, request: TicketUpdate):
    ticket = require_ticket(ticket_id)
    if ticket["revision"] != request.revision:
        raise RevisionConflict("Ticket changed. Refresh the ticket list and try again.")
    try:
        changed = change_ticket(ticket, request.status, request.repaired_at, request.note)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return app.state.store.update_ticket(changed, request.revision)


@router.post("/tickets/{ticket_id}/verify")
def verify_ticket(ticket_id: str, file: Annotated[UploadFile, File()], revision: Annotated[int, Form(ge=0)]):
    ticket = require_ticket(ticket_id)
    if ticket["revision"] != revision:
        raise RevisionConflict("Ticket changed. Refresh the ticket list and try again.")
    source = app.state.store.get_analysis(ticket["analysis_id"])
    if source is None:
        raise HTTPException(status_code=404, detail="Saved original analysis not found.")
    followup = process_upload(file, ticket["household_id"])
    try:
        ticket["verification"] = compare_repair(ticket, source, followup)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    ticket["revision"] += 1
    ticket["updated_at"] = utc_now()
    ticket["history"] = (ticket["history"] + [{"at": ticket["updated_at"], "action": "followup_checked", "note": ticket["verification"]["outcome"]}])[-50:]
    return app.state.store.update_ticket(ticket, revision)


class FindingRequest(BaseModel):
    outcome: Literal['confirmed_leak', 'normal_activity', 'undetermined']
    note: str = Field(min_length=1, max_length=1000)
    revision: int = Field(ge=0)


@router.post('/tickets/{ticket_id}/finding')
def save_finding(ticket_id: str, request: FindingRequest):
    ticket = require_ticket(ticket_id)
    if ticket['revision'] != request.revision:
        raise RevisionConflict('Ticket changed. Refresh the ticket list and try again.')
    try:
        changed = record_finding(ticket, request.outcome, request.note)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return app.state.store.update_ticket(changed, request.revision)


class NotificationPreferences(BaseModel):
    email_enabled: bool
    revision: int = Field(ge=0)


@router.get('/notification-settings')
def notification_settings():
    return preferences(app.state.store)


@router.put('/notification-settings')
def update_notification_settings(request: NotificationPreferences):
    store = app.state.store
    if request.email_enabled and not preferences(store)['email_configured']:
        raise HTTPException(status_code=400, detail='Configure the AWS SES sender, recipient, and region on the server first.')
    record = {'email_enabled': request.email_enabled, 'revision': request.revision + 1}
    current = store.get_record('settings', 'notifications')
    if current is None:
        if request.revision != 0:
            raise RevisionConflict('Settings changed. Refresh and try again.')
        created, _ = store.create_record('settings', 'notifications', record)
        if not created:
            raise RevisionConflict('Settings changed. Refresh and try again.')
    else:
        store.update_record('settings', 'notifications', record, request.revision)
    return preferences(store)


@router.get('/notifications')
def list_notifications():
    events = sorted(app.state.store.list_records('notification'), key=lambda row: row['created_at'], reverse=True)
    return {'notifications': events[:200], 'unread_count': sum(not event['read'] for event in events)}


@router.post('/notifications/{notification_id}/read')
def read_notification(notification_id: str):
    store = app.state.store
    event = store.get_record('notification', notification_id)
    if event is None:
        raise HTTPException(status_code=404, detail='Notification not found.')
    if event['read']:
        return event
    revision = event['revision']
    event.update(read=True, revision=revision + 1)
    return store.update_record('notification', notification_id, event, revision)


@router.post('/notifications/{notification_id}/retry-email')
def retry_email(notification_id: str, background_tasks: BackgroundTasks):
    store = app.state.store
    settings = preferences(store)
    if not settings['email_configured'] or not settings['email_enabled']:
        raise HTTPException(status_code=400, detail='Configure and enable email notifications first.')
    event = store.get_record('notification', notification_id)
    if event is None:
        raise HTTPException(status_code=404, detail='Notification not found.')
    if event['email_status'] not in ['failed', 'pending']:
        raise HTTPException(status_code=409, detail='This email is already being sent, accepted, or was not enabled for this analysis.')
    background_tasks.add_task(deliver_email, store, notification_id)
    return {'status': 'queued'}


# Keep the original documentation URLs; /api also works in the deployed app.
app.include_router(router)
app.include_router(router, prefix="/api", include_in_schema=False)
dist = root / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
