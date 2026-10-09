package com.omnivault

import android.util.Base64
import org.json.JSONObject
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

object VaultCrypto {
    private const val SALT_LEN = 16
    private const val IV_LEN = 12
    private const val ITERATIONS = 100_000
    private const val KEY_LEN_BITS = 256
    private const val GCM_TAG_LEN_BITS = 128

    private fun deriveKey(masterPassword: String, salt: ByteArray): SecretKeySpec {
        val spec = PBEKeySpec(masterPassword.toCharArray(), salt, ITERATIONS, KEY_LEN_BITS)
        val factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
        val keyBytes = factory.generateSecret(spec).encoded
        return SecretKeySpec(keyBytes, "AES")
    }

    fun encrypt(plaintextJson: String, masterPassword: String): JSONObject {
        val random = SecureRandom()
        val salt = ByteArray(SALT_LEN)
        val iv = ByteArray(IV_LEN)
        random.nextBytes(salt)
        random.nextBytes(iv)

        val keySpec = deriveKey(masterPassword, salt)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val gcmSpec = GCMParameterSpec(GCM_TAG_LEN_BITS, iv)
        cipher.init(Cipher.ENCRYPT_MODE, keySpec, gcmSpec)

        val ciphertext = cipher.doFinal(plaintextJson.toByteArray(Charsets.UTF_8))

        val envelope = JSONObject()
        envelope.put("version", 1)
        envelope.put("kdf", "PBKDF2HMAC-SHA256")
        envelope.put("cipher", "AES-256-GCM")
        envelope.put("iterations", ITERATIONS)
        envelope.put("salt", Base64.encodeToString(salt, Base64.NO_WRAP))
        envelope.put("iv", Base64.encodeToString(iv, Base64.NO_WRAP))
        envelope.put("data", Base64.encodeToString(ciphertext, Base64.NO_WRAP))
        envelope.put("updated_at", System.currentTimeMillis() / 1000)

        return envelope
    }

    fun decrypt(envelope: JSONObject, masterPassword: String): String {
        val salt = Base64.decode(envelope.getString("salt"), Base64.DEFAULT)
        val iv = Base64.decode(envelope.getString("iv"), Base64.DEFAULT)
        val ciphertext = Base64.decode(envelope.getString("data"), Base64.DEFAULT)

        val keySpec = deriveKey(masterPassword, salt)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val gcmSpec = GCMParameterSpec(GCM_TAG_LEN_BITS, iv)
        cipher.init(Cipher.DECRYPT_MODE, keySpec, gcmSpec)

        val decryptedBytes = cipher.doFinal(ciphertext)
        return String(decryptedBytes, Charsets.UTF_8)
    }
}
