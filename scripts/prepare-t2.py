#!/usr/bin/env python3
"""Adapt a pinned Hafthi checkout into a live-only T2 build."""
from pathlib import Path
import sys
import json

PARAMS='intel_iommu=on iommu=pt pm_async=off apple_gmux.force_igd=1'
MODULES='t2bce_dma t2bce_core t2bce_vhci'
REPO='\n[arch-mact2]\nSigLevel = Never\nServer = https://mirror.funami.tech/arch-mact2/os/x86_64\n'

def prepare(root):
    root=Path(root)
    build=root/'scripts/build-iso.sh'
    s=build.read_text()
    assert '\nlinux\n' in s and '# Use the normal Arch repositories' in s
    s=s.replace('\nlinux\n','\nlinux-t2\nintel-ucode\napple-t2-audio-config\napple-bcm-firmware-fetcher\nt2fanrd\niwd\nusbutils\npciutils\nalsa-utils\n')
    s=s.replace('iso_name="hafthios-prototype"','iso_name="hafthios-t2-live"').replace('iso_label="HAFTHIOS"','iso_label="HAFTHIT2"')
    injection='''
# T2 packages currently use upstream's unsigned arch-mact2 repository.
# This exception is scoped to that repository; Arch signature checks stay on.
cat >> "$profile/pacman.conf" <<'T2REPO'
'''+REPO+'''T2REPO
cp /etc/pacman.conf "$profile/airootfs/etc/pacman.conf"
cat >> "$profile/airootfs/etc/pacman.conf" <<'T2REPO'
'''+REPO+'''T2REPO
mkdir -p "$profile/airootfs/etc/mkinitcpio.conf.d" "$profile/airootfs/etc/mkinitcpio.d"
rm -f "$profile/airootfs/etc/mkinitcpio.d/linux.preset"
cat > "$profile/airootfs/etc/mkinitcpio.d/linux-t2.preset" <<'PRESET'
PRESETS=('archiso')
ALL_kver='/boot/vmlinuz-linux-t2'
archiso_config='/etc/mkinitcpio.conf.d/archiso.conf'
archiso_image='/boot/initramfs-linux-t2.img'
PRESET
printf '\\nMODULES+=(t2bce_dma t2bce_core t2bce_vhci)\\n' >> "$profile/airootfs/etc/mkinitcpio.conf.d/archiso.conf"
find "$profile/grub" "$profile/syslinux" -name '*.cfg' -exec sed -i \\
 's/vmlinuz-linux/vmlinuz-linux-t2/g; s/initramfs-linux.img/initramfs-linux-t2.img/g; s/cow_spacesize=50%/cow_spacesize=50% '''+PARAMS+'''/g' {} +
ln -sf ../hafthi-t2-live-check.service "$profile/airootfs/etc/systemd/system/multi-user.target.wants/hafthi-t2-live-check.service"
ln -sf /usr/lib/systemd/system/t2fanrd.service "$profile/airootfs/etc/systemd/system/multi-user.target.wants/t2fanrd.service"
'''
    s=s.replace('# Use the normal Arch repositories',injection+'\n# Use the normal Arch repositories')
    s=s.replace('python3 "$root/scripts/build-update.py" "$profile/airootfs" "$root/out"','# T2 live image does not publish a desktop update.')
    build.write_text(s)
    inventory=root/'scripts/package-inventory.py'
    inventory.write_text(inventory.read_text().replace('initramfs-linux.img','initramfs-linux-t2.img'))
    live=root/'live'
    def write(path,text):
        p=live/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    write('etc/modprobe.d/hafthi-t2.conf','options apple-gmux force_igd=y\n')
    write('etc/modules-load.d/hafthi-t2.conf','t2bce_vhci\n')
    write('etc/hafthios-t2-live','MacBook Pro 15-inch 2018 USB evaluation; installation disabled\n')
    write('usr/local/bin/hafthios-install','#!/usr/bin/env python3\nif __name__ == "__main__":\n    raise SystemExit("T2 USB-testversion: diskinstallation är ännu inte tillgänglig. Ingen disk har ändrats.")\n')
    write('usr/local/bin/hafthios-update','#!/usr/bin/env python3\nif __name__ == "__main__":\n    raise SystemExit("T2-testversion: använd inte uppdateringar för vanliga Hafthi OS.")\n')
    write('etc/NetworkManager/conf.d/wifi-backend.conf','[device]\nwifi.backend=iwd\n')
    write('etc/systemd/system/hafthi-t2-live-check.service','[Unit]\nAfter=multi-user.target\n[Service]\nType=oneshot\nExecStart=/bin/sh -c "echo HAFTHIOS_T2_LIVE_READY $(uname -r) > /dev/ttyS0"\n[Install]\nWantedBy=multi-user.target\n')
    # Avoid ordering a service after the very target that waits for it.
    p=live/'etc/systemd/system/hafthi-t2-live-check.service';p.write_text(p.read_text().replace('After=multi-user.target','After=systemd-modules-load.service'))
    d=live/'etc/systemd/system/multi-user.target.wants';d.mkdir(parents=True,exist_ok=True)

    (live/'usr/local/bin/hafthios-t2-diagnostics').write_text((Path(__file__).parent/'t2-diagnostics.py').read_text())
    session=live/'usr/local/bin/hafthios-session'
    if session.exists():
        text=session.read_text()
        # Select Intel dynamically; DRM card numbers can change across boots.
        selection='for device in /sys/class/drm/card[0-9]*; do\n    [[ $(basename "$(readlink -f "$device/device/driver")") == i915 ]] || continue\n    export WLR_DRM_DEVICES="/dev/dri/$(basename "$device")"\n    break\ndone\n'
        session.write_text(text.replace('welcome_args=()',selection+'welcome_args=()',1))
    catalog_path=root/'docs/file-guide.json'
    catalog=json.loads(catalog_path.read_text())
    known={entry['path'] for entry in catalog['files']}
    descriptions={
        'live/etc/NetworkManager/conf.d/wifi-backend.conf':'Selects iwd for T2 Broadcom Wi-Fi.',
        'live/etc/hafthios-t2-live':'Identifies the live-only evaluation build.',
        'live/etc/modprobe.d/hafthi-t2.conf':'Selects Intel graphics through Apple GMUX.',
        'live/etc/modules-load.d/hafthi-t2.conf':'Loads the T2 internal USB input stack.',
        'live/etc/systemd/system/hafthi-t2-live-check.service':'Reports live startup on the VM serial console.',
        'live/usr/local/bin/hafthios-t2-diagnostics':'Collects a read-only hardware report without serial numbers.'}
    for path,purpose in descriptions.items():
        if path not in known:
            catalog['files'].append({'path':path,'purpose':purpose,
                'when':'During the T2 USB evaluation.', 'connections':[],
                'details':['T2 live evaluation only; does not enable disk installation.']})
    for entry in catalog['files']:
        if entry['path'] in ('live/usr/local/bin/hafthios-install','live/usr/local/bin/hafthios-update'):
            entry.update(purpose='Rejects this operation in the T2 live evaluation image.',
                         details=['Disabled until physical T2 testing is complete.'])
    catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
    # Include executable permissions via the existing Archiso profile array.
    build.write_text(build.read_text().replace('file_permissions+=(', 'file_permissions+=(\n  ["/usr/local/bin/hafthios-t2-diagnostics"]="0:0:755"'))

if __name__=='__main__':prepare(sys.argv[1])
