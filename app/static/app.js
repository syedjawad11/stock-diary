/* Stock Diary frontend logic. Plain JS, no build step, no frameworks.
   Talks to the FastAPI backend described in API.md. */

(function () {
  "use strict";

  // ---------- state ----------
  var state = {
    lang: loadLang(),
    stock: [], // [{product, qty, is_low}]
    recent: [], // [Movement]
    quota: { used_today: 0, limit_today: 30 },
    products: [], // flat list of Product, derived from stock
    proposals: [], // mutable working copy of /api/parse proposals
    confirmKey: null,
    originalText: "",
    exampleIndex: 0,
    filter: "all",
    manualDirection: "in",
    manualKey: null,
    productKey: null,
    busy: {
      checking: false,
      confirming: false,
      asking: false,
      resetting: false,
    },
    lastSaved: [], // movement ids from the last confirm, for the toast Undo
  };

  // ---------- small helpers ----------

  function $(id) {
    return document.getElementById(id);
  }

  function loadLang() {
    try {
      var v = localStorage.getItem("sd_lang");
      if (v === "en" || v === "ur") return v;
    } catch (e) {
      /* storage unavailable: fall through */
    }
    return "en";
  }

  function saveLang(lang) {
    try {
      localStorage.setItem("sd_lang", lang);
    } catch (e) {
      /* ignore */
    }
  }

  function tr(key, vars) {
    return t(state.lang, key, vars);
  }

  function bdi(value) {
    var span = document.createElement("bdi");
    span.textContent = String(value);
    return span;
  }

  function clearChildren(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function productById(id) {
    for (var i = 0; i < state.products.length; i++) {
      if (state.products[i].id === id) return state.products[i];
    }
    return null;
  }

  function productName(product) {
    if (!product) return "";
    return state.lang === "ur" ? product.name_ur || product.name_en : product.name_en;
  }

  function errorMessage(err) {
    if (err && err.network) return tr("errorNetwork");
    if (err && err.error === "rate_limited")
      return tr(err.scope === "day" ? "rateDaily" : "rateMinute");
    if (err) {
      var msg = state.lang === "ur" ? err.message_ur : err.message_en;
      if (msg) return msg;
    }
    return tr("errorGeneric");
  }

  // ---------- fetch wrapper ----------

  function api(path, opts) {
    opts = opts || {};
    var fetchOpts = {
      method: opts.method || "GET",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
    };
    if (opts.body) fetchOpts.body = JSON.stringify(opts.body);

    return fetch(path, fetchOpts)
      .catch(function () {
        return Promise.reject({ network: true });
      })
      .then(function (res) {
        return res
          .json()
          .catch(function () {
            return null;
          })
          .then(function (data) {
            if (!res.ok) {
              var err = data || {};
              err.status = res.status;
              return Promise.reject(err);
            }
            return data;
          });
      });
  }

  // ---------- translating static markup ----------

  function applyTranslations() {
    var nodes = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < nodes.length; i++) {
      var key = nodes[i].getAttribute("data-i18n");
      nodes[i].textContent = tr(key);
    }
    var placeholders = document.querySelectorAll("[data-i18n-placeholder]");
    for (var j = 0; j < placeholders.length; j++) {
      var pkey = placeholders[j].getAttribute("data-i18n-placeholder");
      placeholders[j].setAttribute("placeholder", tr(pkey));
    }
  }

  function applyLangToDocument() {
    document.documentElement.setAttribute("lang", state.lang === "ur" ? "ur" : "en");
    document.documentElement.setAttribute("dir", state.lang === "ur" ? "rtl" : "ltr");
    $("lang-en").setAttribute("aria-pressed", state.lang === "en" ? "true" : "false");
    $("lang-ur").setAttribute("aria-pressed", state.lang === "ur" ? "true" : "false");
  }

  function setLang(lang) {
    if (lang !== "en" && lang !== "ur") return;
    state.lang = lang;
    saveLang(lang);
    applyLangToDocument();
    applyTranslations();
    renderQuota();
    renderStock();
    renderManualProducts();
    renderUnitOptions();
    updateManual();
    renderProposals();
    renderRecent();
    // answer card keeps whatever was last asked; re-render with new language text
    if (state.lastAnswer) renderAnswer(state.lastAnswer);
  }

  // ---------- quota ----------

  function renderQuota() {
    var el = $("quota-text"),
      template = tr("quotaText", { used: "{used}", limit: "{limit}" });
    clearChildren(el);
    template.split(/(\{used\}|\{limit\})/).forEach(function (part) {
      if (part === "{used}") el.appendChild(bdi(state.quota.used_today));
      else if (part === "{limit}") el.appendChild(bdi(state.quota.limit_today));
      else el.appendChild(document.createTextNode(part));
    });
  }

  // ---------- stock ----------

  function setFilter(filter) {
    state.filter = filter;
    ["all", "low", "out"].forEach(function (f) {
      var btn = $("filter-" + f);
      btn.classList.toggle("active", f === filter);
      btn.setAttribute("aria-pressed", f === filter ? "true" : "false");
    });
    renderStock();
  }

  function stockStatus(row) {
    return row.qty === 0 ? "out" : row.is_low ? "low" : "ok";
  }
  function statusBadge(row) {
    var status = stockStatus(row),
      el = document.createElement("span");
    el.className = "badge badge-" + status;
    el.textContent = tr(status === "out" ? "out" : status === "low" ? "low" : "ok");
    return el;
  }
  function namedCell(row) {
    var wrap = document.createElement("span"),
      name = document.createElement("span"),
      other = document.createElement("small");
    name.className = "product-name";
    name.textContent = productName(row.product);
    wrap.appendChild(name);
    if (row.product.id.indexOf("custom-") === 0) {
      var tag = document.createElement("span");
      tag.className = "new-tag";
      tag.textContent = tr("newTag");
      wrap.appendChild(tag);
    }
    other.className = "other-name";
    other.textContent = state.lang === "ur" ? row.product.name_en : row.product.name_ur;
    if (other.textContent && other.textContent !== name.textContent) wrap.appendChild(other);
    return wrap;
  }
  function adjustButton(row) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "inline-action";
    btn.textContent = tr("adjust");
    btn.addEventListener("click", function () {
      selectTab("manual");
      $("manual-product").value = row.product.id;
      manualChanged();
      $("manual-qty").focus();
    });
    return btn;
  }
  function renderStock() {
    var list = $("stock-list");
    clearChildren(list);
    var products = 0,
      low = 0,
      out = 0;
    state.stock.forEach(function (r) {
      products++;
      if (r.qty === 0) out++;
      else if (r.is_low) low++;
    });
    [
      ["count-products", products],
      ["count-low", low],
      ["count-out", out],
    ].forEach(function (pair) {
      var el = $(pair[0]);
      clearChildren(el);
      el.appendChild(bdi(pair[1]));
    });
    var term = $("stock-search").value.trim().toLocaleLowerCase();
    var rows = state.stock.filter(function (r) {
      if (state.filter === "low" && !(r.is_low && r.qty > 0)) return false;
      if (state.filter === "out" && r.qty !== 0) return false;
      var p = r.product;
      return (
        !term ||
        [p.name_en, p.name_ur].concat(p.aliases || []).some(function (v) {
          return (
            String(v || "")
              .toLocaleLowerCase()
              .indexOf(term) >= 0
          );
        })
      );
    });
    if (!rows.length) {
      var empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = tr("emptyFilter");
      list.appendChild(empty);
      return;
    }
    var table = document.createElement("table");
    table.className = "stock-table";
    var head = document.createElement("thead"),
      hr = document.createElement("tr");
    ["product", "unit", "inStock", "lowAt", "status", "adjust"].forEach(function (key) {
      var th = document.createElement("th");
      th.textContent = tr(key);
      hr.appendChild(th);
    });
    head.appendChild(hr);
    table.appendChild(head);
    var body = document.createElement("tbody"),
      mobile = document.createElement("div");
    mobile.className = "stock-mobile";
    rows.forEach(function (r) {
      var trEl = document.createElement("tr");
      [
        namedCell(r),
        document.createTextNode(unitLabel(r.product.unit, state.lang, 1)),
        bdi(r.qty),
        bdi(r.product.low_threshold),
        statusBadge(r),
        adjustButton(r),
      ].forEach(function (node) {
        var td = document.createElement("td");
        td.appendChild(node);
        trEl.appendChild(td);
      });
      body.appendChild(trEl);
      var card = document.createElement("div");
      card.className = "stock-mobile-row";
      var top = document.createElement("div");
      top.className = "stock-mobile-top";
      top.appendChild(namedCell(r));
      top.appendChild(statusBadge(r));
      card.appendChild(top);
      var meta = document.createElement("div");
      meta.className = "stock-mobile-meta";
      ["inStock", "lowAt"].forEach(function (key) {
        var span = document.createElement("span");
        span.appendChild(document.createTextNode(tr(key) + ": "));
        span.appendChild(bdi(key === "inStock" ? r.qty : r.product.low_threshold));
        span.appendChild(
          document.createTextNode(
            " " +
              unitLabel(
                r.product.unit,
                state.lang,
                key === "inStock" ? r.qty : r.product.low_threshold,
              ),
          ),
        );
        meta.appendChild(span);
      });
      meta.appendChild(adjustButton(r));
      card.appendChild(meta);
      mobile.appendChild(card);
    });
    table.appendChild(body);
    list.appendChild(table);
    list.appendChild(mobile);
  }

  function refreshFromStateShape(data) {
    state.stock = data.stock || [];
    state.recent = data.recent || [];
    state.quota = data.quota || state.quota;
    state.products = state.stock.map(function (r) {
      return r.product;
    });
    renderQuota();
    renderStock();
    renderManualProducts();
    updateManual();
    renderRecent();
  }

  function loadState() {
    return api("/api/state")
      .then(function (data) {
        refreshFromStateShape(data);
      })
      .catch(function (err) {
        $("quota-text").textContent = errorMessage(err);
      });
  }

  // ---------- entry / parse ----------

  function setBusy(key, isBusy) {
    state.busy[key] = isBusy;
  }

  function showStatus(elId, message, isError) {
    var el = $(elId);
    el.textContent = message || "";
    el.classList.toggle("status-error", !!isError);
  }

  function nextExample() {
    var s = EXAMPLE_SENTENCES[state.exampleIndex % EXAMPLE_SENTENCES.length];
    state.exampleIndex++;
    $("entry-text").value = s;
  }

  function checkEntry() {
    if (state.busy.checking) return;
    var text = $("entry-text").value.trim();
    showStatus("parse-status", "", false);
    if (!text) return;

    setBusy("checking", true);
    $("check-btn").disabled = true;
    $("example-btn").disabled = true;
    showStatus("parse-status", tr("checking"), false);

    api("/api/parse", { method: "POST", body: { text: text } })
      .then(function (data) {
        showStatus("parse-status", "", false);
        state.originalText = text;
        state.confirmKey = data.confirm_key;
        state.proposals = (data.proposals || []).map(function (p) {
          return {
            product_text: p.product_text,
            product_id: p.product_id,
            candidates: p.candidates || [],
            qty: p.qty,
            unit: p.unit,
            direction: p.direction,
            balance_before: p.balance_before,
            balance_after: p.balance_after,
            problem: p.problem,
            unit_mismatch: !!p.unit_mismatch, // the stated unit differs from the product's unit
            unit_accepted: false, // set only by the explicit "Use <unit>" button
          };
        });
        if (!state.proposals.length) {
          showStatus("parse-status", tr("noProposals"), true);
          $("proposals-section").hidden = true;
        } else {
          recomputeProposals();
          renderProposals();
          $("proposals-section").hidden = false;
        }
      })
      .catch(function (err) {
        showStatus("parse-status", errorMessage(err), true);
      })
      .then(function () {
        setBusy("checking", false);
        $("check-btn").disabled = false;
        $("example-btn").disabled = false;
      });
  }

  // ---------- proposals (check-before-saving cards) ----------

  function currentStockMap() {
    var map = {};
    state.stock.forEach(function (row) {
      map[row.product.id] = row.qty;
    });
    return map;
  }

  function recomputeProposals() {
    var running = currentStockMap();
    state.proposals.forEach(function (p) {
      if (!p.product_id) {
        p.balance_before = null;
        p.balance_after = null;
        p.problem = "unknown_product";
        return;
      }
      var before = running.hasOwnProperty(p.product_id) ? running[p.product_id] : 0;
      var qty = p.qty > 0 ? p.qty : 0;
      var after = p.direction === "out" ? before - qty : before + qty;
      p.balance_before = before;
      p.balance_after = after;
      running[p.product_id] = after;
      p.problem =
        after < 0
          ? "insufficient_stock"
          : p.unit_mismatch && !p.unit_accepted
            ? "unit_mismatch"
            : null;
    });
  }

  function anyProposalProblem() {
    return state.proposals.some(function (p) {
      return !!p.problem;
    });
  }

  function problemText(problem) {
    if (problem === "unknown_product") return tr("problemUnknownProduct");
    if (problem === "insufficient_stock") return tr("problemInsufficientStock");
    if (problem === "unit_mismatch") return tr("problemUnitMismatch");
    return "";
  }

  function allProductOptions(proposal) {
    var seen = {};
    var options = [];
    (proposal.candidates || []).forEach(function (c) {
      if (!seen[c.id]) {
        seen[c.id] = true;
        options.push(c);
      }
    });
    state.products.forEach(function (p) {
      if (!seen[p.id]) {
        seen[p.id] = true;
        options.push(p);
      }
    });
    return options;
  }

  function renderProposals() {
    var list = $("proposals-list");
    clearChildren(list);

    state.proposals.forEach(function (p, index) {
      var card = document.createElement("div");
      card.className = "proposal-card" + (p.problem ? " has-problem" : "");

      // product name / select row
      var header = document.createElement("div");
      header.className = "proposal-header";
      var nameEl = document.createElement("span");
      nameEl.className = "proposal-name";
      var prod = p.product_id ? productById(p.product_id) : null;
      nameEl.textContent = prod ? productName(prod) : p.product_text;
      header.appendChild(nameEl);
      card.appendChild(header);

      var select = document.createElement("select");
      select.className = "proposal-select";
      select.setAttribute("aria-label", tr("selectProduct"));
      var placeholderOpt = document.createElement("option");
      placeholderOpt.value = "";
      placeholderOpt.textContent = tr("selectProduct");
      if (!p.product_id) placeholderOpt.selected = true;
      select.appendChild(placeholderOpt);
      allProductOptions(p).forEach(function (opt) {
        var optionEl = document.createElement("option");
        optionEl.value = opt.id;
        optionEl.textContent = productName(opt);
        if (opt.id === p.product_id) optionEl.selected = true;
        select.appendChild(optionEl);
      });
      select.addEventListener("change", function () {
        p.product_id = select.value || null;
        p.problem = null;
        p.unit = productById(p.product_id) ? productById(p.product_id).unit : p.unit;
        recomputeProposals();
        renderProposals();
      });
      card.appendChild(select);

      // controls row: direction toggle + qty
      var controls = document.createElement("div");
      controls.className = "proposal-controls";

      var dirGroup = document.createElement("div");
      dirGroup.className = "dir-toggle";
      ["in", "out"].forEach(function (dir) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dir-btn" + (p.direction === dir ? " active" : "");
        btn.textContent = dir === "in" ? tr("directionIn") : tr("directionOut");
        btn.addEventListener("click", function () {
          p.direction = dir;
          recomputeProposals();
          renderProposals();
        });
        dirGroup.appendChild(btn);
      });
      controls.appendChild(dirGroup);

      var qtyInput = document.createElement("input");
      qtyInput.type = "number";
      qtyInput.min = "1";
      qtyInput.className = "proposal-qty";
      qtyInput.value = p.qty;
      qtyInput.setAttribute("aria-label", "qty");
      qtyInput.addEventListener("change", function () {
        var v = /^\d+$/.test(qtyInput.value) ? Number(qtyInput.value) : 0;
        p.qty = v > 0 && v <= 100000 ? v : 1;
        p.problem = null;
        qtyInput.value = p.qty;
        recomputeProposals();
        renderProposals();
      });
      controls.appendChild(qtyInput);

      var unitSpan = document.createElement("span");
      unitSpan.className = "proposal-unit";
      unitSpan.textContent = unitLabel(p.unit || (prod ? prod.unit : null), state.lang, p.qty);
      controls.appendChild(unitSpan);

      card.appendChild(controls);

      // balance line
      var balanceLine = document.createElement("div");
      balanceLine.className = "proposal-balance";
      var sign = p.direction === "in" ? "+" : "-";
      var dirLabel = document.createElement("span");
      dirLabel.className = "balance-dir";
      dirLabel.textContent =
        (p.direction === "in" ? tr("directionIn") : tr("directionOut")) + " " + sign;
      balanceLine.appendChild(dirLabel);
      balanceLine.appendChild(bdi(p.qty));

      var stockLine = document.createElement("span");
      stockLine.className = "balance-stock";
      stockLine.appendChild(document.createTextNode(tr("stockWord") + " "));
      stockLine.appendChild(
        bdi(p.balance_before === null || p.balance_before === undefined ? "–" : p.balance_before),
      );
      stockLine.appendChild(document.createTextNode(" → "));
      stockLine.appendChild(
        bdi(p.balance_after === null || p.balance_after === undefined ? "–" : p.balance_after),
      );
      balanceLine.appendChild(stockLine);
      card.appendChild(balanceLine);

      if (p.problem) {
        var problemEl = document.createElement("div");
        problemEl.className = "proposal-problem";
        problemEl.textContent = problemText(p.problem);
        card.appendChild(problemEl);
      }

      if (p.problem === "unit_mismatch" && prod) {
        var help = document.createElement("div");
        help.className = "proposal-help";
        help.textContent = tr("countedIn", { unit: unitLabel(prod.unit, state.lang, 1) });
        card.appendChild(help);
        var use = document.createElement("button");
        use.type = "button";
        use.className = "inline-action";
        use.textContent = tr("useUnit", { unit: unitLabel(prod.unit, state.lang, 1) });
        use.addEventListener("click", function () {
          p.unit = prod.unit;
          p.unit_accepted = true;
          recomputeProposals();
          renderProposals();
        });
        card.appendChild(use);
      }
      if (p.problem === "unknown_product") {
        var create = document.createElement("button");
        create.type = "button";
        create.className = "inline-action";
        create.textContent = tr("createFromProposal", { name: p.product_text });
        create.addEventListener("click", function () {
          selectTab("product");
          $("product-name-en").value = p.product_text;
          if (
            UNITS[p.unit] &&
            ["carton", "bag", "tin", "packet", "box", "piece"].indexOf(p.unit) >= 0
          )
            $("product-unit").value = p.unit;
          productChanged();
          $("product-name-en").focus();
        });
        card.appendChild(create);
      }
      list.appendChild(card);
    });

    var hasProblem = anyProposalProblem();
    $("confirm-btn").disabled = hasProblem || state.busy.confirming || !state.proposals.length;
    $("confirm-hint").hidden = !hasProblem;
  }

  function cancelProposals() {
    state.proposals = [];
    state.confirmKey = null;
    $("proposals-section").hidden = true;
    showStatus("confirm-error", "", false);
    $("confirm-error").hidden = true;
  }

  function confirmProposals() {
    if (state.busy.confirming || anyProposalProblem() || !state.proposals.length) return;
    setBusy("confirming", true);
    $("confirm-btn").disabled = true;
    $("cancel-btn").disabled = true;
    $("confirm-error").hidden = true;

    var lines = state.proposals.map(function (p) {
      return { product_id: p.product_id, qty: p.qty, direction: p.direction };
    });

    api("/api/confirm", {
      method: "POST",
      body: { confirm_key: state.confirmKey, lines: lines, note: state.originalText },
    })
      .then(function (data) {
        refreshFromStateShape(data);
        state.lastSaved = (data.saved || []).map(function (m) {
          return m.id;
        });
        $("entry-text").value = "";
        cancelProposals();
        showToast();
      })
      .catch(function (err) {
        var el = $("confirm-error");
        el.textContent = errorMessage(err);
        el.hidden = false;
      })
      .then(function () {
        setBusy("confirming", false);
        $("cancel-btn").disabled = false;
        renderProposals();
      });
  }

  // ---------- toast / undo ----------

  var toastTimer = null;

  function showToast(message) {
    var toast = $("toast");
    $("toast-msg").textContent = message || tr("savedToast");
    $("toast-undo").disabled = !state.lastSaved.length;
    $("toast-undo").hidden = !state.lastSaved.length;
    toast.hidden = false;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toast.hidden = true;
    }, 8000);
  }

  function hideToast() {
    $("toast").hidden = true;
    if (toastTimer) clearTimeout(toastTimer);
  }

  function undoMovements(ids) {
    if (!ids.length) return Promise.resolve();
    var id = ids[ids.length - 1];
    return api("/api/undo", { method: "POST", body: { movement_id: id } }).then(function (data) {
      refreshFromStateShape(data);
      return undoMovements(ids.slice(0, -1));
    });
  }

  function undoLastSave() {
    if (!state.lastSaved.length) {
      hideToast();
      return;
    }
    $("toast-undo").disabled = true;
    undoMovements(state.lastSaved.slice())
      .then(function () {
        state.lastSaved = [];
        hideToast();
      })
      .catch(function (err) {
        $("toast-msg").textContent = errorMessage(err);
        $("toast-undo").disabled = false;
      });
  }

  function undoSingleMovement(id, btn) {
    btn.disabled = true;
    api("/api/undo", { method: "POST", body: { movement_id: id } })
      .then(function (data) {
        refreshFromStateShape(data);
      })
      .catch(function (err) {
        btn.disabled = false;
        showStatus("parse-status", errorMessage(err), true);
      });
  }

  // ---------- recent entries ----------

  function formatTime(iso) {
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleString(state.lang === "ur" ? "ur" : "en", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  function renderRecent() {
    var list = $("recent-list");
    clearChildren(list);
    if (!state.recent.length) {
      var empty = document.createElement("p");
      empty.className = "recent-empty";
      empty.textContent = tr("recentEmpty");
      list.appendChild(empty);
      return;
    }
    state.recent.forEach(function (m) {
      var row = document.createElement("div");
      row.className = "recent-row";

      var prod = productById(m.product_id);
      var top = document.createElement("div");
      top.className = "recent-top";

      var nameEl = document.createElement("span");
      nameEl.className = "recent-name";
      nameEl.textContent = prod ? productName(prod) : m.product_id;
      top.appendChild(nameEl);

      var directionBadge = document.createElement("span");
      directionBadge.className = "badge " + (m.direction === "in" ? "badge-in" : "badge-out-dir");
      directionBadge.textContent = m.direction === "in" ? tr("movementIn") : tr("movementOut");
      top.insertBefore(directionBadge, nameEl);
      var qtyEl = document.createElement("span");
      qtyEl.className = "recent-qty " + (m.direction === "in" ? "qty-in" : "qty-out");
      qtyEl.appendChild(document.createTextNode(m.direction === "in" ? "+" : "-"));
      qtyEl.appendChild(bdi(m.qty));
      if (prod)
        qtyEl.appendChild(document.createTextNode(" " + unitLabel(prod.unit, state.lang, m.qty)));
      top.appendChild(qtyEl);

      row.appendChild(top);

      var meta = document.createElement("div");
      meta.className = "recent-meta";
      var noteEl = document.createElement("span");
      noteEl.className = "recent-note";
      noteEl.textContent =
        m.note === "manual add"
          ? tr("manualAddNote")
          : m.note === "manual remove"
            ? tr("manualRemoveNote")
            : m.note;
      meta.appendChild(noteEl);
      var timeEl = document.createElement("span");
      timeEl.className = "recent-time";
      timeEl.textContent = formatTime(m.created_at);
      meta.appendChild(timeEl);
      row.appendChild(meta);

      var isReversal = m.reverses !== null && m.reverses !== undefined;
      var isReversed = m.reversed_by !== null && m.reversed_by !== undefined;
      if (!isReversal && !isReversed) {
        var undoBtn = document.createElement("button");
        undoBtn.type = "button";
        undoBtn.className = "btn btn-link recent-undo";
        undoBtn.textContent = tr("undo");
        undoBtn.addEventListener("click", function () {
          undoSingleMovement(m.id, undoBtn);
        });
        row.appendChild(undoBtn);
      } else if (isReversed) {
        var done = document.createElement("span");
        done.className = "recent-tag";
        done.textContent = tr("reversed");
        row.appendChild(done);
      } else if (isReversal) {
        var tag = document.createElement("span");
        tag.className = "recent-tag";
        tag.textContent = tr("reversalNote");
        row.appendChild(tag);
      }

      list.appendChild(row);
    });
  }

  // ---------- ask ----------

  function renderAnswer(answer) {
    var card = $("answer-card");
    clearChildren(card);
    var text = state.lang === "ur" ? answer.answer_ur : answer.answer_en;
    var p = document.createElement("p");
    p.textContent = text;
    card.appendChild(p);
    if (answer.items && answer.items.length) {
      var table = document.createElement("table");
      table.className = "restock-table";
      var head = document.createElement("tr");
      ["product", "restockHave", "lowAt", "restockOrder"].forEach(function (k) {
        var th = document.createElement("th");
        th.textContent = tr(k);
        head.appendChild(th);
      });
      table.appendChild(head);
      answer.items.forEach(function (item) {
        // Shape from API.md (/api/ask restock): {product_id, qty, low_threshold, min_order}
        var product = productById(item.product_id);
        var row = document.createElement("tr");
        var values = [
          product ? productName(product) : item.product_id,
          item.qty,
          item.low_threshold,
          item.min_order,
        ];
        values.forEach(function (v, i) {
          var td = document.createElement("td");
          if (i === 0) td.textContent = v || "";
          else {
            td.appendChild(bdi(v === undefined ? "–" : v));
            if (i === 3 && product)
              td.appendChild(document.createTextNode(" " + unitLabel(product.unit, state.lang, v)));
          }
          row.appendChild(td);
        });
        table.appendChild(row);
      });
      card.appendChild(table);
    }
    card.hidden = false;
  }

  function askQuestion(text) {
    if (state.busy.asking || !text) return;
    setBusy("asking", true);
    $("ask-btn").disabled = true;
    $("chip-low").disabled = true;
    $("chip-today").disabled = true;
    $("chip-reorder").disabled = true;
    showStatus("ask-status", tr("asking"), false);

    api("/api/ask", { method: "POST", body: { text: text } })
      .then(function (data) {
        showStatus("ask-status", "", false);
        state.lastAnswer = data;
        renderAnswer(data);
      })
      .catch(function (err) {
        showStatus("ask-status", errorMessage(err), true);
      })
      .then(function () {
        setBusy("asking", false);
        $("ask-btn").disabled = false;
        $("chip-low").disabled = false;
        $("chip-today").disabled = false;
        $("chip-reorder").disabled = false;
      });
  }

  // ---------- reset ----------

  function resetDemo() {
    if (state.busy.resetting) return;
    if (!window.confirm(tr("resetConfirm"))) return;
    setBusy("resetting", true);
    $("reset-btn").disabled = true;
    api("/api/reset", { method: "POST", body: {} })
      .then(function (data) {
        refreshFromStateShape(data);
        cancelProposals();
        $("entry-text").value = "";
        hideToast();
        $("answer-card").hidden = true;
        state.lastAnswer = null;
      })
      .catch(function (err) {
        showStatus("parse-status", errorMessage(err), true);
      })
      .then(function () {
        setBusy("resetting", false);
        $("reset-btn").disabled = false;
      });
  }

  // ---------- tabs and manual forms ----------

  function selectTab(name) {
    ["ai", "manual", "product", "ask"].forEach(function (tab) {
      var active = tab === name;
      $("tab-" + tab).setAttribute("aria-selected", active ? "true" : "false");
      $("tab-" + tab).tabIndex = active ? 0 : -1;
      $("panel-" + tab).hidden = !active;
    });
  }

  function randomKey() {
    var bytes = new Uint8Array(12);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(bytes);
    else for (var i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    return Array.prototype.map
      .call(bytes, function (n) {
        return ("0" + n.toString(16)).slice(-2);
      })
      .join("");
  }

  function validDigits(raw, min) {
    return /^\d+$/.test(raw) && Number(raw) >= min && Number(raw) <= 100000;
  }
  function formError(id, message) {
    var el = $(id);
    el.textContent = message || "";
    el.hidden = !message;
  }

  function renderManualProducts() {
    var select = $("manual-product"),
      selected = select.value;
    clearChildren(select);
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = tr("selectProductManual");
    select.appendChild(placeholder);
    state.products.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = productName(p) + " · " + unitLabel(p.unit, state.lang, 1);
      select.appendChild(opt);
    });
    select.value = selected;
  }
  function renderUnitOptions() {
    var select = $("product-unit"),
      selected = select.value;
    clearChildren(select);
    ["carton", "bag", "tin", "packet", "box", "piece"].forEach(function (u) {
      var opt = document.createElement("option");
      opt.value = u;
      opt.textContent = unitLabel(u, state.lang, 1);
      select.appendChild(opt);
    });
    select.value = selected || "carton";
  }
  function manualChanged() {
    state.manualKey = null;
    state.manualServerError = "";
    state.manualTouched = true;
    updateManual();
  }
  function updateManual() {
    var row = null,
      id = $("manual-product").value,
      raw = $("manual-qty").value;
    state.stock.forEach(function (r) {
      if (r.product.id === id) row = r;
    });
    var valid = validDigits(raw, 1),
      after =
        row && valid
          ? row.qty + (state.manualDirection === "in" ? Number(raw) : -Number(raw))
          : null;
    var localError =
      state.manualTouched && !valid
        ? tr("invalidQuantity")
        : after !== null && after < 0
          ? tr("insufficientManual")
          : "";
    formError("manual-error", localError || state.manualServerError || "");
    $("manual-save").disabled = !row || !valid || !!localError || !!state.busy.manual;
    var preview = $("manual-preview");
    clearChildren(preview);
    if (row) {
      preview.appendChild(
        document.createTextNode(
          tr("preview", {
            before: "\u0001",
            after: "\u0002",
            unit: unitLabel(row.product.unit, state.lang, after),
          }).split("\u0001")[0],
        ),
      );
      var rest =
        tr("preview", {
          before: "\u0001",
          after: "\u0002",
          unit: unitLabel(row.product.unit, state.lang, after),
        }).split("\u0001")[1] || "";
      preview.appendChild(bdi(row.qty));
      preview.appendChild(document.createTextNode(rest.split("\u0002")[0]));
      preview.appendChild(bdi(after === null ? "–" : after));
      preview.appendChild(document.createTextNode(rest.split("\u0002")[1] || ""));
    }
  }
  function saveManual(e) {
    e.preventDefault();
    updateManual();
    if ($("manual-save").disabled) {
      if (!validDigits($("manual-qty").value, 1)) formError("manual-error", tr("invalidQuantity"));
      return;
    }
    var id = $("manual-product").value,
      qty = Number($("manual-qty").value),
      dir = state.manualDirection,
      note = $("manual-reason").value.trim() || (dir === "in" ? "manual add" : "manual remove");
    if (!state.manualKey) state.manualKey = randomKey();
    state.busy.manual = true;
    updateManual();
    api("/api/confirm", {
      method: "POST",
      body: {
        confirm_key: state.manualKey,
        lines: [{ product_id: id, qty: qty, direction: dir }],
        note: note,
      },
    })
      .then(function (data) {
        state.manualKey = null;
        refreshFromStateShape(data);
        state.lastSaved = (data.saved || []).map(function (m) {
          return m.id;
        });
        $("manual-qty").value = "";
        $("manual-reason").value = "";
        state.manualTouched = false;
        state.manualServerError = "";
        showToast();
      })
      .catch(function (err) {
        state.manualServerError = errorMessage(err);
      })
      .then(function () {
        state.busy.manual = false;
        updateManual();
      });
  }
  function productChanged() {
    state.productKey = null;
    formError("product-error", "");
  }
  function saveProduct(e) {
    e.preventDefault();
    if (state.busy.product) return;
    var name = $("product-name-en").value.trim(),
      ur = $("product-name-ur").value.trim(),
      raw = $("product-aliases").value;
    var aliases = raw
      ? raw
          .split(",")
          .map(function (a) {
            return a.trim();
          })
          .filter(function (a) {
            return !!a;
          })
      : [];
    var low = $("product-low").value,
      error = "";
    if (name.length < 2 || name.length > 60) error = tr("invalidName");
    else if (ur.length > 60) error = tr("invalidUrduName");
    else if (
      aliases.length > 8 ||
      aliases.some(function (a) {
        return a.length > 40;
      })
    )
      error = tr("invalidAliases");
    else if (!validDigits(low, 0)) error = tr("invalidThreshold");
    if (error) {
      formError("product-error", error);
      return;
    }
    if (!state.productKey) state.productKey = randomKey();
    state.busy.product = true;
    $("product-save").disabled = true;
    api("/api/products", {
      method: "POST",
      body: {
        key: state.productKey,
        product: {
          name_en: name,
          name_ur: ur,
          aliases: aliases,
          unit: $("product-unit").value,
          low_threshold: Number(low),
        },
      },
    })
      .then(function (data) {
        state.productKey = null;
        refreshFromStateShape(data);
        $("product-form").reset();
        renderUnitOptions();
        formError("product-error", "");
        state.lastSaved = [];
        showToast(tr("productAdded", { name: productName(data.created) }));
        selectTab("manual");
        $("manual-product").value = data.created.id;
        state.manualDirection = "in";
        renderManualDirection();
        manualChanged();
        $("manual-qty").focus();
      })
      .catch(function (err) {
        formError("product-error", errorMessage(err));
      })
      .then(function () {
        state.busy.product = false;
        $("product-save").disabled = false;
      });
  }
  function renderManualDirection() {
    ["in", "out"].forEach(function (dir) {
      var btn = $("manual-" + dir);
      btn.classList.toggle("active", state.manualDirection === dir);
      btn.setAttribute("aria-pressed", state.manualDirection === dir ? "true" : "false");
    });
  }

  // ---------- wiring ----------

  function init() {
    applyLangToDocument();
    applyTranslations();
    renderUnitOptions();
    if (window.innerWidth >= 900) $("recent-section").open = true;
    ["ai", "manual", "product", "ask"].forEach(function (tab) {
      $("tab-" + tab).addEventListener("click", function () {
        selectTab(tab);
      });
    });
    ["all", "low", "out"].forEach(function (filter) {
      $("filter-" + filter).addEventListener("click", function () {
        setFilter(filter);
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll(".overview-card"), function (btn) {
      btn.addEventListener("click", function () {
        setFilter(btn.getAttribute("data-filter"));
      });
    });
    $("stock-search").addEventListener("input", renderStock);
    $("manual-product").addEventListener("change", manualChanged);
    $("manual-qty").addEventListener("input", manualChanged);
    $("manual-reason").addEventListener("input", manualChanged);
    ["in", "out"].forEach(function (dir) {
      $("manual-" + dir).addEventListener("click", function () {
        state.manualDirection = dir;
        renderManualDirection();
        manualChanged();
      });
    });
    $("manual-form").addEventListener("submit", saveManual);
    [
      "product-name-en",
      "product-name-ur",
      "product-aliases",
      "product-unit",
      "product-low",
    ].forEach(function (id) {
      $(id).addEventListener("input", productChanged);
      $(id).addEventListener("change", productChanged);
    });
    $("product-form").addEventListener("submit", saveProduct);

    $("lang-en").addEventListener("click", function () {
      setLang("en");
    });
    $("lang-ur").addEventListener("click", function () {
      setLang("ur");
    });
    $("reset-btn").addEventListener("click", resetDemo);

    $("example-btn").addEventListener("click", nextExample);
    $("check-btn").addEventListener("click", checkEntry);
    $("entry-text").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        checkEntry();
      }
    });

    $("cancel-btn").addEventListener("click", cancelProposals);
    $("confirm-btn").addEventListener("click", confirmProposals);

    $("toast-undo").addEventListener("click", undoLastSave);

    $("chip-low").addEventListener("click", function () {
      var q = state.lang === "ur" ? "کس چیز کا سٹاک کم ہے؟" : "What is low on stock?";
      $("ask-text").value = q;
      askQuestion(q);
    });
    $("chip-today").addEventListener("click", function () {
      var q = state.lang === "ur" ? "آج کیا ہوا؟" : "What happened today?";
      $("ask-text").value = q;
      askQuestion(q);
    });
    $("chip-reorder").addEventListener("click", function () {
      var q = "kal kya mangwana hai?";
      $("ask-text").value = q;
      askQuestion(q);
    });
    $("ask-btn").addEventListener("click", function () {
      askQuestion($("ask-text").value.trim());
    });
    $("ask-text").addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        askQuestion($("ask-text").value.trim());
      }
    });

    loadState();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
