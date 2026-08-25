# -*- coding: utf-8 -*-
"""
補 `assets/resources/furniture/` 的 .meta（Cocos Creator 沒開時不會自動匯入）。

格式照同資料夾既有的 meta 抄：type=texture、redirect 到 @6c48a 子資產 ——
`GameArt` 是 `resources.load(path, ImageAsset)` 再自己包 SpriteFrame，
所以不需要 sprite-frame 子資產。濾鏡用 **nearest**（貨架是像素畫，linear 會糊）。

已經有 meta 的檔案**沿用原本的 uuid**，只把濾鏡換成 nearest；新檔案的 uuid 固定在
a9000000-00XX 這一段（同 witch8/town 手工 meta 的作法），重跑不會變。
"""
import json, os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'assets', 'resources', 'furniture')


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


def main():
    names = sorted(f[:-4] for f in os.listdir(DIR) if f.endswith('.png'))
    nxt = 1
    used = set()
    for n in names:
        mp = os.path.join(DIR, n + '.png.meta')
        if os.path.exists(mp):
            used.add(json.load(open(mp, encoding='utf-8'))['uuid'])
    for n in names:
        mp = os.path.join(DIR, n + '.png.meta')
        if os.path.exists(mp):
            uuid = json.load(open(mp, encoding='utf-8'))['uuid']
            tag = '沿用'
        else:
            while True:
                uuid = 'a9000000-%04x-4a90-8b90-a90000000%03x' % (nxt, nxt)
                nxt += 1
                if uuid not in used:
                    break
            used.add(uuid)
            tag = '新增'
        with open(mp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(png_meta(n, uuid), f, indent=2, ensure_ascii=False)
            f.write('\n')
        print(f'{tag} {n:14s} {uuid}')
    print(f'共 {len(names)} 個 meta')


if __name__ == '__main__':
    main()
