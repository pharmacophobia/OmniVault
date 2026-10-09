package com.omnivault

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

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
    var entries = mutableListOf<VaultEntry>()
        private set
    var isUnlocked: Boolean = false
        private set
    var activeMasterPassword: String? = null
        private set

    fun hasVault(): Boolean = vaultFile.exists() && vaultFile.length() > 0

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
            isUnlocked = true
            true
        } catch (e: Exception) {
            false
        }
    }

    fun createVault(masterPassword: String): Boolean {
        if (hasVault()) return false
        activeMasterPassword = masterPassword
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
        val removed = entries.removeAll { it.id == entryId }
        return if (removed) save() else false
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
        entries = list
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
                if (!exists && (entry.account.isNotEmpty() || entry.password.isNotEmpty())) {
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

    private fun parseImportString(text: String): List<VaultEntry> {
        val result = mutableListOf<VaultEntry>()
        val trimmed = text.trim()

        // 1. Try JSON
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
            try {
                if (trimmed.startsWith("[")) {
                    val array = JSONArray(trimmed)
                    for (i in 0 until array.length()) {
                        val obj = array.getJSONObject(i)
                        result.add(
                            VaultEntry(
                                id = "import_${System.currentTimeMillis()}_$i",
                                service = obj.optString("service", obj.optString("name", "Imported")),
                                account = obj.optString("account", obj.optString("username", "")),
                                password = obj.optString("password", ""),
                                url = obj.optString("url", ""),
                                notes = obj.optString("notes", "")
                            )
                        )
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
                            if (user.isNotEmpty() || pass.isNotEmpty()) {
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
                if (account.isNotEmpty() || password.isNotEmpty()) {
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
            if (currentAccount.isNotEmpty() && currentPassword.isNotEmpty()) {
                result.add(VaultEntry("import_${System.currentTimeMillis()}_$idx", currentService, currentAccount, currentPassword))
                currentService = "Imported"
                currentAccount = ""
                currentPassword = ""
            }
        }

        return result
    }
}
