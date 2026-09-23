# Tabis VPN — Complete Open Source Ecosystem

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Android](https://img.shields.io/badge/Platform-Android%20%7C%20Windows%20%7C%20Web-green.svg)](https://tabisvpn.site)
[![API](https://img.shields.io/badge/API-FastAPI%20%7C%20Python%203.11%2B-blue.svg)](https://fastapi.tiangolo.com)
[![Protocol](https://img.shields.io/badge/Protocols-Hysteria%202%20%7C%20VLESS%20Reality%20%7C%20Xray-orange.svg)](https://v2fly.org)

Official open-source repository for the **Tabis VPN** privacy ecosystem: client applications (Android and Windows), management backend server (FastAPI), web touchpoints, and administrative dashboards.

Tabis VPN is designed to bypass strict network censorship, ISP throttling, and packet loss using modern cryptographic protocols (**Hysteria 2 over QUIC/UDP**, **VLESS Reality**, **Trojan**, and **Shadowsocks**).

---

## 🔒 Open Source & Privacy Principles

We believe that software handling user traffic and digital privacy **must be open-source, auditable, and transparent**.

- **End-to-End Cryptography**: All tunnel payloads are encrypted with state-of-the-art TLS 1.3 / ChaCha20-Poly1305 / AES-128-GCM ciphers.
- **Reproducible Builds**: All client releases can be independently compiled directly from this repository.
- **Clean Architecture**: Decoupled backend with environment-based configuration, parameterized server nodes, and strict exclusion of private keys from public source trees.
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
├── backend/              # Management API server (FastAPI, SQLite, Docker)
│   ├── core/             # Security, auth, and crypto helpers
│   ├── routers/          # API endpoints (auth, client, profile, public, admin)
│   ├── services/         # Billing, traffic retention, metrics, and Xray sync
│   ├── models.py         # Pydantic data models
│   ├── database.py       # SQLite connection pool and migrations
│   ├── Dockerfile        # Container build definition
│   ├── docker-compose.yml# Container orchestration
│   └── .env.example      # Sample configuration file
├── admin/                # Web administrative dashboard (Vue 3, Chart.js, Tailwind CSS)
├── profile/              # User self-service portal (subscription management, devices)
├── android/              # Android client portal & APK verification instructions
├── ios/                  # iOS setup portal (Streisand, Happ, Karing, Shadowrocket)
├── windows/              # Windows desktop download portal
├── assets/               # Shared stylesheets, branding, and live chat widget
├── fastlane/             # Store release metadata and branding
├── compile-hevtun.sh     # NDK build script for hev-socks5-tunnel (tun2socks)
├── .github/workflows/    # Automated CI/CD pipeline for reproducible builds
├── LICENSE               # GNU General Public License v3.0
├── ROADMAP.md            # Technical and feature roadmap
├── TERMS.md              # Terms of Service & legal framework
├── PRIVACY.md            # Privacy policy & data protection declaration
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

## 🛠 Running the Backend

### Quick Start with Docker Compose

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```
3. Copy the sample server list:
   ```bash
   cp servers.example.txt servers.txt
   ```
4. Start the container:
   ```bash
   docker compose up -d --build
   ```
5. Check health:
   ```bash
   curl http://localhost:8080/health
   # Returns: {"status":"ok","time":...}
   ```

---

## 📱 Building the Clients

### Android Client (`V2rayNG`)

#### Prerequisites
- **JDK**: Java 21 (Temurin or OpenJDK)
- **Android SDK**: API Level 35+ with Build Tools 35.0.0+
- **Android NDK**: Version `29.0.14206865` or latest LTS
- **Git** with submodule support

#### Build Steps
```bash
cd V2rayNG
git submodule update --init --recursive
./gradlew assemblePlaystoreRelease
```

### Windows Desktop Client (`windows-client`)

#### Prerequisites
- **Python 3.11+**
- **PyInstaller**: `pip install pyinstaller pywebview pillow`
- **Inno Setup 6** (for building `TabisVPN_Setup.exe`)

#### Build Steps
```bash
cd windows-client
python -m PyInstaller TabisVPN.spec
```

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.
