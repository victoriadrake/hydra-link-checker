# Hydra: multithreaded site-crawling link checker in Python

![Tests status badge](https://github.com/victoriadrake/hydra-link-checker/workflows/test/badge.svg)

A Python program that ~~crawls~~ slithers 🐍 a website for links and prints a YAML report of broken links.

## Requires

Python 3.6 or higher.

There are no external dependencies, Neo.

## Usage

```sh
$ python hydra.py -h
usage: hydra.py [-h] [--config CONFIG] URL
```

Positional arguments:

- `URL`: The URL of the website to crawl. Ensure `URL` is absolute including schema, e.g. `https://example.com`.

Optional arguments:

- `-h`, `--help`: Show help message and exit
- `--config CONFIG`, `-c CONFIG`: Path to a configuration file

A broken links report will be output to stdout, so you may like to redirect this to a file.

The report will be [YAML](https://yaml.org/) formatted. To save the output to a file, run:

```sh
python hydra.py [URL] > [PATH/TO/FILE.yaml]
```

You can add the current date to the filename using a command substitution, such as:

```sh
python hydra.py [URL] > /path/to/$(date '+%Y_%m_%d')_report.yaml
```

To see how long Hydra takes to check your site, add `time`:

```sh
time python hydra.py [URL]
```

### GitHub Action

You can easily incorporate Hydra as part of an automated process using the [link-snitch](https://github.com/victoriadrake/link-snitch) action.

## Configuration

Hydra can accept an optional JSON configuration file for specific parameters, for example:

```json
{
    "OK": [
        200,
        999,
        403
    ],
    "attrs": [
        "href"
    ],
    "exclude_scheme_prefixes": [
        "tel"
    ],
    "tags": [
        "a",
        "img"
    ],
    "threads": 25,
    "timeout": 30,
    "graceful_exit": "True"
}
```

To use a configuration file, supply the filename:

```sh
python hydra.py https://example.com --config ./hydra-config.json
```

Possible settings:

- `OK` - [HTTP response codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status) to consider as a successful link check. Defaults to `[200, 999]`.
- `attrs` - Attributes of the HTML tags to check for links. Defaults to `["href", "src"]`.
- `exclude_scheme_prefixes` - HTTP scheme prefixes to exclude from checking. Defaults to `["tel:", "javascript:"]`.
- `tags` - HTML tags to check for links. Defaults to `["a", "link", "img", "script"]`.
- `threads` - Maximum workers to run. Defaults to `50`.
- `timeout` - Maximum seconds to wait for HTTP response. Defaults to `60`.
- `graceful_exit` - If set to `True`, and there are broken links present return `exit code 0` else return `exit code 1`.

## Test

Run:

```sh
python -m unittest tests/test.py
```
