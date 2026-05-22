"""打包脚本 - 从 VERSION 文件读取版本号，生成安装脚本，打包 exe"""

import subprocess
import sys
import os
import re


def get_version():
    """从 VERSION 文件读取版本号"""
    version_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    with open(version_path, "r") as f:
        return f.read().strip()


def generate_version_info(version, project_dir):
    """生成 PyInstaller Windows 版本信息文件"""
    nums = version.split(".")
    while len(nums) < 4:
        nums.append("0")
    version_tuple = ",".join(nums[:4])

    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u"080404b0",
          [
            StringStruct(u"CompanyName", u"NetSwitch"),
            StringStruct(u"FileDescription", u"NetSwitch - 网络配置切换工具"),
            StringStruct(u"FileVersion", u"{version}"),
            StringStruct(u"InternalName", u"NetSwitch"),
            StringStruct(u"OriginalFilename", u"NetSwitch.exe"),
            StringStruct(u"ProductName", u"NetSwitch"),
            StringStruct(u"ProductVersion", u"{version}"),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u"Translation", [2052, 1200])])
  ]
)
"""
    path = os.path.join(project_dir, "version_info.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def generate_installer_iss(version, project_dir):
    """从模板生成 installer.iss"""
    template_path = os.path.join(project_dir, "installer.iss")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    content = template.replace("{{VERSION}}", version)

    out_path = os.path.join(project_dir, "installer_output.iss")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def build():
    version = get_version()
    project_dir = os.path.dirname(os.path.abspath(__file__))

    # 生成版本信息文件
    vi_path = generate_version_info(version, project_dir)

    # 生成 installer.iss
    iss_path = generate_installer_iss(version, project_dir)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--icon=icon.ico",
        "--manifest=app.manifest",
        "--name=NetSwitch",
        "--add-data=icon.ico;.",
        "--add-data=tray_16.png;.",
        "--add-data=tray_32.png;.",
        "--add-data=VERSION;.",
        f"--version-file={vi_path}",
        "main.py",
    ]

    print(f"打包 NetSwitch v{version} ...")
    result = subprocess.run(cmd, cwd=project_dir)

    # 清理临时文件
    for f in [vi_path]:
        if os.path.exists(f):
            os.remove(f)

    if result.returncode == 0:
        print(f"\n打包成功！")
        print(f"  exe:  dist/NetSwitch.exe")
        print(f"  安装脚本: {iss_path}")
        print(f"\n制作安装包: iscc {iss_path}")
    else:
        print("\n打包失败！")
        sys.exit(1)


if __name__ == "__main__":
    build()
