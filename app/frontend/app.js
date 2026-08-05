const $ = (id) => document.getElementById(id);

let currentRows = [];
let currentView = "dashboard";

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function firstDayOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function formatDate(value) {
  if (!value) return "";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}

function money(n) {
  return Number(n || 0).toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toast(msg, type = "ok") {
  const el = $("toast");
  el.textContent = msg;
  el.className = `toast show ${type}`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.classList.remove("show"), 4300);
}

function setBusy(busy, showLoader = true) {
  $("btnBuscar").disabled = busy;
  $("btnGenerar").disabled = busy || currentRows.length === 0;
  $("loadingOverlay").classList.toggle("show", busy && showLoader);
}

function navigate(viewName) {
  currentView = viewName;
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  $(`view-${viewName}`).classList.add("active");
  document.querySelector(`.nav-item[data-view="${viewName}"]`)?.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderRows(rows) {
  currentRows = rows;
  $("contador").textContent = String(rows.length);
  $("btnGenerar").disabled = rows.length === 0;

  const tbody = $("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty">No hay registros en las fechas consultadas.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map((r) => `<tr>
    <td title="${escapeHtml(r.local || "")}">${escapeHtml(r.local || "")}</td>
    <td class="mono">${escapeHtml(r.t_comp || "")}</td>
    <td class="mono" title="${escapeHtml(r.n_comp || "")}">${escapeHtml(r.n_comp || "")}</td>
    <td class="mono">${formatDate(r.fecha_emis)}</td>
    <td title="${escapeHtml(r.razon_soci || "")}">${escapeHtml(r.razon_soci || "")}</td>
    <td class="mono">${escapeHtml(r.identiftri || "")}</td>
    <td class="num">${money(r.importe_gravado)}</td>
    <td class="num">${money(r.importe)}</td>
    <td class="mono">${r.alicuota ?? ""}</td>
    <td title="${escapeHtml(r.desc_alic || "")}">${escapeHtml(r.desc_alic || "")}</td>
  </tr>`).join("");
}

function updateStatus(connected) {
  ["statusDot", "moduleStatusDot"].forEach((id) => {
    $(id).className = `dot ${connected ? "ok" : "bad"}`;
  });
  $("statusText").textContent = connected ? "Conectado" : "Desconectado";
  $("moduleStatusText").textContent = connected ? "Conectado" : "Desconectado";
}

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateStatus(Boolean(data.central_reachable));
  } catch {
    updateStatus(false);
  }
}

async function search() {
  const desde = $("desde").value;
  const hasta = $("hasta").value;
  if (!desde || !hasta) {
    toast("Completá las fechas Desde y Hasta.", "error");
    return;
  }
  if (desde > hasta) {
    toast("La fecha Desde no puede ser posterior a Hasta.", "error");
    return;
  }

  setBusy(true);
  $("errors").textContent = "";

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ desde, hasta, demo: false }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error en la consulta");

    $("branchesOk").textContent = data.branches_ok;
    $("branchesErr").textContent = data.branches_error;
    $("errors").textContent = data.errors?.join("\n") || "";
    renderRows(data.rows || []);

    $("dashRows").textContent = String(data.total || 0);
    $("dashBranches").textContent = String(data.branches_ok || 0);
    $("dashLastQuery").textContent =
      `${formatDate(desde)} al ${formatDate(hasta)} · ${data.total || 0} registros`;

    toast(
      data.total ? `Consulta terminada: ${data.total} registros.` : "No se encontraron registros.",
      data.total ? "ok" : "error"
    );
  } catch (err) {
    toast(err.message || String(err), "error");
  } finally {
    setBusy(false);
  }
}

function filenameFor(dateValue) {
  const [year, month, day] = dateValue.split("-");
  return `${Number(day)}-${Number(month)}-${year} ibper.txt`;
}

async function saveTxt() {
  if (!currentRows.length) return;
  setBusy(true, false);
  try {
    const hasta = $("hasta").value;
    const suggestedName = filenameFor(hasta);
    const res = await fetch("/api/generate-download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        desde: $("desde").value,
        hasta,
        rows: currentRows,
        demo: false,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "No se pudo generar el TXT");
    }

    const blob = await res.blob();

    // Edge/Chrome con contexto seguro: selector nativo "Guardar como".
    if ("showSaveFilePicker" in window) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName,
          types: [{
            description: "Archivo de texto ARBA",
            accept: { "text/plain": [".txt"] },
          }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        toast(`TXT guardado: ${handle.name}`, "ok");
        return;
      } catch (err) {
        if (err?.name === "AbortError") {
          toast("Guardado cancelado.", "error");
          return;
        }
        // Si el navegador no habilita el selector, descarga normal.
      }
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = suggestedName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("TXT generado. Elegí dónde guardarlo desde las descargas del navegador.", "ok");
  } catch (err) {
    toast(err.message || String(err), "error");
  } finally {
    setBusy(false);
  }
}

function init() {
  $("desde").value = firstDayOfMonth();
  $("hasta").value = isoToday();
  $("todayLabel").textContent = new Intl.DateTimeFormat("es-AR", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  }).format(new Date());

  document.querySelectorAll("[data-view]").forEach((el) => {
    el.addEventListener("click", () => navigate(el.dataset.view));
  });
  document.querySelectorAll("[data-view-target]").forEach((el) => {
    el.addEventListener("click", () => navigate(el.dataset.viewTarget));
  });
  document.querySelectorAll("[data-open]").forEach((el) => {
    el.addEventListener("click", () => navigate(el.dataset.open));
  });
  $("btnBuscar").addEventListener("click", search);
  $("btnGenerar").addEventListener("click", saveTxt);

  refreshStatus();

  // La bienvenida se luce una vez por carga y luego entrega el dashboard.
  setTimeout(() => {
    $("splash").classList.add("hide");
    $("appShell").classList.add("ready");
  }, 4700);
}

init();
