/*
 * Copyright (C) 2026 Gru Contributors
 * Licensed under the Apache License, Version 2.0.
 */

package com.pguillen.gru

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

internal object GruColors {
    val Gold = Color(0xFFFFD84D)
    val Cyan = Color(0xFF20B8FF)
    val Success = Color(0xFF31E6A1)
    val Danger = Color(0xFFFF4D57)
    val Night = Color(0xFF050607)
    val Panel = Color(0xFF111416)
    val PanelHigh = Color(0xFF191D20)
    val Outline = Color(0xFF30363A)
}

private val GruDarkColors = darkColorScheme(
    primary = GruColors.Cyan,
    onPrimary = Color(0xFF001F2A),
    primaryContainer = Color(0xFF073D52),
    onPrimaryContainer = Color(0xFFBCE9FF),
    secondary = GruColors.Gold,
    onSecondary = Color(0xFF211B00),
    secondaryContainer = Color(0xFF4D4100),
    onSecondaryContainer = Color(0xFFFFE68A),
    tertiary = GruColors.Success,
    onTertiary = Color(0xFF003824),
    error = GruColors.Danger,
    onError = Color.Black,
    background = GruColors.Night,
    onBackground = Color(0xFFF3F4F5),
    surface = GruColors.Panel,
    onSurface = Color(0xFFF3F4F5),
    surfaceVariant = GruColors.PanelHigh,
    onSurfaceVariant = Color(0xFFB5BDC2),
    outline = GruColors.Outline,
    outlineVariant = Color(0xFF22272A),
)

private val GruLightColors = lightColorScheme(
    primary = Color(0xFF00658A),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFC6E7F6),
    onPrimaryContainer = Color(0xFF001F2A),
    secondary = Color(0xFF725C00),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFE17A),
    onSecondaryContainer = Color(0xFF231B00),
    tertiary = Color(0xFF006C4A),
    error = Color(0xFFBA1A1A),
    background = Color(0xFFFBF9F1),
    onBackground = Color(0xFF191C1D),
    surface = Color(0xFFFFFBF4),
    onSurface = Color(0xFF191C1D),
    surfaceVariant = Color(0xFFF0ECE4),
    onSurfaceVariant = Color(0xFF444749),
    outline = Color(0xFF74777A),
    outlineVariant = Color(0xFFC4C7C9),
)

private val GruTypography = Typography(
    headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 32.sp, lineHeight = 38.sp),
    headlineMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 28.sp, lineHeight = 34.sp),
    headlineSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 22.sp, lineHeight = 28.sp),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 14.sp, lineHeight = 20.sp),
    labelSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium, fontSize = 10.sp, lineHeight = 14.sp),
)

private val GruShapes = Shapes(
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp),
)

@Composable
fun GruTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) GruDarkColors else GruLightColors
    MaterialTheme(colorScheme = colors, typography = GruTypography, shapes = GruShapes, content = content)
}
