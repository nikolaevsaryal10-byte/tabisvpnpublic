package com.v2ray.ang.ui.tabis

import android.util.Base64
import com.v2ray.ang.AppConfig
import com.v2ray.ang.AppConfig.DEFAULT_SUBSCRIPTION_ID
import com.v2ray.ang.dto.entities.ProfileItem
import com.v2ray.ang.dto.entities.SubscriptionItem
import com.v2ray.ang.fmt.Hysteria2Fmt
import com.v2ray.ang.fmt.ShadowsocksFmt
import com.v2ray.ang.fmt.TrojanFmt
import com.v2ray.ang.fmt.VlessFmt
import com.v2ray.ang.fmt.VmessFmt
import com.v2ray.ang.fmt.WireguardFmt
import com.v2ray.ang.handler.MmkvManager
import com.v2ray.ang.util.LogUtil
import com.v2ray.ang.util.Utils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

data class TabisUserProfile(
    val id: Int = 0,
    val email: String = "",
    val nickname: String = "",
    val userCode: String = "",
    val balance: Int = 0,
    val createdAt: String = "",
    val daysRemaining: Int = 0,
    val activeDevices: Int = 0,
    val totalDevices: Int = 0,
    val monthlyCost: Int = 0,
    val isActive: Boolean = false
)

data class TabisDevice(
    val id: Int,
    val deviceName: String,
    val token: String,
    val isActive: Boolean,
    val tariffPlan: String,
    val tariffName: String,
    val monthlyCost: Int,
    val subscriptionExpiresAt: String,
    val daysRemaining: Int,
    val speedLimit: String,
    val trafficGb: Double,
    val trafficLimitGb: Int,
    val trafficPercent: Double,
    val statusText: String,
    val isPrimary: Boolean
)

data class TabisSupportMessage(
    val id: Int,
    val senderType: String, // "user" or "admin"
    val senderName: String,
    val text: String,
    val createdAt: String
)

enum class ConnectionStatusCheck {
    ALLOWED,
    ZERO_BALANCE,
    ACCESS_REVOKED,
    DEVICE_DELETED
}

object TabisSecurityManager {

    // 256-bit AES key and 128-bit IV
    private val AES_KEY_BYTES = byteArrayOf(
        0x54, 0x61, 0x62, 0x69, 0x73, 0x56, 0x70, 0x6E,
        0x53, 0x61, 0x66, 0x65, 0x4B, 0x65, 0x79, 0x5F,
        0x32, 0x30, 0x32, 0x36, 0x5F, 0x45, 0x6E, 0x63,
        0x72, 0x79, 0x70, 0x74, 0x65, 0x64, 0x33, 0x32
    )

    private val AES_IV_BYTES = byteArrayOf(
        0x54, 0x61, 0x62, 0x69, 0x73, 0x56, 0x70, 0x6E,
        0x49, 0x6E, 0x69, 0x74, 0x49, 0x56, 0x31, 0x36
    )

    const val PREF_TABIS_BACKEND_URL = "pref_tabis_backend_url"
    const val PREF_TABIS_API_KEY = "pref_tabis_api_key"
    const val PREF_TABIS_USER_TOKEN = "pref_tabis_user_token"
    const val PREF_TABIS_DEVICE_ID = "pref_tabis_device_id"
    const val PREF_TABIS_SESSION_TOKEN = "pref_tabis_session_token"
    const val PREF_TABIS_USER_EMAIL = "pref_tabis_user_email"
    const val PREF_TABIS_USER_NICKNAME = "pref_tabis_user_nickname"
    const val PREF_TABIS_USER_CODE = "pref_tabis_user_code"
    const val PREF_TABIS_USER_BALANCE = "pref_tabis_user_balance"
    const val PREF_TABIS_USER_CREATED_AT = "pref_tabis_user_created_at"
    const val PREF_TABIS_IS_NEW_USER = "pref_tabis_is_new_user"
    const val PREF_TABIS_SUPPORT_CHAT_TOKEN = "pref_tabis_support_chat_token"

    fun getSupportChatSessionToken(): String {
        var token = MmkvManager.decodeSettingsString(PREF_TABIS_SUPPORT_CHAT_TOKEN)
        if (token.isNullOrBlank()) {
            token = "chat_" + java.util.UUID.randomUUID().toString().replace("-", "")
            MmkvManager.encodeSettings(PREF_TABIS_SUPPORT_CHAT_TOKEN, token)
        }
        return token
    }

    // Production backend configuration on your VPS domain
    const val DEFAULT_BACKEND_URL = "https://tabisvpn.site/api/v1/servers"
    const val DEFAULT_API_KEY = "YOUR_TABIS_DEVICE_TOKEN"

    fun getSessionToken(): String? {
        return MmkvManager.decodeSettingsString(PREF_TABIS_SESSION_TOKEN)?.takeIf { it.isNotBlank() }
    }

    fun setSessionToken(token: String?) {
        if (token != null) {
            MmkvManager.encodeSettings(PREF_TABIS_SESSION_TOKEN, token.trim())
        } else {
            MmkvManager.encodeSettings(PREF_TABIS_SESSION_TOKEN, "")
        }
    }

    fun getUserEmail(): String = MmkvManager.decodeSettingsString(PREF_TABIS_USER_EMAIL).orEmpty()
    fun getUserNickname(): String = MmkvManager.decodeSettingsString(PREF_TABIS_USER_NICKNAME).orEmpty().ifBlank { "Пользователь" }
    fun getUserCode(): String = MmkvManager.decodeSettingsString(PREF_TABIS_USER_CODE).orEmpty().ifBlank { "TABIS-XXXX-XXXX" }
    fun getUserBalance(): Int = MmkvManager.decodeSettingsInt(PREF_TABIS_USER_BALANCE, 0)
    fun getUserCreatedAt(): String = MmkvManager.decodeSettingsString(PREF_TABIS_USER_CREATED_AT).orEmpty()
    fun isNewUser(): Boolean = MmkvManager.decodeSettingsBool(PREF_TABIS_IS_NEW_USER, false)
    fun setNewUser(isNew: Boolean) = MmkvManager.encodeSettings(PREF_TABIS_IS_NEW_USER, isNew)

    fun getApiBaseUrl(): String {
        return getBackendUrl().substringBefore("/api/")
    }

    fun logout() {
        setSessionToken(null)
        setUserToken(null)
        MmkvManager.encodeSettings(PREF_TABIS_USER_EMAIL, "")
        MmkvManager.encodeSettings(PREF_TABIS_USER_NICKNAME, "")
        MmkvManager.encodeSettings(PREF_TABIS_USER_CODE, "")
        MmkvManager.encodeSettings(PREF_TABIS_USER_BALANCE, 0)
        MmkvManager.encodeSettings(PREF_TABIS_IS_NEW_USER, false)
    }

    fun getDeviceId(): String {
        var id = MmkvManager.decodeSettingsString(PREF_TABIS_DEVICE_ID)
        if (id.isNullOrBlank()) {
            id = java.util.UUID.randomUUID().toString()
            MmkvManager.encodeSettings(PREF_TABIS_DEVICE_ID, id)
        }
        return id
    }

    fun getUserToken(): String? {
        return MmkvManager.decodeSettingsString(PREF_TABIS_USER_TOKEN)?.takeIf { it.isNotBlank() }
    }

    fun setUserToken(token: String?) {
        if (token != null) {
            MmkvManager.encodeSettings(PREF_TABIS_USER_TOKEN, token.trim().uppercase())
        } else {
            MmkvManager.encodeSettings(PREF_TABIS_USER_TOKEN, "")
        }
    }

    fun isActivated(): Boolean {
        return !getSessionToken().isNullOrBlank() || !getUserToken().isNullOrBlank()
    }

    fun getDeviceModel(): String {
        val manufacturer = android.os.Build.MANUFACTURER.replaceFirstChar { it.uppercase() }
        val model = android.os.Build.MODEL
        return "$manufacturer $model"
    }

    fun getBackendUrl(): String {
        val saved = MmkvManager.decodeSettingsString(PREF_TABIS_BACKEND_URL)
        return if (!saved.isNullOrBlank()) saved else DEFAULT_BACKEND_URL
    }

    fun setBackendUrl(url: String) {
        MmkvManager.encodeSettings(PREF_TABIS_BACKEND_URL, url)
    }

    fun getApiKey(): String {
        // Use active user token if authenticated, otherwise fallback to default api key
        return getUserToken() ?: DEFAULT_API_KEY
    }

    fun setApiKey(key: String) {
        MmkvManager.encodeSettings(PREF_TABIS_API_KEY, key)
    }

    fun isBackendConfigured(): Boolean {
        val url = getBackendUrl()
        return url.isNotBlank() && !url.contains("yourdomain.com")
    }

    private fun decodeBase64(str: String): ByteArray {
        return try {
            java.util.Base64.getDecoder().decode(str)
        } catch (_: Throwable) {
            Base64.decode(str, Base64.DEFAULT)
        }
    }

    private fun encodeBase64(bytes: ByteArray): String {
        return try {
            java.util.Base64.getEncoder().encodeToString(bytes)
        } catch (_: Throwable) {
            Base64.encodeToString(bytes, Base64.NO_WRAP)
        }
    }

    fun decrypt(encryptedBase64: String): String? {
        return try {
            val cipherBytes = decodeBase64(encryptedBase64)
            val keySpec = SecretKeySpec(AES_KEY_BYTES, "AES")
            val ivSpec = IvParameterSpec(AES_IV_BYTES)
            val cipher = try {
                Cipher.getInstance("AES/CBC/PKCS7Padding")
            } catch (_: Throwable) {
                Cipher.getInstance("AES/CBC/PKCS5Padding")
            }
            cipher.init(Cipher.DECRYPT_MODE, keySpec, ivSpec)
            val decryptedBytes = cipher.doFinal(cipherBytes)
            String(decryptedBytes, StandardCharsets.UTF_8)
        } catch (e: Exception) {
            null
        }
    }

    fun encrypt(plainText: String): String? {
        return try {
            val keySpec = SecretKeySpec(AES_KEY_BYTES, "AES")
            val ivSpec = IvParameterSpec(AES_IV_BYTES)
            val cipher = try {
                Cipher.getInstance("AES/CBC/PKCS7Padding")
            } catch (_: Throwable) {
                Cipher.getInstance("AES/CBC/PKCS5Padding")
            }
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, ivSpec)
            val encryptedBytes = cipher.doFinal(plainText.toByteArray(StandardCharsets.UTF_8))
            encodeBase64(encryptedBytes)
        } catch (_: Exception) {
            null
        }
    }

    fun parseServerProfile(uri: String): ProfileItem? {
        return try {
            when {
                uri.startsWith("vless://") -> VlessFmt.parse(uri)
                uri.startsWith("vmess://") -> VmessFmt.parse(uri)
                uri.startsWith("ss://") -> ShadowsocksFmt.parse(uri)
                uri.startsWith("trojan://") -> TrojanFmt.parse(uri)
                uri.startsWith("hysteria2://") || uri.startsWith("hy2://") -> Hysteria2Fmt.parse(uri)
                uri.startsWith("wireguard://") -> WireguardFmt.parse(uri)
                else -> null
            }
        } catch (e: Exception) {
            LogUtil.e(AppConfig.TAG, "Failed to parse URI", e)
            null
        }
    }

    fun getServerDisplayName(guid: String, fallbackIndex: Int = 1): String {
        val serverList = MmkvManager.decodeAllServerList()
        val index = serverList.indexOf(guid)
        val number = if (index >= 0) index + 1 else fallbackIndex
        return "Сервер #$number"
    }

    /**
     * Applies a list of encrypted (or raw) server keys into storage.
     * Renames all of them neutrally to "Сервер #1", "Сервер #2", etc.
     */
    fun applyServerKeys(keys: List<String>): String? {
        if (MmkvManager.decodeSubscription(DEFAULT_SUBSCRIPTION_ID) == null) {
            val defaultSub = SubscriptionItem(remarks = "Default")
            MmkvManager.encodeSubscription(DEFAULT_SUBSCRIPTION_ID, defaultSub)
        }

        val existingGuids = MmkvManager.decodeServerList(DEFAULT_SUBSCRIPTION_ID)
        val newGuids = ArrayList<String>()
        var firstGuid: String? = null

        keys.forEachIndexed { index, key ->
            val plainUri = decrypt(key) ?: (if (key.contains("://")) key else null) ?: return@forEachIndexed
            val serverNumber = index + 1
            val maskedName = "Сервер #$serverNumber"

            val profile = parseServerProfile(plainUri) ?: return@forEachIndexed
            profile.remarks = maskedName
            profile.subscriptionId = DEFAULT_SUBSCRIPTION_ID

            // Preserve existing guid if available to avoid breaking active connection
            val matchedGuid = existingGuids.firstOrNull { guid ->
                val p = MmkvManager.decodeServerConfig(guid)
                p?.remarks == maskedName
            } ?: Utils.getUuid()

            MmkvManager.encodeServerConfig(matchedGuid, profile)
            newGuids.add(matchedGuid)
            if (firstGuid == null) firstGuid = matchedGuid
        }

        if (newGuids.isNotEmpty()) {
            val removedGuids = existingGuids.filter { !newGuids.contains(it) }
            removedGuids.forEach { MmkvManager.removeServer(it) }

            MmkvManager.encodeServerList(newGuids, DEFAULT_SUBSCRIPTION_ID)
        }

        val currentSelected = MmkvManager.getSelectServer()
        if ((currentSelected.isNullOrEmpty() || !newGuids.contains(currentSelected)) && firstGuid != null) {
            MmkvManager.setSelectServer(firstGuid)
        }

        // Optimize DNS & Routing for high speed and Russian censorship bypass
        optimizeRoutingAndDns()

        return MmkvManager.getSelectServer() ?: firstGuid
    }

    /**
     * Ensures optimal VPN settings for Hysteria 2 speed and Russian censorship bypass.
     *
     * Key optimizations:
     * - MTU 1350: prevents QUIC packet blackholing on mobile/ISP networks (1500 + QUIC headers > path MTU)
     * - DoH remote DNS: plain UDP 53 to 1.1.1.1/8.8.8.8 is intercepted by TSPU in Russia
     * - Local DNS enabled: routes all DNS queries through the VPN tunnel
     * - Mux disabled: conflicts with QUIC's native stream multiplexing in Hysteria 2
     * - Sniffing enabled: required for correct domain-based routing
     */
    fun optimizeRoutingAndDns() {
        try {
            // MTU 1350 is critical for Hysteria 2 (QUIC/UDP):
            // Mobile carriers and Russian ISPs drop oversized UDP packets silently.
            // QUIC adds ~50-80 bytes of headers, so 1500 MTU inner packets become
            // 1550-1580 bytes on the wire, exceeding the typical 1420-1500 path MTU.
            MmkvManager.encodeSettings(AppConfig.PREF_VPN_MTU, "1350")

            // Use DoH (DNS-over-HTTPS) for remote DNS to avoid TSPU interception
            // of plain UDP DNS queries on port 53
            MmkvManager.encodeSettings(AppConfig.PREF_REMOTE_DNS, "https://1.1.1.1/dns-query")
            MmkvManager.encodeSettings(AppConfig.PREF_DOMESTIC_DNS, "https://1.1.1.1/dns-query")
            MmkvManager.encodeSettings(AppConfig.PREF_VPN_DNS, "1.1.1.1,8.8.8.8")

            // Enable local DNS so all DNS queries are routed through the tunnel
            MmkvManager.encodeSettings(AppConfig.PREF_LOCAL_DNS_ENABLED, true)

            // Enable sniffing for proper domain-based routing decisions
            MmkvManager.encodeSettings(AppConfig.PREF_SNIFFING_ENABLED, true)

            // Disable Mux: Hysteria 2 uses QUIC which has native stream multiplexing.
            // Enabling Mux on top of QUIC causes double-encapsulation overhead and stalls.
            MmkvManager.encodeSettings(AppConfig.PREF_MUX_ENABLED, false)

            // Disable fragment: not needed for QUIC-based protocols and adds overhead
            MmkvManager.encodeSettings(AppConfig.PREF_FRAGMENT_ENABLED, false)

            // Ensure global routing rule is present (proxy everything except private LAN)
            val globalRules = mutableListOf(
                com.v2ray.ang.dto.entities.RulesetItem(
                    remarks = "Bypass LAN IP",
                    outboundTag = AppConfig.TAG_DIRECT,
                    ip = arrayListOf(AppConfig.GEOIP_PRIVATE),
                    enabled = true
                ),
                com.v2ray.ang.dto.entities.RulesetItem(
                    remarks = "Bypass LAN Domain",
                    outboundTag = AppConfig.TAG_DIRECT,
                    domain = arrayListOf(AppConfig.GEOSITE_PRIVATE),
                    enabled = true
                ),
                com.v2ray.ang.dto.entities.RulesetItem(
                    remarks = "Global Proxy",
                    outboundTag = AppConfig.TAG_PROXY,
                    port = "0-65535",
                    enabled = true
                )
            )
            MmkvManager.encodeRoutingRulesets(globalRules)
        } catch (e: Exception) {
            LogUtil.w(AppConfig.TAG, "Failed to optimize routing and DNS", e)
        }
    }

    /**
     * Initial local sync on app startup using embedded keys if no servers are loaded yet.
     */
    fun syncEmbeddedServers(): String? {
        optimizeRoutingAndDns()
        val existingGuids = MmkvManager.decodeServerList(DEFAULT_SUBSCRIPTION_ID)
        return if (existingGuids.isNotEmpty()) {
            MmkvManager.getSelectServer() ?: existingGuids.firstOrNull()
        } else {
            null
        }
    }

    /**
     * Activates a single-use or user access token from the backend.
     * Locks the token to this device_id.
     */
    suspend fun activateToken(token: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val cleanToken = token.trim().uppercase()
        val deviceId = getDeviceId()
        val deviceModel = getDeviceModel()
        val baseUrl = getBackendUrl().substringBefore("/api/")

        try {
            val client = OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(10, TimeUnit.SECONDS)
                .build()

            val jsonBody = JSONObject().apply {
                put("token", cleanToken)
                put("device_id", deviceId)
                put("device_model", deviceModel)
            }

            val mediaType = "application/json; charset=utf-8".toMediaTypeOrNull()
            val requestBody = jsonBody.toString().toRequestBody(mediaType)

            val request = Request.Builder()
                .url("$baseUrl/api/v1/auth/activate")
                .header("Content-Type", "application/json")
                .header("User-Agent", "TabisVPN-Android/1.0")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val bodyStr = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    setUserToken(cleanToken)
                    // Immediately sync server keys
                    syncRemoteServers()
                    return@withContext Pair(true, "Успешно подключено!")
                } else {
                    val errMsg = try {
                        JSONObject(bodyStr).optString("detail", "Ошибка активации (${response.code})")
                    } catch (_: Exception) {
                        "Ошибка активации (${response.code})"
                    }
                    return@withContext Pair(false, errMsg)
                }
            }
        } catch (e: Exception) {
            LogUtil.e(AppConfig.TAG, "Token activation network error", e)
            return@withContext Pair(false, "Не удалось связаться с сервером. Проверьте интернет.")
        }
    }

    /**
     * Fetches server keys from remote VPS backend.
     * Safe, non-blocking, falls back quietly if network/server is down.
     */
    suspend fun syncRemoteServers(): Boolean = withContext(Dispatchers.IO) {
        val baseUrl = getBackendUrl()
        if (baseUrl.isBlank()) return@withContext false

        val token = getUserToken() ?: DEFAULT_API_KEY
        val deviceId = getDeviceId()
        val url = if (baseUrl.contains("?")) {
            "$baseUrl&token=$token&device_id=$deviceId"
        } else {
            "$baseUrl?token=$token&device_id=$deviceId"
        }

        try {
            val client = OkHttpClient.Builder()
                .connectTimeout(7, TimeUnit.SECONDS)
                .readTimeout(10, TimeUnit.SECONDS)
                .build()

            val request = Request.Builder()
                .url(url)
                .header("X-API-Key", token)
                .header("User-Agent", "TabisVPN-Android/1.0")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    LogUtil.w(AppConfig.TAG, "Remote sync response code: ${response.code}")
                    if (response.code == 401 || response.code == 403) {
                        // Token revoked or device mismatch - invalidate local activation
                        setUserToken(null)
                    }
                    return@withContext false
                }

                val body = response.body?.string().orEmpty()
                val json = JSONObject(body)
                val serversArray = json.optJSONArray("servers") ?: return@withContext false

                val remoteKeys = mutableListOf<String>()
                for (i in 0 until serversArray.length()) {
                    val k = serversArray.optString(i)
                    if (k.isNotBlank()) {
                        remoteKeys.add(k)
                    }
                }

                if (remoteKeys.isNotEmpty()) {
                    applyServerKeys(remoteKeys)
                    LogUtil.i(AppConfig.TAG, "Successfully synced ${remoteKeys.size} servers from VPS")
                    return@withContext true
                }
            }
        } catch (e: Exception) {
            LogUtil.w(AppConfig.TAG, "Remote server sync skipped or failed: ${e.message}")
        }
        return@withContext false
    }

    suspend fun checkConnectionEligibility(): Pair<ConnectionStatusCheck, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) {
            val token = getUserToken()
            if (token.isNullOrBlank()) {
                return@withContext Pair(ConnectionStatusCheck.ACCESS_REVOKED, "Требуется авторизация")
            }
            return@withContext Pair(ConnectionStatusCheck.ALLOWED, "")
        }

        val baseUrl = getApiBaseUrl()
        try {
            val client = OkHttpClient.Builder()
                .connectTimeout(6, TimeUnit.SECONDS)
                .readTimeout(6, TimeUnit.SECONDS)
                .build()

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/me")
                .header("Authorization", "Bearer $session")
                .header("User-Agent", "TabisVPN-Android/2.4.1")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (response.code == 401 || response.code == 403) {
                    return@withContext Pair(
                        ConnectionStatusCheck.ACCESS_REVOKED,
                        "Вы были отключены от доступа к серверам, обратитесь в поддержку в телеграме @atlzgamerz"
                    )
                }
                if (!response.isSuccessful) {
                    return@withContext Pair(ConnectionStatusCheck.ALLOWED, "")
                }

                val body = response.body?.string().orEmpty()
                val json = JSONObject(body)
                val userObj = json.optJSONObject("user")
                val balance = userObj?.optInt("balance", 0) ?: 0
                val devicesArray = json.optJSONArray("devices")

                MmkvManager.encodeSettings(PREF_TABIS_USER_BALANCE, balance)

                val currentToken = getUserToken()
                var currentDeviceObj: JSONObject? = null
                if (devicesArray != null && devicesArray.length() > 0) {
                    for (i in 0 until devicesArray.length()) {
                        val d = devicesArray.optJSONObject(i) ?: continue
                        if (d.optString("token") == currentToken || d.optString("device_name").contains("Основное", ignoreCase = true)) {
                            currentDeviceObj = d
                            break
                        }
                    }
                    if (currentDeviceObj == null && devicesArray.length() > 0) {
                        currentDeviceObj = devicesArray.optJSONObject(0)
                    }
                }

                if (currentDeviceObj == null) {
                    return@withContext Pair(
                        ConnectionStatusCheck.DEVICE_DELETED,
                        "Это устройство было удалено, обратитесь в поддержку в телеграме @atlzgamerz"
                    )
                }

                val daysRemaining = currentDeviceObj.optInt("days_remaining", 0)
                val isActive = currentDeviceObj.optInt("is_active", 0) == 1

                if (balance <= 0 && daysRemaining <= 0) {
                    return@withContext Pair(
                        ConnectionStatusCheck.ZERO_BALANCE,
                        "У вас на балансе 0 руб, пополните пожалуйста"
                    )
                }

                if (!isActive && daysRemaining <= 0) {
                    return@withContext Pair(
                        ConnectionStatusCheck.ZERO_BALANCE,
                        "Срок действия тарифа истек. Пополните баланс для продолжения работы"
                    )
                }

                return@withContext Pair(ConnectionStatusCheck.ALLOWED, "")
            }
        } catch (e: Exception) {
            return@withContext Pair(ConnectionStatusCheck.ALLOWED, "")
        }
    }

    suspend fun fetchProfileMe(): Pair<TabisUserProfile?, List<TabisDevice>> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(null, emptyList())
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder()
                .connectTimeout(8, TimeUnit.SECONDS)
                .readTimeout(8, TimeUnit.SECONDS)
                .build()

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/me")
                .header("Authorization", "Bearer $session")
                .header("User-Agent", "TabisVPN-Android/2.4.1")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext Pair(null, emptyList())
                val body = response.body?.string().orEmpty()
                val json = JSONObject(body)

                val userObj = json.optJSONObject("user")
                val billingObj = json.optJSONObject("billing")
                val devicesArr = json.optJSONArray("devices")

                val profile = if (userObj != null) {
                    val id = userObj.optInt("id")
                    val email = userObj.optString("email")
                    val nickname = userObj.optString("nickname")
                    val userCode = userObj.optString("user_code")
                    val balance = userObj.optInt("balance")
                    val createdAt = userObj.optString("created_at")

                    MmkvManager.encodeSettings(PREF_TABIS_USER_EMAIL, email)
                    MmkvManager.encodeSettings(PREF_TABIS_USER_NICKNAME, nickname)
                    MmkvManager.encodeSettings(PREF_TABIS_USER_CODE, userCode)
                    MmkvManager.encodeSettings(PREF_TABIS_USER_BALANCE, balance)
                    MmkvManager.encodeSettings(PREF_TABIS_USER_CREATED_AT, createdAt)

                    TabisUserProfile(
                        id = id,
                        email = email,
                        nickname = nickname,
                        userCode = userCode,
                        balance = balance,
                        createdAt = createdAt,
                        activeDevices = billingObj?.optInt("active_devices", 0) ?: 0,
                        totalDevices = billingObj?.optInt("total_devices", 0) ?: 0,
                        monthlyCost = billingObj?.optInt("total_monthly_cost_rub", 0) ?: 0,
                        isActive = billingObj?.optBoolean("is_active", false) ?: false
                    )
                } else null

                val devices = mutableListOf<TabisDevice>()
                if (devicesArr != null) {
                    for (i in 0 until devicesArr.length()) {
                        val d = devicesArr.optJSONObject(i) ?: continue
                        val isPrimary = i == 0 || d.optString("device_name").contains("Основное", ignoreCase = true)
                        val devToken = d.optString("token")
                        if (isPrimary && getUserToken().isNullOrBlank()) {
                            setUserToken(devToken)
                        }

                        devices.add(
                            TabisDevice(
                                id = d.optInt("id"),
                                deviceName = d.optString("device_name"),
                                token = devToken,
                                isActive = d.optInt("is_active") == 1,
                                tariffPlan = d.optString("tariff_plan", "base"),
                                tariffName = d.optString("tariff_name", "Базовый"),
                                monthlyCost = d.optInt("monthly_cost", 60),
                                subscriptionExpiresAt = d.optString("subscription_expires_at"),
                                daysRemaining = d.optInt("days_remaining", 0),
                                speedLimit = d.optString("speed_limit", "до 10 Мбит/с"),
                                trafficGb = d.optDouble("traffic_gb", 0.0),
                                trafficLimitGb = d.optInt("traffic_limit_gb", 100),
                                trafficPercent = d.optDouble("traffic_percent", 0.0),
                                statusText = d.optString("status_text", "Активно"),
                                isPrimary = isPrimary
                            )
                        )
                    }
                }
                return@withContext Pair(profile, devices)
            }
        } catch (e: Exception) {
            LogUtil.w(AppConfig.TAG, "fetchProfileMe failed: ${e.message}")
            return@withContext Pair(null, emptyList())
        }
    }

    suspend fun topUp(amount: Int): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(false, "Требуется авторизация")
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply { put("amount", amount) }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/top-up")
                .header("Authorization", "Bearer $session")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    val json = JSONObject(body)
                    val confirmationUrl = json.optString("confirmation_url")
                    return@withContext Pair(true, confirmationUrl)
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка пополнения") } catch (_: Exception) { "Ошибка пополнения" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun addDevice(name: String, tariffPlan: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(false, "Требуется авторизация")
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply {
                put("device_name", name)
                put("tariff_plan", tariffPlan)
            }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/devices")
                .header("Authorization", "Bearer $session")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    return@withContext Pair(true, "Устройство успешно добавлено")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка добавления устройства") } catch (_: Exception) { "Ошибка добавления устройства" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun changeDeviceTariff(deviceId: Int, tariffPlan: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(false, "Требуется авторизация")
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply { put("tariff_plan", tariffPlan) }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/devices/$deviceId/tariff")
                .header("Authorization", "Bearer $session")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    return@withContext Pair(true, "Тариф успешно изменен")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка смены тарифа") } catch (_: Exception) { "Ошибка смены тарифа" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun deleteDevice(deviceId: Int): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(false, "Требуется авторизация")
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/devices/$deviceId")
                .header("Authorization", "Bearer $session")
                .delete()
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    return@withContext Pair(true, "Устройство удалено")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка удаления устройства") } catch (_: Exception) { "Ошибка удаления устройства" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun updateNickname(nickname: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(false, "Требуется авторизация")
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply { put("nickname", nickname.trim()) }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/nickname")
                .header("Authorization", "Bearer $session")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    MmkvManager.encodeSettings(PREF_TABIS_USER_NICKNAME, nickname.trim())
                    return@withContext Pair(true, "Никнейм обновлен")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка обновления никнейма") } catch (_: Exception) { "Ошибка обновления никнейма" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun deleteAccountSendOtp(): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(false, "Требуется авторизация")
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val requestBody = "{}".toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/delete-account/send-otp")
                .header("Authorization", "Bearer $session")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    val msg = try { JSONObject(body).optString("message", "Код отправлен на почту") } catch (_: Exception) { "Код отправлен на почту" }
                    return@withContext Pair(true, msg)
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка отправки кода") } catch (_: Exception) { "Ошибка отправки кода" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun deleteAccountComplete(code: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val session = getSessionToken()
        if (session.isNullOrBlank()) return@withContext Pair(false, "Требуется авторизация")
        val baseUrl = getApiBaseUrl()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply { put("code", code.trim()) }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/profile/delete-account/complete")
                .header("Authorization", "Bearer $session")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    logout()
                    return@withContext Pair(true, "Аккаунт успешно удален")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Неверный код") } catch (_: Exception) { "Неверный код" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun registerSendOtp(email: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val baseUrl = getApiBaseUrl()
        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply {
                put("email", email.trim().lowercase())
                put("agree_terms", true)
                put("agree_privacy", true)
            }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/auth/register/send-otp")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    val msg = try { JSONObject(body).optString("message", "Код отправлен на почту") } catch (_: Exception) { "Код отправлен на почту" }
                    return@withContext Pair(true, msg)
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка регистрации") } catch (_: Exception) { "Ошибка регистрации" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun registerVerifyOtp(email: String, code: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val baseUrl = getApiBaseUrl()
        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply {
                put("email", email.trim().lowercase())
                put("code", code.trim())
            }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/auth/register/verify-otp")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    val regToken = JSONObject(body).optString("reg_token")
                    return@withContext Pair(true, regToken)
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Неверный код") } catch (_: Exception) { "Неверный код" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun registerComplete(email: String, regToken: String, nickname: String, password: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val baseUrl = getApiBaseUrl()
        try {
            val deviceId = getDeviceId()
            val client = OkHttpClient.Builder().connectTimeout(12, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply {
                put("email", email.trim().lowercase())
                put("reg_token", regToken)
                put("nickname", nickname.trim())
                put("password", password.trim())
                put("confirm_password", password.trim())
                put("ref_code", "")
                put("platform", "android")
                put("device_id", deviceId)
            }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/auth/register/complete")
                .header("Content-Type", "application/json")
                .header("X-Client-Platform", "android")
                .header("X-Device-Id", deviceId)
                .header("User-Agent", "TabisVPN-Android/2.5.1")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    val json = JSONObject(body)
                    val sessToken = json.optString("token")
                    val userObj = json.optJSONObject("user")
                    setSessionToken(sessToken)
                    setNewUser(true)

                    if (userObj != null) {
                        MmkvManager.encodeSettings(PREF_TABIS_USER_EMAIL, userObj.optString("email"))
                        MmkvManager.encodeSettings(PREF_TABIS_USER_NICKNAME, userObj.optString("nickname"))
                        MmkvManager.encodeSettings(PREF_TABIS_USER_CODE, userObj.optString("user_code"))
                        MmkvManager.encodeSettings(PREF_TABIS_USER_BALANCE, userObj.optInt("balance", 0))
                    }

                    fetchProfileMe()
                    syncRemoteServers()
                    return@withContext Pair(true, "Регистрация успешно завершена!")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Ошибка завершения регистрации") } catch (_: Exception) { "Ошибка завершения регистрации" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun login(email: String, password: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val baseUrl = getApiBaseUrl()
        val deviceId = getDeviceId()
        try {
            val client = OkHttpClient.Builder().connectTimeout(12, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply {
                put("email", email.trim().lowercase())
                put("password", password.trim())
                put("platform", "android")
                put("device_id", deviceId)
            }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/auth/login")
                .header("Content-Type", "application/json")
                .header("X-Client-Platform", "android")
                .header("X-Device-Id", deviceId)
                .header("User-Agent", "TabisVPN-Android/2.5.1")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    val json = JSONObject(body)
                    val sessToken = json.optString("token")
                    val userObj = json.optJSONObject("user")
                    setSessionToken(sessToken)
                    setNewUser(false)

                    if (userObj != null) {
                        MmkvManager.encodeSettings(PREF_TABIS_USER_EMAIL, userObj.optString("email"))
                        MmkvManager.encodeSettings(PREF_TABIS_USER_NICKNAME, userObj.optString("nickname"))
                        MmkvManager.encodeSettings(PREF_TABIS_USER_CODE, userObj.optString("user_code"))
                        MmkvManager.encodeSettings(PREF_TABIS_USER_BALANCE, userObj.optInt("balance", 0))
                    }

                    fetchProfileMe()
                    syncRemoteServers()
                    return@withContext Pair(true, "Вход выполнен успешно!")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Неверный email или пароль") } catch (_: Exception) { "Неверный email или пароль" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun resetPasswordSendOtp(email: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val baseUrl = getApiBaseUrl()
        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply { put("email", email.trim().lowercase()) }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/auth/reset-password/send-otp")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    val msg = try { JSONObject(body).optString("message", "Код для сброса пароля отправлен на email") } catch (_: Exception) { "Код для сброса пароля отправлен" }
                    return@withContext Pair(true, msg)
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Пользователь с таким email не найден") } catch (_: Exception) { "Ошибка сброса пароля" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun resetPasswordComplete(email: String, code: String, newPassword: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val baseUrl = getApiBaseUrl()
        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply {
                put("email", email.trim().lowercase())
                put("code", code.trim())
                put("new_password", newPassword.trim())
            }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val request = Request.Builder()
                .url("$baseUrl/api/v1/auth/reset-password/complete")
                .header("Content-Type", "application/json")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    return@withContext Pair(true, "Пароль успешно изменен. Теперь вы можете войти.")
                } else {
                    val detail = try { JSONObject(body).optString("detail", "Неверный или просроченный код") } catch (_: Exception) { "Ошибка сброса пароля" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun sendSupportMessage(messageText: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val cleanMsg = messageText.trim()
        if (cleanMsg.isBlank()) return@withContext Pair(false, "Сообщение не может быть пустым")

        val baseUrl = getApiBaseUrl()
        val chatSession = getSupportChatSessionToken()
        val userSession = getSessionToken()

        try {
            val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
            val jsonBody = JSONObject().apply {
                put("session_token", chatSession)
                put("message", cleanMsg)
                put("page_url", "Android App")
            }
            val requestBody = jsonBody.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

            val reqBuilder = Request.Builder()
                .url("$baseUrl/api/v1/support/messages")
                .header("Content-Type", "application/json")
                .header("User-Agent", "TabisVPN-Android/2.5.1")
                .post(requestBody)

            if (!userSession.isNullOrBlank()) {
                reqBuilder.header("Authorization", "Bearer $userSession")
            }

            client.newCall(reqBuilder.build()).execute().use { response ->
                if (response.isSuccessful) {
                    return@withContext Pair(true, "Сообщение отправлено")
                } else {
                    val body = response.body?.string().orEmpty()
                    val detail = try { JSONObject(body).optString("detail", "Ошибка отправки сообщения") } catch (_: Exception) { "Ошибка отправки сообщения" }
                    return@withContext Pair(false, detail)
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "Сетевая ошибка: ${e.message}")
        }
    }

    suspend fun fetchSupportMessages(): Pair<Boolean, List<TabisSupportMessage>> = withContext(Dispatchers.IO) {
        val baseUrl = getApiBaseUrl()
        val chatSession = getSupportChatSessionToken()

        try {
            val client = OkHttpClient.Builder().connectTimeout(8, TimeUnit.SECONDS).build()
            val request = Request.Builder()
                .url("$baseUrl/api/v1/support/history?session_token=$chatSession")
                .header("User-Agent", "TabisVPN-Android/2.5.1")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string().orEmpty()
                    val json = JSONObject(body)
                    val msgsArray = json.optJSONArray("messages")
                    val result = mutableListOf<TabisSupportMessage>()
                    if (msgsArray != null) {
                        for (i in 0 until msgsArray.length()) {
                            val item = msgsArray.getJSONObject(i)
                            result.add(
                                TabisSupportMessage(
                                    id = item.optInt("id"),
                                    senderType = item.optString("sender_type", "user"),
                                    senderName = item.optString("sender_name", ""),
                                    text = item.optString("text", ""),
                                    createdAt = item.optString("created_at", "")
                                )
                            )
                        }
                    }
                    return@withContext Pair(true, result)
                } else {
                    return@withContext Pair(false, emptyList())
                }
            }
        } catch (e: Exception) {
            return@withContext Pair(false, emptyList())
        }
    }
}

