#!/usr/bin/env python3
"""Run the website's browser checks under a GitHub-style project subdirectory."""
import argparse
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time

import build_site


class Results(HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.status = None; self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'pre' and attrs.get('id') == 'results':
            self.active = True; self.status = attrs.get('data-status')

    def handle_endtag(self, tag):
        if tag == 'pre': self.active = False

    def handle_data(self, text):
        if self.active: self.text.append(text)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-prose', action='store_true', help='also run prose checks using the locally generated Python oracle')
    parser.add_argument('--chrome', help='Chrome/Chromium executable')
    args = parser.parse_args()
    chrome = args.chrome or next((p for p in (shutil.which('google-chrome'), shutil.which('chromium'),
                                           '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') if p and Path(p).exists()), None)
    if not chrome: raise SystemExit('Install Chrome/Chromium or pass --chrome /path/to/browser')
    files = {name: (build_site.SOURCE / name).read_bytes() for name in build_site.PUBLIC_FILES}
    build_site.validate(files)
    suites = ['workbench'] + (['prose'] if args.with_prose else [])
    for suite in suites:
        for name in ('checks.html', 'checks.js'):
            files[suite + '/' + name] = (build_site.SOURCE / suite / name).read_bytes()
    files['workbench/checks-oracle.json'] = (build_site.SOURCE / 'workbench/checks-oracle.json').read_bytes()
    if args.with_prose: files['prose/test-oracle.json'] = (build_site.ROOT / 'build/prose-editor-oracle.json').read_bytes()
    with tempfile.TemporaryDirectory(prefix='shiren-site-check-') as directory:
        root = Path(directory)
        for name, payload in files.items():
            path = root / 'project' / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            for suite in suites:
                output = root / (suite + '.html'); log = root / (suite + '.log')
                command = [chrome, '--headless', '--disable-gpu', '--disable-background-networking', '--disable-component-update',
                           '--disable-sync', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
                           '--user-data-dir=' + str(root / (suite + '-profile')), '--window-size=1440,1100',
                           '--virtual-time-budget=50000', '--dump-dom', f'http://127.0.0.1:{server.server_port}/project/{suite}/checks.html']
                with output.open('w') as out, log.open('w') as err:
                    process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
                    try:
                        deadline = time.monotonic() + 60
                        while time.monotonic() < deadline and process.poll() is None:
                            if output.stat().st_size and '</html>' in output.read_text(): break
                            time.sleep(.2)
                    finally:
                        if process.poll() is None:
                            try: os.killpg(process.pid, signal.SIGTERM)
                            except ProcessLookupError: pass
                        process.wait(timeout=10)
                result = Results(); result.feed(output.read_text()); report = ''.join(result.text)
                print(f'{suite}: {report}', flush=True)
                # The existing prose suite predates the data-status attribute.
                prose_pass = False
                if suite == 'prose':
                    try:
                        old_result = json.loads(report)
                        prose_pass = old_result.get('status') == 'PASS' and old_result.get('checks', 0) > 0
                    except ValueError: pass
                if result.status != 'passed' and not prose_pass:
                    raise SystemExit('Browser checks failed. ' + (report or log.read_text()[-2000:]))
        finally: server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__': main()
