package com.v2ray.ang.ui.tabis

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.content.FileProvider
import com.v2ray.ang.AppConfig
import com.v2ray.ang.BuildConfig
import com.v2ray.ang.util.LogUtil
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.Locale
import java.util.concurrent.TimeUnit

data class TabisAppUpdateInfo(
    val hasUpdate: Boolean,
    val latestVersionCode: Int,
    val latestVersionName: String,
    val changelog: String,
    val downloadUrl: String,
    val sha256: String = ""
)

object TabisUpdateManager {

    private const val UPDATE_CHECK_URL = "https://tabisvpn.site/api/v1/app/version"

    suspend fun checkForAppUpdate(): TabisAppUpdateInfo? = withContext(Dispatchers.IO) {
        try {
            val client = OkHttpClient.Builder()
                .connectTimeout(5, TimeUnit.SECONDS)
                .readTimeout(8, TimeUnit.SECONDS)
                .build()

            val request = Request.Builder()
                .url(UPDATE_CHECK_URL)
                .header("User-Agent", "TabisVPN-Android/${BuildConfig.VERSION_NAME}")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext null
                val body = response.body.string()
                val json = JSONObject(body)

                val remoteCode = json.optInt("version_code", 0)
                val remoteName = json.optString("version_name", "")
                val changelog = json.optString("changelog", "")
                val downloadUrl = json.optString("download_url", "https://tabisvpn.site/downloads/TabisVPN.apk")
                val sha256 = json.optString("sha256", "").trim()

                val currentCode = BuildConfig.VERSION_CODE
                val currentNorm = currentCode % 1000000
                val remoteNorm = remoteCode % 1000000

                val hasUpdate = (remoteCode > currentCode) ||
                        (remoteNorm > currentNorm) ||
                        (remoteName.isNotBlank() && remoteName != BuildConfig.VERSION_NAME && remoteNorm >= currentNorm)

                LogUtil.i(AppConfig.TAG, "Update check: localCode=$currentCode, remoteCode=$remoteCode, hasUpdate=$hasUpdate")

                return@withContext TabisAppUpdateInfo(
                    hasUpdate = hasUpdate,
                    latestVersionCode = remoteCode,
                    latestVersionName = remoteName,
                    changelog = changelog,
                    downloadUrl = downloadUrl,
                    sha256 = sha256
                )
            }
        } catch (e: Exception) {
            LogUtil.w(AppConfig.TAG, "Update check skipped/failed: ${e.message}")
            return@withContext null
        }
    }

    suspend fun downloadAndInstallApk(
        context: Context,
        downloadUrl: String,
        onProgress: (Int) -> Unit
    ): Boolean = downloadAndInstallApk(context, downloadUrl, null, onProgress)

    suspend fun downloadAndInstallApk(
        context: Context,
        downloadUrl: String,
        expectedSha256: String? = null,
        onProgress: (Int) -> Unit
    ): Boolean = withContext(Dispatchers.IO) {
        val apkFile = File(context.cacheDir, "update.apk")
        try {
            val client = OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .build()

            val request = Request.Builder()
                .url(downloadUrl)
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    if (apkFile.exists()) {
                        apkFile.delete()
                    }
                    return@withContext false
                }
                val body = response.body
                val contentLength = body.contentLength()

                if (apkFile.exists()) {
                    apkFile.delete()
                }

                body.byteStream().use { input ->
                    FileOutputStream(apkFile).use { output ->
                        val buffer = ByteArray(8192)
                        var bytesRead: Int
                        var totalBytes: Long = 0

                        while (input.read(buffer).also { bytesRead = it } != -1) {
                            output.write(buffer, 0, bytesRead)
                            totalBytes += bytesRead
                            if (contentLength > 0) {
                                val progress = ((totalBytes * 100) / contentLength).toInt()
                                withContext(Dispatchers.Main) {
                                    onProgress(progress)
                                }
                            }
                        }
                        output.flush()
                    }
                }

                val isValid = validateApk(context, apkFile, expectedSha256)
                if (!isValid) {
                    if (apkFile.exists()) {
                        apkFile.delete()
                    }
                    return@withContext false
                }

                withContext(Dispatchers.Main) {
                    installApk(context, apkFile)
                }
                return@withContext true
            }
        } catch (e: Exception) {
            LogUtil.e(AppConfig.TAG, "Failed to download update APK: ${e.message}", e)
            if (apkFile.exists()) {
                apkFile.delete()
            }
            return@withContext false
        }
    }

    fun installApk(context: Context, apkFile: File, expectedSha256: String? = null): Boolean {
        try {
            if (!apkFile.exists() || !apkFile.isFile) {
                LogUtil.w(AppConfig.TAG, "Cannot launch installer: file does not exist or is invalid")
                return false
            }

            val authority = "${context.packageName}.cache"
            val apkUri: Uri = FileProvider.getUriForFile(context, authority, apkFile)

            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(apkUri, "application/vnd.android.package-archive")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
            }
            context.startActivity(intent)
            return true
        } catch (e: Exception) {
            LogUtil.e(AppConfig.TAG, "Failed to launch package installer: ${e.message}", e)
            return false
        }
    }

    internal fun calculateSha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { fis ->
            val buffer = ByteArray(8192)
            var bytesRead: Int
            while (fis.read(buffer).also { bytesRead = it } != -1) {
                digest.update(buffer, 0, bytesRead)
            }
        }
        val hashBytes = digest.digest()
        val sb = java.lang.StringBuilder(hashBytes.size * 2)
        for (b in hashBytes) {
            sb.append(String.format(Locale.US, "%02x", b))
        }
        return sb.toString()
    }

    fun validateApk(context: Context, apkFile: File, expectedSha256: String? = null): Boolean {
        if (!apkFile.exists() || !apkFile.isFile) {
            LogUtil.w(AppConfig.TAG, "APK validation failed: file does not exist or is not a regular file")
            return false
        }

        try {
            // 1. Streaming SHA-256 digest computation and validation
            val computedHash = calculateSha256(apkFile)
            LogUtil.i(AppConfig.TAG, "Downloaded APK SHA-256 digest: $computedHash")
            if (!expectedSha256.isNullOrBlank()) {
                if (!computedHash.equals(expectedSha256.trim(), ignoreCase = true)) {
                    LogUtil.w(AppConfig.TAG, "APK validation failed: SHA-256 mismatch (expected: $expectedSha256, actual: $computedHash)")
                    if (apkFile.exists()) {
                        apkFile.delete()
                    }
                    return false
                }
            }

            val pm = context.packageManager

            // 2. Archive parsing and package name verification
            val apkPackageInfo = getPackageArchiveInfoCompat(pm, apkFile.absolutePath)
            if (apkPackageInfo == null) {
                LogUtil.w(AppConfig.TAG, "APK validation failed: unable to parse package archive info")
                if (apkFile.exists()) {
                    apkFile.delete()
                }
                return false
            }

            if (apkPackageInfo.packageName != context.packageName) {
                LogUtil.w(
                    AppConfig.TAG,
                    "APK validation failed: package name mismatch (expected: ${context.packageName}, actual: ${apkPackageInfo.packageName})"
                )
                if (apkFile.exists()) {
                    apkFile.delete()
                }
                return false
            }

            // 3. Signing certificate verification against running application
            val currentPackageInfo = getCurrentPackageInfoCompat(pm, context.packageName)
            if (currentPackageInfo == null) {
                LogUtil.w(AppConfig.TAG, "APK validation failed: unable to retrieve current app package info")
                if (apkFile.exists()) {
                    apkFile.delete()
                }
                return false
            }

            val apkSignatures = getSignaturesCompat(apkPackageInfo)
            val currentSignatures = getSignaturesCompat(currentPackageInfo)

            if (apkSignatures.isEmpty() || currentSignatures.isEmpty()) {
                LogUtil.w(AppConfig.TAG, "APK validation failed: signing certificates could not be extracted")
                if (apkFile.exists()) {
                    apkFile.delete()
                }
                return false
            }

            if (!areSignaturesMatching(currentSignatures, apkSignatures)) {
                LogUtil.w(AppConfig.TAG, "APK validation failed: signing certificate does not match running application")
                if (apkFile.exists()) {
                    apkFile.delete()
                }
                return false
            }

            LogUtil.i(AppConfig.TAG, "APK validation succeeded for package: ${apkPackageInfo.packageName}")
            return true
        } catch (e: Exception) {
            LogUtil.w(AppConfig.TAG, "APK validation error: ${e.message}", e)
            if (apkFile.exists()) {
                apkFile.delete()
            }
            return false
        }
    }

    private fun getPackageArchiveInfoCompat(pm: PackageManager, archiveFilePath: String): PackageInfo? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            pm.getPackageArchiveInfo(
                archiveFilePath,
                PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong())
            )
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            @Suppress("DEPRECATION")
            pm.getPackageArchiveInfo(archiveFilePath, PackageManager.GET_SIGNING_CERTIFICATES)
        } else {
            @Suppress("DEPRECATION")
            pm.getPackageArchiveInfo(archiveFilePath, PackageManager.GET_SIGNATURES)
        }
    }

    private fun getCurrentPackageInfoCompat(pm: PackageManager, packageName: String): PackageInfo? {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getPackageInfo(
                    packageName,
                    PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong())
                )
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES)
            } else {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(packageName, PackageManager.GET_SIGNATURES)
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun getSignaturesCompat(packageInfo: PackageInfo): List<ByteArray> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val signingInfo = packageInfo.signingInfo ?: return emptyList()
            val signatures = if (signingInfo.hasMultipleSigners()) {
                signingInfo.apkContentsSigners
            } else {
                signingInfo.signingCertificateHistory
            } ?: signingInfo.apkContentsSigners
            signatures?.map { it.toByteArray() } ?: emptyList()
        } else {
            @Suppress("DEPRECATION")
            packageInfo.signatures?.map { it.toByteArray() } ?: emptyList()
        }
    }

    internal fun areSignaturesMatching(currentSignatures: List<ByteArray>, apkSignatures: List<ByteArray>): Boolean {
        if (currentSignatures.isEmpty() || apkSignatures.isEmpty()) {
            return false
        }
        if (currentSignatures.size != apkSignatures.size) {
            return false
        }
        val apkMatchesCurrent = apkSignatures.all { apkSig ->
            currentSignatures.any { curSig -> curSig.contentEquals(apkSig) }
        }
        val currentMatchesApk = currentSignatures.all { curSig ->
            apkSignatures.any { apkSig -> apkSig.contentEquals(curSig) }
        }
        if (!apkMatchesCurrent || !currentMatchesApk) {
            return false
        }

        val matched = BooleanArray(currentSignatures.size)
        for (apkSig in apkSignatures) {
            val matchIdx = currentSignatures.indices.firstOrNull { i ->
                !matched[i] && currentSignatures[i].contentEquals(apkSig)
            } ?: return false
            matched[matchIdx] = true
        }
        return true
    }
}
