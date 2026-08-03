# -*- coding: utf-8 -*-
"""
手工生 resources/witch8/ 的 .meta（Cocos Creator 沒開，不會自動匯入）。

格式照 resources/villagers/*.png.meta 抄：type=texture、redirect 到 @6c48a 子資產，
GameArt 是用 `resources.load(path, ImageAsset)` 再自己包 SpriteFrame，所以不需要
sprite-frame 子資產。⚠️ 濾鏡改 **nearest**：這批是像素畫，linear 會糊掉。

uuid 固定在 a8000000-00XX 這一段（同 town/candy 手工 meta 的作法），重跑不會變。
"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

DIR = r"D:\Crash\witch-shop\assets\resources\witch8"
FOLDER_UUID = "a8000000-0000-4a80-8b80-a80000000000"
FILES = ["base", "sleep", "green", "green-sleep", "brown", "brown-sleep", "ivory", "ivory-sleep"]

def png_meta(name, uuid):
    return {
        "ver": "1.0.27",
        "importer": "image",
        "imported": True,
        "uuid": uuid,
        "files": [".json", ".png"],
        "subMetas": {
            "6c48a": {
                "importer": "texture",
                "uuid": uuid + "@6c48a",
                "displayName": name,
                "id": "6c48a",
                "name": "texture",
                "userData": {
                    "wrapModeS": "clamp-to-edge",
                    "wrapModeT": "clamp-to-edge",
                    "minfilter": "nearest",
                    "magfilter": "nearest",
                    "mipfilter": "none",
                    "anisotropy": 0,
                    "isUuid": True,
                    "imageUuidOrDatabaseUri": uuid,
                    "visible": False,
                },
                "ver": "1.0.22",
                "imported": True,
                "files": [".json"],
                "subMetas": {},
            }
        },
        "userData": {
            "type": "texture",
            "fixAlphaTransparencyArtifacts": False,
            "hasAlpha": True,
            "redirect": uuid + "@6c48a",
        },
    }

def write(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("  ", os.path.basename(path))

print("寫出 meta：")
write(DIR + ".meta", {"ver": "1.2.0", "importer": "directory", "imported": True,
                      "uuid": FOLDER_UUID, "files": [], "subMetas": {}, "userData": {}})
for i, name in enumerate(FILES):
    uuid = f"a8000000-{i+1:04d}-4a80-8b80-a800000{i+1:05d}"
    write(os.path.join(DIR, name + ".png.meta"), png_meta(name, uuid))
