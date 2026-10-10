"""Behaviour checks for household isolation, explanations, findings, and notifications."""
import copy
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import boto3
from botocore.stub import Stubber, ANY
import joblib
import numpy as np
import pandas as pd

from backend.detector import analyse_readings
from backend.households import train_household, validate_identity, explain_analysis
from backend.notifications import make_notification, preferences, deliver_email
from backend.storage import LocalStore, RevisionConflict, AwsStore
from backend.workflow import build_ticket, record_finding

ROOT = Path(__file__).resolve().parents[1]


def example_analysis():
    grid = pd.date_range('2021-01-01', periods=10, freq='15min', tz='UTC')
    return {'household_id': 'hh-02', 'household_name': 'Test home', 'model_fingerprint': 'model-test', 'analysis_id': 'analysis-test', 'anomaly_threshold': .6,
            'readings': [{'timestamp': time.isoformat(), 'litres_used': 3.0, 'anomaly_score': .7, 'is_candidate': True, 'is_alert': i >= 6} for i, time in enumerate(grid)],
            'incidents': [{'incident_id': 'incident-0001', 'first_alert_at': grid[6].isoformat(), 'last_alert_at': grid[-1].isoformat(), 'alert_intervals': 4}]}


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = LocalStore(Path(self.folder.name) / 'records.sqlite3')

    def test_household_training_uses_own_history_and_persists_model(self):
        config = json.loads((ROOT/'models/detection_config.json').read_text())
        grid = pd.date_range('2024-01-01', periods=15*96, freq='15min', tz='UTC')
        water = np.where((np.arange(len(grid)) % 96 > 30) & (np.arange(len(grid)) % 96 < 35), 12.0, 0.0)
        frame = pd.DataFrame({'timestamp': grid.astype(str), 'litres_used': water, 'household_id': 'hh-02'})
        with self.assertRaises(ValueError):
            validate_identity(frame, 'hh-01')
        missing = frame.copy(); missing.loc[0, 'household_id'] = None
        with self.assertRaises(ValueError):
            validate_identity(missing, 'hh-02')
        with self.assertRaises(ValueError):
            train_household(frame.head(100), 'hh-02', 'Test home', 'UTC', config['feature_columns'])
        profile, artifact = train_household(frame, 'hh-02', 'Test home', 'UTC', config['feature_columns'])
        self.store.save_model(profile['model_key'], artifact)
        restored = joblib.load(BytesIO(self.store.get_model(profile['model_key'])))
        self.assertEqual(profile['training_rows'] + profile['calibration_rows'], len(grid) - 3)
        self.assertNotEqual(profile['config']['anomaly_threshold'], config['anomaly_threshold'])
        result = analyse_readings(frame, restored, profile['config'])
        explain_analysis(result, profile['config'], profile)
        self.assertTrue(result['baseline_overlap'])
        self.assertEqual(result['household_name'], 'Test home')
        self.assertEqual(result['summary']['total_recorded_litres'], float(water.sum()))
        # A different household history actually yields a different fitted artifact.
        second = frame.copy(); second['household_id'] = 'hh-03'; second['litres_used'] *= 3
        other, _ = train_household(second, 'hh-03', 'Other home', 'UTC', config['feature_columns'])
        self.assertNotEqual(other['model_fingerprint'], profile['model_fingerprint'])

    def test_explanation_matches_observed_readings_and_finding_is_separate(self):
        result = example_analysis()
        profile = {'household_id': 'hh-02', 'name': 'Test home'}
        explain_analysis(result, {'timezone': 'UTC'}, profile)
        evidence = result['incidents'][0]['explanation']['evidence']
        self.assertEqual(evidence['litres_in_trigger_hour'], 12)
        self.assertEqual(evidence['positive_use_minutes'], 105)
        self.assertEqual(evidence['consecutive_unusual_intervals'], 4)
        ticket = build_ticket(result, result['incidents'][0], 'Review')
        original = copy.deepcopy(result)
        changed = record_finding(ticket, 'normal_activity', 'Washing clothes')
        self.assertEqual(changed['finding']['source'], 'user_reported')
        self.assertEqual(changed['status'], 'open')
        self.assertEqual(result, original)
        for outcome, note in [('bad', 'x'), ('undetermined', '  ')]:
            with self.assertRaises(ValueError):
                record_finding(ticket, outcome, note)

    def test_notification_deduplication_and_household_separation(self):
        result = example_analysis()
        first = make_notification(self.store, result)
        self.assertEqual(first['email_status'], 'disabled')
        self.assertIsNone(make_notification(self.store, result))
        # A new file ID with the same observed episode also stays deduplicated.
        result['analysis_id'] = 'different-file'
        self.assertIsNone(make_notification(self.store, result))
        result['household_id'] = 'hh-03'
        self.assertIsNotNone(make_notification(self.store, result))
        self.assertEqual(len(self.store.list_records('notification')), 2)
        record = {**first, 'read': True, 'revision': 1}
        self.store.update_record('notification', first['notification_id'], record, 0)
        with self.assertRaises(RevisionConflict):
            self.store.update_record('notification', first['notification_id'], record, 0)

    def test_email_opt_in_failure_retry_and_service_acceptance(self):
        env = {'LEAKLENS_EMAIL_FROM': 'sender@example.com', 'LEAKLENS_EMAIL_TO': 'recipient@example.com', 'AWS_REGION': 'ap-south-1'}
        client = boto3.client('ses', region_name='ap-south-1', aws_access_key_id='testing', aws_secret_access_key='testing')
        with patch.dict(os.environ, env):
            self.assertTrue(preferences(self.store)['email_configured'])
            self.assertFalse(preferences(self.store)['email_enabled'])
            self.store.create_record('settings', 'notifications', {'email_enabled': True, 'revision': 1})
            event = make_notification(self.store, example_analysis())
            expected = {'Source': 'sender@example.com', 'Destination': {'ToAddresses': ['recipient@example.com']}, 'Message': ANY}
            with Stubber(client) as stub:
                stub.add_client_error('send_email', service_error_code='MessageRejected', expected_params=expected)
                deliver_email(self.store, event['notification_id'], client)
                self.assertEqual(self.store.get_record('notification', event['notification_id'])['email_status'], 'failed')
                stub.add_response('send_email', {'MessageId': 'accepted-test-message'}, expected)
                deliver_email(self.store, event['notification_id'], client)
                accepted = self.store.get_record('notification', event['notification_id'])
                self.assertEqual(accepted['email_status'], 'accepted')
                self.assertEqual(accepted['email_message_id'], 'accepted-test-message')
                deliver_email(self.store, event['notification_id'], client)  # Already accepted: no second send.
                stub.assert_no_pending_responses()

    def test_aws_model_storage_does_not_use_expiring_analysis_prefix(self):
        store = object.__new__(AwsStore); store.bucket = 'test-bucket'
        store.s3 = boto3.client('s3', region_name='ap-south-1', aws_access_key_id='testing', aws_secret_access_key='testing')
        with Stubber(store.s3) as stub:
            stub.add_response('put_object', {}, {'Bucket': 'test-bucket', 'Key': 'models/model-test.joblib', 'Body': b'internal-model', 'ContentType': 'application/octet-stream', 'ServerSideEncryption': 'AES256'})
            store.save_model('model-test', b'internal-model')
            stub.assert_no_pending_responses()


if __name__ == '__main__':
    unittest.main()
