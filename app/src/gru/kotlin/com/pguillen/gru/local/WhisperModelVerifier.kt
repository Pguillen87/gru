/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

class WhisperModelVerifier {
    fun validate(file: File, spec: WhisperModelSpec): WhisperModelError? {
        if (!file.isFile || file.length() != spec.expectedBytes) return WhisperModelError.INVALID_SIZE
        return if (sha256(file).equals(spec.sha256, ignoreCase = true)) null else WhisperModelError.INVALID_CHECKSUM
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(BUFFER_BYTES)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private companion object {
        const val BUFFER_BYTES = 1024 * 1024
    }
}
