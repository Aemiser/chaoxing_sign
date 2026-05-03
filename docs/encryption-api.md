# 前端非对称加密对接文档

## 加密方案概述

采用 **混合加密**（AES-256-GCM + RSA-2048-OAEP with SHA-256）：

- 数据体用 AES-GCM 加密（对称、快速、带完整性校验）
- AES 密钥用 RSA 公钥加密（非对称、仅服务端可解密）

## 数据格式

### 加密后的二进制 Blob 结构

```
nonce(12 bytes) | encrypted_key(256 bytes) | tag(16 bytes) | ciphertext(变长)
```

| 字段 | 长度 | 说明 |
|---|---|---|
| nonce | 12 字节 | AES-GCM 随机初始化向量 |
| encrypted_key | 256 字节 | RSA-2048-OAEP 加密的 AES-256 原始密钥（32 字节） |
| tag | 16 字节 | AES-GCM 认证标签 |
| ciphertext | 变长 | AES-GCM 密文（不含 tag） |

最终将整个 Blob 做 **Base64 编码**，作为 `encrypted` 参数传输。

### 加密流程

```
原始参数 dict
  → JSON.stringify → UTF-8 字节
  → AES-256-GCM 加密（随机密钥 + 随机 nonce）
  → 得到 ciphertext + tag
  → AES 密钥用 RSA-2048-OAEP(SHA-256) 加密
  → 拼接 nonce + encrypted_key + tag + ciphertext
  → Base64 编码
```

## API 对接方式

### 1. 获取公钥

```
GET /api/public-key

响应:
{
  "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhki...\n-----END PUBLIC KEY-----"
}
```

页面/小程序初始化时调用一次，缓存公钥。

### 2. 登录接口

```
POST /api/login?token=xxx&encrypted=<Base64密文>
```

加密前的原始参数（一个 JSON 对象）：

```json
{
  "phone": "13812345678",
  "password": "mypassword"
}
```

### 3. 签到接口（查询字符串方式）

```
POST /api/sign?token=xxx&encrypted=<Base64密文>
```

加密前的原始参数：

```json
{
  "active_id": "...",
  "course_id": "...",
  "class_id": "...",
  "sign_type": "normal|photo|gesture|location|qrcode|qrcode_location|code",
  "enc": "",
  "sign_code": "",
  "gesture_code": "",
  "longitude": "",
  "latitude": "",
  "location_name": "",
  "use_trilateration": "1"
}
```

### 4. 签到接口（JSON Body 方式，扫码签到）

```
POST /api/checkin/qrcode?token=xxx

Content-Type: application/json

{
  "encrypted": "<Base64密文>"
}
```

加密前的原始参数：

```json
{
  "qr_data": "...",
  "active_id": "...",
  "course_id": "...",
  "class_id": "...",
  "sign_type": "qrcode|qrcode_location",
  "longitude": "",
  "latitude": "",
  "location_name": "",
  "proxy_friend_ids": [],
  "use_trilateration": "1"
}
```

### 5. 添加好友接口

```
POST /api/friends?token=xxx

Content-Type: application/json

{
  "encrypted": "<Base64密文>"
}
```

加密前的原始参数：

```json
{
  "target_account": "对方手机号或账号"
}
```

### 6. 课程列表接口

```
GET /api/courses?token=xxx&encrypted=<Base64密文>
```

加密前的原始参数：

```json
{
  "source": 0,
  "user_id": 42
}
```

### 7. 签到任务接口

```
GET /api/tasks/{course_id}/{class_id}?token=xxx&encrypted=<Base64密文>
```

加密前的原始参数：

```json
{
  "course_id": "...",
  "class_id": "...",
  "sync": 0
}
```

---

## Web Crypto API 实现参考（浏览器端）

以下是浏览器端的完整实现，小程序端需用对应平台的加密 API 替代。

### 步骤 1: 导入公钥

```javascript
async function importPublicKey(pem) {
  // 去掉 PEM 头尾和换行符
  var b64 = pem
    .replace('-----BEGIN PUBLIC KEY-----', '')
    .replace('-----END PUBLIC KEY-----', '')
    .replace(/\s/g, '');
  // Base64 解码为 DER 二进制
  var binaryDer = Uint8Array.from(atob(b64), function(c) { return c.charCodeAt(0); });
  // 导入为 CryptoKey（SPKI 格式，RSA-OAEP + SHA-256）
  return await crypto.subtle.importKey(
    'spki',
    binaryDer,
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['encrypt']
  );
}
```

### 步骤 2: 加密参数

```javascript
async function encryptPayload(dataObj, publicKey) {
  // 将参数 JSON 序列化并编码为 UTF-8 字节
  var plaintext = new TextEncoder().encode(JSON.stringify(dataObj));

  // ① 生成随机 AES-256 密钥
  var aesKey = await crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,
    ['encrypt']
  );

  // ② 生成随机 12 字节 nonce
  var nonce = crypto.getRandomValues(new Uint8Array(12));

  // ③ AES-GCM 加密 → 返回 ciphertext || tag
  var ciphertextWithTag = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: nonce },
      aesKey,
      plaintext
    )
  );
  // 分离：末尾 16 字节是 tag，前面是密文
  var ciphertext = ciphertextWithTag.slice(0, -16);
  var tag = ciphertextWithTag.slice(-16);

  // ④ 导出 AES 原始密钥（32 字节）
  var rawAesKey = new Uint8Array(
    await crypto.subtle.exportKey('raw', aesKey)
  );

  // ⑤ RSA-OAEP 加密 AES 密钥（256 字节输出）
  var encryptedKey = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: 'RSA-OAEP' },
      publicKey,
      rawAesKey
    )
  );

  // ⑥ 拼接: nonce(12) + encryptedKey(256) + tag(16) + ciphertext(变长)
  var blob = new Uint8Array(
    nonce.length + encryptedKey.length + tag.length + ciphertext.length
  );
  blob.set(nonce, 0);
  blob.set(encryptedKey, nonce.length);
  blob.set(tag, nonce.length + encryptedKey.length);
  blob.set(ciphertext, nonce.length + encryptedKey.length + tag.length);

  // ⑦ Base64 编码
  var binary = '';
  for (var i = 0; i < blob.length; i++) {
    binary += String.fromCharCode(blob[i]);
  }
  return btoa(binary);
}
```

### 步骤 3: 发送加密请求

**查询字符串方式**（用于 `api()`）：

```javascript
// 分离 token（明文）和其他参数（加密）
var tokenVal = params.token;
var sensitiveParams = {};
Object.keys(params).forEach(function(k) {
  if (k !== 'token') sensitiveParams[k] = params[k];
});

var encrypted = await encryptPayload(sensitiveParams, publicKey);
var qs = 'token=' + encodeURIComponent(tokenVal)
       + '&encrypted=' + encodeURIComponent(encrypted);
var url = '/api/login?' + qs;

var resp = await fetch(url, { method: 'POST' });
```

**JSON Body 方式**（用于 `apiAuth()`）：

```javascript
var encrypted = await encryptPayload(bodyData, publicKey);
var resp = await fetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ encrypted: encrypted }),
});
```

---

## 微信小程序端实现要点

微信小程序 **没有** Web Crypto API，需要自行实现或用第三方库。以下是关键参数对照：

| 参数 | Web Crypto | 小程序需实现 |
|---|---|---|
| RSA 密钥长度 | 2048 bits | 2048 bits |
| RSA 填充 | OAEP (SHA-256) | OAEP with SHA-256 |
| AES 模式 | GCM | GCM |
| AES 密钥长度 | 256 bits | 256 bits |
| GCM nonce | 12 字节 | 12 字节 |
| GCM tag | 16 字节 | 16 字节 |
| 公钥格式 | SPKI (PEM→DER) | SPKI DER |
| 密文编码 | Base64 | Base64 |

### 推荐小程序加密库

- **jsencrypt** + **aes-js** 或 **crypto-js**：纯 JS 实现，兼容小程序
- 或者使用微信小程序的 **wx.arrayBufferToBase64** 等原生 API 配合自写逻辑

### 小程序实现伪代码

```javascript
// 1. 获取公钥
const res = await wx.request({ url: `${host}/api/public-key` });
const publicKeyPem = res.data.public_key;

// 2. 解析 PEM，提取 DER（去掉 -----BEGIN/END----- 和换行）
const pemBody = publicKeyPem
  .replace(/-----(BEGIN|END) PUBLIC KEY-----/g, '')
  .replace(/\s/g, '');
const publicKeyDer = base64ToArrayBuffer(pemBody);

// 3. 加密参数
const jsonStr = JSON.stringify(params);
const plaintext = stringToUtf8Bytes(jsonStr);

// 生成随机 AES-256 密钥（32 字节）
const aesKey = randomBytes(32);
// 生成随机 nonce（12 字节）
const nonce = randomBytes(12);

// AES-256-GCM 加密
const { ciphertext, tag } = aesGcmEncrypt(aesKey, nonce, plaintext);
// 注意：tag 为 16 字节，ciphertext 不含 tag

// RSA-OAEP(SHA-256) 加密 AES 密钥
const encryptedKey = rsaOaepEncrypt(publicKeyDer, aesKey);
// 输出 256 字节

// 拼接: nonce(12) + encryptedKey(256) + tag(16) + ciphertext
const blob = concatBytes([nonce, encryptedKey, tag, ciphertext]);

// Base64 编码
const encrypted = arrayBufferToBase64(blob);

// 4. 发送请求
await wx.request({
  url: `${host}/api/login`,
  method: 'POST',
  data: {
    token: token,
    encrypted: encrypted,
  },
});
```

---

## 服务端解密流程（参考）

```python
# 1. 接收 encrypted 参数
encrypted = request.query_params.get("encrypted")

# 2. Base64 解码
blob = base64.b64decode(encrypted)

# 3. 拆分
nonce        = blob[0:12]      # 12 字节
encrypted_key = blob[12:268]    # 256 字节 (RSA-2048)
tag          = blob[268:284]    # 16 字节
ciphertext   = blob[284:]       # 剩余密文

# 4. RSA-OAEP(SHA-256) 解密 AES 密钥
aes_key = rsa_private_key.decrypt(encrypted_key)

# 5. AES-GCM 解密
plaintext = aes_gcm_decrypt(aes_key, nonce, ciphertext, tag)

# 6. JSON 解析
params = json.loads(plaintext)  # 得到原始参数字典
```

---

## 向后兼容

如果公钥加载失败或加密过程出错，应回退到明文传输（将参数逐个放入 query string 或 JSON body）。所有后端接口均同时支持加密和明文两种模式。
