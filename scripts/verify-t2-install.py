#!/usr/bin/env python3
"""CI only: install into a disposable GPT image, preserve Apple-shaped bytes,
then boot the installed disk in OVMF. Does not emulate Apple Recovery or T2 hardware.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run(args,**kwargs):
    return subprocess.run(args,check=True,text=True,capture_output=True,**kwargs).stdout


def digest(path):
    with open(path,'rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(root):
    root=Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix='t2-install-') as temporary:
        work=Path(temporary);image=work/'installed.raw'
        with image.open('wb') as stream:stream.truncate(16*1024**3)
        loop=run(['losetup','--find','--show','--partscan',str(image)]).strip()
        mounted=[]
        try:
            run(['sfdisk',loop],input='label: gpt\nsize=314MiB,type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B\nsize=512MiB,type=7C3457EF-0000-11AA-AA11-00306543ECAC\ntype=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7\n')
            run(['partx','--update',loop]);run(['udevadm','settle'])
            efi,apple,target=[loop+'p'+str(number) for number in (1,2,3)]
            run(['mkfs.fat','-F','32',efi]);run(['mkfs.exfat','-L','HAFTHI',target])
            with open(apple,'r+b') as stream:stream.write(b'APPLE_PARTITION_MUST_SURVIVE')
            table=run(['sfdisk','--dump',loop]);apple_hash=digest(apple)
            esp=work/'esp';esp.mkdir();run(['mount',efi,str(esp)])
            try:
                (esp/'EFI/APPLE').mkdir(parents=True)
                (esp/'EFI/APPLE/preserved.bin').write_bytes(b'APPLE_EFI_MUST_SURVIVE')
            finally:run(['umount',str(esp)])
            for name in ('dev','proc','sys'):
                run(['mount','--rbind','/'+name,str(root/name)])
                run(['mount','--make-rslave',str(root/name)]);mounted.append(root/name)
            run(['mount','-t','tmpfs','tmpfs',str(root/'run')]);mounted.append(root/'run')
            # The extracted root is not a booted Archiso overlay. Replace only
            # environment discovery in this test; actual installer and block
            # identity / confirmation / formatting / copying remain unchanged.
            script=root/'var/tmp/t2-ci-install.py'
            script.parent.mkdir(parents=True,exist_ok=True)
            script.write_text('''import importlib.machinery, json
m=importlib.machinery.SourceFileLoader('t2installer','/usr/local/bin/hafthios-install').load_module()
m.live_root=lambda: True
m.read_disks=lambda: m.t2_targets(json.loads(m.command(['lsblk','--json','--bytes','--tree','--output',m.COLUMNS+',FSTYPE,LABEL,PARTTYPE,PARTUUID,UUID,START,PTTYPE,TRAN,RM',LOOP])))
plan=m.make_plan(TARGET)
m.install({'token':plan['token'],'confirmation':plan['confirmation'],'password':'CI-t2-password','settings':{'language':'sv','keyboard':'se'}})
'''.replace('LOOP',repr(loop)).replace('TARGET',repr(target)))
            run(['chroot',str(root),'python3','/var/tmp/t2-ci-install.py'])
            if run(['sfdisk','--dump',loop])!=table or digest(apple)!=apple_hash:
                raise RuntimeError('Apple partition or GPT changed')
            installed=work/'installed';installed.mkdir();run(['mount',target,str(installed)])
            try:
                assert (installed/'boot/vmlinuz-linux-t2').is_file()
                assert (installed/'boot/initramfs-linux-t2.img').is_file()
                assert (installed/'etc/hafthios-t2-installed').is_file()
                # CI-only serial probe, never included in the shipped ISO.
                service=installed/'etc/systemd/system/t2-ci-installed.service'
                service.write_text('[Unit]\nAfter=local-fs.target\n[Service]\nType=oneshot\nExecStart=/bin/sh -c "test -f /etc/hafthios-t2-installed && test $(findmnt -n -o FSTYPE /) = ext4 && echo HAFTHIOS_T2_INSTALLED_BOOT_OK > /dev/ttyS0"\n[Install]\nWantedBy=multi-user.target\n')
                (installed/'etc/systemd/system/multi-user.target.wants/t2-ci-installed.service').symlink_to('../t2-ci-installed.service')
            finally:run(['umount',str(installed)])
            run(['mount',efi,str(esp)])
            try:assert (esp/'EFI/APPLE/preserved.bin').read_bytes()==b'APPLE_EFI_MUST_SURVIVE'
            finally:run(['umount',str(esp)])
            print('HAFTHIOS_T2_PARTITION_INSTALL_TEST_OK (GPT/Apple-shaped bytes preserved)',flush=True)
        finally:
            for path in reversed(mounted):run(['umount','-R',str(path)])
            run(['losetup','--detach',loop])
        variables=work/'VARS.fd';shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd',variables)
        serial=Path('t2-installed-serial.log').resolve();serial.unlink(missing_ok=True)
        process=subprocess.Popen(['qemu-system-x86_64','-machine','q35','-m','4096','-smp','2',
            '-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
            '-drive','if=pflash,format=raw,file='+str(variables),
            '-drive','if=virtio,format=raw,file='+str(image),'-display','none',
            '-serial','file:'+str(serial),'-no-reboot','-net','none'])
        try:
            deadline=time.monotonic()+360
            while time.monotonic()<deadline:
                if serial.exists() and 'HAFTHIOS_T2_INSTALLED_BOOT_OK' in serial.read_text(errors='replace'):
                    print('HAFTHIOS_T2_INSTALLED_UEFI_BOOT_OK (VM only)',flush=True);break
                if process.poll() is not None:raise RuntimeError('Installed VM exited')
                time.sleep(2)
            else:raise RuntimeError('Installed disk did not reach ext4 root readiness without ISO')
        finally:
            process.terminate();process.wait(timeout=15)


if __name__=='__main__':verify(sys.argv[1])
