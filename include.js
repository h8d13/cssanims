// Minimal HTML includes: replaces <div data-include="x.html"> with x.html's
// contents, then marks the current page's nav link. Requires HTTP (not file://).
(async () => {
  await Promise.all(
    [...document.querySelectorAll("[data-include]")].map(async (el) => {
      const res = await fetch(el.getAttribute("data-include"));
      el.outerHTML = await res.text();
    })
  );

  const page = location.pathname.split("/").pop() || "index.html";
  const link = document.querySelector(`nav a[href="${page}"]`);
  if (link) link.setAttribute("aria-current", "page");
})();
