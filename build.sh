#!/bin/bash
#
# Build distribution packages.
#
#   ./build.sh          build whichever formats this machine has tools for
#   ./build.sh deb      build only the .deb   (needs dpkg-buildpackage)
#   ./build.sh rpm      build only the .rpm   (needs rpmbuild)

set -e

cd "$(dirname "$0")"
ROOT="$PWD"
TARGET="${1:-auto}"

# Single source of truth for the version: the newest debian/changelog entry.
VERSION="$(sed -n '1s/^nkms (\([^)]*\)).*/\1/p' debian/changelog)"

rm -rf ./build
mkdir ./build

build_deb() {
    rsync -a --delete --exclude='.idea' --exclude='.venv' --exclude='__pycache__' --exclude='build' --exclude='.git' ./ ./build/nkms/
    (cd ./build/nkms && dpkg-buildpackage -us -uc)
}

build_rpm() {
    local topdir="$ROOT/build/rpmbuild"
    mkdir -p "$topdir"/{SOURCES,SPECS}
    tar --exclude='.idea' --exclude='.venv' --exclude='__pycache__' --exclude='./build' --exclude='.git' \
        --transform "s,^\.,nkms-$VERSION," -czf "$topdir/SOURCES/nkms-$VERSION.tar.gz" .
    rpmbuild -bb rpm/nkms.spec \
        --define "_topdir $topdir" \
        --define "nkms_version $VERSION"
    find "$topdir/RPMS" -name '*.rpm' -exec cp {} ./build/ \;
}

case "$TARGET" in
    deb) build_deb ;;
    rpm) build_rpm ;;
    auto)
        built=0
        if command -v dpkg-buildpackage >/dev/null; then build_deb; built=1; fi
        if command -v rpmbuild >/dev/null; then build_rpm; built=1; fi
        if [ "$built" = 0 ]; then
            echo "Neither dpkg-buildpackage nor rpmbuild found." >&2
            echo "Install 'dpkg-dev debhelper dh-python' (Debian) or 'rpm-build python3-devel' (Fedora)." >&2
            exit 1
        fi
        ;;
    *) echo "Usage: $0 [deb|rpm]" >&2; exit 1 ;;
esac

echo -e "\nBuild finished. Check the ./build directory for packages."
