#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
URL="$(portal_url | sed 's#/portal/$##')"
set -a; source .env; set +a
python3 - "$URL" "${ADMIN_EMAIL:-admin@localhost}" "${ADMIN_PASSWORD:-ChangeThisBeforeUse123!}" <<'PY'
import json, sys, urllib.request, http.cookiejar
base,email,password=sys.argv[1:4]; jar=http.cookiejar.CookieJar(); opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def call(path, method='GET', data=None):
    headers={'Content-Type':'application/json'}
    if method!='GET':
        csrf=next((c.value for c in jar if c.name=='smp_csrf'),''); headers['X-CSRF-Token']=csrf
    req=urllib.request.Request(base+'/api'+path, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
    return json.load(opener.open(req))
try:
    call('/auth/bootstrap','POST',{})
except Exception:
    call('/auth/login','POST',{'email':email,'password':password})
print(json.dumps(call('/workflows/demo','POST',{}),indent=2))
PY
