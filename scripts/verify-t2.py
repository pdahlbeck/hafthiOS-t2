#!/usr/bin/env python3
import subprocess,tempfile,time,sys,shutil
from pathlib import Path
iso=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)
    subprocess.run(['xorriso','-osirrox','on','-indev',str(iso),'-extract','/arch',str(p/'arch')],check=True)
    assert (p/'arch/boot/x86_64/vmlinuz-linux-t2').is_file()
    assert (p/'arch/boot/x86_64/initramfs-linux-t2.img').is_file()
    subprocess.run(['unsquashfs','-no-xattrs','-no-progress','-d',str(p/'root'),str(p/'arch/x86_64/airootfs.sfs')],check=True)
    root=p/'root'
    assert (root/'etc/hafthios-t2-live').is_file()
    for module in ('t2bce_dma','t2bce_core','t2bce_vhci'):
        assert list((root/'usr/lib/modules').rglob(module+'.ko*')),module
    for name in ('hafthios-install','hafthios-update'):
        r=subprocess.run(['python3',str(root/'usr/local/bin'/name)],capture_output=True)
        assert r.returncode!=0
    print('HAFTHIOS_T2_IMAGE_TEST_OK',flush=True)
    import runpy
    runpy.run_path('scripts/verify-t2-install.py')['verify'](root)
    firmware=Path('/usr/share/OVMF/OVMF_CODE_4M.fd')
    template=Path('/usr/share/OVMF/OVMF_VARS_4M.fd')
    if not firmware.is_file() or not template.is_file():
        raise RuntimeError('OVMF code/variables firmware pair is missing')
    variables=p/'OVMF_VARS.fd'
    shutil.copyfile(template,variables)
    Path('t2-serial.log').unlink(missing_ok=True)
    args=['qemu-system-x86_64','-machine','q35','-m','4096','-smp','2','-drive','if=pflash,format=raw,readonly=on,file='+str(firmware),'-drive','if=pflash,format=raw,file='+str(variables),'-cdrom',str(iso),'-boot','d','-display','none','-serial','file:t2-serial.log','-no-reboot','-net','none']
    process=subprocess.Popen(args)
    try:
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            log=Path('t2-serial.log')
            if log.exists() and 'HAFTHIOS_T2_LIVE_READY' in log.read_text(errors='replace'):
                print('HAFTHIOS_T2_UEFI_BOOT_OK (VM only; physical T2 untested)');break
            if process.poll() is not None:raise RuntimeError('QEMU exited before readiness')
            time.sleep(2)
        else:raise RuntimeError('T2 kernel UEFI boot did not reach live readiness')
    finally:
        process.terminate();process.wait(timeout=15)
