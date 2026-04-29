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
                location: '位置签到', qrcode: '二维码签到', code: '签到码签到',
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
            _scanMapLoaded: false,
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
            if (val !== 'scan' && this._scanMap) { this._scanMap.destroy(); this._scanMap = null; }
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
            if (task.sign_type === 'qrcode' || task.sign_type === 'code' || task.sign_type === 'gesture' || task.sign_type === 'location') {
                if (task.sign_type === 'code') this.signMode = 'code';
                else if (task.sign_type === 'gesture') this.signMode = 'gesture';
                else if (task.sign_type === 'location') this.signMode = 'location';
                else this.signMode = 'qrcode';
                this.selectedFriends = [];
                this.scanLogs = [];
                this.signCodeInput = '';
                this.gestureCode = '';
                this.gesturePoints = [];
                this.locationLng = '';
                this.locationLat = '';
                this.locationName = '';
                this.locationSearch = '';
                this.currentTask = task;
                this.currentPage = 'scan';
                var self = this;
                if (this.signMode === 'gesture') { nextTick(function() { self.gestureInitCanvas(); }); }
                if (this.signMode === 'location') { nextTick(function() { self.initScanMap(); }); }
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
            this.currentTask = task;
            if (task.sign_type === 'code') this.signMode = 'code';
            else if (task.sign_type === 'gesture') this.signMode = 'gesture';
            else if (task.sign_type === 'location') this.signMode = 'location';
            else this.signMode = 'qrcode';
            this.currentPage = 'scan';
            var self = this;
            if (this.signMode === 'location') { nextTick(function() { self.initScanMap(); }); }
        },

        doDirectSign: async function(task) {
            var self = this;
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
            } catch (e) {}
        },

        // ============================================================
        // 扫码签到（新流程：勾选好友 → 摄像头扫码 → 自动签到 → 日志）
        // ============================================================

        exitScanPage: function() {
            this.stopScanCamera();
            this.selectedFriends = [];
            this.scanLogs = [];
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
                        self.addLog('扫描', 'info', '识别成功，开始签到...');
                        self.doScanSign(code.data);
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
        initScanMap: function() {
            var self = this;
            self.locationLng = localStorage.getItem('cx_loc_lng') || '116.404';
            self.locationLat = localStorage.getItem('cx_loc_lat') || '39.915';
            self.locationName = localStorage.getItem('cx_loc_name') || '北京市';

            var retryCount = 0;
            var MAX_RETRY = 20;
            var loadMap = function() {
                var tryInit = function() {
                    retryCount++;
                    if (retryCount > MAX_RETRY) {
                        self.toast('地图加载失败，可手动输入经纬度签到');
                        return;
                    }
                    setTimeout(function() {
                        var el = document.getElementById('scan-location-map');
                        if (!el || el.clientHeight === 0) { tryInit(); return; }
                        if (typeof AMap === 'undefined' || !AMap.Map) { tryInit(); return; }
                        if (self._scanMap) { self._scanMap.destroy(); }
                        self._scanMap = new AMap.Map('scan-location-map', {
                            center: [parseFloat(self.locationLng), parseFloat(self.locationLat)],
                            zoom: 15,
                            resizeEnable: true,
                        });
                        self._scanMap.on('click', function(e) {
                            self.locationLng = String(e.lnglat.getLng());
                            self.locationLat = String(e.lnglat.getLat());
                            var geocoder = new AMap.Geocoder();
                            geocoder.getAddress(e.lnglat, function(status, result) {
                                if (status === 'complete' && result.regeocode) {
                                    self.locationName = result.regeocode.formattedAddress || '';
                                }
                            });
                        });
                    }, 300);
                };
                tryInit();
            };

            if (window.AMap) { loadMap(); return; }
            var key = localStorage.getItem('cx_amap_key') || '你的高德地图key';
            var s = document.createElement('script');
            s.src = 'https://webapi.amap.com/maps?v=2.0&key=' + key + '&plugin=AMap.Geocoder,AMap.Geolocation,AMap.PlaceSearch';
            s.onload = loadMap;
            s.onerror = function() {
                self.toast('地图服务不可用，请检查高德 Key 域名白名单');
            };
            document.head.appendChild(s);
        },

        doLocationSearch: function() {
            var self = this;
            if (!self.locationSearch.trim() || !window.AMap) return;
            var placeSearch = new AMap.PlaceSearch({
                pageSize: 5,
                pageIndex: 1,
                citylimit: false,
            });
            placeSearch.search(self.locationSearch.trim(), function(status, result) {
                if (status === 'complete' && result.poiList && result.poiList.count > 0) {
                    var poi = result.poiList.pois[0];
                    self.locationLng = String(poi.location.getLng());
                    self.locationLat = String(poi.location.getLat());
                    self.locationName = poi.name;
                    if (self._scanMap) {
                        self._scanMap.setCenter([parseFloat(self.locationLng), parseFloat(self.locationLat)]);
                    }
                }
            });
        },

        doLocationSign: async function() {
            var self = this;
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

        // 位置签到（旧版弹窗，保留兼容）
        openLocationModal: function() {
            var self = this;
            if (window.AMap) {
                self.initAMap();
                return;
            }
            var amapKey = localStorage.getItem('cx_amap_key') || '你的高德地图key';
            var script = document.createElement('script');
            script.src = 'https://webapi.amap.com/maps?v=2.0&key=' + amapKey + '&plugin=AMap.Geocoder,AMap.Geolocation';
            script.onload = function() { self.initAMap(); };
            document.head.appendChild(script);
        },

        initAMap: function() {
            var self = this;
            self.locationLng = localStorage.getItem('cx_loc_lng') || '116.404';
            self.locationLat = localStorage.getItem('cx_loc_lat') || '39.915';
            self.locationName = localStorage.getItem('cx_loc_name') || '北京市';

            var container = document.createElement('div');
            container.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:1000;background:#fff';
            container.innerHTML =
                '<div id="loc-map" style="width:100%;height:calc(100% - 140px)"></div>' +
                '<div style="padding:12px;position:fixed;bottom:50px;left:0;right:0;background:#fff;z-index:1001">' +
                '  <p id="loc-info" style="margin-bottom:8px;color:#666">点击地图选择位置</p>' +
                '  <button id="loc-submit" class="btn btn-primary" style="width:100%">确认签到</button>' +
                '</div>' +
                '<span style="position:fixed;top:12px;right:16px;font-size:28px;z-index:1001;cursor:pointer" id="loc-close">×</span>';
            document.body.appendChild(container);

            document.getElementById('loc-close').onclick = function() {
                document.body.removeChild(container);
            };

            var map = new AMap.Map('loc-map', {
                center: [parseFloat(self.locationLng), parseFloat(self.locationLat)],
                zoom: 15,
                resizeEnable: true,
            });

            map.on('click', function(e) {
                self.locationLng = String(e.lnglat.getLng());
                self.locationLat = String(e.lnglat.getLat());
                var geocoder = new AMap.Geocoder();
                geocoder.getAddress(e.lnglat, function(status, result) {
                    if (status === 'complete' && result.regeocode) {
                        self.locationName = result.regeocode.formattedAddress || '';
                        document.getElementById('loc-info').textContent = self.locationName;
                    }
                });
            });

            AMap.plugin('AMap.Geolocation', function() {
                var geo = new AMap.Geolocation({ enableHighAccuracy: true, timeout: 5000 });
                geo.getCurrentPosition(function(status, result) {
                    if (status === 'complete' && result.position) {
                        map.setCenter([result.position.lng, result.position.lat]);
                        self.locationLng = String(result.position.lng);
                        self.locationLat = String(result.position.lat);
                        if (result.formattedAddress) {
                            self.locationName = result.formattedAddress;
                            document.getElementById('loc-info').textContent = self.locationName;
                        }
                    }
                });
            });

            document.getElementById('loc-submit').onclick = async function() {
                document.body.removeChild(container);
                localStorage.setItem('cx_loc_lng', self.locationLng);
                localStorage.setItem('cx_loc_lat', self.locationLat);
                localStorage.setItem('cx_loc_name', self.locationName);
                try {
                    var data = await self.api('POST', '/sign', {
                        active_id: self.currentTask.active_id,
                        course_id: self.currentCourseId,
                        class_id: self.currentClassId,
                        sign_type: 'location',
                        longitude: self.locationLng,
                        latitude: self.locationLat,
                        location_name: self.locationName,
                    });
                    if (data.ok) {
                        self.toast('签到成功');
                        setTimeout(function() { self.loadTasks(); }, 1500);
                    } else {
                        self.toast(data.message || '签到失败');
                    }
                } catch (e) {}
            };
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
