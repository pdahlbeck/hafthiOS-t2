#!/usr/bin/env python3
"""Read-only hardware report; excludes serial numbers, MACs and journal contents."""
import json,subprocess,platform
from pathlib import Path

def command(args):
    try:
        r=subprocess.run(args,capture_output=True,text=True,timeout=15)
        return {'status':r.returncode,'output':r.stdout[:24000],'error':r.stderr[:1000]}
    except (OSError,subprocess.TimeoutExpired) as e:return {'unavailable':str(e)}
def read(path):
    try:return path.read_text().strip()
    except OSError:return None

def hardware(sysfs=Path('/sys')):
    displays=[]
    for connector in sorted((sysfs/'class/drm').glob('card*-*')):
        status=read(connector/'status')
        if status is not None:
            displays.append({'connector':connector.name,'status':status,
                             'modes':read(connector/'modes')})
    power=[]
    for supply in sorted((sysfs/'class/power_supply').glob('*')):
        # Do not collect serial_number, manufacturer or model_name.
        power.append({'device':supply.name,**{field:read(supply/field)
            for field in ('type','status','capacity','online')}})
    return {'model':read(sysfs/'class/dmi/id/product_name') or 'unknown',
            'uefi':(sysfs/'firmware/efi').is_dir(),'displays':displays,'power':power,
            'sleep_states':read(sysfs/'power/state'),
            'sleep_modes':read(sysfs/'power/mem_sleep')}

def main():
    report={'schema':2,'kernel':platform.release(),**hardware()}
    probes={'pci':['lspci','-nnk'],'usb':['lsusb'],'modules':['lsmod'],
        'audio':['aplay','-l'],'network':['nmcli','-f','DEVICE,TYPE,STATE','device'],
        'disks':['lsblk','-o','NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS'],
        'fan_service':['systemctl','is-active','t2fanrd.service']}
    for name,args in probes.items():report[name]=command(args)
    # Detection must never be presented as physical functional verification.
    report['manual_tests']={
        'wifi':'Connect to Wi-Fi and open a webpage.',
        'audio':'Play audio quietly; verify speakers and headphones separately.',
        'input':'Verify Swedish keys, clicking, scrolling and dragging.',
        'sleep':'Save work, suspend, wake, then recheck display, input and network.'}
    report['installation_verified']=False
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
