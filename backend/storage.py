"""Persist analyses and tickets locally, or in S3 and DynamoDB on AWS."""
import gzip
import base64
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class StorageUnavailable(RuntimeError):
    pass


class RevisionConflict(ValueError):
    pass


class LocalStore:
    name = "SQLite (local)"

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(kind,id))")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save_analysis(self, analysis):
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO records(kind,id,body) VALUES ('analysis',?,?)", (analysis["analysis_id"], json.dumps(analysis, allow_nan=False)))

    def get_analysis(self, analysis_id):
        return self.get("analysis", analysis_id)

    def get(self, kind, record_id):
        with self.connect() as connection:
            row = connection.execute("SELECT body FROM records WHERE kind=? AND id=?", (kind, record_id)).fetchone()
        return json.loads(row[0]) if row else None

    def create_ticket(self, ticket):
        with self.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO records(kind,id,body,revision) VALUES ('ticket',?,?,?)", (ticket["ticket_id"], json.dumps(ticket), ticket["revision"]))
        return self.get_ticket(ticket["ticket_id"])

    def get_ticket(self, ticket_id):
        return self.get("ticket", ticket_id)

    def list_tickets(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT body FROM records WHERE kind='ticket'").fetchall()
        return sorted([json.loads(row[0]) for row in rows], key=lambda item: item["created_at"], reverse=True)

    def update_ticket(self, ticket, expected_revision):
        with self.connect() as connection:
            changed = connection.execute("UPDATE records SET body=?,revision=? WHERE kind='ticket' AND id=? AND revision=?", (json.dumps(ticket, allow_nan=False), ticket["revision"], ticket["ticket_id"], expected_revision)).rowcount
            if changed != 1:
                raise RevisionConflict("Ticket changed. Refresh the ticket list and try again.")
        return ticket


    def get_record(self, kind, record_id):
        return self.get(kind, record_id)

    def list_records(self, kind):
        with self.connect() as connection:
            rows = connection.execute("SELECT body FROM records WHERE kind=?", (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def create_record(self, kind, record_id, record):
        with self.connect() as connection:
            inserted = connection.execute("INSERT OR IGNORE INTO records(kind,id,body,revision) VALUES (?,?,?,?)", (kind, record_id, json.dumps(record, allow_nan=False), record.get('revision', 0))).rowcount
        return bool(inserted), self.get_record(kind, record_id)

    def update_record(self, kind, record_id, record, expected_revision):
        with self.connect() as connection:
            changed = connection.execute("UPDATE records SET body=?,revision=? WHERE kind=? AND id=? AND revision=?", (json.dumps(record, allow_nan=False), record['revision'], kind, record_id, expected_revision)).rowcount
        if changed != 1:
            raise RevisionConflict('This record changed. Refresh and try again.')
        return record

    def save_model(self, model_key, artifact):
        self.create_record('model', model_key, {'data': base64.b64encode(artifact).decode(), 'revision': 0})

    def get_model(self, model_key):
        record = self.get_record('model', model_key)
        if record is None:
            raise StorageUnavailable('The saved household model is unavailable.')
        return base64.b64decode(record['data'])


class AwsStore:
    name = "Amazon S3 + DynamoDB"

    def __init__(self, bucket, table_name, region):
        import boto3
        from botocore.config import Config
        self.bucket = bucket
        config = Config(connect_timeout=5, read_timeout=20, retries={"max_attempts": 3})
        self.s3 = boto3.client("s3", region_name=region, config=config)
        self.table = boto3.resource("dynamodb", region_name=region, config=config).Table(table_name)

    def save_analysis(self, analysis):
        try:
            self.s3.put_object(Bucket=self.bucket, Key=f"analyses/{analysis['analysis_id']}.json.gz", Body=gzip.compress(json.dumps(analysis, allow_nan=False).encode()), ContentType="application/json", ContentEncoding="gzip", ServerSideEncryption="AES256")
            self.table.put_item(Item={"pk": f"analysis#{analysis['analysis_id']}", "kind": "analysis", "body": json.dumps({key: analysis[key] for key in ["analysis_id", "household_id", "summary", "model_fingerprint"]}, allow_nan=False)})
        except Exception as error:
            raise StorageUnavailable("AWS storage is unavailable. Check the instance role, bucket, table, and region.") from error

    def get_analysis(self, analysis_id):
        from botocore.exceptions import ClientError
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=f"analyses/{analysis_id}.json.gz")
            with response["Body"] as body:
                return json.loads(gzip.decompress(body.read()))
        except ClientError as error:
            if error.response["Error"]["Code"] in ["NoSuchKey", "404"]:
                return None
            raise StorageUnavailable("Cannot read the saved analysis from S3.") from error

    def create_ticket(self, ticket):
        from botocore.exceptions import ClientError
        try:
            self.table.put_item(Item={"pk": f"ticket#{ticket['ticket_id']}", "kind": "ticket", "body": json.dumps(ticket), "revision": ticket["revision"]}, ConditionExpression="attribute_not_exists(pk)")
            return ticket
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return self.get_ticket(ticket["ticket_id"])
            raise StorageUnavailable("Cannot create the DynamoDB ticket.") from error

    def get_ticket(self, ticket_id):
        try:
            item = self.table.get_item(Key={"pk": f"ticket#{ticket_id}"}, ConsistentRead=True).get("Item")
            return json.loads(item["body"]) if item else None
        except Exception as error:
            raise StorageUnavailable("Cannot read the DynamoDB ticket.") from error

    def list_tickets(self):
        try:
            items = []
            options = {"FilterExpression": "#kind = :kind", "ExpressionAttributeNames": {"#kind": "kind"}, "ExpressionAttributeValues": {":kind": "ticket"}, "ConsistentRead": True}
            while True:
                response = self.table.scan(**options)
                items.extend(json.loads(item["body"]) for item in response.get("Items", []))
                if "LastEvaluatedKey" not in response:
                    break
                options["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            return sorted(items, key=lambda item: item["created_at"], reverse=True)
        except Exception as error:
            raise StorageUnavailable("Cannot list DynamoDB tickets.") from error

    def update_ticket(self, ticket, expected_revision):
        from botocore.exceptions import ClientError
        try:
            self.table.put_item(Item={"pk": f"ticket#{ticket['ticket_id']}", "kind": "ticket", "body": json.dumps(ticket, allow_nan=False), "revision": ticket["revision"]}, ConditionExpression="#revision = :expected", ExpressionAttributeNames={"#revision": "revision"}, ExpressionAttributeValues={":expected": expected_revision})
            return ticket
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise RevisionConflict("Ticket changed. Refresh the ticket list and try again.") from error
            raise StorageUnavailable("Cannot update the DynamoDB ticket.") from error


    def get_record(self, kind, record_id):
        try:
            item = self.table.get_item(Key={'pk': f'{kind}#{record_id}'}, ConsistentRead=True).get('Item')
            return json.loads(item['body']) if item else None
        except Exception as error:
            raise StorageUnavailable('Cannot read the saved AWS record.') from error

    def list_records(self, kind):
        try:
            items = []
            options = {'FilterExpression': '#kind = :kind', 'ExpressionAttributeNames': {'#kind': 'kind'}, 'ExpressionAttributeValues': {':kind': kind}, 'ConsistentRead': True}
            while True:
                response = self.table.scan(**options)
                items.extend(json.loads(item['body']) for item in response.get('Items', []))
                if 'LastEvaluatedKey' not in response:
                    return items
                options['ExclusiveStartKey'] = response['LastEvaluatedKey']
        except Exception as error:
            raise StorageUnavailable('Cannot list saved AWS records.') from error

    def create_record(self, kind, record_id, record):
        from botocore.exceptions import ClientError
        try:
            self.table.put_item(Item={'pk': f'{kind}#{record_id}', 'kind': kind, 'body': json.dumps(record, allow_nan=False), 'revision': record.get('revision', 0)}, ConditionExpression='attribute_not_exists(pk)')
            return True, record
        except ClientError as error:
            if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False, self.get_record(kind, record_id)
            raise StorageUnavailable('Cannot create the AWS record.') from error

    def update_record(self, kind, record_id, record, expected_revision):
        from botocore.exceptions import ClientError
        try:
            self.table.put_item(Item={'pk': f'{kind}#{record_id}', 'kind': kind, 'body': json.dumps(record, allow_nan=False), 'revision': record['revision']}, ConditionExpression='#revision = :expected', ExpressionAttributeNames={'#revision': 'revision'}, ExpressionAttributeValues={':expected': expected_revision})
            return record
        except ClientError as error:
            if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise RevisionConflict('This record changed. Refresh and try again.') from error
            raise StorageUnavailable('Cannot update the AWS record.') from error

    def save_model(self, model_key, artifact):
        try:
            self.s3.put_object(Bucket=self.bucket, Key=f'models/{model_key}.joblib', Body=artifact, ContentType='application/octet-stream', ServerSideEncryption='AES256')
        except Exception as error:
            raise StorageUnavailable('Cannot save the household model in S3.') from error

    def get_model(self, model_key):
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=f'models/{model_key}.joblib')
            with response['Body'] as body:
                return body.read()
        except Exception as error:
            raise StorageUnavailable('Cannot load the household model from S3.') from error


def make_store(root):
    mode = os.getenv("LEAKLENS_STORAGE", "local")
    if mode == "local":
        return LocalStore(os.getenv("LEAKLENS_DB_PATH", str(root / "data" / "app" / "leaklens.sqlite3")))
    if mode != "aws":
        raise RuntimeError("LEAKLENS_STORAGE must be local or aws.")
    bucket = os.getenv("LEAKLENS_BUCKET")
    table = os.getenv("LEAKLENS_TABLE")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not all([bucket, table, region]):
        raise RuntimeError("AWS mode requires LEAKLENS_BUCKET, LEAKLENS_TABLE, and AWS_REGION.")
    return AwsStore(bucket, table, region)
