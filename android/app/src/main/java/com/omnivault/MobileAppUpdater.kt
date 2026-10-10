package com.omnivault

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Environment
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
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
            conn.setRequestProperty("User-Agent", "Android-App-Updater")
            conn.connectTimeout = 10000
            conn.readTimeout = 15000

            if (conn.responseCode in 200..299) {
                val reader = BufferedReader(InputStreamReader(conn.inputStream))
                val responseStr = reader.use { it.readText() }
                val json = JSONObject(responseStr)
                val tag = json.optString("tag_name", "").removePrefix("v").trim()
                val notes = json.optString("body", "New update available on GitHub.")
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
                    updateAvailable = isNewer,
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
            downloadUrl = "",
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

    fun downloadAndInstallApk(info: AppUpdateInfo) {
        if (info.downloadUrl.isNotEmpty()) {
            downloadAndInstallApk(info.downloadUrl)
        }
    }

    fun downloadAndInstallApk(downloadUrl: String, fileName: String = "app-update.apk") {
        try {
            val destination = File(
                context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),
                fileName
            )
            if (destination.exists()) destination.delete()

            val request = DownloadManager.Request(Uri.parse(downloadUrl))
                .setTitle("Downloading App Update")
                .setDescription("Downloading latest release from GitHub...")
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationUri(Uri.fromFile(destination))

            val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            val downloadId = manager.enqueue(request)

            val onComplete = object : BroadcastReceiver() {
                override fun onReceive(ctxt: Context, intent: Intent) {
                    val id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L)
                    if (id == downloadId) {
                        try {
                            ctxt.unregisterReceiver(this)
                        } catch (e: Exception) {}
                        installApk(destination)
                    }
                }
            }

            val filter = IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                context.registerReceiver(onComplete, filter, Context.RECEIVER_EXPORTED)
            } else {
                context.registerReceiver(onComplete, filter)
            }

        } catch (e: Exception) {
            e.printStackTrace()
            // Direct browser fallback if DownloadManager fails
            val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse(downloadUrl)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(browserIntent)
        }
    }

    private fun installApk(file: File) {
        if (!file.exists()) return

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
    }
}
