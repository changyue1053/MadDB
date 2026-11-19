#include <jni.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "maddb.h"

/* Copy Java arrays before SQLite: never hold pinned Java memory during blocking IO. */
typedef struct { uint8_t *data; size_t size; } bytes;
static int read_bytes(JNIEnv *env, jbyteArray array, bytes *out) {
    out->data = NULL; out->size = 0;
    if (array == NULL) return MADDB_INVALID_ARGUMENT;
    jsize length = (*env)->GetArrayLength(env, array);
    if ((*env)->ExceptionCheck(env)) return MADDB_INTERNAL_ERROR;
    out->size = (size_t)length;
    if (length == 0) return MADDB_OK;
    out->data = malloc((size_t)length);
    if (out->data == NULL) return MADDB_INTERNAL_ERROR;
    (*env)->GetByteArrayRegion(env, array, 0, length, (jbyte *)out->data);
    if ((*env)->ExceptionCheck(env)) { free(out->data); out->data = NULL; return MADDB_INTERNAL_ERROR; }
    return MADDB_OK;
}
static uint64_t handle_bits(jlong value) {
    uint64_t result; _Static_assert(sizeof(result) == sizeof(value), "64-bit handle");
    memcpy(&result, &value, sizeof(result)); return result;
}
static jint version(JNIEnv *env, jclass cls) { (void)env; (void)cls; return (jint)maddb_abi_version(); }
static jint open_db(JNIEnv *env, jclass cls, jbyteArray path, jbyteArray ns, jlongArray out) {
    (void)cls; bytes p = {0}, n = {0}; maddb_handle handle = 0; jlong bits = 0;
    if (out == NULL || (*env)->GetArrayLength(env, out) != 1) return MADDB_INVALID_ARGUMENT;
    (*env)->SetLongArrayRegion(env, out, 0, 1, &bits);
    if ((*env)->ExceptionCheck(env)) return MADDB_INTERNAL_ERROR;
    int status = read_bytes(env, path, &p);
    if (status == MADDB_OK) status = read_bytes(env, ns, &n);
    if (status == MADDB_OK) status = maddb_open(p.data, p.size, n.data, n.size, &handle);
    free(p.data); free(n.data);
    if (status == MADDB_OK) {
        memcpy(&bits, &handle, sizeof(bits));
        (*env)->SetLongArrayRegion(env, out, 0, 1, &bits);
        if ((*env)->ExceptionCheck(env)) { (void)maddb_close(handle); return MADDB_INTERNAL_ERROR; }
    }
    return status;
}
static jint put(JNIEnv *env, jclass cls, jlong h, jbyteArray key, jbyteArray value) {
    (void)cls; bytes k = {0}, v = {0}; int status = read_bytes(env, key, &k);
    if (status == MADDB_OK) status = read_bytes(env, value, &v);
    if (status == MADDB_OK) status = maddb_put(handle_bits(h), k.data, k.size, v.data, v.size);
    free(k.data); free(v.data); return status;
}
static jint get(JNIEnv *env, jclass cls, jlong h, jbyteArray key, jbyteArray buffer, jlongArray length) {
    (void)cls; bytes k = {0}; jlong result = 0; size_t needed = 0;
    if (buffer == NULL || length == NULL || (*env)->GetArrayLength(env, length) != 1) return MADDB_INVALID_ARGUMENT;
    (*env)->SetLongArrayRegion(env, length, 0, 1, &result);
    if ((*env)->ExceptionCheck(env)) return MADDB_INTERNAL_ERROR;
    int status = read_bytes(env, key, &k);
    if (status != MADDB_OK) return status;
    jsize capacity = (*env)->GetArrayLength(env, buffer);
    uint8_t *output = capacity == 0 ? NULL : malloc((size_t)capacity);
    if (capacity != 0 && output == NULL) { free(k.data); return MADDB_INTERNAL_ERROR; }
    status = maddb_get(handle_bits(h), k.data, k.size, output, (size_t)capacity, &needed);
    free(k.data);
    if (needed > INT64_MAX) { free(output); return MADDB_INTERNAL_ERROR; }
    result = (jlong)needed;
    if (status == MADDB_OK && needed > 0) {
        (*env)->SetByteArrayRegion(env, buffer, 0, (jsize)needed, (jbyte *)output);
    }
    free(output);
    if ((*env)->ExceptionCheck(env)) return MADDB_INTERNAL_ERROR;
    (*env)->SetLongArrayRegion(env, length, 0, 1, &result);
    return (*env)->ExceptionCheck(env) ? MADDB_INTERNAL_ERROR : status;
}
static jint remove_key(JNIEnv *env, jclass cls, jlong h, jbyteArray key) {
    (void)cls; bytes k = {0}; int status = read_bytes(env, key, &k);
    if (status == MADDB_OK) status = maddb_remove(handle_bits(h), k.data, k.size);
    free(k.data); return status;
}
static jint close_db(JNIEnv *env, jclass cls, jlong h) { (void)env; (void)cls; return maddb_close(handle_bits(h)); }
JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    (void)reserved; JNIEnv *env = NULL;
    if ((*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6) != JNI_OK) return JNI_ERR;
    jclass cls = (*env)->FindClass(env, "io/maddb/MadDb");
    if (cls == NULL) return JNI_ERR;
    JNINativeMethod methods[] = {
        {"nativeVersion", "()I", (void *)version},
        {"nativeOpen", "([B[B[J)I", (void *)open_db},
        {"nativePut", "(J[B[B)I", (void *)put},
        {"nativeGet", "(J[B[B[J)I", (void *)get},
        {"nativeRemove", "(J[B)I", (void *)remove_key},
        {"nativeClose", "(J)I", (void *)close_db}
    };
    int ok = (*env)->RegisterNatives(env, cls, methods, (jint)(sizeof(methods)/sizeof(methods[0])));
    (*env)->DeleteLocalRef(env, cls);
    return ok == JNI_OK ? JNI_VERSION_1_6 : JNI_ERR;
}
