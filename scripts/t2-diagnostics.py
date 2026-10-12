#!/usr/bin/env python3
"""Read-only hardware report; excludes serial numbers, MACs and journal contents."""
import json,subprocess,platform
from pathlib import Path

def command(args):
    try:
        r=subprocess.run(args,capture_output=True,text=True,timeout=15)
        return {'status':r.returncode,'output':r.stdout[:24000],'error':r.stderr[:1000]}
    except (OSError,subprocess.TimeoutExpired) as e:return {'unavailable':str(e)}
report={'kernel':platform.release(),'model':Path('/sys/class/dmi/id/product_name').read_text().strip() if Path('/sys/class/dmi/id/product_name').exists() else 'unknown'}
for name,args in {'pci':['lspci','-nnk'],'usb':['lsusb'],'modules':['lsmod'],'audio':['aplay','-l'],'graphics':['ls','/sys/class/drm'],'network':['nmcli','-f','DEVICE,TYPE,STATE','device'],'disks':['lsblk','-o','NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS']}.items():report[name]=command(args)
print(json.dumps(report,indent=2))
