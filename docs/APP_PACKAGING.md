# 原生 App 打包（Android / iOS 离线打包）

本项目用 uni-app（Vue3 + Vite）开发，目标是把同一套代码打包成 Android APK 和 iOS IPA。
本仓库通过 **GitHub Actions 离线打包** 完成，不依赖 DCloud 云打包（原因见下）。

---

## 为什么走离线打包，而不是 DCloud 云打包

- DCloud 云打包需要 DCloud 账号登录；但 **中国区账号通过 CLI 登录有已知 bug**（GUI 能登、CLI 报"用户名或密码错误"），而托管 runner 无法复用 GUI 登录态，**中国区应用基本无法走 CLI 云打包**。
- 离线打包：CI 里直接合并 DCloud 官方离线 SDK + 用 Android SDK / Xcode 本地编译，**完全不依赖 DCloud 云、不消耗打包额度、不受登录 bug 影响**。
- iOS 无论如何都需要 **Apple 开发者账号（$99/年）+ 证书 + 描述文件**（这是 Apple 的硬性要求，任何方案都绕不开）。

---

## 关键现实：DCloud 离线 SDK 现在只走网盘

官方下载页（https://nativesupport.dcloud.net.cn/AppDocs/download/android.html 、ios.html）**只提供百度云 / 和彩云网盘链接**，不再提供 CI 可直接 `curl` 的直链 zip。因此本工作流**不假设能从网盘自动下载**，而是要求你先把 SDK 壳工程放到以下两处之一，CI 就能拿到：

- **方案 A（推荐、最稳）**：把 SDK 壳工程**提交到仓库** `native/android/` 和 `native/ios/`。
- **方案 B**：把下载的 zip 重命名为 `android-sdk.zip` / `ios-sdk.zip`，上传到本仓库一个 **GitHub Release（标签固定为 `native-sdk`）**，CI 用 `gh release download` 拉取。

> ⚠️ **离线 SDK 的版本必须和本地 uni 编译器版本严格匹配**，否则运行时闪退 / 页面加载失败。
> 当前本地编译器版本为 **5.26**（HBuilderX `5.26.2026091802`，见 `npm run build:app` 输出）。

---

## 一、一次性准备：获取离线 SDK 壳工程（最重要）

1. 打开官方下载页，找到与 **HBuilderX 5.26.2026091802** 对应的离线 SDK：
   - Android：https://nativesupport.dcloud.net.cn/AppDocs/download/android.html
     - **正式版**：百度云 `https://pan.baidu.com/s/1AFjLggD7g6ue0iKgZ8yVyA?pwd=jrrb`（提取码 `jrrb`）；和彩云 `https://yun.139.com/shareweb/#/w/i/2w2KLgoTHEPz0`
   - iOS：https://nativesupport.dcloud.net.cn/AppDocs/download/ios.html（页面内同版本对应链接）
2. 下载并解压，你会得到一个带版本号的文件夹（如 `Android-SDK@5.26.xxx` / `iOS-SDK@5.26.xxx`），里面有：
   - Android：`HBuilder-Integrate-AS/`（含 `gradlew`，这就是 Gradle 工程）
   - iOS：`HBuilder-Hello/`（含 `.xcodeproj` / `.xcworkspace`，这就是 Xcode 工程）

### 方案 A：提交到仓库 `native/`（推荐）

把上面的工程**内容**直接放进仓库（**不要多套一层 `Android-SDK@xxx` 文件夹**，让 `native/android/gradlew` 直接存在）：

```bash
# Android：把 HBuilder-Integrate-AS 里的全部内容复制到 native/android/
cp -r "Android-SDK@5.26.xxx/HBuilder-Integrate-AS/." native/android/

# iOS：把 HBuilder-Hello 里的全部内容复制到 native/ios/
cp -r "iOS-SDK@5.26.xxx/HBuilder-Hello/." native/ios/

# native/ 已在 .gitignore 忽略，需强制添加：
git add -f native/android native/ios
git commit -m "chore: 加入 DCloud 5.26 离线打包 SDK 壳工程"
git push origin main
```

> 体积提示：Android 壳工程通常 100~300MB，可接受入库；iOS 壳工程（含 framework）往往 1GB+，入库会显著增大仓库。若介意体积，改用方案 B。

### 方案 B：上传到 GitHub Release（标签 `native-sdk`）

把官方下载的原始 zip **直接重命名**后上传（脚本会自动解压并按文件名定位工程，**无需二次解压**）：

```bash
# 把官方 Android 离线 SDK zip 改名为 android-sdk.zip
mv "Android离线SDK_xxx.zip" android-sdk.zip
# 同理 iOS
mv "iOS离线SDK_xxx.zip" ios-sdk.zip
```

然后在 GitHub 仓库 **Releases → Draft a new release**，Tag 填 `native-sdk`（与 `build-app.yml` 的 `NATIVE_SDK_RELEASE` 一致），把 `android-sdk.zip` 和 `ios-sdk.zip` 作为附件上传并发布。

---

## 二、配置仓库 Secrets

路径：仓库 **Settings → Secrets and variables → Secrets**。

### Android（可选，缺省自动生成调试签名）
| Secret | 说明 |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | release keystore 的 base64（可上传到商店）。**不填则 CI 自动生成调试 keystore，只能测试、不能上架** |
| `ANDROID_KEY_ALIAS` | keystore 别名（提供 keystore 时必填） |
| `ANDROID_KEY_PASSWORD` | 密钥密码（提供 keystore 时必填） |
| `ANDROID_STORE_PASSWORD` | keystore 密码（提供 keystore 时必填） |

生成并 base64 一个 release keystore（本地执行）：
```bash
keytool -genkeypair -v -keystore release.keystore -keyalg RSA -keysize 2048 -validity 10000 \
  -alias zaima -dname "CN=Zaima, O=Zaima"
base64 -i release.keystore | tr -d '\n'   # 粘到 ANDROID_KEYSTORE_BASE64
```

### iOS（必填，需要 Apple 开发者账号）
| Secret | 说明 |
|---|---|
| `IOS_P12_BASE64` | 发布/开发证书 `.p12` 的 base64 |
| `IOS_MOBILEPROVISION_BASE64` | `.mobileprovision` 描述文件的 base64 |
| `IOS_CERT_PASSWORD` | p12 导入密码 |
| `APPLE_TEAM_ID` | Apple 开发者 Team ID（10 位大写字母数字） |

导出 base64（本地执行）：
```bash
base64 -i Certificates.p12 | tr -d '\n'        # → IOS_P12_BASE64
base64 -i zaima.mobileprovision | tr -d '\n'   # → IOS_MOBILEPROVISION_BASE64
```

可选 Variables：
- `IOS_EXPORT_METHOD`：`development`（默认，真机调试）/ `ad-hoc`（内测）/ `app-store`（上架）。
- `NATIVE_SDK_RELEASE`：改用其他 Release 标签名时设置（默认 `native-sdk`）。
- `DCLOUD_ANDROID_SDK_URL` / `DCLOUD_IOS_SDK_URL`：若你有**自己托管的直链** zip，可填此处（优先级低于方案 A/B）。

---

## 三、触发构建

- **手动**：仓库 **Actions → 构建原生 App 安装包 → Run workflow**，选择 `android` / `ios` / `both`。
- **打 tag**：`git tag v1.0.1 && git push origin v1.0.1` 自动构建 `both`。

完成后在对应 run 的 **Artifacts** 下载：
- `android-apk`：`native/android/app/build/outputs/apk/release/*.apk`
- `ios-ipa`：`native/ios/build/*.ipa`

---

## 四、相关文件

| 文件 | 作用 |
|---|---|
| `.github/workflows/build-app.yml` | CI 工作流（按平台分 job） |
| `scripts/build-android.sh` | 取壳工程 → 合并资源 → gradle 构建/签名 APK |
| `scripts/build-ios.sh` | 取壳工程 → 合并资源 → 导入证书 → xcodebuild 出 IPA |
| `frontend/src/manifest.json` | `appid` / `app-plus.distribute.android.package` / `app-plus.distribute.ios.bundle` 已配置 |

> `native/` 默认被 `.gitignore` 忽略（CI 运行时也会重新生成）。若采用方案 A，需 `git add -f`。

---

## 五、常见问题 / 微调点

1. **Android 报「未找到 gh / native/android 不存在」**：说明你既没提交 `native/android`，也没在 Release 放 `android-sdk.zip`。按「方案一 / 二」补齐其一即可。
2. **gradle 报 `failed to find Build Tools / SDK platform`**：脚本已装 `android-34/33` 与 `build-tools 34.0.0/33.0.2`；若你的 SDK 工程要求更高版本，在 `build-app.yml` 的「安装 Android SDK」步骤补装对应 `platforms;android-XX` / `build-tools;XX.0.0`。
3. **appid 没替换成功**：脚本用 `find` 定位 `dcloud_control.xml` 并 sed 替换 `__UNI__XXXX`；若 SDK 把 appid 写在别处，确认 `control.xml` 已被修改、`apps/<APP_ID>/www` 已生成。
4. **iOS 描述文件名称不匹配**：脚本自动从 mobileprovision 解析 `Name` 写进 `exportOptions.plist`；若失败，检查 bundle id 与描述文件是否一致、`APPLE_TEAM_ID` 是否正确。
5. **iOS 真机调试用 `development`，上架用 `app-store`**：通过 `IOS_EXPORT_METHOD` 变量切换。
6. **iOS 离线打包 CI 首次成功率较低**：Xcode 版本匹配、描述文件、entitlements 等需调试；若持续卡住，更现实的路径是用 **HBuilderX 云打包**（需 Apple 开发者账号+证书，在 HBuilderX「发行 → 原生App-云打包」里配置），CI 仅作参考。
