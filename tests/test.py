import functools
import http.server
import os
import socketserver
import tempfile
import threading
import time
import unittest

from hydra import Checker, Config, Parser, extract_domain

HTMLDATA = os.path.join(os.path.dirname(__file__), "data/test-page.html")
CONFIGDATA = os.path.join(os.path.dirname(__file__), "data/basic_config.json")


class TestCases(unittest.TestCase):
    """Open and close file from data/"""

    def setUp(self):
        self.testfile = open(HTMLDATA)
        self.data = self.testfile.read()
        self.url = "https://example.com"
        self.check = Checker(self.url, Config())
        self.parser = Parser(Config())

    def tearDown(self):
        self.testfile.close()

    def test_parser_expected_output(self):
        """ Parser gives expected values"""
        links = self.parser.feed_me(self.data)
        expected_output = [
            "style.css",
            "scripts.js",
            "http://baddomain.com/i-donut-exist",
            "image.png",
            "www.anotherbaddomain.com/multithreading-is-fun",
            "https://example.com/i-have-links",
            "https://example.com",
        ]
        self.assertEqual(links, expected_output)

    def test_domain_extraction(self):
        """Checker uses correct domain for comparison"""
        self.assertEqual(extract_domain(self.url), "example.com")

    def test_process_queue_length(self):
        """Checker doesn't add visited links to queue"""
        self.pagedata = {
            "url": "https://example.com/test-page.html",
            "parent": "https://example.com/test-page.html",
            "data": """
                <!DOCTYPE html>\n
                <html>\n\n
                <head>\n
                    <title>Test Data Page</title>\n\n
                    <meta charset="utf-8">\n
                    <meta http-equiv="Content-type" content="text/html; charset=UTF-8">\n
                    <meta name="viewport" content="width=device-width, initial-scale=1">\n
                    <link rel="stylesheet" href="style.css" type="text/css">\n
                    <script type="text/javascript" src="scripts.js"></script>\n
                </head>\n\n
                <body>\n
                    <div>\n
                        <h1>Test Data Page</h1>\n
                        <p>This page does not exist: <a href="/i-donut-exist">Whale</a></p>\n
                        <p>This is not a link: <a>No Spoon</a></p>\n
                        <img src="image.png" />\n
                        <p>This page does not exist: <a href="/multithreading-is-fun">Petunias</a></p>\n
                        <p>This page contains more links: <a href="/i-have-links">Crawl Me</a></p>\n
                        <p>This domain is for use in illustrative examples in documents. You may use this\n
                            domain in literature without prior coordination or asking for permission:
                            <a href="https://example.com">Example</a>
                        </p>\n
                     </div>\n\n\n
                </body>\n
                </html>'
            """,
            "valid_content_type": True,
        }
        # There are 7 links in pagedata["data"]
        first_parse = 7
        self.check.parse_page(self.pagedata)
        self.assertEqual(len(self.check.TO_PROCESS.queue), first_parse)
        self.check.visited.add("https://example.com/style.css")
        # Checker should add to queue all but the one visited link
        second_parse = 13
        self.check.parse_page(self.pagedata)
        self.assertEqual(len(self.check.TO_PROCESS.queue), second_parse)

    def test_run_visits_all_links_despite_lulls(self):
        """run() drains the whole site even when jobs finish slowly.

        Regression test for inconsistent results: the crawler must not stop
        while a worker is still in flight. Each fake fetch sleeps, so the
        queue goes empty while a job is pending; only the pending-job guard
        keeps the crawl going until every page is visited.
        """
        check = Checker("https://example.com", Config())
        # The work queue is shared across Checker instances, so isolate it.
        with check.TO_PROCESS.mutex:
            check.TO_PROCESS.queue.clear()

        pages = {
            "https://example.com": '<a href="https://example.com/a">a</a>',
            "https://example.com/a": '<a href="https://example.com/b">b</a>',
            "https://example.com/b": "<p>no more links</p>",
        }

        def fake_load_url(page, timeout):
            time.sleep(0.05)  # simulate latency so the queue empties mid-flight
            return {
                "url": page["url"],
                "parent": page["parent"],
                "data": pages.get(page["url"], ""),
                "valid_content_type": True,
            }

        check.load_url = fake_load_url
        check.TO_PROCESS.put(
            {"parent": "https://example.com", "url": "https://example.com"}
        )
        check.run()

        self.assertEqual(
            check.visited,
            {
                "https://example.com",
                "https://example.com/a",
                "https://example.com/b",
            },
        )

    def test_end_to_end_crawl_over_http(self):
        """Crawl a real site served on localhost, end to end.

        The other tests call parse_page directly and never make a request, so
        the urllib fetch, response handling, and the run() queue/thread loop go
        unexercised. Serve a tiny fixture site and assert Hydra crawls the good
        pages and reports exactly the one broken link. Self-contained: binds to
        127.0.0.1 on an ephemeral port, so it needs no internet access.
        """
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "index.html"), "w") as f:
            f.write('<a href="page2.html">ok</a><a href="missing.html">broken</a>')
        with open(os.path.join(tmpdir, "page2.html"), "w") as f:
            f.write('<a href="index.html">home</a>')

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass  # keep test output clean

        handler = functools.partial(QuietHandler, directory=tmpdir)
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            url = f"http://127.0.0.1:{port}/"
            check = Checker(url, Config())
            # TO_PROCESS is shared across Checker instances; start from empty.
            with check.TO_PROCESS.mutex:
                check.TO_PROCESS.queue.clear()
            check.TO_PROCESS.put({"parent": url, "url": url})
            check.run()
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(
            len(check.broken), 1, f"expected one broken link, got {check.broken}"
        )
        self.assertEqual(check.broken[0]["code"], 404)
        self.assertTrue(check.broken[0]["link"].endswith("/missing.html"))
        # The seed page and the good internal page were both crawled.
        self.assertGreaterEqual(len(check.visited), 2)

    def test_read_config_without_file(self):
        # Arrange

        # Act
        results = Config()

        # Assert
        expected = (
            f"tags: ['a', 'link', 'img', 'script']"
            f"attrs: ['href', 'src']"
            f"exclude_scheme_prefixes = ['tel:', 'javascript:']"
            f"threads = 50"
            f"timeout = 60"
            f"OK = [200, 999]"
        )
        self.assertEqual(str(results), expected)

    def test_read_config_with_valid_config_file(self):
        # Arrange

        # Act
        results = Config(CONFIGDATA)

        # Assert
        expected = (
            f"tags: ['a', 'img']"
            f"attrs: ['href']"
            f"exclude_scheme_prefixes = ['tel']"
            f"threads = 25"
            f"timeout = 30"
            f"OK = [200, 999, 403]"
        )
        self.assertEqual(str(results), expected)


if __name__ == "__main__":
    unittest.main()
