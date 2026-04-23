import { getDetectReportDetail } from "/ui/src/detect-api.js";

function setText(id, value, fallback = "-") {
  const el = document.getElementById(id);
  if (!el) return;
  const text = value == null || String(value).trim() === "" ? fallback : String(value);
  el.textContent = text;
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${y}.${m}.${d} ${hh}:${mm}:${ss}`;
}

function queryDetectId() {
  const qs = new URLSearchParams(window.location.search);
  const raw = qs.get("detect_id") || qs.get("id");
  const id = Number(raw);
  return Number.isFinite(id) && id > 0 ? id : null;
}

async function init() {
  const detectId = queryDetectId();
  if (!detectId) {
    throw new Error("缺少 detect_id 参数");
  }
  const data = await getDetectReportDetail(detectId);
  const overall = data?.overall_judgment || {};
  const rag = data?.rag_result || {};
  const multi = data?.multimodal_fusion_recognition || {};
  const personal = data?.personal_info_analysis || {};

  setText("report-detail-report-id", `AF-${data.report_id}`);
  setText("report-detail-time", formatTime(data.detect_time || data.created_at));
  setText("report-detail-risk-index", Number(data.risk_index || 0).toFixed(2));
  setText("report-detail-fraud-type", data.fraud_type || overall.fraud_type_rag);
  setText("report-detail-conclusion", overall.conclusion);
  setText("report-detail-prevention", overall.prevention_measures);
  setText("report-detail-post-actions", overall.post_fraud_actions);
  setText("report-detail-personal-analysis", personal.conclusion);
  setText("report-detail-rag-case", rag.retrieved_case);
  setText("report-detail-rag-similarity", rag.similarity == null ? "-" : Number(rag.similarity).toFixed(2));
  setText("report-detail-rag-reason", rag.retrieval_reason);
  setText("report-detail-ai-probability", multi.ai_synthesis_probability == null ? "-" : Number(multi.ai_synthesis_probability).toFixed(2));
  setText("report-detail-ai-reason", multi.judgment_reason);
}

init().catch((err) => {
  setText("report-detail-conclusion", err?.message || "报告加载失败");
});

export async function exportReportPdf() {
  const btn = document.getElementById("btn-export-pdf");
  if (btn) { btn.disabled = true; btn.textContent = "导出中…"; }

  const content = document.getElementById("pdf-content");
  const target = content || document.querySelector("main");

  try {
    const canvas = await html2canvas(target, {
      scale: 2,
      useCORS: true,
      backgroundColor: getComputedStyle(document.documentElement).getPropertyValue("--color-background").trim() || "#0f1923",
      logging: false,
    });

    const { jsPDF } = window.jspdf;
    const orientation = canvas.width > canvas.height ? "landscape" : "portrait";
    const pdf = new jsPDF({ orientation, unit: "px", format: [canvas.width / 2, canvas.height / 2] });

    const imgData = canvas.toDataURL("image/jpeg", 0.95);
    pdf.addImage(imgData, "JPEG", 0, 0, canvas.width / 2, canvas.height / 2);

    const reportId = document.getElementById("report-detail-report-id")?.textContent || "report";
    pdf.save(`反诈报告_${reportId.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, "_")}.pdf`);
  } catch (err) {
    console.error("PDF 导出失败:", err);
    alert("PDF 导出失败，请稍后重试。");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "导出PDF"; }
  }
}

window.exportReportPdf = exportReportPdf;
