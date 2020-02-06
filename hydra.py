from concurrent import futures
from html.parser import HTMLParser
from queue import Queue, Empty
from urllib import error, parse, request
import gzip
import sys


class Parser(HTMLParser):
    # Tags to check
    TAGS = ["a", "link", "img", "script"]
    # Valid attributes to check
    ATTRS = ["href", "src"]

    def __init__(self):
        super(Parser, self).__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            return
        for a in attrs:
            if a[0] in self.ATTRS:
                self.links.append(a[1])

    def feed_me(self, data):
        self.links = []
        self.feed(data)
        return self.links

    def error(self, msg):
        return msg


class Checker:
    TO_PROCESS = Queue()
    # Maximum workers to run
    THREADS = 20
    # Maximum seconds to wait for HTTP response
    TIMEOUT = 60

    def __init__(self, url):
        self.broken = []
        self.domain = self.extract_domain(url)
        self.visited = set()
        self.pool = futures.ThreadPoolExecutor(max_workers=self.THREADS)

    def extract_domain(self, l):
        domain = parse.urlsplit(l).netloc
        return domain

    # Try to retreive contents of a page and record result
    def load_url(self, page, timeout):
        # Store the link to be checked and its parent in the result
        result = {
            "url": page["url"],
            "parent": page["parent"],
            "data": "",
            "content_type": "",
        }

        # Use GET as HEAD is frequently not allowed
        r = request.Request(
            page["url"],
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0"
            },
        )

        try:
            http_response = request.urlopen(r, timeout=self.TIMEOUT)
            encoding = http_response.headers.get("Content-Encoding")
            content_type = http_response.headers.get("Content-Type")
            if encoding and "gzip" in encoding:
                data = gzip.decompress(http_response.read()).decode(
                    encoding="utf-8", errors="ignore"
                )
            elif encoding is None:
                data = http_response.read().decode(encoding="utf-8", errors="ignore")
            else:
                # Support for other less common directives not handled
                raise NotImplementedError

            result["data"] = data
            result["content_type"] = content_type

        except error.HTTPError as e:
            code = e.getcode()
            reason = e.reason
            entry = {
                "code": code,
                "link": page["url"],
                "parent": page["parent"],
                "err": reason,
            }
            self.broken.append(entry)
        except (
            error.URLError,
            UnicodeEncodeError,
            UnicodeDecodeError,
            NotImplementedError,
        ) as e:
            code = 0
            reason = e

            entry = {
                "code": code,
                "link": page["url"],
                "parent": page["parent"],
                "err": reason,
            }
            self.broken.append(entry)

        return result

    def handle_future(self, result):
        if result.result():
            page = result.result()
            self.parse_page(page)

    # Get more links from successfully retrieved pages in the same domain
    def parse_page(self, page):
        if (
            self.domain == self.extract_domain(page["url"])
            and "text/html" in page["content_type"]
            or "text/plain" in page["content_type"]
        ):
            parent = page["url"]
            parser = Parser()
            links = parser.feed_me(page["data"])
            new_links = [x for x in links if x not in self.visited]
            full_links = [parse.urljoin(parent, l) for l in new_links]
            for l in full_links:
                if l not in self.visited:
                    li = {"parent": parent, "url": l}
                    self.TO_PROCESS.put(li)

    # Parse broken links list into YAML report
    def report(self):
        self.report = "---\ntitle: Broken Link Report"
        self.report += "\nchecked: " + str(len(self.visited))
        self.report += "\nbroken: " + str(len(self.broken))
        self.report += "\n---\n"
        sorted_list = sorted(self.broken, key=lambda k: k["code"])
        for link in sorted_list:
            self.report += f"\n- code:    {link['code']}\n  url:     {link['link']}\n  parent:  {link['parent']}\n  error:   {link['err']}\n"
        return self.report

    # Run crawler until TO_PROCESS queue is empty
    def run(self):
        while True:
            try:
                target_url = self.TO_PROCESS.get(block=True, timeout=self.TIMEOUT + 5)
                if target_url["url"] not in self.visited:
                    self.visited.add(target_url["url"])
                    job = self.pool.submit(self.load_url, target_url, self.TIMEOUT)
                    job.add_done_callback(self.handle_future)
            except Empty:
                return
            except Exception as e:
                print(e)
                continue


if __name__ == "__main__":
    url = sys.argv[1]
    first_url = {"parent": url, "url": url}

    check = Checker(url)
    check.TO_PROCESS.put(first_url)
    check.run()
    print(check.report())
