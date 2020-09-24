import gzip
import json
import sys
from concurrent import futures
from html.parser import HTMLParser
from http.client import IncompleteRead, InvalidURL
from os import path
from queue import Empty, Queue
from socket import timeout as SocketTimeoutError
from urllib import error, parse, request


class Config:
    def __init__(self, config_filename=""):
        self.tags = ["a", "link", "img", "script"]
        self.attrs = ["href", "src"]
        self.exclude_scheme_prefixes = ["tel:"]
        self.threads = 50
        self.timeout = 60
        self.OK = [200, 999]

        if config_filename != "":
            with open(config_filename, "r") as file:
                file_text = file.read()
                config_json = json.loads(file_text)
                self.tags = config_json.get("tags", self.tags)
                self.attrs = config_json.get("attrs", self.attrs)
                self.exclude_scheme_prefixes = config_json.get(
                    "exclude_scheme_prefixes", self.exclude_scheme_prefixes
                )
                self.threads = config_json.get("threads", self.threads)
                self.timeout = config_json.get("timeout", self.timeout)
                self.OK = config_json.get("OK", self.OK)

    def __str__(self):
        text = f"""tags: {self.tags}
attrs: {self.attrs}
exclude_scheme_prefixes = {self.exclude_scheme_prefixes}
threads = {self.threads}
timeout = {self.timeout}
OK = {self.OK}"""
        return text


class Parser(HTMLParser):
    def __init__(self, config):
        super(Parser, self).__init__()
        self.links = []
        self.config = config

    def handle_starttag(self, tag, attrs):
        if tag not in self.config.tags:
            return
        for a in attrs:
            if a[0] in self.config.attrs:
                exclude_list = [
                    e for e in self.config.exclude_scheme_prefixes if a[1].startswith(e)
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

    def __init__(self, url, config):
        self.config = config
        self.broken = []
        self.domain = extract_domain(url)
        self.visited = set()
        self.mailto_links = list()
        self.pool = futures.ThreadPoolExecutor(max_workers=self.config.threads)
        self.report = ""

    def add_entry(self, code, reason, page):
        if code in self.config.OK:
            return
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
            http_response = request.urlopen(r, timeout=self.config.timeout)

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
            parser = Parser(self.config)
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
                    job = self.pool.submit(
                        self.load_url, target_url, self.config.timeout
                    )
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

    config_file_name = ""
    if len(sys.argv) == 3:
        config_file_name = sys.argv[2]
        if not path.exists(config_file_name):
            print(f"can't find {config_file_name} as config file")
            sys.exit(1)
    config = Config(config_file_name)

    check = Checker(url, config)
    check.TO_PROCESS.put(first_url)
    check.run()
    print(check.make_report())

    if check.broken:
        sys.exit(1)


if __name__ == "__main__":
    main()
