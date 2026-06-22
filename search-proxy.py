#!/usr/bin/env python3
"""Simple search proxy using Bing, works from China. Exposes SearXNG-compatible API."""
import json, subprocess, sys, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

class SearchHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self.path.startswith('/search'):
            self.send_error(404); return
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        query = qs.get('q', [''])[0]
        fmt = qs.get('format', ['html'])[0]

        if not query:
            self.send_error(400); return

        results = self._search_bing(query)

        if fmt == 'json':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({
                "query": query,
                "results": results,
                "unresponsive_engines": []
            }, ensure_ascii=False).encode())
        else:
            html = f"<h1>Search: {query}</h1><ul>"
            for r in results:
                html += f'<li><a href="{r["url"]}">{r["title"]}</a><p>{r.get("content","")[:200]}</p></li>'
            html += "</ul>"
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode())

    def _search_bing(self, query):
        encoded = urllib.parse.quote(query)
        url = f"https://www.bing.com/search?q={encoded}&setlang=zh-cn"
        try:
            r = subprocess.run(
                ['curl', '-sL', '--max-time', '8',
                 '-H', 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                 url],
                capture_output=True, text=True, timeout=10
            )
            html = r.stdout
            results = []
            # Simple extraction of search results
            import re
            # Match Bing result blocks
            blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
            for block in blocks[:8]:
                link_match = re.search(r'<a[^>]*href="(https?://[^"]+)"', block)
                title_match = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
                snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
                if link_match and title_match:
                    results.append({
                        "title": re.sub(r'<[^>]+>', '', title_match.group(1)).strip(),
                        "url": link_match.group(1),
                        "content": re.sub(r'<[^>]+>', '', snippet_match.group(1) if snippet_match else '').strip()[:300],
                        "engine": "bing"
                    })
            return results
        except Exception as e:
            return [{"title": f"Search error: {e}", "url": "", "content": "", "engine": "error"}]

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8889
    print(f"Search proxy on http://localhost:{port}/search?q=<query>&format=json")
    HTTPServer(('127.0.0.1', port), SearchHandler).serve_forever()
