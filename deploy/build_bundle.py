"""Package only runtime files; never include keys, the venv, or the raw dataset."""
from pathlib import Path
import json
import zipfile

root = Path(__file__).resolve().parents[1]


def main():
    dist = root / 'frontend/dist'
    if not (dist / 'index.html').exists():
        raise SystemExit('Build the frontend with npm run build first.')
    files = list((root / 'backend').glob('*.py')) + list(dist.rglob('*'))
    files += [root / 'models/isolation_forest.joblib', root / 'models/detection_config.json', root / 'requirements-runtime.txt', root / 'CREDITS.md', root / 'THIRD_PARTY_NOTICES.txt', root / 'LICENSE']
    files = [path for path in files if path.is_file()]
    output = root / 'build'
    output.mkdir(exist_ok=True)
    bundle = output / 'leaklens-deploy.zip'
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root))
    print('Deployment bundle:', bundle)
    print('Size:', round(bundle.stat().st_size / 1024 / 1024, 2), 'MB')
    print('CloudShell upload files: leaklens-deploy.zip, deploy/cloudformation.json, deploy/deploy_aws.sh')
    print(json.dumps({'file_count': len(files), 'raw_dataset_included': False, 'credentials_included': False}))


if __name__ == '__main__':
    main()
