const me = document.currentScript;
(async () => {
  const root = me.getAttribute("src").replace(/include\.js$/, "");

  await Promise.all([...document.querySelectorAll("[data-include]")].map(async (el) =>
    (el.outerHTML = await (await fetch(root + el.dataset.include)).text())));

  const file = location.pathname.split("/").pop() || "index.html";
  const onArticle = location.pathname.includes("/articles/");
  document.querySelectorAll(".site-header a").forEach((a) => {
    const h = a.getAttribute("href");
    if (!/^(\/|https?:|#)/.test(h)) a.setAttribute("href", root + h);
    if (a.closest("nav") && (h.endsWith(file) || (onArticle && h.endsWith("articles.html"))))
      a.setAttribute("aria-current", "page");
  });

  const list = document.querySelector("[data-articles]");
  if (list) {
    const dir = new DOMParser().parseFromString(await (await fetch(root + "articles/")).text(), "text/html");
    list.innerHTML = [...dir.querySelectorAll("a")]
      .map((a) => a.getAttribute("href")).filter((h) => h?.endsWith(".html"))
      .map((f) => {
        const slug = f.replace(".html", "");
        return `<a class="article-card" href="${root}articles/${f}">
          <div class="thumb" style="view-transition-name:cover-${slug}"></div>
          <div class="article-meta"><h3>${slug.replace(/-/g, " ")}</h3></div></a>`;
      }).join("");
  }

  const hero = document.querySelector("[data-hero]");
  if (hero) hero.style.viewTransitionName = "cover-" + file.replace(".html", "");
})();
