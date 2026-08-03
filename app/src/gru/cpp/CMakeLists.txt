cmake_minimum_required(VERSION 3.22.1)
project(gru_whisper LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(GRU_DYNAMIC_CPU_BACKENDS OFF)
if(ANDROID AND ANDROID_ABI STREQUAL "arm64-v8a")
    set(GRU_DYNAMIC_CPU_BACKENDS ON)
    set(GRU_ANDROID_MINIMAL_CPU_VARIANTS ON)
    set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
    set(GGML_BACKEND_DL ON CACHE BOOL "" FORCE)
    set(GGML_CPU_ALL_VARIANTS ON CACHE BOOL "" FORCE)
else()
    set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
    set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
    set(GGML_CPU_ALL_VARIANTS OFF CACHE BOOL "" FORCE)
endif()
set(WHISPER_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_BLAS OFF CACHE BOOL "" FORCE)
set(GGML_CUDA OFF CACHE BOOL "" FORCE)
set(GGML_METAL OFF CACHE BOOL "" FORCE)
set(GGML_VULKAN OFF CACHE BOOL "" FORCE)
set(GGML_OPENCL OFF CACHE BOOL "" FORCE)
set(GGML_HEXAGON OFF CACHE BOOL "" FORCE)
set(GGML_RPC OFF CACHE BOOL "" FORCE)
set(GGML_CPU_ARM_ARCH "" CACHE STRING "" FORCE)

add_subdirectory(third_party/whisper.cpp whisper-build EXCLUDE_FROM_ALL)

# Android debug packages are used for physical-device benchmarks and QA. Keep
# native inference optimized in every package so CMake's Debug default does not
# make Whisper tens of times slower than the shipped release build.
if(ANDROID)
    set(gru_optimized_targets
        whisper
        ggml
        ggml-base
        ggml-cpu
        ggml-cpu-android_armv8.0_1
        ggml-cpu-android_armv8.2_1
        ggml-cpu-android_armv8.2_2)
    foreach(target ${gru_optimized_targets})
        if(TARGET ${target})
            target_compile_options(${target} PRIVATE -O3)
        endif()
    endforeach()
endif()

add_library(gru_whisper SHARED gru_whisper_jni.c)
target_include_directories(gru_whisper PRIVATE
    third_party/whisper.cpp/include
    third_party/whisper.cpp/ggml/include)
target_link_libraries(gru_whisper PRIVATE whisper ggml android log)

if(GRU_DYNAMIC_CPU_BACKENDS)
    target_compile_definitions(gru_whisper PRIVATE GRU_DYNAMIC_CPU_BACKENDS=1)
endif()

target_compile_options(gru_whisper PRIVATE -Wall -Wextra -Werror)
