package com.omnivault

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.FileOutputStream
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

data class AppUpdateInfo(
    val updateAvailable: Boolean,
    val currentVersion: String,
    val latestVersion: String,
    val downloadUrl: String,
    val releaseNotes: String
)

class MobileAppUpdater(private val context: Context, private val githubRepo: String) {

    init {
        cleanupOldApk()
    }

    fun cleanupOldApk() {
        try {
            val updateFile = File(context.cacheDir, "omnivault_update.apk")
            if (updateFile.exists()) {
                updateFile.delete()
            }
        } catch (e: Exception) {
            // Ignore cleanup errors
        }
    }

    suspend fun checkForUpdates(currentVersionName: String = ""): AppUpdateInfo = withContext(Dispatchers.IO) {
        val curVer = if (currentVersionName.isNotEmpty()) {
            currentVersionName
        } else {
            try {
                val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
                pInfo.versionName ?: "1.0.0"
            } catch (e: Exception) {
                "1.0.0"
            }
        }
        val curClean = curVer.removePrefix("v").trim()
        try {
            val url = URL("https://api.github.com/repos/$githubRepo/releases/latest")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "OmniVault-Android-Updater")
            conn.connectTimeout = 10000
            conn.readTimeout = 15000

            if (conn.responseCode in 200..299) {
                val reader = BufferedReader(InputStreamReader(conn.inputStream))
                val responseStr = reader.use { it.readText() }
                val json = JSONObject(responseStr)
                val tag = json.optString("tag_name", "").removePrefix("v").trim()
                val notes = json.optString("body", "New release available on GitHub.")
                var apkUrl = ""

                val assets = json.optJSONArray("assets")
                if (assets != null) {
                    for (i in 0 until assets.length()) {
                        val asset = assets.getJSONObject(i)
                        val name = asset.optString("name", "")
                        if (name.endsWith(".apk", ignoreCase = true)) {
                            apkUrl = asset.optString("browser_download_url", "")
                            break
                        }
                    }
                }

                // Fallback to repo root raw apk link
                if (apkUrl.isEmpty()) {
                    val repoName = githubRepo.substringAfterLast("/")
                    apkUrl = "https://github.com/$githubRepo/raw/main/$repoName.apk"
                }

                val isNewer = isVersionNewer(tag, curClean)
                return@withContext AppUpdateInfo(
                    updateAvailable = isNewer || (tag.isNotEmpty() && tag != curClean),
                    currentVersion = curClean,
                    latestVersion = if (tag.isNotEmpty()) tag else curClean,
                    downloadUrl = apkUrl,
                    releaseNotes = notes
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        AppUpdateInfo(
            updateAvailable = false,
            currentVersion = curClean,
            latestVersion = curClean,
            downloadUrl = "https://github.com/$githubRepo/raw/main/OmniVault.apk",
            releaseNotes = ""
        )
    }

    private fun isVersionNewer(latest: String, current: String): Boolean {
        if (latest.isEmpty()) return false
        val lParts = latest.split(".").mapNotNull { it.toIntOrNull() }
        val cParts = current.split(".").mapNotNull { it.toIntOrNull() }
        for (i in 0 until maxOf(lParts.size, cParts.size)) {
            val l = lParts.getOrElse(i) { 0 }
            val c = cParts.getOrElse(i) { 0 }
            if (l > c) return true
            if (l < c) return false
        }
        return false
    }

    suspend fun downloadApkWithProgress(
        downloadUrl: String,
        onProgress: (Int) -> Unit
    ): File? = withContext(Dispatchers.IO) {
        var currentUrl = downloadUrl
        val destination = File(context.cacheDir, "omnivault_update.apk")
        if (destination.exists()) destination.delete()

        try {
            var redirects = 0
            while (redirects < 5) {
                val url = URL(currentUrl)
                val conn = url.openConnection() as HttpURLConnection
                conn.instanceFollowRedirects = true
                conn.setRequestProperty("User-Agent", "OmniVault-Android-Updater")
                conn.connectTimeout = 15000
                conn.readTimeout = 30000
                conn.connect()

                val code = conn.responseCode
                if (code in 300..399) {
                    val newLoc = conn.getHeaderField("Location")
                    if (newLoc != null) {
                        currentUrl = newLoc
                        redirects++
                        continue
                    }
                }

                if (code in 200..299) {
                    val fileLength = conn.contentLength
                    conn.inputStream.use { input ->
                        FileOutputStream(destination).use { output ->
                            val buffer = ByteArray(8192)
                            var total: Long = 0
                            var count: Int
                            while (input.read(buffer).also { count = it } != -1) {
                                total += count
                                output.write(buffer, 0, count)
                                if (fileLength > 0) {
                                    val progress = ((total * 100) / fileLength).toInt()
                                    withContext(Dispatchers.Main) {
                                        onProgress(progress)
                                    }
                                }
                            }
                            output.flush()
                        }
                    }
                    withContext(Dispatchers.Main) {
                        onProgress(100)
                    }
                    return@withContext destination
                } else {
                    return@withContext null
                }
            }
            null
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    fun installApk(file: File) {
        if (!file.exists()) return

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                if (!context.packageManager.canRequestPackageInstalls()) {
                    val permIntent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                        data = Uri.parse("package:${context.packageName}")
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    context.startActivity(permIntent)
                    Toast.makeText(context, "Please allow OmniVault to install updates, then return to complete install.", Toast.LENGTH_LONG).show()
                }
            }

            val uri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.provider",
                file
            )

            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/vnd.android.package-archive")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
            }

            context.startActivity(intent)
        } catch (e: Exception) {
            e.printStackTrace()
            openInBrowserFallback("https://github.com/$githubRepo/raw/main/OmniVault.apk")
        }
    }

    fun openInBrowserFallback(url: String) {
        try {
            val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(browserIntent)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}
