package com.pguillen.gru

import android.app.Application

class GruApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        GruAppCheck.install()
    }
}
