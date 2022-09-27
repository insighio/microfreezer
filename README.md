# microfreezer

microfreezer is a handy tool providing an alternative update method for micropython-enabled microcontrollers, by packaging a project into either an update package or into the 'frozen' part of the firmware regardless the included file types.

![microfreezer-scheme-4](https://user-images.githubusercontent.com/550020/114547587-48178e80-9c67-11eb-8c41-c2050f63ca33.png)

# Method 1: freezing the unfreezable

Having the source code of the micropython firmware, any Python source code added in `esp32/frozen` will be compiled and added with the firmware. In the case of Pycom devices, that folder is at `pycom-micropython-sigfox/esp32/frozen` and includes multiple other folders with necessary code. The suggested folder for placing custom Python files is `pycom-micropython-sigfox/esp32/frozen/Custom/`. More info on this can be found here: https://docs.pycom.io/advance/frozen/

Consider having the following project folder that needs to be flashed into multiple microcontrollers.

```
|- .git
|- lib
|  |- lib_a.py
|  |- README.md
|- html
|  |- index.html
|  |- favicon.ico
|- main.py
|- boot.py
|- README
|- LICENSE
```

## prepare the configuration file

microfreezer provides an alternative way of packing these files into the firmware. First of, prepare the configuration file by defining the following keys:

1. `excludeList`: select irrelevant files that should be ignored. (if not provided, all files will be included)
    * "README.md", "README", "LICENSE", ".git" files
1. `directoriesKeptInFrozen`: first select which folders of the project will be added in the `frozen` modules to be used directly by the user code. (if not provided, no files will be kept in `frozen`)
    * "lib" folder contents
1. `enableZlibCompression`: by default is enabled. kept for cases of zlib unavailability. Turning it off results to bigger packages.
1. `targetESP32`: flag to set the build configurations for ESP32 devices
1. `targetPycom`: flag to set the build configurations for Pycom devices
1. the rest of the files will be converted into a compressed format, packed into the `frozen` modules and will be ready to be exported to the user space "ex. /flash or / paths".
1. `minify`: minify if possible the .py source files. requires _pip install python-minifier_

Putting these into a configuration file named `config.json`:

```json
{
  "excludeList": [
             "README",
             "README.md",
             "LICENSE",
             ".git"],
  "directoriesKeptInFrozen": ["lib"],
  "enableZlibCompression": true,
  "flashRootFolder": "/",
  "minify": true,
  "minifyExcludeFolderList": ["~/path/to/folder/to/exclude/from/minify"],
  "targetESP32": true,
  "targetPycom": false  
}
```

## run microfreezer

Ready to run microfreezer. The `config.json` needs to be present at the same path as microfreezer. If not, default values will be used as indicated above.

```bash
#python3 microfreezer.py (-v: verbose output) <project-folder-path> <output-folder-path>
python3 microfreezer.py ~/projects/my_new_project ~/projects/my_new_project_packed

#or

python3 microfreezer.py -s ~/projects/my_new_project -d ~/projects/my_new_project_packed
```

The output is split into two folders `Base` and `Custom` based on the directory design of Pycom devices:

```
|- Base
|  |- _main.py
|- Custom
|  |- lib_a.py
|  |- _todefrost
|  |  |- base64_0.py
|  |  |- base64_1.py
|  |  |- base64_2.py
|  |  |- base64_3.py
|  |  |- microwave.py
|  |  |- package_md5sum.py
```

Copy both folders to `pycom-micropython-sigfox/esp32/frozen` folder and rebuild firmware. Now it is ready to be flashed.

During the boot of the device:
* _main.py checks if md5sum of the files in "_todefrost" path has changed
* if yes, runs "microwave" module that reads each file in "_todefrost" and unpacks each file to the desired destination in user space (ex. /flash)
* store the md5sum of new packages at "/" or "/flash" for future checks on boot.

## Notes on output files

* `Base/_main.py`: the file is automatically called by the device before calling use space main.py.
* `Custom/lib_a.py`: `lib_a` is a module that was part of the `directoriesKeptInFrozen`. This means that it will be globally available as a frozen module.
* `Custom/_todefrost`: the folder contains 3 main file types
  * `base64_<id>.py`: Each such file is a Python source file with two variables:
    * `PATH`: the path where it needs to be extracted which is a concatenation of target's root folder from the configuration file (targetESP32, targetPycom) and the relative path of the file in the project.
    * `DATA`: the contents of the file converted to Base64 and compressed with `zlib`.
  * `package_md5sum.py`: an md5sum of the all the base64 Python files in `_todefrost`
  * `microwave.py`: the script responsible of decompressing and converting the `DATA` of each base64 file and placing it to the destination folder defined by `PATH`

# Method 2: Creating a simple update package with user code.

Apart from embedding a project into the firmware, an alternative way would be to pack all files that do not belong to `frozen` modules into one packet, send it to the device and unpack it.

## prepare the configuration file

The configuration file is exactly the same as (Method 1). The only difference is that whatever files are found in the defined folder from `directoriesKeptInFrozen` are ignored.

## run microfreezer

Ready to run microfreezer. The `config.json` needs to be present at the same path as microfreezer. If not, default values will be used as indicated above.

```bash
#python3 microfreezer.py (-v: verbose output) <project-folder-path> <output-folder-path>
python3 microfreezer.py --ota-package ~/projects/my_new_project ~/projects/my_new_project_packed

#or

python3 microfreezer.py --ota-package -s ~/projects/my_new_project -d ~/projects/my_new_project_packed

```

The output folder now contains 2 files:

```
|- _apply_package.py
|- 1234567890abcdef1234567890abcdef.tar.gz
```

The `tar.gz` can be send to the required devices and by importing the `_apply_package.py` at the same folder as the package, it...applies the package :P

## Notes on output files

* `<md5>.tar.gz`: the zipped tar file that contains all required files and folders to be applied
* `_apply_package.py`: searches for a `.tar` or `.tar.gz` file, decompresses it if needed, and untars the files using as base folder defined by the target in the configuration file (targetESP32, targetPycom).


# Future work

* auto-validation of package MD5 before or after decompression for package validity check
