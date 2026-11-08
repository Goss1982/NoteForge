#!/usr/bin/env python3
"""Create local deployment settings without printing secrets or overwriting .env."""
import argparse
import secrets
from pathlib import Path
from urllib.parse import urlsplit

parser = argparse.ArgumentParser(description='Create NoteForge deployment settings.')
parser.add_argument('--url', required=True, help='Exact browser origin, e.g. https://notes.example.com')
parser.add_argument('--http', action='store_true', help='Allow HTTP cookies for a local LAN deployment')
parser.add_argument('--bind', default='127.0.0.1', choices=['127.0.0.1', '0.0.0.0'])
args = parser.parse_args()
url = urlsplit(args.url)
if url.scheme not in ('https', 'http') or not url.hostname or url.path not in ('','/') or url.query or url.fragment or url.username:
    parser.error('--url must be a valid HTTP(S) origin with no path, credentials, query or fragment')
if url.scheme == 'http' and not args.http:
    parser.error('Use HTTPS, or pass --http for a local HTTP deployment')
root = Path(__file__).resolve().parent.parent
target = root / '.env'
if target.exists():
    parser.error('.env already exists; edit it explicitly instead of overwriting credentials')
text = (root / '.env.example').read_text()
text = text.replace('replace-with-a-long-url-safe-random-value', secrets.token_urlsafe(32))
text = text.replace('replace-with-a-unique-password-at-least-12-characters', secrets.token_urlsafe(24))
text = text.replace('replace-with-at-least-32-random-characters', secrets.token_urlsafe(48))
text = text.replace('PUBLIC_URL=http://localhost:3000', 'PUBLIC_URL='+args.url.rstrip('/'))
text = text.replace('COOKIE_SECURE=false', 'COOKIE_SECURE='+str(url.scheme=='https').lower())
text = text.replace('WEB_BIND=127.0.0.1', 'WEB_BIND='+args.bind)
with target.open('x') as out:
    target.chmod(0o600)
    out.write(text)
print('Created .env with unique credentials. Read ADMIN_PASSWORD there to sign in. Add your AI key before deployment.')
