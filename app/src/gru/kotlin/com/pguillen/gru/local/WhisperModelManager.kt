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

class WhisperModelManager private constructor(context: Context) {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val spec = GruWhisperModel.LARGE_V3_TURBO_Q5_0
    private val modelDir = File(appContext.filesDir, "whisper-models")
    private val modelFile = File(modelDir, spec.fileName)
    private val partialFile = File(modelDir, "${spec.fileName}.part")
    private val verifier = WhisperModelVerifier()
    private val downloader = WhisperModelDownloader(OkHttpClient())
    private val mutableState = MutableStateFlow<WhisperModelState>(WhisperModelState.Preparing)
    val state: StateFlow<WhisperModelState> = mutableState.asStateFlow()
    private var downloadJob: Job? = null

    init {
        refresh()
    }

    fun download() {
        if (downloadJob?.isActive == true || state.value is WhisperModelState.Installed) return
        downloadJob = scope.launch {
            mutableState.value = WhisperModelState.Preparing
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
                partialFile.delete()
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

    fun removeModel(onRemoved: (() -> Unit)? = null) {
        downloadJob?.cancel()
        scope.launch {
            onRemoved?.invoke()
            partialFile.delete()
            modelFile.delete()
            mutableState.value = WhisperModelState.NotInstalled
        }
    }

    fun installedModel(): File? = (state.value as? WhisperModelState.Installed)?.file

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
        val remaining = (spec.expectedBytes - partialFile.length()).coerceAtLeast(0L)
        return StatFs(modelDir.absolutePath).availableBytes >= remaining + FREE_SPACE_MARGIN_BYTES
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

    companion object {
        private const val FREE_SPACE_MARGIN_BYTES = 128L * 1024L * 1024L

        @Volatile private var instance: WhisperModelManager? = null

        fun get(context: Context): WhisperModelManager = instance ?: synchronized(this) {
            instance ?: WhisperModelManager(context).also { instance = it }
        }
    }
}
