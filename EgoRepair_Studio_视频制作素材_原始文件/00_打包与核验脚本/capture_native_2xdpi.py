"""Capture current unmodified UI at browser deviceScaleFactor=2; no media transforms."""
import asyncio, hashlib, json, os, threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path('/home/xklv/ego_robot/a4_experiment')
RUN = Path('/data/xklv_data/a4_experiment/video_materials/20261008T135842_689360Z')
OUT = RUN / 'work/native_2xdpi'
SITE = ROOT / 'deployment_v2/site'

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fonts = ROOT / '.runtime/browser_native_20261005T154753_833839Z/extracted/usr/share/fonts'
    (OUT/'fonts.conf').write_text(f'<fontconfig><dir>{fonts}</dir><cachedir>{OUT}/font-cache</cachedir></fontconfig>')
    os.environ['FONTCONFIG_FILE'] = str(OUT/'fonts.conf')
    for key, sub in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
        os.environ[key] = str(OUT/sub)
    os.environ['TMPDIR'] = str(ROOT/'.runtime/bt')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(SITE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    errors=[]; bad=[]; records=[]
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=str(ROOT/'.runtime/browsers/chromium-1243/chrome-linux64/chrome'), headless=True, args=['--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width':1600,'height':1150}, device_scale_factor=2)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('response', lambda r: bad.append({'status':r.status,'url':r.url}) if r.status>=400 else None)
        response=await page.goto(url, wait_until='domcontentloaded')
        site_sha=hashlib.sha256(await response.body()).hexdigest()
        assert site_sha==hashlib.sha256((SITE/'index.html').read_bytes()).hexdigest()
        await page.wait_for_function("document.querySelectorAll('.rp-step').length===8 && document.querySelectorAll('.wf-node').length===8")
        await page.locator('#btnDemo').click()
        print('Started existing example UI playback; static local site only.',flush=True)
        await page.wait_for_function("document.querySelector('#runStatus').textContent==='已完成'", timeout=200000)
        for name,index in [('M2_多智能体协作',2),('M4_轨迹修复',4),('M5_审计',5),('M6_物理回放',6),('M7_机器人轨迹',7)]:
            await page.locator('.wf-node').nth(index).click()
            if index==4: await page.locator('.rp-step').nth(5).click()
            await page.wait_for_timeout(7000 if index in [4,6] else 2400)
            locator=page.locator('#repair' if index==4 else '.workflow-section')
            await locator.scroll_into_view_if_needed()
            path=OUT/(name+'.png')
            await locator.screenshot(path=str(path), animations='disabled')
            records.append({'source':str(path),'dest':'P1/Studio_新2xDPI截图/'+path.name,'priority':'P1','category':'studio_native_2xdpi','status':'NATIVE_BROWSER_CAPTURE','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'captured_at':datetime.now(timezone.utc).isoformat(),'deviceScaleFactor':2,'viewport':{'width':1600,'height':1150},'ui_module':name,'source_site':str(SITE),'site_index_sha256':site_sha,'site_mutation':False,'semantics':'当前Studio原有示例数据与记录播放界面；不是实时推理或同一episode端到端物理成功。'})
            print(name+' captured',flush=True)
        result={'records':records,'source_url':url,'pageerrors':errors,'bad_responses':bad,'external_network_used':False,'dom_data_mutated':False}
        (OUT/'CaptureManifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        await browser.close()
    server.shutdown()

if __name__=='__main__': asyncio.run(main())
