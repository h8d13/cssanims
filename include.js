// Shared partials + nav state + auto-built article list. Needs HTTP, not file://.
(async () => {
  // Inject <div data-include="/header.html"> etc.
  await Promise.all([...document.querySelectorAll("[data-include]")].map(async (el) =>
    (el.outerHTML = await (await fetch(el.dataset.include)).text())));

  // Mark the current nav link.
  const here = location.pathname;
  document.querySelectorAll("nav a").forEach((a) => {
    const base = new URL(a.href).pathname.replace(/(index)?\.html$/, "");
    if (here === a.getAttribute("href") || (base !== "/" && here.startsWith(base)))
      a.setAttribute("aria-current", "page");
  });

  // Build the list from every .html in /articles/, each thumb named for its zoom.
  const list = document.querySelector("[data-articles]");
  if (list) {
    const dir = new DOMParser().parseFromString(await (await fetch("/articles/")).text(), "text/html");
    list.innerHTML = [...dir.querySelectorAll("a")]
      .map((a) => a.getAttribute("href")).filter((h) => h?.endsWith(".html"))
      .map((f) => {
        const slug = f.replace(".html", "");
        return `<a class="article-card" href="/articles/${f}">
          <div class="thumb" style="view-transition-name:cover-${slug}"></div>
          <div class="article-meta"><h3>${slug.replace(/-/g, " ")}</h3></div></a>`;
      }).join("");
  }

  // On an article page, name the hero so its thumbnail zooms into it.
  const hero = document.querySelector("[data-hero]");
  if (hero) hero.style.viewTransitionName = "cover-" + location.pathname.split("/").pop().replace(".html", "");
})();
