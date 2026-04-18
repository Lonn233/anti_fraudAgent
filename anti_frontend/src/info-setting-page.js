import { getMe, updateMeProfile } from "/ui/src/user-api.js";

function setValue(id, value, fallback = "-") {
  const el = document.getElementById(id);
  if (!el) return;
  const text = value && String(value).trim() ? String(value) : fallback;
  if ("value" in el) {
    el.value = text;
  } else {
    el.textContent = text;
  }
}

function buildBirthText(birthDate) {
  if (!birthDate) return "-";
  const parts = String(birthDate).split("-");
  if (parts.length >= 3) {
    return `${parts[0]}年${parts[1]}月${parts[2]}日`;
  }
  return String(birthDate);
}

function calcGroup(age) {
  if (age == null || Number.isNaN(Number(age))) return "-";
  const n = Number(age);
  if (n <= 18) return "儿童";
  if (n <= 54) return "青壮年";
  return "老人";
}

function calcAgeFromBirthDate(birthDate) {
  if (!birthDate) return null;
  const parts = String(birthDate).split("-");
  if (parts.length < 3) return null;
  const y = Number(parts[0]);
  const m = Number(parts[1]);
  const d = Number(parts[2]);
  if (!y || !m || !d) return null;
  const now = new Date();
  let age = now.getFullYear() - y;
  const thisYearBirthdayPassed =
    now.getMonth() + 1 > m || (now.getMonth() + 1 === m && now.getDate() >= d);
  if (!thisYearBirthdayPassed) age -= 1;
  return Math.max(age, 0);
}

function isValidUsername(username) {
  return /^[\s\S]{4,8}$/.test(username);
}

function isValidPhone(phone) {
  return /^\d{11}$/.test(phone);
}

const JOB_MAP = {
  学生: ["小学生", "中学生", "大学生", "研究生", "博士生"],
  教育行业: ["小学老师", "中学老师", "大学老师", "导师", "教授", "校长", "辅导员", "幼教"],
  金融行业: ["银行职员", "证券", "基金", "保险", "会计", "审计", "投资"],
  "互联网与 IT": ["前端开发", "后端开发", "测试", "产品", "设计", "运维", "数据分析"],
  服务业: ["餐饮", "零售", "物流", "酒店", "安保", "家政", "美容"],
  医疗健康: ["医生", "护士", "药师", "医技", "护理", "健康管理"],
  制造业: ["普工", "技工", "工程师", "质检", "管理"],
  自由职业: ["设计师", "摄影师", "博主", "家教", "独立顾问"],
  其他: ["其他职业"],
};

const REGION_MAP = {
  北京市: ["北京"],
  天津市: ["天津"],
  河北省: ["石家庄", "唐山", "秦皇岛", "邯郸", "邢台", "保定", "张家口", "承德", "沧州", "廊坊", "衡水"],
  山西省: ["太原", "大同", "阳泉", "长治", "晋城", "朔州", "晋中", "运城", "忻州", "临汾", "吕梁"],
  内蒙古自治区: ["呼和浩特", "包头", "乌海", "赤峰", "通辽", "鄂尔多斯", "呼伦贝尔", "巴彦淖尔", "乌兰察布", "兴安盟", "锡林郭勒盟", "阿拉善盟"],
  辽宁省: ["沈阳", "大连", "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛"],
  吉林省: ["长春", "吉林", "四平", "辽源", "通化", "白山", "松原", "白城", "延边朝鲜族自治州"],
  黑龙江省: ["哈尔滨", "齐齐哈尔", "鸡西", "鹤岗", "双鸭山", "大庆", "伊春", "佳木斯", "七台河", "牡丹江", "黑河", "绥化", "大兴安岭地区"],
  上海市: ["上海"],
  江苏省: ["南京", "无锡", "徐州", "常州", "苏州", "南通", "连云港", "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁"],
  浙江省: ["杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水"],
  安徽省: ["合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"],
  福建省: ["福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩", "宁德"],
  江西省: ["南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶"],
  山东省: ["济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂", "德州", "聊城", "滨州", "菏泽"],
  河南省: ["郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店"],
  湖北省: ["武汉", "黄石", "十堰", "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施土家族苗族自治州"],
  湖南省: ["长沙", "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西土家族苗族自治州"],
  广东省: ["广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮"],
  广西壮族自治区: ["南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左"],
  海南省: ["海口", "三亚", "三沙", "儋州"],
  重庆市: ["重庆"],
  四川省: ["成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充", "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "阿坝", "甘孜", "凉山"],
  贵州省: ["贵阳", "六盘水", "遵义", "安顺", "毕节", "铜仁", "黔西南", "黔东南", "黔南"],
  云南省: ["昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "楚雄", "红河", "文山", "西双版纳", "大理", "德宏", "怒江", "迪庆"],
  西藏自治区: ["拉萨", "日喀则", "昌都", "林芝", "山南市", "那曲", "阿里"],
  陕西省: ["西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康", "商洛"],
  甘肃省: ["兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西", "陇南", "临夏", "甘南"],
  青海省: ["西宁", "海东", "海北", "黄南", "海南", "果洛", "玉树", "海西"],
  宁夏回族自治区: ["银川", "石嘴山", "吴忠", "固原", "中卫"],
  新疆维吾尔自治区: ["乌鲁木齐", "克拉玛依", "吐鲁番", "哈密", "昌吉", "博尔塔拉", "巴音郭楞", "阿克苏", "克孜勒苏", "喀什", "和田", "伊犁", "塔城", "阿勒泰"],
  香港特别行政区: ["香港"],
  澳门特别行政区: ["澳门"],
  台湾省: ["台北", "新北", "桃园", "台中", "台南", "高雄", "基隆", "新竹", "嘉义", "苗栗", "彰化", "南投", "云林", "嘉义县", "屏东", "宜兰", "花莲", "台东", "澎湖"],
};

let snapshot = null;
/** @type {string} */
let defaultAvatarSrc = "";

const AVATAR_MAX_BYTES = 5 * 1024 * 1024;
const AVATAR_MAX_SIDE = 512;
const AVATAR_ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];

function avatarStorageKey(userId) {
  return `anti_fraud_profile_avatar_${userId}`;
}

function applyAvatarDisplay() {
  const img = document.getElementById("profile-avatar-img");
  if (!img || snapshot == null || snapshot.id == null) return;
  const raw = localStorage.getItem(avatarStorageKey(snapshot.id));
  if (raw && typeof raw === "string" && raw.startsWith("data:image")) {
    img.src = raw;
  } else {
    img.src = defaultAvatarSrc || img.src;
  }
}

/**
 * @param {File} file
 * @returns {Promise<string>}
 */
function fileToResizedDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.onload = () => {
      const url = reader.result;
      if (typeof url !== "string") {
        reject(new Error("读取文件失败"));
        return;
      }
      const image = new Image();
      image.onload = () => {
        let w = image.naturalWidth;
        let h = image.naturalHeight;
        const scale = Math.min(1, AVATAR_MAX_SIDE / Math.max(w, h, 1));
        w = Math.max(1, Math.round(w * scale));
        h = Math.max(1, Math.round(h * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("无法处理图片"));
          return;
        }
        ctx.drawImage(image, 0, 0, w, h);
        let quality = 0.88;
        let dataUrl = canvas.toDataURL("image/jpeg", quality);
        while (dataUrl.length > 480000 && quality > 0.42) {
          quality -= 0.06;
          dataUrl = canvas.toDataURL("image/jpeg", quality);
        }
        if (dataUrl.length > 520000) {
          reject(new Error("压缩后仍过大，请换一张更小的图片"));
          return;
        }
        resolve(dataUrl);
      };
      image.onerror = () => reject(new Error("无法解析图片"));
      image.src = url;
    };
    reader.readAsDataURL(file);
  });
}

function bindAvatarUpload() {
  const input = document.getElementById("profile-avatar-input");
  const trigger = document.getElementById("profile-avatar-trigger");
  const errEl = document.getElementById("profile-avatar-error");
  const img = document.getElementById("profile-avatar-img");

  if (!input || !trigger || !img) return;

  trigger.addEventListener("click", () => {
    if (errEl) errEl.textContent = "";
    input.click();
  });

  input.addEventListener("change", async () => {
    if (errEl) errEl.textContent = "";
    const file = input.files && input.files[0];
    input.value = "";
    if (!file || snapshot == null || snapshot.id == null) return;

    if (!AVATAR_ALLOWED_TYPES.includes(file.type)) {
      if (errEl) errEl.textContent = "请使用 JPG、PNG、WebP 或 GIF 图片";
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      if (errEl) errEl.textContent = "文件不能超过 5MB";
      return;
    }

    try {
      const dataUrl = await fileToResizedDataUrl(file);
      localStorage.setItem(avatarStorageKey(snapshot.id), dataUrl);
      img.src = dataUrl;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "上传失败";
      if (errEl) errEl.textContent = msg;
    }
  });
}

const usernameError = document.getElementById("profile-username-error");
const birthError = document.getElementById("profile-birth-error");
const jobError = document.getElementById("profile-job-error");
const regionError = document.getElementById("profile-region-error");

function clearFieldErrors() {
  if (usernameError) usernameError.textContent = "";
  if (birthError) birthError.textContent = "";
  if (jobError) jobError.textContent = "";
  if (regionError) regionError.textContent = "";
}

function setFieldError(field, message) {
  const map = {
    username: usernameError,
    birth: birthError,
    job: jobError,
    region: regionError,
  };
  const target = map[field];
  if (target) target.textContent = message;
}

function hasSelectedValue(selectEl) {
  return !!selectEl && selectEl.selectedIndex > 0 && String(selectEl.value || "").trim() !== "";
}

function fillSelect(select, options, placeholder) {
  if (!select) return;
  select.innerHTML = "";
  const first = document.createElement("option");
  first.value = "";
  first.disabled = true;
  first.selected = true;
  first.textContent = placeholder;
  select.appendChild(first);
  options.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item;
    opt.textContent = item;
    select.appendChild(opt);
  });
}

function populateBirthSelects() {
  const y = document.getElementById("profile-birth-year");
  const m = document.getElementById("profile-birth-month");
  const d = document.getElementById("profile-birth-day");
  if (!y || !m || !d) return;
  const yearNow = new Date().getFullYear();
  fillSelect(y, Array.from({ length: yearNow - 1949 }, (_, i) => `${yearNow - i}`), "年");
  fillSelect(m, Array.from({ length: 12 }, (_, i) => `${i + 1}`), "月");
  fillSelect(d, [], "日");

  const refreshDays = () => {
    const yy = Number(y.value);
    const mm = Number(m.value);
    if (!yy || !mm) {
      fillSelect(d, [], "日");
      return;
    }
    const days = new Date(yy, mm, 0).getDate();
    fillSelect(d, Array.from({ length: days }, (_, i) => `${i + 1}`), "日");
  };
  y.addEventListener("change", () => {
    fillSelect(m, Array.from({ length: 12 }, (_, i) => `${i + 1}`), "月");
    fillSelect(d, [], "日");
  });
  m.addEventListener("change", refreshDays);
}

function populateCascades() {
  const jobCategory = document.getElementById("profile-job-category");
  const jobSub = document.getElementById("profile-job-subcategory");
  const prov = document.getElementById("profile-region-province");
  const city = document.getElementById("profile-region-city");
  fillSelect(jobCategory, Object.keys(JOB_MAP), "选择职业大类");
  fillSelect(jobSub, [], "选择职业小类");
  fillSelect(prov, Object.keys(REGION_MAP), "选择省市");
  fillSelect(city, [], "选择城市");

  jobCategory?.addEventListener("change", () => {
    fillSelect(jobSub, JOB_MAP[jobCategory.value] || [], "选择职业小类");
  });
  prov?.addEventListener("change", () => {
    fillSelect(city, REGION_MAP[prov.value] || [], "选择城市");
  });
}

function applySnapshot() {
  if (!snapshot) return;
  applyAvatarDisplay();
  setValue("profile-system-id", snapshot.username || `USER_${snapshot.id}`);
  setValue("profile-username", snapshot.username);
  setValue("profile-phone", snapshot.phone);
  setValue("profile-birth-date", buildBirthText(snapshot.birth_date));
  setValue("profile-group", calcGroup(snapshot.age));
  setValue("profile-occupation-display", snapshot.job);

  const profileGroup = document.getElementById("profile-group");
  const jobCategory = document.getElementById("profile-job-category");
  const jobSub = document.getElementById("profile-job-subcategory");
  const prov = document.getElementById("profile-region-province");
  const city = document.getElementById("profile-region-city");
  const by = document.getElementById("profile-birth-year");
  const bm = document.getElementById("profile-birth-month");
  const bd = document.getElementById("profile-birth-day");

  profileGroup.innerHTML = calcGroup(snapshot.age);
  if (jobCategory) {
    jobCategory.value = snapshot.occupation_category || "";
    fillSelect(jobSub, JOB_MAP[jobCategory.value] || [], "选择职业小类");
  }
  if (jobSub) jobSub.value = snapshot.occupation_subcategory || "";

  if (prov) {
    prov.value = snapshot.region_province || "";
    fillSelect(city, REGION_MAP[prov.value] || [], "选择城市");
  }
  if (city) city.value = snapshot.region_city || "";

  if (snapshot.birth_date && by && bm && bd) {
    const parts = String(snapshot.birth_date).split("-");
    by.value = parts[0] || "";
    by.dispatchEvent(new Event("change"));
    bm.value = String(Number(parts[1] || 0)) || "";
    bm.dispatchEvent(new Event("change"));
    bd.value = String(Number(parts[2] || 0)) || "";
  } else if (by && bm && bd) {
    by.value = "";
    by.dispatchEvent(new Event("change"));
  }
}

async function loadMe() {
  const me = await getMe();
  snapshot = me;
  applySnapshot();
}

function bindActions() {
  const saveBtn = document.getElementById("profile-save-btn");
  const cancelBtn = document.getElementById("profile-cancel-btn");
  const errorBox = document.getElementById("profile-save-error");
  const successBox = document.getElementById("profile-save-success");
  const usernameInput = document.getElementById("profile-username");
  const birthYearSelect = document.getElementById("profile-birth-year");
  const birthMonthSelect = document.getElementById("profile-birth-month");
  const birthDaySelect = document.getElementById("profile-birth-day");
  const jobCategorySelect = document.getElementById("profile-job-category");
  const jobSubcategorySelect = document.getElementById("profile-job-subcategory");
  const provinceSelect = document.getElementById("profile-region-province");
  const citySelect = document.getElementById("profile-region-city");

  usernameInput?.addEventListener("input", () => setFieldError("username", ""));
  usernameInput?.addEventListener("input", () => {
    if (successBox) successBox.textContent = "";
  });
  [birthYearSelect, birthMonthSelect, birthDaySelect].forEach((el) =>
    el?.addEventListener("change", () => {
      setFieldError("birth", "");
      if (successBox) successBox.textContent = "";
    })
  );
  [jobCategorySelect, jobSubcategorySelect].forEach((el) =>
    el?.addEventListener("change", () => {
      setFieldError("job", "");
      if (successBox) successBox.textContent = "";
    })
  );
  [provinceSelect, citySelect].forEach((el) =>
    el?.addEventListener("change", () => {
      setFieldError("region", "");
      if (successBox) successBox.textContent = "";
    })
  );

  if (cancelBtn) {
    cancelBtn.addEventListener("click", (event) => {
      event.preventDefault();
      if (errorBox) errorBox.textContent = "";
      if (successBox) successBox.textContent = "";
      clearFieldErrors();
      applySnapshot();
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      if (errorBox) errorBox.textContent = "";
      if (successBox) successBox.textContent = "";
      clearFieldErrors();

      const username = document.getElementById("profile-username")?.value?.trim() || "";
      const phone = document.getElementById("profile-phone")?.value?.trim() || "";
      const occupationCategory = document.getElementById("profile-job-category")?.value || null;
      const occupationSubcategory = document.getElementById("profile-job-subcategory")?.value || null;
      const regionProvince = document.getElementById("profile-region-province")?.value || null;
      const regionCity = document.getElementById("profile-region-city")?.value || null;
      const birthYear = document.getElementById("profile-birth-year")?.value || "";
      const birthMonth = document.getElementById("profile-birth-month")?.value || "";
      const birthDay = document.getElementById("profile-birth-day")?.value || "";
      const birthYearSelectEl = document.getElementById("profile-birth-year");
      const birthMonthSelectEl = document.getElementById("profile-birth-month");
      const birthDaySelectEl = document.getElementById("profile-birth-day");
      const birthDate = birthYear && birthMonth && birthDay
        ? `${birthYear}-${birthMonth.padStart(2, "0")}-${birthDay.padStart(2, "0")}`
        : null;

      if (!isValidUsername(username)) {
        setFieldError("username", "用户名需为4-8位");
        return;
      }
      if (!isValidPhone(phone)) {
        if (errorBox) errorBox.textContent = "手机号需为11位数字";
        return;
      }
      if (!hasSelectedValue(birthYearSelectEl) || !hasSelectedValue(birthMonthSelectEl) || !hasSelectedValue(birthDaySelectEl)) {
        setFieldError("birth", "请完整选择出生日期");
        return;
      }
      if (!occupationCategory || !occupationSubcategory) {
        setFieldError("job", "请完整选择职业（大类+小类）");
        return;
      }
      if (!regionProvince || !regionCity) {
        setFieldError("region", "请完整选择省市（省份+城市）");
        return;
      }

      try {
        const updated = await updateMeProfile({
          username,
          phone,
          birth_date: birthDate,
          occupation_category: occupationCategory || null,
          occupation_subcategory: occupationSubcategory || null,
          region_province: regionProvince || null,
          region_city: regionCity || null,
        });
        snapshot = updated;
        applySnapshot();
        if (successBox) successBox.textContent = "更改成功";
      } catch (err) {
        const message = err?.message || "保存失败";
        if (message.includes("Username already exists")) {
          setFieldError("username", "用户名已存在");
          return;
        }
        if (message.includes("Phone already exists")) {
          if (errorBox) errorBox.textContent = "手机号已存在";
          return;
        }
        if (errorBox) errorBox.textContent = message;
      }
    });
  }
}

(async function initInfoSetting() {
  try {
    const avatarImg = document.getElementById("profile-avatar-img");
    if (avatarImg && avatarImg.src) defaultAvatarSrc = avatarImg.src;
    populateBirthSelects();
    populateCascades();
    await loadMe();
    bindActions();
    bindAvatarUpload();
  } catch (_err) {
    window.location.href = "/ui/Login.html";
  }
})();
