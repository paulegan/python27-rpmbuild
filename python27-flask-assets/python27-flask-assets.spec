Name: python27-flask-assets
Version: 0.10
Release: 1
Summary: Asset management for Flask, to compress and merge CSS and Javascript files
Group: Development/Libraries
License: BSD
URL: http://github.com/miracle2k/flask-assets
Source0: http://pypi.python.org/packages/source/F/Flask-Assets/Flask-Assets-%{version}.tar.gz

BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch: noarch
BuildRequires: python27-setuptools python27-flask-script python27-webassets
Requires: python27-flask-script python27-webassets

%description
Integrates the webassets library with Flask, adding support for
merging, minifying and compiling CSS and Javascript files.

%prep
%setup -q -n Flask-Assets-%{version}

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
%doc README.rst LICENSE
%{python_sitelib}/*

%changelog
* Tue May  6 2014 Paul Egan <paulegan@rockpack.com> - 0.9-1
- create_parser patch included upstream

* Thu Feb 13 2014 Paul Egan <paulegan@rockpack.com> - 0.8-3
- Added patch for create_parser

* Tue Mar 19 2013 Paul Egan <paulegan@rockpack.com> - 0.8-1
- Initial release
