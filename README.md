# Pretalx Scripts Collection

This repository contains a collection of Python scripts for various tasks of a programme committee of a conference managed with Pretalx.


## Pretalx PC Renderer

This script renders LaTeX templates for abstracts and/or ratings of submissions. This collection currently comes with

* cards.tex, a template for cards (4 cards per A4 page) with average scores and snippets of reviewers' comments to be used on a meeting of the programme selection committee
* abstracts.tex, a very basic template to generate a PDF with descriptions and abstracts of all submissions

These two templates require LuaLaTeX for compilation.

Preatlx PC Renderer is able to filter the submissions by type, status and track before it fills out the template. For further details about Pretalx PC Renderer, call `python3 pretalx_pc_renderer.py --help`.


## Pretalx Pretix Comparison

This tool compares ticket sales by Pretix (it uses the JSON export) with a list of speakers obtained using the Pretalx API.


## Pretalx JSON to CSV Converter

Generate CSV files with accepted/confirmed submissions and their scheduled slots for mass mailings to speakers.


## [Review Analysis](review_analysis/README.md)

Plot some statistics about reviews using Matplotlib.


## License

See [LICENSE.txt](LICENSE.txt).
