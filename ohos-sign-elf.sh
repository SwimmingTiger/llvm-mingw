#!/bin/sh

BASE_DIR="$(dirname "$(realpath "$0")")"
PREFIX="$1"
LLVM_LIB="$PREFIX/lib"
LLVM_SO="$LLVM_LIB/libLLVM.so"
HOMEBREW_LIB="$HOME/.harmonybrew/lib"

llvm_ldd() {
    llvm-readelf --needed-libs "$@" | grep '^\s\s*' | sed 's/^\s\s*//'
}

remove_signature() {
    llvm-objcopy --remove-section .codesign "$@"
}

sign_elf() {
    binary-sign-tool sign -inFile "$1" -outFile "$1" -selfSign 1
}

# copy llvm lib depends without signature
if [ -f "$LLVM_SO" ]; then
    llvm_ldd "$LLVM_SO" | while read so; do
        if [ ! -f "$LLVM_LIB/$so" ] && [ -f "$HOMEBREW_LIB/$so" ]; then
            cp "$HOMEBREW_LIB/$so" "$LLVM_LIB/$so"
            remove_signature "$LLVM_LIB/$so"
            if [ -f "$LLVM_LIB/$so" ]; then
                echo "COPIED: $HOMEBREW_LIB/$so -> $LLVM_LIB/$so"
            fi
        fi
    done
fi

# sign all ELFs
"$BASE_DIR/ohos-sign-elf.py" "$PREFIX"

