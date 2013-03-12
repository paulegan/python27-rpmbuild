Name: python27-pytest
Version: 2.3.4
Release: 1
Summary: Simple powerful testing with Python
Group: Development/Libraries
License: MIT
URL: http://pytest.org
Source0: http://pypi.python.org/packages/source/p/pytest/pytest-%{version}.zip

BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch: noarch
BuildRequires: python27-py
Requires: python27-py

%description
The py.test testing tool makes it easy to write small tests, yet
scales to support complex functional testing.

%prep
%setup -q -n pytest-%{version}

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%check
%{__python} setup.py test

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc README.txt LICENSE
%{python_sitelib}/*pytest*
%{_bindir}/py.test*

%changelog
* Thu Jan 24 2013 Paul Egan <paulegan@rockpack.com> - 2.3.4-1
- Initial release