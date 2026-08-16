plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

val releaseKeystore = System.getenv("ANDROID_KEYSTORE_FILE")
val releaseKeystorePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
val releaseKeyAlias = System.getenv("ANDROID_KEY_ALIAS")
val releaseKeyPassword = System.getenv("ANDROID_KEY_PASSWORD")
val releaseVersionCode = System.getenv("DEEPTEST_ANDROID_VERSION_CODE")?.toIntOrNull() ?: 1
val releaseVersionName = System.getenv("DEEPTEST_ANDROID_VERSION_NAME") ?: "0.1.0-test"

android {
    namespace = "com.koaan.deeptest2"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.koaan.deeptest2"
        minSdk = 29
        targetSdk = 36
        versionCode = releaseVersionCode
        versionName = releaseVersionName
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    signingConfigs {
        if (!releaseKeystore.isNullOrBlank()) {
            create("release") {
                storeFile = file(releaseKeystore)
                storePassword = releaseKeystorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }
    buildTypes {
        getByName("release") {
            signingConfigs.findByName("release")?.let { signingConfig = it }
            isMinifyEnabled = false
        }
    }
    packaging {
        jniLibs.useLegacyPackaging = true
    }
}

chaquopy {
    defaultConfig {
        version = "3.10"
        pip {
            install("requests>=2.31")
            install("cryptography>=41")
            install("flask>=3.0")
        }
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("com.google.android.material:material:1.13.0")
}
