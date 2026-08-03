package com.pguillen.gru.mascot

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import java.io.ByteArrayOutputStream
import kotlin.math.roundToInt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

internal data class PreparedMascotPhoto(
    val bytes: ByteArray,
    val contentType: String,
    val width: Int,
    val height: Int,
)

internal class MascotPhotoPreparationException(cause: Throwable) : Exception("Selected photo cannot be prepared.", cause)

internal suspend fun Context.prepareMascotPhoto(uri: Uri): PreparedMascotPhoto = withContext(Dispatchers.IO) {
    try {
        val decoded = decodeMascotBitmap(uri)
        try {
            require(minOf(decoded.width, decoded.height) >= MIN_SIDE) { "Selected photo is too small." }
            val output = ByteArrayOutputStream()
            require(decoded.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)) { "Selected photo cannot be encoded." }
            val bytes = output.toByteArray()
            require(bytes.size in 1..MAX_BYTES) { "Selected photo is too large." }
            PreparedMascotPhoto(bytes, JPEG_CONTENT_TYPE, decoded.width, decoded.height)
        } finally {
            decoded.recycle()
        }
    } catch (error: Exception) {
        throw MascotPhotoPreparationException(error)
    }
}

private fun Context.decodeMascotBitmap(uri: Uri): Bitmap {
    val bitmap = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
        val source = ImageDecoder.createSource(contentResolver, uri)
        ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            val target = scaledSize(info.size.width, info.size.height)
            if (target.first != info.size.width || target.second != info.size.height) {
                decoder.setTargetSize(target.first, target.second)
            }
        }
    } else {
        decodeLegacy(uri)
    }
    return scaleDown(bitmap)
}

private fun Context.decodeLegacy(uri: Uri): Bitmap {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
    require(bounds.outWidth > 0 && bounds.outHeight > 0) { "Selected photo cannot be decoded." }
    var sampleSize = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / sampleSize > MAX_SIDE * 2) sampleSize *= 2
    val options = BitmapFactory.Options().apply { inSampleSize = sampleSize }
    return contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
        ?: throw IllegalArgumentException("Selected photo cannot be decoded.")
}

private fun scaleDown(bitmap: Bitmap): Bitmap {
    val target = scaledSize(bitmap.width, bitmap.height)
    if (target.first == bitmap.width && target.second == bitmap.height) return bitmap
    return Bitmap.createScaledBitmap(bitmap, target.first, target.second, true).also { bitmap.recycle() }
}

internal fun scaledSize(width: Int, height: Int, maxSide: Int = MAX_SIDE): Pair<Int, Int> {
    require(width > 0 && height > 0 && maxSide > 0)
    val largest = maxOf(width, height)
    if (largest <= maxSide) return width to height
    val ratio = maxSide.toDouble() / largest
    return (width * ratio).roundToInt().coerceAtLeast(1) to (height * ratio).roundToInt().coerceAtLeast(1)
}

private const val JPEG_CONTENT_TYPE = "image/jpeg"
private const val JPEG_QUALITY = 90
private const val MIN_SIDE = 256
private const val MAX_SIDE = 4096
private const val MAX_BYTES = 10 * 1024 * 1024
