"""Build an explicit source-only PythonAnywhere upload; omit credentials and patient files."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,json
root=Path(__file__).resolve().parent.parent
out=root.parent/'pythonanywhere-upload'
out.mkdir(exist_ok=True)
archive=out/'dentalhealth-pythonanywhere.zip'
files=[root/name for name in ('manage.py','requirements.in','requirements.txt','.env.example','.gitignore','SETUP.txt','API.md')]
for folder in ['accounts','dentalhealth','templates','static','deploy']:
    files.extend(p for p in (root/folder).rglob('*') if p.is_file())
files=sorted({p for p in files if '__pycache__' not in p.parts and p.suffix not in {'.pyc','.sqlite3','.zip','.log'}
              and p.name not in {'tests.py','wsgi.generated.py','deployment-status.json'}})
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for p in files:z.write(p,'dentalhealth/'+p.relative_to(root).as_posix())
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(not n.endswith('/.env') and '/media/' not in n and '/.venv/' not in n and '.sqlite3' not in n for n in z.namelist())
manifest={'archive':archive.name,'files':len(files),'bytes':archive.stat().st_size,
          'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'includes_credentials':False,'includes_patient_data':False}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
print(archive)
