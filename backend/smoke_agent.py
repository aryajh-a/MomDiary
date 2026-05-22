import json, http.cookiejar, urllib.request, urllib.error
BASE = "http://127.0.0.1:8765"
ORIGIN = "http://localhost:5173"
def caller():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    def call(method, path, body=None, headers=None, expect=None, label=""):
        data = None
        h = {"Content-Type":"application/json","Origin":ORIGIN,"Referer":ORIGIN+"/"}
        if headers: h.update(headers)
        if body is not None: data = json.dumps(body).encode()
        req = urllib.request.Request(BASE+path, data=data, method=method, headers=h)
        try:
            r = op.open(req); status = r.status; payload = json.loads(r.read() or b"null")
            sess = r.headers.get("X-Session-ID")
        except urllib.error.HTTPError as e:
            status = e.code; payload = json.loads(e.read() or b"null"); sess=None
        ok = expect is None or status == expect
        print(("PASS" if ok else "FAIL"), label, method, path, "->", status, "sess=", (sess or "")[:8], json.dumps(payload)[:240])
        return status, payload, sess
    return call

c = caller()
c("POST","/v1/auth/register",{"email":"agent@example.com","password":"correcthorsebatterystaple","display_name":"AG"}, expect=201, label="register")
_,b1,_ = c("POST","/v1/babies",{"display_name":"Baby One","date_of_birth":"2025-01-01"}, expect=201, label="baby1")
baby1 = b1["id"]
# Agent write under baby1
_,e1,s1 = c("POST","/v1/entries",{"message":"fed her 60ml formula at 2025-01-15T08:00:00Z"}, expect=200, label="entry-baby1")
print("entry1 outcome:", e1.get("outcome"))
_,f1,_ = c("GET","/v1/feeds?date=2025-01-15", expect=200, label="feeds-baby1")
print("feeds-baby1 count:", len(f1) if isinstance(f1,list) else len(f1.get("items",[])))
# Second baby
_,b2,_ = c("POST","/v1/babies",{"display_name":"Baby Two","date_of_birth":"2025-01-02"}, expect=201, label="baby2")
baby2 = b2["id"]
c("POST","/v1/users/me/active-baby",{"baby_id":baby2}, expect=200, label="switch-to-baby2")
# Agent write under baby2 — re-use session id from baby1 (should be rejected as cross-partition and a new session minted)
_,e2,s2 = c("POST","/v1/entries",{"message":"fed her 90ml formula at 2025-01-15T10:00:00Z"}, headers={"X-Session-ID": s1 or ""}, expect=200, label="entry-baby2-with-old-sid")
assert s2 and s2 != s1, ("session not re-partitioned", s1, s2)
print("PASS session-partition-isolation")
_,f2,_ = c("GET","/v1/feeds?date=2025-01-15", expect=200, label="feeds-baby2")
items2 = f2 if isinstance(f2,list) else f2.get("items",[])
print("feeds-baby2 count:", len(items2))
assert len(items2) == 1, ("baby2 should see only its 1 feed", items2)
# Switch back to baby1 and confirm baby1 still has exactly 1 feed (no cross-write)
c("POST","/v1/users/me/active-baby",{"baby_id":baby1}, expect=200, label="switch-back-to-baby1")
_,f1b,_ = c("GET","/v1/feeds?date=2025-01-15", expect=200, label="feeds-baby1-after")
items1b = f1b if isinstance(f1b,list) else f1b.get("items",[])
print("feeds-baby1-after count:", len(items1b))
assert len(items1b) == 1, ("baby1 should still have 1 feed", items1b)
print("PASS data-isolation")
print("ALL DONE")
