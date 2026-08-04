/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

enum class GruPet {
    LUME,
    FAISCA,
    BIP,
    PINGO,
    PUDIM,
}

enum class GruPetSize(val scale: Float) {
    SMALL(0.78f),
    MEDIUM(1f),
    LARGE(1.24f),
}
