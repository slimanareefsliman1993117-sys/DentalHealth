"""Build and validate the source archive in a fresh disposable Python environment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

source = Path(__file__).resolve().parent.parent
archive = source.parent / 'pythonanywhere-upload/dentalhealth-pythonanywhere.zip'
report_path = source / 'validation/deployment-checks.json'
private_paths = [source / '.env', source / 'db.sqlite3']
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in private_paths if p.exists()}


def run(args, root, env, *, code=None, succeeds=True):
    result = subprocess.run(args, cwd=root, env=env, text=True, input=code, capture_output=True)
    if succeeds and result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args)) + '\n' + result.stdout + result.stderr)
    return result


def main():
    subprocess.run([sys.executable, 'deploy/build_package.py'], cwd=source, check=True)
    env = os.environ.copy()
    for key in ['SECRET_KEY', 'DEBUG', 'DB_ENGINE', 'SQLITE_PATH', 'DJANGO_SETTINGS_MODULE', 'ALLOWED_HOSTS',
                'CSRF_TRUSTED_ORIGINS', 'CORS_ALLOWED_ORIGINS', 'TRUST_PROXY_HEADERS', 'ADMIN_TIME_ZONE',
                'PUBLIC_DEMO_ENABLED', 'PUBLIC_DEMO_EMAIL', 'PUBLIC_DEMO_PASSWORD', 'DEMO_SQLITE_PATH']:
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='dental-release-') as folder:
        with ZipFile(archive) as upload:
            names = upload.namelist()
            assert upload.testzip() is None
            assert all(name.startswith('dentalhealth/') and '..' not in Path(name).parts for name in names)
            assert not any(name.endswith('/.env') or '.sqlite3' in name or '/.local/' in name or '/media/' in name
                           or '/.venv/' in name or '/validation/' in name for name in names)
            upload.extractall(folder)
        root = Path(folder) / 'dentalhealth'
        python = root / '.venv/bin/python'
        run(['uv', 'venv', '--python', sys.executable, str(root / '.venv')], root, env)
        run(['uv', 'pip', 'sync', '--python', str(python), 'requirements.txt'], root, env)
        run(['uv', 'pip', 'check', '--python', str(python)], root, env)
        run([str(python), 'deploy/configure_pythonanywhere.py', '--domain', 'release-validation.example.test'], root, env)
        original = (root / '.env').read_bytes()
        refused = run([str(python), 'deploy/configure_pythonanywhere.py', '--domain', 'different.example.test'], root, env, succeeds=False)
        assert refused.returncode != 0 and (root / '.env').read_bytes() == original
        run([str(python), 'manage.py', 'migrate', '--noinput'], root, env)
        run([str(python), 'manage.py', 'makemigrations', '--check', '--dry-run'], root, env)
        run([str(python), 'manage.py', 'collectstatic', '--noinput'], root, env)
        run([str(python), 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'], root, env)
        scenario = run([str(python), '-'], root, env, code=(source / 'validation/production_scenario.py').read_text())
        results = json.loads(scenario.stdout)
        demo_env = {**env, 'PUBLIC_DEMO_ENABLED': 'True', 'PUBLIC_DEMO_PASSWORD': 'Synthetic-Public-Preview-924!'}
        (root / '.local').mkdir(mode=0o700)
        run([str(python), 'manage.py', 'migrate', '--database', 'demo', '--noinput'], root, demo_env)
        run([str(python), 'manage.py', 'setup_public_demo'], root, demo_env)
        demo = run([str(python), '-'], root, demo_env, code=(source / 'validation/demo_production_scenario.py').read_text())
        results.update(json.loads(demo.stdout))
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in private_paths if p.exists()}
    results.update(fresh_virtualenv='passed', pinned_dependencies='compatible', fresh_migrations='passed',
                   migration_consistency='passed', production_checks='passed', static_collection='passed',
                   private_env_mode='0o600', existing_environment_overwrite_refused=True,
                   source_database_and_environment_unchanged=True, preview_data_excluded=True,
                   archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    report_path.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
