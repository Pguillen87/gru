package com.pguillen.gru

import android.content.Context
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.test.core.app.ApplicationProvider
import org.junit.Rule
import org.junit.Test

class GruConversationSuppressionUiTest {
    @get:Rule val compose = createComposeRule()
    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun suppressedConversationCardShowsCountAndClears() {
        var cleared = false
        compose.setContent { GruTheme { SuppressedConversationsCard(2) { cleared = true } } }

        compose.onNodeWithText(context.getString(R.string.gru__suppressed_conversations_title)).assertExists()
        compose.onNodeWithText(context.resources.getQuantityString(R.plurals.gru__suppressed_conversations_summary, 2, 2))
            .assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__show_again)).performClick()
        check(cleared)
    }

    @Test
    fun cardSupportsTwoHundredPercentTextAndRtl() {
        compose.setContent {
            CompositionLocalProvider(
                LocalDensity provides Density(context.resources.displayMetrics.density, 2f),
                LocalLayoutDirection provides LayoutDirection.Rtl,
            ) {
                GruTheme { SuppressedConversationsCard(1) {} }
            }
        }

        compose.onNodeWithText(context.getString(R.string.gru__suppressed_conversations_title)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__show_again)).assertExists()
    }
}
