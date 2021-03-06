Name: python27-fixture
Version: 1.5
Release: 1
Summary: fixture is a python module for loading and referencing test data
Group: Development/Libraries
License: LGPL
URL: http://farmdev.com/projects/fixture/
Source0: http://pypi.python.org/packages/source/f/fixture/fixture-%{version}.tar.gz

BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch: noarch
BuildRequires: python27-setuptools

%description
It provides several utilities for achieving a fixed state when testing
Python programs.  Specifically, these utilities setup/teardown databases and
work with temporary file systems.

%prep
%setup -q -n fixture-%{version}

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc README.txt
%{python_sitelib}/fixture*
%{_bindir}/*

%changelog
* Thu Feb 13 2014 Paul Egan <paulegan@rockpack.com> - 1.5-1
- Bumped

* Mon Feb 25 2013 Paul Egan <paulegan@rockpack.com> - 1.4-2
- Added expunge_all patch

* Thu Feb 14 2013 Paul Egan <paulegan@rockpack.com> - 1.4-1
- Initial release
