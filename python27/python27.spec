#%define _buildid .18

# ======================================================
# Conditionals and other variables controlling the build
# ======================================================
%bcond_with X11

%global _skip_check 1

%{!?__python_ver:%global __python_ver EMPTY}
%global __python_ver 27
%global unicode ucs4

%global _default_patch_fuzz 2

%if "%{__python_ver}" != "EMPTY"
%global main_python 0
%global python python%{__python_ver}
%global tkinter tkinter%{__python_ver}
%else
%global main_python 1
%global python python
%global tkinter tkinter
%endif

%global pybasever 2.7
%global pylibdir %{_libdir}/python%{pybasever}
%global tools_dir %{pylibdir}/Tools
%global demo_dir %{pylibdir}/Demo
%global doc_tools_dir %{pylibdir}/Doc/tools
%global dynload_dir %{pylibdir}/lib-dynload
%global site_packages %{pylibdir}/site-packages

# Python's configure script defines SOVERSION, and this is used in the Makefile
# to determine INSTSONAME, the name of the libpython DSO:
#   LDLIBRARY='libpython$(VERSION).so'
#   INSTSONAME="$LDLIBRARY".$SOVERSION
# We mirror this here in order to make it easier to add the -gdb.py hooks.
# (if these get out of sync, the payload of the libs subpackage will fail
# and halt the build)
%global py_SOVERSION 1.0
%global py_INSTSONAME_optimized libpython%{pybasever}.so.%{py_SOVERSION}
%global py_INSTSONAME_debug     libpython%{pybasever}_d.so.%{py_SOVERSION}

%global with_debug_build 0

# Disabled for now:
%global with_huntrleaks 0

%global with_gdb_hooks 1

%global with_systemtap 1

# some arches dont have valgrind so we need to disable its support on them
%ifarch %{ix86} x86_64 ppc ppc64 s390x
%global with_valgrind 1
%else
%global with_valgrind 0
%endif

# Some of the files below /usr/lib/pythonMAJOR.MINOR/test  (e.g. bad_coding.py)
# are deliberately invalid, leading to SyntaxError exceptions if they get
# byte-compiled.
#
# These errors are ignored by the normal python build, and aren't normally a
# problem in the buildroots since /usr/bin/python isn't present.
# 
# However, for the case where we're rebuilding the python srpm on a machine
# that does have python installed we need to set this to avoid
# brp-python-bytecompile treating these as fatal errors:
#
%global _python_bytecompile_errors_terminate_build 0

# We need to get a newer configure generated out of configure.in for the following
# patches:
#   patch 4 (CFLAGS)
#   patch 52 (valgrind)
#   patch 55 (systemtap)
# 
# For patch 55 (systemtap), we need to get a new header for configure to use
#
# configure.in requires autoconf-2.65, but the version in Fedora is currently
# autoconf-2.66
#
# For now, we'll generate a patch to the generated configure script and
# pyconfig.h.in on a machine that has a local copy of autoconf 2.65
#
# Instructions on obtaining such a copy can be seen at
#   http://bugs.python.org/issue7997
#
# To make it easy to regenerate the patch, this specfile can be run in two
# ways:
# (i) regenerate_autotooling_patch  0 : the normal approach: prep the
# source tree using a pre-generated patch to the "configure" script, and do a
# full build
# (ii) regenerate_autotooling_patch 1 : intended to be run on a developer's
# workstation: prep the source tree without patching configure, then rerun a
# local copy of autoconf-2.65, regenerate the patch, then exit, without doing
# the rest of the build
%global regenerate_autotooling_patch 0


# ==================
# Top-level metadata
# ==================
Summary: An interpreted, interactive, object-oriented programming language
Name: %{python}
# Remember to also rebase python-docs when changing this:
Version: 2.7.6
Release: 1%{?_buildid}%{?dist}
License: Python
Group: Development/Languages
Requires: %{python}-libs%{?_isa} = %{version}-%{release}
Provides: python-abi = %{pybasever}
Provides: python(abi) = %{pybasever}


# =======================
# Build-time requirements
# =======================

# (keep this list alphabetized)

BuildRequires: autoconf
BuildRequires: bzip2
BuildRequires: bzip2-devel
BuildRequires: db4-devel
BuildRequires: expat-devel
BuildRequires: findutils
BuildRequires: gcc-c++
BuildRequires: gdbm-devel
BuildRequires: glibc-devel
BuildRequires: gmp-devel
BuildRequires: libffi-devel
BuildRequires: ncurses-devel
BuildRequires: openssl-devel
BuildRequires: pkgconfig
BuildRequires: readline-devel
BuildRequires: sqlite-devel

%if 0%{?with_systemtap}
BuildRequires: systemtap-sdt-devel
# (this introduces a circular dependency, in that systemtap-sdt-devel's
# /usr/bin/dtrace is a python script)
%global tapsetdir      /usr/share/systemtap/tapset
%endif # with_systemtap

BuildRequires: tar
BuildRequires: tcl-devel

%if 0%{?with_valgrind}
BuildRequires: valgrind-devel
%endif

BuildRequires: zlib-devel

%if %{with X11}
BuildRequires: libX11-devel
BuildRequires: libGL-devel
BuildRequires: tix-devel
BuildRequires: tk-devel
%endif

# =======================
# Source code and patches
# =======================

Source: http://www.python.org/ftp/python/%{version}/Python-%{version}.tgz

# Work around bug 562906 until it's fixed in rpm-build by providing a fixed
# version of pythondeps.sh:
Source2: pythondeps.sh
%global __python_requires %{SOURCE2}

# Systemtap tapset to make it easier to use the systemtap static probes
# (actually a template; LIBRARY_PATH will get fixed up during install)
# Written by dmalcolm; not yet sent upstream
Source3: libpython.stp


# Example systemtap script using the tapset
# Written by wcohen, mjw, dmalcolm; not yet sent upstream
Source4: systemtap-example.stp

# Another example systemtap script that uses the tapset
# Written by dmalcolm; not yet sent upstream
Source5: pyfuntop.stp

# Supply various useful macros for building python 2 modules:
#  __python2, python2_sitelib, python2_sitearch, python2_version
Source6: macros.python2


# Modules/Setup.dist is ultimately used by the "makesetup" script to construct
# the Makefile and config.c
#
# Upstream leaves many things disabled by default, to try to make it easy as
# possible to build the code on as many platforms as possible.
#
# TODO: many modules can also now be built by setup.py after the python binary
# has been built; need to assess if we should instead build things there
#
# We patch it downstream as follows:
#   - various modules are built by default by upstream as static libraries;
#   we built them as shared libraries
#   - build the "readline" module (appears to also be handled by setup.py now)
#   - enable the build of the following modules:
#     - array arraymodule.c	# array objects
#     - cmath cmathmodule.c # -lm # complex math library functions
#     - math mathmodule.c # -lm # math library functions, e.g. sin()
#     - _struct _struct.c	# binary structure packing/unpacking
#     - time timemodule.c # -lm # time operations and variables
#     - operator operator.c	# operator.add() and similar goodies
#     - _weakref _weakref.c	# basic weak reference support
#     - _testcapi _testcapimodule.c    # Python C API test module
#     - _random _randommodule.c	# Random number generator
#     - _collections _collectionsmodule.c # Container types
#     - itertools itertoolsmodule.c
#     - strop stropmodule.c
#     - _functools _functoolsmodule.c
#     - _bisect _bisectmodule.c	# Bisection algorithms
#     - unicodedata unicodedata.c    # static Unicode character database
#     - _locale _localemodule.c
#     - fcntl fcntlmodule.c	# fcntl(2) and ioctl(2)
#     - spwd spwdmodule.c		# spwd(3) 
#     - grp grpmodule.c		# grp(3)
#     - select selectmodule.c	# select(2); not on ancient System V
#     - mmap mmapmodule.c  # Memory-mapped files
#     - _csv _csv.c  # CSV file helper
#     - _socket socketmodule.c  # Socket module helper for socket(2)
#     - _ssl _ssl.c
#     - crypt cryptmodule.c -lcrypt	# crypt(3)
#     - nis nismodule.c -lnsl	# Sun yellow pages -- not everywhere
#     - termios termios.c	# Steen Lumholt's termios module
#     - resource resource.c	# Jeremy Hylton's rlimit interface
#     - audioop audioop.c	# Operations on audio samples
#     - imageop imageop.c	# Operations on images
#     - _md5 md5module.c md5.c
#     - _sha shamodule.c
#     - _sha256 sha256module.c
#     - _sha512 sha512module.c
#     - linuxaudiodev linuxaudiodev.c
#     - timing timingmodule.c
#     - _tkinter _tkinter.c tkappinit.c
#     - dl dlmodule.c
#     - gdbm gdbmmodule.c
#     - _bsddb _bsddb.c
#     - binascii binascii.c
#     - parser parsermodule.c
#     - cStringIO cStringIO.c
#     - cPickle cPickle.c
#     - zlib zlibmodule.c
#     - _multibytecodec cjkcodecs/multibytecodec.c
#     - _codecs_cn cjkcodecs/_codecs_cn.c
#     - _codecs_hk cjkcodecs/_codecs_hk.c
#     - _codecs_iso2022 cjkcodecs/_codecs_iso2022.c
#     - _codecs_jp cjkcodecs/_codecs_jp.c
#     - _codecs_kr cjkcodecs/_codecs_kr.c
#     - _codecs_tw cjkcodecs/_codecs_tw.c
Patch0: python-2.7.1-config.patch

# Removes the "-g" option from "pydoc", for some reason; I believe
# (dmalcolm 2010-01-29) that this was introduced in this change:
# - fix pydoc (#68082)
# in 2.2.1-12 as a response to the -g option needing TkInter installed
# (Red Hat Linux 8)
# Not upstream
Patch1: Python-2.2.1-pydocnogui.patch

# Add $(CFLAGS) to the linker arguments when linking the "python" binary
# since some architectures (sparc64) need this (rhbz:199373).
# Not yet filed upstream
Patch4: python-2.5-cflags.patch

# Work around a bug in Python' gettext module relating to the "Plural-Forms"
# header (rhbz:252136)
# Related to upstream issues:
#   http://bugs.python.org/issue1448060 and http://bugs.python.org/issue1475523
# though the proposed upstream patches are, alas, different
Patch6: python-2.5.1-plural-fix.patch

# This patch was listed in the changelog as: 
#  * Fri Sep 14 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-11
#  - fix encoding of sqlite .py files to work around weird encoding problem 
#  in Turkish (#283331)
# A traceback attached to rhbz 244016 shows the problem most clearly: a
# traceback on attempting to import the sqlite module, with:
#   "SyntaxError: encoding problem: with BOM (__init__.py, line 1)"
# This seems to come from Parser/tokenizer.c:check_coding_spec
# Our patch changes two source files within sqlite3, removing the
# "coding: ISO-8859-1" specs and character E4 = U+00E4 = 
# LATIN SMALL LETTER A WITH DIAERESIS from in ghaering's surname. 
#
# It may be that the conversion of "ISO-8859-1" to "iso-8859-1" is thwarted
# by the implementation of "tolower" in the Turkish locale; see:
#   https://bugzilla.redhat.com/show_bug.cgi?id=191096#c9
# 
# TODO: Not yet sent upstream, and appears to me (dmalcolm 2010-01-29) that
# it may be papering over a symptom
Patch7: python-2.5.1-sqlite-encoding.patch

# FIXME: Lib/ctypes/util.py posix implementation defines a function
# _get_soname(f).  Upstreams's implementation of this uses objdump to read the
# SONAME from a library; we avoid this, apparently to minimize space
# requirements on the live CD:
# (rhbz:307221)
Patch10: python-2.7rc1-binutils-no-dep.patch

# Upstream as of Python 2.7.3:
#  Patch11: python-2.7rc1-codec-ascii-tolower.patch

# Add various constants to the socketmodule (rhbz#436560):
# TODO: these patches were added in 2.5.1-22 and 2.5.1-24 but appear not to
# have been sent upstream yet:
Patch13: python-2.7rc1-socketmodule-constants.patch
Patch14: python-2.7rc1-socketmodule-constants2.patch

# Remove an "-rpath $(LIBDIR)" argument from the linkage args in configure.in:
# FIXME: is this for OSF, not Linux?
Patch16: python-2.6-rpath.patch

# Fixup distutils/unixccompiler.py to remove standard library path from rpath:
# Adapted from Patch0 in ivazquez' python3000 specfile, removing usage of
# super() as it's an old-style class
Patch17: python-2.6.4-distutils-rpath.patch

# Patch setup.py so that it links against db-4.8:
Patch54: python-2.6.4-setup-db48.patch

# Systemtap support: add statically-defined probe points
# Patch based on upstream bug: http://bugs.python.org/issue4111
# fixed up by mjw and wcohen for 2.6.2, then fixed up by dmalcolm for 2.6.4
# then rewritten by mjw (attachment 390110 of rhbz 545179), then reformatted
# for 2.7rc1 by dmalcolm:
Patch55: python-2.7rc1-dtrace.patch

# "lib64 patches"
# This patch seems to be associated with bug 122304, which was
#  http://sourceforge.net/tracker/?func=detail&atid=105470&aid=931848&group_id=5470
# and is now
#  http://bugs.python.org/issue931848
# However, as it stands this patch is merely a copy of:
#  http://svn.python.org/view/python/trunk/Lib/test/test_re.py?r1=35825&r2=35824&pathrev=35825
# which is already upstream
# Earlier versions of the patch (from the "dist-pkgs" CVS repo within RH)
# contained additional changes that applied fixes to the internals of the regex
# module, but these appear to have all been applied as part of 
#  http://bugs.python.org/issue931848
Patch101: python-2.3.4-lib64-regex.patch

# Only used when "%{_lib}" == "lib64"
# Fixup various paths throughout the build and in distutils from "lib" to "lib64",
# and add the /usr/lib64/pythonMAJOR.MINOR/site-packages to sitedirs, in front of
# /usr/lib/pythonMAJOR.MINOR/site-packages
# Not upstream
Patch102: python-2.7.3-lib64.patch

# Python 2.7 split out much of the path-handling from distutils/sysconfig.py to
# a new sysconfig.py (in r77704).
# We need to make equivalent changes to that new file to ensure that the stdlib
# and platform-specific code go to /usr/lib64 not /usr/lib, on 64-bit archs:
Patch103: python-2.7-lib64-sysconfig.patch

# Patch the Makefile.pre.in so that the generated Makefile doesn't try to build
# a libpythonMAJOR.MINOR.a (bug 550692):
Patch111: python-2.7rc1-no-static-lib.patch

# Patch to support building both optimized vs debug stacks DSO ABIs, sharing
# the same .py and .pyc files, using "_d.so" to signify a debug build of an
# extension module.
#
# Based on Debian's patch for the same, 
#  http://patch-tracker.debian.org/patch/series/view/python2.6/2.6.5-2/debug-build.dpatch
# 
# (which was itself based on the upstream Windows build), but with some
# changes:
#
#   * Debian's patch to dynload_shlib.c looks for module_d.so, then module.so,
# but this can potentially find a module built against the wrong DSO ABI.  We
# instead search for just module_d.so in a debug build
#
#   * We remove this change from configure.in's build of the Makefile:
#   SO=$DEBUG_EXT.so
# so that sysconfig.py:customize_compiler stays with shared_lib_extension='.so'
# on debug builds, so that UnixCCompiler.find_library_file can find system
# libraries (otherwise "make sharedlibs" fails to find system libraries,
# erroneously looking e.g. for "libffi_d.so" rather than "libffi.so")
#
#   * We change Lib/distutils/command/build_ext.py:build_ext.get_ext_filename
# to add the _d there, when building an extension.  This way, "make sharedlibs"
# can build ctypes, by finding the sysmtem libffi.so (rather than failing to
# find "libffi_d.so"), and builds the module as _ctypes_d.so
#   
#   * Similarly, update build_ext:get_libraries handling of Py_ENABLE_SHARED by
# appending "_d" to the python library's name for the debug configuration
#
#   * We modify Modules/makesetup to add the "_d" to the generated Makefile
# rules for the various Modules/*.so targets
#
# This may introduce issues when building an extension that links directly
# against another extension (e.g. users of NumPy?), but seems more robust when
# searching for external libraries
#
#   * We don't change Lib/distutils/command/build.py: build.build_purelib to
# embed plat_specifier, leaving it as is, as pure python builds should be
# unaffected by these differences (we'll be sharing the .py and .pyc files)
#
#   * We introduce DEBUG_SUFFIX as well as DEBUG_EXT:
#     - DEBUG_EXT is used by ELF files (names and SONAMEs); it will be "_d" for
# a debug build
#     - DEBUG_SUFFIX is used by filesystem paths; it will be "-debug" for a
# debug build
#
#   Both will be empty in an optimized build.  "_d" contains characters that
# are valid ELF metadata, but this leads to various ugly filesystem paths (such
# as the include path), and DEBUG_SUFFIX allows these paths to have more natural
# names.  Changing this requires changes elsewhere in the distutils code.
#
#   * We add DEBUG_SUFFIX to PYTHON in the Makefile, so that the two
# configurations build parallel-installable binaries with different names
# ("python-debug" vs "python").
#
#   * Similarly, we add DEBUG_SUFFIX within python-config and
#  python$(VERSION)-config, so that the two configuration get different paths
#  for these.
#
#  See also patch 130 below
#
Patch112: python-2.7.3-debug-build.patch


# Add configure-time support for the COUNT_ALLOCS and CALL_PROFILE options
# described at http://svn.python.org/projects/python/trunk/Misc/SpecialBuilds.txt
# so that if they are enabled, they will be in that build's pyconfig.h, so that
# extension modules will reliably use them
Patch113: python-2.6.5-more-configuration-flags.patch

# Add flags for statvfs.f_flag to the constant list in posixmodule (i.e. "os")
# (rhbz:553020); partially upstream as http://bugs.python.org/issue7647
Patch114: python-2.7rc1-statvfs-f_flag-constants.patch

# Upstream of of Python 2.7.3:
#  Patch115: make-pydoc-more-robust-001.patch

# Upstream r79310 removed the "Modules" directory from sys.path when Python is
# running from the build directory on POSIX to fix a unit test (issue #8205).
# This seems to have broken the compileall.py done in "make install": it cannot
# find shared library extension modules at this point in the build (sys.path
# does not contain DESTDIR/usr/lib(64)/python-2.7/lib-dynload for some reason),
# leading to the build failing with:
# Traceback (most recent call last):
#   File "/home/david/rpmbuild/BUILDROOT/python-2.7-0.1.rc2.fc14.x86_64/usr/lib64/python2.7/compileall.py", line 17, in <module>
#     import struct
#   File "/home/david/rpmbuild/BUILDROOT/python-2.7-0.1.rc2.fc14.x86_64/usr/lib64/python2.7/struct.py", line 1, in <module>
#    from _struct import *
# ImportError: No module named _struct
#
# This patch adds the build Modules directory to build path.
Patch121: 00121-add-Modules-to-build-path.patch

# COUNT_ALLOCS is useful for debugging, but the upstream behaviour of always
# emitting debug info to stdout on exit is too verbose and makes it harder to
# use the debug build.  Add a "PYTHONDUMPCOUNTS" environment variable which
# must be set to enable the output on exit
# Not yet sent upstream:
Patch125: less-verbose-COUNT_ALLOCS.patch

# Fix dbm module on big-endian 64-bit
# Sent upstream as http://bugs.python.org/issue9687 (rhbz#626756)
Patch126: fix-dbm_contains-on-64bit-bigendian.patch

# Fix test_structmember on big-endian 64-bit
# Sent upstream as http://bugs.python.org/issue9960
Patch127: fix-test_structmember-on-64bit-bigendian.patch

# 2.7.1 (in r84230) added a test to test_abc which fails if python is
# configured with COUNT_ALLOCS, which is the case for our debug build
# (the COUNT_ALLOCS instrumentation keeps "C" alive).
# Not yet sent upstream
Patch128: python-2.7.1-fix_test_abc_with_COUNT_ALLOCS.patch

# Fix the --with-tsc option on ppc64, and rework it on 32-bit ppc to avoid
# aliasing violations (rhbz#698726)
# Sent upstream as http://bugs.python.org/issue12872
Patch129: python-2.7.2-tsc-on-ppc.patch

# Add "--extension-suffix" option to python-config and python-debug-config
# (rhbz#732808)
#
# This is adapted from 3.2's PEP-3149 support.
#
# Fedora's debug build has some non-standard features (see also patch 112
# above), though largely shared with Debian/Ubuntu and Windows
#
# In particular, SO in the Makefile is currently always just ".so" for our
# python 2 optimized builds, but for python 2 debug it should be '_d.so', to
# distinguish the debug vs optimized ABI, following the pattern in the above
# patch.
#
# Not yet sent upstream
Patch130: python-2.7.2-add-extension-suffix-to-python-config.patch

# The four tests in test_io built on top of check_interrupted_write_retry
# fail when built in Koji, for ppc and ppc64; for some reason, the SIGALRM
# handlers are never called, and the call to write runs to completion
# (rhbz#732998)
Patch131: python-2.7.2-disable-tests-in-test_io.patch

# This is the generated patch to "configure"; see the description of
#   %{regenerate_autotooling_patch}
# above:
Patch300: python-2.7-autotool-intermediates.patch

# Amazon build patches
Patch1000: python-2.7.2-notk.patch
Patch1001: python-2.7.2-amazon.patch

# ======================================================
# Additional metadata, and subpackages
# ======================================================

Provides: python2 = %{version}
%if %{main_python}
Obsoletes: Distutils
Provides: Distutils
Obsoletes: python2 
Obsoletes: python-elementtree <= 1.2.6
Obsoletes: python-sqlite < 2.3.2
Provides: python-sqlite = 2.3.2
Obsoletes: python-ctypes < 1.0.1
Provides: python-ctypes = 1.0.1
Obsoletes: python-hashlib < 20081120
Provides: python-hashlib = 20081120
Obsoletes: python-uuid < 1.31
Provides: python-uuid = 1.31

# python-argparse is part of python as of version 2.7
# drop this Provides in F17
# (having Obsoletes here caused problems with multilib; see rhbz#667984)
Provides:   python-argparse = %{version}-%{release}
%endif

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

URL: http://www.python.org/

%description
Python is an interpreted, interactive, object-oriented programming
language often compared to Tcl, Perl, Scheme or Java. Python includes
modules, classes, exceptions, very high level dynamic data types and
dynamic typing. Python supports interfaces to many system calls and
libraries, as well as to various windowing systems (X11, Motif, Tk,
Mac and MFC).

Programmers can write new built-in modules for Python in C or C++.
Python can be used as an extension language for applications that need
a programmable interface.

Note that documentation for Python is provided in the python-docs
package.

This package provides the "python" executable; most of the actual
implementation is within the "python-libs" package.

%package libs
Summary: Runtime libraries for Python
Group: Applications/System

# Needed for ctypes, to load libraries, worked around for Live CDs size
# Requires: binutils

%description libs
This package contains runtime libraries for use by Python:
- the libpython dynamic library, for use by applications that embed Python as
a scripting language, and by the main "python" executable
- the Python standard library

%package devel
Summary: The libraries and header files needed for Python development
Group: Development/Libraries
Requires: %{python}%{?_isa} = %{version}-%{release}
Requires: pkgconfig
# Needed here because of the migration of Makefile from -devel to the main
# package
Conflicts: %{python} < %{version}-%{release}
Provides: python2-devel = %{version}-%{release}
%if %{main_python}
Obsoletes: python2-devel
%endif

%description devel
The Python programming language's interpreter can be extended with
dynamically loaded extensions and can be embedded in other programs.
This package contains the header files and libraries needed to do
these types of tasks.

Install python-devel if you want to develop Python extensions.  The
python package will also need to be installed.  You'll probably also
want to install the python-docs package, which contains Python
documentation.

%package tools
Summary: A collection of development tools included with Python
Group: Development/Tools
Requires: %{name} = %{version}-%{release}
%if %{with X11}
Requires: %{tkinter} = %{version}-%{release}
%endif
Provides: python2-tools = %{version}
%if %{main_python}
Obsoletes: python2-tools
%endif

%description tools
This package includes several tools to help with the development of Python   
programs, including IDLE (an IDE with editing and debugging facilities), a 
color editor (pynche), and a python gettext program (pygettext.py).  

%package -n %{tkinter}
Summary: A graphical user interface for the Python scripting language
Group: Development/Languages
Requires: %{name} = %{version}-%{release}
Provides: tkinter2 = %{version}
%if %{main_python}
Obsoletes: tkinter2
%endif

%description -n %{tkinter}

The Tkinter (Tk interface) program is an graphical user interface for
the Python scripting language.

You should install the tkinter package if you'd like to use a graphical
user interface for Python programming.

%package test
Summary: The test modules from the main python package
Group: Development/Languages
Requires: %{name} = %{version}-%{release}

%description test

The test modules from the main python package: %{name}
These have been removed to save space, as they are never or almost
never used in production.

You might want to install the python-test package if you're developing python
code that uses more than just unittest and/or test_support.py.

%if 0%{?with_debug_build}
%package debug
Summary: Debug version of the Python runtime
Group: Applications/System

# The debug build is an all-in-one package version of the regular build, and
# shares the same .py/.pyc files and directories as the regular build.  Hence
# we depend on all of the subpackages of the regular build:
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-libs%{?_isa} = %{version}-%{release}
Requires: %{name}-devel%{?_isa} = %{version}-%{release}
Requires: %{name}-test%{?_isa} = %{version}-%{release}
Requires: tkinter%{?_isa} = %{version}-%{release}
Requires: %{name}-tools%{?_isa} = %{version}-%{release}

%description debug
python-debug provides a version of the Python runtime with numerous debugging
features enabled, aimed at advanced Python users, such as developers of Python
extension modules.

This version uses more memory and will be slower than the regular Python build,
but is useful for tracking down reference-counting issues, and other bugs.

The bytecodes are unchanged, so that .pyc files are compatible between the two
version of Python, but the debugging features mean that C/C++ extension modules
are ABI-incompatible with those built for the standard runtime.

It shares installation directories with the standard Python runtime, so that
.py and .pyc files can be shared.  All compiled extension modules gain a "_d"
suffix ("foo_d.so" rather than "foo.so") so that each Python implementation can
load its own extensions.
%endif # with_debug_build


# ======================================================
# The prep phase of the build:
# ======================================================

%prep
%setup -q -n Python-%{version}

%if 0%{?with_systemtap}
# Provide an example of usage of the tapset:
cp -a %{SOURCE4} .
cp -a %{SOURCE5} .
%endif # with_systemtap

# Ensure that we're using the system copy of various libraries, rather than
# copies shipped by upstream in the tarball:
#   Remove embedded copy of expat:
rm -r Modules/expat || exit 1

#   Remove embedded copy of libffi:
for SUBDIR in darwin libffi libffi_arm_wince libffi_msvc libffi_osx ; do
  rm -r Modules/_ctypes/$SUBDIR || exit 1 ;
done

#   Remove embedded copy of zlib:
rm -r Modules/zlib || exit 1

#
# Apply patches:
#
%patch0 -p1 -b .rhconfig
%patch1 -p1 -b .no_gui
%patch4 -p1 -b .cflags
%patch6 -p1 -b .plural
%patch7 -p1

# Try not disabling egg-infos, bz#414711
#patch50 -p1 -b .egginfo

%patch101 -p1 -b .lib64-regex
%if "%{_lib}" == "lib64"
%patch102 -p1 -b .lib64
%patch103 -p1 -b .lib64-sysconfig
%endif

%patch10 -p1 -b .binutils-no-dep
#patch11: upstream as of Python 2.7.3
%patch13 -p1 -b .socketmodule
%patch14 -p1 -b .socketmodule2
%patch16 -p1 -b .rpath
%patch17 -p1 -b .distutils-rpath

#patch54 -p1 -b .setup-db48
%if 0%{?with_systemtap}
%patch55 -p1 -b .systemtap
%endif

%patch111 -p1 -b .no-static-lib

%patch112 -p1 -b .debug-build

%patch113 -p1 -b .more-configuration-flags

%patch114 -p1 -b .statvfs-f-flag-constants

#patch115: upstream as of Python 2.7.3

%patch121 -p1
%patch125 -p1 -b .less-verbose-COUNT_ALLOCS
# Upstream as of 2.7.5
#%patch126 -p0 -b .fix-dbm_contains-on-64bit-bigendian
#%patch127 -p1 -b .fix-test_structmember-on-64bit-bigendian
%patch128 -p1
%patch129 -p1 -b .tsc-on-ppc
%patch130 -p1

%ifarch ppc ppc64
%patch131 -p1
%endif

# amazon patches
%if ! %{with X11}
%patch1000 -p1
%endif
%patch1001 -p1

# This shouldn't be necesarry, but is right now (2.2a3)
find -name "*~" |xargs rm -f

%if ! 0%{regenerate_autotooling_patch}
# Normally we apply the patch to "configure"
# We don't apply the patch if we're working towards regenerating it
%patch300 -p1 -b .autotool-intermediates
%endif


# ======================================================
# Configuring and building the code:
# ======================================================

%build
topdir=$(pwd)
export CFLAGS="$RPM_OPT_FLAGS -D_GNU_SOURCE -fPIC -fwrapv"
export CXXFLAGS="$RPM_OPT_FLAGS -D_GNU_SOURCE -fPIC -fwrapv"
export CPPFLAGS="$(pkg-config --cflags-only-I libffi)"
export OPT="$RPM_OPT_FLAGS -D_GNU_SOURCE -fPIC -fwrapv"
export LINKCC="gcc"
if pkg-config openssl ; then
  export CFLAGS="$CFLAGS $(pkg-config --cflags openssl)"
  export LDFLAGS="$LDFLAGS $(pkg-config --libs-only-L openssl)"
fi
# Force CC
export CC=gcc

%if 0%{regenerate_autotooling_patch}
# If enabled, this code regenerates the patch to "configure", using a
# local copy of autoconf-2.65, then exits the build
#
# The following assumes that the copy is installed to ~/autoconf-2.65/bin
# as per these instructions:
#   http://bugs.python.org/issue7997

for f in pyconfig.h.in configure ; do
    cp $f $f.autotool-intermediates ;
done

# Rerun the autotools:
PATH=~/autoconf-2.65/bin:$PATH autoconf
autoheader

# Regenerate the patch:
gendiff . .autotool-intermediates > %{PATCH300}


# Exit the build
exit 1
%endif

# Define a function, for how to perform a "build" of python for a given
# configuration:
BuildPython() {
  ConfName=$1	      
  BinaryName=$2
  SymlinkName=$3
  ExtraConfigArgs=$4
  PathFixWithThisBinary=$5

  ConfDir=build/$ConfName

  echo STARTING: BUILD OF PYTHON FOR CONFIGURATION: $ConfName - %{_bindir}/$BinaryName
  mkdir -p $ConfDir

  pushd $ConfDir

../../configure --build=%{_build} --host=%{_host} --target=%{_target_platform} \
        --prefix=%{_prefix} \
        --exec-prefix=%{_exec_prefix} \
        --sbindir=%{_sbindir} \
        --sysconfdir=%{_sysconfdir} \
        --datadir=%{_datadir} \
        --includedir=%{_includedir} \
        --libdir=%{_libdir} \
        --libexecdir=%{_libexecdir} \
        --localstatedir=%{_localstatedir} \
        --sharedstatedir=%{_sharedstatedir} \
        --mandir=%{_mandir} \
        --infodir=%{_infodir} \
  --enable-ipv6 \
  --enable-unicode=%{unicode} \
  --enable-shared \
  --with-system-ffi \
%if 0%{?with_valgrind}
  --with-valgrind \
%endif
%if 0%{?with_systemtap}
  --with-dtrace \
  --with-tapset-install-dir=%{tapsetdir} \
%endif
  --with-system-expat \
  $ExtraConfigArgs \
  %{nil}

make EXTRA_CFLAGS="$CFLAGS" %{?_smp_mflags}

# We need to fix shebang lines across the full source tree.
#
# We do this using the pathfix.py script, which requires one of the
# freshly-built Python binaries.
#
# We use the optimized python binary, and make the shebangs point at that same
# optimized python binary:
if $PathFixWithThisBinary
then
  LD_LIBRARY_PATH="$topdir/$ConfDir" ./$BinaryName \
    $topdir/Tools/scripts/pathfix.py \
      -i "%{_bindir}/env $BinaryName" \
      $topdir
fi

# Rebuild with new python
# We need a link to a versioned python in the build directory
ln -s $BinaryName $SymlinkName
LD_LIBRARY_PATH="$topdir/$ConfDir" PATH=$PATH:$topdir/$ConfDir make -s EXTRA_CFLAGS="$CFLAGS" %{?_smp_mflags}

  popd
  echo FINISHED: BUILD OF PYTHON FOR CONFIGURATION: $ConfDir
}

# Use "BuildPython" to support building with different configurations:

%if 0%{?with_debug_build}
BuildPython debug \
  python-debug \
  python%{pybasever}-debug \
%ifarch %{ix86} x86_64 ppc
  "--with-pydebug --with-tsc --with-count-allocs --with-call-profile" \
%else
  "--with-pydebug --with-count-allocs --with-call-profile" \
%endif
  false
%endif # with_debug_build

BuildPython optimized \
  python \
  python%{pybasever} \
  "" \
  true


# ======================================================
# Installing the built code:
# ======================================================

%install
topdir=$(pwd)
rm -rf %{buildroot}
mkdir -p %{buildroot}%{_prefix} %{buildroot}%{_mandir}

# Clean up patched .py files that are saved as .lib64
for f in distutils/command/install distutils/sysconfig; do
    rm -f Lib/$f.py.lib64
done

InstallPython() {

  ConfName=$1	      
  BinaryName=$2
  PyInstSoName=$3

  ConfDir=build/$ConfName

  echo STARTING: INSTALL OF PYTHON FOR CONFIGURATION: $ConfName - %{_bindir}/$BinaryName
  mkdir -p $ConfDir

  pushd $ConfDir

make install DESTDIR=%{buildroot}

# We install a collection of hooks for gdb that make it easier to debug
# executables linked against libpython (such as /usr/lib/python itself)
#
# These hooks are implemented in Python itself
#
# gdb-archer looks for them in the same path as the ELF file, with a -gdb.py suffix.
# We put them in the debuginfo package by installing them to e.g.:
#  /usr/lib/debug/usr/lib/libpython2.6.so.1.0.debug-gdb.py
# (note that the debug path is /usr/lib/debug for both 32/64 bit)
#
# See https://fedoraproject.org/wiki/Features/EasierPythonDebugging for more
# information
# 
# Initially I tried:
#  /usr/lib/libpython2.6.so.1.0-gdb.py
# but doing so generated noise when ldconfig was rerun (rhbz:562980)
#
%if 0%{?with_gdb_hooks}
DirHoldingGdbPy=%{_prefix}/lib/debug/%{_libdir}
PathOfGdbPy=$DirHoldingGdbPy/$PyInstSoName.debug-gdb.py

mkdir -p %{buildroot}$DirHoldingGdbPy
cp $topdir/Tools/gdb/libpython.py %{buildroot}$PathOfGdbPy

# Manually byte-compile the file, in case find-debuginfo.sh is run before
# brp-python-bytecompile, so that the .pyc/.pyo files are properly listed in
# the debuginfo manifest:
LD_LIBRARY_PATH="$topdir/$ConfDir" $topdir/$ConfDir/$BinaryName \
  -c "import compileall; import sys; compileall.compile_dir('%{buildroot}$DirHoldingGdbPy', ddir='$DirHoldingGdbPy')"

LD_LIBRARY_PATH="$topdir/$ConfDir" $topdir/$ConfDir/$BinaryName -O \
  -c "import compileall; import sys; compileall.compile_dir('%{buildroot}$DirHoldingGdbPy', ddir='$DirHoldingGdbPy')"
%endif # with_gdb_hooks

  popd

  echo FINISHED: INSTALL OF PYTHON FOR CONFIGURATION: $ConfName
}

# Use "InstallPython" to support building with different configurations:

# Install the "debug" build first, so that we can move some files aside
%if 0%{?with_debug_build}
InstallPython debug \
  python%{pybasever}-debug \
  %{py_INSTSONAME_debug}
%endif # with_debug_build

# Now the optimized build:
InstallPython optimized \
  python%{pybasever} \
  %{py_INSTSONAME_optimized}


# Fix the interpreter path in binaries installed by distutils 
# (which changes them by itself)
# Make sure we preserve the file permissions
for fixed in %{buildroot}%{_bindir}/pydoc; do
    sed 's,#!.*/python$,#!%{_bindir}/env python%{pybasever},' $fixed > $fixed- \
        && cat $fixed- > $fixed && rm -f $fixed-
done

# Junk, no point in putting in -test sub-pkg
rm -f %{buildroot}/%{pylibdir}/idlelib/testcode.py*

# don't include tests that are run at build time in the package
# This is documented, and used: rhbz#387401
if /bin/false; then
 # Move this to -test subpackage.
mkdir save_bits_of_test
for i in test_support.py __init__.py; do
  cp -a %{buildroot}/%{pylibdir}/test/$i save_bits_of_test
done
rm -rf %{buildroot}/%{pylibdir}/test
mkdir %{buildroot}/%{pylibdir}/test
cp -a save_bits_of_test/* %{buildroot}/%{pylibdir}/test
fi

%if %{main_python}
ln -s python2.7-debug-config %{buildroot}%{_bindir}/python-debug-config
%if 0%{?with_debug_build}
ln -s python-debug %{buildroot}%{_bindir}/python2-debug
%endif # with_debug_build
%else
mv %{buildroot}%{_bindir}/python %{buildroot}%{_bindir}/%{python}
%if 0%{?with_debug_build}
mv %{buildroot}%{_bindir}/python-debug %{buildroot}%{_bindir}/%{python}-debug
%endif # with_debug_build
#mv %{buildroot}/%{_mandir}/man1/python.1 %{buildroot}/%{_mandir}/man1/python%{pybasever}.1
%endif

# tools

mkdir -p ${RPM_BUILD_ROOT}%{site_packages}

#pynche
cat > ${RPM_BUILD_ROOT}%{_bindir}/pynche << EOF
#!/bin/bash
exec %{site_packages}/pynche/pynche
EOF
chmod 755 ${RPM_BUILD_ROOT}%{_bindir}/pynche
rm -f Tools/pynche/*.pyw
cp -r Tools/pynche \
  ${RPM_BUILD_ROOT}%{site_packages}/

cp Tools/pynche/README Tools/pynche/README.pynche

#gettext
install -m755  Tools/i18n/pygettext.py %{buildroot}%{_bindir}/
install -m755  Tools/i18n/msgfmt.py %{buildroot}%{_bindir}/

# Useful development tools
install -m755 -d %{buildroot}%{tools_dir}/scripts
install Tools/README %{buildroot}%{tools_dir}/
install Tools/scripts/*py %{buildroot}%{tools_dir}/scripts/

# Documentation tools
install -m755 -d %{buildroot}%{doc_tools_dir}
#install -m755 Doc/tools/mkhowto %{buildroot}%{doc_tools_dir}

# Useful demo scripts
install -m755 -d %{buildroot}%{demo_dir}
cp -ar Demo/* %{buildroot}%{demo_dir}

# Get rid of crap
find %{buildroot}/ -name "*~"|xargs rm -f
find %{buildroot}/ -name ".cvsignore"|xargs rm -f
find %{buildroot}/ -name "*.bat"|xargs rm -f
find . -name "*~"|xargs rm -f
find . -name ".cvsignore"|xargs rm -f
#zero length
rm -f %{buildroot}%{pylibdir}/LICENSE.txt


#make the binaries install side by side with the main python
%if !%{main_python}
pushd %{buildroot}%{_bindir}
mv idle idle%{__python_ver}
mv pynche pynche%{__python_ver}
mv pygettext.py pygettext%{__python_ver}.py
mv msgfmt.py msgfmt%{__python_ver}.py
mv smtpd.py smtpd%{__python_ver}.py
mv pydoc pydoc%{__python_ver}
mv 2to3 %{__python_ver}to3
popd
%endif

# Fix for bug #136654
rm -f %{buildroot}%{pylibdir}/email/test/data/audiotest.au %{buildroot}%{pylibdir}/test/audiotest.au

# Fix bug #143667: python should own /usr/lib/python2.x on 64-bit machines
%if "%{_lib}" == "lib64"
install -d %{buildroot}/usr/lib/python%{pybasever}/site-packages
%endif

# Make python-devel multilib-ready (bug #192747, #139911)
%global _pyconfig32_h pyconfig-32.h
%global _pyconfig64_h pyconfig-64.h

%ifarch ppc64 s390x x86_64 ia64 alpha sparc64
%global _pyconfig_h %{_pyconfig64_h}
%else
%global _pyconfig_h %{_pyconfig32_h}
%endif

%if 0%{?with_debug_build}
%global PyIncludeDirs python%{pybasever} python%{pybasever}-debug
%else
%global PyIncludeDirs python%{pybasever}
%endif

for PyIncludeDir in %{PyIncludeDirs} ; do
  mv %{buildroot}%{_includedir}/$PyIncludeDir/pyconfig.h \
     %{buildroot}%{_includedir}/$PyIncludeDir/%{_pyconfig_h}
  cat > %{buildroot}%{_includedir}/$PyIncludeDir/pyconfig.h << EOF
#include <bits/wordsize.h>

#if __WORDSIZE == 32
#include "%{_pyconfig32_h}"
#elif __WORDSIZE == 64
#include "%{_pyconfig64_h}"
#else
#error "Unknown word size"
#endif
EOF
done
ln -s ../../libpython%{pybasever}.so %{buildroot}%{pylibdir}/config/libpython%{pybasever}.so

# Fix for bug 201434: make sure distutils looks at the right pyconfig.h file
# Similar for sysconfig: sysconfig.get_config_h_filename tries to locate
# pyconfig.h so it can be parsed, and needs to do this at runtime in site.py
# when python starts up.
#
# Split this out so it goes directly to the pyconfig-32.h/pyconfig-64.h
# variants:
sed -i -e "s/'pyconfig.h'/'%{_pyconfig_h}'/" \
  %{buildroot}%{pylibdir}/distutils/sysconfig.py \
  %{buildroot}%{pylibdir}/sysconfig.py

# Install macros for rpm:
%if %{main_python}
mkdir -p %{buildroot}/%{_sysconfdir}/rpm
install -m 644 %{SOURCE6} %{buildroot}/%{_sysconfdir}/rpm
%endif

# Ensure that the curses module was linked against libncursesw.so, rather than
# libncurses.so (bug 539917)
ldd %{buildroot}/%{dynload_dir}/_curses*.so \
    | grep curses \
    | grep libncurses.so && (echo "_curses.so linked against libncurses.so" ; exit 1)

# Ensure that the debug modules are linked against the debug libpython, and
# likewise for the optimized modules and libpython:
for Module in %{buildroot}/%{dynload_dir}/*.so ; do
    case $Module in
    *_d.so)
        ldd $Module | grep %{py_INSTSONAME_optimized} &&
            (echo Debug module $Module linked against optimized %{py_INSTSONAME_optimized} ; exit 1)
            
        ;;
    *)
        ldd $Module | grep %{py_INSTSONAME_debug} &&
            (echo Optimized module $Module linked against debug %{py_INSTSONAME_optimized} ; exit 1)
        ;;
    esac
done

# fix strip errors on read only .so files
find %{buildroot}/%{dynload_dir} -name \*.so -a -not -perm -u=w -exec chmod -v u+w {} \;
find %{buildroot}/%{_libdir} -name libpython\*.so\* -a -not -perm -u=w -exec chmod -v u+w {} \;

# create pkgconfig alias
ln -s python-%{pybasever}.pc %{buildroot}%{_libdir}/pkgconfig/python%{pybasever}.pc

#
# Systemtap hooks:
#
%if 0%{?with_systemtap}
# Install a tapset for this libpython into tapsetdir, fixing up the path to the
# library:
mkdir -p %{buildroot}%{tapsetdir}
%ifarch ppc64 s390x x86_64 ia64 alpha sparc64
%global libpython_stp_optimized libpython%{pybasever}-64.stp
%global libpython_stp_debug     libpython%{pybasever}-debug-64.stp
%else
%global libpython_stp_optimized libpython%{pybasever}-32.stp
%global libpython_stp_debug     libpython%{pybasever}-debug-32.stp
%endif

sed \
   -e "s|LIBRARY_PATH|%{_libdir}/%{py_INSTSONAME_optimized}|" \
   %{SOURCE3} \
   > %{buildroot}%{tapsetdir}/%{libpython_stp_optimized}

%if 0%{?with_debug_build}
sed \
   -e "s|LIBRARY_PATH|%{_libdir}/%{py_INSTSONAME_debug}|" \
   %{SOURCE3} \
   > %{buildroot}%{tapsetdir}/%{libpython_stp_debug}
%endif # with_debug_build
%endif # with_systemtap

# fix up symlinks for packaging as non-main python
%if ! %{main_python}
rm -f %{buildroot}%{_bindir}/%{python}
ln %{buildroot}%{_bindir}/python%{pybasever} %{buildroot}%{_bindir}/%{python}
sed -i -e 's|/usr/bin/env python$|/usr/bin/env python%{pybasever}|' %{buildroot}%{_bindir}/*.py
%endif

# ======================================================
# Running the upstream test suite
# ======================================================

%check
topdir=$(pwd)
CheckPython() {
  ConfName=$1
  BinaryName=$2
  ConfDir=$(pwd)/build/$ConfName

  echo STARTING: CHECKING OF PYTHON FOR CONFIGURATION: $ConfName

  # Notes about disabled tests:
  #
  # test_argparse:
  #   fails when in a full build, but works when run standalone; seems to be
  #   http://bugs.python.org/issue9553 (needs COLUMNS=80 in the environment)
  #
  # test_distutils:
  #   fails with
  #      /usr/bin/ld: cannot find -lpython2.7
  #   in: test_build_ext (distutils.tests.test_build_ext.BuildExtTestCase)
  #       test_get_outputs (distutils.tests.test_build_ext.BuildExtTestCase)
  #
  # test_dl: 
  #   fails with:
  #     <type 'exceptions.SystemError'>: module dl requires sizeof(int) ==
  #     sizeof(long) == sizeof(char*)
  #   on 64-bit builds, and the module is deprecated in favour of ctypes
  #
  # test_gdb:
  #   very dependent on GCC version
  #
  # test_http*
  #   I've seen occasional hangs in some http tests when running the test suite
  #   inside Koji on Python 3.  For that reason I exclude them
  #
  # test_socket.py:
  #   Can fail on Koji build with:
  #     gaierror: [Errno -3] Temporary failure in name resolution
  #
  # test_urllib2
  #   Can fail on Koji build with:
  #     gaierror: [Errno -3] Temporary failure in name resolution
  #
  #
  ###########################################################################
  # TO BE INVESTIGATED:
  ###########################################################################
  # 
  # test_file:
  #   Fails in Koji with:
  #  ======================================================================
  #  FAIL: testStdin (test.test_file.COtherFileTests)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7/Lib/test/test_file.py", line 160, in testStdin
  #      self.assertRaises((IOError, ValueError), sys.stdin.seek, -1)
  #  AssertionError: (<type 'exceptions.IOError'>, <type 'exceptions.ValueError'>) not raised
  #  ======================================================================
  #  FAIL: testStdin (test.test_file.PyOtherFileTests)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7/Lib/test/test_file.py", line 160, in testStdin
  #      self.assertRaises((IOError, ValueError), sys.stdin.seek, -1)
  #  AssertionError: (<type 'exceptions.IOError'>, <type 'exceptions.ValueError'>) not raised
  #  ----------------------------------------------------------------------
  #
  # test_file2k:
  #   Fails in Koji on with:
  #  ======================================================================
  #  FAIL: testStdin (test.test_file2k.OtherFileTests)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7/Lib/test/test_file2k.py", line 211, in testStdin
  #      self.assertRaises(IOError, sys.stdin.seek, -1)
  #  AssertionError: IOError not raised
  #  ----------------------------------------------------------------------
  #
  # test_openpty:
  #   Fails in Koji, possibly due to a mock issue (rhbz#714627)
  #  ======================================================================
  #  ERROR: test (test.test_openpty.OpenptyTest)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7.2/Lib/test/test_openpty.py", line 12, in test
  #      master, slave = os.openpty()
  #  OSError: [Errno 2] No such file or directory
  #  ----------------------------------------------------------------------
  #
  # test_pty:
  #   Fails in Koji, possibly due to a mock issue (rhbz#714627)
  #  ======================================================================
  #  ERROR: test_fork (test.test_pty.PtyTest)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7.2/Lib/test/test_pty.py", line 114, in test_fork
  #      pid, master_fd = pty.fork()
  #    File "/builddir/build/BUILD/Python-2.7.2/Lib/pty.py", line 107, in fork
  #      master_fd, slave_fd = openpty()
  #    File "/builddir/build/BUILD/Python-2.7.2/Lib/pty.py", line 29, in openpty
  #      master_fd, slave_name = _open_terminal()
  #    File "/builddir/build/BUILD/Python-2.7.2/Lib/pty.py", line 70, in _open_terminal
  #      raise os.error, 'out of pty devices'
  #  OSError: out of pty devices
  #  ----------------------------------------------------------------------
  #
  # test_subprocess:
  #    Fails in Koji with:
  #  ======================================================================
  #  ERROR: test_leaking_fds_on_error (test.test_subprocess.ProcessTestCase)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7/Lib/test/test_subprocess.py", line 534, in test_leaking_fds_on_error
  #      raise c.exception
  #  OSError: [Errno 13] Permission denied
  #  ======================================================================
  #  ERROR: test_leaking_fds_on_error (test.test_subprocess.ProcessTestCaseNoPoll)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7/Lib/test/test_subprocess.py", line 534, in test_leaking_fds_on_error
  #      raise c.exception
  #  OSError: [Errno 13] Permission denied
  #  ----------------------------------------------------------------------
  #
  EXCLUDED_TESTS="test_argparse \
      test_distutils \
      test_dl \
      test_gdb \
      test_http_cookies \
      test_httplib \
      test_socket \
      test_urllib2 \
      test_file \
      test_file2k \
      test_openpty \
      test_pty \
      test_subprocess \
  %{nil}"

  #
  # Additional architecture-specific test exclusions:
  #

  # ARM-specific test exclusions (see rhbz#706253):
  # test_float:
  #   This is upstream bug: http://bugs.python.org/issue8265
  #  ======================================================================
  #  FAIL: test_from_hex (test.test_float.HexFloatTestCase)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7/Lib/test/test_float.py", line 1204, in test_from_hex
  #      self.identical(fromHex('0x0.ffffffffffffd6p-1022'), MIN-3*TINY)
  #    File "/builddir/build/BUILD/Python-2.7/Lib/test/test_float.py", line 914, in identical
  #      self.fail('%r not identical to %r' % (x, y))
  #  AssertionError: 2.2250738585072e-308 not identical to 2.2250738585071984e-308
  #  ----------------------------------------------------------------------
%ifarch %{arm}
  EXCLUDED_TESTS="$EXCLUDED_TESTS \
      test_float \
  %{nil}"
%endif


  # Sparc-specific test exclusions (see rhbz#711584):
  # test_ctypes:
  #   This is upstream bug: http://bugs.python.org/issue8314
  #   which appears to be a libffi bug
  #  ======================================================================
  #  FAIL: test_ulonglong (ctypes.test.test_callbacks.Callbacks)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "/builddir/build/BUILD/Python-2.7.1/Lib/ctypes/test/test_callbacks.py",
  #  line 72, in test_ulonglong
  #      self.check_type(c_ulonglong, 10955412242170339782)
  #    File "/builddir/build/BUILD/Python-2.7.1/Lib/ctypes/test/test_callbacks.py",
  #  line 31, in check_type
  #      self.assertEqual(result, arg)
  #  AssertionError: 10955412241121898851L != 10955412242170339782L
  #  ----------------------------------------------------------------------
%ifarch %{sparc}
  EXCLUDED_TESTS="$EXCLUDED_TESTS \
      test_ctypes \
  %{nil}"
%endif

  # Debug build shows some additional failures (to be investigated):
  #
  # test_gc:
  #  ======================================================================
  #  FAIL: test_newinstance (__main__.GCTests)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "Lib/test/test_gc.py", line 105, in test_newinstance
  #      self.assertNotEqual(gc.collect(), 0)
  #  AssertionError: 0 == 0
  #  
  #  ----------------------------------------------------------------------
  #
  # test_sys:
  #  ======================================================================
  #  FAIL: test_objecttypes (__main__.SizeofTest)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "Lib/test/test_sys.py", line 739, in test_objecttypes
  #      check(newstyleclass, s)
  #    File "Lib/test/test_sys.py", line 510, in check_sizeof
  #      self.assertEqual(result, size, msg)
  #  AssertionError: wrong size for <type 'type'>: got 960, expected 920
  #  
  #  ----------------------------------------------------------------------
  #  which is this code:
  #          # type
  #          # (PyTypeObject + PyNumberMethods +  PyMappingMethods +
  #          #  PySequenceMethods + PyBufferProcs)
  #          s = size(vh + 'P2P15Pl4PP9PP11PI') + size('41P 10P 3P 6P')
  #          class newstyleclass(object):
  #              pass
  #          check(newstyleclass, s)
  #  
  # test_weakref:
  #  ======================================================================
  #  FAIL: test_callback_in_cycle_resurrection (__main__.ReferencesTestCase)
  #  ----------------------------------------------------------------------
  #  Traceback (most recent call last):
  #    File "Lib/test/test_weakref.py", line 591, in test_callback_in_cycle_resurrection
  #      self.assertEqual(alist, ["C went away"])
  #  AssertionError: Lists differ: [] != ['C went away']
  #  
  #  Second list contains 1 additional elements.
  #  First extra element 0:
  #  C went away
  #  
  #  - []
  #  + ['C went away']
  #  
  #  ----------------------------------------------------------------------
  #
  if [ "$ConfName" = "debug"  ] ; then
    EXCLUDED_TESTS="$EXCLUDED_TESTS \
      test_gc \
      test_sys \
      test_weakref \
    %{nil}"
  fi
  
  # Note that we're running the tests using the version of the code in the
  # builddir, not in the buildroot.

  pushd $ConfDir

  EXTRATESTOPTS="--verbose"

%if 0%{?with_huntrleaks}
  # Try to detect reference leaks on debug builds.  By default this means
  # running every test 10 times (6 to stabilize, then 4 to watch):
  if [ "$ConfName" = "debug"  ] ; then
    EXTRATESTOPTS="$EXTRATESTOPTS --huntrleaks : "
  fi
%endif

  # Actually invoke regrtest.py:
  EXTRATESTOPTS="$EXTRATESTOPTS -x $EXCLUDED_TESTS" make test

  popd

  echo FINISHED: CHECKING OF PYTHON FOR CONFIGURATION: $ConfName

}

%if ! 0%{?_skip_check}
# Check each of the configurations:
%if 0%{?with_debug_build}
CheckPython \
  debug \
  python%{pybasever}-debug
%endif # with_debug_build
CheckPython \
  optimized \
  python%{pybasever}
%endif

# ======================================================
# Cleaning up
# ======================================================

%clean
rm -fr %{buildroot}


# ======================================================
# Scriptlets
# ======================================================

%post libs -p /sbin/ldconfig

%postun libs -p /sbin/ldconfig



%files
%defattr(-, root, root, -)
%doc LICENSE README
%{_bindir}/pydoc*
%{_bindir}/%{python}
%if %{main_python}
%{_bindir}/python2
%else
%exclude %{_bindir}/python2
%endif
%{_bindir}/python%{pybasever}
%{_mandir}/*/*

%files libs
%defattr(-,root,root,-)
%doc LICENSE README
%dir %{pylibdir}
%dir %{dynload_dir}
%{dynload_dir}/Python-%{version}-py%{pybasever}.egg-info
%{dynload_dir}/_bisectmodule.so
%{dynload_dir}/_bsddb.so
%{dynload_dir}/_codecs_cn.so
%{dynload_dir}/_codecs_hk.so
%{dynload_dir}/_codecs_iso2022.so
%{dynload_dir}/_codecs_jp.so
%{dynload_dir}/_codecs_kr.so
%{dynload_dir}/_codecs_tw.so
%{dynload_dir}/_collectionsmodule.so
%{dynload_dir}/_csv.so
%{dynload_dir}/_ctypes.so
%{dynload_dir}/_curses.so
%{dynload_dir}/_curses_panel.so
%{dynload_dir}/_elementtree.so
%{dynload_dir}/_functoolsmodule.so
%{dynload_dir}/_hashlib.so
%{dynload_dir}/_heapq.so
%{dynload_dir}/_hotshot.so
%{dynload_dir}/_io.so
%{dynload_dir}/_json.so
%{dynload_dir}/_localemodule.so
%{dynload_dir}/_lsprof.so
%{dynload_dir}/_md5module.so
%{dynload_dir}/_multibytecodecmodule.so
%{dynload_dir}/_multiprocessing.so
%{dynload_dir}/_randommodule.so
%{dynload_dir}/_sha256module.so
%{dynload_dir}/_sha512module.so
%{dynload_dir}/_shamodule.so
%{dynload_dir}/_socketmodule.so
%{dynload_dir}/_sqlite3.so
%{dynload_dir}/_ssl.so
%{dynload_dir}/_struct.so
%{dynload_dir}/arraymodule.so
%{dynload_dir}/audioop.so
%{dynload_dir}/binascii.so
%{dynload_dir}/bz2.so
%{dynload_dir}/cPickle.so
%{dynload_dir}/cStringIO.so
%{dynload_dir}/cmathmodule.so
%{dynload_dir}/cryptmodule.so
%{dynload_dir}/datetime.so
%{dynload_dir}/dbm.so
%{dynload_dir}/dlmodule.so
%{dynload_dir}/fcntlmodule.so
%{dynload_dir}/future_builtins.so
%{dynload_dir}/gdbmmodule.so
%{dynload_dir}/grpmodule.so
%{dynload_dir}/imageop.so
%{dynload_dir}/itertoolsmodule.so
%{dynload_dir}/linuxaudiodev.so
%{dynload_dir}/math.so
%{dynload_dir}/mmapmodule.so
%{dynload_dir}/nismodule.so
%{dynload_dir}/operator.so
%{dynload_dir}/ossaudiodev.so
%{dynload_dir}/parsermodule.so
%{dynload_dir}/pyexpat.so
%{dynload_dir}/readline.so
%{dynload_dir}/resource.so
%{dynload_dir}/selectmodule.so
%{dynload_dir}/spwdmodule.so
%{dynload_dir}/stropmodule.so
%{dynload_dir}/syslog.so
%{dynload_dir}/termios.so
%{dynload_dir}/timemodule.so
%{dynload_dir}/timingmodule.so
%{dynload_dir}/unicodedata.so
%{dynload_dir}/xxsubtype.so
%{dynload_dir}/zlibmodule.so

%dir %{site_packages}
%{site_packages}/README
%{pylibdir}/*.py*
%{pylibdir}/*.doc
%{pylibdir}/wsgiref.egg-info
%dir %{pylibdir}/bsddb
%{pylibdir}/bsddb/*.py*
%{pylibdir}/compiler
%dir %{pylibdir}/ctypes
%{pylibdir}/ctypes/*.py*
%{pylibdir}/ctypes/macholib
%{pylibdir}/curses
%dir %{pylibdir}/distutils
%{pylibdir}/distutils/*.py*
%{pylibdir}/distutils/README
%{pylibdir}/distutils/command
%exclude %{pylibdir}/distutils/command/wininst-*.exe
%dir %{pylibdir}/email
%{pylibdir}/email/*.py*
%{pylibdir}/email/mime
%{pylibdir}/encodings
%{pylibdir}/hotshot
%{pylibdir}/idlelib
%{pylibdir}/importlib
%dir %{pylibdir}/json
%{pylibdir}/json/*.py*
%{pylibdir}/lib2to3
%{pylibdir}/logging
%{pylibdir}/multiprocessing
%{pylibdir}/plat-linux2
%{pylibdir}/pydoc_data
%dir %{pylibdir}/sqlite3
%{pylibdir}/sqlite3/*.py*
%dir %{pylibdir}/test
%{pylibdir}/test/test_support.py*
%{pylibdir}/test/__init__.py*
%{pylibdir}/unittest
%{pylibdir}/wsgiref
%{pylibdir}/xml
%if "%{_lib}" == "lib64"
%attr(0755,root,root) %dir %{_prefix}/lib/python%{pybasever}
%attr(0755,root,root) %dir %{_prefix}/lib/python%{pybasever}/site-packages
%endif

# "Makefile" and the config-32/64.h file are needed by
# distutils/sysconfig.py:_init_posix(), so we include them in the libs
# package, along with their parent directories (bug 531901):
%dir %{pylibdir}/config
%{pylibdir}/config/Makefile
%dir %{_includedir}/python%{pybasever}
%{_includedir}/python%{pybasever}/%{_pyconfig_h}

%{_libdir}/%{py_INSTSONAME_optimized}
%if 0%{?with_systemtap}
%{tapsetdir}/%{libpython_stp_optimized}
%doc systemtap-example.stp pyfuntop.stp
%endif

%files devel
%defattr(-,root,root,-)
%{_libdir}/pkgconfig/python%{pybasever}.pc
%{_libdir}/pkgconfig/python-%{pybasever}.pc
%exclude %{_libdir}/pkgconfig/python.pc
%exclude %{_libdir}/pkgconfig/python2.pc
%{pylibdir}/config/*
%exclude %{pylibdir}/config/Makefile
%{pylibdir}/distutils/command/wininst-*.exe
%{_includedir}/python%{pybasever}/*.h
%exclude %{_includedir}/python%{pybasever}/%{_pyconfig_h}
%doc Misc/README.valgrind Misc/valgrind-python.supp Misc/gdbinit
%if %{main_python}
%{_bindir}/python-config
%{_bindir}/python2-config
%else
%exclude %{_bindir}/python-config
%exclude %{_bindir}/python2-config
%endif
%{_bindir}/python%{pybasever}-config
%{_libdir}/libpython%{pybasever}.so
%if %{main_python}
%config(noreplace) %{_sysconfdir}/rpm/macros.python2
%endif

%files tools
%defattr(-,root,root,755)
%doc Tools/pynche/README.pynche
%{site_packages}/pynche
%{_bindir}/smtpd*.py*
%if %{main_python}
%{_bindir}/2to3*
%else
%{_bindir}/%{__python_ver}to3
%endif
%{_bindir}/idle*
%{_bindir}/pynche*
%{_bindir}/pygettext*.py*
%{_bindir}/msgfmt*.py*
%{tools_dir}
%{demo_dir}
%{pylibdir}/Doc

%if %{with X11}
%files -n %{tkinter}
%defattr(-,root,root,755)
%{pylibdir}/lib-tk
%{dynload_dir}/_tkinter.so
%else
%exclude %{pylibdir}/lib-tk
%endif

%files test
%defattr(-, root, root, -)
%{pylibdir}/bsddb/test
%{pylibdir}/ctypes/test
%{pylibdir}/distutils/tests
%{pylibdir}/email/test
%{pylibdir}/json/tests
%{pylibdir}/sqlite3/test
%{pylibdir}/test/*
# These two are shipped in the main subpackage:
%exclude %{pylibdir}/test/test_support.py*
%exclude %{pylibdir}/test/__init__.py*
%{dynload_dir}/_ctypes_test.so
%{dynload_dir}/_testcapimodule.so


# We don't bother splitting the debug build out into further subpackages:
# if you need it, you're probably a developer.

# Hence the manifest is the combination of analogous files in the manifests of
# all of the other subpackages

%if 0%{?with_debug_build}
%files debug
%defattr(-,root,root,-)

# Analog of the core subpackage's files:
%{_bindir}/%{python}-debug
%if %{main_python}
%{_bindir}/python2-debug
%endif
%{_bindir}/python%{pybasever}-debug

# Analog of the -libs subpackage's files, with debug builds of the built-in
# "extension" modules:
%{dynload_dir}/_bisectmodule_d.so
%{dynload_dir}/_bsddb_d.so
%{dynload_dir}/_codecs_cn_d.so
%{dynload_dir}/_codecs_hk_d.so
%{dynload_dir}/_codecs_iso2022_d.so
%{dynload_dir}/_codecs_jp_d.so
%{dynload_dir}/_codecs_kr_d.so
%{dynload_dir}/_codecs_tw_d.so
%{dynload_dir}/_collectionsmodule_d.so
%{dynload_dir}/_csv_d.so
%{dynload_dir}/_ctypes_d.so
%{dynload_dir}/_curses_d.so
%{dynload_dir}/_curses_panel_d.so
%{dynload_dir}/_elementtree_d.so
%{dynload_dir}/_functoolsmodule_d.so
%{dynload_dir}/_hashlib_d.so
%{dynload_dir}/_heapq_d.so
%{dynload_dir}/_hotshot_d.so
%{dynload_dir}/_io_d.so
%{dynload_dir}/_json_d.so
%{dynload_dir}/_localemodule_d.so
%{dynload_dir}/_lsprof_d.so
%{dynload_dir}/_md5module_d.so
%{dynload_dir}/_multibytecodecmodule_d.so
%{dynload_dir}/_multiprocessing_d.so
%{dynload_dir}/_randommodule_d.so
%{dynload_dir}/_sha256module_d.so
%{dynload_dir}/_sha512module_d.so
%{dynload_dir}/_shamodule_d.so
%{dynload_dir}/_socketmodule_d.so
%{dynload_dir}/_sqlite3_d.so
%{dynload_dir}/_ssl_d.so
%{dynload_dir}/_struct_d.so
%{dynload_dir}/arraymodule_d.so
%{dynload_dir}/audioop_d.so
%{dynload_dir}/binascii_d.so
%{dynload_dir}/bz2_d.so
%{dynload_dir}/cPickle_d.so
%{dynload_dir}/cStringIO_d.so
%{dynload_dir}/cmathmodule_d.so
%{dynload_dir}/cryptmodule_d.so
%{dynload_dir}/datetime_d.so
%{dynload_dir}/dbm_d.so
%{dynload_dir}/dlmodule_d.so
%{dynload_dir}/fcntlmodule_d.so
%{dynload_dir}/future_builtins_d.so
%{dynload_dir}/gdbmmodule_d.so
%{dynload_dir}/grpmodule_d.so
%{dynload_dir}/imageop_d.so
%{dynload_dir}/itertoolsmodule_d.so
%{dynload_dir}/linuxaudiodev_d.so
%{dynload_dir}/math_d.so
%{dynload_dir}/mmapmodule_d.so
%{dynload_dir}/nismodule_d.so
%{dynload_dir}/operator_d.so
%{dynload_dir}/ossaudiodev_d.so
%{dynload_dir}/parsermodule_d.so
%{dynload_dir}/pyexpat_d.so
%{dynload_dir}/readline_d.so
%{dynload_dir}/resource_d.so
%{dynload_dir}/selectmodule_d.so
%{dynload_dir}/spwdmodule_d.so
%{dynload_dir}/stropmodule_d.so
%{dynload_dir}/syslog_d.so
%{dynload_dir}/termios_d.so
%{dynload_dir}/timemodule_d.so
%{dynload_dir}/timingmodule_d.so
%{dynload_dir}/unicodedata_d.so
%{dynload_dir}/xxsubtype_d.so
%{dynload_dir}/zlibmodule_d.so

# No need to split things out the "Makefile" and the config-32/64.h file as we
# do for the regular build above (bug 531901), since they're all in one package
# now; they're listed below, under "-devel":

%{_libdir}/%{py_INSTSONAME_debug}
%if 0%{?with_systemtap}
%{tapsetdir}/%{libpython_stp_debug}
%endif

# Analog of the -devel subpackage's files:
%dir %{pylibdir}/config-debug
%{pylibdir}/config-debug/*
%{_includedir}/python%{pybasever}-debug/*.h
%if %{main_python}
%{_bindir}/python-debug-config
%endif
%{_bindir}/python%{pybasever}-debug-config
%{_libdir}/libpython%{pybasever}_d.so

# Analog of the -tools subpackage's files:
#  None for now; we could build precanned versions that have the appropriate
# shebang if needed

# Analog  of the tkinter subpackage's files:
%{dynload_dir}/_tkinter_d.so

# Analog  of the -test subpackage's files:
%{dynload_dir}/_ctypes_test_d.so
%{dynload_dir}/_testcapimodule_d.so

%else
%exclude /usr/lib/debug/usr/*/*
%endif # with_debug_build


# We put the debug-gdb.py file inside /usr/lib/debug to avoid noise from
# ldconfig (rhbz:562980).
# 
# The /usr/lib/rpm/redhat/macros defines %__debug_package to use
# debugfiles.list, and it appears that everything below /usr/lib/debug and
# (/usr/src/debug) gets added to this file (via LISTFILES) in
# /usr/lib/rpm/find-debuginfo.sh
# 
# Hence by installing it below /usr/lib/debug we ensure it is added to the
# -debuginfo subpackage
# (if it doesn't, then the rpmbuild ought to fail since the debug-gdb.py 
# payload file would be unpackaged)


# ======================================================
# Finally, the changelog:
# ======================================================

%changelog
* Fri May 18 2012 Cristian Gafton <gafton@amazon.com>
- import source package F16/python-2.7.3-1.fc16
- rebase to 2.7.3 for security updates and bug fixes.

* Fri Apr 13 2012 David Malcolm <dmalcolm@redhat.com> - 2.7.3-1
- 2.7.3; refresh patches 102 (lib64) and 112 (debug build); revise patch 127
(test_structmember); drop upstream patches 11 (tolower) and 115 (pydoc
robustness); add python2.pc to python-devel; regenerate the autotool
intermediates patch (patch 300)

* Mon Mar 26 2012 Cristian Gafton <gafton@amazon.com>
- rename 2to3 to avoid conflict with main python

* Tue Mar 6 2012 Cristian Gafton <gafton@amazon.com>
- alias python-M.m.pc to pythonM.m.pc for pkgconfig files
- exclude unversioned python.pc from the devel package

* Mon Feb 20 2012 Andrew Jorgensen <ajorgens@amazon.com>
- Conditionalize dependency on tkinter

* Sat Feb 18 2012 Cristian Gafton <gafton@amazon.com>
- re-enable tests during build
- only install the macros.python2 file if building as the main python on the system
- fix /usr/bin/strip complaining about read only .so files....
- fix for building as a non-main python
- fix attempts by upstream to redefine macros after they're used by rpm to create the script for building....
- disable forced Berkeley DB version require update
- add support for skipping make check for devel builds
- conditionalize X11/Tk/tix support

* Fri Feb 17 2012 Cristian Gafton <gafton@amazon.com>
- setup for building as an alternate
- import source package F16/python-2.7.2-5.2.fc16

* Wed Oct 26 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.7.2-5.2
- Rebuilt for glibc bug#747377

* Thu Sep  1 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.2-4.2
- run selftests with "--verbose"
- disable parts of test_io on ppc (rhbz#732998)
- add --extension-suffix option to python-config (patch 130; rhbz#732808)
- reenable and fix the --with-tsc option on ppc64, and rework it on 32-bit
ppc to avoid aliasing violations (patch 129; rhbz#698726)
- add rpm macros file (rhbz#731800)

* Tue Aug 23 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.2-4.1
- don't use --with-tsc on ppc64 debug builds (rhbz#698726)

* Fri Jul  8 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.2-4
- cleanup of BuildRequires; add comment headings to specfile sections

* Wed Jun 22 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.2-3
- reorganize test exclusions (test_openpty and test_pty seem to be failing on
every arch, not just the explicitly-listed ones)

* Mon Jun 13 2011 Dan Horák <dan[at]danny.cz> - 2.7.2-2
- add s390(x) excluded tests

* Mon Jun 13 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.2-1
- 2.7.2; drop upstreamed patches: patch 122 (parallel make fix), patch 124
(test_commands and SELinux), patch 130 (ppc preprocessor macro in debug
build); patch 131 (decimal in Turkish locale); regenerate the autotool
intermediates patch (patch 300)

* Tue Jun 07 2011 Dennis Gilmore <dennis@ausil.us> - 2.7.1-9
- fix sparc building by excluding failing tests RHBZ#711584

* Mon May 23 2011 Peter Robinson <pbrobinson@gmail.com> - 2.7.1-8
- fix compile on ARM by excluding failing tests on arm - RHBZ #706253

* Tue Apr 12 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.1-7
- fix "import decimal" in the Turkish locale (patch 131; rhbz#694928)

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.7.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Fri Jan  21 2011 Toshio Kuratomi <toshio@fedoraproject.org> - 2.7.1-5
- Switch from setting OPT to setting EXTRA_CFLAGS so we don't overwrite the
  DNDEBUG flag

* Fri Jan  7 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.1-4
- for now, drop "obsoletes" of python-argparse, since it interracts badly with
multilib (rhbz#667984)

* Fri Jan  7 2011 Thomas Spura <tomspur@fedoraproject.org> - 2.7.1-3
- obsolete/provide python-argparse (new in 2.7)

* Thu Jan  6 2011 David Malcolm <dmalcolm@redhat.com> - 2.7.1-2
- fix the ppc build of the debug configuration (patch 130; rhbz#661510)

* Thu Dec 23 2010 David Malcolm <dmalcolm@redhat.com> - 2.7.1-1
- 2.7.1, reworking patch 0 (config), patch 102 (lib64); drop upstream
patch 56 (cfgparse), patch 110 (ctypes/SELinux/noexecmem), patch 119 (expat
compat), patch 123 (2to3 on "from itertools import *")
- fix test_abc's test_cache_leak in the debug build (patch 128)
- drop _weakref.so from manifest (_weakref became a core module in r84230)

* Wed Sep 29 2010 jkeating - 2.7-13
- Rebuilt for gcc bug 634757

* Mon Sep 27 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-12
- fix test_structmember on 64bit-bigendian (patch 127)

* Fri Sep 24 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-11
- fix dbm_contains on 64bit-bigendian (patch 126; rhbz#626756)

* Thu Sep 16 2010 Toshio Kuratomi <toshio@fedoraproject.org> - 2.7-10
- backport a patch to fix a change in behaviour in configparse.

* Thu Sep  9 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-9
- move most of the payload of the core package to the libs subpackage, given
that the libs aren't meaningfully usable without the standard libraries

* Wed Aug 18 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-8
- add %%check section
- update lib64 patch (patch 102) to fix expected output in test_site.py on
64-bit systems
- patch test_commands.py to work with SELinux (patch 124)
- patch the debug build's usage of COUNT_ALLOCS to be less verbose (patch 125)

* Mon Jul 26 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-7
- fixup missing -lcrypt to "crypt" module in config patch (patch 0)

* Mon Jul 26 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-6
- re-enable systemtap
- cherrypick upstream patch to 2to3 for "from itertools import *"
traceback (patch 123)

* Thu Jul 22 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-5
- disable systemtap for now (dtrace is failing on startup due to the bug
mentioned in 2.7-4)
- provide relative path to python binary when running pathfix.py
- fix parallel make (patch 122)

* Thu Jul 22 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-4
- fix reference to pyconfig.h in sysconfig that led to failure on startup if
python-devel was not installed

* Thu Jul  8 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-3
- add patch to fixup the new sysconfig.py for our multilib support on
64-bit (patch 103)

* Thu Jul  8 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-2
- add machinery for regenerating the "configure" script in the face of
mismatching autoconf versions (patch 300)

* Tue Jul  6 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-1
- 2.7 final; drop alphatag
- drop patch 117 (upstream), patch 120 (upstreamed)
- fix the commented-out __python_ver from 26 to 27

* Tue Jun 22 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-0.1.rc2
- 2.7rc2
- revert r79310 (patch 121)
- remove modulator: upstream removed it in r78338
- rename mathmodule(_d).so to math(_d).so in manifests (appears to be changed
by r76861)
- _bytesio(_d).so and _filesio(_d).so were consolidated into _io(_d).so in
r73394 (upstream issue 6215)
- use the gdb hooks from the upstream tarball, rather than keeping our own
copy. The upstream version has some whitespace changes, a new write_repr for
unicode objects, and various bulletproofings for being run on older gdbs

* Tue Jun 22 2010 David Malcolm <dmalcolm@redhat.com> - 2.7-0.1.rc1
- 2.7rc1:
  - rework patches to apply against 2.7 (which among other changes has had a
whitespace cleanup of the .c code): .rhconfig (patch0), .binutils-no-dep
(patch10), .ascii-tolower (patch11), .socketmodule (patch13), .socketmodule2
(patch14), .systemtap (patch55), .lib64 (patch102), .selinux (patch110),
.no-static-lib (patch111), .debug-build (patch112), .statvfs-f-flag-constants
(patch114), ..CVE-2010-2089 (patch117)
  - drop upstream patches: .expat (patch3), .brprpm (patch51), .valgrind
(patch52), .db48 (patch53), .CVE-2010-1634 (patch 116), .CVE-2008-5983 (patch
118)

* Tue Jun 22 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-17
- Stop python bailing out with an assertion failure when UnicodeDecodeErrors
occur on very large buffers (patch 120, upstream issue 9058)

* Mon Jun 21 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-16
- Fix an incompatibility between pyexpat and the system expat-2.0.1 that led to
a segfault running test_pyexpat.py (patch 119; upstream issue 9054)

* Tue Jun  8 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-15
- add a flag to make it easy to turn off the debug build when troubleshooting
the rpm build

* Sat Jun  5 2010 Dan Horák <dan[at]danny.cz> - 2.6.5-14
- reading the timestamp counter is available only on some arches (see Python/ceval.c)
- disable --with-valgrind on s390(x) arches

* Fri Jun  4 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-13
- ensure that the compiler is invoked with "-fwrapv" (rhbz#594819)
- CVE-2010-1634: fix various integer overflow checks in the audioop
module (patch 116)
- CVE-2010-2089: further checks within the audioop module (patch 117)
- CVE-2008-5983: the new PySys_SetArgvEx entry point from r81399 (patch 118)

* Thu May 27 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-12
- make "pydoc -k" more robust in the face of broken modules (rhbz:461419, patch115)

* Wed May 26 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-11
- add flags for statvfs.f_flag to the constant list in posixmodule (i.e. "os")
(patch 114)

* Tue May 25 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-10
- add configure-time support for COUNT_ALLOCS and CALL_PROFILE debug options
(patch 113); enable them and the WITH_TSC option within the debug build

* Tue May 18 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-9
- build and install two different configurations of Python: debug and standard,
packaging the debug build in a new "python-debug" subpackage (patch 112)

* Tue May  4 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-8
- don't delete wsgiref.egg-info (rhbz:588426)

* Mon Apr 26 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-7
- disable --with-valgrind on sparc arches

* Mon Apr 12 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-6
- move the "bdist_wininst" command's template .exe files from the core package
to the devel subpackage, to save space (rhbz:525469)
- fix stray doublelisting of config directory wildcard in devel subpackage

* Wed Mar 31 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-5
- update python-gdb.py from v4 to v5 (improving performance and stability,
adding commands)

* Thu Mar 25 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-4
- update python-gdb.py from v3 to v4 (fixing infinite recursion on reference
cycles and tracebacks on bytes 0x80-0xff in strings, adding handlers for sets
and exceptions)

* Wed Mar 24 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-3
- refresh gdb hooks to v3 (reworking how they are packaged)

* Mon Mar 22 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-2
- remove unnecessary arch-conditionality for patch 101

* Fri Mar 19 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.5-1
- update to 2.6.5: http://www.python.org/download/releases/2.6.5/
- replace our patch to compile against db4.8 with a patch from
upstream (patch 53, from r78974); update patch 54 since part of it is now in
that upstream patch
- update patch 110 so that it still applies in the face of upstream r78380

* Tue Mar 16 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-23
- fixup distutils/unixccompiler.py to remove standard library path from
rpath (patch 17)
- delete DOS batch files

* Fri Mar 12 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-22
- add pyfuntop.stp; allow systemtap support to be disabled
- remove trailing period from tkinter summary
- don't own /usr/bin/python-config if you're not the main python

* Thu Mar 11 2010 Marcela Mašláňová <mmaslano@redhat.com> - 2.6.4-21
- rebuild with new gdbm

* Thu Feb 11 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-20
- avoid having the "test" subdirectory and the files within it that are in the
core subpackage also be owned by the test subpackage (rhbz:467588)

* Wed Feb 10 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-19
- revise the systemtap patch (patch 55:python-2.6.4-dtrace.patch) to the
new version by mjw in attachment 390110 of rhbz:545179, as this should
eliminate the performance penalty for the case where the probes aren't in
use, and eliminate all architecture-specific code (rhbz:563541; except on
sparc)

* Tue Feb  9 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-18
- add a systemtap tapset defining "python.function.entry" and
"python.function.return" to make it easy to use the static probepoint within
Python; add an example of using the tapset to the docs

* Tue Feb  9 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-17
- add systemtap static probes (wcohen; patch 55; rh bug #545179)
- update some comments in specfile relating to gdb work
- manually byte-compile the gdb.py file with the freshly-built python to ensure
that .pyx and .pyo files make it into the debuginfo manifest if they are later
byte-compiled after find-debuginfo.sh is run

* Mon Feb  8 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-16
- move the -gdb.py file from %%{_libdir}/INSTSONAME-gdb.py to
%%{_prefix}/lib/debug/%%{_libdir}/INSTSONAME.debug-gdb.py to avoid noise from
ldconfig (bug 562980), and which should also ensure it becomes part of the
debuginfo subpackage, rather than the libs subpackage
- introduce %%{py_SOVERSION} and %%{py_INSTSONAME} to reflect the upstream
configure script, and to avoid fragile scripts that try to figure this out
dynamically (e.g. for the -gdb.py change)

* Mon Feb  8 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-15
- work around bug 562906 by supplying a fixed version of pythondeps.sh
- set %%{_python_bytecompile_errors_terminate_build} to 0 to prevent the broken
test files from killing the build on buildroots where python is installed

* Fri Feb  5 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-14
- add gdb hooks for easier debugging

* Fri Jan 29 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-13
- document all patches, and remove the commented-out ones

* Tue Jan 26 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-12
- Address some of the issues identified in package review (bug 226342):
  - update libs requirement on base package to use %%{name} for consistency's
sake
  - convert from backticks to $() syntax throughout
  - wrap value of LD_LIBRARY_PATH in quotes
  - convert "/usr/bin/find" requirement to "findutils"
  - remove trailing periods from summaries of -devel and -tools subpackages
  - fix spelling mistake in description of -test subpackage
  - convert usage of $$RPM_BUILD_ROOT to %%{buildroot} throughout, for
stylistic consistency
  - supply dirmode arguments to defattr directives

* Mon Jan 25 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-11
- update python-2.6.2-config.patch to remove downstream customization of build
of pyexpat and elementtree modules
- add patch adapted from upstream (patch 3) to add support for building against
system expat; add --with-system-expat to "configure" invocation
- remove embedded copy of expat from source tree during "prep"

* Mon Jan 25 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-10
- introduce macros for 3 directories, replacing expanded references throughout:
%%{pylibdir}, %%{dynload_dir}, %%{site_packages}
- explicitly list all lib-dynload files, rather than dynamically gathering the
payload into a temporary text file, so that we can be sure what we are
shipping; remove now-redundant testing for presence of certain .so files
- remove embedded copy of zlib from source tree before building

* Mon Jan 25 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-9
- change python-2.6.2-config.patch to remove our downstream change to curses
configuration in Modules/Setup.dist, so that the curses modules are built using
setup.py with the downstream default (linking against libncursesw.so, rather
than libncurses.so), rather than within the Makefile; add a test to %%install
to verify the dso files that the curses module is linked against the correct
DSO (bug 539917; changes _cursesmodule.so -> _curses.so)

* Fri Jan 22 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-8
- rebuild (bug 556975)

* Wed Jan 20 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-7
- move lib2to3 from -tools subpackage to main package (bug 556667)

* Mon Jan 18 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-6
- patch Makefile.pre.in to avoid building static library (patch111, bug 556092)
- split up the "configure" invocation flags onto individual lines

* Fri Jan 15 2010 David Malcolm <dmalcolm@redhat.com> - 2.6.4-5
- replace usage of %%define with %%global
- use the %%{_isa} macro to ensure that the python-devel dependency on python
is for the correct multilib arch (#555943)
- delete bundled copy of libffi to make sure we use the system one
- replace references to /usr with %%{_prefix}; replace references to
/usr/include with %%{_includedir}

* Wed Dec 16 2009 David Malcolm <dmalcolm@redhat.com> - 2.6.4-4
- automatically disable arena allocator when run under valgrind (upstream
issue 2422; patch 52)
- add patch from Josh Boyer containing diff against upstream PyBSDDB to make
the bsddb module compile against db-4.8 (patch 53, #544275); bump the necessary
version of db4-devel to 4.8
- patch setup.py so that it searches for db-4.8, and enable debug output for
said search; make Setup.dist use db-4.8 (patch 54)

* Thu Nov 12 2009 David Malcolm <dmalcolm@redhat.com> - 2.6.4-3
- fixup the build when __python_ver is set (Zach Sadecki; bug 533989); use
pybasever in the files section

* Thu Oct 29 2009 David Malcolm <dmalcolm@redhat.com> - 2.6.4-2
- "Makefile" and the config-32/64.h file are needed by distutils/sysconfig.py
_init_posix(), so we include them in the core package, along with their parent
directories (bug 531901)

* Mon Oct 26 2009 David Malcolm <dmalcolm@redhat.com> - 2.6.4-1
- Update to 2.6.4

* Fri Aug 21 2009 Tomas Mraz <tmraz@redhat.com> - 2.6.2-2
- rebuilt with new openssl

* Mon Jul 27 2009 James Antill <james.antill@redhat.com> - 2.6.2-1
- Update to 2.6.2

* Sun Jul 26 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Sat Jul 4 2009 Jonathan Steffan <jsteffan@fedoraproject.org> - 2.6-10
- Move python-config to devel subpackage (#506153)
- Update BuildRoot for new standard

* Sun Jun 28 2009 Jonathan Steffan <jsteffan@fedoraproject.org> - 2.6-9
- Update python-tools description (#448940)

* Wed Apr 15 2009 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> 2.6-8
- Replace python-hashlib and python-uuid (#484715)

* Tue Mar 17 2009 James Antill <james@fedoraproject.org> - 2.6-7
- Use system libffi
- Resolves: bug#490573
- Fix SELinux execmem problems
- Resolves: bug#488396

* Thu Feb 26 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Fri Jan 16 2009 Tomas Mraz <tmraz@redhat.com> - 2.6-4
- rebuild with new openssl

* Tue Jan  6 2009 James Antill <james.antill@redhat.com> - 2.6-3
- Fix distutils generated rpms.
- Resolves: bug#236535

* Wed Dec 10 2008 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> - 2.6-2
- Enable -lcrypt for cryptmodule

* Fri Nov 28 2008 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> - 2.6-1
- Update to 2.6

* Tue Sep 30 2008 James Antill <james.antill@redhat.com> - 2.5.2-1
- Move to 2.5.2
- Fix CVE-2008-2316 hashlib overflow.

* Thu Jul 17 2008 Jeremy Katz <katzj@redhat.com> - 2.5.1-30
- Fix up the build for new rpm
- And actually build against db4-4.7 (#455170)

* Thu Jul 10 2008 Tom "spot" Callaway <tcallawa@redhat.com> - 2.5.1-27
- fix license tag
- enable support for db4-4.7

* Sun Jun 15 2008 James Antill <jantill@redhat.com> - 2.5.1-26
- Fix sporadic listdir problem
- Resolves: bug#451494

* Mon Apr  7 2008 James Antill <jantill@redhat.com> - 2.5.1-25
- Rebuild to re-gen autoconf file due to glibc change.
- Resolves: bug#441003

* Tue Mar 25 2008 James Antill <jantill@redhat.com> - 2.5.1-24
- Add more constants to socketmodule

* Sat Mar  8 2008 James Antill <jantill@redhat.com> - 2.5.1-22
- Add constants to socketmodule
- Resolves: bug#436560

* Tue Feb 19 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 2.5.1-22
- Autorebuild for GCC 4.3

* Sun Jan 13 2008 Tom "spot" Callaway <tcallawa@redhat.com> - 2.5.1-21
- rebuild for new tk in rawhide

* Mon Jan  7 2008 James Antill <jantill@redhat.com> - 2.5.1-20
- Add valgrind support files, as doc, to python-devel
- Relates: rhbz#418621
- Add new API from 2.6, set_wakeup_fd ... use at own risk, presumably won't
- change but I have no control to guarantee that.
- Resolves: rhbz#427794
- Add gdbinit support file, as doc, to python-devel

* Fri Jan  4 2008 Tom "spot" Callaway <tcallawa@redhat.com> - 2.5.1-19
- rebuild for new tcl/tk in rawhide

* Fri Dec  7 2007 James Antill <jantill@redhat.com> - 2.5.1-18
- Create a python-test sub-module, over 3MB of stuff noone wants.
- Don't remove egginfo files, try this see what happens ... may revert.
- Resolves: rhbz#414711

* Mon Dec  3 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-17
- rebuild for new libssl

* Fri Nov 30 2007 James Antill <jantill@redhat.com> - 2.5.1-16
- Fix pyconfig.h comment typo.
- Add back test_support.py and the __init__.py file.
- Resolves: rhbz#387401

* Tue Oct 30 2007 James Antill <jantill@redhat.com> - 2.5.1-15
- Do codec lowercase in C Locale.
- Resolves: 207134 191096
- Fix stupid namespacing in pysqlite, minimal upgrade to 2.3.3 pysqlite
- Resolves: 263221

* Wed Oct 24 2007 James Antill <jantill@redhat.com> - 2.5.1-14
- Remove bintuils dep. for live CD ... add work around for ctypes

* Mon Oct 22 2007 James Antill <jantill@redhat.com> - 2.5.1-13
- Add tix buildprereq
- Add tkinter patch
- Resolves: #281751
- Fix ctypes loading of libraries, add requires on binutils
- Resolves: #307221
- Possible fix for CVE-2007-4965 possible exploitable integer overflow
- Resolves: #295971

* Tue Oct 16 2007 Mike Bonnet <mikeb@redhat.com> - 2.5.1-12
- fix marshalling of objects in xmlrpclib (python bug #1739842)

* Fri Sep 14 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-11
- fix encoding of sqlite .py files to work around weird encoding problem 
  in Turkish (#283331)

* Mon Sep 10 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-10
- work around problems with multi-line plural specification (#252136)

* Tue Aug 28 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-9
- rebuild against new expat

* Tue Aug 14 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-8
- build against db4.6

* Tue Aug 14 2007 Dennis Gilmore <dennis@ausil.us> - 2.5.1-7
- add sparc64 to the list of archs for _pyconfig64_h

* Fri Aug 10 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-6
- fix ctypes again on some arches (Hans de Goede, #251637)

* Fri Jul  6 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-5
- link curses modules with ncursesw (#246385)

* Wed Jun 27 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-4
- fix _elementtree.so build (#245703)
- ensure that extension modules we expect are actually built rather than 
  having them silently fall out of the package

* Tue Jun 26 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-3
- link with system expat (#245703)

* Thu Jun 21 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-2
- rebuild to take advantage of hardlinking between identical pyc/pyo files

* Thu May 31 2007 Jeremy Katz <katzj@redhat.com> - 2.5.1-1
- update to python 2.5.1

* Mon Mar 19 2007 Jeremy Katz <katzj@redhat.com> - 2.5.3-12
- fix alpha build (#231961)

* Tue Feb 13 2007 Jeremy Katz <katzj@redhat.com> - 2.5.3-11
- tcl/tk was reverted; rebuild again

* Thu Feb  1 2007 Jeremy Katz <katzj@redhat.com> - 2.5.3-10
- rebuild for new tcl/tk

* Tue Jan 16 2007 Miroslav Lichvar <mlichvar@redhat.com> - 2.5.3-9
- link with ncurses

* Sat Jan  6 2007 Jeremy Katz <katzj@redhat.com> - 2.5.3-8
- fix extensions to use shared libpython (#219564)
- all 64bit platforms need the regex fix (#122304)

* Wed Jan  3 2007 Jeremy Katz <katzj@redhat.com> - 2.5.3-7
- fix ctypes to not require execstack (#220669)

* Fri Dec 15 2006 Jeremy Katz <katzj@redhat.com> - 2.5.3-6
- don't link against compat-db (Robert Scheck)

* Wed Dec 13 2006 Jarod Wilson <jwilson@redhat.com> - 2.5.3-5
- fix invalid assert in debug mode (upstream changeset 52622)

* Tue Dec 12 2006 Jeremy Katz <katzj@redhat.com> - 2.5.3-4
- obsolete/provide python-ctypes (#219256)

* Mon Dec 11 2006 Jeremy Katz <katzj@redhat.com> - 2.5.3-3
- fix atexit traceback with failed syslog logger (#218214)
- split libpython into python-libs subpackage for multilib apps 
  embedding python interpreters

* Wed Dec  6 2006 Jeremy Katz <katzj@redhat.com> - 2.5.3-2
- disable installation of .egg-info files for now

* Tue Dec  5 2006 Jeremy Katz <katzj@redhat.com>
- support db 4.5
- obsolete python-elementtree; since it requires some code tweaks, don't 
  provide it
- obsolete old python-sqlite; provide the version that's actually included

* Mon Oct 30 2006 Jeremy Katz <katzj@redhat.com>
- fix _md5 and _sha modules (Robert Sheck)
- no longer provide optik compat; it's been a couple of years now
- no longer provide the old shm module; if this is still needed, let's 
  build it separately
- no longer provide japanese codecs; should be a separate package

* Mon Oct 23 2006 Jeremy Katz <katzj@redhat.com> - 2.5-0
- update to 2.5.0 final

* Fri Aug 18 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.99.c1
- Updated to 2.5c1. Merged fixes from FC6 too:
- Fixed bug #199373 (on some platforms CFLAGS is needed when linking)
- Fixed bug #198971 (case conversion not locale safe in logging library)
- Verified bug #201434 (distutils.sysconfig is confused by the change to make
  python-devel multilib friendly) is fixed upstream

* Sun Jul 16 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.99.b2
- Updated to 2.5b2 (which for comparison reasons is re-labeled 2.4.99.b2)

* Fri Jun 23 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.99.b1
- Updated to 2.5b1 (which for comparison reasons is re-labeled 2.4.99.b1)

* Tue Jun 13 2006 Jeremy Katz <katzj@redhat.com> - 2.4.3-11.FC6
- and fix it for real

* Tue Jun 13 2006 Jeremy Katz <katzj@redhat.com> - 2.4.3-10.FC6
- fix python-devel on ia64

* Tue Jun 13 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-9
- Fixed python-devel to be multilib friendly (bug #192747, #139911)

* Tue Jun 13 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-8
- Only copying mkhowto from the Docs - we don't need perl dependencies from
  python-tools.

* Mon Jun 12 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-7
- Fixed bug #121198 (webbrowser.py should use the user's preferences first)

* Mon Jun 12 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-6
- Fixed bug #192592 (too aggressive assertion fails) - SF#1257960
- Fixed bug #167468 (Doc/tools not included) - added in the python-tools package

* Thu Jun  8 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-5
- Fixed bug #193484 (added pydoc in the main package)

* Mon Jun  5 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-4
- Added dist in the release

* Mon May 15 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-3
- rebuilt to fix broken libX11 dependency

* Wed Apr 12 2006 Jeremy Katz <katzj@redhat.com> - 2.4.3-2
- rebuild with new gcc to fix #188649

* Thu Apr  6 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-1
- Updated to 2.4.3

* Fri Feb 10 2006 Jesse Keating <jkeating@redhat.com> - 2.4.2-3.2.1
- bump again for double-long bug on ppc(64)

* Fri Feb 10 2006 Mihai Ibanescu <misa@redhat.com> - 2.4.3-3.2
- rebuilt for newer tix

* Tue Feb 07 2006 Jesse Keating <jkeating@redhat.com> - 2.4.2-3.1
- rebuilt for new gcc4.1 snapshot and glibc changes

* Fri Jan 20 2006 Mihai Ibanescu <misa@redhat.com> 2.4.2-3
- fixed #136654 for another instance of audiotest.au

* Fri Dec 09 2005 Jesse Keating <jkeating@redhat.com>
- rebuilt

* Sat Nov 19 2005 Bill Nottingham <notting@redhat.com> 2.4.2-2
- fix build for modular X, remove X11R6 path references

* Tue Nov 15 2005 Mihai Ibanescu <misa@redhat.com> 2.4.2-1
- Upgraded to 2.4.2
- BuildRequires autoconf

* Wed Nov  9 2005 Mihai Ibanescu <misa@redhat.com> 2.4.1-16
- Rebuilding against newer openssl.
- XFree86-devel no longer exists

* Mon Sep 26 2005 Peter Jones <pjones@redhat.com> 2.4.1-14
- Once more -- this time, to fix -EPERM when you run it in a directory
  you can't read from.

* Mon Sep 26 2005 Peter Jones <pjones@redhat.com> 2.4.1-13
- So, 5 or 6 people have said it works for them with this patch...

* Sun Sep 25 2005 Peter Jones <pjones@redhat.com> 2.4.1-12
- Fixed bug #169159 (check for argc>0 and argv[0] == NULL, not just
    argv[0][0]='\0')
  Reworked the patch from -8 a bit more.

* Fri Sep 23 2005 Mihai Ibanescu <misa@redhat.com> 2.4.1-10
- Fixed bug #169159 (don't let python core dump if no arguments are passed in)
  Reworked the patch from -8 a bit more.

* Thu Sep 22 2005 Peter Jones <pjones@redhat.com> 2.4.1-8
- Fix bug #169046 more correctly.

* Thu Sep 22 2005 Mihai Ibanescu <misa@redhat.com> 2.4.1-7
- Fixed bug #169046 (realpath is unsafe); thanks to 
  Peter Jones <pjones@redhat.com> and Arjan van de Ven <arjanv@redhat.com> for
  diagnosing and the patch.

* Tue Sep 20 2005 Mihai Ibanescu <misa@redhat.com> 2.4.1-4
- Fixed bug #168655 (fixes for building as python24)

* Tue Jul 26 2005 Mihai Ibanescu <misa@redhat.com> 2.4.1-3
- Fixed bug #163435 (pynche doesn't start))

* Wed Apr 20 2005 Mihai Ibanescu <misa@redhat.com> 2.4.1-2
- Fixed bug #143667 (python should own /usr/lib/python* on 64-bit systems, for
  noarch packages)
- Fixed bug #143419 (BuildRequires db4 is not versioned)

* Wed Apr  6 2005 Mihai Ibanescu <misa@redhat.com> 2.4.1-1
- updated to 2.4.1

* Mon Mar 14 2005 Mihai Ibanescu <misa@redhat.com> 2.4-6
- building the docs from a different source rpm, to decouple bootstrapping
  python from having tetex installed

* Fri Mar 11 2005 Dan Williams <dcbw@redhat.com> 2.4-5
- Rebuild to pick up new libssl.so.5

* Wed Feb  2 2005 Mihai Ibanescu <misa@redhat.com> 2.4-4
- Fixed security issue in SimpleXMLRPCServer.py (#146647)

* Wed Jan 12 2005 Tim Waugh <twaugh@redhat.com> 2.4-3
- Rebuilt for new readline.

* Mon Dec  6 2004 Jeff Johnson <jbj@jbj.org> 2.4-2
- db-4.3.21 returns DB_BUFFER_SMALL rather than ENOMEM (#141994).
- add Provide: python(abi) = 2.4
- include msgfmt/pygettext *.pyc and *.pyo from brp-python-bytecompile.

* Fri Dec  3 2004 Mihai Ibanescu <misa@redhat.com> 2.4-1
- Python-2.4.tar.bz2 (final)

* Fri Nov 19 2004 Mihai Ibanescu <misa@redhat.com> 2.4-0.c1.1
- Python-2.4c1.tar.bz2 (release candidate 1)

* Thu Nov 11 2004 Jeff Johnson <jbj@jbj.org> 2.4-0.b2.4
- rebuild against db-4.3.21.

* Mon Nov  8 2004 Jeremy Katz <katzj@redhat.com> - 2.4-0.b2.3
- fix the lib64 patch so that 64bit arches still look in /usr/lib/python...

* Mon Nov  8 2004 Jeremy Katz <katzj@redhat.com> - 2.4-0.b2.2
- cryptmodule still needs -lcrypt (again)

* Thu Nov  4 2004 Mihai Ibanescu <misa@redhat.com> 2.4-0.b2.1
- Updated to python 2.4b2 (and labeled it 2.4-0.b2.1 to avoid breaking rpm's
  version comparison)

* Thu Nov  4 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-13
- Fixed bug #138112 (python overflows stack buffer) - SF bug 105470

* Tue Nov  2 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-12
- Fixed bugs #131439 #136023 #137863 (.pyc/.pyo files had the buildroot added)

* Tue Oct 26 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-11
- Fixed bug #136654 (python has sketchy audio clip)

* Tue Aug 31 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-10
- Fixed bug #77418 (Demo dir not packaged)
- More tweaking on #19347 (Moved Tools/ under /usr/lib/python2.3/Tools)

* Fri Aug 13 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-8
- Fixed bug #129769: Makefile in new python conflicts with older version found
  in old python-devel
- Reorganized the spec file to get rid of the aspython2 define; __python_ver
  is more powerful.

* Tue Aug  3 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-7
- Including html documentation for non-i386 arches
- Fixed #125362 (python-doc html files have japanese character encoding)
- Fixed #128923 (missing dependency between python and python-devel)

* Fri Jul 30 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-6
- Fixed #128030 (help() not printing anything)
- Fixed #125472 (distutils.sysconfig.get_python_lib() not returning the right
  path on 64-bit systems)
- Fixed #127357 (building python as a shared library)
- Fixed  #19347 (including the contents of Tools/scripts/ in python-tools)

* Tue Jun 15 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Tue Jun  8 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-3
- Added an optik.py that provides the same interface from optparse for
  backward compatibility; obsoleting python-optik

* Mon Jun  7 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-2
- Patched bdist_rpm to allow for builds of multiple binary rpms (bug #123598)

* Fri Jun  4 2004 Mihai Ibanescu <misa@redhat.com> 2.3.4-1
- Updated to 2.3.4-1 with Robert Scheck's help (bug #124764)
- Added BuildRequires: tix-devel (bug #124918)

* Fri May  7 2004 Mihai Ibanescu <misa@redhat.com> 2.3.3-6
- Correct fix for #122304 from upstream:
  http://sourceforge.net/tracker/?func=detail&atid=105470&aid=931848&group_id=5470

* Thu May  6 2004 Mihai Ibanescu <misa@redhat.com> 2.3.3-4
- Fix for bug #122304 : splitting the domain name fails on 64-bit arches
- Fix for bug #120879 : including Makefile into the main package

- Requires XFree86-devel instead of -libs (see bug #118442)

* Tue Mar 16 2004 Mihai Ibanescu <misa@redhat.com> 2.3.3-3
- Requires XFree86-devel instead of -libs (see bug #118442)

* Tue Mar 02 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Fri Feb 13 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Fri Dec 19 2003 Jeff Johnson <jbj@jbj.org> 2.3.3-1
- upgrade to 2.3.3.

* Sat Dec 13 2003 Jeff Johnson <jbj@jbj.org> 2.3.2-9
- rebuild against db-4.2.52.

* Fri Dec 12 2003 Jeremy Katz <katzj@redhat.com> 2.3.2-8
- more rebuilding for new tcl/tk

* Wed Dec  3 2003 Jeff Johnson <jbj@jbj.org> 2.3.2-7.1
- rebuild against db-4.2.42.

* Fri Nov 28 2003 Mihai Ibanescu <misa@redhat.com> 2.3.2-7
- rebuilt against newer tcl/tk

* Mon Nov 24 2003 Mihai Ibanescu <misa@redhat.com> 2.3.2-6
- added a Provides: python-abi

* Wed Nov 12 2003 Mihai Ibanescu <misa@redhat.com> 2.3.2-5
- force CC (#109268)

* Sun Nov  9 2003 Jeremy Katz <katzj@redhat.com> 2.3.2-4
- cryptmodule still needs -lcrypt

* Wed Nov  5 2003 Mihai Ibanescu <misa@redhat.com> 2.3.2-2
- Added patch for missing mkhowto

* Thu Oct 16 2003 Mihai Ibanescu <misa@redhat.com> 2.3.2-1
- Updated to 2.3.2

* Thu Sep 25 2003 Mihai Ibanescu <misa@redhat.com> 2.3.1-1
- 2.3.1 final

* Tue Sep 23 2003 Mihai Ibanescu <misa@redhat.com> 2.3.1-0.8.RC1
- Building the python 2.3.1 release candidate
- Updated the lib64 patch

* Wed Jul 30 2003 Mihai Ibanescu <misa@redhat.com> 2.3-0.2
- Building python 2.3
- Added more BuildRequires
- Updated the startup files for modulator and pynche; idle installs its own
  now.

* Thu Jul  3 2003 Mihai Ibanescu <misa@redhat.com> 2.2.3-4
- Rebuilt against newer db4 packages (bug #98539)

* Mon Jun 9 2003 Elliot Lee <sopwith@redhat.com> 2.2.3-3
- rebuilt

* Wed Jun  7 2003 Mihai Ibanescu <misa@redhat.com> 2.2.3-2
- Rebuilt

* Tue Jun  6 2003 Mihai Ibanescu <misa@redhat.com> 2.2.3-1
- Upgraded to 2.2.3

* Wed Apr  2 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-28
- Rebuilt

* Wed Apr  2 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-27
- Modified the ftpuri patch conforming to http://ietf.org/rfc/rfc1738.txt

* Mon Feb 24 2003 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Mon Feb 24 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-25
- Fixed bug #84886: pydoc dies when run w/o arguments
- Fixed bug #84205: add python shm module back (used to be shipped with 1.5.2)
- Fixed bug #84966: path in byte-compiled code still wrong

* Thu Feb 20 2003 Jeremy Katz <katzj@redhat.com> 2.2.2-23
- ftp uri's should be able to specify being rooted at the root instead of 
  where you login via ftp (#84692)

* Mon Feb 10 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-22
- Using newer Japanese codecs (1.4.9). Thanks to 
  Peter Bowen <pzb@datastacks.com> for pointing this out.

* Thu Feb  6 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-21
- Rebuild

* Wed Feb  5 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-20
- Release number bumped really high: turning on UCS4 (ABI compatibility
  breakage)

* Fri Jan 31 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-13
- Attempt to look both in /usr/lib64 and /usr/lib/python2.2/site-packages/:
  some work on python-2.2.2-lib64.patch

* Thu Jan 30 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-12
- Rebuild to incorporate the removal of .lib64 and - files.

* Thu Jan 30 2003 Mihai Ibanescu <misa@redhat.com> 2.2.2-11.7.3
- Fixed bug #82544: Errata removes most tools
- Fixed bug #82435: Python 2.2.2 errata breaks redhat-config-users
- Removed .lib64 and - files that get installed after we fix the multilib
  .py files.

* Wed Jan 22 2003 Tim Powers <timp@redhat.com>
- rebuilt

* Wed Jan 15 2003 Jens Petersen <petersen@redhat.com> 2.2.2-10
- rebuild to update tkinter's tcltk deps
- convert changelog to utf-8

* Tue Jan  7 2003 Nalin Dahyabhai <nalin@redhat.com> 2.2.2-9
- rebuild

* Fri Jan  3 2003 Nalin Dahyabhai <nalin@redhat.com>
- pick up OpenSSL cflags and ldflags from pkgconfig if available

* Thu Jan  2 2003 Jeremy Katz <katzj@redhat.com> 2.2.2-8
- urllib2 didn't support non-anonymous ftp.  add support based on how 
  urllib did it (#80676, #78168)

* Mon Dec 16 2002 Mihai Ibanescu <misa@redhat.com> 2.2.2-7
- Fix bug #79647 (Rebuild of SRPM fails if python isn't installed)
- Added a bunch of missing BuildRequires found while fixing the
  above-mentioned bug

* Tue Dec 10 2002 Tim Powers <timp@redhat.com> 2.2.2-6
- rebuild to fix broken tcltk deps for tkinter

* Fri Nov 22 2002 Mihai Ibanescu <misa@redhat.com>
2.2.2-3.7.3
- Recompiled for 7.3 (to fix the -lcrypt bug)
- Fix for the spurious error message at the end of the build (build-requires
  gets confused by executable files starting with """"): make the tests
  non-executable.

* Wed Nov 20 2002 Mihai Ibanescu <misa@redhat.com>
2.2.2-5
- Fixed configuration patch to add -lcrypt when compiling cryptmodule.c

2.2.2-4
- Spec file change from Matt Wilson <msw@redhat.com> to disable linking 
  with the C++ compiler.

* Mon Nov 11 2002 Mihai Ibanescu <misa@redhat.com>
2.2.2-3.*
- Merged patch from Karsten Hopp <karsten@redhat.de> from 2.2.1-17hammer to
  use %%{_libdir}
- Added XFree86-libs as BuildRequires (because of tkinter)
- Fixed duplicate listing of plat-linux2
- Fixed exclusion of lib-dynload/japanese
- Added lib64 patch for the japanese codecs
- Use setup magic instead of using tar directly on JapaneseCodecs

* Tue Nov  5 2002 Mihai Ibanescu <misa@redhat.com>
2.2.2-2
- Fix #76912 (python-tools contains idle, which uses tkinter, but there is no
  requirement of tkinter from python-tools).
- Fix #74013 (rpm is missing the /usr/lib/python2.2/test directory)

* Mon Nov  4 2002 Mihai Ibanescu <misa@redhat.com>
- builds as python2 require a different libdb
- changed the buildroot name of python to match python2 builds

* Fri Nov  1 2002 Mihai Ibanescu <misa@redhat.com>
- updated python to 2.2.2 and adjusted the patches accordingly

* Mon Oct 21 2002 Mihai Ibanescu <misa@redhat.com>
- Fix #53930 (Python-2.2.1-buildroot-bytecode.patch)
- Added BuildPrereq dependency on gcc-c++

* Fri Aug 30 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-17
- security fix for _execvpe

* Tue Aug 13 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-16
- Fix  #71011,#71134, #58157

* Wed Aug  7 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-15
- Resurrect tkinter
- Fix for distutils (#67671)
- Fix #69962

* Thu Jul 25 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-14
- Obsolete tkinter/tkinter2 (#69838)

* Tue Jul 23 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-13
- Doc fixes (#53951) - not on alpha at the momemt

* Mon Jul  8 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-12
- fix pydoc (#68082)

* Mon Jul  8 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-11
- Add db4-devel as a BuildPrereq

* Fri Jun 21 2002 Tim Powers <timp@redhat.com> 2.2.1-10
- automated rebuild

* Mon Jun 17 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-9
- Add Japanese codecs (#66352)

* Tue Jun 11 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-8
- No more tkinter...

* Wed May 29 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-7
- Rebuild

* Tue May 21 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-6
- Add the email subcomponent (#65301)

* Fri May 10 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-5
- Rebuild

* Thu May 02 2002 Than Ngo <than@redhat.com> 2.2.1-4
- rebuild i new enviroment

* Tue Apr 23 2002 Trond Eivind Glomsrød <teg@redhat.com>
- Use ucs2, not ucs4, to avoid breaking tkinter (#63965)

* Mon Apr 22 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-2
- Make it use db4

* Fri Apr 12 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2.1-1
- 2.2.1 - a bugfix-only release

* Fri Apr 12 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-16
- the same, but in builddirs - this will remove them from the 
  docs package, which doesn't look in the buildroot for files.

* Fri Apr 12 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-15
- Get rid of temporary files and .cvsignores included 
  in the tarball and make install

* Fri Apr  5 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-14
- Don't own lib-tk in main package, only in tkinter (#62753)

* Mon Mar 25 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-13
- rebuild

* Mon Mar 25 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-12
- rebuild

* Fri Mar  1 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-11
- Add a not to the Distutils obsoletes test (doh!)

* Fri Mar  1 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-10
- Rebuild

* Mon Feb 25 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-9
- Only obsolete Distutils when built as python

* Thu Feb 21 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-8
- Make files in /usr/bin install side by side with python 1.5 when
- Drop explicit requirement of db4
  built as python2

* Thu Jan 31 2002 Elliot Lee <sopwith@redhat.com> 2.2-7
- Use version and pybasever macros to make updating easy
- Use _smp_mflags macro

* Tue Jan 29 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-6
- Add db4-devel to BuildPrereq

* Fri Jan 25 2002 Nalin Dahyabhai <nalin@redhat.com> 2.2-5
- disable ndbm support, which is db2 in disguise (really interesting things
  can happen when you mix db2 and db4 in a single application)

* Thu Jan 24 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-4
- Obsolete subpackages if necesarry 
- provide versioned python2
- build with db4

* Wed Jan 16 2002 Trond Eivind Glomsrød <teg@redhat.com> 2.2-3
- Alpha toolchain broken. Disable build on alpha.
- New openssl

* Wed Dec 26 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-1
- 2.2 final

* Fri Dec 14 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-0.11c1
- 2.2 RC 1
- Don't include the _tkinter module in the main package - it's 
  already in the tkiter packace
- Turn off the mpzmodule, something broke in the buildroot

* Wed Nov 28 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-0.10b2
- Use -fPIC for OPT as well, in lack of a proper libpython.so

* Mon Nov 26 2001 Matt Wilson <msw@redhat.com> 2.2-0.9b2
- changed DESTDIR to point to / so that distutils will install dynload
  modules properly in the installroot

* Fri Nov 16 2001 Matt Wilson <msw@redhat.com> 2.2-0.8b2
- 2.2b2

* Fri Oct 26 2001 Matt Wilson <msw@redhat.com> 2.2-0.7b1
- python2ify

* Fri Oct 19 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-0.5b1
- 2.2b1

* Sun Sep 30 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-0.4a4
- 2.2a4
- Enable UCS4 support
- Enable IPv6
- Provide distutils
- Include msgfmt.py and pygettext.py

* Fri Sep 14 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-0.3a3
- Obsolete Distutils, which is now part of the main package
- Obsolete python2

* Thu Sep 13 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-0.2a3
- Add docs, tools and tkinter subpackages, to match the 1.5 layout

* Wed Sep 12 2001 Trond Eivind Glomsrød <teg@redhat.com> 2.2-0.1a3
- 2.2a3
- don't build tix and blt extensions

* Mon Aug 13 2001 Trond Eivind Glomsrød <teg@redhat.com>
- Add tk and tix to build dependencies

* Sat Jul 21 2001 Trond Eivind Glomsrød <teg@redhat.com>
- 2.1.1 bugfix release - with a GPL compatible license

* Fri Jul 20 2001 Trond Eivind Glomsrød <teg@redhat.com>
- Add new build dependencies (#49753)

* Tue Jun 26 2001 Nalin Dahyabhai <nalin@redhat.com>
- build with -fPIC

* Fri Jun  1 2001 Trond Eivind Glomsrød <teg@redhat.com>
- 2.1
- reorganization of file includes

* Wed Dec 20 2000 Trond Eivind Glomsrød <teg@redhat.com>
- fix the "requires" clause, it lacked a space causing problems
- use %%{_tmppath}
- don't define name, version etc
- add the available patches from the Python home page

* Fri Dec 15 2000 Matt Wilson <msw@redhat.com>
- added devel subpackage
- modify all files to use "python2.0" as the intrepter
- don't build the Expat bindings
- build against db1

* Mon Oct 16 2000 Jeremy Hylton <jeremy@beopen.com>
- updated for 2.0 final

* Mon Oct  9 2000 Jeremy Hylton <jeremy@beopen.com>
- updated for 2.0c1
- build audioop, imageop, and rgbimg extension modules
- include xml.parsers subpackage
- add test.xml.out to files list

* Thu Oct  5 2000 Jeremy Hylton <jeremy@beopen.com>
- added bin/python2.0 to files list (suggested by Martin v. L?)

* Tue Sep 26 2000 Jeremy Hylton <jeremy@beopen.com>
- updated for release 1 of 2.0b2
- use .bz2 version of Python source

* Tue Sep 12 2000 Jeremy Hylton <jeremy@beopen.com>
- Version 2 of 2.0b1
- Make the package relocatable.  Thanks to Suchandra Thapa.
- Exclude Tkinter from main RPM.  If it is in a separate RPM, it is
  easier to track Tk releases.
