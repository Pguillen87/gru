package com.pguillen.gru

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.unit.Density
import org.junit.Rule
import org.junit.Test

class GruPerchScreenTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun perchKeepsEssentialActionsAtTwoHundredPercentText() {
        compose.setContent {
            val context = LocalContext.current
            CompositionLocalProvider(LocalDensity provides Density(context.resources.displayMetrics.density, 2f)) {
                GruTheme { GruPerchScreen(GruPreferences.get(context)) }
            }
        }

        compose.onNodeWithText("Puleiro do Gru").assertExists()
        compose.onNodeWithText("Código do mascote").performTextInput("inválido")
        compose.onNodeWithText("Colar código").assert(hasClickAction())
        compose.onNodeWithText("Buscar").performClick()
        compose.onNodeWithText("Confira o código e tente novamente.").assertExists()
    }
}
