#include <jni.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "whisper.h"

typedef struct {
    struct whisper_context * context;
    atomic_bool cancelled;
} gru_whisper_session;

static void throw_illegal_state(JNIEnv * env, const char * message) {
    jclass type = (*env)->FindClass(env, "java/lang/IllegalStateException");
    if (type != NULL) {
        (*env)->ThrowNew(env, type, message);
    }
}

static bool should_abort(void * data) {
    gru_whisper_session * session = (gru_whisper_session *) data;
    return atomic_load_explicit(&session->cancelled, memory_order_relaxed);
}

static void quiet_log(enum ggml_log_level level, const char * text, void * user_data) {
    (void) level;
    (void) text;
    (void) user_data;
}

JNIEXPORT jlong JNICALL
Java_com_pguillen_gru_local_WhisperNativeBridge_create(
        JNIEnv * env,
        jobject instance,
        jstring model_path) {
    (void) instance;
    if (model_path == NULL) {
        throw_illegal_state(env, "Model path is required");
        return 0;
    }

    const char * path = (*env)->GetStringUTFChars(env, model_path, NULL);
    if (path == NULL) return 0;

    whisper_log_set(quiet_log, NULL);
    struct whisper_context_params params = whisper_context_default_params();
    params.use_gpu = false;
    struct whisper_context * context = whisper_init_from_file_with_params(path, params);
    (*env)->ReleaseStringUTFChars(env, model_path, path);
    if (context == NULL) {
        throw_illegal_state(env, "Unable to load Whisper model");
        return 0;
    }

    gru_whisper_session * session = calloc(1, sizeof(gru_whisper_session));
    if (session == NULL) {
        whisper_free(context);
        throw_illegal_state(env, "Unable to allocate Whisper session");
        return 0;
    }
    session->context = context;
    atomic_init(&session->cancelled, false);
    return (jlong) (intptr_t) session;
}

JNIEXPORT jstring JNICALL
Java_com_pguillen_gru_local_WhisperNativeBridge_transcribe(
        JNIEnv * env,
        jobject instance,
        jlong handle,
        jfloatArray samples,
        jstring language,
        jint thread_count) {
    (void) instance;
    gru_whisper_session * session = (gru_whisper_session *) (intptr_t) handle;
    if (session == NULL || session->context == NULL || samples == NULL) {
        throw_illegal_state(env, "Invalid Whisper session");
        return NULL;
    }

    const jsize sample_count = (*env)->GetArrayLength(env, samples);
    jfloat * pcm = (*env)->GetFloatArrayElements(env, samples, NULL);
    if (pcm == NULL) return NULL;
    const char * language_code = language == NULL
            ? "auto"
            : (*env)->GetStringUTFChars(env, language, NULL);
    if (language_code == NULL) {
        (*env)->ReleaseFloatArrayElements(env, samples, pcm, JNI_ABORT);
        return NULL;
    }

    atomic_store_explicit(&session->cancelled, false, memory_order_relaxed);
    struct whisper_full_params params = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    params.n_threads = thread_count < 1 ? 1 : thread_count;
    params.language = language_code;
    params.translate = false;
    params.no_context = true;
    params.no_timestamps = true;
    params.print_progress = false;
    params.print_realtime = false;
    params.print_timestamps = false;
    params.abort_callback = should_abort;
    params.abort_callback_user_data = session;

    const int result = whisper_full(session->context, params, pcm, sample_count);
    (*env)->ReleaseFloatArrayElements(env, samples, pcm, JNI_ABORT);
    if (language != NULL) {
        (*env)->ReleaseStringUTFChars(env, language, language_code);
    }
    if (result != 0) {
        if (atomic_load_explicit(&session->cancelled, memory_order_relaxed)) {
            throw_illegal_state(env, "Whisper transcription cancelled");
        } else {
            throw_illegal_state(env, "Whisper transcription failed");
        }
        return NULL;
    }

    size_t length = 1;
    const int segment_count = whisper_full_n_segments(session->context);
    for (int index = 0; index < segment_count; index++) {
        length += strlen(whisper_full_get_segment_text(session->context, index));
    }
    char * transcript = calloc(length, sizeof(char));
    if (transcript == NULL) {
        throw_illegal_state(env, "Unable to allocate transcript");
        return NULL;
    }
    for (int index = 0; index < segment_count; index++) {
        strcat(transcript, whisper_full_get_segment_text(session->context, index));
    }
    jstring value = (*env)->NewStringUTF(env, transcript);
    free(transcript);
    return value;
}

JNIEXPORT void JNICALL
Java_com_pguillen_gru_local_WhisperNativeBridge_cancel(
        JNIEnv * env,
        jobject instance,
        jlong handle) {
    (void) env;
    (void) instance;
    gru_whisper_session * session = (gru_whisper_session *) (intptr_t) handle;
    if (session != NULL) {
        atomic_store_explicit(&session->cancelled, true, memory_order_relaxed);
    }
}

JNIEXPORT void JNICALL
Java_com_pguillen_gru_local_WhisperNativeBridge_destroy(
        JNIEnv * env,
        jobject instance,
        jlong handle) {
    (void) env;
    (void) instance;
    gru_whisper_session * session = (gru_whisper_session *) (intptr_t) handle;
    if (session == NULL) return;
    whisper_free(session->context);
    free(session);
}
