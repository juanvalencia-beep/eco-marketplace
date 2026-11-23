// Hand-made charts, no library:
//  - lineChart(): an SVG area/line chart with a hover tooltip (revenue per day)
//  - barList():   horizontal bars built with plain HTML (stores, products, customers)
// Colors come from CSS variables, so the charts follow light and dark mode.

// Rounds a maximum up to a "nice" number for the axis (e.g. 87 -> 100, 230 -> 250)
function niceMax(value) {
  if (value <= 0) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(value)));
  const f = value / power;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * power;
}

// points: [{ label, value, detail }]  label = text under the x axis, detail = extra tooltip line
function lineChart(container, points, { format = money, axisFormat = moneyShort, height = 240 } = {}) {
  container._redraw = () => lineChart(container, points, { format, axisFormat, height });
  watchResize(container);

  if (!points.length || points.every((p) => !p.value)) {
    container.innerHTML = emptyBlock("Sin ventas en este periodo", "Los ingresos aparecerán aquí cuando se registren pedidos.");
    return;
  }

  const width = Math.max(container.clientWidth, 280);
  const pad = { top: 14, right: 12, bottom: 28, left: 52 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const max = niceMax(Math.max(...points.map((p) => p.value)));
  const step = points.length > 1 ? innerW / (points.length - 1) : 0;

  const x = (i) => pad.left + (points.length > 1 ? i * step : innerW / 2);
  const y = (v) => pad.top + innerH - (v / max) * innerH;

  // horizontal grid lines with their labels
  let grid = "";
  for (let i = 0; i <= 4; i++) {
    const value = (max / 4) * i;
    const gy = y(value).toFixed(1);
    grid += `<line class="grid" x1="${pad.left}" x2="${width - pad.right}" y1="${gy}" y2="${gy}"/>`;
    grid += `<text class="axis" x="${pad.left - 8}" y="${gy}" dy="0.32em" text-anchor="end">${esc(axisFormat(value))}</text>`;
  }

  // x labels: about 6 of them, so they never overlap
  const every = Math.max(1, Math.ceil(points.length / 6));
  let xLabels = "";
  points.forEach((p, i) => {
    if (i % every === 0) {
      xLabels += `<text class="axis" x="${x(i).toFixed(1)}" y="${height - 8}" text-anchor="middle">${esc(p.label)}</text>`;
    }
  });

  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  const area = `${line}L${x(points.length - 1).toFixed(1)},${y(0)}L${x(0).toFixed(1)},${y(0)}Z`;

  container.innerHTML = `
    <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" aria-hidden="true">
      ${grid}
      <path class="area" d="${area}"/>
      <path class="line" d="${line}"/>
      <line class="guide" x1="0" x2="0" y1="${pad.top}" y2="${pad.top + innerH}" visibility="hidden"/>
      <circle class="dot" r="4.5" cx="0" cy="0" visibility="hidden"/>
      ${xLabels}
      <rect class="hit" x="${pad.left}" y="${pad.top}" width="${innerW}" height="${innerH}"/>
    </svg>
    <div class="tooltip" hidden></div>`;

  // hover: find the nearest day and show its value
  const svg = container.querySelector("svg");
  const guide = svg.querySelector(".guide");
  const dot = svg.querySelector(".dot");
  const tip = container.querySelector(".tooltip");

  svg.querySelector(".hit").addEventListener("pointermove", (e) => {
    const box = svg.getBoundingClientRect();
    const px = e.clientX - box.left;
    const i = Math.max(0, Math.min(points.length - 1, Math.round((px - pad.left) / (step || 1))));
    const p = points[i];
    guide.setAttribute("x1", x(i));
    guide.setAttribute("x2", x(i));
    dot.setAttribute("cx", x(i));
    dot.setAttribute("cy", y(p.value));
    guide.removeAttribute("visibility");
    dot.removeAttribute("visibility");
    tip.innerHTML = `<strong>${esc(format(p.value))}</strong><span>${esc(p.tooltip || p.label)}</span>${p.detail ? `<span>${esc(p.detail)}</span>` : ""}`;
    tip.hidden = false;
    // keep the tooltip inside the chart
    const left = Math.min(Math.max(x(i) - tip.offsetWidth / 2, 0), width - tip.offsetWidth);
    tip.style.left = left + "px";
    tip.style.top = Math.max(y(p.value) - tip.offsetHeight - 12, 0) + "px";
  });
  svg.querySelector(".hit").addEventListener("pointerleave", () => {
    guide.setAttribute("visibility", "hidden");
    dot.setAttribute("visibility", "hidden");
    tip.hidden = true;
  });
}

// rows: [{ label, value, note }]. Bars are as long as value / largest value.
function barList(container, rows, { format = money, emptyTitle = "Nada que mostrar", emptyHint = "" } = {}) {
  if (!rows.length || rows.every((r) => !r.value)) {
    container.innerHTML = emptyBlock(emptyTitle, emptyHint);
    return;
  }
  const max = Math.max(...rows.map((r) => r.value));
  container.innerHTML = `<ol class="bars">${rows
    .map(
      (r) => `<li>
        <div class="bar-top">
          <span class="bar-label">${esc(r.label)}</span>
          <span class="bar-value">${esc(format(r.value))}</span>
        </div>
        <div class="bar-track"><span class="bar-fill" style="width:${max ? ((r.value / max) * 100).toFixed(1) : 0}%"></span></div>
        ${r.note ? `<div class="bar-note">${esc(r.note)}</div>` : ""}
      </li>`
    )
    .join("")}</ol>`;
}

// Redraws SVG charts when their box changes width (window resize, sidebar, print).
const chartObserver = new ResizeObserver((entries) => {
  for (const entry of entries) {
    const el = entry.target;
    const w = Math.round(entry.contentRect.width);
    if (w && w !== el._lastWidth && el._redraw) {
      const first = el._lastWidth === undefined;
      el._lastWidth = w;
      if (!first) el._redraw();
    }
  }
});

function watchResize(container) {
  if (!container._watched) {
    container._watched = true;
    chartObserver.observe(container);
  }
  container._lastWidth = Math.round(container.clientWidth) || container._lastWidth;
}
