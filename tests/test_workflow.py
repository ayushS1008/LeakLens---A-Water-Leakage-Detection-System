import copy
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber
import pandas as pd

from backend.storage import AwsStore, LocalStore, RevisionConflict
from backend.workflow import build_ticket, change_ticket, compare_repair


def analysis_fixture(alerts_before=True, alerts_after=False):
    repair = pd.Timestamp('2021-06-01T12:00:00Z')
    grid = pd.date_range(repair - pd.Timedelta(hours=25), repair + pd.Timedelta(hours=24), freq='15min')
    readings = [{"timestamp": timestamp.isoformat(), "litres_used": 15.0 if timestamp <= repair else 1.0, "anomaly_score": .7, "is_alert": alerts_before if timestamp <= repair else alerts_after} for timestamp in grid]
    return {"analysis_id": "analysis-example", "household_id": "hh-01", "model_fingerprint": "fixed", "readings": readings, "summary": {}, "incidents": [{"incident_id": "incident-0001", "first_alert_at": '2021-05-31T14:00:00+00:00', "last_alert_at": repair.isoformat()}]}


def repaired_ticket(source):
    ticket = build_ticket(source, source['incidents'][0], 'Test investigation')
    return change_ticket(ticket, 'repaired', datetime(2021, 6, 1, 12, tzinfo=timezone.utc), 'Reported repair')


class WorkflowTests(unittest.TestCase):
    def test_improvement_is_not_a_water_saved_claim(self):
        source = analysis_fixture()
        report = compare_repair(repaired_ticket(source), source, source)
        self.assertEqual(report['outcome'], 'improved')
        self.assertEqual(report['before']['valid_intervals'], 96)
        self.assertEqual(report['after']['valid_intervals'], 96)
        self.assertNotIn('water_saved', report)

    def test_missing_after_reading_cannot_pass(self):
        source = analysis_fixture()
        followup = copy.deepcopy(source)
        followup['readings'][-1]['litres_used'] = None
        report = compare_repair(repaired_ticket(source), source, followup)
        self.assertEqual(report['outcome'], 'insufficient_data')
        self.assertIsNone(report['consumption_change_percent'])

    def test_unscored_after_window_cannot_pass(self):
        source = analysis_fixture()
        followup = copy.deepcopy(source)
        followup['readings'][-1]['anomaly_score'] = None
        self.assertEqual(compare_repair(repaired_ticket(source), source, followup)['outcome'], 'insufficient_data')

    def test_no_before_alert_is_inconclusive(self):
        source = analysis_fixture(alerts_before=False)
        self.assertEqual(compare_repair(repaired_ticket(source), source, source)['outcome'], 'inconclusive')

    def test_persistent_alerts_do_not_pass(self):
        source = analysis_fixture(alerts_after=True)
        self.assertEqual(compare_repair(repaired_ticket(source), source, source)['outcome'], 'alerts_persist')

    def test_household_and_model_must_match(self):
        source = analysis_fixture()
        for key in ['household_id', 'model_fingerprint']:
            followup = copy.deepcopy(source)
            followup[key] = 'different'
            with self.assertRaises(ValueError):
                compare_repair(repaired_ticket(source), source, followup)

    def test_repair_time_requires_timezone_and_grid(self):
        source = analysis_fixture()
        for time in [datetime(2021, 6, 1, 12), datetime(2021, 6, 1, 12, 1, tzinfo=timezone.utc)]:
            with self.assertRaises(ValueError):
                change_ticket(build_ticket(source, source['incidents'][0], ''), 'repaired', time, '')

    def test_persistence_deduplication_and_revision_conflicts(self):
        source = analysis_fixture()
        ticket = build_ticket(source, source['incidents'][0], 'Test')
        with tempfile.TemporaryDirectory() as folder:
            store = LocalStore(Path(folder) / 'records.sqlite3')
            store.save_analysis(source)
            store.create_ticket(ticket)
            store.create_ticket(ticket)
            restarted = LocalStore(Path(folder) / 'records.sqlite3')
            self.assertEqual(len(restarted.list_tickets()), 1)
            self.assertEqual(restarted.get_analysis(source['analysis_id'])['household_id'], 'hh-01')
            updated = change_ticket(copy.deepcopy(ticket), 'investigating', None, 'Checked')
            restarted.update_ticket(updated, 0)
            with self.assertRaises(RevisionConflict):
                restarted.update_ticket(updated, 0)


class AwsAdapterTests(unittest.TestCase):
    def setUp(self):
        # Explicit test credentials and Stubber ensure these checks never call AWS.
        options = dict(region_name='ap-south-1', aws_access_key_id='testing', aws_secret_access_key='testing')
        self.store = object.__new__(AwsStore)
        self.store.bucket = 'test-bucket'
        self.store.s3 = boto3.client('s3', **options)
        self.store.table = boto3.resource('dynamodb', **options).Table('test-table')

    def test_s3_roundtrip_format(self):
        analysis = analysis_fixture()
        packed = gzip.compress(json.dumps(analysis).encode())
        with Stubber(self.store.s3) as stub:
            stub.add_response('get_object', {'Body': StreamingBody(io.BytesIO(packed), len(packed))}, {'Bucket': 'test-bucket', 'Key': 'analyses/analysis-example.json.gz'})
            self.assertEqual(self.store.get_analysis('analysis-example'), analysis)
            stub.assert_no_pending_responses()

    def test_ticket_write_is_conditional(self):
        source = analysis_fixture()
        ticket = build_ticket(source, source['incidents'][0], 'Test')
        client = self.store.table.meta.client
        with Stubber(client) as stub:
            stub.add_response('put_item', {}, {'TableName': 'test-table', 'Item': {'pk': f"ticket#{ticket['ticket_id']}", 'kind': 'ticket', 'body': json.dumps(ticket), 'revision': 0}, 'ConditionExpression': 'attribute_not_exists(pk)'})
            self.assertEqual(self.store.create_ticket(ticket), ticket)
            stub.assert_no_pending_responses()

    def test_conflicting_dynamodb_update_is_not_silently_overwritten(self):
        source = analysis_fixture()
        ticket = repaired_ticket(source)
        with Stubber(self.store.table.meta.client) as stub:
            stub.add_client_error('put_item', service_error_code='ConditionalCheckFailedException')
            with self.assertRaises(RevisionConflict):
                self.store.update_ticket(ticket, 0)


if __name__ == '__main__':
    unittest.main()
