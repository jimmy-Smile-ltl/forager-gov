# -*- coding: utf-8 -*-
"""P195 渲染子进程: 单次渲染一个 URL, 输出渲染后 HTML 到 stdout。
子进程隔离——渲染器的 DrissionPage 收尾异常不会拖垮主采集进程。
用法: python data/p195_render_one.py <url>"""
import sys, os, time, subprocess, httpx

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "util"))


def main():
    url = sys.argv[1]
    sys.stderr.write(f"[child] start pid={os.getpid()} url={url!r}\n")
    sys.stderr.flush()
    port = 9556 + (os.getpid() % 300)
    prof = f"/tmp/p195r_{port}"
    dbg = os.environ.get("P195_DEBUG")
    tr = None
    if dbg:
        tr = open(f"/tmp/p195r_trace_{os.getpid()}.log", "a")
        tr.write(f"start url={url} port={port}\n")
        tr.flush()
    def trace(msg):
        if tr:
            tr.write(msg + "\n")
            tr.flush()
    chrome_err = open(f"/tmp/p195r_chromeerr_{port}.log", "ab")
    proc = subprocess.Popen(
        [PROJECT_CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
         # 规避「Chromium Safe Storage」钥匙串弹窗（用户指令 2026-11-12）
         "--use-mock-keychain", "--password-store=basic",
         f"--remote-debugging-port={port}", f"--user-data-dir={prof}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=chrome_err,
        start_new_session=True)   # 独立进程组: 收尾按组杀, Helper 子进程不带
                                   # user-data-dir/端口 flags, 按串 pkill 全漏网
    trace(f"chrome spawned pid={proc.pid} chrome_alive={proc.poll() is None}")

    def _kill_tree():
        """2026-11-12: 按进程组整树杀——Chromium Helper 子进程命令行不带
        user-data-dir/端口 flags, 旧 pkill 按串只杀到主进程, 每次渲染漏 9-10 个
        Helper 孤儿（实测累计 102 个, 8GB 内存被压满）。"""
        try:
            import signal as _sig
            os.killpg(os.getpgid(proc.pid), _sig.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        subprocess.Popen(f"pkill -9 -f {prof}", shell=True)
        subprocess.Popen(f"pkill -9 -f remote-debugging-port={port}", shell=True)
    # 诊断看门狗: 每 1s 采样 Chrome 存活与调试端口应答, 定位「启动后即死」时刻
    import threading as _th
    def _watch():
        for _ in range(45):
            time.sleep(1)
            alive = proc.poll() is None
            try:
                r2 = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=1)
                ans = f"http{r2.status_code}"
            except Exception as e:
                ans = type(e).__name__
            trace(f"[watch] chrome_alive={alive} port_ans={ans}")
            if not alive:
                break
    _th.Thread(target=_watch, daemon=True).start()
    try:
        ws = None
        for i in range(20):
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=2)
                if r.status_code == 200:
                    ws = r.json()["webSocketDebuggerUrl"]
                    trace(f"ws ok at poll {i}")
                    break
            except Exception:
                pass
            time.sleep(1)
        if not ws:
            trace("ws fail after 20 polls")
            sys.stderr.write(f"[child] port {port} /json/version 20 次未通, "
                             f"chrome_alive={proc.poll() is None}, "
                             f"dbg={os.environ.get('P195_DEBUG')!r}\n")
            sys.stderr.flush()
            return 1
        # 2026-11-12 修复: Chrome 冷启动后渲染器未就绪, DrissionPage 连接即断
        # （PageDisconnectedError 于 ChromiumPage 构造期）。预热 3s + 连接重试 3 次
        time.sleep(3)
        from DrissionPage import ChromiumPage
        from DrissionPage.errors import PageDisconnectedError as _PDE
        page = None
        for _try in range(3):
            try:
                page = ChromiumPage(addr_or_opts=ws)
                break
            except _PDE:
                trace(f"drission 连接断开 重试 {_try}")
                time.sleep(4)
        if page is None:
            trace("drission 3 次连接失败")
            return 1
        trace("drission connected")
        try:
            # 2026-11-13: 梅州等门户加载慢, page.get 默认超时取 DOM 报
            # TimeoutError(DOM.getOuterHTML)——显式放宽到 45s
            page.get(url, timeout=45)
            trace("page.get done")
            time.sleep(6)
            # 2026-11-13 梅州形态: 县区导航藏在 tab 面板（点击「县市区/区县」
            # 类 tab 才展开, 渲染初始 DOM 未激活 → 提取漏掉全部县区链接）。
            # 自动点击含县市区类关键词的短文本可点击元素, 展开面板再取 DOM。
            try:
                page.run_js("""
                (()=>{const kws=['县市区','区县','县区','各县','区县导航','县市区政府'];
                  const els=[...document.querySelectorAll('a,li,button,span,div')].filter(e=>{
                    const t=(e.textContent||'').trim();
                    return t.length>0&&t.length<12&&kws.some(k=>t.includes(k));
                  }).slice(0,8);
                  els.forEach(e=>{try{e.click()}catch(x){}});
                  return els.length;})()
                """)
                time.sleep(2.5)
                trace("tab click done")
            except Exception as _e:
                trace(f"tab click 异常 {type(_e).__name__}: {str(_e)[:80]}")
            html = page.html or ""
            trace(f"page.html len={len(html)} url={page.url!r}")
            sys.stderr.write(f"[child] page.html len={len(html)} url={page.url!r}\n")
            sys.stderr.flush()
            sys.stdout.write(html)
            sys.stdout.flush()
            return 0
        except Exception as e:
            trace(f"page.get 异常 {type(e).__name__}: {str(e)[:100]}")
            sys.stderr.write(f"[child] page.get 异常 {type(e).__name__}: {str(e)[:100]}\n")
            sys.stderr.flush()
            return 1
    except BaseException as e:
        # 2026-11-12 关键修复: 旧版 finally 里无条件 os._exit(0) 把 traceback 吞掉
        # （硬退出不打印异常、rc 恒 0）——DrissionPage 连接/导入异常从此不可见,
        # 表现为「渲染成功但空输出」的假失败。先落盘 traceback 再硬退。
        import traceback as _tb
        msg = f"[child] 异常 {type(e).__name__}: {str(e)[:200]}\n" + _tb.format_exc()
        try:
            sys.stderr.write(msg)
            sys.stderr.flush()
        except Exception:
            pass
        trace("EXCEPTION " + msg[:400])
        _kill_tree()
        os._exit(1)
    finally:
        trace("finally begin")
        _kill_tree()
        os._exit(0)   # 硬退出, 不等 DrissionPage 线程收尾（其 ws 断连异常曾拖垮主进程）


if __name__ == "__main__":
    import glob as _g
    from util.browser_lifecycle import PROJECT_CHROME
    # 2026-11-12 关键修复: PROJECT_CHROME 默认解析为 playwright Chrome for
    # Testing(com.google.Chrome.forTesting) — 与 college teacher 项目常驻 CfT
    # 同 bundle ID, macOS 单例 rendezvous 拒收新实例(mach_port_rendezvous
    # Permission denied 1100 → "No rendezvous client, terminating process"),
    # Chrome 启动 3-5s 后自杀, 渲染必然失败。CloakBrowser(org.chromium.
    # Chromium) 独立 bundle ID, 无此冲突, 优先使用。
    _cb = ""
    for _p in sorted(_g.glob(os.path.expanduser(
            "~/.cloakbrowser/chromium-*/Chromium.app/Contents/MacOS/Chromium"))):
        if os.path.exists(_p):
            _cb = _p
            break
    PROJECT_CHROME = _cb or PROJECT_CHROME
    sys.exit(main())
