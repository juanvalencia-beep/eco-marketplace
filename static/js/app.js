// Navigation: each page is a <section id="page-NAME">, chosen by the URL hash (#orders, #reports...).
// This file loads last, so every load function from the other files already exists.

const pages = {
  dashboard: loadDashboard,
  orders: loadOrdersPage,
  reports: loadReportsPage,
  customers: loadCustomers,
  stores: loadStores,
  products: loadProducts,
  inventory: loadInventoryPage,
};

function currentPage() {
  const name = location.hash.slice(1);
  return pages[name] ? name : "dashboard";
}

function showPage(moveFocus) {
  const name = currentPage();
  let title = "";
  $$(".page").forEach((page) => {
    const active = page.id === "page-" + name;
    page.hidden = !active;
    if (active) title = page.dataset.title;
  });
  $$(".nav a").forEach((link) => {
    if (link.dataset.page === name) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${title} | Eco-Marketplace Admin`;
  closeNav();
  window.scrollTo(0, 0);
  // after clicking a link, move keyboard focus to the new page heading
  if (moveFocus) $(`#page-${name} h1`).focus({ preventScroll: true });
  pages[name]();
}

window.addEventListener("hashchange", () => showPage(true));

/* ---------- mobile navigation drawer ---------- */

function openNav() {
  document.body.classList.add("nav-open");
  $("#scrim").hidden = false;
  $("#nav-toggle").setAttribute("aria-expanded", "true");
  $("#nav-toggle").setAttribute("aria-label", "Close navigation");
  $(".nav a").focus();
}

function closeNav() {
  if (!document.body.classList.contains("nav-open")) return;
  document.body.classList.remove("nav-open");
  $("#scrim").hidden = true;
  $("#nav-toggle").setAttribute("aria-expanded", "false");
  $("#nav-toggle").setAttribute("aria-label", "Open navigation");
}

$("#nav-toggle").addEventListener("click", () => {
  if (document.body.classList.contains("nav-open")) closeNav();
  else openNav();
});
$("#scrim").addEventListener("click", closeNav);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.body.classList.contains("nav-open")) {
    closeNav();
    $("#nav-toggle").focus();
  }
});
// clicking the current page link again still closes the drawer
$(".nav").addEventListener("click", closeNav);

showPage(false);
