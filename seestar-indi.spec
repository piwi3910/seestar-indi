%global pypi_name seestar-indi

Name:           %{pypi_name}
Version:        1.0.0
Release:        1%{?dist}
Summary:        INDI Driver for Seestar Telescope

License:        MIT
URL:            https://github.com/yourusername/seestar-indi
Source0:        %{pypi_name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip

# Runtime dependencies
Requires:       python3
Requires:       python3-PyIndi
Requires:       python3-requests
Requires:       python3-astropy
Requires:       python3-blinker
Requires:       python3-tomli
Requires:       python3-flask
Requires:       python3-flask-socketio
Requires:       python3-gevent
Requires:       python3-gevent-websocket

%description
INDI driver implementation for the Seestar S50 Smart Telescope. 
Provides control for mount, camera, filter wheel, and focuser through
INDI protocol, command-line interface, and web-based control panel.

%prep
%autosetup -n %{pypi_name}-%{version}

%build
%py3_build

%install
%py3_install

# Install configuration
mkdir -p %{buildroot}%{_sysconfdir}/seestar
install -p -m 644 config.toml.example %{buildroot}%{_sysconfdir}/seestar/config.toml

# Install systemd service files
mkdir -p %{buildroot}%{_unitdir}
install -p -m 644 systemd/seestar-indi.service %{buildroot}%{_unitdir}/
install -p -m 644 systemd/seestar-web.service %{buildroot}%{_unitdir}/

# Create log directory
mkdir -p %{buildroot}%{_localstatedir}/log/seestar

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}-%{version}-py%{python3_version}.egg-info
%{_bindir}/seestar-indi
%{_bindir}/seestar-cli
%{_bindir}/seestar-web
%config(noreplace) %{_sysconfdir}/seestar/config.toml
%{_unitdir}/seestar-indi.service
%{_unitdir}/seestar-web.service
%dir %{_localstatedir}/log/seestar

%post
%systemd_post seestar-indi.service
%systemd_post seestar-web.service

%preun
%systemd_preun seestar-indi.service
%systemd_preun seestar-web.service

%postun
%systemd_postun_with_restart seestar-indi.service
%systemd_postun_with_restart seestar-web.service

%changelog
* Wed Jan 24 2024 Your Name <your.email@example.com> - 1.0.0-1
- Initial package
