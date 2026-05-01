const { createApp, ref, computed, watch, onMounted, onUnmounted, nextTick } = Vue;

const app = createApp({
    data() {
        return {
            currentPage: 'login',

            // 认证
            token: localStorage.getItem('cx_token') || '',
            jwt: localStorage.getItem('cx_jwt') || '',
            uid: '',
            name: '',
            user: { id: 0, supernova_account: '', nickname: '' },

            // 登录表单
            loginPhone: localStorage.getItem('cx_phone') || '',
            loginPassword: '',
            loggingIn: false,

            // 加载状态
            loadingActive: false,
            loadingCourses: false,
            loadingFriends: false,

            // 课程
            courses: [],
            activeCourses: [],
            courseSearch: '',
            courseIcons: ['auto_stories', 'menu_book', 'import_contacts', 'book_2', 'dictionary', 'library_books', 'school', 'local_library'],

            // 任务
            currentCourseName: '',
            currentCourseId: '',
            currentClassId: '',
            currentTask: null,
            activeTasks: [],
            endedTasks: [],
            loadingTasks: false,

            // 签到类型
            typeLabels: {
                normal: '普通签到', photo: '拍照签到', gesture: '手势签到',
                location: '位置签到', qrcode: '二维码签到', qrcode_location: '指定位置二维码签到',
                code: '签到码签到',
            },

            // 扫码/签到码/手势
            signMode: 'qrcode',
            signCodeInput: '',
            gestureCode: '',
            gesturePoints: [],
            gestureDrawing: false,
            cameraActive: false,
            qrVideoStream: null,
            qrScanTimer: null,

            // 代签
            selectedFriends: [],
            scanLogs: [],
            signing: false,

            // 指定位置二维码签到
            scannedQrData: '',
            scannedEnc: '',

            // 好友
            friends: [],
            showAddFriendModal: false,
            addFriendAccount: '',
            addingFriend: false,

            // Toast
            toastMsg: '',
            toastTimer: null,

            // 位置
            locationLng: '',
            locationLat: '',
            locationName: '',
            locationSearch: '',
            _scanMap: null,
            _locationMarker: null,
            locating: false,
        };
    },

    computed: {
        showNav() { return this.currentPage !== 'login'; },
        allFriendsSelected() {
            return this.friends.length > 0 && this.selectedFriends.length === this.friends.length;
        },
        filteredCourses() {
            if (!this.courseSearch) return this.courses;
            var kw = this.courseSearch.toLowerCase();
            return this.courses.filter(function(c) {
                return c.name.toLowerCase().indexOf(kw) !== -1 ||
                       (c.teacher && c.teacher.toLowerCase().indexOf(kw) !== -1);
            });
        },
    },

    watch: {
        currentPage(val) {
            if (this.cameraActive) this.stopScanCamera();
            if (val !== 'scan' && this._scanMap) { this._scanMap.destroy(); this._scanMap = null; this._locationMarker = null; }
            if (val === 'home') { var self = this; self.loadFriends().then(function() { self.loadActiveCourses(); }); }
            if (val === 'courses') this.loadCourses();
            if (val === 'scan') { this.loadFriends(); if (this.signMode === 'gesture') { var s = this; nextTick(function() { s.gestureInitCanvas(); }); } }
            if (val === 'friends') this.loadFriends();
            if (val === 'tasks') { var self = this; nextTick(function() { self.loadTasks(); }); }
            if (val === 'login') this.loginPassword = '';
        },
    },

    methods: {
        // Toast
        toast: function(msg, duration) {
            var self = this;
            duration = duration || 2000;
            self.toastMsg = msg;
            clearTimeout(self.toastTimer);
            self.toastTimer = setTimeout(function() { self.toastMsg = ''; }, duration);
        },

        // 通用 API
        api: async function(method, path, params) {
            var self = this;
            params = params || {};
            if (self.token) params.token = self.token;
            var url = '/api' + path;
            var opts = { method: method };
            // 始终把 params 放入 query string（后端统一用 Query() 获取）
            var qs = Object.keys(params).map(function(k) {
                return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]);
            }).join('&');
            if (qs) url += '?' + qs;
            try {
                var resp = await fetch(url, opts);
                if (!resp.ok) {
                    var txt = await resp.text();
                    var detail = txt;
                    try { detail = JSON.parse(txt).detail || txt; } catch (e) {}
                    throw new Error(detail);
                }
                return await resp.json();
            } catch (e) {
                self.toast(e.message);
                throw e;
            }
        },

        // JWT 认证 API
        apiAuth: async function(method, path, body) {
            var self = this;
            var headers = { 'Content-Type': 'application/json' };
            if (self.jwt) headers['Authorization'] = 'Bearer ' + self.jwt;
            var url = '/api' + path;
            if (self.token) url += (url.indexOf('?') !== -1 ? '&' : '?') + 'token=' + self.token;
            var opts = { method: method, headers: headers };
            if (body && method !== 'GET') opts.body = JSON.stringify(body);
            try {
                var resp = await fetch(url, opts);
                if (!resp.ok) {
                    var txt = await resp.text();
                    var detail = txt;
                    try { detail = JSON.parse(txt).detail || txt; } catch (e) {}
                    throw new Error(detail);
                }
                return await resp.json();
            } catch (e) {
                self.toast(e.message);
                throw e;
            }
        },

        // 登录
        doLogin: async function() {
            var self = this;
            if (!self.loginPhone || !self.loginPassword) {
                return self.toast('请输入手机号和密码');
            }
            self.loggingIn = true;
            try {
                var data = await self.api('POST', '/login', {
                    phone: self.loginPhone, password: self.loginPassword,
                });
                self.token = data.token;
                self.uid = data.uid;
                self.name = data.name;
                localStorage.setItem('cx_token', data.token);
                localStorage.setItem('cx_name', data.name);
                localStorage.setItem('cx_phone', self.loginPhone);
                if (data.jwt) {
                    self.jwt = data.jwt;
                    self.user = data.user;
                    localStorage.setItem('cx_jwt', data.jwt);
                    localStorage.setItem('cx_user', JSON.stringify(data.user));
                }
                self.currentPage = 'home';
                self.toast('登录成功');
            } catch (e) {} finally { self.loggingIn = false; }
        },

        doLogout: async function() {
            var self = this;
            try { await self.api('POST', '/logout'); } catch (e) {}
            self.token = '';
            self.jwt = '';
            self.uid = '';
            self.name = '';
            self.user = { id: 0, supernova_account: '', nickname: '' };
            self.courses = [];
            self.friends = [];
            ['cx_token', 'cx_jwt', 'cx_name', 'cx_user', 'cx_friends'].forEach(function(k) { localStorage.removeItem(k); });
            self.currentPage = 'login';
        },

        // 有签到活动的课程
        loadActiveCourses: async function() {
            var self = this;
            if (self._loadingActive) return;
            self._loadingActive = true;
            self.loadingActive = true;
            try {
                var data = await self.api('GET', '/active-courses');
                self.activeCourses = data.courses || [];
            } catch (e) { self.activeCourses = []; }
            finally { self.loadingActive = false; self._loadingActive = false; }
        },

        loadCourses: async function() {
            var self = this;
            self.loadingCourses = true;
            try {
                var data = await self.api('GET', '/courses');
                self.courses = data.courses || [];
            } catch (e) { self.courses = []; }
            finally { self.loadingCourses = false; }
        },

        openTasks: function(course) {
            this.currentCourseId = course.course_id;
            this.currentClassId = course.class_id;
            this.currentCourseName = course.name;
            this.currentPage = 'tasks';
        },

        loadTasks: async function() {
            var self = this;
            self.loadingTasks = true;
            try {
                var data = await self.api('GET', '/tasks/' + self.currentCourseId + '/' + self.currentClassId);
                var tasks = data.tasks || [];
                self.activeTasks = tasks.filter(function(t) { return t.status === 'active'; });
                self.endedTasks = tasks.filter(function(t) { return t.status !== 'active'; });
            } catch (e) {
                self.activeTasks = [];
                self.endedTasks = [];
            } finally { self.loadingTasks = false; }
        },

        // 签到
        startSign: function(task) {
            var interactive = ['qrcode', 'code', 'gesture', 'location', 'qrcode_location'];
            if (interactive.indexOf(task.sign_type) !== -1) {
                this.signMode = task.sign_type === 'qrcode_location' ? 'qrcode_location'
                    : task.sign_type === 'code' ? 'code'
                    : task.sign_type === 'gesture' ? 'gesture'
                    : task.sign_type === 'location' ? 'location'
                    : 'qrcode';
                this.selectedFriends = [];
                this.scanLogs = [];
                this.signCodeInput = '';
                this.gestureCode = '';
                this.gesturePoints = [];
                this.locationLng = '';
                this.locationLat = '';
                this.locationName = '';
                this.locationSearch = '';
                this.scannedQrData = '';
                this.scannedEnc = '';
                this.currentTask = task;
                this.currentPage = 'scan';
                var self = this;
                if (this.signMode === 'gesture') { nextTick(function() { self.gestureInitCanvas(); }); }
                if (this.signMode === 'location') { nextTick(function() { self.initScanMap(); }); }
                if (this.signMode === 'qrcode_location') { nextTick(function() { self.initScanMap(); }); }
            }
        },

        // 已签任务代签：进入扫码页帮好友签到
        startProxySign: function(task) {
            this.selectedFriends = [];
            this.scanLogs = [];
            this.signCodeInput = '';
            this.gestureCode = '';
            this.gesturePoints = [];
            this.locationLng = '';
            this.locationLat = '';
            this.locationName = '';
            this.locationSearch = '';
            this.scannedQrData = '';
            this.scannedEnc = '';
            this.currentTask = task;
            if (task.sign_type === 'code') this.signMode = 'code';
            else if (task.sign_type === 'gesture') this.signMode = 'gesture';
            else if (task.sign_type === 'location') this.signMode = 'location';
            else if (task.sign_type === 'qrcode_location') this.signMode = 'qrcode_location';
            else this.signMode = 'qrcode';
            this.currentPage = 'scan';
            var self = this;
            if (this.signMode === 'location') { nextTick(function() { self.initScanMap(); }); }
            if (this.signMode === 'qrcode_location') { nextTick(function() { self.initScanMap(); }); }
        },

        doDirectSign: async function(task) {
            var self = this;
            if (self.signing) return;
            self.signing = true;
            try {
                var data = await self.api('POST', '/sign', {
                    active_id: task.active_id,
                    course_id: self.currentCourseId,
                    class_id: self.currentClassId,
                    sign_type: task.sign_type,
                });
                if (data.ok) {
                    self.toast(task.name + ' - 签到成功');
                    setTimeout(function() { self.loadTasks(); }, 1500);
                } else {
                    self.toast(data.message || '签到失败');
                }
            } catch (e) {} finally {
                self.signing = false;
            }
        },

        // ============================================================
        // 扫码签到（新流程：勾选好友 → 摄像头扫码 → 自动签到 → 日志）
        // ============================================================

        exitScanPage: function() {
            this.stopScanCamera();
            this.selectedFriends = [];
            this.scanLogs = [];
            this.scannedQrData = '';
            this.scannedEnc = '';
            this.currentPage = this.currentTask ? 'tasks' : 'home';
        },

        getMaskedPhone: function(f) {
            var uid = f.supernova_account || '';
            if (uid.length >= 7) {
                return uid.substring(0, 3) + '****' + uid.substring(uid.length - 4);
            }
            return uid;
        },

        toggleFriend: function(id) {
            var idx = this.selectedFriends.indexOf(id);
            if (idx >= 0) {
                this.selectedFriends.splice(idx, 1);
            } else {
                this.selectedFriends.push(id);
            }
        },

        toggleSelectAllFriends: function() {
            if (this.allFriendsSelected) {
                this.selectedFriends = [];
            } else {
                this.selectedFriends = this.friends.map(function(f) { return f.id; });
            }
        },

        addLog: function(name, status, text) {
            var now = new Date();
            var time = ('0' + now.getHours()).slice(-2) + ':' +
                       ('0' + now.getMinutes()).slice(-2) + ':' +
                       ('0' + now.getSeconds()).slice(-2);
            this.scanLogs.push({ time: time, name: name, status: status, text: text || '' });
            var self = this;
            nextTick(function() {
                var box = self.$refs.logBox;
                if (box) box.scrollTop = box.scrollHeight;
            });
        },

        startScanCamera: function() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                return this.toast('设备不支持摄像头');
            }
            var self = this;
            self.scanLogs = [];
            self.addLog('系统', 'info', '准备扫码...');
            navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 640 } }
            }).then(function(stream) {
                self.qrVideoStream = stream;
                self.cameraActive = true;
                nextTick(function() {
                    var video = document.getElementById('qr-video');
                    if (video) {
                        video.srcObject = stream;
                        video.play();
                        self.scanQrLoop();
                    }
                });
            }).catch(function() {
                self.toast('无法访问摄像头');
            });
        },

        stopScanCamera: function() {
            this.cameraActive = false;
            if (this.qrVideoStream) {
                this.qrVideoStream.getTracks().forEach(function(t) { t.stop(); });
                this.qrVideoStream = null;
            }
            clearTimeout(this.qrScanTimer);
        },

        scanQrLoop: function() {
            var self = this;
            if (!self.cameraActive) return;
            var video = document.getElementById('qr-video');
            var canvas = document.getElementById('qr-canvas');
            if (!video || !canvas) { self.qrScanTimer = setTimeout(function() { self.scanQrLoop(); }, 150); return; }
            var ctx = canvas.getContext('2d');
            if (video.readyState === video.HAVE_ENOUGH_DATA) {
                canvas.width = video.videoWidth || 320;
                canvas.height = video.videoHeight || 320;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                try {
                    var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    var code = jsQR(imageData.data, imageData.width, imageData.height);
                    if (code && code.data) {
                        self.stopScanCamera();
                        if (self.signMode === 'qrcode_location') {
                            self.scannedQrData = code.data;
                            var m = code.data.match(/enc=([a-zA-Z0-9_\-]+)/);
                            self.scannedEnc = m ? m[1] : code.data;
                            self.addLog('扫描', 'info', '二维码已识别，请选择位置');
                        } else {
                            self.addLog('扫描', 'info', '识别成功，开始签到...');
                            self.doScanSign(code.data);
                        }
                        return;
                    }
                } catch (e) {}
            }
            self.qrScanTimer = setTimeout(function() { self.scanQrLoop(); }, 150);
        },

        doScanSign: async function(qrData) {
            var self = this;
            if (!self.jwt) {
                self.addLog('系统', 'fail', '未登录');
                return self.toast('请先登录');
            }

            var m = qrData.match(/enc=([a-zA-Z0-9_\-]+)/);
            var enc = m ? m[1] : qrData;

            if (self.signing) return;
            self.signing = true;

            // 为自己签到
            try {
                var selfData = await self.apiAuth('POST', '/checkin/qrcode', {
                    qr_data: qrData,
                    active_id: self.currentTask ? self.currentTask.active_id : '',
                    course_id: self.currentTask ? self.currentCourseId : '',
                    class_id: self.currentTask ? self.currentClassId : '',
                    proxy_friend_ids: [],
                });
                var selfResult = (selfData.results && selfData.results.self) || 'failed';
                self.addLog(self.user.nickname || '自己', selfResult);
            } catch (e) {
                self.addLog('自己', 'fail');
            }

            // 为勾选的好友代签
            if (self.selectedFriends.length > 0) {
                try {
                    var data = await self.apiAuth('POST', '/checkin/qrcode', {
                        qr_data: qrData,
                        active_id: self.currentTask ? self.currentTask.active_id : '',
                        course_id: self.currentTask ? self.currentCourseId : '',
                        class_id: self.currentTask ? self.currentClassId : '',
                        proxy_friend_ids: self.selectedFriends,
                    });

                    var proxyResults = (data.results && data.results.proxy) || [];
                    proxyResults.forEach(function(p) {
                        var name = p.nickname || p.supernova_account || ('好友#' + p.friend_id);
                        self.addLog(name, p.result === 'success' ? 'success' : 'fail');
                    });
                } catch (e) {
                    self.addLog('代签', 'fail', '请求失败');
                }
            }

            self.signing = false;
            self.addLog('系统', 'info', '签到完成');

            // 如果从任务页来，刷新任务列表
            if (self.currentTask) {
                setTimeout(function() { self.loadTasks(); }, 1500);
            }
        },

        // 手势签到 (canvas-only)
        gestureInitCanvas: function() {
            var canvas = this.$refs.gestureCanvas;
            if (!canvas) return;
            var dpr = window.devicePixelRatio || 1;
            var w = canvas.clientWidth;
            var h = canvas.clientHeight;
            canvas.width = w * dpr;
            canvas.height = h * dpr;
            var ctx = canvas.getContext('2d');
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            this._gestureDots = [];
            var gap = w / 4;
            for (var r = 0; r < 3; r++) {
                for (var c = 0; c < 3; c++) {
                    this._gestureDots.push({
                        n: r * 3 + c + 1,
                        x: gap * (c + 1),
                        y: gap * (r + 1),
                    });
                }
            }
            this._drawGestureDots();
        },

        _drawGestureDots: function() {
            var canvas = this.$refs.gestureCanvas;
            if (!canvas) return;
            var ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
            var dots = this._gestureDots;
            if (!dots) return;

            // draw lines
            if (this.gesturePoints && this.gesturePoints.length >= 2) {
                ctx.strokeStyle = '#1677ff';
                ctx.lineWidth = 3;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                ctx.beginPath();
                for (var i = 0; i < this.gesturePoints.length; i++) {
                    var pt = dots[this.gesturePoints[i] - 1];
                    if (i === 0) ctx.moveTo(pt.x, pt.y);
                    else ctx.lineTo(pt.x, pt.y);
                }
                ctx.stroke();
            }

            // draw dots
            for (var j = 0; j < dots.length; j++) {
                var d = dots[j];
                var active = this.gesturePoints && this.gesturePoints.indexOf(d.n) >= 0;
                ctx.beginPath();
                ctx.arc(d.x, d.y, active ? 12 : 8, 0, Math.PI * 2);
                ctx.fillStyle = active ? '#1677ff' : 'transparent';
                ctx.fill();
                ctx.strokeStyle = active ? '#1677ff' : '#ccc';
                ctx.lineWidth = 2;
                ctx.stroke();
            }
        },

        _hitDot: function(cx, cy) {
            if (!this._gestureDots) return -1;
            for (var i = 0; i < this._gestureDots.length; i++) {
                var d = this._gestureDots[i];
                var dist = Math.sqrt((cx - d.x) * (cx - d.x) + (cy - d.y) * (cy - d.y));
                if (dist < 22) return d.n;
            }
            return -1;
        },

        gestureStart: function(e) {
            this.gestureDrawing = true;
            this.gesturePoints = [];
            this.gestureCode = '';
            var canvas = this.$refs.gestureCanvas;
            if (!canvas) return;
            var rect = canvas.getBoundingClientRect();
            var cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
            var cy = (e.touches ? e.touches[0].clientY : e.clientY) - rect.top;
            var n = this._hitDot(cx, cy);
            if (n > 0) {
                this.gesturePoints.push(n);
                this.gestureCode = String(n);
                this._drawGestureDots();
            }
        },

        gestureMove: function(e) {
            if (!this.gestureDrawing) return;
            var canvas = this.$refs.gestureCanvas;
            if (!canvas) return;
            var rect = canvas.getBoundingClientRect();
            var cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
            var cy = (e.touches ? e.touches[0].clientY : e.clientY) - rect.top;
            var n = this._hitDot(cx, cy);
            if (n > 0 && this.gesturePoints.indexOf(n) < 0) {
                this.gesturePoints.push(n);
                this.gestureCode = this.gesturePoints.join('');
                this._drawGestureDots();
            }
        },

        gestureEnd: function() {
            this.gestureDrawing = false;
        },

        gestureReset: function() {
            this.gesturePoints = [];
            this.gestureCode = '';
            this._drawGestureDots();
        },

        doGestureSign: async function() {
            var self = this;
            if (self.signing) return;
            if (!self.gestureCode) return self.toast('请绘制手势图案');
            self.scanLogs = [];
            self.signing = true;
            self.addLog('系统', 'info', '手势签到 ' + self.gestureCode);

            try {
                var selfData = await self.api('POST', '/sign', {
                    active_id: self.currentTask ? self.currentTask.active_id : '',
                    course_id: self.currentTask ? self.currentCourseId : '',
                    class_id: self.currentTask ? self.currentClassId : '',
                    sign_type: 'gesture',
                    gesture_code: self.gestureCode,
                });
                if (selfData.ok) self.addLog(self.user.nickname || '自己', 'success');
                else self.addLog(self.user.nickname || '自己', 'fail');
            } catch (e) { self.addLog('自己', 'fail'); }

            // 好友代签
            if (self.selectedFriends.length > 0) {
                for (var i = 0; i < self.selectedFriends.length; i++) {
                    var fid = self.selectedFriends[i];
                    var friend = self.friends.find(function(f) { return f.id === fid; });
                    var name = friend ? friend.nickname : ('好友#' + fid);
                    try {
                        var data = await self.api('POST', '/sign', {
                            active_id: self.currentTask ? self.currentTask.active_id : '',
                            course_id: self.currentTask ? self.currentCourseId : '',
                            class_id: self.currentTask ? self.currentClassId : '',
                            sign_type: 'gesture',
                            gesture_code: self.gestureCode,
                        });
                        if (data.ok) self.addLog(name, 'success');
                        else self.addLog(name, 'fail');
                    } catch (e) { self.addLog(name, 'fail'); }
                }
            }

            self.signing = false;
            self.addLog('系统', 'info', '签到完成');
            if (self.currentTask) setTimeout(function() { self.loadTasks(); }, 1500);
        },

        doCodeSign: async function() {
            var self = this;
            var code = self.signCodeInput.trim();
            if (self.signing) return;
            if (!code) return self.toast('请输入签到码');
            self.scanLogs = [];
            self.signing = true;
            self.addLog('系统', 'info', '开始签到码签到...');

            // 为自己签到
            try {
                var selfData = await self.api('POST', '/sign', {
                    active_id: self.currentTask ? self.currentTask.active_id : '',
                    course_id: self.currentTask ? self.currentCourseId : '',
                    class_id: self.currentTask ? self.currentClassId : '',
                    sign_type: 'code',
                    sign_code: code,
                });
                if (selfData.ok) {
                    self.addLog(self.user.nickname || '自己', 'success');
                } else {
                    self.addLog(self.user.nickname || '自己', 'fail');
                }
            } catch (e) {
                self.addLog('自己', 'fail');
            }

            // 为好友代签
            if (self.selectedFriends.length > 0) {
                for (var i = 0; i < self.selectedFriends.length; i++) {
                    var fid = self.selectedFriends[i];
                    var friend = self.friends.find(function(f) { return f.id === fid; });
                    var name = friend ? friend.nickname : ('好友#' + fid);
                    try {
                        var data = await self.api('POST', '/sign', {
                            active_id: self.currentTask ? self.currentTask.active_id : '',
                            course_id: self.currentTask ? self.currentCourseId : '',
                            class_id: self.currentTask ? self.currentClassId : '',
                            sign_type: 'code',
                            sign_code: code,
                        });
                        if (data.ok) {
                            self.addLog(name, 'success');
                        } else {
                            self.addLog(name, 'fail');
                        }
                    } catch (e) {
                        self.addLog(name, 'fail');
                    }
                }
            }

            self.signing = false;
            self.addLog('系统', 'info', '签到完成');

            if (self.currentTask) {
                setTimeout(function() { self.loadTasks(); }, 1500);
            }
        },

        // 好友
        loadFriends: async function() {
            var self = this;
            if (!self.jwt) return;

            // 先从缓存恢复，保证秒显
            var cached = localStorage.getItem('cx_friends');
            if (cached) {
                try { self.friends = JSON.parse(cached); } catch (e) {}
            }

            self.loadingFriends = true;
            try {
                var data = await self.apiAuth('GET', '/friends');
                self.friends = data.friends || [];
                localStorage.setItem('cx_friends', JSON.stringify(self.friends));
            } catch (e) { self.friends = self.friends.length ? self.friends : []; }
            finally { self.loadingFriends = false; }
        },

        doAddFriend: async function() {
            var self = this;
            if (!self.addFriendAccount.trim()) return self.toast('请输入好友账号');
            self.addingFriend = true;
            try {
                await self.apiAuth('POST', '/friends', {
                    target_account: self.addFriendAccount.trim(),
                });
                self.toast('添加成功');
                self.showAddFriendModal = false;
                self.addFriendAccount = '';
                await self.loadFriends();
            } catch (e) {} finally { self.addingFriend = false; }
        },

        deleteFriend: async function(friend) {
            var self = this;
            if (!confirm('确定删除好友 ' + (friend.nickname || friend.supernova_account) + ' ?')) return;
            try {
                await self.apiAuth('DELETE', '/friends/' + friend.id);
                self.toast('已删除');
                await self.loadFriends();
            } catch (e) {}
        },

        // 位置签到（内嵌地图）
        // ============================================================
        // 高德地图 AMap — 地图选点
        // ============================================================

        initScanMap: function() {
            var self = this;
            self.locationLng = localStorage.getItem('cx_loc_lng') || '116.404';
            self.locationLat = localStorage.getItem('cx_loc_lat') || '39.915';
            self.locationName = localStorage.getItem('cx_loc_name') || '北京市';

            var _retry = 0;
            var _maxRetry = 30;

            var _init = function() {
                _retry++;
                if (_retry > _maxRetry) { self.toast('地图加载超时'); return; }
                var el = document.getElementById('scan-location-map');
                if (!el || el.clientHeight === 0) { setTimeout(_init, 300); return; }
                var A = window.AMap;
                if (!A || !A.Map) { setTimeout(_init, 300); return; }

                if (self._scanMap) { self._scanMap.destroy(); }

                var center = [parseFloat(self.locationLng), parseFloat(self.locationLat)];
                self._scanMap = new A.Map('scan-location-map', { center: center, zoom: 15, resizeEnable: true });

                self._locationMarker = new A.Marker({
                    map: self._scanMap,
                    position: center,
                    title: self.locationName || '',
                });

                self._scanMap.on('click', function(e) {
                    var lng = e.lnglat.getLng();
                    var lat = e.lnglat.getLat();
                    self.locationLng = String(lng);
                    self.locationLat = String(lat);
                    self._locationMarker.setPosition([lng, lat]);
                    var gc = new A.Geocoder();
                    gc.getAddress([lng, lat], function(status, result) {
                        if (status === 'complete' && result.regeocode) {
                            self.locationName = result.regeocode.formattedAddress || '';
                        }
                    });
                });

                // 地图就绪后自动触发一次定位
                self.doGeolocation();
            };

            if (window.AMap && window.AMap.Map) { _init(); return; }
            var key = localStorage.getItem('cx_amap_key') || '';
            if (!key) { self.toast('未配置高德地图 Key'); return; }
            var s = document.createElement('script');
            s.src = 'https://webapi.amap.com/maps?v=2.0&key=' + key + '&plugin=AMap.Geocoder,AMap.Geolocation,AMap.PlaceSearch';
            s.onload = function() { _init(); };
            s.onerror = function() { self.toast('高德地图 JS 加载失败，请检查 Key 域名白名单'); };
            document.head.appendChild(s);
        },

        doLocationSearch: function() {
            var self = this;
            var kw = (self.locationSearch || '').trim();
            if (!kw) return;
            var A = window.AMap;
            if (!A) { self.toast('地图服务未就绪，请稍后重试'); return; }

            var ps = new A.PlaceSearch({ pageSize: 5, citylimit: false });
            ps.search(kw, function(status, result) {
                if (status === 'complete' && result.poiList && result.poiList.count > 0) {
                    // 显示所有匹配的标记物
                    var pois = result.poiList.pois;
                    var firstPoi = pois[0];
                    var lng = firstPoi.location.getLng();
                    var lat = firstPoi.location.getLat();
                    self.locationLng = String(lng);
                    self.locationLat = String(lat);
                    self.locationName = firstPoi.name;
                    if (self._scanMap) {
                        self._scanMap.setZoomAndCenter(16, [lng, lat]);
                        if (self._locationMarker) {
                            self._locationMarker.setPosition([lng, lat]);
                            self._locationMarker.setTitle(firstPoi.name);
                        }
                    }
                    if (pois.length > 1) {
                        self.toast('已定位到「' + firstPoi.name + '」，共' + pois.length + '个结果');
                    }
                } else {
                    self.toast('未搜索到匹配地点');
                }
            });
        },

        doGeolocation: function() {
            var self = this;
            if (self.locating) return;
            self.locating = true;

            var onDone = function(msg) {
                self.locating = false;
                if (msg) self.toast(msg);
            };

            // 优先用 AMap.Geolocation 插件（比浏览器 API 更稳定）
            var A = window.AMap;
            if (A && A.Geolocation) {
                var geo = new A.Geolocation({ enableHighAccuracy: true, timeout: 8000 });
                geo.getCurrentPosition(function(status, result) {
                    if (status === 'complete' && result.position) {
                        var lng = result.position.lng;
                        var lat = result.position.lat;
                        self.locationLng = String(lng);
                        self.locationLat = String(lat);
                        self.locationName = result.formattedAddress || '我的位置';
                        if (self._scanMap) {
                            self._scanMap.setZoomAndCenter(17, [lng, lat]);
                            if (self._locationMarker) self._locationMarker.setPosition([lng, lat]);
                        }
                        onDone('已定位到当前位置');
                    } else {
                        onDone('定位失败，请检查设备定位是否开启');
                    }
                });
                return;
            }

            // 浏览器 API 兜底
            if (!navigator.geolocation) {
                self.locating = false;
                return self.toast('当前浏览器不支持定位功能');
            }
            // 开始计时：3s 内无回调则提示正在定位
            var t = setTimeout(function() { self.toast('正在获取位置...'); }, 3000);
            navigator.geolocation.getCurrentPosition(
                function(pos) {
                    clearTimeout(t);
                    var lng = String(pos.coords.longitude);
                    var lat = String(pos.coords.latitude);
                    self.locationLng = lng;
                    self.locationLat = lat;
                    self.locationName = '我的位置';
                    if (self._scanMap) {
                        self._scanMap.setZoomAndCenter(17, [parseFloat(lng), parseFloat(lat)]);
                        if (self._locationMarker) self._locationMarker.setPosition([parseFloat(lng), parseFloat(lat)]);
                    }
                    // 反查地址
                    if (A && A.Geocoder) {
                        var gc = new A.Geocoder();
                        gc.getAddress([parseFloat(lng), parseFloat(lat)], function(status, result) {
                            if (status === 'complete' && result.regeocode) {
                                self.locationName = result.regeocode.formattedAddress || '我的位置';
                            }
                        });
                    }
                    onDone('已定位到当前位置');
                },
                function(err) {
                    clearTimeout(t);
                    var msg = '定位失败';
                    if (err.code === 1) msg = '定位被拒绝，请在系统设置中开启定位权限';
                    else if (err.code === 2) msg = '无法获取定位，请检查设备';
                    else if (err.code === 3) msg = '定位超时，请移至开阔处重试';
                    onDone(msg);
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
            );
        },

        doLocationSign: async function() {
            var self = this;
            if (self.signing) return;
            if (!self.locationLng) return self.toast('请选择位置');
            self.scanLogs = [];
            self.signing = true;
            self.addLog('系统', 'info', '位置签到 ' + self.locationName);

            var signParams = {
                active_id: self.currentTask ? self.currentTask.active_id : '',
                course_id: self.currentTask ? self.currentCourseId : '',
                class_id: self.currentTask ? self.currentClassId : '',
                sign_type: 'location',
                longitude: self.locationLng,
                latitude: self.locationLat,
                location_name: self.locationName,
            };

            try {
                var selfData = await self.api('POST', '/sign', signParams);
                self.addLog(self.user.nickname || '自己', selfData.ok ? 'success' : 'fail');
            } catch (e) { self.addLog('自己', 'fail'); }

            if (self.selectedFriends.length > 0) {
                for (var i = 0; i < self.selectedFriends.length; i++) {
                    var fid = self.selectedFriends[i];
                    var friend = self.friends.find(function(f) { return f.id === fid; });
                    var name = friend ? friend.nickname : ('好友#' + fid);
                    try {
                        var data = await self.api('POST', '/sign', signParams);
                        self.addLog(name, data.ok ? 'success' : 'fail');
                    } catch (e) { self.addLog(name, 'fail'); }
                }
            }

            self.signing = false;
            self.addLog('系统', 'info', '签到完成');
            localStorage.setItem('cx_loc_lng', self.locationLng);
            localStorage.setItem('cx_loc_lat', self.locationLat);
            localStorage.setItem('cx_loc_name', self.locationName);
            if (self.currentTask) setTimeout(function() { self.loadTasks(); }, 1500);
        },

        // 指定位置二维码签到
        resetQrcodeLocationScan: function() {
            this.scannedQrData = '';
            this.scannedEnc = '';
            this.stopScanCamera();
        },

        doQrcodeLocationSign: async function() {
            var self = this;
            if (self.signing) return;
            if (!self.scannedQrData) return self.toast('请先扫描二维码');
            if (!self.locationLng) return self.toast('请选择位置');
            if (!self.jwt) return self.toast('请先登录');
            self.scanLogs = [];
            self.signing = true;
            self.addLog('系统', 'info', '指定位置扫码签到 ' + self.locationName);

            try {
                var selfData = await self.apiAuth('POST', '/checkin/qrcode', {
                    qr_data: self.scannedQrData,
                    active_id: self.currentTask ? self.currentTask.active_id : '',
                    course_id: self.currentTask ? self.currentCourseId : '',
                    class_id: self.currentTask ? self.currentClassId : '',
                    sign_type: 'qrcode_location',
                    longitude: self.locationLng,
                    latitude: self.locationLat,
                    location_name: self.locationName,
                    proxy_friend_ids: [],
                });
                var selfResult = (selfData.results && selfData.results.self) || 'failed';
                self.addLog(self.user.nickname || '自己', selfResult);
            } catch (e) {
                self.addLog('自己', 'fail');
            }

            if (self.selectedFriends.length > 0) {
                try {
                    var data = await self.apiAuth('POST', '/checkin/qrcode', {
                        qr_data: self.scannedQrData,
                        active_id: self.currentTask ? self.currentTask.active_id : '',
                        course_id: self.currentTask ? self.currentCourseId : '',
                        class_id: self.currentTask ? self.currentClassId : '',
                        sign_type: 'qrcode_location',
                        longitude: self.locationLng,
                        latitude: self.locationLat,
                        location_name: self.locationName,
                        proxy_friend_ids: self.selectedFriends,
                    });
                    var proxyResults = (data.results && data.results.proxy) || [];
                    proxyResults.forEach(function(p) {
                        var name = p.nickname || p.supernova_account || ('好友#' + p.friend_id);
                        self.addLog(name, p.result === 'success' ? 'success' : 'fail');
                    });
                } catch (e) {
                    self.addLog('代签', 'fail', '请求失败');
                }
            }

            self.signing = false;
            self.addLog('系统', 'info', '签到完成');
            localStorage.setItem('cx_loc_lng', self.locationLng);
            localStorage.setItem('cx_loc_lat', self.locationLat);
            localStorage.setItem('cx_loc_name', self.locationName);
            if (self.currentTask) setTimeout(function() { self.loadTasks(); }, 1500);
        },

        openLocationModal: function() {
            var self = this;
            if (window.AMap && window.AMap.Map) {
                self.initScanMap();
                self.currentPage = 'scan';
                self.signMode = 'location';
                return;
            }
            var key = localStorage.getItem('cx_amap_key') || '';
            if (!key) { self.toast('未配置高德地图 Key'); return; }
            var s = document.createElement('script');
            s.src = 'https://webapi.amap.com/maps?v=2.0&key=' + key + '&plugin=AMap.Geocoder,AMap.Geolocation,AMap.PlaceSearch';
            s.onload = function() {
                self.initScanMap();
                self.currentPage = 'scan';
                self.signMode = 'location';
            };
            s.onerror = function() { self.toast('高德地图 JS 加载失败'); };
            document.head.appendChild(s);
        },
    },

    // 初始化
    mounted: async function() {
        var self = this;
        // 获取高德地图 key
        try {
            var configResp = await fetch('/api/config');
            var configData = await configResp.json();
            if (configData.amap_key) {
                localStorage.setItem('cx_amap_key', configData.amap_key);
            }
            if (configData.tmap_key) {
                localStorage.setItem('cx_tmap_key', configData.tmap_key);
            }
        } catch (e) {}

        var savedJwt = localStorage.getItem('cx_jwt');
        var savedUser = localStorage.getItem('cx_user');
        if (savedJwt && savedUser) {
            self.jwt = savedJwt;
            try { self.user = JSON.parse(savedUser); } catch (e) {}
        }

        if (self.token) {
            try {
                var data = await self.api('GET', '/session');
                self.uid = data.uid;
                self.name = data.name;
                self.currentPage = 'home';
            } catch (e) {
                self.token = '';
                localStorage.removeItem('cx_token');
                self.currentPage = 'login';
            }
        }
    },

    beforeUnmount: function() {
        this.stopScanCamera();
    },
});

app.mount('#app');
