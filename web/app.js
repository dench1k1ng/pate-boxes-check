const els = {
  input: document.querySelector("#messageInput"),
  parseBtn: document.querySelector("#parseBtn"),
  clearBtn: document.querySelector("#clearBtn"),
  sampleBtn: document.querySelector("#sampleBtn"),
  status: document.querySelector("#status"),
  total: document.querySelector("#totalCount"),
  ok: document.querySelector("#okCount"),
  review: document.querySelector("#reviewCount"),
  body: document.querySelector("#itemsBody"),
  tabs: [...document.querySelectorAll(".tab")],
  dryRunBtn: document.querySelector("#dryRunBtn"),
  sendCrmBtn: document.querySelector("#sendCrmBtn"),
  uploadReport: document.querySelector("#uploadReport"),
};

let items = [];
let filter = "all";

const sample = `Пате Ишим: 40%
улитка 2 шт
слойка творог 4 шт
фисташка малина 1 пор
лимон тарт макс 1

Пате Толе би
Безглютеновая галета с нектарином макси/мини 3480/1590 вместо 5800/2650

Туран
Банановые рогалики 1110тг вместо 1850тг 9уп
Круассаны 660тг вместо 1100тг 5 шт`;

function setStatus(text, tone = "idle") {
  els.status.textContent = text;
  els.status.dataset.tone = tone;
}

function money(value) {
  return typeof value === "number" ? `${value.toLocaleString("ru-RU")} ₸` : "нет";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function imageCell(item) {
  const src = item.images?.[0] ? `/images/${item.images[0]}` : "";
  const image = src
    ? `<img class="thumb" src="${escapeHtml(src)}" alt="">`
    : `<div class="thumb"></div>`;
  const raw = item.rawLine_name || item.rawLine || "";
  return `
    <div class="product">
      ${image}
      <div>
        <div class="name">${escapeHtml(item.name || item.matchedCanonical || raw)}</div>
        <div class="raw">${escapeHtml(raw)}</div>
      </div>
    </div>
  `;
}

function reasonCell(item) {
  const reasons = item.reviewReasons || [];
  if (!reasons.length) return `<span class="muted">без замечаний</span>`;
  return `
    <div class="reason-list">
      ${reasons.map((reason) => `<span class="reason">${escapeHtml(reason)}</span>`).join("")}
    </div>
  `;
}

function render() {
  const visible = items.filter((item) => {
    if (filter === "ok") return !item.needsReview;
    if (filter === "review") return item.needsReview;
    return true;
  });

  els.total.textContent = items.length;
  els.ok.textContent = items.filter((item) => !item.needsReview).length;
  els.review.textContent = items.filter((item) => item.needsReview).length;
  els.dryRunBtn.disabled = !items.length;
  els.sendCrmBtn.disabled = !items.some((item) => !item.needsReview);

  if (!visible.length) {
    els.body.innerHTML = `<tr class="empty"><td colspan="6">Нет позиций для этого фильтра.</td></tr>`;
    return;
  }

  els.body.innerHTML = visible
    .map((item) => {
      const badge = item.needsReview
        ? `<span class="badge review">Проверить</span>`
        : `<span class="badge ok">Сделал сам</span>`;
      return `
        <tr>
          <td>${badge}</td>
          <td>${escapeHtml(item.storeName || "")}</td>
          <td>${imageCell(item)}</td>
          <td>${money(item.price)}<div class="raw">вместо ${money(item.originalPrice)}</div></td>
          <td>${escapeHtml(item.stockQuantity ?? 1)}</td>
          <td>${reasonCell(item)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderUploadReport(data) {
  const summary = data.summary || {};
  const report = data.report || [];
  els.uploadReport.hidden = false;
  els.uploadReport.innerHTML = `
    <div class="upload-summary">
      <strong>${summary.dryRun ? "Проверка payload" : "Отправка в CRM"}</strong>
      <span>готово: ${summary.ok ?? 0}</span>
      <span>пропущено: ${summary.skipped ?? 0}</span>
      <span>ошибок: ${summary.failed ?? 0}</span>
    </div>
    <div class="upload-lines">
      ${report
        .slice(0, 12)
        .map((item) => {
          const tone = item.result === "ok" || item.result === "dry-run" ? "ok" : item.result === "skipped" ? "skip" : "fail";
          return `<div class="upload-line ${tone}">
            <span>${escapeHtml(item.result)}</span>
            <strong>${escapeHtml(item.name || "")}</strong>
            <em>${escapeHtml(item.reason || item.response_text || "")}</em>
          </div>`;
        })
        .join("")}
    </div>
  `;
}

async function uploadToCrm(dryRun) {
  if (!items.length) {
    setStatus("Сначала обработай сообщение", "warn");
    return;
  }

  const readyCount = items.filter((item) => !item.needsReview).length;
  if (!dryRun && readyCount === 0) {
    setStatus("Нет готовых позиций для CRM", "warn");
    return;
  }

  els.dryRunBtn.disabled = true;
  els.sendCrmBtn.disabled = true;
  setStatus(dryRun ? "Проверяю payload..." : "Отправляю в CRM...", "busy");

  try {
    const response = await fetch("/api/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items, dryRun, force: false }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Ошибка CRM");
    renderUploadReport(data);
    const summary = data.summary;
    setStatus(
      dryRun
        ? `Payload готов: ${summary.ok} можно отправлять, ${summary.skipped} пропущено`
        : `CRM: ${summary.ok} создано, ${summary.skipped} пропущено, ${summary.failed} ошибок`,
      summary.failed ? "error" : "ok",
    );
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    render();
  }
}

async function parseMessage() {
  const text = els.input.value.trim();
  if (!text) {
    setStatus("Вставь сообщение", "warn");
    return;
  }

  els.parseBtn.disabled = true;
  setStatus("Обрабатываю...", "busy");

  try {
    const response = await fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Ошибка парсинга");
    items = data.items || [];
    els.uploadReport.hidden = true;
    render();
    setStatus(`Готово: ${data.summary.ok} автоматически, ${data.summary.review} проверить`, "ok");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    els.parseBtn.disabled = false;
  }
}

els.parseBtn.addEventListener("click", parseMessage);
els.clearBtn.addEventListener("click", () => {
  els.input.value = "";
  items = [];
  els.uploadReport.hidden = true;
  render();
  setStatus("Готов к парсингу");
});
els.sampleBtn.addEventListener("click", () => {
  els.input.value = sample;
  els.input.focus();
});

els.tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    filter = tab.dataset.filter;
    els.tabs.forEach((item) => item.classList.toggle("active", item === tab));
    render();
  });
});

els.dryRunBtn.addEventListener("click", () => uploadToCrm(true));
els.sendCrmBtn.addEventListener("click", () => uploadToCrm(false));
