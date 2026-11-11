# Version is passed in by build.sh (taken from debian/changelog) so there is
# a single source of truth for releases.
%{!?nkms_version: %global nkms_version 0}

Name:           nkms
Version:        %{nkms_version}
Release:        1%{?dist}
Summary:        Network Keyboard Mouse Switch
License:        LicenseRef-Unspecified
URL:            https://github.com/nicholasyoder/nkms
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros

Requires:       python3
Requires:       python3-pyqt6
Requires:       python3-evdev
Requires:       python3-pyudev
Requires:       dbus
Requires:       systemd

%description
Switch keyboard and mouse input between multiple machines via the network.

%prep
%autosetup -n %{name}-%{version}

%build
# Pure Python, nothing to build.

%install
mkdir -p %{buildroot}%{python3_sitelib}
cp -a nkms %{buildroot}%{python3_sitelib}/

install -Dm755 usr/bin/nkms-daemon %{buildroot}%{_bindir}/nkms-daemon
install -Dm755 usr/bin/nkms-applet %{buildroot}%{_bindir}/nkms-applet

install -Dm644 etc/nkms/nkms.conf %{buildroot}%{_sysconfdir}/nkms/nkms.conf
install -Dm644 etc/dbus-1/system.d/nkms.conf %{buildroot}%{_datadir}/dbus-1/system.d/nkms.conf
install -Dm644 etc/xdg/autostart/nkms.desktop %{buildroot}%{_sysconfdir}/xdg/autostart/nkms.desktop
install -Dm644 etc/systemd/system/nkms.service %{buildroot}%{_unitdir}/nkms.service
install -Dm644 nkms/logo/nkms.png %{buildroot}%{_datadir}/icons/hicolor/48x48/apps/nkms.png

%post
# Mirror the Debian postinst: enable and start the daemon on install.
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl reload dbus >/dev/null 2>&1 || :
if [ $1 -eq 1 ]; then
    systemctl enable --now nkms.service >/dev/null 2>&1 || :
else
    systemctl try-restart nkms.service >/dev/null 2>&1 || :
fi

%preun
if [ $1 -eq 0 ]; then
    systemctl disable --now nkms.service >/dev/null 2>&1 || :
fi

%postun
systemctl daemon-reload >/dev/null 2>&1 || :

%files
%doc README.md
%{python3_sitelib}/nkms/
%{_bindir}/nkms-daemon
%{_bindir}/nkms-applet
%dir %{_sysconfdir}/nkms
%config(noreplace) %{_sysconfdir}/nkms/nkms.conf
%{_datadir}/dbus-1/system.d/nkms.conf
%config(noreplace) %{_sysconfdir}/xdg/autostart/nkms.desktop
%{_unitdir}/nkms.service
%{_datadir}/icons/hicolor/48x48/apps/nkms.png
