/*
 * Copyright (C) 2026 DevEmperor (Dictate)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

package com.pguillen.gru.overlay

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.os.SystemClock
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

internal enum class PetMotionMode { IDLE, LISTENING, PROCESSING, SUCCESS, ERROR }

/**
 * Renders the pet as one continuously moving body. Atlas poses only change expression at authored
 * moments; breathing, weight, tilt and jumps are interpolated every display frame.
 */
internal class LivingPetView(context: Context, atlasRes: Int) : View(context) {
    private val bitmap: Bitmap = decodeAtlas(atlasRes)
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.DITHER_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val source = Rect()
    private val destination = RectF()
    private val density = resources.displayMetrics.density
    private var mode = PetMotionMode.IDLE
    private var modeStartedAt = SystemClock.elapsedRealtime()
    private var targetLevel = 0f
    private var renderedLevel = 0f
    private var animator: ValueAnimator? = null

    fun setMode(value: PetMotionMode) {
        if (mode == value) return
        mode = value
        modeStartedAt = SystemClock.elapsedRealtime()
        invalidate()
    }

    fun setAudioLevel(value: Float) {
        targetLevel = value.coerceIn(0f, 1f)
    }

    fun release() {
        animator?.cancel()
        animator = null
        if (!bitmap.isRecycled) bitmap.recycle()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        animator = createAnimator()?.also(ValueAnimator::start)
    }

    override fun onDetachedFromWindow() {
        animator?.cancel()
        animator = null
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        renderedLevel += (targetLevel - renderedLevel) * 0.16f
        val seconds = (SystemClock.elapsedRealtime() - modeStartedAt) / 1_000f
        val motion = motionAt(seconds)
        canvas.save()
        canvas.translate(width / 2f + motion.x, height / 2f + motion.y)
        canvas.rotate(motion.rotation)
        canvas.scale(motion.scaleX, motion.scaleY)
        canvas.translate(-width / 2f, -height / 2f)
        drawBlend(canvas, motion.fromFrame, motion.toFrame, motion.blend)
        canvas.restore()
    }

    private fun motionAt(seconds: Float): PetMotion = when (mode) {
        PetMotionMode.IDLE -> idleMotion(seconds)
        PetMotionMode.LISTENING -> listeningMotion(seconds)
        PetMotionMode.PROCESSING -> processingMotion(seconds)
        PetMotionMode.SUCCESS -> successMotion(seconds)
        PetMotionMode.ERROR -> errorMotion(seconds)
    }

    private fun idleMotion(t: Float): PetMotion {
        val cycle = t % IDLE_CYCLE_SECONDS
        val breath = sin(t * PI.toFloat() * 0.82f)
        val base = PetMotion(
            y = breath * density * 1.1f,
            rotation = sin(t * 0.72f) * 1.35f,
            scaleX = 1f - breath * 0.012f,
            scaleY = 1f + breath * 0.018f,
        )
        return when {
            cycle in 2.55f..2.82f -> base.blink((cycle - 2.55f) / 0.27f)
            cycle >= 5.55f -> jumpMotion(base, (cycle - 5.55f) / 1.25f)
            else -> base
        }
    }

    private fun listeningMotion(t: Float): PetMotion {
        val voice = renderedLevel
        val pulse = sin(t * 8.2f)
        val look = ((sin(t * 1.7f) + 1f) / 2f).coerceIn(0f, 1f)
        val excited = smoothStep(0.35f, 0.75f, voice)
        return PetMotion(
            x = sin(t * 1.35f) * density * 1.25f,
            y = -voice * density * 3.5f + pulse * density * (0.35f + voice),
            rotation = -3.5f + look * 7f + pulse * voice * 1.4f,
            scaleX = 1f + voice * 0.035f,
            scaleY = 1f + voice * 0.055f,
            fromFrame = 4,
            toFrame = 7,
            blend = excited,
        )
    }

    private fun processingMotion(t: Float): PetMotion {
        val orbit = t * PI.toFloat() * 1.25f
        return PetMotion(
            x = cos(orbit) * density * 1.4f,
            y = sin(orbit * 2f) * density,
            rotation = sin(orbit) * 7f,
            scaleX = 0.99f + cos(orbit) * 0.012f,
            scaleY = 1.01f - cos(orbit) * 0.012f,
            fromFrame = 10,
        )
    }

    private fun successMotion(t: Float): PetMotion {
        val p = (t / 0.82f).coerceIn(0f, 1f)
        val jump = sin(p * PI.toFloat()).coerceAtLeast(0f)
        return PetMotion(
            y = -jump * density * 12f,
            rotation = sin(p * PI.toFloat() * 2f) * 5f,
            scaleX = 1f + jump * 0.06f,
            scaleY = 1f - jump * 0.035f,
            fromFrame = 0,
            toFrame = 12,
            blend = smoothStep(0.06f, 0.38f, p),
        )
    }

    private fun errorMotion(t: Float): PetMotion {
        val wave = sin(t * 4.2f)
        val hop = ((sin(t * 2.1f) + 1f) / 2f).coerceIn(0f, 1f)
        return PetMotion(
            y = -hop * density * 2.2f,
            rotation = wave * 2.4f,
            scaleX = 1f + hop * 0.018f,
            scaleY = 1f + hop * 0.025f,
            fromFrame = 12,
        )
    }

    private fun jumpMotion(base: PetMotion, raw: Float): PetMotion {
        val p = raw.coerceIn(0f, 1f)
        val anticipation = smoothStep(0f, 0.16f, p) * (1f - smoothStep(0.16f, 0.28f, p))
        val airborne = sin(smoothStep(0.18f, 0.86f, p) * PI.toFloat()).coerceAtLeast(0f)
        val happy = smoothStep(0.5f, 0.82f, p) * (1f - smoothStep(0.9f, 1f, p))
        return base.copy(
            y = base.y + anticipation * density * 4f - airborne * density * 10f,
            rotation = base.rotation + airborne * 5.5f,
            scaleX = base.scaleX + anticipation * 0.055f,
            scaleY = base.scaleY - anticipation * 0.07f + airborne * 0.035f,
            fromFrame = 0,
            toFrame = 12,
            blend = happy,
        )
    }

    private fun PetMotion.blink(raw: Float): PetMotion {
        val p = raw.coerceIn(0f, 1f)
        val closed = sin(p * PI.toFloat()).coerceIn(0f, 1f)
        return copy(fromFrame = 0, toFrame = 3, blend = closed)
    }

    private fun drawBlend(canvas: Canvas, from: Int, to: Int, blend: Float) {
        val amount = blend.coerceIn(0f, 1f)
        drawFrame(canvas, from, ((1f - amount) * 255).toInt())
        if (amount > 0.01f && to != from) drawFrame(canvas, to, (amount * 255).toInt())
        paint.alpha = 255
    }

    private fun drawFrame(canvas: Canvas, frame: Int, alpha: Int) {
        val column = frame % 4
        val row = frame / 4
        source.set(
            column * bitmap.width / 4,
            row * bitmap.height / 4,
            (column + 1) * bitmap.width / 4,
            (row + 1) * bitmap.height / 4,
        )
        destination.set(0f, 0f, width.toFloat(), height.toFloat())
        paint.alpha = alpha
        canvas.drawBitmap(bitmap, source, destination, paint)
    }

    private fun createAnimator(): ValueAnimator? {
        if (!ValueAnimator.areAnimatorsEnabled()) return null
        return ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 1_000L
            repeatCount = ValueAnimator.INFINITE
            interpolator = LinearInterpolator()
            addUpdateListener { invalidate() }
        }
    }

    private fun decodeAtlas(atlasRes: Int): Bitmap {
        val decoded = checkNotNull(
            BitmapFactory.decodeResource(
                resources,
                atlasRes,
                BitmapFactory.Options().apply {
                    inPreferredConfig = Bitmap.Config.ARGB_8888
                    inScaled = false
                },
            ),
        ) { "Unable to decode pet atlas" }
        if (decoded.config != Bitmap.Config.HARDWARE) return decoded
        return checkNotNull(decoded.copy(Bitmap.Config.ARGB_8888, false)) {
            "Unable to prepare pet atlas"
        }.also { decoded.recycle() }
    }

    private fun smoothStep(from: Float, to: Float, value: Float): Float {
        val x = ((value - from) / (to - from)).coerceIn(0f, 1f)
        return x * x * (3f - 2f * x)
    }

    private data class PetMotion(
        val x: Float = 0f,
        val y: Float = 0f,
        val rotation: Float = 0f,
        val scaleX: Float = 1f,
        val scaleY: Float = 1f,
        val fromFrame: Int = 0,
        val toFrame: Int = fromFrame,
        val blend: Float = 0f,
    )

    private companion object {
        const val IDLE_CYCLE_SECONDS = 7.2f
    }
}

/** Draws state around the pet without adding another button or obscuring the character. */
internal class PetSignalView(
    context: Context,
    private val accentColor: Int,
    private val recordingColor: Int,
    private val successColor: Int,
    private val errorColor: Int,
) : View(context) {
    private val density = resources.displayMetrics.density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val bounds = RectF()
    private var mode = PetMotionMode.IDLE
    private var targetLevel = 0f
    private var renderedLevel = 0f
    private var animator: ValueAnimator? = null

    fun setMode(value: PetMotionMode) {
        mode = value
        invalidate()
    }

    fun setAudioLevel(value: Float) {
        targetLevel = value.coerceIn(0f, 1f)
    }

    fun release() {
        animator?.cancel()
        animator = null
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        animator = createAnimator()?.also(ValueAnimator::start)
    }

    override fun onDetachedFromWindow() {
        animator?.cancel()
        animator = null
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        renderedLevel += (targetLevel - renderedLevel) * 0.18f
        val t = SystemClock.elapsedRealtime() / 1_000f
        when (mode) {
            PetMotionMode.IDLE -> Unit
            PetMotionMode.LISTENING -> drawListening(canvas, t)
            PetMotionMode.PROCESSING -> drawProcessing(canvas, t)
            PetMotionMode.SUCCESS -> drawStatusRing(canvas, successColor, 0.78f)
            PetMotionMode.ERROR -> drawStatusRing(canvas, errorColor, 0.62f)
        }
    }

    private fun drawListening(canvas: Canvas, t: Float) {
        val cx = width / 2f
        val cy = height / 2f
        val level = renderedLevel
        repeat(2) { index ->
            val wave = ((t * 1.35f + index * 0.48f) % 1f)
            val radius = width * (0.31f + wave * 0.16f) + level * density * 2f
            paint.color = recordingColor
            paint.alpha = ((1f - wave) * (90 + level * 100)).toInt().coerceIn(0, 190)
            paint.strokeWidth = density * (2.2f - wave * 0.8f)
            canvas.drawCircle(cx, cy, radius, paint)
        }
        paint.style = Paint.Style.FILL
        paint.alpha = (190 + sin(t * 7f) * 50f).toInt().coerceIn(120, 240)
        canvas.drawCircle(cx, height * 0.085f, density * (3.1f + level * 1.2f), paint)
        paint.style = Paint.Style.STROKE
    }

    private fun drawProcessing(canvas: Canvas, t: Float) {
        val inset = width * 0.16f
        bounds.set(inset, inset, width - inset, height - inset)
        paint.color = accentColor
        paint.alpha = 150
        paint.strokeWidth = density * 2f
        canvas.drawArc(bounds, t * 150f % 360f, 95f, false, paint)
        canvas.drawArc(bounds, (t * 150f + 180f) % 360f, 48f, false, paint)
    }

    private fun drawStatusRing(canvas: Canvas, color: Int, alpha: Float) {
        paint.color = color
        paint.alpha = (255 * alpha).toInt()
        paint.strokeWidth = density * 2.4f
        canvas.drawCircle(width / 2f, height / 2f, width * 0.39f, paint)
    }

    private fun createAnimator(): ValueAnimator? {
        if (!ValueAnimator.areAnimatorsEnabled()) return null
        return ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 1_000L
            repeatCount = ValueAnimator.INFINITE
            interpolator = LinearInterpolator()
            addUpdateListener { invalidate() }
        }
    }
}
