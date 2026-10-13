"""Adapt the pinned upstream installer; never resize or erase Apple partitions."""
READ_DISKS = '''def read_disks():
    live_only()
    if not Path('/sys/firmware/efi').is_dir():
        raise RuntimeError('T2 installation requires UEFI boot.')
    excluded = live_media_paths()
    columns = COLUMNS + ',FSTYPE,LABEL,PARTTYPE,PARTUUID,UUID,START,PTTYPE,TRAN,RM'
    payload = json.loads(command(['lsblk', '--json', '--bytes', '--tree', '--output', columns]))
    return t2_targets(payload, excluded)


def t2_targets(payload, excluded=()):
    targets = []
    apfs = '7c3457ef-0000-11aa-aa11-00306543ecac'
    esp = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
    basic = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
    for disk in payload.get('blockdevices', []):
        items = list(descendants(disk))
        if (disk.get('type') != 'disk' or disk.get('ro') or disk.get('rm')
                or disk.get('tran') == 'usb' or disk.get('pttype') != 'gpt'
                or any(item.get('path') in excluded for item in items)
                or any(item.get('ro') or any(item.get('mountpoints') or []) for item in items)
                or any(item.get('type') not in ('disk', 'part') for item in items)):
            continue
        parts = disk.get('children', [])
        apple = [p for p in parts if str(p.get('parttype', '')).lower() == apfs]
        efis = [p for p in parts if str(p.get('parttype', '')).lower() == esp
                and p.get('fstype') == 'vfat']
        if not apple or len(efis) != 1:
            continue
        # Snapshot every partition identity and its exact extent. Never write GPT.
        layout = [{k: p.get(k) for k in ('path', 'partuuid', 'parttype', 'start', 'size')}
                  for p in parts]
        if any(not p['partuuid'] or p['start'] is None or not p['size'] for p in layout):
            continue
        for part in parts:
            if (part.get('label') != 'HAFTHI' or part.get('fstype') not in ('exfat', 'ext4')
                    or str(part.get('parttype', '')).lower() != basic
                    or int(part.get('size') or 0) < MIN_SIZE):
                continue
            target = dict(part)
            target.update(model='HAFTHI partition; Apple APFS preserved',
                          parent=identity(disk), layout=layout,
                          efi=efis[0]['path'], efi_uuid=efis[0].get('uuid'))
            if target['efi_uuid']:
                targets.append(target)
    return targets


'''

EFI_CHECK = '''def check_efi(efi):
    # Never overwrite an existing fallback loader, Apple directory or other OS.
    with tempfile.TemporaryDirectory(prefix='efi-check-', dir=STATE) as directory:
        command(['mount', '-o', 'ro', efi, directory])
        try:
            root = Path(directory)
            if (root / 'EFI/BOOT').exists() or (root / 'EFI/hafthios-t2').exists():
                raise RuntimeError('EFI already contains a fallback or Hafthi loader. No partition was formatted. Manual review is required.')
            if shutil.disk_usage(root).free < 16 * 1024**2:
                raise RuntimeError('EFI partition needs at least 16 MiB free.')
        finally:
            command(['umount', directory])


'''


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Pinned installer changed: ' + old[:80])
    return source.replace(old, new, 1)


def adapt(source):
    start = source.index('def read_disks():')
    end = source.index('def identity(disk):', start)
    source = source[:start] + READ_DISKS + source[end:]
    source = replace_once(source,
        "keys = ('path', 'size', 'model', 'serial', 'wwn', 'maj:min')",
        "keys = ('path', 'size', 'model', 'serial', 'wwn', 'maj:min', 'partuuid', 'uuid', 'parent', 'layout', 'efi', 'efi_uuid')")
    source = replace_once(source,
        "'layout': ['1 MiB BIOS boot', '512 MiB EFI system', 'Remaining space: ext4 root']",
        "'layout': ['Selected HAFTHI partition: ext4 root', 'Existing EFI: add Hafthi loader without formatting', 'Apple APFS/Recovery and GPT: preserved']")
    source = replace_once(source, "'confirmation': 'ERASE ' + path", "'confirmation': 'FORMAT ' + path")
    start = source.index("        phase('Partitioning the confirmed disk')")
    end = source.index("        with tempfile.TemporaryDirectory(prefix='target-'", start)
    source = source[:start] + '''        efi, system = disk['efi'], device
        check_efi(efi)
        phase('Formatting only the confirmed HAFTHI partition; Apple APFS is preserved')
        command(['mkfs.ext4', '-F', '-L', 'HAFTHI', system])
''' + source[end:]
    source = replace_once(source, 'def install(request):', EFI_CHECK + 'def install(request):')
    source = replace_once(source,
        "                command(['arch-chroot', str(root), 'grub-install', '--target=i386-pc', device])\n", '')
    source = replace_once(source,
        "'--efi-directory=/boot/efi', '--bootloader-id=hafthios', '--removable', '--no-nvram'",
        "'--efi-directory=/boot/efi', '--bootloader-id=hafthios-t2', '--removable', '--no-nvram'")
    source = source.replace('vmlinuz-linux', 'vmlinuz-linux-t2').replace('initramfs-linux.img', 'initramfs-linux-t2.img')
    source = source.replace('etc/mkinitcpio.d/linux.preset', 'etc/mkinitcpio.d/linux-t2.preset')
    source = replace_once(source, 'MODULES=()\\nBINARIES=()', 'MODULES=(t2bce_dma t2bce_core t2bce_vhci virtio_pci virtio_blk)\\nBINARIES=()')
    source = replace_once(source, 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"',
        'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash intel_iommu=on iommu=pt pm_async=off apple_gmux.force_igd=1"')
    # Cage must use Intel, GLES2 and Retina scale for the installed greeter too.
    source = replace_once(source,
        '/usr/bin/cage -s -- /usr/local/bin/hafthios-greeter',
        '/usr/local/bin/hafthios-t2-greeter')
    source = replace_once(source, "    write(root, '/etc/hafthios-installed'",
        "    (root / 'etc/hafthios-t2-live').unlink(missing_ok=True)\n"
        "    write(root, '/etc/hafthios-t2-installed', 'T2 partition installation\\n')\n"
        "    write(root, '/etc/hafthios-installed'")
    source = source.replace('Type the exact ERASE confirmation', 'Type the exact FORMAT confirmation')
    source = source.replace('Whole-disk offline installer.', 'T2 prepared-partition offline installer.')
    return source
