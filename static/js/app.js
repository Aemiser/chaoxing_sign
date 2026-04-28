/* ============================================================
   超星学习通签到 - Frontend Logic
   ============================================================ */

// ============================================================
// State
// ============================================================

const state = {
    token: localStorage.getItem("cx_token") || "",
    name: localStorage.getItem("cx_name") || "",
    currentCourseId: "",
    currentClassId: "",
    pendingSign: null,         // { active_id, course_id, class_id, sign_type }
    qrEnc: "",                // parsed enc from QR
    locationLat: "",
    locationLng: "",
    locationAddr: "",
    qrStream: null,           // camera stream
    amap: null,               // AMap instance
    amapMarker: null,
    amapGeocoder: null,
};

// ============================================================
// Page Navigation
// ============================================================

function showPage(name, data) {
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    const page = document.getElementById("page-" + name);
    if (page) page.classList.add("active");

    if (name === "courses") loadCourses();
    if (name === "tasks" && data) loadTasks(data.course_id, data.class_id, data.name);
    if (name === "login") {
        document.getElementById("login-phone").value = "";
        document.getElementById("login-password").value = "";
    }
}

// ============================================================
// Toast
// ============================================================

function toast(msg, duration) {
    duration = duration || 2000;
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(el._timer);
    el._timer = setTimeout(function () { el.classList.remove("show"); }, duration);
}

// ============================================================
// API helper
// ============================================================

async function api(method, path, params) {
    params = params || {};
    if (state.token) params.token = state.token;

    var qs = Object.keys(params)
        .map(function (k) { return k + "=" + encodeURIComponent(params[k]); })
        .join("&");

    var url = "/api" + path + (qs ? "?" + qs : "");

    try {
        var resp = await fetch(url, { method: method || "GET" });
        if (!resp.ok) {
            var errText = await resp.text();
            throw new Error(errText || "请求失败");
        }
        return await resp.json();
    } catch (e) {
        toast(e.message || "网络错误", 2000);
        throw e;
    }
}

// ============================================================
// Login
// ============================================================

async function doLogin() {
    var phone = document.getElementById("login-phone").value.trim();
    var password = document.getElementById("login-password").value.trim();
    if (!phone || !password) {
        toast("请输入手机号和密码");
        return;
    }

    var btn = document.getElementById("login-btn");
    btn.disabled = true;
    btn.textContent = "登录中...";

    try {
        var data = await api("POST", "/login", { phone: phone, password: password });
        state.token = data.token;
        state.name = data.name;
        localStorage.setItem("cx_token", data.token);
        localStorage.setItem("cx_name", data.name);
        toast("登录成功");
        showPage("courses");
    } catch (e) {
        // error already toasted
    } finally {
        btn.disabled = false;
        btn.textContent = "登 录";
    }
}

function doLogout() {
    if (state.token) {
        api("POST", "/logout", {});
    }
    state.token = "";
    state.name = "";
    localStorage.removeItem("cx_token");
    localStorage.removeItem("cx_name");
    showPage("login");
}

// ============================================================
// Courses
// ============================================================

async function loadCourses() {
    var list = document.getElementById("course-list");
    list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        var data = await api("GET", "/courses");
        renderCourses(data.courses);
    } catch (e) {
        list.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
    }
}

function renderCourses(courses) {
    var list = document.getElementById("course-list");
    if (!courses || courses.length === 0) {
        list.innerHTML = '<div class="empty-state"><div class="empty-icon">📚</div><p>暂无课程</p></div>';
        return;
    }

    var icons = ["📖", "📕", "📗", "📘", "📙", "💻", "🔬", "🎨", "📐", "🌍"];
    var html = "";
    courses.forEach(function (c, i) {
        var ico = icons[i % icons.length];
        var teacher = c.teacher ? c.teacher.replace(/[^一-龥a-zA-Z]/g, "").substring(0, 12) : "";
        html += '<div class="course-item" onclick="openTasks(\'' + c.course_id + '\',\'' + c.class_id + '\',\'' + esc(c.name) + '\')">' +
            '<div class="ci-icon">' + ico + '</div>' +
            '<div class="ci-body">' +
            '<div class="ci-title">' + escHtml(c.name) + '</div>' +
            (teacher ? '<div class="ci-sub">' + escHtml(teacher) + '</div>' : '') +
            '</div>' +
            '<div class="ci-arrow">›</div>' +
            '</div>';
    });
    list.innerHTML = html;
}

function filterCourses() {
    var kw = document.getElementById("course-search").value.toLowerCase();
    var items = document.querySelectorAll("#course-list .course-item");
    items.forEach(function (item) {
        var text = item.textContent.toLowerCase();
        item.style.display = text.indexOf(kw) >= 0 ? "" : "none";
    });
}

function openTasks(courseId, classId, name) {
    state.currentCourseId = courseId;
    state.currentClassId = classId;
    showPage("tasks", { course_id: courseId, class_id: classId, name: name });
}

// ============================================================
// Tasks
// ============================================================

var _allTasks = [];

async function loadTasks(courseId, classId, name) {
    document.getElementById("task-course-name").textContent = name || "课程";
    var list = document.getElementById("task-list");
    list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        var data = await api("GET", "/tasks/" + courseId + "/" + classId);
        _allTasks = data.tasks;
        renderTasks(data.tasks);
    } catch (e) {
        list.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
    }
}

function renderTasks(tasks) {
    var list = document.getElementById("task-list");
    if (!tasks || tasks.length === 0) {
        list.innerHTML = '<div class="empty-state"><div class="empty-icon">✅</div><p>当前没有签到任务</p></div>';
        return;
    }

    var active = tasks.filter(function (t) { return t.status === "active"; });
    var ended = tasks.filter(function (t) { return t.status !== "active"; });

    var icons = { normal: "✍", photo: "📷", gesture: "✋", location: "📍", qrcode: "📱", code: "🔢" };
    var badges = { normal: "badge-normal", photo: "badge-photo", gesture: "badge-gesture", location: "badge-location", qrcode: "badge-qrcode", code: "badge-code" };
    var labels = { normal: "普通", photo: "拍照", gesture: "手势", location: "位置", qrcode: "二维码", code: "签到码" };

    var html = "";

    if (active.length > 0) {
        html += '<div class="section-title">进行中 (' + active.length + ')</div>';
        active.forEach(function (t) {
            var badgeCls = badges[t.sign_type] || "badge-normal";
            html += '<div class="task-item">' +
                '<div class="ti-icon">' + (icons[t.sign_type] || "✍") + '</div>' +
                '<div class="ti-body">' +
                '<div class="ti-title">' + escHtml(t.name) + '</div>' +
                (t.end_time ? '<div class="ti-time">结束: ' + formatTime(t.end_time) + '</div>' : '') +
                '</div>' +
                '<span class="ti-badge ' + badgeCls + '" onclick="startSign(\'' + t.active_id + '\',\'' + t.sign_type + '\',\'' + esc(t.name) + '\')">' + (labels[t.sign_type] || "签到") + '</span>' +
                '</div>';
        });
    }

    if (ended.length > 0) {
        html += '<div class="section-title">已结束 (' + ended.length + ')</div>';
        ended.forEach(function (t) {
            html += '<div class="task-item">' +
                '<div class="ti-icon">' + (icons[t.sign_type] || "✍") + '</div>' +
                '<div class="ti-body">' +
                '<div class="ti-title">' + escHtml(t.name) + '</div>' +
                '</div>' +
                '<span class="ti-badge badge-ended">已结束</span>' +
                '</div>';
        });
    }

    list.innerHTML = html;
}

function startSign(activeId, signType, name) {
    state.pendingSign = {
        active_id: activeId,
        course_id: state.currentCourseId,
        class_id: state.currentClassId,
        sign_type: signType,
        name: name,
    };

    if (signType === "qrcode") {
        openQrModal();
    } else if (signType === "location") {
        openLocationModal();
    } else {
        // 普通/拍照/手势/签到码 — 直接签到
        doDirectSign();
    }
}

async function doDirectSign() {
    if (!state.pendingSign) return;

    var s = state.pendingSign;
    toast("签到中...", 1500);
    try {
        var data = await api("POST", "/sign", {
            active_id: s.active_id,
            course_id: s.course_id,
            class_id: s.class_id,
            sign_type: s.sign_type,
        });
        if (data.ok) {
            toast("签到成功! 🎉");
            // 刷新任务列表
            loadTasks(s.course_id, s.class_id, "");
        } else {
            toast(data.message || "签到失败");
        }
    } catch (e) {
        // error toasted in api()
    }
    state.pendingSign = null;
}

// ============================================================
// QR Code Sign
// ============================================================

function openQrModal() {
    document.getElementById("modal-qr").classList.add("show");
    state.qrEnc = "";
    state._qrAutoSigned = false;  // 防止重复自动签到
    document.getElementById("qr-scan-result").textContent = "";
    document.getElementById("qr-file-result").textContent = "";
    document.getElementById("qr-text-result").textContent = "";
    document.getElementById("qr-text-input").value = "";
    document.getElementById("qr-enc-input").value = "";
    document.getElementById("qr-submit-btn").style.display = "none";
    switchQrTab("scan");
    startCamera();
}

function closeQrModal() {
    document.getElementById("modal-qr").classList.remove("show");
    stopCamera();
    state.pendingSign = null;
}

function switchQrTab(tab) {
    document.querySelectorAll("#qr-tabs .qr-tab").forEach(function (t) { t.classList.remove("active"); });
    document.querySelectorAll("[id^='qr-panel-']").forEach(function (p) { p.classList.remove("active"); });

    var tabEl = document.querySelector("#qr-tabs .qr-tab[data-tab='" + tab + "']");
    if (tabEl) tabEl.classList.add("active");

    var panel = document.getElementById("qr-panel-" + tab);
    if (panel) panel.classList.add("active");

    if (tab === "scan") startCamera();
    else stopCamera();

    // enc tab 显示提交按钮，其他 tab 隐藏（自动签到）
    var submitBtn = document.getElementById("qr-submit-btn");
    submitBtn.style.display = tab === "enc" ? "block" : "none";
}

// --- Camera ---

async function startCamera() {
    stopCamera();
    var video = document.getElementById("qr-video");
    var panel = document.getElementById("qr-panel-scan");
    if (!panel || !panel.classList.contains("active")) return;

    try {
        var stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 } }
        });
        state.qrStream = stream;
        video.srcObject = stream;
        video.play();
        scanQrLoop();
    } catch (e) {
        document.getElementById("qr-scan-result").textContent = "无法打开摄像头: " + e.message;
    }
}

function stopCamera() {
    if (state.qrStream) {
        state.qrStream.getTracks().forEach(function (t) { t.stop(); });
        state.qrStream = null;
    }
    var video = document.getElementById("qr-video");
    if (video) video.srcObject = null;
}

function scanQrLoop() {
    var video = document.getElementById("qr-video");
    var canvas = document.getElementById("qr-canvas");
    if (!state.qrStream || video.readyState < 2) {
        setTimeout(scanQrLoop, 200);
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    var ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    var code = jsQR(imageData.data, canvas.width, canvas.height);

    if (code) {
        var resultEl = document.getElementById("qr-scan-result");
        resultEl.textContent = "识别成功，正在签到...";
        resultEl.className = "qr-result success";
        stopCamera();
        parseQrData(code.data);
        return;
    }

    setTimeout(scanQrLoop, 150);
}

// --- File ---

function handleQrFile(event) {
    var file = event.target.files[0];
    if (!file) return;

    var img = new Image();
    img.onload = function () {
        var canvas = document.getElementById("qr-canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        var ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);

        var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        var code = jsQR(imageData.data, canvas.width, canvas.height);

        var resultEl = document.getElementById("qr-file-result");
        if (code) {
            resultEl.textContent = "识别成功，正在签到...";
            resultEl.className = "qr-result success";
            parseQrData(code.data);
        } else {
            resultEl.textContent = "未识别到二维码";
            resultEl.className = "qr-result error";
        }
    };
    img.src = URL.createObjectURL(file);
}

// --- Text ---

function parseQrText() {
    var text = document.getElementById("qr-text-input").value.trim();
    if (!text) {
        toast("请输入二维码内容");
        return;
    }
    var resultEl = document.getElementById("qr-text-result");
    resultEl.textContent = "已输入，正在签到...";
    resultEl.className = "qr-result success";
    parseQrData(text);
}

// --- Enc ---

// enc Tab 手动签到（唯一需要点击按钮的）
function doQrSign() {
    state.qrEnc = document.getElementById("qr-enc-input").value.trim();
    if (!state.qrEnc) {
        toast("请输入 enc 参数");
        return;
    }
    executeSign({ enc: state.qrEnc });
}

function parseQrData(data) {
    // 提取 enc
    var m = data.match(/enc=([a-zA-Z0-9_\-]+)/);
    if (m) {
        state.qrEnc = m[1];
    } else {
        state.qrEnc = data.trim();
    }
    // 扫码/文件/文字 自动签到，不等待手动点击
    doAutoSign();
}

// 自动签到（扫码、文件、文字 tab 识别成功后直接调用）
function doAutoSign() {
    if (!state.qrEnc) {
        toast("无法解析 enc 参数");
        return;
    }
    if (state._qrAutoSigned) return;  // 防止重复
    state._qrAutoSigned = true;
    executeSign({ enc: state.qrEnc });
}

// ============================================================
// Location Sign
// ============================================================

function openLocationModal() {
    document.getElementById("modal-location").classList.add("show");
    state.locationLat = "";
    state.locationLng = "";

    // Load AMap if needed
    if (window.AMap) {
        initMap();
    } else {
        loadAMap(initMap);
    }
}

function closeLocationModal() {
    document.getElementById("modal-location").classList.remove("show");
    state.pendingSign = null;
}

function loadAMap(cb) {
    // 高德地图 key — 用户需自行替换
    var key = localStorage.getItem("cx_amap_key") || "你的高德地图key";
    var script = document.createElement("script");
    script.src = "https://webapi.amap.com/maps?v=2.0&key=" + key + "&callback=amapReady";
    window.amapReady = function () { cb(); };
    document.head.appendChild(script);
}

function initMap() {
    if (state.amap) {
        state.amap.destroy();
    }

    var mapDiv = document.getElementById("location-map");
    mapDiv.innerHTML = "";

    var defaultPos = [116.404, 39.915]; // 北京

    state.amap = new AMap.Map("location-map", {
        zoom: 15,
        center: defaultPos,
        resizeEnable: true,
    });

    // 居中十字标记
    var pin = document.createElement("div");
    pin.className = "location-pin";
    pin.textContent = "📍";
    mapDiv.appendChild(pin);

    // 点击地图移动中心
    state.amap.on("click", function (e) {
        state.amap.setCenter([e.lnglat.lng, e.lnglat.lat]);
        updateLocationInfo(e.lnglat.lng, e.lnglat.lat);
    });

    // 首次定位
    state.amap.plugin("AMap.Geolocation", function () {
        var geo = new AMap.Geolocation({ enableHighAccuracy: true, timeout: 5000 });
        geo.getCurrentPosition(function (status, result) {
            if (status === "complete" && result.position) {
                var pos = [result.position.lng, result.position.lat];
                state.amap.setCenter(pos);
                updateLocationInfo(pos[0], pos[1]);
            } else {
                updateLocationInfo(defaultPos[0], defaultPos[1]);
            }
        });
    });

    // 逆地理编码
    state.amap.plugin("AMap.Geocoder", function () {
        state.amapGeocoder = new AMap.Geocoder({});
    });
}

function updateLocationInfo(lng, lat) {
    state.locationLng = String(lng);
    state.locationLat = String(lat);
    var info = document.getElementById("location-info");
    info.textContent = lat.toFixed(6) + ", " + lng.toFixed(6);

    if (state.amapGeocoder) {
        state.amapGeocoder.getAddress([lng, lat], function (status, result) {
            if (status === "complete" && result.regeocode) {
                var addr = result.regeocode.formattedAddress || "";
                info.textContent = addr;
                state.locationAddr = addr;
            }
        });
    }
}

function doLocationSign() {
    if (!state.locationLat || !state.locationLng) {
        toast("请在地图上点击选择位置");
        return;
    }

    executeSign({
        longitude: state.locationLng,
        latitude: state.locationLat,
        location_name: state.locationAddr || (state.locationLat + "," + state.locationLng),
    });
}

// ============================================================
// Execute Sign
// ============================================================

async function executeSign(extra) {
    var s = state.pendingSign;
    if (!s) return;

    // 对于直接签到（普通/手势/拍照/签到码），extra 为空
    extra = extra || {};

    toast("签到中...", 1500);
    try {
        var data = await api("POST", "/sign", {
            active_id: s.active_id,
            course_id: s.course_id,
            class_id: s.class_id,
            sign_type: s.sign_type,
            enc: extra.enc || state.qrEnc || "",
            longitude: extra.longitude || "",
            latitude: extra.latitude || "",
            location_name: extra.location_name || "",
        });

        if (data.ok) {
            toast("签到成功! 🎉", 2500);
            closeQrModal();
            closeLocationModal();
            state.pendingSign = null;
            setTimeout(function () { loadTasks(s.course_id, s.class_id, ""); }, 1500);
        } else {
            toast(data.message || "签到失败", 2500);
        }
    } catch (e) {
        // error toasted in api()
    }
}

// ============================================================
// Helpers
// ============================================================

function esc(s) {
    return (s || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function escHtml(s) {
    return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatTime(ts) {
    try {
        var d = new Date(Number(ts));
        if (isNaN(d.getTime())) return ts;
        var m = d.getMonth() + 1;
        var day = d.getDate();
        var h = d.getHours();
        var min = String(d.getMinutes()).padStart(2, "0");
        return m + "-" + day + " " + h + ":" + min;
    } catch (e) {
        return ts;
    }
}

// ============================================================
// Init
// ============================================================

(function init() {
    if (state.token) {
        // 验证 token 有效性
        api("GET", "/session").then(function (data) {
            if (data.ok) {
                state.name = data.name || state.name;
                showPage("courses");
            } else {
                state.token = "";
                localStorage.removeItem("cx_token");
                showPage("login");
            }
        }).catch(function () {
            showPage("login");
        });
    } else {
        showPage("login");
    }

    // 回车登录
    document.getElementById("login-password").addEventListener("keydown", function (e) {
        if (e.key === "Enter") doLogin();
    });
})();
