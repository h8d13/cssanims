#!/usr/bin/env python3
# Static-site builder: bake the data-include / data-articles / data-hero hooks
# that include.js resolved at runtime into plain HTML at build time. Output in
# dist/ ships ZERO JavaScript; the cross-document view transitions are pure CSS
# (@view-transition in styles.css) and keep working. "Dynamic articles" stays
# data-driven via articles.json -- edit it, drop in an article page, re-run.
#
#   ./build.py            -> dist/
#
# Why a build step: a static host (GitHub Pages) can't fetch JSON and render a
# list without JS, and doesn't support server-side includes. Build time is the
# only place the templating can happen while runtime stays JS-free.
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"

HEADER = (ROOT / "header.html").read_text()
FOOTER = (ROOT / "footer.html").read_text()
ARTICLES = json.loads((ROOT / "articles.json").read_text())  # ["article-1.html", ...]

# Pages to build: every top-level .html that isn't a partial, plus articles/.
PARTIALS = {"header.html", "footer.html"}


def _rel(href):
	# Relative link (not absolute / external / anchor) -> needs depth prefixing.
	return not re.match(r"^(/|https?:|#|mailto:)", href)


def _header(active, prefix):
	# Resolve the header partial for one page: depth-prefix relative hrefs and
	# mark the active nav link with aria-current (the JS-free active state).
	def fix(m):
		href = m.group(1)
		new = prefix + href if _rel(href) else href
		cur = ' aria-current="page"' if href == active else ""
		return 'href="{}"{}'.format(new, cur)
	return re.sub(r'href="([^"]+)"', fix, HEADER)


def _article_cards():
	# The data-articles grid, baked from articles.json. Each thumb carries the
	# view-transition-name that pairs with its article hero (the morph effect).
	cards = []
	for f in ARTICLES:
		slug = f[:-5] if f.endswith(".html") else f  # article-1
		cards.append(
			'<a class="article-card" href="articles/{f}">\n'
			'        <div class="thumb" style="view-transition-name:cover-{slug}"></div>\n'
			'        <div class="article-meta"><h3>{title}</h3></div></a>'.format(
				f=f, slug=slug, title=slug.replace("-", " ")))
	return "\n        ".join(cards)


def _bake(html, *, active, prefix, hero_slug=None):
	# data-include -> partial contents
	html = html.replace('<div data-include="header.html"></div>',
						 _header(active, prefix))
	html = html.replace('<div data-include="footer.html"></div>', FOOTER)
	# data-articles -> static grid
	html = re.sub(r'<section class="articles" data-articles>\s*</section>',
				  '<section class="articles">\n        {}\n      </section>'.format(
					  _article_cards()), html)
	# data-hero -> hero with its own view-transition-name baked in
	if hero_slug:
		html = html.replace(
			'<div class="article-hero" data-hero></div>',
			'<div class="article-hero" style="view-transition-name:cover-{}"></div>'.format(
				hero_slug))
	# Drop the script tag entirely -- runtime is now JS-free.
	html = re.sub(r'\s*<script src="[^"]*include\.js"></script>', "", html)
	return html


def build():
	if DIST.exists():
		shutil.rmtree(DIST)
	(DIST / "articles").mkdir(parents=True)
	shutil.copy(ROOT / "styles.css", DIST / "styles.css")

	# Top-level pages: active nav = own filename; no depth prefix.
	for p in ROOT.glob("*.html"):
		if p.name in PARTIALS:
			continue
		(DIST / p.name).write_text(
			_bake(p.read_text(), active=p.name, prefix=""))

	# Article pages live one level down: prefix nav with ../, active = articles.
	for p in (ROOT / "articles").glob("*.html"):
		slug = p.stem  # article-1
		(DIST / "articles" / p.name).write_text(
			_bake(p.read_text(), active="articles.html", prefix="../",
				  hero_slug=slug))

	pages = len(list(DIST.glob("*.html"))) + len(list((DIST / "articles").glob("*.html")))
	print("[build] {} pages -> {}/ (0 scripts, {} articles)".format(
		pages, DIST.name, len(ARTICLES)))


if __name__ == "__main__":
	build()
