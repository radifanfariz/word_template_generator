const state = {
  step: 1,
  mode: "single",
  templateFile: null,
  templateName: "",
  fields: [],
  csvFile: null,
  csvHeaders: [],
};

const panels = [1, 2, 3].map((n) => document.getElementById(`panel-${n}`));
const stepEls = [...document.querySelectorAll(".step")];
const templateInput = document.getElementById("template-input");
const templateLabel = document.getElementById("template-label");
const fieldsPreview = document.getElementById("fields-preview");
const fieldsList = document.getElementById("fields-list");
const singleForm = document.getElementById("single-form");
const csvInput = document.getElementById("csv-input");
const csvLabel = document.getElementById("csv-label");
const mappingWrap = document.getElementById("mapping-table-wrap");
const mappingBody = document.getElementById("mapping-body");
const filenameField = document.getElementById("filename-field");
const summary = document.getElementById("summary");
const statusEl = document.getElementById("status");

function setStep(step) {
  state.step = step;
  panels.forEach((panel, index) => {
    panel.classList.toggle("active", index + 1 === step);
  });
  stepEls.forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.step) === step);
  });
}

function showStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
  statusEl.classList.remove("hidden");
}

function clearStatus() {
  statusEl.classList.add("hidden");
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
  document.getElementById("single-mode").classList.toggle("active", mode === "single");
  document.getElementById("batch-mode").classList.toggle("active", mode === "batch");
}

function renderFields() {
  fieldsList.innerHTML = "";
  state.fields.forEach((field) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = field;
    fieldsList.appendChild(chip);
  });
  fieldsPreview.classList.toggle("hidden", state.fields.length === 0);

  singleForm.innerHTML = "";
  state.fields.forEach((field) => {
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    wrapper.innerHTML = `
      <label for="field-${field}">${field}</label>
      <input id="field-${field}" name="${field}" type="text" autocomplete="off" />
    `;
    singleForm.appendChild(wrapper);
  });

  mappingBody.innerHTML = "";
  filenameField.innerHTML = '<option value="">Auto (document_1, document_2, ...)</option>';

  state.fields.forEach((field) => {
    const row = document.createElement("tr");
    const options = ['<option value="">— skip —</option>']
      .concat(
        state.csvHeaders.map(
          (header) =>
            `<option value="${escapeHtml(header)}" ${
              header === field ? "selected" : ""
            }>${escapeHtml(header)}</option>`
        )
      )
      .join("");

    row.innerHTML = `
      <td><code>${escapeHtml(field)}</code></td>
      <td><select data-field="${escapeHtml(field)}">${options}</select></td>
    `;
    mappingBody.appendChild(row);
  });

  state.csvHeaders.forEach((header) => {
    const option = document.createElement("option");
    option.value = header;
    option.textContent = header;
    filenameField.appendChild(option);
  });
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function scanTemplate(file) {
  const formData = new FormData();
  formData.append("template", file);

  const response = await fetch("/api/templates/scan", {
    method: "POST",
    body: formData,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to scan template");
  }

  return payload;
}

async function handleTemplateFile(file) {
  if (!file.name.toLowerCase().endsWith(".docx")) {
    showStatus("Please upload a .docx file.", "error");
    return;
  }

  clearStatus();
  templateLabel.textContent = file.name;
  showStatus("Scanning template...", "info");

  try {
    const result = await scanTemplate(file);
    state.templateFile = file;
    state.templateName = result.filename;
    state.fields = result.fields || [];
    renderFields();
    document.getElementById("btn-to-2").disabled = state.fields.length === 0;
    showStatus(
      state.fields.length
        ? `Found ${state.fields.length} field(s).`
        : "No placeholders found. Add {{ field_name }} to your template.",
      state.fields.length ? "success" : "error"
    );
  } catch (error) {
    state.templateFile = null;
    state.fields = [];
    renderFields();
    document.getElementById("btn-to-2").disabled = true;
    showStatus(error.message, "error");
  }
}

function parseCsvHeaders(text) {
  const firstLine = text.split(/\r?\n/).find((line) => line.trim());
  if (!firstLine) {
    return [];
  }

  const headers = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < firstLine.length; i += 1) {
    const char = firstLine[i];
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === "," && !inQuotes) {
      headers.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  headers.push(current.trim());
  return headers.filter(Boolean);
}

async function handleCsvFile(file) {
  clearStatus();
  csvLabel.textContent = file.name;
  const text = await file.text();
  const headers = parseCsvHeaders(text);

  if (!headers.length) {
    state.csvFile = null;
    state.csvHeaders = [];
    mappingWrap.classList.add("hidden");
    showStatus("CSV must include a header row.", "error");
    return;
  }

  state.csvFile = file;
  state.csvHeaders = headers;
  renderFields();
  mappingWrap.classList.remove("hidden");
  showStatus(`Loaded CSV with ${headers.length} column(s).`, "success");
}

function getSingleData() {
  const data = {};
  state.fields.forEach((field) => {
    const input = document.getElementById(`field-${field}`);
    data[field] = input ? input.value : "";
  });
  return data;
}

function getFieldMapping() {
  const mapping = {};
  mappingBody.querySelectorAll("select[data-field]").forEach((select) => {
    if (select.value) {
      mapping[select.dataset.field] = select.value;
    }
  });
  return mapping;
}

function buildSummary() {
  const modeLabel = state.mode === "single" ? "Single document" : "Batch ZIP";
  const fieldList = state.fields.map((field) => `<code>${escapeHtml(field)}</code>`).join(", ");

  if (state.mode === "single") {
    const data = getSingleData();
    const rows = state.fields
      .map(
        (field) =>
          `<div><strong>${escapeHtml(field)}:</strong> ${escapeHtml(data[field] || "")}</div>`
      )
      .join("");

    summary.innerHTML = `
      <div><strong>Template:</strong> ${escapeHtml(state.templateName)}</div>
      <div><strong>Mode:</strong> ${modeLabel}</div>
      <div><strong>Fields:</strong> ${fieldList}</div>
      <div style="margin-top:12px">${rows}</div>
    `;
    return;
  }

  const mapping = getFieldMapping();
  const mapped = Object.entries(mapping)
    .map(
      ([field, column]) =>
        `<div><code>${escapeHtml(field)}</code> ← ${escapeHtml(column)}</div>`
    )
    .join("");

  summary.innerHTML = `
    <div><strong>Template:</strong> ${escapeHtml(state.templateName)}</div>
    <div><strong>Mode:</strong> ${modeLabel}</div>
    <div><strong>CSV:</strong> ${escapeHtml(state.csvFile?.name || "Not selected")}</div>
    <div><strong>Fields:</strong> ${fieldList}</div>
    <div style="margin-top:12px"><strong>Column mapping</strong></div>
    ${mapped || "<div class='muted'>No columns mapped yet.</div>"}
  `;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function filenameFromDisposition(header, fallback) {
  if (!header) {
    return fallback;
  }
  const match = header.match(/filename="?([^"]+)"?/i);
  return match ? match[1] : fallback;
}

async function generateSingle() {
  const formData = new FormData();
  formData.append("template", state.templateFile);
  formData.append("data", JSON.stringify(getSingleData()));

  const response = await fetch("/api/generate", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Generation failed");
  }

  const blob = await response.blob();
  const filename = filenameFromDisposition(
    response.headers.get("Content-Disposition"),
    "document.docx"
  );
  downloadBlob(blob, filename);
}

async function generateBatch() {
  if (!state.csvFile) {
    throw new Error("Upload a CSV file for batch generation.");
  }

  const mapping = getFieldMapping();
  if (!Object.keys(mapping).length) {
    throw new Error("Map at least one template field to a CSV column.");
  }

  const formData = new FormData();
  formData.append("template", state.templateFile);
  formData.append("csv_file", state.csvFile);
  formData.append("field_mapping", JSON.stringify(mapping));
  formData.append("filename_field", filenameField.value || "");

  const response = await fetch("/api/generate/batch", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Batch generation failed");
  }

  const blob = await response.blob();
  downloadBlob(blob, "documents.zip");
}

function wireDropzone(zoneId, inputId, onFile) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("dragover");
    const file = event.dataTransfer.files[0];
    if (file) {
      onFile(file);
    }
  });
  input.addEventListener("change", () => {
    const file = input.files[0];
    if (file) {
      onFile(file);
    }
  });
}

wireDropzone("template-dropzone", "template-input", handleTemplateFile);
wireDropzone("csv-dropzone", "csv-input", handleCsvFile);

document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
});

document.getElementById("btn-to-2").addEventListener("click", () => {
  clearStatus();
  setStep(2);
});

document.getElementById("btn-back-1").addEventListener("click", () => {
  clearStatus();
  setStep(1);
});

document.getElementById("btn-to-3").addEventListener("click", () => {
  clearStatus();
  buildSummary();
  setStep(3);
});

document.getElementById("btn-back-2").addEventListener("click", () => {
  clearStatus();
  setStep(2);
});

document.getElementById("btn-generate").addEventListener("click", async () => {
  if (!state.templateFile) {
    showStatus("Upload a template first.", "error");
    return;
  }

  const button = document.getElementById("btn-generate");
  button.disabled = true;
  showStatus("Generating...", "info");

  try {
    if (state.mode === "single") {
      await generateSingle();
      showStatus("Document downloaded.", "success");
    } else {
      await generateBatch();
      showStatus("ZIP downloaded.", "success");
    }
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    button.disabled = false;
  }
});
