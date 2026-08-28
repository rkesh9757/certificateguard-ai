(() => {
  "use strict";

  // ============================================================
  // CertificateGuard AI - Frontend ↔ Flask Backend
  // ============================================================

  const API_BASE = "http://127.0.0.1:5000/api";

  let activeTab = "upload";
  let uploadedFile = null;

  // ============================================================
  // Element references
  // ============================================================

  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");

  const previewWrap = document.getElementById("previewWrap");
  const previewImg = document.getElementById("previewImg");
  const clearFileBtn = document.getElementById("clearFile");

  const manualForm = document.getElementById("manualForm");
  const runBtn = document.getElementById("runBtn");

  const ocrStatus = document.getElementById("ocrStatus");
  const ocrBarFill = document.getElementById("ocrBarFill");
  const ocrStatusText = document.getElementById("ocrStatusText");

  const reportEmpty = document.getElementById("reportEmpty");
  const reportBody = document.getElementById("reportBody");

  const reportId = document.getElementById("reportId");
  const reportTime = document.getElementById("reportTime");

  const verdictSeal = document.getElementById("verdictSeal");
  const verdictLabel = document.getElementById("verdictLabel");
  const sealArcText = document.getElementById("sealArcText");

  const confidenceDial = document.getElementById("confidenceDial");
  const confidenceNum = document.getElementById("confidenceNum");
  const confidenceDesc = document.getElementById("confidenceDesc");

  const extractedGrid = document.getElementById("extractedGrid");
  const evidenceLog = document.getElementById("evidenceLog");

  const printBtn = document.getElementById("printBtn");


  // ============================================================
  // Tabs
  // ============================================================

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      activeTab = btn.dataset.tab;

      tabBtns.forEach(b => {
        b.classList.toggle("is-active", b === btn);
        b.setAttribute(
          "aria-selected",
          b === btn ? "true" : "false"
        );
      });

      tabPanels.forEach(panel => {
        panel.classList.toggle(
          "is-active",
          panel.dataset.panel === activeTab
        );
      });
    });
  });


  // ============================================================
  // File upload
  // ============================================================

  function setFile(file) {
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Please upload an image file such as JPG, PNG or WEBP.");
      return;
    }

    uploadedFile = file;

    const url = URL.createObjectURL(file);

    previewImg.src = url;
    previewWrap.hidden = false;
  }


  if (fileInput) {
    fileInput.addEventListener("change", event => {
      const file = event.target.files[0];

      if (file) {
        setFile(file);
      }
    });
  }


  if (dropzone) {

    ["dragenter", "dragover"].forEach(eventName => {
      dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        dropzone.classList.add("is-dragover");
      });
    });


    ["dragleave", "drop"].forEach(eventName => {
      dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        dropzone.classList.remove("is-dragover");
      });
    });


    dropzone.addEventListener("drop", event => {
      const file = event.dataTransfer.files[0];

      if (file) {
        setFile(file);
      }
    });
  }


  if (clearFileBtn) {
    clearFileBtn.addEventListener("click", () => {

      uploadedFile = null;

      if (fileInput) {
        fileInput.value = "";
      }

      if (previewImg) {
        previewImg.removeAttribute("src");
      }

      if (previewWrap) {
        previewWrap.hidden = true;
      }
    });
  }


  // ============================================================
  // Helper: safely escape HTML
  // ============================================================

  function escapeHtml(value) {

    return String(value ?? "").replace(/[&<>"']/g, char => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[char]));
  }


  // ============================================================
  // Show OCR progress
  // ============================================================

  function showOCRStatus(message, percentage) {

    if (!ocrStatus) return;

    ocrStatus.hidden = false;

    if (ocrBarFill) {
      ocrBarFill.style.width = `${percentage}%`;
    }

    if (ocrStatusText) {
      ocrStatusText.textContent = message;
    }
  }


  // ============================================================
  // Reset OCR status
  // ============================================================

  function resetOCRStatus() {

    if (!ocrStatus) return;

    ocrStatus.hidden = true;

    if (ocrBarFill) {
      ocrBarFill.style.width = "0%";
    }

    if (ocrStatusText) {
      ocrStatusText.textContent = "";
    }
  }


  // ============================================================
  // Backend request
  // ============================================================

  async function sendToBackend(endpoint, options = {}) {

    const response = await fetch(`${API_BASE}${endpoint}`, options);

    let data;

    try {
      data = await response.json();
    } catch {
      throw new Error(
        `Backend returned an invalid response. HTTP ${response.status}`
      );
    }

    if (!response.ok) {
      throw new Error(
        data.error || `Verification failed. HTTP ${response.status}`
      );
    }

    return data;
  }


  // ============================================================
  // Upload verification
  // ============================================================

  async function verifyUploadedCertificate() {

    if (!uploadedFile) {
      alert(
        "Please upload a certificate image first, or switch to manual entry."
      );
      return;
    }

    resetOCRStatus();

    showOCRStatus(
      "Uploading certificate to CertificateGuard AI...",
      10
    );

    const formData = new FormData();

    formData.append("file", uploadedFile);


    showOCRStatus(
      "Sending certificate to the verification engine...",
      25
    );


    const result = await sendToBackend(
      "/verify/upload",
      {
        method: "POST",
        body: formData
      }
    );


    showOCRStatus(
      "OCR and verification completed.",
      100
    );


    renderReport(result);

    setTimeout(() => {
      if (ocrStatus) {
        ocrStatus.hidden = true;
      }
    }, 1500);
  }


  // ============================================================
  // Manual verification
  // ============================================================

  async function verifyManualCertificate() {

    if (!manualForm) {
      throw new Error("Manual verification form was not found.");
    }


    const formData = new FormData(manualForm);


    const fields = {

      candidateName:
        (formData.get("candidateName") || "").trim(),

      institution:
        (formData.get("institution") || "").trim(),

      certId:
        (formData.get("certId") || "").trim(),

      issueDate:
        (formData.get("issueDate") || "").trim(),

      course:
        (formData.get("course") || "").trim()
    };


    if (
      !fields.candidateName &&
      !fields.institution &&
      !fields.certId
    ) {

      alert(
        "Please fill in at least the candidate name, institution and certificate ID."
      );

      return;
    }


    const result = await sendToBackend(
      "/verify/manual",
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json"
        },

        body: JSON.stringify(fields)
      }
    );


    renderReport(result);
  }


  // ============================================================
  // Run verification button
  // ============================================================

  if (runBtn) {

    runBtn.addEventListener("click", async () => {

      runBtn.disabled = true;

      const originalText = runBtn.textContent;

      runBtn.textContent = "Verifying...";


      try {

        if (activeTab === "upload") {

          await verifyUploadedCertificate();

        } else {

          await verifyManualCertificate();

        }

      } catch (error) {

        console.error("CertificateGuard error:", error);

        alert(
          "Something went wrong while analyzing the certificate.\n\n" +
          error.message
        );

      } finally {

        runBtn.disabled = false;

        runBtn.textContent = originalText;
      }
    });
  }


  // ============================================================
  // Render verification report
  // ============================================================

  function renderReport(result) {

    if (!result) return;


    if (reportEmpty) {
      reportEmpty.hidden = true;
    }

    if (reportBody) {
      reportBody.hidden = false;
    }


    // ----------------------------------------------------------
    // Report information
    // ----------------------------------------------------------

    if (reportId) {
      reportId.textContent =
        `REPORT #${result.reportId || "CG-UNKNOWN"}`;
    }


    if (reportTime) {

      let formattedTime;

      try {

        formattedTime = new Date(
          result.timestamp
        ).toLocaleString();

      } catch {

        formattedTime = new Date().toLocaleString();
      }

      reportTime.textContent = formattedTime;
    }


    // ----------------------------------------------------------
    // Verdict
    // ----------------------------------------------------------

    const verdict = result.verdict || "suspicious";

    const verdictMeta = {

      genuine: {
        text: "LIKELY\nGENUINE",
        cls: "v-genuine"
      },

      suspicious: {
        text: "SUSPICIOUS",
        cls: "v-suspicious"
      },

      fake: {
        text: "LIKELY\nFAKE",
        cls: "v-fake"
      }

    }[verdict] || {
      text: "SUSPICIOUS",
      cls: "v-suspicious"
    };


    if (verdictSeal) {

      verdictSeal.className =
        "verdict-seal " + verdictMeta.cls;


      const ring =
        verdictSeal.querySelector(".seal-ring");


      if (ring) {

        ring.style.animation = "none";

        void ring.offsetWidth;

        ring.style.animation = "";
      }
    }


    if (verdictLabel) {

      verdictLabel.innerHTML =
        verdictMeta.text
          .split("\n")
          .join("<br>");
    }


    if (sealArcText) {

      sealArcText.textContent =
        verdictMeta.text.replace("\n", " ") +
        " • CERTIFICATEGUARD • ";
    }


    // ----------------------------------------------------------
    // Score
    // ----------------------------------------------------------

    const score = Number(result.score) || 0;


    if (confidenceDial) {

      confidenceDial.style.setProperty(
        "--p",
        "0"
      );

      requestAnimationFrame(() => {

        confidenceDial.style.setProperty(
          "--p",
          String(score)
        );
      });
    }


    if (confidenceNum) {

      confidenceNum.textContent =
        `${score}%`;
    }


    if (confidenceDesc) {

      confidenceDesc.textContent = {

        genuine:
          "Most checks are consistent with a genuine certificate.",

        suspicious:
          "Some details couldn't be confirmed — manual review is recommended.",

        fake:
          "Multiple checks failed or conflict with verification records."

      }[verdict] ||
        "The certificate requires further review.";
    }


    // ----------------------------------------------------------
    // Extracted fields
    // ----------------------------------------------------------

    const fields = result.fields || {};


    const displayFields = [

      [
        "Candidate Name",
        fields.candidateName
      ],

      [
        "Institution",
        fields.institution
      ],

      [
        "Certificate ID",
        fields.certId
      ],

      [
        "Issue Date",
        fields.issueDate
      ],

      [
        "Course / Program",
        fields.course
      ]

    ];


    if (extractedGrid) {

      extractedGrid.innerHTML =
        displayFields.map(([label, value]) => {

          const displayValue =
            value
              ? escapeHtml(value)
              : `<span style="color:var(--ink-soft);font-weight:400;">Not found</span>`;

          return `
            <div>
              <dt>${escapeHtml(label)}</dt>
              <dd>${displayValue}</dd>
            </div>
          `;

        }).join("");
    }


    // ----------------------------------------------------------
    // Evidence / checks
    // ----------------------------------------------------------

    const checks = Array.isArray(result.checks)
      ? result.checks
      : [];


    if (evidenceLog) {

      evidenceLog.innerHTML = checks.map(check => {

        const tone =
          check.tone ||
          (check.pass ? "ok" : "warn");


        let icon = "!";

        if (tone === "ok") {
          icon = "✓";
        } else if (tone === "bad") {
          icon = "✕";
        }


        return `
          <li class="${escapeHtml(tone)}">

            <span class="ev-icon">
              ${icon}
            </span>

            <span>

              <strong>
                ${escapeHtml(check.label || "Verification check")}
              </strong>

              <span class="ev-detail">
                ${escapeHtml(check.detail || "")}
              </span>

            </span>

          </li>
        `;

      }).join("");
    }


    // ----------------------------------------------------------
    // Scroll to report
    // ----------------------------------------------------------

    if (reportBody) {

      reportBody.scrollIntoView({
        behavior: "smooth",
        block: "nearest"
      });
    }
  }


  // ============================================================
  // Print report
  // ============================================================

  if (printBtn) {

    printBtn.addEventListener(
      "click",
      () => window.print()
    );
  }


  // ============================================================
  // Backend connection test
  // ============================================================

  async function testBackendConnection() {

    try {

      const response = await fetch(
        `${API_BASE}/health`
      );

      if (!response.ok) {
        throw new Error("Backend unavailable");
      }

      const data = await response.json();

      console.log(
        "CertificateGuard backend:",
        data.status
      );

    } catch (error) {

      console.warn(
        "CertificateGuard backend is not reachable.",
        error
      );
    }
  }


  // Test connection when page loads
  testBackendConnection();

})();