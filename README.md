# Tabis VPN — Open Source Client Applications

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Android](https://img.shields.io/badge/Platform-Android%20%7C%20Windows-green.svg)](https://tabisvpn.site)
[![API](https://img.shields.io/badge/API-24%2B-yellow.svg)](https://developer.android.com)
[![Protocol](https://img.shields.io/badge/Protocols-Hysteria%202%20%7C%20V2Ray%20%7C%20Xray-orange.svg)](https://v2fly.org)

Official open-source repository for **Tabis VPN** client applications.

Tabis VPN is a next-generation, high-performance privacy service designed to bypass strict network censorship, ISP throttling, and packet loss using modern protocols (Hysteria 2 over QUIC/UDP, VLESS, Trojan, and Shadowsocks).

---

## 🔒 Open Source & Privacy Principles

We believe that any software handling user traffic and digital privacy **must be open-source, auditable, and transparent**.

- **Zero-Logs Architecture**: Client applications do not collect or transmit browsing telemetry, visited domains, or DNS traffic.
- **End-to-End Cryptography**: All tunnel payloads are encrypted with state-of-the-art TLS 1.3 / ChaCha20-Poly1305 / AES-128-GCM ciphers.
- **Reproducible Builds**: All client releases can be independently compiled directly from this repository.
- **GPLv3 Compliance**: Licensed under the GNU General Public License v3, ensuring user freedom and preventing proprietary lock-in.

---

## 📁 Repository Structure

```text
├── V2rayNG/              # Android native application (Kotlin, Jetpack Compose, Material 3)
│   ├── app/              # Android app module (UI, Services, Core tunnels, IPC)
│   ├── gradle/           # Gradle wrapper and version catalog (libs.versions.toml)
│   └── build.gradle.kts  # Project build configuration
├── windows-client/       # Windows desktop client (Python, PyWebView UI, Hysteria 2)
│   ├── ui/               # Modern desktop frontend assets
│   ├── main.py           # Core client process & system proxy controller
│   ├── installer.py      # Automated Windows setup helper
│   ├── TabisVPN.spec     # PyInstaller bundle specification
│   └── TabisVPN_Setup.iss# Inno Setup Windows installer script
├── fastlane/             # Store release metadata and branding
├── compile-hevtun.sh     # NDK build script for hev-socks5-tunnel (tun2socks)
├── .github/workflows/    # Automated CI/CD pipeline for reproducible builds
├── LICENSE               # GNU General Public License v3.0
└── README.md             # Project documentation
```

---

## 🚀 Protocols & Core Engine

1. **Hysteria 2 (QUIC / UDP)**:
   - Custom congestion control algorithm (Brutal CC) optimized for unstable and high-latency cellular or home networks.
   - Resistant to DPI (Deep Packet Inspection) and active probing via port-hopping and TLS masquerading.
2. **Xray / V2Ray Core**:
   - High-throughput routing for VLESS, Trojan, VMess, and Shadowsocks.
   - Built-in geo-routing (`geosite.dat`, `geoip.dat`) for split-tunneling and domestic bypassing.
3. **hev-socks5-tunnel**:
   - Lightweight, multi-threaded native C TUN-to-SOCKS5 forwarder for Android VPNService integration.

---

## 🛠 Building from Source

### Android Client (`V2rayNG`)

#### Prerequisites
- **JDK**: Java 21 (Temurin or OpenJDK)
- **Android SDK**: API Level 35+ with Build Tools 35.0.0+
- **Android NDK**: Version `29.0.14206865` or latest LTS
- **Git** with submodule support

#### Build Steps

1. **Clone repository with submodules**:
   ```bash
   git clone --recursive https://github.com/tabisvpn/tabisvpn-client.git
   cd tabisvpn-client
   ```

2. **Compile native HEV tunnel library**:
   ```bash
   bash compile-hevtun.sh
   cp -r libs/* V2rayNG/app/libs/
   ```

3. **Fetch or compile `libv2ray.aar`**:
   The native Xray core (`libv2ray.aar`) can be built from [AndroidLibXrayLite](https://github.com/2dust/AndroidLibXrayLite) or downloaded from its release tags and placed into `V2rayNG/app/libs/libv2ray.aar`.

4. **Build APK via Gradle**:
   ```bash
   cd V2rayNG
   ./gradlew assemblePlaystoreDebug
   ```
   The compiled APK will be generated at `V2rayNG/app/build/outputs/apk/playstore/debug/`.

---

### Windows Desktop Client (`windows-client`)

#### Prerequisites
- **Python**: Version 3.10+
- **PyInstaller**: `pip install pyinstaller pywebview pillow`
- **Inno Setup**: Version 6+ (for generating `.exe` installer)

#### Build Steps

1. **Navigate to the Windows client directory**:
   ```bash
   cd windows-client
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt # pywebview, pillow
   ```

3. **Obtain official Hysteria 2 binary**:
   Place the official `hysteria-windows-amd64.exe` as `windows-client/bin/hysteria.exe`.

4. **Build standalone executable**:
   ```bash
   build.bat
   ```
   Or execute PyInstaller directly:
   ```bash
   pyinstaller TabisVPN.spec
   ```
   The output binary will be located in `windows-client/dist/TabisVPN/`.

---

## 🛡 Security & Vulnerability Disclosure

Security and user trust are our top priorities. If you discover a vulnerability or potential security flaw:

- Please email us directly at: **security@tabisvpn.site**
- Include detailed reproduction steps and logs.
- We support responsible disclosure and will address confirmed reports promptly.

---

## 📄 License

This repository is licensed under the [GNU General Public License v3.0 (GPLv3)](LICENSE).

Third-party dependencies and cores:
- **v2rayNG / AndroidLibXrayLite**: GPLv3
- **Xray-core / v2fly**: Mozilla Public License 2.0 / MIT
- **Hysteria 2**: MIT License
- **hev-socks5-tunnel**: MIT License
