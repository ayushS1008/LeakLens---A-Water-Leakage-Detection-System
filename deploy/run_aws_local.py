"""Launch the local website with explicit AWS storage settings, not shell exports."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError


ENV_KEYS = ('AWS_PROFILE', 'AWS_REGION', 'LEAKLENS_BUCKET', 'LEAKLENS_TABLE',
            'LEAKLENS_EMAIL_FROM', 'LEAKLENS_EMAIL_TO', 'LEAKLENS_PUBLIC_URL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check AWS access without starting the website.')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    settings_path = root / '.aws' / 'leaklens-local.json'
    try:
        settings = json.loads(settings_path.read_text())
    except (OSError, ValueError) as error:
        print(f'Cannot read local AWS settings at {settings_path}: {error}', file=sys.stderr)
        return 1
    if not shutil.which('aws'):
        print('Install AWS CLI v2 and reopen your terminal.', file=sys.stderr)
        return 1
    for key in ('AWS_ACCOUNT_ID', 'AWS_APP_USER', 'AWS_PROFILE', 'AWS_REGION', 'LEAKLENS_BUCKET', 'LEAKLENS_TABLE'):
        if not isinstance(settings.get(key), str) or not settings[key].strip():
            print(f'Missing {key} in local AWS settings.', file=sys.stderr)
            return 1
    if not (root / 'frontend' / 'dist' / 'index.html').is_file():
        print('Build the website first: run npm run build inside frontend.', file=sys.stderr)
        return 1
    env = os.environ.copy()
    # A named short-term profile must take precedence over unrelated shell keys.
    for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
                'AWS_SECURITY_TOKEN', 'AWS_DEFAULT_PROFILE'):
        env.pop(key, None)
    for key in ENV_KEYS:
        env.pop(key, None)
        if settings.get(key):
            env[key] = settings[key]
    env['LEAKLENS_STORAGE'] = 'aws'
    try:
        session = boto3.Session(profile_name=settings['AWS_PROFILE'], region_name=settings['AWS_REGION'])
        identity = session.client('sts').get_caller_identity()
        if identity['Account'] != settings['AWS_ACCOUNT_ID']:
            print('AWS profile belongs to a different account. Check the selected login.', file=sys.stderr)
            return 1
        expected_arn = f"arn:aws:iam::{settings['AWS_ACCOUNT_ID']}:user/{settings['AWS_APP_USER']}"
        if identity['Arn'] != expected_arn:
            print('AWS profile must use the limited app IAM user, not root. Sign in as ' + settings['AWS_APP_USER'] + '.', file=sys.stderr)
            return 1
        session.client('dynamodb').get_item(TableName=settings['LEAKLENS_TABLE'],
            Key={'pk': {'S': 'healthcheck#leaklens'}}, ConsistentRead=True)
    except (BotoCoreError, ClientError) as error:
        print(f'AWS access check failed: {error}', file=sys.stderr)
        print('Renew the browser login for the source profile documented in deploy/AWS_LOCAL.md.', file=sys.stderr)
        return 1
    print(f'AWS connection checked: {settings["AWS_REGION"]}; storage: Amazon S3 + DynamoDB.', flush=True)
    if args.check:
        return 0
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', args.port)) == 0:
            print(f'Port {args.port} is occupied. Stop the old backend with Ctrl+C first.', file=sys.stderr)
            return 1
    print(f'Open http://127.0.0.1:{args.port}/#/', flush=True)
    try:
        return subprocess.call([sys.executable, '-m', 'uvicorn', 'backend.main:app',
            '--host', '127.0.0.1', '--port', str(args.port)], cwd=root, env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())
