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

## Test

Run:

```sh
python -m unittest tests/test.py
```
