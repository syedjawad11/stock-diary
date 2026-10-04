/* Stock Diary frontend logic. Plain JS, no build step, no frameworks.
   Talks to the FastAPI backend described in API.md. */

(function () {
  "use strict";

  // ---------- state ----------
  var state = {
    lang: loadLang(),
    stock: [],       // [{product, qty, is_low}]
    recent: [],       // [Movement]
    quota: { used_today: 0, limit_today: 30 },
    products: [],     // flat list of Product, derived from stock
    proposals: [],    // mutable working copy of /api/parse proposals
    confirmKey: null,
    originalText: "",
    exampleIndex: 0,
    busy: {
      checking: false,
      confirming: false,
      asking: false,
      resetting: false,
    },
    lastSaved: [],    // movement ids from the last confirm, for the toast Undo
  };

  // ---------- small helpers ----------

  function $(id) { return document.getElementById(id); }

  function loadLang() {
    try {
      var v = localStorage.getItem("sd_lang");
      if (v === "en" || v === "ur") return v;
    } catch (e) { /* storage unavailable: fall through */ }
    return "en";
  }

  function saveLang(lang) {
    try { localStorage.setItem("sd_lang", lang); } catch (e) { /* ignore */ }
  }

  function tr(key, vars) { return t(state.lang, key, vars); }

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
    return state.lang === "ur" ? product.name_ur : product.name_en;
  }

  function errorMessage(err) {
    if (err && err.network) return tr("errorNetwork");
    if (err && err.error === "rate_limited") return tr("rateLimited");
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

    return fetch(path, fetchOpts).catch(function () {
      return Promise.reject({ network: true });
    }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (data) {
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
    renderProposals();
    renderRecent();
    // answer card keeps whatever was last asked; re-render with new language text
    if (state.lastAnswer) renderAnswer(state.lastAnswer);
  }

  // ---------- quota ----------

  function renderQuota() {
    $("quota-text").textContent = tr("quotaText", {
      used: state.quota.used_today,
      limit: state.quota.limit_today,
    });
  }

  // ---------- stock ----------

  function renderStock() {
    var list = $("stock-list");
    clearChildren(list);
    if (!state.stock.length) return;
    state.stock.forEach(function (row) {
      var item = document.createElement("div");
      item.className = "stock-row";

      var nameEl = document.createElement("span");
      nameEl.className = "stock-name";
      nameEl.textContent = productName(row.product);
      item.appendChild(nameEl);

      var qtyWrap = document.createElement("span");
      qtyWrap.className = "stock-qty";
      qtyWrap.appendChild(bdi(row.qty));
      qtyWrap.appendChild(document.createTextNode(" " + unitLabel(row.product.unit, state.lang, row.qty)));
      item.appendChild(qtyWrap);

      if (row.is_low) {
        var badge = document.createElement("span");
        badge.className = "badge badge-low";
        badge.textContent = tr("low");
        item.appendChild(badge);
      }
      list.appendChild(item);
    });
  }

  function refreshFromStateShape(data) {
    state.stock = data.stock || [];
    state.recent = data.recent || [];
    state.quota = data.quota || state.quota;
    state.products = state.stock.map(function (r) { return r.product; });
    renderQuota();
    renderStock();
    renderRecent();
  }

  function loadState() {
    return api("/api/state").then(function (data) {
      refreshFromStateShape(data);
    }).catch(function (err) {
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

    api("/api/parse", { method: "POST", body: { text: text } }).then(function (data) {
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
    }).catch(function (err) {
      showStatus("parse-status", errorMessage(err), true);
    }).then(function () {
      setBusy("checking", false);
      $("check-btn").disabled = false;
      $("example-btn").disabled = false;
    });
  }

  // ---------- proposals (check-before-saving cards) ----------

  function currentStockMap() {
    var map = {};
    state.stock.forEach(function (row) { map[row.product.id] = row.qty; });
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
      p.problem = after < 0 ? "insufficient_stock" : null;
    });
  }

  function anyProposalProblem() {
    return state.proposals.some(function (p) { return !!p.problem; });
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
      if (!seen[c.id]) { seen[c.id] = true; options.push(c); }
    });
    state.products.forEach(function (p) {
      if (!seen[p.id]) { seen[p.id] = true; options.push(p); }
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
        var v = parseInt(qtyInput.value, 10);
        p.qty = (v > 0) ? v : 1;
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
      dirLabel.textContent = (p.direction === "in" ? tr("directionIn") : tr("directionOut")) + " " + sign;
      balanceLine.appendChild(dirLabel);
      balanceLine.appendChild(bdi(p.qty));

      var stockLine = document.createElement("span");
      stockLine.className = "balance-stock";
      stockLine.appendChild(document.createTextNode(tr("stockWord") + " "));
      stockLine.appendChild(bdi(p.balance_before === null || p.balance_before === undefined ? "–" : p.balance_before));
      stockLine.appendChild(document.createTextNode(" → "));
      stockLine.appendChild(bdi(p.balance_after === null || p.balance_after === undefined ? "–" : p.balance_after));
      balanceLine.appendChild(stockLine);
      card.appendChild(balanceLine);

      if (p.problem) {
        var problemEl = document.createElement("div");
        problemEl.className = "proposal-problem";
        problemEl.textContent = problemText(p.problem);
        card.appendChild(problemEl);
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
    }).then(function (data) {
      refreshFromStateShape(data);
      state.lastSaved = (data.saved || []).map(function (m) { return m.id; });
      $("entry-text").value = "";
      cancelProposals();
      showToast();
    }).catch(function (err) {
      var el = $("confirm-error");
      el.textContent = errorMessage(err);
      el.hidden = false;
    }).then(function () {
      setBusy("confirming", false);
      $("cancel-btn").disabled = false;
      renderProposals();
    });
  }

  // ---------- toast / undo ----------

  var toastTimer = null;

  function showToast() {
    var toast = $("toast");
    $("toast-msg").textContent = tr("savedToast");
    $("toast-undo").disabled = false;
    toast.hidden = false;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; }, 8000);
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
    if (!state.lastSaved.length) { hideToast(); return; }
    $("toast-undo").disabled = true;
    undoMovements(state.lastSaved.slice()).then(function () {
      state.lastSaved = [];
      hideToast();
    }).catch(function (err) {
      $("toast-msg").textContent = errorMessage(err);
      $("toast-undo").disabled = false;
    });
  }

  function undoSingleMovement(id, btn) {
    btn.disabled = true;
    api("/api/undo", { method: "POST", body: { movement_id: id } }).then(function (data) {
      refreshFromStateShape(data);
    }).catch(function (err) {
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
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } catch (e) { return iso; }
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

      var qtyEl = document.createElement("span");
      qtyEl.className = "recent-qty " + (m.direction === "in" ? "qty-in" : "qty-out");
      qtyEl.appendChild(document.createTextNode((m.direction === "in" ? "+" : "-")));
      qtyEl.appendChild(bdi(m.qty));
      if (prod) qtyEl.appendChild(document.createTextNode(" " + unitLabel(prod.unit, state.lang, m.qty)));
      top.appendChild(qtyEl);

      row.appendChild(top);

      var meta = document.createElement("div");
      meta.className = "recent-meta";
      var noteEl = document.createElement("span");
      noteEl.className = "recent-note";
      noteEl.textContent = m.note;
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
    card.hidden = false;
  }

  function askQuestion(text) {
    if (state.busy.asking || !text) return;
    setBusy("asking", true);
    $("ask-btn").disabled = true;
    $("chip-low").disabled = true;
    $("chip-today").disabled = true;
    showStatus("ask-status", tr("asking"), false);

    api("/api/ask", { method: "POST", body: { text: text } }).then(function (data) {
      showStatus("ask-status", "", false);
      state.lastAnswer = data;
      renderAnswer(data);
    }).catch(function (err) {
      showStatus("ask-status", errorMessage(err), true);
    }).then(function () {
      setBusy("asking", false);
      $("ask-btn").disabled = false;
      $("chip-low").disabled = false;
      $("chip-today").disabled = false;
    });
  }

  // ---------- reset ----------

  function resetDemo() {
    if (state.busy.resetting) return;
    if (!window.confirm(tr("resetConfirm"))) return;
    setBusy("resetting", true);
    $("reset-btn").disabled = true;
    api("/api/reset", { method: "POST", body: {} }).then(function (data) {
      refreshFromStateShape(data);
      cancelProposals();
      $("entry-text").value = "";
      hideToast();
      $("answer-card").hidden = true;
      state.lastAnswer = null;
    }).catch(function (err) {
      showStatus("parse-status", errorMessage(err), true);
    }).then(function () {
      setBusy("resetting", false);
      $("reset-btn").disabled = false;
    });
  }

  // ---------- wiring ----------

  function init() {
    applyLangToDocument();
    applyTranslations();

    $("lang-en").addEventListener("click", function () { setLang("en"); });
    $("lang-ur").addEventListener("click", function () { setLang("ur"); });
    $("reset-btn").addEventListener("click", resetDemo);

    $("example-btn").addEventListener("click", nextExample);
    $("check-btn").addEventListener("click", checkEntry);
    $("entry-text").addEventListener("keydown", function (e) {
      if ((e.key === "Enter") && (e.metaKey || e.ctrlKey)) {
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
