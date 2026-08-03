/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import android.content.Context
import android.os.StatFs
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient

fun interface WhisperModelProvider {
    fun installedModel(): File?
}

class WhisperModelManager private constructor(context: Context) : WhisperModelProvider {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val spec = GruWhisperModel.BASE_Q5_1
    private val modelDir = File(appContext.filesDir, "whisper-models")
    private val modelFile = File(modelDir, spec.fileName)
    private val partialFile = File(modelDir, "${spec.fileName}.part")
    private val verifier = WhisperModelVerifier()
    private val downloader = WhisperModelDownloader(OkHttpClient())
    private val mutableState = MutableStateFlow<WhisperModelState>(WhisperModelState.Preparing)
    val state: StateFlow<WhisperModelState> = mutableState.asStateFlow()
    private var downloadJob: Job? = null

    init {
        removeObsoleteModels()
        refresh()
    }

    fun download() {
        if (downloadJob?.isActive == true || state.value is WhisperModelState.Installed) return
        downloadJob = scope.launch {
            mutableState.value = WhisperModelState.Preparing
            discardInvalidPartial()
            if (!hasSpaceForDownload()) {
                mutableState.value = WhisperModelState.Error(WhisperModelError.INSUFFICIENT_SPACE)
                return@launch
            }
            try {
                downloader.download(spec, partialFile) { downloaded ->
                    mutableState.value = WhisperModelState.Downloading(downloaded, spec.expectedBytes)
                }
                mutableState.value = WhisperModelState.Verifying
                val error = verifier.validate(partialFile, spec)
                if (error != null) {
                    partialFile.delete()
                    mutableState.value = WhisperModelState.Error(error)
                    return@launch
                }
                promoteVerifiedModel()
                mutableState.value = WhisperModelState.Installed(modelFile, modelFile.length())
            } catch (_: CancellationException) {
                partialFile.delete()
                mutableState.value = WhisperModelState.NotInstalled
            } catch (_: IOException) {
                mutableState.value = WhisperModelState.Error(WhisperModelError.NETWORK)
            } catch (_: Throwable) {
                partialFile.delete()
                mutableState.value = WhisperModelState.Error(WhisperModelError.STORAGE)
            }
        }
    }

    fun cancelDownload() {
        downloadJob?.cancel()
    }

    fun removeModel(onRemoved: (suspend () -> Unit)? = null) {
        downloadJob?.cancel()
        scope.launch {
            onRemoved?.invoke()
            partialFile.delete()
            modelFile.delete()
            mutableState.value = WhisperModelState.NotInstalled
        }
    }

    override fun installedModel(): File? = (state.value as? WhisperModelState.Installed)?.file

    fun refresh() {
        scope.launch {
            mutableState.value = WhisperModelState.Preparing
            if (!modelFile.exists()) {
                mutableState.value = WhisperModelState.NotInstalled
                return@launch
            }
            mutableState.value = WhisperModelState.Verifying
            val error = verifier.validate(modelFile, spec)
            mutableState.value = if (error == null) {
                WhisperModelState.Installed(modelFile, modelFile.length())
            } else {
                modelFile.delete()
                WhisperModelState.Error(error)
            }
        }
    }

    private fun hasSpaceForDownload(): Boolean {
        modelDir.mkdirs()
        val resumableBytes = partialFile.length().takeIf { it in 1 until spec.expectedBytes } ?: 0L
        val remaining = spec.expectedBytes - resumableBytes
        return StatFs(modelDir.absolutePath).availableBytes >= remaining + FREE_SPACE_MARGIN_BYTES
    }

    private fun discardInvalidPartial() {
        if (partialFile.exists() && partialFile.length() !in 1 until spec.expectedBytes) {
            partialFile.delete()
        }
    }

    private fun promoteVerifiedModel() {
        modelDir.mkdirs()
        Files.move(
            partialFile.toPath(),
            modelFile.toPath(),
            StandardCopyOption.REPLACE_EXISTING,
            StandardCopyOption.ATOMIC_MOVE,
        )
    }

    private fun removeObsoleteModels() {
        OBSOLETE_MODEL_FILES.forEach { fileName ->
            File(modelDir, fileName).delete()
            File(modelDir, "$fileName.part").delete()
        }
    }

    companion object {
        private const val FREE_SPACE_MARGIN_BYTES = 128L * 1024L * 1024L
        private val OBSOLETE_MODEL_FILES = listOf(
            "ggml-large-v3-turbo-q5_0.bin",
            "ggml-small-q5_1.bin",
        )

        @Volatile private var instance: WhisperModelManager? = null

        fun get(context: Context): WhisperModelManager = instance ?: synchronized(this) {
            instance ?: WhisperModelManager(context).also { instance = it }
        }
    }
}
