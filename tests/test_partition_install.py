import copy
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

adapt=runpy.run_path('scripts/adapt-installer.py')['adapt']
source=adapt(Path('tests/fixtures/upstream-install.py').read_text())
namespace={'__name__':'installer_test'}
exec(compile(source,'adapted-installer','exec'),namespace)
ESP='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
APFS='7c3457ef-0000-11aa-aa11-00306543ecac'
BASIC='ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'

def disk():
    parts=[]
    for number,kind,fs,label,size in [(1,ESP,'vfat','EFI',314600000),
            (2,APFS,'apfs',None,120000000000),(3,BASIC,'exfat','HAFTHI',880240754688)]:
        parts.append({'path':f'/dev/nvme0n1p{number}','type':'part','parttype':kind,
            'fstype':fs,'label':label,'size':size,'start':number*1000000,
            'partuuid':f'part-{number}','uuid':f'fs-{number}','mountpoints':[None]})
    return {'path':'/dev/nvme0n1','type':'disk','pttype':'gpt','tran':'nvme',
        'size':1000558100480,'children':parts,'mountpoints':[None]}

class PartitionTests(unittest.TestCase):
    def targets(self,d=None,excluded=()):
        return namespace['t2_targets']({'blockdevices':[d or disk()]},excluded)

    def test_only_prepared_partition_offered(self):
        targets=self.targets()
        self.assertEqual([t['path'] for t in targets],['/dev/nvme0n1p3'])
        self.assertEqual(targets[0]['efi'],'/dev/nvme0n1p1')
        self.assertEqual(len(targets[0]['layout']),3)

    def test_usb_mounted_apple_missing_efi_missing_identity_rejected(self):
        for change in ('usb','mounted','no-apple','no-efi','no-identity','wrong-label','wrong-type','readonly'):
            d=disk()
            if change=='usb':d['tran']='usb'
            if change=='mounted':d['children'][1]['mountpoints']=['/mnt/apple']
            if change=='no-apple':d['children'][1]['parttype']=BASIC
            if change=='no-efi':d['children'][0]['fstype']='ext4'
            if change=='no-identity':d['children'][2]['partuuid']=None
            if change=='wrong-label':d['children'][2]['label']='DATA'
            if change=='wrong-type':d['children'][2]['parttype']=APFS
            if change=='readonly':d['ro']=True
            with self.subTest(change=change):self.assertEqual(self.targets(d),[])
        self.assertEqual(self.targets(excluded=['/dev/nvme0n1p1']),[])

    def test_partition_layout_change_invalidates_identity(self):
        original=self.targets()[0]
        d=disk();d['children'][1]['size']-=4096
        self.assertNotEqual(namespace['identity'](original),namespace['identity'](self.targets(d)[0]))

    def test_efi_conflict_aborts_before_format(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory);namespace['STATE']=state
            def command(args,**kwargs):
                if args[0]=='mount':(Path(args[-1])/'EFI/BOOT').mkdir(parents=True)
                return ''
            with patch.dict(namespace,command=command):
                with self.assertRaisesRegex(RuntimeError,'No partition was formatted'):
                    namespace['check_efi']('/dev/testefi')

    def test_no_partition_table_or_apple_format_commands_and_t2_boot_config(self):
        self.assertNotIn("'sfdisk'",source)
        self.assertNotIn("'mkfs.fat'",source)
        self.assertNotIn('--target=i386-pc',source)
        self.assertIn('vmlinuz-linux-t2',source)
        self.assertIn('MODULES=(t2bce_dma t2bce_core t2bce_vhci virtio_pci virtio_blk)',source)
        self.assertIn('apple_gmux.force_igd=1',source)
        self.assertIn('/usr/local/bin/hafthios-t2-greeter',source)

    def test_unexpected_upstream_source_rejected(self):
        with self.assertRaises(ValueError):adapt(source)
