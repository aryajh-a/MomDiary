import json, http.cookiejar, urllib.request, urllib.error
BASE = "http://127.0.0.1:8765"
ORIGIN = "http://localhost:5173"
def make_caller():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    def call(method, path, body=None, headers=None, expect=None, label=""):
        data = None
        h = {"Content-Type": "application/json", "Origin": ORIGIN, "Referer": ORIGIN+"/"}
        if headers: h.update(headers)
        if body is not None: data = json.dumps(body).encode()
        req = urllib.request.Request(BASE+path, data=data, method=method, headers=h)
        try:
            r = op.open(req); status = r.status; payload = json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            status = e.code; payload = json.loads(e.read() or b"null")
        ok = expect is None or status == expect
        print(("PASS" if ok else "FAIL"), label, method, path, "->", status, json.dumps(payload)[:220])
        return status, payload
    return call

c1 = make_caller()
c1("POST","/v1/auth/register",{"email":"e2e@example.com","password":"correcthorsebatterystaple","display_name":"E2E"}, expect=201, label="U1.register")
c1("GET","/v1/auth/me", expect=200, label="U1.me-before-baby")
c1("GET","/v1/feeds?date=2025-01-15", expect=409, label="U1.feeds-no-baby")
_, b = c1("POST","/v1/babies",{"display_name":"Baby A","date_of_birth":"2025-01-01"}, expect=201, label="U1.baby-create")
baby_id = b["id"]
_, m = c1("GET","/v1/auth/me", expect=200, label="U1.me-after-baby")
assert m["user"]["active_baby_id"] == baby_id, ("active_baby not auto-set", m)
print("PASS auto-active-baby")
c1("GET","/v1/feeds?date=2025-01-15", expect=200, label="U1.feeds-ok")
c1("GET","/v1/sleeps?date=2025-01-15", expect=200, label="U1.sleeps-ok")
c1("GET","/v1/poops?date=2025-01-15", expect=200, label="U1.poops-ok")
c1("GET","/v1/appointments?date=2025-01-15", expect=200, label="U1.appts-ok")

# Cross-tenant isolation
c2 = make_caller()
c2("POST","/v1/auth/register",{"email":"e2e2@example.com","password":"correcthorsebatterystaple","display_name":"E2E2"}, expect=201, label="U2.register")
# user2 has no active baby of their own; explicitly target U1's baby via header.
c2("GET","/v1/feeds?date=2025-01-15", headers={"X-Active-Baby-Id":str(baby_id)}, expect=404, label="U2.cross-tenant-baby-404")

# Logout U1
c1("POST","/v1/auth/logout", expect=200, label="U1.logout")
c1("GET","/v1/auth/me", expect=401, label="U1.me-after-logout")
print("ALL DONE")
