package com.pguillen.gru

import com.pguillen.gru.mascot.MascotPoseChoices
import com.pguillen.gru.mascot.MascotPoseRole
import kotlin.test.Test
import kotlin.test.assertEquals

class GruMascotCreationFlowTest {
    @Test fun `draft submits the photo before generated choices`() {
        val sequence = generateSequence(MascotDraftStep.PHOTO) { step ->
            step.next().takeUnless { it == step }
        }.toList()

        assertEquals(
            listOf(
                MascotDraftStep.PHOTO,
                MascotDraftStep.CONFIRM,
            ),
            sequence,
        )
    }

    @Test fun `generated customization asks for name before the three visual galleries`() {
        val sequence = generateSequence(MascotCustomizationStep.NAME) { step ->
            step.next().takeUnless { it == step }
        }.toList()

        assertEquals(
            listOf(
                MascotCustomizationStep.NAME,
                MascotCustomizationStep.NORMAL,
                MascotCustomizationStep.LISTENING,
                MascotCustomizationStep.TRANSCRIBING,
            ),
            sequence,
        )
    }

    @Test fun `each runtime moment keeps the option selected by the user`() {
        val choices = MascotPoseChoices()
            .select(MascotPoseRole.NORMAL, "normal_curious")
            .select(MascotPoseRole.LISTENING, "listening_natural")
            .select(MascotPoseRole.TRANSCRIBING, "transcribing_notes")

        assertEquals("normal_curious", choices.normal)
        assertEquals("listening_natural", choices.listening)
        assertEquals("transcribing_notes", choices.transcribing)
    }
}
