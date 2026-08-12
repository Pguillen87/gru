package com.pguillen.gru

import android.content.Context
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.test.core.app.ApplicationProvider
import androidx.compose.ui.semantics.SemanticsProperties
import com.pguillen.gru.mascot.CustomMascotStore
import com.pguillen.gru.mascot.importing.MascotImportAsset
import com.pguillen.gru.mascot.importing.MascotImportManifest
import com.pguillen.gru.mascot.importing.MascotPoseRole
import com.pguillen.gru.mascot.importing.MascotVisibility
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import java.security.MessageDigest

class GruMascotScreenTest {
    @get:Rule val compose = createComposeRule()
    private val context: Context = ApplicationProvider.getApplicationContext()

    @Before
    fun selectKnownBuiltIn() {
        GruPreferences.get(context).setPet(GruPet.FAISCA)
        GruPreferences.get(context).setOpacity(100)
        CustomMascotStore(context).entries().filter { it.source == CustomMascotStore.SOURCE_CODE_IMPORT }
            .forEach { CustomMascotStore(context).remove(it.poseSetId) }
    }

    @Test
    fun libraryShowsApprovedSectionsAndSelectionSemantics() {
        compose.setContent { GruTheme { GruMascotScreen(GruPreferences.get(context)) } }

        compose.onNodeWithText(context.getString(R.string.gru__mascots_title)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__current_mascot)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__gru_mascots)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__my_mascots)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__appearance)).assertExists()
        compose.onNodeWithContentDescription(context.getString(R.string.gru__pet_faisca))
            .assertHasClickAction()
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.Selected, true))
    }

    @Test
    fun essentialLibraryControlsRemainReachableAtTwoHundredPercentText() {
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(context.resources.displayMetrics.density, 2f)) {
                GruTheme { GruMascotScreen(GruPreferences.get(context)) }
            }
        }

        compose.onNodeWithText(context.getString(R.string.gru__size)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__size_small)).performClick()
        compose.onNodeWithText(context.getString(R.string.gru__opacity, 100)).assertExists()
    }

    @Test
    fun importedMascotExposesAccessibleActionsAndRemovalConfirmation() {
        val bytes = context.resources.openRawResource(R.drawable.gru_pet_lume).use { it.readBytes() }
        val manifest = testManifest(bytes)
        val installed = CustomMascotStore(context).promoteImported(
            manifest,
            MascotPoseRole.entries.associateWith { bytes },
        )
        check(installed)

        compose.setContent { GruTheme { GruMascotScreen(GruPreferences.get(context)) } }

        compose.onNodeWithText(manifest.displayName).performScrollTo().assertExists()
        compose.onNodeWithContentDescription(context.getString(R.string.gru__add_favorite)).performClick()
        compose.onNodeWithContentDescription(context.getString(R.string.gru__mascot_actions, manifest.displayName))
            .performScrollTo()
            .performClick()
        compose.onNodeWithText(context.getString(R.string.gru__remove_imported_mascot)).performClick()
        compose.onNodeWithText(context.getString(R.string.gru__remove_mascot_title)).assertExists()
    }

    @Test
    fun libraryKeepsEssentialSectionsInRtl() {
        compose.setContent {
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                GruTheme { GruMascotScreen(GruPreferences.get(context)) }
            }
        }

        compose.onNodeWithText(context.getString(R.string.gru__gru_mascots)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__my_mascots)).assertExists()
        compose.onNodeWithText(context.getString(R.string.gru__appearance)).assertExists()
    }

    private fun testManifest(bytes: ByteArray): MascotImportManifest {
        val sha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        fun asset(role: MascotPoseRole) = MascotImportAsset(
            poseId = role.name.lowercase(),
            role = role,
            assetUrl = "https://assets.example.invalid/${role.name.lowercase()}.webp",
            sha256 = sha,
            expectedBytes = bytes.size.toLong(),
            mimeType = "image/webp",
        )
        val poses = MascotPoseRole.entries.map(::asset)
        return MascotImportManifest(
            schemaVersion = 1,
            mascotId = "compose-test",
            packageVersion = "v1",
            displayName = "Amigo do Puleiro",
            visibility = MascotVisibility.PUBLIC,
            preview = poses.first(),
            poses = poses,
        )
    }
}
