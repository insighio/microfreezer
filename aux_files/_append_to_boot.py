from _todefrost import package_md5sum

md5 = None
try:
    with open('/flash/package.md5') as f:
        md5 = f.read().strip()
except Exception as e:
    pass

if md5 != package_md5sum.md5sum:
    print("package md5 changed....defrosting...")
    from _todefrost import microwave
    microwave.defrost()
    import machine
    machine.reset()
