"""A persistent inbox and opt-in email summaries; no credentials in requests."""
import hashlib
import os
from urllib.parse import urlencode

from backend.storage import RevisionConflict
from backend.workflow import utc_now


def email_configuration():
    sender = os.getenv('LEAKLENS_EMAIL_FROM', '').strip()
    recipient = os.getenv('LEAKLENS_EMAIL_TO', '').strip()
    region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION')
    return sender, recipient, region


def preferences(store):
    saved = store.get_record('settings', 'notifications') or {'email_enabled': False, 'revision': 0}
    sender, recipient, region = email_configuration()
    return {**saved, 'email_configured': bool(sender and recipient and region), 'email_recipient': recipient,
            'email_note': 'Email uses the sender and recipient configured on the server. AWS SES must allow both addresses.'}


def make_notification(store, analysis):
    if not analysis['incidents']:
        return None
    # Deduplicate each observed episode across repeated uploads, then group fresh episodes.
    fresh = []
    for incident in analysis['incidents']:
        identity = f"{analysis['household_id']}:{analysis['model_fingerprint']}:{incident['first_alert_at']}"
        key = hashlib.sha256(identity.encode()).hexdigest()[:32]
        existing = store.get_record('episode_seen', key)
        if existing is None:
            fresh.append((key, incident))
    if not fresh:
        return None
    identity = ':'.join(sorted(key for key, _ in fresh))
    event_id = 'notification-' + hashlib.sha256(identity.encode()).hexdigest()[:24]
    settings = preferences(store)
    count = len(fresh)
    event = {
        'notification_id': event_id, 'analysis_id': analysis['analysis_id'], 'household_id': analysis['household_id'],
        'title': f"{count} suspected {'episode' if count == 1 else 'episodes'} · {analysis.get('household_name', analysis['household_id'])}",
        'message': 'New suspicious patterns were found in an uploaded file. Review their dates and explanations before confirming a leak.',
        'incident_ids': [incident['incident_id'] for _, incident in fresh], 'created_at': utc_now(), 'read': False,
        'first_alert_at': min(incident['first_alert_at'] for _, incident in fresh),
        'last_alert_at': max(incident['last_alert_at'] for _, incident in fresh),
        'email_status': 'pending' if settings['email_enabled'] and settings['email_configured'] else 'disabled',
        'email_error': None, 'revision': 0,
    }
    created, saved = store.create_record('notification', event_id, event)
    for key, _ in fresh:
        store.create_record('episode_seen', key, {'notification_id': event_id, 'revision': 0})
    return saved if created else None


def send_email(event, client=None):
    sender, recipient, region = email_configuration()
    if not (sender and recipient and region):
        raise ValueError('Email is not configured. Set the AWS region, verified sender, and recipient on the server.')
    if client is None:
        import boto3
        from botocore.config import Config
        client = boto3.client('ses', region_name=region, config=Config(connect_timeout=5, read_timeout=15, retries={'max_attempts': 0}))
    public_url = os.getenv('LEAKLENS_PUBLIC_URL', '').rstrip('/')
    link = f"{public_url}/#/alerts?{urlencode({'analysis': event['analysis_id']})}" if public_url else 'Open LeakLens, select this household, and review Alerts.'
    body = f"{event['title']}\n\n{event['message']}\n\nHousehold: {event['household_id']}\nReading period: {event['first_alert_at']} to {event['last_alert_at']}\n\n{link}\n\nThese are suspected patterns in uploaded readings, not confirmed leaks or live meter notifications."
    return client.send_email(Source=sender, Destination={'ToAddresses': [recipient]}, Message={'Subject': {'Data': f"LeakLens: {event['title']}", 'Charset': 'UTF-8'}, 'Body': {'Text': {'Data': body, 'Charset': 'UTF-8'}}})['MessageId']


def deliver_email(store, event_id, client=None):
    event = store.get_record('notification', event_id)
    if not event or event['email_status'] not in ['pending', 'failed']:
        return
    if not preferences(store)['email_enabled']:
        return
    revision = event['revision']
    event.update(email_status='sending', email_error=None, revision=revision + 1)
    try:
        store.update_record('notification', event_id, event, revision)
    except RevisionConflict:
        return
    try:
        message_id = send_email(event, client)
        updates = {'email_status': 'accepted', 'email_message_id': message_id, 'email_sent_at': utc_now(), 'email_error': None}
    except Exception:
        updates = {'email_status': 'failed', 'email_error': 'The email attempt failed or its result is unknown. Check SES verification, permissions, region, and sending limits. Verify its status before retrying to avoid a duplicate.'}
    # Preserve a simultaneous mark-as-read change when recording delivery status.
    for _ in range(3):
        current = store.get_record('notification', event_id)
        expected = current['revision']
        current.update(**updates, revision=expected + 1)
        try:
            store.update_record('notification', event_id, current, expected)
            return
        except RevisionConflict:
            continue
