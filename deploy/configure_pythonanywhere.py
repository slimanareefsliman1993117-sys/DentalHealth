"""Create private configuration for a new deployment, never overwrite an existing one."""
import argparse
import os
from pathlib import Path
import re
import secrets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain',required=True)
    args=parser.parse_args()
    domain=args.domain.strip().lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',domain) or '.' not in domain:
        parser.error('Provide the hostname only, without a scheme, path or port.')
    root=Path(__file__).resolve().parent.parent
    env=root/'.env'
    values={'SECRET_KEY':secrets.token_urlsafe(64),'DEBUG':'False','DB_ENGINE':'sqlite',
            'ALLOWED_HOSTS':domain,'CSRF_TRUSTED_ORIGINS':'https://'+domain,
            'CORS_ALLOWED_ORIGINS':'','TRUST_PROXY_HEADERS':'False'}
    descriptor=os.open(env,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream:
        stream.write(''.join(f'{key}={value}\n' for key,value in values.items()))
    wsgi=(f'import os, sys\nproject = {str(root)!r}\n'
          'if project not in sys.path: sys.path.insert(0, project)\n'
          'os.environ["DJANGO_SETTINGS_MODULE"] = "dentalhealth.settings"\n'
          'from django.core.wsgi import get_wsgi_application\napplication = get_wsgi_application()\n')
    (root/'deploy/wsgi.generated.py').write_text(wsgi)
    print('Private .env created with mode 0600. Persistent signing key generated; no secrets printed.')
    print('WSGI source: '+str(root/'deploy/wsgi.generated.py'))


if __name__=='__main__':
    main()
