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

try:
	import markdown
except ImportError:
	raise SystemExit("[build] pip install markdown markdown-callouts")

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


# Articles: front matter (title, lead) hand-parsed, body through the real
# markdown lib. github-callouts turns "> [!NOTE]" blockquotes into
# admonition divs, toc anchors every heading (styled in styles.css).
MD = markdown.Markdown(
	extensions=["github-callouts", "fenced_code", "tables", "toc"])


def _md_parse(path):
	# -> {slug, title, lead, body, secs} where body is the rendered inner
	# HTML with each ## heading's run wrapped in <section class="reveal">,
	# and secs = [(id, name)] feeds the on-page TOC + scroll-spy.
	text = path.read_text()
	meta = {}
	if text.startswith("---\n"):
		fm, _, text = text[4:].partition("\n---\n")
		for ln in fm.splitlines():
			key, _, val = ln.partition(":")
			meta[key.strip()] = val.strip()

	MD.reset()  # per-document state (toc, footnote counters etc.)
	html = MD.convert(text)
	secs = [(t["id"], t["name"]) for t in MD.toc_tokens if t["level"] == 2]

	# Split on rendered h2 boundaries: intro stays bare, each section
	# becomes a scroll-reveal block that also publishes a named
	# view-timeline (--sec-<id>) for the sidebar scroll-spy.
	parts = re.split(r"(?=<h2)", html)
	body = [parts[0].rstrip()] if parts[0].strip() else []
	for part in parts[1:]:
		sid = re.search(r'<h2 id="([^"]+)"', part).group(1)
		body.append(
			'<section class="reveal" style="view-timeline-name: --sec-{}">'
			"\n{}\n</section>".format(sid, part.rstrip()))
	return {"slug": path.stem, "title": meta.get("title", path.stem),
			"lead": meta.get("lead", ""), "body": "\n\n".join(body),
			"secs": secs}


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
# link, hero/header/footer resolve in _bake like any other page. The grid
# flanks the body with two baked sidebars: all articles left, on-page TOC
# right. scope_attr hoists each section's view-timeline up to the article so
# the TOC links (descendants of a different subtree) can animate from them.
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
    <article class="article-full"{scope_attr}>
      <div class="article-hero" data-hero></div>
      <div class="article-grid">
        <aside class="side side-left">
          <nav class="toc">
            <p class="tag">Articles</p>
{artnav}
          </nav>
        </aside>
        <div class="wrap">
          <h1>{title}</h1>
          <p class="lead">{lead}</p>
{body}

          <a class="back" href="../articles.html">All articles</a>
        </div>
        <aside class="side side-right">
{secnav}
        </aside>
      </div>
    </article>
  </main>

  <div data-include="footer.html"></div>
</body>
</html>
"""


def _art_nav(articles, current):
	# Left sidebar: every article, current one marked like the header nav.
	return "\n".join(
		'            <a href="{slug}.html"{cur}>{title}</a>'.format(
			slug=a["slug"], title=a["title"],
			cur=' aria-current="page"' if a["slug"] == current else "")
		for a in articles)


def _sec_nav(secs):
	# Right sidebar: this article's ## sections. Each link subscribes to
	# its section's hoisted view-timeline (inline, ids vary per article);
	# the spy keyframes in styles.css do the highlighting.
	if not secs:
		return ""
	links = ['          <nav class="toc">',
		 '            <p class="tag">On this page</p>']
	for sid, name in secs:
		links.append(
			'            <a href="#{sid}" style="animation-timeline: '
			"--sec-{sid}\">{name}</a>".format(sid=sid, name=name))
	links.append("          </nav>")
	return "\n".join(links)


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
		scope = ' style="timeline-scope: {}"'.format(
			", ".join("--sec-" + s for s, _ in a["secs"])) if a["secs"] else ""
		(DIST / "articles" / (a["slug"] + ".html")).write_text(
			_bake(ARTICLE_SHELL.format(
					title=a["title"], lead=a["lead"], body=a["body"],
					scope_attr=scope, artnav=_art_nav(articles, a["slug"]),
					secnav=_sec_nav(a["secs"])),
				  active="articles.html", prefix="../", articles=articles,
				  hero_slug=a["slug"]))

	pages = len(list(DIST.glob("*.html"))) + len(list((DIST / "articles").glob("*.html")))
	print("[build] {} pages -> {}/ (0 scripts, {} articles)".format(
		pages, DIST.name, len(articles)))


if __name__ == "__main__":
	build()
