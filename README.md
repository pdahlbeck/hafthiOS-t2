# Hafthi OS T2 — live evaluation

Target: MacBook Pro 15-inch 2018, Intel i7, Intel UHD 630 + Radeon Pro 560X.

This separate project builds the Hafthi desktop from pinned upstream commit
`8867975f6c8dc1c7e9cdd75341acc3d6c5422f4f`, with `linux-t2`, early T2 keyboard/trackpad modules, T2 audio configuration, fan service and Intel graphics selected at boot.

**First milestone: USB live evaluation. Disk installation and the regular desktop updater are disabled.** VM boot verifies packaging and UEFI startup, not physical Apple hardware, sleep, battery life or working Wi-Fi. No ISO is ready until its build succeeds.

In macOS Recovery, Startup Security Utility must be set to No Security and allow external boot. Preserve macOS and Recovery. Boot the written USB while holding Option.

Try the desktop, keyboard, trackpad, audio and network. Run:

```
python3 /usr/local/bin/hafthios-t2-diagnostics > ~/t2-report.json
```

The report reads hardware status without changing disks. It omits serial numbers and network addresses. Wi-Fi requires Apple's model-specific firmware; the fetcher is included but firmware retrieval needs a network connection or prior macOS preparation.

Package trust: official Arch repositories retain their normal signature policy.
The upstream `arch-mact2` repository currently documents `SigLevel = Never`; this exception is confined to T2 packages and is a limitation of this experimental build, not a signed-release guarantee.

Sources: [T2 Arch installation](https://wiki.t2linux.org/distributions/arch/installation/), [early modules](https://wiki.t2linux.org/guides/postinstall/), [hybrid graphics](https://wiki.t2linux.org/guides/hybrid-graphics/).
