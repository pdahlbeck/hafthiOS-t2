import runpy,unittest,tempfile
from pathlib import Path
prepare=runpy.run_path('scripts/prepare-t2.py')['prepare']
class T2Tests(unittest.TestCase):
 def test_live_install_and_updater_are_disabled_and_t2_kernel_is_selected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'scripts').mkdir()
   (p/'scripts/build-iso.sh').write_text('iso_name="hafthios-prototype"\niso_label="HAFTHIOS"\nfile_permissions+=(\n)\nlinux\n# Use the normal Arch repositories\n')
   (p/'scripts/package-inventory.py').write_text('initramfs-linux.img')
   (p/'docs').mkdir()
   (p/'docs/file-guide.json').write_text('{"files":[]}')
   prepare(p)
   s=(p/'scripts/build-iso.sh').read_text()
   self.assertIn('linux-t2',s);self.assertNotIn('\nlinux\n',s)
   for name in ('hafthios-install','hafthios-update'):
    with self.assertRaises(SystemExit):runpy.run_path(str(p/'live/usr/local/bin'/name))
   self.assertIn('intel_iommu=on',s);self.assertIn('pm_async=off',s)
   self.assertIn('t2bce_vhci',s)
   self.assertIn('https://mirror.funami.tech/arch-mact2/os/x86_64',s)
   self.assertNotIn('/os/$arch',s)
