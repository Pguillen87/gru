package com.pguillen.gru.overlay

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.pguillen.gru.R

/** Visual-only drop target. The pet retains the complete touch gesture. */
internal class SuppressionTargetView(context: Context) : TextView(context) {
    private val density = resources.displayMetrics.density

    init {
        gravity = Gravity.CENTER
        includeFontPadding = false
        maxLines = 3
        minHeight = dp(56)
        setPaddingRelative(dp(18), dp(12), dp(18), dp(12))
        setTextColor(Color.WHITE)
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 14f)
        setCompoundDrawablesRelativeWithIntrinsicBounds(R.drawable.ic_gru_visibility_off, 0, 0, 0)
        compoundDrawablePadding = dp(10)
        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        setOverTarget(false)
    }

    fun setOverTarget(overTarget: Boolean) {
        text = context.getString(
            if (overTarget) R.string.gru__release_to_hide_conversation else R.string.gru__hide_in_conversation,
        )
        background = roundedBackground(
            fill = if (overTarget) ContextCompat.getColor(context, R.color.colorError) else Color.rgb(32, 35, 38),
            stroke = if (overTarget) Color.WHITE else Color.rgb(111, 118, 123),
        )
    }

    private fun roundedBackground(fill: Int, stroke: Int) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(28).toFloat()
        setColor(fill)
        setStroke(dp(1), stroke)
    }

    private fun dp(value: Int): Int = (value * density).toInt()
}
