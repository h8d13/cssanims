#!/usr/bin/env python3
# Static-site builder: bake the data-include / data-articles / data-hero hooks
# that include.js resolved at runtime into plain HTML at build time. Output in
# dist/ ships ZERO JavaScript; the cross-document view transitions are pure CSS
# (@view-transition in styles.css) and keep working. Articles are markdown in
# articles/*.md (front matter: title, lead), ordered by articles.json -- edit
# it, drop in a .md, re-run.
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
ARTICLES = json.loads((ROOT / "articles.json").read_text())  # ["article-1.md", ...]

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


# Markdown subset the articles use: front matter (title, lead), ## sections
# (become <section class="reveal">), blank-line paragraphs, and inline
# **bold** / *em* / `code` / [text](url). Anything fancier: extend here.

def _md_inline(text):
	text = (text.replace("&", "&amp;").replace("<", "&lt;")
			.replace(">", "&gt;"))
	text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
	text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
	text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
	text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
	return text


def _md_parse(path):
	# -> {slug, title, lead, body} where body is the baked inner HTML
	# (intro <p>s, then one <section class="reveal"> per ## heading).
	lines = path.read_text().splitlines()
	meta = {}
	if lines and lines[0] == "---":
		end = lines.index("---", 1)
		for ln in lines[1:end]:
			key, _, val = ln.partition(":")
			meta[key.strip()] = val.strip()
		lines = lines[end + 1:]

	out, para, in_section = [], [], False

	def flush():
		if para:
			out.append("        <p>{}</p>".format(
				_md_inline("\n          ".join(para))))
			para.clear()

	for ln in lines:
		if ln.startswith("## "):
			flush()
			if in_section:
				out.append("        </section>")
			out.append('\n        <section class="reveal">')
			out.append("          <h2>{}</h2>".format(_md_inline(ln[3:])))
			in_section = True
		elif ln.strip():
			para.append(ln.strip())
		else:
			flush()
	flush()
	if in_section:
		out.append("        </section>")

	return {"slug": path.stem, "title": meta.get("title", path.stem),
			"lead": meta.get("lead", ""), "body": "\n".join(out)}


def _article_cards(articles):
	# The data-articles grid, baked from the parsed markdown. Each thumb
	# carries the view-transition-name pairing with its article hero (the
	# morph effect); card titles come from front matter.
	cards = []
	for a in articles:
		cards.append(
			'<a class="article-card" href="articles/{slug}.html">\n'
			'        <div class="thumb" style="view-transition-name:cover-{slug}"></div>\n'
			'        <div class="article-meta"><h3>{title}</h3></div></a>'.format(
				slug=a["slug"], title=a["title"]))
	return "\n        ".join(cards)


# The HTML shell every article bakes into; body slots between lead and back
# link, hero/header/footer resolve in _bake like any other page.
ARTICLE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <link rel="stylesheet" href="../styles.css" />
</head>
<body>
  <div data-include="header.html"></div>

  <main>
    <article class="article-full">
      <div class="article-hero" data-hero></div>
      <div class="wrap">
        <h1>{title}</h1>
        <p class="lead">{lead}</p>
{body}

        <a class="back" href="../articles.html">All articles</a>
      </div>
    </article>
  </main>

  <div data-include="footer.html"></div>
</body>
</html>
"""


def _bake(html, *, active, prefix, articles, hero_slug=None):
	# data-include -> partial contents
	html = html.replace('<div data-include="header.html"></div>',
						 _header(active, prefix))
	html = html.replace('<div data-include="footer.html"></div>', FOOTER)
	# data-articles -> static grid
	html = re.sub(r'<section class="articles" data-articles>\s*</section>',
				  '<section class="articles">\n        {}\n      </section>'.format(
					  _article_cards(articles)), html)
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

	articles = [_md_parse(ROOT / "articles" / f) for f in ARTICLES]

	# Top-level pages: active nav = own filename; no depth prefix.
	for p in ROOT.glob("*.html"):
		if p.name in PARTIALS:
			continue
		(DIST / p.name).write_text(
			_bake(p.read_text(), active=p.name, prefix="", articles=articles))

	# Article pages live one level down: prefix nav with ../, active = articles.
	for a in articles:
		(DIST / "articles" / (a["slug"] + ".html")).write_text(
			_bake(ARTICLE_SHELL.format(**a), active="articles.html",
				  prefix="../", articles=articles, hero_slug=a["slug"]))

	pages = len(list(DIST.glob("*.html"))) + len(list((DIST / "articles").glob("*.html")))
	print("[build] {} pages -> {}/ (0 scripts, {} articles)".format(
		pages, DIST.name, len(articles)))


if __name__ == "__main__":
	build()
