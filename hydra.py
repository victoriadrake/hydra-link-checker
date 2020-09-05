import gzip
import sys
from concurrent import futures
from html.parser import HTMLParser
from http.client import IncompleteRead, InvalidURL
from queue import Queue, Empty
from socket import timeout as SocketTimeoutError
from urllib import error, parse, request


class Parser(HTMLParser):
    # Tags to check
    TAGS = ["a", "link", "img", "script"]
    # Valid attributes to check
    ATTRS = ["href", "src"]
    # Protocols to exclude
    EXCLUDE_SCHEME_PREFIXES = ["tel:"]

    def __init__(self):
        super(Parser, self).__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            return
        for a in attrs:
            if a[0] in self.ATTRS:
                exclude_list = [
                    e for e in self.EXCLUDE_SCHEME_PREFIXES if a[1].startswith(e)
                ]
                if len(exclude_list) > 0:
                    return
                self.links.append(a[1])

    def feed_me(self, data):
        self.links = []
        self.feed(data)
        return self.links

    def error(self, msg):
        return msg


def extract_domain(link):
    domain = parse.urlsplit(link).netloc
    return domain


class Checker:
    TO_PROCESS = Queue()
    # Maximum workers to run
    THREADS = 50
    # Maximum seconds to wait for HTTP response
    TIMEOUT = 60

    def __init__(self, url):
        self.broken = []
        self.domain = extract_domain(url)
        self.visited = set()
        self.mailto_links = list()
        self.pool = futures.ThreadPoolExecutor(max_workers=self.THREADS)
        self.report = ""

    def add_entry(self, code, reason, page):
        code = code
        reason = reason
        entry = {
            "code": code,
            "link": page["url"],
            "parent": page["parent"],
            "err": reason,
        }
        self.broken.append(entry)

    # Try to retrieve contents of a page and record result
    def load_url(self, page, timeout):
        # Store the link to be checked and its parent in the result
        result = {
            "url": page["url"],
            "parent": page["parent"],
            "data": "",
            "valid_content_type": False,
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

            content_type = http_response.headers.get("Content-Type")
            if (
                content_type is not None
                and "text/html" in content_type
                or "text/plain" in content_type
            ):
                valid_content_type = True
            else:
                valid_content_type = False
            result["valid_content_type"] = valid_content_type

        except error.HTTPError as e:
            code = e.getcode()
            reason = e.reason
            self.add_entry(code, reason, page)
            return
        except (
            error.URLError,
            ConnectionRefusedError,
            ConnectionResetError,
            IncompleteRead,
            InvalidURL,
            NotImplementedError,
            SocketTimeoutError,
            TimeoutError,
            TypeError,
            UnicodeEncodeError,
            UnicodeDecodeError,
        ) as e:
            code = 0
            reason = e
            self.add_entry(code, reason, page)
            return
        except TimeoutError as e:
            code = 408
            reason = e
            self.add_entry(code, reason, page)
            return

        return result

    def handle_future(self, result):
        if result.result():
            page = result.result()
            self.parse_page(page)

    # Get more links from successfully retrieved pages in the same domain
    def parse_page(self, page):
        if self.domain == extract_domain(page["url"]) and page["valid_content_type"]:
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
    def make_report(self):
        self.report = "---\ntitle: Broken Link Report"
        self.report += "\nchecked: " + str(len(self.visited))
        self.report += "\nnumber of email links: " + str(len(self.mailto_links))
        self.report += "\nemails: " + ", ".join(
            [str(m) for m in set(self.mailto_links)]
        )
        self.report += "\nbroken: " + str(len(self.broken))
        self.report += "\n---\n"
        sorted_list = sorted(self.broken, key=lambda k: k["code"], reverse=True)
        for link in sorted_list:
            self.report += f"\n- code:    {link['code']}\n  url:     {link['link']}\n  parent:  {link['parent']}\n  error:   {link['err']}\n"
        return self.report

    # Run crawler until TO_PROCESS queue is empty
    def run(self):
        while True:
            try:
                target_url = self.TO_PROCESS.get(block=True, timeout=4)
                if target_url["url"].startswith("mailto:"):
                    email = target_url["url"][len("mailto:") :]
                    self.mailto_links.append(email)

                elif target_url["url"] not in self.visited:
                    self.visited.add(target_url["url"])
                    job = self.pool.submit(self.load_url, target_url, self.TIMEOUT)
                    job.add_done_callback(self.handle_future)
            except Empty:
                return
            except Exception as e:
                print(e)


def main():
    if len(sys.argv) == 1:
        print("url missing as a sh parameter")
        sys.exit(1)

    url = sys.argv[1]
    first_url = {"parent": url, "url": url}

    check = Checker(url)
    check.TO_PROCESS.put(first_url)
    check.run()
    print(check.make_report())

    if check.broken:
        sys.exit(1)


if __name__ == "__main__":
    main()
