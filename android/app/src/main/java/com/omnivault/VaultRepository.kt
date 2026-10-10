package com.omnivault

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.snapshots.SnapshotStateList

data class VaultEntry(
    val id: String,
    val service: String,
    val account: String,
    val password: String,
    val notes: String = "",
    val url: String = "",
    val updatedAt: Long = System.currentTimeMillis() / 1000
)

class VaultRepository(private val context: Context) {
    private val vaultFile = File(context.filesDir, "vault.enc")
    val entries: SnapshotStateList<VaultEntry> = mutableStateListOf<VaultEntry>()
    var isUnlocked: Boolean = false
        private set
    var activeMasterPassword: String? = null
        private set

    private val prefs = context.getSharedPreferences("omnivault_prefs", Context.MODE_PRIVATE)
    private val keyStoreAlias = "omnivault_master_key"

    fun hasVault(): Boolean = vaultFile.exists() && vaultFile.length() > 0

    fun hasBiometricsEnrolledKey(): Boolean {
        return prefs.contains("bio_enc_pwd") && prefs.contains("bio_iv")
    }

    private fun getOrCreateKeyStoreKey(): javax.crypto.SecretKey {
        val keyStore = java.security.KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (!keyStore.containsAlias(keyStoreAlias)) {
            val keyGenerator = javax.crypto.KeyGenerator.getInstance(
                android.security.keystore.KeyProperties.KEY_ALGORITHM_AES,
                "AndroidKeyStore"
            )
            val builder = android.security.keystore.KeyGenParameterSpec.Builder(
                keyStoreAlias,
                android.security.keystore.KeyProperties.PURPOSE_ENCRYPT or android.security.keystore.KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(android.security.keystore.KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(android.security.keystore.KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
            keyGenerator.init(builder.build())
            return keyGenerator.generateKey()
        }
        val entry = keyStore.getEntry(keyStoreAlias, null) as java.security.KeyStore.SecretKeyEntry
        return entry.secretKey
    }

    private fun storeMasterPasswordInKeyStore(masterPassword: String) {
        try {
            val secretKey = getOrCreateKeyStoreKey()
            val cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(javax.crypto.Cipher.ENCRYPT_MODE, secretKey)
            val iv = cipher.iv
            val encryptedBytes = cipher.doFinal(masterPassword.toByteArray(Charsets.UTF_8))
            prefs.edit()
                .putString("bio_enc_pwd", android.util.Base64.encodeToString(encryptedBytes, android.util.Base64.NO_WRAP))
                .putString("bio_iv", android.util.Base64.encodeToString(iv, android.util.Base64.NO_WRAP))
                .apply()
        } catch (e: Exception) {
            // Log or ignore
        }
    }

    private fun retrieveMasterPasswordFromKeyStore(): String? {
        val encStr = prefs.getString("bio_enc_pwd", null) ?: return null
        val ivStr = prefs.getString("bio_iv", null) ?: return null
        return try {
            val secretKey = getOrCreateKeyStoreKey()
            val encBytes = android.util.Base64.decode(encStr, android.util.Base64.DEFAULT)
            val iv = android.util.Base64.decode(ivStr, android.util.Base64.DEFAULT)
            val cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding")
            val spec = javax.crypto.spec.GCMParameterSpec(128, iv)
            cipher.init(javax.crypto.Cipher.DECRYPT_MODE, secretKey, spec)
            val plainBytes = cipher.doFinal(encBytes)
            String(plainBytes, Charsets.UTF_8)
        } catch (e: Exception) {
            null
        }
    }

    fun unlockWithBiometrics(): Boolean {
        if (!hasVault()) return false
        val pw = retrieveMasterPasswordFromKeyStore() ?: return false
        return unlock(pw)
    }

    fun getEncryptedEnvelope(): JSONObject? {
        if (!hasVault()) return null
        return try {
            JSONObject(vaultFile.readText())
        } catch (e: Exception) {
            null
        }
    }

    fun saveRemoteEnvelope(envelope: JSONObject, masterPasswordIfKnown: String? = null): Boolean {
        return try {
            if (isUnlocked && activeMasterPassword != null) {
                // Verify decrypt
                val decrypted = VaultCrypto.decrypt(envelope, activeMasterPassword!!)
                parseEntries(decrypted)
            } else if (masterPasswordIfKnown != null) {
                val decrypted = VaultCrypto.decrypt(envelope, masterPasswordIfKnown)
                parseEntries(decrypted)
                activeMasterPassword = masterPasswordIfKnown
                storeMasterPasswordInKeyStore(masterPasswordIfKnown)
                isUnlocked = true
            }
            vaultFile.writeText(envelope.toString(2))
            true
        } catch (e: Exception) {
            false
        }
    }

    fun unlock(masterPassword: String): Boolean {
        if (!hasVault()) return false
        return try {
            val envelope = JSONObject(vaultFile.readText())
            val decryptedJson = VaultCrypto.decrypt(envelope, masterPassword)
            parseEntries(decryptedJson)
            activeMasterPassword = masterPassword
            storeMasterPasswordInKeyStore(masterPassword)
            isUnlocked = true
            true
        } catch (e: Exception) {
            false
        }
    }

    fun createVault(masterPassword: String): Boolean {
        if (hasVault()) return false
        activeMasterPassword = masterPassword
        storeMasterPasswordInKeyStore(masterPassword)
        entries.clear()
        isUnlocked = true
        return save()
    }

    fun lock() {
        activeMasterPassword = null
        entries.clear()
        isUnlocked = false
    }

    fun addOrUpdateEntry(entry: VaultEntry): Boolean {
        val idx = entries.indexOfFirst { it.id == entry.id }
        if (idx >= 0) {
            entries[idx] = entry
        } else {
            entries.add(entry)
        }
        return save()
    }

    fun deleteEntry(entryId: String): Boolean {
        val idx = entries.indexOfFirst { it.id == entryId }
        if (idx >= 0) {
            entries.removeAt(idx)
            return save()
        }
        return false
    }

    fun deleteEntriesWithoutPassword(): Int {
        val before = entries.size
        entries.removeAll { it.password.trim().isEmpty() }
        val removed = before - entries.size
        if (removed > 0) {
            save()
        }
        return removed
    }

    fun deleteEntriesWithoutAccount(): Int {
        val before = entries.size
        entries.removeAll { it.account.trim().isEmpty() }
        val removed = before - entries.size
        if (removed > 0) {
            save()
        }
        return removed
    }

    private fun save(): Boolean {
        if (!isUnlocked || activeMasterPassword == null) return false
        return try {
            val array = JSONArray()
            entries.forEach { entry ->
                val obj = JSONObject()
                obj.put("id", entry.id)
                obj.put("service", entry.service)
                obj.put("account", entry.account)
                obj.put("password", entry.password)
                obj.put("notes", entry.notes)
                obj.put("url", entry.url)
                obj.put("updated_at", entry.updatedAt)
                array.put(obj)
            }
            val envelope = VaultCrypto.encrypt(array.toString(), activeMasterPassword!!)
            vaultFile.writeText(envelope.toString(2))
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun parseEntries(jsonString: String) {
        val list = mutableListOf<VaultEntry>()
        val array = JSONArray(jsonString)
        for (i in 0 until array.length()) {
            val obj = array.getJSONObject(i)
            list.add(
                VaultEntry(
                    id = obj.optString("id", "entry_${System.currentTimeMillis()}_$i"),
                    service = obj.optString("service", "Untitled"),
                    account = obj.optString("account", ""),
                    password = obj.optString("password", ""),
                    notes = obj.optString("notes", ""),
                    url = obj.optString("url", ""),
                    updatedAt = obj.optLong("updated_at", System.currentTimeMillis() / 1000)
                )
            )
        }
        entries.clear()
        entries.addAll(list)
    }

    fun scanPhoneStorageForCredentials(): Int {
        if (!isUnlocked || activeMasterPassword == null) return 0
        var totalImported = 0
        try {
            val searchDirs = listOfNotNull(
                android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS),
                android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOCUMENTS),
                File("/sdcard/Download"),
                File("/sdcard/Documents"),
                context.getExternalFilesDir(null)
            )

            val candidateFiles = mutableListOf<File>()
            for (dir in searchDirs) {
                if (dir.exists() && dir.canRead()) {
                    dir.walkTopDown().maxDepth(2).forEach { file ->
                        if (file.isFile && (
                            file.name.contains("pass", ignoreCase = true) ||
                            file.name.contains("login", ignoreCase = true) ||
                            file.name.contains("export", ignoreCase = true) ||
                            file.name.endsWith(".csv", ignoreCase = true) ||
                            file.name.endsWith(".json", ignoreCase = true)
                        )) {
                            candidateFiles.add(file)
                        }
                    }
                }
            }

            for (file in candidateFiles.distinctBy { it.absolutePath }) {
                try {
                    val content = file.readText()
                    val parsed = parseImportString(content)
                    for (entry in parsed) {
                        val exists = entries.any { it.service.equals(entry.service, true) && it.account.equals(entry.account, true) }
                        if (!exists && entry.password.isNotBlank()) {
                            entries.add(entry)
                            totalImported++
                        }
                    }
                } catch (e: Exception) {}
            }
            if (totalImported > 0) save()
        } catch (e: Exception) {}
        return totalImported
    }

    fun importFromExportFile(uri: android.net.Uri): Int {
        if (!isUnlocked || activeMasterPassword == null) return 0
        return try {
            val inputStream = context.contentResolver.openInputStream(uri) ?: return 0
            val content = inputStream.bufferedReader().use { it.readText() }
            val imported = parseImportString(content)
            var count = 0
            for (entry in imported) {
                val exists = entries.any { it.service.equals(entry.service, true) && it.account.equals(entry.account, true) }
                if (!exists && entry.password.isNotBlank()) {
                    entries.add(entry)
                    count++
                }
            }
            if (count > 0) save()
            count
        } catch (e: Exception) {
            0
        }
    }

    fun parseImportString(text: String): List<VaultEntry> {
        val result = mutableListOf<VaultEntry>()
        val trimmed = text.trim()

        // 1. Try JSON
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
            try {
                if (trimmed.startsWith("[")) {
                    val array = JSONArray(trimmed)
                    for (i in 0 until array.length()) {
                        val obj = array.getJSONObject(i)
                        val pass = obj.optString("password", "")
                        if (pass.isNotBlank()) {
                            result.add(
                                VaultEntry(
                                    id = "import_${System.currentTimeMillis()}_$i",
                                    service = obj.optString("service", obj.optString("name", "Imported")),
                                    account = obj.optString("account", obj.optString("username", "")),
                                    password = pass,
                                    url = obj.optString("url", ""),
                                    notes = obj.optString("notes", "")
                                )
                            )
                        }
                    }
                    return result
                } else {
                    val root = JSONObject(trimmed)
                    if (root.has("items")) {
                        val items = root.getJSONArray("items")
                        for (i in 0 until items.length()) {
                            val it = items.getJSONObject(i)
                            val login = it.optJSONObject("login")
                            val user = login?.optString("username", "") ?: ""
                            val pass = login?.optString("password", "") ?: ""
                            if (pass.isNotBlank()) {
                                result.add(
                                    VaultEntry(
                                        id = "import_${System.currentTimeMillis()}_$i",
                                        service = it.optString("name", "Imported"),
                                        account = user,
                                        password = pass,
                                        notes = it.optString("notes", "")
                                    )
                                )
                            }
                        }
                        return result
                    }
                }
            } catch (e: Exception) {}
        }

        // 2. Try CSV (Chrome, Firefox, Google Passwords)
        val lines = trimmed.lines().filter { it.isNotBlank() }
        if (lines.isNotEmpty() && lines[0].contains(",")) {
            val headers = lines[0].split(",").map { it.trim().lowercase().replace("\"", "") }
            val nameIdx = headers.indexOfFirst { it.contains("name") || it.contains("title") || it.contains("url") }
            val userIdx = headers.indexOfFirst { it.contains("username") || it.contains("user") || it.contains("account") || it.contains("login") }
            val passIdx = headers.indexOfFirst { it.contains("password") || it.contains("secret") }
            val noteIdx = headers.indexOfFirst { it.contains("note") }

            for (i in 1 until lines.size) {
                val cols = lines[i].split(",").map { it.trim().replace("\"", "") }
                val service = if (nameIdx in cols.indices) cols[nameIdx] else "Imported"
                val account = if (userIdx in cols.indices) cols[userIdx] else ""
                val password = if (passIdx in cols.indices) cols[passIdx] else ""
                val notes = if (noteIdx in cols.indices) cols[noteIdx] else ""
                if (password.isNotBlank()) {
                    result.add(
                        VaultEntry(
                            id = "import_${System.currentTimeMillis()}_$i",
                            service = service.ifBlank { "Imported Account" },
                            account = account,
                            password = password,
                            notes = notes
                        )
                    )
                }
            }
            if (result.isNotEmpty()) return result
        }

        // 3. Fallback Key:Value parser
        var currentService = "Imported"
        var currentAccount = ""
        var currentPassword = ""
        for ((idx, line) in lines.withIndex()) {
            val lower = line.lowercase()
            when {
                lower.startsWith("service:") || lower.startsWith("website:") || lower.startsWith("title:") ->
                    currentService = line.substringAfter(":").trim()
                lower.startsWith("user:") || lower.startsWith("username:") || lower.startsWith("account:") || lower.startsWith("email:") ->
                    currentAccount = line.substringAfter(":").trim()
                lower.startsWith("password:") || lower.startsWith("pass:") ->
                    currentPassword = line.substringAfter(":").trim()
            }
            if (currentPassword.isNotBlank()) {
                result.add(VaultEntry("import_${System.currentTimeMillis()}_$idx", currentService, currentAccount, currentPassword))
                currentService = "Imported"
                currentAccount = ""
                currentPassword = ""
            }
        }

        return result
    }
}
