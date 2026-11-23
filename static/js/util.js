// Helpers shared by every page script: DOM shortcuts, formatting, toasts,
// dialogs, loading/empty states, CSV export and the shared lookup lists.

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const LOW_STOCK = 10; // same threshold the API uses for /inventario/stock-bajo
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- escaping and formatting ---------- */

// Every value that comes from the database goes through esc() before it is put in HTML.
function esc(value) {
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value ?? "").replace(/[&<>"']/g, (c) => map[c]);
}

const moneyFormat = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function money(value) {
  return moneyFormat.format(Number(value) || 0);
}

// Short money for chart axes: $1.2k instead of $1,200.00
function moneyShort(value) {
  const n = Number(value) || 0;
  if (Math.abs(n) >= 1000) return "$" + (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1) + "k";
  return "$" + (Number.isInteger(n) ? n : n.toFixed(2));
}

// Quantities have up to 2 decimals (liters, kg...)
function qty(value) {
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function int(value) {
  return Math.round(Number(value) || 0).toLocaleString("en-US");
}

// "2026-11-21T10:07:00" -> "Nov 21, 2026, 10:07 AM" (the API sends local time without a zone)
function dateTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

// "2026-11-21" -> a local Date (new Date("2026-11-21") would be UTC and can shift a day)
function parseDay(day) {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function dayLabel(day, withYear = false) {
  const options = { month: "short", day: "numeric" };
  if (withYear) options.year = "numeric";
  return parseDay(day).toLocaleDateString("en-US", options);
}

// Local date as YYYY-MM-DD
function isoDay(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDay(d);
}

// Same rule as points_for() in models.py: 10 eco-points per unit, rounded down.
// Working in hundredths avoids float surprises like 0.29 * 10 = 2.9000000000000004.
function pointsFor(quantity) {
  return Math.floor(Math.round(Number(quantity) * 100) / 10);
}

// Same rounding as the API: quantity x price, rounded to cents
function lineSubtotal(quantity, price) {
  return Math.round(Number(quantity) * Number(price) * 100) / 100;
}

function plural(n, word, many = word + "s") {
  return `${int(n)} ${n === 1 ? word : many}`;
}

/* ---------- toasts ---------- */

// The toast list lives in <body>, but a modal <dialog> sits in the browser "top layer"
// and would cover it. So while a dialog is open we move the list inside that dialog.
function toastHost() {
  const open = $$("dialog[open]");
  return open.length ? open[open.length - 1] : document.body;
}

function toast(message, type = "success") {
  const list = $("#toasts");
  moveToasts();

  const item = document.createElement("div");
  item.className = "toast toast-" + type;
  item.innerHTML = `<span class="toast-text"></span>
    <button type="button" class="toast-close" aria-label="Dismiss message">
      <svg class="icon"><use href="#i-close"/></svg>
    </button>`;
  item.querySelector(".toast-text").textContent = message;
  list.appendChild(item);

  const remove = () => {
    item.classList.add("leaving");
    setTimeout(() => item.remove(), reduceMotion ? 0 : 180);
  };
  item.querySelector(".toast-close").addEventListener("click", remove);
  setTimeout(remove, type === "error" ? 7000 : 4500);
}

function showError(err) {
  toast(err.message || String(err), "error");
}

// Moves the toast list to wherever it can be seen right now.
function moveToasts() {
  const list = $("#toasts");
  if (list.parentNode !== toastHost()) toastHost().appendChild(list);
}

// Closes a dialog and brings its toasts back out to the page at once.
function closeDialog(dialog) {
  if (dialog.open) dialog.close();
  moveToasts();
}

// Dialogs closed with the Esc key fire "close"; move the toasts back then too.
document.addEventListener("close", moveToasts, true);

/* ---------- dialogs ---------- */

// Buttons with data-close close the dialog they are in.
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-close]");
  if (btn) closeDialog(btn.closest("dialog"));
});

// Clicking the dark backdrop around a dialog closes it too.
document.addEventListener("mousedown", (e) => {
  if (e.target.tagName === "DIALOG" && e.target.open) {
    const box = e.target.getBoundingClientRect();
    const inside = e.clientX >= box.left && e.clientX <= box.right && e.clientY >= box.top && e.clientY <= box.bottom;
    if (!inside) closeDialog(e.target);
  }
});

// Asks a yes/no question. Resolves to true when the user confirms.
function confirmAction(text, { title = "Are you sure?", yes = "Delete" } = {}) {
  const dialog = $("#confirm-dialog");
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  $("#confirm-yes").textContent = yes;
  dialog.showModal();
  return new Promise((resolve) => {
    // Answer as soon as a button is clicked (the dialog's "close" event can arrive late).
    // Esc or a click on the backdrop closes the dialog and counts as "no".
    const done = (answer) => {
      dialog.removeEventListener("click", onClick);
      dialog.removeEventListener("close", onClose);
      closeDialog(dialog);
      resolve(answer);
    };
    const onClick = (e) => {
      const button = e.target.closest("button[value]");
      if (!button) return;
      e.preventDefault();
      done(button.value === "yes");
    };
    const onClose = () => done(false);
    dialog.addEventListener("click", onClick);
    dialog.addEventListener("close", onClose);
  });
}

// Edit dialog shared by customers, stores and products.
// fields: [{ name, label, type, step, min, list, prefix }]
// save: async function that receives the form values; if it throws, the error shows in the dialog.
let editSave = null;

function openEdit(title, fields, values, save) {
  $("#edit-title").textContent = title;
  $("#edit-fields").innerHTML = fields
    .map((f) => {
      const attrs = [
        `name="${f.name}"`,
        `type="${f.type || "text"}"`,
        `value="${esc(values[f.name])}"`,
        f.step ? `step="${f.step}"` : "",
        f.min !== undefined ? `min="${f.min}"` : "",
        f.list ? `list="${f.list}"` : "",
        f.maxlength ? `maxlength="${f.maxlength}"` : "",
        "required",
      ].join(" ");
      const input = f.prefix
        ? `<span class="input-unit input-prefix"><span class="unit">${esc(f.prefix)}</span><input ${attrs}></span>`
        : `<input ${attrs}>`;
      return `<label class="field">${esc(f.label)} ${input}</label>`;
    })
    .join("");
  $("#edit-error").hidden = true;
  editSave = save;
  $("#edit-dialog").showModal();
  $("#edit-fields input").focus();
}

$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    await editSave(formData(form));
    closeDialog($("#edit-dialog"));
  } catch (err) {
    $("#edit-error").textContent = err.message;
    $("#edit-error").hidden = false;
  } finally {
    submit.disabled = false;
  }
});

/* ---------- forms, loading and empty states ---------- */

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

// Disables a button while an async action runs, so it can't be sent twice.
async function busy(button, action) {
  if (button) {
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  }
  try {
    return await action();
  } finally {
    if (button) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  }
}

// Grey placeholder rows shown while a table loads (same height as real rows, so nothing jumps).
function loadingRows(tbody, cols, rows = 4) {
  const cells = Array.from({ length: cols }, () => '<td><span class="skeleton"></span></td>').join("");
  tbody.innerHTML = Array.from({ length: rows }, () => `<tr class="loading-row">${cells}</tr>`).join("");
  tbody.setAttribute("aria-busy", "true");
}

function emptyRow(cols, title, hint = "") {
  return `<tr class="empty-row"><td colspan="${cols}">
    <div class="empty"><strong>${esc(title)}</strong>${hint ? `<span>${hint}</span>` : ""}</div>
  </td></tr>`;
}

function emptyBlock(title, hint = "") {
  return `<div class="empty"><strong>${esc(title)}</strong>${hint ? `<span>${hint}</span>` : ""}</div>`;
}

function setRows(tbody, html) {
  tbody.innerHTML = html;
  tbody.removeAttribute("aria-busy");
}

// Small "jar" whose fill shows a stock level. ratio: 0..1
function jar(ratio, low) {
  const pct = Math.max(0, Math.min(1, ratio)) * 100;
  return `<span class="jar${low ? " is-low" : ""}" aria-hidden="true"><span style="height:${pct.toFixed(0)}%"></span></span>`;
}

// Animates a number from 0 to its value (skipped when the user prefers reduced motion).
function countUp(el, value, format = int) {
  const target = Number(value) || 0;
  if (reduceMotion || target === 0) {
    el.textContent = format(target);
    return;
  }
  const duration = 900;
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = format(target * eased);
    if (t < 1) requestAnimationFrame(step);
    else el.textContent = format(target);
  };
  requestAnimationFrame(step);
}

/* ---------- CSV export ---------- */

// columns: [{ label, value: (row) => ... }]. The file is built in the browser and downloaded.
function downloadCSV(filename, columns, rows) {
  const cell = (v) => {
    const text = String(v ?? "");
    return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const lines = [columns.map((c) => cell(c.label)).join(",")];
  for (const row of rows) lines.push(columns.map((c) => cell(c.value(row))).join(","));

  // The BOM (byte order mark) makes Excel read accents (Cumbayá, Pérez) correctly
  const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---------- lookups shared by the selects ---------- */

// Customers, stores and products are kept in memory to fill the <select>s.
const lookups = { customers: [], stores: [], products: [] };

async function loadLookups() {
  const [customers, stores, products] = await Promise.all([
    api.get("/clientes"),
    api.get("/tiendas"),
    api.get("/productos"),
  ]);
  Object.assign(lookups, { customers, stores, products });
}

function storeOptions(placeholder) {
  return (placeholder ? `<option value="">${esc(placeholder)}</option>` : "") +
    lookups.stores.map((s) => `<option value="${s.tienda_id}">${esc(s.nombre_sucursal)}</option>`).join("");
}

function customerOptions(placeholder) {
  return (placeholder ? `<option value="">${esc(placeholder)}</option>` : "") +
    lookups.customers.map((c) => `<option value="${c.cliente_id}">${esc(c.nombre_completo)}</option>`).join("");
}

// Rebuilds a select's options but keeps the current choice if it still exists
function fillSelect(select, html) {
  const current = select.value;
  select.innerHTML = html;
  if ([...select.options].some((o) => o.value === current)) select.value = current;
}

function findProduct(id) {
  return lookups.products.find((p) => p.producto_id === Number(id));
}
