import os
import unittest

from hydra import Checker, Config, Parser, extract_domain

HTMLDATA = os.path.join(os.path.dirname(__file__), "data/test-page.html")
CONFIGDATA = os.path.join(os.path.dirname(__file__), "data/basic_config.json")


class TestCases(unittest.TestCase):
    # Open and close file from data/
    def setUp(self):
        self.testfile = open(HTMLDATA)
        self.data = self.testfile.read()
        self.url = "https://example.com"
        self.check = Checker(self.url, Config())
        self.parser = Parser(Config())

    def tearDown(self):
        self.testfile.close()

    # Parser gives expected values
    def test_parser_expected_output(self):
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

    # Checker uses correct domain for comparison
    def test_domain_extraction(self):
        self.assertEqual(extract_domain(self.url), "example.com")

    # Checker doesn't add visited links to queue
    def test_process_queue_length(self):
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

    def test_read_config_without_file(self):
        # Arrange

        # Act
        results = Config()

        # Assert
        expected = """tags: ['a', 'link', 'img', 'script']
attrs: ['href', 'src']
exclude_scheme_prefixes = ['tel:', 'javascript:']
threads = 50
timeout = 60
OK = [200, 999]"""
        self.assertEqual(str(results), expected)

    def test_read_config_with_valid_config_file(self):
        # Arrange

        # Act
        results = Config(CONFIGDATA)

        # Assert
        expected = """tags: ['a']
attrs: ['href']
exclude_scheme_prefixes = []
threads = 25
timeout = 30
OK = [200, 999]"""
        self.assertEqual(str(results), expected)


if __name__ == "__main__":
    unittest.main()
