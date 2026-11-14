(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const nf = new Intl.NumberFormat("en-US");
  const NS = "http://www.w3.org/2000/svg";

  const el = (tag, attrs = {}, text) => {
    const n = document.createElementNS(tag === "svg" || attrs.svg ? NS : "http://www.w3.org/1999/xhtml", tag);
    for (const [k, v] of Object.entries(attrs)) if (k !== "svg") n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const html = (tag, text) => Object.assign(document.createElement(tag), { textContent: text });
  const label = (s) => String(s).replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

  async function post(url, body) {
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  function wire(form, run) {
    const btn = $("button[type=submit]", form), err = $("#error");
    const text = btn.textContent;
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      btn.disabled = true;
      btn.textContent = "Running\u2026";
      try {
        await run(Object.fromEntries(new FormData(form)));
        $("#empty").hidden = true;
        $("#result").hidden = false;
      } catch (ex) {
        err.textContent = ex.message;
        err.hidden = false;
      } finally {
        btn.disabled = false;
        btn.textContent = text;
      }
    });
  }

  function prediction() {
    const rows = [];
    wire($("#form"), async (f) => {
      const d = await post("/api/predict", {
        user_id: f.user_id.trim(), content_id: f.content_id.trim(), context: { user_state: f.user_state },
      });
      const pct = Number(d.prediction_percentage);
      $("#score").textContent = pct.toFixed(1);
      $("#bar").style.width = `${Math.max(0, Math.min(100, pct))}%`;
      $("#confidence").textContent = label(d.confidence || "unknown");
      $("#rec").textContent = d.recommendation || "None";
      $("#factors").replaceChildren(...(d.factors || []).map((x) => html("li", label(x))));
      rows.unshift([new Date().toLocaleTimeString(), f.user_id, f.content_id, pct.toFixed(1) + "%"]);
      rows.length = Math.min(rows.length, 8);
      $("#log tbody").replaceChildren(...rows.map((r) => {
        const tr = document.createElement("tr");
        r.forEach((c, i) => { const td = html("td", c); if (i === 3) td.className = "n"; tr.append(td); });
        return tr;
      }));
      $("#log-box").hidden = false;
    });
  }

  function chart(svg, hover, fc) {
    const W = 720, H = 300, p = { l: 48, r: 10, t: 10, b: 26 };
    const { dates, values, lower, upper } = fc, n = values.length;
    const lo = Math.floor(Math.min(...lower) * 0.9), hi = Math.ceil(Math.max(...upper) * 1.05) || 1;
    const x = (i) => p.l + (n === 1 ? 0 : (i / (n - 1)) * (W - p.l - p.r));
    const y = (v) => p.t + (1 - (v - lo) / (hi - lo || 1)) * (H - p.t - p.b);
    const pts = (a) => a.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    svg.replaceChildren();
    for (let k = 0; k <= 4; k++) {
      const v = lo + ((hi - lo) * k) / 4, yy = y(v);
      svg.append(el("line", { class: "grid", x1: p.l, x2: W - p.r, y1: yy, y2: yy }));
      svg.append(el("text", { x: p.l - 6, y: yy + 4, "text-anchor": "end" }, nf.format(Math.round(v))));
    }
    [0, Math.floor((n - 1) / 2), n - 1].forEach((i, k) => {
      svg.append(el("text", { x: x(i), y: H - 8, "text-anchor": k === 0 ? "start" : k === 2 ? "end" : "middle" }, dates[i] || ""));
    });
    svg.append(el("polygon", { class: "band", points: [...pts(upper), ...pts(lower).reverse()].join(" ") }));
    svg.append(el("polyline", { class: "line", points: pts(values).join(" ") }));
    const cur = el("line", { class: "cur", y1: p.t, y2: H - p.b, visibility: "hidden" });
    svg.append(cur);
    const show = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(n - 1, Math.round(((px - p.l) / (W - p.l - p.r)) * (n - 1))));
      cur.setAttribute("x1", x(i)); cur.setAttribute("x2", x(i)); cur.setAttribute("visibility", "visible");
      hover.textContent = `${dates[i]}  ${nf.format(values[i])} streams  (${nf.format(lower[i])} to ${nf.format(upper[i])})`;
    };
    svg.onpointermove = show;
    svg.onpointerleave = () => { cur.setAttribute("visibility", "hidden"); hover.textContent = ""; };
  }

  function forecasting() {
    wire($("#form"), async (f) => {
      const d = await post("/api/forecast", { content_id: f.content_id.trim(), periods: Number(f.periods), method: f.method });
      const s = d.summary, fc = d.forecast;
      $("#s-total").textContent = nf.format(s.total);
      $("#s-avg").textContent = nf.format(s.average);
      $("#s-min").textContent = nf.format(s.min);
      $("#s-max").textContent = nf.format(s.max);
      $("#result").hidden = false;
      chart($("#chart"), $("#hover"), fc);
      $("#rows").replaceChildren(...fc.dates.map((dt, i) => {
        const tr = document.createElement("tr");
        [dt, fc.values[i], fc.lower[i], fc.upper[i]].forEach((c, k) => {
          const td = html("td", k ? nf.format(c) : c); if (k) td.className = "n"; tr.append(td);
        });
        return tr;
      }));
    });
  }

  const page = document.body.dataset.page;
  if (page === "prediction") prediction();
  if (page === "forecasting") forecasting();
})();
