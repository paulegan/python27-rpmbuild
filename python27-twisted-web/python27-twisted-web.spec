Name: python27-twisted-web
Version: 12.3.0
Release: 1%{?dist}
Summary: Twisted web client and server, programmable in Python
License: MIT
URL: http://twistedmatrix.com/trac/wiki/TwistedWeb
Source0: http://twistedmatrix.com/Releases/Web/12.3/TwistedWeb-%{version}.tar.bz2
BuildRequires: python27-twisted-core >= %{version}

BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
Requires: python27-twisted-core >= %{version}
#Requires: SOAPpy

# a noarch-turned-arch package should not have debuginfo
%define debug_package %{nil}

%description
Twisted is an event-based framework for internet applications.

Twisted Web is a complete web server, aimed at hosting web applications using
Twisted and Python, but fully able to serve static pages too.

%prep
%setup -q -n TwistedWeb-%{version}

# Remove spurious shellbangs
sed -i -e '/^#! *\/usr\/bin\/python/d' twisted/web/test/test_cgi.py
sed -i -e '/^#! *\/usr\/bin\/python/d' twisted/web/test/test_distrib.py

%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT

# This is a pure python package, but extending the twisted namespace from
# python-twisted-core, which is arch-specific, so it needs to go in sitearch
%{__python} setup.py install -O1 --skip-build \
    --install-purelib %{python_sitearch} --root $RPM_BUILD_ROOT

# See if there's any egg-info
if [ -f $RPM_BUILD_ROOT%{python_sitearch}/Twisted*.egg-info ]; then
    echo $RPM_BUILD_ROOT%{python_sitearch}/Twisted*.egg-info |
        sed -e "s|^$RPM_BUILD_ROOT||"
fi > egg-info

%post
if [ -x %{_libexecdir}/twisted-dropin-cache ]; then
    %{_libexecdir}/twisted-dropin-cache || :
fi

%postun
if [ -x %{_libexecdir}/twisted-dropin-cache ]; then
    %{_libexecdir}/twisted-dropin-cache || :
fi

%files -f egg-info
%doc LICENSE NEWS README doc/*
%{python_sitearch}/twisted/plugins/twisted_web.py*
%{python_sitearch}/twisted/web/

%changelog
* Tue Feb 26 2013 Paul Egan <paulegan@rockpack.com> - 12.3.0-1
- Imported Fedora spec and bumped version

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 12.1.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Sun Jun 17 2012 Julian Sikorski <belegdol@fedoraproject.org> - 12.1.0-1
- Updated to 12.1.0

* Sun Feb 12 2012 Julian Sikorski <belegdol@fedoraproject.org> - 12.0.0-1
- Updated to 12.0.0

* Sat Jan 07 2012 Julian Sikorski <belegdol@fedoraproject.org> - 11.1.0-2
- Rebuilt for gcc-4.7

* Fri Nov 18 2011 Julian Sikorski <belegdol@fedoraproject.org> - 11.1.0-1
- Updated to 11.1.0
- Dropped obsolete Group, Buildroot, %%clean and %%defattr

* Sat Apr 30 2011 Julian Sikorski <belegdol@fedoraproject.org> - 11.0.0-1
- Updated to 11.0.0

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 10.2.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sat Jan 15 2011 Julian Sikorski <belegdol@fedoraproject.org> - 10.2.0-1
- Updated to 10.2.0

* Tue Sep 21 2010 Julian Sikorski <belegdol@fedoraproject.org> - 10.1.0-1
- Updated to 10.1.0
- Switched to macros for versioned dependencies

* Thu Jul 22 2010 David Malcolm <dmalcolm@redhat.com> - 8.2.0-4
- Rebuilt for https://fedoraproject.org/wiki/Features/Python_2.7/MassRebuild

* Sun Jul 26 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 8.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Thu Feb 26 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 8.2.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Mon Dec 29 2008 Matthias Saou <http://freshrpms.net/> 8.2.0-1
- Update to 8.2.0.
- Change back spec cosmetic details from Paul's to Thomas' preference.

* Tue Dec 23 2008 Matthias Saou <http://freshrpms.net/> 8.1.0-2
- Update to 8.1.0.
- Merge back changes from Paul Howarth.
- Make sure the scriplets never return a non-zero exit status.

* Sun Nov 30 2008 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> - 0.7.0-5
- Fix locations for Python 2.6

* Sat Nov 29 2008 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> - 0.7.0-4
- Rebuild for Python 2.6

* Fri Mar 07 2008 Jesse Keating <jkeating@redhat.com> - 0.7.0-3
- Handle egg issue, drop the pyver stuff.

* Wed Feb 20 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 0.7.0-2
- Autorebuild for GCC 4.3

* Fri Aug 31 2007 Thomas Vander Stichele <thomas at apestaart dot org>
- 0.7.0-1
- updated to new version
- updated core requires
- removed websetroot

* Fri Dec 22 2006 Jef Spaleta <jspaleta@gmail.com>
- 0.6.0-4
- Docs and Url fixes as suggested in the review
- Added BR for python-devel for python 2.5, merry Christmas!

* Wed Nov 01 2006 Thomas Vander Stichele <thomas at apestaart dot org>
- 0.6.0-3
- remove shebang lines from unit test files

* Tue Sep 26 2006 Thomas Vander Stichele <thomas at apestaart dot org>
- 0.6.0-2
- no longer ghost .pyo files
- rebuild dropin.cache

* Wed Jun 07 2006 Thomas Vander Stichele <thomas at apestaart dot org>
- 0.6.0-1
- update to new release
- remove NoArch
- change dep to SOAPpy as it is called in extras

* Tue Aug 23 2005 Jeff Pitman <symbiont+pyvault@berlios.de> 0.5.0-2
- disttag

* Wed Mar 16 2005 Jeff Pitman <symbiont+pyvault@berlios.de> 0.5.0-0.1.a3
- upstream release

* Sat Mar 12 2005 Jeff Pitman <symbiont+pyvault@berlios.de> 0.5.0-0.1.a2
- prerelease; FE versioning

* Mon Feb 07 2005 Jeff Pitman <symbiont+pyvault@berlios.de> 0.1.0-1
- prep for split

