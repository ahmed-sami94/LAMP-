"use strict";
const $ = (selector) => document.querySelector(selector);
let overview = { sites: [], backups: [], jobs: [], metrics: {} };
const csrf = $('meta[name="csrf-token"]').content;
const escapeHTML = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const date = (epoch) => new Date(epoch * 1000).toLocaleString();
const gb = (bytes) =>
  bytes == null ? "Unavailable" : (bytes / 1073741824).toFixed(1) + " GB";
function notice(message, error = false) {
  const el = $("#notice");
  el.textContent = message;
  el.classList.toggle("error", error);
  el.hidden = false;
}
async function action(name, data) {
  const response = await fetch("/api/actions/" + name, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify(data),
  });
  if (response.status === 401) {
    location.assign("/login");
    throw new Error("Session expired");
  }
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || "Operation could not be queued.");
  notice("Operation queued.");
  await refresh();
  return result;
}
function renderSites() {
  const filter = $("#search").value.toLowerCase();
  const rows = overview.sites.filter((site) =>
    (site.hostname + site.title).toLowerCase().includes(filter),
  );
  $("#site-list").innerHTML = rows.length
    ? `<table><thead><tr><th>Website</th><th>Application</th><th>Status</th><th>PHP memory</th><th>Actions</th></tr></thead><tbody>${rows.map(siteRow).join("")}</tbody></table>`
    : '<div class="empty">No websites found.</div>';
}
function siteRow(site) {
  const application = {
    empty: "Custom PHP / HTML",
    wordpress: "WordPress",
    joomla: "Joomla",
  }[site.cms];
  const address = `${location.protocol}//${site.hostname}${location.port ? ":" + location.port : ""}/`;
  const actions =
    site.status === "ready"
      ? `<div class="row-actions">
    <button class="icon" data-settings="${site.id}" title="PHP and backup settings" aria-label="Settings for ${escapeHTML(site.hostname)}"><img class="control-icon" src="/static/icons/settings.svg" alt=""></button>
    <button class="icon" data-backup="${site.id}" title="Create recovery point" aria-label="Back up ${escapeHTML(site.hostname)}"><img class="control-icon" src="/static/icons/archive.svg" alt=""></button>
    </div>`
      : "Setup incomplete";
  const host =
    site.status === "ready"
      ? `<a href="${escapeHTML(address)}" target="_blank" rel="noopener">${escapeHTML(site.hostname)}</a>`
      : escapeHTML(site.hostname);
  return `<tr><td><strong>${escapeHTML(site.title)}</strong><small>${host}</small></td>
    <td>${escapeHTML(application)}</td><td><span class="status ${escapeHTML(site.status)}">${escapeHTML(site.status)}</span></td>
    <td>${site.php.memory} MB</td><td>${actions}</td></tr>`;
}
function render() {
  renderSites();
  const metrics = overview.metrics;
  const healthy = Object.values(metrics.services).filter(Boolean).length;
  $("#metrics").innerHTML =
    `<div class="metric"><small>Websites</small><strong>${overview.sites.filter((s) => s.status === "ready").length}</strong><span>active</span></div><div class="metric"><small>Services</small><strong>${healthy} / ${Object.keys(metrics.services).length}</strong><span>responding</span></div><div class="metric"><small>Volume space</small><strong>${gb(metrics.storage_free)}</strong><span>available</span></div>`;
  $("#service-list").innerHTML =
    Object.entries(metrics.services)
      .map(
        ([name, up]) =>
          `<div class="service"><strong>${escapeHTML(name)}</strong><span class="status ${up ? "" : "failed"}">${up ? "Responding" : "Unavailable"}</span></div>`,
      )
      .join("") +
    `<div class="service"><strong>Container memory</strong><span>${gb(metrics.memory_bytes)} / ${metrics.memory_limit == null ? "No cgroup limit" : gb(metrics.memory_limit)}</span></div>`;
  $("#metric-scope").textContent = metrics.scope;
  $("#backup-list").innerHTML = overview.backups.length
    ? `<table><thead><tr><th>Website</th><th>Created</th><th>Recovery</th></tr></thead><tbody>${overview.backups.map((item) => `<tr><td>${escapeHTML(item.hostname)}</td><td>${date(item.created)}</td><td><button data-restore="${item.id}">Restore</button></td></tr>`).join("")}</tbody></table>`
    : '<div class="empty">No recovery points yet.</div>';
  $("#job-list").innerHTML = overview.jobs.length
    ? overview.jobs
        .map(
          (job) =>
            `<div class="job"><div><p><strong>${escapeHTML(job.action)}</strong> &middot; ${escapeHTML(job.message)}</p><small>${date(job.created)}</small></div><span class="status ${escapeHTML(job.status)}">${escapeHTML(job.status)}</span></div>`,
        )
        .join("")
    : '<div class="empty">No recent operations.</div>';
  $("#updated").textContent = "Measured " + date(metrics.measured_at);
}
async function refresh() {
  try {
    const response = await fetch("/api/overview");
    if (response.status === 401) return location.assign("/login");
    if (!response.ok)
      throw new Error("Measurements unavailable. Retrying shortly.");
    overview = await response.json();
    render();
  } catch (error) {
    notice(error.message, true);
    $("#updated").textContent = "Connection unavailable";
  }
}
document.querySelectorAll("[data-view]").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll("[data-view]")
      .forEach((tab) => tab.removeAttribute("aria-current"));
    button.setAttribute("aria-current", "page");
    document.querySelectorAll(".view").forEach((section) => {
      section.hidden = section.id !== button.dataset.view;
    });
    $("#heading").textContent = button.textContent;
  }),
);
$("#new-site").addEventListener("click", () => $("#site-dialog").showModal());
document
  .querySelectorAll(".close")
  .forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close()),
  );
$("#site-form select").addEventListener("change", (event) => {
  $("#cms-fields").hidden = event.target.value === "empty";
  $("#cms-fields")
    .querySelectorAll("input")
    .forEach((input) => {
      input.required = !$("#cms-fields").hidden;
    });
});
function handleForm(selector, handler) {
  $(selector).addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await handler(form);
      form.closest("dialog").close();
    } catch (error) {
      form.closest("dialog").close();
      notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
}
handleForm("#site-form", async (form) => {
  await action("site.create", Object.fromEntries(new FormData(form)));
  form.reset();
  $("#cms-fields").hidden = true;
  $("#cms-fields")
    .querySelectorAll("input")
    .forEach((input) => {
      input.required = false;
    });
});
handleForm("#settings-form", async (form) => {
  const data = Object.fromEntries(new FormData(form));
  await action("php.update", {
    site: data.site,
    memory: Number(data.memory),
    upload: Number(data.upload),
    timeout: Number(data.timeout),
  });
  await action("backup.schedule", {
    site: data.site,
    enabled: form.elements.enabled.checked,
    retention: Number(data.retention),
  });
});
handleForm("#restore-form", (form) =>
  action("backup.restore", Object.fromEntries(new FormData(form))),
);
$("#search").addEventListener("input", renderSites);
document.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.settings) {
    const site = overview.sites.find((s) => s.id === button.dataset.settings);
    const form = $("#settings-form");
    $("#settings-host").textContent = site.hostname;
    form.elements.site.value = site.id;
    ["memory", "upload", "timeout"].forEach((key) => {
      form.elements[key].value = site.php[key];
    });
    form.elements.enabled.checked = site.daily_backup;
    form.elements.retention.value = site.retention;
    $("#settings-dialog").showModal();
  }
  if (button.dataset.backup) {
    button.disabled = true;
    try {
      await action("backup.create", { site: button.dataset.backup });
    } catch (error) {
      notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  }
  if (button.dataset.restore) {
    const item = overview.backups.find((b) => b.id === button.dataset.restore);
    const form = $("#restore-form");
    form.reset();
    form.elements.site.value = item.site;
    form.elements.backup.value = item.id;
    $("#restore-target").textContent =
      item.hostname + " / " + date(item.created);
    $("#restore-dialog").showModal();
  }
});
refresh();
setInterval(refresh, 5000);
