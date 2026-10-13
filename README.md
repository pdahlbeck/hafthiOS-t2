# Hafthi OS T2 — live evaluation

Target: MacBook Pro 15-inch 2018, Intel i7, Intel UHD 630 + Radeon Pro 560X.

This separate project builds the Hafthi desktop from pinned upstream commit
`8867975f6c8dc1c7e9cdd75341acc3d6c5422f4f`, with `linux-t2`, early T2 keyboard/trackpad modules, T2 audio configuration, fan service and Intel graphics selected at boot.

The USB desktop has been tested by Petrus on the physical MacBook Pro, including sleep/wake. The next build enables installation only into a prepared `HAFTHI` partition. The regular desktop updater remains disabled. No installation ISO is ready until its build and installation verification succeed.

## Prepared-partition installation

Create a separate ExFAT partition named `HAFTHI` from macOS before booting the installer. The confirmed test-machine layout is EFI (314.6 MB), Apple APFS (120 GB, containing macOS and Recovery), and HAFTHI (880.2 GB). This installation keeps macOS as well as Recovery; it does not remove macOS volumes.

The helper offers only an unmounted HAFTHI ExFAT/ext4 partition on a GPT disk with an Apple APFS partition and a FAT EFI partition. The live USB is excluded. Type the reviewed `FORMAT /dev/...` confirmation to format only that partition as ext4. The partition table, APFS container and EFI filesystem are not reformatted. An existing EFI fallback loader causes an error before formatting; it is never overwritten automatically.

The installed system uses linux-t2, early T2 input modules, Intel graphics, Swedish keymap and a Retina-scaled GLES2 greeter. CI installs onto a disposable GPT disk, verifies unchanged partition geometry and Apple-shaped sentinel bytes, and boots the installed ext4 root without the ISO in OVMF. This does not test Apple Recovery functionality or a physical Mac installation. The local Recovery volume must remain inside its APFS container; Internet Recovery is not a substitute for preserving it.

In macOS Recovery, Startup Security Utility must be set to No Security and allow external boot. Preserve macOS and Recovery. Boot the written USB while holding Option.

Try the desktop, keyboard, trackpad, audio and network. Run:

```
python3 /usr/local/bin/hafthios-t2-diagnostics > ~/t2-report.json
```

The report reads hardware status without changing disks. It omits serial numbers and network addresses. Wi-Fi requires Apple's model-specific firmware; the fetcher is included but firmware retrieval needs a network connection or prior macOS preparation.

Package trust: official Arch repositories retain their normal signature policy.
The upstream `arch-mact2` repository currently documents `SigLevel = Never`; this exception is confined to T2 packages and is a limitation of this experimental build, not a signed-release guarantee.

Sources: [T2 Arch installation](https://wiki.t2linux.org/distributions/arch/installation/), [early modules](https://wiki.t2linux.org/guides/postinstall/), [hybrid graphics](https://wiki.t2linux.org/guides/hybrid-graphics/).
