import os
import subprocess
import sys
import time
import requests
import signal
from pathlib import Path

# Use Playwright for Python

ROOT = Path(__file__).resolve().parents[2]
CLEAN_START = ROOT / 'clean_start.py'

BACKEND_PORT = int(os.getenv('BACKEND_PORT', '8014'))
FRONTEND_PORT = int(os.getenv('FRONTEND_PORT', '3000'))

def start_clean_start():
    python = sys.executable
    cmd = [python, str(CLEAN_START)]
    env = os.environ.copy()
    env['TEST_MODE'] = '1'

    kwargs = {
        'cwd': str(ROOT),
        'env': env,
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE,
        'text': True
    }
    # On Unix, start the process in a new session to become the process group leader.
    # This allows us to kill the entire process group reliably.
    if os.name != 'nt':
        kwargs['preexec_fn'] = os.setsid

    proc = subprocess.Popen(cmd, **kwargs)

    # Stream output in background
    import threading

    def _stream(pipe, prefix):
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                print(f"[{prefix}] {line.rstrip()}")
        except Exception:
            pass

    threading.Thread(target=_stream, args=(proc.stdout, 'STDOUT'), daemon=True).start()
    threading.Thread(target=_stream, args=(proc.stderr, 'STDERR'), daemon=True).start()
    return proc


def wait_for_url(url, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_frontend(hosts=('127.0.0.1', 'localhost'), port=3000, timeout=120):
    """Try multiple hostnames (127.0.0.1 and localhost) and return the URL that worked or None."""
    start = time.time()
    while time.time() - start < timeout:
        for h in hosts:
            url = f'http://{h}:{port}'
            try:
                r = requests.get(url, timeout=3)
                if r.status_code < 500:
                    print(f'Frontend reachable at {url} (status {r.status_code})')
                    return True
            except Exception:
                pass
        time.sleep(1)
    return False


def run_e2e():
    proc = start_clean_start()
    print('Started clean_start.py PID', proc.pid)

    try:
        backend_ok = wait_for_url(f'http://127.0.0.1:{BACKEND_PORT}/api/status', timeout=60)
        if not backend_ok:
            raise RuntimeError('Backend did not become ready within 60s')
        print('Backend is ready')

        # Some dev servers bind to localhost instead of 127.0.0.1; try both.
        frontend_ok = wait_for_frontend(port=FRONTEND_PORT, timeout=120)
        if not frontend_ok:
            raise RuntimeError('Frontend did not become ready within 120s')
        print('Frontend is ready')

        # Start Playwright and open WhatsApp (skip if not available)
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            print('Playwright not available, skipping browser checks:', e)
            sync_playwright = None

        if sync_playwright:
            browser = None
            context = None
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context()
                    page = context.new_page()
                    whatsapp_url = os.getenv('WHATSAPP_URL', 'https://web.whatsapp.com/')
                    page.goto(whatsapp_url, timeout=60000)
                    # Wait for common element that indicates page loaded (QR canvas or sidebar)
                    try:
                        page.wait_for_selector('canvas', timeout=30000)
                    except Exception:
                        # Try sidebar selector
                        page.wait_for_selector('div[role="grid"]', timeout=30000)
                    print('WhatsApp page loaded')

                    # Inject a test message via backend test endpoint
                    inject_payload = {'from_number': '+15551234567', 'message': 'E2E test ping'}
                    inject_res = requests.post(f'http://127.0.0.1:{BACKEND_PORT}/api/test/inject-message', json=inject_payload, timeout=10)
                    if inject_res.status_code != 200:
                        raise RuntimeError(f'Inject endpoint failed: {inject_res.status_code} {inject_res.text}')
                    print('Injected test message')

                    # Poll for messages processed (backend will expose /api/test/messages)
                    start = time.time()
                    received = False
                    while time.time() - start < 30:
                        r = requests.get(f'http://127.0.0.1:{BACKEND_PORT}/api/test/messages', timeout=5)
                        if r.status_code == 200:
                            data = r.json()
                            msgs = data.get('messages', [])
                            if msgs:
                                print('Backend returned messages:', msgs)
                                received = True
                                break
                        time.sleep(1)

                    if not received:
                        raise RuntimeError('No messages processed by backend within 30s')

                    print('E2E flow succeeded')
            finally:
                try:
                    if context:
                        context.close()
                except Exception:
                    pass
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass

    finally:
        print(f"--- E2E test finished, cleaning up process {proc.pid} ---")
        try:
            if os.name == 'nt':
                # On Windows, use taskkill to forcefully terminate the process tree.
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                    check=True, capture_output=True
                )
                print(f"Terminated process tree for PID {proc.pid} using taskkill.")
            else:
                # On Unix, send SIGTERM to the entire process group.
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                print(f"Sent SIGTERM to process group {proc.pid}.")
            proc.wait(timeout=10)
        except Exception as e:
            print(f"Failed to clean up processes gracefully: {e}. Falling back to kill.")
            proc.kill()


if __name__ == '__main__':
    # Ensure test mode
    os.environ['TEST_MODE'] = '1'
    run_e2e()
