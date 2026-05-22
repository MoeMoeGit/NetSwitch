"""打包脚本 - 使用 PyInstaller 打包为单个 exe"""

import subprocess
import sys
import os
import re


def get_version():
    """从 main.py 读取版本号"""
    main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        match = re.search(r'__version__\s*=\s*"(.+?)"', f.read())
    return match.group(1) if match else "0.0.0"


def build():
    """执行打包"""
    version = get_version()
    project_dir = os.path.dirname(os.path.abspath(__file__))

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--icon=icon.ico",
        "--manifest=app.manifest",
        f"--name=NetSwitch",
        "--add-data=icon.ico;.",
        "--add-data=tray_16.png;.",
        "--add-data=tray_32.png;.",
        f"--version-file=version_info.txt",
        "main.py",
    ]

    # 生成 version_info.txt（PyInstaller Windows 版本信息）
    version_nums = version.split(".")
    while len(version_nums) < 4:
        version_nums.append("0")
    version_tuple = ",".join(version_nums[:4])

    version_info = f"""# UTF-8
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
    vi_path = os.path.join(project_dir, "version_info.txt")
    with open(vi_path, "w", encoding="utf-8") as f:
        f.write(version_info)

    print(f"打包 NetSwitch v{version} ...")
    result = subprocess.run(cmd, cwd=project_dir)

    # 清理临时文件
    for f in [vi_path]:
        if os.path.exists(f):
            os.remove(f)

    if result.returncode == 0:
        print(f"\n打包成功！输出：dist/NetSwitch.exe")
    else:
        print("\n打包失败！")
        sys.exit(1)


if __name__ == "__main__":
    build()
