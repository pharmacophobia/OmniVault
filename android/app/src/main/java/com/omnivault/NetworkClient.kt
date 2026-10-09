package com.omnivault

import android.content.Context
import android.net.Uri
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class NetworkClient(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS) // Ollama vision extraction may take ~45s on CPU
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    suspend fun checkServerStatus(serverHost: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        try {
            val url = "http://$serverHost:8765/api/status"
            val request = Request.Builder().url(url).get().build()
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    Pair(true, "Desktop Vault Server Connected")
                } else {
                    Pair(false, "Server returned HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            Pair(false, "Cannot connect to $serverHost:8765: ${e.message}")
        }
    }

    suspend fun pullVault(serverHost: String): JSONObject? = withContext(Dispatchers.IO) {
        try {
            val url = "http://$serverHost:8765/api/vault/encrypted"
            val request = Request.Builder().url(url).get().build()
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful && response.body != null) {
                    JSONObject(response.body!!.string())
                } else null
            }
        } catch (e: Exception) {
            null
        }
    }

    suspend fun pushVault(serverHost: String, envelope: JSONObject): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        try {
            val url = "http://$serverHost:8765/api/vault/sync"
            val body = envelope.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder().url(url).post(body).build()
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    Pair(true, "Synced to Desktop successfully!")
                } else {
                    Pair(false, "Sync failed: HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            Pair(false, "Sync error: ${e.message}")
        }
    }

    suspend fun extractFromScreenshot(serverHost: String, imageUri: Uri): JSONObject? = withContext(Dispatchers.IO) {
        try {
            val inputStream = context.contentResolver.openInputStream(imageUri) ?: return@withContext null
            val bytes = inputStream.readBytes()
            inputStream.close()
            val base64Img = Base64.encodeToString(bytes, Base64.NO_WRAP)

            val payload = JSONObject().apply {
                put("image_base64", base64Img)
            }

            val url = "http://$serverHost:8765/api/vision/extract"
            val body = payload.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder().url(url).post(body).build()

            client.newCall(request).execute().use { response ->
                if (response.isSuccessful && response.body != null) {
                    val respJson = JSONObject(response.body!!.string())
                    respJson.optJSONObject("data")
                } else null
            }
        } catch (e: Exception) {
            null
        }
    }
}
