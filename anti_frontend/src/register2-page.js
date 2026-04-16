import { register } from "/ui/src/auth-api.js";

const form = document.getElementById("register2-form");
const errorBox = document.getElementById("register2-error");
const birthError = document.getElementById("register2-birth-error");
const jobError = document.getElementById("register2-job-error");
const regionError = document.getElementById("register2-region-error");

function isValidUsername(username) {
  return /^[\s\S]{4,8}$/.test(username);
}
// console.log("1241");
function isValidPhone(phone) {
  return /^\d{11}$/.test(phone);
}

function clearFieldErrors() {
  if (birthError) birthError.textContent = "";
  if (jobError) jobError.textContent = "";
  if (regionError) regionError.textContent = "";
}

function setFieldError(field, message) {
  const map = {
    birth: birthError,
    job: jobError,
    region: regionError,
  };
  const target = map[field];
  if (target) target.textContent = message;
}

function valueOf(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}

function hasSelectedValue(id) {
  const el = document.getElementById(id);
  return !!el && el.selectedIndex > 0 && String(el.value || "").trim() !== "";
}

if (form) {
  ["birth-year", "birth-month", "birth-day"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => setFieldError("birth", ""));
  });
  ["job-category", "job-subcategory"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => setFieldError("job", ""));
  });
  ["region-province", "region-city"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => setFieldError("region", ""));
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (errorBox) errorBox.textContent = "";
    clearFieldErrors();

    const draftRaw = sessionStorage.getItem("register_draft");
    if (!draftRaw) {
      if (errorBox) errorBox.textContent = "注册第一步信息不存在，请返回上一步";
      return;
    }

    const draft = JSON.parse(draftRaw);
    if (!isValidUsername((draft.username || "").trim()) || !isValidPhone((draft.phone || "").trim())) {
      if (errorBox) errorBox.textContent = "第一步账号信息不符合要求，请返回上一步修改";
      return;
    }
    const birthYear = valueOf("birth-year")?.trim();
const birthMonth = valueOf("birth-month")?.trim();
const birthDay = valueOf("birth-day")?.trim();

const occupationCategory = valueOf("job-category")?.trim();
const occupationSubcategory = valueOf("job-subcategory")?.trim();

const regionProvince = valueOf("region-province")?.trim();
const regionCity = valueOf("region-city")?.trim();

if (!occupationCategory || !occupationSubcategory) {
  setFieldError("job", "请完整选择职业（大类+小类）");
  return;
}
if (!regionProvince || !regionCity) {
  setFieldError("region", "请完整选择省市（省份+城市）");
  return;
}
// 关键在这里：必须判断 “空 或者 未选择”
if (!hasSelectedValue("birth-year") || !hasSelectedValue("birth-month") || !hasSelectedValue("birth-day")) {
  setFieldError("birth", "请完整选择出生日期");
  return;
}


    const payload = {
      username: draft.username,
      phone: draft.phone,
      password: draft.password,
      birth_date: `${birthYear}-${birthMonth}-${birthDay}`,
      occupation_category: occupationCategory,
      occupation_subcategory: occupationSubcategory,
      region_province: regionProvince,
      region_city: regionCity,
    };

    try {
      await register(payload);
      sessionStorage.removeItem("register_draft");
      window.location.href = "/ui/Login.html";
    } catch (err) {
      if (errorBox) errorBox.textContent = err.message || "注册失败，请重试";
    }
  });
}
