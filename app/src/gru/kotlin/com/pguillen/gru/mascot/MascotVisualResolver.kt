package com.pguillen.gru.mascot

import com.pguillen.gru.GruPet
import com.pguillen.gru.R
import java.io.File

/** One place where runtime state resolves to an offline visual. */
class MascotVisualResolver(private val store: CustomMascotStore) {
    fun resolve(source: MascotSource, state: MascotRuntimeState): MascotVisual = when (source) {
        is MascotSource.BuiltIn -> MascotVisual.Atlas(atlasFor(source.pet))
        is MascotSource.Custom -> store.poseFile(source.poseSetId, state)
            ?.takeIf(File::isFile)
            ?.let { MascotVisual.ImageFile(it.absolutePath) }
            ?: MascotVisual.Atlas(atlasFor(GruPet.FAISCA))
    }

    private fun atlasFor(pet: GruPet): Int = when (pet) {
        GruPet.LUME -> R.drawable.gru_pet_lume_atlas
        GruPet.FAISCA -> R.drawable.gru_pet_faisca_atlas
        GruPet.BIP -> R.drawable.gru_pet_bip_atlas
        GruPet.PINGO -> R.drawable.gru_pet_pingo_atlas
        GruPet.PUDIM -> R.drawable.gru_pet_pudim_atlas
    }
}
