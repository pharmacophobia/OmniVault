package com.omnivault

import java.security.SecureRandom

object PasswordGenerator {
    private const val UPPERCASE = "ABCDEFGHJKLMNPQRSTUVWXYZ" // O, I removed for ambiguity
    private const val LOWERCASE = "abcdefghijkmnopqrstuvwxyz" // l removed
    private const val DIGITS = "23456789" // 0, 1 removed
    private const val SYMBOLS = "!@#$%^&*()-_=+[]{}|;:,.<>?"

    fun generate(
        length: Int = 18,
        useUpper: Boolean = true,
        useLower: Boolean = true,
        useDigits: Boolean = true,
        useSymbols: Boolean = true
    ): String {
        val random = SecureRandom()
        val pool = StringBuilder()
        val guaranteed = mutableListOf<Char>()

        if (useUpper) {
            pool.append(UPPERCASE)
            guaranteed.add(UPPERCASE[random.nextInt(UPPERCASE.length)])
        }
        if (useLower) {
            pool.append(LOWERCASE)
            guaranteed.add(LOWERCASE[random.nextInt(LOWERCASE.length)])
        }
        if (useDigits) {
            pool.append(DIGITS)
            guaranteed.add(DIGITS[random.nextInt(DIGITS.length)])
        }
        if (useSymbols) {
            pool.append(SYMBOLS)
            guaranteed.add(SYMBOLS[random.nextInt(SYMBOLS.length)])
        }

        val poolStr = if (pool.isNotEmpty()) pool.toString() else LOWERCASE + DIGITS
        val remaining = (length - guaranteed.size).coerceAtLeast(0)

        val chars = ArrayList(guaranteed)
        for (i in 0 until remaining) {
            chars.add(poolStr[random.nextInt(poolStr.length)])
        }

        // Fisher-Yates shuffle
        for (i in chars.indices.reversed()) {
            val j = random.nextInt(i + 1)
            val tmp = chars[i]
            chars[i] = chars[j]
            chars[j] = tmp
        }

        return chars.joinToString("")
    }

    data class Strength(val score: Int, val label: String)

    fun calculateStrength(password: String): Strength {
        if (password.length < 8) return Strength(1, "Weak")
        var types = 0
        if (password.any { it.isUpperCase() }) types++
        if (password.any { it.isLowerCase() }) types++
        if (password.any { it.isDigit() }) types++
        if (password.any { !it.isLetterOrDigit() }) types++

        return when {
            password.length >= 16 && types >= 3 -> Strength(4, "Very Strong")
            password.length >= 12 && types >= 3 -> Strength(3, "Strong")
            password.length >= 8 && types >= 2 -> Strength(2, "Moderate")
            else -> Strength(1, "Weak")
        }
    }
}
