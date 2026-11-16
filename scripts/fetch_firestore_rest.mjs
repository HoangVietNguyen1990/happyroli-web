import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const PROJECT_ROOT = path.resolve(import.meta.dirname, '..', '..');
const KEY_PATH = path.join(PROJECT_ROOT, 'app-database-b486e-firebase-adminsdk-fbsvc-913610cd6b.json');
const OUT_FILE = path.join(PROJECT_ROOT, 'happyrolly_web', 'backup_snapshot', 'firestore_live_dump.json');

const sa = JSON.parse(fs.readFileSync(KEY_PATH, 'utf8'));

function base64url(input) {
  return Buffer.from(input).toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

async function getAccessToken() {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: 'RS256', typ: 'JWT' };
  const payload = {
    iss: sa.client_email,
    sub: sa.client_email,
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
    scope: 'https://www.googleapis.com/auth/datastore https://www.googleapis.com/auth/cloud-platform'
  };
  const unsigned = `${base64url(JSON.stringify(header))}.${base64url(JSON.stringify(payload))}`;
  const sign = crypto.createSign('RSA-SHA256');
  sign.update(unsigned);
  const signature = sign.sign(sa.private_key, 'base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
  const jwt = `${unsigned}.${signature}`;

  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion: jwt
    })
  });
  const data = await res.json();
  if (!data.access_token) throw new Error('Token error: ' + JSON.stringify(data));
  return data.access_token;
}

function parseFirestoreValue(v) {
  if (!v || typeof v !== 'object') return v;
  if ('stringValue' in v) return v.stringValue;
  if ('integerValue' in v) return Number(v.integerValue);
  if ('doubleValue' in v) return Number(v.doubleValue);
  if ('booleanValue' in v) return Boolean(v.booleanValue);
  if ('nullValue' in v) return '';
  if ('timestampValue' in v) return v.timestampValue;
  if ('arrayValue' in v) return (v.arrayValue.values || []).map(parseFirestoreValue);
  if ('mapValue' in v) {
    const out = {};
    for (const [k, val] of Object.entries(v.mapValue.fields || {})) {
      out[k] = parseFirestoreValue(val);
    }
    return out;
  }
  return '';
}

function parseFirestoreDoc(doc) {
  const out = {};
  for (const [k, val] of Object.entries(doc.fields || {})) {
    out[k] = parseFirestoreValue(val);
  }
  return out;
}

async function fetchCollection(token, collName) {
  const baseUrl = `https://firestore.googleapis.com/v1/projects/${sa.project_id}/databases/(default)/documents/${encodeURIComponent(collName)}`;
  let docs = [];
  let pageToken = '';
  while (true) {
    const url = pageToken ? `${baseUrl}?pageSize=300&pageToken=${encodeURIComponent(pageToken)}` : `${baseUrl}?pageSize=300`;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) break;
    const data = await res.json();
    for (const d of (data.documents || [])) {
      const id = d.name.split('/').pop();
      docs.push({ _id: id, ...parseFirestoreDoc(d) });
    }
    if (!data.nextPageToken) break;
    pageToken = data.nextPageToken;
  }
  return docs;
}

async function main() {
  const token = await getAccessToken();
  const collections = [
    'employees',
    'unavailability',
    'unavailabilities',
    'staff_unavailability',
    'availability',
    'requirements',
    'fixed',
    'timecards',
    'timecard_records',
    'finalized_rosters',
    'roster_drafts',
    'system'
  ];

  const dump = {};
  for (const c of collections) {
    dump[c] = await fetchCollection(token, c);
    console.log(`Fetched ${c}: ${dump[c].length} doc(s)`);
  }
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify(dump, null, 2), 'utf8');
  console.log('Saved complete live Firestore dump to', OUT_FILE);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
