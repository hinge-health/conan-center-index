from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools import files, microsoft, scm
from conan.tools.env import VirtualBuildEnv
from conan.tools.gnu import Autotools, AutotoolsToolchain
from conan.tools.layout import basic_layout
import os


required_conan_version = ">=1.53.0"


class GetTextConan(ConanFile):
    name = "gettext"
    description = "An internationalization and localization system for multilingual programs"
    topics = ("gettext", "intl", "libintl", "i18n")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.gnu.org/software/gettext"
    license = "GPL-3.0-or-later"
    settings = "os", "arch", "compiler"

    @property
    def _settings_build(self):
        return getattr(self, "settings_build", self.settings)

    @property
    def _user_info_build(self):
        return getattr(self, "user_info_build", self.deps_user_info)

    def layout(self):
        basic_layout(self, src_folder="src")

    def export_sources(self):
        files.export_conandata_patches(self)

    def configure(self):
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd

    def requirements(self):
        self.requires("libiconv/1.17")

    def build_requirements(self):
        if self._settings_build.os == "Windows":
            if not self.conf.get("tools.microsoft.bash:path", default=False, check_type=bool):
                self.tool_requires("msys2/cci.latest")
            self.win_bash = True
        if microsoft.is_msvc(self):
            self.tool_requires("automake/1.16.5")

    def validate(self):
        if scm.Version(self.version) < "0.21" and microsoft.is_msvc(self):
            # FIXME: it used to be possible. What changed?
            raise ConanInvalidConfiguration(
                "MSVC builds of gettext for versions < 0.21 are not supported.")

    def package_id(self):
        del self.info.settings.compiler

    def source(self):
        files.get(self, **self.conan_data["sources"]
                  [self.version], strip_root=True)

    def generate(self):
        tc = AutotoolsToolchain(self)

        libiconv_prefix = microsoft.unix_path(self,
                                              self.deps_cpp_info["libiconv"].rootpath)

        tc.configure_args.extend([
            "HELP2MAN=/bin/true",
            "EMACS=no",
            "--with-libiconv-prefix={}".format(libiconv_prefix),
            "--disable-nls",
            "--disable-dependency-tracking",
            "--enable-relocatable",
            "--disable-c++",
            "--disable-java",
            "--disable-csharp",
            "--disable-libasprintf",
            "--disable-curses",
        ])

        tc.make_args.extend(["-C", "intl"])

        if microsoft.is_msvc(self):
            tc.extra_cflags.append("-FS")

            rc = None

            # INSTALL.windows: Native binaries, built using the MS Visual C/C++ tool chain.
            if self.settings.arch == "x86":
                host = "i686-w64-mingw32"
                rc = "windres --target=pe-i386"
            elif self.settings.arch == "x86_64":
                host = "x86_64-w64-mingw32"
                rc = "windres --target=pe-x86-64"
            if rc:
                tc.configure_args.extend([
                    "--host={}".format(host),
                    "RC={}".format(rc),
                    "WINDRES={}".format(rc),
                ])

        env = tc.environment()
        if microsoft.is_msvc(self):
            env.define("CC", "{} cl -nologo".format(microsoft.unix_path(self,
                       self._user_info_build["automake"].compile)))
            env.define("LD", "link -nologo")
            env.define("NM", "dumpbin -symbols")
            env.define("STRIP", ":")
            env.define("AR", "{} lib".format(microsoft.unix_path(
                self, self._user_info_build["automake"].ar_lib)))
            env.define("RANLIB", "")

        tc.generate(env)

        env = VirtualBuildEnv(self)
        env.generate()

    def build(self):
        files.apply_conandata_patches(self)

        files.replace_in_file(self, os.path.join(
            self.source_folder, "gettext-tools", "misc", "autopoint.in"), "@prefix@", "$GETTEXT_ROOT_UNIX")
        files.replace_in_file(self, os.path.join(
            self.source_folder, "gettext-tools", "misc", "autopoint.in"), "@datarootdir@", "$prefix/res")

        with files.chdir(self, "gettext-tools"):
            autotools = Autotools(self)
            autotools.configure()
            autotools.make()

    def package(self):
        files.copy(self, "COPYING", src=self.source_folder,
                   dst=os.path.join(self.package_folder, "licenses"))

        autotools = Autotools(self)
        autotools.install(
            args=[f"DESTDIR={microsoft.unix_path(self, self.package_folder)}"])

        files.rmdir(self, os.path.join(self.package_folder, "lib"))
        files.rmdir(self, os.path.join(self.package_folder, "include"))
        files.rmdir(self, os.path.join(self.package_folder, "share", "doc"))
        files.rmdir(self, os.path.join(self.package_folder, "share", "info"))
        files.rmdir(self, os.path.join(self.package_folder, "share", "man"))

    def package_info(self):
        self.cpp_info.libdirs = []
        self.cpp_info.includedirs = []

        bindir = os.path.join(self.package_folder, "bin")
        self.output.info(
            "Appending PATH environment variable: {}".format(bindir))
        self.env_info.PATH.append(bindir)

        aclocal = microsoft.unix_path(self, os.path.join(
            self.package_folder, "res", "aclocal"))
        self.output.info(
            "Appending AUTOMAKE_CONAN_INCLUDES environment variable: {}".format(aclocal))
        self.env_info.AUTOMAKE_CONAN_INCLUDES.append(aclocal)

        autopoint = microsoft.unix_path(self, os.path.join(
            self.package_folder, "bin", "autopoint"))
        self.output.info(
            "Setting AUTOPOINT environment variable: {}".format(autopoint))
        self.env_info.AUTOPOINT = autopoint

        self.env_info.GETTEXT_ROOT_UNIX = microsoft.unix_path(self,
                                                              self.package_folder)
