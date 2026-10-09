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
}
