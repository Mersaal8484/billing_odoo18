plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    // ✅ Namespace تم إرجاعه للأصلي
    namespace = "com.example.meter_reading_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // ⚠️ تم الإبقاء على الـ ID الأصلي لتجنب كراش على الأجهزة المثبت عليها
        // النسخة القديمة. غيّره إلى com.pec.meterreading فقط عند النشر الجديد
        // على Google Play بعد حذف النسخة القديمة من الأجهزة.
        applicationId = "com.example.meter_reading_app"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // ⚠️ قبل الرفع على Google Play يجب:
            // 1. إنشاء keystore: keytool -genkey -v -keystore pec-release.jks ...
            // 2. إضافة signingConfigs هنا بالبيانات الحقيقية
            // 3. تغيير السطر التالي ليستخدم signingConfigs.getByName("release")
            // حالياً يستخدم debug key للاختبار الداخلي فقط
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
