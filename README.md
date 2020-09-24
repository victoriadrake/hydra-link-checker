# Hydra: multithreaded site-crawling link checker in Python

![Tests status badge](https://github.com/victoriadrake/hydra-link-checker/workflows/test/badge.svg)

A Python program that ~~crawls~~ slithers 🐍 a website for links and prints a YAML report of broken links.

## Requires

Python 3.6 or higher.

There are no external dependencies, Neo.

## Usage

Run in a terminal:

```sh
python hydra.py [URL]
```

Ensure `URL` is an absolute url including schema, i.e. `https://example.com`.

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

## Configuration
Hydra can accept a JSON configuration file for specific parameters:

```
{
    "timeout": 30,
    "tags": [
        "a", "img"
    ],
    "attrs": [
        "href"
    ],
    "exclude_scheme_prefixes": ["tel"],
    "threads": 25,
    "OK": [
        200,
        999
    ]
}
```

To use a configuration file, supply the filename as the command line argument after the URL:

```
python hydra.py https://example.com my_config.json
```

Possible settings:
* timeout - Maximum seconds to wait for HTTP response. Defaults to 60
* tags - HTML tags to check for links. Defaults to ["a", "link", "img", "script"]
* attr - Attributes of the HTML tags to check for links. Defaults to ["href", "src"]
* exclude_scheme_prefixes - HTTP scheme prefixes to exclude from checking. Defaults to ["tel:"]
* threads - Maximum workers to run. Defaults to 50.
* OK - HTTP response codes to consider as a successful link check. Defaults to [200, 999]

## Test

Run:

```sh
python -m unittest tests/test.py
```
