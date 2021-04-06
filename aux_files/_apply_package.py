import uctypes
import uos
import sys
import uerrno

###############################
# utarfile from: https://github.com/micropython/micropython-lib/blob/master/utarfile/utarfile.py
# http://www.gnu.org/software/tar/manual/html_node/Standard.html
TAR_HEADER = {
    "name": (uctypes.ARRAY | 0, uctypes.UINT8 | 100),
    "size": (uctypes.ARRAY | 124, uctypes.UINT8 | 11),
}

DIRTYPE = "dir"
REGTYPE = "file"


def roundup(val, align):
    return (val + align - 1) & ~(align - 1)


class FileSection:

    def __init__(self, f, content_len, aligned_len):
        self.f = f
        self.content_len = content_len
        self.align = aligned_len - content_len

    def read(self, sz=65536):
        if self.content_len == 0:
            return b""
        if sz > self.content_len:
            sz = self.content_len
        data = self.f.read(sz)
        sz = len(data)
        self.content_len -= sz
        return data

    def readinto(self, buf):
        if self.content_len == 0:
            return 0
        if len(buf) > self.content_len:
            buf = memoryview(buf)[:self.content_len]
        sz = self.f.readinto(buf)
        self.content_len -= sz
        return sz

    def skip(self):
        sz = self.content_len + self.align
        if sz:
            buf = bytearray(16)
            while sz:
                s = min(sz, 16)
                self.f.readinto(buf, s)
                sz -= s


class TarInfo:

    def __str__(self):
        return "TarInfo(%r, %s, %d)" % (self.name, self.type, self.size)


class TarFile:

    def __init__(self, name=None, byteData=None):
        self.b = byteData
        self.i = 0
        self.f = name

        if self.f:
            self.f = open(name, "rb")
        self.subf = None

    def next(self):
        if self.subf:
            self.subf.skip()

        buf = None
        if self.f:
            buf = self.f.read(512)
        elif self.b:
            buf = self.b[self.i:512]
            self.i += 512

        if not buf:
            return None

        h = uctypes.struct(uctypes.addressof(buf), TAR_HEADER, uctypes.LITTLE_ENDIAN)

        # Empty block means end of archive
        if h.name[0] == 0:
            return None

        d = TarInfo()
        d.name = str(h.name, "utf-8").rstrip("\0")
        d.size = int(bytes(h.size), 8)
        d.type = [REGTYPE, DIRTYPE][d.name[-1] == "/"]
        self.subf = d.subf = FileSection(self.f, d.size, roundup(d.size, 512))
        return d

    def __iter__(self):
        return self

    def __next__(self):
        v = self.next()
        if v is None:
            raise StopIteration
        return v

    def extractfile(self, tarinfo):
        return tarinfo.subf


def readFromFile(source):
    try:
        f = open(source, "rb")
        contents = f.read()
        f.close()
        print("file [{}] read finished.".format(source))
        return contents
    except Exception as e:
        print("file [{}] read failed.".format(source))
        sys.print_exception(e)
        return ""


def mkdir(directoryPath):
    try:
        uos.mkdir(directoryPath)
        print("Made directory: {}".format(directoryPath))
    except OSError as e:
        if e.args[0] != uerrno.EEXIST:
            print("directory {} failed".format(directoryPath))
            sys.print_exception(e)


def writeToFile(destination, content):
    try:
        out_file = open(destination, "wb")
        out_file.write(content)
        out_file.close()
        return True
        print("file [{}] write finished.".format(destination))
    except Exception as e:
        print("file [{}] write failed.".format(destination))
        sys.print_exception(e)
        return False


# https://github.com/micropython/micropython-lib/blob/eae01bd4e4cd1b22d9ccfedbd6bf9d879f64d9bd/shutil/shutil.py#L11
def copyfileobj(src, dest, length=512):
    if hasattr(src, "readinto"):
        buf = bytearray(length)
        while True:
            sz = src.readinto(buf)
            if not sz:
                break
            if sz == length:
                dest.write(buf)
            else:
                b = memoryview(buf)[:sz]
                dest.write(b)
    else:
        while True:
            buf = src.read(length)
            if not buf:
                break
            dest.write(buf)
    dest.close()

###############################


flashRootFolder = "/flash"

is_compressed = False
package_file = None
for f in uos.listdir(flashRootFolder):
    if f.endswith(".tar"):
        package_file = flashRootFolder + "/" + f
        break
    if f.endswith(".tar.gz"):
        package_file = flashRootFolder + "/" + f
        is_compressed = True
        break

print("package file found: {}, is_compressed: {}".format(package_file, is_compressed))

if package_file:
    t = None
    try:
        if is_compressed:
            data = readFromFile(package_file)
            import uzlib
            byteData = uzlib.decompress(data[8:])
            compressed_file_name = package_file
            package_file = "{}.tar".format(package_file.split(".")[0])
            if writeToFile(package_file, byteData):
                print("removing gzip file...")
                uos.remove(compressed_file_name)
            # clear memory
            byteData = bytearray(0)
            print("package file decompressed")

        t = TarFile(name=package_file)

        print("tar file opened: " + package_file)

        for i in t:
            if i.name != "././@PaxHeader":
                print(i)
            if i.type == DIRTYPE:
                mkdir(i.name)
            else:
                f = t.extractfile(i)
                copyfileobj(f, open(i.name, "w"))
        if t:
            print("removing tar file...")
            uos.remove(package_file)

        print("Operation completed.")

        print("about to reset...")
        import machine
        machine.reset()
    except Exception as e:
        print("error unpacking update package: {}".format(package_file))
        sys.print_exception(e)
