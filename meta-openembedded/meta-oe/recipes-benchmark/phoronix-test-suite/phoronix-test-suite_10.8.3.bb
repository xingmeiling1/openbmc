SUMMARY = "Phoronix Test Suite"
DESCRIPTION = "The Phoronix Test Suite is designed to carry out both qualitative \
and quantitative benchmarks in a clean, reproducible, and easy-to-use manner."
LICENSE = "GPL-3.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=d32239bcb673463ab874e80d47fae504"
SECTION = "console/tests"

SRC_URI = "http://www.phoronix-test-suite.com/releases/${BP}.tar.gz"
SRC_URI[sha256sum] = "4b742e28a9542fe2b57aacb691159d69d3e1c77d95da6d24b7867889ce84ba80"

S = "${WORKDIR}/phoronix-test-suite"

inherit systemd allarch mime mime-xdg

do_install() {
    DESTDIR=${D} ./install-sh ${exec_prefix}

    if [ "${systemd_unitdir}" != "/usr/lib/systemd" ]; then
        install -d ${D}/${systemd_unitdir}/system/
        mv ${D}/usr/lib/systemd/system/* ${D}/${systemd_unitdir}/system/
        rm -rf ${D}/usr/lib/
    fi
}

# It is not advisable to enable these services by default since they can cause
# continual target reboots if they encounter network problems.
#
SYSTEMD_AUTO_ENABLE = "disable"
SYSTEMD_SERVICE:${PN} = "phoromatic-client.service phoromatic-server.service"

RDEPENDS:${PN} += "bash python3-core php-cli util-linux-lscpu os-release lsb-release"

FILES:${PN} += " \
    ${datadir}/phoronix-test-suite \
    ${datadir}/appdata/phoronix-test-suite.appdata.xml \
    ${datadir}/icons/hicolor/48x48/apps/phoronix-test-suite.png \
    ${datadir}/icons/hicolor/64x64/mimetypes/application-x-openbenchmarking.png \
    ${datadir}/mime/packages/openbenchmarking-mime.xml \
    ${systemd_unitdir}/* \
"
