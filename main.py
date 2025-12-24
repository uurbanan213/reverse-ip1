from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
import httpx
import asyncio
import os

app = FastAPI()

# ----------------------------------------------------
# PROVIDERS
# ----------------------------------------------------

async def yougetsignal(ip):
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            res = await client.post(
                "https://domains.yougetsignal.com/domains.php",
                headers={
                    "content-type":"application/x-www-form-urlencoded",
                    "user-agent":"Mozilla/5.0",
                    "origin":"https://www.yougetsignal.com",
                    "referer":"https://www.yougetsignal.com/tools/web-sites-on-web-server/"
                },
                data=f"remoteAddress={ip}&key=&_"
            )

            if '"status":"Fail"' in res.text:
                return f"[ {ip} ] -> Rate Limit / Blocked"

            js = res.json()
            arr = js.get("domainArray", [])

            if not arr:
                return f"[ {ip} ] -> No Domains"

            domains = "\n".join(d[0] for d in arr)
            return f"[ {ip} ] ({len(arr)} domains)\n{domains}"

    except:
        return f"[ {ip} ] -> Error / Timeout"


async def hackertarget(ip):
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            res = await client.get(
                f"https://api.hackertarget.com/reverseiplookup/?q={ip}"
            )

            txt = res.text

            if "error" in txt.lower() or "No DNS" in txt:
                return f"[ {ip} ] -> No Result"

            return f"[ {ip} ]\n{txt}"

    except:
        return f"[ {ip} ] -> Error"


async def resolve(ip, provider):
    if provider == "yougetsignal":
        return await yougetsignal(ip)

    if provider == "hackertarget":
        return await hackertarget(ip)

    # AUTO MODE
    result = await yougetsignal(ip)
    if "Rate Limit" in result or "Error" in result:
        result = await hackertarget(ip)

    return result


# ----------------------------------------------------
# ROUTES
# ----------------------------------------------------

@app.get("/")
async def home():
    return HTMLResponse(open("index.html","r").read())

@app.post("/scan")
async def scan(request: Request):
    data = await request.json()
    ips = data["ips"]
    provider = data["provider"]

    results = []

    # LIMIT PARALLEL (biar brutal tapi aman)
    sem = asyncio.Semaphore(8)

    async def worker(ip):
        async with sem:
            result = await resolve(ip, provider)
            results.append(result)

    tasks = [worker(ip) for ip in ips]
    await asyncio.gather(*tasks)

    return PlainTextResponse("\n\n".join(results))